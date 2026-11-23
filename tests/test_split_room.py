"""A room in front of a split reads neither 153 nor, where the app hides it, 117.

Issue #224 : two Murao splits behind a CozyBox, rooms 557 and 558. Both
heat -- 181 at 4, the app's sun icon -- and Home Assistant said `idle` and a
room at 0.0 degrees.

153 is a radiator's element. A room wired it as one whatever was in front
of it, and on a split it never moves (0 on #224's rooms while heating, 0 on
the Navizone's while cooling), so a heating split read idle. A room whose
103026 names the split (8) and no electric heater no longer wires it.

117 read 0, unchanged for twelve days, and the app shows no ambient reading
for these rooms : its tile needs the TEMPERATURE bit (1) of 100024, which
reads 0 there and 1 on the Navizone rooms. A room reporting 100024 with
that bit clear shows no current temperature, rather than a false 0.

Everything else answers as before : a room that reports no 103026 or no
100024, a radiator, a room in front of a heat pump or a boiler.
"""

import pytest

from custom_components.cozytouch.capability import get_capability_infos
from custom_components.cozytouch.model import get_device_model_infos

# A split's room behind a CozyBox : room 557 of #224 (a Murao), cut to the
# ids this reads.
SPLIT_ROOM = {
    7: "4",
    40: "17",
    117: "0.00000000000000000000",
    153: "0",
    166: "411",
    177: "26",
    181: "4",
    100002: "111",
    100022: "415",
    100024: "0",
    103026: "8",
    103150: "1",
}

# A Navizone room, which shows its temperature in the app.
NAVIZONE = SPLIT_ROOM | {100002: "1", 100024: "1", 117: "23.17"}


def climate(capabilities, gateway=2449, family="Connectivity_Box"):
    box = {
        "deviceId": 2,
        "modelId": gateway,
        "productId": 63,
        "modelFamily": family,
        "name": "",
    }
    slot = {
        "deviceId": 1,
        "modelId": 557,
        "productId": 26,
        "masterDeviceId": 2,
        "name": "ROOM_0",
        "capabilities": [
            {"capabilityId": capabilityId, "value": value}
            for capabilityId, value in capabilities.items()
        ],
    }
    infos = get_device_model_infos([box, slot], slot, "Salon")
    return get_capability_infos(infos, 7, "4", set(capabilities))


def test_a_heating_split_is_not_held_at_idle():
    assert "heatingActiveCapabilityId" not in climate(SPLIT_ROOM)


def test_the_app_hidden_ambient_is_not_shown():
    assert climate(SPLIT_ROOM).get("currentValueCapabilityId") is None


def test_the_rest_of_the_split_room_is_unchanged():
    room = climate(SPLIT_ROOM)

    assert room.hvacActionCapabilityId == 181
    assert room.targetCapabilityId == 40
    assert room.targetCoolCapabilityId == 177


def test_a_navizone_room_keeps_its_temperature():
    assert climate(NAVIZONE, 1758, "Air_Conditioning").currentValueCapabilityId == 117


@pytest.mark.parametrize(
    "generator",
    [
        "128",  # radiators behind a CozyBox (gduteil/cozytouch#172)
        "16",  # an OROSI 2 (#190)
        "24",  # a split and a panel heater
        "2",  # an air-to-water heat pump, never seen on a room
        "4",  # a boiler, never seen on a room
        "0",  # nothing declared
        None,  # the 2024 Takao rooms report no 103026
    ],
)
def test_any_other_room_keeps_153(generator):
    capabilities = dict(SPLIT_ROOM)
    if generator is None:
        del capabilities[103026]
    else:
        capabilities[103026] = generator

    assert climate(capabilities).heatingActiveCapabilityId == 153


@pytest.mark.parametrize("options", ["1", "3", "111", None])
def test_a_room_with_the_temperature_bit_or_without_100024_keeps_117(options):
    capabilities = dict(SPLIT_ROOM)
    if options is None:
        del capabilities[100024]
    else:
        capabilities[100024] = options

    assert climate(capabilities).currentValueCapabilityId == 117
