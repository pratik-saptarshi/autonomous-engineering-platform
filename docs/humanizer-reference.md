# Humanizer skill reference

## What it is

pratik-saptarshi/humanizer (fork of blader/humanizer, default branch `develop`) — a coding-agent skill that rewrites AI-sounding prose so it reads like the writer, without changing what it says. It is built on Wikipedia's "Signs of AI writing": 26 numbered patterns in six groups (staging instead of stating, rhythm and formatting by rule, inflation, stock vocabulary, structural habits, and leftover chat artifacts), ordered by strength and frequency. The method is mark the tells, draft a rewrite, check the draft against the patterns and the original's claims, then write the final version. It supports pasted-text, file, and embedded modes, and can match a supplied writing sample's voice. The whole skill is one `SKILL.md`; the rest of the tree is plugin packaging for Claude Code, Cursor, and OpenAI-compatible agents, plus a stdlib-only package validator.

Vendored snapshot: [PROVENANCE.md](../reference/humanizer/PROVENANCE.md) — fork `https://github.com/pratik-saptarshi/humanizer` at `0ef9fe5bc3572734fd3ae6c448fe00a30cd5dcf0` (2026-11-04), upstream version 3.1.0. Upstream: `https://github.com/blader/humanizer`.

## License

MIT (© 2025 Siqi Chen). The tree carries a `LICENSE` file and the skill frontmatter declares `license: MIT`, so the snapshot may be reused under the MIT terms — a different position from the ub-mode snapshot, which carries no license and is held as reference data only.

## The working copy is not this tree

This snapshot is the pristine upstream baseline and is never edited in place. The copy AEP works from is [`skills/humanizer/`](../skills/humanizer/), which carries two local amendments, marked `fork_of: "blader/humanizer"` / `fork_version: 1` in its frontmatter and logged in its `FORK.md`:

1. **Scope note** — the skill must not be applied to evidence-bearing artifacts (receipts and sealed records, reviewer or verification reports, decision records, NeuroStrata inscriptions), where several upstream patterns would strip load-bearing hedging, signposting, and proof structure.
2. **File-mode verification** — file mode must read the file's current contents in full before editing (never rewrite from memory) and report section coverage afterward (addresses upstream issue #326).

The same amendments live on the fork's `feat/scope-and-file-mode-amendments` branch. A re-vendor replaces this snapshot wholesale and regenerates `.github/vendor-humanizer.sha256`; the amendments are re-applied to `skills/humanizer/` in the same change, never to this tree.

## What runs on this VM

Nothing executes from the vendored tree. The live skill is `~/workspace/custom-skills/humanizer`, kept consistent with `skills/humanizer/` by the skills sync and the manifest gate. The snapshot's own validator (`scripts/validate-package.py`) is a packaging checker for the upstream repo; it is not run here.

## Agent-rules caveat

The snapshot's `SKILL.md` is an agent skill addressed to whatever agent loads it to humanize prose, and its `AGENTS.md` is upstream's guide for changing the skill itself. As vendored reference data neither governs work in this repository; AEP's own `AGENTS.md` does.
