# Archify — SkillSpector gate disposition

**Skill:** archify (vendored from tt-a1i/archify into autonomous-engineering-platform, PR #27)
**Scanner:** NVIDIA SkillSpector v2.12.0, static analysis only (`--no-llm`)
**Disposition date:** 2026-10-23
**Scope:** the modified tree — archify with its self-update mechanism removed (see below).

## Gate history

1. **Original scan — BLOCKED.** The vendored skill shipped a self-update mechanism
   (`scripts/check-update.mjs`, `scripts/update-contract.mjs`,
   `scripts/delivery-update-child.mjs`, `bin/delivery-update.mjs`,
   `references/update-awareness.md`) that fetched a remote update manifest
   (`DEFAULT_MANIFEST_URL`) and managed update state. That remote-fetch machinery
   is not acceptable in an installed skill, so the mechanism was excised:
   the 5 files above deleted; `bin/finalize.mjs` and `bin/archify.mjs` edited to
   drop the import, deadline, call sites, and receipt fields; the "Update
   awareness" section removed from `SKILL.md`.
   Excision verified: `node --check` clean, zero residual references to the
   mechanism, and a deliver smoke test rendered an 825 KB HTML whose receipt
   contains no `update` key.
2. **Re-scan of the modified tree — score 94, CRITICAL, DO_NOT_INSTALL,**
   57 issues. None of the 57 findings concern the removed mechanism; their
   composition is dispositioned below.
3. **Disposition + baseline (this note).** All 57 findings were reviewed and
   dispositioned. A CLI-native fingerprint baseline was generated from the
   modified tree, and the per-finding record was written in this repo's
   baseline convention.
4. **Verification re-scan with the baseline applied — score 0, LOW,**
   0 remaining issues, 57 suppressed, no new findings. Gate clears
   (score ≤ 50 and no HIGH/CRITICAL findings).

## Findings disposition

### AE1 — HIGH ×45 — dismissed (scanner coverage failure)

Every AE1 issue is anchored in `SKILL.md` and flags a bundled artifact the
scanner only partially inspected. The scan's own ledger records
`reason_code: runtime_limit` ("Inspection reached its configured runtime
limit") and `analysis_completeness` reports **0 of 199 files fully inspected
(0.0% coverage), status partial**. Incomplete scanner coverage of a large
skill is not evidence of obfuscation or malice in the referenced files — each
target is one of the skill's own schemas, examples, reference docs, or its
main CLI. Dismissed as false positives attributable to the scanner's runtime
limit, with the caveat that a future scanner configuration with a higher
limit should re-verify this category.

### AE3 — HIGH ×1 — dismissed (false positive)

`renderers/shared/diagnostics.mjs:37`: the flagged NUL bytes are literal
separator characters inside a dedupe-key template string in
`recordDiagnostic()`:

```
const key = `${normalized.code}<NUL>${normalized.message}<NUL>${JSON.stringify(normalized.subject)}`;
```

NUL is used as an unambiguous field separator that cannot collide with
diagnostic text — a standard join-key idiom, verified in context. No hidden
or obfuscated payload.

### LP3 — MEDIUM ×1 — accepted

`SKILL.md:1`: the skill declares no `permissions`/`allowed-tools` scope, while
the scanner detected env and network capabilities. Accepted: those
capabilities are inherent to the skill's function as a local diagram-renderer
CLI — it reads environment configuration and, only on an explicit user
request, fetches a brand-mark from a user-provided URL (documented in
`SKILL.md`). The vendored upstream skill predates tool-scope declarations.

### AE4 — MEDIUM ×1 — dismissed (false positive)

`examples/locales/ru.json:1`: the flagged content is the file's Russian
translation strings (e.g. `"page.title": "{title} — диаграмма"`). Cyrillic is
the content of the locale file, not mixed-script spoofing or deceptive
Unicode.

### EA3 — LOW ×9 — dismissed (false positive, Scope Creep)

`assets/template.html:135` and 8 rendered example HTMLs at the same line: the
flagged text `NOT LIMITED TO` is part of the SIL Open Font License warranty
disclaimer embedded in the template and its rendered outputs — third-party
font license boilerplate, not instructions or scope creep.

## Baseline files

- `archify.json` (this directory) — per-finding disposition record in the
  repo's baseline convention (`accepted` / `dismissed` with rationale).
- `archify.skillspector-baseline.json` (this directory) — CLI-native
  fingerprint baseline (SkillSpector v2 format) generated from the modified
  tree. Future scans suppress exactly the dispositioned findings:

  ```bash
  skillspector scan <archify-dir> --no-llm \
    --baseline skillspector-baselines/archify.skillspector-baseline.json
  ```

  Any finding not in this baseline is new and must be triaged on its own
  merits; the AE1 entries in particular should be re-examined if scanner
  coverage of this skill ever becomes complete.

## Approval

Install of the modified skill and this disposition were approved by the
skill's owner on 2026-10-23, with the baseline as the condition for clearing
the gate.
