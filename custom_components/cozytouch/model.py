"""Atlantic Cozytouch device model mapping.

Every device the Cozytouch cloud reports carries a number, its modelId. This
module turns that number into what the integration needs to know: the
commercial name to show, the kind of device it is, and which optional features
it may have.

===========================================================================
ADDING A DEVICE
===========================================================================

You need two things: the modelId, and the commercial name of the product.

To find the modelId, download a diagnostics dump -- Settings, Devices &
Services, Atlantic Cozytouch, the three dots on the device, then Download
diagnostics. An unmapped device appears there as "Unknown product (1234)".

Then add one line to the MODELS table below, in numeric order, choosing the
profile that matches the kind of device:

    1234: ("Atlantic Whatever 200L", WATER_HEATER),

That is the whole change for most devices. The profiles are listed just above
the table, each with a comment saying what it covers.

Two things to know before picking a profile:

  * A profile says what a device *may* have, not what it does have. Declaring
    fan modes does not create a fan control -- the integration only wires one
    up if the device actually reports the capability behind it. So a profile
    that offers a little too much is safe; one that offers the wrong kind of
    thing is not.

  * If no profile fits, or the device has something none of them offer, please
    open an issue with the diagnostics dump instead of inventing a profile.
    Guessing changes the entity list for everyone who owns that hardware, and
    the dump is enough for someone to get it right.

===========================================================================
WHAT A PROFILE MAY CONTAIN
===========================================================================

Required :
    * type : the kind of device, from CozytouchDeviceType.
    * HVACModes : the value/mode pairs the device accepts.

Optional, and only worth setting where a device differs from the default :
    * HVACModesCapabilityId : which capability ids carry the mode (default 7, 8)
    * HeatingModes : value/mode pairs for the heating mode selector
    * AirCirculationSpeeds : value/speed pairs for air circulation
    * fanModes : value/mode pairs for the fan
    * swingModes : value/mode pairs for the louvre
    * currentTemperatureAvailable : default True
    * currentTemperatureAvailableZ1 : for HEAT_PUMP, default True
    * currentTemperatureAvailableZ2 : for HEAT_PUMP, default True
    * exhaustTemperatureAvailable : default True
    * quietModeAvailable : default False
    * awayModeTemperatureAvailable : the absence setpoint, default True
    * ecoModeAvailable : default True
"""  # noqa: D205

import copy
from enum import StrEnum

from homeassistant.components.climate import HVACMode
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
)

from .const import (
    AIR_CIRCULATION_SPEED_HIGH,
    AIR_CIRCULATION_SPEED_LOW,
    AIR_CIRCULATION_SPEED_MEDIUM,
    HEATING_MODE_ECO_PLUS,
    HEATING_MODE_MANUAL,
    HEATING_MODE_PROG,
    SWING_MODE_DOWN,
    SWING_MODE_MIDDLE_DOWN,
    SWING_MODE_MIDDLE_UP,
    SWING_MODE_UP,
)


class CozytouchDeviceType(StrEnum):
    """Device types enum."""

    UNKNOWN = "unknown"
    THERMOSTAT = "thermostat"
    GAZ_BOILER = "gaz_boiler"
    HEAT_PUMP = "heat_pump"
    WATER_HEATER = "water_heater"
    TOWEL_RACK = "towel_rack"
    AC = "ac"
    AC_CONTROLLER = "ac_controller"
    HUB = "hub"


# Almost every device carries its mode on capability 7 or 8. Only a profile
# that says otherwise departs from this.
DEFAULT_HVAC_MODES_CAPABILITY_ID = {7, 8}

OFF_AND_HEAT = {0: HVACMode.OFF, 4: HVACMode.HEAT}
OFF_ONLY = {0: HVACMode.OFF}


# ===========================================================================
# PROFILES
# ===========================================================================
# Reuse one of these in the MODELS table. Do not copy a profile to change one
# thing: put the difference on the model's own line instead, the way 1957 does.

# Gas boilers, driven through a Navilink thermostat.
GAS_BOILER = {
    "type": CozytouchDeviceType.GAZ_BOILER,
    "HVACModes": OFF_AND_HEAT,
}

# Domestic hot water: tanks, heat pump water heaters, hybrids. By far the
# largest family, and they all behave the same way.
WATER_HEATER = {
    "type": CozytouchDeviceType.WATER_HEATER,
    "HVACModes": OFF_AND_HEAT,
    "HeatingModes": {
        0: HEATING_MODE_MANUAL,
        3: HEATING_MODE_ECO_PLUS,
        4: HEATING_MODE_PROG,
    },
}

# Electric towel rails.
TOWEL_RACK = {
    "type": CozytouchDeviceType.TOWEL_RACK,
    "HVACModes": OFF_AND_HEAT,
}

# A room thermostat.
THERMOSTAT = {
    "type": CozytouchDeviceType.THERMOSTAT,
    "HVACModes": OFF_AND_HEAT,
}

