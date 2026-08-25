"""The repair raised for a device the model table does not know.

An unmapped device is the one problem this integration cannot solve on its
own : it needs a diagnostics dump, and the model ids, from the person who owns
the hardware. Until now the only thing telling them so was a device called
`Unknown product (…)` and a paragraph in the README.

The cases worth keeping are the ones about what the ask costs that person. It
is made once per model rather than once per device; one dialog speaks for
every unmapped device on the account, so a gateway with three unknown zones is
one issue and not four; answering settles all of them; and the report carries
the ids and nothing about their household.

One case pins something that was taken out rather than put in : no attempt is
made to work out which devices are not really products.
"""

import asyncio
import json
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
import yaml

from custom_components.cozytouch import repairs
from custom_components.cozytouch.hub import Hub
from custom_components.cozytouch.model import get_model_infos

TRANSLATIONS = (
    "custom_components/cozytouch/strings.json",
    "custom_components/cozytouch/translations/en.json",
    "custom_components/cozytouch/translations/fr.json",
)

# A mapped id and two nothing claims, checked below so none of them can drift
# into meaning the opposite of what the case it serves is named for.
MAPPED_MODEL = 235
UNMAPPED_MODEL = 99999
OTHER_UNMAPPED_MODEL = 88888


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
    """The config entry store, as much of it as the repair touches."""

    def __init__(self, entries):
        self.entries = list(entries)
        self.updated = []

    def async_entries(self, domain):
        return list(self.entries)

    def async_get_entry(self, entry_id):
        return next((e for e in self.entries if e.entry_id == entry_id), None)

    def async_update_entry(self, entry, options=None):
        self.updated.append(options)
        entry.options = options


def make_entry(
    modelId=UNMAPPED_MODEL,
    title="Salon",
    options=None,
    unmapped=(101, 102),
    account=None,
    entry_id="entry",
    deviceName=None,
):
    """An entry whose hub reports one model and sees the given account.

    `deviceName` matters for one kind of device: a zone is recognised by the
    name the API gives it rather than by its model id, so a hub that does not
    hand the name over reports it as unmapped.
    """
    if account is None:
        account = [modelId] if modelId is not None else []

    hub = SimpleNamespace(
        get_model_id=lambda: modelId,
        get_model_infos=lambda: get_model_infos(modelId, None, deviceName),
        get_unmapped_models=lambda: sorted(account),
        get_capability_names=lambda: ({}, list(unmapped)),
    )

    return SimpleNamespace(
        entry_id=entry_id,
        title=title,
        options=options or {},
        runtime_data=hub,
    )


def make_hass(entries):
    """A hass stand-in carrying nothing but the entry store."""
    return SimpleNamespace(config_entries=FakeEntries(entries))


def check(monkeypatch, modelId, entry=None, others=()):
    """Run the check for one entry, and report what the registry was asked."""
    registry = FakeRegistry()
    monkeypatch.setattr(repairs, "ir", registry)

    entry = entry if entry is not None else make_entry(modelId)
    hass = make_hass([entry, *others])
    repairs.async_check_model_mapping(hass, entry, entry.runtime_data)

    return registry


def run_flow(monkeypatch, entry, others=(), modelId=UNMAPPED_MODEL, user_input=None):
    """Drive the fix flow one step, the way the dialog does."""
    registry = FakeRegistry()
    monkeypatch.setattr(repairs, "ir", registry)
    hass = make_hass([entry, *others])

    flow = repairs.UnknownModelRepairFlow(entry.entry_id, modelId)
    flow.hass = hass
    flow.flow_id = "flow"
    flow.handler = "cozytouch"

    # The dialog opens on init and comes back to the step the form named, so
    # a submission is not init being called a second time.
    step = flow.async_step_confirm if user_input is not None else flow.async_step_init

    return asyncio.run(step(user_input)), hass.config_entries, registry


def test_the_model_ids_these_cases_rest_on_still_mean_what_they_say():
    """A mapping added for 99999 would turn half of this file green for the
    wrong reason, and silently.
    """
    assert get_model_infos(MAPPED_MODEL)["type"].name != "UNKNOWN"
    assert get_model_infos(UNMAPPED_MODEL)["type"].name == "UNKNOWN"
    assert get_model_infos(OTHER_UNMAPPED_MODEL)["type"].name == "UNKNOWN"
    # And the zone the case below rests on is mapped through its *name*, which
    # is the whole reason it stops asking.
    assert get_model_infos(1505, None, "THZONE_0")["type"].name == "ZONE"


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
    text about a file the user has to go and find.
    """
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
    the setup after the update is the only place that shows.
    """
    registry = check(monkeypatch, MAPPED_MODEL)

    assert registry.created == []
    assert registry.deleted == [("cozytouch", f"unknown_model_{MAPPED_MODEL}")]


def test_a_zone_is_not_a_device_to_report(monkeypatch):
    """A THZONE is a zone of a ducted heat pump, and a six-zone installation
    used to raise this dialog six times over hardware working as designed --
    asking for a dump about something nobody needs to map.
    """
    entry = make_entry(modelId=1505, deviceName="THZONE_0")

    registry = check(monkeypatch, 1505, entry)

    assert registry.created == []
    assert registry.deleted == [("cozytouch", "unknown_model_1505")]


