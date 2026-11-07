# Goldfish Review — EGM Adoption Strategy (AEP) — Round 1

- **Target:** `/home/hatch/workspace/plans/2026-11-06-egm-adoption-aep.md` (lines 1–337, full file)
- **Date:** 2026-11-06
- **Loop:** `egm-review-loop`, round 1, direct dispatch (flat swarm, no synthesizer)
- **Standards:** feature-spec-standard (design_critic, structural, comprehension),
  implementation-readiness-standard (implementation_readiness),
  zoom-out-standard (zoom_out)
- **GoldfishContext:** `2026-11-06-egm-adoption-neurostrata.md`,
  AEP `skills/README.md`, AEP repo clone (read-only)

## Round verdict: NOT CLEAN

3 Blockers, 35 Majors, 27 Nits. All 5 reviewers completed; none not run.
A round is clean only when no reviewer raises a Blocker or Major finding
that is not settled. This round is not clean. No fixes were applied in this
round; the decision gate belongs to the user (egm-resolve is a separate step).

## Per-reviewer status

| Reviewer | Standard | Status | Blocker | Major | Nit |
|---|---|---|---|---|---|
| design_critic | feature-spec | completed | 0 | 7 | 3 |
| structural | feature-spec | completed | 0 | 5 | 4 |
| implementation_readiness | implementation-readiness | completed | 1 | 8 | 8 |
| comprehension | feature-spec | completed | 2 | 10 | 9 |
| zoom_out | zoom-out | completed | 0 | 5 | 3 |
| **Total** | | **5 completed, 0 not run** | **3** | **35** | **27** |

## Findings — Blockers (3)

