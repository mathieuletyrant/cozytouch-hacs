"""Services for the Atlantic Cozytouch integration."""

from __future__ import annotations

from datetime import datetime
import json
import logging
import operator
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .hub import AWAY_START_DELAY_DELTA, DEFAULT_AWAY_DURATION_DELTA

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_CLEAR_AWAY_MODE = "clear_away_mode"
SERVICE_GET_SCHEDULE = "get_schedule"

# A weekly program is seven consecutive capabilities, one per day starting on
# monday. Heating and cooling are two separate blocks; the Cozytouch app calls
# them "Chauffage" and "Refroidissement".
PROGRAM_FIRST_CAPABILITY = {"heating": 196, "cooling": 203}

DAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

# Shortcuts the day picker offers next to the seven days. Expanded here rather
# than in the frontend, so a YAML automation gets them too.
DAY_GROUPS = {
    "all": DAYS,
    "weekdays": DAYS[:5],
    "weekend": DAYS[5:],
}

# The device always stores ten slots, unused ones being [0,0].
MAX_SLOTS = 10

# The device advertises how many slots a day may hold. Its encoding has never
# been confirmed against a capture, so it is only ever allowed to tighten the
# check, never to change the matrix that gets written.
SLOTS_PER_DAY_CAPABILITY = 306


def _expand_days(days: list[str]) -> list[str]:
    """Turn the group shortcuts into the days they stand for.

    Runs as the last step of the validator so that everything downstream only
    ever sees a day name, and so "weekend" plus "sunday" -- or "monday" twice
    -- still writes each capability once.
    """
    named = {day for item in days for day in DAY_GROUPS.get(item, [item])}
    return [day for day in DAYS if day in named]


SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("program"): vol.In(PROGRAM_FIRST_CAPABILITY),
        # vol.All is a pipeline, so the length check has to run before the
        # expansion -- afterwards a group has already become several days,
        # and an empty list is the only thing left that it could catch.
        vol.Required("days"): vol.All(
            cv.ensure_list,
            vol.Length(min=1),
            [vol.In([*DAYS, *DAY_GROUPS])],
            _expand_days,
        ),
        vol.Required("slots"): vol.All(
            cv.ensure_list,
            vol.Length(min=1, max=MAX_SLOTS),
            [
                vol.Schema(
                    {
                        vol.Required("time"): cv.time,
                        vol.Required("temperature"): vol.Coerce(float),
                    }
                )
            ],
        ),
    }
)

GET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("program"): vol.In(PROGRAM_FIRST_CAPABILITY),
    }
)


SET_AWAY_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Optional("start"): cv.datetime,
        # One end, said one way. `end` for "back on sunday", `duration` for
        # "for ten days" -- which is the one an automation can compute, and the
        # reason this service exists at all.
        vol.Exclusive("end", "away_window_end"): cv.datetime,
        vol.Exclusive("duration", "away_window_end"): cv.positive_time_period,
        vol.Optional("temperature"): vol.Coerce(float),
    }
)

CLEAR_AWAY_MODE_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.entity_ids})


def _away_window(data: dict) -> tuple[int | None, int | None]:
    """The pair of epochs to write, from whichever way the call said it.

    A call that says nothing at all gets `(None, None)`, which is how the hub
    is asked for its own default window -- so "away from now until further
    notice" does not need a start computed here as well as there.

    Naive datetimes are read in Home Assistant's zone, which is what
    `dt_util.as_utc` does with one, and an epoch is absolute from then on. That
    is why this path cannot pick up the double offset the away timestamp
    *sensor* has (docs/architecture.md records it).
    """
    start, end, duration = (
        data.get("start"),
        data.get("end"),
        data.get("duration"),
    )
    if start is None and end is None and duration is None:
        return None, None

    if start is None:
        start = datetime.now(tz=dt_util.DEFAULT_TIME_ZONE) + AWAY_START_DELAY_DELTA

    if end is None:
        if duration is None:
            duration = DEFAULT_AWAY_DURATION_DELTA
        end = start + duration

    start, end = dt_util.as_utc(start), dt_util.as_utc(end)
    if end <= start:
        raise ServiceValidationError(
            f"The away window would end before it starts ({start} -> {end})"
        )

    # The hub substitutes its default for a window that is already over, which
    # is right for the switch offering back a stale staged pair and wrong here:
    # a call that named a date said it out loud, and silently getting a
    # different window is worse than being told the date has passed.
    if end <= dt_util.utcnow():
        raise ServiceValidationError(f"The away window ended in the past ({end})")

    return int(start.timestamp()), int(end.timestamp())


