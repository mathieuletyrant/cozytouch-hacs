"""Which capability a mode change writes, and which one off writes.

An air-conditioning system runs one service at a time : the outdoor unit
cannot cool one room and dry the next. So the mode is the system's, carried
on 102020, and every room follows when it is written. What is a room's own is
whether it is running at all, which is its own service capability at 0.

Captured from the iOS app on a three-room account, 2026-09-21, three writes :

    mode   -> {"capabilityId": 102020, "deviceId": <room>, "value": "8"}
    off    -> {"capabilityId": 7,      "deviceId": <room>, "value": "0"}
    on     -> {"capabilityId": 7,      "deviceId": <room>, "value": "3"}

The last is the service the house is already running, which is why switching
a room back on beside a mode change is one gesture here and two there.

The app's general stop was not in that capture. It is the first entry of the
same dropdown, so the system switch writes 102020 at 0, the off of that value
space, and turning it on writes back the service it last saw running.
"""

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.cozytouch.capability import get_capability_infos
from custom_components.cozytouch.climate import CozytouchClimate
from custom_components.cozytouch.const import SERVICE_OFF
from custom_components.cozytouch.infos import CapabilityInfos
from custom_components.cozytouch.model import get_model_infos
from custom_components.cozytouch.switch import CozytouchSystemSwitch
from homeassistant.components.climate import HVACMode
from homeassistant.exceptions import HomeAssistantError

ROOM_SERVICE = 7
SYSTEM_SERVICE = 102020
COOL = 3
DRY = 8

# An air-conditioning room, model 557, as the account reports one.
AC_ROOM = 557


def build(reported, system=SYSTEM_SERVICE):
    """A climate entity over a hub stand-in that records what it writes.

    Only the three attributes `async_set_hvac_mode` reads are set : the entity
    is not the subject here, the two capability ids it chooses between are.
    """
    written = []

    async def set_capability_value(capabilityId, value):
        written.append((capabilityId, value))
        reported[capabilityId] = value

    entity = CozytouchClimate.__new__(CozytouchClimate)
    entity._modelInfos = SimpleNamespace(
        HVACModes={0: HVACMode.OFF, COOL: HVACMode.COOL, DRY: HVACMode.DRY}
    )
    entity._capability = CapabilityInfos(
        capabilityId=ROOM_SERVICE,
        **({"systemServiceCapabilityId": system} if system else {}),
    )
    entity.coordinator = SimpleNamespace(
        set_capability_value=set_capability_value,
        get_capability_value=lambda cid, default="0": reported.get(cid, default),
        async_request_refresh=_noop,
    )
    return entity, written


async def _noop():
    """What the entity calls once it has written."""


def test_a_mode_is_written_to_the_system():
    """The whole point : one write, and every room of the system follows."""
    entity, written = build({ROOM_SERVICE: str(COOL), SYSTEM_SERVICE: str(COOL)})

    asyncio.run(entity.async_set_hvac_mode(HVACMode.DRY))

    assert written == [(SYSTEM_SERVICE, str(DRY))]


def test_off_is_written_to_the_room():
    """Off is the one service value that is the room's own."""
    entity, written = build({ROOM_SERVICE: str(DRY), SYSTEM_SERVICE: str(DRY)})

    asyncio.run(entity.async_set_hvac_mode(HVACMode.OFF))

    assert written == [(ROOM_SERVICE, SERVICE_OFF)]


def test_a_room_that_was_off_is_switched_back_on():
    """Two gestures in the app, one here : the mode, then the room itself."""
    entity, written = build({ROOM_SERVICE: SERVICE_OFF, SYSTEM_SERVICE: str(COOL)})

    asyncio.run(entity.async_set_hvac_mode(HVACMode.DRY))

    assert written == [(SYSTEM_SERVICE, str(DRY)), (ROOM_SERVICE, str(DRY))]


def test_a_device_without_the_system_capability_writes_its_own():
    """A boiler has no system beside it, and keeps the write it always had."""
    entity, written = build({ROOM_SERVICE: str(COOL)}, system=None)

    asyncio.run(entity.async_set_hvac_mode(HVACMode.DRY))

    assert written == [(ROOM_SERVICE, str(DRY))]


def test_the_room_climate_is_wired_to_the_system_service():
    """The id is derived from what the device reports, not written per model."""
    capability = get_capability_infos(
        get_model_infos(AC_ROOM),
        ROOM_SERVICE,
        "0",
        {ROOM_SERVICE, SYSTEM_SERVICE, 40, 117},
    )

    assert capability.systemServiceCapabilityId == SYSTEM_SERVICE



def build_switch(reported):
    """A system switch over a hub stand-in that records what it writes."""
    written = []

    async def set_capability_value(capabilityId, value):
        written.append((capabilityId, value))
        reported[capabilityId] = value

    switch = CozytouchSystemSwitch.__new__(CozytouchSystemSwitch)
    switch._capability = CapabilityInfos(
        capabilityId=SYSTEM_SERVICE, roomServiceCapabilityId=ROOM_SERVICE
    )
    switch.coordinator = SimpleNamespace(
        set_capability_value=set_capability_value,
        get_capability_value=lambda cid, default="0": reported.get(cid, default),
        async_request_refresh=_noop,
    )
    switch._last_service = None
    switch._remember_service()
    return switch, written


def test_off_is_the_general_stop():
    """One write, on the system's service, and no room's own state touched."""
    switch, written = build_switch({SYSTEM_SERVICE: str(COOL)})

    asyncio.run(switch.async_turn_off())

    assert written == [(SYSTEM_SERVICE, SERVICE_OFF)]
    assert switch.is_on is False


def test_on_goes_back_to_the_service_the_system_left():
    """102020 forgets it ; the switch does not."""
    switch, written = build_switch({SYSTEM_SERVICE: str(DRY)})

    asyncio.run(switch.async_turn_off())
    asyncio.run(switch.async_turn_on())

    assert written == [(SYSTEM_SERVICE, SERVICE_OFF), (SYSTEM_SERVICE, str(DRY))]
    assert switch.is_on is True


def test_on_falls_back_on_the_room_when_nothing_was_seen():
    """Stopped before Home Assistant ever saw it run : the room may say."""
    switch, written = build_switch(
        {SYSTEM_SERVICE: SERVICE_OFF, ROOM_SERVICE: str(COOL)}
    )

    asyncio.run(switch.async_turn_on())

    assert written == [(SYSTEM_SERVICE, str(COOL))]


def test_on_with_nothing_to_go_back_to_writes_nothing():
    """Better an error than a guessed service the house never asked for."""
    switch, written = build_switch(
        {SYSTEM_SERVICE: SERVICE_OFF, ROOM_SERVICE: SERVICE_OFF}
    )

    with pytest.raises(HomeAssistantError):
        asyncio.run(switch.async_turn_on())

    assert written == []
