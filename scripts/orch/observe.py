"""Demand-observation log for the dry-run CLI.

One dry-run with ``--log`` appends one observation object (JSONL) to the
log. The observation is the demand evidence the Election Gate reads:
whether ready work actually waits under the current regime.

Observation schema (pinned — ``append_observation`` writes exactly
these fields):

- ``ts``: ISO 8601 UTC timestamp of the observation.
- ``tracker``: the spec's tracker name (``"beads"`` | ``"github"``).
- ``ready``: identifiers the dry-run would dispatch, in dispatch order.
- ``rejected``: ``{identifier: reason}`` for every rejected candidate.
- ``ready_wait_s``: ``{identifier: seconds}`` — how long each ready
  issue has waited in its current state (see the basis rule below).
- ``ready_wait_basis``: ``"status_entry"`` when every ready wait was
  measured from the tracker's status-entry time (``Issue.status_since``
  — the true wait in the current state), else ``"updated_at_lb"``:
  waits measured from ``updated_at``, which is a **lower bound** on the
  true wait and is labeled **indicative only** everywhere it appears,
  including :func:`summarize` output.
- ``exits``: ``[{identifier, pickup_explained}]`` — identifiers ready
  in the previous observation and absent now. ``pickup_explained`` is
  true iff a lane manifest bearing the identifier's lane name (the
  eligibility engine's encoding) was active in the interval between
  the two observations — evidence the current regime demonstrably
  picked the work up, as opposed to it leaving ready by closure,
  blocking, or operator action.
- ``age_s``: ``{identifier: seconds}`` since each ready issue's
  ``created_at``.
- ``points_spent``: gateway points the poll cost, for live runs of the
  repo-hosted tracker; ``None`` when unmeasured (never estimated).
- ``fetch_count``: records the adapter fetched this run.
- ``type_excluded_count``: records the type allowlist excluded.
- ``truncated``: true when the fetch hit its pinned limit.

:func:`summarize` computes the gate metrics over a log: tick count and
window span; ready-set size (min / median / max); mean churn (mean
symmetric-difference size between consecutive ready sets — ``n/a``
with fewer than two observations); ready-wait median and p95 across
all ready observations, with the basis printed beside them (p95 is
nearest-rank: the ``ceil(0.95 * n)``-th smallest value); pickup-lag
median over pickup-explained exits (first-ready observation to exit
observation); and the fraction of ticks with a non-empty ready set.
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from orch.claims import lane_name_for
from orch.model import Issue

__all__ = [
    "active_lane_names",
    "append_observation",
    "build_observation",
    "parse_ts",
    "read_observations",
    "summarize",
]

_ACTIVE_CLAIM_STATE = "claimed"


def parse_ts(value) -> datetime | None:
    """Parse an ISO 8601 timestamp; ``None`` when unparseable.

    Naive values are read as UTC (the trackers on this fleet emit
    offset-carrying or ``Z``-suffixed values).
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _seconds_between(start: datetime | None, end: datetime) -> int | None:
    if start is None:
        return None
    return int((end - start).total_seconds())


def build_observation(
    *,
    now: datetime,
    tracker: str,
    dispatch: list[Issue],
    rejections: dict[str, str],
    previous: dict | None,
    active_lanes: set[str],
    points_spent: int | None,
    fetch_count: int,
    type_excluded_count: int,
    truncated: bool,
) -> dict:
    """Build one observation object in the pinned schema.

    ``previous`` is the log's prior observation (or ``None``);
    ``active_lanes`` names the lanes whose manifests were active in
    the interval since ``previous`` (see :func:`active_lane_names`).
    """
    ready = [issue.identifier for issue in dispatch]
    ready_wait_s: dict[str, int] = {}
    age_s: dict[str, int] = {}
    all_status_entry = bool(dispatch)
    for issue in dispatch:
        if issue.status_since is None:
            all_status_entry = False
        wait = _seconds_between(
            parse_ts(issue.status_since or issue.updated_at), now
        )
        if wait is not None:
            ready_wait_s[issue.identifier] = wait
        age = _seconds_between(parse_ts(issue.created_at), now)
        if age is not None:
            age_s[issue.identifier] = age
    exits = []
    if previous is not None:
        current = set(ready)
        for identifier in previous.get("ready", []):
            if identifier not in current:
                exits.append(
                    {
                        "identifier": identifier,
                        "pickup_explained": lane_name_for(identifier)
                        in active_lanes,
                    }
                )
    return {
        "ts": now.isoformat(),
        "tracker": tracker,
        "ready": ready,
        "rejected": dict(rejections),
        "ready_wait_s": ready_wait_s,
        "ready_wait_basis": (
            "status_entry" if all_status_entry else "updated_at_lb"
        ),
        "exits": exits,
        "age_s": age_s,
        "points_spent": points_spent,
        "fetch_count": fetch_count,
        "type_excluded_count": type_excluded_count,
        "truncated": truncated,
    }


