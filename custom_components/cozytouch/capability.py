"""Atlantic Cozytouch capabilility mapping."""

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

# Capabilities the device uses to describe itself: what it supports, what its
# scheduler allows, which controls exist. The name below is everything that is
# known about each one, it was not read off this hardware, and any of them can
# turn out to be wrong: none says what the unit is, how the value is encoded, or
# how to read a bitmask.
#
# So they are surfaced as raw strings under a real name and switched off by
# default: there for anyone investigating their own hardware, invisible to
# everyone else. A device reports dozens of these, and turning them all on for
# every user would bury the handful of entities that mean something.
#
# Promoting one to a typed entity takes someone watching it change against the
# Cozytouch app and reporting what it does. Until then, the honest thing is to
# show the value and not claim to know what it is.
SELF_DESCRIBING_CAPABILITIES = {
    73: "available_thermostat_modes",
    93: "zones_count",
    120: "boiler_or_heat_pump",
    157: "override_setpoint_activation",
    164: "energy_consumption_supported",
    166: "system_operating_mode",
    168: "available_dhw_modes",
    188: "home_services",
    217: "system_setpoint_mode",
    223: "dhw_system_operating_mode",
    224: "dhw_estimation_supported",
    230: "dhw_operating_mode",
    236: "max_dhw_schedule_slots_per_day",
    294: "target_temperature_step",
    295: "schedule_time_step",
    296: "schedule_minimum_interval",
    306: "max_schedule_slots_per_day",
    307: "heating_period_min_duration",
    329: "min_schedule_ranges_per_day",
    330: "schedule_range_step",
    331: "schedule_range_max_duration",
    332: "schedule_range_min_duration",
    333: "heating_period_max_duration",
    336: "dhw_panel_capabilities",
    337: "main_cursor_information",
    338: "secondary_cursor_information",
    339: "dhw_panel_data",
    340: "water_setpoint_step",
    344: "linked_interfaces_count",
    350: "air_circulation_supported_speeds",
    351: "connectivity_display_capabilities",
    358: "air_circulation_scope",
    381: "ble_pairing_compatibility",
    100002: "supported_estimation_modes",
    100004: "available_control_modes",
    100013: "available_schedule_types",
    100021: "supported_control_modes",
    100022: "supported_system_operating_modes",
    100023: "supported_system_modes",
    100024: "available_estimation_modes",
    100078: "identify_supported",
    100102: "adaptive_planning",
    100103: "unexpected_events",
    100197: "night_target_temperature",
    100198: "presence_target_temperature",
    100300: "schedule_start_day",
    100301: "max_schedule_slots_per_week",
    100334: "new_schedule_monday",
    100335: "new_schedule_tuesday",
    100336: "new_schedule_wednesday",
    100337: "new_schedule_thursday",
    100338: "new_schedule_friday",
    100339: "new_schedule_saturday",
    100341: "new_schedule_sunday",
    100503: "wifi_fw",
    100800: "available_fan_speeds",
    103034: "room_controls_capabilities",
    103150: "ambient_temperature_available",
    103199: "antifrost_temperature",
    103450: "schedule_anticipation_state",
    104050: "open_window_detection",
    104051: "open_window_state",
    105012: "supported_dhw_system_operating_modes",
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

# The speed selectors name a whole set rather than one speed, so each value
# spells its set out.
_SPEED_SETS = {
    "0": "low, medium, high",
    "1": "low, high",
    "2": "low, medium, high, auto",
    "3": "low, high, auto",
    "4": "on, auto",
}

# What the numbers in the table above mean. The ventilation control and option
# masks the app also carries are deliberately absent: on the captures a tenth
# of their readings set a bit past the last member the app names (128 on
# 100004/100021, 104 on 100002, and 124 on 224's single-bit mask), so either
# those ids are not what the app calls them or the enum read out of it is
# partial. Naming the low bits of a mask whose top bits are unexplained is how
# a wrong reading gets believed.
# The vendor's Android app decodes
# them in plain Kotlin, and every entry here was read off it and then checked
# against the capture corpus -- see docs/decisions.md. A member can claim
# several bits at once, which is how the app reads them: it matches on any bit
# of the member's mask, not on the whole of it.
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
    336: (
        (1, "v40_state_of_charge"),
        (2, "main_setpoint_cursor"),
        (4, "secondary_setpoint_cursor"),
        (8, "data_inside"),
    ),
    100013: ((1, "on_off"),),
    100022: _HVAC_MODE_BITS,
    100023: _CONTROL_MODE_BITS,
    102005: _AIR_CIRCULATION_MODE_BITS,
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
    350: _SPEED_SETS,
    100800: _SPEED_SETS,
}


