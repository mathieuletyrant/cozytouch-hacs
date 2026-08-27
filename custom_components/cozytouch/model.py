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
from .infos import ModelInfos


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
    ZONE = "zone"


# What the API calls a zone of a ducted heat pump. The name is the signal
# rather than the model id, because the ids look like they encode the zone's
# index and not a product: a capture pairs 1505 with THZONE_0, 1506 with
# THZONE_1, and so on, which means a bigger installation walks off the end of
# any range guessed from one household. The API's own `name` field is checked,
# not `customName` -- renaming the zone in the Cozytouch app is a thing people
# do, and this has to survive it.
ZONE_NAME_PREFIX = "THZONE"


def get_model_infos(  # noqa: C901
    modelId: int,
    zoneName: str | None = None,
    deviceName: str | None = None,
) -> ModelInfos:
    """Return infos from model ID.

    One long if/elif over model ids, which is why it is over the complexity
    ceiling: the shape of the problem is a lookup table, and the table is the
    function. Splitting it per device type would move the branches without
    removing one.

    `deviceName` is the exception to that: a zone is recognised by the name the
    API gives it, before any id is looked at, because the ids are per zone
    rather than per product.
    """
    modelInfos = ModelInfos(modelId=modelId, HVACModesCapabilityId={7, 8})

    if (deviceName or "").startswith(ZONE_NAME_PREFIX):
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

    elif modelId == 211:
        modelInfos.name = "Alfea Extensa Duo A.I. 3 R32"
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

    elif 386 <= modelId <= 394:
        # One ACI HYB hybrid water heater platform sold under three brands, in
        # VS 300L, VM 150L and VM 200L variants. Only the commercial name
        # changes between the nine ids, so they share a branch.
        modelInfos.name = {
            386: "PHAZY VS 300L 3000M",
            387: "PHAZY VM 150L 2200M",
            388: "PHAZY VM 200L 2200M",
            389: "AQUEO ACI HYB VS 300L 3000M",
            390: "AQUEO ACI HYB VM 150L 2200M",
            391: "AQUEO ACI HYB VM 200L 2200M",
            392: "DURALIS CONNECT ACI HYB VS 300L 3000M",
            393: "DURALIS CONNECT ACI HYB VM 150L 2200M",
            394: "DURALIS CONNECT ACI HYB VM 200L 2200M",
        }[modelId]
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
        modelInfos.name = "Atlantic Loria Duo 6006"
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

    elif modelId == 1758:
        # AC gateway, drives the same 557-561 units as the 556 Naviclim hub
        modelInfos.name = "HUB Navizone"
        modelInfos.type = CozytouchDeviceType.HUB
        modelInfos.awayModeTemperatureAvailable = False
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
        }

    elif (modelId >= 557 and modelId <= 561) or modelId == 1734:
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
        # Cozytouch app offers no eco mode for them anywhere. 1734 is a separate
        # product and is left alone, no report either way on that one.
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

    elif modelId in (1369, 1376):
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

    elif modelId in (1371, 1372):
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

    elif modelId == 1388:
        modelInfos.name = "Doris étroit 1500W BLC"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 1595:
        modelInfos.name = "Doris étroit 1300W CARAT"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 1444:
        modelInfos.name = "Naema 3 Micro 25"
        modelInfos.type = CozytouchDeviceType.GAZ_BOILER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 1543:
        modelInfos.name = "Asama Connecté II Ventilo 1750W Blanc"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }
    elif modelId == 1546:  # Asama Connecté II Ventilo 1500W
        modelInfos.name = "Asama Connecté II Ventilo 1500W ANTH"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 1547:  # Asama Connecté II Ventilo 1750W
        modelInfos.name = "Asama Connecté II Ventilo 1750W ANTH"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 1551:
        modelInfos.name = "Asama Connecté II Ventilo 1750W Noir"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 1622:
        modelInfos.name = "Thermor Riva 5"
        modelInfos.type = CozytouchDeviceType.TOWEL_RACK
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    elif modelId == 1641:
        modelInfos.name = "Atlantic Explorer V5 (200L)"
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

    elif modelId == 1642:
        modelInfos.name = "Atlantic Explorer V5 (270L)"
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

    elif modelId == 1644:
        modelInfos.name = "Atlantic Explorer V5 (240L)"
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

    elif modelId == 1645:
        modelInfos.name = "Atlantic Explorer V5 (270L with coil)"
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

    elif modelId == 1962:
        modelInfos.name = "Thermor Malicio 3 65L"
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

    elif modelId == 1966:
        modelInfos.name = "Thermor Malicio 3 120L"
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

    elif modelId == 1957:
        modelInfos.name = "LINEO CONNECTE MP 100L 2250W"
        modelInfos.type = CozytouchDeviceType.WATER_HEATER
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

        modelInfos.HeatingModes = {
            0: HEATING_MODE_MANUAL,
            3: HEATING_MODE_ECO_PLUS,
        }
    elif modelId == 2346:
        modelInfos.name = "Egeo VS 250L"
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

    elif modelId == 2374:
        modelInfos.name = "Explorer EVO 3 (260L)"
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
        modelInfos.name = "Unknown product (" + str(modelId) + ")"
        modelInfos.type = CozytouchDeviceType.UNKNOWN
        modelInfos.HVACModes = {
            0: HVACMode.OFF,
            4: HVACMode.HEAT,
        }

    return modelInfos
