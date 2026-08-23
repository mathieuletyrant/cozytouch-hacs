"""What setting up a config entry actually produces, and what it releases.

`async_setup_entry` is nine lines of Home Assistant plumbing that nothing else
in the suite reaches: it builds the Hub, polls once, forwards seven platforms,
and -- three times over, each with a comment saying why -- hands the aiohttp
session back when it does not get that far. HA does not call
`async_unload_entry` for a setup that failed, so a leaked session is only ever
visible from a test that lets the real config-entry machinery run the failure.

The entity assertions are characterisation, like the rest of the suite: they
are what this account produces today, not what it ought to. The account is one
thermostat and its gateway, served by the fake API in conftest.py.
"""

from datetime import timedelta

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

# What the five reported capabilities come out as. 7 is read twice over -- as
# the climate entity and as a sensor of the raw mode -- 40 becomes an
# adjustable number rather than a sensor, and the connectivity binary sensor is
# the hub's own, not a capability at all.
EXPECTED_ENTITIES = {
    "binary_sensor.thermostat_cozytouch",
    "climate.thermostat_navilink_connect_heat",
    "number.thermostat_navilink_connect_target_temperature",
    "sensor.thermostat_navilink_connect_heat",
    "sensor.thermostat_navilink_connect_open_window_detection",
    "sensor.thermostat_navilink_connect_thermostat_temperature_z1",
}

POLL = timedelta(seconds=61)


async def setup_entry(hass, entry):
    """Set the entry up the way Home Assistant does, and settle."""
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return result


async def test_a_config_entry_builds_the_entities_its_capabilities_map_to(
    hass, api, entry
):
    assert await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    registry = er.async_get(hass)
    assert set(registry.entities) == EXPECTED_ENTITIES


async def test_a_self_describing_capability_is_registered_and_left_off(
    hass, api, entry
):
    """104050 is named but its encoding is unverified.

    SELF_DESCRIBING_CAPABILITIES exists so an id like this costs nobody
    anything until someone turns it on to investigate, which means the entity
    has to be there and disabled rather than absent.
    """
    await setup_entry(hass, entry)

    registered = er.async_get(hass).entities[
        "sensor.thermostat_navilink_connect_open_window_detection"
    ]

    assert registered.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(registered.entity_id) is None


async def test_a_capability_the_table_does_not_know_is_not_an_entity(hass, api, entry):
    """999999 is reported by the device and named nowhere."""
    await setup_entry(hass, entry)

    assert not [
        entity_id
        for entity_id in er.async_get(hass).entities
        if "999999" in entity_id
    ]


async def test_the_unknown_capability_option_surfaces_it(hass, api, entry):
    """What the option is for: a value to watch while working out its meaning."""
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={"create_unknown": True})

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        "sensor.thermostat_navilink_connect_capability_999999"
        in er.async_get(hass).entities
    )


async def test_the_entry_registers_one_device_and_identifies_it_by_entry_id(
    hass, api, entry
):
    """Pinned as it stands, and it is worth knowing which way round this is.

    The identifier the entities register under is the config entry's id, not
    the Atlantic deviceId -- Hub.device_info builds one from the deviceId, and
    nothing uses it. So removing and re-adding the same physical device leaves
    the old device behind rather than adopting it.

    One device and not two: the gateway is in the setup view but has no config
    entry of its own here, and a device can only be registered under an entry.
    tests/test_topology.py covers what that does to the gateway link.
    """
    await setup_entry(hass, entry)

    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={("cozytouch", entry.entry_id)})

    assert len(registry.devices) == 1
    assert device.name == "Thermostat Navilink Connect"
    assert device.model == "Thermostat Navilink Connect"
    assert device.manufacturer == "Atlantic"
    assert device.via_device_id is None


async def test_the_values_only_arrive_with_the_next_poll(hass, api, entry):
    """Pinned as it stands, which is not as it should be.

    Setup fetches the capabilities -- `async_config_entry_first_refresh` is
    what makes it fail cleanly when the API is down -- but the entities read
    their value in `_handle_coordinator_update`, and a CoordinatorEntity is not
    called on the data that was already there when it was added. So every
    entity reads unknown from setup until the next poll lands, which is up to
    POLL_INTERVAL later: after a Home Assistant restart the dashboard is blank
    for a minute although the data arrived in the first second.
    """
    await setup_entry(hass, entry)
    temperature = "sensor.thermostat_navilink_connect_thermostat_temperature_z1"

    assert hass.states.get(temperature).state == "unknown"

    async_fire_time_changed(hass, dt_util.utcnow() + POLL)
    await hass.async_block_till_done()

    assert hass.states.get(temperature).state == "19.5"
    assert hass.states.get("climate.thermostat_navilink_connect_heat").state == "heat"
    assert (
        hass.states.get(
            "number.thermostat_navilink_connect_target_temperature"
        ).state
        == "20.5"
    )


async def test_unloading_the_entry_closes_the_session(hass, api, entry):
    """A reload builds a new Hub, so the old session has to go with the old one."""
    await setup_entry(hass, entry)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert api.session.closed is True


async def test_a_rejected_password_asks_for_a_retry_without_leaking(hass, api, entry):
    """HA builds a new Hub per attempt, so a session kept here is one per retry."""
    api.token = {"error": "invalid_grant"}

    assert not await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert [session.closed for session in api.sessions] == [True]


async def test_a_first_poll_that_fails_does_not_leak_either(hass, api, entry):
    """The other exit: connected, then the capabilities call comes back 500.

    This is the path HA does not unload -- setup raises after the Hub exists --
    and the one the `except Exception:` in async_setup_entry is there for.
    """
    api.capabilities_status = 500

    assert not await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert [session.closed for session in api.sessions] == [True]


async def test_changing_an_option_reloads_and_the_old_session_goes_with_it(
    hass, api, entry
):
    await setup_entry(hass, entry)
    first_session = api.session

    hass.config_entries.async_update_entry(entry, options={"create_unknown": True})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert len(api.sessions) == 2
    assert first_session.closed is True
    assert api.session.closed is False
