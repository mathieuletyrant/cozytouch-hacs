"""The repair raised for a device the model table does not know.

An unmapped device is the one problem this integration cannot solve on its
own : it needs a diagnostics dump, and the model id, from the person who owns
the hardware. Until now the only thing telling them so was a device called
`Unknown product (…)` and a paragraph in the README.

The cases worth keeping are the ones about what the ask costs the user. It is
made once per model rather than once per device; it stops once they have
answered; it goes away by itself when a release maps the thing; and the report
it hands them carries the model id and nothing about their household.
"""

import asyncio
import io
import json
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

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


class FakeEntries:
    """The config entry store, as much of it as a repair flow touches."""

    def __init__(self, entry):
        self.entry = entry
        self.updated = []

    def async_get_entry(self, entry_id):
        return self.entry if entry_id == self.entry.entry_id else None

    def async_update_entry(self, entry, options=None):
        self.updated.append(options)
        entry.options = options


def make_entry(title="Salon", options=None, unmapped=(101, 102)):
    """A config entry whose hub reports the given unmapped capability ids."""
    return SimpleNamespace(
        entry_id="entry",
        title=title,
        options=options or {},
        runtime_data=SimpleNamespace(
            get_capability_names=lambda: ({}, list(unmapped))
        ),
    )


def check(monkeypatch, modelId, entry=None):
    """Run the check against a hub reporting one model, and report the calls."""
    registry = FakeRegistry()
    monkeypatch.setattr(repairs, "ir", registry)

    hub = SimpleNamespace(
        get_model_id=lambda: modelId,
        get_model_infos=lambda: get_model_infos(modelId),
    )
    repairs.async_check_model_mapping(
        SimpleNamespace(), entry or make_entry(), hub
    )

    return registry


def run_flow(entry, modelId=UNMAPPED_MODEL, user_input=None):
    """Drive the fix flow one step, the way the dialog does."""
    entries = FakeEntries(entry)

    flow = repairs.UnknownModelRepairFlow(entry.entry_id, modelId)
    flow.hass = SimpleNamespace(config_entries=entries)
    flow.flow_id = "flow"
    flow.handler = "cozytouch"

    # The dialog opens on init and comes back to the step the form named, so
    # a submission is not init being called a second time.
    step = flow.async_step_confirm if user_input is not None else flow.async_step_init
    result = asyncio.run(step(user_input))

    return result, entries


def test_the_two_model_ids_these_cases_rest_on_still_mean_what_they_say():
    """A mapping added for 99999 would turn half of this file green for the
    wrong reason, and silently."""
    assert get_model_infos(MAPPED_MODEL)["type"].name != "UNKNOWN"
    assert get_model_infos(UNMAPPED_MODEL)["type"].name == "UNKNOWN"


def test_an_unmapped_model_asks_the_user_for_a_report(monkeypatch):
    """Nothing else in the integration ever asks, and it cannot be inferred."""
    registry = check(monkeypatch, UNMAPPED_MODEL)

    assert len(registry.created) == 1
    domain, issue_id, kwargs = registry.created[0]

    assert domain == "cozytouch"
    assert issue_id == "unknown_model_99999"
    assert kwargs["translation_key"] == "unknown_model"
    assert kwargs["learn_more_url"] == repairs.ISSUE_TRACKER


def test_the_dialog_has_something_to_click(monkeypatch):
    """Fixable is what puts a button there; without it the dialog is a wall of
    text about a file the user has to go and find."""
    kwargs = check(monkeypatch, UNMAPPED_MODEL).created[0][2]

    assert kwargs["is_fixable"] is True
    assert kwargs["data"] == {"entry_id": "entry", "model_id": UNMAPPED_MODEL}


def test_the_issue_names_the_device_and_the_id_a_report_has_to_carry(
    monkeypatch,
):
    """The model id is the whole content of the bug report being asked for."""
    entry = make_entry(title="Sèche-serviettes")

    registry = check(monkeypatch, UNMAPPED_MODEL, entry)

    assert registry.created[0][2]["translation_placeholders"] == {
        "device_name": "Sèche-serviettes",
        "model_id": "99999",
    }


def test_a_mapped_model_clears_the_issue_rather_than_raising_one(monkeypatch):
    """A release that adds the mapping is how this issue is meant to end, and
    the setup after the update is the only place that shows."""
    registry = check(monkeypatch, MAPPED_MODEL)

    assert registry.created == []
    assert registry.deleted == [("cozytouch", f"unknown_model_{MAPPED_MODEL}")]


def test_a_model_already_reported_is_not_asked_about_again(monkeypatch):
    """The model stays unmapped until a release maps it, so without this the
    issue comes back at every restart at someone who already answered."""
    entry = make_entry(options={repairs.REPORTED_MODELS: [UNMAPPED_MODEL]})

    registry = check(monkeypatch, UNMAPPED_MODEL, entry)

    assert registry.created == []


