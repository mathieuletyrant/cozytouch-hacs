"""Sensors for Atlantic Cozytouch integration."""

from __future__ import annotations

import datetime
import json
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CozytouchCapabilityVariableType
from .hub import CozytouchConfigEntry, Hub, device_info_for
from .infos import CapabilityCategory, CapabilityType

_LOGGER = logging.getLogger(__name__)


# The value a healthy fault code reads as, and the one an empty slot carries.
# 0xFF fills a field of a slot that holds no fault: on the captures, whole
# accounts report the same `[0,255,0,4]` row repeated ten times, which is a
# ten-row empty list and not ten identical faults. See docs/decisions.md.
ERROR_CODE_HEALTHY = "OK"
ERROR_CODE_EMPTY_SLOT = 255


def decode_error_code(raw: str | None) -> str | None:
    """Turn a fault-code matrix into the codes that are actually active.

    The device reports a matrix of `[system, majorCode, minorCode, level]`
    rows (some firmwares carry a fifth field). A row is a fault only when it
    is neither all-zero (healthy) nor carrying the 0xFF empty-slot sentinel;
    an active row becomes `system_majorCode_minorCode_level`, the same key
    shape Atlantic's own fault table uses. Healthy reads as "OK", so the
    common case stops being a ten-row matrix nobody could read.

    The raw string is returned unchanged when it does not parse, so an
    encoding this does not expect is surfaced rather than swallowed. What no
    capture has ever shown is an active row, so the join is derived from the
    format, not from a decoded example -- and naming a code is a separate
    step this does not attempt, since that table is Atlantic's to ship.
    """
    if raw is None:
        return None

    try:
        matrix = json.loads(raw)
        rows = [[int(field) for field in row] for row in matrix]
    except (ValueError, TypeError):
        return raw

    codes = []
    for row in rows:
        if not any(row) or ERROR_CODE_EMPTY_SLOT in row:
            continue
        code = "_".join(str(field) for field in row)
        if code not in codes:
            codes.append(code)

    return ", ".join(codes) if codes else ERROR_CODE_HEALTHY


