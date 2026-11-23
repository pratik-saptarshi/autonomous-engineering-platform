---
name: dependency-triage-by-source
version: 1.0.0
author: pratik-saptarshi
description: >-
  Scope a dependency programme by crossing three independent inventories
  (Dependabot PRs, Dependabot alerts, cargo audit) and classifying every
  finding patch-only / transitive-major / structural-replacement / drop
  before any bump is proposed. Use when scoping dependency upgrades,
  Dependabot backlogs, or audit remediation on a Rust repo, and whenever
  a cargo update dry-run tempts an opportunistic bump.
---

# Dependency Triage by Source

**Announce at start:** "I'm using the dependency-triage-by-source skill to scope this dependency programme."

## The rule in one line

Cross three inventories, classify every finding, and only then propose bumps. A crate with no advisory and no Dependabot PR is `drop` — do not bump it.

## Step 1 — Cross three inventories (all three, always)

Before any classification or bump, enumerate **all three** inventories as separate inputs:

1. **Dependabot PRs** — every open PR in the repo, dependency bumps and anything else that happens to be open.
2. **Dependabot alerts** — every open alert.
3. **cargo audit** — a fresh audit of every lockfile in the repo (a repo can hold more than one; audit each one and keep its rows separate).

Deduplication across inventories is part of the work: the same subject may appear in one, two, or all three. For **each** classified subject, record which inventories it appeared in (PR / alerts / audit). A subject found in only one inventory is still classified — in particular, audit-only subjects (no PR, no alert) must appear in the output; triaging from Dependabot PRs alone silently loses them.

Also capture the `cargo update --dry-run` offer list, but treat it as **none of the three inventories**: it is evidence for the drop rule and the restraint rule (Step 4), never a source of findings by itself.

## Step 2 — Classify every finding, before any bump is proposed

Classify **every** finding into **exactly one** of the four classes below. The classification of the full set is presented **before, and independently of, any proposed bump list**. An output that proposes bumps for a subset and never classifies the rest fails this procedure, as does an output whose only "classification" is the bump list itself. No finding is left unclassified, and no subject that no inventory produced is invented as a finding.

| Class | Definition |
|---|---|
| `patch-only` | A patch-version bump (same major, same minor for 0.x: same 0.minor) resolvable in the lockfile with no `Cargo.toml` change clears the finding. |
| `transitive-major` | The available fix or proposed bump is **not** patch-resolvable: a major bump, or a 0.x minor bump (breaking under 0.x semver), or a non-cargo major (e.g. a GitHub Action major). It needs a manifest change or a deliberate compatibility decision, and must not be folded into a patch-only batch. |
| `structural-replacement` | No version bump of the named crate clears the finding: the crate must leave the tree, be replaced, or arrive at a fixed major only as a side effect of replacing/upgrading the structural parent that pulls it in. Patch bumps of the crate or its entry points demonstrably do not clear it. Never fold this class into `transitive-major`, and never propose a bump of the named crate as its fix. |
| `drop` | The crate has **no advisory and no Dependabot PR**. It is not bumped, however attractive the dry-run offer looks. See Step 3. |

Non-dependency PRs found in the PR inventory (e.g. a release-automation PR) are named as **not-a-finding** and excluded from the classification set — never classified into a bump class, and never silently counted as dependency PRs.

## Step 3 — The drop rule (no advisory + no PR = drop)

A crate that appears in **none** of the three inventories — no advisory in the cargo audit inventory, no Dependabot PR, no Dependabot alert — and is present only as a `cargo update --dry-run` offer is classified **`drop`: do not bump**. Full stop.

- The rule fires in the full-set classification pass (Step 2), not as an afterthought.
- Do not classify it `patch-only` because the offered bump looks patch-shaped.
- Do not propose the bump "opportunistically" alongside real findings.
- Do not defer it as undecided: the rule decides.
- Do not require an owner ruling to drop it.

## Step 4 — Dry-run restraint (deferred is not drop)

The dry-run offer list is always much larger than the finding set (in the worked example below, roughly 80 offers; the count itself is unstable — 80/81/85 were all measured, and there is no canonical count). Beyond the subjects the record drops *with reasons*, the remaining offers are **intentionally deferred, not overlooked** — and **deferred is not `drop` and is not a class**. Never classify every unlisted dry-run offer as `drop`: the `drop` class contains exactly the subjects dropped with stated reasons under Step 3, no others.

## Step 5 — Propose bumps, grouped by class

Only after the full classification exists:

- `patch-only` subjects form the lockfile-only bump batch.
- `transitive-major` subjects are split out individually, each with its manifest change or compatibility decision stated; they never ride in the patch-only batch.
- `structural-replacement` subjects become structural follow-ups naming the parent whose replacement or upgrade clears them; no bump of the named crate is proposed.
- `drop` subjects get no bump proposal of any kind.

## Worked example — the 2026-11-07 Rocinante census (gold set)

