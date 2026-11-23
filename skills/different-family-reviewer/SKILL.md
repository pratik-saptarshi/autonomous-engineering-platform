---
name: different-family-reviewer
description: A review counts as independent only if the reviewer is a different model family from the implementer, enforced by an allowlist in code..
---

> Installed live 2026-11-23 from pattern-mining candidate A3, approved by Pratik in the Pattern mining lane (pattern-mining report, 2026-11-23).

# Different-Family Reviewer Rule

## Postulate

Independence is a property of who reviewed, not of the prompt. A reviewer from the same model family as the implementer does not count as an independent review, however the brief is worded.

## Rule

1. Maintain an explicit allowed-models list for delegated review, naming model families different from the implementer's.
2. Enforce the list in the dispatcher, before a session is created: a model not on the list is refused (hard exit), never silently substituted. Membership is not enough: the dispatcher must also reject any reviewer whose family matches the *current* implementer's family, evaluated at dispatch time — an allowlist written for a previous implementer does not carry over.
3. A model named in a brief that does not exist in the live catalog is flagged as non-existent, not approximated.
4. Record for every delegated review: implementer family, reviewer family, model id, session id. A review missing the family record is not counted as independent.
5. If a reviewer model stalls (zero-token / repeated timeout), substitute a *different allowed family*, and record the substitution and why.

## Boundary

`roundtable_review` runs multi-perspective panels. This rule supplies the independence criterion and its enforcement; panels should apply it to seat selection, but the rule also stands alone for single delegated reviews.

## Evidence

- OpenChamber bridge, 2026-11-20/21: 9-model allowlist enforced in dispatch.py; a non-catalog model refused before session creation (exit 64); a non-existent model name flagged, not added.
- replay-core waves 8/9 and AEP PR #191 panels, 2026-11-21/22: all dispatches different-family from the Claude implementer, substitutions recorded.
