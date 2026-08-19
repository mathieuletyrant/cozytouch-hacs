"""Diagnostics for the Atlantic Cozytouch integration.

Every unsupported device starts the same way: someone has hardware nobody has
mapped, and the only way to map it is to see what the API says about it. Asking
for that by hand costs the reporter an option to tick, a log file to find and a
JSON to redact, and it is where most reports stop.

This is the same information, one click away from the integration page, with
the account details already taken out.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hub import Hub

# Credentials, and everything that would place the account at an address.
TO_REDACT = {
    "username",
    "password",
    "address",
    "formattedAddress",
    "latitude",
    "longitude",
    "locality",
    "postalCode",
    "gatewaySerialNumber",
    "serialNumber",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return what the API reports for this account, minus the account itself."""
    hub: Hub = hass.data[DOMAIN][entry.entry_id]

    return async_redact_data(
        {
            "entry": {
                "options": dict(entry.options),
                # data carries the credentials; only the non-secret keys are useful.
                "data": {
                    key: value
                    for key, value in entry.data.items()
                    if key not in ("username", "password")
                },
            },
            "online": hub.online,
            **hub.get_diagnostics(),
        },
        TO_REDACT,
    )
