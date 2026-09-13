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
# rather than the model id, because the ids look like they encode the zone's
# index and not a product: a capture pairs 1505 with THZONE_0, 1506 with
# THZONE_1, and so on, which means a bigger installation walks off the end of
# any range guessed from one household. The API's own `name` field is checked,
# not `customName` -- renaming the zone in the Cozytouch app is a thing people
# do, and this has to survive it.
ZONE_NAME_PREFIX = "THZONE"

# Product lines whose ids are a grid the vendor fills in one figure at a time.
# Each table below holds every id of one line that the catalogue names; the
# ones that arrived from a capture are marked, and the rest are the catalogue's
# own listing of the same line in another volume, another badge or another
# country. See docs/decisions.md for what that evidence is worth.

# 1368 and 754 are two listings of the 200L; 1367 is the 150L of the same line.
CALYPSO_SPLIT_VM = {
    754: "Calypso SPLIT VM 200L",
    1367: "Calypso SPLIT VM 150L",
    1368: "Calypso SPLIT VM 200L",
}

# Two listings of one platform: EGEO VS <volume>L, and the internal code
# TD <volume> VS <brand> 1800M TYB CA. 1010/2346 and 957/2345 are the same two
# products under both. ATL is Atlantic, TH Thermor, SA Sauter; the badges we
# have no commercial name for keep the catalogue's string.
EGEO_PLATFORM = {
    957: "Egeo VS 200L",
    1010: "Egeo VS 250L",
    2345: "Egeo VS 200L",
    2346: "Egeo VS 250L",
    2347: "TD 200 VS TH 1800M TYB CA",
    2348: "TD 250 VS TH 1800M TYB CA",
    2349: "TD 200 VS SA 1800M TYB CA",
    2350: "TD 250 VS SA 1800M TYB CA",
    2351: "TD 250 VS ATE 1800M TYB CA SERP",
    2352: "TD 250 VS THE 1800M TYB CA SERP",
}

AEROMAX_PREMIUM_CV5 = {
    1669: "CV5 Aeromax Premium 100L",
    1670: "CV5 Aeromax Premium 150L",
}

# 1957 came from a capture and declares no prog mode, which is why the others
# do not either: they are the same appliance in another volume.
LINEO_CONNECTE_MP = {
    1954: "LINEO CONNECTE MP 040L 2250W",
    1955: "LINEO CONNECTE MP 065L 2250W",
    1956: "LINEO CONNECTE MP 080L 2250W",
    1957: "LINEO CONNECTE MP 100L 2250W",
}

# MP and VM are two form factors of one range. The names drop that letter, as
# the two captured ids already did -- except at 100L, where both exist and the
# letter is the only thing telling them apart.
MALICIO_3 = {
    1961: "Thermor Malicio 3 40L",
    1962: "Thermor Malicio 3 65L",
    1963: "Thermor Malicio 3 80L",
    1964: "Thermor Malicio 3 MP 100L",
    1965: "Thermor Malicio 3 VM 100L",
    1966: "Thermor Malicio 3 120L",
    1967: "Thermor Malicio 3 150L",
}

NAEMA_3 = {
    1444: "Naema 3 Micro 25",
    1445: "Naema 3 Micro 30",
    1446: "Naema 3 Micro 35",
    1447: "Naema 3 Duo 25",
    1448: "Naema 3 Duo 35",
}