The procedure above, applied to the 2026-11-07 Rocinante dependency-tree check, reproduces this classification exactly. Census state: main at `6210b25`, cargo-audit 0.22.2, advisory DB 1422; pristine `src-tauri` audit = 11 vulnerabilities + 5 warnings; pristine `tools/sled-migration` audit = 1 vulnerability (ctutils).

### Inventory accounting

- **PR inventory: 12 rows** — 11 Dependabot bumps + Release Please PR #120 (subject 24, not-a-finding). Reporting "12 Dependabot PRs" without noticing the Release Please PR is a provenance failure.
- **Alert inventory: 8 rows** — 4 on zip (#19, #20, #21, #22) + 4 on rustls (#15, #16, #17, #18). No alerts exist for tokio, ctutils, webpki-roots / rustls-webpki, or the zbus trio — those are audit-only.
- **Audit inventory: 17 rows** — `src-tauri`: 11 vulnerabilities (zip ×4: RUSTSEC-2026-0367/-0368/-0369/-0429; rustls ×4: -0346/-0347/-0348/-0349; rustls-webpki -0382; webpki-roots -0381; ctutils -0385) + 5 warnings (tokio -0386 unsound; arrow-data -0442 unsound; zvariant -0370, zbus_names -0371, zvariant_derive -0372 unmaintained); `tools/sled-migration`: 1 vulnerability (ctutils -0385, second lockfile — same advisory, separate row).
- **Class totals over the 23 classified subjects:** patch-only **9**, transitive-major **7**, structural-replacement **5**, drop **2**.

### The 24 subjects

Inventories: PR = Dependabot/open-PR inventory, AL = Dependabot alerts, AU = cargo audit.

| # | Subject | Inventories | Class |
|---|---|---|---|
| 1 | rustls 0.23.45 — audit RUSTSEC-2026-0346 (medium), -0347/-0348/-0349 (low), fix ≥0.23.46; alerts #15–#18; PR #135 proposes 0.23.45 → 0.23.46. Arrives via ureq. | PR, AL, AU | patch-only |
| 2 | rustls-webpki 0.103.15 — audit RUSTSEC-2026-0382, fix ≥0.103.16. No alert, no PR of its own. | AU | patch-only |
| 3 | webpki-roots 1.0.9 — audit RUSTSEC-2026-0381, fix ≥1.0.10. Via ureq. No alert, no PR of its own. | AU | patch-only |
| 4 | ctutils 0.4.2 — audit RUSTSEC-2026-0385, fix ≥0.4.4; present in both lockfiles (the sled-migration lockfile's only pristine finding). No alert, no PR. | AU | patch-only |
| 5 | tokio 1.53.1 — audit RUSTSEC-2026-0386 (unsound), fix ≥1.53.3 by its patch floor. No alert, no PR. | AU | patch-only |
| 6 | arrow-data 58.4.0 — audit RUSTSEC-2026-0442 / CVE-2026-111959 (unsound), via duckdb → arrow 58.4.0; patched in ≥58.4.1. | AU | patch-only |
| 7 | zip 6.0.0 — audit RUSTSEC-2026-0367, -0368, -0369 (critical 9.1) and -0429; alerts #19 (critical), #20 (high), #21 (high), #22 (medium). Fix needs ≥9.0.0, a major jump that arrives only **via libduckdb-sys** (zip is DuckDB-side plumbing, not a direct pin a patch bump can move; the dry-run leaves zip at 6.0.0). No Dependabot PR fixes it. The libduckdb-sys 1.20 line drops zip entirely, closing the advisories by removal — structural either way. | AL, AU | structural-replacement |
| 8 | zvariant 5.15.0 — audit RUSTSEC-2026-0370 (unmaintained), zbus stack, transitive only; patch bump → 5.15.1 does not clear the warning. | AU | structural-replacement |
| 9 | zvariant_derive 5.15.0 — audit RUSTSEC-2026-0372 (unmaintained). Same stack, same reasoning as subject 8. | AU | structural-replacement |
| 10 | zbus_names 4.3.4 — audit RUSTSEC-2026-0371 (unmaintained); patch bump → 4.3.5 does not clear it. | AU | structural-replacement |
| 11 | zbus 5.19.0 — stack parent of subjects 8–10 (via rfd → ashpd, tray-icon → ksni, notify-rust, behind the `native-ui` feature). No advisory ID of its own and no manifest names it; the census names the zbus / zvariant / zbus_names trio as needing structural replacement, not a bump. | AU (as stack member) | structural-replacement |
| 12 | notify-rust — PR #133 proposes 4.18.1 → 4.18.2. No advisory of its own. Its zbus-stack membership does not change this subject's class: the bump is patch-only; the warning belongs to subjects 8–11. | PR | patch-only |
| 13 | objc2 — PR #131 proposes 0.6.4 → 0.6.5; the lockfile holds a second copy, 0.5.2, whose patch move is 0.5.2 → 0.5.3 (the `@version` form of `cargo update -p` is required). | PR | patch-only |
| 14 | rfd — PR #128 proposes 0.15.4 → 0.16.0: a 0.x minor (breaking) bump needing a `Cargo.toml` change. | PR | transitive-major |
| 15 | tray-icon — PR #134 proposes 0.25.1 → 0.26.1: same 0.x-minor shape as subject 14. | PR | transitive-major |
| 16 | base64 — PR #126 proposes 0.22.1 → 0.23.1: same 0.x-minor shape as subject 14. | PR | transitive-major |
| 17 | actions/upload-artifact — PR #124 proposes 4 → 7: a GitHub Action major. *(Class inferred from the version delta under the class definitions; the census records assign it no class.)* | PR | transitive-major |
| 18 | actions/setup-node — PR #125 proposes 4 → 7: a GitHub Action major. *(Class inferred, as subject 17.)* | PR | transitive-major |
| 19 | pnpm/action-setup — PR #130 proposes 4 → 6: a GitHub Action major. *(Class inferred, as subject 17.)* | PR | transitive-major |
| 20 | trufflesecurity/trufflehog — PR #129 proposes 3.97.9 → 3.99.0: a non-cargo tool minor, not lockfile-patch-resolvable. *(Class inferred, as subject 17.)* | PR | transitive-major |
| 21 | taiki-e/install-action — PR #127 proposes 2.87.23 → 2.87.26: a patch-delta Action update. *(Class inferred from the patch-only version delta.)* | PR | patch-only |
| 22 | ureq — appears **only** as a dry-run offer (→ 3.5.1). No advisory, no Dependabot PR; duckdb-internal plumbing via libduckdb-sys → duckdb, not app code; the offered move is additionally a minor bump dragging ureq-proto 0.6 → 0.7. Dropped with stated reasons. | dry-run only — none of the three | drop |
| 23 | serde_json — appears **only** as a dry-run offer (→ 1.0.154). No advisory, no Dependabot PR. Dropped with stated reasons. | dry-run only — none of the three | drop |
| 24 | Release Please PR #120 (0.2.2) — an open PR that is not a dependency finding at all. | PR | **NOT-A-FINDING** — named as excluded, never classified into a bump class |

Provenance note: subjects 1–16 and 22–23 are fully sourced (identity, versions/IDs, and class all in the census records). Subjects 17–21 are sourced for identity and versions, with class **inferred** from the version delta under the class definitions — they are cited above with that mark, never as fully sourced. The remaining ~80 dry-run offers are **not** classified: per Step 4 they are deferred, not dropped. Yanked-crate warnings and post-census arrivals are outside this census and are not findings here.

## Second structural fixture — rkyv / RUSTSEC-2026-0235

- **Advisory:** RUSTSEC-2026-0235 — rkyv < 0.8.17, out-of-bounds read via shared-pointer validation skipping metadata; the 0.7 series is unsupported upstream and the fix exists only in rkyv 0.8.17+.
- **Why structural, not a bump:** rkyv 0.7.46's sole dependent was rust_decimal 1.41.0 (an optional dependency behind its `rkyv` feature, enabled by no consumer). No bump of rkyv itself within its line fixes it; the finding clears only when the parent edge moves and the rkyv cluster **leaves the tree**. Classifying it patch-only because the clearing command is a single `-p` update of the parent is wrong: the class describes what happens to the finding's crate, and rkyv is removed, not patched.
- **The clearing move:** `cargo update -p rust_decimal --precise 1.43.0` — rust_decimal 1.41.0 → 1.43.0, lockfile-only (both parents' caret ranges already admit it); 1.43.0 deletes the rkyv 0.7 dependency outright.
- **Structural fallout:** 13 packages removed outright (rkyv, rkyv_derive, bytecheck, bytecheck_derive, rend, ptr_meta, ptr_meta_derive, seahash, bitvec, funty, radium, tap, wyz) + 3 cluster-only versions shed; package count 547 → 531; audit delta exactly RUSTSEC-2026-0235.
- **Documented record:** the 2026-11-09 NeuroStrata record (draft PR #47, commit `3f175bd`).
- **Attribution caveat:** the **ladybug-rust attribution is unverified** — the mining ledger carries the case as "(rkyv/RUSTSEC-2026-0235, ladybug-rust, 2026-11-12)", but a first-hand check found no rkyv entry and no such bump in the 2026-11-12 ladybug research tree, and no record of the alleged merge commit. The fixture's class and mechanism stand; its ladybug-rust provenance is stated as unverified, never as established.

**Classification: structural-replacement.**

## Output shape

Per triage round, report in this order: (1) the three inventory counts and how they were crossed; (2) the full classification table — every subject, its inventories, its class, and any not-a-finding exclusions named; (3) only then, bump proposals grouped by class (patch batch, individual transitive-majors, structural follow-ups), with `drop` subjects listed as dropped with their reason (no advisory, no PR) and the unlisted dry-run remainder recorded as deferred.
