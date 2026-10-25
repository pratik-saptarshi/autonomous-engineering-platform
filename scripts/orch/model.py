"""Normalized tracker issue model shared by all orchestrator adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

__all__ = ["BlockerRef", "Issue", "TrackerAdapter"]


@dataclass(frozen=True)
class BlockerRef:
    """A reference to an issue that may block another issue.

    Adapters derive ``is_terminal`` against the workflow's terminal-state
    set: a blocker continues to block until its state is in that set.
    """

    key: str
    state: str
    is_terminal: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", self.state.lower())
        object.__setattr__(self, "is_terminal", bool(self.is_terminal))

    @classmethod
    def from_state(
        cls,
        key: str,
        state: str,
        terminal_states: Iterable[str],
    ) -> "BlockerRef":
        """Build a blocker reference, deriving ``is_terminal`` by state."""

        normalized_state = state.lower()
        normalized_terminal_states = {
            terminal_state.lower() for terminal_state in terminal_states
        }
        return cls(
            key=key,
            state=normalized_state,
            is_terminal=normalized_state in normalized_terminal_states,
        )


@dataclass(frozen=True)
class Issue:
    """The tracker-independent issue shape consumed by the engine.

    ``key`` is the adapter-scoped stable form (``"<tracker>:<raw-id>"``),
    while ``identifier`` is the human-facing form. A priority of ``None``
    means that the tracker supplied no priority and therefore sorts last.
    Adapter-computed fields, including ``assigned_to_worker`` and
    ``author_ok``, are populated by adapters rather than by the engine.
    """

    key: str
    identifier: str
    title: str
    description: str = ""
    state: str = "open"
    priority: int | None = None
    labels: tuple[str, ...] = ()
    blockers: tuple[BlockerRef, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    status_since: str | None = None
    url: str = ""
    branch: str | None = None
    assignee: str | None = None
    assigned_to_worker: bool = False
    author: str | None = None
    author_ok: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", self.state.lower())

        labels = (
            (self.labels,)
            if isinstance(self.labels, str)
            else tuple(self.labels)
        )
        object.__setattr__(
            self, "labels", tuple(label.lower() for label in labels)
        )

        blockers = (
            (self.blockers,)
            if isinstance(self.blockers, BlockerRef)
            else tuple(self.blockers)
        )
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(
            self, "assigned_to_worker", bool(self.assigned_to_worker)
        )
        object.__setattr__(self, "author_ok", bool(self.author_ok))


@runtime_checkable
class TrackerAdapter(Protocol):
    """The read/write contract implemented by each tracker adapter.

    Stage 1 implementations provide the three read operations. Their
    ``comment`` and ``transition`` methods raise
    ``NotImplementedError("read-only in Stage 1")`` until write support is
    enabled by a later stage.
    """

    def fetch_candidates(self) -> list[Issue]:
        """Return the issues currently eligible for adapter filtering."""
        ...

    def fetch_by_ids(self, keys: list[str]) -> list[Issue]:
        """Return the requested issues that are present on the tracker."""
        ...

    def fetch_states(self, keys: list[str]) -> dict[str, str]:
        """Return current states for requested issues that are present."""
        ...

    def comment(self, key: str, body: str) -> None:
        """Add a comment to an issue."""
        ...

    def transition(self, key: str, state_name: str) -> None:
        """Move an issue to the named state."""
        ...
