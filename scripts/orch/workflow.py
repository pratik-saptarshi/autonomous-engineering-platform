"""Workflow-file loader for the orchestrator.

Parses the pinned frontmatter subset by hand (stdlib only — no YAML
library), validates the result into a frozen :class:`Workflow`, and carries
the bidirectional knob census (:data:`FIELD_CONSUMERS`): every field names
the task that consumes it, and a spec key with no field is a load warning,
so an inert knob cannot ship silently in either direction.

Grammar (the whole subset — anything outside it is a load error naming
the line, never a best-effort parse):

- The file opens with a ``---`` line; the frontmatter ends at the next
  ``---`` line. Everything after it is the prompt template, verbatim.
- Inside: ``key: value`` lines. Keys match ``[a-z][a-z0-9_]*``. One level
  of section nesting: a bare ``key:`` line followed by two-space-indented
  ``key: value`` lines. Deeper nesting, tabs, and duplicate keys are load
  errors.
- Lists are ``[a, b, c]``; entries may contain ``:`` and ``=``. Dict
  fields ride either a section or the ``[key=value, ...]`` list form
  (exactly one ``=`` per entry).
- Scalars are strings, integers, floats, ``true``/``false``, or ``null``.
  An integer literal is accepted for a float field (coerced).
- Comments: a line whose first non-space character is ``#`` is skipped; a
  trailing comment begins at the first `` #`` and is stripped before
  parsing (a value needing a literal `` #`` is outside the subset).
- The ``$`` rule: a scalar is an environment reference iff the *whole
  value* matches ``$[A-Z_][A-Z0-9_]*``. Fields are classified before ``$``
  handling — values under ``hooks`` and the entries of ``agent_command``
  are command values and are never env-resolved. An embedded ``$NAME``
  inside a longer string is literal text. An unset referenced variable is
  a load error naming the variable. A resolved (or plain) value beginning
  with ``~/`` is expanded to an absolute path. Neither this loader nor any
  CLI verb ever prints a resolved ``$ENV`` value.

There is deliberately no reloader here: Stage 1 processes load the file
once per run; hot reload belongs to the daemon stage that consumes it.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field as _dc_field
from pathlib import Path

__all__ = ["FIELD_CONSUMERS", "Workflow", "WorkflowError", "load_workflow"]


class WorkflowError(Exception):
    """A workflow file failed to load; the message names the line or field."""


HOOK_NAMES = ("after_create", "before_run", "after_run", "before_remove")

ISSUE_TYPES_DEFAULT = ("task", "bug", "story", "spike", "chore")

# Knob census (bidirectional): every Workflow field -> the task id that
# consumes it. A field whose consumer is an outline task id (2.x-4.x) is
# parsed and type-checked now, but its shape is provisional until that
# stage is elected; Stage 1 standardizes only the committed surface.
FIELD_CONSUMERS: dict[str, str] = {
    "project_root": "1.3",
    "project_slug": "1.4",
    "tracker": "1.6",
    "repo": "1.4",
    "managed_by": "1.6",
    "assignee": "1.3",
    "author_association": "1.4",
    "active_states": "1.5",
    "terminal_states": "1.3",
    "done_state": "2.5",
    "transition_on_success": "2.5",
    "poll_seconds": "4.4",
    "max_calls_per_poll": "1.4",
    "github_fetch_limit": "1.4",
    "max_candidates": "1.3",
    "cap_global": "1.5",
    "cap_per_state": "1.5",
    "priority_labels": "1.4",
    "issue_types": "1.3",
    "run_deadline_s": "2.3",
    "stall_s": "2.3",
    "cancel_grace_s": "4.4",
    "hook_timeout_s": "2.2",
    "backoff_base_s": "3.1",
    "backoff_cap_s": "3.1",
    "max_infra_attempts": "3.1",
    "hooks": "2.2",
    "agent_command": "2.3",
    "agent_result_file": "2.3",
    "agent_heartbeat_file": "2.3",
    "base_ref": "2.1",
    "workspace_on_terminal": "2.5",
    "workspace_max_age_h": "2.1",  # reserved field; the age sweep is a named non-goal
    "allow_repo_remote_mismatch": "1.1",
    "prompt_template": "2.4",
}


@dataclass(frozen=True)
class Workflow:
    project_root: str  # canonicalized (realpath)
    project_slug: str
    tracker: str  # "beads" | "github"
    assignee: str
    active_states: tuple[str, ...]
    terminal_states: tuple[str, ...]
    prompt_template: str = ""  # the file body, verbatim
    repo: str | None = None  # owner/repo, github only
    managed_by: str | None = None  # the one-dispatcher declaration
    author_association: str = "owner"
    done_state: str | None = None
    transition_on_success: bool = False
    poll_seconds: int = 300
    max_calls_per_poll: int = 6
    github_fetch_limit: int = 500
    max_candidates: int = 10_000
    cap_global: int | None = None
    cap_per_state: dict[str, int] = _dc_field(default_factory=dict)
    priority_labels: dict[str, int] = _dc_field(default_factory=dict)
    issue_types: tuple[str, ...] = ISSUE_TYPES_DEFAULT
    run_deadline_s: int = 3600
    stall_s: int = 300
    cancel_grace_s: int = 30
    hook_timeout_s: int = 60
    backoff_base_s: float = 10.0
    backoff_cap_s: float = 300.0
    max_infra_attempts: int = 5
    hooks: dict[str, str | None] = _dc_field(
        default_factory=lambda: {name: None for name in HOOK_NAMES}
    )
    agent_command: tuple[str, ...] = ()
    agent_result_file: str | None = None
    agent_heartbeat_file: str | None = None
    base_ref: str | None = None
    workspace_on_terminal: str = "keep"  # "keep" | "release-clean"
    workspace_max_age_h: float = 0.0  # 0 = sweep disabled
    allow_repo_remote_mismatch: bool = False


# --------------------------------------------------------------------------
# Frontmatter parsing (raw values: scalars, list[str], or section dicts)
# --------------------------------------------------------------------------

_KEY_RE = re.compile(r"[a-z][a-z0-9_]*")
_INT_RE = re.compile(r"[+-]?\d+")
_FLOAT_RE = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?")
_ENV_RE = re.compile(r"\$[A-Z_][A-Z0-9_]*")


def _parse_scalar(token: str):
    if token == "null":
        return None
    if token == "true":
        return True
    if token == "false":
        return False
    if _INT_RE.fullmatch(token):
        return int(token)
    if _FLOAT_RE.fullmatch(token) and any(c in token for c in ".eE"):
        return float(token)
    return token


def _parse_value(value_str: str, path: str, lineno: int):
    if value_str.startswith("["):
        if not value_str.endswith("]"):
            raise WorkflowError(f"{path}: line {lineno}: unclosed list (missing ']')")
        inner = value_str[1:-1].strip()
        if not inner:
            return []
        entries = [entry.strip() for entry in inner.split(",")]
        if any(not entry for entry in entries):
            raise WorkflowError(f"{path}: line {lineno}: empty entry in list")
        return entries
    return _parse_scalar(value_str)


def _parse_key_value(content: str, path: str, lineno: int):
    """Split a ``key: value`` line; returns (key, value_str | None for bare)."""
    idx = content.find(":")
    if idx < 0:
        raise WorkflowError(f"{path}: line {lineno}: expected a 'key: value' line")
    key = content[:idx]
    if not _KEY_RE.fullmatch(key):
        raise WorkflowError(
            f"{path}: line {lineno}: invalid key {key!r} (keys match [a-z][a-z0-9_]*)"
        )
    rest = content[idx + 1 :]
    if rest == "":
        return key, None
    if not rest.startswith(" "):
        raise WorkflowError(
            f"{path}: line {lineno}: expected a space after ':' for key {key!r}"
        )
    return key, rest.strip()


def _parse_frontmatter(text: str, path: str):
    """Returns (raw, body): raw maps key -> (value, lineno)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise WorkflowError(
            f"{path}: line 1: file must open with a '---' frontmatter delimiter"
        )
    close = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close = i
            break
    if close is None:
        raise WorkflowError(f"{path}: missing closing '---' frontmatter delimiter")
    body = "".join(lines[close + 1 :])

    raw: dict[str, tuple[object, int]] = {}
    section: str | None = None
    for i in range(1, close):
        lineno = i + 1
        line = lines[i].rstrip("\r\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in line:
            raise WorkflowError(
                f"{path}: line {lineno}: tab characters are outside the supported grammar"
            )
        hash_idx = line.find(" #")
        if hash_idx != -1:
            line = line[:hash_idx].rstrip()
            if not line.strip():
                continue
        indent = len(line) - len(line.lstrip(" "))
        content = line[indent:]
        if indent == 0:
            section = None
            key, value_str = _parse_key_value(content, path, lineno)
            if key in raw:
                raise WorkflowError(f"{path}: line {lineno}: duplicate key {key!r}")
            if value_str is None:
                raw[key] = ({}, lineno)
                section = key
            else:
                raw[key] = (_parse_value(value_str, path, lineno), lineno)
        elif indent == 2:
            if section is None:
                raise WorkflowError(
                    f"{path}: line {lineno}: indented entry outside any section"
                )
            key, value_str = _parse_key_value(content, path, lineno)
            entries = raw[section][0]
            assert isinstance(entries, dict)
            if key in entries:
                raise WorkflowError(
                    f"{path}: line {lineno}: duplicate key {key!r} in section {section!r}"
                )
            if value_str is None:
                entries[key] = None
            elif value_str.startswith("["):
                raise WorkflowError(
                    f"{path}: line {lineno}: lists are not supported inside sections"
                )
            else:
                entries[key] = _parse_scalar(value_str)
        else:
            raise WorkflowError(
                f"{path}: line {lineno}: indentation must be 0 or 2 spaces "
                "(deeper nesting is outside the supported grammar)"
            )
    return raw, body


# --------------------------------------------------------------------------
# Environment resolution (never applied to command values)
# --------------------------------------------------------------------------


def _resolve_env(value, field_name: str):
    """Resolve a whole-value $NAME reference. Returns (value, was_env)."""
    if isinstance(value, str) and _ENV_RE.fullmatch(value):
        name = value[1:]
        if name not in os.environ:
            raise WorkflowError(
                f"environment variable {name} is not set "
                f"(referenced by field {field_name!r})"
            )
        return os.environ[name], True
    return value, False


def _expand_home(value):
    if isinstance(value, str) and value.startswith("~/"):
        return os.path.expanduser(value)
    return value


# --------------------------------------------------------------------------
# Typed conversion
# --------------------------------------------------------------------------


def _type_error(field_name: str, expected: str, path: str, lineno: int):
    return WorkflowError(
        f"{path}: line {lineno}: field {field_name!r} expects {expected}"
    )


def _as_str(field_name: str, raw, path: str, lineno: int, *, nullable: bool):
    if isinstance(raw, dict) and not raw:
        raw = None  # a bare `key:` line with no section entries
    if raw is None:
        if nullable:
            return None
        raise _type_error(field_name, "a string", path, lineno)
    value, _ = _resolve_env(raw, field_name)
    if not isinstance(value, str):
        raise _type_error(field_name, "a string", path, lineno)
    return _expand_home(value)


def _as_int(field_name: str, raw, path: str, lineno: int, *, nullable: bool):
    if isinstance(raw, dict) and not raw:
        raw = None
    if raw is None:
        if nullable:
            return None
        raise _type_error(field_name, "an integer", path, lineno)
    value, was_env = _resolve_env(raw, field_name)
    if isinstance(value, bool):
        raise _type_error(field_name, "an integer", path, lineno)
    if isinstance(value, int):
        return value
    if was_env and isinstance(value, str) and _INT_RE.fullmatch(value.strip()):
        return int(value)
    raise _type_error(field_name, "an integer", path, lineno)


def _as_float(field_name: str, raw, path: str, lineno: int):
    value, was_env = _resolve_env(raw, field_name)
    if isinstance(value, bool):
        raise _type_error(field_name, "a number", path, lineno)
    if isinstance(value, (int, float)):
        return float(value)
    if was_env and isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    raise _type_error(field_name, "a number", path, lineno)


def _as_bool(field_name: str, raw, path: str, lineno: int):
    value, was_env = _resolve_env(raw, field_name)
    if isinstance(value, bool):
        return value
    if was_env and value in ("true", "false"):
        return value == "true"
    raise _type_error(field_name, "true or false", path, lineno)


def _as_str_list(field_name: str, raw, path: str, lineno: int, *, command: bool):
    if not isinstance(raw, list):
        raise _type_error(field_name, "a list [a, b, c]", path, lineno)
    entries = []
    for entry in raw:
        if command:
            entries.append(entry)  # command values are never env-resolved
        else:
            value, _ = _resolve_env(entry, field_name)
            entries.append(value)
    return tuple(entries)


def _as_int_dict(field_name: str, raw, path: str, lineno: int):
    result: dict[str, int] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise _type_error(field_name, "integer values", path, lineno)
            result[key] = value
        return result
    if isinstance(raw, list):
        for entry in raw:
            if entry.count("=") != 1:
                raise WorkflowError(
                    f"{path}: line {lineno}: field {field_name!r} list entries "
                    "must have the form key=value (exactly one '=')"
                )
            key, _, val = entry.partition("=")
            key, val = key.strip(), val.strip()
            if not key or not _INT_RE.fullmatch(val):
                raise _type_error(field_name, "key=integer entries", path, lineno)
            if key in result:
                raise WorkflowError(
                    f"{path}: line {lineno}: duplicate key {key!r} in field {field_name!r}"
                )
            result[key] = int(val)
        return result
    raise _type_error(field_name, "a section or a [key=value, ...] list", path, lineno)


def _as_hooks(raw, path: str, lineno: int):
    if raw is None:
        return {name: None for name in HOOK_NAMES}
    if not isinstance(raw, dict):
        raise _type_error("hooks", "a section", path, lineno)
    result = {name: None for name in HOOK_NAMES}
    for key, value in raw.items():
        if key not in HOOK_NAMES:
            raise WorkflowError(
                f"{path}: line {lineno}: unknown hook {key!r} "
                f"(expected one of: {', '.join(HOOK_NAMES)})"
            )
        if value is not None and not isinstance(value, str):
            raise _type_error("hooks", "string or null hook commands", path, lineno)
        result[key] = value  # command values: never env-resolved, never expanded
    return result


_KINDS = {
    "project_root": "str",
    "project_slug": "str",
    "tracker": "str",
    "repo": "str?",
    "managed_by": "str?",
    "assignee": "str",
    "author_association": "str",
    "active_states": "strlist",
    "terminal_states": "strlist",
    "done_state": "str?",
    "transition_on_success": "bool",
    "poll_seconds": "int",
    "max_calls_per_poll": "int",
    "github_fetch_limit": "int",
    "max_candidates": "int",
    "cap_global": "int?",
    "cap_per_state": "intdict",
    "priority_labels": "intdict",
    "issue_types": "strlist",
    "run_deadline_s": "int",
    "stall_s": "int",
    "cancel_grace_s": "int",
    "hook_timeout_s": "int",
    "backoff_base_s": "float",
    "backoff_cap_s": "float",
    "max_infra_attempts": "int",
    "hooks": "hooks",
    "agent_command": "cmdlist",
    "agent_result_file": "str?",
    "agent_heartbeat_file": "str?",
    "base_ref": "str?",
    "workspace_on_terminal": "str",
    "workspace_max_age_h": "float",
    "allow_repo_remote_mismatch": "bool",
}

_DEFAULTS = {
    "repo": None,
    "managed_by": None,
    "author_association": "owner",
    "done_state": None,
    "transition_on_success": False,
    "poll_seconds": 300,
    "max_calls_per_poll": 6,
    "github_fetch_limit": 500,
    "max_candidates": 10_000,
    "cap_global": None,
    "cap_per_state": {},
    "priority_labels": {},
    "issue_types": ISSUE_TYPES_DEFAULT,
    "run_deadline_s": 3600,
    "stall_s": 300,
    "cancel_grace_s": 30,
    "hook_timeout_s": 60,
    "backoff_base_s": 10.0,
    "backoff_cap_s": 300.0,
    "max_infra_attempts": 5,
    "hooks": None,  # -> the all-None hook map
    "agent_command": (),
    "agent_result_file": None,
    "agent_heartbeat_file": None,
    "base_ref": None,
    "workspace_on_terminal": "keep",
    "workspace_max_age_h": 0.0,
    "allow_repo_remote_mismatch": False,
}

_REQUIRED = {
    "project_root",
    "project_slug",
    "tracker",
    "assignee",
    "active_states",
    "terminal_states",
}


def _convert(field_name: str, kind: str, raw, path: str, lineno: int):
    if kind == "str":
        return _as_str(field_name, raw, path, lineno, nullable=False)
    if kind == "str?":
        return _as_str(field_name, raw, path, lineno, nullable=True)
    if kind == "int":
        return _as_int(field_name, raw, path, lineno, nullable=False)
    if kind == "int?":
        return _as_int(field_name, raw, path, lineno, nullable=True)
    if kind == "float":
        return _as_float(field_name, raw, path, lineno)
    if kind == "bool":
        return _as_bool(field_name, raw, path, lineno)
    if kind == "strlist":
        return _as_str_list(field_name, raw, path, lineno, command=False)
    if kind == "cmdlist":
        return _as_str_list(field_name, raw, path, lineno, command=True)
    if kind == "intdict":
        return _as_int_dict(field_name, raw, path, lineno)
    if kind == "hooks":
        return _as_hooks(raw, path, lineno)
    raise AssertionError(f"unknown kind {kind!r}")


# --------------------------------------------------------------------------
# Remote resolution (R-14 cross-check + base_ref default)
# --------------------------------------------------------------------------


def _normalize_remote(url: str) -> str:
    """Normalize a git remote URL to owner/repo form."""
    u = url.strip().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    if "://" in u:
        parts = u.split("://", 1)[1].split("/")[1:]  # drop the host segment
    elif ":" in u:  # scp-like: git@host:owner/repo
        parts = u.split(":", 1)[1].split("/")
    else:
        parts = u.split("/")
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return u


def _default_remote_of(project_root: str):
    """Resolve (origin_url, default_branch) via git; either may be None."""

    def _git(*args):
        try:
            proc = subprocess.run(
                ["git", "-C", project_root, *args],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout.strip() or None

    url = _git("remote", "get-url", "origin")
    branch = _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if branch and branch.startswith("origin/"):
        branch = branch[len("origin/") :]
    return url, branch


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def load_workflow(path: str, remote_of=None) -> Workflow:
    """Load and validate the workflow file at *path*.

    *remote_of* is the git-remote resolution seam: a callable taking the
    canonical project root and returning ``(origin_url, default_branch)``
    (either may be None). It is consulted only when needed — for a github
    spec's repo/remote cross-check, or to resolve a default ``base_ref``.
    The default implementation shells out to ``git``.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowError(f"cannot read workflow file {path}: {exc}") from exc

    raw, body = _parse_frontmatter(text, path)

    known_keys = set(_KINDS)
    for key, (_, lineno) in raw.items():
        if key not in known_keys:
            print(
                f"warning: {path}: line {lineno}: unknown workflow key {key!r} "
                "has no consumer and is ignored",
                file=sys.stderr,
            )

    values: dict[str, object] = {}
    for name, kind in _KINDS.items():
        if name not in raw:
            if name in _REQUIRED:
                raise WorkflowError(f"{path}: missing required field {name!r}")
            default = _DEFAULTS[name]
            if name == "hooks":
                values[name] = _as_hooks(default, path, 0)
            else:
                values[name] = dict(default) if isinstance(default, dict) else default
            continue
        raw_value, lineno = raw[name]
        values[name] = _convert(name, kind, raw_value, path, lineno)

    values["prompt_template"] = body
    values["project_root"] = os.path.realpath(values["project_root"])

    if values["tracker"] not in ("beads", "github"):
        raise WorkflowError(
            f"field 'tracker' must be \"beads\" or \"github\", got {values['tracker']!r}"
        )
    if values["workspace_on_terminal"] not in ("keep", "release-clean"):
        raise WorkflowError(
            "field 'workspace_on_terminal' must be \"keep\" or \"release-clean\", "
            f"got {values['workspace_on_terminal']!r}"
        )
    if values["transition_on_success"] and values["done_state"] is None:
        raise WorkflowError(
            "field 'transition_on_success' is true but 'done_state' is not set"
        )

    remote_url = default_branch = None
    if values["tracker"] == "github" or values["base_ref"] is None:
        resolver = remote_of if remote_of is not None else _default_remote_of
        remote_url, default_branch = resolver(values["project_root"])

    if values["tracker"] == "github":
        repo = values["repo"]
        if repo is None:
            raise WorkflowError("field 'repo' is required for tracker \"github\"")
        if not re.fullmatch(r"[^/\s]+/[^/\s]+", repo):
            raise WorkflowError(f"field 'repo' must be in owner/repo form, got {repo!r}")
        if remote_url is None:
            raise WorkflowError(
                f"could not resolve the origin remote of the project at "
                f"{values['project_root']} to cross-check repo {repo!r}"
            )
        remote_repo = _normalize_remote(remote_url)
        if remote_repo.lower() != repo.lower() and not values["allow_repo_remote_mismatch"]:
            raise WorkflowError(
                f"repo {repo!r} does not match the project origin remote "
                f"{remote_repo!r} (set allow_repo_remote_mismatch: true to load anyway)"
            )

    if values["base_ref"] is None:
        if default_branch:
            values["base_ref"] = default_branch
        else:
            raise WorkflowError(
                "could not resolve a default branch for repo "
                f"{values['repo'] or values['project_slug']!r}; set base_ref in the spec"
            )

    return Workflow(**values)
