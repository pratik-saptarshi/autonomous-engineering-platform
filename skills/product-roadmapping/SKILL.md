---
name: product-roadmapping
description: Use when turning a feature list, source plan, or product idea into a staged roadmap that agents will execute against — when capabilities need evidence-checking, features need acceptance criteria and eval levels, stages need exit gates, or open decisions block later stages. Also use when a roadmap draft may have paraphrased, re-cut, or silently dropped parts of its source plan.
---

# Product Roadmapping

## Overview

A roadmap is an argument: every feature traces to a capability, every capability to evidence, every stage to an exit gate that passes on named evidence or not at all. Elaborate progressively — capability → feature → use case → acceptance criteria (AC) → function/task → eval level — in a machine-readable traceability matrix, and depth-grade the work: detail is earned by nearness, not spread evenly.

**Core principle:** Structure is cheap to fake and expensive to trust. Lints prove the matrix is *connected*; only independent re-verification against the sources proves it is *true*.

## When to Use

- A source plan, feature list, or research findings must become an execution-grade roadmap with stages and gates.
- Multiple agents (a panel) will elaborate the roadmap, so hand-offs need a shared, checkable artifact.
- Open decisions or rulings block later stages and must be tracked, not assumed away.
- A previous roadmap or brief may have drifted from its source (paraphrased models, re-cut phases, dropped features).

When NOT to use: a single phase small enough for one `writing-plans` pass; a roadmap the author will execute inline with full context; pure brainstorming with no execution downstream (use `brainstorming` / `egm-brainstorm`).

## The Laws

These override convenience at every stage below.

