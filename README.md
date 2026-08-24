# Cozytouch
This is an Atlantic Cozytouch cloud integration. Atlantic use multiple protocols, in my case the protocol is different than the one implemented by official integration (overkiz).

## Supported devices

Every Cozytouch device is identified by a numeric `modelId`, and each one needs
its own mapping before its capabilities turn into Home Assistant entities. The
tables below are the whole of what is mapped today.

Most of these mappings were built from a single user's capture of their own
unit. They say what that device reported — not that every feature has been
exercised on every variant.

### Boilers / Chaudières

| modelId | Model |
| ------: | ----- |
| 56 | Naema 2 Micro 25 |
| 61 | Naia 2 Micro 25 |
| 65 | Naema 2 Duo 25 |
| 1444 | Naema 3 Micro 25 |

### Heat pumps / Pompes à chaleur

| modelId | Model |
| ------: | ----- |
| 76 | Alfea Extensa Duo AI UE |
| 211 | Alfea Extensa Duo A.I. 3 R32 |

### Thermostats

| modelId | Model |
| ------: | ----- |
| 235 | Thermostat Navilink Connect |
| 418 | Atlantic Loria Duo 6006 |

### Water heaters / Chauffe-eau

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
| 1369, 1376 | Calypso Split |
| 1371, 1372 | Aeromax SPLIT 3 |
| 1641 | Atlantic Explorer V5 (200L) |
| 1642 | Atlantic Explorer V5 (270L) |
| 1644 | Atlantic Explorer V5 (240L) |
| 1645 | Atlantic Explorer V5 (270L with coil) |
| 1656 | Aeromax 6 |
| 1657 | Calypso 200L |
| 1658 | Calypso connecté |
| 1957 | LINEO CONNECTE MP 100L 2250W |
| 1962 | Thermor Malicio 3 65L |
| 1966 | Thermor Malicio 3 120L |
| 2346 | Egeo VS 250L |
| 2374 | Explorer EVO 3 (260L) |

### Towel racks / Sèche-serviettes

| modelId | Model |
| ------: | ----- |
| 1381 | KELUD 1750W BLC |
| 1382 | KELUD 1750W Anthracite Standard |
| 1388 | Doris étroit 1500W BLC |
| 1543 | Asama Connecté II Ventilo 1750W Blanc |
| 1546 | Asama Connecté II Ventilo 1500W ANTH |
| 1547 | Asama Connecté II Ventilo 1750W ANTH |
| 1551 | Asama Connecté II Ventilo 1750W Noir |
| 1595 | Doris étroit 1300W CARAT |
| 1622 | Thermor Riva 5 |

### Air conditioning / Climatisation

Room units do not talk to the cloud themselves : they sit behind a gateway,
which reports each of them under its own `modelId`. Adding the gateway is what
brings the rooms in.

| modelId | Model |
| ------: | ----- |
| 557-561, 1734 | Air conditioner (room unit) |
| 562-570 | Air conditioner user interface |

### Gateways / Passerelles

| modelId | Model |
| ------: | ----- |
| 556 | Naviclim Hub |
| 1353 | Calypso Split Interface |
| 1457 | HUB Cozytouch |
| 1758 | HUB Navizone |
| 1763 | FLAT/S4 IOTHUB |

### Confirmed on real hardware

These are the devices the mappings were originally written against, and that are
known to work end to end :

  - `Atlantic Naema 2 Micro 25` gas boiler, through a `Navilink Radio-Connect 128` thermostat
  - `Atlantic Naema 2 Duo 25` gas boiler, through a `Navilink Radio-Connect 128` thermostat
  - `Atlantic Naia 2 Micro 25` gas boiler, through a `Navilink Radio-Connect 128` thermostat
  - `Atlantic Loria Duo 6006 R32` heat pump, through a `Navilink Radio-Connect 128` thermostat
  - `Takao M3` air conditioning
  - `HUB Navizone` air conditioning gateway driving room units
  - `Kelud 1750W` towel rack
  - `Sauter Asama Connecté II Ventilo 1750W` towel rack

### My device is not listed

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

The file lists every device on the account with its model id, says which ones
the mapping already knows, and for the device this entry drives, which capability
ids nothing names yet. That last list is what a mapping is built from. Your
credentials and address are stripped out before the file is written.

If you want to see the unmapped capabilities as entities in the meantime, tick
`Create entities for unknown capabilities` when adding the device (see
[Configuration](#configuration)). It is useful for working out what a value
means, and noisy enough that you will want it off again afterwards.

## Installation

You can install it using HACS or manually.

#### With HACS

This integration is not in the HACS default store, so add it as a custom repository first:

[![Add HACS repository.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mathieuletyrant&repository=cozytouch-hacs&category=integration)

Or manually, in HACS : `⋮ -> Custom repositories`, URL `https://github.com/mathieuletyrant/cozytouch-hacs`, type `Integration`.

More informations about HACS [here](https://hacs.xyz/).

#### Manually

Clone this repository and copy `custom_components/cozytouch` to your Home Assistant config durectory (ex : `config/custom_components/cozytouch`)

Restart Home Assistant.

## Configuration

Once your Home Assistant has restarted, go to `Settings -> Devices & Services -> Add an  integration`.

Search for `cozytouch` and select the `Atlantic Cozytouch` integration.

Enter your Cozytouch credentials.

If connection is working, you should have a list of devices configured on your account.

Select the device you want to add.

Only some values are mapped for now, you can select `Create entities for unknown capabilities` if you want to add all detected capabilities (this can be useful to help mapping).

## Scheduling

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

## Versioning

Releases use CalVer : `YEAR.MONTH.PATCH` (ex : `2026.8.0`).

`main` is protected, so a release is two steps. First a pull request setting
`version` in `custom_components/cozytouch/manifest.json` to the version being
released ; then a `Release` workflow dispatch naming that same version. The
workflow refuses to run while the manifest says something else, and otherwise
tags the commit and writes the notes from the commit subjects since the
previous tag.

## Credits

This integration started as a fork of [gduteil/cozytouch](https://github.com/gduteil/cozytouch)
and is now maintained independently here. All the original work is theirs.

Several device mappings come from pull requests opened against that project by
people who owned the hardware and worked out what it reported. Their work is
here because they did it :

| Device | modelId | By |
| ------ | ------: | -- |
| ACI HYB water heaters (PHAZY / AQUEO / DURALIS) | 386-394 | [@FreeTHX](https://github.com/FreeTHX), [@beorn-](https://github.com/beorn-) |
| Doris étroit 1300W CARAT | 1595 | [@tomcastleman](https://github.com/tomcastleman) |
| Calypso connecté | 1658 | [@picosam](https://github.com/picosam) |
| FLAT/S4 IOTHUB gateway | 1763 | [@Joonel](https://github.com/Joonel) |
| Thermor Malicio 3 65L | 1962 | [@genmllc](https://github.com/genmllc) |
| Egeo VS 250L | 2346 | [@Mathieu-Pasco-Breillot](https://github.com/Mathieu-Pasco-Breillot) |
| Explorer EVO 3 (260L) | 2374 | [@StefanWokusch](https://github.com/StefanWokusch) |

Where only part of a pull request was taken, the commit that took it says which
part and why the rest was left alone.
