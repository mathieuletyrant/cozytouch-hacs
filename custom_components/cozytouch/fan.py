"""Fans for Atlantic Cozytouch integration.

Air circulation is one thing the hardware does and three entities the
integration used to expose : a switch, a speed, and a duration. Home Assistant
has a word for "runs, at a speed", and a card and a voice assistant that know
it. See docs/decisions.md.
"""

from __future__ import annotations

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN
from .hub import CozytouchConfigEntry, CozytouchDeviceEntity, Hub

# The switch, and the speed beside it. The duration and what is left of it
# stay their own entities : they are a setting and a reading, not a fan.
AIR_CIRCULATION = 102024
AIR_CIRCULATION_SPEED = 102004


# config flow setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    for subentry_id in config_entry.subentries:
        hub = config_entry.runtime_data.hubs[subentry_id]

        if hub.get_capability_value(AIR_CIRCULATION, None) is None:
            continue

        async_add_entities(
            [CozytouchAirCirculationFan(coordinator=hub, config_uniq_id=subentry_id)],
            True,
            config_subentry_id=subentry_id,
        )


class CozytouchAirCirculationFan(CozytouchDeviceEntity, FanEntity):
    """The air circulation, as the thing that blows air that it is."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "air_circulation"

    def __init__(self, coordinator: Hub, config_uniq_id: str) -> None:
        """Initialize the air circulation fan."""
        super().__init__(coordinator)

        self._device_uniq_id = config_uniq_id
        self._attr_unique_id = f"{DOMAIN}_{config_uniq_id}_air_circulation_fan"

        # The speeds this model names, in the order they climb. A model that
        # names none leaves a fan that only runs or does not.
        self._speeds: list[str] = [
            str(value)
            for value in sorted(
                coordinator.get_model_infos().get("AirCirculationSpeeds", {})
            )
        ]

        self._attr_supported_features = (
            FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        )
        if self._speeds and (
            coordinator.get_capability_value(AIR_CIRCULATION_SPEED, None) is not None
        ):
            self._attr_supported_features |= FanEntityFeature.SET_SPEED

    @property
    def _has_speeds(self) -> bool:
        """Whether this device lets a speed be asked for at all."""
        return FanEntityFeature.SET_SPEED in self._attr_supported_features

    @property
    def is_on(self) -> bool:
        """Whether the air is being circulated."""
        return self.coordinator.get_capability_value(AIR_CIRCULATION) == "1"

    @property
    def speed_count(self) -> int:
        """How many speeds this model has, which HA turns into percentages."""
        return len(self._speeds) or 1

    @property
    def percentage(self) -> int | None:
        """The speed as a percentage, which is the only thing HA speaks.

        A fan that is off reads 0 rather than its last speed: that is what
        makes a card's slider agree with the switch beside it.
        """
        if not self.is_on:
            return 0

        if not self._has_speeds:
            return 100

        value = self.coordinator.get_capability_value(AIR_CIRCULATION_SPEED, None)
        if value not in self._speeds:
            return None

        return ordered_list_item_to_percentage(self._speeds, value)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed, or stop when asked for none."""
        if percentage == 0:
            await self.async_turn_off()
            return

        if self._has_speeds:
            await self.coordinator.set_capability_value(
                AIR_CIRCULATION_SPEED,
                percentage_to_ordered_list_item(self._speeds, percentage),
            )

        if not self.is_on:
            await self.coordinator.set_capability_value(AIR_CIRCULATION, "1")

        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Start circulating, at a speed when one was asked for."""
        if percentage:
            await self.async_set_percentage(percentage)
            return

        await self.coordinator.set_capability_value(AIR_CIRCULATION, "1")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Stop circulating."""
        await self.coordinator.set_capability_value(AIR_CIRCULATION, "0")
        await self.coordinator.async_request_refresh()
