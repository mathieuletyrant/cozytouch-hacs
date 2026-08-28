# Decisions

Why the configuration is what it is. The workflows and the config files say
what happens ; this file says why, so that the reasoning does not have to sit
as a comment block on top of every setting.

One section per file, one entry per setting. An entry states the evidence and
its limits — what was measured, on what, and what the measurement does not
cover — in the same way a commit message here does.

Files written before this convention still carry their reasoning inline :
`pyproject.toml`, the three requirements files, and the modules under
`custom_components/`. They are not being rewritten wholesale. A file moves
here when it is edited for some other reason.

## `.github/workflows/tests.yaml`

### ruff, and not `ruff format`

Check only. The tree is not formatter-clean, and reformatting it is a change
that should be reviewed on its own rather than folded into a lint pass.
`pyproject.toml` holds the configuration, including which rules are off and
why.

### The ruff job installs with pip, the pytest job with uv

Measured, not assumed : ruff is one small wheel, so pip fetches it in about
four seconds. Installing uv first to halve that costs three seconds, which
leaves nothing. The pytest job is where the installer is worth changing.

### The pytest job installs with uv

Nine tenths of this workflow was the installer, not the tests. On run
32898866439, pip took 47 s on the pinned environment and 96 s on the floor,
against 4 s of pytest and under a second of ruff ; the median run over the
preceding thirty was 92 s. The suite itself is not slow — 279 tests finish in
three seconds.

uv fetches and unpacks in parallel and reads a wheel's metadata without
downloading the whole file, which on a dependency tree of Home Assistant's size is
where the time goes. Measured on `requirements_test_min.txt`, cold cache :
96 s of pip becomes 9 s, with Home Assistant 2024.12.0 and the same 279 tests
passing. The whole step sequence, from `pip install uv` to the last
assertion, runs in 19 s.

What that does not cover : the pinned leg. No 3.14 interpreter is installable
off the runner, so 47 s is CI's own figure and the gain there is inferred
from the floor's.

### uv is pinned

Same reason `requirements_lint.txt` gives for pinning ruff : a tool that
arrives on its own can turn a green branch red without a commit. Bump it
deliberately.

### A venv, rather than `uv pip install --system`

`--system` is the shorter spelling, and it resolves whatever interpreter
`PATH` happens to hold — then refuses outright on one its distribution marks
as externally managed. The runner's is not, so `--system` would work there,
but it is the form that cannot be rehearsed anywhere else. The venv names the
interpreter instead of inheriting it.

Consequence worth knowing : `uv venv` does not put pip in the venv, so
`.venv/bin/pip` does not exist and the step that reports what was installed
uses `uv pip show`.

### Nothing is cached

A warm uv cache does the install in 0.7 s rather than 9 s. The cache is
444 MB for one matrix leg alone : restoring that costs about what the cold
install costs, and there would be two of them living under the repository's
cache quota to buy it.

### The matrix does not fail fast

One combination failing should not hide the result of the other. Which of the
two broke is the whole diagnostic.

### The two legs

`requirements_test.txt` on Python 3.14.2 is the pinned environment : what a
contributor's venv resolves to, and what CLAUDE.md tells you to build.
`requirements_test_min.txt` on Python 3.13.7 is the floor `hacs.json`
declares, tested so that the declaration keeps meaning something ;
`tests/test_floor.py` is the part of the suite that leg exists for.

The floor is 2025.4.0, and it was found by running that suite rather than by
reading a changelog. Config subentries — one entry per account, one subentry
per device — are absent from 2025.2.0, and the whole 2025.3.x line cannot be
installed at all : it pins an `aiohttp` release PyPI has since yanked.
`requirements_test_min.txt` carries the same reasoning inline, at more
length.

### A job named `pytest`, on top of the matrix

