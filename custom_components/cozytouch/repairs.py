"""Repair issues the integration raises about itself.

A model the table does not know is asked about at the one moment it is obvious
the mapping is missing, with the report already written. See docs/decisions.md.
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

# Where the acknowledgement is kept, so the issue does not come back at each
# restart at someone who already did their part. See docs/decisions.md.
REPORTED_MODELS = "reported_models"


def _account_report(entry: ConfigEntry) -> dict[int, list[int]]:
    """Every unmapped model on the account, with the ids nothing names for it.

    Covers devices nobody added, which is most unmapped hardware. See
    docs/decisions.md.
    """
    runtime = entry.runtime_data
    report: dict[int, list[int]] = {
        modelId: [] for modelId in runtime.account.get_unmapped_models()
    }

    # Any hub answers for any device on its account.
    hub = next(iter(runtime.hubs.values()), None)
    if hub is None:
        return report

    for device in runtime.account.devices:
        modelId = device["modelId"]
        if modelId not in report:
            continue

        _, unnamed = hub.get_capability_names(device["deviceId"])
        # A silent device must not overwrite a talkative sibling's report.
        if unnamed:
            report[modelId] = unnamed

    return report


def _report_url(report: dict[int, list[int]]) -> str:
    """A new-issue link with the report already filled in.

    Ids only : a URL is clicked without being read, so nothing about the
    household goes in one. See docs/decisions.md.
    """
    models = sorted(report)
    query = urlencode(
        {
            # The keys below are that form's own field ids. See
            # docs/decisions.md.
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
    """Models somebody has already sent a report for, across every entry."""
    reported: set[int] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        reported.update(entry.options.get(REPORTED_MODELS, []))

    return reported


@callback
def async_check_model_mapping(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Raise, or clear, the "this model is not mapped" issue for an account.

    Keyed on the model id rather than on the device, and cleared as well as
    raised. See docs/decisions.md.
    """
    reported = _already_reported(hass)
    # One ask per model, recognised here rather than left to the registry to
    # overwrite. See docs/decisions.md.
    asked: set[int] = set()

    for subentry_id, hub in entry.runtime_data.hubs.items():
        modelId = hub.get_model_id()
        if modelId is None:
            continue

        issue_id = UNKNOWN_MODEL_ISSUE.format(modelId=modelId)

        if hub.get_model_infos().type is not CozytouchDeviceType.UNKNOWN:
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
        """What this dialog speaks for, read as it opens rather than stored."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None or getattr(entry, "runtime_data", None) is None:
            return {}

        return _account_report(entry)

    @callback
    def _async_remember_it_was_reported(self, report: dict[int, list[int]]) -> None:
        """Take everything the report covered off the list of things to ask."""
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
        """Close the repairs raised for the other models in the report.

        The one this flow belongs to is deleted by Home Assistant.
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
