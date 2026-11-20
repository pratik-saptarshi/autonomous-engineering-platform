#!/usr/bin/env python3
"""Fork fleet census -- the standing record behind the "Fork fleet --
sync status" Google Sheet (docs/fork-fleet-sheet-reference.md; plan:
docs/plans/2026-11-18-fork-fleet-sheet-plan.html).

Bounded claim: this tool measures, at census time and only from live
GitHub compares taken through the ghg gateway, two axes per eligible
fork (a fork whose default branch is ``develop``):

  * mirror axis -- the fork's branch named after the upstream repo's
    default branch vs that upstream branch: is the mirror current,
    behind, diverged (blocked), missing, or unmeasurable?
  * develop axis -- the fork's ``develop`` vs its mirror: current,
    fast-forward-ready, carrying fork-local commits, or unmeasurable?

It is an observer. It never syncs, merges, pushes, or writes to any
repository (the plan's decision D6); its only output is a census JSON
(and, with --prev-rows, the sheet rows derived from it). Figures are
never parsed from the sync text log -- the 2026-11-17/18 measurement
incident (orca reported as 0 / 1,658 / 258 commits of develop lag by
three log-derived sources, 258 by direct compare) is why every number
here comes from a compare taken during the run. A measurement that
fails is reported as ``unknown`` with blank counts, never as a
fabricated zero.

Compare directions (pinned by the transposition fixture in the tests):

  * mirror:  compare/{mirror}...{upstream_owner}:{mirror}
             ahead_by  = upstream commits the mirror lacks (E)
             behind_by = commits unique to the mirror (F)
             base_commit.sha = the mirror head (G)
  * develop: compare/develop...{mirror}
             ahead_by  = mirror commits not in develop (J, the lag)
             behind_by = develop commits the mirror lacks (K)
             base_commit.sha = the develop head (L)

The compare payload carries no head_commit; the head SHA of each
compare is recovered from its permalink_url (abbreviated form,
validated as a hex prefix) and, for the upstream head (H), from a
branches call on the upstream repo (skipped when the mirror compare
is identical, where H == G by definition).

Cross-check: the develop compare's head must be the mirror tip the
mirror compare reported as its base. A disagreement marks the whole
row ``unknown`` rather than publishing two disagreeing figures.

Attribution ("last updated by", column N) uses a closed vocabulary --
a bot GHG_ACTOR (``fork-sync`` for mirror syncs, from its JSON run
record; ``fork-fleet-census`` for first-observation rows) or
``unknown (external change)``. Develop movements are not bot-made;
no person is ever inferred from commit authorship. An axis that
fails to measure keeps its last measured head as the baseline in
the derived sheet row (counts blank, status ``unknown``) and the
row's verification stamp does not advance, so a sync applied
during a failed observation is still attributable when measurement
recovers.

Exit codes: 0 = census complete, every repo measured; 1 = census
complete but at least one repo has an unknown/skip axis or a partial
measurement (e.g. the upstream head could not be read) -- the sheet
is still updated for what measured; 2 = fatal (repo list failure,
ghg budget denial at any stage, or an I/O failure) -- no sheet write
may be made from a run that exits 2.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OWNER = "pratik-saptarshi"
ACTOR = "fork-fleet-census"
GHG = os.environ.get("GHG_BIN", os.path.expanduser("~/go/bin/ghg"))
CHICAGO = ZoneInfo("America/Chicago")

MIRROR_STATUSES = {
    "current",
    "behind",
    "blocked-diverged",
    "no-mirror",
    "unknown",
    "skip",
    "retired",
}
DEVELOP_STATUSES = {
    "current",
    "ff-ready",
    "fork-local",
    "unknown",
    "skip",
    "retired",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PERMALINK_HEAD_RE = re.compile(r"\.\.\.[^:/]+:([0-9a-f]{4,40})$")

# Sheet columns A:P, in order. Q:R are human-owned and never appear here.
ROW_FIELDS = 16
COL_REPO = 0
COL_MIRROR_STATUS = 3
COL_DEVELOP_STATUS = 8
COL_LAST_SYNC = 12
COL_ACTOR = 13
COL_VERIFIED = 14
COL_NOTES = 15


class BudgetDenied(Exception):
    """A ghg call exited 75: stop the run, sheet untouched."""


class CensusFatal(Exception):
    """The census cannot be produced at all (exit 2)."""


def classify_mirror(ahead_by: int, behind_by: int) -> str:
    if behind_by > 0:
        return "blocked-diverged"
    if ahead_by > 0:
        return "behind"
    return "current"


def classify_develop(ahead_by: int, behind_by: int) -> str:
    if behind_by > 0:
        return "fork-local"
    if ahead_by > 0:
        return "ff-ready"
    return "current"


def permalink_head(url: str) -> str | None:
    """Abbreviated head SHA from a compare permalink_url, or None."""
    if not url:
        return None
    match = PERMALINK_HEAD_RE.search(url)
    return match.group(1) if match else None


def ghg_runner(args):
    """Default runner: one ghg call. Returns (obj, err, rc)."""
    env = {**os.environ, "GHG_ACTOR": ACTOR}
    try:
        proc = subprocess.run(
            [GHG, "run", "--", *args], capture_output=True, text=True, env=env
        )
    except OSError as exc:
        # A gateway that cannot even launch (missing executable,
        # permissions) is a fatal gateway failure, not a partial
        # census: nothing was measured.
        raise CensusFatal(f"cannot launch ghg ({GHG}): {exc}") from exc
    if proc.returncode == 75:
        raise BudgetDenied(f"ghg budget denial on: {' '.join(args)}")
    if proc.returncode != 0:
        return None, (proc.stderr.strip() or f"exit {proc.returncode}"), proc.returncode
    try:
        return json.loads(proc.stdout), None, 0
    except ValueError:
        return None, f"unparseable output: {proc.stdout[:200]}", proc.returncode


def _blank_row(repo: str) -> dict:
    return {
        "repo": repo,
        "upstream": None,
        "mirror_branch": None,
        "mirror_status": "unknown",
        "mirror_behind": None,
        "mirror_unique": None,
        "mirror_head": None,
        "upstream_head": None,
        "develop_status": "unknown",
        "develop_behind": None,
        "develop_fork_local": None,
        "develop_head": None,
        "error": None,
        "partial": False,
    }


def _call(runner, args):
    """One runner call; a 75 exit anywhere is a budget denial."""
    obj, err, rc = runner(args)
    if rc == 75:
        raise BudgetDenied(f"ghg budget denial on: {' '.join(args)}")
    return obj, err, rc


def _load_sync_record(path) -> dict:
    """Read fork-sync's JSON run record.

    A missing file degrades to {} (fork-sync has not applied a run
    since records began; plan S3). A file that exists but cannot be
    read or parsed raises CensusFatal: silently degrading would
    misattribute that night's syncs as external changes.
    """
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise CensusFatal(f"cannot read --sync-record {path}: {exc}") from exc


def census_repo(repo: str, runner) -> dict:
    """Measure one fork. `runner` maps ghg args -> (obj, err, rc)."""
    row = _blank_row(repo)
    info, err, _rc = _call(runner, ("api", f"repos/{repo}"))
    if info is None:
        row["error"] = f"repo-info: {err}"
        return row
    parent = info.get("parent") or {}
    upstream = parent.get("full_name")
    if not upstream:
        row["mirror_status"] = "skip"
        row["develop_status"] = "skip"
        row["error"] = "skip: no parent recorded — not a true fork?"
        return row
    mirror = parent.get("default_branch", "main")
    row["upstream"] = upstream
    row["mirror_branch"] = mirror
    upstream_owner = upstream.split("/")[0]

    cmp_up, err_up, _ = _call(
        runner, ("api", f"repos/{repo}/compare/{mirror}...{upstream_owner}:{mirror}")
    )
    if cmp_up is None:
        # Distinguish a missing mirror branch from a failed compare:
        # only a 404 from the branch probe means no-mirror; any other
        # probe failure is transient and leaves the axis unknown.
        _probe, perr, prc = _call(runner, ("api", f"repos/{repo}/branches/{mirror}"))
        if prc != 0 and ("404" in (perr or "") or "Not Found" in (perr or "")):
            row["mirror_status"] = "no-mirror"
            row["error"] = (
                f"no-mirror: no branch named {mirror} on the fork "
                f"(compare: {err_up})"
            )
        else:
            row["error"] = f"mirror-compare: {err_up}"
    else:
        row["mirror_status"] = classify_mirror(cmp_up["ahead_by"], cmp_up["behind_by"])
        row["mirror_behind"] = cmp_up["ahead_by"]
        row["mirror_unique"] = cmp_up["behind_by"]
        row["mirror_head"] = cmp_up["base_commit"]["sha"]
        if cmp_up["ahead_by"] == 0 and cmp_up["behind_by"] == 0:
            row["upstream_head"] = row["mirror_head"]
        else:
            up_branch, err_b, _ = _call(
                runner, ("api", f"repos/{upstream}/branches/{mirror}")
            )
            if up_branch is not None:
                sha = up_branch["commit"]["sha"]
                # The lookup races the compare: validate the returned
                # head against the upstream head the compare itself
                # measured (its permalink prefix). A disagreement
                # means upstream moved mid-measurement -- the counts
                # describe a tip we can no longer name, so the mirror
                # axis goes unknown instead of publishing an
                # inconsistent row.
                abbrev = permalink_head(cmp_up.get("permalink_url", ""))
                if abbrev is None or not sha.startswith(abbrev):
                    row["mirror_status"] = "unknown"
                    row["mirror_behind"] = None
                    row["mirror_unique"] = None
                    note = "upstream head moved during measurement"
                    row["error"] = (
                        f"{row['error']}; {note}" if row["error"] else note
                    )
                else:
                    row["upstream_head"] = sha
            else:
                row["partial"] = True
                row["error"] = f"upstream-head: {err_b}"

    cmp_dev, err_dev, _ = _call(
        runner, ("api", f"repos/{repo}/compare/develop...{mirror}")
    )
    if cmp_dev is None:
        if row["mirror_status"] != "no-mirror":
            note = f"develop-compare: {err_dev}"
            row["error"] = f"{row['error']}; {note}" if row["error"] else note
    else:
        row["develop_status"] = classify_develop(
            cmp_dev["ahead_by"], cmp_dev["behind_by"]
        )
        row["develop_behind"] = cmp_dev["ahead_by"]
        row["develop_fork_local"] = cmp_dev["behind_by"]
        row["develop_head"] = cmp_dev["base_commit"]["sha"]
        # Consistency: this compare's head is the mirror tip; it must
        # agree with the mirror compare's base (the same tip).
        head_abbrev = permalink_head(cmp_dev.get("permalink_url", ""))
        if row["mirror_head"] is not None and (
            head_abbrev is None or not row["mirror_head"].startswith(head_abbrev)
        ):
            row["mirror_status"] = "unknown"
            row["develop_status"] = "unknown"
            row["mirror_behind"] = None
            row["mirror_unique"] = None
            row["develop_behind"] = None
            row["develop_fork_local"] = None
            note = "mirror-head mismatch between compares"
            row["error"] = f"{row['error']}; {note}" if row["error"] else note
    return row


def run_census(runner) -> dict:
    """Full fleet census. Raises CensusFatal / BudgetDenied."""
    repos, err, _rc = _call(
        runner,
        (
            "repo",
            "list",
            OWNER,
            "--limit",
            "300",
            "--json",
            "nameWithOwner,isFork,defaultBranchRef",
        )
    )
    if repos is None:
        raise CensusFatal(f"repo list failed: {err}")
    eligible = sorted(
        r["nameWithOwner"]
        for r in repos
        if r.get("isFork") and (r.get("defaultBranchRef") or {}).get("name") == "develop"
    )
    rows = []
    for repo in eligible:
        row = census_repo(repo, runner)
        # Per-repo measurement time. The attribution window is
        # bounded by when THIS repo was measured, not by when the
        # whole run finished: a sync fork-sync applies while the
        # remaining repos are still being measured postdates this
        # repo's compares, and must stay attributable on the next
        # census (column O carries this stamp; see build_rows).
        row["measured_at"] = datetime.now(CHICAGO).isoformat(timespec="seconds")
        rows.append(row)
    return {
        "version": 1,
        "actor": ACTOR,
        "generated_at": datetime.now(CHICAGO).isoformat(timespec="seconds"),
        "repos": rows,
    }


def census_exit_code(census: dict) -> int:
    for row in census["repos"]:
        if (
            row["mirror_status"] in ("unknown", "skip")
            or row["develop_status"] in ("unknown", "skip")
            or row.get("partial")
        ):
            return 1
    return 0


def validate_census(census) -> list[str]:
    """Schema + invariant check for --check. Returns error strings."""
    errors: list[str] = []
    if not isinstance(census, dict):
        return ["census is not a JSON object"]
    if census.get("version") != 1:
        errors.append("version must be 1")
    if not census.get("generated_at"):
        errors.append("generated_at missing")
    repos = census.get("repos")
    if not isinstance(repos, list):
        return errors + ["repos must be a list"]
    for row in repos:
        name = row.get("repo", "?")
        ms, ds = row.get("mirror_status"), row.get("develop_status")
        if ms not in MIRROR_STATUSES:
            errors.append(f"{name}: mirror_status {ms!r} not in vocabulary")
        if ds not in DEVELOP_STATUSES:
            errors.append(f"{name}: develop_status {ds!r} not in vocabulary")
        for field, status, unmeasured in (
            ("mirror_behind", ms, ("unknown", "no-mirror", "skip")),
            ("mirror_unique", ms, ("unknown", "no-mirror", "skip")),
            ("develop_behind", ds, ("unknown", "skip")),
            ("develop_fork_local", ds, ("unknown", "skip")),
        ):
            value = row.get(field)
            if status in unmeasured:
                if value is not None:
                    errors.append(
                        f"{name}: {field} must be null when status is "
                        f"{status} (never a fabricated zero)"
                    )
            elif not isinstance(value, int) or value < 0:
                errors.append(f"{name}: {field} must be a non-negative int")
        for field in ("mirror_head", "upstream_head", "develop_head"):
            value = row.get(field)
            if value is not None and not SHA_RE.match(str(value)):
                errors.append(f"{name}: {field} is not a full SHA")
    return errors


def _cell(value):
    """Sheet cell form: None -> blank; ints stay ints; SHAs shorten."""
    if value is None:
        return ""
    return value


def _short(sha):
    return sha[:12] if sha else ""


def _canon(row) -> list[str]:
    return [str(v).strip() for v in row]


def _after(later: str, earlier: str) -> bool:
    """True if ISO timestamp `later` is after `earlier`.

    Both writers (fork-sync's run record, this census) emit ISO 8601
    with a UTC offset; parse and compare as datetimes so a DST offset
    change cannot misorder the comparison. An empty `earlier` (no
    previous verification) counts as before everything. Unparseable
    values fall back to string order.
    """
    if not earlier:
        return True
    try:
        return datetime.fromisoformat(later) > datetime.fromisoformat(earlier)
    except ValueError:
        return later > earlier


def build_rows(census, prev_rows, sync_record, verified_at):
    """Derive sheet rows (A:P) from a census + previous sheet state.

    prev_rows: the sheet's current machine range as lists of values
    (strings, as the Sheets API returns them), in sheet order.
    sync_record: fork-sync's JSON run record ({repos: {name:
    {last_applied_at}}}) or {}.
    Returns (rows, changed_indices): rows preserves previous order,
    appends new repos in census order, retires departed ones; a row is
    "changed" when any tracked field (A:P except column O) differs.
    """
    record_repos = (sync_record or {}).get("repos", {})
    prev_by_repo = {}
    prev_order = []
    for prow in prev_rows:
        if prow and str(prow[COL_REPO]).strip():
            repo = str(prow[COL_REPO]).strip()
            if repo not in prev_by_repo:
                prev_order.append(repo)
            # Normalize to exactly the machine range: pad short rows,
            # truncate wide ones -- a caller that hands over Q:R must
            # never see them carried into the output.
            prev_by_repo[repo] = (list(prow) + [""] * ROW_FIELDS)[:ROW_FIELDS]
    census_by_repo = {r["repo"]: r for r in census["repos"]}
    rows: list[list] = []
    changed: list[int] = []

    def emit(repo: str, new_row: list, prev: list | None):
        idx = len(rows)
        rows.append(new_row)
        if prev is None or _canon(new_row[:COL_VERIFIED] + new_row[COL_VERIFIED + 1 :]) != _canon(
            prev[:COL_VERIFIED] + prev[COL_VERIFIED + 1 :]
        ):
            changed.append(idx)

    def census_sheet_row(row: dict, prev: list | None) -> list:
        last_sync = ""
        actor = "fork-fleet-census"
        # Column O is the repo's own measurement time when the
        # census recorded one (rows from older censuses fall back
        # to the run-level stamp): the attribution window compares
        # sync records against it, and a run-completion stamp would
        # exclude syncs applied while the run was still measuring.
        verified = row.get("measured_at") or verified_at
        m_behind, m_unique, m_head = (
            _cell(row["mirror_behind"]),
            _cell(row["mirror_unique"]),
            _short(row["mirror_head"]),
        )
        d_behind, d_local, d_head = (
            _cell(row["develop_behind"]),
            _cell(row["develop_fork_local"]),
            _short(row["develop_head"]),
        )
        if prev is not None:
            last_sync = prev[COL_LAST_SYNC]
            actor = prev[COL_ACTOR] or actor
            # Placeholder rule: an axis that failed to measure keeps
            # the last measured head as its baseline (counts blank,
            # status unknown), and the row's verification stamp only
            # advances when both axes measured -- a failed observation
            # must not erase the baseline a later recovery is
            # attributed against.
            if row["mirror_status"] == "unknown":
                m_behind, m_unique, m_head = "", "", prev[6]
            if row["develop_status"] == "unknown":
                d_behind, d_local, d_head = "", "", prev[11]
            if "unknown" in (row["mirror_status"], row["develop_status"]):
                verified = prev[COL_VERIFIED] or verified_at
            # Attribution is per-axis: each axis is attributable on
            # its own measurement, independently of the other axis.
            # fork-sync moves mirrors only, so a develop-axis failure
            # must not defer (and thereby permanently lose) a mirror
            # attribution -- once the moved head is written, later
            # runs see no movement. Symmetrically, a mirror-axis
            # failure must not defer a develop attribution: column L
            # advances to the measured develop head tonight, so a
            # develop movement left unstamped would be invisible on
            # recovery. An unknown axis (including the
            # consistency-failure shape, whose rejected heads are
            # non-null) is simply not evaluated; if neither axis
            # measured a movement, the previous attribution stands.
            mirror_measured = (
                row["mirror_status"] != "unknown" and row["mirror_head"] is not None
            )
            develop_measured = (
                row["develop_status"] != "unknown"
                and row["develop_head"] is not None
            )
            mirror_moved = mirror_measured and (
                _short(row["mirror_head"]) != str(prev[6]).strip()
            )
            develop_moved = develop_measured and (
                _short(row["develop_head"]) != str(prev[11]).strip()
            )
            if mirror_moved:
                applied = record_repos.get(row["repo"], {}).get(
                    "last_applied_at"
                )
                # The record is evidence only if it is new: after
                # the row's verification stamp AND after the last
                # sync already recorded in column M. M is the
                # consumption watermark -- a partial row's frozen
                # stamp must not let an already-attributed sync be
                # reused for a later, external movement.
                prev_sync = str(prev[COL_LAST_SYNC]).strip()
                if (
                    applied
                    and _after(applied, str(prev[COL_VERIFIED]).strip())
                    and (not prev_sync or _after(applied, prev_sync))
                ):
                    actor = "fork-sync"
                    last_sync = applied
                    if develop_moved:
                        # The sync happened (M records it), but
                        # fork-sync never touches develop: a develop
                        # movement in the same window is not the
                        # bot's, so N must not claim the bot made
                        # the last change.
                        actor = "unknown (external change)"
                else:
                    actor = "unknown (external change)"
            elif develop_moved:
                # A develop-only move is never bot-made.
                actor = "unknown (external change)"
        else:
            applied = record_repos.get(row["repo"], {}).get("last_applied_at")
            if applied:
                last_sync = applied
        notes = row["error"] or ""
        return [
            row["repo"],
            row["upstream"] or "",
            row["mirror_branch"] or "",
            row["mirror_status"],
            m_behind,
            m_unique,
            m_head,
            _short(row["upstream_head"]),
            row["develop_status"],
            d_behind,
            d_local,
            d_head,
            last_sync,
            actor,
            verified,
            notes,
        ]

    seen = set()
    for repo in prev_order:
        seen.add(repo)
        prev = prev_by_repo[repo]
        if repo in census_by_repo:
            emit(repo, census_sheet_row(census_by_repo[repo], prev), prev)
        elif (
            prev[COL_MIRROR_STATUS] == "retired"
            and prev[COL_DEVELOP_STATUS] == "retired"
        ):
            # Already retired: keep the original mark and date; only
            # the verification stamp moves, so the row is not "changed"
            # again on every subsequent run.
            still = list(prev)
            still[COL_VERIFIED] = verified_at
            emit(repo, still, prev)
        else:
            retired = list(prev)
            retired[COL_MIRROR_STATUS] = "retired"
            retired[COL_DEVELOP_STATUS] = "retired"
            retired[COL_VERIFIED] = verified_at
            note = f"retired {verified_at[:10]}"
            retired[COL_NOTES] = (
                f"{prev[COL_NOTES]}; {note}" if prev[COL_NOTES] else note
            )
            emit(repo, retired, prev)
    for row in census["repos"]:
        if row["repo"] not in seen:
            emit(row["repo"], census_sheet_row(row, None), None)
    return rows, changed


def summarize(census: dict) -> dict:
    summary = {"total": len(census["repos"]), "mirror": {}, "develop": {}}
    for row in census["repos"]:
        for axis in ("mirror", "develop"):
            key = f"{axis}_status"
            summary[axis][row[key]] = summary[axis].get(row[key], 0) + 1
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", help="write the census JSON here")
    parser.add_argument("--check", metavar="FILE", help="validate a census file")
    parser.add_argument(
        "--prev-rows",
        metavar="FILE",
        help="JSON list of the sheet's current A:P rows; with --rows-output, "
        "also derive sheet rows",
    )
    parser.add_argument(
        "--rows-output", metavar="FILE", help="write derived sheet rows JSON here"
    )
    parser.add_argument(
        "--sync-record",
        metavar="FILE",
        help="fork-sync JSON run record (attribution columns M/N)",
    )
    args = parser.parse_args(argv)

    if args.check:
        try:
            census = json.loads(Path(args.check).read_text())
        except (OSError, ValueError) as exc:
            print(f"--check: cannot read census: {exc}", file=sys.stderr)
            return 2
        errors = validate_census(census)
        if errors:
            for error in errors:
                print(f"--check: {error}", file=sys.stderr)
            return 1
        print(f"--check: {args.check} is a valid census")
        return 0

    # Read inputs before any ghg call: an I/O failure is fatal (2),
    # never a traceback the agent procedure would read as "partial".
    prev_rows = []
    if args.prev_rows:
        try:
            prev_rows = json.loads(Path(args.prev_rows).read_text())
        except (OSError, ValueError) as exc:
            print(f"FATAL: cannot read --prev-rows: {exc}", file=sys.stderr)
            return 2
    sync_record = {}
    if args.sync_record:
        try:
            sync_record = _load_sync_record(args.sync_record)
        except CensusFatal as exc:
            print(f"FATAL: {exc}", file=sys.stderr)
            return 2

    try:
        census = run_census(ghg_runner)
    except BudgetDenied as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2
    except CensusFatal as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2

    if args.sync_record:
        # Refresh the record now that measurement is done: fork-sync
        # may have applied (and recorded) a sync while this census
        # was measuring. The pre-census copy would label that
        # movement external and advance the stored head past it, so
        # no later run could ever repair the attribution. A failed
        # refresh is fatal, like the first read.
        try:
            sync_record = _load_sync_record(args.sync_record)
        except CensusFatal as exc:
            print(f"FATAL: {exc}", file=sys.stderr)
            return 2

    code = census_exit_code(census)
    census["exit_status"] = "complete" if code == 0 else "partial"
    census["summary"] = summarize(census)
    try:
        if args.output:
            Path(args.output).write_text(json.dumps(census, indent=1))
        if args.rows_output:
            rows, changed = build_rows(
                census, prev_rows, sync_record, census["generated_at"]
            )
            Path(args.rows_output).write_text(
                json.dumps({"rows": rows, "changed": changed}, indent=1)
            )
    except OSError as exc:
        print(f"FATAL: cannot write output: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(census["summary"]))
    return code


if __name__ == "__main__":
    sys.exit(main())
