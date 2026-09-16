# What the Cozytouch API exposes

A record of a probing session run on 2026-08-20, kept so the next person
asking "can we stop guessing?" starts from what was already ruled out rather
than repeating it.

The short answer to that question is **no for capabilities, partly for
devices, and yes for model *names*** -- the last one found on 2026-09-12 and
corrected below, where this document previously said no catalogue existed at
all.

## How to probe

`scripts/probe_api.py` authenticates and prints the *shape* of what each route
returns. Add routes to its list and re-run; it never writes.

    umask 077
    pbpaste > ~/.cozytouch-pass          # password from the clipboard, not
    COZYTOUCH_USER=you@example.com \     # from the shell history
      COZYTOUCH_PASS_FILE=~/.cozytouch-pass \
      python3 scripts/probe_api.py [--new-routes]
    rm -f ~/.cozytouch-pass

Unauthenticated requests are enough to map the **gateway's** route table: it
answers 401 on a path it knows and 404 on one it does not. That is how the
list below was built without spending logins.

The gateway is WSO2 API Manager (`Welcome to APIM` at the root, an `apimadmin`
cookie, `/api` redirecting to a Carbon admin console). It is a proxy, so a 404
means "no API is published on this path at the gateway", not "the backend has
no such thing". Its admin plane under `/carbon/` is off limits -- that is their
infrastructure, not the device API.

The trap: the gateway's table is not the backend's. `/magellan/refs/countries`
answers 401 unauthenticated -- the gateway routes it -- and 404 with an HTML
error page once a token is attached. A 401 therefore means "the gateway
accepts this path", not "this endpoint works".

Repeated *failed logins* are the one thing here that could get an account
locked; reads are not. The integration itself polls `setupviewv2` twice a
minute, so a handful of GETs is noise inside a setup's own traffic. A refused
token is a reason to stop and check the credentials, never to retry in a loop.

## The route map

Base: `https://apis.groupe-atlantic.com`

| Route | State |
| ----- | ----- |
| `POST /users/token` | used. Basic auth with the client id in `const.py`, username prefixed `GA-PRIVATEPERSON/` |
| `GET /magellan/cozytouch/setupviewv2` | used. Everything the integration knows comes from here, and polled every 30s because of it |
| `GET /magellan/capabilities/?deviceId=` | used, after a write. A subset of the setup view, so no longer the poll |
| `POST /magellan/executions/writecapability` | used, writes |
| `GET /magellan/executions/{id}` | used, polls a write |
| `PUT /magellan/v2/setups/{id}/…` | used, away mode |
| `GET /magellan/cozytouch/setupview` | v1. Dead: 404 + HTML with a token, like refs/countries |
| `GET /magellan/devices` | works, unused, adds nothing (see below) |
| `GET /magellan/setups` | works, unused. `[{id, name}]` |
| `GET /magellan/setups/{id}` | 405, GET not allowed. The collection is all there is |
| `GET /magellan/gateways` | works, unused. `[{id, serialNumber}]` |
| `GET /magellan/zones` | works, unused. `[{id, name, zoneType, numberOfDevices}]` |
| `GET /magellan/refs/countries` | **dead.** 404 + HTML with a token. `_update_localization` has been failing silently |

Not routed at all -- 404 unauthenticated, so the gateway has never heard of
them. Roughly 90 paths were tried; these are the ones worth recording as
ruled out:

- `refs/{capabilities, capabilitydefinitions, models, products, devices,
  deviceTypes, languages, timezones, units, currencies, energies, types,
  categories, tags, labels, translations, definitions, parameters, enums,
  values}` -- `refs/` contains **only** `countries`
- `capabilities/definitions`, `metadata`, `descriptors`, `dictionary`, `i18n`,
  `models`, `catalog`, `features`, `products`, `references`
- `swagger/v1/swagger.json`, `swagger/index.html`, `openapi.json` -- no
  machine-readable spec is published

`capabilities/definitions` answers 405, which looks promising and is not:
`capabilities/123` and `capabilities/foo` answer 405 too. It is the generic
reply for any sub-path of a collection, not evidence of a route.

## There is a model catalogue, after all

