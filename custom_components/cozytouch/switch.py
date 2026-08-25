"""Switches for Atlantic Cozytouch integration."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import CozytouchConfigEntry, Hub
from .sensor import CozytouchSensor

_LOGGER = logging.getLogger(__name__)


# config flow setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up entry."""
    # One device per subentry, and its entities are registered under it :
    # the subentry id is the identity that used to be the entry's own, back
    # when an entry meant a device.
    for subentry_id, subentry in config_entry.subentries.items():
        hub = config_entry.runtime_data.hubs[subentry_id]

        # Init switches
        switches = []
        capabilities = hub.get_capabilities_for_device()
        for capability in capabilities:
            if capability["type"] == "switch":
                switches.append(
                    CozytouchSwitch(
                        coordinator=hub,
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                    )
                )
            elif capability["type"] == "away_mode_switch":
                switches.append(
                    CozytouchAwayModeSwitch(
                        coordinator=hub,
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                    )
                )

        # Add the entities to HA
        if len(switches) > 0:
            async_add_entities(switches, True, config_subentry_id=subentry_id)


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
        capabilityId = capability["capabilityId"]
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
        value = self.coordinator.get_capability_value(self._capability["capabilityId"])
        self._state = value is not None and value == self._value_on
        return self._state

    async def async_turn_on(self):
        """Turn On method."""
        await self.coordinator.set_capability_value(
            self._capability["capabilityId"],
            self._value_on,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        """Turn Off method."""
        await self.coordinator.set_capability_value(
            self._capability["capabilityId"],
            self._value_off,
        )
        await self.coordinator.async_request_refresh()

    async def async_toggle(self) -> None:
        """Toggle the power on the zone."""
        if self._state:
            await self.async_turn_off()
        else:
            await self.async_turn_on()


class CozytouchAwayModeSwitch(SwitchEntity, CozytouchSensor):
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
        capabilityId = capability["capabilityId"]
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

        self._nb_ignore = 0

        self._value_off = capability.get("value_off", "0")
        self._value_on = capability.get("value_on", "1")
        self._value_pending = capability.get("value_pending", "2")

    @property
    def is_on(self) -> bool:
        """Return the state."""
        if self._nb_ignore > 0:
            self._nb_ignore = self._nb_ignore - 1
        else:
            value = self.coordinator.get_capability_value(
                self._capability["capabilityId"]
            )
            self._state = value is not None and value != self._value_off

        return self._state

    async def async_turn_on(self):
        """Turn On method.

        The window and the fallback for an unset one both live on the hub now,
        which is what the two services and the climate preset go through as
        well -- this used to hold the only copy of "a minute out, for two
        days", and a switch is a poor place for the household's idea of how
        long an absence lasts.
        """
        self._nb_ignore = 5
        self._state = True
        await self.coordinator.start_away_mode(
            self.coordinator.get_away_mode_start(),
            self.coordinator.get_away_mode_end(),
        )
        self._nb_ignore = 1
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        """Turn Off method."""
        self._nb_ignore = 5
        self._state = False
        await self.coordinator.stop_away_mode()
        self._nb_ignore = 1
        await self.coordinator.async_request_refresh()

    async def async_toggle(self) -> None:
        """Toggle the power on the zone."""
        if self._state:
            await self.async_turn_off()
        else:
            await self.async_turn_on()
