"""What a voice assistant is allowed to do with a device's weekly program.

Home Assistant discovers this module by name : the `llm` integration imports
`<integration>/llm.py` from every loaded integration and asks it for tools,
so nothing here has to be registered and nothing outside it has to change.
That platform is newer than the Home Assistant version `hacs.json` declares,
which is why this module is not in the floor test's list -- an install too
old to have the platform never imports it. See docs/decisions.md.

The two tools are deliberately not the two services. A service writes a whole
day, because that is what the device stores; a person asks for a stretch of
one. Handing the raw write to an assistant means asking a language model to
copy nine slots back unchanged, and the day that gets written is the day it
remembered. `apply_period` does the merge instead.
"""

from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.llm import LLM_API_ASSIST, LLMContext, Tool, ToolInput
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN, PROGRAM_DAYS, WRITABLE_PROGRAM_BLOCKS
from .services import (
    DAY_GROUPS,
    SERVICE_GET_SCHEDULE,
    SERVICE_SET_SCHEDULE,
    apply_period,
    expand_days,
)

PROMPT = (
    "A Cozytouch heater or air conditioner keeps its own weekly program, which "
    "runs whether or not Home Assistant is up. A day is a list of slots, each "
    "one a time it starts and a temperature it asks for, and a slot runs until "
    "the next one starts. Read the program before answering questions about it, "
    "and change it with the period tool rather than describing the change."
)

_ENTITY = vol.Required(
    "entity_id",
    description="The climate entity, as its entity id, for example climate.salon",
)
_PROGRAM = vol.Required(
    "program",
    description="Which of the device's two programs, heating or cooling",
)
_DAYS = vol.Required(
    "days",
    description=(
        "The days to change. Either day names, or the shortcuts "
        f"{', '.join(DAY_GROUPS)}"
    ),
)


class ReadSchedule(Tool):
    """Read a device's weekly program back."""

    name = "cozytouch_get_schedule"
    description = (
        "Read the weekly program a Cozytouch heater or air conditioner keeps in "
        "its own memory. Answers with each day's slots: when each one starts and "
        "the temperature it asks for, a slot running until the next one."
    )
    parameters = vol.Schema(
        {_ENTITY: cv.entity_id, _PROGRAM: vol.In(WRITABLE_PROGRAM_BLOCKS)}
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Answer with the program, as the device holds it."""
        args = self.parameters(tool_input.tool_args)
        return await _read(hass, llm_context, args["entity_id"], args["program"])


class SetPeriod(Tool):
    """Hold one temperature over a stretch of a day, on the days asked for."""

    name = "cozytouch_set_schedule_period"
    description = (
        "Have a Cozytouch heater or air conditioner hold one temperature between "
        "two times of day, on the days given, leaving the rest of each day as it "
        "is. Use this for any change to the program: it reads the day first and "
        "puts back whatever was running when the period ends."
    )
    parameters = vol.Schema(
        {
            _ENTITY: cv.entity_id,
            _PROGRAM: vol.In(WRITABLE_PROGRAM_BLOCKS),
            _DAYS: vol.All(
                cv.ensure_list,
                vol.Length(min=1),
                [vol.In([*PROGRAM_DAYS, *DAY_GROUPS])],
            ),
            vol.Required(
                "start", description="When the period starts, as HH:MM"
            ): cv.time,
            vol.Required(
                "end",
                description=(
                    "When the period ends, as HH:MM. 00:00 means the end of the "
                    "day"
                ),
            ): cv.time,
            vol.Required(
                "temperature", description="The temperature to hold, in °C"
            ): vol.Coerce(float),
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> JsonObjectType:
        """Merge the period into each day, then write the days that changed."""
        args = self.parameters(tool_input.tool_args)
        entity_id, program = args["entity_id"], args["program"]

        stored = (await _read(hass, llm_context, entity_id, program))["days"]

        # Days that end up identical are written together : one call is one
        # refresh of the device, and seven of them for "every day" is a poll
        # storm for a single sentence.
        together: dict[str, list[str]] = {}
        for day in expand_days(args["days"]):
            if day not in stored:
                continue
            slots = apply_period(
                stored[day], args["start"], args["end"], args["temperature"]
            )
            written = [
                {"time": slot["time"].isoformat(timespec="minutes"),
                 "temperature": slot["temperature"]}
                for slot in slots
            ]
            together.setdefault(json.dumps(written), []).append(day)

        for shape, days in together.items():
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SET_SCHEDULE,
                {
                    "entity_id": entity_id,
                    "program": program,
                    "days": days,
                    "slots": json.loads(shape),
                },
                blocking=True,
                context=llm_context.context,
            )

        # The program as it now stands, so the assistant reports what the
        # device holds rather than what it asked for.
        return await _read(hass, llm_context, entity_id, program)


async def _read(
    hass: HomeAssistant, llm_context: LLMContext, entity_id: str, program: str
) -> dict[str, Any]:
    """The get_schedule response for one entity."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_SCHEDULE,
        {"entity_id": entity_id, "program": program},
        blocking=True,
        return_response=True,
        context=llm_context.context,
    )
    return (response or {})[entity_id]


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Offer the program tools to Assist, and only where there is a device."""
    if api_id != LLM_API_ASSIST or not hass.config_entries.async_entries(DOMAIN):
        return None

    return LLMTools(tools=[ReadSchedule(), SetPeriod()], prompt=PROMPT)
