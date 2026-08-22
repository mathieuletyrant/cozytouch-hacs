"""Repair issues the integration raises about itself.

A device the model table does not know still gets entities -- the generic
capabilities work -- but the specifics are missing and its name reads
`Unknown product (…)`. The user has no reason to connect that string to
anything they can do about it, so the fix has always depended on someone
thinking to open an issue and attach a diagnostics dump. This asks for it
instead, at the one moment it is obvious the mapping is missing, and hands
over a report that is already written.
"""

from __future__ import annotations

from urllib.parse import urlencode

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .model import CozytouchDeviceType

ISSUE_TRACKER = "https://github.com/mathieuletyrant/cozytouch-hacs/issues"

# The form the link opens. Lives in .github/ISSUE_TEMPLATE/.
ISSUE_FORM = "unmapped_model.yml"

UNKNOWN_MODEL_ISSUE = "unknown_model_{modelId}"

# The API lists things that are not products. A thermal zone is the one seen so
# far : it hangs off a gateway, reports a model id no table knows, and there is
# nothing behind it to describe -- no mapping would give it an entity, so its
# owner has nothing to send and no reason to be asked.
#
# Two markers, neither of them certain. "---" is the longName placeholder
# docs/api-surface.md records against the thermal zones of the one probed
# account (models 1505-1507). The prefixes are names reported from an account
# rather than read off a capture kept here, so they are matched loosely, on
# either name, and the list is meant to grow as more turn up. A prefix rather
# than a substring on purpose : people call a real device "Zone de nuit".
PLACEHOLDER_LONG_NAME = "---"
VIRTUAL_DEVICE_PREFIXES = ("thzone",)

# Where the acknowledgement is kept. Written by the fix flow, read on every
# setup: the model stays unmapped until a release maps it, so without this the
# issue would come back at each restart at someone who already did their part.
REPORTED_MODELS = "reported_models"


def _is_not_a_product(hub) -> bool:
    """Whether the API is listing an internal object rather than hardware."""
    reported = [name for name in hub.get_reported_names() if name]

    if any(name.strip() == PLACEHOLDER_LONG_NAME for name in reported):
        return True

    return any(
        name.lower().startswith(prefix)
        for name in reported
        for prefix in VIRTUAL_DEVICE_PREFIXES
    )


def _report_url(modelId: int, unmapped: list[int]) -> str:
    """A new-issue link with the report already filled in.

    Deliberately only the model id and the capability ids nothing names : those
    are what a mapping is built from, and they say nothing about the household.
    Values stay out -- among them are the wifi SSID (219) and the gateway
    serial -- and so does the device name, which people call after a room or a
    child. A URL is clicked without being read. The dump the form asks for
    carries all of that, stripped, and is attached knowingly.
    """
    query = urlencode(
        {
            # The keys after `template` are the ids of that form's fields, which
            # is how GitHub fills them in. Renaming one there breaks the link
            # quietly -- it just arrives empty -- so the two move together.
            "template": ISSUE_FORM,
            "title": f"Unmapped model {modelId}",
            "model_id": str(modelId),
            "capability_ids": ", ".join(str(id) for id in unmapped) or "none",
        }
    )

    return f"{ISSUE_TRACKER}/new?{query}"


@callback
def async_check_model_mapping(
    hass: HomeAssistant, entry: ConfigEntry, hub
) -> None:
    """Raise, or clear, the "this model is not mapped" issue for an entry.

    Keyed on the model id rather than on the device, so a pair of identical
    towel racks asks once. Cleared on the way through as well as raised: a
    release that adds the mapping is the expected end of this issue, and the
    setup that follows the update is where that shows.

    Only the device this entry drives is considered. The account may hold
    others, but a diagnostics dump only carries capability values for the
    configured one -- which is what a mapping gets built from -- so asking
    about the rest would ask for a file that cannot answer.
    """
    modelId = hub.get_model_id()
    if modelId is None:
        return

    issue_id = UNKNOWN_MODEL_ISSUE.format(modelId=modelId)

    mapped = hub.get_model_infos()["type"] is not CozytouchDeviceType.UNKNOWN
    if mapped or _is_not_a_product(hub):
        # Both are reasons there is nothing to ask, and either can become true
        # for a device that was already asked about, so the issue goes with it.
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    if modelId in entry.options.get(REPORTED_MODELS, []):
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        learn_more_url=ISSUE_TRACKER,
        translation_key="unknown_model",
        translation_placeholders={
            "device_name": entry.title,
            "model_id": str(modelId),
        },
        data={"entry_id": entry.entry_id, "model_id": modelId},
    )


class UnknownModelRepairFlow(RepairsFlow):
    """Hands over a written report, and stops asking once it is sent."""

    def __init__(self, entry_id: str, modelId: int) -> None:
        """Remember which entry and model the issue was raised for."""
        self._entry_id = entry_id
        self._modelId = modelId

    async def async_step_init(self, user_input=None):
        """Start at the only step there is."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Show the report, and record that it was sent."""
        if user_input is not None:
            self._async_remember_it_was_reported()
            return self.async_create_entry(data={})

        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        unmapped: list[int] = []
        if entry is not None and hasattr(entry, "runtime_data"):
            # The ids are read now rather than stored on the issue: a device
            # that gained a capability since setup should report the one it has.
            _, unmapped = entry.runtime_data.get_capability_names()

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "model_id": str(self._modelId),
                "capability_ids": ", ".join(str(id) for id in unmapped) or "-",
                "report_url": _report_url(self._modelId, unmapped),
            },
        )

    @callback
    def _async_remember_it_was_reported(self) -> None:
        """Take this model off the list of things to ask about.

        Stored on the config entry, which reloads the integration on any write
        -- the same reload changing an option causes. That is the cost of the
        issue not coming back at the next restart.
        """
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return

        reported = list(entry.options.get(REPORTED_MODELS, []))
        if self._modelId in reported:
            return

        self.hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, REPORTED_MODELS: [*reported, self._modelId]},
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict | None
) -> RepairsFlow:
    """Build the flow behind the button in the repair dialog."""
    data = data or {}

    return UnknownModelRepairFlow(data.get("entry_id"), data.get("model_id"))
