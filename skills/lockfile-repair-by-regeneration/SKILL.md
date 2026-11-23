---
name: lockfile-repair-by-regeneration
version: 1.0.0
author: pratik-saptarshi
description: >-
  Repair a diverged Cargo.lock by discarding the branch lock, taking main's
  lock wholesale as the base, and applying only targeted
  cargo update -p <pkg> --precise <ver> updates for the intended edges, then
  proving the diff against main is exactly the allowlisted edge flips with
  every unrelated pin byte-identical. Use when a branch lockfile has diverged
  from main, drift pins have accumulated, or a lockfile-only bump must be
  repaired without losing its one intended edge.
---

# Lockfile Repair by Regeneration

**Announce at start:** "I'm using the lockfile-repair-by-regeneration skill to repair this diverged lockfile."

## When to Use

A branch's `Cargo.lock` has diverged from main's — cut from an older base, regenerated on the branch side, or carrying stale pins alongside one or a few deliberate changes — and the repair must preserve exactly the intended edges and nothing else. The branch lock is the defect; the goal is a repaired lock whose entire difference from main is explained, in advance, by an allowlist.

Do NOT use for: an ordinary dependency bump on a lock that already matches its base (just run the targeted update and the gate), a `Cargo.toml` change (a manifest change is a different task — this procedure makes no manifest edit), or any resolution shape named in the Refusals section below.

Precedents: Rocinante #126 (merged `3c0cb08`), #128 (repair `2b0c2fd`, merged `3020090`), and #124 (merged `3649715`, 2026-11-21) — lockfiles repaired by regeneration rather than by merging the diverged locks.

## Quiet-window rule (by reference)

This rule is already homed in the `rust-pre-pr-gate` skill ("Run discipline" and "Quiet-window discipline"); this skill cross-references it rather than claiming it as novel content, and applies it to every cargo step below.

- Before any Rust-touching rehearsal or repair step, check for foreign `cargo`/`rustc` processes on this host (for example `pgrep -a cargo; pgrep -a rustc`, excluding your own process tree).
- If any foreign `cargo`/`rustc` process is running, wait for a quiet window. Do not start the repair, the rehearsal, or a gate run concurrently.
- Record the check result (quiet, or waited and for how long) in the run record. If another lane starts mid-run anyway, disclose the load and corroborate any flake with a solo re-run.

A run that skips this check fails, regardless of its lock outcome.

## Procedure

### Step 1 — Name the intended edges and build the allowlist first

Before touching any lock:

- Identify main's `Cargo.lock` as the wholesale source of truth, and pin which main head it comes from.
- Enumerate the branch's intended edges only: each deliberate change, as a package name and its exact target version (for example a Dependabot-class bump of one package). Everything else that differs between the branch lock and main's lock is drift, by definition, and must not survive the repair.
- Write the allowlist down before the repair: for each intended edge, the package, the version line before and after, and the checksum line before and after. Add any removal the flip structurally causes (see the worked fixture in Step 4). The allowlist must also enumerate, item by item, every other change the flip structurally causes in exactly these categories: (a) a dependency-reference removal or edit inside a surviving package's `dependencies` list (for example the `"rkyv"` entry disappearing from the surviving `rust_decimal` block when its dependency is deleted); (b) a dependency-entry change inside the flipped package's own `[[package]]` block, beyond its version and checksum lines; and (c) any added line the flip structurally causes (for example a replacement dependency entry, or the new version/checksum lines as they appear in the flipped block). A change in one of these categories that is not itemised here in advance is not allowlisted — it is an unlisted change under Step 4's halt rule. The allowlist is the acceptance test for Step 4; a repair with no written allowlist has no proof.

### Step 2 — Repair: take main's lock wholesale, then targeted precise updates only

The repair procedure, in order:

1. Run the quiet-window check above.
2. Discard the branch lock as a base. Take main's lock wholesale: the repaired lock starts as a byte copy of main's `Cargo.lock`.
3. Apply targeted updates for the intended edges only, one per intended edge, in exactly this form:

   ```
   cargo update -p <pkg> --precise <ver>
   ```

