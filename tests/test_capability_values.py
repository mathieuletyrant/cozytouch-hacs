"""What a descriptor capability's number is read as.

The tables in `capability.py` come from the vendor's Android app and were
checked against `research`'s capture corpus; these pin the readings the corpus
actually holds, so a table edited on a hunch has to fail something. The values
below are real ones -- 411 and 415 are what an air conditioner reports, 17 is
what a radiator reports, 16133 is a Calypso's hot-water mask.

They also pin the two refusals: a mask nothing names is not decoded, and a bit
past the last member the table knows is reported rather than dropped.
"""

import pytest

from custom_components.cozytouch.capability import (
    describe_capability_value,
    read_setpoint,
)


@pytest.mark.parametrize(
    ("capabilityId", "value", "expected"),
    [
        # The HVAC space. auto claims bits 1 and 2, which is why 411 and 415
        # read the same: the app matches on any bit of a member's mask.
        (100022, "411", "off, auto, cool, heat, fan, dry"),
        (100022, "415", "off, auto, cool, heat, fan, dry"),
        (166, "285", "off, auto, cool, heat, dry"),
        (166, "17", "off, heat"),
        (166, "9", "off, cool"),
        # The control space, which is a different enum on the same-looking
        # numbers: 3075 is nonsense read as HVAC modes.
        (217, "3075", "basic, prog, absence, scheduled_absence"),
        (100023, "3", "basic, prog"),
        # Hot water.
        (
            168,
            "16133",
            (
                "manual, auto, boost, scheduled_boost, absence, "
                "scheduled_absence, antilegionella, smart_grid"
            ),
        ),
        (
            336,
            "15",
            (
                "v40_state_of_charge, main_setpoint_cursor, "
                "secondary_setpoint_cursor, data_inside"
            ),
        ),
        (105012, "7", "heat, scheduled_heat, off_peak_heat"),
        # Value spaces rather than masks.
        (73, "4", "cooling_and_heating"),
        (73, "2", "heating_only"),
        (337, "6", "water_setpoint"),
        (100800, "2", "low, medium, high, auto"),
        (350, "0", "low, medium, high"),
        # A speed set naming one speed, which is what the app's table says and
        # what "on, auto" used to get wrong.
        (350, "4", "auto"),
        (100800, "4", "auto"),
        # Nothing set is a reading of its own, not an empty string.
        (164, "0", "none"),
        # A bit the table does not name is carried through, since these
        # entities exist for the reader chasing exactly that.
        (188, "257", "thermal_comfort, unknown (256)"),
        (164, "1040", "electricity_dhw, unknown (1024)"),
    ],
)
def test_a_descriptor_reads_as_what_it_says(capabilityId, value, expected):
    assert describe_capability_value(capabilityId, value) == expected


@pytest.mark.parametrize(
    ("capabilityId", "value"),
    [
        # No table for this id.
        (179, "-47"),
        # A table, but the value is not a number.
        (100022, "1.3.14"),
        (100022, None),
        # A value space that does not hold this member.
        (73, "9"),
    ],
)
def test_a_descriptor_nothing_explains_is_left_alone(capabilityId, value):
    assert describe_capability_value(capabilityId, value) is None


@pytest.mark.parametrize(
    ("capabilityId", "value", "expected"),
    [
        # A room program in hundredths, which is the app's own rule.
        (196, 1950, 19.5),
        (100320, 2100, 21.0),
        # Below the threshold nothing is touched.
        (196, 19.5, 19.5),
        (196, 40, 40),
        # The hot-water block really does carry 50-65 °C, so the rule must
        # not reach it -- 65 read as 0.65 would be the bug.
        (237, 65, 65),
        (243, 50, 50),
        # No id, no rule: parse_slots is called that way by the services that
        # do not know which block they are reading.
        (None, 1950, 1950),
        # Anything unparseable is handed back rather than raising.
        (196, "n/a", "n/a"),
    ],
)
def test_a_setpoint_in_hundredths_is_only_divided_where_it_can_be_one(
    capabilityId, value, expected
):
    assert read_setpoint(capabilityId, value) == expected
