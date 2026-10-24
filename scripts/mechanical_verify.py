#!/usr/bin/env python3
"""Allowlist mechanical verifier.

Discovers verification commands from a fixed allowlist of project markers,
then runs them bounded (per-command timeout, tail-capped output) and
budgeted (overall wall-clock budget, memory preflight), stopping at the
first failure. Stdlib only.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_CAP_BYTES = 65536
SCAN_CHARS = 65536
MIN_MEMORY_KB = 524288  # 512 MiB
TERM_GRACE_SECONDS = 0.75

MARKDOWNLINT_ARGV = (
    "markdownlint-cli2",
    "**/*.md",
    "!reference/esf/**/*.md",
    "!skills/archify/**/*.md",
)


@dataclass(frozen=True)
class VerificationCommand:
    id: str
    label: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class VerificationResult:
    command: VerificationCommand
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    stdout: str
    stderr: str
    output_truncated: bool

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def discover_verification_commands(root: Path) -> tuple[VerificationCommand, ...]:
    commands: list[VerificationCommand] = []
    seen: set[str] = set()

    def add(command: VerificationCommand) -> None:
        if command.id not in seen:
            seen.add(command.id)
            commands.append(command)

    # 1. Go (AEP addition).
    if (root / "go.mod").is_file():
        add(VerificationCommand("go-test", "Go tests", ("go", "test", "./...")))

    # 2. Rust.
    if (root / "Cargo.toml").is_file():
        add(VerificationCommand("cargo-test", "Rust tests", ("cargo", "test")))

    # 3. Node — only with a real scripts.test string.
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            scripts = data.get("scripts")
            if isinstance(scripts, dict):
                test_script = scripts.get("test")
                if (
                    isinstance(test_script, str)
                    and test_script.strip()
                    and "no test specified" not in test_script.lower()
                ):
                    add(
                        VerificationCommand(
                            "npm-test", "Node tests", ("npm", "test")
                        )
                    )

    # 4. Python markers.
    if (
        (root / "pytest.ini").is_file()
        or (root / "pyproject.toml").is_file()
        or (root / "setup.cfg").is_file()
        or (root / "tests").exists()
    ):
        add(
            VerificationCommand(
                "pytest", "Python tests", ("python3", "-m", "pytest", "-q")
            )
        )

    # 5. Root-level python test files, partitioned by style: modules
    # importing unittest run under the unittest runner (named
    # explicitly — discover's default pattern (test*.py) would
    # silently skip the *_test.py files discovery accepts), and the
    # remaining modules fall to the pytest command, which collects
    # plain test functions the unittest runner never would. A mixed
    # suite therefore runs BOTH runners; a single-style suite runs
    # exactly the one command it ran before.
    test_files: list[Path] = []
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if not entry.is_file() or not entry.name.endswith(".py"):
                continue
            if entry.name.startswith("test_") or entry.name.endswith("_test.py"):
                test_files.append(entry)
    if test_files:
        unittest_modules: list[str] = []
        pytest_modules: list[str] = []
        for path in test_files:
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read(SCAN_CHARS)
            except OSError:
                text = ""
            if "import unittest" in text or "from unittest" in text:
                unittest_modules.append(path.stem)
            else:
                pytest_modules.append(path.stem)
        if unittest_modules:
            add(
                VerificationCommand(
                    "unittest",
                    "Python unittest",
                    ("python3", "-m", "unittest", "-v", *unittest_modules),
                )
            )
        if pytest_modules:
            add(
                VerificationCommand(
                    "pytest", "Python tests", ("python3", "-m", "pytest", "-q")
                )
            )

    # 6. Make (AEP addition).
    makefile = root / "Makefile"
    if makefile.is_file():
        try:
            text = makefile.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        if re.search(r"^test:", text, re.MULTILINE):
            add(VerificationCommand("make-test", "Make tests", ("make", "test")))

    # 7. Markdown lint (AEP addition) — binary called directly, never npx.
    if (root / ".markdownlint.yaml").is_file() and (
        shutil.which("markdownlint-cli2") is not None
    ):
        add(
            VerificationCommand(
                "markdownlint", "Markdown lint", MARKDOWNLINT_ARGV
            )
        )

    # 8. Scripts test suite (AEP addition) — suites living in
    # scripts/tests, run exactly as CI's script-tests job's
    # unittest-discover step runs them. Require at least one real
    # (non-symlink) file matching unittest discover's default pattern
    # (test*.py) in a real (non-symlink) directory: an empty or
    # test-less directory must not manufacture a vacuous command, and
    # a symlinked suite must not attest a foreign tree's tests.
    scripts_tests = root / "scripts" / "tests"
    if (
        scripts_tests.is_dir()
        and not scripts_tests.is_symlink()
        and any(
            entry.is_file() and not entry.is_symlink()
            for entry in scripts_tests.glob("test*.py")
        )
    ):
        add(
            VerificationCommand(
                "scripts-unittest",
                "Scripts unittest",
                (
                    "python3",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "scripts/tests",
                    "-v",
                ),
            )
        )

    return tuple(commands)


class _TailBuffer:
    """Byte sink retaining only the last OUTPUT_CAP_BYTES bytes."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.total = 0

    def append(self, chunk: bytes) -> None:
        self.total += len(chunk)
        self._buf.extend(chunk)
        overflow = len(self._buf) - OUTPUT_CAP_BYTES
        if overflow > 0:
            del self._buf[:overflow]

    @property
    def truncated(self) -> bool:
        return self.total > OUTPUT_CAP_BYTES

    def text(self) -> str:
        return bytes(self._buf).decode("utf-8", errors="replace")