Not for capabilities -- the section below still holds -- but for the *models*.
The vendor's Android app calls a namespace none of the ~90 probes reached,
because they all went under `refs/` and `capabilities/`:

| Route | What it answers |
| ----- | --------------- |
| `GET /magellan/productmodels/models/{modelId}` | 200 with `longName`, `name`, `commercialReference`, `productId`; 404 `Model Id 'N' not found.` otherwise |
| `GET /magellan/productmodels/models/{modelId}/detailederrors` | **used.** The model's whole fault table, labels included. The parameters the 400 asks for are optional; see below |

It is keyed on a *model* id rather than a device, and is not scoped to the
account asking -- a model nobody on the account owns answers the same way.
So the first column of `model.py` is checkable against the vendor's own
naming, and `Unknown product (…)` is answerable without asking a reporter for
anything.

Two things it is not. It carries no capabilities, no modes and no flags, so a
model named here still needs a dump before it can claim anything a device
*does*. And it is a courtesy, not a bulk data source: read the ids you have a
question about. Nothing here is worth turning into a crawl of somebody else's
production API.

The sweep is now complete: ids 1-2450, 1759 rows, and it ships as
`custom_components/cozytouch/model_catalogue.py` -- the name an unmapped model
arrives under, and nothing else (`docs/decisions.md`). Measured against the
branches: of the 110 mapped ids the catalogue also names, 65 carry the vendor's
name character for character, seven disagreed on a point of fact and were
changed, and the rest are the room and interface slots and the readable names
this table keeps where the catalogue has an internal reference.

### detailederrors answers the whole table, and the codes match (16/09/2026)

The 400 above names `ParentErrorCode` and `ChildErrorCode`, which reads like a
lookup taking two required parameters. It is not one: called with neither, the
route answers **every** fault row the model has -- 59 for the Naema 2 Micro 25
(modelId 56), 43 for the Alfea Extensa Duo AI UE (76). Passing parameters
changes nothing in the answer.

A row carries `parentErrorLabel`, `probableCauseErrorLabel` and
`repairInstructionsLabel`, plus a child triplet for the sub-faults of one
parent -- which is how the heat pump's outdoor-unit errors are written.

What makes it usable is that `parentProductErrorCode` is the fault-code matrix
row, packed. The row is `[system, majorCode, minorCode, level]`, the vendor's
interface displays it dotted, and the table carries the four fields one per
byte:

    40.13.0.3  ->  (40<<24)|(13<<16)|(0<<8)|3  =  671940611
    40.01.0.3  ->                                 671154179
    10.15.0.3  ->                                 168755203

Three codes on two models, all three exact. That is what the integration looks
a fault up by (`faults.py`).

Three limits, measured:

- **Air conditioners have no table.** 557 and 1758 answer 404
  `ErrorCodeNotFound`. This is boiler, heat-pump and water-heater territory,
  which is also where the `ERROR_CODE` capabilities live.
- **The language is the account's.** `Accept-Language: en-GB` returns the same
  French labels. Nothing tried so far changes it, and no non-French account
  has been seen.
- **Two code spaces coexist.** Most rows carry a small `parentProductErrorCode`
  (4 to 516) with an empty `parentIhmErrorCode` -- generator codes rather than
  interface ones, and nothing yet says which capability reports them.

## There is no capability catalogue

The *capabilities* have none, and that has not changed. A capability item
carries exactly three fields:

    {"capabilityId": 93, "modificationDate": 1786182322, "value": "1"}

No name, no type, no unit, no bounds, no enumeration labels. This holds in
both places capabilities appear -- embedded in `setupviewv2` and from
`/magellan/capabilities/`. `capability.py` stays reverse-engineered from
captures; there is nothing to fetch that would replace it.

`modificationDate` is a per-capability epoch of the last change, and it is now
read: `Hub.get_capability_modification_date` answers for one capability,
`get_last_modification_date` for the newest on a device, and the diagnostics
dump carries all of them beside the values. It costs no request -- the poll
already copies each item whole -- and it is the only thing in the payload that
distinguishes a value that is wrong from an id the hardware never feeds.

What it does *not* establish is what a normal silence looks like. Nothing says
how often a device that is working reports, so nothing here decides when one
has gone quiet; the dates are surfaced and the judgement is left to whoever
reads them. Answering that needs dumps from hardware sitting idle, which is
what putting the dates in the dump is for.