# 219 is 211 under the Thermor badge, and the catalogue says so in the name.
ALFEA_EXTENSA_DUO_AI_3 = {
    211: "Alfea Extensa Duo A.I. 3 R32",
    219: "Alfea Extensa Duo A.I. 3 R32 Thermor",
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
    1643: "Atlantic Explorer V5 (200L with coil)",
    1644: "Atlantic Explorer V5 (240L)",
    1645: "Atlantic Explorer V5 (270L with coil)",
    1646: "TD 200 VS THE 1200M TYB V5S",
    1647: "TD 270 VS THE 1200M TYB V5S",
    1648: "TD 200 VS THE 1200M TYB V5S SERP",
    1649: "TD 270 VS THE 1200M TYB V5S SERP",
    1650: "TD 200 VS AE 1200M TYB V5S",
    1651: "TD 270 VS AE 1200M TYB V5S",
    1652: "TD 200 VS AE 1200M TYB V5S SERP",
    1653: "TD 240 VS AE 1200M TYB V5S SERP",
    1654: "TD 270 VS AE 1200M TYB V5S SERP",
    1655: "TD 200 VS TH 1200M TYB V5S",
    1659: "TD 270 VS SA 1200M TYB V5S",
    1660: "TD 200 VS ATS 1200M TYB V5S SERP",
    1661: "TD 240 VS ATS 1200M TYB V5S SERP",
    1662: "TD 270 VS ATS 1200M TYB V5S SERP",
    1663: "TD 200 VS NEU 1200M TYB V5S SERP",
    1664: "TD 270 VS NEU 1200M TYB V5S SERP",
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
    1364: "THE DURALIS CONNECT VM 150 2200M PE",
    1365: "THE DURALIS CONNECT VM 200 2200M PE",
    1366: "THE DURALIS CONNECT VS 300 3000M PE",
}

# The connectivity box, under each of the brands it is sold as. The catalogue
# calls 2447 "Hub IO Sauter" and the next three "Hub IO Thermor", "Hub IO
# Atlantic" and "Hub IO Inter": one box, four badges. This is a set rather
# than four branches because the branch below is not the whole of it -- a room
# slot reads its master's id to tell a radiator from an air conditioner, and
# an unmapped badge sent every one of them to the air conditioner branch.
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
    1540: "Asama Connecté II 500W BLC",
    1541: "Asama Connecté II 750W BLC",
    1542: "Asama Connecté II 1500W BLC",
    1543: "Asama Connecté II 1750W Blanc",
    1544: "Asama Connecté II 500W ANTH",
    1545: "Asama Connecté II 750W ANTH",
    1546: "Asama Connecté II 1500W ANTH",
    1547: "Asama Connecté II 1750W ANTH",
    1548: "Asama Connecté II 500W NOIR",
    1549: "Asama Connecté II 750W NOIR",
    1550: "Asama Connecté II 1500W NOIR",
    1551: "Asama Connecté II 1750W Noir",
    1552: "Asama Connecté II 500W CAPP",
    1553: "Asama Connecté II 750W CAPP",
    1554: "Asama Connecté II 1500W CAPP",
    1555: "Asama Connecté II 1750W CAPP",
    1562: "Doris étroit 300W BLC",
    1563: "Doris étroit 500W BLC",
    1564: "Riva 5 étroit 300W BLC",
    1565: "Riva 5 étroit 500W BLC",
    1587: "Doris étroit 1300W BLC",
    1588: "Doris étroit 1500W BLC",
    1589: "Doris étroit 300W ANTH",
    1590: "Doris étroit 500W ANTH",
    1591: "Doris étroit 1300W ANTH",
    1592: "Doris étroit 1500W ANTH",
    1593: "Doris étroit 300W CARAT",
    1594: "Doris étroit 500W CARAT",
    1595: "Doris étroit 1300W CARAT",
    1596: "Doris étroit 1500W CARAT",
    1597: "Doris étroit 300W NOIR",
    1598: "Doris étroit 500W NOIR",
    1599: "Doris étroit 1300W NOIR",
    1600: "Doris étroit 1500W NOIR",
    1622: "Riva 5 étroit 1300W BLC",
    1623: "Riva 5 étroit 1500W BLC",
    1624: "Riva 5 étroit 300W ARDOISE",
    1625: "Riva 5 étroit 300W MENHIR",
    1626: "Riva 5 étroit 500W MENHIR",
    1627: "Riva 5 étroit 1300W MENHIR",
    1628: "Riva 5 étroit 1500W MENHIR",
    1629: "Riva 5 étroit 500W ARDOISE",
    1630: "Riva 5 étroit 1300W ARDOISE",
    1631: "Riva 5 étroit 1500W ARDOISE",
    1632: "Riva 5 étroit 300W CARBONE",
    1633: "Riva 5 étroit 500W CARBONE",
    1634: "Riva 5 étroit 1300W CARBONE",
    1635: "Riva 5 étroit 1500W CARBONE",
}