Everything outside the workflow refers to a check by its name, and a matrix
renames every job it touches : `pytest` became `pytest (HA … on Python …)`,
twice. Anything that required the old name — the branch protection rule
requiring `ruff`, `pytest` and `validate-hacs` above all — then waits forever
for a check that no longer reports, which looks exactly like the tests never
starting.

So the name stays, on a job that does nothing but agree with the matrix.
`needs` on a matrix job is the aggregate : success only if every leg
succeeded. `if: always()` because a skipped job reports neither pass nor fail,
and the point of this one is to always report something.

### Python is pinned down to the patch

Not `"3.14"`. Home Assistant pins its Python floor that precisely — 2026.8.3
needs >= 3.14.2 — so a floating minor would let the runner image decide which
Home Assistant is installable, which is the drift the pinned requirements
exist to remove.

### pyright, on the typed core

The declared fields on `ModelInfos`/`CapabilityInfos` are only worth what
checks them, and until this job nothing did. `pyproject.toml` scopes pyright
to `infos.py`, `model.py`, `capability.py` and `derive.py` — the typed core,
where the declarations live — rather than the tree : the platforms and the hub read
Home Assistant's heavily-typed API, and making them pyright-clean is its own
project, not a line in this one. Basic mode for the same reason.

`pythonVersion` is `"3.13"`, the floor's Python, not the pinned 3.14 : syntax
the floor cannot parse has to fail here, and anything 3.13 accepts 3.14
accepts too.

The pin is inline in the workflow, next to uv's, because pyright needs the
full test environment to resolve the `homeassistant` imports — it cannot live
in `requirements_lint.txt` without dragging Home Assistant into the ruff job.

Measured before wiring it up : 11 errors on the scope, of which 10 were the
missing venv configuration and one was real — `get_model_infos` could assign
a `str | None` device name into the zone's `name` field, which the
`(deviceName or "")` guard hid from the checker. The run that stays green is
the run that found one.

## `custom_components/cozytouch/capability.py`

### Capability 218 `wifiConnected` is shown raw, not as a connected/off flag

218 is `wifiConnected` by name, and was mapped as a boolean binary sensor
whose `is_on` is `value == "1"`. It reads permanently "disconnected" on
working hardware, because the value is never "1": across 42 models in the
capture corpus it is "0" (92 readings) or "4" (6), never "1". A device
plainly online with a -62 dB wifi signal still read "off", and so did every
unit sitting behind a gateway with no radio of its own.

The app does not use 218 for this at all — it reads a device's `isAvailable`
field for connectivity. And nothing decodes the 0/4 value space: it is not
referenced in the decompiled Dart or the Kotlin SDK, and no reflected enum
covers it (the parser confirms only the name, id 218 → case 2 → wifiConnected).

So the honest reading is that we do not know what 218 encodes. It is surfaced
raw and `enabled_by_default` False rather than as a flag that is always
wrong; account reachability is the connectivity binary sensor, and a proper
per-device connectivity sensor would come from `isAvailable`, the way the app
does it. The `4` reading is still unexplained. Research in
`research/FINDINGS.md`.

## `custom_components/cozytouch/derive.py`

### A derivation exists, and only the diagnostics dump reads it

The vendor's app is not updated when a model ships, which means it cannot
work the way `model.py` does. Decompiling it (August 2026) showed how it
does work : it has no `modelId` table at all — it displays the `longName` /
`modelFamily` the server sends — and every feature the UI offers is derived
from the capabilities the device reports. `derive.py` is that derivation
rebuilt on our side ; the entries below say what each piece rests on.

Nothing wires entities from it, because the evidence covers a handful of
device families and the table carries *deliberate* suppressions the
derivation would undo — 557-561 report capability 100507 and the vendor app
still offers no eco mode for them, which is why `ecoModeAvailable` is False
there. The dump prints the derived description and where it disagrees with
the declared one, so every report from the tracker measures the derivation
on hardware nobody here owns. Wiring from it is a later decision, taken
model by model on that record, with the table kept as the override layer
for exactly those suppressions.