def active_lane_names(lanes_dir, start: datetime, end: datetime) -> set[str]:
    """Lane names whose manifests were active in ``[start, end]``.

    A manifest (lane-coord's per-lane JSON: ``state``, ``claimed_at``,
    ``updated_at``) counts when it was claimed at or before ``end`` and
    either is still in the active-claim state or was last updated at or
    after ``start`` (claimed during the interval and settled within
    it). Manifests that fail to parse, or whose claim time cannot be
    established, do not count: pickup credit is claimed only on
    evidence.
    """
    names: set[str] = set()
    directory = Path(lanes_dir)
    if not directory.is_dir():
        return names
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        claimed_at = parse_ts(data.get("claimed_at"))
        if claimed_at is None or claimed_at > end:
            continue
        if data.get("state") == _ACTIVE_CLAIM_STATE:
            names.add(path.stem)
            continue
        updated_at = parse_ts(data.get("updated_at"))
        if updated_at is not None and updated_at >= start:
            names.add(path.stem)
    return names


def read_observations(path) -> list[dict]:
    """All observations in the log at *path* (``[]`` when absent)."""
    log_path = Path(path)
    if not log_path.is_file():
        return []
    observations = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            observations.append(json.loads(line))
    return observations


def append_observation(path, observation: dict) -> None:
    """Append one observation object as a JSON line to the log."""
    log_path = Path(path)
    if log_path.parent != Path(""):
        log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(observation) + "\n")


def _fmt_number(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _p95(values: list[int]) -> int:
    ordered = sorted(values)
    rank = math.ceil(0.95 * len(ordered))
    return ordered[max(rank, 1) - 1]


def summarize(observations: list[dict]) -> str:
    """The gate metrics over *observations*, as printable lines."""
    lines = [f"observations: {len(observations)}"]
    if not observations:
        lines.append("mean churn: n/a")
        lines.append("pickup lag: n/a")
        return "\n".join(lines)

    stamps = [parse_ts(obs.get("ts")) for obs in observations]
    if all(stamp is not None for stamp in stamps):
        span = int((stamps[-1] - stamps[0]).total_seconds())
        lines.append(f"window span: {span}s")
    else:
        lines.append("window span: n/a")

    sizes = [len(obs.get("ready", [])) for obs in observations]
    lines.append(
        "ready-set size: min {}, median {}, max {}".format(
            min(sizes), _fmt_number(statistics.median(sizes)), max(sizes)
        )
    )

    if len(observations) < 2:
        lines.append("mean churn: n/a")
    else:
        churns = [
            len(set(a.get("ready", [])) ^ set(b.get("ready", [])))
            for a, b in zip(observations, observations[1:])
        ]
        lines.append(f"mean churn: {_fmt_number(sum(churns) / len(churns))}")

    bases = []
    for obs in observations:
        basis = obs.get("ready_wait_basis")
        if basis and basis not in bases:
            bases.append(basis)
    if bases:
        rendered = ", ".join(
            f"{basis} (indicative only)"
            if basis == "updated_at_lb"
            else basis
            for basis in bases
        )
        lines.append(f"ready-wait basis: {rendered}")
    waits = [
        value
        for obs in observations
        for value in (obs.get("ready_wait_s") or {}).values()
    ]
    if waits:
        lines.append(
            "ready-wait: median {}s, p95 {}s".format(
                _fmt_number(statistics.median(waits)), _p95(waits)
            )
        )
    else:
        lines.append("ready-wait: n/a")

    lags: list[float] = []
    first_ready: dict[str, int] = {}
    for index, obs in enumerate(observations):
        for identifier in obs.get("ready", []):
            first_ready.setdefault(identifier, index)
        for exit_ in obs.get("exits", []):
            if not exit_.get("pickup_explained"):
                continue
            identifier = exit_.get("identifier")
            if identifier not in first_ready:
                continue
            start = stamps[first_ready[identifier]]
            end = stamps[index]
            if start is not None and end is not None:
                lags.append((end - start).total_seconds())
    if lags:
        lines.append(
            "pickup lag: median {}s over {} pickup-explained exit{}".format(
                _fmt_number(statistics.median(lags)),
                len(lags),
                "s" if len(lags) != 1 else "",
            )
        )
    else:
        lines.append("pickup lag: n/a")

    nonempty = sum(1 for size in sizes if size > 0)
    lines.append(f"non-empty ready fraction: {nonempty}/{len(observations)}")
    return "\n".join(lines)