# config flow setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Modern (thru config entry) sensors setup."""
    _LOGGER.debug("%s: setting up sensor plateform", config_entry.title)
    # One device per subentry, and its entities are registered under it :
    # the subentry id is the identity that used to be the entry's own, back
    # when an entry meant a device.
    for subentry_id, subentry in config_entry.subentries.items():
        hub = config_entry.runtime_data.hubs[subentry_id]

        # Init sensors
        sensors = []
        capabilities = hub.get_capabilities_for_device()
        for capability in capabilities:
            if capability.type in (CapabilityType.STRING, CapabilityType.INT):
                # Use a CozytouchSensor for integers
                sensors.append(
                    CozytouchSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                    )
                )
            elif capability.type == CapabilityType.TEMPERATURE:
                # MEASUREMENT on everything that reads an instant value, here
                # and on the four branches below. Without a state class the
                # recorder keeps the state history and no long-term
                # statistics, so a temperature is gone from the charts after
                # the purge window -- ten days by default -- and min/max/mean
                # over a season is not available at all. The types that count
                # something instead (energy, water) declare TOTAL_INCREASING
                # further down.
                sensors.append(
                    CozytouchUnitSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    )
                )
            elif capability.type == CapabilityType.PRESSURE:
                sensors.append(
                    CozytouchUnitSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                        device_class=SensorDeviceClass.PRESSURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfPressure.BAR,
                    )
                )
            elif capability.type == CapabilityType.AWAY_MODE_TIMESTAMPS:
                for index, timestamp in enumerate(capability.timestamps):
                    sensors.append(
                        CozytouchAwayModeTimestampSensor(
                            capability=capability,
                            config_title=subentry.title,
                            config_uniq_id=subentry_id,
                            attr_uniq_id=f"{subentry_id}_{index}",
                            coordinator=hub,
                            name=timestamp.name,
                            icon=timestamp.icon,
                            separator=",",
                            timestamp_index=index,
                        )
                    )
            elif capability.type in (CapabilityType.SWITCH, CapabilityType.BINARY):
                sensors.append(
                    CozytouchBinarySensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                    )
                )
            elif capability.type == CapabilityType.AWAY_MODE_SWITCH:
                sensors.append(
                    CozytouchAwayModeSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                    )
                )
            elif capability.type == CapabilityType.SIGNAL:
                sensors.append(
                    CozytouchUnitSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
                    )
                )
            elif capability.type == CapabilityType.ENERGY:
                native_unit_of_measurement = capability.get(
                    "displayed_unit_of_measurement", UnitOfEnergy.WATT_HOUR
                )

                display_factor = 1.0
                if native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR:
                    display_factor = 0.001

                sensors.append(
                    CozytouchUnitSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                        device_class=SensorDeviceClass.ENERGY,
                        state_class=SensorStateClass.TOTAL_INCREASING,
                        native_unit_of_measurement=native_unit_of_measurement,
                        display_factor=display_factor,
                    )
                )
            elif capability.type == CapabilityType.VOLUME:
                sensors.append(
                    CozytouchUnitSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                        # VOLUME_STORAGE, not VOLUME: the three capabilities
                        # typed `volume` are how much water the tank holds or
                        # has left (258, 268, 270), never how much ran through
                        # it. The distinction is not cosmetic -- VOLUME accepts
                        # only the totalling state classes, so MEASUREMENT on
                        # it is the combination Home Assistant rejects outright.
                        device_class=SensorDeviceClass.VOLUME_STORAGE,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfVolume.LITERS,
                    )
                )
            elif capability.type == CapabilityType.WATER_CONSUMPTION:
                sensors.append(
                    CozytouchUnitSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                        device_class=SensorDeviceClass.WATER,
                        native_unit_of_measurement=UnitOfVolume.LITERS,
                        state_class=SensorStateClass.TOTAL_INCREASING,
                    )
                )
            elif capability.type == CapabilityType.PERCENTAGE:
                sensors.append(
                    CozytouchUnitSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                        # No device class: percentage is the unit, not the meaning.
                        # SensorDeviceClass.BATTERY was the closest match and made
                        # hot_water_available (271) read as a battery level, icon
                        # and voice assistants included.
                        device_class=None,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                    )
                )
            elif capability.type == CapabilityType.TIME:
                sensors.append(
                    CozytouchTimeSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                    )
                )

            elif capability.type == CapabilityType.TIMEZONE:
                sensors.append(
                    CozytouchTimezoneSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                    )
                )
            elif capability.type == CapabilityType.ERROR_CODE:
                sensors.append(
                    CozytouchErrorCodeSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                    )
                )
            elif capability.type == CapabilityType.PROG:
                sensors.append(
                    CozytouchProgSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                    )
                )
            elif capability.type == CapabilityType.PROGTIME:
                sensors.append(
                    CozytouchProgTimeSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                    )
                )
            elif capability.type == CapabilityType.CLIMATE:
                sensors.append(
                    CozytouchSensor(
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                        coordinator=hub,
                    )
                )

        # Not built from a capability, so it is not in the loop above: the
        # date comes with every capability the device reports rather than
        # being one of them. Only created when the device actually reports
        # one, which is the same rule the capability flags follow -- an entity
        # nobody's hardware backs is worse than no entity.
        if hub.get_last_modification_date() is not None:
            sensors.append(
                CozytouchLastUpdateSensor(
                    config_uniq_id=subentry_id,
                    coordinator=hub,
                )
            )

        # Add the entities to HA
        if len(sensors) > 0:
            async_add_entities(sensors, True, config_subentry_id=subentry_id)