def test_a_model_already_reported_is_not_asked_about_again(monkeypatch):
    """The model stays unmapped until a release maps it, so without this the
    issue comes back at every restart at someone who already answered.
    """
    entry = make_entry(options={repairs.REPORTED_MODELS: [UNMAPPED_MODEL]})

    registry = check(monkeypatch, UNMAPPED_MODEL, entry)

    assert registry.created == []


def test_a_model_reported_from_another_device_is_not_asked_about_again(
    monkeypatch,
):
    """One report speaks for the account, and it is answered from whichever
    dialog the user happened to open. The answer is stored on that one entry,
    so every entry has to read all of them.
    """
    answered = make_entry(
        modelId=OTHER_UNMAPPED_MODEL,
        entry_id="other",
        options={repairs.REPORTED_MODELS: [UNMAPPED_MODEL, OTHER_UNMAPPED_MODEL]},
    )

    registry = check(monkeypatch, UNMAPPED_MODEL, others=[answered])

    assert registry.created == []


def test_two_devices_of_one_model_ask_once(monkeypatch):
    """Keyed on the model, not the device : a pair of identical towel racks is
    one mapping to write, so it is one thing to ask for.
    """
    first = check(monkeypatch, UNMAPPED_MODEL, make_entry(title="Salle de bain"))
    second = check(monkeypatch, UNMAPPED_MODEL, make_entry(title="Chambre"))

    assert first.created[0][1] == second.created[0][1]


def test_a_hub_that_cannot_name_its_own_device_says_nothing(monkeypatch):
    """Better silent than an issue titled after a device nobody can find."""
    registry = check(monkeypatch, None)

    assert registry.created == []
    assert registry.deleted == []


# --- what is deliberately not filtered ------------------------------------


@pytest.mark.parametrize("title", ["THZone_0", "---", "Salon"])
def test_an_unmapped_model_is_asked_about_whatever_it_is_called(
    monkeypatch, title
):
    """The API returns its thermal zones as if they were devices, and nothing
    tells one apart from a real device nobody has mapped yet : the gateway's
    id is in masterDeviceId on both, modelFamily is null on both, and
    capabilities are only fetched for the configured device.

    A filter was tried on those names and taken back out. The two ways of
    being wrong do not cost the same -- a zone reported is an issue closed in
    seconds, a real device silenced is someone never finding out why their
    hardware is half-supported -- so this pins that nothing is guessed. A
    filter added later has to break this case, and read why first.
    """
    registry = check(monkeypatch, UNMAPPED_MODEL, make_entry(title=title))

    assert len(registry.created) == 1


# --- one report for the whole account -------------------------------------


def test_the_dialog_speaks_for_every_unmapped_device_on_the_account(
    monkeypatch,
):
    """A gateway with three unknown zones raises four repairs, and it would be
    four issues from one person about one account if each dialog only knew its
    own device.
    """
    entry = make_entry(account=[UNMAPPED_MODEL, OTHER_UNMAPPED_MODEL])

    result, _, _ = run_flow(monkeypatch, entry)

    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["model_ids"] == "88888, 99999"


def test_the_capability_ids_come_from_the_devices_that_have_them(monkeypatch):
    """A hub holds capabilities for its own device and no other, so the report
    is assembled from the entries Home Assistant has loaded. A model nobody
    added still belongs in it -- half a report is what a mapping starts from.
    """
    entry = make_entry(
        unmapped=(101,), account=[UNMAPPED_MODEL, OTHER_UNMAPPED_MODEL, 77777]
    )
    other = make_entry(
        modelId=OTHER_UNMAPPED_MODEL, entry_id="other", unmapped=(207, 208)
    )

    report = repairs._account_report(make_hass([entry, other]), entry)

    assert report == {
        77777: [],
        OTHER_UNMAPPED_MODEL: [207, 208],
        UNMAPPED_MODEL: [101],
    }


def test_the_link_carries_the_report_already_written():
    """The friction was never willingness, it was knowing what to write."""
    url = urlparse(repairs._report_url({99999: [101, 207], 88888: []}))
    query = parse_qs(url.query)

    assert url.path.endswith("/issues/new")
    assert query["template"] == [repairs.ISSUE_FORM]
    assert query["title"] == ["Unmapped models 88888, 99999"]
    assert query["model_ids"] == ["88888, 99999"]
    assert query["capability_ids"] == ["88888: none\n99999: 101, 207"]


def test_one_unmapped_model_is_not_announced_in_the_plural():
    """Most accounts have exactly one, and "Unmapped models 1457" reads as a
    template nobody finished.
    """
    query = parse_qs(urlparse(repairs._report_url({1457: [101]})).query)

    assert query["title"] == ["Unmapped model 1457"]


