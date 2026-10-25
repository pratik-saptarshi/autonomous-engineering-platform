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
  true iff a lane bearing the identifier's lane name (the eligibility
  engine's encoding) was under claim during the interval between the
  two observations, per its claim/settlement intervals (see
  :func:`active_lane_names`) — evidence the current regime
  demonstrably picked the work up, as opposed to it leaving ready by
  closure, blocking, or operator action.
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
median over pickup-explained exits (first-ready observation of the
issue's current ready episode to the exit observation — the baseline
clears on every exit from ready, so time spent not-ready between
episodes is never counted as dispatch delay); and the fraction of
ticks with a non-empty ready set.
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from orch.claims import ACTIVE_CLAIM_STATE, lane_name_for
from orch.model import Issue

__all__ = [
    "ObservationLogError",
    "active_lane_names",
    "append_observation",
    "build_observation",
    "parse_ts",
    "read_observations",
    "summarize",
]


class ObservationLogError(ValueError):
    """An observation log line is not valid JSON.

    The message names the log path and the malformed line, so the CLI
    can surface it as a clean error instead of a traceback.
    """


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


# History events that close a claim interval: the lane leaves the
# active-claim state. ``setup-failed`` / ``claim-refused`` settle a
# just-written manifest as released; ``settled-interrupted`` precedes
# or accompanies a reap. Post-settlement housekeeping (``cleaned``)
# is deliberately absent: it follows a settlement and says nothing
# about when the lane was active.
_SETTLEMENT_EVENTS = frozenset(
    {
        "released",
        "reaped",
        "settled-interrupted",
        "setup-failed",
        "claim-refused",
    }
)


def _claim_intervals(
    directory: Path, stem: str, manifest: dict
) -> list[tuple[datetime, datetime | None]]:
    """Claim/settlement intervals for one lane, from its history log.

    The sibling ``<stem>.log`` (lane-coord's per-lane history:
    ``<ts> <event> epoch=<n> worker=<w>`` per line) is the evidence:
    each ``claimed`` event opens an interval and the next settlement
    event closes it. A trailing open interval is kept only while the
    manifest still shows the claim active. When the history yields no
    interval for a still-claimed manifest (log absent or rotated),
    the manifest alone is one open interval from ``claimed_at``. A
    settled lane whose settlement time the history cannot establish
    yields no interval: pickup credit is claimed only on evidence.
    """
    intervals: list[tuple[datetime, datetime | None]] = []
    try:
        lines = (directory / f"{stem}.log").read_text(
            encoding="utf-8"
        ).splitlines()
    except (OSError, UnicodeDecodeError):
        lines = []
    open_since: datetime | None = None
    for line in lines:
        fields = line.split()
        if len(fields) < 2:
            continue
        stamp = parse_ts(fields[0])
        if stamp is None:
            continue
        event = fields[1]
        if event == "claimed":
            if open_since is not None:
                intervals.append((open_since, stamp))
            open_since = stamp
        elif event in _SETTLEMENT_EVENTS and open_since is not None:
            intervals.append((open_since, stamp))
            open_since = None
    if open_since is not None and manifest.get("state") == ACTIVE_CLAIM_STATE:
        intervals.append((open_since, None))
    if manifest.get("state") == ACTIVE_CLAIM_STATE and all(
        settled is not None for _, settled in intervals
    ):
        claimed_at = parse_ts(manifest.get("claimed_at"))
        if claimed_at is not None:
            intervals.append((claimed_at, None))
    return intervals


def active_lane_names(lanes_dir, start: datetime, end: datetime) -> set[str]:
    """Lane names under claim at any point in ``[start, end]``.

    A lane counts when one of its claim/settlement intervals (see
    :func:`_claim_intervals`) intersects the window: claimed at or
    before ``end`` and settled at or after ``start``, or still
    claimed. The manifest's ``updated_at`` is never evidence — every
    state rewrite refreshes it while preserving ``claimed_at``,
    including the post-settlement cleanup rewrite, so a recent
    ``updated_at`` does not establish the lane was active in the
    interval. Manifests that fail to parse, or whose claim time
    cannot be established, do not count: pickup credit is claimed
    only on evidence.
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
        if parse_ts(data.get("claimed_at")) is None:
            continue
        for claimed_at, settled_at in _claim_intervals(
            directory, path.stem, data
        ):
            if claimed_at <= end and (
                settled_at is None or settled_at >= start
            ):
                names.add(path.stem)
                break
    return names


def read_observations(path) -> list[dict]:
    """All observations in the log at *path* (``[]`` when absent)."""
    log_path = Path(path)
    if not log_path.is_file():
        return []
    observations = []
    for lineno, line in enumerate(
        log_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue
        try:
            observations.append(json.loads(line))
        except json.JSONDecodeError as exc:
            preview = line if len(line) <= 120 else line[:117] + "..."
            raise ObservationLogError(
                f"malformed observation log {log_path}: "
                f"line {lineno} is not valid JSON: {preview!r}"
            ) from exc
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
        # The lag baseline is per ready episode: once an issue is
        # absent from the ready set it has exited — explained or not —
        # and its baseline clears, so a later re-entry starts a fresh
        # episode instead of inheriting the first-ever sighting.
        current = set(obs.get("ready", []))
        for identifier in list(first_ready):
            if identifier not in current:
                del first_ready[identifier]
        for identifier in obs.get("ready", []):
            first_ready.setdefault(identifier, index)
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