def describe_capability_value(capabilityId: int, value) -> str | None:
    """Read a descriptor capability as what it says, or None if nothing does.

    Bits nothing names are kept as a count rather than dropped: these entities
    exist to investigate hardware nobody here owns, and a bit the tables do not
    cover is exactly what such a reader is after.
    """
    space = CAPABILITY_VALUE_SPACES.get(capabilityId)
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
        capabilityId in availableCapabilityIds
        for capabilityId in program_block(first)
    )


def _by_id(table: dict) -> dict[int, dict]:
    """One entry per capability id, from a table whose keys may name several."""
    return {
        capabilityId: fields
        for key, fields in table.items()
        for capabilityId in (key if isinstance(key, tuple) else (key,))
    }


# Every capability whose whole mapping is a set of fixed fields: a name, a
# type, a category, and sometimes an icon or a bound. Ninety-eight of the
# hundred and twenty ids this module knows are one of those, which is why they
# are a table rather than a hundred branches. What is left in
# get_capability_infos below is the twenty-odd whose answer depends on the
# model, on the device's other capabilities, or on the value itself.
#
# A key naming several ids gives every one of them the same fields.
SIMPLE_CAPABILITIES: dict[int, dict] = _by_id({
    19: {
        "name": "temperature_setpoint",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.SENSOR,
    },
    25: {
        "name": "number_of_starts_ch_pump",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:water-pump",
    },
    26: {
        "name": "number_of_starts_dhw_pump",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:water-pump",
    },
    28: {
        "name": "number_of_hours_ch_pump",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:water-pump",
    },
    29: {
        "name": "number_of_hours_dhw_pump",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:water-pump",
    },
    40: {
        "name": "target_temperature",
        "type": CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        "category": CapabilityCategory.SENSOR,
        "lowestValueCapabilityId": 160,
        "highestValueCapabilityId": 161,
    },
    41: {
        "name": "target_temperature_eco_z1",
        "type": CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        "category": CapabilityCategory.SENSOR,
        "lowestValueCapabilityId": 160,
        "highestValueCapabilityId": 161,
    },
    42: {
        "name": "target_temperature_eco_z2",
        "type": CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        "category": CapabilityCategory.SENSOR,
        "lowestValueCapabilityId": 160,
        "highestValueCapabilityId": 161,
    },
    44: {
        "name": "ch_power_consumption",
        "type": CapabilityType.ENERGY,
        "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:radiator",
    },
    45: {
        "name": "dhw_power_consumption",
        "type": CapabilityType.ENERGY,
        "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:faucet",
    },
    46: {
        "name": "total_power_consumption",
        "type": CapabilityType.ENERGY,
        "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:water-boiler",
    },
    (57, 59): {
        "name": "power_consumption",
        "type": CapabilityType.ENERGY,
        "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        "category": CapabilityCategory.SENSOR,
    },
    86: {
        "name": "domestic_hot_water",
        "type": CapabilityType.SWITCH,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:faucet",
    },
    # water-boiler icon: this is the domestic-hot-water mode, not heating.
    87: {
        "name": "domestic_hot_water_mode",
        "type": CapabilityType.SELECT,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:water-boiler",
        "modelList": "HeatingModes",
    },
    88: {
        "name": "model_name",
        "type": CapabilityType.STRING,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:tag",
    },
    (94, 98): {
        "name": "product_number",
        "type": CapabilityType.STRING,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:tag",
    },
    100: {
        "name": "water_pressure",
        "type": CapabilityType.PRESSURE,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:gauge",
        "displayed_unit_of_measurement": UnitOfPressure.BAR,
    },
    109: {
        "name": "boiler_water_temperature",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.SENSOR,
    },
    111: {
        "name": "dhw_temperature",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.SENSOR,
    },
    117: {
        "name": "thermostat_temperature_z1",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.SENSOR,
    },
    118: {
        "name": "thermostat_temperature_z2",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.SENSOR,
    },
    121: {
        "name": "version",
        "type": CapabilityType.STRING,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:tag",
    },
    154: {
        "name": "zone_1",
        "type": CapabilityType.STRING,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:home-floor-1",
    },
    155: {
        "name": "zone_2",
        "type": CapabilityType.STRING,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:home-floor-2",
    },
    # Target temperature adjustment min limit
    160: {
        "name": "temperature_adjustment_min",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:thermometer-chevron-down",
    },
    # Target temperature adjustment max limit
    161: {
        "name": "temperature_adjustment_max",
        "type": CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:thermometer-chevron-up",
        "lowest_value": 19,
        "highest_value": 28,
        "step": 0.5,
    },
    169: {
        "name": "radio_signal",
        "type": CapabilityType.PERCENTAGE,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:radio-tower",
    },
    179: {
        "name": "wifi_signal",
        "type": CapabilityType.SIGNAL,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:wifi",
    },
    # Ignore, same as heat sensor (7, 8)
    184: {
        "name": "prog_mode",
        "type": CapabilityType.SWITCH,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:clock-outline",
    },
    # Room fault code: a matrix of [system, majorCode, minorCode, level]
    # rows, all-zero when healthy. The type decodes it to a code list;
    # see sensor.py and docs/decisions.md for the format and its limits.
    303: {
        "name": "error_code",
        "type": CapabilityType.ERROR_CODE,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:alert-circle-outline",
    },
    219: {
        "name": "wifi_ssid",
        "type": CapabilityType.STRING,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:wifi",
    },
    228: {
        "name": "absence_dhw_temperature",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.DIAG,
    },
    232: {
        "name": "boost_total_time",
        "type": CapabilityType.TIME,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:clock-outline",
    },
    233: {
        "name": "boost_remaining_time",
        "type": CapabilityType.TIME,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:clock-outline",
    },
    245: {
        "name": "prog_01",
        "type": CapabilityType.PROGTIME,
        "category": CapabilityCategory.DIAG,
    },
    246: {
        "name": "prog_02",
        "type": CapabilityType.PROGTIME,
        "category": CapabilityCategory.DIAG,
    },
    247: {
        "name": "prog_03",
        "type": CapabilityType.PROGTIME,
        "category": CapabilityCategory.DIAG,
    },
    248: {
        "name": "prog_04",
        "type": CapabilityType.PROGTIME,
        "category": CapabilityCategory.DIAG,
    },
    249: {
        "name": "prog_05",
        "type": CapabilityType.PROGTIME,
        "category": CapabilityCategory.DIAG,
    },
    250: {
        "name": "prog_06",
        "type": CapabilityType.PROGTIME,
        "category": CapabilityCategory.DIAG,
    },
    251: {
        "name": "prog_07",
        "type": CapabilityType.PROGTIME,
        "category": CapabilityCategory.DIAG,
    },
    252: {
        "name": "target_temperature_max",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.DIAG,
    },
    253: {
        "name": "target_temperature_min",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.DIAG,
    },
    258: {
        "name": "tank_capacity",
        "type": CapabilityType.VOLUME,
        "category": CapabilityCategory.SENSOR,
    },
    264: {
        "name": "condenser_temperature",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.SENSOR,
    },
    265: {
        "name": "tank_middle_temperature",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.SENSOR,
    },
    266: {
        "name": "tank_top_temperature",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.SENSOR,
    },
    267: {
        "name": "tank_bottom_temperature",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.SENSOR,
    },
    268: {
        "name": "v40_water_available",
        "type": CapabilityType.VOLUME,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:water-thermometer",
    },
    269: {
        "name": "water_consumption",
        "type": CapabilityType.WATER_CONSUMPTION,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:water-pump",
    },
    270: {
        "name": "v40_water_capacity",
        "type": CapabilityType.VOLUME,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:water-thermometer",
    },
    271: {
        "name": "hot_water_available",
        "type": CapabilityType.PERCENTAGE,
        "category": CapabilityCategory.SENSOR,
    },
    280: {
        "name": "cold_water_temperature",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:coolant-temperature",
    },
    283: {
        "name": "off_peak_hours",
        "type": CapabilityType.BINARY,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:clock-outline",
    },
    # Not a level: the app counts showers. Atlantic water heaters display a
    # number of expected/remaining showers rather than a percentage.
    292: {
        "name": "hot_water_showers_expected",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:water-plus",
    },
    # Remaining showers, the counterpart of 292 -- see the note there.
    293: {
        "name": "hot_water_showers_remaining",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:water-check",
    },
    315: {
        "name": "timezone",
        "type": CapabilityType.TIMEZONE,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:map-clock-outline",
    },
    316: {
        "name": "interface_fw",
        "type": CapabilityType.STRING,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:tag",
    },
    335: {
        "name": "serial_number",
        "type": CapabilityType.STRING,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:tag",
    },
    # Per-room mirror of the hub's away mode flag (152). The room units carry
    # it alongside the absence window in 100260, which stays unmapped: the
    # window is written for the whole setup from the hub, not room by room.
    100261: {
        "name": "away_mode",
        "type": CapabilityType.BINARY,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:airplane",
    },
    100402: {
        "name": "number_of_hours_burner",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:fire",
    },
    100406: {
        "name": "number_of_starts_burner",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:fire",
    },
    # The vendor app's "Anticipation de chauffe"; 0/1 encoding verified on
    # a live toggle -- see docs/decisions.md.
    100450: {
        "name": "schedule_anticipation",
        "type": CapabilityType.SWITCH,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:clock-fast",
    },
    100505: {
        "name": "powerful_mode",
        "type": CapabilityType.SWITCH,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:wind-power",
    },
    100320: {
        "name": "prog_heat_monday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100321: {
        "name": "prog_heat_tuesday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100322: {
        "name": "prog_heat_wednesday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100323: {
        "name": "prog_heat_thursday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100324: {
        "name": "prog_heat_friday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100325: {
        "name": "prog_heat_saturday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100326: {
        "name": "prog_heat_sunday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100327: {
        "name": "prog_cool_monday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100328: {
        "name": "prog_cool_tuesday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100329: {
        "name": "prog_cool_wednesday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100330: {
        "name": "prog_cool_thursday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100331: {
        "name": "prog_cool_friday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100332: {
        "name": "prog_cool_saturday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100333: {
        "name": "prog_cool_sunday",
        "type": CapabilityType.PROG,
        "category": CapabilityCategory.DIAG,
    },
    100802: {
        "name": "quiet_mode",
        "type": CapabilityType.SWITCH,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:fan-minus",
    },
    100804: {
        "name": "swing_mode",
        "type": CapabilityType.SWITCH,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:arrow-oscillating",
    },
    102004: {
        "name": "air_circulation_speed",
        "type": CapabilityType.SELECT,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:fan",
        "modelList": "AirCirculationSpeeds",
    },
    # Air circulation runs for a set number of minutes, and the app offers
    # the duration as a picker on a grid the device itself declares --
    # 102025 the minimum, 102026 the maximum, 102022 the step. A select
    # built from those rather than a free number; see docs/decisions.md.
    # The grid capabilities stay exposed as their own diag entities below.
    # The corpus values, for a device reporting the duration without its
    # grid.
    102021: {
        "name": "air_circulation_total_time",
        "type": CapabilityType.DURATION_SELECT,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:fan-clock",
        "lowestValueCapabilityId": 102025,
        "highestValueCapabilityId": 102026,
        "stepCapabilityId": 102022,
        "lowest_value": 15,
        "highest_value": 300,
        "step": 15,
    },
    102023: {
        "name": "air_circulation_remaining_time",
        "type": CapabilityType.TIME,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:fan-clock",
    },
    102024: {
        "name": "air_circulation",
        "type": CapabilityType.SWITCH,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:fan",
    },
    # Home-level fault code, sibling of the room (303) and DHW (290) codes,
    # same matrix shape and decoding.
    150: {
        "name": "home_error_code",
        "type": CapabilityType.ERROR_CODE,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:alert-circle-outline",
    },
    # DHW fault code, same matrix shape and decoding as the room code (303).
    290: {
        "name": "dhw_error_code",
        "type": CapabilityType.ERROR_CODE,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:alert-circle-outline",
    },
    # The set of air-circulation modes this device supports -- a static
    # descriptor bitmask, not a control. Off by default like every other
    # supported_*/available_* descriptor (which reach that state through
    # SELF_DESCRIBING_CAPABILITIES); this one has its own branch and was
    # the lone one left visible.
    102005: {
        "name": "air_circulation_supported_modes",
        "type": CapabilityType.STRING,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:fan",
        "enabled_by_default": False,
    },
    # Step for the air-circulation duration (102021).
    102022: {
        "name": "air_circulation_time_step",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:fan-clock",
        "enabled_by_default": False,
    },
    # Minimum air-circulation duration; the lower bound of 102021.
    102025: {
        "name": "air_circulation_time_min",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:fan-clock",
        "enabled_by_default": False,
    },
    # Maximum air-circulation duration; the upper bound of 102021.
    102026: {
        "name": "air_circulation_time_max",
        "type": CapabilityType.INT,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:fan-clock",
        "enabled_by_default": False,
    },
    104044: {
        "name": "boost_mode",
        "type": CapabilityType.SWITCH,
        "category": CapabilityCategory.SENSOR,
        "icon": "mdi:heat-wave",
    },
    # Boost timeout max. in minutes
    104047: {
        "name": "boost_timeout_max",
        "type": CapabilityType.MINUTES_ADJUSTMENT_NUMBER,
        "category": CapabilityCategory.DIAG,
        "icon": "mdi:clock-outline",
        "lowest_value": 5,
        "highest_value": 60,
        "step": 5,
    },
    105300: {
        "name": "water_temperature_limit",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.DIAG,
    },
    105304: {
        "name": "max_target_temperature_derogation",
        "type": CapabilityType.TEMPERATURE,
        "category": CapabilityCategory.DIAG,
    },
    105906: {
        "name": "Target 105906",
        "type": CapabilityType.TEMPERATURE_PERCENT_ADJUSTMENT_NUMBER,
        "category": CapabilityCategory.SENSOR,
        "temperatureMin": 15.0,
        "temperatureMax": 65.0,
    },
    105907: {
        "name": "Target 105907",
        "type": CapabilityType.TEMPERATURE_PERCENT_ADJUSTMENT_NUMBER,
        "category": CapabilityCategory.SENSOR,
        "temperatureMin": 15.0,
        "temperatureMax": 65.0,
    },
})


