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

# Where the acknowledgement is kept. Written by the fix flow, read on every
# setup: the model stays unmapped until a release maps it, so without this the
# issue would come back at each restart at someone who already did their part.
REPORTED_MODELS = "reported_models"


def _account_report(entry: ConfigEntry) -> dict[int, list[int]]:
    """Every unmapped model on the account, with the ids nothing names for it.

    One entry per account, so this reads one account rather than scanning the
    entry store. It also no longer depends on which devices somebody added :
    the setup view carries a capability list for every device on the account
    and the account keeps all of them, so an unmapped model contributes its
    capability ids whether it has a subentry or not. That used to be the half
    of a report that was missing exactly when it mattered -- hardware nobody
    has mapped is hardware nobody has added yet.
    """
    runtime = entry.runtime_data
    report: dict[int, list[int]] = {
        modelId: [] for modelId in runtime.account.get_unmapped_models()
    }

    # Any hub answers for any device on its account : the mapping is keyed on
    # the model, and the capabilities it reads are the account's.
    hub = next(iter(runtime.hubs.values()), None)
    if hub is None:
        return report

    for device in runtime.account.devices:
        modelId = device["modelId"]
        if modelId not in report:
            continue

        _, unnamed = hub.get_capability_names(device["deviceId"])
        # Several devices can share one unmapped model; a silent one must not
        # overwrite what a talkative sibling reported.
        if unnamed:
            report[modelId] = unnamed

    return report


def _report_url(report: dict[int, list[int]]) -> str:
    """A new-issue link with the report already filled in.

    Deliberately only the model ids and the capability ids nothing names :
    those are what a mapping is built from, and they say nothing about the
    household. Values stay out -- among them are the wifi SSID (219) and the
    gateway serial -- and so does the device name, which people call after a
    room or a child. A URL is clicked without being read. The dump the form
    asks for carries all of that, stripped, and is attached knowingly.
    """
    models = sorted(report)
    query = urlencode(
        {
            # The keys after `template` are the ids of that form's fields, which
            # is how GitHub fills them in. Renaming one there breaks the link
            # quietly -- it just arrives empty -- so the two move together.
            "template": ISSUE_FORM,
            "title": "Unmapped model" + ("s " if len(models) > 1 else " ")
            + ", ".join(str(modelId) for modelId in models),
            "model_ids": ", ".join(str(modelId) for modelId in models),
            "capability_ids": "\n".join(
                f"{modelId}: "
                + (
                    ", ".join(str(capabilityId) for capabilityId in report[modelId])
                    or "none"
                )
                for modelId in models
            ),
        }
    )

    return f"{ISSUE_TRACKER}/new?{query}"


def _already_reported(hass: HomeAssistant) -> set[int]:
    """Models somebody has already sent a report for.

    Read across every entry, because one report speaks for the whole account :
    answering the dialog on one device has to settle the devices it covered.
    """
    reported: set[int] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        reported.update(entry.options.get(REPORTED_MODELS, []))

    return reported


@callback
def async_check_model_mapping(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Raise, or clear, the "this model is not mapped" issue for an account.

    Keyed on the model id rather than on the device, so a pair of identical
    towel racks asks once. Cleared on the way through as well as raised: a
    release that adds the mapping is the expected end of this issue, and the
    setup that follows the update is where that shows.

    Every device the entry has a subentry for is considered, which is what the
    account holds a hub for.

    Everything the table does not know is asked about, including the thermal
    zones the API returns as if they were devices. Nothing separates one of
    those from a real device that nobody has mapped yet : the gateway's id
    sits in masterDeviceId on both, and modelFamily is null on both. Any rule
    would be a guess, and the two ways of being wrong do not cost the same --
    a zone reported is an issue closed in seconds, a real device silenced is
    someone never finding out why their hardware is half-supported.
    """
    reported = _already_reported(hass)
    # One ask per model, and every device of the account is walked, so a pair
    # of identical towel racks has to be recognised here rather than left to
    # the issue registry to overwrite -- the second one would replace the
    # first one's device name and ask about the same mapping twice.
    asked: set[int] = set()

    for subentry_id, hub in entry.runtime_data.hubs.items():
        modelId = hub.get_model_id()
        if modelId is None:
            continue

        issue_id = UNKNOWN_MODEL_ISSUE.format(modelId=modelId)

        if hub.get_model_infos()["type"] is not CozytouchDeviceType.UNKNOWN:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue

        if modelId in reported or modelId in asked:
            continue

        asked.add(modelId)
        subentry = entry.subentries[subentry_id]
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            learn_more_url=ISSUE_TRACKER,
            translation_key="unknown_model",
            translation_placeholders={
                "device_name": subentry.title,
                "model_id": str(modelId),
            },
            data={"entry_id": entry.entry_id, "model_id": modelId},
        )


class UnknownModelRepairFlow(RepairsFlow):
    """Hands over one written report, and stops asking about all of it."""

    def __init__(self, entry_id: str, modelId: int) -> None:
        """Remember which entry and model the issue was raised for."""
        self._entry_id = entry_id
        self._modelId = modelId

    async def async_step_init(self, user_input=None):
        """Start at the only step there is."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Show the report, and settle everything it covered."""
        report = self._report()

        if user_input is not None:
            self._async_remember_it_was_reported(report)
            self._async_drop_the_other_issues(report)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "model_id": str(self._modelId),
                "model_ids": ", ".join(str(modelId) for modelId in sorted(report))
                or str(self._modelId),
                "report_url": _report_url(report or {self._modelId: []}),
            },
        )

    def _report(self) -> dict[int, list[int]]:
        """What this dialog speaks for.

        Read when the dialog opens rather than stored on the issue : a device
        that gained a capability, or an entry added since, belongs in the
        report someone is about to send.
        """
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None or getattr(entry, "runtime_data", None) is None:
            return {}

        return _account_report(entry)

    @callback
    def _async_remember_it_was_reported(self, report: dict[int, list[int]]) -> None:
        """Take everything the report covered off the list of things to ask.

        Written to the entry the dialog was opened from, and read back across
        every entry : an unmapped model is a gap in the table, so a report for
        it answers for whoever else owns the same hardware.
        """
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return

        reported = list(entry.options.get(REPORTED_MODELS, []))
        fresh = [modelId for modelId in sorted(report) if modelId not in reported]
        if not fresh:
            return

        self.hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, REPORTED_MODELS: [*reported, *fresh]},
        )

    @callback
    def _async_drop_the_other_issues(self, report: dict[int, list[int]]) -> None:
        """Close the repairs raised for the other devices in the report.

        One issue was sent for all of them, so leaving their dialogs standing
        would ask the same person for the same file again. The one this flow
        belongs to is deleted by Home Assistant when the flow finishes.
        """
        for modelId in report:
            if modelId != self._modelId:
                ir.async_delete_issue(
                    self.hass, DOMAIN, UNKNOWN_MODEL_ISSUE.format(modelId=modelId)
                )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict | None
) -> RepairsFlow:
    """Build the flow behind the button in the repair dialog."""
    data = data or {}

    return UnknownModelRepairFlow(data.get("entry_id"), data.get("model_id"))
