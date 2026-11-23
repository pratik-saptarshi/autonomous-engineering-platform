---
name: stored-manifest-refresh
version: 1.0.0
author: pratik-saptarshi
description: >-
  Refresh a stored integrity manifest only by that system's documented
  procedure, prove the regeneration moved exactly the expected entries, and
  verify both integrity legs locally before anything is committed. Covers the
  AEP skills manifest (scripts/check_skills_manifest.py --root skills
  --write/--check inside a scratch clone, plus the
  .github/skills-sync-scope.txt membership edit for new skills) and
  vendor-integrity sha256sum -c style manifests. Use when a change has
  stale-dated a stored manifest, a new member must enter a manifest's scope,
  or a regeneration's diff needs proving before commit.
---

# Stored Manifest Refresh

**Announce at start:** "I'm using the stored-manifest-refresh skill to refresh this stored manifest."

## When to Use

A stored integrity manifest — a checked-in file of hashes that other tooling verifies against — no longer matches the tree it describes, because files changed, were added, or were removed. The refresh must regenerate the manifest, and the regeneration is only trustworthy if its diff is exactly the change that stale-dated it.

Do NOT use for: hand-editing a single hash line to make a check pass (that is the failure this skill exists to prevent), a lockfile repair (that is `lockfile-repair-by-regeneration`), or screening a third-party skill before install (that is `skill_ingestion_gate`).

Two systems are evidenced, and their mechanics differ, so each gets its own worked procedure below. Never transfer one system's procedure to the other.

- **System A — AEP skills manifest.** Manifest `.github/skills-manifest.sha256`, scope `.github/skills-sync-scope.txt`, checker `scripts/check_skills_manifest.py`. Evidence: the H7 scratch-clone rehearsal (416 entries, `--check` PASS) and the tranche-1 landing (416 → 418 entries, diff of exactly 5 entries).
- **System B — vendor-integrity manifests.** One `.github/vendor-<name>.sha256` per vendored tree, verified with `sha256sum -c`. Evidence: the ruling events over PRs #147/#152, #157, and #163 F1, where the owner ruled REFRESH the vendored manifest rather than exempting or hand-patching it.

## Rules that bind both systems

1. **Regenerate only by the system's documented procedure.** Never hand-edit a hash, never compute hashes with a generic tool and paste them in, and never carry a hash over from an old snapshot for a file that changed. A correct-looking manifest produced by the wrong route does not count — the procedure is part of the outcome.
2. **Enumerate the expected entries before regenerating.** Write down, before any mutating command: the starting entry count, and every entry the change should add, remove, or re-hash — no more, no fewer. This enumeration is the diff oracle for step 4 of either procedure.
3. **Prove the diff is exactly the enumeration.** After regenerating, diff the new manifest against the old one. The diff must equal the enumerated entries exactly. Every other line is byte-identical, the entry-count delta is fully explained by the enumeration, and no entry moved that the enumeration does not name.
4. **Halt on an unlisted entry.** If regeneration moves an entry the enumeration does not list, halt and report — name the entry, commit nothing, and do not extend the enumeration after the fact to absorb it. An unexplained moved entry is a divergence to explain, not to commit past.
5. **Verify both integrity legs locally before commit.** Each system below names its two legs (regeneration check and independent verification). Both must pass locally, in the shape the system's own tooling uses, before the refreshed manifest is committed. A leg run from the wrong directory or against the wrong tree verifies nothing.
6. **Record the head's CI state truthfully.** When recording status for a head, read the head's actual check runs first. If the list is empty, the record states "no CI run at this head" — verified against those check runs, not merely written. Never write "CI pending", "CI passed", or leave the field blank in place of that verified state.

## System A — AEP skills manifest

Manifest operations run **only inside a scratch clone** (or the repo clone designated for the landing), never against a working checkout: the checker resolves the manifest and the scope file from its own repo root, and `--write` mutates them.

Step order — the order is load-bearing:

