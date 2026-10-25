"""Read-only adapter over the local beads issue database (the ``bd`` CLI).

Reads shell out to ``bd`` through an injectable ``runner`` seam (default
``subprocess.run``) with ``cwd`` set to the workflow's project root:

- candidates: ``bd list --json --all --limit 0`` — the limit is pinned:
  an unpinned fetch silently windows the result set, so completeness is
  a property of the argv, not an assumption. A fetch returning more
  records than ``workflow.max_candidates`` raises
  :class:`FetchCeilingExceeded` instead of truncating.
- by-ids: ``bd show <id> --json`` per id. On this track the native id
  *is* the human form (``dap-…``), so no identifier translation exists
  to get wrong. A missing id is *omitted*, per the Protocol's absence
  semantics: ``bd show`` reports it with exit 1, a JSON
  ``{"error": "no issues found …"}`` object on stdout, and
  ``Issue <id> not found`` on stderr. Only that not-found signal
  omits — every other ``bd`` failure raises :class:`BeadsError`.
- states: resolved from the same list fetch; a requested key absent
  from the fetch is omitted, which is how callers detect a vanished
  issue.

Blockers come **only** from each record's embedded ``dependencies``
list — the ``blocks`` entries, resolved against the states of the
referenced records from the same fetch. There is no separate edge
table in this database and the adapter never looks for one; a record
carrying no ``dependencies`` key has zero blockers. A blocker target
absent from the fetch is carried with an empty state, which is not
terminal — a blocker counts as blocking until its state is known to
be terminal.

The two read paths spell that list differently, and both spellings are
handled: ``bd list`` emits edge objects (``type`` + ``depends_on_id``),
while ``bd show`` embeds the target records themselves, each carrying
``dependency_type`` and its own ``id``.

There is no author-association rule on this track (that rule belongs to
the repo-hosted track): ``Issue.author`` is the record's ``created_by``
where the record carries one, else ``None``, and ``author_ok`` is true.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from orch.model import BlockerRef, Issue
from orch.workflow import Workflow

__all__ = ["BeadsAdapter", "BeadsError", "FetchCeilingExceeded"]


class BeadsError(RuntimeError):
    """The beads CLI could not be run, or its output could not be read."""


class FetchCeilingExceeded(Exception):
    """A fetch returned more records than ``max_candidates`` allows."""


class BeadsAdapter:
    """Read-only :class:`~orch.model.TrackerAdapter` over ``bd``."""

    def __init__(self, workflow: Workflow, runner=subprocess.run) -> None:
        self._workflow = workflow
        self._runner = runner
        self.last_fetch_count = 0
        self.last_type_excluded_count = 0
        # "closed" is terminal on this track regardless of the spec's
        # terminal vocabulary (the pinned state-mapping rule); the
        # workflow's terminal states add to it.
        self._terminal_states = {
            str(state).lower() for state in workflow.terminal_states
        } | {"closed"}

    # ------------------------------------------------------------------
    # bd plumbing
    # ------------------------------------------------------------------

    def _bd_path(self) -> str:
        path = shutil.which("bd")
        if path is None:
            raise BeadsError(
                "bd executable not found on PATH; on this fleet bd is "
                "installed under ~/go/bin and resolves in login shells "
                "only — run from a login shell or add ~/go/bin to PATH"
            )
        return path

    @staticmethod
    def _is_not_found(proc, raw_id: str) -> bool:
        """Whether a failed ``bd show`` is the CLI's not-found signal.

        Verified against the real CLI: exit 1, a JSON error object
        (``{"error": "no issues found matching the provided IDs", …}``)
        on stdout, and ``Issue <id> not found`` on stderr. Either
        signal suffices; anything else is a genuine failure.
        """
        if f"Issue {raw_id} not found" in (proc.stderr or ""):
            return True
        try:
            payload = json.loads(proc.stdout or "")
        except json.JSONDecodeError:
            return False
        if isinstance(payload, dict):
            error = payload.get("error")
            return isinstance(error, str) and "no issues found" in error
        return False

    def _run_bd(self, *args: str, not_found_id: str | None = None) -> list[dict]:
        argv = [self._bd_path(), *args]
        try:
            proc = self._runner(
                argv,
                cwd=self._workflow.project_root,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise BeadsError(f"failed to run bd: {exc}") from exc
        if proc.returncode != 0:
            if not_found_id is not None and self._is_not_found(proc, not_found_id):
                return []
            detail = (proc.stderr or "").strip()
            raise BeadsError(
                f"bd {' '.join(args)} failed with exit {proc.returncode}"
                + (f": {detail}" if detail else "")
            )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise BeadsError(
                f"bd {' '.join(args)} returned unparseable JSON: {exc}"
            ) from exc
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list) and all(
            isinstance(item, dict) for item in payload
        ):
            return payload
        raise BeadsError(
            f"bd {' '.join(args)} returned an unexpected payload shape"
        )

    def _fetch_all_records(self) -> list[dict]:
        records = self._run_bd("list", "--json", "--all", "--limit", "0")
        self.last_fetch_count = len(records)
        if len(records) > self._workflow.max_candidates:
            raise FetchCeilingExceeded(
                f"beads fetch returned {len(records)} records, above the "
                f"spec's max_candidates of {self._workflow.max_candidates}; "
                "refusing to continue with a possibly truncated view"
            )
        return records

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _key(self, raw_id: str) -> str:
        return f"{self._workflow.tracker}:{raw_id}"

    def _raw_id(self, key: str) -> str:
        prefix = f"{self._workflow.tracker}:"
        return key[len(prefix) :] if key.startswith(prefix) else key

    @staticmethod
    def _state_of(record: dict) -> str:
        return str(record.get("status") or "").lower()

    def _blockers(
        self, record: dict, state_by_id: dict[str, str]
    ) -> tuple[BlockerRef, ...]:
        blockers = []
        for dep in record.get("dependencies") or []:
            if not isinstance(dep, dict):
                continue
            if "depends_on_id" in dep:
                # `bd list` shape: an edge object.
                dep_type, target = dep.get("type"), dep.get("depends_on_id")
            else:
                # `bd show` shape: the embedded target record itself.
                dep_type, target = dep.get("dependency_type"), dep.get("id")
            if dep_type != "blocks" or not target:
                continue
            target = str(target)
            blockers.append(
                BlockerRef.from_state(
                    self._key(target),
                    state_by_id.get(target, ""),
                    self._terminal_states,
                )
            )
        return tuple(blockers)

    @staticmethod
    def _status_since(record: dict, state: str) -> str | None:
        history = record.get("history") or record.get("status_history")
        if not isinstance(history, list):
            return None
        stamps = []
        for entry in history:
            if not isinstance(entry, dict):
                continue
            entry_state = entry.get("status") or entry.get("new_status")
            if entry_state is None or str(entry_state).lower() != state:
                continue
            stamp = (
                entry.get("created_at")
                or entry.get("timestamp")
                or entry.get("changed_at")
            )
            if stamp:
                stamps.append(str(stamp))
        return max(stamps) if stamps else None

    def _normalize(self, record: dict, state_by_id: dict[str, str]) -> Issue:
        raw_id = str(record["id"])
        state = self._state_of(record)
        assignee = record.get("assignee") or None
        return Issue(
            key=self._key(raw_id),
            identifier=raw_id,
            title=str(record.get("title") or ""),
            description=str(record.get("description") or ""),
            state=state,
            priority=record.get("priority"),
            labels=tuple(record.get("labels") or ()),
            blockers=self._blockers(record, state_by_id),
            created_at=str(record.get("created_at") or ""),
            updated_at=str(record.get("updated_at") or ""),
            status_since=self._status_since(record, state),
            assignee=assignee,
            assigned_to_worker=assignee == self._workflow.assignee,
            author=record.get("created_by") or None,
            author_ok=True,
        )

    @staticmethod
    def _state_map(records: list[dict]) -> dict[str, str]:
        return {str(record["id"]): BeadsAdapter._state_of(record) for record in records}

    # ------------------------------------------------------------------
    # TrackerAdapter reads
    # ------------------------------------------------------------------

    def fetch_candidates(self) -> list[Issue]:
        records = self._fetch_all_records()
        state_by_id = self._state_map(records)
        allowed = {str(t).lower() for t in self._workflow.issue_types}
        kept = []
        excluded = 0
        for record in records:
            if str(record.get("issue_type") or "").lower() not in allowed:
                excluded += 1
                continue
            kept.append(record)
        self.last_type_excluded_count = excluded
        return [self._normalize(record, state_by_id) for record in kept]

    def fetch_by_ids(self, keys: list[str]) -> list[Issue]:
        # Blocker states resolve against the full fetch, as in
        # fetch_candidates; the records themselves come from `bd show`.
        state_by_id = self._state_map(self._fetch_all_records())
        issues = []
        for key in keys:
            raw_id = self._raw_id(key)
            for record in self._run_bd(
                "show", raw_id, "--json", not_found_id=raw_id
            ):
                issues.append(self._normalize(record, state_by_id))
        return issues

    def fetch_states(self, keys: list[str]) -> dict[str, str]:
        state_by_id = self._state_map(self._fetch_all_records())
        states = {}
        for key in keys:
            raw_id = self._raw_id(key)
            if raw_id in state_by_id:
                states[key] = state_by_id[raw_id]
        return states

    # ------------------------------------------------------------------
    # Writes: not in Stage 1
    # ------------------------------------------------------------------

    def comment(self, key: str, body: str) -> None:
        raise NotImplementedError("read-only in Stage 1")

    def transition(self, key: str, state_name: str) -> None:
        raise NotImplementedError("read-only in Stage 1")
