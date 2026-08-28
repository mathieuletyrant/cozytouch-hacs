"""Tests for the capability-only derivation the diagnostics dump shadows.

These pin the derivation against the two real signatures it was written
from: the Navizone room units of one account (capability 100022 = 285, no
fan or swing capabilities) and the same model ids on other accounts of the
upstream tracker (100022 = 411, the full climate panel). What matters here
is honesty at the edges — an unknown bit is reported and never guessed, a
missing family claims no type — because nothing checks the derivation in
the field except the dumps these shapes end up in.

The diff half is compared behaviour to behaviour: a declared flag only ever
acts on a capability the device reports, so the tests feed real capability
sets and expect the diff to stay silent when both sides would wire the same
entities, whichever words they use for it.
"""

from custom_components.cozytouch.derive import declared_vs_derived, derive_model_infos
from custom_components.cozytouch.model import get_model_infos
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
)


def device(capabilityIds, modelFamily=None, customName=None, values=None):
    """A device dict shaped like one entry of the setup view's list."""
    values = values or {}
    return {
        "deviceId": 1,
        "name": "ROOM_0",
        "customName": customName,
        "modelId": 557,
        "modelFamily": modelFamily,
        "capabilities": [
            {"capabilityId": capabilityId, "value": values.get(capabilityId, "0")}
            for capabilityId in capabilityIds
        ],
    }


# What one Navizone room unit actually reports (capture of 2026-08-28),
# reduced to the ids the derivation reads.
NAVIZONE_ROOM = device(
    [40, 117, 154, 171, 172, 177, 100022, 100507, 103150],
    values={154: "Chambre parentale", 100022: "285", 103150: "1"},
)


def test_a_room_unit_behind_a_hub_derives_without_any_table_entry():
    derived = derive_model_infos(NAVIZONE_ROOM, masterFamily="Air_Conditioning")

    assert derived["name"] == "Chambre parentale"
    assert derived["modelFamily"] == "Air_Conditioning"
    assert derived["type"] == "ac"
    assert derived["HVACModes"] == {0: "off", 3: "cool", 4: "heat", 8: "dry"}
    assert derived["ecoModeAvailable"] is True
    assert derived["awayModeTemperatureAvailable"] is True
    assert derived["currentTemperatureAvailable"] is True
    assert derived["quietModeAvailable"] is False
    assert "fanModes" not in derived
    assert "swingModes" not in derived


def test_a_mask_bit_nothing_names_is_reported_and_never_guessed():
    """285 carries bit 2, which no capture has named. A guess would wire a
    mode the hardware may not have; the dump carries the bit instead, which
    is what will eventually name it.
    """
    derived = derive_model_infos(NAVIZONE_ROOM)

    assert derived["HVACModesUnknownBits"] == [2]


def test_the_full_mask_reads_back_the_declared_table():
    """100022 = 411 is what the tracker's captures of the same model ids
    report, and it decodes to the exact HVACModes table model.py declares
    for them -- the observation the decoding was built on.
    """
    dev = device([100022], values={100022: "411"})

    derived = derive_model_infos(dev)

    assert derived["HVACModes"] == {
        value: str(mode)
        for value, mode in get_model_infos(557).HVACModes.items()
    }
    assert "HVACModesUnknownBits" not in derived


def test_the_mode_pairs_are_the_global_vocabulary_not_model_data():
    dev = device([100801, 100802, 100803])

    derived = derive_model_infos(dev)

    assert derived["fanModes"] == {1: FAN_LOW, 2: FAN_MEDIUM, 3: FAN_HIGH, 5: FAN_AUTO}
    assert derived["swingModes"] == {
        1: "up",
        2: "middle_up",
        3: "middle_down",
        4: "down",
    }
    assert derived["quietModeAvailable"] is True


