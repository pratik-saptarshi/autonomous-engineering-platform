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

    # 5. Root-level python test files: unittest if any imports it, else the
    # pytest command as fallback (deduplicated against rule 4).
    test_files: list[Path] = []
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if not entry.is_file() or not entry.name.endswith(".py"):
                continue
            if entry.name.startswith("test_") or entry.name.endswith("_test.py"):
                test_files.append(entry)
    if test_files:
        imports_unittest = False
        for path in test_files:
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read(SCAN_CHARS)
            except OSError:
                continue
            if "import unittest" in text or "from unittest" in text:
                imports_unittest = True
                break
        if imports_unittest:
            add(
                VerificationCommand(
                    "unittest",
                    "Python unittest",
                    ("python3", "-m", "unittest", "discover", "-v"),
                )
            )
        else:
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
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
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


def append_receipt(
    receipts_path: Path, task: str, result: VerificationResult
) -> None:
    """Append one hash-chained receipt for a result the verifier produced.

    Only hashes of the capped output are recorded — never output text.
    The append holds an exclusive flock and lands as a single os.write.
    """
    fd = os.open(receipts_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        prev_chain = _last_chain(receipts_path)
        body = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "task": task,
            "command_id": result.command.id,
            "argv": list(result.command.argv),
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "duration_ms": result.duration_ms,
            "stdout_sha256": hashlib.sha256(
                result.stdout.encode("utf-8")
            ).hexdigest(),
            "stderr_sha256": hashlib.sha256(
                result.stderr.encode("utf-8")
            ).hexdigest(),
        }
        receipt = dict(body)
        receipt["chain_sha256"] = _chain_sha256(body, prev_chain)
        line = json.dumps(receipt, sort_keys=True, ensure_ascii=False) + "\n"
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def check_receipts(receipts_path: Path, task: str) -> int:
    lines = _receipt_lines(receipts_path)
    receipts: list[dict] = []
    for number, line in enumerate(lines, start=1):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            print(f"RECEIPTS: corrupt at line {number}")
            return 1
        if not isinstance(parsed, dict) or any(
            field not in parsed for field in RECEIPT_FIELDS
        ):
            print(f"RECEIPTS: corrupt at line {number}")
            return 1
        receipts.append(parsed)

    prev_chain = GENESIS_CHAIN
    for number, receipt in enumerate(receipts, start=1):
        body = {k: v for k, v in receipt.items() if k != "chain_sha256"}
        if _chain_sha256(body, prev_chain) != receipt["chain_sha256"]:
            print(f"RECEIPTS: chain broken at line {number}")
            return 1
        prev_chain = receipt["chain_sha256"]

    mine = [r for r in receipts if r["task"] == task]
    if not mine:
        print(f"RECEIPTS: FAIL task {task}: no receipts")
        return 1
    for receipt in mine:
        if receipt["exit_code"] != 0 or receipt["timed_out"]:
            print(
                f"RECEIPTS: FAIL task {task}: "
                f"receipt failed: {receipt['command_id']}"
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
    args = parser.parse_args(argv)

    if args.subcommand == "check-receipts":
        return check_receipts(Path(args.receipts), args.task)

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
    on_result = None
    if receipts_path is not None:
        task = args.task

        def on_result(result: VerificationResult) -> None:
            append_receipt(receipts_path, task, result)

    return run_all(
        root,
        commands,
        timeout_seconds=args.timeout,
        budget_seconds=args.budget,
        mem_available_kb=available_memory_kb,
        on_result=on_result,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
