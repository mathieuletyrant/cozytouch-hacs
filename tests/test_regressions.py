"""Guards for two bugs that were live and silent.

Neither showed up in a test run, because neither is reachable from the model or
capability tables that the rest of the suite walks. One needed two config
entries to be visible at all, the other needed a device that reports a
duration. Both are cheap to pin now that they are known.
"""

from datetime import time as time_cls
import inspect
from types import SimpleNamespace

import pytest

from custom_components.cozytouch.hub import Hub
from custom_components.cozytouch.time import CozytouchTime


def setup_payload(zones, devices=()):
    """The shape of the setupviewv2 response, cut down to what is read here."""
    return [{"zones": list(zones), "devices": list(devices)}]


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


def test_zones_are_refreshed_and_not_only_read_once():
    """A rename in the Cozytouch app has to reach Home Assistant.

    Zones were loaded under `if len(self._zones) == 0`, so the first setup view
    won and every later one was discarded. The setup view is re-fetched on each
    reconnect -- which happens whenever the token expires -- so the data was
    there, and thrown away. Zone names feed entity names, so a room renamed in
    the app kept its old name here indefinitely.
    """
    hub = SimpleNamespace(
        _dump_json=False, _devices=[], _deviceId=1, _zoneId=-1,
        _zones=[{"id": 991904, "name": "Mezzanine"}],
    )

    Hub.update_devices_from_json_data(
        hub, setup_payload([{"id": 991904, "name": "Chambre 2"}])
    )

    assert hub._zones == [{"id": 991904, "name": "Chambre 2"}]


def test_a_setup_view_without_zones_leaves_the_known_ones_alone():
    """Absent is not the same as empty; a partial payload must not wipe them."""
    hub = SimpleNamespace(
        _dump_json=False, _devices=[], _deviceId=1, _zoneId=-1,
        _zones=[{"id": 991904, "name": "Mezzanine"}],
    )

    Hub.update_devices_from_json_data(hub, [{"devices": []}])

    assert hub._zones == [{"id": 991904, "name": "Mezzanine"}]


def test_the_stored_zones_are_a_copy_of_the_payload():
    """The payload is reused by the caller; storing a reference would alias it."""
    payload = setup_payload([{"id": 991904, "name": "Mezzanine"}])
    hub = SimpleNamespace(
        _dump_json=False, _devices=[], _deviceId=1, _zoneId=-1, _zones=[]
    )

    Hub.update_devices_from_json_data(hub, payload)
    payload[0]["zones"][0]["name"] = "muté après coup"

    assert hub._zones[0]["name"] == "Mezzanine"


def test_the_dev_only_json_loader_is_gone():
    """It read a hardcoded capture from the user's config directory."""
    source = inspect.getsource(Hub)

    assert "_test_load" not in source
    assert "cozytouch_eoras2" not in source
