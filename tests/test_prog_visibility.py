"""The per-day program sensors give way to the calendar that shows the week.

A device that reports a whole program block gets a calendar for it
(tests/test_calendar.py), and fourteen near-identical diagnostic rows next to
it said the same thing worse -- issue #42. Two halves make them step back, and
both are pinned here: the mapping ships the per-day sensors of a covered block
`enabled_by_default: False`, which only speaks when an entity is first
registered; and the 2.2 entry migration disables the ones an existing install
already registered -- exactly once, so a sensor somebody re-enables afterwards
stays re-enabled.

The whole-block rule gates both halves: a partial block builds no calendar,
and its per-day sensors stay its only view. No capture has ever shown a
partial block, so those cases are the seam's insurance rather than observed
behaviour. The blocks without a calendar at all -- the reduced milestones
(100320-100333) and the time ranges (245-251) -- must keep arriving enabled
for the same reason.

The migration is tested through fakes at the registry seam, the way
tests/test_topology.py fakes the device registry: what it reads is the entity
list of one config entry, and what it does is flip `disabled_by`.
"""

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.cozytouch import (
    _covered_prog_unique_ids,
    async_migrate_entry,
    sensor as sensor_platform,
)
from custom_components.cozytouch.capability import get_capability_infos
from custom_components.cozytouch.const import DOMAIN
from custom_components.cozytouch.infos import (
    CapabilityCategory,
    CapabilityInfos,
    CapabilityType,
)
from custom_components.cozytouch.model import get_model_infos
from homeassistant.helpers import entity_registry as er

SUBENTRY_ID = "sub-1"

HEATING = frozenset(range(196, 203))
COOLING = frozenset(range(203, 210))
HOT_WATER = frozenset(range(237, 244))


def block_uids(subentry_id, first):
    return {
        f"{DOMAIN}_{subentry_id}_{capabilityId}"
        for capabilityId in range(first, first + 7)
    }


# --- what the mapping declares ----------------------------------------------


@pytest.mark.parametrize("capabilityId", [196, 202, 203, 209])
def test_a_day_of_a_whole_block_arrives_disabled(capabilityId):
    """The calendar shows the block, so its fourteen rows step back."""
    infos = get_model_infos(557)

    result = get_capability_infos(infos, capabilityId, "0", HEATING | COOLING)

    assert result["enabled_by_default"] is False


def test_a_day_of_a_partial_block_stays_enabled():
    """Six days build no calendar, so the per-day sensors are the only view."""
    infos = get_model_infos(557)

    result = get_capability_infos(infos, 196, "0", HEATING - {202})

    assert "enabled_by_default" not in result


def test_each_block_is_gated_by_its_own_seven_days():
    """A complete cooling block next to a partial heating one: only the
    complete one steps back, whatever the other is missing.
    """
    infos = get_model_infos(557)
    available = (HEATING - {202}) | COOLING

    heating = get_capability_infos(infos, 196, "0", available)
    cooling = get_capability_infos(infos, 203, "0", available)

    assert "enabled_by_default" not in heating
    assert cooling["enabled_by_default"] is False


def test_a_whole_hot_water_block_arrives_disabled():
    infos = get_model_infos(557)

    result = get_capability_infos(infos, 237, "0", HOT_WATER)

    assert result["enabled_by_default"] is False


@pytest.mark.parametrize(
    ("capabilityId", "block_first"),
    [(100320, 100320), (100327, 100327), (245, 245)],
)
def test_a_block_no_calendar_covers_keeps_its_sensors_enabled(
    capabilityId, block_first
):
    """The milestones and the time ranges have no other view to give way to."""
    infos = get_model_infos(557)
    available = frozenset(range(block_first, block_first + 7))

    result = get_capability_infos(infos, capabilityId, "0", available)

    assert "enabled_by_default" not in result


# --- which registry entries the migration selects ---------------------------


def test_a_whole_registered_block_is_covered():
    existing = block_uids(SUBENTRY_ID, 196)

    assert _covered_prog_unique_ids({SUBENTRY_ID}, existing) == existing


def test_a_partial_block_is_not_covered_and_neither_is_anything_else():
    existing = (block_uids(SUBENTRY_ID, 196) - {f"{DOMAIN}_{SUBENTRY_ID}_202"}) | {
        f"{DOMAIN}_{SUBENTRY_ID}_40",
        f"{DOMAIN}_{SUBENTRY_ID}_102004",
    }

    assert _covered_prog_unique_ids({SUBENTRY_ID}, existing) == set()


def test_a_block_is_counted_per_subentry_not_across_them():
    """Six days on one device and the seventh on another is two partial
    blocks, not one whole one.
    """
    existing = (block_uids("sub-1", 196) - {f"{DOMAIN}_sub-1_202"}) | {
        f"{DOMAIN}_sub-2_202"
    }

    assert _covered_prog_unique_ids({"sub-1", "sub-2"}, existing) == set()