def get_capability_infos(  # noqa: C901
    modelInfos: ModelInfos,
    capabilityId: int,
    capabilityValue: str,
    availableCapabilityIds: set[int],
) -> CapabilityInfos | None:
    """Get capabilities for a device.

    availableCapabilityIds is what the device actually reports. Optional
    features are declared per model, but the same model id is reused across
    hardware that does not always implement them, so they are only wired up
    when the device backs them.
    """
    modelId = modelInfos.modelId

    capability = CapabilityInfos(modelId=modelId, capabilityId=capabilityId)

    if capabilityId in SIMPLE_CAPABILITIES:
        capability.update(SIMPLE_CAPABILITIES[capabilityId])
        return capability

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
        # `wifiConnected` by name, but not the boolean it looks like. Every
        # capture reads "0" (occasionally "4") and never "1", so the connected
        # sensor -- is_on is value == "1" -- sat permanently at "disconnected"
        # on hardware that was plainly online, and every unit behind a gateway
        # reported it too though only the gateway has a radio. The app does not
        # surface it: it reads a device's `isAvailable` for connectivity. The
        # 0/4 encoding is unknown (see docs/decisions.md), so it is shown raw
        # and off by default rather than as a flag that is always wrong.
        #
        # A zone still gets nothing at all: it has no readings, and the
        # fall-through would give it a lone disabled sensor.
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

    elif 237 <= capabilityId <= 243:
        # Domestic-hot-water weekly program, one capability per day, monday first.
        capability.name = f"dhw_prog_{PROGRAM_DAYS[capabilityId - 237]}"
        capability.type = CapabilityType.PROG
        capability.category = CapabilityCategory.DIAG
        if _whole_block_reported(237, availableCapabilityIds):
            capability.enabled_by_default = False

    # For test
    elif capabilityId == 312:
        # Atlantic calls this one currentControlTarget, which matches the
        # setpoint shape read below -- but it gives 306 the same name, and 306 is
        # already mapped as a schedule bound. One of the two is wrong and nothing
        # here says which, so the placeholder name stays until a capture settles
        # it.
        capability.name = "Temp_" + str(capabilityId)
        capability.type = CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER
        capability.category = CapabilityCategory.SENSOR

    elif capabilityId in SELF_DESCRIBING_CAPABILITIES:
        capability.name = SELF_DESCRIBING_CAPABILITIES[capabilityId]
        capability.type = CapabilityType.STRING
        capability.category = CapabilityCategory.DIAG
        capability.enabled_by_default = False

    else:
        return None

    return capability
