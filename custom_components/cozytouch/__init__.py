"""The Atlantic Cozytouch integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from .account import CozytouchAccount
from .const import DOMAIN
from .hub import CozytouchConfigEntry, Hub
from .repairs import async_check_model_mapping
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
    account = CozytouchAccount(
        hass, entry.data["username"], entry.data["password"]
    )
    account.set_dump_json(_setting(entry, "dump_json"))

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    async_register_services(hass)

    if not await account.connect():
        # tells HA to retry setup with exponential backoff until the network
        # is available
        raise ConfigEntryNotReady("Cannot connect to Atlantic Cozytouch API")

    theHub = Hub(hass, account, entry.data["deviceId"], config_entry=entry)
    entry.runtime_data = theHub

    theHub.set_create_entities_for_unknown_entities(_setting(entry, "create_unknown"))
    # raises ConfigEntryNotReady if the first poll fails, which gets us a retry
    await theHub.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Once the devices are loaded, and only for a setup that got this far:
    # an unmapped model is worth a word to the user, a failed setup is not.
    async_check_model_mapping(hass, entry, theHub)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CozytouchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
