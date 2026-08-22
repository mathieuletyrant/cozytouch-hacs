"""Repair issues the integration raises about itself.

A device the model table does not know still gets entities -- the generic
capabilities work -- but the specifics are missing and its name reads
`Unknown product (…)`. The user has no reason to connect that string to
anything they can do about it, so the fix has always depended on someone
thinking to open an issue and attach a diagnostics dump. This asks for it
instead, at the one moment it is obvious the mapping is missing.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .model import CozytouchDeviceType

ISSUE_TRACKER = "https://github.com/mathieuletyrant/cozytouch-hacs/issues"

UNKNOWN_MODEL_ISSUE = "unknown_model_{modelId}"


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

    if hub.get_model_infos()["type"] is not CozytouchDeviceType.UNKNOWN:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        learn_more_url=ISSUE_TRACKER,
        translation_key="unknown_model",
        translation_placeholders={
            "device_name": entry.title,
            "model_id": str(modelId),
        },
    )
