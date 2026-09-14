"""How a capability id becomes an entity.

The mechanism only : which row answers an id, how a descriptor's number
reads, and the handful of ids no row can decide. The rows themselves are in
`capability_table.py`, which is the file to open to add a device.
"""

from .capability_table import (
    CAPABILITIES,
    CAPABILITY_BIT_FIELDS,
    CAPABILITY_SPEED_SETS,
    CAPABILITY_VALUE_SPACES,
    ELECTRIC_HEATERS,
    SELF_DESCRIBING_CAPABILITIES,
)
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
        capability = CAPABILITIES[capabilityId].resolve(capability, modelInfos)

    elif capabilityId in (101, 102, 103, 104):
        capability.name = "Capability_" + str(capabilityId)
        capability.type = CapabilityType.STRING
        capability.value_type = CozytouchCapabilityVariableType.ARRAY
        capability.category = CapabilityCategory.SENSOR

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

    elif capabilityId in SELF_DESCRIBING_CAPABILITIES:
        capability.name, capability.type = SELF_DESCRIBING_CAPABILITIES[capabilityId]
        capability.category = CapabilityCategory.DIAG
        capability.enabled_by_default = False

    else:
        return None

    return capability
