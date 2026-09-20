"""Atlantic Cozytouch device model mapping.

Mandatory :
    * modelId : modelId of the device
    * name : commercial name of the device.
    * type : device type from CozytouchDeviceType enum.
    * HVACModes : list of available HVAC value/mode pairs

Optional :
    * currentTemperatureAvailable : enable current temperature availability
      (default : True)
    * currentTemperatureAvailableZ1 : enable current temperature availability
      for Z1 (used for HEAT_PUMP, default : True)
    * currentTemperatureAvailableZ2 : enable current temperature availability
      for Z2 (used for HEAT_PUMP, default : True)
    * exhaustTemperatureAvailable : enable exhaust temperature availability
      (default : True)
    * fanModes : list of value/mode pairs
    * swingModes : list of value/mode pairs
    * quietModeAvailable : enable quiet mode availability (default : False)
    * awayModeTemperatureAvailable : enable the absence setpoint (default : True)
    * ecoModeAvailable : enable eco mode availability (default : True)

"""

from enum import StrEnum

from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACMode,
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
from .infos import ModelInfos
from .model_catalogue import MODEL_CATALOGUE


class CozytouchDeviceType(StrEnum):
    """Device types enum."""

    UNKNOWN = "unknown"
    THERMOSTAT = "thermostat"
    GAZ_BOILER = "gaz_boiler"
    HEAT_PUMP = "heat_pump"
    WATER_HEATER = "water_heater"
    TOWEL_RACK = "towel_rack"
    RADIATOR = "radiator"
    AC = "ac"
    AC_CONTROLLER = "ac_controller"
    HUB = "hub"
    ZONE = "zone"


# What the API calls a zone of a ducted heat pump. The name is the signal
# rather than the model id, and it is the API's `name` and not `customName`
# -- see docs/decisions.md.
ZONE_NAME_PREFIX = "THZONE"

# The mode tables the branches below share. A branch that declares a literal
# instead is one whose hardware differs. Shared objects, never mutated.
OFF_HEAT = {
    0: HVACMode.OFF,
    4: HVACMode.HEAT,
}

# The hubs and the Naviclim box, which report a mode and cannot heat.
OFF_ONLY = {
    0: HVACMode.OFF,
}

MANUAL_ECO_PROG = {
    0: HEATING_MODE_MANUAL,
    3: HEATING_MODE_ECO_PLUS,
    4: HEATING_MODE_PROG,
}

MANUAL_ONLY = {
    0: HEATING_MODE_MANUAL,
}

# Each table below holds every id of one product line the catalogue names.
# `# catalogue only` means no capture of that id exists, and a table whose
# whole body is catalogue-sourced says so in its own comment rather than
# repeating the marker. See docs/decisions.md.

# 1368 and 754 are two listings of the 200L; 1367 is the 150L of the same line.
CALYPSO_SPLIT_VM = {
    754: "Calypso SPLIT VM 200L",  # catalogue only
    1367: "Calypso SPLIT VM 150L",  # catalogue only
    1368: "Calypso SPLIT VM 200L",
}

# Two listings of one platform: EGEO VS <volume>L, and the internal code
# TD <volume> VS <brand> 1800M TYB CA. 1010/2346 and 957/2345 are the same two
# products under both.
EGEO_PLATFORM = {
    957: "Egeo VS 200L",  # catalogue only
    1010: "Egeo VS 250L",  # catalogue only
    2345: "Egeo VS 200L",  # catalogue only
    2346: "Egeo VS 250L",
    2347: "TD 200 VS TH 1800M TYB CA",  # catalogue only
    2348: "TD 250 VS TH 1800M TYB CA",  # catalogue only
    2349: "TD 200 VS SA 1800M TYB CA",  # catalogue only
    2350: "TD 250 VS SA 1800M TYB CA",  # catalogue only
    2351: "TD 250 VS ATE 1800M TYB CA SERP",  # catalogue only
    2352: "TD 250 VS THE 1800M TYB CA SERP",  # catalogue only
}

AEROMAX_PREMIUM_CV5 = {
    1669: "CV5 Aeromax Premium 100L",
    1670: "CV5 Aeromax Premium 150L",  # catalogue only
}

# 1957 came from a capture and declares no prog mode, which is why the others
# do not either: they are the same appliance in another volume.
LINEO_CONNECTE_MP = {
    1954: "LINEO CONNECTE MP 040L 2250W",  # catalogue only
    1955: "LINEO CONNECTE MP 065L 2250W",  # catalogue only
    1956: "LINEO CONNECTE MP 080L 2250W",  # catalogue only
    1957: "LINEO CONNECTE MP 100L 2250W",
}

# MP and VM are two form factors of one range. The names drop that letter, as
# the two captured ids already did -- except at 100L, where both exist and the
# letter is the only thing telling them apart.
MALICIO_3 = {
    1961: "Thermor Malicio 3 40L",  # catalogue only
    1962: "Thermor Malicio 3 65L",
    1963: "Thermor Malicio 3 80L",  # catalogue only
    1964: "Thermor Malicio 3 MP 100L",  # catalogue only
    1965: "Thermor Malicio 3 VM 100L",  # catalogue only
    1966: "Thermor Malicio 3 120L",
    1967: "Thermor Malicio 3 150L",  # catalogue only
}