def test_every_subentry_contributes_its_own_blocks():
    existing = block_uids("sub-1", 196) | block_uids("sub-2", 237)

    assert _covered_prog_unique_ids({"sub-1", "sub-2"}, existing) == existing


def test_the_migration_flips_the_unique_ids_the_sensors_actually_claim():
    """The flip targets by exact unique_id, so the shape the migration builds
    and the shape the sensor platform claims must be the same string.
    """
    hub = SimpleNamespace(
        get_capabilities_for_device=lambda deviceId=None: [
            CapabilityInfos(
                capabilityId=196,
                name="prog_heating_monday",
                type=CapabilityType.PROG,
                category=CapabilityCategory.DIAG,
            )
        ],
        get_last_modification_date=lambda: None,
        get_last_poll=lambda: None,
    )
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(hubs={SUBENTRY_ID: hub}),
        subentries={
            SUBENTRY_ID: SimpleNamespace(data={"deviceId": 1}, title="Salon")
        },
        title="cozytouch@example.test",
        entry_id="entry123",
    )
    entities = []
    asyncio.run(
        sensor_platform.async_setup_entry(
            None,
            entry,
            lambda new, update_before_add, config_subentry_id=None: entities.extend(
                new
            ),
        )
    )

    (prog,) = entities
    assert prog.unique_id in _covered_prog_unique_ids(
        {SUBENTRY_ID}, block_uids(SUBENTRY_ID, 196)
    )


# --- the migration itself ---------------------------------------------------


def registered(unique_id, disabled_by=None):
    return SimpleNamespace(
        unique_id=unique_id,
        entity_id=f"sensor.{unique_id}",
        disabled_by=disabled_by,
    )


class FakeEntityRegistry:
    """Records which entities the migration disables."""

    def __init__(self):
        self.disabled = []

    def async_update_entity(self, entity_id, disabled_by):
        self.disabled.append((entity_id, disabled_by))


def migrate(monkeypatch, entry, entities):
    """Run async_migrate_entry over a scripted registry."""
    registry = FakeEntityRegistry()
    monkeypatch.setattr(er, "async_get", lambda hass: registry)
    monkeypatch.setattr(
        er, "async_entries_for_config_entry", lambda reg, entry_id: entities
    )
    bumps = []
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_update_entry=lambda entry, minor_version: bumps.append(
                minor_version
            )
        )
    )

    result = asyncio.run(async_migrate_entry(hass, entry))

    return result, registry, bumps


def make_entry(version=2, minor_version=1, subentry_ids=(SUBENTRY_ID,)):
    return SimpleNamespace(
        version=version,
        minor_version=minor_version,
        entry_id="entry123",
        subentries={subentry_id: SimpleNamespace() for subentry_id in subentry_ids},
    )


def test_the_migration_disables_a_covered_block_and_bumps_the_entry(monkeypatch):
    entities = [registered(uid) for uid in sorted(block_uids(SUBENTRY_ID, 196))]
    entities.append(registered(f"{DOMAIN}_{SUBENTRY_ID}_40"))

    result, registry, bumps = migrate(monkeypatch, make_entry(), entities)

    assert result is True
    assert bumps == [2]
    assert sorted(registry.disabled) == [
        (f"sensor.{uid}", er.RegistryEntryDisabler.INTEGRATION)
        for uid in sorted(block_uids(SUBENTRY_ID, 196))
    ]


def test_a_sensor_the_user_already_disabled_keeps_saying_user(monkeypatch):
    """Flipping USER to INTEGRATION would rewrite who made that choice."""
    uids = sorted(block_uids(SUBENTRY_ID, 196))
    entities = [registered(uids[0], disabled_by=er.RegistryEntryDisabler.USER)]
    entities += [registered(uid) for uid in uids[1:]]

    _, registry, _ = migrate(monkeypatch, make_entry(), entities)

    assert f"sensor.{uids[0]}" not in [entity_id for entity_id, _ in registry.disabled]
    assert len(registry.disabled) == 6


def test_an_entry_already_at_2_2_is_left_alone(monkeypatch):
    """The one-shot promise: somebody who re-enabled a sensor after the
    migration must never find it disabled again on the next start.
    """
    entities = [registered(uid) for uid in block_uids(SUBENTRY_ID, 196)]

    result, registry, bumps = migrate(
        monkeypatch, make_entry(minor_version=2), entities
    )

    assert result is True
    assert registry.disabled == []
    assert bumps == []


def test_a_version_1_entry_still_asks_to_be_added_again(monkeypatch):
    """v1 landing in MIGRATION_ERROR is documented behaviour, not a gap this
    migration is allowed to close by accident.
    """
    result, registry, bumps = migrate(monkeypatch, make_entry(version=1), [])

    assert result is False
    assert registry.disabled == []
    assert bumps == []