1. **Quote normative sources verbatim; never paraphrase a model from memory.** Stage scopes, feature IDs, field names, and decided values are *copied* from the source plan, then the copy is grep-verified (every source ID appears in the roadmap; every roadmap ID exists in the source or is logged as discovered/removed). A paraphrase that changes a shape — a renamed field, a re-cut phase, a dropped feature — is a defect even when it reads better. If a re-cut is genuinely right, log it as an explicit ruling in the disagreement log; never label your own edit a "seed" from the source.
2. **Capability status has three states.** `VERIFIED` — evidence exists and was opened. `UNVERIFIED` — claimed, no evidence found. `DEFINED` — design-first: the evidence proves the thing does *not* exist yet, and a named design document is its authority. A two-state taxonomy mechanically blocks every define-and-build capability, which is most of what a roadmap exists to create. Only `VERIFIED` and `DEFINED` capabilities may seed features; `UNVERIFIED` rows are listed, never built on.
3. **Open rulings are structural, not greppable.** Every matrix row carries a `depends_on_ruling` field (empty = none). A stage with any unresolved entry is labelled `BLOCKED-ON-RULING` and is elaborated only to feature level — no ACs, no gate criteria — until the ruling lands. Token greps for the ruling's name do not satisfy this law: an AC can assume a ruling's answer without ever naming it (see Law 4's semantic check).
4. **Lints are necessary and decorative alone.** Pair every structural check with semantic verification: an agent who did not author the rows re-opens the cited evidence and confirms it says what the row claims — 100% of capability rows and of identity/safety-bearing rows, plus a sample of at least 1 in 4 of the remaining rows, selected by the verifier (spread across stages), never by the author. Every AC carries a mandatory **failure witness**: the observation that would *fail* it. An AC whose author cannot state its failure witness is prose, not a criterion.
5. **Decision briefs outrank elaboration.** When an open ruling blocks a stage, the highest-value artifact is the brief — options, a recommendation, and the cheapest empirical test that could decide it — not more detail around the block. Produce briefs before elaborating anything downstream of the ruling.
6. **Probe the environment before writing criteria that depend on it.** Carriers, sandboxes, daemons, quotas, tool availability: check the actual environment and record the probe results as evidence. A stage AC that assumes an unprobed environment fact is `UNVERIFIED` work wearing a criterion's clothes.
7. **Gate law.** An exit gate passes only when its named evidence artifacts *exist and are cited* — never on narrative, status meetings, or lint output alone. Gates are ruled by the human owner; the panel recommends, with adversarial verdicts attached. No role grades its own output, and the synthesizer who assembles the roadmap does not also rule its gates.

## The Method

### Stage 0 — Price and scope the run

Panel economics first, cheapest mechanism first. Write down: roles × rounds, a wall-clock/token budget, a retry cap per round (default 2 — a round whose exit check fails twice escalates to the owner instead of looping), and the execution mode.

- **Round-gated** (default): owner checkpoints after capability map, feature set, and final assembly.
- **Standing panel**: re-convene at each stage boundary during implementation (see Maintenance).
- **One-shot** (all rounds, owner sees only the result): **forbidden while any load-bearing ruling is open** (Law 3) — a ruling is load-bearing if any stage or row carries it in `depends_on_ruling` — it delivers the briefs and the roadmap built around their absence in the same package.

**Exit check:** budget, mode, and retry cap are written in the run's working papers; mode is legal under Law 3.

### Stage 1 — Baseline: sources, environment, hygiene

- Inventory the normative sources (source plan, research findings, landed code, decision records). Assign each a short **alias**; artifacts cite aliases, never raw filenames — a source's filename may itself leak what a public artifact must not contain.
- Probe the environment per Law 6; record results as evidence rows.
- Fix the hygiene rule for the run: which artifacts may become public, and the banned-token grep every artifact passes before it leaves the working papers.

**Exit check:** every source has an alias and a location that resolves; environment probes are recorded, not asserted.

### Stage 2 — Capability map

One row per capability: ID (copied from source, Law 1), mechanism in one sentence, evidence pointer (alias + section), status (`VERIFIED` / `UNVERIFIED` / `DEFINED` + the design document that authorizes it). Splits, merges, and retirements are allowed — each logged with its evidence.

**Exit check:** 100% of rows re-verified semantically by a non-author (Law 4); every `UNVERIFIED` row is explicitly listed in the output.

### Stage 3 — Decision briefs for blocking rulings

For each open ruling that any later stage depends on: options (≥2), a recommendation, the cheapest empirical test that could decide it, and the list of rows/stages blocked on it. Briefs go to the owner *now*, not bundled with the finished roadmap.

**Exit check:** every `depends_on_ruling` value named anywhere in working papers has a brief; blocked stages are labelled `BLOCKED-ON-RULING`.

### Stage 4 — Feature set and discovery

Features trace to `VERIFIED` or `DEFINED` capabilities only. Discovery loop for candidates the source missed — a candidate enters only with all three legs: (1) a named consumer or workload, (2) an evidence pointer, (3) a kill criterion stated up front. Failures are recorded as **considered-and-killed** with the reason: the roadmap shows its negative space. Dropping or renaming a source feature requires a logged synthesizer ruling, never a silent edit (Law 1).

**Exit check:** traceability lint (Stage 8's, run early on the rows that exist so far) passes; considered-and-killed list is non-empty, or the panel states on record why killing nothing is credible.

### Stage 5 — Use cases and acceptance criteria

Per feature: actors, preconditions, main flow, failure flows, observable outcome — then ACs. Features in a `BLOCKED-ON-RULING` stage are skipped entirely — no use cases, no ACs — until the ruling lands (Law 3). Each AC is mechanically checkable (a command, a test name, or a measurement with a threshold) **and** carries its failure witness (Law 4). **Eval level is assigned here, by the AC's author** — it is part of authoring the criterion, not a separate mapping pass:

| Level | Meaning | Discharges with |
|---|---|---|
| L0 — Conformance | Deterministic corpus/unit proof; bit-for-bit where identity is involved | Corpus cases, golden values |
| L1 — Integration | Component-against-component behaviour | Integration tests, recovery drills |
| L2 — Adversarial / property | Fuzz, mutation, break-the-behavior: the check is shown to bite | Fuzz corpora, mutation reports |
| L3 — Field / pilot | Real consumer workload, supervised, outcomes recorded | Pilot run report |

**Floor rule:** identity- and safety-bearing ACs (digests, identity, fail-closed behaviour, confinement) require **L2 minimum**; a stage containing them cannot exit on L0/L1 evidence alone. When in doubt whether an AC is safety-bearing, it is.

**Exit check:** every feature outside a blocked stage has ≥1 use case, every use case ≥1 AC, every AC has a failure witness and an eval level; checkability lint passes.

### Stage 6 — Function/task mapping (depth-graded)

Map ACs down to functions/modules and implementation tasks — **only as deep as nearness justifies**:

| Horizon | Depth |
|---|---|
| Next stage | Full function/task mapping; tasks sized for one implementer + one reviewer |
| Stage after next | Module-level mapping only (components, interfaces, no task list) |
| All later stages | Feature-level only; mapping is deferred until they become "next" |

Big-up-front task mapping for distant stages is waste with extra steps: later stages will be re-mapped against landed code, which is strictly better ground truth.

**Exit check:** depth table honoured — a task list for a non-next stage is a finding, not thoroughness.

### Stage 7 — Stage assembly and exit gates

Assemble stages in dependency order. Each stage ships: scope (feature IDs), its discrete ACs, and ≥1 exit gate in the **gate register**: gate ID, the evidence artifacts that discharge it (named in advance), the eval floor it enforces, and its ruling owner (the human). `BLOCKED-ON-RULING` stages appear with their label and their brief, not with drafted gate criteria.

**Exit check:** every non-blocked stage has ≥1 gate whose evidence is named; every blocked stage names its ruling; gate register is complete.

### Stage 8 — Verification pass

Run both halves — neither substitutes for the other:

- **Structural lints (scripted, must actually run):** over the machine-readable matrix — every F → ≥1 non-`UNVERIFIED` C; every F outside a blocked stage → ≥1 UC (blocked-stage features have none, by Law 3); every UC → ≥1 AC; every AC → exactly one eval level, and a mapping at its horizon's depth (≥1 task for the next stage, ≥1 module for the stage after, none yet for later stages — absence there is correct, not an orphan); every stage → ≥1 gate or a `BLOCKED-ON-RULING` label; ID copy-check against the source (Law 1); banned-token grep (Stage 1 hygiene rule).
- **Semantic verification:** sampled re-verification per Law 4, plus the review questions lints cannot ask: *Does any AC assume an open ruling's answer without naming it? Does any evidence pointer fail to say what its row claims? Is any AC's failure witness actually observable?* Then run the roadmap through `planning-wringer` (adversarial panel + independent review) before handoff.

**Exit check:** lint output attached; semantic sample documented with its rate; every P1 from the wringer is folded in or overruled in writing by the synthesizer with a ground-truth citation.

## The Traceability Matrix

The matrix is the product; human-readable roadmaps are renderings of it. Keep it machine-readable (JSON or CSV) beside any HTML/document rendering, under a stable ID scheme:

`C-nn` capability · `F-nn` feature · `UC-nn` use case · `AC-nn` criterion · `FN-nn` function/task · `G-nn` gate · `R-nn` ruling/brief

Required fields per row: `id`, `title`, `links` (upstream IDs), `evidence` (alias + section), `depends_on_ruling` (Law 3). AC rows additionally require `check` (the mechanical check), `failure_witness`, `eval_level`. Capability rows require `status`. The lint tooling that checks the matrix is in-scope working papers — a lint that exists only as a bullet in a plan is not a lint (Stage 8).

## Panel Composition

Full panel (one fresh agent per role; no role grades its own output):

| Role | Owns |
|---|---|
| Capability Mapper | Stage 2 capability map |
| Feature Developer | Stage 4 feature specs + discovery |
| Use-Case + Acceptance Analyst | Stage 5 — one role, deliberately: splitting use cases from their criteria severs the failure witness from the flow that produces it |
| Decomposer | Stage 6 function/task mapping |
| Synthesizer (judge) | Stage 7 assembly, disagreement log, cross-role rulings |
| Adversarial seats (outside the panel) | `planning-wringer` personas — Feasibility, Risk, Devil's Advocate — at Stage 8 and at stage boundaries during execution |

There is **no separate Eval Mapper role**: eval-level assignment belongs to acceptance authoring (Stage 5), where the criterion's substance is in front of the author.

**Lean variants** (prefer these; escalate to the full panel only when the roadmap gates major downstream spend):

- **Solo + reviewer:** one agent runs Stages 1–7, a fresh agent runs Stage 8's semantic half. Fits a single product with a decided source plan.
- **Trio:** Capability Mapper, Use-Case + Acceptance Analyst, Synthesizer; the Synthesizer also decomposes. Fits multi-stage roadmaps with open rulings.
- Merge order when cutting: Decomposer folds into Synthesizer first; Feature Developer folds into Capability Mapper second. Never merge the adversarial seats into the panel.

## Maintenance

- **Versioning:** the matrix carries a version; amendments are new versions with a changelog of row-level diffs (added / changed / retired + why), never silent edits.
- **Amendment trigger:** when a stage lands differently than mapped, amend the matrix *before* the next stage's elaboration begins — downstream depth-grading (Stage 6) always re-derives from landed reality.
- **Freshness rule:** if a stage starts more than ~90 days after the roadmap version that mapped it, or after any intervening stage landed, re-verify that stage's capability evidence and environment probes before elaborating it. Evidence rots; the roadmap does not announce when.

## Quick Reference

| Question | Answer |
|---|---|
| Can this capability seed a feature? | Only if `VERIFIED` or `DEFINED` (Law 2) |
| The source plan's shape looks wrong | Log a re-cut ruling; never silently paraphrase (Law 1) |
| A stage depends on an open ruling | Brief first; stage labelled `BLOCKED-ON-RULING`, feature-level only (Laws 3, 5) |
| Lints all pass | Half done — semantic sample + review questions remain (Law 4) |
| How deep do I map a stage three phases out? | Feature-level. Tasks are for the next stage only (Stage 6) |
| Who rules a gate? | The human owner, on named evidence that exists (Law 7) |
| Cheapest sufficient panel? | Solo + reviewer; grow only on evidence of need (Stage 0) |

## Common Mistakes

- **Paraphrasing the source and labelling it "seed."** The canonical failure: a draft re-cuts the source plan's phases and drops two features while attributing the result to the source. Caught only by ID copy-checks (Law 1), never by reading — the paraphrase reads *better* than the source.
- **Inventing a model from prose.** A brief that restates a record/API model from a plan's prose instead of quoting the normative artifact will invent fields that exist nowhere. Quote the artifact; grep the quote.
- **Two-state capability taxonomy.** "No evidence → cannot seed" sounds rigorous and makes design-first work impossible. The third state (`DEFINED`) is the roadmap's whole reason to exist.
- **Grepping for undecided values.** A token scan certifies that the ruling's *name* is absent, not that its *answer* wasn't assumed. Structure (dependency field) + semantic review questions, or nothing.
- **A matrix that is fully linked and fully invented.** Link-existence lints pass on fiction. Sampled re-verification by a non-author is the only check that touches truth.
- **ACs without failure witnesses.** "Replay completes successfully" cannot fail, therefore cannot pass either. If nothing observable would fail it, it is not a criterion.
- **Big-up-front elaboration.** Full task lists for stage 4, written before stage 1 lands, are fiction with IDs. Depth-grade (Stage 6).
- **Panel as default.** Seven roles × five rounds to produce a document is a budget decision, not a virtue. Price it (Stage 0); the lean variants exist because the full panel is usually overkill.
- **Gates passed on narrative.** "The team feels the store is solid" is not evidence. Named artifact, existing, cited — or the gate has not passed (Law 7).
- **Citing private sources by filename.** The citation itself can leak the thing the hygiene rule protects. Aliases (Stage 1), always.

## Worked Example (one, deliberately brief)

A replay-capability roadmap run (2026-11) supplied most of this skill's scar tissue: its v0 draft silently re-cut the source plan's phases and dropped two features while calling them "seed" (Law 1); its two-state capability taxonomy would have blocked the replay engine itself, which exists only as a design (Law 2); its undecided-value scan was a token grep (Law 3); and its 7-role × 5-round panel was never priced (Stage 0). The same project's Phase 0 — one planner, per-task implementer/reviewer pairs, an executable corpus as ground truth — is the lean pattern the variants above generalize.
