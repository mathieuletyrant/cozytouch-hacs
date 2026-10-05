# How the vendor's apps were read

The API sends `{capabilityId, value}` and nothing else, so most of what this
integration knows about a capability came from watching the vendor's own
client. This page says how, so it can be redone on a newer version. What
was *concluded* lives in `docs/decisions.md` and `docs/api-surface.md`; the
facts extracted from the Android app are in [`android/`](android/README.md),
and the capture corpus in [`corpus.md`](corpus.md).

Three routes, in the order to reach for them today:

1. the vendor's catalogue, `scripts/*_catalogue.jsonl`, which needs no
   decompiling at all;
2. the Android app, whose capability layer is Kotlin and reads in clear;
3. a traffic capture of the iOS app, when a behaviour cannot be reproduced
   through the API.

The iOS decompilation that came first is described last, as obsolete.

## What may be done, and what may be kept

Decompiling a program to obtain what is needed to make another program
interoperate with it is allowed without the rightholder's consent, by
article 6 of Directive 2009/24/EC and, in France, article L122-6-1 IV of the
Code de la propriété intellectuelle. It covers *using* the information for
interoperability. It does not cover redistributing the code, nor the
vendor's UI text (labels, fault descriptions, translations), which are works
of their own.

So this repository holds **facts only**: capability ids, enum member names,
masks, values, routes, field names, and our own descriptions of them. The
APK, the XAPK, any decompiled output, the app bundle and string tables
extracted from it must **never be committed** -- regenerate them locally
with the steps below, and keep them outside the working tree. A table of
vendor strings is not a fact table; translate the meaning into our own
words or leave it out.

## The Android app

Version used: `fr.atlantic.cozytouch` **3.31.0**, versionCode **737**
(September 2026).

### Getting it

Obtain the APK of the version above from a device you own, then decompile it:

```sh
jadx -d out --no-res --no-debug-info fr.atlantic.cozytouch.apk
```

`--no-res` skips resources (nothing in them is capability data: the only
data assets are Lottie animations and an Overkiz demo setup with no
`capabilityId`), `--no-debug-info` keeps jadx from inventing variable
names. jadx itself takes about three minutes; the whole job is an hour.
Note the version you decompiled.

### Where the capability semantics live

| Path under `out/sources/` | What it carries |
| ------------------------- | --------------- |
| `fr/modulotech/app/domain/model/devices/Capabilities.java` | The id enum, `NAME(id)`, nothing else. |
| `fr/modulotech/app/domain/model/devices/features/` | The readers: one `I*Feature` interface per domain. The type lives here, as the decoder each reader calls. |
| `.../devices/features/*/<Enum>.java` | The value spaces and masks (`Service`, `Mode`, `DHWMode`, `VentilationControls`...). |
| `.../devices/CapabilitiesKt.java` | Where the enum says it comes from: an internal spreadsheet that is not in the APK. |
| `com/modulotech/atlantic/devices/gacoma/` | Per-product classes: which device implements which feature. |
| `com/modulotech/atlantic/views/devices/steering/` | The views: whether a capability is *shown* or only read. |
| `com/modulotech/epos/device/DeviceStateCommande.java` | The `"0"`..`"9"` constants jadx substitutes for literals in the enums. |
| `com/modulotech/kmm/` | Code shared with iOS: consumption service, device details. |

### Reading the casts

There is no declared type. `getCapabilityValue()` returns a `String?`, and
the type is whatever the call site does with it: `fromBitField` is a mask,
`fromValue` an enum member, `toFloatOrMaxValue` a number, and so on. The
full table of decoders, and how the extracted files were built from them,
is in [`android/README.md`](android/README.md).

The trap: jadx folds a literal id into an unrelated constant that happens
to have the same value (`NSType.TKEY` for 249), and the enum is not
declared in id order. Resolve an entry by the constant's real value, never
by its position.

The app is authoritative on **what the app does**, not on what the firmware
sends: hardware reports bits no enum member names. The capture corpus is
the check.

