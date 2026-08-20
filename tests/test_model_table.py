"""Guards on the shape of the model table.

The table is meant to be edited by someone who owns the hardware, not
necessarily by someone who writes Python. So the failure modes worth catching
here are the ones that would otherwise be silent: a mistyped flag name does
nothing at all, and nothing about the code would say so -- the feature simply
never appears, and the person who added the line has no way to tell.

These tests read the table rather than any particular device, so a row added
later is checked without anyone remembering to check it.
"""

import pytest

from custom_components.cozytouch.model import (
    MODELS,
    ZONE_NAMED,
    CozytouchDeviceType,
    get_model_infos,
)

# Every key the integration reads off a profile, gathered from capability.py,
# climate.py, sensor.py, select.py and hub.py. A key outside this set is dead:
# nothing will ever look at it.
KEYS_THE_CODE_READS = {
    "AirCirculationSpeeds",
    "awayModeTemperatureAvailable",
    "currentTemperatureAvailable",
    "currentTemperatureAvailableZ1",
    "currentTemperatureAvailableZ2",
    "ecoModeAvailable",
    "exhaustTemperatureAvailable",
    "fanModes",
    "HeatingModes",
    "HVACModes",
    "HVACModesCapabilityId",
    "overrideModeAvailable",
    "quietModeAvailable",
    "swingModes",
    "type",
}

ALL_ROWS = [
    pytest.param(modelId, name, profile, id=str(modelId))
    for modelId, (name, profile) in MODELS.items()
] + [
    pytest.param(first, label, profile, id=f"{first}-{last}")
    for (first, last), (label, profile) in ZONE_NAMED.items()
]


@pytest.mark.parametrize(("modelId", "name", "profile"), ALL_ROWS)
def test_a_row_declares_only_keys_something_reads(modelId, name, profile):
    """A mistyped flag is the failure this catches.

    "ecoModeAvaliable" is accepted by Python, stored, and never looked at. The
    feature it was meant to turn off stays on, and the only symptom is a user
    reporting a control that should not be there.
    """
    unknown = set(profile) - KEYS_THE_CODE_READS

    assert not unknown, f"{modelId} declares {unknown}, which nothing reads"


@pytest.mark.parametrize(("modelId", "name", "profile"), ALL_ROWS)
def test_a_row_says_what_kind_of_device_it_is(modelId, name, profile):
    assert isinstance(profile.get("type"), CozytouchDeviceType)
    assert profile["type"] is not CozytouchDeviceType.UNKNOWN
    assert profile.get("HVACModes"), f"{modelId} has no HVACModes"
    assert name.strip(), f"{modelId} has no name"


def test_no_id_is_claimed_twice():
    """A row in both tables would resolve by whichever is consulted first."""
    ranged = {m for first, last in ZONE_NAMED for m in range(first, last + 1)}
    overlap = set(MODELS) & ranged

    assert not overlap, f"{overlap} appear in both MODELS and ZONE_NAMED"


def test_zone_named_ranges_do_not_overlap_each_other():
    seen: dict[int, tuple[int, int]] = {}
    for first, last in ZONE_NAMED:
        assert first <= last, f"({first}, {last}) runs backwards"
        for m in range(first, last + 1):
            assert m not in seen, f"{m} is in both {seen[m]} and {(first, last)}"
            seen[m] = (first, last)


def test_a_caller_cannot_poison_a_shared_profile():
    """Twenty-five water heaters share one profile dict.

    If the returned dict handed out that shared object, one caller writing into
    it would change what every other device of the family reports -- the same
    shape of bug as the state that used to live on the Hub class.
    """
    first = get_model_infos(2374)
    first["HVACModes"][99] = "poison"
    first["quietModeAvailable"] = True

    second = get_model_infos(2374)

    assert 99 not in second["HVACModes"]
    assert "quietModeAvailable" not in second


def test_an_unmapped_id_is_reported_as_unknown():
    """This is the signal that sends someone to the table."""
    infos = get_model_infos(4242)

    assert infos["type"] is CozytouchDeviceType.UNKNOWN
    assert infos["name"] == "Unknown product (4242)"