NAEMA_3 = {
    1444: "Naema 3 Micro 25",
    1445: "Naema 3 Micro 30",  # catalogue only
    1446: "Naema 3 Micro 35",  # catalogue only
    1447: "Naema 3 Duo 25",
    1448: "Naema 3 Duo 35",  # catalogue only
}

# 219 is 211 under the Thermor badge, and the catalogue says so in the name.
ALFEA_EXTENSA_DUO_AI_3 = {
    211: "Alfea Extensa Duo A.I. 3 R32",
    219: "Alfea Extensa Duo A.I. 3 R32 Thermor",  # catalogue only
}

# The heating circuit slots the catalogue calls TESC_0 to TESC_2, one
# productId each, and the GENERATOR_0 slot that sits beside them.
# See docs/decisions.md.
TESC_SLOTS = range(1388, 1391)
GENERATOR_SLOT = 1391

# The Alfea Extensa S, which reports itself as two devices : the connected
# interface and the generator under it. The catalogue's own productId is what
# separates them, and the ids of each half are contiguous.
# See docs/decisions.md.
ALFEA_EXTENSA_S_INTERFACES = range(2295, 2318)
ALFEA_EXTENSA_S_GENERATORS = range(2326, 2329)

# The Alfea Excellia S, the same shape with its generator reported as a slot
# rather than as a catalogue id. See docs/decisions.md.
ALFEA_EXCELLIA_S_INTERFACES = range(1691, 1693)

# Every interface a room slot can hang off, which is what makes that slot a
# heating circuit rather than an air conditioner.
ALFEA_S_INTERFACES = frozenset(
    (*ALFEA_EXTENSA_S_INTERFACES, *ALFEA_EXCELLIA_S_INTERFACES)
)

# One water heater platform, coded TD <volume> VS <brand> <power>M TYB V5S,
# with SERP for the tank that carries a coil; the grid is volume x coil x
# brand, over eight badges. Only Atlantic's ATE has a commercial name we know.
# See docs/decisions.md.
EXPLORER_V5 = {
    1641: "Atlantic Explorer V5 (200L)",
    1642: "Atlantic Explorer V5 (270L)",
    1643: "Atlantic Explorer V5 (200L with coil)",  # catalogue only
    1644: "Atlantic Explorer V5 (240L)",
    1645: "Atlantic Explorer V5 (270L with coil)",
    1646: "TD 200 VS THE 1200M TYB V5S",  # catalogue only
    1647: "TD 270 VS THE 1200M TYB V5S",  # catalogue only
    1648: "TD 200 VS THE 1200M TYB V5S SERP",  # catalogue only
    1649: "TD 270 VS THE 1200M TYB V5S SERP",  # catalogue only
    1650: "TD 200 VS AE 1200M TYB V5S",  # catalogue only
    1651: "TD 270 VS AE 1200M TYB V5S",  # catalogue only
    1652: "TD 200 VS AE 1200M TYB V5S SERP",  # catalogue only
    1653: "TD 240 VS AE 1200M TYB V5S SERP",  # catalogue only
    1654: "TD 270 VS AE 1200M TYB V5S SERP",  # catalogue only
    1655: "TD 200 VS TH 1200M TYB V5S",  # catalogue only
    1659: "TD 270 VS SA 1200M TYB V5S",  # catalogue only
    1660: "TD 200 VS ATS 1200M TYB V5S SERP",  # catalogue only
    1661: "TD 240 VS ATS 1200M TYB V5S SERP",  # catalogue only
    1662: "TD 270 VS ATS 1200M TYB V5S SERP",  # catalogue only
    1663: "TD 200 VS NEU 1200M TYB V5S SERP",  # catalogue only
    1664: "TD 270 VS NEU 1200M TYB V5S SERP",  # catalogue only
}

# One ACI HYB hybrid water heater platform under four brands, in VS 300L, VM
# 150L and VM 200L. Only the commercial name changes, and on this platform the
# brand *is* the name, so the catalogue's string is kept verbatim.
ACI_HYB_WATER_HEATERS = {
    386: "PHAZY VS 300L 3000M",
    387: "PHAZY VM 150L 2200M",
    388: "PHAZY VM 200L 2200M",
    389: "AQUEO ACI HYB VS 300L 3000M",
    390: "AQUEO ACI HYB VM 150L 2200M",
    391: "AQUEO ACI HYB VM 200L 2200M",
    392: "DURALIS CONNECT ACI HYB VS 300L 3000M",
    393: "DURALIS CONNECT ACI HYB VM 150L 2200M",
    394: "DURALIS CONNECT ACI HYB VM 200L 2200M",
    1364: "THE DURALIS CONNECT VM 150 2200M PE",  # catalogue only
    1365: "THE DURALIS CONNECT VM 200 2200M PE",  # catalogue only
    1366: "THE DURALIS CONNECT VS 300 3000M PE",  # catalogue only
}

