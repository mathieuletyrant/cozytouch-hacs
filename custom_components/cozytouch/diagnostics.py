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

    One dump per account now, and it covers every device the setup view
    returned -- the ones added as subentries and the ones nobody added. That
    used to take one dump per device, which is a file per device to find,
    download and attach for a report that needed all of them.
    """
    runtime = entry.runtime_data

    # Any hub describes the whole account, and the dump does not depend on
    # which one is asked : what it flags as set up here comes from the entry's
    # subentries, not from the hub's own device.
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
