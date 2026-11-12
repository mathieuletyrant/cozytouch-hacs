"""Water heater entity for Atlantic Cozytouch integration."""

from __future__ import annotations

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import CozytouchConfigEntry, Hub, add_capability_entities
from .infos import CapabilityType
from .model import CozytouchDeviceType
from .sensor import CozytouchSensor

# The ids the tank's page in the app is drawn from. See docs/decisions.md,
# *A water heater entity for the tanks*.
MODE_CAPABILITY_ID = 87
SETPOINT_CAPABILITY_ID = 231
TANK_TEMPERATURE_CAPABILITY_ID = 265
SETPOINT_MIN_CAPABILITY_ID = 253
SETPOINT_MAX_CAPABILITY_ID = 252

DEFAULT_MIN_TEMPERATURE = 50.0
DEFAULT_MAX_TEMPERATURE = 65.0


def water_heater_for(coordinator: Hub, capability, **kwargs):
    """One entity per tank, built beside its mode select."""
    if capability.capabilityId != MODE_CAPABILITY_ID:
        return []
    if coordinator.get_model_infos().type != CozytouchDeviceType.WATER_HEATER:
        return []
    if coordinator.get_capability_value(SETPOINT_CAPABILITY_ID, None) is None:
        return []
    return CozytouchWaterHeater(
        coordinator=coordinator, capability=capability, **kwargs
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    add_capability_entities(
        config_entry,
        async_add_entities,
        {CapabilityType.SELECT: water_heater_for},
    )


def _as_float(value) -> float | None:
    """A reading as a number, None when the device sent none."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class CozytouchWaterHeater(WaterHeaterEntity, CozytouchSensor):
    """The tank : its setpoint, its mode, and the water in it."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_target_temperature_step = 1

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
    ) -> None:
        """Initialize a water heater entity."""
        super().__init__(
            coordinator=coordinator,
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=(
                f"{DOMAIN}_{config_uniq_id}_water_heater_{capability.capabilityId!s}"
            ),
            translation_key="hot_water",
            icon="mdi:water-boiler",
        )
        self._modes: dict[int, str] = dict(
            self.coordinator.get_model_infos().get("HeatingModes", {})
        )
        self._attr_operation_list = list(self._modes.values())
        self._attr_current_operation = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_min_temp = DEFAULT_MIN_TEMPERATURE
        self._attr_max_temp = DEFAULT_MAX_TEMPERATURE

    def _read(self, capabilityId: int) -> float | None:
        return _as_float(self.coordinator.get_capability_value(capabilityId, None))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Read the tank back from the hub."""
        lowest = self._read(SETPOINT_MIN_CAPABILITY_ID)
        highest = self._read(SETPOINT_MAX_CAPABILITY_ID)
        if lowest is not None and highest is not None and lowest < highest:
            self._attr_min_temp = lowest
            self._attr_max_temp = highest

        self._attr_target_temperature = self._read(SETPOINT_CAPABILITY_ID)
        self._attr_current_temperature = self._read(TANK_TEMPERATURE_CAPABILITY_ID)

        mode = self._read(MODE_CAPABILITY_ID)
        self._attr_current_operation = (
            None if mode is None else self._modes.get(int(mode))
        )

        self._attr_available = self.coordinator.online
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        """Write the setpoint the temperature number writes."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        temperature = max(self.min_temp, min(float(temperature), self.max_temp))
        await self.coordinator.set_capability_value(
            SETPOINT_CAPABILITY_ID, str(temperature)
        )
        await self.coordinator.async_request_refresh()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Write the mode the mode select writes."""
        for value, mode in self._modes.items():
            if mode == operation_mode:
                await self.coordinator.set_capability_value(
                    MODE_CAPABILITY_ID, str(value)
                )
                await self.coordinator.async_request_refresh()
                return