# The connectivity box, under each of the four brands it is sold as. A set
# rather than four branches because a room slot reads its master's id to tell
# a radiator from an air conditioner. See docs/decisions.md.
# 2448, 2449 and 2450 are catalogue only -- 2447 is the badge that was
# captured.
COZYBOX_HUBS = {2447, 2448, 2449, 2450}

# The three connected towel rack ranges, which are one product in several
# wattages and finishes. Names are the house spelling of the catalogue's
# string ; the eight mapped before keep the name they had, inconsistencies
# included, because renaming one renames somebody's device.
TOWEL_RACK_VARIANTS = {
    1540: "Asama Connecté II 500W BLC",  # catalogue only
    1541: "Asama Connecté II 750W BLC",  # catalogue only
    1542: "Asama Connecté II 1500W BLC",  # catalogue only
    1543: "Asama Connecté II 1750W Blanc",
    1544: "Asama Connecté II 500W ANTH",  # catalogue only
    1545: "Asama Connecté II 750W ANTH",  # catalogue only
    1546: "Asama Connecté II 1500W ANTH",
    1547: "Asama Connecté II 1750W ANTH",
    1548: "Asama Connecté II 500W NOIR",  # catalogue only
    1549: "Asama Connecté II 750W NOIR",  # catalogue only
    1550: "Asama Connecté II 1500W NOIR",  # catalogue only
    1551: "Asama Connecté II 1750W Noir",
    1552: "Asama Connecté II 500W CAPP",  # catalogue only
    1553: "Asama Connecté II 750W CAPP",  # catalogue only
    1554: "Asama Connecté II 1500W CAPP",  # catalogue only
    1555: "Asama Connecté II 1750W CAPP",  # catalogue only
    1562: "Doris étroit 300W BLC",  # catalogue only
    1563: "Doris étroit 500W BLC",  # catalogue only
    1564: "Riva 5 étroit 300W BLC",  # catalogue only
    1565: "Riva 5 étroit 500W BLC",  # catalogue only
    1587: "Doris étroit 1300W BLC",  # catalogue only
    1588: "Doris étroit 1500W BLC",
    1589: "Doris étroit 300W ANTH",  # catalogue only
    1590: "Doris étroit 500W ANTH",  # catalogue only
    1591: "Doris étroit 1300W ANTH",  # catalogue only
    1592: "Doris étroit 1500W ANTH",  # catalogue only
    1593: "Doris étroit 300W CARAT",  # catalogue only
    1594: "Doris étroit 500W CARAT",  # catalogue only
    1595: "Doris étroit 1300W CARAT",
    1596: "Doris étroit 1500W CARAT",  # catalogue only
    1597: "Doris étroit 300W NOIR",  # catalogue only
    1598: "Doris étroit 500W NOIR",  # catalogue only
    1599: "Doris étroit 1300W NOIR",  # catalogue only
    1600: "Doris étroit 1500W NOIR",  # catalogue only
    1622: "Riva 5 étroit 1300W BLC",
    1623: "Riva 5 étroit 1500W BLC",  # catalogue only
    1624: "Riva 5 étroit 300W ARDOISE",  # catalogue only
    1625: "Riva 5 étroit 300W MENHIR",  # catalogue only
    1626: "Riva 5 étroit 500W MENHIR",  # catalogue only
    1627: "Riva 5 étroit 1300W MENHIR",  # catalogue only
    1628: "Riva 5 étroit 1500W MENHIR",  # catalogue only
    1629: "Riva 5 étroit 500W ARDOISE",  # catalogue only
    1630: "Riva 5 étroit 1300W ARDOISE",  # catalogue only
    1631: "Riva 5 étroit 1500W ARDOISE",  # catalogue only
    1632: "Riva 5 étroit 300W CARBONE",  # catalogue only
    1633: "Riva 5 étroit 500W CARBONE",  # catalogue only
    1634: "Riva 5 étroit 1300W CARBONE",  # catalogue only
    1635: "Riva 5 étroit 1500W CARBONE",  # catalogue only
}

# Catalogue only, the whole table. A commercial name is not unique here -- 257
# and 260 are both "Naema Micro 25" -- and the duplicates are distinct ids in
# the vendor's catalogue. See docs/decisions.md.
NAEMA_NAIA_BOILERS = {
    1: "Naema Micro 30",
    2: "Naema 12",
    3: "Naema 20",
    4: "Naema Micro 25",
    5: "Naema Micro 35",
    6: "Naema Duo 30",
    7: "Naema Duo 35",
    8: "Naia 12",
    9: "Naia Micro 25",
    10: "Naia Micro 30",
    11: "Naia Micro 35",
    12: "Naia Duo 30",
    54: "Naema 2 12",
    55: "Naema 2 20",
    227: "Naema 2 30",
    57: "Naema 2 Micro 30",
    58: "Naema 2 Micro 35",
    59: "Naia 2 12",
    60: "Naia 2 20",
    62: "Naia 2 Micro 30",
    63: "Naia 2 Micro 35",
    64: "Naema 2 Duo 35",
    66: "Naia 2 Duo 35",
    67: "Naia 2 Duo 25",
    68: "Naema 2 Duo 30 HE",
    69: "Naia 2 Duo 30 HE",
    253: "Naema 20 Sr",
    254: "Naema 20 SP",
    256: "Naema Micro 25 Cuerpo Caldera",
    257: "Naema Micro 25",
    258: "Naema Micro 30",
    259: "Naema Micro 35",
    260: "Naema Micro 25",
    261: "Naema Micro 30",
    265: "Naema Micro 30 SP",
    266: "Naema Micro 35 SP",
    267: "Naema Duo 30",
    269: "Naia Duo 35",
    270: "Naema Duo 35 SP",
}


