"""Tests for the gateway link the API declares and the integration draws.

Every room unit and thermal zone on an account carries its gateway's id in
masterDeviceId, so the parent/child shape is not inferred -- it is reported.
What has to be got right is the other half: this integration registers one
device per config entry, so the gateway exists in Home Assistant only if
somebody set it up as an entry of its own. Claiming a link to a device that is
not there earns a warning from the device registry, which is what these pin.

Hub.get_via_device is called unbound against a stand-in, the way the
diagnostics tests do -- it reads the account's device list and the entry store,
and neither needs a coordinator.
"""

from types import SimpleNamespace

from custom_components.cozytouch.const import DOMAIN
from custom_components.cozytouch.hub import Hub

GATEWAY_ID = 27906640
ROOM_ID = 27906641


def make_hub(devices, deviceId, entries=()):
    """A stand-in exposing only what get_via_device reads."""
    return SimpleNamespace(
        _account=SimpleNamespace(devices=devices),
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
