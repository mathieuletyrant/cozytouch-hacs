# 🏠 Atlantic Cozytouch

A Home Assistant integration for Atlantic's Cozytouch cloud -- boilers, heat
pumps, water heaters, towel rails and air conditioners.

Atlantic runs several protocols behind the Cozytouch brand. This one talks to
the API the Cozytouch mobile app uses, which is not the one the official
`overkiz` integration covers -- so it fills the gap for the hardware Overkiz
does not see.

## 📬 Contact

For anything about a device -- unmapped model, wrong entity, a value that reads
nothing like the app -- open an [issue](https://github.com/mathieuletyrant/cozytouch-hacs/issues)
and attach the diagnostics dump. A report without the dump cannot be acted on,
and an issue keeps the answer where the next person with that model will find
it.

For anything else -- something you would rather not post in public, or a
question that is not about the code -- <midtown_saucers9e@icloud.com>.

## ✨ What it does

You get the climate entity you would expect : temperature, mode, and fan and
swing where the hardware has them, with the room temperature read back. On top
of that :

- the weekly program the device runs on its own, read and written from Home
  Assistant, and shown as a calendar
- sensors per device for energy, water, wifi signal and decoded error codes
- device triggers for schedule changes and program overrides, on top of the ones
  Home Assistant builds itself
- a diagnostics dump that an unmapped device points you at by itself

Everything runs over the cloud : one login, one poll for the whole account,
every 30 seconds by default.

## 📋 Supported devices

Every Cozytouch device is identified by a numeric `modelId`, and each one needs
its own mapping before its capabilities turn into Home Assistant entities. The
tables below are the whole of what is mapped today.

Most of these mappings were built from a single user's capture of their own
unit. They say what that device reported -- not that every feature has been
exercised on every variant. The *names* are cross-checked against Atlantic's
own model catalogue where the id has been read back from it.

**Some ids are slots, not products.** A gateway reports each room it drives
under its own `modelId`, counting from the first : the vendor's catalogue calls
them `ROOM_0`, `ROOM_1`, … and `UI_0`, `UI_1`, … An id in one of those ranges
says *which room*, never what the hardware in it is -- so the same `modelId`
is an air conditioner on one account and a radiator on another, and what tells
them apart is the gateway it hangs off. Adding the gateway is what brings its
rooms in.

### 🔥 Boilers / Chaudières

| modelId | Model |
| ------: | ----- |
| 1-12 | Naema / Naia (12, 20, Micro 25-35, Duo 30-35) |
| 54-69 | Naema 2 / Naia 2 (12, 20, Micro 25-35, Duo 25-35 HE) |
| 253-254, 256-261, 265-267, 269-270 | Naema / Naia variants (Sr, SP, Cuerpo Caldera) |
| 1444 | Naema 3 Micro 25 |
| 1447 | Naema 3 Duo 25 |

### ♨️ Heat pumps / Pompes à chaleur

| modelId | Model |
| ------: | ----- |
| 76 | Alfea Extensa Duo AI UE |
| 211 | Alfea Extensa Duo A.I. 3 R32 |

### 🎛️ Thermostats

| modelId | Model |
| ------: | ----- |
| 235 | Thermostat Navilink Connect |
| 418 | Atlantic Loria Duo 6006 |

### 🚿 Water heaters / Chauffe-eau

| modelId | Model |
| ------: | ----- |
| 236 | Sauter Phazy |
| 386 | PHAZY VS 300L 3000M |
| 387 | PHAZY VM 150L 2200M |
| 388 | PHAZY VM 200L 2200M |
| 389 | AQUEO ACI HYB VS 300L 3000M |
| 390 | AQUEO ACI HYB VM 150L 2200M |
| 391 | AQUEO ACI HYB VM 200L 2200M |
| 392 | DURALIS CONNECT ACI HYB VS 300L 3000M |
| 393 | DURALIS CONNECT ACI HYB VM 150L 2200M |
| 394 | DURALIS CONNECT ACI HYB VM 200L 2200M |
| 1368 | Calypso SPLIT VM 200L |
| 1369, 1376 | Calypso Split |
| 1371, 1372 | Aeromax SPLIT 3 |
| 1641 | Atlantic Explorer V5 (200L) |
| 1642 | Atlantic Explorer V5 (270L) |
| 1644 | Atlantic Explorer V5 (240L) |
| 1645 | Atlantic Explorer V5 (270L with coil) |
| 1656 | Aeromax 6 |
| 1669 | CV5 Aeromax Premium 100L |
| 1657 | Calypso 200L |
| 1658 | Calypso connecté |
| 1957 | LINEO CONNECTE MP 100L 2250W |
| 1962 | Thermor Malicio 3 65L |
| 1966 | Thermor Malicio 3 120L |
| 2346 | Egeo VS 250L |
| 2374 | Explorer EVO 3 (260L) |

### 🧖 Towel racks / Sèche-serviettes

| modelId | Model |
| ------: | ----- |
| 1381 | KELUD 1750W BLC |
| 1382 | KELUD 1750W Anthracite Standard |
| 1388, 1588 | Doris étroit 1500W BLC |
| 1543 | Asama Connecté II Ventilo 1750W Blanc |
| 1546 | Asama Connecté II Ventilo 1500W ANTH |
| 1547 | Asama Connecté II Ventilo 1750W ANTH |
| 1551 | Asama Connecté II Ventilo 1750W Noir |
| 1595 | Doris étroit 1300W CARAT |
| 1622 | Thermor Riva 5 |

### 🏠 Room slots / Emplacements de pièce

These are the slot ranges, and what the gateway makes of them. `ROOM_0` to
`ROOM_8` share one numbering split across two id blocks -- 557-561 for the
first five rooms, 1734-1737 for the next four.

| modelId | Slot | Behind | Mapped as |
| ------: | ---- | ------ | --------- |
| 557-561 | `ROOM_0`-`ROOM_4` | a CozyBox (2447) | Radiator |
| 557-561 | `ROOM_0`-`ROOM_4` | a Naviclim (556) or Navizone (1681, 1758) | Air conditioner |
| 1734-1737 | `ROOM_5`-`ROOM_8` | a HUB Cozytouch (1457) | Air conditioner |
| 562-570 | `UI_0`-`UI_8` | any of the above | Air conditioner user interface |

A room slot behind a gateway this table does not know falls through to the air
conditioner mapping, which is what the first five ids were read as before the
radiators turned up. If yours is a radiator and arrives as an air conditioner,
that is the bug -- send the diagnostics dump and say which gateway it sits on.

### 📡 Gateways / Passerelles

| modelId | Model |
| ------: | ----- |
| 556 | Naviclim Hub |
| 1353 | Calypso Split Interface |
| 1457 | HUB Cozytouch |
| 1681 | HUB Navizone |
| 1758 | HUB Navizone |
| 1763 | FLAT/S4 IOTHUB |
| 2447 | Hub IO Sauter (CozyBox) |

### ❓ My device is not listed

It will show up as `Unknown product (…)`, and only its generic capabilities will
work. Home Assistant says so on its own : an unmapped device raises a repair
under `Settings -> System -> Repairs`. Opening it hands you a link to an issue
already carrying every unmapped model on the account, with the capability ids
nothing names for each and nothing else about your home -- so a gateway with
three unknown zones is one issue, not four. Attach the dump below to it -- one
per unmapped device, since a dump carries the capability values of the device
it came from and identity only for the rest -- and answering that one dialog
stops the others asking too. A release that adds a mapping clears them either
way.

To do it by hand instead, open an [issue](https://github.com/mathieuletyrant/cozytouch-hacs/issues)
and attach a diagnostics dump :

`Settings -> Devices & Services -> Atlantic Cozytouch -> ⋮ -> Download diagnostics`

One file covers the whole account. It lists every device the API reports with
its model id, says which ones the mapping already knows, and for each of them
which capability ids nothing names yet -- including the devices you have not
added, which is usually where an unmapped model is. That last list is what a
mapping is built from. Your credentials and address are stripped out before
the file is written.

If you want to see the unmapped capabilities as entities in the meantime, tick
`Create entities for unknown capabilities` when adding the account, under
Configuration below. It is useful for working out what a value means, and noisy
enough that you will want it off again afterwards.

## 📦 Installation

### With HACS

This integration is not in the HACS default store, so add it as a custom
repository first :

[![Add HACS repository.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mathieuletyrant&repository=cozytouch-hacs&category=integration)

Or by hand, in HACS : `⋮ -> Custom repositories`, URL
`https://github.com/mathieuletyrant/cozytouch-hacs`, type `Integration`. More
about HACS [here](https://hacs.xyz/).

### Manually

Clone this repository, copy `custom_components/cozytouch` into your Home
Assistant config directory (so `config/custom_components/cozytouch`), and
restart Home Assistant.

## ⚙️ Configuration

Go to `Settings -> Devices & Services -> Add an integration`, search for
`cozytouch`, pick `Atlantic Cozytouch` and enter your Cozytouch credentials.

If the connection works, you get the list of devices on your account : the
gateway and each unit it reports. Tick the ones you want entities for. You get
one entry for the account, with one device per device you picked, so the
credentials are sent once and the account is polled once whatever you own.

To add a device later, use `Add device` on the integration page. To stop
following one, delete it from there.

Values refresh every 30 seconds by default. One request covers the whole
account, so ticking more devices does not make the integration talk to Atlantic
more often. You can change the interval under `Configure` on the integration
page; 15 seconds is the lowest it accepts, and below that the requests stop
buying anything -- Atlantic's cloud hears from your hardware on its own
schedule, whatever we ask it.

Only some values are mapped so far. `Create entities for unknown capabilities`
turns every capability the API reports into an entity, mapped or not, which is
how a mapping gets worked out. It applies to the whole account.

> Upgrading from an earlier release : the integration used to be set up
> one entry per device, and there is no automatic migration -- Home Assistant
> will say the entry cannot be migrated. Remove the integration and add it
> again. The devices and their entities are recreated under the account, which
> means new entity ids, so a dashboard or an automation naming them has to be
> pointed at the new ones.

## 🗓️ Scheduling

Two actions write and read the weekly program the device holds itself, the one
the Cozytouch app calls *Chauffage* and *Refroidissement*. It keeps running when
Home Assistant is off, which is the difference with scheduling the climate
entity from an automation.

`Cozytouch: Set a day program` writes one day program to as many days as you
pick. Days can be named one by one or through `Every day`, `Weekdays` and
`Weekend`. The first slot has to start at `00:00` -- the device has no target
temperature for the hours before the first one -- and a day holds ten slots at
most, fewer if the device says so.

`Cozytouch: Read a week's program` returns the seven days of a program in the
shape the other action takes, so a program can be read, edited and written
back rather than retyped :

```yaml
- action: cozytouch.get_schedule
  target:
    entity_id: climate.salon
  data:
    program: heating
  response_variable: schedule

- action: cozytouch.set_schedule
  target:
    entity_id: climate.salon
  data:
    program: heating
    days: [weekend]
    slots: "{{ schedule['climate.salon'].days.monday }}"
```

On Home Assistant older than 2025.7 the slots field is still a YAML editor
rather than a list of time and temperature pickers : the schema'd form is not
something those frontends can draw. Everything else works the same.

Temperatures are whole degrees. Every program captured from a real device holds
integers, so a half degree has never been confirmed to survive the write.

### Triggering on the program

Five device triggers, offered per device and only when the device reports what
they read. Pick them in the automation editor under *Add trigger > Device*, or
write them out :

| Trigger | Fires when |
| ------- | ---------- |
| `The heating program changed` | any of the seven heating days was rewritten, whether from here, from the Cozytouch app or from the panel |
| `The cooling program changed` | the same, for the cooling block |
| `… went back to its program` | the device resumed following its weekly program |
| `… program was overridden` | a temporary setpoint took over -- which is what setting a temperature while in `prog` does |
| `… stopped following its program` | the program was switched off for a manual setpoint |

The three preset triggers take an optional `for`, so *overridden for two hours*
is a trigger rather than an automation with a timer in it.

```yaml
triggers:
  - trigger: device
    domain: cozytouch
    device_id: 8dd8b7f4c3a24b1e9e0e4a6d5c7b2f10
    type: heating_schedule_changed
```

Everything else worth automating on is already a device trigger Home Assistant
builds itself : *connected* and *disconnected* from the Cozytouch connectivity
sensor, *turned on* from the away-mode switch, *HVAC mode changed* from the
climate entity. Conditions and actions about presets come from the `climate`
domain the same way.

### Seeing the program

A device that holds a program also gets a calendar entity for it -- *Heating
Program*, *Cooling Program*, *Hot Water Program*, whichever of the three it
reports -- so the week can be looked at on a dashboard instead of read off
seven sensors. Each slot is an event running until the next one takes over, and
its title is the target temperature.

The seven per-day sensors of a block the calendar shows are disabled by
default, on existing installations too : fourteen near-identical diagnostic
rows per air conditioner said the same thing worse. Nothing is removed -- a
dashboard or template that reads one can have it back from the device page,
under the disabled entities, and it stays enabled from then on.

They are read-only : a calendar event has a start and an end, a program slot
has only a start, so writing one back would mean deciding what happens to the
slots after it. `Cozytouch: Set a day program` is where that decision is
spelled out.

What they are good for besides looking at them is the `calendar` triggers,
since an event starting *is* the program moving to its next setpoint :

```yaml
triggers:
  - trigger: calendar
    entity_id: calendar.salon_heating_program
    event: start
```

The hot-water program is shown but cannot be written : `Cozytouch: Set a day
program` covers heating and cooling only, because what the second value of a
hot-water slot means has never been confirmed on a real device. Reading it back
is what the hot-water prog sensors have always done.

The times are read in Home Assistant's own timezone. The device stores minutes
past midnight and nothing in the API says which clock those belong to, so a hub
in a different timezone from the house it heats would show the program shifted.

## 🏷️ Versioning

Releases use CalVer : `YEAR.MONTH.PATCH` (ex : `2026.8.0`).

`main` is protected, so a release is two steps. First a pull request setting
`version` in `custom_components/cozytouch/manifest.json` to the version being
released ; then a `Release` workflow dispatch naming that same version. The
workflow refuses to run while the manifest says something else, and otherwise
tags the commit and writes the notes from the commit subjects since the
previous tag.

## 🙏 Credits

This integration started as a fork of [gduteil/cozytouch](https://github.com/gduteil/cozytouch)
and is now maintained independently here. All the original work is theirs.

Several device mappings come from pull requests opened against that project by
people who owned the hardware and worked out what it reported. Their work is
here because they did it :

| Device | modelId | By |
| ------ | ------: | -- |
| ACI HYB water heaters (PHAZY / AQUEO / DURALIS) | 386-394 | [@FreeTHX](https://github.com/FreeTHX), [@beorn-](https://github.com/beorn-) |
| Doris étroit 1300W CARAT | 1595 | [@tomcastleman](https://github.com/tomcastleman) |
| Doris étroit 1500W BLC | 1588 | [@jojeju9428](https://github.com/jojeju9428) |
| Calypso connecté | 1658 | [@picosam](https://github.com/picosam) |
| FLAT/S4 IOTHUB gateway | 1763 | [@Joonel](https://github.com/Joonel) |
| Thermor Malicio 3 65L | 1962 | [@genmllc](https://github.com/genmllc) |
| Egeo VS 250L | 2346 | [@Mathieu-Pasco-Breillot](https://github.com/Mathieu-Pasco-Breillot) |
| Explorer EVO 3 (260L) | 2374 | [@StefanWokusch](https://github.com/StefanWokusch) |
| Calypso SPLIT VM 200L | 1368 | [@mplessis](https://github.com/mplessis) |
| CV5 Aeromax Premium 100L | 1669 | [@Racailloux](https://github.com/Racailloux) |

Where only part of a pull request was taken, the commit that took it says which
part and why the rest was left alone.