### comprehension-1-1 — Blocker — D3 adaptations vs. Path 1 plugin install are irreconcilable
Lines 79, 84–92, 159–178. D3 says the three adaptations are "applied
identically in both environments" and requires every adapted `SKILL.md` to
gain the Muse routing line and bundle-relative path resolution. But §4.2
Path 1 is a verbatim upstream plugin install (`git clone …; muse plugins
install ./elephant-goldfish-model --scope user; muse plugins approve egm`)
with no adaptation step, no `skill.yaml` generation, and no place where an
adapted copy would live. A fresh reader cannot tell whether Path 1 skips D3
entirely (contradicting "identically"), applies D3 to the cloned tree before
install (contradicting D2/D3's "pristine bundle is never edited"), or applies
it somewhere else. The preferred install path for Environment A cannot be
executed as written; the central "one adoption, two installations" claim
(lines 20–21) fails for it.

### comprehension-1-2 — Blocker — Elephant / synthesizer / dispatch never mapped to a concrete actor
Lines 25–28, 137–149, 244–251. The model is defined abstractly ("Elephant
(one agent holds context and drafts the spec)"), but the document never maps
Elephant / synthesizer / parent to a concrete actor in either environment. D7
introduces "dispatch reviewers directly from the parent (direct dispatch)
instead of through the synthesizer" (lines 146–147) without ever defining
the synthesizer; §5.3 says "Wait for actual completion before synthesizing"
(lines 247–248) without saying who synthesizes, in what form, or where the
synthesis goes. `subagent.spawn` is named as the dispatch mechanism (lines
18, 223, 244) but no invocation form, brief template, or argument list is
given. A fresh reader can paraphrase the idea of fresh-eyes review but
cannot run one review loop from this document alone.

### implementation_readiness-1-1 — Blocker — No exact file-change list; Phase 2 write allowlist cannot be enforced
Lines §4 (D4, 94–113), §6 Phase 2 (278). The standard requires an explicit
list of exact repository-relative file paths to be created, modified, or
deleted. The plan gives only directory patterns
(`reference/elephant-goldfish-model/`, `skills/egm-*/`, "scope/manifest/
attribution updates"). The bundle's exact file inventory at the pinned SHA
is never enumerated, the seven wrapper dir names are only inferable, and at
least one required modified file is omitted entirely —
`.github/workflows/ci.yml` (see implementation_readiness-1-7). An implementer
cannot produce a bounded change or an allowlist from this.

## Findings — Majors (35)

### design_critic-1-1 — Major — `vendor-integrity` coverage overstated; Phase 2 omits the required CI edit
Lines 94–106 (D4), 278; AEP `.github/workflows/ci.yml` lines 73–132. D4
states the bundle is "Covered by the `vendor-integrity` CI job". Verified:
the job is nine hand-written, copy-pasted `run:` blocks, one per
`reference/` tree, each doing `sha256sum -c` plus an unlisted-files check.
Adding `reference/elephant-goldfish-model/` requires a tenth block in
`ci.yml`, and Phase 2's scope list does not mention `ci.yml` at all. If the
edit is missed, the new bundle ships with zero integrity verification while
the document claims coverage — silent non-coverage.

### design_critic-1-2 — Major — `skills-freshness` does not do what D4 claims; generated `skill.yaml` is outside the gate
Lines 100–113 (D4), 259–270 (§5.4). (a) The scope file's own header states
the gate proves only that the repo `skills/` tree equals the manifest
generated from the repo tree after the last sync from live — "never a
freshness claim against the live tree (CI cannot see live)". It cannot detect
wrapper↔upstream-bundle drift or wrapper↔local-`custom-skills` drift. (b)
`[exclude-paths]` contains a bare `skill.yaml`, so D3's generated
`skill.yaml` — the file that makes each skill loadable — is entirely
excluded from the manifest. D4's "Covered by the `skills-freshness` gate" is
true only for the adapted `SKILL.md`.

### design_critic-1-3 — Major — "One adoption, two installations" has no canonical source or sync mechanism
Lines 20–21 (§1), 239–240 (§5.2), 269 (§5.4 step 4). §5.2 calls
`~/workspace/egm/` "the single source of truth for personas and standards",
but the local bundle lives outside any repository (no version control,
backup, or sync script named), while the AEP wrappers live in git. No
direction of sync, owner, cadence, or procedure for propagating a fix in
either direction is named. §5.4 step 4 ("byte-identical (modulo the path
prefix…)") is not an executable check, and no normalisation procedure is
defined. Dual-write drift is designed in, not guarded against.

### design_critic-1-4 — Major — D3 path-resolution adaptation underspecified; does not cover persona-internal references
Lines 77–92 (D3); verified against `~/workspace/egm/skills/egm-review/SKILL.md`,
`agents/zoom_out.md:44`, `agents/synthesizer.md:37–38`,
`resources/README.md:16`. (a) D3 gives no rewriting rule: which literal
strings map to what in each environment, by what tool, with what
verification. The only verification, `diff -rq` bundle vs. upstream (§5.4
step 2), checks the pristine bundle — not the adapted copies' links. (b)
Bundle-relative references also live inside the pristine personas and
standards (`agents/zoom_out.md:44` references
`resources/document_standards/zoom-out-standard.md`;
`agents/synthesizer.md:37–38` defines the resolution directories). If the
harness resolves relative paths from the invoking skill's directory, those
references break, and D3's "pristine bundle is never edited" forbids fixing
them in place. (c) The Muse routing line (lines 84–86) is quoted without a
path, though `docs/muse.md` lives at different absolute locations per
environment.

### design_critic-1-5 — Major — Principal risk (D6) has procedural-only mitigation over an unverified mechanism
Lines 124–135 (D6), 292–296 (§7). The mitigation is "brief reviewers
read-only… do not hand reviewers write tools", but the document never
establishes that `subagent.spawn` in Environment B (or any Environment A
harness) can actually withhold write tools — D6 itself concedes Muse has no
tool allowlist. There is no fail-closed control: no sandbox, no pre/post
diff or `git status` check, and "verify outputs" is undefined. A reviewer
that edits the working tree or touches memory services is detectable only
after the fact, if at all.

### design_critic-1-6 — Major — No cost, quota, or loop-bound economics for the review loop
Lines 242–257 (§5.3), 272–284 (§6). The adoption sets no iteration cap, no
per-run subagent-count or token budget, no timeout values, and no escalation
path on non-convergence. The upstream skill mentions cap/converge, but the
plan never operationalises the cap value or who sets it, and no phase gate
measures cost. The most expensive behaviour — repeated full-context re-reads
by fresh reviewers — is unbudgeted.

### design_critic-1-7 — Major — No Goals or success metrics; Alternatives Rule only partly met
Lines 5–21 (§1), 108–113 (D4), 272–284 (§6), 302–310 (§8). (a) No Goals
section and no measurable success criteria anywhere; phase gates are binary
checklists ("gate-scan pass", "CI green", "drift report produces a dated,
accurate finding or a clean bill" — "accurate" undefined, no judge named).
(b) Only one alternative is evaluated (D4's shared `skills/egm-agents/` +
`skills/egm-resources/` dirs). Never evaluated: do-nothing / extend
`grilling` + `roundtable_review` + the Ralph verifier; git submodule vs.
vendoring; Path 1 plugin install for AEP instead of vendoring; adopting a
subset of skills vs. all seven.

### structural-1-1 — Major — Missing required header: "Alternatives Considered"
No such heading anywhere in lines 1–337; nearest content is §3 D4 lines
108–114, §4.2 vs §4.3 (lines 159, 180), §4.4 decision matrix (lines
194–201), §9 item 4 (lines 320–323). The standard's Alternatives Rule makes
evaluation of alternatives mandatory. The document evaluates alternatives
only in fragments — a fresh reader cannot locate a single consolidated
evaluation, and rejection rationales are not gathered in one place.

### structural-1-2 — Major — Missing required header: "Goals & Non-Goals" (Goals half missing)
§8 "Non-goals" lines 302–311 only; no "Goals" heading or goals list
anywhere. The standard requires both. Goals must be inferred from §1
"Purpose" (lines 5–22) and §6 "Rollout" (lines 272–285).

### structural-1-3 — Major — Missing required header: "Problem Statement" (renamed, not headed)
§1 "Purpose" lines 5–22. The standard requires a "Problem Statement"; the
document covers motivation ("design-before-implementation becomes a loadable
skill rather than an implicit habit", lines 7–10) under a different label.

### structural-1-4 — Major — Missing required header: "Proposed Architecture" (content present, heading absent)
No such heading; architectural content is spread across §3 "Design
decisions" (lines 58–150), §4 (lines 151–214), and §5 (lines 216–270). No
single architectural overview section exists.

### structural-1-5 — Major — Missing required header: "Risks & Mitigations" (only a security subset is headed)
§7 "Security notes" lines 286–300; D6 read-only caveat lines 124–136. The
standard's "Risks & Limits" requires explicit failure modes, security
implications, scalability limits, and mitigations under "Risks &
Mitigations". The document heads only security notes; failure modes /
scalability limits have no headed section, and the principal risk (D6) is
stated in §3 and repeated in §7 rather than in a risks section.

### implementation_readiness-1-2 — Major — `skill.yaml` generation schema unspecified
Lines 81–83 (D3 item 1), 102–107, 232–235. "Generate one per skill from the
existing frontmatter (name + description)." The AEP `skill.yaml` format
(verified, e.g. `skills/archify/skill.yaml`) carries `name`, `title`,
`description`, `category`, `include_in_prompt` — the plan specifies values
for only two fields and never says which other fields are required, what
`category`/`title`/`include_in_prompt` should be, or how the file is
validated. Further, the scope file's `[exclude-paths]` excludes the bare
name `skill.yaml` from the manifest, so the generated files are covered by
**neither** gate the plan cites.

### implementation_readiness-1-3 — Major — D3 path-resolution adaptation is not executable as written
Lines 87–90 (D3 item 3), 102–105, 185–189, 232–234. (a) The plan never
enumerates which path references inside each of the seven `SKILL.md` files
must be rewritten, nor the exact replacement strings. (b) Environment B is
told to use "absolute paths to `~/workspace/egm/`" — `~/workspace/egm/` is
not literally an absolute path; the implementer must choose between
`~/workspace/egm/...` and `/home/hatch/workspace/egm/...`. (c) The AEP
wrapper resources path is given as "`.../resources/document_standards/`"
with the prefix elided. (d) Environment A Path 2 (§4.3) uses an
`<install-root>` that is never defined — no default value, no example — and
the relative resolution from `<install-root>/skills/egm-*/` to
`<install-root>/egm/` is never stated.

### implementation_readiness-1-4 — Major — §5.4 step 2 verification command cannot produce its stated expectation
Lines 261–263. "`diff -rq` bundle vs. upstream at the pinned SHA (expect
zero differences outside the adaptation layer)." Two defects: (i) no command
is given to fetch upstream at the pinned SHA; (ii) the bundle is a **subset**
of upstream (§2: `site/`, `scripts/`, tests, per-host manifests are not
vendored), so a bare `diff -rq` against a full upstream clone will report
`Only in <upstream>: site`, `scripts/`, etc. — "zero differences" is
unachievable as specified. No exclusion list is given, and the adaptation
layer lives in `custom-skills/`, not in the bundle, so "outside the
adaptation layer" has no meaning for this diff.

### implementation_readiness-1-5 — Major — §5.4 step 4 sync check has no executable procedure
Lines 268–270. "Sync check: local `custom-skills/egm-*` vs. AEP
`skills/egm-*` wrappers byte-identical (modulo the path prefix:
`~/workspace/egm/` locally vs.
`../../reference/elephant-goldfish-model/` in the repo)." No command or
normalization is specified. A plain `diff -r` fails on every path-reference
line. The implementer must design the normalization themselves, including
deciding whether `~` vs. the expanded home path counts as a difference.

### implementation_readiness-1-6 — Major — No test plan; the core risk (broken path resolution) has no automated check
Lines §4.5 (204–215), §5.4 (260–270), §6 (273–284). The standard requires
specific test cases (happy path and edge cases). The plan contains only
manual acceptance steps. There is no test case asserting that every
`agents/...` and `resources/...` reference in each adapted `SKILL.md`
resolves to an existing file at the installed location, no `skill.yaml`
parse/schema validation, and no check that wrapper `skill.yaml` names match
frontmatter. The exact failure mode D2 warns is "broken by construction"
would only surface in the human pilot.

### implementation_readiness-1-7 — Major — Vendor-integrity coverage claim is false as written; CI change and manifest generation are missing
Lines 96–101, 278. Verified in the repo: `.github/workflows/ci.yml`
`vendor-integrity` is a series of **hardcoded per-tree `run:` blocks** (one
each for `esf`, `neurostrata`, `neurostrata-ops`, `harness2`,
`security-audit-skill`, `ub-mode`, `grim-prompter`, `docs-mcp-server`,
`humanizer`) — no generic loop, so adding
`reference/elephant-goldfish-model/` requires a new block in `ci.yml`, a
file the plan never lists as modified. No command is given to generate
`.github/vendor-elephant-goldfish-model.sha256` in the required `./path`
sha256sum format, and `PROVENANCE.md`'s required fields are unspecified
(existing pattern, e.g. `reference/esf/PROVENANCE.md`, carries upstream URL,
pinned commit + subject, snapshot date, license, exclusions, purpose, and
update history). Phase 2's gate "CI green" would pass vacuously for the new
bundle without the CI edit.

### implementation_readiness-1-8 — Major — Path 1 install for non-Muse harnesses has no steps
Lines 176–177, 198–199, 205–206. "Equivalent native installs exist for
Claude Code, Codex, Cursor, OpenCode, and Antigravity (see `docs/harnesses.md`
and the per-host manifests in the repo root)." No install command, install
path, or verification command is given for any of the five; the decision
matrix assigns them all "Path 1 (native install)" and §4.5 step 1 defers to
"the harness equivalent" of `muse plugins validate`, also undefined per
harness. Only the Muse path has concrete commands.

### implementation_readiness-1-9 — Major — §5.3 dispatch lacks executable parameters
Lines 244–252. "Reviewers: `subagent.spawn` with the persona file path and
the verbatim prompt in the brief" — the "verbatim prompt" is never quoted or
located. "Require the reviewer to read persona + target + every supplied
standard before returning findings (a missing read is an incomplete review…)"
— no enforcement mechanism is specified. "Wait for actual completion before
synthesizing; propagate failures and timeouts" — no timeout value, no
failure-handling procedure. "Tool unavailability is not approval — ask one
plain-text question" — the gate question text is never given. No
`subagent.spawn` tool-restriction parameter is specified for the D6 "do not
hand reviewers write tools" mitigation.

### comprehension-1-3 — Major — Path arithmetic in D2 is wrong/confusing
Lines 71–73. "Skills resolve `agents/` and `resources/` relative to the
plugin root (three parents above each `SKILL.md`)." A skill file at
`skills/<skill>/SKILL.md` reaches the plugin root with two `..` segments
(`../../agents/`), as D4 itself uses
(`../../reference/elephant-goldfish-model/agents/`, lines 103–105). "Three
parents" does not match the document's own path example.

### comprehension-1-4 — Major — SkillSpector gate / `scan-gate.sh` invoked but never explained
Lines 115–122, 190–192, 261, 276–277. D5 mandates "`scan-gate.sh` on each
adapted skill dir; block on score > 50 or any HIGH/CRITICAL finding, fail
closed on scan errors," and §4.3/§5.4/§6 repeat "gate-scan" as a phase gate.
Nowhere does the document say where `scan-gate.sh` lives, how to invoke it,
what the score measures, what a HIGH/CRITICAL finding looks like, what a
"dispositioned baseline entry" contains or where it is recorded, or where
scores are recorded ("record scores," line 261 — in what file?).

### comprehension-1-5 — Major — AEP gates, manifest, scope file, `PROVENANCE.md`, `.sha256`, attribution table named, not specified
Lines 96–107, 334–337. D4 says the bundle is "Covered by the
`vendor-integrity` CI job" and wrappers by "the `skills-freshness` gate
(manifest + `.github/skills-sync-scope.txt` entries…)" and "the attribution
table in `skills/README.md`," and D1 says to "Record the SHA in the
attribution table and in the vendored tree's `PROVENANCE.md`." The document
never states what either gate checks, what a manifest entry or scope-file
entry looks like, what `PROVENANCE.md` or a `.github/vendor-*.sha256` file
contains, or what an EGM row in the attribution table should contain (the
baseline `skills/README.md` shows Source / License / Notes columns, but the
target never maps EGM onto them).

### comprehension-1-6 — Major — `skill.yaml` generation is underspecified
Lines 81–83, 235. "Generate one per skill from the existing frontmatter
(name + description)." No schema, field list, example file, or generator
command is given; it is unclear whether `license` and
`disable-model-invocation` (also named in the frontmatter list, line 82)
belong in the YAML, whether any other fields are required by the local
loader, or where the template lives. `disable-model-invocation` itself is
never explained.

### comprehension-1-7 — Major — Approval / readiness gates referenced but never defined
Lines 55–56, 209–212, 249–251. §5.3 says "preserve the skill's readiness
and section-approval gates" and "ask one plain-text question and wait for
the answer where no structured question tool exists," but the document never
says what a readiness gate checks, what a section-approval gate approves,
when either fires, or what the plain-text question should ask. §2 and §4.5
similarly mention "interactive approval gates" and approvals "simulated up
front" (lines 55, 211) without explaining what was simulated or how.

### comprehension-1-8 — Major — "Verify reviewers read the files" has no mechanism
Lines 244–248, 264–267. §5.3 requires the reviewer "to read persona +
target + every supplied standard before returning findings (a missing read
is an incomplete review, not a clean result)," and §5.4 step 3 asks an
independent subagent to verify "did reviewers actually read
persona/standards/target?" No mechanism is given for observing or proving a
read (no tool output, transcript check, or attestation is named), and D6
simultaneously says reviewers "must not retrieve conversation history or
memory" (lines 133–135) without saying how that prohibition is enforced.

### comprehension-1-9 — Major — Existing local tools used to justify scope are undefined
Lines 252–257, 306–308. §5.3's overlap decision ("EGM formalizes what
`grilling`, `roundtable_review`, and the Ralph per-iteration verifier
already do informally… keep the lighter tools for fast checks") and §8's
non-goal ("No replacement of `grilling`, `roundtable_review`, or the Ralph
verifier") name three project-specific instruments without a definition or
link for any of them. A fresh reader cannot judge the claimed overlap, the
"heavier vs. lighter" distinction, or when to choose EGM over them.

### comprehension-1-10 — Major — D6's mitigation contradicts its own premise and leaves key terms undefined
Lines 124–135, 292–295. D6 states Claude tool allowlists "do **not**
restrict Muse reviewers" and reviewers must be treated as able to write,
then mitigates with "do not hand reviewers write tools" (line 132; repeated
lines 294–295). If tool projections are unsupported on Muse, the document
never explains how a reviewer is *not* handed write tools in practice, or
what "agent tool projections," "Claude tool allowlists," "configured memory
services," and "project instructions" (line 133) mean in the Muse
environment. "Verify outputs" (line 132) is likewise vague — verify against
what?

### comprehension-1-11 — Major — Path resolution for Environment A Path 2 has no concrete example
Lines 87–91, 180–189. D3.3 defers to "see §4/§5," but §4.3 gives only the
generic template "`<install-root>/egm/`" with "paths resolved against
`<install-root>/egm/`" (lines 185–189) — no example of the actual path
string a skill should contain, unlike §5.2 which gives the concrete local
form (`~/workspace/egm/`, lines 233–234) and D4 which gives the concrete AEP
form (`../../reference/...`, lines 103–105). `<install-root>` itself is never
defined.

### comprehension-1-12 — Major — Rollout phase gates lack pass/fail criteria
Lines 276–279. Phase 0's gate is "pilot review verified by an independent
subagent" (no verification criteria beyond the unobservable read check in
comprehension-1-8); Phase 1's gate is "drift report produces a dated,
accurate finding or a clean bill" — "accurate" is judged by no one and
against nothing, and a "clean bill" (no findings) passes identically to a
finding, so the gate cannot fail. Phase 3's gate ("E2E fixture passes on the
fresh VM") is then softened by open decision 3 (lines 318–319), which asks
whether Phase 3 may "stay documented-but-unexecuted."

### zoom_out-1-1 — Major — Environment A is designed in full for an environment with no identified user (YAGNI)
Lines 13–14, 20, §4 (151–213), §6 Phase 3 (line ~280), §9 decision 3 (lines
318–319). The document designs a complete second adoption — plugin install
(§4.2), vendored-skills Path 2 (§4.3), a four-row decision matrix (§4.4,
including a "No subagent tool at all — do not adopt" row for a case in
neither environment), and per-VM-shape verification (§4.5) — covering five
harnesses the user does not run (Claude Code, Codex, Cursor, OpenCode,
Antigravity). The only environment with an identified user and machine is B
(this VM, §5.1). The document concedes the point itself in §9 decision 3:
Phase 3 may "stay documented-but-unexecuted." A section whose own author
flags it as possibly never executed should not be designed in full detail now.

### zoom_out-1-2 — Major — Root problem is asserted, not demonstrated, for AEP itself
Lines §1 (5–10), §5.3 (252–257), §9 decision 2 (316–317). §1 states the
purpose but cites no AEP design document, past review failure, or concrete
case where existing instruments fell short. §9 decision 2 leaves the Phase 0
pilot target TBD. Meanwhile §5.3 concedes EGM "formalizes what `grilling`,
`roundtable_review`, and the Ralph per-iteration verifier already do
informally" and distinguishes it only by the asserted criterion "where a
written standard and a configured reviewer panel add value" — but
`roundtable_review` already *is* a configured reviewer panel, so the
marginal value over the three existing instruments is asserted, not
evidenced. Contrast the companion NeuroStrata doc (§2), which names 14 dated
design docs and live questions (`identity_mode`, #44/#47) as concrete targets.

### zoom_out-1-3 — Major — Two installations of the same adapted content, policed by a manual byte-compare (dual source of truth)
Lines 20, §5.2 (229–240), §5.4 step 4 (268–270). The same 7 adapted skills
live in two places — local `~/workspace/custom-skills/egm-*` (paths to
`~/workspace/egm/`) and AEP `skills/egm-*` wrappers (paths to
`../../reference/elephant-goldfish-model/`) — with §5.2 calling
`~/workspace/egm/` "the single source of truth" while the AEP copy is a
second, divergent-by-path-prefix copy. The only sync enforcement is §5.4
step 4, a manual "byte-identical (modulo the path prefix)" check. No gate
enforces it: the skills-freshness gate's own scope file states its bounded
claim proves only that the repo tree equals the manifest generated from the
repo tree after the last sync from live — "never a freshness claim against
the live tree (CI cannot see live)." Vendor-integrity covers the bundle
hash, not the wrappers.

### zoom_out-1-4 — Major — All 7 skills are vendored on the plan, but only 2 have a demonstrated use; `egm-bootstrap` has no named target at all
Lines §2 table (38–43), §5.3 (256–257), §6 (274–284). The full set (2,810
lines) is scoped into the design, including `egm-bootstrap` (427 lines — the
largest skill) and `egm-drift-report`. §5.3 claims both are "genuinely new
capabilities with no local equivalent," but names no AEP codebase area
needing bootstrap documentation and no AEP design doc needing drift
detection. Phasing (§6) mitigates this only partly: Phase 1's gate is "drift
report produces a dated, accurate finding **or a clean bill**" — a clean bill
passes trivially, so the full set is never actually gated on demonstrated
need.

### zoom_out-1-5 — Major — D4's wrapper indirection is a new coupling pattern with no repo precedent and no resolve check
Lines §3 D4 (104–120), §5.4 (260–270). Wrappers under `skills/egm-*/` point
via relative paths (`../../reference/elephant-goldfish-model/agents/`,
`.../resources/document_standards/`) into the vendored bundle. Verified in
the AEP repo: no existing skill references a `reference/<tree>/` path (the
only `reference/` mentions in `skills/` are `teach`'s own internal directory
and `untangle-codebase`'s prohibition on running on vendored `reference/`
trees). This cross-tree coupling is unproven in this codebase, and no
verification step checks that the referenced paths resolve — §5.4 checks
gate scores, bundle diff, pilot execution, and cross-installation
byte-identity, but never that a wrapper's `../../reference/...` target
exists. A rename of either tree silently breaks all 7 skills.

## Findings — Nits (27)

### structural-1-6 — Nit — Inconsistent subsection numbering scheme
Lines §3 uses decision IDs `### D1`–`D7` (lines 60, 67, 77, 94, 115, 124,
137); §4 uses numeric `### 4.1`–`4.5`; §5 uses numeric `### 5.1`–`5.4`.
Sibling H2 sections use two different H3 naming schemes with no explanation.

### structural-1-7 — Nit — Appendix breaks the numbered H2 sequence
Line 325: `## Appendix — Sources (all verified 2026-11-06)` is the only
unnumbered H2, following numbered H2s `## 1.` through `## 9.`

### structural-1-8 — Nit — Inconsistent parenthetical in the §2 skills table
Lines 37–43. Line 37 reads `` `egm-brainstorm` (271 lines) ``; lines 38–43
read `` `egm-draft` (321) ``, `` `egm-review` (426) ``, etc. — the word
"lines" appears only in the first row.

### structural-1-9 — Nit — No markdown links; Appendix sources are not linkable
Lines 325–337 (Appendix) list sources as plain code spans with no URLs; the
document's only URL is a bare string inside a code block (line 164).
Citations cannot be followed or verified as links.

### design_critic-1-8 — Nit — Appendix factual error: "8 trees"
Line 337. The Appendix (headed "all verified 2026-11-06") says
"`reference/` vendor pattern (8 trees, `.github/vendor-*.sha256`)".
Verified by listing: `reference/` contains 9 trees (docs-mcp-server, esf,
grim-prompter, harness2, humanizer, neurostrata, neurostrata-ops,
security-audit-skill, ub-mode) and `.github/` contains 9 `vendor-*.sha256`
files. Correct to 9. (Same error independently found by comprehension-1-21.)

### design_critic-1-9 — Nit — Local provenance artifact specified in D1 but missing from the §5.2 layout
Lines 60–66 (D1), 227–240 (§5.2). D1 requires the pinned SHA in "the
vendored tree's `PROVENANCE.md` (AEP) / bundle README (local)". The §5.2
local layout lists only `skills/ agents/ resources/ docs/ LICENSE plugin.json`
under `~/workspace/egm/` — no README or provenance file. The local record of
the pin has no home in the layout it must live in.

### design_critic-1-10 — Nit — Environment A may never be validated; the decision is parked, not owned
Lines 312–323 (§9, decision 3), 203–214 (§4.5 step 3). Open decision 3 asks
whether Phase 3 runs on a fresh VM "or stays documented-but-unexecuted",
and §4.5 step 3 notes interactive approval gates "must be exercised by hand
the first time" with no owner or time assigned. Roughly half the document's
design surface (Environment A, §4) can therefore ship as unexecuted
documentation. Until Phase 3 runs, Environment A is specified, not validated.

### implementation_readiness-1-10 — Nit — `muse plugins validate <path>` argument unspecified
Lines 205–207. `<path>` is presumably the cloned repo path
(`./elephant-goldfish-model`), but this is never stated.

### implementation_readiness-1-11 — Nit — E2E fixture location and invocation not given
Lines 210–213. "The upstream fixture — brainstorm → draft → uninterrupted
review — run once per VM shape" — no file path, test name, or invocation in
the upstream repo is cited, and "interactive gates … must be exercised by
hand the first time" has no hand-exercise procedure.

### implementation_readiness-1-12 — Nit — Attribution-table rows unspecified; Source-column convention conflicts with D1
Lines 106–107, 278. The plan requires seven new rows in `skills/README.md`
but gives no row contents. The README's stated convention is "The Source
column names pratik-saptarshi forks wherever a fork exists" — a fork exists
(`pratik-saptarshi/elephant-goldfish-model`), but D1 mandates sourcing from
upstream, not the fork. The implementer must resolve which value goes in
Source (and what the Notes column says, e.g. adapted vs. verbatim).

### implementation_readiness-1-13 — Nit — Gate-scan recording location undefined; scan invocation incomplete
Lines 117–118, 261, 276–277. "Gate-scan all 7 adapted skills; record
scores" — no location for the recorded scores (file, PR body, install
notes). D5 names `scan-gate.sh` but not its path or the per-directory
invocation loop (the script lives at AEP `scripts/scan-gate.sh`, usage
`scan-gate.sh <skill-dir-or-file>`). §4.3 line 192 likewise says scores are
"recorded in the install notes" without defining what/where the install
notes are.

### implementation_readiness-1-14 — Nit — Persona name→file mapping given for only 1 of 10 personas
Lines 142–144 (D7). Only the example "`egm-design` is
`agents/design_critic.md`" is given; the other nine frontmatter-`name` →
file mappings must be derived by the implementer reading each
`agents/*.md` frontmatter.

### implementation_readiness-1-15 — Nit — §4.3 generic layout vs. §5.2 actual layout differ without a stated mapping
Lines 185–189 vs. 230–235. Path 2 puts skill dirs at
`<install-root>/skills/egm-*/`; Environment B puts them at
`~/workspace/custom-skills/egm-*/`. No mapping between the generic layout
and the real one is stated.

### implementation_readiness-1-16 — Nit — Phase 2 branch name not specified
Line 278. The gate requires "Conventional Commits; owner review," but no
branch name is given, although the repo's `AGENTS.md` requires
`type/scope-short-description` branches.

### implementation_readiness-1-17 — Nit — §4.1 prerequisites lack versions
Lines 158–161. `git`, `python3` (+ `pytest`), "one supported harness CLI" —
no minimum versions, although §4.5's checks (`muse plugins validate`,
named-spawn behavior) are version-sensitive per the document's own §4.5
step 4 note.

### comprehension-1-13 — Nit — Unlinked issue reference and unexplained frontmatter field
Lines 81–86. "No EGM skill routes a Muse session to `docs/muse.md`
(upstream gap #252)" cites issue #252 with no link or summary; a fresh
reader cannot check whether the one-line fix actually addresses it.

### comprehension-1-14 — Nit — Unexplained upstream behaviors
Lines 55–56, 169–176, 205–207. "Headless run with approvals simulated up
front," "chat link rendering are untested," "`marketplace add` discovers
zero plugins (Muse reads the Codex catalog first and skips the entry)," and
expected warnings "`multiple-manifests`; Claude-only fields ignored" are all
stated without explanation of what they mean or why they matter.

### comprehension-1-15 — Nit — `concepts_brief.md` and the drift report's destination are unspecified
Lines 37, 43. The brainstorm output `concepts_brief.md` is named with no
location or format, and `egm-drift-report` writes "a dated report" with no
stated directory.

### comprehension-1-16 — Nit — "Byte-identical (modulo the path prefix)" is self-contradictory
Lines 268–270. §5.4 step 4 requires local `custom-skills/egm-*` vs. AEP
`skills/egm-*` wrappers to be "byte-identical (modulo the path prefix:
`~/workspace/egm/` locally vs.
`../../reference/elephant-goldfish-model/` in the repo)." Byte-identical
files cannot differ by prefix; no comparison method (e.g.
normalize-then-diff) is specified.

### comprehension-1-17 — Nit — `re0-upgrade` precedent is unexplained
Lines 320–323. Open decision 4 invokes "the `re0-upgrade` precedent:
force-sync rests on the explicit decision, not on dispositioned findings"
with no definition or link; a fresh reader cannot apply the precedent to a
gate trip.

### comprehension-1-18 — Nit — Standing rules named without definition or pointer
Lines 224–225. "Conventional Commits for any AEP PR; identity scrubbing in
externally visible content" are stated as standing rules with no format,
example, or pointer to where they are defined.

### comprehension-1-19 — Nit — "Install notes" is an undefined artifact
Lines 190–192. §4.3 says where the SkillSpector gate is unavailable, "the
scan is run once on the authoring machine and the scores recorded in the
install notes." No install-notes file, location, or format is defined
anywhere in the document.

### comprehension-1-20 — Nit — Priority order asserts value without rationale
Lines 281–284. "Priority order within each phase follows value, not
alphabetical order" lists `egm-review-loop` + `egm-review` first, then
brainstorm, draft, resolve, drift-report, bootstrap — but never says why
that order is the value order (e.g. why `egm-resolve` precedes
`egm-drift-report`, which §5.3 calls "genuinely new").

### comprehension-1-21 — Nit — Vendor-tree count in the Appendix does not match the repo listing
Line 337. The Appendix claims the `reference/` vendor pattern has "(8
trees, `.github/vendor-*.sha256`)"; a listing of
`~/workspace/autonomous-engineering-platform/reference/` shows 9 entries
(docs-mcp-server, esf, grim-prompter, harness2, humanizer, neurostrata,
neurostrata-ops, security-audit-skill, ub-mode). (Same error independently
found by design_critic-1-8.)

### zoom_out-1-6 — Nit — D5's "no exception" gate has an escape hatch, but only for the speculative environment
Lines §3 D5 (122–128), §4.3 (190–192). D5 states "Standing rule, no
exception" for the SkillSpector gate, yet §4.3 permits the scan to be "run
once on the authoring machine and the scores recorded in the install notes"
where the gate is unavailable — i.e. an unscanned install is acceptable in
Environment A. The exception exists solely to serve the environment flagged
in zoom_out-1-1.

### zoom_out-1-7 — Nit — `skill.yaml` generation is unmechanized and thinner than the repo norm
Lines §3 D3 item 1 (81–83). "Generate one per skill from the existing
frontmatter (name + description)." Verified: 61 `skill.yaml` files exist in
repo `skills/`, but no script generates them (`check_skills_manifest.py`
does not reference `skill.yaml`), so "generate" means 7 hand-written files.
Further, repo `skill.yaml` files carry fields beyond name/description (e.g.
`skills/aim/skill.yaml` has `title`, `category`, `include_in_prompt`); D3
specifies name + description only, so the generated files would not match
the established local format.

### zoom_out-1-8 — Nit — Altitude drops: shell commands and warning names in a strategy document
Lines 165–167 (`git clone ...; muse plugins install ...`), 207 ("Warnings
are expected (`multiple-manifests`...)"), 262 (`diff -rq` bundle vs.
upstream). Literal install commands, a specific expected warning string,
and a specific diff invocation are implementation-level detail in a strategy
document. They belong in the install runbook, not the design.

## Shared root causes (dedup map)

Several findings from different reviewers trace to the same underlying gap.
They are recorded separately above (per-reviewer audit trail) but share one
fix:

1. **Coverage claims vs. actual gates** — design_critic-1-1,
   design_critic-1-2, implementation_readiness-1-2, implementation_readiness-1-7.
   `vendor-integrity` is hardcoded per-tree blocks (CI edit missing);
   `skills-freshness` proves repo-tree/manifest consistency only, never
   live freshness; `skill.yaml` is excluded from the manifest by bare
   basename. The plan's "covered by" claims overstate all three.
2. **Dual installation / sync** — design_critic-1-3, zoom_out-1-3,
   comprehension-1-16, implementation_readiness-1-5. Two adapted copies plus
   a bundle, policed only by a manual "byte-identical (modulo the path
   prefix)" check that is self-contradictory and has no executable procedure.
3. **Path-resolution adaptation not executable** — design_critic-1-4,
   implementation_readiness-1-3, comprehension-1-3, comprehension-1-11.
   "Three parents" contradicts the plan's own `../../` examples; no rewrite
   mapping, no per-skill occurrence list, no persona-internal reference
   coverage, no Path 2 example.
4. **`skill.yaml` generation** — implementation_readiness-1-2,
   comprehension-1-6, zoom_out-1-7. No schema, field set, generator, or
   validation; thinner than the repo norm.
5. **D6 read-only mitigation unenforceable as stated** —
   design_critic-1-5, comprehension-1-10. "Do not hand reviewers write
   tools" is asserted over a mechanism the document itself says cannot
   restrict tools; no fail-closed control, no verification method.
6. **Dispatch / Elephant / synthesizer undefined** — comprehension-1-2,
   implementation_readiness-1-9. Roles never mapped to concrete actors;
   dispatch has no invocation form, brief template, timeout, or gate
   question text.
7. **Missing standard sections** — structural-1-1 through structural-1-5,
   design_critic-1-7. No Goals, Problem Statement, Proposed Architecture,
   Alternatives Considered, or Risks & Mitigations headings.
8. **Gate contradictions (D5 vs. §4.3)** — design_critic-1-8, zoom_out-1-6.
   "No exception" vs. the unscanned-install fallback for Environment A.
9. **Appendix factual error (8 vs. 9 trees)** — design_critic-1-8,
   comprehension-1-21. Two independent verifications; repo has 9.
10. **Scope / YAGNI** — zoom_out-1-1, zoom_out-1-2, zoom_out-1-4,
    design_critic-1-7. Environment A designed in full with no identified
    user; root problem undemonstrated for AEP; all 7 skills scoped before
    pilot evidence.

## What checked out (no finding)

- §2 content counts (7 skills / 1,898 lines / 10 personas / 5 standards)
  verified correct against the local bundle (design_critic).
- D2's "skill-only installers break EGM" rationale backed by the verified
  upstream quote and bundle-relative references (design_critic).
- The D1 fork-vs-upstream call (source from upstream, fork adds nothing)
  stated with a verifiable HEAD claim (design_critic).
- Heading hierarchy, tables, code fences, list sequencing, and internal
  cross-references all clean (structural).
- Verified repo facts that hold: the `reference/` vendor pattern with
  per-tree `.github/vendor-*.sha256` files exists; `skills-freshness` runs
  `scripts/check_skills_manifest.py --root skills --check` against
  `.github/skills-sync-scope.txt`; `scan-gate.sh` exists with the stated
  block thresholds (score > 50, HIGH/CRITICAL, fail-closed);
  `skills/README.md` attribution table format is as described
  (implementation_readiness).

## STOP — decision gate

Round 1 is complete. No fixes were applied, no second round was run, no PR
was opened. Per the skill's turn-taking checkpoint, the loop driver stops
here. The next step is the user's decision: contest findings, propose fixes
(`egm-resolve`), or accept the document as-is.
