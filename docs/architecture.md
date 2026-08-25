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

One config entry drives **one device**. An account with a gateway and three
room air conditioners is four entries, and each one builds its own `Hub`, its
own `aiohttp` session, and its own 60-second poll. They share nothing but the
Atlantic account.

That is why the per-account state on `Hub` matters: it used to live on the
class, so the four hubs wrote over each other's setup and the last one to
connect won. `tests/test_regressions.py` pins it to the instance now.

```
config entry ──> Hub (DataUpdateCoordinator + API client)
                  │
                  │  POST /users/token                       once, then on expiry
                  │  GET  /magellan/cozytouch/setupviewv2    on every (re)connect
                  │  GET  /magellan/capabilities/?deviceId=  every 60s
                  │
                  ├─ _setup     the account: address, zones count, rateLimit…
                  ├─ _zones     zone id → name, refreshed on every setup view
                  └─ _devices   every device on the account, but capabilities
                                only for the one this entry drives
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

Two entities are not capability-driven, and so are not in that fan-out.
`binary_sensor` builds exactly one per entry, a connectivity sensor reflecting
`hub.online`. The sensor platform builds one more beside its capability
entities: a `timestamp` diagnostic carrying the newest `modificationDate` the
device reports, which is what says whether the hardware is still talking to
Atlantic's cloud when a reading has stopped moving. It is created only when the
device actually reports a date, the same rule the model flags follow.

## The Hub is two things at once

`hub.py` is the largest file and does not separate its two jobs. `Hub`
subclasses `DataUpdateCoordinator` *and* is the HTTP client. Worth knowing
before changing it:

**Reconnect is driven by `self.online`.** Almost every failure path sets it
to `False` and raises `UpdateFailed`; the next poll sees `online is False`
and calls `connect()` again, which re-authenticates and re-fetches the setup
view. There is no separate retry loop — the coordinator's own schedule is it.
Token expiry is handled the same way, pre-emptively: `_token_expiry` is set
60 seconds short of what the server said, and crossing it just flips `online`.

**The session is owned, and leaks if you forget it.** Home Assistant does not
call `async_unload_entry` when setup fails, and it discards the hub and builds
a fresh one on each retry. So the session is closed by hand: `__init__.py`
holds three `await theHub.close()` calls — one when the first connect fails,
one when the first refresh or the platform setup raises, one on unload — and
`config_flow.py` a fourth for the throwaway hub it builds to test credentials.

**Writes are not fire-and-forget.** `set_capability_value` POSTs to
`writecapability`, gets an execution id back, then polls
`/magellan/executions/{id}` — once immediately, then up to five more times at
one-second intervals — waiting for state 3. Only then is the local value
updated. A write that never completes leaves the local cache stale until the
next poll corrects it.

**Away mode is the exception to everything.** It is the one feature that does
not go through `writecapability` alone: the absence window is `PUT` to
`/magellan/v2/setups/{id}` — a setup-level resource, not a device one — and
only then written to the timestamps capability. And it is deferred: editing
the start or end datetime entity stages the value on the hub and stamps
`_timestamp_away_mode_last_change`; `_async_update_data` commits it once that
stamp is more than 20 seconds old. The delay is deliberate — it lets someone
set both ends before either is sent. The switch entity compensates for the
API lagging behind by ignoring the reported value for a few reads
(`_nb_ignore`).

## The model table

`get_model_infos(modelId, zoneName=None, deviceName=None)` is one long
`if/elif` returning a dict. 63 model ids are mapped today: 26 water heaters,
9 towel racks, 9 AC user interfaces, 6 air conditioners, 5 gateways, 4 boilers,
2 heat pumps, 2 thermostats. Anything else falls through to
`Unknown product (…)` with a minimal off/heat mapping.

**One device is recognised by its name instead of its id**, and it is the only
one: a THZONE, which is a zone of a ducted heat pump rather than a product. The
check runs before the id chain, so `deviceName` starting with `THZONE` wins over
any id — including an id that also belongs to a real product.

Keying on the name is not a shortcut, it is what the payload supports. A capture
pairs model id 1505 with the device the API calls `THZONE_0`, 1506 with
`THZONE_1`, and so on: the ids count the zones rather than name a product, so a
household with more zones than the captured one walks off the end of any range
guessed from it. The API's `name` is read rather than `customName`, since
renaming a zone in the Cozytouch app is a thing people do.

A zone reports two capabilities, neither of which resolves to anything, and no
climate capability. So it is **ignored, not surfaced**: `Hub.devices()` leaves
it out of what the config flow offers, and `get_diagnostics` leaves it out of
the dump. Adding one would create a device with an empty page behind it, and a
dump is read to find hardware that has to be mapped — listing a zone put two
ids that resolve to nothing, one of them declined on purpose, in front of
whoever reads it, which reads exactly like work to do. The raw setup view still
holds them and the `dump_json` option writes it out, which is the way back if
anybody needs to see what a zone reports.

Recognising the model is still what makes that possible, and it is what stopped
the noise it used to make: unmapped, a zone read as `Unknown product (1505)`
*and* raised an unmapped-model repair per zone, asking six times for a dump
about hardware working as designed. `HVACModes` is empty on purpose — the
fall-through's off/heat pair is what made a zone look like a thermostat that
could heat. Capability 218 is declined too: a zone reads "0" for it while the
API calls the zone available, so the sensor would contradict its own device.

The consequence to know when reading `hub.py`: every lookup it makes passes
`dev["name"]`, because a lookup without one answers `Unknown product` for a
zone — which would put the repair back.

`get_zone_name` answers **None** when the account does not name a zone, where it
used to answer the id as a string. Every caller puts the result in front of
somebody — a device name, a line in a dump — and `Zone (1030104)` is a worse
name than no name: the id is ours to join on, not a room anybody recognises. A
zone with no room falls back to the name the app shows (`THZONE_0`), and an air
conditioner to its position (`Air Conditioner (#1)`), which is what that branch
already did for a device with no zone at all.

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

    sensor    cozytouch_{entry_id}_{capabilityId}
    select    cozytouch_{entry_id}_{capabilityId}   (same shape, other platform)
    switch    cozytouch_{entry_id}_switch_{capabilityId}
    number    cozytouch_{entry_id}_number_{capabilityId}
    climate   cozytouch_{entry_id}_climate_{capabilityId}
    datetime  {entry_id}_0 / _1          (away mode, not domain-prefixed)

So renaming a capability changes its translation key and its friendly name and
leaves every existing entity in place. Recent commits rely on this — four
water-heater capabilities were renamed without breaking anyone's history.

The name doubles as the translation key, which is why a new capability needs
an entry in all three of `strings.json`, `translations/en.json` and
`translations/fr.json`. Miss one and Home Assistant shows the raw key —
`available_system_modes` — in the UI.
`tests/test_capability_coverage.py` walks every name the mapping can produce
and fails on the gap, so this is caught rather than discovered by a user.

Devices are registered per config entry, and hung under their gateway via
`get_via_device` — but only when the gateway was set up as an entry of its
own. The API declares the parent in `masterDeviceId`, so the topology is
reported rather than inferred; what has to be got right is not claiming a link
to a device Home Assistant doesn't have. `tests/test_topology.py` pins that.

## Diagnostics is the intake path

`get_diagnostics` is not a debugging afterthought, it is how new hardware gets
mapped. It lists **every** device on the account — not just the one this entry
drives — with its model id, whether the table knows it, and, for the entry's
own device, the capability ids that came back `None`. That last list is
literally what a new mapping is written from. Credentials and anything that
would place the account at an address are redacted.

Devices this entry does not drive carry a `null` capability block rather than
an empty one, because the hub only keeps capabilities for its own device and
an empty list would read as "this device reports nothing".

## The services

One service, `cozytouch.set_schedule`, writes a weekly program. A day is a
`[[minutes, temperature], …]` matrix of ten slots, unused ones `[0, 0]`, and
the days are seven consecutive capability ids — 196 for heating Monday, 203
for cooling Monday. The service validates that the first slot starts at 00:00,
since otherwise the start of the day would have no target.

It resolves the hub through the entity registry rather than `hass.data`, which
lets it tell apart "that entity belongs to another integration" from "that is
ours but its entry isn't loaded".

## Testing

279 tests, all characterisation tests. They pin the mapping as it stands, not
as it ought to be: most entries came from one user's capture of one device, so
green means "nobody changed this by accident", never "this is correct".

Almost all of them are table tests. The exceptions are the two that cover
`sensor.py`. `tests/test_sensor_values.py` pins what the value builders return
character for character — the zero padding, the double space before a
temperature, a float setpoint still reading as a whole number. That file
renders the strings people actually look at and had no tests at all, which is
how a formatting change can be both invisible in review and visible on every
dashboard. `tests/test_sensor_metadata.py` covers what the platform says about
a value rather than the value: it drives `async_setup_entry` with a hub
stand-in and asserts the state class and device class each capability type
comes out with, including that the pair is one Home Assistant accepts.

**Nothing tests `hub.py`** — not the reconnect path, not token expiry, not the
write-execution polling — so the invariants this document states about them are
documented and unverified. That is the largest hole left in the suite, and it is
worth knowing before changing the file.

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
- **`_zoneId` on the hub is only assigned for devices already in the list**, so
  it holds whichever device matched last rather than this entry's. Nothing in
  production calls `get_zone_name()` without an argument, so the value is never
  read; it would bite the moment something did.
- **`config_flow` declares `CONN_CLASS_LOCAL_PUSH`** while the manifest declares
  `cloud_polling`, which is what actually happens. The constant is legacy and
  unread by current Home Assistant.
- **`validate_input` is annotated `-> dict[str, Any]` and returns a `Hub`.**

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
