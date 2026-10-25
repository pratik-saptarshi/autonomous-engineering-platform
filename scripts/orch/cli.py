"""Dry-run CLI for the orchestrator (Stage 1 verbs).

``orch preflight --workflow <path>`` loads the spec and prints each
environment check's result; any failure exits non-zero naming the
missing piece — never a traceback, and never a resolved ``$ENV``
value (checks report declarations as present/absent only).

``orch dry-run --workflow <path>`` fetches candidates read-only, runs
the eligibility engine against the manifest-backed claim view and an
empty completed set (no store exists in Stage 1 — stated in the
output, not hidden), and prints the would-dispatch list, every
rejection with its reason, the fetch accounting, claim-view warnings,
and the Stage-1 limits line. It writes nothing anywhere except the
explicit ``--log`` file, which appends one demand observation (see
:mod:`orch.observe`) per run. ``orch dry-run --summarize <logpath>``
prints the gate metrics over an observation log.

Stage 1 spawns no agent and writes to no tracker: both adapters'
write methods still raise.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone

from orch.adapters_beads import BeadsAdapter, BeadsError, FetchCeilingExceeded
from orch.adapters_github import (
    BudgetDenied,
    BudgetExceeded,
    GitHubAdapter,
    GitHubError,
)
from orch.claims import ManifestClaimView, LanesDirMissing, _resolve_lanes_dir
from orch.engine import select
from orch.observe import (
    ObservationLogError,
    active_lane_names,
    append_observation,
    build_observation,
    parse_ts,
    read_observations,
    summarize,
)
from orch.workflow import (
    WorkflowError,
    _default_remote_of,
    _normalize_remote,
    load_workflow,
)

__all__ = ["main"]

_LIMITS_LINE = (
    "stage-1 limits: per-state caps evaluated against this batch only "
    "(no store); GitHub blockers reflect label data only; the completed "
    "set is empty (no store exists in Stage 1)"
)

_KNOWN_ERRORS = (
    WorkflowError,
    LanesDirMissing,
    BeadsError,
    FetchCeilingExceeded,
    GitHubError,
    BudgetDenied,
    BudgetExceeded,
    ObservationLogError,
    OSError,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_adapter(workflow):
    """The production adapter for the spec's tracker."""
    if workflow.tracker == "beads":
        return BeadsAdapter(workflow)
    if workflow.tracker == "github":
        return GitHubAdapter(workflow)
    raise WorkflowError(f"unknown tracker {workflow.tracker!r}")


def _format_priority(priority) -> str:
    return "-" if priority is None else str(priority)


def _cmd_preflight(args, out, err) -> int:
    try:
        workflow = load_workflow(args.workflow)
    except _KNOWN_ERRORS as exc:
        print(f"error: workflow failed to load: {exc}", file=err)
        return 1

    failures = 0

    def check(ok: bool, line: str) -> None:
        nonlocal failures
        if not ok:
            failures += 1
        print(f"{'ok' if ok else 'FAIL'}: {line}", file=out)

    check(True, f"workflow loads (tracker: {workflow.tracker})")

    tool = "bd" if workflow.tracker == "beads" else "ghg"
    tool_path = shutil.which(tool)
    if tool_path is not None:
        check(True, f"tracker tool: {tool} found at {tool_path}")
    elif workflow.tracker == "github":
        check(
            False,
            "tracker tool: ghg not found on PATH — the budgeted gateway "
            "is a sequencing precondition for github specs (G3); there "
            "is no ungated fallback",
        )
    else:
        check(
            False,
            "tracker tool: bd not found on PATH — on this fleet bd "
            "resolves via ~/go/bin in login shells only",
        )

    try:
        view = ManifestClaimView()
        check(
            True,
            "lanes directory: resolved as lane-coord resolves it "
            f"({len(view.claimed_lanes())} active claims)",
        )
        for warning in view.warnings:
            print(f"warning: {warning}", file=out)
    except LanesDirMissing as exc:
        check(False, f"lanes directory: {exc}")

    check(
        True,
        "issue_types (effective): " + ", ".join(workflow.issue_types),
    )
    check(
        True,
        "managed_by: "
        + ("present" if workflow.managed_by else "absent")
        + " (the one-dispatcher declaration)",
    )

    if workflow.tracker == "github":
        # Compare here, not just at load: with
        # allow_repo_remote_mismatch set the loader loads a mismatching
        # spec, and this line must report that rather than claim an
        # agreement that does not hold.
        remote_url, _default_branch = _default_remote_of(workflow.project_root)
        if remote_url is None:
            check(
                False,
                "repo/remote agreement: could not resolve the project "
                "origin remote to compare against the spec repo "
                f"{workflow.repo}",
            )
        else:
            remote_repo = _normalize_remote(remote_url)
            if remote_repo.lower() == workflow.repo.lower():
                check(
                    True,
                    f"repo/remote agreement: spec repo {workflow.repo} "
                    f"matches the project origin remote ({remote_repo})",
                )
            elif workflow.allow_repo_remote_mismatch:
                check(
                    True,
                    f"repo/remote agreement: mismatch — spec repo "
                    f"{workflow.repo} differs from the project origin "
                    f"remote ({remote_repo}); allowed by "
                    "allow_repo_remote_mismatch: true",
                )
            else:
                check(
                    False,
                    f"repo/remote agreement: mismatch — spec repo "
                    f"{workflow.repo} differs from the project origin "
                    f"remote ({remote_repo})",
                )
        polls_per_hour = 3600 / workflow.poll_seconds
        projected = polls_per_hour * workflow.max_calls_per_poll
        check(
            True,
            "projected gated-call rate: up to "
            f"{projected:g} calls/hour ({polls_per_hour:g} polls/hour "
            f"at poll_seconds={workflow.poll_seconds} x "
            f"max_calls_per_poll={workflow.max_calls_per_poll})",
        )
    else:
        check(True, "repo/remote agreement: n/a (beads tracker)")

    if failures:
        print(f"preflight: FAIL ({failures} check(s) failed)", file=out)
        return 1
    print("preflight: PASS", file=out)
    return 0