4. No other `cargo update` invocation — no bare `cargo update`, and no targeted update for any package not on the allowlist.
5. No hand edit of `Cargo.lock`, and no `Cargo.toml` edit.

A byte-identical result reached by a different route — hand-editing versions into the branch lock, merging the two locks, or regenerating from scratch — is not this repair. The procedure is part of the outcome, not just the artifact.

### Step 3 — Refusals: two resolution shapes refused by name

When either shape below is proposed, refuse it by name and state the permitted alternative (Step 2) in the same breath. Accepting either proposal, or silently substituting Step 2 without naming the refusal, is a failure.

- **"take either side" merges — refused by name.** Do not resolve a diverged `Cargo.lock` by taking one side of the merge wholesale: no `git checkout --ours Cargo.lock`, no `git checkout --theirs Cargo.lock`, no merge-driver "take side" resolution, and no manually keeping either lock as-is with no targeted update applied. Note that taking main's side alone, without the targeted update, also fails: the intended edge is lost. Taking main's lock is permitted only as the *base* for Step 2, never as the whole repair.
- **Branch-side full regeneration — refused by name.** Do not repair the branch by regenerating its lock from scratch on the branch side: no deleting `Cargo.lock` and running `cargo generate-lockfile`, and no bare `cargo update` (no `-p`/`--precise`) on the branch with the result kept. Full regeneration re-resolves every pin, so drift and unintended upgrades enter silently and the diff can no longer be proved against an allowlist.

Grounds on record: the mining ledger for this pattern states that branch-side full regeneration and "take either side" merges are banned for lockfile repair.

### Step 4 — Diff proof: exactly the allowlisted flips, then halt on anything else

Diff the repaired lock against main's lock (the wholesale base from Step 2) and prove all of the following:

- The diff is exactly the allowlisted edge flips from Step 1: the version and checksum lines of each intended package, inside that package's `[[package]]` block — plus, where an intended flip structurally causes them and the allowlist already itemised them, exactly: the removals the flip causes (see the worked fixture below); a dependency-reference removal or edit inside a surviving package's `dependencies` list; a dependency-entry change inside the flipped package's own block; and an added line the flip structurally causes. Nothing else is permitted: this is a closed enumeration, not a general waiver for changes that look structurally caused.
- Every unrelated pin is byte-identical to main's: every other package's block matches main's byte for byte, in the same order — except for a dependency-reference line inside a surviving package's block that the allowlist itemised under the enumeration above; the package set is unchanged except for allowlisted structural removals; the lock header is unchanged.
- The package-count delta, if any, is fully explained by the allowlisted flips and their structural removals.

**Halt-and-report on any unlisted change.** If the diff contains any additional changed, added, or removed line — a drift pin surviving, a reordered block, a header change, a package added or dropped without an allowlist explanation — halt the repair and report the unlisted change. Do not proceed, do not extend the allowlist after the fact to cover it, and do not push. An unexplained line fails the proof the same way a surviving drift pin does.

Worked fixture (S1/S2 shape, small case): main pins `tokio 1.48.0`; the branch's one intended edge is `tokio 1.49.0`, while its `serde`, `serde_derive`, `anyhow`, and `syn` pins are stale drift. The repair takes main's lock wholesale, runs exactly `cargo update -p tokio --precise 1.49.0`, and the diff against main is exactly two changed lines — the `tokio` version line and the `tokio` checksum line — with every other package's block byte-identical and all four drift pins rejected.

#### Worked fixture at real scale — the rkyv / RUSTSEC-2026-0235 edge-diff

Provenance, stated exactly as the record supports it: the fully documented record of this bump is the 2026-11-09 record at `$HOME/.superpowers/sdd/2026-11-09-rust-decimal-draft-pr/` (`pr-body.md`, `report.md`), for the NeuroStrata fork's draft PR #47. An attribution of this fixture to ladybug-rust (2026-11-12, merged in `c597f919`) appears in the task brief and the mining ledger's one-line watch-list disposition, but that commit was not found in any record searched and the ladybug-rust attribution is **unverified** — do not cite it as established. The values below are the documented NeuroStrata record's values.