def _drain(stream, buffer: _TailBuffer) -> None:
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            buffer.append(chunk)
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass


def run_verification(
    root: Path,
    command: VerificationCommand,
    timeout_seconds: float = 300,
) -> VerificationResult:
    env = dict(os.environ)
    env["CI"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            list(command.argv),
            cwd=str(root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        return VerificationResult(
            command=command,
            exit_code=None,
            timed_out=False,
            duration_ms=int((time.monotonic() - started) * 1000),
            stdout="",
            stderr=str(exc),
            output_truncated=False,
        )

    stdout_buf = _TailBuffer()
    stderr_buf = _TailBuffer()
    threads = [
        threading.Thread(target=_drain, args=(proc.stdout, stdout_buf), daemon=True),
        threading.Thread(target=_drain, args=(proc.stderr, stderr_buf), daemon=True),
    ]
    for thread in threads:
        thread.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            pass
        try:
            proc.wait(timeout=TERM_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        # Escalate even when the leader already exited: a descendant
        # that ignored SIGTERM can outlive it while still holding the
        # process group (and the worktree). SIGKILL whatever remains.
        try:
            os.killpg(proc.pid, 0)
        except OSError:
            pass
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
        if proc.returncode is None:
            proc.wait()
    for thread in threads:
        thread.join(timeout=5)

    return VerificationResult(
        command=command,
        exit_code=proc.returncode,
        timed_out=timed_out,
        duration_ms=int((time.monotonic() - started) * 1000),
        stdout=stdout_buf.text(),
        stderr=stderr_buf.text(),
        output_truncated=stdout_buf.truncated or stderr_buf.truncated,
    )


def available_memory_kb() -> int | None:
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^MemAvailable:\s+(\d+)\s*kB", text, re.MULTILINE)
    if match is None:
        return None
    return int(match.group(1))


def run_all(
    root,
    commands,
    *,
    timeout_seconds=300,
    budget_seconds=600,
    mem_available_kb=available_memory_kb,
    on_result=None,
) -> int:
    mem_kb = mem_available_kb() if mem_available_kb is not None else None
    if mem_kb is not None and mem_kb < MIN_MEMORY_KB:
        print(
            "VERIFY: insufficient memory available "
            f"({mem_kb // 1024} MiB < 512 MiB); refusing to run"
        )
        return 3

    if not commands:
        return 2

    started = time.monotonic()
    executed = 0
    for idx, command in enumerate(commands):
        elapsed = time.monotonic() - started
        if elapsed >= budget_seconds:
            remaining = len(commands) - idx
            print(
                f"VERIFY: budget exhausted ({budget_seconds}s); "
                f"{remaining} command(s) not run"
            )
            return 1
        effective_timeout = min(timeout_seconds, budget_seconds - elapsed)
        result = run_verification(root, command, timeout_seconds=effective_timeout)
        executed += 1
        if on_result is not None:
            on_result(result)
        if result.passed:
            print(f"VERIFY: {command.id} PASS")
        else:
            exit_repr = (
                "spawn-error" if result.exit_code is None else str(result.exit_code)
            )
            print(
                f"VERIFY: {command.id} FAIL exit={exit_repr} "
                f"duration_ms={result.duration_ms}"
            )
            print(f"VERIFY: stopped at first failure ({command.id})")
            return 1
    return 0 if executed else 1


GENESIS_CHAIN = "0" * 64

RECEIPT_FIELDS = (
    "ts",
    "task",
    "command_id",
    "argv",
    "exit_code",
    "timed_out",
    "duration_ms",
    "stdout_sha256",
    "stderr_sha256",
    "chain_sha256",
)

COMPLETION_KIND = "run-complete"

COMPLETION_FIELDS = (
    "ts",
    "task",
    "kind",
    "run_id",
    "command_count",
    "commands_sha256",
    "chain_sha256",
)

RUN_START_KIND = "run-start"

RUN_START_FIELDS = (
    "ts",
    "task",
    "kind",
    "run_id",
    "chain_sha256",
)


def _commands_digest(command_ids) -> str:
    canonical = json.dumps(list(command_ids), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Tree binding (overseer remediation R1): a receipts segment records the
# tree it describes, so a sealed PASS can be re-validated against that
# tree later — never against whatever the working tree holds then.

FS_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "target",
        "node_modules",
        "coverage",
        "htmlcov",
        "dist",
        "build",
        ".tox",
        ".venv",
    }
)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        timeout=60,
    )


def _git_head(root: Path) -> str | None:
    proc = _git(root, "rev-parse", "HEAD")
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace").strip() or None


def _git_tree_digest(root: Path, head: str) -> str | None:
    """Digest of the tree at `head`, computed from git objects only.

    For each entry of `git ls-tree -r -z <head>` (NUL-terminated, raw
    path bytes), hash `mode + " " + blob_sha + " " + path + "\n"` in
    ls-tree's own order. Working-tree content is never read, so the
    digest is reproducible at any later time while the commit exists;
    None when the commit is unreadable.
    """
    proc = _git(root, "ls-tree", "-r", "-z", head)
    if proc.returncode != 0:
        return None
    digest = hashlib.sha256()
    for entry in proc.stdout.split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.partition(b"\t")
        parts = meta.split(b" ")
        if len(parts) != 3:
            return None
        digest.update(parts[0] + b" " + parts[2] + b" " + path + b"\n")
    return digest.hexdigest()


def _fs_tree_digest(root: Path, receipts_path: Path | None = None) -> str:
    """Digest of a non-git tree: sha256 over sorted relative paths of
    `relpath + "\\0" + content + "\\0"`, where content is the file's
    sha256 hex (symlinks: the target string, never followed). Paths
    with a component in FS_EXCLUDED_DIRS and the receipts file itself
    are excluded.
    """
    resolved = root.resolve()
    receipts_resolved = (
        receipts_path.resolve() if receipts_path is not None else None
    )
    entries: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(resolved, followlinks=False):
        current = Path(dirpath)
        descend: list[str] = []
        for name in dirnames:
            if name in FS_EXCLUDED_DIRS:
                continue
            path = current / name
            if path.is_symlink():
                entries.append(
                    (path.relative_to(resolved).as_posix(), os.readlink(path))
                )
            else:
                descend.append(name)
        dirnames[:] = descend
        for name in filenames:
            path = current / name
            if (
                receipts_resolved is not None
                and path.resolve() == receipts_resolved
            ):
                continue
            rel = path.relative_to(resolved).as_posix()
            if path.is_symlink():
                entries.append((rel, os.readlink(path)))
            else:
                entries.append(
                    (
                        rel,
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                )
    entries.sort()
    digest = hashlib.sha256()
    for rel, content in entries:
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def tree_binding(
    root: Path, receipts_path: Path | None = None
) -> dict:
    """The binding a run records for the tree it verifies.

    git mode (root inside a git worktree): head + the ls-tree digest
    at that head. fs mode: head None + the live-tree digest. Root is
    canonicalized with Path.resolve(). Raises ValueError when a git
    root has no readable HEAD/tree to bind to.
    """
    resolved = root.resolve()
    if _git(resolved, "rev-parse", "--git-dir").returncode == 0:
        head = _git_head(resolved)
        digest = (
            _git_tree_digest(resolved, head) if head is not None else None
        )
        if head is None or digest is None:
            raise ValueError(
                f"git root {resolved} has no readable HEAD to bind to"
            )
        return {
            "root": str(resolved),
            "head": head,
            "tree_digest": digest,
            "mode": "git",
        }
    return {
        "root": str(resolved),
        "head": None,
        "tree_digest": _fs_tree_digest(resolved, receipts_path),
        "mode": "fs",
    }


def tree_clean(root: Path, receipts_path: Path | None = None) -> bool:
    """Git-mode cleanliness predicate for the binding gate.

    `git status --porcelain` must be empty after dropping (i) the
    receipts file itself and anything under `.superpowers/` (the
    workflow's own bookkeeping) and (ii) untracked entries whose path
    has a component in FS_EXCLUDED_DIRS (tool caches the run itself
    creates). Modified or staged tracked entries always count as
    dirty; the exclusions never hide a tracked change.
    """
    resolved = root.resolve()
    top = _git(resolved, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return False
    toplevel = Path(
        top.stdout.decode("utf-8", errors="replace").strip()
    ).resolve()
    receipts_rel: str | None = None
    if receipts_path is not None:
        try:
            receipts_rel = (
                receipts_path.resolve().relative_to(toplevel).as_posix()
            )
        except ValueError:
            receipts_rel = None
    proc = _git(resolved, "status", "--porcelain", "-z")
    if proc.returncode != 0:
        return False
    fields = proc.stdout.split(b"\0")
    idx = 0
    while idx < len(fields):
        entry = fields[idx]
        idx += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:].decode("utf-8", errors="surrogateescape")
        if status[:1] in (b"R", b"C"):
            idx += 1  # rename/copy: the source path field follows
        if receipts_rel is not None and path == receipts_rel:
            continue
        if path == ".superpowers" or path.startswith(".superpowers/"):
            continue
        if status == b"??" and any(
            part in FS_EXCLUDED_DIRS for part in path.split("/")
        ):
            continue
        return False
    return True


def _chain_sha256(body: dict, prev_chain: str) -> str:
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((prev_chain + canonical).encode("utf-8")).hexdigest()


def _receipt_lines(receipts_path: Path) -> list[str]:
    try:
        text = receipts_path.read_text(encoding="utf-8")
    except OSError:
        return []
    return text.splitlines()


def _last_chain(receipts_path: Path) -> str:
    """Chain hash of the file's last line; genesis for an empty file.

    Raises ValueError when the last line is malformed (not a JSON object
    carrying a string chain_sha256) — a torn receipts file is never
    appended to blindly.
    """
    lines = _receipt_lines(receipts_path)
    if not lines:
        return GENESIS_CHAIN
    try:
        parsed = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"malformed last receipt line {len(lines)} in {receipts_path}"
        ) from exc
    if not isinstance(parsed, dict) or not isinstance(
        parsed.get("chain_sha256"), str
    ):
        raise ValueError(
            f"malformed last receipt line {len(lines)} in {receipts_path}"
        )
    return parsed["chain_sha256"]


def _append_record(receipts_path: Path, body: dict) -> None:
    """Append one hash-chained record under an exclusive flock.

    The append lands as a single os.write, so concurrent runs cannot
    interleave a line.
    """
    fd = os.open(receipts_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        record = dict(body)
        record["chain_sha256"] = _chain_sha256(body, _last_chain(receipts_path))
        line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def append_receipt(
    receipts_path: Path,
    task: str,
    result: VerificationResult,
    run_id: str | None = None,
) -> None:
    """Append one hash-chained receipt for a result the verifier produced.

    Only hashes of the capped output are recorded — never output text.
    When run_id is given, the receipt carries it so check_receipts can
    attribute the receipt to its run segment.
    """
    body = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "command_id": result.command.id,
        "argv": list(result.command.argv),
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "duration_ms": result.duration_ms,
        "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
    }
    if run_id is not None:
        body["run_id"] = run_id
    _append_record(receipts_path, body)


def append_run_start(
    receipts_path: Path,
    task: str,
    run_id: str,
    binding: dict | None = None,
) -> None:
    """Append the run-boundary record that opens a run segment.

    Written before a verify run executes any command; the run's
    receipts and its completion record carry the same run_id, so
    check_receipts can validate the latest run independently of any
    earlier (possibly interrupted) segments in the same file. When a
    tree binding is given it is recorded here (and on the completion
    record) as an EXTRA field — the required-field tuples deliberately
    do not include it, so its absence routes to the UNBOUND verdict
    rather than a corruption verdict (RC3).
    """
    body = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "kind": RUN_START_KIND,
        "run_id": run_id,
    }
    if binding is not None:
        body["binding"] = binding
    _append_record(receipts_path, body)


