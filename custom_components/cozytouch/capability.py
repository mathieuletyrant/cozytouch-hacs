"""Atlantic Cozytouch capabilility mapping."""

from collections.abc import Mapping
from dataclasses import dataclass

from homeassistant.const import UnitOfEnergy, UnitOfPressure

from .const import PROGRAM_DAYS, CozytouchCapabilityVariableType, program_block
from .infos import (
    CapabilityCategory,
    CapabilityInfos,
    CapabilityType,
    ModelInfos,
    TimestampInfos,
)
from .model import CozytouchDeviceType

# The API's own families split the electric heaters in two -- Radiator and
# Towel_Dryer -- and the mapping follows, because "seche-serviettes" in front
# of a radiator is what gduteil/cozytouch#172 was about. Same wiring on this
# side of it : both report the same ids and mean the same things by them. The
# one place they part is 100506, below.
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


def describe_capability_value(capabilityId: int, value) -> str | None:
    """Read a descriptor capability as what it says, or None if nothing does.

    Bits nothing names are kept as a count rather than dropped: these entities
    exist to investigate hardware nobody here owns, and a bit the tables do not
    cover is exactly what such a reader is after.
    """
    space = CAPABILITY_VALUE_SPACES.get(capabilityId) or CAPABILITY_SPEED_SETS.get(
        capabilityId
    )
    if space is not None:
        return space.get(str(value).strip())

    bits = CAPABILITY_BIT_FIELDS.get(capabilityId)
    if bits is None:
        return None

    try:
        mask = int(str(value).strip())
    except (TypeError, ValueError):
        return None

    if mask == 0:
        return "none"

    named = [label for bit, label in bits if mask & bit]

    known = 0
    for bit, _ in bits:
        known |= bit
    leftover = mask & ~known
    if leftover:
        named.append(f"unknown ({leftover})")

    return ", ".join(named) if named else None


# The program blocks whose slots hold a room temperature. The hot-water block
# (237-243) is deliberately out: its slots really do carry 50-65 °C, so the
# hundredths rule below would read a 65 °C tank as 0.65 °C.
THERMOSTAT_PROG_IDS = frozenset(range(196, 210)) | frozenset(range(100320, 100334))


def read_setpoint(capabilityId: int | None, value):
    """Read a program slot's target temperature.

    Some firmwares store it in hundredths -- the vendor app divides anything
    above 40 by 100 and shows the result, so a slot reading 1950 is 19.5 °C
    and not a device asking for 1950 °C. No capture here has ever shown one,
    so this is the app's rule and nothing more; see docs/decisions.md.
    """
    if capabilityId not in THERMOSTAT_PROG_IDS:
        return value

    try:
        setpoint = float(value)
    except (TypeError, ValueError):
        return value

    return setpoint / 100 if setpoint > 40 else setpoint


