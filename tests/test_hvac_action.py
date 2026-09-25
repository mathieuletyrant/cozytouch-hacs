"""What a radiator reports while it sits at its setpoint, and an air
conditioner while the house is away.

181 carries the mode the device is really running, and that is what the
climate entity turned into an action: a radiator asked for heat reported
`heating` from the moment it was switched on, whether or not the element was
drawing. gduteil/cozytouch#68 is that, seen from the dashboard: setpoint 19,
room 22.95, `153` -- the element -- reading 0, and Home Assistant saying the
radiator was heating.

The entity is driven unbound against a stand-in, the way
test_duration_select.py drives the select: _handle_coordinator_update touches
nothing of Home Assistant beyond async_write_ha_state.
"""

from types import SimpleNamespace

from custom_components.cozytouch.climate import CozytouchClimate
from custom_components.cozytouch.infos import CapabilityInfos, ModelInfos
from homeassistant.components.climate import HVACAction, HVACMode

# The radiator behind a CozyBox, as the dump reports it: mode 4 requested and
# running, a setpoint of 19 and a room three degrees over it.
IDLING = {7: "4", 181: "4", 40: "19.0", 153: "0"}


def entity(values, away=False, air_conditioning=False, **capabilityExtra):
    """A stand-in carrying only what _handle_coordinator_update touches."""
    capability = CapabilityInfos()
    capability.capabilityId = 7
    capability.targetCapabilityId = 40
    capability.hvacActionCapabilityId = 181
    for key, value in capabilityExtra.items():
        capability[key] = value

    modelInfos = ModelInfos()
    modelInfos.HVACModes = {0: HVACMode.OFF, 3: HVACMode.COOL, 4: HVACMode.HEAT}

    fake = SimpleNamespace(
        _capability=capability,
        _modelInfos=modelInfos,
        coordinator=SimpleNamespace(
            get_capability_value=lambda capabilityId, default="0": values.get(
                capabilityId, default
            ),
            absence_under_way=lambda: away,
            is_air_conditioning=lambda: air_conditioning,
        ),
        async_write_ha_state=lambda: None,
    )
    fake._air_circulation_active = lambda: CozytouchClimate._air_circulation_active(
        fake
    )
    return fake


def test_a_radiator_at_its_setpoint_is_idle_not_heating():
    fake = entity(IDLING, heatingActiveCapabilityId=153)

    CozytouchClimate._handle_coordinator_update(fake)

    assert fake._attr_hvac_mode is HVACMode.HEAT
    assert fake._attr_hvac_action is HVACAction.IDLE


def test_a_radiator_drawing_is_heating():
    fake = entity(IDLING | {153: "1"}, heatingActiveCapabilityId=153)

    CozytouchClimate._handle_coordinator_update(fake)

    assert fake._attr_hvac_action is HVACAction.HEATING


def test_a_radiator_switched_off_stays_off():
    """153 only ever downgrades heating: nothing else is second-guessed."""
    fake = entity({7: "0", 181: "0", 40: "19.0", 153: "0"},
                  heatingActiveCapabilityId=153)

    CozytouchClimate._handle_coordinator_update(fake)

    assert fake._attr_hvac_action is HVACAction.OFF


def test_a_device_that_does_not_report_the_element_reads_as_before():
    """The mapping wires 153 only where the device declares it."""
    fake = entity(IDLING)

    CozytouchClimate._handle_coordinator_update(fake)

    assert fake._attr_hvac_action is HVACAction.HEATING


# A Navizone room during an absence, 2026-09-25 : mode and effective mode
# still cooling, as they were before it, and 100261 at 1.
AWAY_ROOM = {7: "3", 181: "3", 40: "17.0", 153: "0"}


def test_an_air_conditioner_away_is_off_whatever_its_mode_says():
    """The absence stops the unit and leaves the mode for the return."""
    fake = entity(AWAY_ROOM, away=True, air_conditioning=True)

    CozytouchClimate._handle_coordinator_update(fake)

    assert fake._attr_hvac_mode is HVACMode.COOL
    assert fake._attr_hvac_action is HVACAction.OFF


def test_an_air_conditioner_at_home_still_reads_its_mode():
    fake = entity(AWAY_ROOM, air_conditioning=True)

    CozytouchClimate._handle_coordinator_update(fake)

    assert fake._attr_hvac_action is HVACAction.COOLING


def test_a_radiator_away_keeps_its_action():
    """A heater runs its absence setpoint : nothing says it stops."""
    fake = entity(IDLING | {153: "1"}, away=True, heatingActiveCapabilityId=153)

    CozytouchClimate._handle_coordinator_update(fake)

    assert fake._attr_hvac_action is HVACAction.HEATING
