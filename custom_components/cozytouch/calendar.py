"""Calendars for Atlantic Cozytouch integration."""

from __future__ import annotations

from datetime import datetime, time, timedelta
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .hub import CozytouchConfigEntry, Hub, device_info_for
from .services import DAYS, parse_slots

_LOGGER = logging.getLogger(__name__)

# The three weekly programs these devices hold, by the first capability of each
# seven-day run: heating and cooling on a boiler or an air conditioner, hot
# water on a water heater. A device gets a calendar per block it reports, which
# in practice means one or two of them.
#
# Deliberately its own table rather than `services.PROGRAM_FIRST_CAPABILITY`,
# which knows 196 and 203 only. Reading a program and writing one are not the
# same risk: what the second member of a hot-water slot means has never been
# confirmed against a capture, and writing a block on that basis could leave a
# water heater running a program it never had. Reading it costs nothing, and
# the prog sensors have rendered 237-243 as a time and a setpoint for as long
# as they have existed -- this shows the same reading, in a form you can look
# at. `set_schedule` still refuses the block, and should until a capture says
# otherwise.
PROGRAM_BLOCKS = {"heating": 196, "cooling": 203, "hot_water": 237}

# How far either side of now to look when answering "what is running". A day
# each way rather than from midnight: the last slot of a day runs into the next
# one, so the event in charge at 00:30 began yesterday -- and the window has to
# reach past now as well, since `_events_between` takes a half-open range and
# would drop a slot starting exactly on the boundary.
CURRENT_EVENT_WINDOW = timedelta(days=1)


# config flow setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    # One device per subentry, and its calendars are registered under it, the
    # way every other platform here does it.
    for subentry_id in config_entry.subentries:
        hub = config_entry.runtime_data.hubs[subentry_id]

        calendars = [
            CozytouchProgramCalendar(
                coordinator=hub,
                config_uniq_id=subentry_id,
                program=program,
            )
            for program, first in PROGRAM_BLOCKS.items()
            if _reports_the_whole_block(hub, first)
        ]

        if calendars:
            async_add_entities(calendars, True, config_subentry_id=subentry_id)


def _reports_the_whole_block(hub: Hub, first: int) -> bool:
    """Whether this device reports all seven days of a program block.

    All seven rather than any: the mapping claims 196-209 wholesale, so a
    device that has the block has every day of it, and a calendar built from a
    partial one would show a gap where it should show a setpoint -- which reads
    as "nothing scheduled that day" rather than as missing data.
    """
    return all(
        hub.get_capability_value(first + day, None) is not None
        for day in range(len(DAYS))
    )


