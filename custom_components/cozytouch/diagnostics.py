"""Diagnostics for the Atlantic Cozytouch integration.

What the API says about the account, one click away, with the account details
taken out. See docs/decisions.md.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .hub import CozytouchConfigEntry

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
    hass: HomeAssistant, entry: CozytouchConfigEntry
) -> dict[str, Any]:
    """Return what the API reports for this account, minus the account itself.

    One dump per account, covering every device the setup view returned.
    """
    runtime = entry.runtime_data

    # Any hub describes the whole account : what the dump flags as set up
    # here comes from the entry's subentries, not from the hub's own device.
    hub = next(iter(runtime.hubs.values()), None)

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
                "devices": {
                    subentry_id: subentry.data.get("deviceId")
                    for subentry_id, subentry in entry.subentries.items()
                },
            },
            "online": runtime.account.online,
            **(hub.get_diagnostics() if hub is not None else {}),
        },
        TO_REDACT,
    )
