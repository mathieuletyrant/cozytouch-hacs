"""Tests for the diagnostics dump.

The dump exists so someone with unmapped hardware can hand over what the API
says about it without editing a JSON by hand. Two things have to hold for that
to be worth anything: an unmapped model has to be visible as unmapped, and the
capability ids nothing names have to be listed rather than silently dropped.
Those are what a maintainer reads first, and they are what these tests pin.

Hub.get_diagnostics is called unbound, against a stand-in carrying only the
attributes it touches -- an account holding the devices, and the id of the one
this entry drives. Building a real Hub means a DataUpdateCoordinator and a
running HomeAssistant, none of which the method uses.
"""

from types import SimpleNamespace

import pytest

from custom_components.cozytouch.account import CozytouchAccount
from custom_components.cozytouch.hub import Hub


def make_hub(devices, deviceId, zones=None):
    """A stand-in exposing only what get_diagnostics reads."""
    account = SimpleNamespace(
        devices=devices,
        setup={"id": 1532156, "name": "setup1"},
        zones=zones if zones is not None else [],
    )
    hub = SimpleNamespace(
        _account=account,
        _deviceId=deviceId,
        # the devices somebody added, which is what isConfiguredHere reports
        _entry=SimpleNamespace(
            subentries={
                f"sub-{deviceId}": SimpleNamespace(data={"deviceId": deviceId})
            }
        ),
    )
    hub.get_zone_name = lambda zoneId=None: next(
        (z["name"] for z in account.zones if z.get("id") == zoneId), str(zoneId)
    )
    # get_diagnostics reads the named/unnamed split off the hub rather than
    # working it out again, so the stand-in has to carry the real one.
    hub.get_capability_names = lambda deviceId=None: Hub.get_capability_names(
        hub, deviceId
    )
    return hub


def test_a_zone_is_not_in_the_dump_at_all():
    """A dump is read to find hardware that has to be mapped, and a zone is not
    hardware: it reports two ids that resolve to nothing, one of them declined
    on purpose, which reads exactly like work to do. It is ignored outright --
    not offered at setup, not listed here.
    """
    hub = make_hub(
        [
            device(1, 557, name="ROOM_0"),
            device(2, 1505, name="THZONE_0"),
        ],
        deviceId=1,
    )

    reported = Hub.get_diagnostics(hub)

    assert [dev["name"] for dev in reported["devices"]] == ["ROOM_0"]


def test_a_zone_is_not_offered_when_adding_the_integration():
    """Adding it would create a device with an empty page behind it. The list
    the config flow reads is the account's, which is where the filter lives.
    """
    account = SimpleNamespace(
        devices=[
            device(1, 557, name="ROOM_0"),
            device(2, 1505, name="THZONE_0"),
        ]
    )

    summaries = CozytouchAccount.device_summaries(account)

    assert [dev["name"] for dev in summaries] == ["ROOM_0"]


def device(deviceId, modelId, capabilities=None, name="ROOM_0", zoneId=991904):
    return {
        "deviceId": deviceId,
        "name": name,
        "modelId": modelId,
        "productId": 65,
        "zoneId": zoneId,
        "gatewaySerialNumber": "3022-6760-8541",
        "tags": [],
        "capabilities": capabilities or [],
    }


def test_an_unmapped_model_is_reported_as_unmapped():
    """The whole point of a dump is to name what the table does not."""
    hub = make_hub([device(1, 9999)], deviceId=1)

    reported = Hub.get_diagnostics(hub)["devices"][0]

    assert reported["modelId"] == 9999
    assert reported["model"]["isMapped"] is False
    assert reported["model"]["name"] == "Unknown product (9999)"


def test_a_mapped_model_carries_its_name_and_type():
    hub = make_hub([device(1, 557)], deviceId=1)

    reported = Hub.get_diagnostics(hub)["devices"][0]

    assert reported["model"]["isMapped"] is True
    assert reported["model"]["name"] == "Air Conditioner (#1)"
    assert reported["model"]["type"] == "ac"


