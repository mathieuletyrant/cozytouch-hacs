"""Atlantic Cozytouch capabilility mapping."""

from homeassistant.const import UnitOfEnergy, UnitOfPressure

from .const import CozytouchCapabilityVariableType
from .model import CozytouchDeviceType

PROG_DAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


# Capabilities the device uses to describe itself: what it supports, what its
# scheduler allows, which controls exist. Named from the capability list shared
# in gduteil/cozytouch#86, which gives Atlantic's own identifier for each id --
# but not the unit, nor the encoding, nor how to read a bitmask.
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
    157: "override_setpoint_activation",
    166: "available_operating_services",
    217: "available_system_modes",
    294: "temperature_update_step",
    295: "schedule_time_step",
    296: "schedule_minimum_interval",
    236: "max_dhw_schedule_slots_per_day",
    306: "max_schedule_slots_per_day",
    350: "supported_air_mixing_speeds",
    100002: "supported_ventilation_options",
    100004: "available_ventilation_controls",
    100013: "available_schedule_types",
    100021: "supported_ventilation_controls",
    100022: "supported_operating_services",
    100023: "supported_system_modes",
    100024: "available_ventilation_options",
    100102: "ventilation_adaptive_planning",
    100103: "ventilation_unexpected_events",
    100300: "schedule_start_day",
    100301: "max_schedule_slots_per_week",
    100450: "ventilation_heating_anticipation",
    100800: "ventilation_fan_speed_mode",
    104050: "open_window_detection",
}


