# What the Cozytouch API exposes

A record of a probing session run on 2026-08-20, kept so the next person
asking "can we stop guessing?" starts from what was already ruled out rather
than repeating it.

The short answer to that question is **no for capabilities, partly for
devices**. Details below.

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
locked; reads are not. The integration itself polls `/magellan/capabilities`
every 60 seconds per device, so a handful of GETs is noise inside a setup's own
traffic. A refused token is a reason to stop and check the credentials, never
to retry in a loop.

## The route map

Base: `https://apis.groupe-atlantic.com`

| Route | State |
| ----- | ----- |
| `POST /users/token` | used. Basic auth with the client id in `const.py`, username prefixed `GA-PRIVATEPERSON/` |
| `GET /magellan/cozytouch/setupviewv2` | used. Everything the integration knows comes from here |
| `GET /magellan/capabilities/?deviceId=` | used. Polled every 60s |
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

## There is no capability catalogue

A capability item carries exactly three fields:

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

`setupviewv2` returns 19 fields per device and the integration copies 7. The
interesting ones it drops, with the values from the one account probed:

| Field | Gateway (1758) | Room AC (557-559) | Thermal zone (1505-1507) |
| ----- | -------------- | ----------------- | ------------------------ |
| `longName` | `"HUB Navizone"` | `"ROOM_0…2"` | `"---"` |
| `modelFamily` | `"Air_Conditioning"` | `null` | `null` |
| `productRange` | `null` | `null` | `null` |
| `masterDeviceId` | `null` | gateway's id | gateway's id |
| `isAvailable` | `true` | `true` | `true` |

`longName` on the gateway is exactly the string `MODELS` hardcodes for 1758.
On the children it is an internal name or a literal `"---"` placeholder, so it
is **not** a substitute for the model table -- least of all for the devices
that need one, the unmapped ones.

`masterDeviceId` is the real find: server-declared parent/child topology, which
nothing in the integration reads.

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
limit. The units are unknown -- nothing decodes them -- but the integration
polls every 60s per device and is under it on any reading. It is now carried
into the dump.

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

## Where to look next

- **The mobile app, not the API.** A `refs/` namespace holding only `countries`
  suggests the capability catalogue -- names, units, bounds, enum labels --
  ships inside the Cozytouch app. Its resources and translation strings are
  the place to look, and would be a far bigger prize than any endpoint here.
- **Other product families.** Once a boiler or water-heater dump arrives with
  the fields this PR added, the table above can be finished.
- **Error messages as a schema leak.** A `writecapability` with an
  out-of-range value may name the accepted bounds in its rejection. That is a
  write, so only against a device you own, and only one at a time.