# Gateways. They hold no climate of their own; they are what the rooms hang
# off, and they are here so they get a name instead of "Unknown product".
GATEWAY = {
    "type": CozytouchDeviceType.HUB,
    "HVACModes": OFF_ONLY,
}

# An air conditioning room unit: heating, cooling, fan, louvre and air
# circulation -- whichever of those the unit turns out to report.
ROOM_AC = {
    "type": CozytouchDeviceType.AC,
    "HVACModes": {
        0: HVACMode.OFF,
        1: HVACMode.AUTO,
        3: HVACMode.COOL,
        4: HVACMode.HEAT,
        7: HVACMode.FAN_ONLY,
        8: HVACMode.DRY,
    },
    "quietModeAvailable": True,
    # The Cozytouch app offers no absence setpoint for these units.
    "awayModeTemperatureAvailable": False,
    "AirCirculationSpeeds": {
        1: AIR_CIRCULATION_SPEED_LOW,
        2: AIR_CIRCULATION_SPEED_MEDIUM,
        3: AIR_CIRCULATION_SPEED_HIGH,
    },
    "fanModes": {
        1: FAN_LOW,
        2: FAN_MEDIUM,
        3: FAN_HIGH,
        5: FAN_AUTO,
    },
    "swingModes": {
        1: SWING_MODE_UP,
        2: SWING_MODE_MIDDLE_UP,
        3: SWING_MODE_MIDDLE_DOWN,
        4: SWING_MODE_DOWN,
    },
}

# The wall panel that comes with a room unit. Reports state, controls nothing.
AC_WALL_PANEL = {
    "type": CozytouchDeviceType.AC_CONTROLLER,
    "HVACModes": OFF_ONLY,
}


# ===========================================================================
# MODELS
# ===========================================================================
# modelId: ("Commercial name", PROFILE)
#
# A model that differs from its profile in one detail carries that detail on
# its own line, so the difference sits next to the device it applies to.

MODELS: dict[int, tuple[str, dict]] = {
    56: ("Naema 2 Micro 25", GAS_BOILER),
    61: ("Naia 2 Micro 25", GAS_BOILER),
    65: ("Naema 2 Duo 25", GAS_BOILER),
    76: (
        "Alfea Extensa Duo AI UE",
        {
            "type": CozytouchDeviceType.HEAT_PUMP,
            "HVACModes": OFF_AND_HEAT,
            "HeatingModes": {0: HEATING_MODE_MANUAL},
            "currentTemperatureAvailableZ1": False,
            "currentTemperatureAvailableZ2": True,
            "exhaustTemperatureAvailable": False,
        },
    ),
    211: (
        "Alfea Extensa Duo A.I. 3 R32",
        {
            "type": CozytouchDeviceType.HEAT_PUMP,
            # This one carries its mode on 1 and 2 rather than 7 and 8.
            "HVACModesCapabilityId": {1, 2},
            "HVACModes": {0: HVACMode.OFF, 1: HVACMode.HEAT, 2: HVACMode.AUTO},
            "HeatingModes": {0: HEATING_MODE_MANUAL},
            "currentTemperatureAvailableZ1": True,
            "currentTemperatureAvailableZ2": True,
            "exhaustTemperatureAvailable": False,
        },
    ),
    235: ("Thermostat Navilink Connect", THERMOSTAT),
    236: ("Sauter Phazy", WATER_HEATER),
    # One ACI HYB hybrid platform sold under three brands, in VS 300L, VM 150L
    # and VM 200L variants. Only the name changes across the nine ids.
    386: ("PHAZY VS 300L 3000M", WATER_HEATER),
    387: ("PHAZY VM 150L 2200M", WATER_HEATER),
    388: ("PHAZY VM 200L 2200M", WATER_HEATER),
    389: ("AQUEO ACI HYB VS 300L 3000M", WATER_HEATER),
    390: ("AQUEO ACI HYB VM 150L 2200M", WATER_HEATER),
    391: ("AQUEO ACI HYB VM 200L 2200M", WATER_HEATER),
    392: ("DURALIS CONNECT ACI HYB VS 300L 3000M", WATER_HEATER),
    393: ("DURALIS CONNECT ACI HYB VM 150L 2200M", WATER_HEATER),
    394: ("DURALIS CONNECT ACI HYB VM 200L 2200M", WATER_HEATER),
    418: (
        "Atlantic Loria Duo 6006",
        THERMOSTAT
        | {
            "exhaustTemperatureAvailable": True,
            "currentTemperatureAvailableZ1": True,
            "currentTemperatureAvailableZ2": False,
            "overrideModeAvailable": True,
        },
    ),
    # Drives the 557-561 room units listed under ZONE_NAMED below.
    556: ("Naviclim Hub", GATEWAY | {"awayModeTemperatureAvailable": False}),
    1353: ("Calypso Split Interface", GATEWAY),
    1369: ("Calypso Split", WATER_HEATER),
    1371: ("Aeromax SPLIT 3", WATER_HEATER),
    1372: ("Aeromax SPLIT 3", WATER_HEATER),
    1376: ("Calypso Split", WATER_HEATER),
    1381: ("KELUD 1750W BLC", TOWEL_RACK),
    1382: ("KELUD 1750W Anthracite Standard", TOWEL_RACK),
    1388: ("Doris étroit 1500W BLC", TOWEL_RACK),
    1444: ("Naema 3 Micro 25", GAS_BOILER),
    1457: ("HUB Cozytouch", GATEWAY),
    1543: ("Asama Connecté II Ventilo 1750W Blanc", TOWEL_RACK),
    1546: ("Asama Connecté II Ventilo 1500W ANTH", TOWEL_RACK),
    1547: ("Asama Connecté II Ventilo 1750W ANTH", TOWEL_RACK),
    1551: ("Asama Connecté II Ventilo 1750W Noir", TOWEL_RACK),
    1595: ("Doris étroit 1300W CARAT", TOWEL_RACK),
    1622: ("Thermor Riva 5", TOWEL_RACK),
    1641: ("Atlantic Explorer V5 (200L)", WATER_HEATER),
    1642: ("Atlantic Explorer V5 (270L)", WATER_HEATER),
    1644: ("Atlantic Explorer V5 (240L)", WATER_HEATER),
    1645: ("Atlantic Explorer V5 (270L with coil)", WATER_HEATER),
    1656: ("Aeromax 6", WATER_HEATER),
    1657: ("Calypso 200L", WATER_HEATER),
    1658: ("Calypso connecté", WATER_HEATER),
    1758: ("HUB Navizone", GATEWAY | {"awayModeTemperatureAvailable": False}),
    1763: ("FLAT/S4 IOTHUB", GATEWAY),
    # The app offers no scheduling for this one.
    1957: (
        "LINEO CONNECTE MP 100L 2250W",
        WATER_HEATER
        | {"HeatingModes": {0: HEATING_MODE_MANUAL, 3: HEATING_MODE_ECO_PLUS}},
    ),
    1962: ("Thermor Malicio 3 65L", WATER_HEATER),
    1966: ("Thermor Malicio 3 120L", WATER_HEATER),
    2346: ("Egeo VS 250L", WATER_HEATER),
    2374: ("Explorer EVO 3 (260L)", WATER_HEATER),
}