1. **Junk-scan and record the baseline.** Scan the tree for `.write-lock`, `__pycache__`, `.DS_Store`, and editor backups; record finds and exclude them. Record the current manifest entry count (`wc -l .github/skills-manifest.sha256`) and confirm the starting state with `python3 scripts/check_skills_manifest.py --root skills --check`, noting any stale entries the change already explains.
2. **Enumerate the expected entries** (Rule 2): every added, removed, or re-hashed entry the change explains, and the expected final count.
3. **Edit scope membership before regenerating, when membership changes.** A new skill enters the manifest only if its directory name is listed in `[skills]` in `.github/skills-sync-scope.txt` (alphabetical). Without the scope edit, regeneration silently omits the new skill — the manifest still regenerates and `--check` still passes, so the omission is visible only in the diff proof (step 5). Membership changes are edits to that file; no scope rule is hardcoded anywhere else. Files named in `[exclude-paths]` (every `skill.yaml`, on the evidenced tree) and files matching an `[exclude-content]` literal contribute no entries — do not expect them in the enumeration.
4. **Regenerate only by the documented procedure**, from the scratch clone's root:

   ```bash
   python3 scripts/check_skills_manifest.py --root skills --write
   ```

5. **Prove the changed-entries-only diff.** Diff `.github/skills-manifest.sha256` against its pre-refresh state. It must equal the step-2 enumeration exactly — in the tranche-1 landing that was +2 entries (the two new skills' `SKILL.md` files) and 3 hash updates, 416 → 418. Any additional moved entry triggers Rule 4's halt. A zero-entry result, or any final count the enumeration does not explain, also halts here, before commit (see the wrong-root guard below).
6. **Verify both legs locally.** Leg 1: `python3 scripts/check_skills_manifest.py --root skills --check` exits 0 with the expected entry count. Leg 2: the diff proof from step 5, re-read against the enumeration — the checker's own OK does not substitute for it, because `--check` cannot see a scope omission (step 3).

### Wrong-root guard (step order, not history)

A wrong `--root` can produce a manifest with zero entries. The step order above catches that shape before commit: the baseline count is recorded in step 1 and the expectation in step 2, *before* the mutating command in step 4, and step 5 compares the regenerated count and diff against that expectation — a zero-entry manifest fails that comparison and halts. This is a requirement this procedure imposes. The historical record is different and must be stated exactly: in the 2026-11-20 incident, a wrong `--root` emptied a manifest and **the operator caught it** — no procedure caught it, and this skill does not claim otherwise.

## System B — vendor-integrity manifests

Each vendored tree carries one manifest, `.github/vendor-<name>.sha256`, in the line format `<sha256hex>  ./<path>` (two spaces), paths relative to the vendored tree's root, in path order.

Step order:

1. **Record the baseline.** Note the manifest's entry count and run the verification leg against the pre-refresh tree to name exactly which entries are stale:

   ```bash
   sha256sum -c .github/vendor-<name>.sha256
   ```

   run from the vendored tree's root, so the `./<path>` entries resolve.
2. **Enumerate the expected entries** (Rule 2): the files the vendored update actually changed. Unchanged files' hash lines must not move.
3. **Regenerate by the documented procedure:** re-hash the refreshed vendored tree and rewrite the manifest in the same line format and path order. Do not hand-edit individual hash lines, and do not reuse hashes from the previous snapshot for changed files.
4. **Prove the changed-entries-only diff.** The manifest diff equals the step-2 enumeration exactly — one changed hash line per changed file, no added or removed lines unless the update itself added or removed files (and then only those). Any other moved line triggers Rule 4's halt.
5. **Verify both legs locally.** Leg 1: `sha256sum -c .github/vendor-<name>.sha256` from the vendored tree's root reports OK for every entry (exit 0). Leg 2: the diff proof from step 4, re-read against the enumeration. A verify run from any other directory is not a leg — the paths will not resolve as the manifest intends.

Precedent: PR #157 — the owner ruled REFRESH the vendored manifest and keep the PR open; the refresh was the correct disposition even though an unrelated guard then closed the PR, and the refreshed manifest was preserved on the branch. Refresh by procedure is the standing answer to a stale-dated vendor manifest; an exemption or a hand-patch is not.

## Stop Conditions

- Regeneration would be done by hand-editing hashes or by any route other than the system's documented procedure — stop; that route is refused.
- The manifest diff moves an entry outside the pre-regen enumeration — halt and report (Rule 4); do not commit, do not extend the enumeration after the fact.
- The regenerated manifest has zero entries, or a count the enumeration does not explain — halt before commit.
- Either local verification leg fails, or was run from the wrong directory or against a working checkout (System A) — stop; the refresh is unverified.
- A new member is missing from the manifest after regen — check scope membership (System A, step 3) before re-running anything; do not hand-add its hash line.
