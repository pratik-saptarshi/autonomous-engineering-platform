"""Fixture-tested adapter over the repo-hosted tracker (GitHub).

Stage 1 builds and tests this adapter **against fixtures only**; its
live path is exercised only inside Task 1.6's conditional section,
behind its gates. Nothing here reads the live tracker in Stage 1.

Every tracker call is *gated*: built by the module's single argv
helper, :func:`gated_argv`, and executed through the module's single
call site, :meth:`GitHubAdapter._run_gated`, via an injectable
``runner`` seam. The gateway (``ghg``) executes ``gh`` itself, so the
helper's parts are gh's arguments with no leading ``gh`` element:
``gated_argv(wf, "issue", "list", ...)`` produces
``ghg run --actor orch-<project_slug> -- issue list ...`` (the
``--actor`` spelling is the gateway's own, verified against its
README usage line and argument parser). Bare ``gh`` is never invoked.

Budget outcomes are typed, never tracebacks and never silent empty
results:

- the gateway's exit 75 raises :class:`BudgetDenied`;
- beginning a call that would exceed ``workflow.max_calls_per_poll``
  raises :class:`BudgetExceeded` *before* the call executes. The call
  counter resets when a poll opens (``fetch_candidates``); every gated
  call through the instance counts toward the current poll, including
  blocker resolution and the ``@me`` lookup.

Points accounting: :meth:`GitHubAdapter.points_spent` reports the
poll's cost in gateway **points**, summed from the gateway ledger's
finalized charges for this adapter's actor over the poll interval —
via the injectable ``points_of`` seam when one is given, else a
read-only query of the ledger database under ``$GHG_STATE_DIR``. An
unavailable or unreadable ledger yields ``None`` (unmeasured), never
an estimate.

Normalization rules (pinned):

- candidates come from **one** list call, open state only; closed and
  terminal issues are never list-fetched. Blocker and by-id state
  resolution goes through ``fetch_by_ids``, so a closed blocker
  resolves truthfully instead of being invisible. A list result whose
  count equals ``github_fetch_limit`` sets ``last_truncated`` — a
  capped fetch is reported, never silent.
- state: a ``status:<name>`` label supplies the normalized state, else
  ``open``; a by-id record carrying the closed state maps to
  ``closed`` (terminal class).
- priority: from ``workflow.priority_labels``; no priority label maps
  to ``None`` (sorts last); multiple priority labels resolve to the
  lowest number.
- blockers: from ``blocked-by:<number>`` labels, each number resolved
  by number through the by-id path. A blocker that cannot be resolved
  is carried with an empty state, which is not terminal — it counts
  as blocking until known otherwise. This tracker does not currently
  use ``blocked-by:`` labels, so on live data today this yields zero
  blockers; the dry-run says so rather than implying dependency
  coverage the data does not carry.
- by-ids queries by issue **number** (the ``gh issue view <number>``
  form), never by node id. A missing number is *omitted*, per the
  Protocol's absence semantics.
- assignee: ``assigned_to_worker`` is the workflow assignee — or, for
  ``@me``, the login resolved by one gated ``api user`` call per
  process, cached — appearing among the issue's assignee logins.
- author association: ``author_ok`` is computed here, never by the
  engine. Under ``"owner"`` the author's login must equal the repo's
  owner segment or the operator's own (``@me``) login; ``"any"``
  lifts the condition. Logins compare case-insensitively, as the
  tracker treats them.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

from orch.model import BlockerRef, Issue
from orch.workflow import Workflow

__all__ = [
    "BudgetDenied",
    "BudgetExceeded",
    "GitHubAdapter",
    "GitHubError",
    "gated_argv",
]

# The list/view field set. ``author`` rides along with the brief's
# pinned fields: the author-association rule consumes the payload's
# author login, which an unrequested field would silently starve.
_JSON_FIELDS = (
    "number,title,body,state,labels,assignees,author,createdAt,updatedAt,url"
)

# Ledger outcomes that represent a finalized charge (the gateway's
# terminal set); reservations are excluded — they are not final.
_TERMINAL_OUTCOMES = (
    "ok",
    "error",
    "denied",
    "bypass",
    "ungated_error",
    "abandoned",
)


class GitHubError(RuntimeError):
    """A gated tracker call could not be run, or its output read."""


class GitHubNotFound(GitHubError):
    """The requested issue number does not resolve on the tracker."""


class BudgetDenied(Exception):
    """The gateway denied a call on budget grounds (its exit 75)."""


class BudgetExceeded(Exception):
    """A call would exceed the spec's ``max_calls_per_poll``."""


def gated_argv(workflow: Workflow, *parts: str) -> list[str]:
    """Build one gated argv: the gateway prefix plus gh's arguments.

    The parts are gh's own arguments (for example ``"issue", "list",
    ...``) with no leading ``gh`` element — the gateway performs the
    gh invocation. Actor attribution rides the gateway's ``--actor``
    flag as ``orch-<project_slug>``.
    """
    return [
        "ghg",
        "run",
        "--actor",
        f"orch-{workflow.project_slug}",
        "--",
        *parts,
    ]