## Devices: the server names only the gateway

`setupviewv2` returns 19 fields per device. Seven drive behaviour; the six
below are carried to the diagnostics dump under the API's own names, because
what an unmapped model gets mapped from is what the vendor says about it. The
values are from the one account probed:

| Field | Gateway (1758) | Room AC (557-559) | Thermal zone (1505-1507) |
| ----- | -------------- | ----------------- | ------------------------ |
| `customName` | what the user typed | `"ROOM_0…2"` | `"THZONE_0…2"` |
| `longName` | `"HUB Navizone"` | `"ROOM_0…2"` | `"---"` |
| `modelFamily` | `"Air_Conditioning"` | `null` | `null` |
| `productRange` | `null` | `null` | `null` |
| `masterDeviceId` | `null` | gateway's id | gateway's id |
| `isAvailable` | `true` | `true` | `true` |

`longName` on the gateway is exactly the string `MODELS` hardcodes for 1758.
On the children it is an internal name or a literal `"---"` placeholder, so it
is **not** a substitute for the model table -- least of all for the devices
that need one, the unmapped ones. `customName` is the one name a reporter
recognises -- it is the name typed in the vendor app -- though on this account
only the gateway's was ever renamed; the room name people actually see lives
in capability 154.

`masterDeviceId` is the real find: server-declared parent/child topology, so
the gateway a device hangs off is reported rather than guessed. `get_via_device`
reads it to draw the link in the device registry, and returns nothing when the
gateway has not been added -- naming a device Home Assistant does not have earns
a warning from the registry.

`/magellan/devices` returns a flat list whose fields are a strict subset of the
same device block. It adds nothing.

## The setup view has no second data plane

Its top-level keys are `absence`, `address`, `area`, `currency`, `devices`,
`gateways`, `id`, `mainDHWEnergy`, `mainHeatingEnergy`, `name`,
`numberOfPersons`, `numberOfRooms`, `rateLimit`, `setupBuildingDate`, `type`,
`zones`. That is the whole payload. There is no `programs`, `schedules` or
`consumptions` hiding a second source of data, and the `/magellan/` collection
routes above are all subsets of what is here. The functional data plane is
this one response.

`rateLimit` is new to us: 30 on this account, the server declaring its own
limit. The units are still unknown -- nothing decodes them, and no capture has
ever produced a 429 that would. It is carried into the dump, and read as
requests per minute in one place only: as a *ceiling* on the poll interval
(`poll_interval` in `hub.py`). Per-minute is the strictest reading that a
60-second-per-device poll working for years does not already disprove, and a
ceiling wants the strictest. At 30 it never bites.

The thing that would settle it is a real 429. `_note_rate_limited` logs every
`X-RateLimit-*` header it sees at warning level for exactly that reason: the
first person to be throttled is holding the only evidence there is.

Worth recording that the poll now reads this route rather than
`/magellan/capabilities/`. The device blocks embed a capability list each, so
one request answers for the whole account where the per-device route answers
for one -- which is what let the interval halve while the request count fell.
What is **not** established is that the two are equally *fresh*: this session
compared their shape, never their latency, and a setup view served from an
aggregated cache would look identical while lagging.
`scripts/probe_api.py --cadence` compares `modificationDate` between them,
which is the measurement nobody has made.

`type`, `mainHeatingEnergy`, `mainDHWEnergy`, `setupBuildingDate` and a zone's
`zoneType` are all integer enums with no catalogue to decode them: the same
guessing problem as capability ids, one level up.

### What this covers, and what it does not

One account: one Navizone gateway, three room air conditioners, three thermal
zones. The `Air_Conditioning` family only. Nothing here says whether a boiler
or a water heater populates `modelFamily` and `longName` on the device itself
rather than only on its gateway -- which is exactly why this PR puts those
fields in the diagnostics dump instead of wiring them into `model.py`. Let the
reports answer it.

## The four routes the app calls and nobody had tried (12/09/2026)

The 26 magellan paths in the decompiled Dart are the whole of what the vendor
app calls. Four of them had never been probed, and `probe_api.py --devices`
now does, against the real account. Three are dead; the fourth is the first
route here to answer with a field `setupviewv2` does not have.

