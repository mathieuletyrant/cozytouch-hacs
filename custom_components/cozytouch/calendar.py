"""Calendars for Atlantic Cozytouch integration."""

from __future__ import annotations

from datetime import datetime, time, timedelta
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PROGRAM_BLOCKS, program_block
from .hub import CozytouchConfigEntry, CozytouchDeviceEntity, Hub
from .services import parse_slots

_LOGGER = logging.getLogger(__name__)

# How far either side of now to look when answering "what is running", which
# is a day each way rather than from midnight. See docs/decisions.md.
CURRENT_EVENT_WINDOW = timedelta(days=1)


# config flow setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
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

    All seven rather than any. See docs/decisions.md.
    """
    return all(
        hub.get_capability_value(capabilityId, None) is not None
        for capabilityId in program_block(first)
    )


class CozytouchProgramCalendar(CozytouchDeviceEntity, CalendarEntity):
    """A weekly program, as the week it actually is.

    Read-only : writing a slot is `set_schedule`'s job. See docs/decisions.md.
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
        # The service's words for these blocks, so one vocabulary covers all
        # three. See docs/decisions.md.
        self._attr_translation_key = f"{program}_program"
        self._attr_unique_id = f"{DOMAIN}_{config_uniq_id}_{program}_program"

    @property
    def event(self) -> CalendarEvent | None:
        """The setpoint the program is holding right now."""
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

        Each slot becomes an event running until the next one, or until
        midnight for the last of a day. Local time throughout. See
        docs/decisions.md.
        """
        zone = dt_util.DEFAULT_TIME_ZONE
        day = dt_util.as_local(start_date).date()
        last = dt_util.as_local(end_date).date()

        # Once, not once per date : a card can ask for a year.
        programs = [self._slots_for(weekday) for weekday in range(7)]

        events: list[CalendarEvent] = []
        while day <= last:
            slots = programs[day.weekday()]
            for index, slot in enumerate(slots):
                start = datetime.combine(day, slot["time"], tzinfo=zone)

                if index + 1 < len(slots):
                    end = datetime.combine(day, slots[index + 1]["time"], tzinfo=zone)
                else:
                    # Held until the day runs out. See docs/decisions.md.
                    end = datetime.combine(
                        day + timedelta(days=1), time(0, 0), tzinfo=zone
                    )

                # Overlapping, not contained. See docs/decisions.md.
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
        """One day's slots, in time order, as times rather than strings."""
        capabilityId = self._first_capability + weekday
        stored = self.coordinator.get_capability_value(capabilityId, None)

        slots = []
        for slot in parse_slots(stored, capabilityId):
            try:
                hours, minutes = (int(part) for part in slot["time"].split(":"))
                slots.append(
                    {
                        "time": time(hours, minutes),
                        # A float here so a string setpoint raises here and
                        # not in the summary. See docs/decisions.md.
                        "temperature": float(slot["temperature"]),
                    }
                )
            except (TypeError, ValueError):
                # Dropped, so the rest of the day still renders.
                _LOGGER.debug(
                    "Unusable slot in program %s: %s", self._program, slot
                )

        return sorted(slots, key=lambda slot: slot["time"])

    @callback
    def _handle_coordinator_update(self) -> None:
        """Publish the program the poll just brought back."""
        self.async_write_ha_state()
