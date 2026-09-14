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
to `infos.py`, `model.py` and `capability.py` — the typed core,
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

## `custom_components/cozytouch/binary_sensor.py`

### Two connectivity sensors, not one

`isAvailable` (the cloud's per-device reachability) and `online` (the account's
session, the existing CloudConnectivity sensor) are two different questions,
and the DeviceAvailability sensor keeps them apart rather than folding them.

Folding — `is_on = online and isAvailable` — was considered and rejected: a
single sensor could not say *which* was down when it read off, and the whole
value of `isAvailable` is telling "the cloud is unreachable" from "this one
device is". So there are two connectivity binary sensors on each device: the
account session (same answer everywhere) and this device's own availability.

`is_on` is the raw `isAvailable`, no gateway→child derivation: the cloud
already marks a child unavailable when its gateway drops (every capture where
one device is false has the whole account false), so deriving it again would
only risk contradicting the field. When the session drops the sensor keeps its
last value and stays available itself — consistent with the 429 backoff, which
holds last values rather than flapping every entity unavailable; the
CloudConnectivity sensor is what says whether the reading is still fresh.
Absent field reads as unknown, never a guessed state.

Enabled by default, unlike the static descriptors: it is one sensor per device
and it is the answer to "is my device reachable", which the freshness sensor
(`last_device_update`) cannot give — a healthy but idle device has an old date
without being down.

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

### An electric heater's action is the element (153), not the mode (181)

181 carries the mode a device is really running, as against the one it was
asked for, and the climate entity turns it into an `HVACAction`. On a radiator
that reads `heating` from the moment the thing is switched on : 181 says heat,
and heat is what it says whether or not the element is drawing.

gduteil/cozytouch#68 is that seen from a dashboard. A Sauter Tahual behind a
CozyBox, setpoint 19, room 22.95, and Home Assistant reporting that the
radiator was heating. Its dump has `153` -- the element -- reading 0, which is
the answer: on, at temperature, idle.

153 is not new here. It already ships as a binary sensor, named `resistance`
on an electric heater and `flame` on a boiler, so what it means is established
in the mapping rather than guessed for this. The wiring is narrow on purpose:
`heatingActiveCapabilityId` is set only for `ELECTRIC_HEATERS`, and only when
the device reports 153. It can only ever turn `HEATING` into `IDLE` -- off
stays off, and nothing else is second-guessed.

Limits. The only capture is one radiator idling, 153 at 0 with the room three
degrees over setpoint; nobody has sent a paired reading of the same radiator
drawing. The reading rests on what the mapping already calls the capability,
not on that pair. **Boilers are deliberately left out** even though 153 is the
flame there : a boiler's flame can be lit for domestic hot water while the
central heating circuit is genuinely idle, so the same rule would report the
opposite error on hardware nobody has a dump for. Air conditioners too -- 153
is reported on the room slots behind a Navizone and reads 0 on every one of
them, which is either an idle compressor or a field the hardware never fills,
and one dump cannot say which.

### Capability 100450 `activationProgAnticipation` is a switch

The vendor app's "Anticipation de chauffe" toggle, per room: on, the device
starts early so the room is at temperature at the scheduled time; off, it
starts heating at the scheduled time. Promoted from a self-describing raw
sensor to a writable switch on a live experiment (2026-08-29): the toggle
was flipped Off on one of three room ACs and the diagnostics dump read back
`100450 = "0"` on that unit with a `modificationDate` stamped at the moment
of the toggle, `"1"` untouched on the other two -- and 100450 was the *only*
capability whose date moved, so the app writes this id directly rather than
through a sibling.

