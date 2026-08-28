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

### pyright, on three files

The declared fields on `ModelInfos`/`CapabilityInfos` are only worth what
checks them, and until this job nothing did. `pyproject.toml` scopes pyright
to `infos.py`, `model.py` and `capability.py` — the typed core, where the
declarations live — rather than the tree : the platforms and the hub read
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

## `.github/workflows/release.yaml`

### It installs with pip, where tests.yaml uses uv

The job is dispatched by hand a few times a year, so the minute it spends is
not worth the change on its own. Leaving it on pip also keeps a standing
proof that the requirements install without uv, which is what a contributor
following the README has.