class GitHubAdapter:
    """Fixture-tested :class:`~orch.model.TrackerAdapter` over ``ghg``."""

    def __init__(
        self,
        workflow: Workflow,
        runner=subprocess.run,
        points_of=None,
    ) -> None:
        self._workflow = workflow
        self._runner = runner
        self._points_of = points_of
        self._actor = f"orch-{workflow.project_slug}"
        # Terminality is the spec's alone (panel A1): no hardcoded
        # addition to the workflow's terminal_states.
        self._terminal_states = {
            str(state).lower() for state in workflow.terminal_states
        }
        self._priority_labels = {
            str(name).lower(): value
            for name, value in workflow.priority_labels.items()
        }
        self._me_login_cache: str | None = None
        self.last_truncated = False
        self.last_fetch_count = 0
        self._calls_made = 0
        self._poll_started_at = int(time.time())

    # ------------------------------------------------------------------
    # Gated plumbing: one helper (above), one call site (here)
    # ------------------------------------------------------------------

    def _run_gated(self, argv: list[str]):
        """Execute one gated argv through the runner seam.

        Raises :class:`BudgetExceeded` before executing when the poll's
        call cap is already reached, :class:`BudgetDenied` on the
        gateway's exit 75, :class:`GitHubNotFound` when the tracker
        reports an unresolvable issue number, and :class:`GitHubError`
        for every other failure.
        """
        if self._calls_made >= self._workflow.max_calls_per_poll:
            raise BudgetExceeded(
                f"poll call cap reached ({self._workflow.max_calls_per_poll});"
                " refusing to begin another gated call"
            )
        self._calls_made += 1
        try:
            proc = self._runner(argv, capture_output=True, text=True)
        except OSError as exc:
            raise GitHubError(f"failed to run the gateway: {exc}") from exc
        if proc.returncode == 75:
            raise BudgetDenied(
                "the gateway denied the call on budget grounds (exit 75):"
                f" {' '.join(argv)}"
            )
        if proc.returncode != 0:
            stderr = proc.stderr or ""
            if "Could not resolve" in stderr:
                raise GitHubNotFound(stderr.strip())
            detail = stderr.strip()
            raise GitHubError(
                f"gated call {' '.join(argv)} failed with exit"
                f" {proc.returncode}" + (f": {detail}" if detail else "")
            )
        return proc

    def _run_json(self, argv: list[str]):
        proc = self._run_gated(argv)
        try:
            return json.loads(proc.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise GitHubError(
                f"gated call {' '.join(argv)} returned unparseable JSON:"
                f" {exc}"
            ) from exc

    def _repo(self) -> str:
        repo = self._workflow.repo
        if not repo:
            raise GitHubError(
                "the spec names no repo; the repo-hosted tracker adapter"
                " cannot run without one"
            )
        return repo

    def _me_login(self) -> str:
        """The operator's own login; one gated call per process, cached."""
        if self._me_login_cache is None:
            proc = self._run_gated(
                gated_argv(self._workflow, "api", "user", "--jq", ".login")
            )
            login = (proc.stdout or "").strip()
            if not login:
                raise GitHubError("the gateway's api user call returned"
                                  " no login")
            self._me_login_cache = login
        return self._me_login_cache

    # ------------------------------------------------------------------
    # Points accounting
    # ------------------------------------------------------------------

    def points_spent(self) -> int | None:
        """The current poll's cost in gateway points, or ``None``.

        ``None`` means unmeasured: the ledger was unavailable or
        unreadable. The figure is never estimated.
        """
        if self._points_of is not None:
            return self._points_of()
        return self._ledger_points()

    def _ledger_points(self) -> int | None:
        state_dir = os.environ.get("GHG_STATE_DIR")
        base = (
            Path(state_dir)
            if state_dir
            else Path.home() / "workspace" / "ghg-state"
        )
        db_path = base / "ghg.db"
        if not db_path.is_file():
            return None
        placeholders = ", ".join("?" for _ in _TERMINAL_OUTCOMES)
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                row = conn.execute(
                    "SELECT COALESCE(SUM(cost), 0) FROM calls"
                    f" WHERE actor = ? AND outcome IN ({placeholders})"
                    " AND ts >= ?",
                    (self._actor, *_TERMINAL_OUTCOMES, self._poll_started_at),
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            return None
        return int(row[0])

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _key(self, number: str) -> str:
        return f"{self._workflow.tracker}:{number}"

    def _raw_id(self, key: str) -> str:
        prefix = f"{self._workflow.tracker}:"
        return key[len(prefix) :] if key.startswith(prefix) else key

    @staticmethod
    def _label_names(record: dict) -> list[str]:
        names = []
        for label in record.get("labels") or []:
            if isinstance(label, dict):
                name = label.get("name")
            else:
                name = label
            if name:
                names.append(str(name).lower())
        return names

    def _state_of(self, record: dict, label_names: list[str]) -> str:
        if str(record.get("state") or "").upper() == "CLOSED":
            return "closed"
        for name in label_names:
            if name.startswith("status:"):
                return name[len("status:") :]
        return "open"

    def _priority(self, label_names: list[str]) -> int | None:
        values = [
            self._priority_labels[name]
            for name in label_names
            if name in self._priority_labels
        ]
        return min(values) if values else None

    @staticmethod
    def _blocker_numbers(label_names: list[str]) -> list[str]:
        return [
            name[len("blocked-by:") :]
            for name in label_names
            if name.startswith("blocked-by:") and name[len("blocked-by:") :]
        ]

    def _blockers(
        self, label_names: list[str], blocker_states: dict[str, str]
    ) -> tuple[BlockerRef, ...]:
        return tuple(
            BlockerRef.from_state(
                self._key(number),
                blocker_states.get(number, ""),
                self._terminal_states,
            )
            for number in self._blocker_numbers(label_names)
        )

    def _assignee_login(self) -> str:
        if self._workflow.assignee == "@me":
            return self._me_login()
        return self._workflow.assignee

    def _author_ok(self, author: str | None) -> bool:
        association = (self._workflow.author_association or "owner").lower()
        if association == "any":
            return True
        if author is None:
            return False
        owner_segment = self._repo().split("/")[0]
        if author.lower() == owner_segment.lower():
            return True
        return author.lower() == self._me_login().lower()

    def _normalize(
        self, record: dict, blocker_states: dict[str, str]
    ) -> Issue:
        number = str(record["number"])
        label_names = self._label_names(record)
        assignee_logins = [
            str(assignee.get("login"))
            for assignee in record.get("assignees") or []
            if isinstance(assignee, dict) and assignee.get("login")
        ]
        author = None
        author_field = record.get("author")
        if isinstance(author_field, dict) and author_field.get("login"):
            author = str(author_field["login"])
        return Issue(
            key=self._key(number),
            identifier=number,
            title=str(record.get("title") or ""),
            description=str(record.get("body") or ""),
            state=self._state_of(record, label_names),
            priority=self._priority(label_names),
            labels=tuple(label_names),
            blockers=self._blockers(label_names, blocker_states),
            created_at=str(record.get("createdAt") or ""),
            updated_at=str(record.get("updatedAt") or ""),
            url=str(record.get("url") or ""),
            assignee=assignee_logins[0] if assignee_logins else None,
            assigned_to_worker=self._assignee_login().lower()
            in {login.lower() for login in assignee_logins},
            author=author,
            author_ok=self._author_ok(author),
        )

    # ------------------------------------------------------------------
    # TrackerAdapter reads
    # ------------------------------------------------------------------

    def _fetch_record(self, number: str) -> dict | None:
        """One by-id record by issue number; ``None`` when absent."""
        try:
            payload = self._run_json(
                gated_argv(
                    self._workflow,
                    "issue",
                    "view",
                    number,
                    "--repo",
                    self._repo(),
                    "--json",
                    _JSON_FIELDS,
                )
            )
        except GitHubNotFound:
            return None
        if not isinstance(payload, dict):
            raise GitHubError(
                f"issue view {number} returned an unexpected payload shape"
            )
        return payload

    def _blocker_states(self, records: list[dict]) -> dict[str, str]:
        """Resolve every ``blocked-by:`` number across ``records`` once."""
        numbers = []
        for record in records:
            for number in self._blocker_numbers(self._label_names(record)):
                if number not in numbers:
                    numbers.append(number)
        states = {}
        for number in numbers:
            blocker_record = self._fetch_record(number)
            if blocker_record is not None:
                states[number] = self._state_of(
                    blocker_record, self._label_names(blocker_record)
                )
        return states

    def fetch_candidates(self) -> list[Issue]:
        # A poll opens here: its call budget and points window reset.
        self._calls_made = 0
        self._poll_started_at = int(time.time())
        payload = self._run_json(
            gated_argv(
                self._workflow,
                "issue",
                "list",
                "--repo",
                self._repo(),
                "--state",
                "open",
                "--limit",
                str(self._workflow.github_fetch_limit),
                "--json",
                _JSON_FIELDS,
            )
        )
        if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise GitHubError("issue list returned an unexpected payload"
                              " shape")
        self.last_fetch_count = len(payload)
        self.last_truncated = (
            len(payload) == self._workflow.github_fetch_limit
        )
        blocker_states = self._blocker_states(payload)
        return [self._normalize(record, blocker_states) for record in payload]

    def fetch_by_ids(self, keys: list[str]) -> list[Issue]:
        records = []
        for key in keys:
            record = self._fetch_record(self._raw_id(key))
            if record is not None:
                records.append(record)
        blocker_states = self._blocker_states(records)
        return [self._normalize(record, blocker_states) for record in records]

    def fetch_states(self, keys: list[str]) -> dict[str, str]:
        return {issue.key: issue.state for issue in self.fetch_by_ids(keys)}

    # ------------------------------------------------------------------
    # Writes: not in Stage 1
    # ------------------------------------------------------------------

    def comment(self, key: str, body: str) -> None:
        raise NotImplementedError("read-only in Stage 1")

    def transition(self, key: str, state_name: str) -> None:
        raise NotImplementedError("read-only in Stage 1")