def _cmd_dry_run(args, out, err, adapter_factory, now) -> int:
    if args.summarize:
        observations = read_observations(args.summarize)
        print(summarize(observations), file=out)
        return 0
    if not args.workflow:
        print(
            "error: dry-run requires --workflow (or --summarize <logpath>)",
            file=err,
        )
        return 2

    workflow = load_workflow(args.workflow)
    factory = adapter_factory if adapter_factory is not None else build_adapter
    adapter = factory(workflow)
    candidates = adapter.fetch_candidates()
    view = ManifestClaimView()
    selection = select(candidates, workflow, view, set())

    print(
        f"dry-run: {args.workflow} (tracker: {workflow.tracker})", file=out
    )
    print(f"would dispatch ({len(selection.dispatch)}):", file=out)
    for issue in selection.dispatch:
        print(
            f"  {issue.identifier} "
            f"priority={_format_priority(issue.priority)} "
            f"state={issue.state}",
            file=out,
        )
    print(f"rejected ({len(selection.rejections)}):", file=out)
    for identifier in sorted(selection.rejections):
        reason, detail = selection.rejections[identifier]
        print(f"  {identifier} {reason.value} ({detail})", file=out)

    fetch_count = getattr(adapter, "last_fetch_count", len(candidates))
    type_excluded = getattr(adapter, "last_type_excluded_count", 0)
    truncated = getattr(adapter, "last_truncated", False)
    print(
        f"fetch: {fetch_count} records fetched, "
        f"type-excluded: {type_excluded}",
        file=out,
    )
    points_spent = None
    if workflow.tracker == "github":
        print(f"truncated: {str(truncated).lower()}", file=out)
        points_spent = adapter.points_spent()
        print(
            "points spent: "
            + ("unmeasured" if points_spent is None else str(points_spent)),
            file=out,
        )
    if view.warnings:
        print("claim-view warnings:", file=out)
        for warning in view.warnings:
            print(f"  {warning}", file=out)
    else:
        print("claim-view warnings: none", file=out)
    print(_LIMITS_LINE, file=out)

    if args.log:
        observations = read_observations(args.log)
        previous = observations[-1] if observations else None
        active_lanes: set[str] = set()
        if previous is not None:
            previous_ts = parse_ts(previous.get("ts"))
            if previous_ts is not None:
                active_lanes = active_lane_names(
                    _resolve_lanes_dir(None), previous_ts, now
                )
        observation = build_observation(
            now=now,
            tracker=workflow.tracker,
            dispatch=selection.dispatch,
            rejections={
                identifier: reason.value
                for identifier, (reason, _detail) in (
                    selection.rejections.items()
                )
            },
            previous=previous,
            active_lanes=active_lanes,
            points_spent=points_spent,
            fetch_count=fetch_count,
            type_excluded_count=type_excluded,
            truncated=truncated,
        )
        append_observation(args.log, observation)
        print(f"observation appended: {args.log}", file=out)
    return 0


def main(argv=None, *, adapter_factory=None, out=None, err=None, now=None) -> int:
    """CLI entry point. Returns the process exit code."""
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    parser = argparse.ArgumentParser(
        prog="orch", description="Orchestrator dry-run CLI (Stage 1)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight_parser = subparsers.add_parser(
        "preflight", help="load a spec and print environment checks"
    )
    preflight_parser.add_argument("--workflow", required=True)
    dry_run_parser = subparsers.add_parser(
        "dry-run", help="read-only selection dry-run over a spec"
    )
    dry_run_parser.add_argument("--workflow")
    dry_run_parser.add_argument("--log")
    dry_run_parser.add_argument("--summarize")
    args = parser.parse_args(argv)

    try:
        if args.command == "preflight":
            return _cmd_preflight(args, out, err)
        return _cmd_dry_run(
            args,
            out,
            err,
            adapter_factory,
            now if now is not None else _now(),
        )
    except _KNOWN_ERRORS as exc:
        print(f"error: {exc}", file=err)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
