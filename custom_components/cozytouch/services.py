"""Services for the Atlantic Cozytouch integration."""

from __future__ import annotations

import json
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_SCHEDULE = "set_schedule"

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

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SCHEDULE, async_set_schedule, schema=SET_SCHEDULE_SCHEMA
    )
