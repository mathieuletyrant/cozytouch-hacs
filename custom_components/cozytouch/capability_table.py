"""The capability table : what each id is, on each product.

The mechanism that reads this lives in `capability.py`. Everything here is
data -- one row per capability id, and the tables that say what a descriptor's
number means. Adding a device means adding rows here; see CLAUDE.md.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from homeassistant.const import UnitOfEnergy, UnitOfPressure

from .const import PROGRAM_BLOCKS, CozytouchCapabilityVariableType, program_block
from .infos import (
    CapabilityCategory,
    CapabilityInfos,
    CapabilityType,
    ModelInfos,
    TimestampInfos,
)
from .model import CozytouchDeviceType

# Both report the same ids and mean the same things by them, so the rows that
# differ from the default differ together. See capability.py for why the API
# splits them at all.
ELECTRIC_HEATERS = (CozytouchDeviceType.TOWEL_RACK, CozytouchDeviceType.RADIATOR)

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


def hidden_by_a_calendar(capabilityId: int, availableCapabilityIds: set[int]) -> bool:
    """Whether this id is a program day whose whole block the device reports.

    All seven days is the calendar platform's condition for building one, so it
    is also the condition for the per-day sensors arriving disabled: a device
    with a partial block has no calendar, and its per-day sensors stay its only
    view. See docs/decisions.md.

    Which ids are program days is not declared on the rows -- PROGRAM_BLOCKS
    says where each block starts, and a row repeating that would be a number to
    keep in step by hand.
    """
    return any(
        capabilityId in program_block(first)
        and all(day in availableCapabilityIds for day in program_block(first))
        for first in PROGRAM_BLOCKS.values()
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
    enabled_by_default
            has no default on purpose : every row states it, so whether an
            entity shows up on a device page is answered by reading the row
            rather than by knowing what the field falls back to.
    bits    the value is a *sum*: one number saying several things at once.
            166 reading 411 is 1+2+4+16+128+256, so the unit does off, auto,
            cool, heat, fan and dry. The question it answers is "which of
            these can I do".
    reads_as
            the value is looked up whole. Usually that is an enum -- 73
            reading 4 is the fourth member, cooling_and_heating -- but not
            always: 350 reading 2 is "low, medium, high, auto", four speeds
            named by one number. Hence reads_as and not values, which would
            promise a member every time.

            At most one of the two, and the choice is not cosmetic: 4 read as
            a sum is the third flag, looked up whole it is the fourth member,
            and both readings look perfectly sensible. Only the id says which,
            which is why a row setting both fails a test. The way to tell them
            apart is whether the device can report two of these at once.
    extra   the remaining keys a platform reads off a capability -- the bounds
            of a number, a step, a modelList. Spelled out rather than given
            fields of their own, because each is read by one platform only.

    The last four say the same id does not mean the same thing on every
    product, which is why this is a table of rows rather than of strings :

    absent_on   device types with no such entity at all.
    needs_flag  a flag from model.py that has to hold for the entity to exist.
                A model that does not mention it is taken to have it.
    per_type    the keys to merge in last, for the device types named in the
                key -- a tuple, like absent_on, so two products reading an id
                the same way say so once.
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
    enabled_by_default: bool
    bits: tuple[tuple[int, str], ...] | None = None
    reads_as: Mapping[str, str] | None = None
    extra: Mapping[str, object] | None = None
    absent_on: tuple[CozytouchDeviceType, ...] = ()
    needs_flag: str | None = None
    per_type: (
        Mapping[tuple[CozytouchDeviceType, ...], Mapping[str, object]] | None
    ) = None
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
        if not self.enabled_by_default:
            capability.enabled_by_default = False
        overrides = [self.extra]
        overrides += [
            override
            for deviceTypes, override in (self.per_type or {}).items()
            if modelInfos.type in deviceTypes
        ]
        overrides.append((self.per_model or {}).get(modelInfos.modelId))
        for source in overrides:
            for key, setting in (source or {}).items():
                capability[key] = setting
        return capability


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
        enabled_by_default=True,
    ),
    22: Entity(
        name="target_temperature_dhw",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
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
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:water-pump",
    ),
    26: Entity(
        name="number_of_starts_dhw_pump",
        type=CapabilityType.INT,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:water-pump",
    ),
    28: Entity(
        name="number_of_hours_ch_pump",
        type=CapabilityType.INT,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:water-pump",
    ),
    29: Entity(
        name="number_of_hours_dhw_pump",
        type=CapabilityType.INT,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:water-pump",
    ),
    40: Entity(
        name="target_temperature",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
        extra={
            "lowestValueCapabilityId": 160,
            "highestValueCapabilityId": 161,
        },
    ),
    41: Entity(
        name="target_temperature_eco_z1",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
        extra={
            "lowestValueCapabilityId": 160,
            "highestValueCapabilityId": 161,
        },
    ),
    42: Entity(
        name="target_temperature_eco_z2",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
        extra={
            "lowestValueCapabilityId": 160,
            "highestValueCapabilityId": 161,
        },
    ),
    44: Entity(
        name="ch_power_consumption",
        type=CapabilityType.ENERGY,
        enabled_by_default=True,
        icon="mdi:radiator",
        extra={
            "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        },
    ),
    45: Entity(
        name="dhw_power_consumption",
        type=CapabilityType.ENERGY,
        enabled_by_default=True,
        icon="mdi:faucet",
        extra={
            "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        },
    ),
    46: Entity(
        name="total_power_consumption",
        type=CapabilityType.ENERGY,
        enabled_by_default=True,
        icon="mdi:water-boiler",
        extra={
            "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        },
    ),
    57: Entity(
        name="power_consumption",
        type=CapabilityType.ENERGY,
        enabled_by_default=True,
        extra={
            "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        },
    ),
    59: Entity(
        name="power_consumption",
        type=CapabilityType.ENERGY,
        enabled_by_default=True,
        extra={
            "displayed_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        },
    ),
    73: Entity(
        name="available_thermostat_modes",
        type=CapabilityType.STRING,
        reads_as={
            "0": "cooling_only",
            "1": "cooling_with_reheat",
            "2": "heating_only",
            "3": "heating_with_reheat",
            "4": "cooling_and_heating",
            "5": "cooling_and_heating_with_reheat",
        },
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    86: Entity(
        name="domestic_hot_water",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:faucet",
    ),
    87: Entity(
        name="domestic_hot_water_mode",
        type=CapabilityType.SELECT,
        enabled_by_default=True,
        icon="mdi:water-boiler",
        extra={
            "modelList": "HeatingModes",
        },
    ),
    88: Entity(
        name="model_name",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    93: Entity(
        name="zones_count",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    94: Entity(
        name="product_number",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    98: Entity(
        name="product_number",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    99: Entity(
        name="dhw_pump",
        type=CapabilityType.BINARY,
        enabled_by_default=True,
        icon="mdi:faucet",
        per_type={
            (CozytouchDeviceType.WATER_HEATER,): {
                "name": "resistance",
                "icon": "mdi:radiator",
            }
        },
    ),
    100: Entity(
        name="water_pressure",
        type=CapabilityType.PRESSURE,
        enabled_by_default=True,
        icon="mdi:gauge",
        extra={
            "displayed_unit_of_measurement": UnitOfPressure.BAR,
        },
    ),
    101: Entity(
        name="Capability_101",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        extra={"value_type": CozytouchCapabilityVariableType.ARRAY},
    ),
    102: Entity(
        name="Capability_102",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        extra={"value_type": CozytouchCapabilityVariableType.ARRAY},
    ),
    103: Entity(
        name="Capability_103",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        extra={"value_type": CozytouchCapabilityVariableType.ARRAY},
    ),
    104: Entity(
        name="Capability_104",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        extra={"value_type": CozytouchCapabilityVariableType.ARRAY},
    ),
    109: Entity(
        name="boiler_water_temperature",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
    ),
    111: Entity(
        name="dhw_temperature",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
    ),
    116: Entity(
        name="exhaust_temperature",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
        needs_flag="exhaustTemperatureAvailable",
    ),
    117: Entity(
        name="thermostat_temperature_z1",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
    ),
    118: Entity(
        name="thermostat_temperature_z2",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
    ),
    119: Entity(
        # Atlantic sends -327.68 rather than nothing when there is no probe.
        name="outside_temperature",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
        valid_above=-327.68,
    ),
    120: Entity(
        name="boiler_or_heat_pump",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    121: Entity(
        name="version",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    150: Entity(
        name="home_error_code",
        type=CapabilityType.ERROR_CODE,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:alert-circle-outline",
    ),
    152: Entity(
        name="away_mode",
        type=CapabilityType.AWAY_MODE_SWITCH,
        enabled_by_default=True,
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
        enabled_by_default=True,
        icon="mdi:fire",
        per_type={ELECTRIC_HEATERS: {"name": "resistance", "icon": "mdi:radiator"}},
    ),
    154: Entity(
        name="zone_1",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:home-floor-1",
    ),
    155: Entity(
        name="zone_2",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:home-floor-2",
    ),
    157: Entity(
        name="override_setpoint_activation",
        type=CapabilityType.BINARY,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    158: Entity(
        name="override_total_time_z1",
        type=CapabilityType.HOURS_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
        icon="mdi:clock-outline",
        extra={"lowest_value": 1, "highest_value": 24},
        per_type={ELECTRIC_HEATERS: {"name": "override_total_time"}},
    ),
    159: Entity(
        name="override_remain_time_z1",
        type=CapabilityType.TIME,
        enabled_by_default=True,
        icon="mdi:clock-outline",
        per_type={ELECTRIC_HEATERS: {"name": "override_remain_time"}},
    ),
    160: Entity(
        name="temperature_adjustment_min",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:thermometer-chevron-down",
    ),
    161: Entity(
        name="temperature_adjustment_max",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
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
        enabled_by_default=False,
    ),
    163: Entity(
        name="cooling_temperature_max",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    164: Entity(
        name="energy_consumption_supported",
        type=CapabilityType.STRING,
        bits=(
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
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    165: Entity(
        # water-boiler icon: a domestic-hot-water boost, not the generic boost.
        name="domestic_hot_water_boost",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:water-boiler",
        per_type={
            (CozytouchDeviceType.HEAT_PUMP,): {"value_off": "false", "value_on": "true"}
        },
    ),
    166: Entity(
        name="system_operating_mode",
        type=CapabilityType.STRING,
        bits=_HVAC_MODE_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    168: Entity(
        name="available_dhw_modes",
        type=CapabilityType.STRING,
        bits=_DHW_MODE_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    169: Entity(
        name="radio_signal",
        type=CapabilityType.PERCENTAGE,
        enabled_by_default=True,
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
        enabled_by_default=False,
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
        enabled_by_default=True,
        needs_flag="awayModeTemperatureAvailable",
        extra={"lowestValueCapabilityId": 160, "highestValueCapabilityId": 161},
    ),
    177: Entity(
        name="target_cool_temperature",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
        absent_on=(CozytouchDeviceType.GAZ_BOILER,),
        extra={"lowestValueCapabilityId": 162, "highestValueCapabilityId": 163},
    ),
    179: Entity(
        name="wifi_signal",
        type=CapabilityType.SIGNAL,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:wifi",
    ),
    184: Entity(
        name="prog_mode",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:clock-outline",
    ),
    188: Entity(
        name="home_services",
        type=CapabilityType.STRING,
        bits=(
            (1, "thermal_comfort"),
            (2, "dhw"),
            (4, "ventilation"),
            (8, "light"),
        ),
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    196: Entity(
        name="prog_01_z1",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_heating_monday"}},
    ),
    197: Entity(
        name="prog_02_z1",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_heating_tuesday"}},
    ),
    198: Entity(
        name="prog_03_z1",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_heating_wednesday"}},
    ),
    199: Entity(
        name="prog_04_z1",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_heating_thursday"}},
    ),
    200: Entity(
        name="prog_05_z1",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_heating_friday"}},
    ),
    201: Entity(
        name="prog_06_z1",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_heating_saturday"}},
    ),
    202: Entity(
        name="prog_07_z1",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_heating_sunday"}},
    ),
    203: Entity(
        name="prog_08_z2",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_cooling_monday"}},
    ),
    204: Entity(
        name="prog_09_z2",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_cooling_tuesday"}},
    ),
    205: Entity(
        name="prog_10_z2",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_cooling_wednesday"}},
    ),
    206: Entity(
        name="prog_11_z2",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_cooling_thursday"}},
    ),
    207: Entity(
        name="prog_12_z2",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_cooling_friday"}},
    ),
    208: Entity(
        name="prog_13_z2",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_cooling_saturday"}},
    ),
    209: Entity(
        name="prog_14_z2",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        per_type={(CozytouchDeviceType.AC,): {"name": "prog_cooling_sunday"}},
    ),
    217: Entity(
        name="system_setpoint_mode",
        type=CapabilityType.STRING,
        bits=_CONTROL_MODE_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
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
        enabled_by_default=False,
    ),
    219: Entity(
        name="wifi_ssid",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:wifi",
    ),
    222: Entity(
        name="away_mode",
        type=CapabilityType.AWAY_MODE_TIMESTAMPS,
        enabled_by_default=True,
        extra={
            "timestamps": AWAY_MODE_TIMESTAMPS,
            "timezoneCapabilityId": 315,
            "capabilityDuplicate": 226,
        },
    ),
    223: Entity(
        name="dhw_system_operating_mode",
        type=CapabilityType.STRING,
        bits=_DHW_HEATING_TYPE_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    224: Entity(
        name="dhw_estimation_supported",
        type=CapabilityType.STRING,
        bits=((2, "water_flow"),),
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    226: Entity(
        name="away_mode",
        type=CapabilityType.AWAY_MODE_TIMESTAMPS,
        enabled_by_default=True,
        extra={
            "timestamps": AWAY_MODE_TIMESTAMPS,
            "timezoneCapabilityId": 315,
            "capabilityDuplicate": 222,
        },
    ),
    227: Entity(
        name="away_mode",
        type=CapabilityType.AWAY_MODE_SWITCH,
        enabled_by_default=True,
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
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    230: Entity(
        name="dhw_operating_mode",
        type=CapabilityType.STRING,
        reads_as={
            "0": "heat",
            "1": "scheduled_heat",
            "2": "off_peak_heat",
        },
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    231: Entity(
        name="target_temperature",
        type=CapabilityType.TEMPERATURE_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
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
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:clock-outline",
    ),
    233: Entity(
        name="boost_remaining_time",
        type=CapabilityType.TIME,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:clock-outline",
    ),
    236: Entity(
        name="max_dhw_schedule_slots_per_day",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    237: Entity(
        name="dhw_prog_monday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    238: Entity(
        name="dhw_prog_tuesday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    239: Entity(
        name="dhw_prog_wednesday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    240: Entity(
        name="dhw_prog_thursday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    241: Entity(
        name="dhw_prog_friday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    242: Entity(
        name="dhw_prog_saturday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    243: Entity(
        name="dhw_prog_sunday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    244: Entity(
        name="max_schedule_ranges_per_day",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    245: Entity(
        name="prog_01",
        type=CapabilityType.PROGTIME,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    246: Entity(
        name="prog_02",
        type=CapabilityType.PROGTIME,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    247: Entity(
        name="prog_03",
        type=CapabilityType.PROGTIME,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    248: Entity(
        name="prog_04",
        type=CapabilityType.PROGTIME,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    249: Entity(
        name="prog_05",
        type=CapabilityType.PROGTIME,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    250: Entity(
        name="prog_06",
        type=CapabilityType.PROGTIME,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    251: Entity(
        name="prog_07",
        type=CapabilityType.PROGTIME,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    252: Entity(
        name="target_temperature_max",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    253: Entity(
        name="target_temperature_min",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    258: Entity(
        name="tank_capacity",
        type=CapabilityType.VOLUME,
        enabled_by_default=True,
    ),
    264: Entity(
        name="condenser_temperature",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
    ),
    265: Entity(
        name="tank_middle_temperature",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
    ),
    266: Entity(
        name="tank_top_temperature",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
    ),
    267: Entity(
        name="tank_bottom_temperature",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
    ),
    268: Entity(
        name="v40_water_available",
        type=CapabilityType.VOLUME,
        enabled_by_default=True,
        icon="mdi:water-thermometer",
    ),
    269: Entity(
        name="water_consumption",
        type=CapabilityType.WATER_CONSUMPTION,
        enabled_by_default=True,
        icon="mdi:water-pump",
    ),
    270: Entity(
        name="v40_water_capacity",
        type=CapabilityType.VOLUME,
        enabled_by_default=True,
        icon="mdi:water-thermometer",
    ),
    271: Entity(
        name="hot_water_available",
        type=CapabilityType.PERCENTAGE,
        enabled_by_default=True,
    ),
    280: Entity(
        name="cold_water_temperature",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
        icon="mdi:coolant-temperature",
    ),
    283: Entity(
        name="off_peak_hours",
        type=CapabilityType.BINARY,
        enabled_by_default=True,
        icon="mdi:clock-outline",
    ),
    290: Entity(
        name="dhw_error_code",
        type=CapabilityType.ERROR_CODE,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:alert-circle-outline",
    ),
    292: Entity(
        name="hot_water_showers_expected",
        type=CapabilityType.INT,
        enabled_by_default=True,
        icon="mdi:water-plus",
    ),
    293: Entity(
        name="hot_water_showers_remaining",
        type=CapabilityType.INT,
        enabled_by_default=True,
        icon="mdi:water-check",
    ),
    294: Entity(
        name="target_temperature_step",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    295: Entity(
        name="schedule_time_step",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    296: Entity(
        name="schedule_minimum_interval",
        type=CapabilityType.TIME,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    303: Entity(
        name="error_code",
        type=CapabilityType.ERROR_CODE,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:alert-circle-outline",
    ),
    306: Entity(
        name="max_schedule_slots_per_day",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    307: Entity(
        name="heating_period_min_duration",
        type=CapabilityType.TIME,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    312: Entity(
        # Read-only: the app has a getter and no writer, unlike 231 beside it.
        # See docs/decisions.md.
        name="dhw_current_control_target",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
    ),
    315: Entity(
        name="timezone",
        type=CapabilityType.TIMEZONE,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:map-clock-outline",
    ),
    316: Entity(
        name="interface_fw",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    329: Entity(
        name="min_schedule_ranges_per_day",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    330: Entity(
        name="schedule_range_step",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    331: Entity(
        name="schedule_range_max_duration",
        type=CapabilityType.TIME,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    332: Entity(
        name="schedule_range_min_duration",
        type=CapabilityType.TIME,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    333: Entity(
        name="heating_period_max_duration",
        type=CapabilityType.TIME,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    335: Entity(
        name="serial_number",
        type=CapabilityType.STRING,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:tag",
    ),
    336: Entity(
        name="dhw_panel_capabilities",
        type=CapabilityType.STRING,
        bits=(
            (1, "v40_state_of_charge"),
            (2, "main_setpoint_cursor"),
            (4, "secondary_setpoint_cursor"),
            (8, "data_inside"),
        ),
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    337: Entity(
        name="main_cursor_information",
        type=CapabilityType.STRING,
        reads_as={
            "0": "nothing",
            "1": "away",
            "2": "boost",
            "3": "photovoltaic",
            "4": "smart_grid",
            "5": "antilegionella",
            "6": "water_setpoint",
        },
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    338: Entity(
        name="secondary_cursor_information",
        type=CapabilityType.STRING,
        reads_as={
            "0": "nothing",
            "1": "eco",
            "2": "water_setpoint",
        },
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    339: Entity(
        name="dhw_panel_data",
        type=CapabilityType.STRING,
        reads_as={
            "0": "nothing",
            "1": "v40_state_of_charge",
            "2": "water_setpoint",
        },
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    340: Entity(
        name="water_setpoint_step",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    344: Entity(
        name="linked_interfaces_count",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    350: Entity(
        name="air_circulation_supported_speeds",
        type=CapabilityType.STRING,
        reads_as=_SPEED_SETS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    351: Entity(
        name="connectivity_display_capabilities",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    352: Entity(
        name="absence_day_heating_temperature",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    353: Entity(
        name="presence_day_heating_temperature",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    354: Entity(
        name="presence_night_heating_temperature",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    355: Entity(
        name="absence_day_cooling_temperature",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    356: Entity(
        name="presence_day_cooling_temperature",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    357: Entity(
        name="presence_night_cooling_temperature",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    358: Entity(
        name="air_circulation_scope",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    381: Entity(
        name="ble_pairing_compatibility",
        type=CapabilityType.BINARY,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100000: Entity(
        name="thermal_zones_count",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100002: Entity(
        name="supported_estimation_modes",
        type=CapabilityType.STRING,
        bits=_VENTILATION_OPTION_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100004: Entity(
        name="available_control_modes",
        type=CapabilityType.STRING,
        bits=_VENTILATION_CONTROL_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100013: Entity(
        name="available_schedule_types",
        type=CapabilityType.STRING,
        bits=(
            (1, "on_off"),
            (2, "boost"),
        ),
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100021: Entity(
        name="supported_control_modes",
        type=CapabilityType.STRING,
        bits=_VENTILATION_CONTROL_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100022: Entity(
        name="supported_system_operating_modes",
        type=CapabilityType.STRING,
        bits=_HVAC_MODE_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100023: Entity(
        name="supported_system_modes",
        type=CapabilityType.STRING,
        bits=_CONTROL_MODE_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100024: Entity(
        name="available_estimation_modes",
        type=CapabilityType.STRING,
        bits=_VENTILATION_OPTION_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100078: Entity(
        name="identify_supported",
        type=CapabilityType.BINARY,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100102: Entity(
        name="adaptive_planning",
        type=CapabilityType.BINARY,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100103: Entity(
        name="unexpected_events",
        type=CapabilityType.BINARY,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100196: Entity(
        name="absence_schedule",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100197: Entity(
        name="night_target_temperature",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100198: Entity(
        name="presence_target_temperature",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100261: Entity(
        name="away_mode",
        type=CapabilityType.BINARY,
        enabled_by_default=True,
        icon="mdi:airplane",
    ),
    100300: Entity(
        name="schedule_start_day",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100301: Entity(
        name="max_schedule_slots_per_week",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100320: Entity(
        name="prog_heat_monday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100321: Entity(
        name="prog_heat_tuesday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100322: Entity(
        name="prog_heat_wednesday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100323: Entity(
        name="prog_heat_thursday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100324: Entity(
        name="prog_heat_friday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100325: Entity(
        name="prog_heat_saturday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100326: Entity(
        name="prog_heat_sunday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100327: Entity(
        name="prog_cool_monday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100328: Entity(
        name="prog_cool_tuesday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100329: Entity(
        name="prog_cool_wednesday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100330: Entity(
        name="prog_cool_thursday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100331: Entity(
        name="prog_cool_friday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100332: Entity(
        name="prog_cool_saturday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100333: Entity(
        name="prog_cool_sunday",
        type=CapabilityType.PROG,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    100334: Entity(
        name="new_schedule_monday",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100335: Entity(
        name="new_schedule_tuesday",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100336: Entity(
        name="new_schedule_wednesday",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100337: Entity(
        name="new_schedule_thursday",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100338: Entity(
        name="new_schedule_friday",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100339: Entity(
        name="new_schedule_saturday",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100341: Entity(
        name="new_schedule_sunday",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100402: Entity(
        name="number_of_hours_burner",
        type=CapabilityType.INT,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:fire",
    ),
    100406: Entity(
        name="number_of_starts_burner",
        type=CapabilityType.INT,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:fire",
    ),
    100450: Entity(
        name="schedule_anticipation",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:clock-fast",
    ),
    100503: Entity(
        name="wifi_fw",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100505: Entity(
        name="powerful_mode",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:wind-power",
    ),
    100506: Entity(
        # Towel dryers only: no capture has one reporting it, and the branch
        # predates the room radiators, which do report it and are sold on the
        # presence detection.
        name="presence_mode",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:account",
        absent_on=(CozytouchDeviceType.TOWEL_RACK,),
    ),
    100507: Entity(
        # Same story as the absence setpoint in 172: the air conditioners report
        # eco mode without the Cozytouch app ever offering it. Reported is not
        # supported, so let the model table decide.
        name="eco_mode",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:flower-outline",
        needs_flag="ecoModeAvailable",
    ),
    100800: Entity(
        name="available_fan_speeds",
        type=CapabilityType.STRING,
        reads_as=_SPEED_SETS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    100802: Entity(
        name="quiet_mode",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:fan-minus",
    ),
    100804: Entity(
        name="swing_mode",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:arrow-oscillating",
    ),
    102004: Entity(
        name="air_circulation_speed",
        type=CapabilityType.SELECT,
        enabled_by_default=True,
        icon="mdi:fan",
        extra={
            "modelList": "AirCirculationSpeeds",
        },
    ),
    102005: Entity(
        name="air_circulation_supported_modes",
        type=CapabilityType.STRING,
        bits=_AIR_CIRCULATION_MODE_BITS,
        category=CapabilityCategory.DIAG,
        icon="mdi:fan",
        enabled_by_default=False,
    ),
    102006: Entity(
        name="air_circulation_available_modes",
        type=CapabilityType.STRING,
        bits=_AIR_CIRCULATION_MODE_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    102020: Entity(
        name="air_circulation_current_mode",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    102021: Entity(
        name="air_circulation_total_time",
        type=CapabilityType.DURATION_SELECT,
        enabled_by_default=True,
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
        enabled_by_default=False,
    ),
    102023: Entity(
        name="air_circulation_remaining_time",
        type=CapabilityType.TIME,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:fan-clock",
    ),
    102024: Entity(
        name="air_circulation",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:fan",
    ),
    102025: Entity(
        name="air_circulation_time_min",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:fan-clock",
        enabled_by_default=False,
    ),
    102026: Entity(
        name="air_circulation_time_max",
        type=CapabilityType.INT,
        category=CapabilityCategory.DIAG,
        icon="mdi:fan-clock",
        enabled_by_default=False,
    ),
    103034: Entity(
        name="room_controls_capabilities",
        type=CapabilityType.STRING,
        bits=((16, "antifrost"),),
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    103150: Entity(
        name="ambient_temperature_available",
        type=CapabilityType.BINARY,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    103199: Entity(
        name="antifrost_temperature",
        type=CapabilityType.TEMPERATURE,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    103450: Entity(
        name="schedule_anticipation_state",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    104044: Entity(
        name="boost_mode",
        type=CapabilityType.SWITCH,
        enabled_by_default=True,
        icon="mdi:heat-wave",
    ),
    104047: Entity(
        name="boost_timeout_max",
        type=CapabilityType.MINUTES_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
        icon="mdi:clock-outline",
        extra={
            "lowest_value": 5,
            "highest_value": 60,
            "step": 5,
        },
    ),
    104050: Entity(
        name="open_window_detection",
        type=CapabilityType.BINARY,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    104051: Entity(
        name="open_window_state",
        type=CapabilityType.BINARY,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    105011: Entity(
        name="supported_dhw_modes",
        type=CapabilityType.STRING,
        bits=_DHW_MODE_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    105012: Entity(
        name="supported_dhw_system_operating_modes",
        type=CapabilityType.STRING,
        bits=_DHW_HEATING_TYPE_BITS,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    105122: Entity(
        name="dhw_boost_end_timestamp",
        type=CapabilityType.STRING,
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    105300: Entity(
        name="water_temperature_limit",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    105304: Entity(
        name="max_target_temperature_derogation",
        type=CapabilityType.TEMPERATURE,
        enabled_by_default=True,
        category=CapabilityCategory.DIAG,
    ),
    105636: Entity(
        name="dhw_comfort_mode",
        type=CapabilityType.STRING,
        reads_as={
            "0": "eco",
            "1": "comfort",
        },
        category=CapabilityCategory.DIAG,
        enabled_by_default=False,
    ),
    105906: Entity(
        name="v40_applied_setpoint",
        type=CapabilityType.TEMPERATURE_PERCENT_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
        extra={
            "temperatureMin": 15.0,
            "temperatureMax": 65.0,
        },
    ),
    105907: Entity(
        name="v40_setpoint_filled_by_user",
        type=CapabilityType.TEMPERATURE_PERCENT_ADJUSTMENT_NUMBER,
        enabled_by_default=True,
        extra={
            "temperatureMin": 15.0,
            "temperatureMax": 65.0,
        },
    ),
}