# Boilers whose only source is the vendor's model catalogue: name, and the
# `productId` of 1 that puts them in the same family as 56, 61 and 65. Kept as
# a table rather than one branch each because the branch body is identical --
# the ids differ by their commercial name and nothing else.
#
# Only the Naema and the Naia are taken from that family. The other ~165 ids
# sharing `productId` 1 are Guillot collective boilers -- VARMAX, VARBLOK,
# CONDENSINOX and the like -- which nobody has ever reported running through
# this integration, and mapping a model is what *stops* the unknown-model
# repair asking its owner for a dump. Naming a product line we have never seen
# would trade the only signal that would tell us it exists.
#
# A commercial name is not unique: 257 and 260 are both "Naema Micro 25", 258
# and 261 both "Naema Micro 30". They are separate model ids in the vendor's
# own catalogue -- regional variants, most likely -- and are kept apart rather
# than collapsed.
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
        # A THZONE is one zone of a ducted heat pump, not a product. What it
        # reports, in the one capture there is, is two capabilities -- 218
        # reading "0" and 100014 reading "255" -- and no climate capability:
        # no setpoint, nothing to drive.
        #
        # Mapping it buys a name and silence rather than entities. Unmapped it
        # arrived as "Unknown product (1505)" *and* raised an unmapped-model
        # repair per zone, six dialogs asking for a diagnostics dump about
        # hardware working as designed. Reported upstream as
        # gduteil/cozytouch#167.
        modelInfos.name = f"Zone ({zoneName})" if zoneName else deviceName
        modelInfos.type = CozytouchDeviceType.ZONE
        # Claims nothing. The fall-through at the end hands every unmapped
        # model an off/heat pair, and that is what made a zone read as a
        # thermostat that could heat.
        modelInfos.HVACModes = {}

    elif modelId in NAEMA_NAIA_BOILERS:
        # The first-generation Naema and Naia, plus the two Naema 2 that sit
        # beside the 56 below. Names are the vendor's own, read back from
        # `GET /magellan/productmodels/models/{id}` -- see docs/decisions.md;
        # `productId` is 1 on every one of them, which the app's own table
        # calls PASS_APC_BOILER.
        #
        # Nothing but the name and the type: no capture exists for any of
        # these, and the three boilers already mapped (56, 61, 65) declare
        # exactly this and no flag. The fall-through already handed them
        # {off, heat}, so this changes the name and the type and nothing a
        # device does.
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
        # A room slot behind a hub, not a product: 557-561 is the room's index
        # and says nothing about the hardware. Behind a CozyBox the slot is a
        # connected electric radiator, behind a Naviclim or Navizone a room air
        # conditioner unit -- same ids, same productIds, same ROOM_n name.
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

        # The room units behind a Naviclim/Navizone hub report 100507, but the
        # Cozytouch app offers no eco mode for them anywhere. 1734-1737 are
        # left alone, no report either way on those -- see docs/decisions.md.
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
        # The vendor names far more models than this table has branches
        # for, and a name is what lets somebody recognise the device they
        # own. The type stays UNKNOWN either way, so the repair asking for
        # a dump is raised exactly as before.
        modelInfos.name = MODEL_CATALOGUE.get(
            modelId, "Unknown product (" + str(modelId) + ")"
        )
        modelInfos.type = CozytouchDeviceType.UNKNOWN
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    return modelInfos
