"""Buttons for Atlantic Cozytouch integration.

The app's general stop : capability 102020 at off, which every room of the
system follows. Starting again is a mode on any room's climate entity, which
already writes 102020. See docs/decisions.md.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SERVICE_OFF
from .hub import (
    CozytouchConfigEntry,
    CozytouchDeviceEntity,
    Hub,
    add_capability_entities,
)
from .infos import CapabilityType


# config flow setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    add_capability_entities(
        config_entry,
        async_add_entities,
        {CapabilityType.SYSTEM_SERVICE: CozytouchSystemStopButton},
    )


class CozytouchSystemStopButton(CozytouchDeviceEntity, ButtonEntity):
    """Stops the whole system, from whichever room it is pressed on."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:power"

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize a button entity."""
        super().__init__(coordinator)

        capabilityId = capability.capabilityId
        self._capability = capability
        self._device_uniq_id = config_uniq_id
        self._attr_translation_key = capability.name
        self._attr_unique_id = f"{DOMAIN}_{config_uniq_id}_button_{capabilityId!s}"

    async def async_press(self) -> None:
        """Write off to the system's service."""
        await self.coordinator.set_capability_value(
            self._capability.capabilityId, SERVICE_OFF
        )
        await self.coordinator.async_request_refresh()