Limits: verified on models 557-559, which are also the only models in the
capture corpus that report the id at all, always as 0/1. The companion
103450 (`progMilestoneAnticipationState`, presumably "currently
anticipating") appears on no captured hardware and stays self-describing.

### Capability 171 `awayCooling` is read-only, where 172 is a number

171 sits next to 172 `awayHeating`, which has been the writable
`away_mode_temperature` since long before this entry. The name comes from the
decompiled app (`research/Capability-Reference.md`), and the capture corpus
agrees on the unit without exception : 35.0 on all eight models that report it
(211, 422, 1444, 1693, 1715, 1758, 1941, 2145), against 17.0 for the heating
side on the boiler the mapping was read from.

What no capture shows is anything writing it. 172 is a number because the app
offers that setting and a dump read the written value back ; nothing equivalent
was seen for 171, and every reading of it is the same untouched 35.0. So it is
a temperature sensor, diagnostic, `enabled_by_default` False -- the unit is
known, the direction is not. Promoting it takes one person moving the absence
cooling setpoint in the app and a dump showing 171 followed.

It carries the same `awayModeTemperatureAvailable` gate as 172, for the reason
given there : an air conditioner stores an absence setpoint and never acts on
it.

The heat-pump branch used to carry `# capability.highestValueCapabilityId =
171` commented out, which would have read the absence setpoint as a maximum
bound. It was never live and is now gone.

## `custom_components/cozytouch/model.py`

### 1734-1737 are the room air conditioners a gateway numbers past its fifth (issue #61)

One household (issue #61, September 2026) runs nine room units behind a
single HUB Cozytouch (1457). The API names them `ROOM_0` to `ROOM_8` and
hands the first five the ids 557-561, then jumps : `ROOM_5` is 1734 and
`ROOM_6`, `ROOM_7`, `ROOM_8` are 1735, 1736, 1737, with `productId` running
97-100 where the first block runs 26-30. So 1734, mapped earlier on its own
from a single report, was the first id of a second block rather than a
separate product, and the three after it are the same thing : the
`iothubChildrenIds` tag is a `THZONE_n` on every one of them, `masterDeviceId`
is the hub, and the reporter calls the units a "Murao" -- the Atlantic
wall-mounted split, sold in multi-split sets, which is what nine indoor units
on one gateway would be.

What the dump shows is the same capability id set on 1734, 1735, 1736 and
1737, id for id -- 77 of them, the climate ids, both program blocks, the fan
and louver ids 100801/100803, the eco flag 100507 -- and 557 differs from
them only by four more : 341, 347, 348 and 100100. The values read as an air conditioner
too : 100022 is 415 on all of them, the same bitmask the 557-561 units carry
for {off, auto, cool, heat, fan_only, dry} ; 1736 was captured cooling, with
7 and 181 both at 3 and its cooling setpoint at 16.0 ; and every fan and
louver value falls inside the vocabularies `model.py` declares.

So the branch condition widens from `modelId == 1734` to `1734 <= modelId <=
1737` and nothing else changes : the same flags 1734 had, the same
`(#n)` fallback name counted from 1734 -- which almost nobody sees, since a
hub child always carries a zone name and that is what the entity is called.

Limits. The range stops at 1737 because that is where this household stops ;
a tenth room would arrive unmapped and ask for its own report, which is the
right failure -- the ids are not known to be per-slot the way the THZONE ones
are. The eco gate that 557-561 carry (`ecoModeAvailable = False`, because the
app offers none for them) is *not* extended : this report attaches the dump
in place of what the app shows, so there is still no statement either way for
1734-1737, and they stay on the default as 1734 already did. Reading 100507
at 0 on every one of them, next to 557-561 also at 0, says nothing about
whether the app exposes it. The `(#n)` numbering was left alone rather than
made to read `#6` for 1734 : it would rename an existing model's fallback on
the strength of one household's slot order.

### Thirty-eight boilers named from the vendor's catalogue, and nothing else claimed

`GET /magellan/productmodels/models/{modelId}` answers for any model id, not
only the ones an account owns (`docs/api-surface.md`). It gives the vendor's
`longName`, a `commercialReference`, and a `productId`. That is `model.py`'s
first column, published -- and it is where ids 1-12, 54 and 55 come from.

They are the Naema and Naia, both generations, filling in around the three
ids (56, 61, 65) that were already mapped from real reports. All of them
report `productId` 1, which the Android app's own `ProductType` table calls
`PASS_APC_BOILER` -- and every one of the seventeen ids in that family this
table already knew is mapped `GAZ_BOILER`, with no exception. Seventeen
independent agreements is what the inference rests on.

What they declare is deliberately the minimum: the name, the type, and the
off/heat pair. No flag. There is no capture for any of them, and the three
boilers mapped from real reports declare exactly this and nothing more, so
copying that shape claims no more than the evidence does. The fall-through
already gave these ids `{off, heat}`, so nothing a device *does* changes --
what changes is the name (`Unknown product (1)` becomes `Naema Micro 30`), the
type, and the repair that used to ask a reporter for a dump the catalogue
already answers.

They share one branch and a name table rather than one `elif` each, because
the body is identical and only the commercial name differs. Two names repeat
across ids (257/260, 258/261); they are distinct models in the vendor's
catalogue and stay distinct here.

**The other ~165 ids sharing `productId` 1 are deliberately left unmapped.**
They are Guillot collective boilers -- VARMAX, VARBLOK, VARFREE, CONDENSINOX
-- a product class nobody has ever reported running through this integration.
The argument that makes the Naema safe (a family with seventeen confirmed
members) does not reach them, and mapping a model is what *stops* the
unknown-model repair asking its owner for a dump. Naming a line we have never
seen would trade away the only signal that would tell us it exists.

Limits. The catalogue gives a name; it says nothing about capabilities, modes
or flags. A boiler here that turns out to need a flag will need a dump like
any other. **The nine Alfea heat pumps the same sweep returned (25, 29, 32,
34-39) were deliberately left out**: `CozytouchDeviceType.HEAT_PUMP` wires
`currentTemperatureAvailableZ1` / `Z2`, `HeatingModes` and
`exhaustTemperatureAvailable`, and every mapped heat pump got those from a
capture. Naming them would mean guessing which zones they report, which is
the one thing this table must not do.

The sweep itself stopped at model id 56 when this was written
(`research/fetch_model_catalogue.py` is resumable); it has since been finished,
and what that changed is the entry below.

### The whole catalogue ships, as a name and nothing more

`research/fetch_model_catalogue.py` finished the sweep the boilers entry above
started : 1759 rows, every id `GET /magellan/productmodels/models/{id}` answers
for, up to 2450. `model_catalogue.py` is that table, verbatim, minus the 101
rows whose name is a firmware slot rather than a product -- `BD1 DEFAULT`,
`ROOM_0`, `UI_3`, the `GENERATOR_n` nodes. 1583 names, of which 1526 belong to
ids this table has no branch for.

It is read in one place, the fall-through at the end of `get_model_infos`, and
it sets the name and nothing else. The type stays `UNKNOWN`, the modes stay the
off/heat pair the fall-through always gave, and `get_unmapped_models` keys on
the type -- so every repair that asked its owner for a dump still asks. What
changes is that the dialog is about "Alfea Extensa A.I. 3 R32" instead of
"Unknown product (207)", which is the difference between a reporter recognising
their hardware and not.

This is the opposite trade from the boilers above, and deliberately so. Mapping
a model *silences* the repair, which is why only 38 of these 1583 were mapped :
naming one in the fall-through costs nothing, because the signal that the model
exists is untouched. The names are kept in the vendor's own spelling, capitals
and all -- `BILBAO 4 H 0750W BLC` reads oddly in Home Assistant, but inventing
a prettier form for 1526 products nobody here has seen would be a guess per
product.

Limits. A name is all it is : no capabilities, no modes, no flags, and no type.
`productId` was dropped from the shipped table -- it groups the catalogue into
families (1 boilers, 2 heat pumps, 47/62 water heaters, 53/64 radiators) and
that grouping is exactly the inference the boilers entry argues has to be
earned family by family, not read off a column.

### Seven names the vendor spells differently

The same sweep is checkable against the branches, and it contradicts seven of
them on a point of fact rather than of style :

| id | was | now | what the catalogue says |
| -: | --- | --- | --- |
| 418 | Atlantic Loria Duo 6006 | Loria 3 Duo R32 | 416-425 is a contiguous Loria R32 block; 418 is `LORIA 3 DUO R32`, and the Loria Duo 4/6-8 are ids 575-578 |
| 1543, 1546, 1547, 1551 | Asama Connecté II **Ventilo** … | Asama Connecté II … | the catalogue enumerates the whole line as wattage × colour (1540-1555) with no Ventilo variant, and these four land on a cell each |
| 1622 | Thermor Riva 5 | Riva 5 étroit 1300W BLC | `RIVA 5 ETROIT 1300W BLC BRI`; the plain Riva 5 is 1559-1561 |
| 2374 | Explorer EVO 3 (260L) | Explorer EVO 3 (270L) | `AE CV5 DACH FS 270L PE COIL (DE)` |

The forty-odd other disagreements are left alone : they are the branches
spelling a readable name where the catalogue has an internal reference
(`Calypso 200L` against `TD 200 VS AT 1200M TYB V5S`) or a slot placeholder
(`Naviclim Hub` against `CLIF Default`), and the readable one is the point.
Nothing here touches a type, a mode or a flag -- the seven are names on
hardware nobody here owns, and the evidence is a name.

### A room slot is whatever its gateway drives, not an air conditioner (issue #172)

`557-561` was read as "air conditioner room unit" from the accounts that had
one. It is not a product: it is the *room's index* behind a gateway. Issue
gduteil/cozytouch#172 (September 2026) is the same five ids reporting Sauter
connected radiators, and the two are indistinguishable device-side:

| | Navizone account (Mathieu, 28/08) | CozyBox account (issue #172) |
| - | - | - |
| `modelId` / `productId` | 557-559 / 26-28 | 557-560 / 26-29 |
| `longName` | `ROOM_0`… | `ROOM_0`… |
| `modelFamily`, `productRange` | null | null |
| gateway | 1758, `Air_Conditioning` | 2447, `Connectivity_Box` |

So the gateway is the only thing that differs, and `get_model_infos` gains a
fourth input for it. Resolving it needs the account's whole device list
(`masterDeviceId` is an id, not a model), which is why every caller now goes
through `get_device_model_infos(devices, dev, zoneName)` instead of calling
the table with a bare model id -- a caller that passed the id alone got the
wrong answer silently, and there were seven of them.

The radiators get `CozytouchDeviceType.RADIATOR`, a member added next to
`TOWEL_RACK` rather than reusing it: the API's own `ProductMainFamily` splits
`Radiator` from `Towel_Dryer` (`research/data/model_families.txt`), and the
reporter's first complaint after "it is not an air conditioner" would have
been "it is not a towel rail". The wiring is the towel rail's, via
`ELECTRIC_HEATERS` in `capability.py`; the one id where they part is 100506,
which stays dropped for towel dryers only -- no capture has one reporting it,
and the room radiators both report it and are sold on presence detection.

Limits, and they are real.

*The gateway is a proxy, not the answer.* Sauter sells the CozyBox for
radiators **and** heat pumps, so "behind a 2447" does not mean "radiator" in
general -- it means "not an air conditioner", which is the half that fixes
this report. A CozyBox driving a reversible heat pump would be named wrong
here. It stays this way because the alternative is worse: nothing the child
reports separates the two. The corpus was checked id by id --

- 100022 (`supportedSystemOperatingMode`, the HVAC-mode bitmask) reads 415 on
  the radiators and 415 on the 1734-1737 air conditioners. Useless.
- 166 reads 17 = {off, heat} on the radiators, but it is the *currently
  permitted* mask: the same Navizone air conditioners read 9 = {off, cool}
  under a summer lock and 411 elsewhere. An air conditioner under a winter
  lock would read 17 too.
- presence of 100800/100802/100804 (fan, quiet, louver) does not split them
  either: the radiators report all three and the Navizone units report none.

*One account.* Four rooms behind one CozyBox is the whole of the evidence,
and the commands were never tested -- the reporter said as much.

### A zone of a ducted heat pump is matched on its name, not its model id

The API reports the zones of a ducted heat pump as devices of their own. The
ids look like they encode the zone's index rather than a product: one capture
pairs 1505 with `THZONE_0`, 1506 with `THZONE_1`, and so on up. A range
guessed from one household is therefore a range a bigger installation walks
off the end of, which is why the branch matches the `THZONE` prefix on the
device's name instead. It reads the API's own `name` field and not
`customName` -- renaming a zone in the Cozytouch app is a thing people do, and
this has to survive it.

What a zone reports, in that one capture, is two capabilities -- 218 reading
`"0"` and 100014 reading `"255"` -- and no climate capability at all: no
setpoint, nothing to drive. So the branch claims a name, the `ZONE` type, and
an empty `HVACModes`. That last one is the point of mapping it: the
fall-through at the end of `get_model_infos` hands every unmapped model an
`{off, heat}` pair, and that is what made a zone read as a thermostat that
could heat.

The rest is silence. Unmapped, six zones arrived as `Unknown product (1505)`
*and* raised an unmapped-model repair each -- six dialogs asking for a
diagnostics dump about hardware working as designed. `Hub.get_diagnostics`
drops zones from the dump for the same reason. Reported upstream as
gduteil/cozytouch#167.

## `custom_components/cozytouch/select.py`

### The air-circulation duration is a select on the device's own grid

Capability 102021 was a free number bounded 15-300, and the vendor app never
offers it that way: its picker (seen 2026-08-29 on a room AC) runs 00:15,
00:30, 00:45 … 05:00 -- every quarter hour and nothing between, 16 or 17
minutes not enterable. The grid is not the app's invention either: the
device itself declares it, 102025 the minimum (15), 102026 the maximum
(300), 102022 the step (15), which the corpus reads on every model that
reports the duration at all (557-559).

A number entity cannot promise that grid -- Home Assistant validates a
typed value against the bounds but not against the step -- so a value the
hardware would refuse (or worse, silently round) was one keystroke away.
`CozytouchDurationSelect` builds its options from the three grid
capabilities read live, falling back to the mapping's constants for a
device that reports the duration without its grid, and shows them the way
the app does (`HH:MM`). A reported value off the grid reads as unknown
rather than snapping to a neighbour, since a snap would misreport what the
device said. The grid capabilities stay exposed as diag entities, disabled
by default (see the entry that hid them).

The entity moves platform (number → select), so its unique_id changes and
an existing install keeps an orphan number entity to delete by hand --
same trade as every promotion, taken for the same reason: the old shape
accepted writes the hardware never did.

## What a catalogue name is worth as evidence

### `# catalogue only`, and why two thirds of the table carries it

`GET /magellan/productmodels/models/{id}` names roughly 1500 model ids, and
`model_catalogue.py` is that scrape. It was added so an unmapped device would
read as its own product rather than `Unknown product (1234)`, and it decided
nothing else -- an id in it and nowhere else stayed typed UNKNOWN.

Reading it a second way turned out to be worth more. A product line in that
catalogue is a grid the vendor fills in one figure at a time: a volume, a
coil, a finish, a brand badge, a country. `RIVA 5 ETROIT 0300W CARBONE` sits
beside the `RIVA 5 ETROIT 1300W BLC` somebody captured; `TD 200 VS ATE 1200M
TYB V5S SERP` is the tank of `TD 200 VS ATE 1200M TYB V5S` with a coil in it.
Where the rest of a line was captured, the empty cells are the same appliance,
and the branch body those captures produced is the answer for all of them.

That is how 131 of the 203 mapped ids got here. Each is marked
`# catalogue only` in `model.py`, or sits in a table whose own comment says
the whole body is catalogue-sourced.

**What the marker promises, and what it does not.** A catalogue name is
evidence of identity, never of behaviour. So a marked id may claim exactly
what its captured sibling claims -- the name, the type and the modes -- and a
test asserts that field by field. It may not carry a flag of its own, because
a flag is a statement about what hardware does and nothing here has watched
this hardware do anything. Two cases where that line was drawn against the
temptation: the Lineo volumes inherit 1957's heating modes with `prog`
missing rather than the generic three, and `LORIA 3 DUO 2C R32` was left
unmapped because `2C` is a second circuit and its sibling declares
`currentTemperatureAvailableZ2 = False`.

**What it costs.** Mapping a model is what stops the unmapped-model repair
asking its owner for a diagnostics dump. Every id taken this way is a dump
that will now never arrive. That trade is worth making for a finish or a
badge, where the guess is nearly free and the alternative is a dialog
nagging somebody about a radiator that works; it is not worth making across a
generation or a power rating, which is why the `Alfea Extensa Duo AI UE`
variants and `NAIA 2 micro 25 G20/G25` are still unmapped and a test pins
them that way.

## The capability-only derivation (tried, and dropped)

### `derive.py` existed for one release, and the dump carries its inputs now

The vendor's app is not updated when a model ships, which means it cannot
work the way `model.py` does. Decompiling it (August 2026) showed how it
does work : it has no `modelId` table at all — it displays the `longName` /
`modelFamily` the server sends — and every feature the UI offers is derived
from the capabilities the device reports. `derive.py` was that derivation
rebuilt on our side, printed in the dump as a shadow next to the declared
table (`derived` / `declaredVsDerived` in each device's `model` block).

Nothing ever wired entities from it, because the evidence covers a handful
of device families and the table carries *deliberate* suppressions the
derivation would undo — 557-561 report capability 100507 and the vendor app
still offers no eco mode for them, which is why `ecoModeAvailable` is False
there.

It was removed (August 2026, one release after it landed) rather than kept
as a read-only shadow : a derivation nothing acts on is a second mapping to
maintain, and every conclusion it printed can be recomputed offline from a
dump that carries the raw inputs. So the dump carries exactly those instead
— every capability id with its value, and the API's identity fields
(`customName`, added to `API_DECLARED_FIELDS` for this ; `longName`,
`modelFamily`, `masterDeviceId`, `isAvailable`). A future switch-over would
start from the evidence below and the dumps on the tracker, with the table
kept as the override layer for exactly those suppressions.

The entries below are what the derivation rested on ; they stay because
they document what the capabilities *mean*, which outlives the module that
read them.

### `HVAC_MODE_BITS` : capability 100022 is a bitmask over the mode values

Measured against the corpus of captures : the units that report
`100022 = 411` (bits 0,1,3,4,7,8) are the ones whose `HVACModes` table
reads {0 off, 1 auto, 3 cool, 4 heat, 7 fan_only, 8 dry} — the exact same
set — and the heating-only boilers and heat pumps (1382, 1444) read `17`
(bits 0,4) against their {0 off, 4 heat}. Two independent matches, no
counter-example seen.

166 (`systemOperatingMode`) carries masks in the same space that *shrink*
while 100022 holds steady — one capture reads `166 = 9` {off, cool} on a
unit whose 100022 says {off, cool, heat, dry, auto}, mid-summer, so 166 is
the modes *currently permitted* (a seasonal lock) against 100022's
*supported*. The derivation read only 100022 ; if the vendor app turns out
to grey modes by 166, reflecting that is a climate-entity question, not a
mapping one.

**Bit 2 was the open question and is now answered: it is part of `auto`.**
The vendor's Android app gives its HVAC enum a mask of **6** for `auto` —
bits 1 and 2 — and matches a member when *any* bit of its mask is set. So
411 and 415 are the same set of modes, 285 has no unexplained bit, and
nothing on the wire needs a name it does not have. The masks in
`CAPABILITY_BIT_FIELDS` are that enum; every value in the capture corpus
decodes with no bit left over.

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

### A reading of zero is a reading

`CozytouchUnitSensor.native_value` asked `if self._last_value:` and returned
None otherwise. Every way a device says zero is falsy -- `0`, `0.0`, `"0"`,
and the `"0.00000000000000000000"` the API actually sends -- so a sensor
reading zero reported *unknown*. An outside temperature at 0 C, an idle power
at 0 W and a thermostat with no probe all came out identical, and none of them
was in fact unknown.

It surfaced from the other end: the reporter on gduteil/cozytouch#69 has a
`Température Thermostat Z1` sensor reading "Inconnu" while the climate card
next to it says "Actuellement : 0 °C". Same capability, two readings, because
one goes through this property and the other does not.

The guard is now against None and the empty string. Two things it deliberately
does not change: an unparseable value still reads as 0.0 rather than as
unknown, which is inherited and which `tests/test_sensor_values.py` pins with
its reasons; and nothing here decides whether a zero is *meaningful* -- a
thermostat with no probe genuinely reports 0, and that is the mapping's
problem, not the sensor's.

The same method scaled before it looked: `float(value) * self._display_factor`
on a capability the device had stopped reporting is a TypeError, reachable by
any ENERGY capability declared in kWh. Guarded in the same place.

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

### The gateway link is declared by registry id, not by identifiers

`via_device` names the gateway by its identifiers and lets the registry
resolve them; `via_device_id` names the registry id outright. The first is
deprecated, and on a current Home Assistant it does more than warn. The
deprecation report walks the stack for an integration frame to attribute
itself to; called from an entity's `device_info` there is none -- the call
comes from `entity_platform`, core code -- so the report raises a RuntimeError
instead of logging, and `_async_add_entity` dies with it.

Three hours of debug logging on a live install (2026-09-13, HA 2026.9) show
what that costs: `Error adding entity None for domain binary_sensor with
platform cozytouch`, once per room unit, every setup and every retry. Every
room unit's cloud-connectivity sensor was silently missing. Only
`binary_sensor` appears in the log because it was the only platform that
carried its *own* copy of the description -- the rest go through
`device_info_for`, whose device the registry already held from setup, so
their `async_get_or_create` came back with nothing to update and never
reached the report. One copy of a description is not tidiness here; it is the
difference between one platform failing and all of them.

So `device_info_for` resolves the gateway and declares `via_device_id`, and
the copy in `binary_sensor.py` is gone -- it now calls `device_info_for` and
overrides `name` alone, which was the only field it ever said differently.

The resolution is a registry lookup, which is why it is not a straight swap.
`via_device_id` naming a device the registry does not hold raises outright,
where the deprecated key merely warned; `via_device_info` answers with no link
at all in that case. Setup registering gateways first (above) is what makes
the lookup find something, so the two halves are one mechanism.

`DeviceInfo` gained `via_device_id` in **2026.8.0** -- bisected over the PyPI
wheels, since the field is a TypedDict key and no release note names it: 2026.7.0
does not have it, 2026.8.0 does. The declared floor is well below that, so both
spellings have to be reachable; `_VIA_DEVICE_ID_SUPPORTED` reads `DeviceInfo.__annotations__`
rather than comparing versions, and it is the only compatibility branch in the
integration. It goes when the floor passes 2026.8.0, which is not a floor worth
having for it -- Home Assistant removes `via_device` in 2027.8 and the branch
expires on its own.

`tests/test_topology.py` pins both spellings on whichever release the job
installed, rather than asserting whatever the installed `DeviceInfo` happens to
declare: a test that says one thing at the floor and another at the pin proves
neither.

### A timeout that stringifies to nothing named nothing

The same log carries `Error requesting Cozytouch_27906640 data: Network error
reading the setup view: , forcing reconnect`. The message is not truncated:
`asyncio.TimeoutError` -- what aiohttp raises past `REQUEST_TIMEOUT`, and the
commonest failure on this API -- carries no args, so `f"{err}"` is the empty
string. The one line that exists to name the cause named nothing, and the
traceback that does name it is behind a debug level nobody has on.

`account.why(err)` is `str(err) or type(err).__name__`, used at the five sites
that format a network error. A fallback, not a replacement: an error that says
something keeps saying it.

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

## `capability.py` : reading the descriptor capabilities

### Where the tables come from, and what they are not

The `supported_*` / `available_*` capabilities are bitmasks, and the ids
around them are small enumerations. Neither the API nor the iOS app says so
in any readable form -- three passes over the iOS binary logged the DHW
masks (168, 336, 105012) as unresolved. The **Android** app settles it: its
capability layer is Kotlin rather than compiled Swift, so the enums, their
masks and their API values are readable as source. `CAPABILITY_BIT_FIELDS`
and `CAPABILITY_VALUE_SPACES` are that reading.

Two properties of it matter when editing them.

**A member can own several bits.** The app tests `mask & value != 0`, not
`mask & value == mask`, which is what lets `auto` claim bits 1 and 2 at
once. A table written as one-bit-per-member would read 415 and 411 as
different mode sets, and they are not.

**The two mode spaces are different enums.** 166 and 100022 are the HVAC
space (off / auto / cool / heat / fan / dry, plus emergency heat,
pre-cooling and sleep which are values but never appear in a mask). 217 and
100023 are the control space (basic, prog, lifestyle prog, heating
anticipation, unexpected events, auto, energy saving, absence, scheduled
absence). They carry numbers of similar size -- 411 against 3331 -- and
reading one with the other's table produces plausible nonsense. Across the
whole capture corpus, split this way, **neither space leaves a single bit
unaccounted for**.

### What was left out, and why

The app also carries ventilation control and option masks that would fit
100002 / 100004 / 100021 / 100024, and a single-bit mask for 224. They are
not in the tables: on the captures, 10 of 38 readings of 100004 and 100021
set bit 7, which is past the last member the app names, and 13 of 15
readings of 224 set bits its one member cannot explain. Either those ids
are not what the app calls them, or the enum read out of it is partial.
Naming the low bits of a mask whose top bits are unexplained is how a wrong
reading gets believed, so they stay raw.

Where a mask *is* decoded and a bit is still unclaimed -- 164 bit 10, 188
bit 8, both seen on real accounts -- the reading says so (`unknown (1024)`)
rather than dropping it. These entities exist to investigate hardware
nobody here owns, so the bit nothing names is the interesting part. The
number the device sent stays on the entity as a `raw` attribute for the
same reason.

### `read_setpoint` : hundredths, but not for hot water

The app divides a program slot's target temperature by 100 when it reads
above 40, so a slot storing 1950 shows as 19.5 °C. No capture here has ever
shown one -- this is the app's rule, carried because a device that did it
would otherwise put 1950 on a dashboard.

It is scoped to the thermostat blocks (196-209, 100320-100333) on purpose.
The hot-water block (237-243) reports 50, 54, 60, 62 and 65 in the corpus:
real tank setpoints, all above the threshold. Applying the rule there would
turn a 65 °C tank into 0 °C, which is why `parse_slots` takes the
capability id and does nothing without one.

## `custom_components/cozytouch/number.py`

### Four classes that were one

`TemperatureAdjustmentNumber`, `TemperaturePercentAdjustmentNumber`,
`HoursAdjustmentNumber` and `MinutesAdjustmentNumber` differed in three
things -- what they declare about themselves, how an API value becomes a
displayed one, how a displayed one goes back -- and were copies of each other
in the hundred lines around those three. The bound alone, four lines of
`if value < min ... elif value > max`, was written eight times: once per read
and once per write in each class.

They are now one base class and four subclasses carrying `_from_api`,
`_to_api` and their own declarations, which is 134 lines less. The four names
survive because `async_setup_entry` dispatches on them, and every one of them
claims the same unique id it always did (`..._number_<capabilityId>`), so no
install wakes up with a renamed entity. That is what made the merge safe, and
`tests/test_number.py` pins it -- along with what each one reads and writes,
which nothing tested at all before.

### Setting a value now asks for a refresh whatever the unit

Hours and minutes called `async_request_refresh()` after a write; the two
temperature entities did not. Nothing distinguishes them -- the same
capability write, the same cloud, the same wait -- so a setpoint typed into a
temperature box sat unreflected until the next account poll, up to
`DEFAULT_POLL_INTERVAL` later, while a duration updated at once. It reads as
an omission rather than a decision, and the base class now refreshes for all
four.

### A ceiling reported as 0 collapses the range, and is left alone

`TemperatureAdjustmentNumber` re-reads its bounds from the device on every
update, through `lowestValueCapabilityId` and `highestValueCapabilityId`. The
guard is `if highestValue:` on the string the API sends, so `None` is ignored
but `"0"` is taken -- and a ceiling of 0 leaves a number entity that cannot be
set to anything.

That is almost certainly wrong, and it is pinned as it stands
(`test_a_bound_reported_as_zero_collapses_the_range`). Nothing in any capture
says whether a device reports 0 for a bound it has not been configured with,
and the suite here is characterisation: changing the reading on a guess would
be inventing behaviour for hardware nobody has looked at. It changes when a
dump shows one.

### The device description is declared once

Five classes carried the same three-line `device_info` property and a sixth
carried its own copy of the whole description -- which is the one that broke
(above). `CozytouchDeviceEntity` in `hub.py` carries it now; a platform class
inherits it and says nothing. `CloudConnectivity` still overrides `name`,
which was always the one field it meant to say differently.

## The declared floor

### 2025.12.0, and what raising it did not buy

The floor was 2025.4.0, and it was found by running the suite against
candidates rather than by reading changelogs. Config subentries -- one entry
per account, one subentry per device, the shape this integration is built on --
are absent from 2025.2.0: `ConfigSubentryFlow` does not import, and
`tests/test_floor.py` says so. The whole 2025.3.x line, which does have them,
cannot be installed at all: it pins `aiohttp==3.11.13`, which PyPI has since
yanked for a regression. A floor nobody can install is a claim nobody can test.

It was raised to 2025.12.0 -- the first of the last 2025 line -- in September 2026,
for no reason stronger than age: nothing in the integration needed an API from
it, and supporting an April 2025 release from late 2026 costs a matrix
combination somebody has to keep green and buys nobody anything.

What it did **not** buy is worth writing down, because it was the reason the
raise was proposed. `via_device_id` arrives in 2026.8.0, not in 2025.12, so
`_VIA_DEVICE_ID_SUPPORTED` survives the raise untouched. Measuring that before
editing anything is what kept the change honest about its own value.

The candidate was validated by running the whole suite against it, which is
also how the one surprise surfaced: `pycares<5`. Home Assistant pins aiodns,
aiodns does not pin pycares, and pycares 5 renamed the result types aiodns
annotates with -- so `import aiodns` raises `AttributeError: module 'pycares'
has no attribute 'ares_query_a_result'` and all twenty-one test files fail to
collect, with nothing in the error naming pycares. A real install never sees
it; it is an artefact of resolving an old release's dependencies fresh today.
The pin lives in `requirements_test_min.txt` and nowhere else, since the
current release resolves it correctly on its own.

## `.github/workflows/release.yaml`

### It installs with pip, where tests.yaml uses uv

The job is dispatched by hand a few times a year, so the minute it spends is
not worth the change on its own. Leaving it on pip also keeps a standing
proof that the requirements install without uv, which is what a contributor
following the README has.

## `custom_components/cozytouch/hub.py`

### The poll is the account's, every 30 seconds

30 seconds where every version of this integration has said 60, and it costs
*less* : the setup view carries every device, so this is two requests a minute
whatever the account holds, where the per-device poll it replaces was one per
device per minute — five for the gateway-plus-four-units account in
`docs/api-surface.md`. Anything from three devices up is both cheaper and
twice as fresh.

30 is also what the account's own `rateLimit` says, which is the one reading
of that field nothing contradicts. That is a coincidence worth naming and not
evidence : `rate_limit` is used as a ceiling in `poll_interval`, never as the
source of this number.

The floor of 15 s is where the requests stop buying anything. Atlantic's cloud
learns from the hardware on its own schedule, and no amount of asking makes a
radiator report sooner.

### `rateLimit` is read as requests per minute, as a ceiling only

Nobody knows what that field counts — `docs/api-surface.md` says so plainly —
but of the readings a working 60-second-per-device poll does not already
disprove, it is the strictest, and a ceiling wants the strictest. On the one
account ever captured it is 30, which permits everything down to the floor and
so never bites ; on an account that declares 1, it does.

### One coordinator on a beat, and one per device pushed to from it

This used to be a coordinator per device, each fetching
`/magellan/capabilities/?deviceId=` for its own — N requests a minute for N
devices. The setup view answers for the whole account in one request
(`account.refresh_setup`), which is why the shape was worth changing : the same
budget buys N times the frequency, and the cost stops growing with the number
of devices somebody ticked at setup.

The hubs stay coordinators with no schedule of their own, which keeps every
entity a `CoordinatorEntity` of its own device — one device failing still shows
as that device failing — and leaves `async_request_refresh()` after a write
working as it did. `Hub._async_update_data` therefore runs only when something
asks, which is after a write : re-reading the whole account to confirm one
setpoint would be the wrong trade at that one moment.

The hubs are a constructor argument of `AccountCoordinator` rather than
something attached afterwards : a coordinator that polls before it knows who to
tell would spend a request and drop the answer.

### The account coordinator subscribes to itself

Nothing else ever does : every entity listens to its hub, and Home Assistant
books a coordinator's next refresh only while it has at least one listener.
Without `async_add_listener(lambda: None)` the interval is dead letter — setup's
one refresh runs and no poll ever follows it. This was live for three releases ;
`tests/test_polling.py` covers it.

### A rate limit backs off, it does not fail

Being asked to slow down is not the same as having failed, and marking every
entity unavailable because the account is a few seconds ahead of its budget
would be a worse lie than a value that is one poll old. The values stand, and
the next tick finds the backoff still holding and skips in turn.

`ConfigEntryAuthFailed` is the opposite case and passes straight through the
coordinator, which answers it by opening a reauth dialog and by not
rescheduling itself. `UpdateFailed` would only book another attempt with the
same rejected password.

### An account failure reaches entities through their hubs

The failure belongs to the account, and no entity listens to the account
coordinator, so `_publish_error` marks every hub instead.

### The away window is staged, then committed

Editing the start or the end of the window stamps the change, and the commit
runs once that stamp is more than 20 seconds old, so both ends can be set
before either is sent. It used to hang off the hub's own 60-second poll, which
no longer exists — so it runs on every path that now stands in for it, the
account's tick and a post-write refresh alike. Hanging it off one of them would
have made the delay depend on which, and off neither would have left a staged
window sitting there for good.

### `modificationDate` reads as None rather than as 1970

Anything missing, unparsable or at or below zero comes back None. The field is
undocumented — there is no catalogue to check it against — so what it holds on
hardware nobody has captured is a guess, and a wrong timestamp on a dashboard
is worse than an empty one. A string is tolerated because `value` arrives from
this API as one.

`get_last_modification_date` takes the newest across the whole device rather
than one capability : the question it answers is whether the hardware is still
talking to Atlantic's cloud, and one capability can legitimately sit unchanged
for hours.

### The device lookup is a module function, not a method

`device_of` is read by eleven of Hub's methods and is deliberately not on the
class : the tests drive those methods unbound against a duck-typed stand-in
(`Hub.get_via_device(SimpleNamespace(...))`), which has no methods of its own.

### A write updates the local value only on a completed execution

A write that never lands has to leave the local value alone, and let the next
poll say what the device really did.

### The diagnostics dump describes the account, not the hub that was asked

Every device the setup returns is listed, whether or not somebody added it,
because what a mapping needs first is the model ids a user actually owns — with
the capability ids to go with them, since the setup view carries a capability
list for every device on the account.

Those lists are all as fresh as each other now that the setup view is the poll :
a device nobody added is refreshed on the same tick as one somebody did, where
it used to hold whatever the last reconnect said. `isConfiguredHere` therefore
says which devices have entities and no longer implies anything about freshness.

Zones are skipped. They are not hardware anybody has to map, and a dump is read
to find hardware that is ; listing them put two capability ids that resolve to
nothing — one of them declined on purpose — in front of whoever reads it, which
reads exactly like work to do.

### The gateway link, and `via_device_id`

The API declares the topology itself : every room unit and thermal zone carries
the gateway's id in `masterDeviceId`. Home Assistant can only draw the link if
the gateway was added too, since a device here is registered under the subentry
it was added as — so `get_via_device` returns None for a gateway, and for a
child whose gateway nobody added. None rather than a guess matters : HA logs a
warning when `via_device` names a device that is not in the registry. The
registry-id spelling is covered under `__init__.py` above.

## `custom_components/cozytouch/calendar.py`

### The program is a calendar, and read-only

The program is what these devices are scheduled by — it keeps running when Home
Assistant is off — and it could only be read as seven strings, one per day,
formatted for a dashboard. `get_schedule` made it machine-readable ; the
calendar makes it a week you can look at, and something the `calendar` triggers
can fire on : "when the program moves to its next setpoint" is an event start,
which is the shape of an automation nobody could write before.

Writing is `set_schedule`'s job and stays there. An event has a start and an
end, while a slot has only a start — the next slot is what ends it — and a
calendar that silently rewrote the following slots would be the wrong place to
resolve that.

The entity's state is not the useful part : a program that covers the whole day
means `event` is never None, so the entity sits at `on` for good. What is
useful is the current event and the next one, which is what the card shows and
what an automation reads.

### A calendar exists only for a block the device reports in full

All seven days rather than any : the mapping claims 196-209 wholesale, so a
device that has the block has every day of it, and a calendar built from a
partial one would show a gap where it should show a setpoint — which reads as
"nothing scheduled that day" rather than as missing data. The same rule gates
the per-day sensors arriving disabled, under `__init__.py` above.

### `CURRENT_EVENT_WINDOW` is a day either side of now

The last slot of a day runs into the next one, so the event in charge at 00:30
began yesterday. The window has to reach past now as well, since
`_events_between` takes a half-open range and would drop a slot starting
exactly on the boundary.

### Expansion is in Home Assistant's local time

The device stores minutes past midnight and nothing says which clock it keeps.
It reports an offset — the away-mode timestamps use it, and
`docs/architecture.md` records that path applying it twice — but no capture has
ever tied that offset to the program. Home Assistant's zone is the reading that
matches what the app shows for anyone whose house and hub agree, which is
everybody until somebody reports otherwise.

A slot runs until the next one, and the last of the day until midnight : the
next day's first slot starts at 00:00 — `set_schedule` refuses a day that does
not — so nothing is left uncovered. Events are selected by overlapping the
range rather than by being contained in it, because an event that started
before the window is the one running at its beginning.

The seven days are read once and not once per date, or a card asking for a year
would re-read and re-sort the same seven programs 365 times.

### An unusable slot is dropped, and the rest of the day still renders

A minute count past the end of the day, or a setpoint that is not a number.
Neither has been captured ; both are one bad matrix away from breaking every
event in the week. The temperature is carried as a float on purpose : the
summary formats with `%g`, and a value that arrived as a string — which this
API does — would raise there instead, taking the whole calendar with it.

`_slots_for` also sorts, though the device stores slots in order : an event list
built on that assumption without checking would put an evening setpoint in
charge of the morning.

### `heating` and `cooling` are the service's words

Kept so one vocabulary covers all three blocks. `capability.py` calls 203-209
the zone 2 program outside air conditioners, which is the same unresolved naming
`set_schedule` carries ; the program exists in both cool and heat, so nothing
here decides it either.

## `custom_components/cozytouch/account.py`

### The account owns the session, the token and the setup view

Everything a Cozytouch account declares — the token, the household, the zones,
the list of devices — is the same answer whatever device is asking, because
`setupviewv2` describes the whole account and not the device that fetched it.

This lived on `Hub`, which meant one config entry per device also bought one
session, one `POST /users/token` and one `GET setupviewv2` per device : a
gateway plus four units cost five logins for four copies of the same payload.
Worse, the state it filled in sat on the `Hub` *class* for a while, so the hubs
overwrote each other and the last one to connect won —
`tests/test_regressions.py` still pins the fix. The state was always shared ;
owning it in one object says so, and lets the shape be checked.

The per-device half stays on `Hub` : which capability ids that device reports,
what they mean for its model, and the targeted fetch that confirms a write.

The session is Home Assistant's own and not one of ours : it is closed when Home
Assistant stops, so there is nothing left to leak when a setup fails and the
account it built is discarded.

### `connect()` is idempotent, and a failing login is not collapsed

`online` is the whole reconnect mechanism, and every hub on the account flips it
and calls `connect()`. Re-checking it once the lock is held is what keeps a
*successful* reconnect from costing one login per device — five coordinators on
one beat make one request.

A failing one is deliberately not collapsed : a failure leaves `online` False,
so each waiter in turn takes the lock, sees that, and tries again. That is right
for a network failure and wrong for a refused password, which no number of
attempts fixes and which repeated *failed* logins could get an account locked
out for. So `InvalidAuth` is the one exception `connect()` does not fold into
`online = False` : it propagates, and `connect_or_auth_failed` turns it into
`ConfigEntryAuthFailed`, which Home Assistant answers by opening the reauth
dialog and by not rescheduling the coordinator that raised it — "ask once"
rather than "retry the rejected password every minute for as long as the
installation runs". `tests/test_reauth.py` pins the one-retry-per-waiting-hub
limitation that is left.

### A 429 backs off without dropping the connection

`_note_rate_limited` deliberately does not touch `online`. Every other failure
here drops the connection so the next poll re-authenticates, which for a 429 is
exactly backwards : the token is fine, and reconnecting spends a
`POST /users/token` and a `GET setupviewv2` on an account that just asked for
*fewer* requests. Repeated failed logins are also the one thing that can lock an
account out, so answering a throttle with a login loop is the worst move
available. The backoff is checked before the lock and before the login for the
same reason.

`RATE_LIMIT_BACKOFF` is 300 s and is a guess : Atlantic has never been observed
sending a 429, because nothing in the integration used to recognise one. It is
deliberately long — the cost of waiting five minutes too long is stale values,
the cost of waiting too little is being throttled for good. `Retry-After` is
read as seconds per RFC 9110 ; the HTTP-date form no gateway here sends falls
back to the default rather than throwing inside a poll.

`RATE_LIMIT_HEADERS` are logged rather than parsed, at warning level on purpose.
WSO2 API Manager, which `docs/api-surface.md` identifies as the gateway, is the
likely source, and those headers are what would say what the limit actually is —
the one thing no capture has ever established about `rateLimit`. The first
person to see a 429 is holding the only evidence there is.

### `invalid_grant` is the only answer that means the password is wrong

OAuth2 spells it that way and Atlantic uses the standard spelling. Anything else
malformed is a bad response, not a bad password : telling somebody their
password is wrong because the gateway hiccuped sends them off to reset a
password that was fine.

### The setup view is the poll

The same request `connect()` makes, called on a beat rather than once : it
carries a capability list for **every** device on the account, so one request
refreshes the whole account where the per-device route refreshes one device. It
also carries `absence`, which lives nowhere else — an away window set in the
Cozytouch app used to wait for a reconnect to be seen.

What it does not carry is proof of being as fresh as
`/magellan/capabilities/`. The two are the same three fields and the integration
has always built its entities from this payload at startup, but nobody has
compared their latency. `modificationDate` is in both and read by neither, so
the measurement is there to be made — `scripts/probe_api.py --cadence` makes it.

`last_poll` moves only on a success : a skipped or failed poll leaves it
standing, which is what makes it readable as "how old is what the entities
show".

### An expiring token just drops the connection

There is no separate retry loop anywhere : flipping `online` is how every
failure path here asks for a reconnect, and an expiry is another one, seen a
minute early.

### `API_DECLARED_FIELDS` are carried, not read

Nothing decides anything from them. They are carried because a diagnostics dump
is what a mapping gets built from, and the vendor's own name and family for a
model the table does not know is the first thing worth having. On the one
account these were read from, only the gateway carries a real `longName` and a
`modelFamily` — its children report an internal name or a literal `---`, and the
name the user actually typed is `customName` — so what other product families
put here is still open.

`SETUP_WRITABLE_FIELDS` is the subset the away-mode PUT has to send back :
`absence` is what the call is for and `id` addresses the resource, so neither
belongs in the body.

### The setup view refreshes every device, not just the one that asked

It carries capabilities for all of them, and this used to drop all but one —
which cost the account a per-device poll before its entities could be built, and
left a diagnostics dump describing the hardware nobody has mapped yet without
the capability ids that are the whole point of the dump. Zones and
`API_DECLARED_FIELDS` are refreshed on every view rather than set once at
creation, for the same reason : `isAvailable` moves as a device drops off its
gateway, a renamed zone has to reach the entity names it feeds, and a device
renamed in the app should not keep its old `longName`.

### A write waits for its execution

A write is not fire-and-forget : the POST answers with an execution id, and the
state of that execution is polled — once immediately, then up to five more times
a second apart — until it reports 3. Returning False means the local value must
stay as it was, and the next poll will say what actually happened.

A write is attempted even while the account is backing off from a 429, unlike
the polls : somebody just pressed a button, and refusing to send it because a
*reader* was throttled would be a worse answer than letting the server refuse
it. A 429 here still arms the backoff, so the readers learn from a write's
rejection. The execution loop is the burstiest thing the integration does — up
to six requests in five seconds for one button press — so it is the likeliest
place to meet the limit, and the last place to keep hammering after meeting it.

`fetch_capabilities` raises rather than returning a sentinel : the caller is a
coordinator, and an empty list is a legitimate answer that must not read as a
failure. Every failure but a 429 also drops `online`, which is what asks for the
reconnect.

### The absence window is a setup resource

Away mode is the one feature that is not a capability write alone : the window
lives on the setup, a resource of the account rather than of a device, which is
why it is on the account and not on the hub.

### Zones are not offered when adding devices

A THZONE is one zone of a ducted heat pump, not hardware : it reports no climate
capability, no setpoint, and two ids that resolve to nothing, so adding it would
create a device with an empty page behind it. The model comes from the table
rather than from the `modelInfos` filled in when a device first appeared — the
same lookup every other caller makes, and the name a zone is recognised *by* can
change under a cached one. The raw setup view still holds the zones, and the
`dump_json` option writes it out.

`get_unmapped_models` runs over the whole account rather than one device : the
setup view lists them all, and one report that covers everything is one issue
for the person who has to write it. It goes through the name-aware lookup too,
or a THZONE reads as an unknown product and the repair asks for a dump about it,
once per zone.

### A zone with no name reads as None, not as its id

Every caller puts the result in front of somebody — a device name, a line in a
diagnostics dump — and `Zone (1030104)` is a worse name than no name at all :
the id is ours to join on, not a room anybody recognises. The callers decide
what to show instead.

### Three exception types, because they want opposite handling

`CannotConnect` is retried until the network comes back ; `InvalidAuth` never
resolves without somebody typing a new password. `CozytouchRateLimited` is a
subclass of `CozytouchApiError` so a caller that only cares that the call failed
keeps working ; what it adds is `retry_after`, and what it does not do is touch
`online`.

## `custom_components/cozytouch/repairs.py` and `diagnostics.py`

### Why the integration asks, rather than waiting to be told

A device the model table does not know still gets entities — the generic
capabilities work — but the specifics are missing and its name reads
`Unknown product (…)`. The user has no reason to connect that string to anything
they can do about it, so the fix always depended on someone thinking to open an
issue and attach a diagnostics dump. The repair asks at the one moment it is
obvious the mapping is missing, and hands over a report that is already written.

The dump is the same information one click away from the integration page, with
the account details already taken out. Asking for it by hand cost the reporter
an option to tick, a log file to find and a JSON to redact, and that is where
most reports stopped.

### One report per account, covering devices nobody added

`_account_report` reads one account rather than scanning the entry store, and no
longer depends on which devices somebody added : the setup view carries a
capability list for every device on the account, so an unmapped model
contributes its capability ids whether it has a subentry or not. That used to be
the half of a report that was missing exactly when it mattered — hardware nobody
has mapped is hardware nobody has added yet. Any hub answers for any device on
its account, since the mapping is keyed on the model.

Several devices can share one unmapped model, and a silent one must not
overwrite what a talkative sibling reported.

Likewise one dump per account, covering every device the setup view returned. It
used to take one dump per device, which is a file per device to find, download
and attach for a report that needed all of them.

### The report URL carries ids and nothing else

Deliberately only the model ids and the capability ids nothing names : those are
what a mapping is built from, and they say nothing about the household. Values
stay out — among them the wifi SSID (219) and the gateway serial — and so does
the device name, which people call after a room or a child. A URL is clicked
without being read. The dump the form asks for carries all of that, stripped,
and is attached knowingly.

The query keys after `template` are the ids of that form's fields, which is how
GitHub fills them in. Renaming one in `.github/ISSUE_TEMPLATE/` breaks the link
quietly — it just arrives empty — so the two move together, and
`tests/test_repairs.py` checks that they still match.

### The issue is keyed on the model, and asked once

A pair of identical towel racks asks once, which has to be recognised while
walking the account rather than left to the issue registry to overwrite : the
second device would replace the first one's name and ask about the same mapping
twice. `REPORTED_MODELS` is written by the fix flow and read on every setup,
across every entry — the model stays unmapped until a release maps it, so
without it the issue would come back at each restart at someone who already did
their part, and one report speaks for whoever else owns the same hardware.

The issue is cleared on the way through as well as raised : a release that adds
the mapping is the expected end of it, and the setup that follows the update is
where that shows.

The report is read when the dialog opens rather than stored on the issue, so a
device that gained a capability, or an entry added since, is in what somebody is
about to send. Answering it closes the repairs raised for the other models it
covered ; the one the flow belongs to is deleted by Home Assistant.

### Thermal zones are asked about too

Nothing separates a zone from a real device nobody has mapped yet : the
gateway's id sits in `masterDeviceId` on both, and `modelFamily` is null on
both. Any rule would be a guess, and the two ways of being wrong do not cost the
same — a zone reported is an issue closed in seconds, a real device silenced is
someone never finding out why their hardware is half-supported.

## `custom_components/cozytouch/device_trigger.py`

### Two gaps, and nothing else

Home Assistant already builds device triggers out of the entity domains a device
happens to have : the connectivity binary sensor gives "connected" and
"disconnected", the away-mode switch gives "turned on", the climate entity gives
"HVAC mode changed". Nothing there reaches the weekly program, and the program is
what these devices are scheduled by — it keeps running when Home Assistant is
off, which is the whole reason the two schedule services exist.

So this module fills two gaps and no others :

- the program is seven diagnostic sensors, one per day, that no entity groups,
  so "the heating program changed" has no entity to be triggered on ;
- `climate.device_trigger` offers `hvac_mode_changed` and the two current-value
  triggers and no preset trigger at all — and the preset is where prog, override
  and basic are reported.

There is deliberately no `device_condition.py` and no `device_action.py`. The
`climate` domain already ships both for presets : "Cozytouch is set to prog" is
a condition Home Assistant writes itself, and setting one is a climate device
action. Adding ours would put two entries with the same meaning in one picker.

Both kinds are offered only when the device reports what they read : a water
heater with no cooling program gets no cooling trigger, and a device whose
climate entity has no prog preset gets none of the three. Which presets exist is
on the entity and not in the registry, so a climate entity with no state yet
answers for none of them — the same read `climate.device_trigger` makes.

The trigger list follows the programs the schedule services know : a program
nothing can read back is not one an automation should be told changed.

### Both halves fail silently, which is why they are tested

A trigger that never fires logs nothing. `tests/test_device_trigger.py` pins
which triggers a device is offered and what each one then watches.

- A schedule trigger carries no `entity_id` : a program is seven sensors, and
  which seven is a question about the device rather than about any one of them.
  It resolves to registry ids rather than entity ids, so an entity that gets
  renamed keeps working.
- A day sensor that is merely unreachable has not been reprogrammed, so the trip
  through unavailable and back is ruled out at both ends. Ruling both ends out
  also turns it into a state-value trigger : with no `to` or `from` at all, the
  state trigger fires on attribute changes too, and a renamed entity would read
  as an edited program.
- A preset trigger watches the `preset_mode` attribute and not the state : the
  state of a climate entity is its HVAC mode, and a setpoint change would fire
  it.
- `for` is offered on the preset triggers only. "Overridden for two hours" is a
  thing to automate on ; "changed for two hours" is not, since a program that
  changed does not change back.

### A sensor's capability id is the tail of its unique id

Sensors are keyed `cozytouch_{subentry_id}_{capabilityId}`, and a subentry id
carries no underscore. The two away-mode timestamps are the exception,
`{subentry_id}_0` and `{subentry_id}_1`, and 0 and 1 fall outside every program
block, so they rule themselves out.

## `custom_components/cozytouch/config_flow.py`

### One entry per account, one subentry per device

The account is what the credentials buy — one login, one setup view — and the
devices are what somebody actually wants entities for, added at setup time or
later from the integration page.

That shape is also why reauth is one dialog and one write, with no loop over
sibling entries : the credentials exist in exactly one place, and reloading that
entry brings every device on the account back with it. Before the reauth path
existed, a changed Cozytouch password left the account retrying the old one for
as long as the installation ran, saying only that it could not connect. The
username is not asked for again — changing it would point the entry at a
different account, which is an entry to add and not a password to fix.

`validate_input` raises `InvalidAuth` for a refused password and `CannotConnect`
for an account that could not be asked, and the caller shows a different message
for each : "check your password" is unhelpful advice during an outage.

The device list is read once on the way into the subentry step and kept across
the submit : the step is re-entered to answer the form, and logging in again to
resolve the id somebody just picked would double the cost of adding a device for
nothing.

### Only the device id travels in a picker option

It used to be a whole dict — credentials included — serialised with `str()` and
read back with `ast.literal_eval`, which put the account password in the form
the browser posts.

### All three options are account-wide

`dump_json` always was, since there is one `Cozytouch.json`. `create_unknown`
follows it rather than earning a reconfigure flow per device for a setting used
to work out what a value means. `poll_interval` has to be : there is one poll
for the account, so a per-device interval would describe something that does not
exist.