# ===========================================================================
# DEVICES NAMED AFTER THEIR ROOM
# ===========================================================================
# A gateway reports one device per room, each under its own modelId, counting
# up from the first. Their name is the room, so it cannot be written down here
# -- the label below is what the room name gets appended to.
#
# (first id, last id): ("Label ", PROFILE)

ZONE_NAMED: dict[tuple[int, int], tuple[str, dict]] = {
    # Behind a Naviclim (556) or Navizone (1758) gateway. The app offers no eco
    # mode for these anywhere, and capability 100507 has read 0 since
    # provisioning on the one setup there is a capture of.
    (557, 561): ("Air Conditioner ", ROOM_AC | {"ecoModeAvailable": False}),
    (562, 570): ("Air Conditioner User Interface ", AC_WALL_PANEL),
    # A separate product. No report either way on its eco mode, so it keeps the
    # default rather than inheriting a decision made about 557-561.
    (1734, 1734): ("Air Conditioner ", ROOM_AC),
}


def _named_after_zone(modelId: int, zoneName: str | None):
    """Resolve a room-named device, or None when this id is not one."""
    for (first, last), (label, profile) in ZONE_NAMED.items():
        if first <= modelId <= last:
            if zoneName is not None:
                return label + "(" + zoneName + ")", profile
            # With no room name, fall back to counting from the first id.
            return label + "(#" + str(modelId - first + 1) + ")", profile
    return None


def get_model_infos(modelId: int, zoneName: str | None = None) -> dict:
    """Return what is known about a modelId.

    An id nothing knows about comes back as UNKNOWN, which is what makes it
    read as "Unknown product (1234)" in Home Assistant and in a diagnostics
    dump. That is the signal for someone to add it to MODELS above.
    """
    found = MODELS.get(modelId) or _named_after_zone(modelId, zoneName)

    if found is None:
        found = (
            "Unknown product (" + str(modelId) + ")",
            {
                "type": CozytouchDeviceType.UNKNOWN,
                # Heating is the safe guess: it is what almost every Cozytouch
                # product does, and it keeps a bare climate entity working.
                "HVACModes": OFF_AND_HEAT,
            },
        )

    name, profile = found

    # Copied, so nothing downstream can write into a shared profile and change
    # what every other device of that family reports.
    return {
        "modelId": modelId,
        "HVACModesCapabilityId": DEFAULT_HVAC_MODES_CAPABILITY_ID,
        **copy.deepcopy(profile),
        "name": name,
    }
