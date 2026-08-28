"""Leaving the house, in one call.

Away mode was reachable and not automatable. The window lives on the setup and
the device mirrors it, so switching it on meant setting two datetime entities,
waiting out the 20-second debounce that batches those two edits, and then
ticking a switch -- a sequence a person can perform and an automation cannot.
"When the last person leaves for more than two days" had no way to say itself.

Nothing here is new capability knowledge: the PUT, the mirror and the mode flag
were all in the hub already. What these pin is the door in front of them --
`Hub.start_away_mode` / `stop_away_mode`, the two services, and the climate
preset -- and the one thing that was actually missing, which is that the window
the device holds is now read back into the entities that report it.

`FakeHub` stands in where a service is under test, and the real `Hub` is driven
directly where the door itself is. `dt_util.DEFAULT_TIME_ZONE` is UTC in a test
process.
"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import voluptuous as vol

from custom_components.cozytouch import services as services_module
from custom_components.cozytouch.climate import CozytouchClimate
from custom_components.cozytouch.hub import AWAY_START_DELAY, DEFAULT_AWAY_DURATION, Hub
from custom_components.cozytouch.infos import CapabilityInfos, CapabilityType
from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_ECO,
    ClimateEntityFeature,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

# 152 pairs with 222, 227 with 226 -- capability.py owns that pairing, and
# these are the shape it hands back.
AWAY = {
    "modeCapabilityId": 152,
    "timestampsCapabilityId": 222,
    "value_on": "1",
    "value_off": "0",
}


def hub_with(away=AWAY, values=None):
    """A real Hub with its away lookup already answered.

    The cache is pre-filled rather than walked: what the walk does has its own
    case below, and every other case here is about what the door writes.
    """
    hub = object.__new__(Hub)
    hub._away_mode_capabilities = away
    hub._deviceId = 1
    hub._timestamp_away_mode_last_change = None
    hub._timestamp_away_mode_start = None
    hub._timestamp_away_mode_end = None
    hub._timestamps_away_mode_capability_id = None
    hub._account = SimpleNamespace(
        devices=[
            {
                "deviceId": 1,
                "capabilities": [
                    {"capabilityId": capabilityId, "value": value}
                    for capabilityId, value in (values or {}).items()
                ],
            }
        ]
    )

    hub.written = []

    async def set_away_mode_timestamps(
        capabilityIdMode, valueMode, capabilityIdTimestamps, start, end
    ):
        hub.written.append((capabilityIdMode, valueMode, start, end))

    hub.set_away_mode_timestamps = set_away_mode_timestamps

    return hub


class FakeHub:
    """A hub for the services: it records, and answers about its capabilities."""

    def __init__(self, away=AWAY, temperature=None, values=None):
        self._away = away
        self._temperature = temperature
        self._values = values or {}
        self.windows = []
        self.stopped = 0
        self.written = []
        self.refreshes = 0

    def get_away_mode_capabilities(self):
        return self._away

    def get_away_mode_temperature_capability(self):
        return self._temperature

    def get_capability_value(self, capabilityId, defaultIfNotExist="0"):
        return self._values.get(capabilityId, defaultIfNotExist)

    async def set_capability_value(self, capabilityId, value):
        self.written.append((capabilityId, value))

    async def start_away_mode(self, start=None, end=None):
        if self._away is None:
            return False
        self.windows.append((start, end))
        return True

    async def stop_away_mode(self):
        if self._away is None:
            return False
        self.stopped += 1
        return True

    async def async_request_refresh(self):
        self.refreshes += 1


def services_over(hub):
    """Register the services against a fake hass and hand them back by name."""
    registered = {}
    hass = SimpleNamespace(
        services=SimpleNamespace(
            has_service=lambda domain, service: False,
            async_register=lambda domain, service, func, schema=None, **kwargs: (
                registered.update({service: (func, schema)})
            ),
        )
    )
    services_module.async_register_services(hass)
    services_module._resolve_hub = lambda hass, entity_id: hub

    return registered


def call(registered, service, data):
    """Run one service call through its own schema, the way hass would."""
    func, schema = registered[service]
    asyncio.run(func(SimpleNamespace(data=schema(data))))


@pytest.fixture(autouse=True)
def _restore_resolve_hub():
    """`services_over` reaches into the module; put it back afterwards."""
    original = services_module._resolve_hub
    yield
    services_module._resolve_hub = original


def at(*args):
    return datetime(*args, tzinfo=dt_util.DEFAULT_TIME_ZONE)


# --------------------------------------------------------------- the hub door


def test_a_window_with_no_arguments_is_a_minute_out_for_two_days():
    """The fallback the away switch has always used, now in one place."""
    hub = hub_with()
    before = datetime.now(tz=dt_util.DEFAULT_TIME_ZONE).timestamp()

    assert asyncio.run(hub.start_away_mode()) is True

    (capabilityId, value, start, end), = hub.written
    assert (capabilityId, value) == (152, "1")
    # int(), so the epoch written can sit up to a second below `before` + the
    # delay; the window is what is being pinned, not the clock.
    assert int(before) + AWAY_START_DELAY <= start <= before + AWAY_START_DELAY + 5
    assert end - start == DEFAULT_AWAY_DURATION


def test_a_window_that_was_asked_for_is_written_as_asked():
    hub = hub_with()

    asyncio.run(hub.start_away_mode(1_800_000_000, 1_800_600_000))

    assert hub.written == [(152, "1", 1_800_000_000, 1_800_600_000)]


@pytest.mark.parametrize(
    "window",
    [
        (None, None),
        (0, 0),
        (1_800_600_000, 1_800_000_000),  # ends before it starts
    ],
)
def test_a_window_that_says_nothing_usable_falls_back(window):
    """Same rule the switch applied to its staged pair, kept exactly."""
    hub = hub_with()

    asyncio.run(hub.start_away_mode(*window))

    (_, _, start, end), = hub.written
    assert end - start == DEFAULT_AWAY_DURATION


def test_a_window_that_is_already_over_falls_back_too():
    """The case seeding created. The staged pair now comes from the device, so
    turning the switch on after last month's absence would otherwise re-apply
    it and end the moment it began.
    """
    hub = hub_with()

    asyncio.run(hub.start_away_mode(1_600_000_000, 1_600_600_000))

    (_, _, start, end), = hub.written
    assert end - start == DEFAULT_AWAY_DURATION
    assert start > 1_700_000_000


def test_stopping_writes_the_off_value_and_no_window():
    hub = hub_with()

    assert asyncio.run(hub.stop_away_mode()) is True
    assert hub.written == [(152, "0", None, None)]


def test_a_device_with_no_away_mode_is_told_so_rather_than_written_to():
    hub = hub_with(away=None)

    assert asyncio.run(hub.start_away_mode()) is False
    assert asyncio.run(hub.stop_away_mode()) is False
    assert hub.written == []


@pytest.mark.parametrize(
    ("value", "expected"), [("1", True), ("0", False), ("2", True), (None, False)]
)
def test_whether_the_device_says_it_is_away(value, expected):
    """Anything but the off value: the mode also holds a pending state."""
    hub = hub_with(values={152: value} if value is not None else {})

    assert hub.is_away_mode_on() is expected


def test_the_pairing_comes_from_the_capability_table():
    """Not from a second copy of "152 goes with 222" living in the hub."""
    hub = hub_with(away=False)
    hub.get_capabilities_for_device = lambda: [
        CapabilityInfos(capabilityId=100, type=CapabilityType.TEMPERATURE),
        CapabilityInfos(
            capabilityId=227,
            type=CapabilityType.AWAY_MODE_SWITCH,
            timestampsCapabilityId=226,
            value_on="1",
            value_off="0",
        ),
    ]

    assert hub.get_away_mode_capabilities() == {
        "modeCapabilityId": 227,
        "timestampsCapabilityId": 226,
        "value_on": "1",
        "value_off": "0",
    }


def test_a_device_whose_table_has_no_away_switch_gets_none():
    hub = hub_with(away=False)
    hub.get_capabilities_for_device = lambda: [
        CapabilityInfos(capabilityId=100, type=CapabilityType.STRING)
    ]

    assert hub.get_away_mode_capabilities() is None


# ----------------------------------------------- reading back what is set


def test_the_window_the_device_holds_reaches_the_staged_pair():
    """What `away_mode_init` was written for and never called to do.

    Without this the two datetime entities read unknown after every restart,
    even on a device sitting in the middle of an absence, and a window set by
    the service or by the Cozytouch app never showed up at all.
    """
    hub = hub_with(values={222: "[1800000000,1800600000]"})

    asyncio.run(hub._commit_staged_away_mode())

    assert hub.get_away_mode_start() == 1_800_000_000
    assert hub.get_away_mode_end() == 1_800_600_000


@pytest.mark.parametrize("stored", ["[0,0]", "", "not json", "[0]", None])
def test_no_window_reads_as_no_window_rather_than_as_1970(stored):
    hub = hub_with(values={222: stored} if stored is not None else {})

    asyncio.run(hub._commit_staged_away_mode())

    assert hub.get_away_mode_start() is None
    assert hub.get_away_mode_end() is None


def test_a_poll_does_not_undo_an_edit_in_progress():
    """The debounce exists so both ends can be set before either is sent; a
    poll landing between the two edits must not overwrite the first one.
    """
    hub = hub_with(values={222: "[1800000000,1800600000]"})
    asyncio.run(hub.set_away_mode_start(222, 1_900_000_000))

    asyncio.run(hub._commit_staged_away_mode())

    assert hub.get_away_mode_start() == 1_900_000_000


# ------------------------------------------------------------- the services


def test_set_away_mode_with_a_duration_starts_now_and_runs_that_long():
    """The call an automation can actually make."""
    hub = FakeHub()
    registered = services_over(hub)
    before = datetime.now(tz=dt_util.DEFAULT_TIME_ZONE).timestamp()

    call(
        registered,
        "set_away_mode",
        {"entity_id": ["climate.salon"], "duration": {"days": 10}},
    )

    (start, end), = hub.windows
    # int(), so the epoch written can sit up to a second below `before` + the
    # delay; the window is what is being pinned, not the clock.
    assert int(before) + AWAY_START_DELAY <= start <= before + AWAY_START_DELAY + 5
    assert end - start == int(timedelta(days=10).total_seconds())


def test_set_away_mode_with_both_ends_writes_both():
    hub = FakeHub()
    registered = services_over(hub)

    call(
        registered,
        "set_away_mode",
        {
            "entity_id": ["climate.salon"],
            "start": at(2026, 12, 24, 8),
            "end": at(2027, 1, 2, 18),
        },
    )

    assert hub.windows == [
        (int(at(2026, 12, 24, 8).timestamp()), int(at(2027, 1, 2, 18).timestamp()))
    ]


def test_set_away_mode_with_nothing_said_leaves_the_default_to_the_hub():
    """Rather than computing a second default here."""
    hub = FakeHub()
    registered = services_over(hub)

    call(registered, "set_away_mode", {"entity_id": ["climate.salon"]})

    assert hub.windows == [(None, None)]


def test_a_window_that_ends_before_it_starts_is_refused():
    hub = FakeHub()
    registered = services_over(hub)

    with pytest.raises(ServiceValidationError):
        call(
            registered,
            "set_away_mode",
            {
                "entity_id": ["climate.salon"],
                "start": at(2027, 1, 2, 18),
                "end": at(2026, 12, 24, 8),
            },
        )

    assert hub.windows == []


def test_a_window_that_already_ended_is_refused_rather_than_substituted():
    """The hub falls back for the switch; a call that named a date does not get
    a different one silently.
    """
    hub = FakeHub()
    registered = services_over(hub)

    with pytest.raises(ServiceValidationError, match="past"):
        call(
            registered,
            "set_away_mode",
            {
                "entity_id": ["climate.salon"],
                "start": at(2020, 12, 24, 8),
                "end": at(2021, 1, 2, 18),
            },
        )

    assert hub.windows == []


def test_an_end_and_a_duration_together_are_refused_by_the_schema():
    """Two ways of saying the same thing, one of which would have to win."""
    hub = FakeHub()
    registered = services_over(hub)

    with pytest.raises(vol.Invalid):
        call(
            registered,
            "set_away_mode",
            {
                "entity_id": ["climate.salon"],
                "end": at(2027, 1, 2, 18),
                "duration": {"days": 3},
            },
        )


def test_a_setpoint_is_written_before_the_window_opens():
    """Or the absence starts on the setpoint it was going to replace."""
    hub = FakeHub(temperature=CapabilityInfos(capabilityId=172))
    registered = services_over(hub)

    call(
        registered,
        "set_away_mode",
        {"entity_id": ["climate.salon"], "temperature": 12},
    )

    assert hub.written == [(172, "12.0")]
    assert hub.windows == [(None, None)]


def test_a_setpoint_outside_what_the_device_accepts_is_refused_not_clamped():
    """A service call said a number out loud. Writing a different one quietly
    is worse than saying it does not fit.
    """
    hub = FakeHub(
        temperature=CapabilityInfos(
            capabilityId=172,
            lowestValueCapabilityId=160,
            highestValueCapabilityId=161,
        ),
        values={160: "7", 161: "19"},
    )
    registered = services_over(hub)

    with pytest.raises(ServiceValidationError, match="19"):
        call(
            registered,
            "set_away_mode",
            {"entity_id": ["climate.salon"], "temperature": 25},
        )

    assert hub.written == []
    assert hub.windows == []


def test_a_setpoint_on_hardware_that_ignores_it_is_refused():
    """Air conditioners report 172 and never act on it, so the table drops it."""
    hub = FakeHub(temperature=None)
    registered = services_over(hub)

    with pytest.raises(ServiceValidationError):
        call(
            registered,
            "set_away_mode",
            {"entity_id": ["climate.salon"], "temperature": 12},
        )


def test_clear_away_mode_stops_it():
    hub = FakeHub()
    registered = services_over(hub)

    call(registered, "clear_away_mode", {"entity_id": ["climate.salon"]})

    assert (hub.stopped, hub.refreshes) == (1, 1)


def test_a_device_with_no_away_mode_says_so():
    hub = FakeHub(away=None)
    registered = services_over(hub)

    for service in ("set_away_mode", "clear_away_mode"):
        with pytest.raises(ServiceValidationError):
            call(registered, service, {"entity_id": ["climate.salon"]})


# --------------------------------------------------------- the climate preset


class FakeCoordinator:
    """Just enough hub for the preset half."""

    def __init__(self, away=AWAY, on=False):
        self._away = away
        self.on = on
        self.started = 0
        self.stopped = 0
        self.refreshes = 0

    def get_away_mode_capabilities(self):
        return self._away

    def is_away_mode_on(self):
        return self.on

    async def start_away_mode(self, start=None, end=None):
        self.started += 1
        return self._away is not None

    async def stop_away_mode(self):
        self.stopped += 1
        return self._away is not None

    async def async_request_refresh(self):
        self.refreshes += 1


def climate_over(coordinator, capability=None):
    """A climate entity with nothing but what the preset paths read."""
    climate = object.__new__(CozytouchClimate)
    climate._capability = capability if capability is not None else {}
    climate._attr_supported_features = ClimateEntityFeature(0)
    climate._attr_preset_modes = []
    climate._attr_preset_mode = None
    climate.coordinator = coordinator

    return climate


def test_away_is_offered_when_the_device_has_one():
    """On what the device reports, not on what this capability carries: the
    window is on the setup, not on the climate capability.
    """
    climate = climate_over(FakeCoordinator())

    climate._configure_presets()

    assert climate._attr_preset_modes == [PRESET_AWAY]
    assert ClimateEntityFeature.PRESET_MODE in climate._attr_supported_features


def test_away_is_not_offered_when_the_device_has_none():
    climate = climate_over(FakeCoordinator(away=None))

    climate._configure_presets()

    assert climate._attr_preset_modes == []


def test_choosing_away_opens_the_default_window():
    climate = climate_over(FakeCoordinator())
    climate._configure_presets()

    asyncio.run(climate.async_set_preset_mode(PRESET_AWAY))

    assert (climate.coordinator.started, climate.coordinator.stopped) == (1, 0)
    assert climate._attr_preset_mode == PRESET_AWAY


def test_choosing_anything_else_while_away_comes_back_first():
    """Otherwise the preset would be applied under a window still in force."""
    climate = climate_over(FakeCoordinator(on=True))
    climate._configure_presets()

    asyncio.run(climate.async_set_preset_mode(PRESET_ECO))

    assert (climate.coordinator.started, climate.coordinator.stopped) == (0, 1)


def test_choosing_anything_else_when_not_away_leaves_the_window_alone():
    climate = climate_over(FakeCoordinator(on=False))
    climate._configure_presets()

    asyncio.run(climate.async_set_preset_mode(PRESET_ECO))

    assert (climate.coordinator.started, climate.coordinator.stopped) == (0, 0)