def _away_temperature(hub, temperature: float) -> tuple[int, str]:
    """The capability to write an absence setpoint to, and the value for it.

    Refused rather than clamped, unlike the number entity: a service call said
    a number out loud, and writing a different one silently is worse than
    saying it does not fit.
    """
    capability = hub.get_away_mode_temperature_capability()
    if capability is None:
        raise ServiceValidationError(
            "This device has no absence setpoint. Air conditioners report one "
            "and never act on it, so the integration does not offer it there"
        )

    for key, compare, wording in (
        ("lowestValueCapabilityId", operator.lt, "below"),
        ("highestValueCapabilityId", operator.gt, "above"),
    ):
        capabilityId = capability.get(key)
        if capabilityId is None:
            continue

        try:
            bound = float(hub.get_capability_value(capabilityId))
        except (TypeError, ValueError):
            # The device did not say, so nothing here can rule the value out.
            continue

        if compare(temperature, bound):
            raise ServiceValidationError(
                f"{temperature} °C is {wording} what this device accepts "
                f"({bound} °C)"
            )

    return capability.capabilityId, str(temperature)


def _build_matrix(slots: list[dict]) -> str:
    """Turn slots into the [[minutes,temperature],...] string the device stores."""
    entries = sorted(
        (
            (slot["time"].hour * 60 + slot["time"].minute, slot["temperature"])
            for slot in slots
        ),
        key=lambda entry: entry[0],
    )

    minutes = [entry[0] for entry in entries]
    # Unreachable through the service, which requires one slot, but reachable
    # from anything else that calls this: minutes[0] below is indexed blind.
    if not minutes:
        raise ServiceValidationError("A day program needs at least one slot")

    if len(set(minutes)) != len(minutes):
        raise ServiceValidationError("Two slots share the same time")

    if minutes[0] != 0:
        raise ServiceValidationError(
            "The first slot must start at 00:00, otherwise the beginning of the "
            "day would have no target temperature"
        )

    matrix = [
        [minute, int(temperature) if temperature == int(temperature) else temperature]
        for minute, temperature in entries
    ]
    matrix += [[0, 0]] * (MAX_SLOTS - len(matrix))

    return json.dumps(matrix, separators=(",", ":"))


def parse_slots(value: str | None) -> list[dict]:
    """Read a stored program back into the slots set_schedule takes.

    Public because calendar.py reads programs through it too: one reading of
    the stored matrix, so a calendar and `get_schedule` cannot disagree about
    what a day holds.

    The device pads the unused slots with [0,0], and padding runs to the end of
    the matrix, so a pair of zeroes ends the day. A real slot at midnight
    carries a target temperature, never 0 °C, which is what tells the two apart
    -- the same rule the prog sensors already read by.
    """
    try:
        entries = json.loads(value)
    except (TypeError, ValueError):
        return []

    if not isinstance(entries, list):
        return []

    slots: list[dict] = []
    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 2:
            continue

        minute, temperature = entry[0], entry[1]
        if minute == 0 and temperature == 0:
            break

        hours, minutes = divmod(int(minute), 60)
        slots.append({"time": f"{hours:02d}:{minutes:02d}", "temperature": temperature})

    return slots


def _slot_limit(hub) -> int:
    """How many slots a day may hold on this device.

    Capability 306 is self-describing and its encoding is unverified, so it is
    trusted only when it reads as a plain count, and only to lower the ceiling.
    Anything else leaves the ten slots every working install writes today.
    """
    value = hub.get_capability_value(SLOTS_PER_DAY_CAPABILITY, None)

    try:
        limit = int(value)
    except (TypeError, ValueError):
        return MAX_SLOTS

    if limit < 2:
        return MAX_SLOTS

    return min(limit, MAX_SLOTS)


