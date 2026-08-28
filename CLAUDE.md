# Atlantic Cozytouch — Home Assistant integration

A custom integration talking to Atlantic's Cozytouch cloud. It is not the
official `overkiz` integration : Atlantic runs several protocols, and this one
covers the boilers, water heaters, towel racks and air conditioners that speak
the Cozytouch API rather than Overkiz.

## Where to read first

This file says what to do and where. Three documents say how the thing works,
and are worth reading before a change rather than after :

| Document | What it answers |
| -------- | --------------- |
| `docs/architecture.md` | How a capability id becomes an entity, what the account owns and what the Hub owns, which invariants hold, and the rough edges that are real and inherited. |
| `docs/api-surface.md` | What the API does and does not expose. Read it before probing anything : ~90 paths are already ruled out, and there is no capability catalogue to fetch. |
| `docs/decisions.md` | Why a setting is the value it is — which run was measured, what was tried and dropped. This is where the reasoning lives that used to sit in comment blocks above the setting. |

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

Python 3.14.2 — the system `python3` on this machine is too old. Build the
venv with `uv venv --python 3.14.2`, install with
`uv pip install -r requirements_test.txt`, run `.venv/bin/pytest tests/ -q`.
`uv pip` and not `pip`, because a uv venv ships no pip of its own.
The patch version matters: `requirements_test.txt`
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

`uv pip install -r requirements_lint.txt`, then `.venv/bin/ruff check .`. CI
runs the same check and it has to come back clean.

CI runs on pull requests based on `main` **or** on a `claude/**` branch. That
second one is not decoration: the trigger filters on the *base* branch, so
before it was added a pull request stacked on another one got no checks at all
-- which is not the same as passing, and reads exactly like it.

The configuration is `pyproject.toml`, and it is worth reading before arguing
with a finding : the rules that are off are off for a stated reason, and two of
them matter here. Naming rules (`N803`/`N806`) are not enabled because the
camelCase locals mirror the field names the Atlantic API itself uses, and
`PLR2004` is not enabled because the numeric capability ids *are* the domain.
Do not "fix" code to satisfy a rule the config deliberately drops.

Types are checked by pyright, but only on the typed core — `infos.py`,
`model.py`, `capability.py` — as `pyproject.toml` scopes it ; CI runs it in
the pinned test venv (`.venv/bin/pyright`), and the scope's reasons are in
`docs/decisions.md`.

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
- `tests/test_reauth.py` — the split between a refused password and a server
  that is not answering, end to end : what the token endpoint said, what
  `connect()` raises, what setup and the poll turn it into, and what the reauth
  dialog does with the password somebody types. Its `FakeSession` is the only
  stand-in in the suite that reaches the HTTP layer, so it is where the rest of
  `account.py` gets tested when somebody gets to it. One case pins a
  *limitation* on purpose : a refused login is retried once per waiting hub,
  and if that number ever drops the case should say why.
- `tests/test_floor.py` — what the Home Assistant version `hacs.json` declares
  has to provide. It imports every module, which the rest of the suite does not
  — four of them, and none touching the config flow or the platforms — and
  names the config-subentry APIs the current shape rests on. **The floor is
  found by running this, not by reading a changelog**: it is what established
  that 2025.2 has no subentries and that the whole 2025.3 line cannot be
  installed (a yanked `aiohttp` pin).
- `tests/test_polling.py` — the account-level beat : one setup-view request
  for the whole account where it used to be one per device per minute, and
  what a 429 does — back off and keep the last values, rather than answering
  a rate-limit complaint with a login. Its `FakeSession` is a deliberate copy
  of `test_reauth.py`'s, kept separate so a change there cannot quietly
  rewrite what these say.
- `tests/test_diagnostics.py` — that an unmapped model reads as unmapped and
  unnamed capability ids get listed, since that is what a dump is read for.
- `tests/test_sensor_values.py` — what the value builders in `sensor.py`
  return, character for character : the zero padding on a duration, the double
  space before a temperature, a setpoint arriving from JSON as a float and
  still reading as a whole number. This is the file whose strings end up on a
  dashboard, so **the assertions are the current output, not the nicer output**
  — including one case pinned as wrong on purpose, the timezone offset applied
  twice. Changing any of these should mean changing a test in the same commit.
- `tests/test_sensor_metadata.py` — what the platform declares *about* a value :
  the state class that decides whether the recorder keeps long-term statistics,
  and the firmware version that reaches the device registry. It drives
  `async_setup_entry` rather than restating its table, and checks each
  device-class/state-class pair against Home Assistant's own compatibility
  table — the check that catches a combination HA rejects at runtime, which is
  how the tank volumes ended up as `volume_storage`.