class CozytouchSensor(SensorEntity, CoordinatorEntity):
    """Common class for sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        attr_uniq_id: str | None = None,
        name: str | None = None,
        translation_key: str | None = None,
        icon: str | None = None,
        value_type: CozytouchCapabilityVariableType | None = None,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(coordinator)

        self._capability = capability
        self._config_title = config_title
        self._config_uniq_id = config_uniq_id
        self._last_value: str | None = None
        self._device_uniq_id = config_uniq_id

        # Only set _attr_name when there is a name to set. Assigning None here
        # would tell HA this entity *is* the device, which collapses every
        # entity to the device name and skips the translation key entirely.
        if name:
            self._attr_name = name

        if value_type:
            self._value_type = value_type
        elif "value_type" in self._capability:
            self._value_type = self._capability.value_type
        else:
            self._value_type = None

        if attr_uniq_id:
            self._attr_unique_id = attr_uniq_id
        else:
            capabilityId = self._capability.capabilityId
            self._attr_unique_id = f"{DOMAIN}_{config_uniq_id}_{capabilityId!s}"

        self.entity_description = SensorEntityDescription(
            key="capability_" + str(capability.capabilityId),
            name=name if name else self._capability.name,
        )

        self._attr_translation_key = (
            translation_key if translation_key else self.entity_description.name
        )

        # A capability can ask to arrive switched off. It is still mapped, named
        # and searchable in the entity registry, but it holds no state and costs
        # nothing in the recorder until someone turns it on. That is the right
        # default for the values the API reports about itself -- supported-mode
        # bitmasks, scheduling constants -- which are worth having available and
        # not worth showing to everybody.
        self._attr_entity_registry_enabled_default = self._capability.get(
            "enabled_by_default", True
        )

        if "category" in self._capability:
            if self._capability.category == CapabilityCategory.DIAG:
                self._attr_entity_category = EntityCategory.DIAGNOSTIC
            elif self._capability.category == CapabilityCategory.CONFIG:
                self._attr_entity_category = EntityCategory.CONFIG
            else:
                self._attr_entity_category = None

        if icon:
            self._attr_icon = icon
        elif "icon" in self._capability:
            self._attr_icon = self._capability.icon

    def get_value(self):
        """Retrieve value from hub."""
        if self._value_type == CozytouchCapabilityVariableType.ARRAY:
            return "array"

        try:
            value = self.coordinator.get_capability_value(
                self._capability.capabilityId
            )
            if value is None:
                return None
            if self._value_type == CozytouchCapabilityVariableType.BOOL:
                return bool(value)
            if self._value_type == CozytouchCapabilityVariableType.FLOAT:
                return float(value)
            if self._value_type == CozytouchCapabilityVariableType.INT:
                return int(value)
        except ValueError:
            return value

        return value

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return device_info_for(self.coordinator, self._device_uniq_id)

    @property
    def native_value(self):
        """Value of the sensor."""
        return self._last_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the value of the sensor from the hub."""
        # Get last seen value from controller
        value = self.get_value()
        # _LOGGER.info("%s: update %s (%s)", self._config_title, self._attr_name, value)

        # Handle entity availability
        if value is None:
            if self._attr_available and not self.coordinator.online:
                _LOGGER.debug(
                    "%s: marking the %s sensor as unavailable:"
                    " Cozytouch connection lost",
                    self._config_title,
                    self.name,
                )
                self._attr_available = False
        elif not self._attr_available:
            _LOGGER.info(
                "%s: marking the %s sensor as available now !",
                self._config_title,
                self.name,
            )
            self._attr_available = True

        # Save value
        self._last_value = value
        self.async_write_ha_state()


class CozytouchAwayModeTimestampSensor(CozytouchSensor):
    """Class for away mode timestamp sensor."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
        separator: str | None = None,
        timestamp_index: int | None = None,
        attr_uniq_id: str | None = None,
    ) -> None:
        """Initialize an away mode timestamp Sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=attr_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
            value_type=CozytouchCapabilityVariableType.STRING,
        )
        self._separator = separator
        self._timestamp_index = timestamp_index

    def get_value(self) -> str:
        """Retrieve value from hub."""
        value = self.coordinator.get_capability_value(self._capability.capabilityId)
        if value is not None:
            value = value.translate(str.maketrans("", "", "[]"))
            timestamps = value.split(self._separator, 2)
            if len(timestamps) == 2:
                if timestamps[0] != "0" and timestamps[1] != "0":
                    timestamp = int(timestamps[self._timestamp_index])
                    timeOffset = int(
                        self.coordinator.get_capability_value(
                            self._capability.timezoneCapabilityId
                        )
                    )
                    # The device's own offset is already added to the unix
                    # timestamp, so what is wanted here is that sum read as
                    # wall-clock time. fromtimestamp() without a tz reads it
                    # in Home Assistant's local zone instead, which applies
                    # the offset a second time for anyone not on UTC. Passing
                    # tz=UTC is the fix, and it changes what this sensor
                    # displays -- so it belongs in its own change, with a
                    # capture of what the Cozytouch app shows, rather than
                    # riding along in a lint pass. Recorded as a rough edge
                    # in docs/architecture.md.
                    ts = datetime.datetime.fromtimestamp(  # noqa: DTZ006
                        timestamp + timeOffset
                    )

                    # Check if we need to init timestamps in coordinator
                    timestampStart = self.coordinator.get_away_mode_start()
                    timestampEnd = self.coordinator.get_away_mode_end()
                    if timestampStart is None or timestampEnd is None:
                        self.coordinator.away_mode_init(
                            int(timestamps[0]), int(timestamps[1])
                        )

                    return ts.strftime("%H:%M %d/%m/%Y")

                return "Undefined"

        return None


