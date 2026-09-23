"""What a fan, swing or away-date change from Home Assistant writes.

Fan and swing share one write path, and so do the away mode's two dates, so
a slip in either shows up on every device that has them. Nothing else in the
suite calls these writes. The entities are driven unbound against a stand-in,
the way test_hvac_action.py drives the update.
"""

import asyncio
from datetime import UTC, datetime
from functools import partial
from types import SimpleNamespace

from custom_components.cozytouch.climate import FAN_QUIET, CozytouchClimate
from custom_components.cozytouch.datetime import CozytouchAwayModeDateTime
from custom_components.cozytouch.hub import Hub
from custom_components.cozytouch.infos import CapabilityInfos, ModelInfos
from homeassistant.components.climate import SWING_ON

FAN = {"quietModeCapabilityId": 30, "fanModeCapabilityId": 31}
SWING = {"swingOnCapabilityId": 40, "swingModeCapabilityId": 41}


def climate(**capabilityIds):
    capability = CapabilityInfos()
    for key, value in capabilityIds.items():
        capability[key] = value

    modelInfos = ModelInfos()
    modelInfos.fanModes = {1: "low", 3: "high"}
    modelInfos.swingModes = {2: "up", 4: "down"}

    writes = []

    async def set_capability_value(capabilityId, value):
        writes.append((capabilityId, value))

    async def async_request_refresh():
        writes.append("refresh")

    fake = SimpleNamespace(
        _capability=capability,
        _modelInfos=modelInfos,
        coordinator=SimpleNamespace(
            set_capability_value=set_capability_value,
            async_request_refresh=async_request_refresh,
        ),
    )
    fake._write_mode = partial(CozytouchClimate._write_mode, fake)
    return fake, writes


def run(coroutine):
    asyncio.run(coroutine)


def test_a_fan_speed_switches_quiet_off_then_writes_the_speed():
    fake, writes = climate(**FAN)

    run(CozytouchClimate.async_set_fan_mode(fake, "high"))

    assert writes == [(30, "0"), (31, "3"), "refresh"]


def test_quiet_is_written_to_its_own_capability_alone():
    fake, writes = climate(**FAN)

    run(CozytouchClimate.async_set_fan_mode(fake, FAN_QUIET))

    assert writes == [(30, "1"), "refresh"]


def test_a_fan_speed_without_a_quiet_capability_writes_only_the_speed():
    fake, writes = climate(fanModeCapabilityId=31)

    run(CozytouchClimate.async_set_fan_mode(fake, "low"))

    assert writes == [(31, "1"), "refresh"]


def test_a_fan_speed_the_table_does_not_name_writes_no_speed():
    fake, writes = climate(**FAN)

    run(CozytouchClimate.async_set_fan_mode(fake, "turbo"))

    assert writes == [(30, "0"), "refresh"]


def test_a_swing_position_switches_swing_off_then_writes_the_position():
    fake, writes = climate(**SWING)

    run(CozytouchClimate.async_set_swing_mode(fake, "down"))

    assert writes == [(40, "0"), (41, "4"), "refresh"]


def test_swing_on_is_written_to_its_own_capability_alone():
    fake, writes = climate(**SWING)

    run(CozytouchClimate.async_set_swing_mode(fake, SWING_ON))

    assert writes == [(40, "1"), "refresh"]


def test_fan_and_swing_do_not_write_into_each_other():
    fake, writes = climate(**FAN, **SWING)

    run(CozytouchClimate.async_set_fan_mode(fake, "low"))
    run(CozytouchClimate.async_set_swing_mode(fake, "up"))

    assert writes == [(30, "0"), (31, "1"), "refresh", (40, "0"), (41, "2"), "refresh"]


def away_hub():
    hub = SimpleNamespace(
        _timestamp_away_mode_start=None,
        _timestamp_away_mode_end=None,
        _timestamps_away_mode_capability_id=None,
        _timestamp_away_mode_last_change=None,
    )
    hub.set_away_mode_bound = partial(Hub.set_away_mode_bound, hub)
    hub.get_away_mode_start = partial(Hub.get_away_mode_start, hub)
    hub.get_away_mode_end = partial(Hub.get_away_mode_end, hub)
    return hub


def away_date(hub, index):
    capability = CapabilityInfos()
    capability.capabilityId = 222
    return SimpleNamespace(
        _capability=capability, _timestamp_index=index, coordinator=hub
    )


START = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
END = datetime(2026, 10, 8, 18, 0, tzinfo=UTC)


def test_the_start_date_lands_on_the_start_and_the_end_on_the_end():
    hub = away_hub()

    run(CozytouchAwayModeDateTime.async_set_value(away_date(hub, 0), START))
    run(CozytouchAwayModeDateTime.async_set_value(away_date(hub, 1), END))

    assert hub._timestamp_away_mode_start == int(START.timestamp())
    assert hub._timestamp_away_mode_end == int(END.timestamp())
    assert hub._timestamps_away_mode_capability_id == 222
    assert hub._timestamp_away_mode_last_change is not None


def test_each_date_reads_back_what_was_set():
    hub = away_hub()
    start, end = away_date(hub, 0), away_date(hub, 1)

    run(CozytouchAwayModeDateTime.async_set_value(start, START))
    run(CozytouchAwayModeDateTime.async_set_value(end, END))

    assert CozytouchAwayModeDateTime.native_value.fget(start) == START
    assert CozytouchAwayModeDateTime.native_value.fget(end) == END


def test_an_index_past_the_two_dates_writes_nothing():
    hub = away_hub()

    run(CozytouchAwayModeDateTime.async_set_value(away_date(hub, 2), START))

    assert hub._timestamp_away_mode_start is None
    assert hub._timestamp_away_mode_end is None
    assert hub._timestamp_away_mode_last_change is None
