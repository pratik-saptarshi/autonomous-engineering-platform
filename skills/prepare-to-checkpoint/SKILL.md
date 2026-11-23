---
name: prepare-to-checkpoint
description: The agent prepares everything up to an irreversible step; the owner executes that step; verification is by resulting state, not receipt..
---

> Installed live 2026-11-23 from pattern-mining candidate A7, approved by Pratik in the Pattern mining lane (pattern-mining report, 2026-11-23).

# Prepare to the Checkpoint — Owner Executes the Irreversible Step

## Postulate

For an irreversible step (pay, send, submit, book, checkout), the agent's job ends at a prepared, verified checkpoint. The owner performs the step. The next run verifies by the *resulting state*, not by a receipt or a success message.

## Procedure

1. Identify the irreversible step explicitly before starting. Everything before it is agent work; the step itself is not.
2. Prepare to the checkpoint: cart filled / draft written / form completed / plan priced and timed — and verified against the owner's standing rules (price, exclusions, overlap constraints) at preparation time. Preparation is resumable and idempotent: before adding or creating anything, reconcile the persisted cart/draft/plan left by an interrupted run — a rerun continues the existing preparation instead of duplicating it.
3. Present the checkpoint plainly: what is prepared, the total/commitment, and what the owner's action will do. Stop.
4. After the owner acts, verify by state on the next touch: library contents, tracker status, reservation record — not the checkout/send receipt.
5. If the expected state is absent, do not re-prepare or re-fill automatically: first attribute the gap (owner acted elsewhere, items lapsed, preparation never landed). See the empty-state watchlist pattern in the 2026-11-23 pattern-mining report.

## Boundary

This is a posture for owner-facing irreversible actions, not a general approval framework: steps the owner has pre-authorized by standing rule (e.g. gated auto-merge under branch protection) follow that rule, not this checkpoint.

## Evidence

- Books/Chirp, resolved 2026-11-08, repeated 2026-11-20: agent carts only; owner checks out on his phone; library presence next run is the ownership verification.
- Movies, 2026-10-24: chains planned and presented; owner booked.
- Job search, 2026-11-04 / 11-15: application brief and recruiter reply drafted, not sent; closed on the owner's word.
