"""Tests for the gateway link the API declares and the integration draws.

Every room unit and thermal zone on an account carries its gateway's id in
masterDeviceId, so the parent/child shape is not inferred -- it is reported.
What has to be got right is the other half: this integration registers one
device per config entry, so the gateway exists in Home Assistant only if
somebody set it up as an entry of its own. Claiming a link to a device that is
not there earns a warning from the device registry, which is what these pin.

Hub.get_via_device is called unbound against a stand-in, the way the
diagnostics tests do -- it reads three attributes and none of them need a
coordinator.
"""

from types import SimpleNamespace

from custom_components.cozytouch.const import DOMAIN
from custom_components.cozytouch.hub import Hub
from custom_components.cozytouch.model import CozytouchDeviceType

GATEWAY_ID = 27906640
ROOM_ID = 27906641


def make_hub(devices, deviceId, entries=()):
    """A stand-in exposing only what get_via_device reads."""
    return SimpleNamespace(
        _devices=devices,
        _deviceId=deviceId,
        _hass=SimpleNamespace(
            config_entries=SimpleNamespace(async_entries=lambda domain: list(entries))
        ),
    )


def entry(deviceId, entry_id):
    return SimpleNamespace(data={"deviceId": deviceId}, entry_id=entry_id)


def device(deviceId, masterDeviceId):
    return {"deviceId": deviceId, "masterDeviceId": masterDeviceId}


def test_a_room_unit_points_at_the_entry_its_gateway_was_set_up_under():
    """The link is to the gateway's config entry, not its Cozytouch id: that
    is the identifier every device in this integration is registered under.
    """
    hub = make_hub(
        [device(ROOM_ID, GATEWAY_ID), device(GATEWAY_ID, None)],
        deviceId=ROOM_ID,
        entries=[entry(GATEWAY_ID, "abc123"), entry(ROOM_ID, "def456")],
    )

    assert Hub.get_via_device(hub) == (DOMAIN, "abc123")


def test_no_link_is_claimed_when_the_gateway_was_never_set_up():
    """Somebody can add one room unit and nothing else. The parent device does
    not exist then, and naming it anyway makes the registry complain.
    """
    hub = make_hub(
        [device(ROOM_ID, GATEWAY_ID)],
        deviceId=ROOM_ID,
        entries=[entry(ROOM_ID, "def456")],
    )

    assert Hub.get_via_device(hub) is None


def test_a_gateway_has_no_parent_of_its_own():
    hub = make_hub(
        [device(GATEWAY_ID, None)],
        deviceId=GATEWAY_ID,
        entries=[entry(GATEWAY_ID, "abc123")],
    )

    assert Hub.get_via_device(hub) is None


def test_a_device_from_before_the_field_was_carried_reports_no_parent():
    """A stored device dict predating masterDeviceId has no such key, and a
    reload must not raise on the way to rebuilding it.
    """
    hub = make_hub(
        [{"deviceId": ROOM_ID}],
        deviceId=ROOM_ID,
        entries=[entry(GATEWAY_ID, "abc123")],
    )

    assert Hub.get_via_device(hub) is None


def test_an_unknown_device_id_is_not_linked_to_anything():
    hub = make_hub([device(ROOM_ID, GATEWAY_ID)], deviceId=999999)

    assert Hub.get_via_device(hub) is None


# --- the zone half of the same payload -------------------------------------


def zone_hub():
    """A hub over the two halves of one capture.

    The device is the THZONE the API reports at deviceId 27906644 with
    `zoneId: 1030104`; the setup view's `zones` array is what turns that id into
    a room. Both come from the same install, ids and names included, so this is
    the wiring as it really arrives rather than a shape invented for a test.
    """
    hub = object.__new__(Hub)
    hub._deviceId = 27906644
    hub._zoneId = 1030104
    hub._devices = [
        {
            "deviceId": 27906644,
            "modelId": 1505,
            "name": "THZONE_0",
            "zoneId": 1030104,
            "masterDeviceId": GATEWAY_ID,
        }
    ]
    hub._zones = [
        {"id": 1030103, "name": "Zone 1", "zoneType": 29, "numberOfDevices": 1},
        {
            "id": 1030104,
            "name": "Chambre parentale",
            "zoneType": 1,
            "numberOfDevices": 2,
        },
    ]

    return hub


def test_a_zone_is_named_after_the_room_the_account_calls_it():
    """`zoneId` is the join between the device and the room, and it is the
    difference between a device called THZONE_0 and one called after the
    bedroom it heats.
    """
    infos = Hub.get_model_infos(zone_hub())

    assert infos["name"] == "Zone (Chambre parentale)"
    assert infos["type"] is CozytouchDeviceType.ZONE


def test_a_zone_the_account_has_not_named_keeps_the_name_the_app_shows():
    """`get_zone_name` answers the id as a string when the zones array has no
    entry for it, and "Zone (1030104)" is worse than what the app displays.
    """
    hub = zone_hub()
    hub._zones = []

    assert Hub.get_model_infos(hub)["name"] == "THZONE_0"