def test_capabilities_split_into_what_is_named_and_what_is_not():
    """303 is mapped, 100044 is not; a report needs to show both."""
    hub = make_hub(
        [
            device(
                1,
                557,
                capabilities=[
                    {"capabilityId": 303, "value": "0"},
                    {"capabilityId": 100044, "value": "[72,88]"},
                ],
            )
        ],
        deviceId=1,
    )

    caps = Hub.get_diagnostics(hub)["devices"][0]["capabilities"]

    assert caps["mapped"][303] == "error_code"
    assert caps["unmapped"] == [100044]
    assert caps["values"][100044] == "[72,88]"


def test_devices_this_entry_does_not_drive_are_still_described():
    """The account holds every device the setup view returned, capabilities
    included, so a dump covers hardware nobody has added yet.

    That is the point of the dump: the capability ids of an unmapped model are
    what a mapping gets written from, and asking somebody to add the device as
    an entry first only to read them was a step that lost reports. What
    `isConfiguredHere` still says is which one this entry drives, and so which
    list came from a live poll rather than from the last setup view.
    """
    hub = make_hub(
        [
            device(1, 557, capabilities=[{"capabilityId": 303, "value": "0"}]),
            device(
                2, 1457, name="HUB",
                capabilities=[{"capabilityId": 100, "value": "1"}],
            ),
        ],
        deviceId=1,
    )

    driven, other = Hub.get_diagnostics(hub)["devices"]

    assert driven["isConfiguredHere"] is True
    assert driven["capabilities"]["values"] == {303: "0"}
    assert other["isConfiguredHere"] is False
    assert other["capabilities"]["values"] == {100: "1"}


def test_the_zone_name_is_resolved_rather_than_left_as_an_id():
    hub = make_hub(
        [device(1, 557, zoneId=991904)],
        deviceId=1,
        zones=[{"id": 991904, "name": "Chambre 2"}],
    )

    assert Hub.get_diagnostics(hub)["devices"][0]["zoneName"] == "Chambre 2"


def test_model_flags_are_reported_so_a_report_shows_what_was_wired():
    """Which optional features a model declares decides its entity list."""
    hub = make_hub([device(1, 557)], deviceId=1)

    infos = Hub.get_diagnostics(hub)["devices"][0]["model"]["infos"]

    assert infos["ecoModeAvailable"] == "False"
    assert infos["quietModeAvailable"] == "True"
    assert "name" not in infos
    assert "type" not in infos


def test_what_the_api_itself_calls_the_device_is_carried_through():
    """A dump is what an unmapped model gets mapped from, so the vendor's own
    name and family for it are worth more than the ones our table invented.
    """
    hub = make_hub(
        [
            device(1, 9999)
            | {
                "longName": "HUB Navizone",
                "modelFamily": "Air_Conditioning",
                "productRange": None,
                "masterDeviceId": None,
                "isAvailable": True,
            }
        ],
        deviceId=1,
    )

    reported = Hub.get_diagnostics(hub)["devices"][0]

    assert reported["longName"] == "HUB Navizone"
    assert reported["modelFamily"] == "Air_Conditioning"
    assert reported["isAvailable"] is True


def test_fields_the_api_leaves_out_read_as_none_rather_than_failing():
    """Only the gateway carried a modelFamily on the account these were read
    from; a room unit reports null, and a dump has to survive that.
    """
    hub = make_hub([device(1, 557)], deviceId=1)

    reported = Hub.get_diagnostics(hub)["devices"][0]

    assert reported["modelFamily"] is None
    assert reported["masterDeviceId"] is None


@pytest.mark.parametrize("key", ["setup", "zones", "devices"])
def test_the_dump_carries_the_sections_a_report_is_built_from(key):
    hub = make_hub([device(1, 557)], deviceId=1)

    assert key in Hub.get_diagnostics(hub)
