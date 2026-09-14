"""The capability table : what each id is, on each product.

The mechanism that reads this lives in `capability.py`. Everything here is
data -- one row per capability id, and the tables that say what a descriptor's
number means. Adding a device means adding rows here; see CLAUDE.md.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from homeassistant.const import UnitOfEnergy, UnitOfPressure

from .const import CozytouchCapabilityVariableType
from .infos import (
    CapabilityCategory,
    CapabilityInfos,
    CapabilityType,
    ModelInfos,
    TimestampInfos,
)
from .model import CozytouchDeviceType

ELECTRIC_HEATERS = (CozytouchDeviceType.TOWEL_RACK, CozytouchDeviceType.RADIATOR)

# Capabilities the device uses to describe itself : the name, and what the
# value is. STRING means the encoding is unverified, which is most of them --
# the typed ones are the subset the vendor app's readers settle. All of them
# are diag and switched off by default. See docs/decisions.md.
SELF_DESCRIBING_CAPABILITIES = {
    73: ("available_thermostat_modes", CapabilityType.STRING),
    93: ("zones_count", CapabilityType.STRING),
    120: ("boiler_or_heat_pump", CapabilityType.STRING),
    157: ("override_setpoint_activation", CapabilityType.BINARY),
    164: ("energy_consumption_supported", CapabilityType.STRING),
    166: ("system_operating_mode", CapabilityType.STRING),
    168: ("available_dhw_modes", CapabilityType.STRING),
    188: ("home_services", CapabilityType.STRING),
    217: ("system_setpoint_mode", CapabilityType.STRING),
    223: ("dhw_system_operating_mode", CapabilityType.STRING),
    224: ("dhw_estimation_supported", CapabilityType.STRING),
    230: ("dhw_operating_mode", CapabilityType.STRING),
    236: ("max_dhw_schedule_slots_per_day", CapabilityType.STRING),
    244: ("max_schedule_ranges_per_day", CapabilityType.STRING),
    294: ("target_temperature_step", CapabilityType.STRING),
    295: ("schedule_time_step", CapabilityType.STRING),
    296: ("schedule_minimum_interval", CapabilityType.TIME),
    306: ("max_schedule_slots_per_day", CapabilityType.STRING),
    307: ("heating_period_min_duration", CapabilityType.TIME),
    329: ("min_schedule_ranges_per_day", CapabilityType.STRING),
    330: ("schedule_range_step", CapabilityType.STRING),
    331: ("schedule_range_max_duration", CapabilityType.TIME),
    332: ("schedule_range_min_duration", CapabilityType.TIME),
    333: ("heating_period_max_duration", CapabilityType.TIME),
    336: ("dhw_panel_capabilities", CapabilityType.STRING),
    337: ("main_cursor_information", CapabilityType.STRING),
    338: ("secondary_cursor_information", CapabilityType.STRING),
    339: ("dhw_panel_data", CapabilityType.STRING),
    340: ("water_setpoint_step", CapabilityType.STRING),
    344: ("linked_interfaces_count", CapabilityType.STRING),
    352: ("absence_day_heating_temperature", CapabilityType.TEMPERATURE),
    353: ("presence_day_heating_temperature", CapabilityType.TEMPERATURE),
    354: ("presence_night_heating_temperature", CapabilityType.TEMPERATURE),
    355: ("absence_day_cooling_temperature", CapabilityType.TEMPERATURE),
    356: ("presence_day_cooling_temperature", CapabilityType.TEMPERATURE),
    357: ("presence_night_cooling_temperature", CapabilityType.TEMPERATURE),
    350: ("air_circulation_supported_speeds", CapabilityType.STRING),
    351: ("connectivity_display_capabilities", CapabilityType.STRING),
    358: ("air_circulation_scope", CapabilityType.STRING),
    381: ("ble_pairing_compatibility", CapabilityType.BINARY),
    100000: ("thermal_zones_count", CapabilityType.STRING),
    100002: ("supported_estimation_modes", CapabilityType.STRING),
    100004: ("available_control_modes", CapabilityType.STRING),
    100013: ("available_schedule_types", CapabilityType.STRING),
    100021: ("supported_control_modes", CapabilityType.STRING),
    100022: ("supported_system_operating_modes", CapabilityType.STRING),
    100023: ("supported_system_modes", CapabilityType.STRING),
    100024: ("available_estimation_modes", CapabilityType.STRING),
    100078: ("identify_supported", CapabilityType.BINARY),
    100102: ("adaptive_planning", CapabilityType.BINARY),
    100103: ("unexpected_events", CapabilityType.BINARY),
    100196: ("absence_schedule", CapabilityType.STRING),
    100197: ("night_target_temperature", CapabilityType.STRING),
    100198: ("presence_target_temperature", CapabilityType.STRING),
    100300: ("schedule_start_day", CapabilityType.STRING),
    100301: ("max_schedule_slots_per_week", CapabilityType.STRING),
    100334: ("new_schedule_monday", CapabilityType.STRING),
    100335: ("new_schedule_tuesday", CapabilityType.STRING),
    100336: ("new_schedule_wednesday", CapabilityType.STRING),
    100337: ("new_schedule_thursday", CapabilityType.STRING),
    100338: ("new_schedule_friday", CapabilityType.STRING),
    100339: ("new_schedule_saturday", CapabilityType.STRING),
    100341: ("new_schedule_sunday", CapabilityType.STRING),
    100503: ("wifi_fw", CapabilityType.STRING),
    100800: ("available_fan_speeds", CapabilityType.STRING),
    102006: ("air_circulation_available_modes", CapabilityType.STRING),
    102020: ("air_circulation_current_mode", CapabilityType.STRING),
    103034: ("room_controls_capabilities", CapabilityType.STRING),
    103150: ("ambient_temperature_available", CapabilityType.BINARY),
    103199: ("antifrost_temperature", CapabilityType.TEMPERATURE),
    103450: ("schedule_anticipation_state", CapabilityType.STRING),
    104050: ("open_window_detection", CapabilityType.BINARY),
    104051: ("open_window_state", CapabilityType.BINARY),
    105011: ("supported_dhw_modes", CapabilityType.STRING),
    105012: ("supported_dhw_system_operating_modes", CapabilityType.STRING),
    105122: ("dhw_boost_end_timestamp", CapabilityType.STRING),
    105636: ("dhw_comfort_mode", CapabilityType.STRING),
}

_HVAC_MODE_BITS = (
    (1, "off"),
    (6, "auto"),
    (8, "cool"),
    (16, "heat"),
    (128, "fan"),
    (256, "dry"),
)

_CONTROL_MODE_BITS = (
    (1, "basic"),
    (2, "prog"),
    (4, "lifestyle_prog"),
    (8, "heating_anticipation"),
    (16, "unexpected_events"),
    (32, "auto"),
    (256, "energy_saving"),
    (1024, "absence"),
    (2048, "scheduled_absence"),
)

_DHW_MODE_BITS = (
    (1, "manual"),
    (2, "eco_comfort_schedule"),
    (4, "auto"),
    (8, "prog"),
    (256, "boost"),
    (512, "scheduled_boost"),
    (1024, "absence"),
    (2048, "scheduled_absence"),
    (4096, "antilegionella"),
    (8192, "smart_grid"),
    (16384, "on_off"),
)

_DHW_HEATING_TYPE_BITS = (
    (1, "heat"),
    (2, "scheduled_heat"),
    (4, "off_peak_heat"),
    (8, "self_consumption_heat"),
)

_AIR_CIRCULATION_MODE_BITS = (
    (1, "off"),
    (2, "auto_temperature"),
    (4, "auto_season"),
    (8, "cool"),
    (16, "heat"),
    (128, "fan"),
    (256, "dry"),
)

_VENTILATION_OPTION_BITS = (
    (1, "temperature"),
    (2, "open_window_detection"),
    (4, "presence_detection"),
    (32, "adaptive_planning"),
)

_VENTILATION_CONTROL_BITS = (
    (1, "temperature"),
    (2, "hygrometry"),
    (4, "emergency_temperature"),
    (8, "powerful_mode"),
    (16, "boost_with_fan"),
    (32, "boost_without_fan"),
    (64, "horizontal_blade_position"),
    (128, "vertical_blade_position"),
)

# What the numbers in the table above mean, read off the vendor's Android app
# and checked against the capture corpus. A member can claim several bits at
# once, and the app matches on any bit of the member's mask. Which masks were
# deliberately left out, and why, is in docs/decisions.md.
CAPABILITY_BIT_FIELDS: dict[int, tuple[tuple[int, str], ...]] = {
    164: (
        (1, "gas_heating"),
        (2, "electricity_heating"),
        (4, "electricity_cooling"),
        (8, "gas_dhw"),
        (16, "electricity_dhw"),
        (32, "fuel_heating"),
        (64, "fuel_dhw"),
        (256, "heating_production"),
        (512, "cooling_production"),
        (1024, "dhw_production"),
    ),
    166: _HVAC_MODE_BITS,
    168: _DHW_MODE_BITS,
    188: (
        (1, "thermal_comfort"),
        (2, "dhw"),
        (4, "ventilation"),
        (8, "light"),
    ),
    217: _CONTROL_MODE_BITS,
    223: _DHW_HEATING_TYPE_BITS,
    224: ((2, "water_flow"),),
    336: (
        (1, "v40_state_of_charge"),
        (2, "main_setpoint_cursor"),
        (4, "secondary_setpoint_cursor"),
        (8, "data_inside"),
    ),
    100002: _VENTILATION_OPTION_BITS,
    100004: _VENTILATION_CONTROL_BITS,
    100013: (
        (1, "on_off"),
        (2, "boost"),
    ),
    100021: _VENTILATION_CONTROL_BITS,
    100022: _HVAC_MODE_BITS,
    100023: _CONTROL_MODE_BITS,
    100024: _VENTILATION_OPTION_BITS,
    102005: _AIR_CIRCULATION_MODE_BITS,
    102006: _AIR_CIRCULATION_MODE_BITS,
    103034: ((16, "antifrost"),),
    105011: _DHW_MODE_BITS,
    105012: _DHW_HEATING_TYPE_BITS,
}

# The same, for the ids whose value is one member rather than a set of them.
CAPABILITY_VALUE_SPACES: dict[int, dict[str, str]] = {
    73: {
        "0": "cooling_only",
        "1": "cooling_with_reheat",
        "2": "heating_only",
        "3": "heating_with_reheat",
        "4": "cooling_and_heating",
        "5": "cooling_and_heating_with_reheat",
    },
    230: {
        "0": "heat",
        "1": "scheduled_heat",
        "2": "off_peak_heat",
    },
    337: {
        "0": "nothing",
        "1": "away",
        "2": "boost",
        "3": "photovoltaic",
        "4": "smart_grid",
        "5": "antilegionella",
        "6": "water_setpoint",
    },
    338: {
        "0": "nothing",
        "1": "eco",
        "2": "water_setpoint",
    },
    339: {
        "0": "nothing",
        "1": "v40_state_of_charge",
        "2": "water_setpoint",
    },
    105636: {
        "0": "eco",
        "1": "comfort",
    },
}


# The speed selectors name a whole set rather than one speed, so each value
# spells its set out. A third mechanism next to the two tables above, and the
# app's own: `buildListFromValue`. See docs/decisions.md.
_SPEED_SETS = {
    "0": "low, medium, high",
    "1": "low, high",
    "2": "low, medium, high, auto",
    "3": "low, high, auto",
    "4": "auto",
}

CAPABILITY_SPEED_SETS: dict[int, dict[str, str]] = {
    350: _SPEED_SETS,
    100800: _SPEED_SETS,
}


@dataclass(frozen=True, kw_only=True, slots=True)
class Entity:
    """What a capability becomes when the id alone decides it.

    Most of the mapping is this : a name, a type, and which category the
    entity lands in. `CAPABILITIES` below is the answer to "what is id N", and
    the chain in `get_capability_infos` is the ids that need more than an
    answer -- the ones that read the model, the value, or another capability.

    Fields are keyword-only : a row reading Entity("x", "y") tells the next
    reader nothing about what x and y are.

    name    the entity name and its translation key, so a new one needs an
            entry in strings.json and in every file under translations/.
    type    the platform that builds it. Only claim one whose unit is known.
    extra   the remaining keys a platform reads off a capability -- the bounds
            of a number, a step, a modelList. Spelled out rather than given
            fields of their own, because each is read by one platform only.

    The last four say the same id does not mean the same thing on every
    product, which is why this is a table of rows rather than of strings :

    absent_on   device types with no such entity at all.
    needs_flag  a flag from model.py that has to hold for the entity to exist.
                A model that does not mention it is taken to have it.
    per_type    per device type, the keys to merge in last.
    per_model   the same per model id, for the products Atlantic wired to
                different capabilities.
    valid_above the entity exists only while the value is above this. Atlantic
                sends a far-out-of-range reading rather than nothing when a
                probe has nothing to say.
    """

    name: str
    type: CapabilityType
    category: CapabilityCategory = CapabilityCategory.SENSOR
    icon: str | None = None
    extra: Mapping[str, object] | None = None
    absent_on: tuple[CozytouchDeviceType, ...] = ()
    needs_flag: str | None = None
    per_type: Mapping[CozytouchDeviceType, Mapping[str, object]] | None = None
    per_model: Mapping[int, Mapping[str, object]] | None = None
    valid_above: float | None = None

    def resolve(
        self, capability: CapabilityInfos, modelInfos: ModelInfos, value: str = "0"
    ) -> CapabilityInfos:
        """Fill the capability in, or hand back an empty one where it does not exist."""
        if modelInfos.type in self.absent_on:
            return CapabilityInfos()
        if self.needs_flag and not modelInfos.get(self.needs_flag, True):
            return CapabilityInfos()
        if self.valid_above is not None and float(value) <= self.valid_above:
            return CapabilityInfos()

        capability.name = self.name
        capability.type = self.type
        capability.category = self.category
        if self.icon is not None:
            capability.icon = self.icon
        for source in (
            self.extra,
            (self.per_type or {}).get(modelInfos.type),
            (self.per_model or {}).get(modelInfos.modelId),
        ):
            for key, setting in (source or {}).items():
                capability[key] = setting
        return capability


@dataclass(frozen=True, kw_only=True, slots=True)
class Family:
    """A run of consecutive ids a device fills one per day.

    Atlantic lays a weekly program out as seven capabilities, monday first.
    Nothing about them varies but the name, so the names are the table -- one
    per id, in id order, and a test checks there are as many as the range
    holds.

    per_type    the whole name list again, for a device type that reads the
                block differently. An air conditioner's second block is the
                cooling program ; on anything else it is a second zone.
    """

    ids: range
    names: tuple[str, ...]
    type: CapabilityType
    category: CapabilityCategory = CapabilityCategory.SENSOR
    per_type: Mapping[CozytouchDeviceType, tuple[str, ...]] | None = None

    def resolve(
        self, capability: CapabilityInfos, capabilityId: int, modelInfos: ModelInfos
    ) -> CapabilityInfos:
        """Fill the capability in with the name this id carries."""
        names = (self.per_type or {}).get(modelInfos.type, self.names)
        capability.name = names[capabilityId - self.ids.start]
        capability.type = self.type
        capability.category = self.category
        return capability


# The weekly programs. A block whose every day the device reports gets a
# calendar instead, so its per-day sensors arrive disabled; see
# docs/decisions.md.
FAMILIES: tuple[Family, ...] = (
    Family(
        ids=range(196, 203),
        names=(
            "prog_01_z1",
            "prog_02_z1",
            "prog_03_z1",
            "prog_04_z1",
            "prog_05_z1",
            "prog_06_z1",
            "prog_07_z1",
        ),
        per_type={
            CozytouchDeviceType.AC: (
                "prog_heating_monday",
                "prog_heating_tuesday",
                "prog_heating_wednesday",
                "prog_heating_thursday",
                "prog_heating_friday",
                "prog_heating_saturday",
                "prog_heating_sunday",
            )
        },
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    Family(
        ids=range(203, 210),
        names=(
            "prog_08_z2",
            "prog_09_z2",
            "prog_10_z2",
            "prog_11_z2",
            "prog_12_z2",
            "prog_13_z2",
            "prog_14_z2",
        ),
        per_type={
            CozytouchDeviceType.AC: (
                "prog_cooling_monday",
                "prog_cooling_tuesday",
                "prog_cooling_wednesday",
                "prog_cooling_thursday",
                "prog_cooling_friday",
                "prog_cooling_saturday",
                "prog_cooling_sunday",
            )
        },
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    Family(
        ids=range(237, 244),
        names=(
            "dhw_prog_monday",
            "dhw_prog_tuesday",
            "dhw_prog_wednesday",
            "dhw_prog_thursday",
            "dhw_prog_friday",
            "dhw_prog_saturday",
            "dhw_prog_sunday",
        ),
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
)

# The two ends of the away window, which arrive as one comma-separated value.
AWAY_MODE_TIMESTAMPS = (
    TimestampInfos("away_mode_start", "mdi:airplane-takeoff"),
    TimestampInfos("away_mode_stop", "mdi:airplane-landing"),
)

# Ids the mapping deliberately drops: reported, understood, and not wanted as
# an entity of their own.
SUPPRESSED_CAPABILITIES = frozenset({181})


CAPABILITIES: dict[int, Entity] = {
    19: Entity(
        name="temperature_setpoint",
        type=CapabilityType.TEMPERATURE,
    ),
    22: Entity(
        name="target_temperature_dhw",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        extra={"lowestValueCapabilityId": 160, "highestValueCapabilityId": 161},
        per_model={
            2374: {
                "lowestValueCapabilityId": 253,
                "highestValueCapabilityId": 252,
                "step": 1,
            }
        },
    ),
    25: Entity(
        name="number_of_starts_ch_pump",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:water-pump",
    ),
    26: Entity(
        name="number_of_starts_dhw_pump",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:water-pump",
    ),
    28: Entity(
        name="number_of_hours_ch_pump",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:water-pump",
    ),
    29: Entity(
        name="number_of_hours_dhw_pump",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:water-pump",
    ),
    40: Entity(
        name="target_temperature",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        extra={
            "lowestValueCapabilityId": 160,
            "highestValueCapabilityId": 161,
        },
    ),
    41: Entity(
        name="target_temperature_eco_z1",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        extra={
            "lowestValueCapabilityId": 160,
            "highestValueCapabilityId": 161,
        },
    ),
    42: Entity(
        name="target_temperature_eco_z2",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        extra={
            "lowestValueCapabilityId": 160,
            "highestValueCapabilityId": 161,
        },
    ),
    44: Entity(
        name="ch_power_consumption",
        type=CapabilityType.ENERGY,
        icon="mdi:radiator",
        extra={
            "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        },
    ),
    45: Entity(
        name="dhw_power_consumption",
        type=CapabilityType.ENERGY,
        icon="mdi:faucet",
        extra={
            "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        },
    ),
    46: Entity(
        name="total_power_consumption",
        type=CapabilityType.ENERGY,
        icon="mdi:water-boiler",
        extra={
            "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        },
    ),
    57: Entity(
        name="power_consumption",
        type=CapabilityType.ENERGY,
        extra={
            "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        },
    ),
    59: Entity(
        name="power_consumption",
        type=CapabilityType.ENERGY,
        extra={
            "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        },
    ),
    86: Entity(
        name="domestic_hot_water",
        type=CapabilityType.SWITCH,
        icon="mdi:faucet",
    ),
    87: Entity(
        name="domestic_hot_water_mode",
        type=CapabilityType.SELECT,
        icon="mdi:water-boiler",
        extra={
            "modelList": "HeatingModes",
        },
    ),
    88: Entity(
        name="model_name",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    94: Entity(
        name="product_number",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    98: Entity(
        name="product_number",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    99: Entity(
        name="dhw_pump",
        type=CapabilityType.BINARY,
        icon="mdi:faucet",
        per_type={
            CozytouchDeviceType.WATER_HEATER: {
                "name": "resistance",
                "icon": "mdi:radiator",
            }
        },
    ),
    100: Entity(
        name="water_pressure",
        type=CapabilityType.PRESSURE,
        icon="mdi:gauge",
        extra={
            "displayed_unit_of_measurement": UnitOfPressure.BAR,
        },
    ),
    101: Entity(
        name="Capability_101",
        type=CapabilityType.STRING,
        extra={"value_type": CozytouchCapabilityVariableType.ARRAY},
    ),
    102: Entity(
        name="Capability_102",
        type=CapabilityType.STRING,
        extra={"value_type": CozytouchCapabilityVariableType.ARRAY},
    ),
    103: Entity(
        name="Capability_103",
        type=CapabilityType.STRING,
        extra={"value_type": CozytouchCapabilityVariableType.ARRAY},
    ),
    104: Entity(
        name="Capability_104",
        type=CapabilityType.STRING,
        extra={"value_type": CozytouchCapabilityVariableType.ARRAY},
    ),
    109: Entity(
        name="boiler_water_temperature",
        type=CapabilityType.TEMPERATURE,
    ),
    111: Entity(
        name="dhw_temperature",
        type=CapabilityType.TEMPERATURE,
    ),
    116: Entity(
        name="exhaust_temperature",
        type=CapabilityType.TEMPERATURE,
        needs_flag="exhaustTemperatureAvailable",
    ),
    117: Entity(
        name="thermostat_temperature_z1",
        type=CapabilityType.TEMPERATURE,
    ),
    118: Entity(
        name="thermostat_temperature_z2",
        type=CapabilityType.TEMPERATURE,
    ),
    119: Entity(
        # Atlantic sends -327.68 rather than nothing when there is no probe.
        name="outside_temperature",
        type=CapabilityType.TEMPERATURE,
        valid_above=-327.68,
    ),
    121: Entity(
        name="version",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    150: Entity(
        name="home_error_code",
        type=CapabilityType.ERROR_CODE,
        category=CapabilityCategory.DIAG,
        icon="mdi:alert-circle-outline",
    ),
    152: Entity(
        name="away_mode",
        type=CapabilityType.AWAY_MODE_SWITCH,
        icon="mdi:airplane",
        extra={
            "value_off": "0",
            "value_on": "1",
            "value_pending": "2",
            "timestampsCapabilityId": 222,
        },
    ),
    153: Entity(
        name="flame",
        type=CapabilityType.BINARY,
        icon="mdi:fire",
        per_type={
            deviceType: {"name": "resistance", "icon": "mdi:radiator"}
            for deviceType in ELECTRIC_HEATERS
        },
    ),
    154: Entity(
        name="zone_1",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:home-floor-1",
    ),
    155: Entity(
        name="zone_2",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:home-floor-2",
    ),
    158: Entity(
        name="override_total_time_z1",
        type=CapabilityType.HOURS_ADJUSTMENT_NUMBER,
        icon="mdi:clock-outline",
        extra={"lowest_value": 1, "highest_value": 24},
        per_type={
            deviceType: {"name": "override_total_time"}
            for deviceType in ELECTRIC_HEATERS
        },
    ),
    159: Entity(
        name="override_remain_time_z1",
        type=CapabilityType.TIME,
        icon="mdi:clock-outline",
        per_type={
            deviceType: {"name": "override_remain_time"}
            for deviceType in ELECTRIC_HEATERS
        },
    ),
    160: Entity(
        name="temperature_adjustment_min",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        icon="mdi:thermometer-chevron-down",
    ),
    161: Entity(
        name="temperature_adjustment_max",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        category=CapabilityCategory.DIAG,
        icon="mdi:thermometer-chevron-up",
        extra={
            "lowest_value": 19,
            "highest_value": 28,
            "step": 0.5,
        },
    ),
    162: Entity(
        # The cooling counterpart of the 160/161 heating bounds. Two independent
        # reverse-engineering efforts name these the same way, so the unit is
        # not a guess -- but nothing reads them yet. Wiring them as the climate
        # entity's min and max while cooling is a separate change.
        name="cooling_temperature_min",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        extra={"enabled_by_default": False},
    ),
    163: Entity(
        name="cooling_temperature_max",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        extra={"enabled_by_default": False},
    ),
    165: Entity(
        # water-boiler icon: a domestic-hot-water boost, not the generic boost.
        name="domestic_hot_water_boost",
        type=CapabilityType.SWITCH,
        icon="mdi:water-boiler",
        per_type={
            CozytouchDeviceType.HEAT_PUMP: {"value_off": "false", "value_on": "true"}
        },
    ),
    169: Entity(
        name="radio_signal",
        type=CapabilityType.PERCENTAGE,
        category=CapabilityCategory.DIAG,
        icon="mdi:radio-tower",
    ),
    171: Entity(
        # The cooling half of the absence setpoint, 172 being the heating one.
        # Read-only where 172 is a number. See docs/decisions.md.
        name="away_mode_cooling_temperature",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        needs_flag="awayModeTemperatureAvailable",
        extra={"enabled_by_default": False},
    ),
    172: Entity(
        # Absence setpoint. Only the heating products act on it. An air
        # conditioner reports it and stores what is written, but never reads it
        # back: absence there stops the units until the return date, and the
        # weekly program keeps driving 40 and 177 throughout. Exposing a number
        # nothing honours would promise a setting the Cozytouch app does not
        # even offer on this hardware.
        name="away_mode_temperature",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        needs_flag="awayModeTemperatureAvailable",
        extra={"lowestValueCapabilityId": 160, "highestValueCapabilityId": 161},
    ),
    177: Entity(
        name="target_cool_temperature",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        absent_on=(CozytouchDeviceType.GAZ_BOILER,),
        extra={"lowestValueCapabilityId": 162, "highestValueCapabilityId": 163},
    ),
    179: Entity(
        name="wifi_signal",
        type=CapabilityType.SIGNAL,
        category=CapabilityCategory.DIAG,
        icon="mdi:wifi",
    ),
    184: Entity(
        name="prog_mode",
        type=CapabilityType.SWITCH,
        icon="mdi:clock-outline",
    ),
    218: Entity(
        # `wifiConnected` by name, but never the boolean it looks like : shown
        # raw and off by default. See docs/decisions.md. A zone gets nothing at
        # all, having no readings to go with it.
        name="wifi_connected",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:wifi",
        absent_on=(CozytouchDeviceType.ZONE,),
        extra={"enabled_by_default": False},
    ),
    219: Entity(
        name="wifi_ssid",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:wifi",
    ),
    222: Entity(
        name="away_mode",
        type=CapabilityType.AWAY_MODE_TIMESTAMPS,
        extra={
            "timestamps": AWAY_MODE_TIMESTAMPS,
            "timezoneCapabilityId": 315,
            "capabilityDuplicate": 226,
        },
    ),
    226: Entity(
        name="away_mode",
        type=CapabilityType.AWAY_MODE_TIMESTAMPS,
        extra={
            "timestamps": AWAY_MODE_TIMESTAMPS,
            "timezoneCapabilityId": 315,
            "capabilityDuplicate": 222,
        },
    ),
    227: Entity(
        name="away_mode",
        type=CapabilityType.AWAY_MODE_SWITCH,
        icon="mdi:airplane",
        extra={
            "value_off": "0",
            "value_on": "1",
            "value_pending": "2",
            "timestampsCapabilityId": 226,
        },
    ),
    228: Entity(
        name="absence_dhw_temperature",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
    ),
    231: Entity(
        name="target_temperature",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        extra={
            "lowestValueCapabilityId": 105301,
            "highestValueCapabilityId": 105304,
        },
        per_model={
            2374: {
                "lowestValueCapabilityId": 253,
                "highestValueCapabilityId": 252,
                "step": 1,
            }
        },
    ),
    232: Entity(
        name="boost_total_time",
        type=CapabilityType.TIME,
        category=CapabilityCategory.DIAG,
        icon="mdi:clock-outline",
    ),
    233: Entity(
        name="boost_remaining_time",
        type=CapabilityType.TIME,
        category=CapabilityCategory.DIAG,
        icon="mdi:clock-outline",
    ),
    245: Entity(
        name="prog_01",
        type=CapabilityType.PROGTIME,
        category=CapabilityCategory.DIAG,
    ),
    246: Entity(
        name="prog_02",
        type=CapabilityType.PROGTIME,
        category=CapabilityCategory.DIAG,
    ),
    247: Entity(
        name="prog_03",
        type=CapabilityType.PROGTIME,
        category=CapabilityCategory.DIAG,
    ),
    248: Entity(
        name="prog_04",
        type=CapabilityType.PROGTIME,
        category=CapabilityCategory.DIAG,
    ),
    249: Entity(
        name="prog_05",
        type=CapabilityType.PROGTIME,
        category=CapabilityCategory.DIAG,
    ),
    250: Entity(
        name="prog_06",
        type=CapabilityType.PROGTIME,
        category=CapabilityCategory.DIAG,
    ),
    251: Entity(
        name="prog_07",
        type=CapabilityType.PROGTIME,
        category=CapabilityCategory.DIAG,
    ),
    252: Entity(
        name="target_temperature_max",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
    ),
    253: Entity(
        name="target_temperature_min",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
    ),
    258: Entity(
        name="tank_capacity",
        type=CapabilityType.VOLUME,
    ),
    264: Entity(
        name="condenser_temperature",
        type=CapabilityType.TEMPERATURE,
    ),
    265: Entity(
        name="tank_middle_temperature",
        type=CapabilityType.TEMPERATURE,
    ),
    266: Entity(
        name="tank_top_temperature",
        type=CapabilityType.TEMPERATURE,
    ),
    267: Entity(
        name="tank_bottom_temperature",
        type=CapabilityType.TEMPERATURE,
    ),
    268: Entity(
        name="v40_water_available",
        type=CapabilityType.VOLUME,
        icon="mdi:water-thermometer",
    ),
    269: Entity(
        name="water_consumption",
        type=CapabilityType.WATER_CONSUMPTION,
        icon="mdi:water-pump",
    ),
    270: Entity(
        name="v40_water_capacity",
        type=CapabilityType.VOLUME,
        icon="mdi:water-thermometer",
    ),
    271: Entity(
        name="hot_water_available",
        type=CapabilityType.PERCENTAGE,
    ),
    280: Entity(
        name="cold_water_temperature",
        type=CapabilityType.TEMPERATURE,
        icon="mdi:coolant-temperature",
    ),
    283: Entity(
        name="off_peak_hours",
        type=CapabilityType.BINARY,
        icon="mdi:clock-outline",
    ),
    290: Entity(
        name="dhw_error_code",
        type=CapabilityType.ERROR_CODE,
        category=CapabilityCategory.DIAG,
        icon="mdi:alert-circle-outline",
    ),
    292: Entity(
        name="hot_water_showers_expected",
        type=CapabilityType.INT,
        icon="mdi:water-plus",
    ),
    293: Entity(
        name="hot_water_showers_remaining",
        type=CapabilityType.INT,
        icon="mdi:water-check",
    ),
    303: Entity(
        name="error_code",
        type=CapabilityType.ERROR_CODE,
        category=CapabilityCategory.DIAG,
        icon="mdi:alert-circle-outline",
    ),
    312: Entity(
        # Atlantic calls this one currentControlTarget, which matches the
        # setpoint shape read below -- but it gives 306 the same name, and 306
        # is already mapped as a schedule bound. One of the two is wrong and
        # nothing here says which, so the placeholder name stays until a
        # capture settles it.
        name="Temp_312",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
    ),
    315: Entity(
        name="timezone",
        type=CapabilityType.TIMEZONE,
        category=CapabilityCategory.DIAG,
        icon="mdi:map-clock-outline",
    ),
    316: Entity(
        name="interface_fw",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    335: Entity(
        name="serial_number",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    100261: Entity(
        name="away_mode",
        type=CapabilityType.BINARY,
        icon="mdi:airplane",
    ),
    100320: Entity(
        name="prog_heat_monday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100321: Entity(
        name="prog_heat_tuesday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100322: Entity(
        name="prog_heat_wednesday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100323: Entity(
        name="prog_heat_thursday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100324: Entity(
        name="prog_heat_friday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100325: Entity(
        name="prog_heat_saturday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100326: Entity(
        name="prog_heat_sunday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100327: Entity(
        name="prog_cool_monday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100328: Entity(
        name="prog_cool_tuesday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100329: Entity(
        name="prog_cool_wednesday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100330: Entity(
        name="prog_cool_thursday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100331: Entity(
        name="prog_cool_friday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100332: Entity(
        name="prog_cool_saturday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100333: Entity(
        name="prog_cool_sunday",
        type=CapabilityType.PROG,
        category=CapabilityCategory.DIAG,
    ),
    100402: Entity(
        name="number_of_hours_burner",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:fire",
    ),
    100406: Entity(
        name="number_of_starts_burner",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:fire",
    ),
    100450: Entity(
        name="schedule_anticipation",
        type=CapabilityType.SWITCH,
        icon="mdi:clock-fast",
    ),
    100505: Entity(
        name="powerful_mode",
        type=CapabilityType.SWITCH,
        icon="mdi:wind-power",
    ),
    100506: Entity(
        # Towel dryers only: no capture has one reporting it, and the branch
        # predates the room radiators, which do report it and are sold on the
        # presence detection.
        name="presence_mode",
        type=CapabilityType.SWITCH,
        icon="mdi:account",
        absent_on=(CozytouchDeviceType.TOWEL_RACK,),
    ),
    100507: Entity(
        # Same story as the absence setpoint in 172: the air conditioners report
        # eco mode without the Cozytouch app ever offering it. Reported is not
        # supported, so let the model table decide.
        name="eco_mode",
        type=CapabilityType.SWITCH,
        icon="mdi:flower-outline",
        needs_flag="ecoModeAvailable",
    ),
    100802: Entity(
        name="quiet_mode",
        type=CapabilityType.SWITCH,
        icon="mdi:fan-minus",
    ),
    100804: Entity(
        name="swing_mode",
        type=CapabilityType.SWITCH,
        icon="mdi:arrow-oscillating",
    ),
    102004: Entity(
        name="air_circulation_speed",
        type=CapabilityType.SELECT,
        icon="mdi:fan",
        extra={
            "modelList": "AirCirculationSpeeds",
        },
    ),
    102005: Entity(
        name="air_circulation_supported_modes",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:fan",
        extra={
            "enabled_by_default": False,
        },
    ),
    102021: Entity(
        name="air_circulation_total_time",
        type=CapabilityType.DURATION_SELECT,
        icon="mdi:fan-clock",
        extra={
            "lowestValueCapabilityId": 102025,
            "highestValueCapabilityId": 102026,
            "stepCapabilityId": 102022,
            "lowest_value": 15,
            "highest_value": 300,
            "step": 15,
        },
    ),
    102022: Entity(
        name="air_circulation_time_step",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:fan-clock",
        extra={
            "enabled_by_default": False,
        },
    ),
    102023: Entity(
        name="air_circulation_remaining_time",
        type=CapabilityType.TIME,
        category=CapabilityCategory.DIAG,
        icon="mdi:fan-clock",
    ),
    102024: Entity(
        name="air_circulation",
        type=CapabilityType.SWITCH,
        icon="mdi:fan",
    ),
    102025: Entity(
        name="air_circulation_time_min",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:fan-clock",
        extra={
            "enabled_by_default": False,
        },
    ),
    102026: Entity(
        name="air_circulation_time_max",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:fan-clock",
        extra={
            "enabled_by_default": False,
        },
    ),
    104044: Entity(
        name="boost_mode",
        type=CapabilityType.SWITCH,
        icon="mdi:heat-wave",
    ),
    104047: Entity(
        name="boost_timeout_max",
        type=CapabilityType.MINUTES_ADJUSTMENT_NUMBER,
        category=CapabilityCategory.DIAG,
        icon="mdi:clock-outline",
        extra={
            "lowest_value": 5,
            "highest_value": 60,
            "step": 5,
        },
    ),
    105300: Entity(
        name="water_temperature_limit",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
    ),
    105304: Entity(
        name="max_target_temperature_derogation",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
    ),
    105906: Entity(
        name="v40_applied_setpoint",
        type=CapabilityType.TEMPERATURE_PERCENT_ADJUSTMENT_NUMBER,
        extra={
            "temperatureMin": 15.0,
            "temperatureMax": 65.0,
        },
    ),
    105907: Entity(
        name="v40_setpoint_filled_by_user",
        type=CapabilityType.TEMPERATURE_PERCENT_ADJUSTMENT_NUMBER,
        extra={
            "temperatureMin": 15.0,
            "temperatureMax": 65.0,
        },
    ),
}