| Route | Result |
| ----- | ------ |
| `GET /magellan/devices/{id}/details` | 200 on every device, a **strict subset** of the setup view's device block. The same dead end the collection was. |
| `GET /magellan/devices?{filter}` | 200. Filters are `gatewayid`, `productid`, `zoneid`, `unattacheddevices`, `isremotemaintainable`. Fields are poorer still. No product description behind `productid`. |
| `GET /magellan/gateways/ota-check-version` | **403** `API Subscription validation failed`. Our client id is not entitled to it. |
| `GET /magellan/v3/gateways/{gatewayId}/compatible-rooms` | **200**, see below. |

`gatewayid` takes the id from the setup view's top-level `gateways` array, not
the gateway device's `deviceId`. Passing the latter answers `200` with an empty
list on the filter and `404 No Gateway id '…' found for user id '…'` on the v3
route -- a silence that reads exactly like "this route is empty".

### compatible-rooms, and the 400 as a schema oracle

`Where to look next` used to suggest that an out-of-range write might name its
bounds in the rejection. It does, and it does not need a write: this route
answers 400 **naming the parameter it wanted**, so it can be walked with GETs
until it stops complaining. What that yielded:

- `protocol` accepts **`ZIGBEE`** and **`IO`**, refuses `RADIO`, `WIFI`, `BLE`.
  A rejected value answers `The value 'X' is not valid`, an accepted one moves
  the complaint to the next parameter. `IO` is the Overkiz protocol name, on a
  gateway whose account cannot open an Overkiz session at all.
- `deviceType` is an **integer enum of exactly twelve values**: 0-11 pass
  validation, 12 and up answer `The value '12' is invalid`. Every string was
  refused, the vendor's own `ProductMainFamily` names included.

The payload is the gateway's room slots:

    [{"id": 0, "name": "Chambre parentale", "type": 1, "compatible": true},
     {"id": 1, "name": "Bureau Julie",      "type": 1, "compatible": true},
     {"id": 2, "name": "Chambre enfant",    "type": 1, "compatible": true}]

Three slots on a gateway with three room units, ids counting from 0 like the
`ROOM_n` names do, and named after the rooms rather than `ROOM_0`. `compatible`
is **true only for `deviceType=2`**, on both protocols, and identical across
the three rooms -- so it is a property of the gateway and the device type, not
of the slot. On an `Air_Conditioning` gateway, device type 2 is what fits.

What this does not do is answer gduteil/cozytouch#172. The flag describes what
a gateway would accept, not what a slot currently holds, and reading it for
somebody else's CozyBox would need their credentials. The gateway rule in
`model.py` stands, now with one more reason: even the route that knows about
device types only answers per gateway.

`deviceType`'s twelve values, and `type: 1` on a room, are two more integer
enums with no catalogue -- the same problem as capability ids, one level up.

### The setup view's `gateways` array is not read

Unrelated to the above and worth its own look: `setupviewv2` carries a
top-level `gateways` array of `{id, isAlive, serialNumber, setupId, type}`, and
nothing in the integration touches it. `isAlive` is a server-side liveness flag
on the one device that actually has a radio, which is what capability 218 was
mistaken for and could not deliver.

## The Overkiz plane is reachable, and empty for us (12/09/2026)

Atlantic runs several protocols, and `pyoverkiz` reaches "Atlantic Cozytouch"
on a host this document had never probed: every route above lives on
`apis.groupe-atlantic.com/magellan`, and pyoverkiz talks to
`ha110-1.overkiz.com/enduser-mobile-web/enduserAPI/`. The credential is the
same one -- our `COZYTOUCH_CLIENT_ID` is byte-identical to pyoverkiz's -- so
the open question was whether our devices also appear over there, described by
the `widget` / `uiClass` / `controllableName` vocabulary that makes the Overkiz
integration need no model table at all.

Measured on the real account (`research/probe_overkiz_plane.py`, one Navizone
gateway, three room units, three thermal zones):