def test_a_master_is_a_hub_whatever_its_family_says():
    """The family names the product line, so the hub of an air-conditioning
    installation carries Air_Conditioning like the units behind it. Being
    named masterDeviceId by anything is what tells the head apart.
    """
    dev = device([], modelFamily="Air_Conditioning", customName="HUB SHOGUN")

    derived = derive_model_infos(dev, isMaster=True)

    assert derived["type"] == "hub"
    assert derived["name"] == "HUB SHOGUN"


def test_a_family_the_integration_has_no_type_for_claims_none():
    derived = derive_model_infos(device([], modelFamily="Radiator"))

    assert derived["modelFamily"] == "Radiator"
    assert "type" not in derived


def test_a_device_reporting_nothing_derives_nothing_but_the_flags():
    """The THZONE case: two capabilities, no climate signature. Every
    positive key is absent rather than defaulted -- absence is the honest
    answer -- and the flags read False, which wires nothing.
    """
    derived = derive_model_infos({"deviceId": 1, "capabilities": []})

    assert "name" not in derived
    assert "type" not in derived
    assert "HVACModes" not in derived
    assert derived["currentTemperatureAvailable"] is False


def test_a_malformed_mask_is_carried_raw_rather_than_dropped():
    dev = device([100022], values={100022: "[1,2]"})

    derived = derive_model_infos(dev)

    assert "HVACModes" not in derived
    assert derived["HVACModesRaw"] == "[1,2]"


def test_the_api_availability_flag_wins_over_a_present_temperature():
    """103150 is the API's own currentTemperatureAvailable; when it says no,
    a reported 117 is not a reading anybody should see.
    """
    dev = device([117, 103150], values={103150: "0"})

    assert derive_model_infos(dev)["currentTemperatureAvailable"] is False


def test_the_diff_shows_the_deliberate_suppressions_as_findings():
    """model.py switches eco and the absence setpoint off for 557-561 on
    purpose -- the vendor app offers neither -- while the hardware reports
    100507 and 172. Those are exactly the disagreements the shadow exists to
    put in front of a reader, so they are pinned as present.
    """
    declared = get_model_infos(557)
    derived = derive_model_infos(NAVIZONE_ROOM, masterFamily="Air_Conditioning")
    capabilityIds = {
        cap["capabilityId"] for cap in NAVIZONE_ROOM["capabilities"]
    }

    diff = declared_vs_derived(declared, derived, capabilityIds)

    assert diff["ecoModeAvailable"] == {"declared": False, "derived": True}
    assert diff["awayModeTemperatureAvailable"] == {
        "declared": False,
        "derived": True,
    }
    # 285 against the declared six-mode table: no auto, no fan_only.
    assert diff["HVACModes"]["declared"] != diff["HVACModes"]["derived"]


def test_the_diff_is_silent_where_both_sides_wire_the_same_entities():
    """557 declares fanModes and quietModeAvailable, but against a device
    reporting neither 100801 nor 100802 the wiring builds neither -- and the
    derivation says the same thing. A flag compared before its presence gate
    would flood every dump with disagreements that change nothing.
    """
    declared = get_model_infos(557)
    derived = derive_model_infos(NAVIZONE_ROOM, masterFamily="Air_Conditioning")
    capabilityIds = {
        cap["capabilityId"] for cap in NAVIZONE_ROOM["capabilities"]
    }

    diff = declared_vs_derived(declared, derived, capabilityIds)

    assert "fanModes" not in diff
    assert "swingModes" not in diff
    assert "quietModeAvailable" not in diff
    assert "type" not in diff
    assert "currentTemperatureAvailable" not in diff


def test_the_diff_reads_the_declared_flags_with_the_wiring_defaults():
    """An unmapped model declares no flags at all; the diff has to read the
    absent ones exactly as capability.py would -- eco and away default on --
    or the shadow would report a different integration than the one running.
    """
    declared = get_model_infos(9999)
    dev = device([100507, 172])
    derived = derive_model_infos(dev)

    diff = declared_vs_derived(
        declared, derived, {cap["capabilityId"] for cap in dev["capabilities"]}
    )

    assert "ecoModeAvailable" not in diff
    assert "awayModeTemperatureAvailable" not in diff
