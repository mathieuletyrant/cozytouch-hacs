# How the integration works

`CLAUDE.md` says what to do and where. This says how the thing runs, so that
a change can be reasoned about before it is made. It was written by reading
the code as it stands on `main`, and it says which parts are load-bearing and
which are inherited from upstream and never exercised.

## The one thing to understand first

The Cozytouch API has no vocabulary. A device reports a list of items shaped
exactly like this, and nothing else:

    {"capabilityId": 93, "modificationDate": 1786182322, "value": "1"}

No name, no type, no unit, no bounds, no enum labels. `docs/api-surface.md`
records the session that went looking for a catalogue and established there
isn't one — `refs/` holds only `countries`, and no OpenAPI spec is published.

So the whole integration is one long act of translation: **a numeric model id
plus a numeric capability id become a Home Assistant entity**, and every rule
for doing so was reverse-engineered from captures. Two tables carry all of it:

- `model.py` — `modelId` → what the product is and what it can do
- `capability.py` — `capabilityId` (+ the model's answer) → what entity to build

Everything else is plumbing around those two.

## The shape of a running install

One config entry is **one Atlantic account**, and one subentry of it is **one
device**. An account with a gateway and three room air conditioners is one
entry with four subentries: one login, one setup view, and one 60-second poll
per device, because that poll is the only part that is genuinely per device.

It was one entry per device until the account entry landed, which is why the
per-account state matters: four entries each held their own copy of a payload
describing all four, and that state lived on the `Hub` *class* for a while, so
they wrote over each other and the last one to connect won. It is one object
now, shared on purpose. `tests/test_regressions.py` pins both halves — nothing
on the class, and one login when ten hubs reconnect at once.

```
config entry (the account) ──> CozytouchAccount
                                │
                                │  POST /users/token                      once, then on expiry
                                │  GET  /magellan/cozytouch/setupviewv2   on every (re)connect
                                │
                                ├─ setup     address, zones count, rateLimit…
                                ├─ zones     zone id → name, refreshed on every setup view
                                └─ devices   every device on the account, each with the
                                             capability list the setup view gave for it
                                │
  subentry (a device) ──> Hub (DataUpdateCoordinator)
                                │
                                │  GET /magellan/capabilities/?deviceId=  every 60s
                                │
                    get_capabilities_for_device()
                                  │
                       for each reported capability:
                       get_capability_infos(modelInfos, id, value, availableIds)
                                  │
                                  ▼
                    a dict — name, type, category, wiring —
                    which each platform filters on `type`
                                  │
   ┌────────┬────────┬───────┬────┴────┬────────┬─────────────┐
 climate  sensor   switch  number   select  datetime   binary_sensor
```

Each platform's `async_setup_entry` loops over `entry.subentries` and adds its
entities with `config_subentry_id=`, which is what puts them under the right
device.

`binary_sensor` is the odd one out: it is not capability-driven at all. It
builds exactly one entity per subentry, a connectivity sensor reflecting
`hub.online` — which is the *account's* connection, the same answer for every
device on it.

## The account and the hub

`account.py` is the HTTP client and everything the account declares.
`hub.py` is a `DataUpdateCoordinator` per device plus the mapping accessors
the platforms call. Worth knowing before changing either:

**Reconnect is driven by `account.online`.** Almost every failure path clears
it and raises `UpdateFailed`; the next poll sees it False and calls
`connect()`, which re-authenticates and re-fetches the setup view. There is no
separate retry loop — the coordinators' own schedule is it. Token expiry is
handled the same way, pre-emptively: `_token_expiry` is set 60 seconds short of
what the server said, and crossing it just clears `online`.

`connect()` is idempotent under an `asyncio.Lock`, and re-checks `online` once
the lock is held. Every hub on the account clears the flag and reaches for the
login on the same beat, and repeated *failed* logins are the one thing that
could lock a Cozytouch account out (`docs/api-surface.md`).

**The session belongs to Home Assistant.** `async_get_clientsession(hass)`,
which is closed at shutdown. There is nothing to close by hand, which matters
because HA does not call `async_unload_entry` when a setup fails — it discards
whatever the setup built and tries again.

**Setup does not depend on the polls landing.** The setup view carries a
capability list for every device, so the entities are built from what it said;
each hub's first poll only refreshes values. Only the account's `connect()`
raises `ConfigEntryNotReady`, so one flaky device leaves its own entities stale
instead of failing a setup its siblings share.

**Writes are not fire-and-forget.** `set_capability_value` POSTs to
`writecapability`, gets an execution id back, then polls
`/magellan/executions/{id}` — once immediately, then up to five more times at
one-second intervals — waiting for state 3. Only then is the local value
updated. A write that never completes leaves the local cache stale until the
next poll corrects it.

**Away mode is the exception to everything.** It is the one feature that does
not go through `writecapability` alone: the absence window is `PUT` to
`/magellan/v2/setups/{id}` — a setup-level resource, not a device one, which
is why `set_absence` lives on the account and the staging on the hub — and
only then written to the timestamps capability. And it is deferred: editing
the start or end datetime entity stages the value on the hub and stamps
`_timestamp_away_mode_last_change`; `_async_update_data` commits it once that
stamp is more than 20 seconds old. The delay is deliberate — it lets someone
set both ends before either is sent. The switch entity compensates for the
API lagging behind by ignoring the reported value for a few reads
(`_nb_ignore`).

## The model table

`get_model_infos(modelId, zoneName=None)` is one long `if/elif` returning a
dict. 63 model ids are mapped today: 26 water heaters, 9 towel racks, 9 AC
user interfaces, 6 air conditioners, 5 gateways, 4 boilers, 2 heat pumps,
2 thermostats. Anything else falls through to `Unknown product (…)` with a
minimal off/heat mapping.

Three kinds of key come back:

- **Identity** — `name`, `type`, `modelId`.
- **Enumerations** — `HVACModes`, `HeatingModes`, `fanModes`, `swingModes`,
  `AirCirculationSpeeds`. Each maps the integer the device reports to the
  Home Assistant constant. These are per-model because the same integer means
  different things on different products.
- **Flags** — `ecoModeAvailable`, `awayModeTemperatureAvailable`,
  `quietModeAvailable`, `overrideModeAvailable`, `exhaustTemperatureAvailable`,
  `currentTemperatureAvailable{,Z1,Z2}`.

The flags are the dangerous part, and `tests/test_capability.py` exists
because of it. A flag is read by `capability.py` to decide whether an entity
exists at all, so setting one on a branch shared by nine model ids removes or
adds an entity on all nine. Worse, most flags default to `True` when absent,
so flipping a default in `capability.py` changes every model at once while
leaving `model.py` — and every case in `test_model.py` — untouched. The
isolation tests walk the whole table and assert which model ids declare each
flag, which is the only place that catches it.

`HVACModesCapabilityId` is the subtlest entry. It says which capability id
carries the mode for this product: `{7, 8}` by default, but `{1, 2}` for the
Alfea Extensa Duo A.I. 3 R32 (211). The same physical function, a different
number, on two models of the same product family.

`zoneName` is threaded in for one purpose: air conditioners and their user
interfaces are named `Air Conditioner (Salon)` rather than
`Air Conditioner (#1)` when the zone is known. `Hub.get_model_infos` resolves
the zone, following the `iothubChildrenIds` tag to a master device's zone for
sub-devices.

## The capability mapping

`get_capability_infos(modelInfos, capabilityId, capabilityValue, availableCapabilityIds)`
answers for 172 ids. Reading the chain end to end is one way to find out what
one of them becomes; `scripts/dump_capability_map.py` is the other — it walks
every id against one model per device type and prints the answer. It writes
nothing, so there is no table anywhere to fall out of date.

Three return values, and they are not the same:

- **a dict** — build this entity
- **`{}`** — this id is claimed, and refused for this device. Capability 172
  (the absence setpoint) returns `{}` on air conditioners because they report
  it and never honour it.
- **`None`** — nothing maps this id. It shows up in the diagnostics dump under
  `unmapped`, and becomes a raw entity only if the user ticked
  `Create entities for unknown capabilities`.

The dict's `type` is what routes it to a platform, and the routing is
one-to-many. A `switch` capability produces **both** a `CozytouchSwitch` on
the switch platform and a `CozytouchBinarySensor` on the sensor platform. An
`away_mode_timestamps` capability produces four entities: two sensors and two
datetimes. A `climate` capability produces a climate entity and a sensor. This
is inherited behaviour, not an accident to clean up casually — the entity ids
are in people's dashboards.

Which type reaches which platform is only visible by reading the seven
`async_setup_entry` functions, so here it is once:

| type | platform |
| --- | --- |
| `climate` | climate **+** sensor |
| `string`, `int`, `temperature`, `pressure`, `energy`, `volume`, `water_consumption`, `percentage`, `signal`, `time`, `timezone`, `prog`, `progtime`, `binary` | sensor |
| `switch` | sensor **+** switch |
| `away_mode_switch` | sensor **+** switch |
| `away_mode_timestamps` | sensor ×2 **+** datetime ×2 |
| `temperature_adjustment_number`, `temperature_percent_adjustment_number`, `hours_adjustment_number`, `minutes_adjustment_number` | number |
| `select` | select |

It also runs the other way. A device can report two ids for the same thing —
222 and 226 both carry the away-mode window — so the mapping names each as a
`capabilityDuplicate` of the other, and `get_capabilities_for_device` drops
whichever arrives second. One window, one pair of entities, whichever id the
hardware happens to use.

The fourth argument, `availableCapabilityIds`, is what the device actually
reports. It exists because a model id is reused across hardware that does not
implement the same things: the mapping asks "does this device back that
feature?" before wiring it. That is why the climate branch is full of
`if 100507 in availableCapabilityIds`.

### The climate branch is the wiring hub

Capabilities 1, 2, 7 and 8 don't just produce a climate entity — they collect
the ids of every other capability that entity needs, and the climate entity
reads them back out:

| key | points at | used for |
| --- | --- | --- |
| `targetCapabilityId` | 40, or 17/18 on a heat pump | the setpoint |
| `targetCoolCapabilityId` | 177 | the cooling setpoint |
| `currentValueCapabilityId` | 117 / 118 | the measured temperature |
| `lowest/highestValueCapabilityId` | 160 / 161 | the setpoint bounds |
| `lowest/highestCoolValueCapabilityId` | 162 / 163 | the cooling bounds |
| `hvacActionCapabilityId` | 181 | the mode actually running |
| `stepCapabilityId` | 294 | the setpoint granularity |
| `fanModeCapabilityId` | 100801 | fan speed |
| `quietModeCapabilityId` | 100802 | the quiet fan mode |
| `swingMode/swingOnCapabilityId` | 100803 / 100804 | louvres |
| `activity/eco/boostCapabilityId` | 100506 / 100507 / 100505 | presets |
| `progCapabilityId` + override trio | 184, 157, 158, 159 | the schedule presets |
| `airCirculationCapabilityId` | 102024 | reporting FAN while circulating |

Two details in there are not obvious. `hvacActionCapabilityId` (181) exists
because on a zoned install only the master picks the mode: a slave keeps
showing its own request while running whatever the master imposes. And
`HVACMode.AUTO` is deliberately absent from the `HVAC_ACTIONS` table — a
system in auto is really heating, cooling or idle, and guessing would be
worse than reporting nothing.

The presets are a small state machine. `basic`/`prog`/`override` come from the
scheduler (184 and 157); `none`/`activity`/`eco`/`boost` come from the three
mode capabilities. Setting a temperature while in `prog` silently switches to
`override` first, because writing a setpoint the scheduler will overwrite in
an hour would be a lie.

## Entity identity, and why renaming is safe

Unique ids key on the capability id, never on the name:

    sensor    cozytouch_{subentry_id}_{capabilityId}
    select    cozytouch_{subentry_id}_{capabilityId}  (same shape, other platform)
    switch    cozytouch_{subentry_id}_switch_{capabilityId}
    number    cozytouch_{subentry_id}_number_{capabilityId}
    climate   cozytouch_{subentry_id}_climate_{capabilityId}
    datetime  {subentry_id}_0 / _1        (away mode, not domain-prefixed)

Every platform funnels that id through one parameter, `config_uniq_id`, which
is also what the device is registered under — `identifiers={(DOMAIN, it)}`. It
was the config entry id when an entry meant a device. Nothing else in the
integration builds an identity, which is why moving to subentries touched one
argument per platform.

So renaming a capability changes its translation key and its friendly name and
leaves every existing entity in place. Recent commits rely on this — four
water-heater capabilities were renamed without breaking anyone's history.

The name doubles as the translation key, which is why a new capability needs
an entry in all three of `strings.json`, `translations/en.json` and
`translations/fr.json`. Miss one and Home Assistant shows the raw key —
`available_system_modes` — in the UI.
`tests/test_capability_coverage.py` walks every name the mapping can produce
and fails on the gap, so this is caught rather than discovered by a user.

Devices are registered per subentry, and hung under their gateway via
`get_via_device` — but only when the gateway was added as a device of its own.
The API declares the parent in `masterDeviceId`, so the topology is reported
rather than inferred; what has to be got right is not claiming a link to a
device Home Assistant doesn't have. `tests/test_topology.py` pins that.

## Diagnostics is the intake path

`get_diagnostics` is not a debugging afterthought, it is how new hardware gets
mapped. One dump per account. It lists **every** device the setup view returned
— including the ones nobody added — with its model id, whether the table knows
it, and the capability ids that came back `None`. That last list is literally
what a new mapping is written from, and unmapped hardware is usually hardware
nobody has added yet, which is why it is no longer held back to the configured
device. Credentials and anything that would place the account at an address
are redacted.

`isConfiguredHere` says which devices have a subentry, and so which capability
lists a 60-second poll keeps fresh rather than the last setup view. It is read
off the entry's subentries, so the dump does not depend on which hub produced
it.

## The services

One service, `cozytouch.set_schedule`, writes a weekly program. A day is a
`[[minutes, temperature], …]` matrix of ten slots, unused ones `[0, 0]`, and
the days are seven consecutive capability ids — 196 for heating Monday, 203
for cooling Monday. The service validates that the first slot starts at 00:00,
since otherwise the start of the day would have no target.

It resolves the hub through the entity registry rather than `hass.data`, which
lets it tell apart "that entity belongs to another integration" from "that is
ours but its entry isn't loaded". The registry entry's `config_subentry_id` is
the last hop: it names which device, and so which hub.

## Testing

247 tests, almost all characterisation tests. They pin the mapping as it
stands, not as it ought to be: most entries came from one user's capture of one
device, so green means "nobody changed this by accident", never "this is
correct".

Almost all of them are table tests. The exception is
`tests/test_sensor_values.py`, which pins what the value builders in
`sensor.py` return character for character — the zero padding, the double space
before a temperature, a float setpoint still reading as a whole number. That
file renders the strings people actually look at and had no tests at all, which
is how a formatting change can be both invisible in review and visible on every
dashboard.

**Almost nothing tests the API client.** `tests/test_regressions.py` now covers
the connect lock, a refused login and what the setup view fills in; token
expiry and the write-execution polling are still documented and unverified.
That is the largest hole left in the suite, and it is worth knowing before
changing `account.py`.

`tests/test_floor.py` is what makes the second CI job mean something: it
imports every module — the suite otherwise imports four of them — and names the
subentry APIs the declared minimum Home Assistant has to provide. The floor was
set by running it, not by reading a changelog.

`CLAUDE.md` has the per-file breakdown and the venv instructions. Two things
worth repeating: `test_capability.py` carries a hard count of mapped model ids
(63) and walks `range(1, 2500)` — adding a model means updating the count, and
adding one above 2500 means widening the walk — and the requirements are pinned
exactly, so the version of Home Assistant the tests run against is a decision
somebody made rather than whatever pip found. CI runs the suite twice, once on
that pin and once on the oldest release `hacs.json` claims to support.

`ruff check .` is the other half, and CI gates on it. `pyproject.toml` carries
the configuration and the reason for every rule that is switched off.

## Rough edges, verified

Things that are true of the code today and would otherwise be discovered the
hard way. Most are inherited from upstream.

This list is only worth having if it is accurate, and it had gone stale: five
entries described code that had already been fixed or removed — a `time`
platform that no longer exists, a `power` type, three capabilities filed under
`diagnostic`, `percentage` claiming `SensorDeviceClass.BATTERY`, and an unused
`CozytouchDateTime`. They were checked one by one against the tree and dropped.
Anything below has been re-verified; add to it in the same spirit, and delete
from it when a change makes an entry untrue.

- **`signal` maps to `SIGNAL_STRENGTH` with `UnitOfSoundPressure.DECIBEL`.**
  The unit string is `dB`, which is valid for the device class, but it is
  reached through the sound-pressure enum.
- **The away-mode timestamp sensor applies the device's timezone offset twice.**
  `CozytouchAwayModeTimestampSensor.get_value` adds the offset the device
  reports to the unix timestamp, then formats the sum with a bare
  `datetime.fromtimestamp()` — which reads it in Home Assistant's local zone,
  adding the offset again for anyone not on UTC. `tz=UTC` is the fix; it changes
  what the sensor displays, so it wants a capture of what the Cozytouch app
  shows before it is made. The line carries a `noqa: DTZ006` so the linter does
  not have to be argued with twice, and
  `tests/test_sensor_values.py::test_the_timezone_offset_is_applied_twice_outside_utc`
  pins it, so making the fix shows up as that test failing rather than as a
  silent shift in what people see.
- **A few capabilities are deliberate placeholders.** 101–104 come out as
  `Capability_101`…, 105906/105907 as `Target 105906`…, and 312 is commented
  `For test`. The coverage test skips them by regex, which is why they have no
  translations.
- **A version 1 config entry cannot be loaded.** One entry per device became
  one entry per account with a subentry per device, and no
  `async_migrate_entry` was written — nobody was running the integration yet.
  Such an entry lands in `MIGRATION_ERROR`, and the fix is to remove the
  integration and add it again.
- **`create_unknown` is account-wide**, so turning it on to investigate one
  device adds raw entities on all of them.

## Where the boundaries are

- **Do not fetch a capability catalogue.** There isn't one.
  `docs/api-surface.md` records roughly 90 paths already ruled out; read it
  before probing anything.
- **Do not widen a shared model branch to fix one product.** Nine ids share
  the ACI HYB branch and six share the air-conditioner branch. Model-specific
  behaviour goes behind `if modelId == …`.
- **Do not claim a type for a capability whose encoding is unverified.** It
  belongs in `SELF_DESCRIBING_CAPABILITIES`: named, raw string, off by default.
  24 ids sit there today.
- **Do not rename entities to tidy up.** Unique ids survive a rename, but the
  friendly name people built dashboards on does not.
