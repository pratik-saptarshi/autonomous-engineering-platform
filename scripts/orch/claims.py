"""Lane-name encoding and the manifest-backed claim view.

The lane name is the join key between tracker identifiers, the eligibility
engine, and lane-coord's manifests. The encoding follows lane-coord's slug
grammar (``^[a-z0-9][a-z0-9-]*$``) by construction.

lane-coord names a lane ``<project>-<lane>``: the claim's ``--project``
and ``--lane`` arguments are each validated against the slug grammar
(never rewritten), and the manifest is ``<project>-<lane>.json``.
:func:`lane_name_for` mirrors that composition — the lane part is the
slug encoding of the identifier, the project part is the workflow's
``project_slug`` — except when the identifier's encoding already begins
with the project namespace: beads identifiers embed their project
prefix (``dap-…``, and the spec's ``project_slug`` is that same
prefix), so prefixing again would double it and match no manifest the
coordinator writes.

``ManifestClaimView`` reads lane-coord's manifest files. Ground truth,
pinned against ``scripts/lane-coord.sh``: manifests live at
``<lanes-dir>/<lane-name>.json`` (one JSON object per lane, written by
``write_manifest`` via temp file + rename); the state field is ``state``;
the active-claim value written at claim time is ``"claimed"`` (lane-coord's
own capacity count tests exactly that value); settled values are
``"released"``, ``"reaped"``, and ``"cleaned"`` and never block. The lanes
directory resolves exactly as lane-coord resolves it: ``$AEP_LANES_DIR``
when set, else ``~/workspace/worktrees/.lanes``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = [
    "ACTIVE_CLAIM_STATE",
    "ClaimView",
    "LanesDirMissing",
    "ManifestClaimView",
    "lane_name_for",
]

_NON_SLUG_CHARS = re.compile(r"[^a-z0-9-]")
_MAX_LANE_NAME = 48
_TRUNCATED_BODY = 41
_HASH_PREFIX = 6
ACTIVE_CLAIM_STATE = "claimed"


class LanesDirMissing(Exception):
    """The resolved lanes directory does not exist.

    Raised loudly: a claim view that silently reports no claims would
    report safety it has not observed.
    """


def lane_name_for(identifier: str, project_slug: str | None = None) -> str:
    """Encode an issue identifier as the coordinator's lane name.

    The lane part is the slug encoding of the identifier (capped at
    48 characters, hash-suffixed when truncated). With
    ``project_slug``, the result is the manifest name lane-coord
    writes, ``<project>-<lane>`` — unless the lane part already
    begins with the project namespace (beads identifiers embed it),
    in which case it stands as is. Without ``project_slug``, the
    bare lane part is returned.
    """

    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    mapped = _NON_SLUG_CHARS.sub("-", identifier.lower()).strip("-")
    if not mapped:
        mapped = f"x-{digest[:_HASH_PREFIX]}"
    elif len(mapped) > _MAX_LANE_NAME:
        mapped = mapped[:_TRUNCATED_BODY] + "-" + digest[:_HASH_PREFIX]
    if project_slug:
        namespace = project_slug.lower()
        if not mapped.startswith(namespace + "-"):
            mapped = f"{namespace}-{mapped}"
    return mapped


@runtime_checkable
class ClaimView(Protocol):
    """Read-only view of what is already claimed or running."""

    warnings: list[str]

    def claimed_lanes(self) -> set[str]:
        """Lane names with an active claim."""
        ...

    def running_by_state(self) -> dict[str, int]:
        """Count of running dispatches per normalized tracker state."""
        ...


def _resolve_lanes_dir(lanes_dir: str | None) -> Path:
    if lanes_dir is not None:
        return Path(lanes_dir)
    env_dir = os.environ.get("AEP_LANES_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / "workspace" / "worktrees" / ".lanes"


class ManifestClaimView:
    """Claim view backed by lane-coord's manifest files.

    Only manifests whose recorded ``state`` is the active-claim value
    count as claimed; settled manifests do not block. Files that fail to
    parse (or carry no usable state) are skipped and named in
    ``warnings``. ``running_by_state`` returns ``{}``: manifests do not
    carry tracker states.
    """

    def __init__(self, lanes_dir: str | None = None) -> None:
        self._lanes_dir = _resolve_lanes_dir(lanes_dir)
        if not self._lanes_dir.is_dir():
            raise LanesDirMissing(
                f"lanes directory does not exist: {self._lanes_dir} "
                "(resolved as lane-coord resolves it: $AEP_LANES_DIR, "
                "else ~/workspace/worktrees/.lanes)"
            )
        self.warnings: list[str] = []
        self._claimed: set[str] = set()
        self._scan()

    def _scan(self) -> None:
        for path in sorted(self._lanes_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self.warnings.append(
                    f"skipping unparseable lane manifest {path.name}: {exc}"
                )
                continue
            state = data.get("state") if isinstance(data, dict) else None
            if not isinstance(state, str):
                self.warnings.append(
                    f"skipping lane manifest {path.name}: no usable 'state' field"
                )
                continue
            if state == ACTIVE_CLAIM_STATE:
                self._claimed.add(path.stem)

    def claimed_lanes(self) -> set[str]:
        return set(self._claimed)

    def running_by_state(self) -> dict[str, int]:
        return {}
