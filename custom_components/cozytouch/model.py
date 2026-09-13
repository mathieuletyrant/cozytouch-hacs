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
# products under both. ATL is Atlantic, TH Thermor, SA Sauter; the badges we
# have no commercial name for keep the catalogue's string.
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

# One water heater platform, coded TD <volume> VS <brand> <power>M TYB V5S,
# with SERP for the tank that carries a coil. Eight brands share it and the
# grid is volume x coil x brand.
#
# Atlantic's own badge, ATE, is the only one with a commercial name we know,
# so it is the only one whose ids read as Explorer V5; 1656 and 1657/1658 came
# from captures under the Thermor and AT badges and keep the names their
# reporters gave. The rest keep the catalogue's string, which is what they
# already displayed -- what they gain is the water heater type, and with it a
# resistance sensor that is not called a pump and a hot water mode select with
# options in it.
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

# One ACI HYB hybrid water heater platform sold under four brands, in VS 300L,
# VM 150L and VM 200L variants. Only the commercial name changes between the
# ids, so they share a branch. Names are the catalogue's own string, verbatim,
# because on this platform the brand *is* the name.
#
# The last three are that fourth badge, and are read off the catalogue rather
# than off a report: "THE DURALIS CONNECT VM 150 2200M PE" carries the product
# line and the figures of 393 and differs in the listing prefix, the dropped
# ACI HYB and a PE suffix. 386-394 came from captures; these three did not.
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

# The connectivity box, under each of the brands it is sold as. The catalogue
# calls 2447 "Hub IO Sauter" and the next three "Hub IO Thermor", "Hub IO
# Atlantic" and "Hub IO Inter": one box, four badges. This is a set rather
# than four branches because the branch below is not the whole of it -- a room
# slot reads its master's id to tell a radiator from an air conditioner, and
# an unmapped badge sent every one of them to the air conditioner branch.
# 2448, 2449 and 2450 are catalogue only -- 2447 is the badge that was
# captured.
COZYBOX_HUBS = {2447, 2448, 2449, 2450}