# What Atlantic's own app classifies on. `ProductType.java` in the decompiled
# client holds these ranges ; the setup view sends the `productId` they index,
# and `account.py` already stores it per device. See docs/decisions.md.
PRODUCT_TYPES: dict[str, frozenset[int]] = {
    "ROOM": frozenset((*range(26, 31), *range(97, 112))),
    "AIR_CONDITIONER_UI": frozenset(range(31, 41)),
    "TH_ZONE": frozenset(range(65, 95)),
    "CESA_V2_MAIN_COMPONENT": frozenset({54}),
    "CESA_V2_GENERATOR": frozenset(range(58, 62)),
    "DHW": frozenset({47, 62}),
    "AIR_CONDITIONER": frozenset({25}),
    "NAVI_HUB": frozenset({63}),
    "ZONI_CLIM_HUB": frozenset({96}),
    "SPLIT_3S_HUB": frozenset({95}),
    "S_HUB": frozenset({98}),
    "DISCOVER_MASTER": frozenset({6, 44, 112, 113}),
    "HDG2": frozenset({7}),
    "DARWIN_BOILER": frozenset({4}),
    "TD1": frozenset({53}),
    "BD0": frozenset({41}),
    "HE3Z": frozenset({64}),
    "PASS_APC_BOILER": frozenset({1}),
    "PASS_APC_HEAT_PUMP": frozenset({2}),
    "PASS_APC_HYBRID": frozenset({3}),
    "UNDERFLOOR_HEATER": frozenset({121}),
    "CONSOLE": frozenset({122}),
    "WALL_AIR_CONDITIONER": frozenset({123}),
    "REMOTE_CONTROL": frozenset({124}),
}

# The modes a room air conditioner offers, shared by the mapped branch and the
# derivation below.
AC_HVAC_MODES = {
    0: HVACMode.OFF,
    1: HVACMode.AUTO,
    3: HVACMode.COOL,
    4: HVACMode.HEAT,
    7: HVACMode.FAN_ONLY,
    8: HVACMode.DRY,
}

# The room control of a heating circuit : the app's OFF / ON / AUTO.
CIRCUIT_HVAC_MODES = {
    0: HVACMode.OFF,
    1: HVACMode.AUTO,
    4: HVACMode.HEAT,
}

# What each ProductType is, and the modes that go with it. Five tables cover
# every mapped model, which is why this is a lookup and not a branch.
DERIVED_TYPES: dict[str, tuple[CozytouchDeviceType, dict]] = {
    "AIR_CONDITIONER_UI": (CozytouchDeviceType.AC_CONTROLLER, OFF_ONLY),
    "TH_ZONE": (CozytouchDeviceType.ZONE, {}),
    "CESA_V2_MAIN_COMPONENT": (CozytouchDeviceType.HEAT_PUMP, {}),
    "CESA_V2_GENERATOR": (CozytouchDeviceType.HEAT_PUMP, {}),
    "DHW": (CozytouchDeviceType.WATER_HEATER, OFF_HEAT),
    "AIR_CONDITIONER": (CozytouchDeviceType.AC, AC_HVAC_MODES),
    "NAVI_HUB": (CozytouchDeviceType.HUB, OFF_ONLY),
    "ZONI_CLIM_HUB": (CozytouchDeviceType.HUB, OFF_ONLY),
    "SPLIT_3S_HUB": (CozytouchDeviceType.HUB, OFF_ONLY),
    "S_HUB": (CozytouchDeviceType.HUB, OFF_ONLY),
    "DISCOVER_MASTER": (CozytouchDeviceType.HUB, OFF_ONLY),
    "HDG2": (CozytouchDeviceType.WATER_HEATER, OFF_HEAT),
    "DARWIN_BOILER": (CozytouchDeviceType.THERMOSTAT, OFF_HEAT),
    "TD1": (CozytouchDeviceType.TOWEL_RACK, OFF_HEAT),
    "BD0": (CozytouchDeviceType.RADIATOR, OFF_HEAT),
    "HE3Z": (CozytouchDeviceType.THERMOSTAT, OFF_HEAT),
    "PASS_APC_BOILER": (CozytouchDeviceType.GAZ_BOILER, OFF_HEAT),
    "PASS_APC_HEAT_PUMP": (CozytouchDeviceType.HEAT_PUMP, OFF_HEAT),
    "PASS_APC_HYBRID": (CozytouchDeviceType.HEAT_PUMP, OFF_HEAT),
    "UNDERFLOOR_HEATER": (CozytouchDeviceType.RADIATOR, OFF_HEAT),
    "CONSOLE": (CozytouchDeviceType.AC, AC_HVAC_MODES),
    "WALL_AIR_CONDITIONER": (CozytouchDeviceType.AC, AC_HVAC_MODES),
}

