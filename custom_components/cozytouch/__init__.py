"""The Atlantic Cozytouch integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from .account import CozytouchAccount
from .const import DOMAIN
from .hub import CozytouchConfigEntry, CozytouchRuntimeData, Hub
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


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload so new options -- or a device added or removed -- are picked up.

    Home Assistant fires the update listeners for a subentry change as well as
    for an options change, which is what builds the hub for a device somebody
    just added without asking them to reload by hand.
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: CozytouchConfigEntry) -> bool:
    """Set up Atlantic Cozytouch from a config entry."""
    account = CozytouchAccount(hass, entry.data["username"], entry.data["password"])
    account.set_dump_json(_setting(entry, "dump_json"))

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    async_register_services(hass)

    # ConfigEntryNotReady tells HA to retry with exponential backoff until the
    # network is back; a refused password comes out of here as
    # ConfigEntryAuthFailed instead, which asks for a new one rather than
    # retrying the old one until somebody goes looking.
    if not await account.connect_or_auth_failed():
        raise ConfigEntryNotReady("Cannot connect to Atlantic Cozytouch API")

    create_unknown = _setting(entry, "create_unknown")
    hubs: dict[str, Hub] = {}
    for subentry_id, subentry in entry.subentries.items():
        hub = Hub(
            hass,
            account,
            subentry.data["deviceId"],
            config_entry=entry,
            subentry_id=subentry_id,
        )
        hub.set_create_entities_for_unknown_entities(create_unknown)
        hubs[subentry_id] = hub

    entry.runtime_data = CozytouchRuntimeData(account, hubs)

    # The setup view has already filled in a capability list for every device,
    # so the entities can be built from what it said. Each hub's first poll
    # only refreshes values -- one device failing it leaves that device's
    # entities stale rather than taking the whole account down, which is what
    # a first refresh that raises would do to its four siblings.
    #
    # One at a time on purpose: the account declares a rateLimit nothing
    # decodes, and firing one request per device at once is the shape most
    # likely to meet it.
    for hub in hubs.values():
        await hub.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Once the devices are loaded, and only for a setup that got this far:
    # an unmapped model is worth a word to the user, a failed setup is not.
    async_check_model_mapping(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CozytouchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