# The three connected towel rack ranges, by model id. Every one of these is the
# same product in another wattage or another finish -- the catalogue lists them
# as RIVA 5 ETROIT 0300W CARBONE beside RIVA 5 ETROIT 1300W BLC -- and the
# branch body was already identical for the eight that were mapped one at a
# time: a name, the towel rack type, and off/heat.
#
# The names are the house spelling of the catalogue's own string, minus the
# BRI suffix and the leading zero on a wattage. The eight that were already
# mapped keep the name they had, inconsistencies included ("1750W Blanc" next
# to "1500W ANTH"), because the name reaches the device registry and rewriting
# it renames the device of somebody who already has one.
TOWEL_RACK_VARIANTS = {
    1388: "Doris étroit 1500W BLC",
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

# Catalogue only, the whole table: name and the `productId` of 1 that puts
# these in the same family as 56, 61 and 65. A commercial name is not unique
# here -- 257 and 260 are both "Naema Micro 25" -- and the duplicates are
# distinct ids in the vendor's catalogue. See docs/decisions.md.
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
    masterModelId = next(
        (
            master["modelId"]
            for master in devices
            if master["deviceId"] == masterDeviceId
        ),
        None,
    )

    return get_model_infos(dev["modelId"], zoneName, dev.get("name"), masterModelId)


def get_model_infos(  # noqa: C901
    modelId: int,
    zoneName: str | None = None,
    deviceName: str | None = None,
    masterModelId: int | None = None,
) -> ModelInfos:
    """Return infos from model ID.

    One long if/elif over model ids, which is why it is over the complexity
    ceiling: the shape of the problem is a lookup table, and the table is the
    function. Splitting it per device type would move the branches without
    removing one.

    `deviceName` is the exception to that: a zone is recognised by the name the
    API gives it, before any id is looked at, because the ids are per zone
    rather than per product.

    `masterModelId` is the second one: a room slot's id says which room, not
    what the hardware is, so the hub it hangs off is what tells a radiator from
    an air conditioner. None when the device has no hub, or when the account
    does not hold it.
    """
    modelInfos = ModelInfos(modelId=modelId, HVACModesCapabilityId={7, 8})

    if deviceName is not None and deviceName.startswith(ZONE_NAME_PREFIX):
        # A zone of a ducted heat pump, not a product: it reports no climate
        # capability, so mapping it buys a name and silence rather than
        # entities. See docs/decisions.md.
        modelInfos.name = f"Zone ({zoneName})" if zoneName else deviceName
        modelInfos.type = CozytouchDeviceType.ZONE
        # Empty on purpose: the fall-through's off/heat pair is what made a
        # zone read as a thermostat that could heat.
        modelInfos.HVACModes = {}

    elif modelId in NAEMA_NAIA_BOILERS:
        # The first-generation Naema and Naia, plus the two Naema 2 that sit
        # beside the 56 below. Name and type only, no flag -- see
        # docs/decisions.md.
        modelInfos.name = NAEMA_NAIA_BOILERS[modelId]
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 56:
        modelInfos.name = "Naema 2 Micro 25"
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 61:
        modelInfos.name = "Naia 2 Micro 25"
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 65:
        modelInfos.name = "Naema 2 Duo 25"
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 76:
        modelInfos.name = "Alfea Extensa Duo AI UE"
        modelInfos.type = CozytouchDeviceType.HEAT_PUMP
        modelInfos.currentTemperatureAvailableZ1 = False
        modelInfos.currentTemperatureAvailableZ2 = True
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
        }

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

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
        }

        modelInfos.exhaustTemperatureAvailable = False

    elif modelId == 235:
        modelInfos.name = "Thermostat Navilink Connect"
        modelInfos.type = CozytouchDeviceType.THERMOSTAT
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 236:
        modelInfos.name = "Sauter Phazy"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }
        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    elif modelId in ACI_HYB_WATER_HEATERS:
        modelInfos.name = ACI_HYB_WATER_HEATERS[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }
        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    elif modelId == 418:
        modelInfos.name = "Loria 3 Duo R32"
        modelInfos.type = CozytouchDeviceType.THERMOSTAT
        modelInfos.exhaustTemperatureAvailable = True
        modelInfos.currentTemperatureAvailableZ1 = True
        modelInfos.currentTemperatureAvailableZ2 = False
        modelInfos.overrideModeAvailable = True

        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 556:
        modelInfos.name = "Naviclim Hub"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.awayModeTemperatureAvailable = False
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
        }

    elif modelId == 1457:
        modelInfos.name = "HUB Cozytouch"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
        }

    elif modelId in (1681, 1758):
        # AC gateway, drives the same 557-561 units as the 556 Naviclim hub
        modelInfos.name = "HUB Navizone"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.awayModeTemperatureAvailable = False
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
        }

    elif modelId in COZYBOX_HUBS:
        # Connectivity box, seen driving 557-560 room units like the hubs above
        modelInfos.name = "CozyBox"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.awayModeTemperatureAvailable = False
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
        }

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
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

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

        # 557-561 report 100507 and the app offers no eco mode for them;
        # 1734-1737 are left alone -- see docs/decisions.md.
        if modelId <= 561:
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

        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            1: HVACMode.AUTO,
            3: HVACMode.COOL,
            4: HVACMode.HEAT,
            7: HVACMode.FAN_ONLY,
            8: HVACMode.DRY,
        }

    elif modelId >= 562 and modelId <= 570:
        name = "Air Conditioner User Interface "
        if zoneName is not None:
            modelInfos.name = name + "(" + zoneName + ")"
        else:
            modelInfos.name = name + "(#" + str(modelId - 561) + ")"

        modelInfos.type = CozytouchDeviceType.AC_CONTROLLER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
        }

    elif modelId == 1353:
        modelInfos.name = "Calypso Split Interface"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
        }

    elif modelId in CALYPSO_SPLIT_VM:
        modelInfos.name = CALYPSO_SPLIT_VM[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    # 664 is catalogue only: the same string as 1369 in the vendor's older
    # all-capitals listing.
    elif modelId in (1369, 1376, 664):
        modelInfos.name = "Calypso Split"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    # 1370 is catalogue only: the 150L of a range captured in 200L and 270L.
    elif modelId in (1370, 1371, 1372):
        modelInfos.name = "Aeromax SPLIT 3"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    elif modelId == 1381:
        modelInfos.name = "KELUD 1750W BLC"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 1382:
        modelInfos.name = "KELUD 1750W Anthracite Standard"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId in TOWEL_RACK_VARIANTS:
        modelInfos.name = TOWEL_RACK_VARIANTS[modelId]
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId in NAEMA_3:
        modelInfos.name = NAEMA_3[modelId]
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId in EXPLORER_V5:
        modelInfos.name = EXPLORER_V5[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    elif modelId == 1656:
        modelInfos.name = "Aeromax 6"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    elif modelId in AEROMAX_PREMIUM_CV5:
        modelInfos.name = AEROMAX_PREMIUM_CV5[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    elif modelId == 1657:
        modelInfos.name = "Calypso 200L"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    elif modelId == 1658:
        modelInfos.name = "Calypso connecté"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    elif modelId == 1763:
        modelInfos.name = "FLAT/S4 IOTHUB"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
        }

    elif modelId in MALICIO_3:
        modelInfos.name = MALICIO_3[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    elif modelId in LINEO_CONNECTE_MP:
        modelInfos.name = LINEO_CONNECTE_MP[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
        }
    elif modelId in EGEO_PLATFORM:
        modelInfos.name = EGEO_PLATFORM[modelId]
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    # 2375 and 2376 are catalogue only: 2374 without the coil, and 2374 sold
    # into Austria rather than Germany.
    elif modelId in (2374, 2375, 2376):
        modelInfos.name = "Explorer EVO 3 (270L)"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
            4: HEATING_MODE_PROG,
        }

    else:
        # A catalogue name where there is one; the type stays UNKNOWN
        # either way. See docs/decisions.md.
        modelInfos.name = MODEL_CATALOGUE.get(
            modelId, "Unknown product (" + str(modelId) + ")"
        )
        modelInfos.type = CozytouchDeviceType.UNKNOWN
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    return modelInfos