def append_completion(
    receipts_path: Path,
    task: str,
    commands,
    run_id: str | None = None,
    binding: dict | None = None,
) -> None:
    """Append the run-completion record for a fully successful run.

    Written only when every discovered command executed and passed; it
    carries the expected command count and a digest of the ordered
    command set, so check_receipts can reject the partial receipt set
    of a run that stopped early. `binding`, when given, is the tree
    binding computed at run start (see append_run_start).
    """
    body = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "kind": COMPLETION_KIND,
        "command_count": len(commands),
        "commands_sha256": _commands_digest([c.id for c in commands]),
    }
    if run_id is not None:
        body["run_id"] = run_id
    if binding is not None:
        body["binding"] = binding
    _append_record(receipts_path, body)


def check_receipts(
    receipts_path: Path,
    task: str,
    root: Path,
    historical: bool = False,
) -> int:
    lines = _receipt_lines(receipts_path)
    records: list[dict] = []
    for number, line in enumerate(lines, start=1):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            print(f"RECEIPTS: corrupt at line {number}")
            return 1
        if not isinstance(parsed, dict):
            print(f"RECEIPTS: corrupt at line {number}")
            return 1
        if parsed.get("kind") == COMPLETION_KIND:
            required = COMPLETION_FIELDS
        elif parsed.get("kind") == RUN_START_KIND:
            required = RUN_START_FIELDS
        else:
            required = RECEIPT_FIELDS
        if any(field not in parsed for field in required):
            print(f"RECEIPTS: corrupt at line {number}")
            return 1
        records.append(parsed)

    prev_chain = GENESIS_CHAIN
    for number, receipt in enumerate(records, start=1):
        body = {k: v for k, v in receipt.items() if k != "chain_sha256"}
        if _chain_sha256(body, prev_chain) != receipt["chain_sha256"]:
            print(f"RECEIPTS: chain broken at line {number}")
            return 1
        prev_chain = receipt["chain_sha256"]

    task_records = [r for r in records if r["task"] == task]
    if not task_records:
        print(f"RECEIPTS: FAIL task {task}: no receipts")
        return 1

    # Segment selection. A verify run opens with a run-start record
    # and its receipts and completion carry that run_id; only the
    # task's LATEST segment is evidence — an interrupted earlier run
    # must not poison a successful retry, and earlier segments remain
    # audit history under the whole-file chain validation above. A
    # file with no run-start record for the task predates segments and
    # keeps the original whole-history semantics.
    start_idx = None
    for idx, record in enumerate(task_records):
        if record.get("kind") == RUN_START_KIND:
            start_idx = idx
    if start_idx is None:
        segment = list(task_records)
        segment_run_id = None
        start_record = None
    else:
        start_record = task_records[start_idx]
        segment_run_id = start_record["run_id"]
        segment = [
            r
            for r in task_records[start_idx + 1 :]
            if r.get("run_id") == segment_run_id
        ]

    mine = [r for r in segment if r.get("kind") != COMPLETION_KIND]
    if not mine and segment_run_id is None:
        print(f"RECEIPTS: FAIL task {task}: no receipts")
        return 1
    for receipt in mine:
        if receipt["exit_code"] != 0 or receipt["timed_out"]:
            print(
                f"RECEIPTS: FAIL task {task}: "
                f"receipt failed: {receipt['command_id']}"
            )
            return 1

    # The task's latest run must be proven complete: the task's records
    # must end with a run-completion record for that run whose count
    # and command-set digest match the run's command receipts. Without
    # one, the receipts may be all that a stopped-early run managed to
    # write.
    if task_records[-1].get("kind") != COMPLETION_KIND or (
        segment_run_id is not None
        and task_records[-1].get("run_id") != segment_run_id
    ):
        print(
            f"RECEIPTS: FAIL task {task}: "
            "incomplete run: no completion record"
        )
        return 1
    completion = task_records[-1]
    if segment_run_id is None:
        run_receipts: list[dict] = []
        for record in reversed(task_records[:-1]):
            if record.get("kind") == COMPLETION_KIND:
                break
            run_receipts.append(record)
        run_receipts.reverse()
    else:
        run_receipts = mine
    if len(run_receipts) != completion["command_count"] or _commands_digest(
        [r["command_id"] for r in run_receipts]
    ) != completion["commands_sha256"]:
        print(
            f"RECEIPTS: FAIL task {task}: "
            "completion record does not match run receipts"
        )
        return 1

    # Tree binding (R1): the segment must describe a tree. `binding`
    # is read directly — it is deliberately absent from the required
    # field tuples, so a pre-binding (legacy) segment reaches this
    # branch and is refused as UNBOUND, never misread as corrupt and
    # never silently validated (RC3).
    binding = completion.get("binding")
    start_binding = (
        start_record.get("binding") if start_record is not None else None
    )
    if binding is not None and start_binding is not None:
        if binding != start_binding:
            print(
                f"RECEIPTS: STALE task {task}: "
                "run-start and completion bindings disagree"
            )
            return 1
    if binding is None:
        binding = start_binding
    if (
        not isinstance(binding, dict)
        or binding.get("mode") not in ("git", "fs")
        or not isinstance(binding.get("tree_digest"), str)
        or not isinstance(binding.get("root"), str)
    ):
        print(
            f"RECEIPTS: UNBOUND task {task}: "
            "segment carries no tree binding"
        )
        return 2
    resolved_root = root.resolve()
    if binding["root"] != str(resolved_root):
        print(
            f"RECEIPTS: FAIL task {task}: segment is bound to root "
            f"{binding['root']}, not {resolved_root}"
        )
        return 1
    if binding["mode"] == "git":
        recorded_head = binding.get("head")
        digest = (
            _git_tree_digest(resolved_root, recorded_head)
            if isinstance(recorded_head, str)
            else None
        )
        if digest is None:
            print(
                f"RECEIPTS: UNVERIFIABLE task {task}: recorded commit "
                f"{recorded_head} is not readable"
            )
            return 2
        if digest != binding["tree_digest"]:
            print(
                f"RECEIPTS: STALE task {task}: tree digest does not "
                "match the recorded head"
            )
            return 1
        if not historical:
            current_head = _git_head(resolved_root)
            if current_head != recorded_head:
                print(
                    f"RECEIPTS: HEAD-MOVED task {task}: HEAD is "
                    f"{current_head}, segment bound to {recorded_head}"
                )
                return 1
            if not tree_clean(resolved_root, receipts_path):
                print(
                    f"RECEIPTS: DIRTY task {task}: "
                    "working tree is not clean"
                )
                return 1
    else:
        try:
            live_digest = _fs_tree_digest(resolved_root, receipts_path)
        except OSError:
            print(
                f"RECEIPTS: UNVERIFIABLE task {task}: "
                "live tree cannot be read"
            )
            return 2
        if live_digest != binding["tree_digest"]:
            print(
                f"RECEIPTS: STALE task {task}: live tree digest does "
                "not match the segment"
            )
            return 1
    print(f"RECEIPTS: PASS task {task}: {len(mine)} receipts, chain valid")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mechanical_verify.py")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--root", required=True)
    verify.add_argument("--task", required=True)
    verify.add_argument("--timeout", type=int, default=300)
    verify.add_argument("--budget", type=int, default=600)
    verify.add_argument("--receipts", default=None)
    check_cmd = subparsers.add_parser("check-receipts")
    check_cmd.add_argument("--receipts", required=True)
    check_cmd.add_argument("--task", required=True)
    check_cmd.add_argument("--root", required=True)
    check_cmd.add_argument("--historical", action="store_true")
    args = parser.parse_args(argv)

    if args.subcommand == "check-receipts":
        return check_receipts(
            Path(args.receipts),
            args.task,
            Path(args.root),
            historical=args.historical,
        )

    receipts_path = Path(args.receipts) if args.receipts is not None else None
    if receipts_path is not None:
        # Fail closed before running anything: never append to a receipts
        # file whose last line is malformed.
        lines = _receipt_lines(receipts_path)
        if lines:
            try:
                _last_chain(receipts_path)
            except ValueError:
                print(
                    f"RECEIPTS: corrupt at line {len(lines)} "
                    f"in {args.receipts}"
                )
                return 1

    root = Path(args.root)
    commands = discover_verification_commands(root)
    markdownlint_skipped = (root / ".markdownlint.yaml").is_file() and all(
        c.id != "markdownlint" for c in commands
    )
    if not commands:
        print(
            f"VERIFY: no verification commands discovered at {root} "
            "— no mechanical evidence available"
        )
        if markdownlint_skipped:
            print(
                "VERIFY: markdownlint SKIPPED tool missing "
                "(markdownlint-cli2 not on PATH)"
            )
        return 2
    if markdownlint_skipped:
        print(
            "VERIFY: markdownlint SKIPPED tool missing "
            "(markdownlint-cli2 not on PATH)"
        )
    run_id: str | None = None
    binding: dict | None = None
    on_result = None
    if receipts_path is not None:
        task = args.task
        run_id = uuid.uuid4().hex
        # Tree binding (R1): an evidence run binds to the tree before
        # its first command. Git mode refuses a dirty tree outright —
        # a segment sealed over uncommitted state could never be
        # re-validated against its recorded HEAD.
        try:
            binding = tree_binding(root, receipts_path)
        except (OSError, ValueError) as exc:
            print(
                f"VERIFY: cannot bind receipts to the tree "
                f"at {root}: {exc}"
            )
            return 1
        append_run_start(receipts_path, task, run_id, binding=binding)
        if binding["mode"] == "git" and not tree_clean(root, receipts_path):
            print(
                "VERIFY: FAIL tree not clean at HEAD "
                "— commit or stash before verifying"
            )
            return 1

        def on_result(result: VerificationResult) -> None:
            append_receipt(receipts_path, task, result, run_id=run_id)

    rc = run_all(
        root,
        commands,
        timeout_seconds=args.timeout,
        budget_seconds=args.budget,
        mem_available_kb=available_memory_kb,
        on_result=on_result,
    )
    if rc == 0 and receipts_path is not None:
        # run_all returns 0 only when every command executed and
        # passed; seal the run so check_receipts can reject a partial
        # receipt set — but only if the tree is still the tree the run
        # bound to. Dirtied during the run (git) or changed (fs): no
        # completion record; the incomplete segment is the verdict.
        if binding is not None and binding["mode"] == "git":
            seal = tree_clean(root, receipts_path)
        elif binding is not None:
            try:
                seal = (
                    tree_binding(root, receipts_path)["tree_digest"]
                    == binding["tree_digest"]
                )
            except (OSError, ValueError):
                seal = False
        else:
            seal = True
        if not seal:
            print(
                "VERIFY: FAIL tree changed during the run "
                "— no completion record written"
            )
            return 1
        append_completion(
            receipts_path, task, commands, run_id=run_id, binding=binding
        )
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
