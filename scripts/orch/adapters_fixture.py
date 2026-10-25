"""In-memory tracker adapter used by orchestrator tests and drills."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Mapping

from orch.model import Issue

__all__ = ["FixtureAdapter"]


class FixtureAdapter:
    """A dict-backed :class:`~orch.model.TrackerAdapter` implementation.

    The adapter stores issues by their normalized ``Issue.key``. Missing
    keys are omitted from fetch results; in particular, absence from
    ``fetch_states`` is how callers detect that an issue has vanished.
    """

    def __init__(
        self,
        issues: Mapping[str, Issue | Mapping[str, object]]
        | Iterable[Issue | Mapping[str, object]]
        | Issue
        | Mapping[str, object]
        | None = None,
    ) -> None:
        self._issues: dict[str, Issue] = {}
        self._next_fetch_failure: BaseException | None = None

        if issues is None:
            return
        if isinstance(issues, Issue):
            values: Iterable[Issue | Mapping[str, object]] = (issues,)
        elif isinstance(issues, Mapping) and "key" in issues:
            values = (issues,)
        elif isinstance(issues, Mapping):
            values = issues.values()
        else:
            values = issues

        for value in values:
            issue = (
                value
                if isinstance(value, Issue)
                else Issue(**dict(value))
            )
            self._issues[issue.key] = issue

    def _raise_scheduled_fetch_failure(self) -> None:
        if self._next_fetch_failure is not None:
            failure = self._next_fetch_failure
            self._next_fetch_failure = None
            raise failure

    def fetch_candidates(self) -> list[Issue]:
        self._raise_scheduled_fetch_failure()
        return list(self._issues.values())

    def fetch_by_ids(self, keys: list[str]) -> list[Issue]:
        self._raise_scheduled_fetch_failure()
        return [self._issues[key] for key in keys if key in self._issues]

    def fetch_states(self, keys: list[str]) -> dict[str, str]:
        self._raise_scheduled_fetch_failure()
        return {
            key: self._issues[key].state
            for key in keys
            if key in self._issues
        }

    def comment(self, key: str, body: str) -> None:
        raise NotImplementedError("read-only in Stage 1")

    def transition(self, key: str, state_name: str) -> None:
        raise NotImplementedError("read-only in Stage 1")

    def set_state(self, key: str, state: str) -> None:
        """Change the state of a stored issue, or raise ``KeyError``."""

        try:
            issue = self._issues[key]
        except KeyError:
            raise KeyError(key) from None
        self._issues[key] = replace(issue, state=state)

    def remove(self, key: str) -> None:
        """Remove a stored issue, or raise ``KeyError`` if it is absent."""

        try:
            del self._issues[key]
        except KeyError:
            raise KeyError(key) from None

    def fail_next_fetch(self, exc: BaseException) -> None:
        """Make the next fetch operation raise ``exc`` exactly once."""

        self._next_fetch_failure = exc