| Step | Route | Result |
| ---- | ----- | ------ |
| 1 | `POST apis.groupe-atlantic.com/users/token` | 200, as always |
| 2 | `GET apis.groupe-atlantic.com/magellan/accounts/jwt` | **200** — a real 3-segment JWT, 581 chars |
| 3 | `POST ha110-1.overkiz.com/…/enduserAPI/login` (`jwt=`) | **401** |
| 3 | `POST ha111-1.overkiz.com/…/enduserAPI/login` (`jwt=`) | **401** |
| 3 | `POST std14-1.overkiz.com/…/enduserAPI/login` (`jwt=`) | **401** |

So step 2 is a genuine addition to the route map -- a magellan route nobody
had tried, and it mints an Overkiz JWT on demand. But step 3 refuses it on
**every Overkiz host the app itself names**, so step 4 (`enduserAPI/setup`)
was never reached.

What that settles: **the two planes do not overlap for this hardware.** A
Navizone gateway and its room units are magellan-only, there is no
self-describing `widget` / `uiClass` mirror to fall back on, and `model.py`
stays the source of truth rather than becoming an override layer.

What it does not settle: whether a *different* Atlantic product -- one sold
with a TaHoma-style box -- puts the same account on both planes, and what the
JWT of step 2 is actually for, since something mints it. Neither is worth a
further probe until somebody reports hardware that appears in both
integrations at once.

Two things checked before calling the 401 genuine, since the first two runs
failed on this script being wrong rather than the server:

- **The host is not the problem, and it took two passes to establish.** The
  `haNNN-1` number is a shard, and for some brands it encodes a region (Somfy
  Europe/America/Oceania are ha101-1 / ha401-1 / ha201-1). pyoverkiz points
  Atlantic, Sauter *and* Thermor at ha110-1 and knows no other -- but the app
  knows two more: `strings` on the Cozytouch executable yields `ha110-1`,
  `ha111-1` and `std14-1`. All three were tried; all three answer 401. The
  first write-up of this section concluded from ha110-1 alone that no other
  host existed, which was wrong and is why the other two are named here.
- **The login request is not missing anything.** pyoverkiz's `_post_login` is a
  bare form POST to `{endpoint}login` carrying the single field `jwt`, with no
  added header. That is byte for byte what was sent.

Cost of the run, for the record: three login attempts, two of them wasted on
this script's own bugs (pyoverkiz's `/token` where ours is `/users/token`, and
a missing `scope=openid`). Match `account.py` exactly before pointing anything
at a real account -- repeated failed logins are the one thing that locks one.

## A second client hit the same wall (NicolasYDDER/homey-cozytouch)

A Homey app for Cozytouch, JavaScript, dual-plane: Overkiz devices detected by
`controllableName` / `widget` exactly as `pyoverkiz` does, and Magellan devices
by a hand-maintained table of numeric capability ids. Independent confirmation
that the split is real and that nothing self-describing exists on our side.

It credits `gduteil/cozytouch` -- the upstream, not this fork -- and correctly:
the entry it cross-references is modelId 390, which upstream's `model.py` has
had all along. Nothing that originated here is in it.

Two things it knows that this document did not.

**The vendor validates capabilities per product, and says so on a write.** Two
error shapes, quoted from its source:

    {"code":36002008,"type":"NoCapabilityImplementationFound",
     "message":"There is no implementation for capability Id 2 on product Id 7."}
    {"code":36002005,"type":"UnknownCapabilityId",
     "message":"Capability Id '10' not found."}

So the server holds a per-`productId` registry of which capabilities exist, and
distinguishes "no such capability anywhere" from "not on this product". That is
the catalogue this document says does not exist -- reachable only as a
rejection, and only through `writecapability`, which is a write. Worth knowing,
not worth firing blind.

**Capability ids are per product, not per model family.** Its water-heater
table is overridden for `productId` 7 alone, where none of the usual ids exist
and the setpoint sits at 105301/105304. Same lesson as 557-561 from the other
end: `productId` and `modelId` index different things, and neither is the
product.

Treat its Magellan tables as leads rather than evidence. The towel-rack block
matches ours id for id; its heater, climate and water-heater blocks use a low
id space (1, 2, 3, 4, 8, 9) that no capture in `research/capability-corpus` has
ever shown, with no dump cited -- its climate table reads capability 7 as the
current temperature where every capture here has it as the HVAC mode.

## What the rest of the internet has (12/09/2026)

