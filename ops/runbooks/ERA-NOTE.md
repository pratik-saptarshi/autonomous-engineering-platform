# Era note — kit-era runbooks and model-switch plan

The three files in this directory tree copied from the October 2026
NeuroStrata ops kit snapshot (`reference/neurostrata-ops/`) are preserved
doctrine, NOT current practice. Each carries its own era banner as its first
markdown block. This note records every deviation from the kit originals and
names the stale facts a reader must not mistake for current reality.

## Delta table

| File | Deviation from kit original | Kit line | New line |
| --- | --- | --- | --- |
| `ops/runbooks/OPERATIONS.md` | Era banner prepended (first block) | — | 1–4 |
| `ops/runbooks/IDLE-REAPER.md` | Era banner prepended (first block) | — | 1–5 |
| `ops/model-switch/MODEL-SWITCH-BGESMALLQ-PLAN.md` | Era banner prepended (first block) | — | 1–5 |
| `ops/model-switch/MODEL-SWITCH-BGESMALLQ-PLAN.md` | MD009: trailing space removed from the line ending `download through the egress proxy):` (located by content, not by line number) | 51 | 56 |
| `ops/model-switch/MODEL-SWITCH-BGESMALLQ-PLAN.md` | Operator-name scrub 1: given-name possessive reference → "the operator's" (sentence wraps onto the next line) | 3 | 8 |
| `ops/model-switch/MODEL-SWITCH-BGESMALLQ-PLAN.md` | Operator-name scrub 2: given-name reference → "the operator" | 32 | 37 |
| `ops/model-switch/MODEL-SWITCH-BGESMALLQ-PLAN.md` | Operator-name scrub 3: given-name possessive reference in the heading → "the operator's" | 67 | 72 |

No other content differs from the kit originals. In particular, the fork
identifier on kit line 106 (`pratik-saptarshi/NeuroStrata`) is a repo
identifier, not a personal name: it was explicitly NOT scrubbed and is
byte-identical at new line 111 (verified by diff). No given-name occurrence
remains in the model-switch file outside that identifier.

## Stale facts in these files (do not treat as current reality)

- **Reaper cron.** `IDLE-REAPER.md` (kit lines 10–11) describes a
  `neurostrata-idle-reaper` cron every 15 minutes. The standalone reaper is
  retired; see `ops/bin/RETIRED.md` and `ops/crons/CRONS.md`.
- **`~/go/bin` binary path.** `OPERATIONS.md` (kit lines 7, 21, 76–78, 142)
  and `IDLE-REAPER.md` (kit lines 56–57, 72) invoke the daemon from a
  kit-era `~/go/bin` layout. That layout is superseded; for the current
  arrangement see the canonical watchdog (`ops/bin/watchdog-backup.sh`).
- **Three-cron world.** No literal "three-cron" claim appears in these three
  files. The three-job framing lives in the kit scheduler page
  (`reference/neurostrata-ops/crons/CRONS.md`), superseded by
  `ops/crons/CRONS.md`. Within these files the stale assumption surfaces as
  the reaper 15-minute cron and the watchdog 2-hour cron references above.
- **v1.9.0-era version claims.** `OPERATIONS.md` (kit line 7) lists a v1.9.0
  binary, and the model-switch plan (kit line 104) reasons about an installed
  1.9.0 binary. Both claims date to the kit snapshot; do not use them to
  reason about the current runtime.