### `HVAC_MODE_BITS` : capability 100022 is a bitmask over the mode values

Measured against the corpus of captures : the units that report
`100022 = 411` (bits 0,1,3,4,7,8) are the ones whose `HVACModes` table
reads {0 off, 1 auto, 3 cool, 4 heat, 7 fan_only, 8 dry} — the exact same
set — and the heating-only boilers and heat pumps (1382, 1444) read `17`
(bits 0,4) against their {0 off, 4 heat}. Two independent matches, no
counter-example seen.

Limits : bit 2 appears on the wire (285, 415, 21) and no capture has named
it, so the derivation reports it as unknown rather than guessing. And 166
(`systemOperatingMode`) carries masks in the same space that *shrink* while
100022 holds steady — one capture reads `166 = 9` {off, cool} on a unit
whose 100022 says {off, 2?, cool, heat, dry}, mid-summer, so 166 is
suspected to be the modes *currently permitted* (a seasonal lock) against
100022's *supported*. The derivation reads only 100022 ; if the vendor app
turns out to grey modes by 166, reflecting that is a climate-entity
question, not a mapping one.

### `FAN_MODES` / `SWING_MODES` : global vocabularies, not model data

The value/label pairs `model.py` repeats per model are the vendor's own
enums, embedded once in the app : fan speeds are `low / medium / high /
quiet / auto` with the API value one above the enum index (1 low … 5 auto ;
4 is the quiet speed, which the app drives through 100802 instead), louver
positions are `position1..4` at face value. The corpus reads only values
inside those ranges. So availability is the presence of 100801 / 100803,
and the pairs themselves are constants.

### The identity fields

`modelFamily` is the API's own taxonomy — 13 values, closed list, from the
app's parser of that field — but it is only populated on the head device of
an installation : on a captured Navizone account every room unit and zone
behind the hub reads null, and their `longName` is `ROOM_n` / `---`. Hence
the two extra inputs : a child falls back to its master's family, and being
named `masterDeviceId` by anybody makes a device the hub of its line, since
the family cannot tell the head from the units. The user-facing name is
capability 154 (the room name typed in the vendor app), then `customName` ;
the commercial name is the one thing the derivation cannot produce.

## `custom_components/cozytouch/sensor.py`

### The fault-code matrix is decoded, not shown raw

Capabilities 150, 290 and 303 (home, DHW and room fault codes) arrive as a
matrix the device fills with zeroes when healthy, and used to be surfaced as
that raw matrix -- a ten-row string nobody could read. Decompiling the app
(research, August 2026) named the row shape: `[system, majorCode, minorCode,
level]`, the exact key format Atlantic's own fault table uses
(`50_10_0_1`…). `decode_error_code` turns the matrix into the codes that are
active, so a healthy device reads `OK` and a faulted one reads its code list.

What counts as "not a fault" rests on the captures, and is two rules: an
all-zero row is healthy, and a row carrying `255` (`0xFF`) in any field is an
empty slot. The sentinel is well-supported -- whole accounts report the same
`[0,255,0,4]` row repeated ten times, which is one empty ten-slot list and
not ten identical faults. The `0xFF` reading is the app's, confirmed against
that repetition.

Two limits are deliberate. No capture has ever shown an *active* fault row,
so the `system_major_minor_level` join is derived from the format, not from a
decoded example -- if a real fault ever legitimately carried a `255`, this
would read it as empty. And the code is shown, never its meaning: mapping a
code to its human text needs Atlantic's fault-string table, which is theirs
to ship and is kept out of this repository. `OK` is a plain, language-neutral
token rather than a translated state, matching the raw-string diagnostic
sensors around it.

### The last-poll sensor stays available through the failure it dates

