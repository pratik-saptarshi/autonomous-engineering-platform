"""Pure eligibility engine.

``select`` filters tracker candidates against the workflow's assignment,
state, dependency, claim, and cap rules and orders the survivors for
dispatch. It performs no I/O beyond the injected ``ClaimView`` and writes
nothing. Every non-selected candidate gets exactly one rejection reason,
because the dry-run's usefulness is the rejection list.
"""

from __future__ import annotations

import enum
from collections import Counter
from dataclasses import dataclass

from orch.claims import ClaimView, lane_name_for
from orch.model import Issue
from orch.workflow import Workflow

__all__ = ["Reason", "Selection", "select"]


class Reason(str, enum.Enum):
    MISSING_FIELDS = "MISSING_FIELDS"
    NOT_ASSIGNED = "NOT_ASSIGNED"
    STATE_NOT_ACTIVE = "STATE_NOT_ACTIVE"
    STATE_TERMINAL = "STATE_TERMINAL"
    BLOCKED = "BLOCKED"
    ALREADY_CLAIMED = "ALREADY_CLAIMED"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"
    NAME_COLLISION = "NAME_COLLISION"
    CAP_GLOBAL = "CAP_GLOBAL"
    CAP_STATE = "CAP_STATE"


@dataclass(frozen=True)
class Selection:
    dispatch: list[Issue]
    rejections: dict[str, tuple[Reason, str]]


def _normalize_state(state: str) -> str:
    return state.strip().lower()


def _rejection_key(issue: Issue) -> str:
    return issue.identifier if issue.identifier.strip() else issue.key


def _filter_reason(
    issue: Issue,
    *,
    active_states: set[str],
    terminal_states: set[str],
    claimed_lanes: set[str],
    colliding_lanes: set[str],
    completed: set[str],
) -> tuple[Reason, str] | None:
    lane = lane_name_for(issue.identifier)

    missing = [
        field
        for field, value in (
            ("identifier", issue.identifier),
            ("title", issue.title),
        )
        if not value.strip()
    ]
    if missing:
        return Reason.MISSING_FIELDS, ", ".join(missing)

    if issue.key in completed:
        return Reason.ALREADY_COMPLETED, issue.key

    if lane in colliding_lanes:
        return Reason.NAME_COLLISION, lane

    state = _normalize_state(issue.state)
    if state in terminal_states:
        return Reason.STATE_TERMINAL, state
    if state not in active_states:
        return Reason.STATE_NOT_ACTIVE, state

    if not issue.assigned_to_worker:
        return Reason.NOT_ASSIGNED, "assigned_to_worker is false"
    if not issue.author_ok:
        return Reason.NOT_ASSIGNED, "author_ok is false"

    for blocker in issue.blockers:
        if not blocker.is_terminal and (
            _normalize_state(blocker.state) not in terminal_states
        ):
            return Reason.BLOCKED, blocker.key

    if lane in claimed_lanes:
        return Reason.ALREADY_CLAIMED, lane

    return None


def select(
    candidates: list[Issue],
    workflow: Workflow,
    claims: ClaimView,
    completed: set[str],
) -> Selection:
    """Select the candidates to dispatch, in dispatch order.

    Ordering is total: ``(priority is None, priority, created_at,
    identifier)`` — a candidate with no priority sorts after every
    prioritized one. ``workflow.cap_global`` caps the number dispatched
    in this batch; per-state caps count the view's running counts plus
    the candidates already selected in this batch.
    """

    active_states = {_normalize_state(s) for s in workflow.active_states}
    terminal_states = {_normalize_state(s) for s in workflow.terminal_states}
    state_caps = {
        _normalize_state(state): cap
        for state, cap in workflow.cap_per_state.items()
    }
    claimed_lanes = claims.claimed_lanes()
    running_by_state = {
        _normalize_state(state): count
        for state, count in claims.running_by_state().items()
    }

    lane_groups: dict[str, list[Issue]] = {}
    for issue in candidates:
        lane_groups.setdefault(lane_name_for(issue.identifier), []).append(issue)
    colliding_lanes = {
        lane for lane, group in lane_groups.items() if len(group) > 1
    }

    rejections: dict[str, tuple[Reason, str]] = {}
    survivors: list[Issue] = []
    for issue in candidates:
        reason = _filter_reason(
            issue,
            active_states=active_states,
            terminal_states=terminal_states,
            claimed_lanes=claimed_lanes,
            colliding_lanes=colliding_lanes,
            completed=completed,
        )
        if reason is None:
            survivors.append(issue)
        else:
            rejections[_rejection_key(issue)] = reason

    survivors.sort(
        key=lambda issue: (
            issue.priority is None,
            issue.priority,
            issue.created_at,
            issue.identifier,
        )
    )

    dispatch: list[Issue] = []
    selected_by_state: Counter[str] = Counter()
    for issue in survivors:
        if (
            workflow.cap_global is not None
            and len(dispatch) >= workflow.cap_global
        ):
            rejections[_rejection_key(issue)] = (
                Reason.CAP_GLOBAL,
                f"cap_global={workflow.cap_global}",
            )
            continue
        state = _normalize_state(issue.state)
        if state in state_caps and (
            running_by_state.get(state, 0) + selected_by_state[state]
            >= state_caps[state]
        ):
            rejections[_rejection_key(issue)] = (Reason.CAP_STATE, state)
            continue
        dispatch.append(issue)
        selected_by_state[state] += 1

    return Selection(dispatch=dispatch, rejections=rejections)