## Capturing the iOS app

When the app achieves something the API seemingly cannot, capture the
client rather than decompile further. This is what settled capability
102020 -- after months of reading the Android code, one capture showed the
app writing the system's service there (`docs/decisions.md`, *The service
is one house's, and the write is one room's*).

1. On the Mac, run `mitmproxy` (or `mitmweb`); it listens on port **8080**.
2. On the iPhone, same Wi-Fi: Settings, Wi-Fi, the network, Configure Proxy,
   Manual, the Mac's address and port 8080.
3. In Safari on the iPhone, open `http://mitm.it` and install the iOS
   profile (Settings, General, VPN & Device Management).
4. **Then trust it**: Settings, General, About, Certificate Trust Settings,
   enable full trust for the mitmproxy root. This is the step that is always
   missed, and without it every HTTPS call fails.
5. Use the app, and read the `apis.groupe-atlantic.com` requests: route,
   body, headers, and what follows them.

Remove the proxy and the profile afterwards. To replay what was seen,
`scripts/probes/probe_write_service.py` writes one capability, follows the
execution and prints the capability on every device -- with the warnings in
its docstring: it writes to the live account, and only the maintainer runs
it.

## The iOS decompilation (obsolete)

This came first, in August 2026, and gave the first id-to-name table. It is
superseded: the Android app reads in clear, and the iOS names turned out to
be wrong in places (`docs/decisions.md`, *Seventeen names the iOS list got
wrong*). Kept for the record, and in case the Android app ever stops being
readable.

**The bundle.** On an Apple Silicon Mac, install Cozytouch from the Mac App
Store; `/Applications/Cozytouch.app` has unencrypted resources. Three
layers: Flutter/Dart (`App.framework/App`, the UI and the `ga_magellan` API
client), MagellanKitKMM (Kotlin Multiplatform, cloud services) and a Swift
executable that holds the native capability parsing.

**Dart, with blutter.** blutter decompiles Flutter snapshots but only
supported Android ELF. Three local changes made it read the iOS Mach-O:

- its `extract_dart_info.py` learnt to recognise a 64-bit Mach-O, walk its
  load commands for the section table and symbol table, find
  `_kDartVmSnapshotData`, map that virtual address back to a file offset,
  and read the snapshot hash and flags from there; it also reads the Dart
  version string and the CPU type out of the Flutter framework;
- its CMake configuration defined only `DART_TARGET_OS_MACOS_IOS` for iOS,
  but the Dart runtime nests its iOS branch inside the macOS one, so both
  `DART_TARGET_OS_MACOS` and `DART_TARGET_OS_MACOS_IOS` must be defined or
  the build stops on "What operating system?";
- its ELF helper's Mach-O path was an unfinished stub; it was replaced with
  a loader built on the system's `mach-o` headers, which walks the load
  commands, records segments and the symbol table, and resolves the four
  snapshot symbols (VM and isolate, data and instructions) to pointers into
  the mapped file.

Run with `--no-analysis`: the arm64 analyser assumes compressed pointers,
which iOS does not use. The Dart side confirmed the endpoint map and held no
capability table.

**Swift, with Ghidra.** The public Ghidra release has no macOS arm64
decompiler; build the `decompile` binary from source with the Makefile set
to `-arch arm64` and `OSDIR=mac_arm_64`, and install it under
`os/mac_arm_64/`. The parser is a function that is one
`switch (capabilityId)` of some 750 cases returning an enum case index. It
was found by scoring every function on how many of its immediates match the
ids already known -- counting half-values too, since a large id is loaded
in two instructions (`MOVZ`/`MOVK`). The case index is joined to a name
through a 179-case Swift enum read from the `__swift5_fieldmd` reflection
metadata. Two pitfalls: a `case` with an empty body falls to the default
rather than to the next case, and two codes are shared by hundreds of ids
and say nothing. 161 ids were named this way.