def test_two_devices_of_one_model_ask_once(monkeypatch):
    """Keyed on the model, not the device : a pair of identical towel racks is
    one mapping to write, so it is one thing to ask for."""
    first = check(monkeypatch, UNMAPPED_MODEL, make_entry(title="Salle de bain"))
    second = check(monkeypatch, UNMAPPED_MODEL, make_entry(title="Chambre"))

    assert first.created[0][1] == second.created[0][1]


def test_a_hub_that_cannot_name_its_own_device_says_nothing(monkeypatch):
    """Better silent than an issue titled after a device nobody can find."""
    registry = check(monkeypatch, None)

    assert registry.created == []
    assert registry.deleted == []


# --- the button ----------------------------------------------------------


def test_the_dialog_shows_the_ids_a_mapping_is_built_from():
    """Read at the moment the dialog opens, not stored when the issue was
    raised : a device that gained a capability since setup reports the one it
    has now."""
    result, _ = run_flow(make_entry(unmapped=(101, 207)))

    placeholders = result["description_placeholders"]

    assert result["step_id"] == "confirm"
    assert placeholders["model_id"] == "99999"
    assert placeholders["capability_ids"] == "101, 207"


def test_the_link_carries_the_report_already_written():
    """The friction was never willingness, it was knowing what to write."""
    result, _ = run_flow(make_entry(unmapped=(101, 207)))

    url = urlparse(result["description_placeholders"]["report_url"])
    body = parse_qs(url.query)["body"][0]

    assert url.path.endswith("/issues/new")
    assert "99999" in parse_qs(url.query)["title"][0]
    assert "101, 207" in body


def test_the_link_says_nothing_about_the_household():
    """A URL is clicked without being read. Capability values hold the wifi
    SSID and the gateway serial, and people name a device after a room or a
    child -- none of that goes in one. The dump does, and is attached
    knowingly."""
    result, _ = run_flow(make_entry(title="Chambre de Léa", unmapped=(101,)))

    report_url = result["description_placeholders"]["report_url"]

    assert "Chambre" not in report_url
    assert "L%C3%A9a" not in report_url


def test_a_device_with_nothing_unmapped_still_reads_as_a_sentence():
    """A model can be unknown while every capability it reports is named."""
    result, _ = run_flow(make_entry(unmapped=()))

    assert result["description_placeholders"]["capability_ids"] == "-"


def test_submitting_stops_the_asking():
    """What the button is for : the issue is deleted by the flow, and this is
    what keeps the next setup from raising it again."""
    entry = make_entry()

    result, entries = run_flow(entry, user_input={})

    assert result["type"] == "create_entry"
    assert entries.updated == [{repairs.REPORTED_MODELS: [UNMAPPED_MODEL]}]


def test_submitting_twice_does_not_list_the_model_twice():
    """The issue can be raised again between a restart and the write landing."""
    entry = make_entry(options={repairs.REPORTED_MODELS: [UNMAPPED_MODEL]})

    _, entries = run_flow(entry, user_input={})

    assert entries.updated == []


def test_an_entry_that_went_away_mid_flow_is_not_written_to():
    """Removing the integration while its repair dialog is open is rare and
    entirely allowed."""
    entry = make_entry()
    entries = FakeEntries(entry)
    entries.entry = SimpleNamespace(entry_id="gone")

    flow = repairs.UnknownModelRepairFlow("entry", UNMAPPED_MODEL)
    flow.hass = SimpleNamespace(config_entries=entries)
    flow.flow_id, flow.handler = "flow", "cozytouch"

    asyncio.run(flow.async_step_confirm({}))

    assert entries.updated == []


# --- what the report is made of ------------------------------------------


def test_the_mapping_splits_what_it_names_from_what_it_does_not():
    """One rule, read by the diagnostics dump and by the repair alike."""
    hub = SimpleNamespace(
        _devices=[
            {
                "deviceId": 1,
                "modelId": 235,
                "capabilities": [
                    {"capabilityId": 100, "value": "0"},
                    {"capabilityId": 999999, "value": "0"},
                ],
            }
        ],
        _deviceId=1,
    )

    mapped, unmapped = Hub.get_capability_names(hub)

    assert unmapped == [999999]
    assert 100 in mapped


def test_a_device_the_hub_does_not_hold_splits_into_nothing():
    """The caller has to be able to tell "names nothing" from "not there"."""
    hub = SimpleNamespace(_devices=[], _deviceId=7)

    assert Hub.get_capability_names(hub) == ({}, [])


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


# --- the strings ---------------------------------------------------------


@pytest.mark.parametrize("path", TRANSLATIONS)
def test_the_dialog_only_asks_for_placeholders_that_are_filled_in(path):
    """A placeholder nothing supplies reaches the user as a literal `{brace}`,
    and the link is the one thing in there that has to work."""
    with io.open(path, encoding="utf-8") as handle:
        issue = json.load(handle)["issues"]["unknown_model"]

    step = issue["fix_flow"]["step"]["confirm"]
    written = set(re.findall(r"{(\w+)}", step["title"] + step["description"]))

    assert set(re.findall(r"{(\w+)}", issue["title"])) == {"device_name"}
    assert written == {"model_id", "capability_ids", "report_url"}
    assert "{report_url}" in step["description"]
