"""Services for the Atlantic Cozytouch integration."""

from __future__ import annotations

from datetime import datetime
import json
import logging
import operator

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .hub import AWAY_START_DELAY_DELTA, DEFAULT_AWAY_DURATION_DELTA

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_CLEAR_AWAY_MODE = "clear_away_mode"

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

# The device always stores ten slots, unused ones being [0,0].
MAX_SLOTS = 10

SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_ids,
        vol.Required("program"): vol.In(PROGRAM_FIRST_CAPABILITY),
        vol.Required("days"): vol.All(
            cv.ensure_list, [vol.In(DAYS)], vol.Length(min=1)
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

    return capability["capabilityId"], str(temperature)


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
        value = _build_matrix(call.data["slots"])
        first = PROGRAM_FIRST_CAPABILITY[call.data["program"]]

        for entity_id in call.data["entity_id"]:
            hub = _resolve_hub(hass, entity_id)
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