- `tests/test_freshness.py` — the `modificationDate` every capability carries
  and nothing used to read : that a date the API sends survives arriving as a
  string, that nothing useful reads as None rather than as 1970, that a
  device's date is the *newest* of its capabilities (any one of them can sit
  unchanged while the hardware keeps reporting), that the sensor exists only
  when the device reports a date at all, and that the dump carries them per
  capability. It pins the reading, never a staleness threshold — nothing yet
  says what a normal silence looks like.
- `tests/test_calendar.py` — the weekly program expanded into dated events :
  which capability a weekday reads, that a slot runs until the next one rather
  than for a fixed length and that the last of the day runs to midnight, that
  the week repeats over a range, that a slot which began before the window is
  still the one in charge at its start, and that a calendar exists only for a
  block the device reports in full -- one case per block, since the three runs
  (196, 203, 237) are the whole of what it reads. `dt_util.DEFAULT_TIME_ZONE` is UTC in a
  test process, which is what makes the expected datetimes readable.
- `tests/test_prog_visibility.py` — the per-day program sensors giving way to
  the calendar : that a whole block's days arrive disabled by default and a
  partial block's stay enabled (same rule that gates the calendar), that the
  blocks without a calendar keep their sensors, that the 2.2 migration
  disables what an existing install registered — exactly once, so a re-enabled
  sensor stays re-enabled — targeting the same unique_ids the sensor platform
  actually claims, and that a version 1 entry still refuses to migrate.
- `tests/test_repairs.py` — the unmapped-model repair : that it asks once per
  model and about every model the table does not know, whatever the API calls
  the device, that one dialog's report covers the whole account and answering
  it settles every repair that report spoke for, that the report carries the
  model and capability ids and nothing about the household, that its query
  keys still match the issue form's field ids and that every field they do not
  fill is required, and that a release mapping a model clears it.
- `tests/test_services.py` — the schedule services : the matrix `set_schedule`
  builds, and the round trip that is the promise of `get_schedule`, since what
  it returns has to be writable again unchanged.
- `tests/test_device_trigger.py` — the device triggers : which ones a device
  is offered, given what it reports, and what each one then watches — the right
  entities for a program, the preset *attribute* rather than the state for a
  preset. Both halves fail silently in production, since a trigger that never
  fires logs nothing.
- `tests/test_topology.py` — the gateway link. The API reports the parent in
  `masterDeviceId`, but a device is registered under its config entry, so the
  link can only be drawn when the gateway was set up too; these pin that a
  missing gateway yields no link rather than a dangling one.
- `tests/test_snapshot.py` — the whole of both tables against JSON files in
  `tests/snapshots/` : every mapped model id, and every capability id the
  chain claims on one model per device type. This is what makes a pure
  refactor provable — if the files do not change, no answer did. Regenerate
  deliberately, in the same commit as the change the diff shows, with
  `UPDATE_SNAPSHOTS=1 pytest tests/test_snapshot.py`.
- `tests/test_capability.py` — walks every mapped model id to check which
  models a flag reaches and whether the gates in `capability.py` still follow
  the flag they were written for. The walk runs over `range(1, 2500)`; a model
  added outside it needs that range widened.
- `tests/test_capability_coverage.py` — the seams around the mapping : that a
  self-describing capability arrives switched off, that every name the mapping
  can produce has an entry in all three translation files, and that the
  `CapabilityType` members the mapping writes and the ones the platforms match
  on are the same set — a type on one side only is silent both ways, and two
  lived exactly there.

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
4. Tests — a case in `MODEL_GROUPS`, and the snapshots regenerated in the same
   commit (`UPDATE_SNAPSHOTS=1 pytest tests/test_snapshot.py`) so the diff
   shows the new model and nothing else.
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

Reasoning goes in `docs/decisions.md`, not in a comment block above the thing
it explains. Which run was measured, what the app shows, what a capture
proved, what was tried and dropped : all of it belongs in a named entry that
can be read end to end, rather than scattered across the files it happens to
touch.

What stays in the code is a pointer, where the line would otherwise read as a
mistake — `# see docs/decisions.md` on the setting that looks wrong, one line,
no argument restated. A `noqa` still says which rule and why on the spot,
because that one is about the line and nothing else.

Comments never restate the code.

The older files predate this and still carry their reasoning inline :
`pyproject.toml`, the requirements files, and the modules under
`custom_components/`. Do not migrate them wholesale. A file moves to
`docs/decisions.md` when it is being edited for some other reason anyway.
