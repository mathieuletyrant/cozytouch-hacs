"""Switches for Atlantic Cozytouch integration."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SERVICE_OFF
from .hub import (
    CozytouchConfigEntry,
    CozytouchDeviceEntity,
    Hub,
    add_capability_entities,
    away_window_is_valid,
)
from .infos import CapabilityType
from .sensor import CozytouchSensor

_LOGGER = logging.getLogger(__name__)


# config flow setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up entry."""
    add_capability_entities(
        config_entry,
        async_add_entities,
        {
            CapabilityType.SWITCH: CozytouchSwitch,
            CapabilityType.AWAY_MODE_SWITCH: CozytouchAwayModeSwitch,
            CapabilityType.SYSTEM_SERVICE: CozytouchSystemSwitch,
        },
    )


class CozytouchSwitch(SwitchEntity, CozytouchSensor):
    """Class for switches."""

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        name: str | None = None,
    ) -> None:
        """Initialize a Switch entity."""
        capabilityId = capability.capabilityId
        super().__init__(
            coordinator=coordinator,
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=f"{DOMAIN}_{config_uniq_id}_switch_{capabilityId!s}",
            name=name,
        )
        self._state = False
        self._attr_device_class = SwitchDeviceClass.SWITCH

        self._value_off = capability.get("value_off", "0")
        self._value_on = capability.get("value_on", "1")

    @property
    def is_on(self) -> bool:
        """Return the state."""
        value = self.coordinator.get_capability_value(self._capability.capabilityId)
        self._state = value is not None and value == self._value_on
        return self._state

    async def async_turn_on(self):
        """Turn On method."""
        await self.coordinator.set_capability_value(
            self._capability.capabilityId,
            self._value_on,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        """Turn Off method."""
        await self.coordinator.set_capability_value(
            self._capability.capabilityId,
            self._value_off,
        )
        await self.coordinator.async_request_refresh()

    async def async_toggle(self) -> None:
        """Toggle the power on the zone."""
        if self._state:
            await self.async_turn_off()
        else:
            await self.async_turn_on()


class CozytouchAwayModeSwitch(CozytouchSwitch):
    """Class for away mode switch."""

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        name: str | None = None,
    ) -> None:
        """Initialize a Switch entity."""
        super().__init__(coordinator, capability, config_title, config_uniq_id, name)
        self._nb_ignore = 0
        self._value_pending = capability.get("value_pending", "2")

    @property
    def is_on(self) -> bool:
        """Return the state."""
        if self._nb_ignore > 0:
            self._nb_ignore = self._nb_ignore - 1
        else:
            value = self.coordinator.get_capability_value(
                self._capability.capabilityId
            )
            self._state = value is not None and value != self._value_off

        return self._state

    async def async_turn_on(self):
        """Turn On method."""
        timestampStart = self.coordinator.get_away_mode_start()
        timestampEnd = self.coordinator.get_away_mode_end()

        # What the pickers show while the absence is off : no start, or one
        # already past, is the next minute ; no end, or one not after the
        # start, is two days later.
        soon = datetime.now(tz=dt_util.DEFAULT_TIME_ZONE).timestamp() + 60
        if not timestampStart or timestampStart < soon:
            timestampStart = soon
        if not away_window_is_valid(timestampStart, timestampEnd):
            timestampEnd = timestampStart + (2 * 24 * 60 * 60)

        self._nb_ignore = 5
        self._state = True
        await self.coordinator.set_away_mode(int(timestampStart), int(timestampEnd))
        self._nb_ignore = 1

    async def async_turn_off(self):
        """Turn Off method."""
        self._nb_ignore = 5
        self._state = False
        await self.coordinator.set_away_mode(None, None)
        self._nb_ignore = 1


class CozytouchSystemSwitch(CozytouchDeviceEntity, SwitchEntity, RestoreEntity):
    """The whole system, on or at the app's general stop.

    Off is 102020 at 0, which every room follows. 102020 keeps nothing of the
    service it left, so on writes back the last one this entity saw running,
    kept across restarts. See docs/decisions.md.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:power"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize a switch entity."""
        super().__init__(coordinator)

        capabilityId = capability.capabilityId
        self._capability = capability
        self._device_uniq_id = config_uniq_id
        self._attr_translation_key = capability.name
        self._attr_unique_id = f"{DOMAIN}_{config_uniq_id}_switch_{capabilityId!s}"
        self._last_service: str | None = None
        self._remember_service()

    async def async_added_to_hass(self) -> None:
        """Take back the service seen before a restart, if none is seen yet."""
        await super().async_added_to_hass()
        if self._last_service is None:
            state = await self.async_get_last_state()
            if state is not None:
                self._last_service = state.attributes.get("last_service")

    def _remember_service(self) -> None:
        value = self.coordinator.get_capability_value(
            self._capability.capabilityId, None
        )
        if value is not None and str(value) != SERVICE_OFF:
            self._last_service = str(value)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._remember_service()
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool | None:
        """Whether the system runs a service at all."""
        value = self.coordinator.get_capability_value(
            self._capability.capabilityId, None
        )
        if value is None:
            return None
        return str(value) != SERVICE_OFF

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """The service turning on writes back, as the device numbers it."""
        if self._last_service is None:
            return None
        return {"last_service": self._last_service}

    def _service_to_restore(self) -> str:
        if self._last_service is not None:
            return self._last_service
        roomId = self._capability.get("roomServiceCapabilityId")
        if roomId is not None:
            room = self.coordinator.get_capability_value(roomId, None)
            if room is not None and str(room) != SERVICE_OFF:
                return str(room)
        raise HomeAssistantError(
            "No service to go back to: pick a mode on a room's climate entity"
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Run the system again, on the service it left."""
        await self.coordinator.set_capability_value(
            self._capability.capabilityId, self._service_to_restore()
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """The general stop."""
        await self.coordinator.set_capability_value(
            self._capability.capabilityId, SERVICE_OFF
        )
        await self.coordinator.async_request_refresh()
