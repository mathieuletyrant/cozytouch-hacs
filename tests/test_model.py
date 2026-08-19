"""Contract tests for the model table.

get_model_infos is the single place that says what a device can do: capability.py
reads the flags it returns to decide which entities to create, so a group that
silently gains or loses one changes the entity list of every user who owns that
hardware. One case per branch of the table, plus the ids inside a branch that
resolve differently -- 1734 shares the air conditioner branch with 557-561 but
comes out with its own set of flags, and only a case each pins that down.

These are characterisation tests. The expectations were read off the mapping as
it stands, so they say nothing about whether a model is mapped *correctly* --
several are guesses from a single user's capture. What they catch is a change
nobody meant to make.
"""

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
)

from custom_components.cozytouch.const import (
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
from custom_components.cozytouch.model import CozytouchDeviceType, get_model_infos

MODEL_GROUPS = [
    (
        56,
        {
            "modelId": 56,
            "HVACModesCapabilityId": {7, 8},
            "name": "Naema 2 Micro 25",
            "type": CozytouchDeviceType.GAZ_BOILER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        61,
        {
            "modelId": 61,
            "HVACModesCapabilityId": {7, 8},
            "name": "Naia 2 Micro 25",
            "type": CozytouchDeviceType.GAZ_BOILER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        65,
        {
            "modelId": 65,
            "HVACModesCapabilityId": {7, 8},
            "name": "Naema 2 Duo 25",
            "type": CozytouchDeviceType.GAZ_BOILER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        76,
        {
            "modelId": 76,
            "HVACModesCapabilityId": {7, 8},
            "name": "Alfea Extensa Duo AI UE",
            "type": CozytouchDeviceType.HEAT_PUMP,
            "currentTemperatureAvailableZ1": False,
            "currentTemperatureAvailableZ2": True,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {0: HEATING_MODE_MANUAL},
            "exhaustTemperatureAvailable": False,
        },
    ),
    (
        211,
        {
            "modelId": 211,
            "HVACModesCapabilityId": {1, 2},
            "name": "Alfea Extensa Duo A.I. 3 R32",
            "type": CozytouchDeviceType.HEAT_PUMP,
            "currentTemperatureAvailableZ1": True,
            "currentTemperatureAvailableZ2": True,
            "HVACModes": {0: HVACMode.OFF, 1: HVACMode.HEAT, 2: HVACMode.AUTO},
            "HeatingModes": {0: HEATING_MODE_MANUAL},
            "exhaustTemperatureAvailable": False,
        },
    ),
    (
        235,
        {
            "modelId": 235,
            "HVACModesCapabilityId": {7, 8},
            "name": "Thermostat Navilink Connect",
            "type": CozytouchDeviceType.THERMOSTAT,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        236,
        {
            "modelId": 236,
            "HVACModesCapabilityId": {7, 8},
            "name": "Sauter Phazy",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        386,
        {
            "modelId": 386,
            "HVACModesCapabilityId": {7, 8},
            "name": "PHAZY VS 300L 3000M",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        387,
        {
            "modelId": 387,
            "HVACModesCapabilityId": {7, 8},
            "name": "PHAZY VM 150L 2200M",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        388,
        {
            "modelId": 388,
            "HVACModesCapabilityId": {7, 8},
            "name": "PHAZY VM 200L 2200M",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        389,
        {
            "modelId": 389,
            "HVACModesCapabilityId": {7, 8},
            "name": "AQUEO ACI HYB VS 300L 3000M",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        390,
        {
            "modelId": 390,
            "HVACModesCapabilityId": {7, 8},
            "name": "AQUEO ACI HYB VM 150L 2200M",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        391,
        {
            "modelId": 391,
            "HVACModesCapabilityId": {7, 8},
            "name": "AQUEO ACI HYB VM 200L 2200M",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        392,
        {
            "modelId": 392,
            "HVACModesCapabilityId": {7, 8},
            "name": "DURALIS CONNECT ACI HYB VS 300L 3000M",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        393,
        {
            "modelId": 393,
            "HVACModesCapabilityId": {7, 8},
            "name": "DURALIS CONNECT ACI HYB VM 150L 2200M",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        394,
        {
            "modelId": 394,
            "HVACModesCapabilityId": {7, 8},
            "name": "DURALIS CONNECT ACI HYB VM 200L 2200M",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        418,
        {
            "modelId": 418,
            "HVACModesCapabilityId": {7, 8},
            "name": "Atlantic Loria Duo 6006",
            "type": CozytouchDeviceType.THERMOSTAT,
            "exhaustTemperatureAvailable": True,
            "currentTemperatureAvailableZ1": True,
            "currentTemperatureAvailableZ2": False,
            "overrideModeAvailable": True,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        556,
        {
            "modelId": 556,
            "HVACModesCapabilityId": {7, 8},
            "name": "Naviclim Hub",
            "type": CozytouchDeviceType.HUB,
            "awayModeTemperatureAvailable": False,
            "HVACModes": {0: HVACMode.OFF},
        },
    ),
    (
        1457,
        {
            "modelId": 1457,
            "HVACModesCapabilityId": {7, 8},
            "name": "HUB Cozytouch",
            "type": CozytouchDeviceType.HUB,
            "HVACModes": {0: HVACMode.OFF},
        },
    ),
    (
        1758,
        {
            "modelId": 1758,
            "HVACModesCapabilityId": {7, 8},
            "name": "HUB Navizone",
            "type": CozytouchDeviceType.HUB,
            "awayModeTemperatureAvailable": False,
            "HVACModes": {0: HVACMode.OFF},
        },
    ),
    (
        557,
        {
            "modelId": 557,
            "HVACModesCapabilityId": {7, 8},
            "name": "Air Conditioner (#1)",
            "type": CozytouchDeviceType.AC,
            "quietModeAvailable": True,
            "awayModeTemperatureAvailable": False,
            "ecoModeAvailable": False,
            "AirCirculationSpeeds": {
                1: AIR_CIRCULATION_SPEED_LOW,
                2: AIR_CIRCULATION_SPEED_MEDIUM,
                3: AIR_CIRCULATION_SPEED_HIGH,
            },
            "fanModes": {1: FAN_LOW, 2: FAN_MEDIUM, 3: FAN_HIGH, 5: FAN_AUTO},
            "swingModes": {
                1: SWING_MODE_UP,
                2: SWING_MODE_MIDDLE_UP,
                3: SWING_MODE_MIDDLE_DOWN,
                4: SWING_MODE_DOWN,
            },
            "HVACModes": {
                0: HVACMode.OFF,
                1: HVACMode.AUTO,
                3: HVACMode.COOL,
                4: HVACMode.HEAT,
                7: HVACMode.FAN_ONLY,
                8: HVACMode.DRY,
            },
        },
    ),
    (
        561,
        {
            "modelId": 561,
            "HVACModesCapabilityId": {7, 8},
            "name": "Air Conditioner (#5)",
            "type": CozytouchDeviceType.AC,
            "quietModeAvailable": True,
            "awayModeTemperatureAvailable": False,
            "ecoModeAvailable": False,
            "AirCirculationSpeeds": {
                1: AIR_CIRCULATION_SPEED_LOW,
                2: AIR_CIRCULATION_SPEED_MEDIUM,
                3: AIR_CIRCULATION_SPEED_HIGH,
            },
            "fanModes": {1: FAN_LOW, 2: FAN_MEDIUM, 3: FAN_HIGH, 5: FAN_AUTO},
            "swingModes": {
                1: SWING_MODE_UP,
                2: SWING_MODE_MIDDLE_UP,
                3: SWING_MODE_MIDDLE_DOWN,
                4: SWING_MODE_DOWN,
            },
            "HVACModes": {
                0: HVACMode.OFF,
                1: HVACMode.AUTO,
                3: HVACMode.COOL,
                4: HVACMode.HEAT,
                7: HVACMode.FAN_ONLY,
                8: HVACMode.DRY,
            },
        },
    ),
    (
        1734,
        {
            "modelId": 1734,
            "HVACModesCapabilityId": {7, 8},
            "name": "Air Conditioner (#1)",
            "type": CozytouchDeviceType.AC,
            "quietModeAvailable": True,
            "awayModeTemperatureAvailable": False,
            "AirCirculationSpeeds": {
                1: AIR_CIRCULATION_SPEED_LOW,
                2: AIR_CIRCULATION_SPEED_MEDIUM,
                3: AIR_CIRCULATION_SPEED_HIGH,
            },
            "fanModes": {1: FAN_LOW, 2: FAN_MEDIUM, 3: FAN_HIGH, 5: FAN_AUTO},
            "swingModes": {
                1: SWING_MODE_UP,
                2: SWING_MODE_MIDDLE_UP,
                3: SWING_MODE_MIDDLE_DOWN,
                4: SWING_MODE_DOWN,
            },
            "HVACModes": {
                0: HVACMode.OFF,
                1: HVACMode.AUTO,
                3: HVACMode.COOL,
                4: HVACMode.HEAT,
                7: HVACMode.FAN_ONLY,
                8: HVACMode.DRY,
            },
        },
    ),
    (
        562,
        {
            "modelId": 562,
            "HVACModesCapabilityId": {7, 8},
            "name": "Air Conditioner User Interface (#1)",
            "type": CozytouchDeviceType.AC_CONTROLLER,
            "HVACModes": {0: HVACMode.OFF},
        },
    ),
    (
        570,
        {
            "modelId": 570,
            "HVACModesCapabilityId": {7, 8},
            "name": "Air Conditioner User Interface (#9)",
            "type": CozytouchDeviceType.AC_CONTROLLER,
            "HVACModes": {0: HVACMode.OFF},
        },
    ),
    (
        1353,
        {
            "modelId": 1353,
            "HVACModesCapabilityId": {7, 8},
            "name": "Calypso Split Interface",
            "type": CozytouchDeviceType.HUB,
            "HVACModes": {0: HVACMode.OFF},
        },
    ),
    (
        1369,
        {
            "modelId": 1369,
            "HVACModesCapabilityId": {7, 8},
            "name": "Calypso Split",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1376,
        {
            "modelId": 1376,
            "HVACModesCapabilityId": {7, 8},
            "name": "Calypso Split",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1371,
        {
            "modelId": 1371,
            "HVACModesCapabilityId": {7, 8},
            "name": "Aeromax SPLIT 3",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1372,
        {
            "modelId": 1372,
            "HVACModesCapabilityId": {7, 8},
            "name": "Aeromax SPLIT 3",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1381,
        {
            "modelId": 1381,
            "HVACModesCapabilityId": {7, 8},
            "name": "KELUD 1750W BLC",
            "type": CozytouchDeviceType.TOWEL_RACK,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        1382,
        {
            "modelId": 1382,
            "HVACModesCapabilityId": {7, 8},
            "name": "KELUD 1750W Anthracite Standard",
            "type": CozytouchDeviceType.TOWEL_RACK,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        1388,
        {
            "modelId": 1388,
            "HVACModesCapabilityId": {7, 8},
            "name": "Doris étroit 1500W BLC",
            "type": CozytouchDeviceType.TOWEL_RACK,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        1595,
        {
            "modelId": 1595,
            "HVACModesCapabilityId": {7, 8},
            "name": "Doris étroit 1300W CARAT",
            "type": CozytouchDeviceType.TOWEL_RACK,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        1444,
        {
            "modelId": 1444,
            "HVACModesCapabilityId": {7, 8},
            "name": "Naema 3 Micro 25",
            "type": CozytouchDeviceType.GAZ_BOILER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        1543,
        {
            "modelId": 1543,
            "HVACModesCapabilityId": {7, 8},
            "name": "Asama Connecté II Ventilo 1750W Blanc",
            "type": CozytouchDeviceType.TOWEL_RACK,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        1546,
        {
            "modelId": 1546,
            "HVACModesCapabilityId": {7, 8},
            "name": "Asama Connecté II Ventilo 1500W ANTH",
            "type": CozytouchDeviceType.TOWEL_RACK,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        1547,
        {
            "modelId": 1547,
            "HVACModesCapabilityId": {7, 8},
            "name": "Asama Connecté II Ventilo 1750W ANTH",
            "type": CozytouchDeviceType.TOWEL_RACK,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        1551,
        {
            "modelId": 1551,
            "HVACModesCapabilityId": {7, 8},
            "name": "Asama Connecté II Ventilo 1750W Noir",
            "type": CozytouchDeviceType.TOWEL_RACK,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        1622,
        {
            "modelId": 1622,
            "HVACModesCapabilityId": {7, 8},
            "name": "Thermor Riva 5",
            "type": CozytouchDeviceType.TOWEL_RACK,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
    (
        1641,
        {
            "modelId": 1641,
            "HVACModesCapabilityId": {7, 8},
            "name": "Atlantic Explorer V5 (200L)",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1642,
        {
            "modelId": 1642,
            "HVACModesCapabilityId": {7, 8},
            "name": "Atlantic Explorer V5 (270L)",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1644,
        {
            "modelId": 1644,
            "HVACModesCapabilityId": {7, 8},
            "name": "Atlantic Explorer V5 (240L)",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1645,
        {
            "modelId": 1645,
            "HVACModesCapabilityId": {7, 8},
            "name": "Atlantic Explorer V5 (270L with coil)",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1656,
        {
            "modelId": 1656,
            "HVACModesCapabilityId": {7, 8},
            "name": "Aeromax 6",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1657,
        {
            "modelId": 1657,
            "HVACModesCapabilityId": {7, 8},
            "name": "Calypso 200L",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1658,
        {
            "modelId": 1658,
            "HVACModesCapabilityId": {7, 8},
            "name": "Calypso connecté",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1763,
        {
            "modelId": 1763,
            "HVACModesCapabilityId": {7, 8},
            "name": "FLAT/S4 IOTHUB",
            "type": CozytouchDeviceType.HUB,
            "HVACModes": {0: HVACMode.OFF},
        },
    ),
    (
        1962,
        {
            "modelId": 1962,
            "HVACModesCapabilityId": {7, 8},
            "name": "Thermor Malicio 3 65L",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1966,
        {
            "modelId": 1966,
            "HVACModesCapabilityId": {7, 8},
            "name": "Thermor Malicio 3 120L",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        1957,
        {
            "modelId": 1957,
            "HVACModesCapabilityId": {7, 8},
            "name": "LINEO CONNECTE MP 100L 2250W",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {0: HEATING_MODE_MANUAL, 3: HEATING_MODE_ECO_PLUS},
        },
    ),
    (
        2346,
        {
            "modelId": 2346,
            "HVACModesCapabilityId": {7, 8},
            "name": "Egeo VS 250L",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        2374,
        {
            "modelId": 2374,
            "HVACModesCapabilityId": {7, 8},
            "name": "Explorer EVO 3 (260L)",
            "type": CozytouchDeviceType.WATER_HEATER,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
            "HeatingModes": {
                0: HEATING_MODE_MANUAL,
                3: HEATING_MODE_ECO_PLUS,
                4: HEATING_MODE_PROG,
            },
        },
    ),
    (
        9999,
        {
            "modelId": 9999,
            "HVACModesCapabilityId": {7, 8},
            "name": "Unknown product (9999)",
            "type": CozytouchDeviceType.UNKNOWN,
            "HVACModes": {0: HVACMode.OFF, 4: HVACMode.HEAT},
        },
    ),
]


@pytest.mark.parametrize(
    ("modelId", "expected"),
    MODEL_GROUPS,
    ids=[f"{modelId}-{expected['name']}" for modelId, expected in MODEL_GROUPS],
)
def test_model_group(modelId, expected):
    """Every branch of the table declares exactly what it declares today."""
    assert get_model_infos(modelId) == expected


@pytest.mark.parametrize("modelId", [557, 561, 562, 570])
def test_a_zone_name_replaces_the_numbered_name(modelId):
    """Units in a zone are named after the room, not their position."""
    assert get_model_infos(modelId, "Chambre parentale")["name"].endswith(
        "(Chambre parentale)"
    )


def test_an_unmapped_model_falls_through_to_unknown():
    """A device nobody has mapped still yields a usable, clearly labelled entry."""
    infos = get_model_infos(424242)
    assert infos["type"] == CozytouchDeviceType.UNKNOWN
    assert infos["name"] == "Unknown product (424242)"
