"""What the two translation files promise, and what actually reaches a user.

Every string here is read by Home Assistant at runtime and by nothing else, so
the ways they break are quiet ones. Four have been live in this repo:

A `[%key:…%]` reference is resolved by the build that ships Home Assistant
core, and by nothing that ships a custom integration : the abort message for an
already-configured account read as its own placeholder, in both languages --
twice, the second time after the flow was rewritten around one entry per
account.

`errors["base"]` is a translation key, not a sentence. The one set when the
account has no device left to add was the sentence `No new device found`, which
the form has no entry for and so printed verbatim, in English, to everyone.

A field with no `data` entry falls back to its own name : the device picker was
labelled `device`. It is asked for by a subentry flow now, whose labels live one
level deeper, under `config_subentries`. The mirror image of that -- a
`data_description` for a field no step asks for, left behind by a rename --
Home Assistant refuses the whole file over.

A `select` option in `services.yaml` is translated through the selector's
`translation_key`. Without one the action's form offers `heating` and `monday`
as written in the YAML.

The last case is the house convention rather than a bug -- Home Assistant asks
for entity names in sentence case, and every name here was in title case.
"""

import json
import pathlib
import re

import pytest
import yaml

TRANSLATIONS = (
    "custom_components/cozytouch/translations/en.json",
    "custom_components/cozytouch/translations/fr.json",
)

CONFIG_FLOW = "custom_components/cozytouch/config_flow.py"
SERVICES = "custom_components/cozytouch/services.yaml"

# Words allowed to carry a capital in the middle of a name : the acronyms the
# API and the hardware use, the zone and day suffixes, and the mode names
# Atlantic's own app capitalises.
ACRONYMS = frozenset(
    {
        "CH", "DHW", "PAC", "SSID", "V40", "Wi-Fi", "Z1", "Z2",
        "Boost", "Eco", "Powerful", "Prog",
        "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun",
        "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim",
    }
)

# `errors["base"] = "x"`, the only way this flow reports a failure.
ERROR_KEY = re.compile(r'errors\["base"\]\s*=\s*"([^"]+)"')

# `vol.Required("x")` and `vol.Optional("x")`, every field a step asks for.
FIELD = re.compile(r'vol\.(?:Required|Optional)\(\s*"([^"]+)"')


def loaded(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def entity_names(translations):
    """Every entity name in the file, keyed by platform and translation key."""
    for platform, entities in translations["entity"].items():
        for key, entity in entities.items():
            if "name" in entity:
                yield f"{platform}.{key}", entity["name"]


def form_fields(translations, flow):
    """Every field label a config or options flow step declares."""
    fields = set()
    for step in translations.get(flow, {}).get("step", {}).values():
        fields |= set(step.get("data", {}))
    return fields


def subentry_fields(translations):
    """The same, for the subentry flows -- a device is a subentry of an account.

    One level deeper than `config`: the sections are keyed by subentry type,
    and each holds a flow of its own.
    """
    fields = set()
    for subentry in translations.get("config_subentries", {}).values():
        for step in subentry.get("step", {}).values():
            fields |= set(step.get("data", {}))
    return fields


@pytest.mark.parametrize("path", TRANSLATIONS)
def test_no_translation_file_ships_an_unresolved_reference(path):
    """Nothing outside core resolves `[%key:…%]`; the user reads the brackets."""
    text = pathlib.Path(path).read_text(encoding="utf-8")

    assert "[%key:" not in text


@pytest.mark.parametrize("path", TRANSLATIONS)
def test_every_config_flow_error_has_a_translation(path):
    """An error key with no entry is printed as the key, to every language."""
    source = pathlib.Path(CONFIG_FLOW).read_text(encoding="utf-8")
    declared = set(loaded(path)["config"]["error"])

    assert not set(ERROR_KEY.findall(source)) - declared


@pytest.mark.parametrize("path", TRANSLATIONS)
def test_every_config_flow_field_has_a_label(path):
    """A field with no `data` entry is labelled with its own variable name."""
    source = pathlib.Path(CONFIG_FLOW).read_text(encoding="utf-8")
    translations = loaded(path)
    labelled = (
        form_fields(translations, "config")
        | form_fields(translations, "options")
        | subentry_fields(translations)
    )

    assert not set(FIELD.findall(source)) - labelled


@pytest.mark.parametrize("path", TRANSLATIONS)
def test_every_field_description_belongs_to_a_field(path):
    """A `data_description` for a field a step does not ask for.

    Home Assistant refuses the file outright over this -- hassfest fails the
    whole integration -- rather than dropping the stray line, and the way it
    happens is a field being renamed with its helper text left behind: the
    device picker became a multi-select called `devices` and its description
    stayed under `device`.
    """
    translations = loaded(path)
    stray = {}
    for flow in ("config", "options"):
        for name, step in translations.get(flow, {}).get("step", {}).items():
            extra = set(step.get("data_description", {})) - set(step.get("data", {}))
            if extra:
                stray[f"{flow}.{name}"] = extra
    for subentry, section in translations.get("config_subentries", {}).items():
        for name, step in section.get("step", {}).items():
            extra = set(step.get("data_description", {})) - set(step.get("data", {}))
            if extra:
                stray[f"config_subentries.{subentry}.{name}"] = extra

    assert not stray


@pytest.mark.parametrize("path", TRANSLATIONS)
def test_every_service_select_option_is_translated(path):
    """Otherwise the action's form offers the raw values written in the YAML."""
    with open(SERVICES, encoding="utf-8") as handle:
        services = yaml.safe_load(handle)
    selectors = loaded(path).get("selector", {})

    for service, spec in services.items():
        for field, definition in spec.get("fields", {}).items():
            select = (definition.get("selector") or {}).get("select")
            if not select:
                continue
            key = select.get("translation_key")
            assert key, f"{service}.{field} has no translation_key"
            translated = set(selectors.get(key, {}).get("options", {}))
            assert not set(select["options"]) - translated, (
                f"{service}.{field} offers untranslated options"
            )


@pytest.mark.parametrize("path", TRANSLATIONS)
def test_entity_names_are_in_sentence_case(path):
    """Home Assistant's convention, and what every core integration reads as.

    "The rest of the words are lower case (unless it's a proper noun or a
    capitalized abbreviation of course)" -- the ones this integration uses are
    listed in ACRONYMS above.
    """
    wrong = {}
    for key, name in entity_names(loaded(path)):
        for word in name.split()[1:]:
            bare = word.strip("()")
            if bare not in ACRONYMS and re.match(r"^[A-Z][a-z]", bare):
                wrong[key] = name

    assert not wrong
