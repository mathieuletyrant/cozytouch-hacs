"""Which capability a mode change writes, and which one a room's switch writes.

An air-conditioning system runs one service at a time : the outdoor unit
cannot cool one room and dry the next. So the mode is the system's, carried
on 102020, and every room follows when it is written. What is a room's own is
whether it is running at all, which is its own service capability at 0.

Captured from the iOS app on a three-room account, 2026-09-21, three writes :

    mode   -> {"capabilityId": 102020, "deviceId": <room>, "value": "8"}
    off    -> {"capabilityId": 7,      "deviceId": <room>, "value": "0"}
    on     -> {"capabilityId": 7,      "deviceId": <room>, "value": "3"}

The last is the service the house is already running, which is what the
room's switch writes back.

The app's general stop was not in that capture, but a diagnostics dump taken
right after it (2026-09-28) was : 102020 at 0 on all three rooms within the
same second, then each room's 7 at 0 five seconds later. So off on the climate
entity is the general stop, like every other mode, and the room's own off is
the switch.
"""

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.cozytouch.capability import get_capability_infos
from custom_components.cozytouch.climate import CozytouchClimate
from custom_components.cozytouch.const import SERVICE_OFF
from custom_components.cozytouch.infos import CapabilityInfos
from custom_components.cozytouch.model import get_model_infos
from custom_components.cozytouch.switch import CozytouchRoomSwitch
from homeassistant.components.climate import HVACMode
from homeassistant.exceptions import HomeAssistantError

ROOM_SERVICE = 7
SYSTEM_SERVICE = 102020
COOL = 3
DRY = 8

# An air-conditioning room, model 557, as the account reports one.
AC_ROOM = 557


def stand_in(reported):
    """A hub stand-in that records what it is asked to write."""
    written = []

    async def set_capability_value(capabilityId, value):
        written.append((capabilityId, value))
        reported[capabilityId] = value

    coordinator = SimpleNamespace(
        set_capability_value=set_capability_value,
        get_capability_value=lambda cid, default="0": reported.get(cid, default),
        async_request_refresh=_noop,
    )
    return coordinator, written


def build(reported, system=SYSTEM_SERVICE):
    """A climate entity over a hub stand-in that records what it writes.

    Only the three attributes `async_set_hvac_mode` reads are set : the entity
    is not the subject here, the two capability ids it chooses between are.
    """
    entity = CozytouchClimate.__new__(CozytouchClimate)
    entity._modelInfos = SimpleNamespace(
        HVACModes={0: HVACMode.OFF, COOL: HVACMode.COOL, DRY: HVACMode.DRY}
    )
    entity._capability = CapabilityInfos(
        capabilityId=ROOM_SERVICE,
        **({"systemServiceCapabilityId": system} if system else {}),
    )
    entity.coordinator, written = stand_in(reported)
    return entity, written


def build_switch(reported):
    """A room's own switch, built beside 102020 as the platform builds it."""
    coordinator, written = stand_in(reported)
    switch = CozytouchRoomSwitch(
        coordinator=coordinator,
        capability=CapabilityInfos(capabilityId=SYSTEM_SERVICE, name="system_service"),
        config_title="Room",
        config_uniq_id="room",
    )
    return switch, written


async def _noop():
    """What the entity calls once it has written."""


def test_a_mode_is_written_to_the_system():
    """The whole point : one write, and every room of the system follows."""
    entity, written = build({ROOM_SERVICE: str(COOL), SYSTEM_SERVICE: str(COOL)})

    asyncio.run(entity.async_set_hvac_mode(HVACMode.DRY))

    assert written == [(SYSTEM_SERVICE, str(DRY))]


def test_off_is_the_general_stop():
    """Off is a mode like the others : the whole house, not the room."""
    entity, written = build({ROOM_SERVICE: str(DRY), SYSTEM_SERVICE: str(DRY)})

    asyncio.run(entity.async_set_hvac_mode(HVACMode.OFF))

    assert written == [(SYSTEM_SERVICE, SERVICE_OFF)]


def test_a_room_that_was_off_is_switched_back_on():
    """A mode asked of a room switched off turns that room on with it."""
    entity, written = build({ROOM_SERVICE: SERVICE_OFF, SYSTEM_SERVICE: str(COOL)})

    asyncio.run(entity.async_set_hvac_mode(HVACMode.DRY))

    assert written == [(SYSTEM_SERVICE, str(DRY)), (ROOM_SERVICE, str(DRY))]


def test_a_device_without_the_system_capability_writes_its_own():
    """A boiler has no system beside it, and keeps the write it always had."""
    entity, written = build({ROOM_SERVICE: str(COOL)}, system=None)

    asyncio.run(entity.async_set_hvac_mode(HVACMode.OFF))

    assert written == [(ROOM_SERVICE, SERVICE_OFF)]


def test_the_room_climate_is_wired_to_the_system_service():
    """The id is derived from what the device reports, not written per model."""
    capability = get_capability_infos(
        get_model_infos(AC_ROOM),
        ROOM_SERVICE,
        "0",
        {ROOM_SERVICE, SYSTEM_SERVICE, 40, 117},
    )

    assert capability.systemServiceCapabilityId == SYSTEM_SERVICE


def test_the_switch_turns_off_the_room_alone():
    """The app's toggle : 7 at 0, and 102020 left to the other rooms."""
    switch, written = build_switch({ROOM_SERVICE: str(COOL), SYSTEM_SERVICE: str(COOL)})

    asyncio.run(switch.async_turn_off())

    assert written == [(ROOM_SERVICE, SERVICE_OFF)]
    assert switch.is_on is False


def test_the_switch_joins_the_service_the_house_runs():
    """On writes the house's service into the room, as the capture shows."""
    switch, written = build_switch(
        {ROOM_SERVICE: SERVICE_OFF, SYSTEM_SERVICE: str(DRY)}
    )

    asyncio.run(switch.async_turn_on())

    assert written == [(ROOM_SERVICE, str(DRY))]
    assert switch.is_on is True


def test_the_switch_cannot_start_a_stopped_house():
    """166 permits only off while the system is stopped ; say so, write nothing."""
    switch, written = build_switch(
        {ROOM_SERVICE: SERVICE_OFF, SYSTEM_SERVICE: SERVICE_OFF}
    )

    with pytest.raises(HomeAssistantError):
        asyncio.run(switch.async_turn_on())

    assert written == []