A sweep of GitHub code search, the forums and the blogs. The ecosystem splits
cleanly in two, and almost everybody is on the other side:

| Plane | Clients |
| ----- | ------- |
| Overkiz (`haNNN-1.overkiz.com`, JWT via `magellan/accounts/jwt`) | `iMicknl/python-overkiz-api`, `dubocr/overkiz-client`, `pzim-devdata/tahoma`, `phimage/swift-overkiz-api`, `jbilcke-hf/flutter_overkiz`, `oznetmaster/OverkizClient`, `MaGOs92/cozy-airbnb`, `niavok/cozytouch_peak_hours` |
| Magellan (`apis.groupe-atlantic.com/magellan`) | `gduteil/cozytouch`, this fork, `NicolasYDDER/homey-cozytouch`, `Vntoni/HomeHub` |

Four magellan clients exist in the world, and two of them are this project.

### A second client credential exists

`Vntoni/HomeHub` authenticates against the same `/users/token`, same
`GA-PRIVATEPERSON/` prefix, same `scope=openid` -- with a **different client
id and secret**, passed as a plain Basic pair rather than the pre-encoded blob
everyone else copies:

    shared Overkiz  Ct_1JVyTmILX8IefA7aUNBjFnZUa   (ours, and every client above)
    HomeHub         e8D1nA3hvv1tnc1MpoA7G5uD46Aa

This is worth following up on for one specific reason. `ota-check-version`
answers `403 {"code":"900908", "description":"API Subscription validation
failed."}` -- a WSO2 API-gateway message meaning *this client id is not
subscribed to that API*, not that the route does not exist or that the account
lacks rights. A different client id can carry different subscriptions, so some
of what is ruled out above may be ruled out only for our credential.

It also sends headers nothing here does: `User-Agent: cozytouch-ios-v3.25.0`,
plus `appInstallNumber` and `uniqId`. Untested whether any route gates on them.

### Its capability readings are wrong, and the app says so

Useful as a warning about sniffed tables. `HomeHub` documents its ids as "found
by sniffing", and three contradict this project's:

| Id | HomeHub says | `id_to_name.json` (Atlantic's own name) | Corpus values |
| -- | ------------ | --------------------------------------- | ------------- |
| 73 | power state | `availableThermostatMode` | only 4 and 2 |
| 152 | window detection | `homeAwayModeState` | 0, rarely 1/2 |
| 153 | absence mode | `heatCoolOnGoing` | always 0 |

The names come from the vendor's own enum, recovered from the app binary, so
this is not a difference of opinion. A table built from watching one household
reproduces whatever that household happened to do.

### Rooting the hardware (Lafois, 2020)

`lafois.com`'s five-part series roots a Cozytouch box (a Kizbox Mini): LuaJIT
over DBus, a lighttpd REST API shipped disabled whose auth check can be patched
out in Lua bytecode, serving `/enduser-mobile-web/1/enduserAPI/setup/devices`.
That is the Overkiz local plane on Overkiz hardware. It says nothing about a
Navizone or a CozyBox, which are not that box, and it needs physical access.

## Where to look next

- **The mobile app, not the API.** A `refs/` namespace holding only `countries`
  suggests the capability catalogue -- names, units, bounds, enum labels --
  ships inside the Cozytouch app. Its resources and translation strings are
  the place to look, and would be a far bigger prize than any endpoint here.
- **Other product families.** Once a boiler or water-heater dump arrives with
  the fields this PR added, the table above can be finished.
- **An account that lives on both planes.** The Overkiz probe above returned
  401 for this household; a reporter whose hardware shows up in the `overkiz`
  integration *and* in this one would be the case that reopens it.
- **Error messages as a schema leak.** Confirmed, and it needs no write:
  `compatible-rooms` answers 400 naming the parameter it wanted and whether the
  value was valid, which is how `protocol` and `deviceType` were mapped above.
  Any route taking parameters can be walked the same way. A `writecapability`
  with an out-of-range value may name its bounds too -- that one *is* a write,
  so only against a device you own, and only one at a time.
- **The twelve device types.** `compatible-rooms` proves the enum exists and
  that 2 is what an `Air_Conditioning` gateway takes. What the other eleven
  mean is unknown, and a gateway of another family would say more.
