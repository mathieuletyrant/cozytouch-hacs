"""What the capabilities alone would say a device is.

`get_model_infos` answers from a hand-built table keyed on model id. The
vendor's own app carries no such table: it derives every feature from what
the device reports -- a panel exists when its capability is present, the mode
lists come from bitmask capabilities, and the value/label pairs are global
vocabularies shared by every model. This module is that derivation, written
against our vocabulary, with the evidence and its open unknowns recorded in
docs/decisions.md.

Nothing wires entities from it. Its one consumer is the diagnostics dump,
which prints it next to the declared table so that every report measures the
two against each other -- including the models nobody here owns. A
disagreement is a finding, not a defect: the table carries deliberate
suppressions (a capability the hardware reports and the vendor app still
refuses to offer), and those are exactly what a switch-over would have to
keep as overrides.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACMode,
)

from .const import (
    SWING_MODE_DOWN,
    SWING_MODE_MIDDLE_DOWN,
    SWING_MODE_MIDDLE_UP,
    SWING_MODE_UP,
)
from .infos import ModelInfos
from .model import CozytouchDeviceType

# Capability 100022 is a bitmask over the same value space as the HVACModes
# tables in model.py; the bits with no known value are reported, never mapped.
# Evidence in docs/decisions.md.
HVAC_MODE_BITS: dict[int, HVACMode] = {
    0: HVACMode.OFF,
    1: HVACMode.AUTO,
    3: HVACMode.COOL,
    4: HVACMode.HEAT,
    7: HVACMode.FAN_ONLY,
    8: HVACMode.DRY,
}

# The value/label pairs are the vendor's global vocabularies, not per-model
# data; 4 is the quiet speed, carried by 100802 instead. docs/decisions.md.
FAN_MODES: dict[int, str] = {
    1: FAN_LOW,
    2: FAN_MEDIUM,
    3: FAN_HIGH,
    5: FAN_AUTO,
}

SWING_MODES: dict[int, str] = {
    1: SWING_MODE_UP,
    2: SWING_MODE_MIDDLE_UP,
    3: SWING_MODE_MIDDLE_DOWN,
    4: SWING_MODE_DOWN,
}

# `modelFamily` is the API's own taxonomy for the field, complete at 13
# values; only the ones this integration has a type for claim one. The field
# is null on everything behind a hub, so a child inherits its master's.
FAMILY_TO_TYPE: dict[str, CozytouchDeviceType] = {
    "Air_Conditioning": CozytouchDeviceType.AC,
    "Boiler": CozytouchDeviceType.GAZ_BOILER,
    "Connectivity_Box": CozytouchDeviceType.HUB,
    "Heat_Pump": CozytouchDeviceType.HEAT_PUMP,
    "Hybrid_Heat_Pump": CozytouchDeviceType.HEAT_PUMP,
    "Thermodynamic_Water_Heater": CozytouchDeviceType.WATER_HEATER,
    "Thermostat": CozytouchDeviceType.THERMOSTAT,
    "Towel_Dryer": CozytouchDeviceType.TOWEL_RACK,
    "Water_Heater": CozytouchDeviceType.WATER_HEATER,
}


def derive_model_infos(
    device: dict[str, Any],
    masterFamily: str | None = None,
    isMaster: bool = False,
) -> dict[str, Any]:
    """Derive a model description from one device's own report.

    Answers only what the capabilities can answer: a key is absent when the
    device gives nothing to derive it from, never defaulted. The flags are
    plain presence; the mode lists are the global vocabularies filtered by
    what the device carries.
    """
    capabilities = {
        cap["capabilityId"]: cap.get("value")
        for cap in device.get("capabilities", [])
    }

    derived: dict[str, Any] = {}

    # 154 is the room name the user typed in the vendor app; `customName` is
    # the device-level equivalent. The commercial name is *not* derivable:
    # `longName` reads ROOM_n on everything behind a hub.
    name = capabilities.get(154) or device.get("customName") or device.get("name")
    if name:
        derived["name"] = name

    family = device.get("modelFamily") or masterFamily
    if family:
        derived["modelFamily"] = family

    # The family names the product line, not the node's role in it: the hub of
    # an installation carries the same family as the units behind it. Being
    # somebody's master is what tells them apart.
    if isMaster:
        derived["type"] = str(CozytouchDeviceType.HUB)
    elif family in FAMILY_TO_TYPE:
        derived["type"] = str(FAMILY_TO_TYPE[family])

    if 100022 in capabilities:
        try:
            mask = int(capabilities[100022])
        except (TypeError, ValueError):
            derived["HVACModesRaw"] = capabilities[100022]
        else:
            modes: dict[int, str] = {}
            unknown: list[int] = []
            for bit in range(mask.bit_length()):
                if not mask & (1 << bit):
                    continue
                if bit in HVAC_MODE_BITS:
                    modes[bit] = str(HVAC_MODE_BITS[bit])
                else:
                    unknown.append(bit)
            derived["HVACModes"] = modes
            if unknown:
                derived["HVACModesUnknownBits"] = unknown

    if 100801 in capabilities:
        derived["fanModes"] = dict(FAN_MODES)
    if 100803 in capabilities:
        derived["swingModes"] = dict(SWING_MODES)

    derived["quietModeAvailable"] = 100802 in capabilities
    derived["ecoModeAvailable"] = 100507 in capabilities
    derived["awayModeTemperatureAvailable"] = (
        172 in capabilities or 171 in capabilities
    )

    # 103150 is the API's own availability flag for the ambient temperature;
    # presence of the temperature itself is the fallback.
    if 103150 in capabilities:
        derived["currentTemperatureAvailable"] = capabilities[103150] == "1"
    else:
        derived["currentTemperatureAvailable"] = 117 in capabilities

    return derived


def declared_vs_derived(
    declared: ModelInfos,
    derived: dict[str, Any],
    capabilityIds: set[int],
) -> dict[str, Any]:
    """Where the two descriptions would wire different entities.

    The comparison is between behaviours, not fields: a declared flag only
    ever acts on a capability the device reports, so it is compared after
    that gate -- the same `flag and presence` the wiring applies. A flag
    that is False against an absent capability is agreement, not a finding.
    """
    diff: dict[str, Any] = {}

    def compare(field: str, declaredValue: Any, derivedValue: Any) -> None:
        if declaredValue != derivedValue:
            diff[field] = {"declared": declaredValue, "derived": derivedValue}

    if "type" in derived:
        compare("type", str(declared.type), derived["type"])

    if "HVACModes" in derived:
        compare(
            "HVACModes",
            {value: str(mode) for value, mode in declared.get("HVACModes", {}).items()},
            derived["HVACModes"],
        )

    compare(
        "fanModes",
        "fanModes" in declared and 100801 in capabilityIds,
        "fanModes" in derived,
    )
    compare(
        "swingModes",
        "swingModes" in declared and 100803 in capabilityIds,
        "swingModes" in derived,
    )

    # Same defaults as the wiring in capability.py reads them with.
    compare(
        "quietModeAvailable",
        declared.get("quietModeAvailable", False) and 100802 in capabilityIds,
        derived["quietModeAvailable"],
    )
    compare(
        "ecoModeAvailable",
        declared.get("ecoModeAvailable", True) and 100507 in capabilityIds,
        derived["ecoModeAvailable"],
    )
    compare(
        "awayModeTemperatureAvailable",
        declared.get("awayModeTemperatureAvailable", True)
        and (172 in capabilityIds or 171 in capabilityIds),
        derived["awayModeTemperatureAvailable"],
    )
    compare(
        "currentTemperatureAvailable",
        declared.get("currentTemperatureAvailable", True) and 117 in capabilityIds,
        derived["currentTemperatureAvailable"],
    )

    return diff
