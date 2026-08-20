"""Guards for two bugs that were live and silent.

Neither showed up in a test run, because neither is reachable from the model or
capability tables that the rest of the suite walks. One needed two config
entries to be visible at all, the other needed a device that reports a
duration. Both are cheap to pin now that they are known.
"""

from datetime import time as time_cls
from types import SimpleNamespace

import pytest

from custom_components.cozytouch.hub import Hub
from custom_components.cozytouch.time import CozytouchTime


@pytest.mark.parametrize(
    "attribute",
    [
        "_setup",
        "_localization",
        "_zones",
        "_timestamp_away_mode_last_change",
        "_timestamp_away_mode_start",
        "_timestamp_away_mode_end",
    ],
)
def test_per_account_state_is_not_shared_by_every_hub(attribute):
    """These lived on the class, so one dict served every config entry.

    An account is set up one entry per device -- a gateway, then a unit per
    zone -- and each builds its own Hub. While this state sat on the class,
    `self._setup[key] = ...` mutated the one dict they all saw, so the last
    hub to connect overwrote what the others had stored. Reading it back gave
    another device's setup.
    """
    assert not hasattr(Hub, attribute)


@pytest.mark.parametrize(
    ("stored_minutes", "expected"),
    [
        (0, time_cls(0, 0)),
        (45, time_cls(0, 45)),
        (60, time_cls(1, 0)),
        (135, time_cls(2, 15)),
        (1439, time_cls(23, 59)),
    ],
)
def test_a_duration_capability_becomes_a_time(stored_minutes, expected):
    """The module imported both datetime.time and the time module.

    The second shadowed the first, so the name `time` pointed at the stdlib
    module and this property reached for `datetime.time(h, m, 0)` instead --
    an unbound method, which raises TypeError when called with three ints.
    Every time entity was therefore broken, and nothing said so.
    """
    entity = SimpleNamespace(
        coordinator=SimpleNamespace(get_capability_value=lambda _: str(stored_minutes)),
        _capability={"capabilityId": 232},
    )

    assert CozytouchTime.native_value.fget(entity) == expected
