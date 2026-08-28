"""The Atlantic Cozytouch integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv

from .account import CozytouchAccount
from .const import DOMAIN, PROGRAM_BLOCKS
from .hub import (
    AccountCoordinator,
    CozytouchConfigEntry,
    CozytouchRuntimeData,
    Hub,
    device_info_for,
)
from .repairs import async_check_model_mapping
from .services import async_register_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
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


def _register_devices(
    device_registry: dr.DeviceRegistry,
    entry: CozytouchConfigEntry,
    hubs: dict[str, Hub],
) -> None:
    """Create every subentry's device before any platform needs it.

    Gateways first: the children's via_device points at them, and the registry
    only honours a link to a device it already holds.
    """
    for subentry_id, hub in sorted(
        hubs.items(), key=lambda item: item[1].get_via_device() is not None
    ):
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=subentry_id,
            **device_info_for(hub, subentry_id),
        )


def _covered_prog_unique_ids(
    subentry_ids, existing_unique_ids: set[str]
) -> set[str]:
    """The per-day program sensors whose whole block is in the registry.

    What is in the registry mirrors what the device reported when the entities
    were built, so the calendar's whole-block condition can be checked without
    the API: a complete block has a calendar and its per-day sensors are
    duplicates, a partial one has no calendar and they stay its only view.
    """
    covered: set[str] = set()
    for subentry_id in subentry_ids:
        for first in PROGRAM_BLOCKS.values():
            block = {
                f"{DOMAIN}_{subentry_id}_{capabilityId}"
                for capabilityId in range(first, first + 7)
            }
            if block <= existing_unique_ids:
                covered |= block

    return covered


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Bring a stored entry up to the current minor version.

    A version 1 entry keeps landing in MIGRATION_ERROR, as it always has:
    its one-entry-per-device shape is not understood and asking for the
    device to be added again is the migration. See config_flow.VERSION.

    2.2 disables the per-day program sensors a calendar makes redundant.
    Once, not per start: enabled_by_default only speaks at first
    registration, and somebody who re-enables a sensor afterwards must
    never find it disabled again. INTEGRATION and not USER, so the UI says
    who did it -- and a sensor the user already disabled keeps saying USER.
    """
    if entry.version != 2:
        return False

    if entry.minor_version < 2:
        registry = er.async_get(hass)
        by_unique_id = {
            entity.unique_id: entity
            for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        for unique_id in _covered_prog_unique_ids(
            entry.subentries, set(by_unique_id)
        ):
            entity = by_unique_id[unique_id]
            if entity.disabled_by is None:
                registry.async_update_entity(
                    entity.entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                )

        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


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

    coordinator = AccountCoordinator(hass, account, entry, hubs)
    entry.runtime_data = CozytouchRuntimeData(account, hubs, coordinator)

    # One refresh for the account where there used to be one per device, and
    # the setup view `connect()` just read has already filled in a capability
    # list for every one of them -- so this publishes what is there rather than
    # fetching it again.
    #
    # async_refresh, not async_config_entry_first_refresh : the entities are
    # built from those capabilities, so a poll that fails leaves values stale
    # instead of failing a setup that already has what it needs.
    await coordinator.async_refresh()

    # Before the platforms, not as a side effect of their first entity: a
    # child's via_device has to name a device that already exists, and the
    # platforms run concurrently. See docs/decisions.md.
    _register_devices(dr.async_get(hass), entry, hubs)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Once the devices are loaded, and only for a setup that got this far:
    # an unmapped model is worth a word to the user, a failed setup is not.
    async_check_model_mapping(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CozytouchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
