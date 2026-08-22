"""The repair issue raised for a device the model table does not know.

An unmapped device is the one problem this integration cannot solve on its
own : it needs a diagnostics dump from the person who owns the hardware. Until
now the only thing telling them so was a device called `Unknown product (…)`
and a paragraph in the README. These pin that the ask is made, that it is made
once per model rather than once per device, and -- the half that is easy to
forget -- that it goes away by itself when a release finally maps the thing.
"""

import io
import json
import re
from types import SimpleNamespace

import pytest

from custom_components.cozytouch import repairs
from custom_components.cozytouch.hub import Hub
from custom_components.cozytouch.model import get_model_infos

TRANSLATIONS = (
    "custom_components/cozytouch/strings.json",
    "custom_components/cozytouch/translations/en.json",
    "custom_components/cozytouch/translations/fr.json",
)

# A mapped id and one nothing claims, checked below so neither can drift into
# meaning the opposite of what the case it serves is named for.
MAPPED_MODEL = 235
UNMAPPED_MODEL = 99999


class FakeRegistry:
    """Records what the issue registry was asked to do."""

    def __init__(self):
        self.created = []
        self.deleted = []
        self.IssueSeverity = SimpleNamespace(WARNING="warning")

    def async_create_issue(self, hass, domain, issue_id, **kwargs):
        self.created.append((domain, issue_id, kwargs))

    def async_delete_issue(self, hass, domain, issue_id):
        self.deleted.append((domain, issue_id))


def check(monkeypatch, modelId, title="Salon"):
    """Run the check against a hub reporting one model, and report the calls."""
    registry = FakeRegistry()
    monkeypatch.setattr(repairs, "ir", registry)

    hub = SimpleNamespace(
        get_model_id=lambda: modelId,
        get_model_infos=lambda: get_model_infos(modelId),
    )
    repairs.async_check_model_mapping(
        SimpleNamespace(), SimpleNamespace(title=title), hub
    )

    return registry


def test_the_two_model_ids_these_cases_rest_on_still_mean_what_they_say():
    """A mapping added for 99999 would turn half of this file green for the
    wrong reason, and silently."""
    assert get_model_infos(MAPPED_MODEL)["type"].name != "UNKNOWN"
    assert get_model_infos(UNMAPPED_MODEL)["type"].name == "UNKNOWN"


def test_an_unmapped_model_asks_the_user_for_a_diagnostics_dump(monkeypatch):
    """Nothing else in the integration ever asks, and it cannot be inferred."""
    registry = check(monkeypatch, UNMAPPED_MODEL)

    assert len(registry.created) == 1
    domain, issue_id, kwargs = registry.created[0]

    assert domain == "cozytouch"
    assert issue_id == "unknown_model_99999"
    assert kwargs["translation_key"] == "unknown_model"
    assert kwargs["is_fixable"] is False
    assert kwargs["learn_more_url"] == repairs.ISSUE_TRACKER


def test_the_issue_names_the_device_and_the_id_a_report_has_to_carry(
    monkeypatch,
):
    """The model id is the whole content of the bug report being asked for."""
    registry = check(monkeypatch, UNMAPPED_MODEL, title="Sèche-serviettes")

    placeholders = registry.created[0][2]["translation_placeholders"]

    assert placeholders == {
        "device_name": "Sèche-serviettes",
        "model_id": "99999",
    }


def test_a_mapped_model_clears_the_issue_rather_than_raising_one(monkeypatch):
    """A release that adds the mapping is how this issue is meant to end, and
    the setup after the update is the only place that shows."""
    registry = check(monkeypatch, MAPPED_MODEL)

    assert registry.created == []
    assert registry.deleted == [("cozytouch", f"unknown_model_{MAPPED_MODEL}")]


def test_two_devices_of_one_model_ask_once(monkeypatch):
    """Keyed on the model, not the device : a pair of identical towel racks is
    one mapping to write, so it is one thing to ask for."""
    first = check(monkeypatch, UNMAPPED_MODEL, title="Salle de bain")
    second = check(monkeypatch, UNMAPPED_MODEL, title="Chambre")

    assert first.created[0][1] == second.created[0][1]


def test_a_hub_that_cannot_name_its_own_device_says_nothing(monkeypatch):
    """Better silent than an issue titled after a device nobody can find."""
    registry = check(monkeypatch, None)

    assert registry.created == []
    assert registry.deleted == []


def test_the_model_id_comes_back_as_the_api_reported_it():
    """get_model_infos answers what the table made of the id; a bug report
    needs the id itself, which is what this accessor is for."""
    hub = SimpleNamespace(
        _devices=[
            {"deviceId": 1, "modelId": 1457},
            {"deviceId": 2, "modelId": 99999},
        ],
        _deviceId=2,
    )

    assert Hub.get_model_id(hub) == 99999
    assert Hub.get_model_id(hub, 1) == 1457


def test_a_device_the_hub_does_not_hold_has_no_model_id():
    """The caller has to be able to tell "not mapped" from "not there"."""
    hub = SimpleNamespace(_devices=[], _deviceId=7)

    assert Hub.get_model_id(hub) is None


@pytest.mark.parametrize("path", TRANSLATIONS)
def test_the_issue_is_translated_and_fills_in_both_placeholders(path):
    """A placeholder the strings do not use makes the issue unreadable : the
    device it is about is only ever named through them."""
    with io.open(path, encoding="utf-8") as handle:
        issue = json.load(handle)["issues"]["unknown_model"]

    written = set(re.findall(r"{(\w+)}", issue["title"] + issue["description"]))

    assert issue["title"]
    assert written == {"device_name", "model_id"}