def test_the_link_fills_in_fields_the_form_actually_has():
    """GitHub matches these against the form's element ids and drops what it
    does not recognise, so a field renamed on one side arrives empty on the
    other with nothing said about it.
    """
    with open(
        f".github/ISSUE_TEMPLATE/{repairs.ISSUE_FORM}", encoding="utf-8"
    ) as handle:
        form = yaml.safe_load(handle)

    ids = {element["id"] for element in form["body"] if "id" in element}
    query = parse_qs(urlparse(repairs._report_url({1: [2]})).query)

    assert set(query) - {"template", "title"} <= ids


def test_a_field_the_link_cannot_fill_is_required():
    """The dialog fills in two fields. Everything else is a thing only the
    person with the hardware knows -- the commercial name, what the app shows,
    the dump -- and an optional field arrives empty, which costs the round trip
    the pre-filled link was written to save.
    """
    with open(
        f".github/ISSUE_TEMPLATE/{repairs.ISSUE_FORM}", encoding="utf-8"
    ) as handle:
        form = yaml.safe_load(handle)

    filled = set(parse_qs(urlparse(repairs._report_url({1: [2]})).query))

    for element in form["body"]:
        if "id" not in element or element["id"] in filled:
            continue

        required = element.get("validations", {}).get("required")
        assert required, f"{element['id']} is neither filled in nor required"


def test_the_link_says_nothing_about_the_household(monkeypatch):
    """A URL is clicked without being read. Capability values hold the wifi
    SSID and the gateway serial, and people name a device after a room or a
    child -- none of that goes in one. The dump does, and is attached
    knowingly.
    """
    entry = make_entry(title="Chambre de Léa", unmapped=(101,))

    result, _, _ = run_flow(monkeypatch, entry)

    report_url = result["description_placeholders"]["report_url"]

    assert "Chambre" not in report_url
    assert "L%C3%A9a" not in report_url


def test_a_device_with_nothing_unmapped_still_reads_as_a_sentence():
    """A model can be unknown while every capability it reports is named."""
    query = parse_qs(urlparse(repairs._report_url({1457: []})).query)

    assert query["capability_ids"] == ["1457: none"]


# --- answering it ---------------------------------------------------------


def test_submitting_stops_the_asking(monkeypatch):
    """What the button is for : the issue is deleted by the flow, and this is
    what keeps the next setup from raising it again.
    """
    entry = make_entry()

    result, entries, _ = run_flow(monkeypatch, entry, user_input={})

    assert result["type"] == "create_entry"
    assert entries.updated == [{repairs.REPORTED_MODELS: [UNMAPPED_MODEL]}]


def test_submitting_takes_the_other_repairs_with_it(monkeypatch):
    """One issue was sent for all of them. Leaving the other dialogs standing
    would ask the same person for the same file again.
    """
    entry = make_entry(account=[UNMAPPED_MODEL, OTHER_UNMAPPED_MODEL])

    _, entries, registry = run_flow(monkeypatch, entry, user_input={})

    assert registry.deleted == [("cozytouch", "unknown_model_88888")]
    assert entries.updated == [
        {repairs.REPORTED_MODELS: [OTHER_UNMAPPED_MODEL, UNMAPPED_MODEL]}
    ]


def test_submitting_twice_does_not_list_the_model_twice(monkeypatch):
    """The issue can be raised again between a restart and the write landing."""
    entry = make_entry(options={repairs.REPORTED_MODELS: [UNMAPPED_MODEL]})

    _, entries, _ = run_flow(monkeypatch, entry, user_input={})

    assert entries.updated == []


def test_an_entry_that_went_away_mid_flow_is_not_written_to(monkeypatch):
    """Removing the integration while its repair dialog is open is rare and
    entirely allowed.
    """
    monkeypatch.setattr(repairs, "ir", FakeRegistry())
    hass = make_hass([make_entry(entry_id="still here")])

    flow = repairs.UnknownModelRepairFlow("gone", UNMAPPED_MODEL)
    flow.hass = hass
    flow.flow_id, flow.handler = "flow", "cozytouch"

    asyncio.run(flow.async_step_confirm({}))

    assert hass.config_entries.updated == []


# --- what the report is made of ------------------------------------------


def test_the_account_is_read_off_any_one_of_its_devices():
    """Every hub holds the whole setup view, which is what makes one dialog
    able to speak for devices its own entry knows nothing about.
    """
    hub = SimpleNamespace(
        _devices=[
            {"deviceId": 1, "modelId": 235},
            {"deviceId": 2, "modelId": 99999},
            {"deviceId": 3, "modelId": 88888},
            {"deviceId": 4, "modelId": 99999},
        ]
    )

    assert Hub.get_unmapped_models(hub) == [88888, 99999]


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
    needs the id itself, which is what this accessor is for.
    """
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
    and the link is the one thing in there that has to work.
    """
    with open(path, encoding="utf-8") as handle:
        issue = json.load(handle)["issues"]["unknown_model"]

    step = issue["fix_flow"]["step"]["confirm"]
    written = set(re.findall(r"{(\w+)}", step["title"] + step["description"]))

    assert set(re.findall(r"{(\w+)}", issue["title"])) == {"device_name"}
    assert written == {"model_id", "model_ids", "report_url"}
    assert "{report_url}" in step["description"]