def get_capability_infos(  # noqa: C901
    modelInfos: dict,
    capabilityId: int,
    capabilityValue: str,
    availableCapabilityIds: set[int],
):
    """Get capabilities for a device.

    availableCapabilityIds is what the device actually reports. Optional
    features are declared per model, but the same model id is reused across
    hardware that does not always implement them, so they are only wired up
    when the device backs them.
    """
    modelId = modelInfos["modelId"]

    capability = {"modelId": modelId, "capabilityId": capabilityId}

    if (
        capabilityId in (1, 2, 7, 8)
        and capabilityId in modelInfos["HVACModesCapabilityId"]
    ):
        # Default Ids
        capability["targetCapabilityId"] = 40
        capability["lowestValueCapabilityId"] = 160
        capability["highestValueCapabilityId"] = 161

        if (
            modelInfos.get("currentTemperatureAvailable", True)
            and 117 in availableCapabilityIds
        ):
            capability["currentValueCapabilityId"] = 117

        # 181 carries the mode the device is really running, which is not always
        # the one it was asked for
        if 181 in availableCapabilityIds:
            capability["hvacActionCapabilityId"] = 181

        # While air circulation runs it drives the unit, and the Cozytouch app
        # locks the mode and setpoint for the duration
        if 102024 in availableCapabilityIds:
            capability["airCirculationCapabilityId"] = 102024

        # TEMPERATURE_UPDATE_STEP: the device states the setpoint granularity
        if 294 in availableCapabilityIds:
            capability["stepCapabilityId"] = 294

        if modelInfos["type"] == CozytouchDeviceType.GAZ_BOILER:
            capability["name"] = "central_heating"
            capability["icon"] = "mdi:radiator"
            capability["progCapabilityId"] = 184
            capability["progOverrideCapabilityId"] = 157
            capability["progOverrideTotalTimeCapabilityId"] = 158
            capability["progOverrideTimeCapabilityId"] = 159
        elif modelInfos["type"] == CozytouchDeviceType.TOWEL_RACK:
            capability["name"] = "heat"
            capability["icon"] = "mdi:heating-coil"
            capability["progCapabilityId"] = 184
            capability["progOverrideCapabilityId"] = 157
            capability["progOverrideTotalTimeCapabilityId"] = 158
            capability["progOverrideTimeCapabilityId"] = 159
        elif modelInfos["type"] == CozytouchDeviceType.AC:
            capability["name"] = "air_conditioner"
            capability["icon"] = "mdi:air-conditioner"
            capability["targetCoolCapabilityId"] = 177
            capability["lowestCoolValueCapabilityId"] = 162
            capability["highestCoolValueCapabilityId"] = 163
            if 100506 in availableCapabilityIds:
                capability["activityCapabilityId"] = 100506
            if (
                modelInfos.get("ecoModeAvailable", True)
                and 100507 in availableCapabilityIds
            ):
                capability["ecoCapabilityId"] = 100507
            if 100505 in availableCapabilityIds:
                capability["boostCapabilityId"] = 100505
        elif modelInfos["type"] == CozytouchDeviceType.HEAT_PUMP:
            if capabilityId in (1, 7):
                capability["name"] = "heat_pump_z1"
                capability["targetCapabilityId"] = 17
                if (
                    modelInfos.get("currentTemperatureAvailableZ1", True)
                    and 117 in availableCapabilityIds
                ):
                    capability["currentValueCapabilityId"] = 117
                else:
                    capability["currentValueCapabilityId"] = None
            else:
                capability["name"] = "heat_pump_z2"
                capability["targetCapabilityId"] = 18
                if (
                    modelInfos.get("currentTemperatureAvailableZ2", True)
                    and 118 in availableCapabilityIds
                ):
                    capability["currentValueCapabilityId"] = 118
                else:
                    capability["currentValueCapabilityId"] = None

            # capability["lowestValueCapabilityId"] = 172
            # capability["highestValueCapabilityId"] = 171
            capability.pop("lowestValueCapabilityId")
            capability.pop("highestValueCapabilityId")
            capability["icon"] = "mdi:heat-pump"
        else:
            capability["name"] = "heat"

        capability["type"] = "climate"
        capability["category"] = "sensor"

        if "fanModes" in modelInfos and 100801 in availableCapabilityIds:
            capability["fanModeCapabilityId"] = 100801

        if (
            modelInfos.get("quietModeAvailable", False)
            and 100802 in availableCapabilityIds
        ):
            capability["quietModeCapabilityId"] = 100802

        if modelInfos.get("overrideModeAvailable", True):
            capability["progCapabilityId"] = 184
            capability["progOverrideCapabilityId"] = 157
            capability["progOverrideTotalTimeCapabilityId"] = 158
            capability["progOverrideTimeCapabilityId"] = 159

        if "swingModes" in modelInfos and 100803 in availableCapabilityIds:
            capability["swingModeCapabilityId"] = 100803

            if 100804 in availableCapabilityIds:
                capability["swingOnCapabilityId"] = 100804

    elif capabilityId == 19:
        capability["name"] = "temperature_setpoint"
        capability["type"] = "temperature"
        capability["category"] = "sensor"

    elif capabilityId == 22:
        capability["name"] = "target_temperature_dhw"
        capability["type"] = "temperature_adjustment_number"
        capability["category"] = "sensor"
        if modelId == 2374:
            capability["lowestValueCapabilityId"] = 253
            capability["highestValueCapabilityId"] = 252
            capability["step"] = 1
        else:
            capability["lowestValueCapabilityId"] = 160
            capability["highestValueCapabilityId"] = 161

    elif capabilityId == 25:
        capability["name"] = "number_of_starts_ch_pump"
        capability["type"] = "int"
        capability["category"] = "diag"
        capability["icon"] = "mdi:water-pump"

    elif capabilityId == 26:
        capability["name"] = "number_of_starts_dhw_pump"
        capability["type"] = "int"
        capability["category"] = "diag"
        capability["icon"] = "mdi:water-pump"

    elif capabilityId == 28:
        capability["name"] = "number_of_hours_ch_pump"
        capability["type"] = "int"
        capability["category"] = "diag"
        capability["icon"] = "mdi:water-pump"

    elif capabilityId == 29:
        capability["name"] = "number_of_hours_dhw_pump"
        capability["type"] = "int"
        capability["category"] = "diag"
        capability["icon"] = "mdi:water-pump"

    elif capabilityId == 40:
        capability["name"] = "target_temperature"
        capability["type"] = "temperature_adjustment_number"
        capability["category"] = "sensor"
        capability["lowestValueCapabilityId"] = 160
        capability["highestValueCapabilityId"] = 161

    elif capabilityId == 41:
        capability["name"] = "target_temperature_eco_z1"
        capability["type"] = "temperature_adjustment_number"
        capability["category"] = "sensor"
        capability["lowestValueCapabilityId"] = 160
        capability["highestValueCapabilityId"] = 161

    elif capabilityId == 42:
        capability["name"] = "target_temperature_eco_z2"
        capability["type"] = "temperature_adjustment_number"
        capability["category"] = "sensor"
        capability["lowestValueCapabilityId"] = 160
        capability["highestValueCapabilityId"] = 161

    elif capabilityId == 44:
        capability["name"] = "ch_power_consumption"
        capability["type"] = "energy"
        capability["displayed_unit_of_measurement"] = UnitOfEnergy.KILO_WATT_HOUR
        capability["category"] = "sensor"
        capability["icon"] = "mdi:radiator"

    elif capabilityId == 45:
        capability["name"] = "dhw_power_consumption"
        capability["type"] = "energy"
        capability["displayed_unit_of_measurement"] = UnitOfEnergy.KILO_WATT_HOUR
        capability["category"] = "sensor"
        capability["icon"] = "mdi:faucet"

    elif capabilityId == 46:
        capability["name"] = "total_power_consumption"
        capability["type"] = "energy"
        capability["displayed_unit_of_measurement"] = UnitOfEnergy.KILO_WATT_HOUR
        capability["category"] = "sensor"
        capability["icon"] = "mdi:water-boiler"

    elif capabilityId in (57, 59):
        capability["name"] = "power_consumption"
        capability["type"] = "energy"
        capability["displayed_unit_of_measurement"] = UnitOfEnergy.KILO_WATT_HOUR
        capability["category"] = "sensor"

    elif capabilityId == 86:
        capability["name"] = "domestic_hot_water"
        capability["type"] = "switch"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:faucet"

    elif capabilityId == 87:
        # water-boiler icon: this is the domestic-hot-water mode, not heating.
        capability["name"] = "domestic_hot_water_mode"
        capability["type"] = "select"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:water-boiler"
        capability["modelList"] = "HeatingModes"

    elif capabilityId == 88:
        capability["name"] = "model_name"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:tag"

    elif capabilityId in (94, 98):
        capability["name"] = "product_number"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:tag"

    elif capabilityId == 99:
        if modelInfos["type"] == CozytouchDeviceType.WATER_HEATER:
            capability["name"] = "resistance"
            capability["icon"] = "mdi:radiator"
        else:
            capability["name"] = "dhw_pump"
            capability["icon"] = "mdi:faucet"

        capability["type"] = "binary"
        capability["category"] = "sensor"

    elif capabilityId == 100:
        capability["name"] = "water_pressure"
        capability["type"] = "pressure"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:gauge"
        capability["displayed_unit_of_measurement"] = UnitOfPressure.BAR

    elif capabilityId in (101, 102, 103, 104):
        capability["name"] = "Capability_" + str(capabilityId)
        capability["type"] = "string"
        capability["value_type"] = CozytouchCapabilityVariableType.ARRAY
        capability["category"] = "sensor"

    elif capabilityId == 109:
        capability["name"] = "boiler_water_temperature"
        capability["type"] = "temperature"
        capability["category"] = "sensor"

    elif capabilityId == 111:
        capability["name"] = "dhw_temperature"
        capability["type"] = "temperature"
        capability["category"] = "sensor"

    elif capabilityId == 116:
        if modelInfos.get("exhaustTemperatureAvailable", True):
            capability["name"] = "exhaust_temperature"
            capability["type"] = "temperature"
            capability["category"] = "sensor"
        else:
            return {}

    elif capabilityId == 117:
        capability["name"] = "thermostat_temperature_z1"
        capability["type"] = "temperature"
        capability["category"] = "sensor"

    elif capabilityId == 118:
        capability["name"] = "thermostat_temperature_z2"
        capability["type"] = "temperature"
        capability["category"] = "sensor"

    elif capabilityId == 119:
        # Outside temperature is invalid when value is -327.68
        if float(capabilityValue) > -327.68:
            capability["name"] = "outside_temperature"
            capability["type"] = "temperature"
            capability["category"] = "sensor"
        else:
            return {}

    elif capabilityId == 121:
        capability["name"] = "version"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:tag"

    elif capabilityId in (152, 227):
        capability["name"] = "away_mode"
        capability["type"] = "away_mode_switch"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:airplane"
        capability["value_off"] = "0"
        capability["value_on"] = "1"
        capability["value_pending"] = "2"
        if capabilityId == 152:
            capability["timestampsCapabilityId"] = 222
        elif capabilityId == 227:
            capability["timestampsCapabilityId"] = 226

    elif capabilityId == 153:
        if modelInfos["type"] == CozytouchDeviceType.TOWEL_RACK:
            capability["name"] = "resistance"
            capability["icon"] = "mdi:radiator"
        else:
            capability["name"] = "flame"
            capability["icon"] = "mdi:fire"

        capability["type"] = "binary"
        capability["category"] = "sensor"

    elif capabilityId == 154:
        capability["name"] = "zone_1"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:home-floor-1"

    elif capabilityId == 155:
        capability["name"] = "zone_2"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:home-floor-2"

    # elif capabilityId == 157:
    #    # Prog override flag
    #    return {}

    elif capabilityId == 158:
        if modelInfos["type"] == CozytouchDeviceType.TOWEL_RACK:
            capability["name"] = "override_total_time"
        else:
            capability["name"] = "override_total_time_z1"

        capability["type"] = "hours_adjustment_number"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:clock-outline"
        capability["lowest_value"] = 1
        capability["highest_value"] = 24

    elif capabilityId == 159:
        if modelInfos["type"] == CozytouchDeviceType.TOWEL_RACK:
            capability["name"] = "override_remain_time"
        else:
            capability["name"] = "override_remain_time_z1"

        capability["type"] = "time"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:clock-outline"

    elif capabilityId == 160:
        # Target temperature adjustment min limit
        capability["name"] = "temperature_adjustment_min"
        capability["type"] = "temperature"
        capability["category"] = "diag"
        capability["icon"] = "mdi:thermometer-chevron-down"

    elif capabilityId == 161:
        # Target temperature adjustment max limit
        capability["name"] = "temperature_adjustment_max"
        capability["type"] = "temperature_adjustment_number"
        capability["category"] = "diag"
        capability["icon"] = "mdi:thermometer-chevron-up"
        capability["lowest_value"] = 19
        capability["highest_value"] = 28
        capability["step"] = 0.5

    elif capabilityId in (162, 163):
        # The cooling counterpart of the 160/161 heating bounds. Two independent
        # reverse-engineering efforts name these the same way, so the unit is
        # not a guess -- but nothing reads them yet. Wiring them as the climate
        # entity's min and max while cooling is a separate change.
        capability["name"] = (
            "cooling_temperature_min"
            if capabilityId == 162
            else "cooling_temperature_max"
        )
        capability["type"] = "temperature"
        capability["category"] = "diag"
        capability["enabled_by_default"] = False

    elif capabilityId == 165:
        # water-boiler icon: a domestic-hot-water boost, not the generic boost.
        capability["name"] = "domestic_hot_water_boost"
        capability["type"] = "switch"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:water-boiler"

        if modelInfos["type"] == CozytouchDeviceType.HEAT_PUMP:
            capability["value_off"] = "false"
            capability["value_on"] = "true"

    elif capabilityId == 169:
        capability["name"] = "radio_signal"
        capability["type"] = "percentage"
        capability["category"] = "diag"
        capability["icon"] = "mdi:radio-tower"

    elif capabilityId == 172:
        # Absence setpoint. Only the heating products act on it. An air
        # conditioner reports it and stores what is written, but never reads it
        # back: absence there stops the units until the return date, and the
        # weekly program keeps driving 40 and 177 throughout. Exposing a number
        # nothing honours would promise a setting the Cozytouch app does not
        # even offer on this hardware.
        if not modelInfos.get("awayModeTemperatureAvailable", True):
            return {}

        capability["name"] = "away_mode_temperature"
        capability["type"] = "temperature_adjustment_number"
        capability["category"] = "sensor"
        capability["lowestValueCapabilityId"] = 160
        capability["highestValueCapabilityId"] = 161

    elif capabilityId == 177:
        if modelInfos["type"] == CozytouchDeviceType.GAZ_BOILER:
            return {}

        capability["name"] = "target_cool_temperature"
        capability["type"] = "temperature_adjustment_number"
        capability["category"] = "sensor"
        capability["lowestValueCapabilityId"] = 162
        capability["highestValueCapabilityId"] = 163

    elif capabilityId == 179:
        capability["name"] = "wifi_signal"
        capability["type"] = "signal"
        capability["category"] = "diag"
        capability["icon"] = "mdi:wifi"

    elif capabilityId == 181:
        # Ignore, same as heat sensor (7, 8)
        return {}

    elif capabilityId == 184:
        capability["name"] = "prog_mode"
        capability["type"] = "switch"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:clock-outline"

    elif capabilityId == 303:
        # ERROR_CODE_ROOM, a matrix the device fills with zeroes when healthy.
        # Surfaced raw: the list gives the name, not how to read the codes.
        capability["name"] = "error_code"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:alert-circle-outline"

    elif 196 <= capabilityId <= 209:
        # Weekly program: two blocks of seven capabilities, monday first. On an
        # air conditioner the second block is the cooling program rather than a
        # second zone -- the app calls them "Chauffage" and "Refroidissement".
        index = capabilityId - 196
        if modelInfos["type"] == CozytouchDeviceType.AC:
            block = "heating" if index < 7 else "cooling"
            capability["name"] = f"prog_{block}_{PROG_DAYS[index % 7]}"
        else:
            capability["name"] = f"prog_{index + 1:02d}_z{1 if index < 7 else 2}"

        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 218:
        capability["name"] = "wifi_connected"
        capability["type"] = "binary"
        capability["category"] = "diag"
        capability["icon"] = "mdi:wifi"

    elif capabilityId == 219:
        capability["name"] = "wifi_ssid"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:wifi"

    elif capabilityId in (222, 226):
        capability["name"] = "away_mode"
        capability["name_0"] = "away_mode_start"
        capability["name_1"] = "away_mode_stop"
        capability["type"] = "away_mode_timestamps"
        capability["category"] = "sensor"
        capability["icon_0"] = "mdi:airplane-takeoff"
        capability["icon_1"] = "mdi:airplane-landing"
        capability["timezoneCapabilityId"] = 315
        if capabilityId == 222:
            capability["capabilityDuplicate"] = 226
        else:
            capability["capabilityDuplicate"] = 222

    elif capabilityId == 228:
        capability["name"] = "absence_dhw_temperature"
        capability["type"] = "temperature"
        capability["category"] = "diag"

    elif capabilityId == 231:
        capability["name"] = "target_temperature"
        capability["type"] = "temperature_adjustment_number"
        capability["category"] = "sensor"
        if modelId == 2374:
            capability["lowestValueCapabilityId"] = 253
            capability["highestValueCapabilityId"] = 252
            capability["step"] = 1
        else:
            capability["lowestValueCapabilityId"] = 105301
            capability["highestValueCapabilityId"] = 105304

    elif capabilityId == 232:
        capability["name"] = "boost_total_time"
        capability["type"] = "time"
        capability["category"] = "diag"
        capability["icon"] = "mdi:clock-outline"

    elif capabilityId == 233:
        capability["name"] = "boost_remaining_time"
        capability["type"] = "time"
        capability["category"] = "diag"
        capability["icon"] = "mdi:clock-outline"

    elif capabilityId == 245:
        capability["name"] = "prog_01"
        capability["type"] = "progtime"
        capability["category"] = "diag"

    elif capabilityId == 246:
        capability["name"] = "prog_02"
        capability["type"] = "progtime"
        capability["category"] = "diag"

    elif capabilityId == 247:
        capability["name"] = "prog_03"
        capability["type"] = "progtime"
        capability["category"] = "diag"

    elif capabilityId == 248:
        capability["name"] = "prog_04"
        capability["type"] = "progtime"
        capability["category"] = "diag"

    elif capabilityId == 249:
        capability["name"] = "prog_05"
        capability["type"] = "progtime"
        capability["category"] = "diag"

    elif capabilityId == 250:
        capability["name"] = "prog_06"
        capability["type"] = "progtime"
        capability["category"] = "diag"

    elif capabilityId == 251:
        capability["name"] = "prog_07"
        capability["type"] = "progtime"
        capability["category"] = "diag"

    elif capabilityId == 252:
        capability["name"] = "target_temperature_max"
        capability["type"] = "temperature"
        capability["category"] = "diag"

    elif capabilityId == 253:
        capability["name"] = "target_temperature_min"
        capability["type"] = "temperature"
        capability["category"] = "diag"

    elif capabilityId == 258:
        capability["name"] = "tank_capacity"
        capability["type"] = "volume"
        capability["category"] = "sensor"

    elif capabilityId == 264:
        capability["name"] = "condenser_temperature"
        capability["type"] = "temperature"
        capability["category"] = "sensor"

    elif capabilityId == 265:
        capability["name"] = "tank_middle_temperature"
        capability["type"] = "temperature"
        capability["category"] = "sensor"

    elif capabilityId == 266:
        capability["name"] = "tank_top_temperature"
        capability["type"] = "temperature"
        capability["category"] = "sensor"

    elif capabilityId == 267:
        capability["name"] = "tank_bottom_temperature"
        capability["type"] = "temperature"
        capability["category"] = "sensor"

    elif capabilityId == 268:
        capability["name"] = "v40_water_available"
        capability["type"] = "volume"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:water-thermometer"

    elif capabilityId == 269:
        capability["name"] = "water_consumption"
        capability["type"] = "water_consumption"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:water-pump"

    elif capabilityId == 270:
        capability["name"] = "v40_water_capacity"
        capability["type"] = "volume"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:water-thermometer"

    elif capabilityId == 271:
        capability["name"] = "hot_water_available"
        capability["type"] = "percentage"
        capability["category"] = "sensor"

    elif capabilityId == 280:
        capability["name"] = "cold_water_temperature"
        capability["type"] = "temperature"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:coolant-temperature"

    elif capabilityId == 283:
        capability["name"] = "off_peak_hours"
        capability["type"] = "binary"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:clock-outline"

    elif capabilityId == 292:
        # Not a level: the app counts showers. Atlantic water heaters display a
        # number of expected/remaining showers rather than a percentage.
        capability["name"] = "hot_water_showers_expected"
        capability["type"] = "int"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:water-plus"

    elif capabilityId == 293:
        # Remaining showers, the counterpart of 292 -- see the note there.
        capability["name"] = "hot_water_showers_remaining"
        capability["type"] = "int"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:water-check"

    elif capabilityId == 315:
        capability["name"] = "timezone"
        capability["type"] = "timezone"
        capability["category"] = "diag"
        capability["icon"] = "mdi:map-clock-outline"

    elif capabilityId == 316:
        capability["name"] = "interface_fw"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:tag"

    elif capabilityId == 335:
        capability["name"] = "serial_number"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:tag"

    elif capabilityId == 100261:
        # Per-room mirror of the hub's away mode flag (152). The room units carry
        # it alongside the absence window in 100260, which stays unmapped: the
        # window is written for the whole setup from the hub, not room by room.
        capability["name"] = "away_mode"
        capability["type"] = "binary"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:airplane"

    elif capabilityId == 100402:
        capability["name"] = "number_of_hours_burner"
        capability["type"] = "int"
        capability["category"] = "diag"
        capability["icon"] = "mdi:fire"

    elif capabilityId == 100406:
        capability["name"] = "number_of_starts_burner"
        capability["type"] = "int"
        capability["category"] = "diag"
        capability["icon"] = "mdi:fire"

    elif capabilityId == 100505:
        capability["name"] = "powerful_mode"
        capability["type"] = "switch"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:wind-power"

    elif capabilityId == 100506:
        if modelInfos["type"] == CozytouchDeviceType.TOWEL_RACK:
            capability = {}
        else:
            capability["name"] = "presence_mode"
            capability["type"] = "switch"
            capability["category"] = "sensor"
            capability["icon"] = "mdi:account"

    elif capabilityId == 100507:
        # Same story as the absence setpoint in 172: the air conditioners report
        # eco mode without the Cozytouch app ever offering it. Reported is not
        # supported, so let the model table decide.
        if not modelInfos.get("ecoModeAvailable", True):
            return {}

        capability["name"] = "eco_mode"
        capability["type"] = "switch"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:flower-outline"

    elif capabilityId == 100320:
        capability["name"] = "prog_heat_monday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100321:
        capability["name"] = "prog_heat_tuesday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100322:
        capability["name"] = "prog_heat_wednesday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100323:
        capability["name"] = "prog_heat_thursday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100324:
        capability["name"] = "prog_heat_friday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100325:
        capability["name"] = "prog_heat_saturday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100326:
        capability["name"] = "prog_heat_sunday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100327:
        capability["name"] = "prog_cool_monday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100328:
        capability["name"] = "prog_cool_tuesday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100329:
        capability["name"] = "prog_cool_wednesday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100330:
        capability["name"] = "prog_cool_thursday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100331:
        capability["name"] = "prog_cool_friday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100332:
        capability["name"] = "prog_cool_saturday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100333:
        capability["name"] = "prog_cool_sunday"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 100802:
        capability["name"] = "quiet_mode"
        capability["type"] = "switch"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:fan-minus"

    elif capabilityId == 100804:
        capability["name"] = "swing_mode"
        capability["type"] = "switch"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:arrow-oscillating"

    elif capabilityId == 102004:
        capability["name"] = "air_circulation_speed"
        capability["type"] = "select"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:fan"
        capability["modelList"] = "AirCirculationSpeeds"

    elif capabilityId == 102021:
        # Air circulation runs for a set number of minutes. Its bounds and step
        # are reported alongside: 102025 the minimum (15), 102026 the maximum
        # (300), 102022 the step -- exposed as their own diag entities below.
        capability["name"] = "air_circulation_total_time"
        capability["type"] = "minutes_adjustment_number"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:fan-clock"
        capability["lowest_value"] = 15
        capability["highest_value"] = 300

    elif capabilityId == 102023:
        capability["name"] = "air_circulation_remaining_time"
        capability["type"] = "time"
        capability["category"] = "diag"
        capability["icon"] = "mdi:fan-clock"

    elif capabilityId == 102024:
        capability["name"] = "air_circulation"
        capability["type"] = "switch"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:fan"

    elif capabilityId == 150:
        # Home-level fault code, sibling of the room (303) and DHW (290) codes.
        capability["name"] = "home_error_code"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:alert-circle-outline"

    elif 237 <= capabilityId <= 243:
        # Domestic-hot-water weekly program, one capability per day, monday first.
        capability["name"] = f"dhw_prog_{PROG_DAYS[capabilityId - 237]}"
        capability["type"] = "prog"
        capability["category"] = "diag"

    elif capabilityId == 290:
        # DHW fault code, same raw matrix shape as the room error code (303).
        capability["name"] = "dhw_error_code"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:alert-circle-outline"

    elif capabilityId == 102005:
        # The set of air-circulation modes this device supports.
        capability["name"] = "air_circulation_supported_modes"
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["icon"] = "mdi:fan"

    elif capabilityId == 102022:
        # Step for the air-circulation duration (102021).
        capability["name"] = "air_circulation_time_step"
        capability["type"] = "int"
        capability["category"] = "diag"
        capability["icon"] = "mdi:fan-clock"

    elif capabilityId == 102025:
        # Minimum air-circulation duration; the lower bound of 102021.
        capability["name"] = "air_circulation_time_min"
        capability["type"] = "int"
        capability["category"] = "diag"
        capability["icon"] = "mdi:fan-clock"

    elif capabilityId == 102026:
        # Maximum air-circulation duration; the upper bound of 102021.
        capability["name"] = "air_circulation_time_max"
        capability["type"] = "int"
        capability["category"] = "diag"
        capability["icon"] = "mdi:fan-clock"

    elif capabilityId == 104044:
        capability["name"] = "boost_mode"
        capability["type"] = "switch"
        capability["category"] = "sensor"
        capability["icon"] = "mdi:heat-wave"

    elif capabilityId == 104047:
        # Boost timeout max. in minutes
        capability["name"] = "boost_timeout_max"
        capability["type"] = "minutes_adjustment_number"
        capability["category"] = "diag"
        capability["icon"] = "mdi:clock-outline"
        capability["lowest_value"] = 5
        capability["highest_value"] = 60
        capability["step"] = 5

    elif capabilityId == 105300:
        capability["name"] = "water_temperature_limit"
        capability["type"] = "temperature"
        capability["category"] = "diag"

    elif capabilityId == 105304:
        capability["name"] = "max_target_temperature_derogation"
        capability["type"] = "temperature"
        capability["category"] = "diag"

    elif capabilityId == 105906:
        capability["name"] = "Target 105906"
        capability["type"] = "temperature_percent_adjustment_number"
        capability["category"] = "sensor"
        capability["temperatureMin"] = 15.0
        capability["temperatureMax"] = 65.0

    elif capabilityId == 105907:
        capability["name"] = "Target 105907"
        capability["type"] = "temperature_percent_adjustment_number"
        capability["category"] = "sensor"
        capability["temperatureMin"] = 15.0
        capability["temperatureMax"] = 65.0

    # For test
    elif capabilityId == 312:
        capability["name"] = "Temp_" + str(capabilityId)
        capability["type"] = "temperature_adjustment_number"
        capability["category"] = "sensor"

    elif capabilityId in SELF_DESCRIBING_CAPABILITIES:
        capability["name"] = SELF_DESCRIBING_CAPABILITIES[capabilityId]
        capability["type"] = "string"
        capability["category"] = "diag"
        capability["enabled_by_default"] = False

    else:
        return None

    return capability
