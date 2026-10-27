# Ub-mode skill reference

## What it is

unclebob/ub-mode (vendored from the pratik-saptarshi fork) — a coding-agent skill that enforces a reduced set of software-engineering principles on every change: **First Make it Work** (laziness protocol, foundational thinking, TDD, redesign from first principles, attack the premise, subtract before you add, outcome-oriented execution, build the lever, and architecture discipline), **Then Make it Right** (fix root causes, sequence work into verifiable units, test behavior not implementation, three deterministic quality gates, refactoring), and **Follow Practice** (keep a log, guard the context window, worktree cleanup, small ordered commits). It is loosely based on portions of @poteto's rules (`poteto-mode` / `pstack`). The whole skill is two files: a `README.md` and the `SKILL.md` an agent loads.

Vendored snapshot: [PROVENANCE.md](../reference/ub-mode/PROVENANCE.md) — fork `https://github.com/pratik-saptarshi/ub-mode` at `57a8bdd28e45ed41900ace0bafa2ff76dd9ed70f` (2026-10-27). Upstream: `https://github.com/unclebob/ub-mode`.

## License caveat

The source tree carries **no LICENSE file and grants no license**. Nothing in the snapshot is licensed for reuse; it is held as reference data only. This is different from ub-mode's companion tools (below), which are separate repositories under 0BSD — their licenses do not extend to this tree.

## The substance is not in this tree

The skill is a thin orchestration layer. Its "Make it Right" gates are three separate companion repositories, **none of which are vendored here**:

| Companion tool | Gate it enforces |
|---|---|
| [unclebob/crapper](https://github.com/unclebob/crapper) | CRAP score per function — every function under 10, by splitting, testing, or both |
| [unclebob/dryer](https://github.com/unclebob/dryer) | structural duplication — blocks at 0.8 similarity or above are eliminated |
| [unclebob/mutator](https://github.com/unclebob/mutator) | mutation testing — cover the uncovered, kill the survivors, delete dead code |

(A fourth companion, `unclebob/uml-viewer`, visualizes the gate results; it is likewise not vendored.) All three gate tools analyze exactly Clojure, Java, Go, TypeScript, Rust, and Python. Adopting the gates means vendoring or installing those repositories under their own provenance — this snapshot alone provides no executable gate.

## Quirks worth recording

- **Dryer threshold mismatch:** the skill prescribes eliminating duplication ranked 0.8 or above, but dryer's own default threshold is 0.82. Installing the skill does not reconfigure the tool — a run under defaults applies 0.82, not the skill's 0.8.
- **Mutator needs a sibling crapper:** the mutator tool requires a `../crapper` checkout beside it to run, so the companions cannot be laid out independently.
- **No releases:** ub-mode and all three companions are young repositories (created 2026-09-30 / 2026-10-25) with zero releases; any future pin is a raw commit, as here.

## What runs on this VM

Nothing executes from the vendored tree. The snapshot is a study reference for the principles and the gate thresholds — the parts AEP may borrow. An actual ub-mode run would execute from a live checkout of the fork, and the gates from live checkouts of the companion tools, not from `reference/`.

## Agent-rules caveat

The snapshot's `SKILL.md` is an agent skill addressed to whatever agent loads it to run ub-mode. As vendored reference data it does not govern work in this repository; AEP's own `AGENTS.md` does.
