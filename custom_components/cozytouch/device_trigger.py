"""Device triggers for the Atlantic Cozytouch integration.

Home Assistant already builds device triggers out of the entity domains a
device happens to have : the connectivity binary sensor gives "connected" and
"disconnected", the away-mode switch gives "turned on", the climate entity
gives "HVAC mode changed". Nothing there reaches the weekly program, and the
program is what these devices are scheduled by -- it keeps running when Home
Assistant is off, which is the whole reason the two schedule services exist.

Two gaps, then, and this module fills those and nothing else :

- the program itself is seven diagnostic sensors, one per day, that no entity
  groups, so "the heating program changed" has no entity to be triggered on ;
- `climate.device_trigger` offers `hvac_mode_changed` and the two current-value
  triggers, and no preset trigger at all -- and the preset is where prog,
  override and basic are reported.

There is deliberately no `device_condition.py` and no `device_action.py`. The
`climate` domain already ships both for presets : "Cozytouch is set to prog" is
a condition Home Assistant writes itself, and setting one is a climate device
action. Adding ours would put two entries with the same meaning in the same
picker.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.climate.const import ATTR_PRESET_MODE, ATTR_PRESET_MODES
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_PLATFORM,
    CONF_TYPE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .climate import PRESET_BASIC, PRESET_OVERRIDE, PRESET_PROG
from .const import DOMAIN
from .services import DAYS, PROGRAM_FIRST_CAPABILITY

# One per program the schedule services know, so the trigger list and the
# services stay in step: a program nothing can read back is not one an
# automation should be told changed.
SCHEDULE_TRIGGER_TYPES = {
    f"{program}_schedule_changed": program for program in PROGRAM_FIRST_CAPABILITY
}

# The three presets that say what the device is doing about its own program:
# following it, running a temporary override of it, or ignoring it for a
# manual setpoint. capability.py wires all three from capability 184 and 157.
PRESET_TRIGGER_TYPES = {
    "schedule_resumed": PRESET_PROG,
    "schedule_overridden": PRESET_OVERRIDE,
    "schedule_stopped": PRESET_BASIC,
}

# A day sensor that is merely unreachable has not been reprogrammed, so the
# trip through unavailable and back is not a change. Ruling both ends out also
# turns the trigger into a state-value one: with no `to` or `from` at all, the
# state trigger fires on attribute changes too, and a renamed entity would
# read as an edited program.
NOT_A_PROGRAM = [STATE_UNAVAILABLE, STATE_UNKNOWN]

_SCHEDULE_TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        # No entity_id: a program is seven sensors, and which seven is a
        # question about the device rather than about any one of them.
        vol.Required(CONF_TYPE): vol.In(SCHEDULE_TRIGGER_TYPES),
    }
)

_PRESET_TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): vol.In(PRESET_TRIGGER_TYPES),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)

TRIGGER_SCHEMA = vol.Any(_SCHEDULE_TRIGGER_SCHEMA, _PRESET_TRIGGER_SCHEMA)


def _capability_id(unique_id: str | None) -> int | None:
    """The capability id a sensor's unique id ends with.

    Sensors are keyed `cozytouch_{entry_id}_{capabilityId}`, and a config entry
    id carries no underscore, so the tail is the capability. The two away-mode
    timestamps are the exception -- `{entry_id}_0` and `{entry_id}_1` -- and 0
    and 1 fall outside every program block, so they rule themselves out.
    """
    if not unique_id:
        return None

    try:
        return int(unique_id.rpartition("_")[2])
    except ValueError:
        return None


def _program_block(program: str) -> range:
    """The seven consecutive capability ids one program is stored in."""
    first = PROGRAM_FIRST_CAPABILITY[program]
    return range(first, first + len(DAYS))


def _schedule_entity_ids(
    hass: HomeAssistant, device_id: str, program: str
) -> list[str]:
    """The registry ids of the seven day sensors of one program.

    Registry ids rather than entity ids: an entity that gets renamed keeps the
    former and changes the latter, and an automation should survive a rename.
    """
    block = _program_block(program)

    registry = er.async_get(hass)
    return [
        entry.id
        for entry in er.async_entries_for_device(registry, device_id)
        if entry.domain == SENSOR_DOMAIN and _capability_id(entry.unique_id) in block
    ]


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List the triggers this device actually has.

    Both kinds are offered only when the device reports what they read : a
    water heater with no cooling program does not get a cooling trigger, and a
    device whose climate entity has no prog preset gets none of the three.
    """
    registry = er.async_get(hass)
    base_trigger = {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    triggers: list[dict[str, str]] = []
    capabilityIds: set[int] = set()

    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain == SENSOR_DOMAIN:
            capabilityId = _capability_id(entry.unique_id)
            if capabilityId is not None:
                capabilityIds.add(capabilityId)
            continue

        if entry.domain != CLIMATE_DOMAIN:
            continue

        # Which presets exist is on the entity, not in the registry, so a
        # climate entity with no state yet answers for none of them. That is
        # the read climate.device_trigger makes for its own two as well.
        state = hass.states.get(entry.entity_id)
        presets = state.attributes.get(ATTR_PRESET_MODES) or () if state else ()

        triggers += [
            {**base_trigger, CONF_ENTITY_ID: entry.id, CONF_TYPE: trigger_type}
            for trigger_type, preset in PRESET_TRIGGER_TYPES.items()
            if preset in presets
        ]

    triggers += [
        {**base_trigger, CONF_TYPE: trigger_type}
        for trigger_type, program in SCHEDULE_TRIGGER_TYPES.items()
        if not capabilityIds.isdisjoint(_program_block(program))
    ]

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger, as a state trigger on the entities behind it."""
    trigger_type = config[CONF_TYPE]

    if trigger_type in PRESET_TRIGGER_TYPES:
        state_config = {
            CONF_PLATFORM: "state",
            CONF_ENTITY_ID: config[CONF_ENTITY_ID],
            # On the attribute, not on the state: the state of a climate
            # entity is its HVAC mode, and a setpoint change would fire this.
            CONF_ATTRIBUTE: ATTR_PRESET_MODE,
            state_trigger.CONF_TO: PRESET_TRIGGER_TYPES[trigger_type],
        }

        if CONF_FOR in config:
            state_config[CONF_FOR] = config[CONF_FOR]
    else:
        entity_ids = _schedule_entity_ids(
            hass, config[CONF_DEVICE_ID], SCHEDULE_TRIGGER_TYPES[trigger_type]
        )
        if not entity_ids:
            # Reachable from a YAML automation naming a device that never had
            # the program, and from one whose device has been replaced since.
            raise InvalidDeviceAutomationConfig(
                f"Device {config[CONF_DEVICE_ID]} has no "
                f"{SCHEDULE_TRIGGER_TYPES[trigger_type]} program"
            )

        state_config = {
            CONF_PLATFORM: "state",
            CONF_ENTITY_ID: entity_ids,
            state_trigger.CONF_NOT_FROM: NOT_A_PROGRAM,
            state_trigger.CONF_NOT_TO: NOT_A_PROGRAM,
        }

    state_config = await state_trigger.async_validate_trigger_config(hass, state_config)
    return await state_trigger.async_attach_trigger(
        hass, state_config, action, trigger_info, platform_type="device"
    )


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """Offer `for` on the preset triggers, and nothing on the others.

    "Overridden for two hours" is a thing to automate on; "changed for two
    hours" is not, since a program that changed does not change back.
    """
    if config[CONF_TYPE] not in PRESET_TRIGGER_TYPES:
        return {}

    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }
