# Atlantic Cozytouch — Home Assistant integration

A custom integration talking to Atlantic's Cozytouch cloud. It is not the
official `overkiz` integration : Atlantic runs several protocols, and this one
covers the boilers, water heaters, towel racks and air conditioners that speak
the Cozytouch API rather than Overkiz.

## Where to read first

This file says what to do and where. Two documents say how the thing works,
and are worth reading before a change rather than after :

| Document | What it answers |
| -------- | --------------- |
| `docs/architecture.md` | How a capability id becomes an entity, what the account owns and what the Hub owns, which invariants hold, and the rough edges that are real and inherited. |
| `docs/api-surface.md` | What the API does and does not expose. Read it before probing anything : ~90 paths are already ruled out, and there is no capability catalogue to fetch. |

## Repository topology

This repo started as a fork of `gduteil/cozytouch` and now stands on its own.
Three remotes, each with a job :

| Remote     | Repository                     | What goes there |
| ---------- | ------------------------------ | --------------- |
| `origin`   | `mathieuletyrant/cozytouch-hacs` | Our `main`. This is what HACS installs. |
| `fork`     | `mathieuletyrant/cozytouch`      | Branches backing the pull requests still open upstream. |
| `upstream` | `gduteil/cozytouch`              | Read-only. Fetch to see what the original project does. |

`main` tracks `origin`. The PR branches track `fork`, so `git push` on one of
them updates the upstream pull request and nothing else. Do not repoint them.

## Tests

Python 3.14.2, `pip install -r requirements_test.txt`, then `pytest tests/ -q`.
The system `python3` on this machine is too old — build a venv with
`uv venv --python 3.14.2`. The patch version matters: `requirements_test.txt`
pins Home Assistant exactly, and that release declares Python 3.14.2 as its
floor, so an older interpreter makes the install fail rather than resolve
backwards to an HA nobody runs.

The requirements are pinned, not `>=`, for that reason — see the comment at
the top of the file for what the unpinned version did. There are two of them :

| File | What it is |
| ---- | ---------- |
| `requirements_test.txt` | the environment to develop in, and CI's main job |
| `requirements_test_min.txt` | the oldest HA `hacs.json` claims to support, so the claim is tested |

Raising the floor means editing `requirements_test_min.txt` and `hacs.json`
together, and the Python it is paired with in `.github/workflows/tests.yaml`.
`tests/test_floor.py` fails if the first two disagree, and is what says whether
a candidate floor can run this at all.

## Lint

`pip install -r requirements_lint.txt`, then `ruff check .`. CI runs the same
command and it has to come back clean.

The configuration is `pyproject.toml`, and it is worth reading before arguing
with a finding : the rules that are off are off for a stated reason, and two of
them matter here. Naming rules (`N803`/`N806`) are not enabled because the
camelCase locals mirror the field names the Atlantic API itself uses, and
`PLR2004` is not enabled because the numeric capability ids *are* the domain.
Do not "fix" code to satisfy a rule the config deliberately drops.

`ruff format` is **not** run, by CI or otherwise. The tree is not
formatter-clean; reformatting it is its own change, not something to slip into
another one.

The suite is **characterisation tests**. They pin the mapping as it stands, not
as it ought to be : most entries were reverse-engineered from one user's
capture, so a test going green says "nobody changed this by accident", never
"this is correct".

- `tests/test_model.py` — one case per branch of `get_model_infos`, comparing
  the whole returned dict. Ids that resolve differently inside a shared branch
  get their own case.
- `tests/test_regressions.py` — bugs that were live and that no table walk
  would have reached: state that used to sit on the `Hub` class and so was
  shared by every config entry, a shadowed `time` import that made every time
  entity raise, and the connect lock without which every device on an account
  logs in separately.
- `tests/test_floor.py` — what the Home Assistant version `hacs.json` declares
  has to provide. It imports every module, which the rest of the suite does not
  — four of them, and none touching the config flow or the platforms — and
  names the config-subentry APIs the current shape rests on. **The floor is
  found by running this, not by reading a changelog**: it is what established
  that 2025.2 has no subentries and that the whole 2025.3 line cannot be
  installed (a yanked `aiohttp` pin).
- `tests/test_diagnostics.py` — that an unmapped model reads as unmapped and
  unnamed capability ids get listed, since that is what a dump is read for.
- `tests/test_sensor_values.py` — what the value builders in `sensor.py`
  return, character for character : the zero padding on a duration, the double
  space before a temperature, a setpoint arriving from JSON as a float and
  still reading as a whole number. This is the file whose strings end up on a
  dashboard, so **the assertions are the current output, not the nicer output**
  — including one case pinned as wrong on purpose, the timezone offset applied
  twice. Changing any of these should mean changing a test in the same commit.
- `tests/test_repairs.py` — the unmapped-model repair : that it asks once per
  model and about every model the table does not know, whatever the API calls
  the device, that one dialog's report covers the whole account and answering
  it settles every repair that report spoke for, that the report carries the
  model and capability ids and nothing about the household, that its query
  keys still match the issue form's field ids and that every field they do not
  fill is required, and that a release mapping a model clears it.
- `tests/test_topology.py` — the gateway link. The API reports the parent in
  `masterDeviceId`, but a device is registered under its config entry, so the
  link can only be drawn when the gateway was set up too; these pin that a
  missing gateway yields no link rather than a dangling one.
- `tests/test_capability.py` — walks every mapped model id to check which
  models a flag reaches and whether the gates in `capability.py` still follow
  the flag they were written for. It carries a hard count of mapped ids;
  adding models means updating that number, and widening the walk's range if
  the new id falls outside it.

## Entries, subentries, identity

An account is one config entry; each of its devices is a subentry of it. The
subentry id is the identity a device is registered under and the prefix of
every unique id built from it, so a device added twice or a subentry recreated
is a new set of entities. `account.py` owns everything the account declares —
the session, the token, the setup view, the device list — and `hub.py` is one
coordinator per device on top of it.

## Adding a device

1. `custom_components/cozytouch/model.py` — a branch in `get_model_infos`
   returning at minimum `name`, `type` and `HVACModes`. Optional flags are
   documented in the module docstring; **only declare a flag when the device
   actually needs it**, because `capability.py` reads them to decide which
   entities exist, and a flag set on a shared branch reaches every model in it.
2. `custom_components/cozytouch/capability.py` — only if the device reports
   capability ids nothing maps yet. Model-specific behaviour goes behind
   `if modelId == …`, never a change to the shared default. A capability whose
   encoding is unverified belongs in `SELF_DESCRIBING_CAPABILITIES`: named,
   surfaced as a raw string, and `enabled_by_default` False, so it costs nobody
   anything until someone turns it on to investigate. Claim a type only where
   the unit is actually known.
3. Translations — a new capability name needs an entry in **all three** of
   `strings.json`, `translations/en.json` and `translations/fr.json`, kept in
   the alphabetical order and column alignment already in the file.
4. Tests — a case in `MODEL_GROUPS`, and the count in `test_capability.py`.
5. `README.md` — the table for that device class.

`scripts/dump_capability_map.py` prints what the two tables now resolve to, per
device type. Nothing has to be regenerated — run it when you want the answer.
A new device *type* needs a probe model id added to it, which is the same edit
as adding the type to `model.py`.

Devices the integration cannot map fall through to `Unknown product (…)`.
What a mapping gets built from is the diagnostics dump (`diagnostics.py`, backed
by `Hub.get_diagnostics`) : every device on the account with its model id,
whether the table knows it, and the capability ids nothing names yet. Ask a
reporter for that file before anything else. The older
`Create entities for unknown capabilities` option still exists and turns each
unmapped capability into an entity, which is for working out what a value means
rather than for reporting.

## Commit messages

Subject is a sentence saying what changed for the user, in the present tense,
no prefix and no ticket number : *"Stop offering an eco mode the room air
conditioners do not have"*, not *"fix(ac): eco mode"*.

The body leads with **why** — the observed behaviour, what the Cozytouch app
does, what a capture showed — and only then what the change does. State the
evidence and its limits : which model ids a finding covers, which it does not,
what was left alone for lack of a report. Wrap at 76 columns.

## House style

Comments explain why a value is what it is — which capability id the device
reports, what the app shows, what a capture proved. They do not restate the
code. Match the density already in the file.