# The interfaces a room hangs off, and what a room behind each one is: its
# type, its modes, and the word it is named by. The id alone is a room index ;
# the parent says what is in the room.
ROOM_BEHIND: dict[str | None, tuple[CozytouchDeviceType, dict, str]] = {
    "CESA_V2_MAIN_COMPONENT": (
        CozytouchDeviceType.THERMOSTAT,
        CIRCUIT_HVAC_MODES,
        "Heating circuit",
    ),
    "AIR_CONDITIONER": (CozytouchDeviceType.AC, AC_HVAC_MODES, "Air Conditioner"),
    "NAVI_HUB": (CozytouchDeviceType.AC, AC_HVAC_MODES, "Air Conditioner"),
    "ZONI_CLIM_HUB": (CozytouchDeviceType.AC, AC_HVAC_MODES, "Air Conditioner"),
    "SPLIT_3S_HUB": (CozytouchDeviceType.AC, AC_HVAC_MODES, "Air Conditioner"),
}

# The other half of the vendor's classification : `productId` says which part
# of an appliance a device is, `modelFamily` says what it heats or cools. Both
# are enums of Atlantic's own -- this is `ModelFamily.java`, every member of
# it. It is read only after `productId`, which is what keeps a gateway from
# being typed by the installation it fronts : the Navizone sends
# `Air_Conditioning` and is a hub. See docs/decisions.md.
#
# `Heat_Interface_Unit` and `Double_Flow_Ventilation` are the two members left
# out : nothing here is either, and guessing a type for hardware nobody has
# reported is how a device ends up with entities it cannot drive.
MODEL_FAMILIES: dict[str | None, CozytouchDeviceType] = {
    "Air_Conditioning": CozytouchDeviceType.AC,
    "Boiler": CozytouchDeviceType.GAZ_BOILER,
    "Connectivity_Box": CozytouchDeviceType.HUB,
    "Heat_Pump": CozytouchDeviceType.HEAT_PUMP,
    "Hybrid_Heat_Pump": CozytouchDeviceType.HEAT_PUMP,
    "Radiator": CozytouchDeviceType.RADIATOR,
    "Thermodynamic_Water_Heater": CozytouchDeviceType.WATER_HEATER,
    "Thermostat": CozytouchDeviceType.THERMOSTAT,
    "Towel_Dryer": CozytouchDeviceType.TOWEL_RACK,
    "Underfloor_Heater": CozytouchDeviceType.RADIATOR,
    "Water_Heater": CozytouchDeviceType.WATER_HEATER,
}


# The flags a derived device needs beyond its type. A gateway fronting an air
# conditioning installation reports the away mode itself -- capability 152 sits
# on it and on nothing else -- but has no absence *setpoint*, which is what the
# mapped gateway branches say too. Left off means `capability.py` takes the
# flag as held, so a gateway missing from here grows a setpoint it cannot
# drive. See docs/decisions.md.
# A room inherits these from its gateway, so the eco suppression the mapped
# rooms carry reaches a derived one too. On the gateway itself it says the same
# thing and costs nothing : a box reports neither capability.
_AC_GATEWAY = {"awayModeTemperatureAvailable": False, "ecoModeAvailable": False}
DERIVED_FLAGS: dict[str | None, dict[str, bool]] = {
    "NAVI_HUB": _AC_GATEWAY,
    "ZONI_CLIM_HUB": _AC_GATEWAY,
    "SPLIT_3S_HUB": _AC_GATEWAY,
    "S_HUB": _AC_GATEWAY,
    "AIR_CONDITIONER": _AC_GATEWAY,
}


def product_type(productId: int | None) -> str | None:
    """The vendor's name for what a productId is, or None for one it skips."""
    if productId is None:
        return None
    return next(
        (name for name, ids in PRODUCT_TYPES.items() if productId in ids), None
    )


def room_index(productId: int) -> int:
    """The number Atlantic gives a room : `ROOM_0` to `ROOM_19`.

    Two blocks, 26-30 and 97-111, which the vendor numbers as one run.
    """
    return productId - 26 if productId <= 30 else productId - 92