def _whole_block_reported(first: int, availableCapabilityIds: set[int]) -> bool:
    """Whether the device reports all seven days of the program block at `first`.

    All seven is the calendar platform's condition for building one, so this
    is also the condition for the per-day sensors arriving disabled: a device
    with a partial block has no calendar, and its per-day sensors stay its
    only view. See docs/decisions.md.
    """
    return all(
        capabilityId in availableCapabilityIds for capabilityId in program_block(first)
    )


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
    """

    name: str
    type: CapabilityType
    category: CapabilityCategory = CapabilityCategory.SENSOR
    icon: str | None = None
    extra: Mapping[str, object] | None = None

    def apply(self, capability: CapabilityInfos) -> None:
        """Fill in the fields this row declares, and nothing else."""
        capability.name = self.name
        capability.type = self.type
        capability.category = self.category
        if self.icon is not None:
            capability.icon = self.icon
        for key, value in (self.extra or {}).items():
            capability[key] = value


CAPABILITIES: dict[int, Entity] = {
    19: Entity(
        name="temperature_setpoint",
        type=CapabilityType.TEMPERATURE,
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
    100: Entity(
        name="water_pressure",
        type=CapabilityType.PRESSURE,
        icon="mdi:gauge",
        extra={
        "displayed_unit_of_measurement": UnitOfPressure.BAR,
        },
    ),
    109: Entity(
        name="boiler_water_temperature",
        type=CapabilityType.TEMPERATURE,
    ),
    111: Entity(
        name="dhw_temperature",
        type=CapabilityType.TEMPERATURE,
    ),
    117: Entity(
        name="thermostat_temperature_z1",
        type=CapabilityType.TEMPERATURE,
    ),
    118: Entity(
        name="thermostat_temperature_z2",
        type=CapabilityType.TEMPERATURE,
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
    169: Entity(
        name="radio_signal",
        type=CapabilityType.PERCENTAGE,
        category=CapabilityCategory.DIAG,
        icon="mdi:radio-tower",
    ),
    179: Entity(
        name="wifi_signal",
        type=CapabilityType.SIGNAL,
        category=CapabilityCategory.DIAG,
        icon="mdi:wifi",
    ),
    219: Entity(
        name="wifi_ssid",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        icon="mdi:wifi",
    ),
    228: Entity(
        name="absence_dhw_temperature",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
    ),
    232: Entity(
        name="boost_total_time",
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


# C901 is still over: 70 branches of complexity, down from 180. What is left
# reads the model, the value or another capability, so it cannot be a row.
def get_capability_infos(  # noqa: C901
    modelInfos: ModelInfos,
    capabilityId: int,
    capabilityValue: str,
    availableCapabilityIds: set[int],
) -> CapabilityInfos | None:
    """What this device turns this capability into.

    Three answers, in order : the climate entity for an id carrying an HVAC
    mode, a row of `CAPABILITIES` for the ids the id alone decides, and a
    branch below for the rest -- the ones that read the model, the value, or
    which other capabilities the device reports. None means the mapping does
    not know the id, which is what the diagnostics dump reports so somebody
    can name it.

    availableCapabilityIds is what the device actually reports. Optional
    features are declared per model, but the same model id is reused across
    hardware that does not always implement them, so they are only wired up
    when the device backs them.
    """
    modelId = modelInfos.modelId

    capability = CapabilityInfos(modelId=modelId, capabilityId=capabilityId)

    if (
        capabilityId in (1, 2, 7, 8)
        and capabilityId in modelInfos.HVACModesCapabilityId
    ):
        # Default Ids
        capability.targetCapabilityId = 40
        capability.lowestValueCapabilityId = 160
        capability.highestValueCapabilityId = 161

        if (
            modelInfos.get("currentTemperatureAvailable", True)
            and 117 in availableCapabilityIds
        ):
            capability.currentValueCapabilityId = 117

        # 181 carries the mode the device is really running, which is not always
        # the one it was asked for
        if 181 in availableCapabilityIds:
            capability.hvacActionCapabilityId = 181

        # While air circulation runs it drives the unit, and the Cozytouch app
        # locks the mode and setpoint for the duration
        if 102024 in availableCapabilityIds:
            capability.airCirculationCapabilityId = 102024

        # TEMPERATURE_UPDATE_STEP: the device states the setpoint granularity
        if 294 in availableCapabilityIds:
            capability.stepCapabilityId = 294

        if modelInfos.type == CozytouchDeviceType.GAZ_BOILER:
            capability.name = "central_heating"
            capability.icon = "mdi:radiator"
            capability.progCapabilityId = 184
            capability.progOverrideCapabilityId = 157
            capability.progOverrideTotalTimeCapabilityId = 158
            capability.progOverrideTimeCapabilityId = 159
        elif modelInfos.type in ELECTRIC_HEATERS:
            capability.name = "heat"
            capability.icon = "mdi:heating-coil"
            # 153 is the element itself. 181 above only says which mode is
            # running, so a radiator sitting above its setpoint read as
            # heating -- see docs/decisions.md
            if 153 in availableCapabilityIds:
                capability.heatingActiveCapabilityId = 153
            capability.progCapabilityId = 184
            capability.progOverrideCapabilityId = 157
            capability.progOverrideTotalTimeCapabilityId = 158
            capability.progOverrideTimeCapabilityId = 159
        elif modelInfos.type == CozytouchDeviceType.AC:
            capability.name = "air_conditioner"
            capability.icon = "mdi:air-conditioner"
            capability.targetCoolCapabilityId = 177
            capability.lowestCoolValueCapabilityId = 162
            capability.highestCoolValueCapabilityId = 163
            if 100506 in availableCapabilityIds:
                capability.activityCapabilityId = 100506
            if (
                modelInfos.get("ecoModeAvailable", True)
                and 100507 in availableCapabilityIds
            ):
                capability.ecoCapabilityId = 100507
            if 100505 in availableCapabilityIds:
                capability.boostCapabilityId = 100505
        elif modelInfos.type == CozytouchDeviceType.HEAT_PUMP:
            if capabilityId in (1, 7):
                capability.name = "heat_pump_z1"
                capability.targetCapabilityId = 17
                if (
                    modelInfos.get("currentTemperatureAvailableZ1", True)
                    and 117 in availableCapabilityIds
                ):
                    capability.currentValueCapabilityId = 117
                else:
                    capability.currentValueCapabilityId = None
            else:
                capability.name = "heat_pump_z2"
                capability.targetCapabilityId = 18
                if (
                    modelInfos.get("currentTemperatureAvailableZ2", True)
                    and 118 in availableCapabilityIds
                ):
                    capability.currentValueCapabilityId = 118
                else:
                    capability.currentValueCapabilityId = None

            del capability.lowestValueCapabilityId
            del capability.highestValueCapabilityId
            capability.icon = "mdi:heat-pump"
        else:
            capability.name = "heat"

        capability.type = CapabilityType.CLIMATE
        capability.category = CapabilityCategory.SENSOR

        if "fanModes" in modelInfos and 100801 in availableCapabilityIds:
            capability.fanModeCapabilityId = 100801

        if (
            modelInfos.get("quietModeAvailable", False)
            and 100802 in availableCapabilityIds
        ):
            capability.quietModeCapabilityId = 100802

        if modelInfos.get("overrideModeAvailable", True):
            capability.progCapabilityId = 184
            capability.progOverrideCapabilityId = 157
            capability.progOverrideTotalTimeCapabilityId = 158
            capability.progOverrideTimeCapabilityId = 159

        if "swingModes" in modelInfos and 100803 in availableCapabilityIds:
            capability.swingModeCapabilityId = 100803

            if 100804 in availableCapabilityIds:
                capability.swingOnCapabilityId = 100804

    elif capabilityId in CAPABILITIES:
        CAPABILITIES[capabilityId].apply(capability)

    elif capabilityId == 22:
        capability.name = "target_temperature_dhw"
        capability.type = CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER
        capability.category = CapabilityCategory.SENSOR
        if modelId == 2374:
            capability.lowestValueCapabilityId = 253
            capability.highestValueCapabilityId = 252
            capability.step = 1
        else:
            capability.lowestValueCapabilityId = 160
            capability.highestValueCapabilityId = 161

    elif capabilityId == 99:
        if modelInfos.type == CozytouchDeviceType.WATER_HEATER:
            capability.name = "resistance"
            capability.icon = "mdi:radiator"
        else:
            capability.name = "dhw_pump"
            capability.icon = "mdi:faucet"

        capability.type = CapabilityType.BINARY
        capability.category = CapabilityCategory.SENSOR

    elif capabilityId in (101, 102, 103, 104):
        capability.name = "Capability_" + str(capabilityId)
        capability.type = CapabilityType.STRING
        capability.value_type = CozytouchCapabilityVariableType.ARRAY
        capability.category = CapabilityCategory.SENSOR

    elif capabilityId == 116:
        if modelInfos.get("exhaustTemperatureAvailable", True):
            capability.name = "exhaust_temperature"
            capability.type = CapabilityType.TEMPERATURE
            capability.category = CapabilityCategory.SENSOR
        else:
            return CapabilityInfos()

    elif capabilityId == 119:
        # Outside temperature is invalid when value is -327.68
        if float(capabilityValue) > -327.68:
            capability.name = "outside_temperature"
            capability.type = CapabilityType.TEMPERATURE
            capability.category = CapabilityCategory.SENSOR
        else:
            return CapabilityInfos()

    elif capabilityId in (152, 227):
        capability.name = "away_mode"
        capability.type = CapabilityType.AWAY_MODE_SWITCH
        capability.category = CapabilityCategory.SENSOR
        capability.icon = "mdi:airplane"
        capability.value_off = "0"
        capability.value_on = "1"
        capability.value_pending = "2"
        if capabilityId == 152:
            capability.timestampsCapabilityId = 222
        elif capabilityId == 227:
            capability.timestampsCapabilityId = 226

    elif capabilityId == 153:
        if modelInfos.type in ELECTRIC_HEATERS:
            capability.name = "resistance"
            capability.icon = "mdi:radiator"
        else:
            capability.name = "flame"
            capability.icon = "mdi:fire"

        capability.type = CapabilityType.BINARY
        capability.category = CapabilityCategory.SENSOR

    elif capabilityId == 158:
        if modelInfos.type in ELECTRIC_HEATERS:
            capability.name = "override_total_time"
        else:
            capability.name = "override_total_time_z1"

        capability.type = CapabilityType.HOURS_ADJUSTMENT_NUMBER
        capability.category = CapabilityCategory.SENSOR
        capability.icon = "mdi:clock-outline"
        capability.lowest_value = 1
        capability.highest_value = 24

    elif capabilityId == 159:
        if modelInfos.type in ELECTRIC_HEATERS:
            capability.name = "override_remain_time"
        else:
            capability.name = "override_remain_time_z1"

        capability.type = CapabilityType.TIME
        capability.category = CapabilityCategory.SENSOR
        capability.icon = "mdi:clock-outline"

    elif capabilityId in (162, 163):
        # The cooling counterpart of the 160/161 heating bounds. Two independent
        # reverse-engineering efforts name these the same way, so the unit is
        # not a guess -- but nothing reads them yet. Wiring them as the climate
        # entity's min and max while cooling is a separate change.
        capability.name = (
            "cooling_temperature_min"
            if capabilityId == 162
            else "cooling_temperature_max"
        )
        capability.type = CapabilityType.TEMPERATURE
        capability.category = CapabilityCategory.DIAG
        capability.enabled_by_default = False

    elif capabilityId == 165:
        # water-boiler icon: a domestic-hot-water boost, not the generic boost.
        capability.name = "domestic_hot_water_boost"
        capability.type = CapabilityType.SWITCH
        capability.category = CapabilityCategory.SENSOR
        capability.icon = "mdi:water-boiler"

        if modelInfos.type == CozytouchDeviceType.HEAT_PUMP:
            capability.value_off = "false"
            capability.value_on = "true"

    elif capabilityId == 171:
        # The cooling half of the absence setpoint, 172 being the heating one.
        # Read-only where 172 is a number : the app names it, and every capture
        # agrees on the unit, but nothing has been seen writing it. See
        # docs/decisions.md.
        if not modelInfos.get("awayModeTemperatureAvailable", True):
            return CapabilityInfos()

        capability.name = "away_mode_cooling_temperature"
        capability.type = CapabilityType.TEMPERATURE
        capability.category = CapabilityCategory.DIAG
        capability.enabled_by_default = False

    elif capabilityId == 172:
        # Absence setpoint. Only the heating products act on it. An air
        # conditioner reports it and stores what is written, but never reads it
        # back: absence there stops the units until the return date, and the
        # weekly program keeps driving 40 and 177 throughout. Exposing a number
        # nothing honours would promise a setting the Cozytouch app does not
        # even offer on this hardware.
        if not modelInfos.get("awayModeTemperatureAvailable", True):
            return CapabilityInfos()

        capability.name = "away_mode_temperature"
        capability.type = CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER
        capability.category = CapabilityCategory.SENSOR
        capability.lowestValueCapabilityId = 160
        capability.highestValueCapabilityId = 161

    elif capabilityId == 177:
        if modelInfos.type == CozytouchDeviceType.GAZ_BOILER:
            return CapabilityInfos()

        capability.name = "target_cool_temperature"
        capability.type = CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER
        capability.category = CapabilityCategory.SENSOR
        capability.lowestValueCapabilityId = 162
        capability.highestValueCapabilityId = 163

    elif capabilityId == 181:
        # Ignore, same as heat sensor (7, 8)
        return CapabilityInfos()

    elif capabilityId == 184:
        capability.name = "prog_mode"
        capability.type = CapabilityType.SWITCH
        capability.category = CapabilityCategory.SENSOR
        capability.icon = "mdi:clock-outline"

    elif 196 <= capabilityId <= 209:
        # Weekly program: two blocks of seven capabilities, monday first. On an
        # air conditioner the second block is the cooling program rather than a
        # second zone -- the app calls them "Chauffage" and "Refroidissement".
        index = capabilityId - 196
        if modelInfos.type == CozytouchDeviceType.AC:
            block = "heating" if index < 7 else "cooling"
            capability.name = f"prog_{block}_{PROGRAM_DAYS[index % 7]}"
        else:
            capability.name = f"prog_{index + 1:02d}_z{1 if index < 7 else 2}"

        capability.type = CapabilityType.PROG
        capability.category = CapabilityCategory.DIAG
        if _whole_block_reported(196 if index < 7 else 203, availableCapabilityIds):
            capability.enabled_by_default = False

    elif capabilityId == 218:
        # `wifiConnected` by name, but never the boolean it looks like : shown
        # raw and off by default. See docs/decisions.md. A zone gets nothing at
        # all, having no readings to go with it.
        if modelInfos.type is CozytouchDeviceType.ZONE:
            return CapabilityInfos()

        capability.name = "wifi_connected"
        capability.type = CapabilityType.STRING
        capability.category = CapabilityCategory.DIAG
        capability.icon = "mdi:wifi"
        capability.enabled_by_default = False

    elif capabilityId in (222, 226):
        capability.name = "away_mode"
        capability.type = CapabilityType.AWAY_MODE_TIMESTAMPS
        capability.category = CapabilityCategory.SENSOR
        capability.timestamps = (
            TimestampInfos("away_mode_start", "mdi:airplane-takeoff"),
            TimestampInfos("away_mode_stop", "mdi:airplane-landing"),
        )
        capability.timezoneCapabilityId = 315
        if capabilityId == 222:
            capability.capabilityDuplicate = 226
        else:
            capability.capabilityDuplicate = 222

    elif capabilityId == 231:
        capability.name = "target_temperature"
        capability.type = CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER
        capability.category = CapabilityCategory.SENSOR
        if modelId == 2374:
            capability.lowestValueCapabilityId = 253
            capability.highestValueCapabilityId = 252
            capability.step = 1
        else:
            capability.lowestValueCapabilityId = 105301
            capability.highestValueCapabilityId = 105304

    elif capabilityId == 233:
        capability.name = "boost_remaining_time"
        capability.type = CapabilityType.TIME
        capability.category = CapabilityCategory.DIAG
        capability.icon = "mdi:clock-outline"

    elif 237 <= capabilityId <= 243:
        # Domestic-hot-water weekly program, one capability per day, monday first.
        capability.name = f"dhw_prog_{PROGRAM_DAYS[capabilityId - 237]}"
        capability.type = CapabilityType.PROG
        capability.category = CapabilityCategory.DIAG
        if _whole_block_reported(237, availableCapabilityIds):
            capability.enabled_by_default = False

    elif capabilityId == 312:
        # Atlantic calls this one currentControlTarget, which matches the
        # setpoint shape read below -- but it gives 306 the same name, and 306 is
        # already mapped as a schedule bound. One of the two is wrong and nothing
        # here says which, so the placeholder name stays until a capture settles
        # it.
        capability.name = "Temp_" + str(capabilityId)
        capability.type = CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER
        capability.category = CapabilityCategory.SENSOR

    elif capabilityId == 100506:
        # Towel dryers only: no capture has one reporting it, and the branch
        # predates the room radiators, which do report it and are sold on the
        # presence detection.
        if modelInfos.type == CozytouchDeviceType.TOWEL_RACK:
            capability = CapabilityInfos()
        else:
            capability.name = "presence_mode"
            capability.type = CapabilityType.SWITCH
            capability.category = CapabilityCategory.SENSOR
            capability.icon = "mdi:account"

    elif capabilityId == 100507:
        # Same story as the absence setpoint in 172: the air conditioners report
        # eco mode without the Cozytouch app ever offering it. Reported is not
        # supported, so let the model table decide.
        if not modelInfos.get("ecoModeAvailable", True):
            return CapabilityInfos()

        capability.name = "eco_mode"
        capability.type = CapabilityType.SWITCH
        capability.category = CapabilityCategory.SENSOR
        capability.icon = "mdi:flower-outline"

    elif capabilityId in SELF_DESCRIBING_CAPABILITIES:
        capability.name, capability.type = SELF_DESCRIBING_CAPABILITIES[capabilityId]
        capability.category = CapabilityCategory.DIAG
        capability.enabled_by_default = False

    else:
        return None

    return capability