def _resolve_hub(hass: HomeAssistant, entity_id: str):
    """Find the hub behind an entity."""
    registry_entry = er.async_get(hass).async_get(entity_id)
    if registry_entry is None:
        raise ServiceValidationError(
            f"There is no entity called {entity_id}. Check the exact id in "
            "Developer tools > States -- renaming an entity does not change it."
        )

    # Two separate things to rule out, which the old hass.data lookup conflated:
    # an entity from another integration, and one of ours whose entry is not
    # loaded and therefore has no hub on it yet.
    entry = hass.config_entries.async_get_entry(registry_entry.config_entry_id or "")
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            f"{entity_id} is provided by {registry_entry.platform}, not by "
            "Cozytouch"
        )

    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            f"The Cozytouch entry behind {entity_id} is not loaded ({entry.state})"
        )

    # A device is a subentry of its account, and the hub that drives it is
    # keyed on that subentry. An entity with no subentry is one this
    # integration did not build under the shape it builds them today.
    hub = entry.runtime_data.hubs.get(registry_entry.config_subentry_id or "")
    if hub is None:
        raise ServiceValidationError(
            f"{entity_id} is not attached to a Cozytouch device this entry "
            "drives; remove it and add the device again"
        )

    return hub


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register the integration services, once for all config entries."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_SCHEDULE):
        return

    async def async_set_schedule(call: ServiceCall) -> None:
        """Write the same day program to every requested day."""
        slots = call.data["slots"]
        value = _build_matrix(slots)
        first = PROGRAM_FIRST_CAPABILITY[call.data["program"]]

        for entity_id in call.data["entity_id"]:
            hub = _resolve_hub(hass, entity_id)

            limit = _slot_limit(hub)
            if len(slots) > limit:
                raise ServiceValidationError(
                    f"{entity_id} holds {limit} slots a day at most, "
                    f"{len(slots)} were given"
                )

            for day in call.data["days"]:
                capabilityId = first + DAYS.index(day)
                _LOGGER.debug(
                    "set_schedule %s %s %s -> capability %d = %s",
                    entity_id,
                    call.data["program"],
                    day,
                    capabilityId,
                    value,
                )
                await hub.set_capability_value(capabilityId, value)

            await hub.async_request_refresh()

    async def async_set_away_mode(call: ServiceCall) -> None:
        """Open an absence window on every requested device, in one call each.

        This is the door the pieces were missing. Everything it needs already
        existed -- the PUT that puts the window on the setup, the mirror into
        the device capability, the mode flag -- but the only way in was to edit
        two datetime entities, wait out a 20-second debounce and then tick a
        switch, which is not something an automation can do. "When the last
        person leaves for more than two days" is one call now.
        """
        start, end = _away_window(call.data)
        temperature = call.data.get("temperature")

        for entity_id in call.data["entity_id"]:
            hub = _resolve_hub(hass, entity_id)

            # The setpoint first, so the window does not open on the old one.
            if temperature is not None:
                capabilityId, value = _away_temperature(hub, temperature)
                await hub.set_capability_value(capabilityId, value)

            _LOGGER.debug("set_away_mode %s -> %s -> %s", entity_id, start, end)
            if not await hub.start_away_mode(start, end):
                raise ServiceValidationError(
                    f"The device behind {entity_id} does not report an away mode"
                )

            await hub.async_request_refresh()

    async def async_clear_away_mode(call: ServiceCall) -> None:
        """Close the window and take the device off away mode.

        The pair of Nones is what the hub reads as "no window": it writes
        `[0,0]` to the timestamps capability and clears the absence on the
        setup, the same thing turning the switch off does.
        """
        for entity_id in call.data["entity_id"]:
            hub = _resolve_hub(hass, entity_id)
            if not await hub.stop_away_mode():
                raise ServiceValidationError(
                    f"The device behind {entity_id} does not report an away mode"
                )

            await hub.async_request_refresh()
    async def async_get_schedule(call: ServiceCall) -> ServiceResponse:
        """Read a whole week back, in the shape set_schedule takes."""
        program = call.data["program"]
        first = PROGRAM_FIRST_CAPABILITY[program]

        response: dict[str, Any] = {}
        for entity_id in call.data["entity_id"]:
            hub = _resolve_hub(hass, entity_id)

            days = {}
            for index, day in enumerate(DAYS):
                # The default is the string "0", which parses as a number
                # rather than a matrix; None is what makes a device that does
                # not have this program tellable from one whose day is empty.
                value = hub.get_capability_value(first + index, None)
                if value is not None:
                    days[day] = parse_slots(value)

            if not days:
                raise ServiceValidationError(
                    f"{entity_id} reports no {program} program: it has none of "
                    f"capabilities {first} to {first + 6}"
                )

            response[entity_id] = {"program": program, "days": days}

        return response

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SCHEDULE, async_set_schedule, schema=SET_SCHEDULE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_AWAY_MODE, async_set_away_mode, schema=SET_AWAY_MODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_AWAY_MODE,
        async_clear_away_mode,
        schema=CLEAR_AWAY_MODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SCHEDULE,
        async_get_schedule,
        schema=GET_SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
