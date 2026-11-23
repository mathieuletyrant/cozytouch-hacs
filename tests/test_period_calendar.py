"""The week of comfort periods, the program shape of the Alfea heat pumps.

Issue #229 : an Alfea Excellia Duo AI (model 73) holds no setpoint block at
196 or 100320. Its program is one capability per zone and season, 101-104,
holding the whole week as JSON, three periods a day. Inside a period the
device holds its comfort setpoint (the dump, taken at 18:08 inside 06:00-22:00,
reads profile 1 "comfort" and the comfort setpoint 18), outside it eco.

These pin which calendars a device gets (only where the availability next to
the program says so), how the week turns into dated events, and what an edit
writes back : the device's own string, spacing included, since nothing has
measured how strict it is about it.
"""

import asyncio
import datetime
import json
from types import SimpleNamespace

from _harness import SUBENTRY_ID, entry_over, set_up
import pytest

from custom_components.cozytouch import calendar as calendar_platform
from custom_components.cozytouch.calendar import CozytouchPeriodCalendar
from custom_components.cozytouch.const import DOMAIN
from custom_components.cozytouch.infos import ModelInfos
from custom_components.cozytouch.services import add_period, build_week, parse_periods
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

MONDAY = datetime.date(2026, 8, 24)
TUESDAY = datetime.date(2026, 8, 25)

# Capability 103 as issue #229's dump reports it, byte for byte.
ISSUE_229_WEEK = (
    '[{"monday": [{"start": "06:00","end": "22:00"},{"start": "00:00","end": '
    '"00:00"},{"start": "00:00","end": "00:00"}]},{"tuesday": [{"start": '
    '"06:00","end": "22:00"},{"start": "00:00","end": "00:00"},{"start": '
    '"00:00","end": "00:00"}]},{"wednesday": [{"start": "06:00","end": '
    '"22:00"},{"start": "00:00","end": "00:00"},{"start": "00:00","end": '
    '"00:00"}]},{"thursday": [{"start": "06:00","end": "22:00"},{"start": '
    '"00:00","end": "00:00"},{"start": "00:00","end": "00:00"}]},{"friday": '
    '[{"start": "06:00","end": "22:00"},{"start": "00:00","end": "00:00"},'
    '{"start": "00:00","end": "00:00"}]},{"saturday": [{"start": "06:00",'
    '"end": "22:00"},{"start": "00:00","end": "00:00"},{"start": "00:00",'
    '"end": "00:00"}]},{"sunday": [{"start": "06:00","end": "22:00"},'
    '{"start": "00:00","end": "00:00"},{"start": "00:00","end": "00:00"}]}]'
)

# What else the dump reports around it : zone 2's weeks are there too, but
# neither zone 2 availability, and cooling is declared unavailable.
ISSUE_229 = {
    101: ISSUE_229_WEEK,
    102: ISSUE_229_WEEK,
    103: ISSUE_229_WEEK,
    104: ISSUE_229_WEEK,
    176: "1",
    190: "0",
}


def at(day, hour, minute=0):
    return datetime.datetime(
        day.year, day.month, day.day, hour, minute, tzinfo=dt_util.DEFAULT_TIME_ZONE
    )


def make_hub(values):
    return SimpleNamespace(
        get_capability_value=lambda capabilityId, default="0": values.get(
            capabilityId, default
        ),
        get_model_infos=lambda: ModelInfos(name="Alfea Excellia Duo AI"),
        get_serial_number=lambda: "1234-5678-0000",
        get_software_version=lambda: "1.2.3",
        get_via_device=lambda: None,
    )


def writable(values=None, week=103):
    values = dict(ISSUE_229 if values is None else values)
    written = {}
    hub = make_hub(values)

    async def set_capability_value(capabilityId, value):
        written[capabilityId] = value
        values[capabilityId] = value

    async def refresh():
        return None

    hub.set_capability_value = set_capability_value
    hub.async_request_refresh = refresh

    zone = 1 if week in (103, 104) else 2
    program = "heating" if week in (101, 103) else "cooling"
    calendar = CozytouchPeriodCalendar(
        coordinator=hub,
        config_uniq_id=SUBENTRY_ID,
        program=program,
        zone=zone,
        week=week,
    )
    return calendar, written


def events(calendar, start, end):
    return asyncio.run(calendar.async_get_events(None, start, end))


def day_of(written, day):
    for entry in json.loads(written):
        if day in entry:
            return entry[day]
    raise AssertionError(day)


# ------------------------------------------------------------ which entities


def test_issue_229_gets_one_heating_calendar():
    built = set_up(calendar_platform, entry_over(make_hub(ISSUE_229)))

    assert [entity.translation_key for entity in built] == ["heating_program"]
    assert built[0].unique_id == f"{DOMAIN}_{SUBENTRY_ID}_heating_program"


def test_a_week_without_its_availability_gets_no_calendar():
    values = {103: ISSUE_229_WEEK}

    assert set_up(calendar_platform, entry_over(make_hub(values))) == []


def test_zone_2_gets_its_own_calendar_when_declared():
    values = ISSUE_229 | {189: "1"}
    built = set_up(calendar_platform, entry_over(make_hub(values)))

    assert sorted(entity.translation_key for entity in built) == [
        "heating_program",
        "heating_program_z2",
    ]


