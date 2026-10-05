# What the Android app says about capabilities

Facts extracted from the vendor's Android app, `fr.atlantic.cozytouch`
**3.31.0** (versionCode 737), decompiled with jadx in September 2026 for
interoperability. Only ids, enum member names, masks and values are kept
here: no code, no UI text. How to get the app and redo the extraction is in
[`../methods.md`](../methods.md).

**This is a lower bound, not the catalogue.** The app knows what the app
does: the ids it reads and writes, the decoders it calls. It says nothing
about ids it never reads, and real hardware sends values it has no name for
(bit 8 of 188 is still one). The vendor's own catalogue,
`scripts/capability_catalogue.jsonl`, outranks it on names, units and bounds
(`docs/decisions.md`, *The vendor's capability catalogue*), and the capture
corpus ([`../corpus.md`](../corpus.md)) is the check on both.

## The tables

| File | What it is |
| ---- | ---------- |
| `capability_id_to_name_android.tsv` | The `Capabilities` enum: `NAME<TAB>id`, 192 entries. The app's only id table -- a name and nothing else. |
| `android_capability_types.tsv` | For 185 ids, every method that reads or writes one: the reader's interface, return type, and the decoder it calls (367 rows). `kind=ui` rows are views that only display the value. |
| `android_bitfields_331.tsv` | Every enum decoded by `fromBitField`: 16 enums, 93 members, with the mask and, where the member doubles as a value, its API value. |
| `android_value_enums.txt` | The non-mask enums: member and the API value it decodes from. |
| `android_writable_capabilities.tsv` | `NAME<TAB>id` for the 87 ids that appear at a write call site. |
| `android_fake_device_corpus.tsv` | Values from the app's own fake devices (`*FakeHelper`, one per product family), 288 literal pairs. Encodings, not models: the fixtures' `modelId` is random. Room-name placeholders were dropped. |

## How to read them

The app declares **no type** for a capability. The model is
`Capability(id, value: String?, modificationDate)` and the value is a string
on the wire, as it is here. The type is the decoder called where the value
is used, under `fr/modulotech/app/domain/model/devices/features/`:

| Decoder | What the value is |
| ------- | ----------------- |
| `fromBitField` | a sum of powers of two |
| `fromValue` / `fromGacomaValue` | one enum member |
| `buildListFromValue` | a number naming a whole set (350, 100800) |
| `toFloatOrMaxValue` / `toIntOrNull` / `toLongOrNull` | a number |
| `parseToArrayOfArrays` | a matrix; the caller decides the column count |
| `getProgrammingState` | a JSON `[temperature, offState]` |

`toFloatOrMaxValue` is the app's default numeric parser: it proves
"numeric", not "fractional". And a signature can mislead: 224's reader is
`boolean getEstimationSupport`, whose body is a mask test.

In the bit tables, a member's mask may cover several bits (`Service.AUTO`
is 6), and `-1` means "a possible value, never announced in a mask". The
decoder keeps every member with `mask > 0 && (mask & value) != 0`.

Ids below zero (`-100`) are the app's synthetic capabilities and do not
exist on the API.

## How they were extracted

- **Names:** the enum `Capabilities` is `NAME(id)`. jadx folds some literal
  ids into unrelated constants that happen to share the number
  (`NSType.TKEY` for 249, a Compose constant for 100000), and the
  declaration order does not follow the ids, so those were resolved by the
  constant's real value, never by position.
- **Types:** every method in `features/` that takes a `Capabilities` member,
  with its return type and the decoder in its body.
- **Writability:** `IGacomaDevice.writeCapabilitySuspend` takes the enum
  member, so every id the app writes appears beside a write call; the grep
  is in `docs/decisions.md`, *What the Android app is willing to write*. An
  id absent from it is only never written by this version.
- **Fixtures:** string literals passed to the fake devices' builders. 169
  more pairs are enum references (`Service.HEAT.getValue()`), which give a
  nominal value rather than an example, and are not in the table.

## What was concluded from them

Already in `docs/decisions.md`, not restated here:

- *Six more masks, and the two bits the corpus could not place* -- the bit
  tables against ours, 164 bit 10, 100013 bit 1, 224 as a mask.
- *Twenty descriptors read as what they are, and the ones left alone* -- the
  types, the nine booleans, 100196-100198, 105122.
- *The speed sets (350, 100800) name a set, and `4` names one speed*.
- *Seventeen names the iOS list got wrong* and *The enum is not the
  catalogue* -- the names.
- *What the Android app is willing to write* -- writability.
- *`read_setpoint` : hundredths, but not for hot water* -- the app's
  `t > 40 -> t / 100` rule on programme temperatures.

Facts the tables hold that no entry uses yet:

- **Programmes.** Whether a block is pairs `[minutes, temperature]` or
  triplets `[minutes, temperature, mode]` is bit `ON_OFF` of 100013, not the
  id family. A write sorts the milestones, pads with `[0,0]` to 10 slots (4
  for hot water) and drops `.0`. The third column is `ProgramMilestoneMode`
  (0 default, 1 on/off, 2 boost). Hot water also has *ranges*,
  `[startMinutes, endMinutes]` on 3 slots (245-251), with their own bounds.
- **Fault codes.** `[system, major, minor, level]`; the app's `hasError()` is
  `system != 0`; `level` 0-1 is blocking, 2-3 non-blocking, 4 information;
  a room without `ERROR_CODE_HOME` reads its gateway's.
- **Bounds the device declares:** 306 milestones per day, 100301 per week,
  295 time step, 296 minimum gap, 160-163 heating and cooling setpoint
  bounds, 294 setpoint step.