- Change shape: `Cargo.lock` only; no `Cargo.toml` edit (both parents' caret ranges already admitted the target).
- Producing command: `cargo update -p rust_decimal --precise 1.43.0` — no hand edits.
- The one version flip: `rust_decimal` **1.41.0 → 1.43.0** — the only version change in the lock; nothing added.
- Advisory cleared: **RUSTSEC-2026-0235** (`rkyv` < 0.8.17; the fix exists only in `rkyv` 0.8.17+). `rkyv 0.7.46`'s sole dependent was `rust_decimal 1.41.0`, as an optional dependency enabled by no consumer; `rust_decimal 1.43.0` deletes the `rkyv` 0.7 dependency outright.
- Packages removed outright (13): `rkyv` 0.7.46, `rkyv_derive` 0.7.46, `bytecheck` 0.6.12, `bytecheck_derive` 0.6.12, `rend` 0.4.2, `ptr_meta` 0.1.4, `ptr_meta_derive` 0.1.4, `seahash` 4.1.0, `bitvec` 1.1.1, `funty` 2.0.0, `radium` 0.7.0, `tap` 1.0.1, `wyz` 0.5.1.
- Cluster-only versions shed (3): `ahash` 0.7.8, `hashbrown` 0.12.3, `syn` 1.0.109 (other versions of each remain for other consumers).
- Package count: **547 → 531**; diffstat `Cargo.lock` **+5/−161**. Audit before → after: RUSTSEC-2026-0235 gone (zero occurrences of `rkyv` in the lock); the remaining vulnerabilities were the capped quick-xml pair only.
- Commit in that record: `3f175bd` — `chore(deps): bump rust_decimal to 1.43.0 to remove rkyv 0.7 (RUSTSEC-2026-0235)`, draft PR #47, base `develop` @ `a7cc416` — a held draft, not a merge, and not `c597f919`.

The shape this proves: diff(repaired, base) = {the one allowlisted version flip} ∪ {the removals that flip structurally causes} ∪ {the allowlisted dependency-reference edit in the surviving `rust_decimal` block and the flip-caused added lines the allowlist itemised} and nothing else — every surviving package's pin byte-identical, the package-count delta (−16) fully explained by the removed cluster (13 outright + 3 shed versions), and the audit delta exactly the one advisory the edge carried.

### Step 5 — Sled-class repairs: scratch rehearsal before the real branch

A sled-class repair — the lock divergence sits in the `sled` dependency subtree, where the repair interacts with a second tree's pin set and cannot be validated by inspection alone — carries an additional gate. Source incident: Rocinante PR #163's branch, whose sled repair collided with the `src-tauri` tree's rusqlite/sled resolution.

- No step touches the real branch until a scratch rehearsal has succeeded. Execute the drafted repair sequence (Step 2, with its allowlist) in a scratch copy or clone first.
- The rehearsal bar is the source incident's own: **3 successful scratch reproductions** of the drafted sequence, each producing a lock whose diff against main matches the repair's allowlist under Step 4's proof, before the sequence may run on the real branch.
- A failed rehearsal resets the count to zero for the corrected sequence. A changed sequence is a new sequence and restarts the count.
- Every rehearsal run obeys the quiet-window rule above; a rehearsal run concurrently with foreign `cargo`/`rustc` processes does not count toward the 3.
- Running the repair on the real branch after 0, 1, or 2 successful rehearsals is a failure, as is proceeding straight to the real branch because the sequence "looks right".

## Evidence Standard

A completed repair reports: the base main head the wholesale lock was taken from; the written allowlist (each intended edge with its version and checksum lines before and after, plus any structurally caused removals); the exact `cargo update -p <pkg> --precise <ver>` commands run; the quiet-window check result; the Step 4 diff proof result (changed lines counted against the allowlist, unrelated pins byte-identical); and, for a sled-class repair, the scratch-rehearsal record showing 3 successful reproductions before the real branch was touched.

## Stop Conditions

Stop and report: the intended edges cannot be enumerated before the repair; the quiet window cannot be obtained; the Step 4 diff contains any unlisted change; a "take either side" merge or branch-side full regeneration is the only route on offer (refuse both by name, per Step 3); a sled-class repair has fewer than 3 successful scratch reproductions; the repair would require a `Cargo.toml` edit or a hand edit of `Cargo.lock`.
