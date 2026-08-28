"""Tests for the gateway link the API declares and the integration draws.

Every room unit and thermal zone on an account carries its gateway's id in
masterDeviceId, so the parent/child shape is not inferred -- it is reported.
What has to be got right is the other half: this integration registers one
device per subentry, so the gateway exists in Home Assistant only if somebody
added it as a device of its own. Claiming a link to a device that is not there
earns a warning from the device registry, which is what these pin.

Hub.get_via_device is called unbound against a stand-in, the way the
diagnostics tests do -- it reads the account's device list and the entry's
subentries, and neither needs a coordinator.
"""

from types import SimpleNamespace

from custom_components.cozytouch import _register_devices
from custom_components.cozytouch.const import DOMAIN
from custom_components.cozytouch.hub import Hub
from custom_components.cozytouch.model import CozytouchDeviceType

GATEWAY_ID = 27906640
ROOM_ID = 27906641


def make_hub(devices, deviceId, added=()):
    """A stand-in exposing only what get_via_device reads."""
    return SimpleNamespace(
        _account=SimpleNamespace(devices=devices),
        _deviceId=deviceId,
        _entry=SimpleNamespace(
            subentries={
                subentry_id: SimpleNamespace(data={"deviceId": subentryDeviceId})
                for subentryDeviceId, subentry_id in added
            }
        ),
    )


def device(deviceId, masterDeviceId):
    return {"deviceId": deviceId, "masterDeviceId": masterDeviceId}


def test_a_room_unit_points_at_the_entry_its_gateway_was_set_up_under():
    """The link is to the gateway's subentry, not its Cozytouch id: that is
    the identifier every device in this integration is registered under.
    """
    hub = make_hub(
        [device(ROOM_ID, GATEWAY_ID), device(GATEWAY_ID, None)],
        deviceId=ROOM_ID,
        added=[(GATEWAY_ID, "abc123"), (ROOM_ID, "def456")],
    )

    assert Hub.get_via_device(hub) == (DOMAIN, "abc123")


def test_no_link_is_claimed_when_the_gateway_was_never_set_up():
    """Somebody can add one room unit and nothing else. The parent device does
    not exist then, and naming it anyway makes the registry complain.
    """
    hub = make_hub(
        [device(ROOM_ID, GATEWAY_ID)],
        deviceId=ROOM_ID,
        added=[(ROOM_ID, "def456")],
    )

    assert Hub.get_via_device(hub) is None


def test_a_gateway_has_no_parent_of_its_own():
    hub = make_hub(
        [device(GATEWAY_ID, None)],
        deviceId=GATEWAY_ID,
        added=[(GATEWAY_ID, "abc123")],
    )

    assert Hub.get_via_device(hub) is None


def test_a_device_from_before_the_field_was_carried_reports_no_parent():
    """A stored device dict predating masterDeviceId has no such key, and a
    reload must not raise on the way to rebuilding it.
    """
    hub = make_hub(
        [{"deviceId": ROOM_ID}],
        deviceId=ROOM_ID,
        added=[(GATEWAY_ID, "abc123")],
    )

    assert Hub.get_via_device(hub) is None


def test_an_unknown_device_id_is_not_linked_to_anything():
    hub = make_hub([device(ROOM_ID, GATEWAY_ID)], deviceId=999999)

    assert Hub.get_via_device(hub) is None


# --- when the registry learns of the link ----------------------------------
#
# Naming an existing gateway is only half of it: the platforms are set up
# concurrently, and a device used to be created by whichever platform first
# added entities for it. The gateway gets no calendar and no climate, so those
# two registered every room unit -- via_device included -- before the gateway's
# device existed, and the registry warned on a live install. Setup now
# registers every subentry's device itself, before any platform runs, which is
# what these pin. See docs/decisions.md.


class FakeRegistry:
    """Records what setup declares, in the order it declares it."""

    def __init__(self):
        self.created = []

    def async_get_or_create(self, **kwargs):
        self.created.append(kwargs)


def registering_hub(via_device):
    """A stand-in exposing what device_info_for reads."""
    return SimpleNamespace(
        get_model_infos=lambda: SimpleNamespace(name="Air Conditioner"),
        get_serial_number=lambda: "3022-2624-0400",
        get_software_version=lambda: None,
        get_via_device=lambda: via_device,
    )


def test_the_gateway_is_registered_before_the_children_that_name_it():
    """The subentries come in whatever order they were added; the registry
    order cannot be that one, since a child names its gateway on the way in.
    """
    registry = FakeRegistry()
    hubs = {
        "def456": registering_hub((DOMAIN, "abc123")),  # the child first
        "abc123": registering_hub(None),
    }

    _register_devices(registry, SimpleNamespace(entry_id="entry123"), hubs)

    assert [d["identifiers"] for d in registry.created] == [
        {(DOMAIN, "abc123")},
        {(DOMAIN, "def456")},
    ]


def test_the_device_registered_up_front_is_the_one_the_entities_describe():
    """Same identifiers, same subentry, same link: the platforms have to find
    the device setup created, not create a second one next to it.
    """
    registry = FakeRegistry()
    hubs = {"def456": registering_hub((DOMAIN, "abc123"))}

    _register_devices(registry, SimpleNamespace(entry_id="entry123"), hubs)

    (created,) = registry.created
    assert created["config_entry_id"] == "entry123"
    assert created["config_subentry_id"] == "def456"
    assert created["identifiers"] == {(DOMAIN, "def456")}
    assert created["via_device"] == (DOMAIN, "abc123")


def test_a_gateway_is_registered_without_a_link():
    """get_via_device answering None has to mean no via_device key at all:
    passing None through would claim a parent called None.
    """
    registry = FakeRegistry()

    _register_devices(
        registry,
        SimpleNamespace(entry_id="entry123"),
        {"abc123": registering_hub(None)},
    )

    assert "via_device" not in registry.created[0]


# --- the zone half of the same payload -------------------------------------


def zone_hub():
    """A hub over the two halves of one capture.

    The device is the THZONE the API reports at deviceId 27906644 with
    `zoneId: 1030104`; the setup view's `zones` array is what turns that id into
    a room. Both come from the same install, ids and names included, so this is
    the wiring as it really arrives rather than a shape invented for a test.
    """
    zones = [
        {"id": 1030103, "name": "Zone 1", "zoneType": 29, "numberOfDevices": 1},
        {
            "id": 1030104,
            "name": "Chambre parentale",
            "zoneType": 1,
            "numberOfDevices": 2,
        },
    ]
    account = SimpleNamespace(
        devices=[
            {
                "deviceId": 27906644,
                "modelId": 1505,
                "name": "THZONE_0",
                "zoneId": 1030104,
                "masterDeviceId": GATEWAY_ID,
            }
        ],
        zones=zones,
    )
    # The zone lookup lives on the account, which is what the hub delegates to.
    account.get_zone_name = lambda zoneId=None: next(
        (z["name"] for z in account.zones if z.get("id") == zoneId), None
    )

    hub = object.__new__(Hub)
    hub._account = account
    hub._deviceId = 27906644
    hub._zoneId = 1030104

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
    hub._account.zones = []

    assert Hub.get_model_infos(hub)["name"] == "THZONE_0"
