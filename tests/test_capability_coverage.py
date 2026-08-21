"""Coverage and wiring around the capability mapping.

Two failures worth guarding. A capability that arrives switched on floods the
device page for every user who owns the hardware, so the ones that describe the
API to itself have to stay off until someone asks for them. And a capability
whose name has no translation shows up as its raw key -- `available_system_modes`
in the UI -- which is the mistake anyone adding a capability makes once.

The translation check walks every id the mapping answers for, so a capability
added later is covered without anyone remembering to cover it.
"""

import io
import json
import re

import pytest

from custom_components.cozytouch.capability import (
    SELF_DESCRIBING_CAPABILITIES,
    get_capability_infos,
)
from custom_components.cozytouch.model import CozytouchDeviceType, get_model_infos

TRANSLATIONS = (
    "custom_components/cozytouch/strings.json",
    "custom_components/cozytouch/translations/en.json",
    "custom_components/cozytouch/translations/fr.json",
)

# Names that are deliberately raw: a capability whose meaning nobody has worked
# out yet is surfaced under its own number rather than under an invented label.
# They read as placeholders in the UI, which is the point, so they have no
# translation to find.
PLACEHOLDER = re.compile(r"^(Capability_|Temp_|Target )")

# A capability-id superset, so the walk below can reach every mapping branch
# rather than only the ids a single device happens to report.
EVERY_ID = frozenset(range(1, 400)) | frozenset(range(100000, 106000))


def names_the_mapping_produces():
    """Every entity name reachable from the capability mapping."""
    found = set()
    for modelId in (56, 76, 211, 235, 418, 557, 1457, 1641, 1734):
        infos = get_model_infos(modelId)
        if infos["type"] is CozytouchDeviceType.UNKNOWN:
            continue
        for capabilityId in EVERY_ID:
            result = get_capability_infos(infos, capabilityId, "0", EVERY_ID)
            if result and result.get("name"):
                found.add(result["name"])
                for extra in ("name_0", "name_1"):
                    if result.get(extra):
                        found.add(result[extra])
    return found


def translated_keys(path):
    with io.open(path, encoding="utf-8") as handle:
        entity = json.load(handle)["entity"]
    keys = set()
    for platform in entity.values():
        keys |= set(platform)
    return keys


@pytest.mark.parametrize("path", TRANSLATIONS)
def test_every_named_capability_has_a_translation(path):
    """Without one, Home Assistant shows the raw key to the user."""
    missing = {
        name
        for name in names_the_mapping_produces() - translated_keys(path)
        if not PLACEHOLDER.match(name)
    }

    assert not missing, f"{path} has no name for {sorted(missing)}"


@pytest.mark.parametrize("path", TRANSLATIONS[1:])
def test_the_translation_files_cover_the_same_keys(path):
    """A key added to one language and not the other is a silent gap."""
    reference = translated_keys(TRANSLATIONS[0])

    assert translated_keys(path) == reference


@pytest.mark.parametrize("capabilityId", sorted(SELF_DESCRIBING_CAPABILITIES))
def test_a_self_describing_capability_arrives_switched_off(capabilityId):
    """A device reports dozens of these; on by default they bury the rest."""
    infos = get_model_infos(557)

    result = get_capability_infos(infos, capabilityId, "0", {capabilityId})

    assert result["enabled_by_default"] is False
    assert result["name"] == SELF_DESCRIBING_CAPABILITIES[capabilityId]
    assert result["category"] == "diag"


def test_a_capability_that_says_nothing_is_enabled():
    """The flag is opt-in: only a capability that asks for it arrives off."""
    infos = get_model_infos(557)

    result = get_capability_infos(infos, 303, "0", {303})

    assert "enabled_by_default" not in result


def test_the_self_describing_table_does_not_shadow_a_real_mapping():
    """An id in the table that another branch claims first would never be read."""
    infos = get_model_infos(557)

    for capabilityId, name in SELF_DESCRIBING_CAPABILITIES.items():
        result = get_capability_infos(infos, capabilityId, "0", {capabilityId})
        assert result["name"] == name, (
            f"{capabilityId} resolves to {result['name']!r}, not {name!r}"
        )


@pytest.mark.parametrize("capabilityId", [162, 163])
def test_the_cooling_bounds_are_temperatures(capabilityId):
    infos = get_model_infos(557)

    result = get_capability_infos(infos, capabilityId, "18.0", {capabilityId})

    assert result["type"] == "temperature"
    assert result["enabled_by_default"] is False
