"""Snapshot of everything the two tables answer.

The other test files pin the cases somebody thought about. This one pins the
rest: every model id the table maps, and every capability id the chain claims,
against one model of each device type -- the same probes as
scripts/dump_capability_map.py. The point is to make a pure refactor provable:
if the snapshot files do not change, neither did a single answer.

Like every test here it is characterisation, not specification. Regenerate on
purpose, in the same commit as the change the diff shows:

    UPDATE_SNAPSHOTS=1 pytest tests/test_snapshot.py

Sets are stored sorted and dict keys as strings, because the snapshot lives as
JSON; the comparison happens on the JSON side of that round trip.
"""

import json
import os
import pathlib

import pytest

from custom_components.cozytouch.capability import get_capability_infos
from custom_components.cozytouch.model import CozytouchDeviceType, get_model_infos

SNAPSHOT_DIR = pathlib.Path(__file__).parent / "snapshots"

# The whole span test_capability.py walks, so a model added inside it joins
# the snapshot on its own.
MODEL_ID_RANGE = range(1, 2500)

# Names change what the table answers: a zone is recognised by deviceName
# before any id, and the air conditioner branches print zoneName into the
# entity name. One case per naming path, plus the unknown fall-through.
NAMED_MODEL_CASES = (
    (999999, None, None),
    (1505, None, "THZONE_0"),
    (1505, "Salon", "THZONE_0"),
    (557, "Salon", None),
    (1734, "Salon", None),
    (562, "Salon", None),
)

# One model per device type plus the ids whose branch differs from their
# type's probe -- kept in step with scripts/dump_capability_map.py, which
# explains each pick.
PROBE_MODELS = (56, 211, 418, 1641, 1381, 557, 562, 1457, 1505, 999999, 76, 1734, 2374)
ZONE_PROBE_MODEL = 1505
ZONE_PROBE_NAME = "THZONE_0"

# Where the vendor puts the capability ids: a low block below 400 and a high
# block from 100000.
EVERY_ID = sorted(set(range(1, 400)) | set(range(100000, 106000)))

# Ids that answer on their own value -- 119 rejects the no-probe sentinel.
VALUES = {119: "12.0", 172: "20.0"}

# The climate branch is the only reader of availableCapabilityIds, wiring an
# optional feature only when the device reports the id backing it. The full
# sweep hands it every id; this hands it none, so both sides of every gate in
# that branch are pinned.
CLIMATE_IDS = (1, 2, 7, 8)

# Value-sensitive branches, pinned on the side the full sweep cannot reach.
EDGE_CASES = {"119 at the no-outside-probe sentinel": (56, 119, "-327.68")}


def _jsonable(data):
    """The snapshot as JSON stores it: sets sorted, dict keys as strings."""
    return json.loads(json.dumps(data, sort_keys=True, default=sorted))


def _assert_matches(filename, data):
    path = SNAPSHOT_DIR / filename
    dumped = json.dumps(_jsonable(data), indent=1, sort_keys=True) + "\n"

    if os.environ.get("UPDATE_SNAPSHOTS"):
        SNAPSHOT_DIR.mkdir(exist_ok=True)
        path.write_text(dumped)
        return

    if not path.exists():
        pytest.fail(
            f"{path} does not exist -- generate it with "
            "UPDATE_SNAPSHOTS=1 pytest tests/test_snapshot.py"
        )

    assert json.loads(dumped) == json.loads(path.read_text()), (
        f"the mapping no longer matches {path} -- if the change is meant, "
        "regenerate with UPDATE_SNAPSHOTS=1 pytest tests/test_snapshot.py "
        "in the same commit"
    )


def _model_infos(modelId):
    deviceName = ZONE_PROBE_NAME if modelId == ZONE_PROBE_MODEL else None
    return get_model_infos(modelId, None, deviceName)


def test_the_model_table_answers_what_it_answered():
    snapshot = {
        str(modelId): get_model_infos(modelId)
        for modelId in MODEL_ID_RANGE
        if get_model_infos(modelId)["type"] is not CozytouchDeviceType.UNKNOWN
    }
    for modelId, zoneName, deviceName in NAMED_MODEL_CASES:
        key = f"{modelId} zoneName={zoneName} deviceName={deviceName}"
        snapshot[key] = get_model_infos(modelId, zoneName, deviceName)

    _assert_matches("models.json", snapshot)


def test_the_capability_mapping_answers_what_it_answered():
    everyId = set(EVERY_ID)
    full = {
        str(modelId): {
            str(capabilityId): infos
            for capabilityId in EVERY_ID
            # None is the chain not claiming the id; left out so the file only
            # holds answers. A claim that disappears still fails the compare.
            if (
                infos := get_capability_infos(
                    _model_infos(modelId),
                    capabilityId,
                    VALUES.get(capabilityId, "0"),
                    everyId,
                )
            )
            is not None
        }
        for modelId in PROBE_MODELS
    }
    bare = {
        str(modelId): {
            str(capabilityId): get_capability_infos(
                _model_infos(modelId), capabilityId, "0", set()
            )
            for capabilityId in CLIMATE_IDS
        }
        for modelId in PROBE_MODELS
    }
    edges = {
        label: get_capability_infos(
            _model_infos(modelId), capabilityId, value, everyId
        )
        for label, (modelId, capabilityId, value) in EDGE_CASES.items()
    }

    _assert_matches(
        "capabilities.json",
        {"every id reported": full, "none reported": bare, "edge values": edges},
    )