class CozytouchBinarySensor(BinarySensorEntity, CozytouchSensor):
    """Class for binary sensor."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a binary Sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )
        self._last_value: False

    @property
    def is_on(self) -> bool:
        """Return last state value."""
        value_on = "1"
        if "value_on" in self._capability:
            value_on = self._capability.value_on

        return self._last_value == value_on


class CozytouchAwayModeSensor(CozytouchSensor):
    """Class for away mode sensor."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a binary Sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )

    def get_value(self) -> str:
        """Retrieve value from hub."""
        value = self.coordinator.get_capability_value(self._capability.capabilityId)
        if value is not None:
            strValue = "Unknown"
            if value == self._capability.value_off:
                strValue = "Off"
            elif value == self._capability.value_pending:
                strValue = "Pending"
            elif value == self._capability.value_on:
                strValue = "On"

            return strValue

        return None


class CozytouchUnitSensor(CozytouchSensor):
    """Class for unit sensor."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        device_class: SensorDeviceClass,
        native_unit_of_measurement,
        display_factor: float | None = 1.0,
        state_class: SensorStateClass | None = None,
        suggested_precision: int | None = None,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize an unit Sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
            value_type=CozytouchCapabilityVariableType.FLOAT,
        )
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_suggested_display_precision = suggested_precision
        if device_class:
            self._attr_device_class = device_class

        if state_class:
            self._attr_state_class = state_class

        self.displayed_unit_of_measurement = (
            capability.get("displayed_unit_of_measurement", None),
        )

        self._display_factor = display_factor

    def get_value(self):
        """Retrieve value from hub and convert it if needed."""
        value = super().get_value()
        if self._display_factor != 1.0:
            return float(value) * self._display_factor

        return value

    @property
    def native_value(self) -> float | None:
        """Value of the sensor."""
        if self._last_value:
            try:
                return float(self._last_value)
            except ValueError:
                return 0.0

        return None


class CozytouchTimeSensor(CozytouchSensor):
    """Class for time sensor (in minutes)."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a time Sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )
        self._last_value: 0

    def get_value(self) -> str:
        """Retrieve value from hub."""
        value = self.coordinator.get_capability_value(self._capability.capabilityId)
        if value is not None:
            strValue = ""
            days = 0
            remaining = int(value)
            if remaining >= (60 * 24):
                days = int(remaining / (60 * 24))
                remaining -= days * (60 * 24)

            hours = 0
            if remaining >= 60:
                hours = int(remaining / 60)
                remaining -= hours * 60

            minutes = int(remaining)

            if days > 0:
                strValue = str(days) + "d "

            strValue += f"{hours:02d}:{minutes:02d}"
            return strValue

        return None