def derive(
    modelInfos: ModelInfos,
    productId: int | None,
    modelFamily: str | None,
    masterProductId: int | None,
    zoneName: str | None,
    fallbackName: str | None,
) -> None:
    """Fill in what a device says about itself, for an id no branch names.

    The table stays the override layer : this only answers where it said
    nothing. See docs/decisions.md.
    """
    kind = product_type(productId)
    label = None
    if kind == "ROOM" and productId is not None:
        parent = product_type(masterProductId)
        deviceType, modes, label = ROOM_BEHIND.get(
            parent, (CozytouchDeviceType.UNKNOWN, OFF_HEAT, "")
        )
        flags = DERIVED_FLAGS.get(parent, {})
        if label:
            label += f" (#{room_index(productId)})"
        else:
            label = None
    elif kind in DERIVED_TYPES:
        deviceType, modes = DERIVED_TYPES[kind]
        flags = DERIVED_FLAGS.get(kind, {})
    else:
        deviceType = MODEL_FAMILIES.get(modelFamily, CozytouchDeviceType.UNKNOWN)
        modes, flags = OFF_HEAT, {}

    modelInfos.type = deviceType
    modelInfos.HVACModes = modes
    for flag, held in flags.items():
        setattr(modelInfos, flag, held)

    if label is not None:
        # Named after its room the way the mapped ones are, with the vendor's
        # own index where the account names no zone.
        modelInfos.name = f"{label.split(' (#')[0]} ({zoneName})" if zoneName else label
    else:
        # The catalogue names the product ; where it does not, the device does.
        # Nobody should read "Unknown product" for hardware the API describes.
        modelInfos.name = (
            MODEL_CATALOGUE.get(modelInfos.modelId)
            or fallbackName
            or "Unknown product (" + str(modelInfos.modelId) + ")"
        )


def get_device_model_infos(
    devices: list[dict], dev: dict, zoneName: str | None = None
) -> ModelInfos:
    """The table's answer for one device, given every device on its account.

    The entry point every caller uses, because two of the table's inputs are
    properties of the account rather than of the device : the name a zone is
    recognised by, and the model id of the hub the device hangs off -- which is
    what says whether a room slot is a radiator or an air conditioner. A caller
    that passed the model id alone got the wrong one of those, silently.
    """
    masterDeviceId = dev.get("masterDeviceId")
    master = next(
        (found for found in devices if found["deviceId"] == masterDeviceId), None
    )

    return get_model_infos(
        dev["modelId"],
        zoneName,
        dev.get("name"),
        master["modelId"] if master else None,
        productId=dev.get("productId"),
        modelFamily=dev.get("modelFamily"),
        masterProductId=master.get("productId") if master else None,
        # What the API calls the device, for hardware the catalogue does not
        # name. "---" is what it sends for a zone rather than leaving the
        # field out, so it is read as nothing. See docs/decisions.md.
        fallbackName=next(
            (
                found
                for found in (dev.get("longName"), dev.get("customName"))
                if found and found != "---"
            ),
            None,
        ),
    )