def test_a_setpoint_block_keeps_its_calendar():
    """No device holds both shapes ; if one did, the setpoint one stays."""
    values = ISSUE_229 | {196 + day: "[[0,19]]" for day in range(7)}
    built = set_up(calendar_platform, entry_over(make_hub(values)))

    assert [type(entity).__name__ for entity in built] == ["CozytouchProgramCalendar"]


# ------------------------------------------------------------------- reading


def test_the_dump_reads_as_one_period_a_day():
    week = parse_periods(ISSUE_229_WEEK)

    assert week["monday"] == [{"start": "06:00", "end": "22:00"}]
    assert len(week) == 7


def test_a_period_is_an_event_and_the_rest_of_the_day_is_nothing():
    calendar, _ = writable()

    found = events(calendar, at(MONDAY, 0), at(TUESDAY, 0))

    assert [(event.start, event.end) for event in found] == [
        (at(MONDAY, 6), at(MONDAY, 22))
    ]


def test_a_period_ending_at_midnight_runs_to_the_end_of_the_day():
    stored = build_week({"monday": [{"start": "20:00", "end": "00:00"}]})
    calendar, _ = writable({103: stored, 176: "1"})

    found = events(calendar, at(MONDAY, 0), at(TUESDAY, 0))

    assert [(event.start, event.end) for event in found] == [
        (at(MONDAY, 20), at(TUESDAY, 0))
    ]


@pytest.mark.parametrize("unreadable", [None, "", "0", "{}", "[1,2]", "not json"])
def test_an_unreadable_week_has_no_events(unreadable):
    calendar, _ = writable({103: unreadable, 176: "1"})

    assert events(calendar, at(MONDAY, 0), at(TUESDAY, 0)) == []


def test_the_current_event_is_the_period_covering_now(monkeypatch):
    calendar, _ = writable()
    monkeypatch.setattr(dt_util, "now", lambda: at(MONDAY, 12))

    assert calendar.event.start == at(MONDAY, 6)


def test_outside_a_period_nothing_is_running(monkeypatch):
    calendar, _ = writable()
    monkeypatch.setattr(dt_util, "now", lambda: at(MONDAY, 23))

    assert calendar.event is None


# ------------------------------------------------------------------- writing


def test_an_untouched_week_writes_back_byte_for_byte():
    assert build_week(parse_periods(ISSUE_229_WEEK)) == ISSUE_229_WEEK


def test_a_created_event_adds_a_period_on_its_weekday():
    calendar, written = writable()

    asyncio.run(
        calendar.async_create_event(
            dtstart=at(TUESDAY, 1), dtend=at(TUESDAY, 3), summary="Comfort"
        )
    )

    assert day_of(written[103], "tuesday") == [
        {"start": "01:00", "end": "03:00"},
        {"start": "06:00", "end": "22:00"},
        {"start": "00:00", "end": "00:00"},
    ]
    assert day_of(written[103], "monday")[0] == {"start": "06:00", "end": "22:00"}


def test_an_overlapping_event_widens_the_period():
    calendar, written = writable()

    asyncio.run(
        calendar.async_create_event(
            dtstart=at(MONDAY, 21), dtend=at(MONDAY, 23), summary=""
        )
    )

    assert day_of(written[103], "monday")[0] == {"start": "06:00", "end": "23:00"}


def test_a_fourth_period_is_refused():
    periods = [
        {"start": "01:00", "end": "02:00"},
        {"start": "03:00", "end": "04:00"},
        {"start": "05:00", "end": "06:00"},
    ]

    with pytest.raises(HomeAssistantError, match="3 periods"):
        add_period(periods, datetime.time(8), datetime.time(9))


def test_a_period_running_to_midnight_is_not_written():
    calendar, written = writable()

    with pytest.raises(HomeAssistantError, match="23:59"):
        asyncio.run(
            calendar.async_create_event(
                dtstart=at(MONDAY, 23), dtend=at(TUESDAY, 0), summary=""
            )
        )

    assert written == {}


def test_a_deleted_event_leaves_the_day_on_eco():
    calendar, written = writable()
    uid = events(calendar, at(MONDAY, 0), at(TUESDAY, 0))[0].uid

    asyncio.run(calendar.async_delete_event(uid))

    assert day_of(written[103], "monday") == [{"start": "00:00", "end": "00:00"}] * 3


def test_a_moved_event_leaves_its_old_day_in_one_write():
    calendar, written = writable()
    uid = events(calendar, at(MONDAY, 0), at(TUESDAY, 0))[0].uid

    asyncio.run(
        calendar.async_update_event(
            uid, {"dtstart": at(MONDAY, 7), "dtend": at(MONDAY, 21), "summary": ""}
        )
    )

    assert day_of(written[103], "monday")[0] == {"start": "07:00", "end": "21:00"}
    assert list(written) == [103]


def test_a_week_missing_a_day_is_not_rewritten():
    partial = json.dumps(json.loads(ISSUE_229_WEEK)[:6])
    calendar, written = writable({103: partial, 176: "1"})

    with pytest.raises(HomeAssistantError, match="whole week"):
        asyncio.run(
            calendar.async_create_event(
                dtstart=at(MONDAY, 1), dtend=at(MONDAY, 2), summary=""
            )
        )

    assert written == {}