class CozytouchTimezoneSensor(CozytouchSensor):
    """Class for timezone sensor."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a time Sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )
        self._last_value: 0

    def get_value(self) -> str:
        """Retrieve value from hub."""
        value = self.coordinator.get_capability_value(self._capability.capabilityId)
        if value is not None:
            # Floor division rather than %d over a true division: the operand
            # is positive in both branches, so it truncates the same way.
            if float(value) > 0:
                strValue = f"GMT+{int(value) // 3600}"
            elif float(value) < 0:
                strValue = f"GMT-{abs(int(value)) // 3600}"
            else:
                strValue = "GMT"

            return strValue

        return None


class CozytouchProgSensor(CozytouchSensor):
    """Class for Prog sensor."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a prog Sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )

    def get_value(self) -> str:
        """Retrieve value from hub."""
        value = self.coordinator.get_capability_value(self._capability.capabilityId)
        if value is not None:
            progList = json.loads(value)

            strValue = ""
            for prog in progList:
                if len(prog) >= 2 and (prog[0] != 0 or prog[1] != 0):
                    hours = int(prog[0] / 60)
                    minutes = int(prog[0] % 60)

                    if strValue != "":
                        strValue += " / "
                    strValue += f"{hours:02d}:{minutes:02d} "
                    # int() rather than the value itself: the setpoint arrives
                    # from JSON and can be a float, which %d used to truncate.
                    strValue += f" {int(prog[1])}°C"

            return strValue

        return None


class CozytouchProgTimeSensor(CozytouchSensor):
    """Class for ProgTime sensor."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a prog time Sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )

    def get_value(self) -> str:
        """Retrieve value from hub."""
        value = self.coordinator.get_capability_value(self._capability.capabilityId)
        if value is not None:
            progList = json.loads(value)

            strValue = ""
            for prog in progList:
                if len(prog) >= 2 and (prog[0] != 0 or prog[1] != 0):
                    hoursfrom = int(prog[0] / 60)
                    minutesfrom = int(prog[0] % 60)

                    hoursto = int(prog[1] / 60)
                    minutesto = int(prog[1] % 60)

                    if strValue != "":
                        strValue += " / "
                    strValue += (
                        f"{hoursfrom:02d}:{minutesfrom:02d}"
                        f"-{hoursto:02d}:{minutesto:02d}"
                    )

            return strValue

        return None


class CozytouchErrorCodeSensor(CozytouchSensor):
    """A fault-code capability, decoded to the codes that are active."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize an error code Sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
        )

    def get_value(self) -> str | None:
        """Retrieve value from hub and decode the fault matrix."""
        value = self.coordinator.get_capability_value(self._capability.capabilityId)
        return decode_error_code(value)


class CozytouchLastUpdateSensor(CoordinatorEntity, SensorEntity):
    """When the device last changed any of the values it reports.

    Every capability item carries a `modificationDate` alongside its value, and
    until now nothing read it. What it answers is the question a frozen reading
    raises and no other entity here can settle : the value has not moved, but is
    the hardware still reporting, or has it fallen off Atlantic's cloud with the
    integration cheerfully serving the last thing it heard ?

    Deliberately only that. The obvious next step -- calling the device
    unavailable once this is old enough -- needs a threshold nobody can defend
    yet : a stable water heater can leave every capability untouched for hours,
    so a guessed one would mark working hardware as broken. This is the
    measurement that makes the threshold decidable later.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "last_device_update"

    def __init__(self, coordinator: Hub, config_uniq_id: str) -> None:
        """Initialize the last-update sensor."""
        super().__init__(coordinator)

        self._device_uniq_id = config_uniq_id
        # Not keyed on a capability id like every other entity here, because it
        # answers for all of them. `last_device_update` is a name no capability
        # can take: capability.py only ever produces ids.
        self._attr_unique_id = f"{DOMAIN}_{config_uniq_id}_last_device_update"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return device_info_for(self.coordinator, self._device_uniq_id)

    @property
    def native_value(self) -> datetime.datetime | None:
        """The newest date the device reports, as an aware datetime.

        Read on demand rather than cached : there is nothing to convert and no
        formatting to pin, and `tz=datetime.UTC` is what keeps this out of the
        double-offset trap the away-mode timestamp sensor is in -- an epoch is
        absolute, so the only correct reading of it is UTC.
        """
        epoch = self.coordinator.get_last_modification_date()
        if epoch is None:
            return None

        return datetime.datetime.fromtimestamp(epoch, tz=datetime.UTC)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Publish whatever the poll just brought back."""
        self.async_write_ha_state()