`CozytouchLastPollSensor` overrides `available` to "a poll ever succeeded"
instead of inheriting the CoordinatorEntity reading, which follows the *last*
poll's outcome. The default would take the sensor down with everything else
the moment the API stops answering -- which is exactly when "how old is what
the entities show" is the question being asked. A 429 backoff never trips
either reading (the coordinator deliberately treats it as a skip, not a
failure), so the override only shows during a real outage: every value sensor
goes unavailable, and this one keeps naming the moment the data stopped
moving.

Two smaller choices ride along. The date is stamped by the setup-view read
itself (`CozytouchAccount._read_setup`), so `connect()` counts as the first
poll and the sensor is never born empty. And it is surfaced per device even
though one account-level request refreshes everything, so the reading sits on
the device whose values it dates -- the duplication is the account beat made
visible, not N measurements.

## `custom_components/cozytouch/__init__.py`

### Setup registers every device itself, before the platforms

A device used to exist in the registry only once some platform added entities
for it. That is a race: `async_forward_entry_setups` runs the platforms
concurrently, and a room unit's `device_info` names its gateway in
`via_device` -- so any platform that reached the room unit before one gave
the gateway an entity registered a link to a device that was not there. It
was not theoretical: calendar and climate, which build nothing for a gateway,
did exactly that on a live install (HA log, 2026-08-28, `via_device
('cozytouch', <gateway subentry>)` "non existing"), and Home Assistant
announces that 2025.12 stops honouring such a link instead of warning.

So `async_setup_entry` now walks the subentries and calls
`async_get_or_create` for each -- gateways first, since the children's links
point at them -- before forwarding a single platform. The platforms then find
the device already there and merely restate it, which is why the description
they use (`device_info_for`) moved to `hub.py`: one function serving setup
and entities keeps the two registrations identical by construction.

`get_via_device` itself is unchanged. Its check -- link only when the gateway
is a subentry of the same entry -- was always right; what it could not see is
*when* the gateway's device would appear. Registration order is the other
half, and `tests/test_topology.py` pins both.

### The per-day program sensors give way to the calendar (issue #42)

A device that reports a whole program block gets a calendar for it, and the
seven diagnostic sensors next to it render the same days as truncated strings
-- fourteen near-identical rows per air conditioner (screenshot on the issue).
The first plan was one consolidated sensor per block, state = today and the
week as attributes; it died in review against what already exists: the
calendar *is* that view, with the setpoints as event titles and
`calendar.event` as "the setpoint in charge right now". Deleting the sensors
was considered next and dropped too -- disabling gives the same device page
with a two-click way back for whoever reads one in a template.

So there are two halves, and the whole-block rule gates both, because a
partial block builds no calendar and its per-day sensors stay its only view:

- the mapping ships a covered block's days `enabled_by_default: False`
  (`capability.py`), which Home Assistant only reads when an entity is first
  registered -- new installs and new devices;
- the 2.2 entry migration (`async_migrate_entry`, `MINOR_VERSION` in the
  config flow) disables the ones an existing install already registered.
  Exactly once, which is the point of doing it as a migration rather than at
  every setup: somebody who re-enables a sensor must never find it disabled
  again. `disabled_by=INTEGRATION`, and a sensor already disabled by the user
  keeps saying USER.

The two halves read "whole block" off different evidence, and the gap is
known: the mapping checks the ids the device *reports*
(`availableCapabilityIds`), the migration checks the ids the registry
*holds*, while the calendar checks the seven *values* are not None. A block
fully reported with a null day would be disabled here and get no calendar --
no capture has ever shown one, and a wall of unknown-valued sensors is not a
view worth keeping enabled for that case. The milestone blocks
(100320-100333) and the time ranges (245-251) have no calendar and stay
enabled; `tests/test_prog_visibility.py` pins all of it.

## `.github/workflows/release.yaml`

### It installs with pip, where tests.yaml uses uv

The job is dispatched by hand a few times a year, so the minute it spends is
not worth the change on its own. Leaving it on pip also keeps a standing
proof that the requirements install without uv, which is what a contributor
following the README has.