class CozytouchProgramCalendar(CoordinatorEntity, CalendarEntity):
    """A weekly program, as the week it actually is.

    The program is what these devices are scheduled by -- it keeps running when
    Home Assistant is off -- and until now it could only be read as seven
    strings, one per day, formatted for a dashboard. `get_schedule` made it
    machine-readable; this makes it a week you can look at, and something the
    `calendar` triggers can fire on : "when the program moves to its next
    setpoint" is an event start, which is exactly the shape of an automation
    nobody could write before.

    Read-only, deliberately. Writing would mean turning an event into a slot,
    and the two do not have the same shape : an event has a start and an end,
    while a slot has only a start -- the next slot is what ends it. Resolving
    that is `set_schedule`'s job, and a calendar that silently rewrote the
    following slots would be the wrong place for it.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: Hub,
        config_uniq_id: str,
        program: str,
    ) -> None:
        """Initialize a program calendar."""
        super().__init__(coordinator)

        self._program = program
        self._first_capability = PROGRAM_BLOCKS[program]
        self._device_uniq_id = config_uniq_id
        # `heating` and `cooling` are the service's words for those two
        # blocks, kept so one vocabulary covers all three. capability.py calls
        # 203-209 the zone 2 program outside air conditioners, which is the
        # same unresolved naming set_schedule carries; the program exists in
        # both cool and heat, so nothing here decides it either.
        self._attr_translation_key = f"{program}_program"
        self._attr_unique_id = f"{DOMAIN}_{config_uniq_id}_{program}_program"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return device_info_for(self.coordinator, self._device_uniq_id)

    @property
    def event(self) -> CalendarEvent | None:
        """The setpoint the program is holding right now.

        A program that covers the whole day means this is never None, so the
        entity sits at `on` for good -- the state is not the useful part. What
        is useful is this event and the next one, which is what the card shows
        and what an automation reads.
        """
        now = dt_util.now()
        window = self._events_between(
            now - CURRENT_EVENT_WINDOW, now + CURRENT_EVENT_WINDOW
        )
        for event in window:
            if event.start <= now < event.end:
                return event

        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Every setpoint the program holds between two dates."""
        return self._events_between(start_date, end_date)

    def _events_between(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Expand the seven stored days over a range of real dates.

        The program is a week, not a list of dated events, so this is where it
        becomes one : each day of the range is looked up by its weekday, and
        each slot becomes an event running until the next slot -- or until
        midnight, since the last slot of a day holds until the next day's first
        one takes over.

        Local time throughout. The device stores minutes past midnight and
        nothing says which clock it keeps : it reports an offset (the away-mode
        timestamps use it, and docs/architecture.md records that path applying
        it twice), but no capture has ever tied that offset to the program. Home
        Assistant's zone is the reading that matches what the app shows for
        anyone whose house and hub agree, which is everybody until somebody
        reports otherwise.
        """
        zone = dt_util.DEFAULT_TIME_ZONE
        day = dt_util.as_local(start_date).date()
        last = dt_util.as_local(end_date).date()

        # The seven days once, not once per date: a card asking for a year would
        # otherwise re-read and re-sort the same seven programs 365 times.
        programs = [self._slots_for(weekday) for weekday in range(7)]

        events: list[CalendarEvent] = []
        while day <= last:
            slots = programs[day.weekday()]
            for index, slot in enumerate(slots):
                start = datetime.combine(day, slot["time"], tzinfo=zone)

                if index + 1 < len(slots):
                    end = datetime.combine(day, slots[index + 1]["time"], tzinfo=zone)
                else:
                    # Held until the day runs out. The next day's first slot
                    # starts at 00:00 -- set_schedule refuses a day that does
                    # not -- so nothing is left uncovered by stopping here.
                    end = datetime.combine(
                        day + timedelta(days=1), time(0, 0), tzinfo=zone
                    )

                # Overlapping, not contained: an event that started before the
                # window is the one running at its beginning, and dropping it
                # would leave the range looking unscheduled until the next
                # setpoint.
                if end > start_date and start < end_date:
                    events.append(
                        CalendarEvent(
                            start=start,
                            end=end,
                            summary=f"{slot['temperature']:g} °C",
                        )
                    )

            day += timedelta(days=1)

        return events

    def _slots_for(self, weekday: int) -> list[dict]:
        """One day's slots, in time order, as times rather than strings.

        `parse_slots` reads the stored matrix the way `get_schedule` does --
        including telling the [0,0] padding from a real midnight slot -- and
        answers in the shape `set_schedule` takes, which is strings. A calendar
        needs times, and needs them sorted: the device stores them in order,
        and an event list built on that assumption without checking would put
        an evening setpoint in charge of the morning.
        """
        stored = self.coordinator.get_capability_value(
            self._first_capability + weekday, None
        )

        slots = []
        for slot in parse_slots(stored):
            try:
                hours, minutes = (int(part) for part in slot["time"].split(":"))
                slots.append(
                    {
                        "time": time(hours, minutes),
                        # A float on purpose : the summary formats with %g, and
                        # a temperature that arrived as a string -- which this
                        # API does for `value` -- would raise there instead of
                        # here, taking the whole calendar with it.
                        "temperature": float(slot["temperature"]),
                    }
                )
            except (TypeError, ValueError):
                # A minute count past the end of the day, or a setpoint that is
                # not a number. Neither has been captured; both are one bad
                # matrix away from breaking every event in the week, so the
                # slot is dropped and the rest of the day still renders.
                _LOGGER.debug(
                    "Unusable slot in program %s: %s", self._program, slot
                )

        return sorted(slots, key=lambda slot: slot["time"])

    @callback
    def _handle_coordinator_update(self) -> None:
        """Publish the program the poll just brought back."""
        self.async_write_ha_state()