def get_model_infos(  # noqa: C901
    modelId: int,
    zoneName: str | None = None,
    deviceName: str | None = None,
    masterModelId: int | None = None,
    *,
    productId: int | None = None,
    modelFamily: str | None = None,
    masterProductId: int | None = None,
    fallbackName: str | None = None,
) -> ModelInfos:
    """Return infos from model ID.

    `deviceName` and `masterModelId` are the two inputs that are not the id : a
    zone is recognised by its name, and a room slot by the hub it hangs off.

    The three keyword inputs are what the device itself declares, and they are
    read only by the fall-through : a model id the table names is answered by
    the table, unchanged. `get_device_model_infos` fills them in ; a caller
    that has a model id and nothing else leaves them out and gets what it
    always got. See docs/decisions.md.
    """
    modelInfos = ModelInfos(modelId=modelId, HVACModesCapabilityId={7, 8})

    if deviceName is not None and deviceName.startswith(ZONE_NAME_PREFIX):
        # A zone of a ducted heat pump, not a product. See docs/decisions.md.
        modelInfos.name = f"Zone ({zoneName})" if zoneName else deviceName
        modelInfos.type = CozytouchDeviceType.ZONE
        # Empty on purpose : off/heat made a zone read as a thermostat.
        modelInfos.HVACModes = {}

    elif modelId in NAEMA_NAIA_BOILERS:
        # The first-generation Naema and Naia, plus the two Naema 2 beside the
        # 56 below. Name and type only. See docs/decisions.md.
        modelInfos.name = NAEMA_NAIA_BOILERS[modelId]
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = OFF_HEAT

    elif modelId == 56:
        modelInfos.name = "Naema 2 Micro 25"
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = OFF_HEAT

    elif modelId == 61:
        modelInfos.name = "Naia 2 Micro 25"
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = OFF_HEAT

    elif modelId == 65:
        modelInfos.name = "Naema 2 Duo 25"
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = OFF_HEAT

    elif modelId == 76:
        modelInfos.name = "Alfea Extensa Duo AI UE"
        modelInfos.type = CozytouchDeviceType.HEAT_PUMP
        modelInfos.currentTemperatureAvailableZ1 = False
        modelInfos.currentTemperatureAvailableZ2 = True
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ONLY

        modelInfos.exhaustTemperatureAvailable = False

    elif modelId in (211, 219):
        modelInfos.name = ALFEA_EXTENSA_DUO_AI_3[modelId]
        modelInfos.type = CozytouchDeviceType.HEAT_PUMP
        modelInfos.currentTemperatureAvailableZ1 = True
        modelInfos.currentTemperatureAvailableZ2 = True

        modelInfos.HVACModesCapabilityId = {1, 2}

        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            1: HVACMode.HEAT,
            2: HVACMode.AUTO,
        }

        modelInfos.HeatingModes = MANUAL_ONLY

        modelInfos.exhaustTemperatureAvailable = False

    elif modelId in ALFEA_S_INTERFACES:
        # The connected interface of the appliance, not a circuit : it reports
        # the whole-appliance readings and no setpoint, the control living on
        # the room and hot water slots under it. Capability 8 is on it and is
        # not a mode here -- see docs/decisions.md.
        modelInfos.name = MODEL_CATALOGUE[modelId]
        modelInfos.type = CozytouchDeviceType.HEAT_PUMP
        modelInfos.HVACModesCapabilityId = set()
        modelInfos.HVACModes = {}

    elif modelId == GENERATOR_SLOT:
        # The same generator, reported as a slot beside the circuits rather
        # than as a product of its own. See docs/decisions.md.
        modelInfos.name = "Generator"
        modelInfos.type = CozytouchDeviceType.HEAT_PUMP
        modelInfos.HVACModesCapabilityId = set()
        modelInfos.HVACModes = {}

    elif modelId in ALFEA_EXTENSA_S_GENERATORS:
        # The generator under that interface: hydraulic readings only, with no
        # mode capability of any kind. See docs/decisions.md.
        modelInfos.name = MODEL_CATALOGUE[modelId]
        modelInfos.type = CozytouchDeviceType.HEAT_PUMP
        modelInfos.HVACModesCapabilityId = set()
        modelInfos.HVACModes = {}

    elif modelId == 235:
        modelInfos.name = "Thermostat Navilink Connect"
        modelInfos.type = CozytouchDeviceType.THERMOSTAT
        modelInfos.HVACModes = OFF_HEAT

    elif modelId == 236:
        modelInfos.name = "Sauter Phazy"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT
        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId in ACI_HYB_WATER_HEATERS:
        modelInfos.name = ACI_HYB_WATER_HEATERS[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT
        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId == 418:
        modelInfos.name = "Loria 3 Duo R32"
        modelInfos.type = CozytouchDeviceType.THERMOSTAT
        modelInfos.exhaustTemperatureAvailable = True
        modelInfos.currentTemperatureAvailableZ1 = True
        modelInfos.currentTemperatureAvailableZ2 = False
        modelInfos.overrideModeAvailable = True

        modelInfos.HVACModes = OFF_HEAT

    elif modelId == 556:
        modelInfos.name = "Naviclim Hub"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.awayModeTemperatureAvailable = False
        modelInfos.HVACModes = OFF_ONLY

    elif modelId == 1457:
        modelInfos.name = "HUB Cozytouch"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.HVACModes = OFF_ONLY

    elif modelId in (1681, 1758):
        # AC gateway, drives the same 557-561 units as the 556 Naviclim hub
        modelInfos.name = "HUB Navizone"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.awayModeTemperatureAvailable = False
        modelInfos.HVACModes = OFF_ONLY

    elif modelId in COZYBOX_HUBS:
        # Connectivity box, seen driving 557-560 room units like the hubs above
        modelInfos.name = "CozyBox"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.awayModeTemperatureAvailable = False
        modelInfos.HVACModes = OFF_ONLY

    elif masterModelId in COZYBOX_HUBS and 557 <= modelId <= 561:
        # A room slot behind a hub, not a product: 557-561 is the room's
        # index and says nothing about the hardware, so the master's id is
        # what tells a radiator from an air conditioner.
        # See docs/decisions.md.
        modelInfos.name = (
            "Radiator (" + zoneName + ")"
            if zoneName is not None
            else "Radiator (#" + str(modelId - 556) + ")"
        )
        modelInfos.type = CozytouchDeviceType.RADIATOR
        modelInfos.HVACModes = OFF_HEAT

    elif masterModelId in ALFEA_S_INTERFACES and 557 <= modelId <= 561:
        # The same room index behind a heat pump rather than an AC hub, so it
        # is the room control of a heating circuit. Its modes are the app's
        # OFF / ON / AUTO -- frost protection, heating, and heating driven by
        # the outside temperature. See docs/decisions.md.
        modelInfos.name = (
            "Heating circuit (" + zoneName + ")"
            if zoneName is not None
            else "Heating circuit (#" + str(modelId - 556) + ")"
        )
        modelInfos.type = CozytouchDeviceType.THERMOSTAT
        modelInfos.HVACModes = CIRCUIT_HVAC_MODES

    elif 557 <= modelId <= 561 or 1734 <= modelId <= 1737:
        name = "Air Conditioner "
        if zoneName is not None:
            modelInfos.name = name + "(" + zoneName + ")"
        elif modelId <= 561:
            modelInfos.name = name + "(#" + str(modelId - 556) + ")"
        else:
            modelInfos.name = name + "(#" + str(modelId - 1733) + ")"

        modelInfos.type = CozytouchDeviceType.AC
        modelInfos.quietModeAvailable = True
        modelInfos.awayModeTemperatureAvailable = False

        # Every room reports 100507 and the app offers an eco mode for none
        # of them, both ranges checked in the one household that has both.
        # See docs/decisions.md.
        modelInfos.ecoModeAvailable = False

        # Air circulation speed, all three values seen on the wire against the
        # app's "Lente", "Moyenne" and "Rapide".
        modelInfos.AirCirculationSpeeds = {
            1: AIR_CIRCULATION_SPEED_LOW,
            2: AIR_CIRCULATION_SPEED_MEDIUM,
            3: AIR_CIRCULATION_SPEED_HIGH,
        }

        modelInfos.fanModes = {
            1: FAN_LOW,
            2: FAN_MEDIUM,
            3: FAN_HIGH,
            5: FAN_AUTO,
        }

        modelInfos.swingModes = {
            1: SWING_MODE_UP,
            2: SWING_MODE_MIDDLE_UP,
            3: SWING_MODE_MIDDLE_DOWN,
            4: SWING_MODE_DOWN,
        }

        modelInfos.HVACModes = AC_HVAC_MODES

    elif modelId >= 562 and modelId <= 570:
        name = "Air Conditioner User Interface "
        if zoneName is not None:
            modelInfos.name = name + "(" + zoneName + ")"
        else:
            modelInfos.name = name + "(#" + str(modelId - 561) + ")"

        modelInfos.type = CozytouchDeviceType.AC_CONTROLLER
        modelInfos.HVACModes = OFF_ONLY

    elif modelId == 1353:
        modelInfos.name = "Calypso Split Interface"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.HVACModes = OFF_ONLY

    elif modelId in CALYPSO_SPLIT_VM:
        modelInfos.name = CALYPSO_SPLIT_VM[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId == 1376:
        # The hot water slot of an appliance, not a product of its own : the
        # catalogue calls it DHW_0 and gives it no commercial reference.
        # See docs/decisions.md.
        modelInfos.name = "Domestic hot water"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId in TESC_SLOTS:
        # A heating circuit of an appliance, the same way THZONE is a zone of
        # a ducted one. See docs/decisions.md.
        modelInfos.name = (
            "Heating circuit (" + zoneName + ")"
            if zoneName is not None
            else "Heating circuit (#" + str(modelId - 1387) + ")"
        )
        modelInfos.type = CozytouchDeviceType.ZONE
        modelInfos.HVACModes = {}

    # 664 is catalogue only: the same string as 1369 in the vendor's older
    # all-capitals listing.
    elif modelId in (1369, 664):
        modelInfos.name = "Calypso Split"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    # 1370 is catalogue only: the 150L of a range captured in 200L and 270L.
    elif modelId in (1370, 1371, 1372):
        modelInfos.name = "Aeromax SPLIT 3"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId == 1381:
        modelInfos.name = "KELUD 1750W BLC"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = OFF_HEAT

    elif modelId == 1382:
        modelInfos.name = "KELUD 1750W Anthracite Standard"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = OFF_HEAT

    elif modelId in TOWEL_RACK_VARIANTS:
        modelInfos.name = TOWEL_RACK_VARIANTS[modelId]
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = OFF_HEAT

    elif modelId in NAEMA_3:
        modelInfos.name = NAEMA_3[modelId]
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = OFF_HEAT

    elif modelId in EXPLORER_V5:
        modelInfos.name = EXPLORER_V5[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId == 1656:
        modelInfos.name = "Aeromax 6"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId in AEROMAX_PREMIUM_CV5:
        modelInfos.name = AEROMAX_PREMIUM_CV5[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId == 1657:
        modelInfos.name = "Calypso 200L"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId == 1658:
        modelInfos.name = "Calypso connecté"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId == 1763:
        modelInfos.name = "FLAT/S4 IOTHUB"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.HVACModes = OFF_ONLY

    elif modelId in MALICIO_3:
        modelInfos.name = MALICIO_3[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    elif modelId in LINEO_CONNECTE_MP:
        modelInfos.name = LINEO_CONNECTE_MP[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
        }
    elif modelId in EGEO_PLATFORM:
        modelInfos.name = EGEO_PLATFORM[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    # 2375 and 2376 are catalogue only: 2374 without the coil, and 2374 sold
    # into Austria rather than Germany.
    elif modelId in (2374, 2375, 2376):
        modelInfos.name = "Explorer EVO 3 (270L)"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = OFF_HEAT

        modelInfos.HeatingModes = MANUAL_ECO_PROG

    else:
        # No branch names this model id, so the device is asked instead : what
        # it reports classifies it, and names it. See docs/decisions.md.
        derive(
            modelInfos, productId, modelFamily, masterProductId, zoneName, fallbackName
        )

    return modelInfos
