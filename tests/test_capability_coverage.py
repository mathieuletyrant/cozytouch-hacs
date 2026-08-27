"""Coverage and wiring around the capability mapping.

Two failures worth guarding. A capability that arrives switched on floods the
device page for every user who owns the hardware, so the ones that describe the
API to itself have to stay off until someone asks for them. And a capability
whose name has no translation shows up as its raw key -- `available_system_modes`
in the UI -- which is the mistake anyone adding a capability makes once.

A third failure is the wiring itself. A platform picks its entities out of the
capability list by type, and a type on one side of that match and not the other
is silent both ways: a mapping nothing consumes produces no entity, and a
platform waiting for a type nothing produces sets up nothing at all. Two lived
here -- `time_adjustment` in time.py and `power` in sensor.py -- and the
categories have the same shape, since sensor.py reads two spellings and gives
anything else no category.

The checks walk every id the mapping answers for, so a capability added later is
covered without anyone remembering to cover it.
"""

import json
import pathlib
import re

import pytest

from custom_components.cozytouch.capability import (
    SELF_DESCRIBING_CAPABILITIES,
    get_capability_infos,
)
from custom_components.cozytouch.infos import CapabilityType
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


# One per device class, so a branch that only a boiler or only an air
# conditioner reaches is still walked.
MODEL_IDS = (56, 76, 211, 235, 418, 557, 1457, 1641, 1734)

# The platforms that pick their entities out of the capability list by type.
# binary_sensor.py is not one of them: it owns the single cloud-connectivity
# entity and never looks at a capability.
PLATFORMS = (
    "climate.py",
    "datetime.py",
    "number.py",
    "select.py",
    "sensor.py",
    "switch.py",
)

# `capability.type == CapabilityType.X` and `capability.type in
# (CapabilityType.X, CapabilityType.Y)`, the two ways a platform states which
# type it was written for. The member is resolved to its value, so a name the
# enum does not declare fails here rather than matching nothing at runtime.
TYPE_TEST = re.compile(
    r"capability\.type\s*(?:== CapabilityType\.(\w+)|in \(([^)]*)\))"
)

# What sensor.py turns into an EntityCategory, plus the "sensor" that means no
# category at all. Anything else it silently drops on the floor.
CATEGORIES = frozenset({"sensor", "diag", "config"})


def capabilities_the_mapping_produces():
    """Every capability dict reachable from the mapping, across device classes."""
    for modelId in MODEL_IDS:
        infos = get_model_infos(modelId)
        if infos["type"] is CozytouchDeviceType.UNKNOWN:
            continue
        for capabilityId in EVERY_ID:
            result = get_capability_infos(infos, capabilityId, "0", EVERY_ID)
            if result:
                yield result


def names_the_mapping_produces():
    """Every entity name reachable from the capability mapping."""
    found = set()
    for result in capabilities_the_mapping_produces():
        if result.get("name"):
            found.add(result["name"])
            for entity in result.get("timestamps", ()):
                found.add(entity.name)
    return found


def types_the_mapping_produces():
    """Each type the mapping puts on a capability for a platform to match."""
    return {
        result["type"]
        for result in capabilities_the_mapping_produces()
        if "type" in result
    }


def types_the_platforms_consume():
    """Each type a platform matches on, and which platforms match on it."""
    consumed: dict[str, set[str]] = {}
    for platform in PLATFORMS:
        source = pathlib.Path("custom_components/cozytouch", platform).read_text(
            encoding="utf-8"
        )
        for single, group in TYPE_TEST.findall(source):
            members = (
                [single] if single else re.findall(r"CapabilityType\.(\w+)", group)
            )
            for member in members:
                consumed.setdefault(CapabilityType[member].value, set()).add(platform)
    return consumed


def translated_keys(path):
    with open(path, encoding="utf-8") as handle:
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


def test_the_walk_finds_the_platforms_and_the_types_they_match_on():
    """A sanity floor: the regex above found the dispatch, not an empty file."""
    consumed = types_the_platforms_consume()

    assert consumed["climate"] == {"climate.py", "sensor.py"}
    assert len(consumed) > 15


def test_every_type_the_mapping_produces_reaches_a_platform():
    """A type nothing consumes is a capability mapped into no entity at all."""
    assert not types_the_mapping_produces() - set(types_the_platforms_consume())


def test_no_platform_waits_for_a_type_nothing_produces():
    """The other direction: a platform that sets up nothing, and says nothing.

    time.py was written around a `time_adjustment` the mapping never produced,
    so the time platform created no entity on any device and the durations
    stayed read-only. sensor.py held a `power` branch the same way, and that one
    would have raised on the first device to reach it: it passed a keyword
    CozytouchUnitSensor does not take.
    """
    assert not set(types_the_platforms_consume()) - types_the_mapping_produces()


def test_every_category_the_mapping_produces_is_one_the_entities_read():
    """sensor.py tests for "diag"; "diagnostic" reads as no category at all."""
    produced = {
        result["category"]
        for result in capabilities_the_mapping_produces()
        if "category" in result
    }

    assert not produced - CATEGORIES
