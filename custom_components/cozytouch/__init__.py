"""The Atlantic Cozytouch integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from . import hub
from .const import DOMAIN
from .hub import CozytouchConfigEntry
from .services import async_register_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.DATETIME,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _setting(entry: ConfigEntry, key: str) -> bool:
    """Read a setting, options first since that is where the options flow writes."""
    return entry.options.get(key, entry.data.get(key, False))


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload so the new options are picked up."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: CozytouchConfigEntry) -> bool:
    """Set up Atlantic Cozytouch from a config entry."""
    theHub = hub.Hub(
        hass,
        entry.data["username"],
        entry.data["password"],
        entry.data["deviceId"],
        config_entry=entry,
    )

    theHub.set_dump_json(_setting(entry, "dump_json"))
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    async_register_services(hass)

    await theHub.connect()
    if not theHub.online:
        # HA discards this hub and builds a new one on each retry, so release the
        # aiohttp session here or every attempt leaks one
        await theHub.close()
        # tells HA to retry setup with exponential backoff until the network is available
        raise ConfigEntryNotReady("Cannot connect to Atlantic Cozytouch API")

    entry.runtime_data = theHub

    theHub.set_create_entities_for_unknown_entities(_setting(entry, "create_unknown"))
    try:
        # raises ConfigEntryNotReady if the first poll fails, which also gets us
        # a retry -- but only if we hand the session back first
        await theHub.async_config_entry_first_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        # HA does not call async_unload_entry when setup fails, so the session
        # has to be released here or the retry leaks it
        await theHub.close()
        raise

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CozytouchConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # a reload builds a brand new hub, so the old session has to go with it
        await entry.runtime_data.close()

    return unload_ok
