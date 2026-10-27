import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mechanical_verify
from mechanical_verify import (
    VerificationCommand,
    VerificationResult,
    append_receipt,
    check_receipts,
    run_verification,
)

SCRIPT = Path(__file__).resolve().parent.parent / "mechanical_verify.py"
GENESIS = "0" * 64


def write(root: Path, name: str, content: str = "") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def verify(root: Path, task: str, receipts: Path) -> subprocess.CompletedProcess:
    return run_cli(
        "verify",
        "--root",
        str(root),
        "--task",
        task,
        "--receipts",
        str(receipts),
    )


def check(
    receipts: Path, task: str, historical: bool = False
) -> subprocess.CompletedProcess:
    # Every fixture keeps its receipts file directly in the tree root.
    return check_bound(receipts, task, receipts.parent, historical)


def check_bound(
    receipts: Path,
    task: str,
    root: Path,
    historical: bool = False,
) -> subprocess.CompletedProcess:
    args = [
        "check-receipts",
        "--receipts",
        str(receipts),
        "--task",
        task,
        "--root",
        str(root),
    ]
    if historical:
        args.append("--historical")
    return run_cli(*args)


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )


def init_git_repo(
    root: Path, makefile: str = "test:\n\ttrue\n", message: str = "fixture"
) -> None:
    git(root, "init", "-q", "-b", "main")
    write(root, "Makefile", makefile)
    git(root, "add", "Makefile")
    git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    )


def commit_file(root: Path, name: str, content: str, message: str) -> None:
    write(root, name, content)
    git(root, "add", name)
    git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    )


def read_receipts(receipts: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in receipts.read_text(encoding="utf-8").splitlines()
    ]


def recompute_chain(receipt: dict, prev_chain: str) -> str:
    body = {k: v for k, v in receipt.items() if k != "chain_sha256"}
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((prev_chain + canonical).encode("utf-8")).hexdigest()


def rewrite_rechained(receipts: Path, records: list[dict]) -> None:
    """Write records back with a freshly computed hash chain, so a
    test can tamper with exactly one field and have the tamper be the
    ONLY thing validation can object to."""
    prev = GENESIS
    lines = []
    for record in records:
        record = dict(record)
        record["chain_sha256"] = recompute_chain(record, prev)
        prev = record["chain_sha256"]
        lines.append(json.dumps(record, sort_keys=True, ensure_ascii=False))
    receipts.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _path_pytest_available() -> bool:
    """The verifier's pytest command is literal `python3 -m pytest`:
    what matters is the python3 on PATH, not this test process."""
    try:
        proc = subprocess.run(
            ["python3", "-m", "pytest", "--version"],
            capture_output=True,
            timeout=30,
        )
    except OSError:
        return False
    return proc.returncode == 0


def two_command_fixture(root: Path) -> None:
    write(root, "package.json", json.dumps({"scripts": {"test": "true"}}))
    write(root, "Makefile", "test:\n\ttrue\n")


class ReceiptTests(unittest.TestCase):
    def test_verify_writes_receipt_with_hashes_not_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", 'test:\n\tprintf "MARKER-OUTPUT\\n"\n')
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            lines = receipts.read_text(encoding="utf-8").splitlines()
            # Run-start record, one command receipt, run-completion record.
            self.assertEqual(len(lines), 3)
            self.assertNotIn("MARKER-OUTPUT", lines[1])
            receipt = json.loads(lines[1])
            self.assertEqual(receipt["command_id"], "make-test")
            command = next(
                c
                for c in mechanical_verify.discover_verification_commands(root)
                if c.id == "make-test"
            )
            direct = run_verification(root, command)
            expected = hashlib.sha256(
                direct.stdout.encode("utf-8")
            ).hexdigest()
            self.assertEqual(receipt["stdout_sha256"], expected)

    def test_receipt_chain_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            two_command_fixture(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            parsed = read_receipts(receipts)
            # Run-start record, two command receipts, run-completion record.
            self.assertEqual(len(parsed), 4)
            self.assertEqual(
                [r["command_id"] for r in parsed[1:3]],
                ["npm-test", "make-test"],
            )
            prev = GENESIS
            for receipt in parsed:
                self.assertEqual(
                    recompute_chain(receipt, prev), receipt["chain_sha256"]
                )
                prev = receipt["chain_sha256"]

    def test_check_receipts_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            two_command_fixture(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn(
                "RECEIPTS: PASS task 1: 2 receipts, chain valid", proc.stdout
            )

    def test_check_receipts_no_receipts_for_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            two_command_fixture(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "99")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("RECEIPTS: FAIL task 99: no receipts", proc.stdout)

    def test_check_receipts_failed_receipt_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\tfalse\n")
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1)
            self.assertIn(
                "RECEIPTS: FAIL task 1: receipt failed: make-test", proc.stdout
            )

    def test_check_receipts_detects_tampered_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            two_command_fixture(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            lines = receipts.read_text(encoding="utf-8").splitlines()
            first = json.loads(lines[1])
            original = first["stdout_sha256"]
            flipped = ("a" if original[0] != "a" else "b") + original[1:]
            first["stdout_sha256"] = flipped
            lines[1] = json.dumps(first)
            receipts.write_text("\n".join(lines) + "\n", encoding="utf-8")
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("RECEIPTS: chain broken at line 2", proc.stdout)

    def test_check_receipts_detects_deleted_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\ttrue\n")
            receipts = root / "r.jsonl"
            for task in ("1", "2", "3"):
                proc = verify(root, task, receipts)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            lines = receipts.read_text(encoding="utf-8").splitlines()
            # Three runs, each a run-start record, one command receipt,
            # and one completion record.
            self.assertEqual(len(lines), 9)
            del lines[1]
            receipts.write_text("\n".join(lines) + "\n", encoding="utf-8")
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("RECEIPTS: chain broken at line 2", proc.stdout)

    def test_check_receipts_corrupt_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\ttrue\n")
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            with receipts.open("a", encoding="utf-8") as fh:
                fh.write("not json\n")
            line_count = len(
                receipts.read_text(encoding="utf-8").splitlines()
            )
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1)
            self.assertIn(
                f"RECEIPTS: corrupt at line {line_count}", proc.stdout
            )

    def test_verify_appends_run_completion_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            two_command_fixture(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            parsed = read_receipts(receipts)
            self.assertEqual(len(parsed), 4)
            self.assertEqual(parsed[0]["kind"], "run-start")
            completion = parsed[-1]
            self.assertEqual(completion["kind"], "run-complete")
            self.assertEqual(completion["run_id"], parsed[0]["run_id"])
            self.assertEqual(completion["task"], "1")
            self.assertEqual(completion["command_count"], 2)
            expected_digest = hashlib.sha256(
                json.dumps(["npm-test", "make-test"]).encode("utf-8")
            ).hexdigest()
            self.assertEqual(completion["commands_sha256"], expected_digest)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_check_receipts_truncated_run_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            two_command_fixture(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            lines = receipts.read_text(encoding="utf-8").splitlines()
            # Truncate the way a partial artifact would lose its tail:
            # the last command receipt and the completion record are gone.
            receipts.write_text(lines[0] + "\n", encoding="utf-8")
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("no completion record", proc.stdout)

    def test_check_receipts_partial_run_fails(self):
        # The receipts state a budget-exhausted run leaves behind: the
        # first command's passing receipt, and nothing after it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "r.jsonl"
            binding = mechanical_verify.tree_binding(
                root, receipts_path=receipts
            )
            mechanical_verify.append_run_start(
                receipts, "1", "run-x", binding=binding
            )
            result = VerificationResult(
                command=VerificationCommand(
                    "npm-test", "Node tests", ("npm", "test")
                ),
                exit_code=0,
                timed_out=False,
                duration_ms=5,
                stdout="",
                stderr="",
                output_truncated=False,
            )
            append_receipt(receipts, "1", result, run_id="run-x")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = check_receipts(receipts, "1", root)
            self.assertEqual(rc, 1)
            self.assertIn("no completion record", stdout.getvalue())

    def test_check_receipts_retry_after_interrupted_run_passes(self):
        # Codex round-2 finding: an interrupted run (receipts, no
        # completion) followed by a successful retry for the same
        # task/file must PASS — the latest run segment validates
        # independently, earlier segments stay audit history.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            two_command_fixture(root)
            receipts = root / "r.jsonl"
            interrupted = "interrupted-run"
            mechanical_verify.append_run_start(receipts, "1", interrupted)
            result = VerificationResult(
                command=VerificationCommand(
                    "npm-test", "Node tests", ("npm", "test")
                ),
                exit_code=0,
                timed_out=False,
                duration_ms=5,
                stdout="",
                stderr="",
                output_truncated=False,
            )
            mechanical_verify.append_receipt(
                receipts, "1", result, run_id=interrupted
            )
            self.assertEqual(len(read_receipts(receipts)), 2)
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn(
                "RECEIPTS: PASS task 1: 2 receipts, chain valid", proc.stdout
            )

    def test_check_receipts_interrupted_run_alone_fails(self):
        # A run-start plus one passing receipt, no completion record,
        # must FAIL — the interrupted run is not evidence.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "r.jsonl"
            binding = mechanical_verify.tree_binding(
                root, receipts_path=receipts
            )
            mechanical_verify.append_run_start(
                receipts, "1", "run-a", binding=binding
            )
            result = VerificationResult(
                command=VerificationCommand(
                    "npm-test", "Node tests", ("npm", "test")
                ),
                exit_code=0,
                timed_out=False,
                duration_ms=5,
                stdout="",
                stderr="",
                output_truncated=False,
            )
            mechanical_verify.append_receipt(
                receipts, "1", result, run_id="run-a"
            )
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("no completion record", proc.stdout)

    def test_check_receipts_retry_interrupted_again_fails(self):
        # Two interrupted runs in a row: the latest run has no
        # completion record, so the check must FAIL even though the
        # earlier run's receipts are all passing.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "r.jsonl"
            binding = mechanical_verify.tree_binding(
                root, receipts_path=receipts
            )
            for run_id in ("run-a", "run-b"):
                mechanical_verify.append_run_start(
                    receipts, "1", run_id, binding=binding
                )
                result = VerificationResult(
                    command=VerificationCommand(
                        "npm-test", "Node tests", ("npm", "test")
                    ),
                    exit_code=0,
                    timed_out=False,
                    duration_ms=5,
                    stdout="",
                    stderr="",
                    output_truncated=False,
                )
                mechanical_verify.append_receipt(
                    receipts, "1", result, run_id=run_id
                )
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("no completion record", proc.stdout)

    def test_check_receipts_scoped_per_task(self):
        # Per-task scoping under binding: task A's segment stays valid
        # evidence about its own head after task B's failing run on a
        # later commit (validated with --historical — the default
        # completion gate for A correctly reports HEAD-MOVED), and B's
        # failure is B's alone.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "A", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            commit_file(root, "Makefile", "test:\n\tfalse\n", "break it")
            proc = verify(root, "B", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            proc = check(receipts, "A", historical=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn(
                "RECEIPTS: PASS task A: 1 receipts, chain valid", proc.stdout
            )
            proc = check(receipts, "A")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("RECEIPTS: HEAD-MOVED", proc.stdout)
            proc = check(receipts, "B")
            self.assertEqual(proc.returncode, 1)
            self.assertIn(
                "RECEIPTS: FAIL task B: receipt failed: make-test", proc.stdout
            )


def _path_pytest_available() -> bool:
    """The verifier's pytest command is literal `python3 -m pytest`:
    what matters is the python3 on PATH, not this test process."""
    try:
        proc = subprocess.run(
            ["python3", "-m", "pytest", "--version"],
            capture_output=True,
            timeout=30,
        )
    except OSError:
        return False
    return proc.returncode == 0


MIXED_OK = (
    "import unittest\n\n\n"
    "class Ok(unittest.TestCase):\n"
    "    def test_ok(self):\n"
    "        pass\n"
)


@unittest.skipUnless(
    _path_pytest_available(), "python3 on PATH has no pytest module"
)
class MixedRunnerReceiptTests(unittest.TestCase):
    """Mixed unittest+pytest suites: runner selection is per style, so
    plain pytest functions in non-unittest modules are collected too."""

    def test_mixed_suite_failing_pytest_function_fails_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "r.jsonl"
            write(root, "test_ok.py", MIXED_OK)
            write(
                root,
                "test_bad.py",
                "def test_bad():\n"
                "    assert False, 'plain pytest failure must run'\n",
            )
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("VERIFY: pytest FAIL", proc.stdout)
            parsed = read_receipts(receipts)
            command_receipts = [
                r for r in parsed if r.get("command_id") is not None
            ]
            self.assertEqual(
                [r["command_id"] for r in command_receipts],
                ["unittest", "pytest"],
            )
            self.assertEqual(command_receipts[0]["exit_code"], 0)
            self.assertNotEqual(command_receipts[1]["exit_code"], 0)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1)

    def test_mixed_suite_all_passing_runs_both_runners(self):
        with tempfile.TemporaryDirectory() as tmp:
            # The root is a subdirectory so the plain function's marker
            # lands OUTSIDE the tree — a file created inside the root
            # during the run is tree mutation and must not seal.
            root = Path(tmp) / "repo"
            root.mkdir()
            receipts = root / "r.jsonl"
            write(root, "test_ok.py", MIXED_OK)
            write(
                root,
                "test_good.py",
                "from pathlib import Path\n\n\n"
                "def test_good():\n"
                "    marker = Path(__file__).resolve().parent.parent"
                " / 'pytest-side.ran'\n"
                "    marker.write_text('ran')\n",
            )
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            # The plain pytest function demonstrably executed.
            self.assertTrue((Path(tmp) / "pytest-side.ran").is_file())
            parsed = read_receipts(receipts)
            command_receipts = [
                r for r in parsed if r.get("command_id") is not None
            ]
            self.assertEqual(
                [r["command_id"] for r in command_receipts],
                ["unittest", "pytest"],
            )
            completion = parsed[-1]
            self.assertEqual(completion.get("kind"), "run-complete")
            self.assertEqual(completion["command_count"], 2)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn(
                "RECEIPTS: PASS task 1: 2 receipts, chain valid", proc.stdout
            )


class BindingTests(unittest.TestCase):
    """Task 1 (overseer remediation R1): receipts segments bind to the
    tree at their recorded HEAD, so a sealed PASS describes a tree —
    not just a label (panel P0-1)."""

    def test_tree_binding_git_mode_uses_objects_not_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            binding = mechanical_verify.tree_binding(root)
            self.assertEqual(binding["mode"], "git")
            self.assertEqual(binding["root"], str(root.resolve()))
            head = git(root, "rev-parse", "HEAD").stdout.strip()
            self.assertEqual(binding["head"], head)
            # An uncommitted working-tree edit must NOT move the
            # digest: it is computed from git objects at HEAD.
            write(root, "Makefile", "test:\n\tfalse\n")
            self.assertEqual(
                mechanical_verify.tree_binding(root)["tree_digest"],
                binding["tree_digest"],
            )
            commit_file(root, "Makefile", "test:\n\tfalse\n", "break")
            self.assertNotEqual(
                mechanical_verify.tree_binding(root)["tree_digest"],
                binding["tree_digest"],
            )

    def test_tree_binding_fs_mode_exclusions_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "a.txt", "one\n")
            write(root, "sub/b.txt", "two\n")
            write(root, "__pycache__/c.cpython-312.pyc", "cache\n")
            receipts = write(root, "r.jsonl", "")
            (root / "link.txt").symlink_to("a.txt")
            binding = mechanical_verify.tree_binding(
                root, receipts_path=receipts
            )
            self.assertEqual(binding["mode"], "fs")
            self.assertIsNone(binding["head"])
            # Excluded content (tool state: a bytecode file under
            # __pycache__) never moves the digest.
            write(root, "__pycache__/c.cpython-312.pyc", "changed\n")
            write(root, "r.jsonl", "appended\n")
            self.assertEqual(
                mechanical_verify.tree_binding(
                    root, receipts_path=receipts
                )["tree_digest"],
                binding["tree_digest"],
            )
            # A symlink's target string is hashed, not followed.
            (root / "link.txt").unlink()
            (root / "link.txt").symlink_to("sub/b.txt")
            self.assertNotEqual(
                mechanical_verify.tree_binding(
                    root, receipts_path=receipts
                )["tree_digest"],
                binding["tree_digest"],
            )

    def test_tree_binding_fs_mode_records_type_and_exec_bit(self):
        # Codex P2 (gap-fix round 7): the fs digest hashed only file
        # contents, so an execution-relevant permission change left
        # the digest — and a sealed PASS — untouched. Git-mode
        # bindings already capture the executable bit via ls-tree
        # modes; the fs digest must record file type and the
        # executable bit for every entry.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = write(root, "check.sh", "#!/bin/sh\ntrue\n")
            script.chmod(0o755)
            binding = mechanical_verify.tree_binding(root)
            # Removing the executable bit moves the digest.
            script.chmod(0o644)
            self.assertNotEqual(
                mechanical_verify.tree_binding(root)["tree_digest"],
                binding["tree_digest"],
            )
            # Restoring it restores the digest exactly: the digest
            # is deterministic, so seal-time and check-time agree
            # byte-for-byte on an unchanged tree.
            script.chmod(0o755)
            self.assertEqual(
                mechanical_verify.tree_binding(root)["tree_digest"],
                binding["tree_digest"],
            )
            # A permission change that does not touch the
            # executable bit (read bits) is not execution evidence
            # and does not move the digest.
            data = write(root, "data.txt", "payload\n")
            data.chmod(0o644)
            with_data = mechanical_verify.tree_binding(root)[
                "tree_digest"
            ]
            data.chmod(0o600)
            self.assertEqual(
                mechanical_verify.tree_binding(root)["tree_digest"],
                with_data,
            )
            # A type change at the same path moves the digest.
            data.unlink()
            data.symlink_to("check.sh")
            self.assertNotEqual(
                mechanical_verify.tree_binding(root)["tree_digest"],
                with_data,
            )

    def test_bound_check_passes_on_clean_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            parsed = read_receipts(receipts)
            binding = parsed[-1]["binding"]
            self.assertEqual(binding, parsed[0]["binding"])
            self.assertEqual(binding["mode"], "git")
            self.assertEqual(
                binding["head"], git(root, "rev-parse", "HEAD").stdout.strip()
            )
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def test_scripts_symlink_external_suite_cannot_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = base / "external"
            passing = (
                "import unittest\n\n"
                "class ExternalTests(unittest.TestCase):\n"
                "    def test_passes(self):\n"
                "        self.assertTrue(True)\n"
            )
            external_test = write(
                external, "tests/test_external.py", passing
            )
            git(root, "init", "-q", "-b", "main")
            os.symlink(external, root / "scripts")
            git(root, "add", "scripts")
            git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "fixture",
            )
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            parsed = read_receipts(receipts) if receipts.exists() else []
            self.assertNotIn(
                "run-complete", [record.get("kind") for record in parsed]
            )
            external_test.write_text(
                passing.replace("assertTrue(True)", "assertTrue(False)"),
                encoding="utf-8",
            )
            proc = check_bound(receipts, "1", root)
            self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertNotIn("RECEIPTS: PASS", proc.stdout)

    def test_head_moved_default_fails_historical_passes(self):
        # Panel stale-PASS repro, git form: seal on a passing tree,
        # then commit a breaking change. The segment honestly
        # describes its own head (historical PASS) but must not gate
        # completion for the moved HEAD (default HEAD-MOVED).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            commit_file(root, "Makefile", "test:\n\tfalse\n", "break it")
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: HEAD-MOVED", proc.stdout)
            proc = check_bound(receipts, "1", root, historical=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def test_forged_tree_digest_fails_stale_historical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            parsed = read_receipts(receipts)
            completion = parsed[-1]
            digest = completion["binding"]["tree_digest"]
            completion["binding"] = dict(completion["binding"])
            completion["binding"]["tree_digest"] = (
                "0" if digest[0] != "0" else "1"
            ) + digest[1:]
            # Re-chain the forged record so only the binding is wrong.
            prev = parsed[-2]["chain_sha256"]
            completion["chain_sha256"] = recompute_chain(completion, prev)
            receipts.write_text(
                "".join(
                    json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n"
                    for r in parsed
                ),
                encoding="utf-8",
            )
            proc = check_bound(receipts, "1", root, historical=True)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)

    def test_unreadable_recorded_commit_is_unverifiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            # Destroy the recorded commit: fresh history at the same path.
            shutil.rmtree(root / ".git")
            init_git_repo(root, "test:\n\ttrue\n", message="second history")
            proc = check_bound(receipts, "1", root, historical=True)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: UNVERIFIABLE", proc.stdout)

    def test_uncommitted_mutation_default_dirty_historical_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            write(root, "Makefile", "test:\n\tfalse\n")
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: DIRTY", proc.stdout)
            proc = check_bound(receipts, "1", root, historical=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_dirty_tree_at_verify_fails_without_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            write(root, "Makefile", "test:\n\ttrue\n# uncommitted edit\n")
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)
            parsed = read_receipts(receipts)
            self.assertEqual(
                [r.get("kind") for r in parsed], ["run-start"]
            )

    def test_bookkeeping_writes_do_not_break_default_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            # The workflow's own state moves inside the root: SDD
            # bookkeeping under .superpowers/ and further chained
            # records appended to the receipts file itself.
            write(root, ".superpowers/ledger.md", "progress\n")
            proc = verify(root, "2", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def test_tracked_superpowers_modification_is_dirty(self):
        # Bucket A4 (panel CLEAN-P1): the .superpowers/ drop in
        # tree_clean applies only to UNTRACKED bookkeeping. A tracked
        # file under .superpowers/ that is modified is a real tree
        # change: verify refuses at the start gate and a default
        # check-receipts rejects a segment sealed before the change.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            commit_file(root, ".superpowers/ledger.md", "progress\n", "ledger")
            receipts = root / "r.jsonl"
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            write(root, ".superpowers/ledger.md", "tampered\n")
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: DIRTY", proc.stdout)
            proc = verify(root, "2", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)

    def test_receipts_in_fresh_untracked_directory_seals(self):
        # Codex P2 (gap-fix round 2, N2): --receipts into an
        # otherwise-untracked directory outside .superpowers/ was
        # collapsed by git status into a single `?? evidence/`
        # entry, so the exact-file exclusion for the receipts file
        # never matched and verify failed "tree not clean" without
        # running any command.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            # The directory exists but is empty (invisible to git)
            # until the run-start append lands the receipts file
            # in it.
            (root / "evidence").mkdir()
            receipts = root / "evidence" / "receipts.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            parsed = read_receipts(receipts)
            self.assertEqual(parsed[-1].get("kind"), "run-complete")
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def test_sibling_file_in_receipts_directory_is_dirty(self):
        # The per-file enumeration must not overreach: another
        # untracked file in the receipts file's directory is a real
        # tree change, not bookkeeping — the exclusion covers the
        # receipts file exactly, never its whole directory.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "evidence" / "receipts.jsonl"
            write(root, "evidence/stray.txt", "not bookkeeping\n")
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)

    def test_legacy_segment_without_binding_is_unbound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\ttrue\n")
            receipts = root / "r.jsonl"
            # Pre-change format: no binding on any record.
            run_id = "legacy-run"
            mechanical_verify.append_run_start(receipts, "1", run_id)
            command = next(
                c
                for c in mechanical_verify.discover_verification_commands(
                    root
                )
                if c.id == "make-test"
            )
            result = run_verification(root, command)
            mechanical_verify.append_receipt(
                receipts, "1", result, run_id=run_id
            )
            mechanical_verify.append_completion(
                receipts, "1", [command], run_id=run_id
            )
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: UNBOUND", proc.stdout)

    def test_fs_mode_mutation_after_verify_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\ttrue\n")
            receipts = Path(tmp) / "outside" / "r.jsonl"
            receipts.parent.mkdir()
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            write(root, "Makefile", "test:\n\tfalse\n")
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)

    def test_fs_mode_sitecustomize_mutation_is_stale(self):
        # Task 15 (validation 5's truncated section 3 left this
        # surface unrecorded; probed for the remediation): a
        # root-level sitecustomize.py does not execute at the
        # Python legs' startup under the verifier's -m argv
        # shapes — site imports it only from sys.path entries
        # present at interpreter init, which the caller's
        # PYTHONPATH controls (the disclosed caller-environment
        # channel) — but executed or not, the file is ordinary
        # root content and the fs binding covers it: mutating
        # it under a standing seal is STALE like any other
        # root file's mutation.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\ttrue\n")
            write(root, "sitecustomize.py", "# operator notes\n")
            receipts = Path(tmp) / "outside" / "r.jsonl"
            receipts.parent.mkdir()
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)
            write(root, "sitecustomize.py", "# edited after the seal\n")
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)

    def test_fs_mode_exec_bit_removal_is_stale(self):
        # Codex's exact reproduction: verify an fs root whose
        # Makefile invokes ./check.sh, seal, then remove the
        # script's executable bit. No content changed, but the
        # sealed PASS must stop validating — verifying the current
        # tree would fail with permission denied.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\t./check.sh\n")
            script = write(root, "check.sh", "#!/bin/sh\ntrue\n")
            script.chmod(0o755)
            receipts = Path(tmp) / "outside" / "r.jsonl"
            receipts.parent.mkdir()
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)
            script.chmod(0o644)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)
            # Restoring the bit makes the honest tree validate
            # again, and a content-only change still invalidates.
            script.chmod(0o755)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            write(root, "check.sh", "#!/bin/sh\ntrue\n# edited\n")
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)

    def test_skill_invocation_matches_cli(self):
        repo_root = Path(__file__).resolve().parents[2]
        skill = (
            repo_root / "skills" / "subagent-driven-development" / "SKILL.md"
        ).read_text(encoding="utf-8")
        # The literal check-receipts invocation the skill teaches must
        # be the CLI the code accepts (grep-pin, brief Step 4).
        self.assertIn(
            "check-receipts --receipts <workspace>/receipts.jsonl "
            "--task <N> --root <task worktree>",
            skill,
        )
        self.assertIn("--historical", skill)
        proc = run_cli("check-receipts", "--help")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("--root", proc.stdout)
        self.assertIn("--historical", proc.stdout)


class ContentBindingTests(unittest.TestCase):
    """Task 10 (paperthin-validation remediation): the tree binding
    must cover the content a sealed run can execute. PR #42 excluded
    twelve directory names from the fs digest and from tree_clean's
    untracked check; code a run executes from eight of them
    (dependency, venv, and build-output directories) was bound
    nowhere — seal, mutate only that content, and check-receipts
    still blessed the run while a fresh verify failed (validator
    probes P-01..P-05: the #62 stale-PASS class through the digest's
    exclusion door). The eight content-bearing names are bound now.
    The four residue names (.git, __pycache__, .pytest_cache,
    .mypy_cache) stay excluded: the verifier's own legs regenerate
    them during the run itself (a pytest leg creates .pytest_cache
    and __pycache__ from cold), so binding them would make the
    run's own residue abort every seal of a Python tree.

    (Task 11 narrows that last sentence: the exclusion covers
    tool state only — code files under the four names bind now;
    see ResidueCodeBindingTests. Its round 2 narrows it once
    more: under the three cache names EVERY non-tool-state file
    binds, so the loop below asserts a plain payload binds
    there too; only .git keeps a payload unbound.)"""

    CONTENT_DIRS = [
        "node_modules",
        "target",
        "coverage",
        "htmlcov",
        "dist",
        "build",
        ".tox",
        ".venv",
    ]
    RESIDUE_DIRS = [".git", "__pycache__", ".pytest_cache", ".mypy_cache"]

    def test_fs_digest_binds_content_dirs_but_not_residue(self):
        for name in self.CONTENT_DIRS:
            with self.subTest(name=name, kind="content"):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write(root, "a.txt", "one\n")
                    before = mechanical_verify.tree_binding(root)[
                        "tree_digest"
                    ]
                    write(root, f"{name}/payload.txt", "payload\n")
                    after = mechanical_verify.tree_binding(root)[
                        "tree_digest"
                    ]
                    self.assertNotEqual(before, after)
                    write(root, f"{name}/payload.txt", "changed\n")
                    self.assertNotEqual(
                        after,
                        mechanical_verify.tree_binding(root)[
                            "tree_digest"
                        ],
                    )
        for name in self.RESIDUE_DIRS:
            with self.subTest(name=name, kind="residue"):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write(root, "a.txt", "one\n")
                    before = mechanical_verify.tree_binding(root)[
                        "tree_digest"
                    ]
                    write(root, f"{name}/payload.txt", "payload\n")
                    after = mechanical_verify.tree_binding(root)[
                        "tree_digest"
                    ]
                    if name == ".git":
                        # .git's bind set is enumerated (code,
                        # archives, hooks); a plain payload is
                        # outside it and stays unbound.
                        self.assertEqual(before, after)
                    else:
                        # Task 11 round 2 (finding F1): under a
                        # cache name the rule inverts — a plain
                        # payload is not the tool's own state, so
                        # it binds like content anywhere.
                        self.assertNotEqual(before, after)

    def _seal_import_fixture(self, root: Path, helper_rel: str) -> Path:
        """A pytest suite whose only test imports a helper from
        *helper_rel*'s directory (validator P-01/P-03 shape)."""
        helper_dir = str(Path(helper_rel).parent)
        write(root, helper_rel, 'VALUE = "ok"\n')
        write(
            root,
            "test_app.py",
            "import sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, str(Path(__file__).parent / {helper_dir!r}))\n"
            "import helper\n\n\n"
            "def test_helper_value():\n"
            "    assert helper.VALUE == 'ok'\n",
        )
        receipts = root / "r.jsonl"
        proc = verify(root, "1", receipts)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = check(receipts, "1")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("RECEIPTS: PASS", proc.stdout)
        return receipts

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_fs_node_modules_helper_mutation_goes_stale(self):
        # Validator P-01: pre-fix this sealed, the mutation left the
        # audit at PASS, and only a fresh verify noticed.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = self._seal_import_fixture(
                root, "node_modules/helper.py"
            )
            write(root, "node_modules/helper.py", 'VALUE = "broken"\n')
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_fs_venv_helper_mutation_goes_stale(self):
        # Validator P-03: same shape through .venv.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = self._seal_import_fixture(
                root, ".venv/lib/helper.py"
            )
            write(root, ".venv/lib/helper.py", 'VALUE = "broken"\n')
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_fs_build_testpaths_mutation_goes_stale(self):
        # Validator P-02: a bound config aims collection into build/;
        # the collected file is the test itself.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pytest.ini", "[pytest]\ntestpaths = build\n")
            write(
                root,
                "build/test_inside.py",
                "def test_inside():\n    assert True\n",
            )
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)
            write(
                root,
                "build/test_inside.py",
                "def test_inside():\n    assert False\n",
            )
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_fs_unimported_content_dir_is_bound_anyway(self):
        # The new contract is unconditional: content directories
        # bind whether or not this run reached into them, so a later
        # mutation is STALE even when nothing imported the file.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            write(root, "node_modules/unused.py", "X = 1\n")
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            write(root, "node_modules/unused.py", "X = 2\n")
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_fs_residue_churn_does_not_self_stale(self):
        # The run's own residue (__pycache__, .pytest_cache — absent
        # at bind time, created by the run) must not break the seal,
        # on the first run or on a warm-cache rerun.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            receipts = root / "r.jsonl"
            for _ in range(2):
                proc = verify(root, "1", receipts)
                self.assertEqual(
                    proc.returncode, 0, proc.stdout + proc.stderr
                )
                proc = check(receipts, "1")
                self.assertEqual(
                    proc.returncode, 0, proc.stdout + proc.stderr
                )
                self.assertIn("RECEIPTS: PASS", proc.stdout)
            self.assertTrue((root / "__pycache__").is_dir())
            self.assertTrue((root / ".pytest_cache").is_dir())

    def test_git_untracked_content_dir_blocks_sealing(self):
        # Validator P-04: an untracked helper under node_modules was
        # dropped from the cleanliness check, so the run sealed over
        # content the binding (HEAD) never saw.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            commit_file(
                root,
                "main_app.py",
                "import helper\n\nVALUE = helper.VALUE\n",
                "add app",
            )
            write(root, "node_modules/helper.py", 'VALUE = "ok"\n')
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)
            # Committing the helper binds it (ls-tree) and unblocks.
            commit_file(
                root, "node_modules/helper.py", 'VALUE = "ok"\n', "add helper"
            )
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def test_git_tree_clean_ignores_residue_but_not_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            write(root, "__pycache__/mod.cpython-312.pyc", "cache\n")
            write(root, ".pytest_cache/v/cache/nodeids", "[]\n")
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            write(root, "build/out.txt", "artifact\n")
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_git_run_creating_content_dir_cannot_seal(self):
        # A run that creates a content directory mid-run has changed
        # the tree it attests: no completion record (pre-fix the
        # created build/ was dropped from the cleanliness check and
        # the run sealed).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(
                root,
                makefile="test:\n\tmkdir -p build && touch build/out.txt\n",
            )
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("without a completion record", proc.stdout)
            proc = check(receipts, "1")
            self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def _submodule_super(self, tmp: str) -> Path:
        base = Path(tmp)
        src = base / "src"
        src.mkdir()
        git(src, "init", "-q", "-b", "main")
        write(src, "f.txt", "x\n")
        git(src, "add", "f.txt")
        git(
            src,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-q",
            "-m",
            "src",
        )
        root = base / "super"
        root.mkdir()
        init_git_repo(root)
        git(
            root,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            str(src),
            "sub",
        )
        git(
            root,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-q",
            "-m",
            "add submodule",
        )
        return root

    def test_git_submodule_untracked_content_counts_dirty_by_default(self):
        # Validator P-05, control direction: under git's default
        # submodule handling, untracked content inside a submodule
        # surfaces as the submodule's own dirtiness — a tracked
        # entry tree_clean never drops — whatever directory name
        # the file sits under inside the submodule.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._submodule_super(tmp)
            receipts = root / "r.jsonl"
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            write(root, "sub/node_modules/helper.py", 'VALUE = "ok"\n')
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_git_submodule_ignore_untracked_is_the_stated_limit(self):
        # With submodule.<name>.ignore=untracked — the setting a
        # submodule tree currently needs to seal at all (the run's
        # own cache churn inside the submodule otherwise dirties it
        # between the two cleanliness checks) — untracked content
        # inside the submodule is invisible to the superproject's
        # status and therefore outside the binding. Tracked content
        # inside the submodule stays bound by the gitlink. This
        # pins the documented limit so closing it later is a
        # deliberate test change.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._submodule_super(tmp)
            git(root, "config", "submodule.sub.ignore", "untracked")
            receipts = root / "r.jsonl"
            write(root, "sub/node_modules/helper.py", 'VALUE = "ok"\n')
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))


class ResidueCodeBindingTests(unittest.TestCase):
    """Task 11 (paperthin validation 2, §1): the residue exclusion
    cannot extend to planted source. Validation 1 closed the
    content-directory door (Task 10); validation 2 found plain
    SOURCE under the four residue names — imported by bound code
    (B1a/B1b/B1c) or collected via bound testpaths (B2) — was just
    as invisible: seal, mutate only the planted file, and
    check-receipts still blessed the run while a fresh verify
    failed. Code files under a residue name bind now, in both
    modes; only tool-state files (.pyc bytecode, cache data) stay
    unbound, which is what keeps mid-run cache generation from
    aborting a seal. The B2 collection shape is additionally
    refused at discovery (see ResidueConfigAimTests in
    test_mechanical_verify.py).

    Round 2 (Task 11 review, findings F1–F3): under the three
    cache names the rule inverts — everything except the owning
    tool's own state files binds, because zipimport loads a
    module by name from an archive of ANY filename and no suffix
    list can enumerate what a runtime loads. Under .git the bind
    set stays enumerated (code files, module archives, hooks):
    git rewrites its other control files under ordinary
    operations, so inverting there would abort seals on git's
    own bookkeeping."""

    RESIDUE_DIRS = [".git", "__pycache__", ".pytest_cache", ".mypy_cache"]

    # One file per residue name that its owning tool itself
    # writes — the enumerated tool state of
    # mechanical_verify._is_tool_state_file (git's entry is one
    # of its own control files, unbound under the .git rule).
    TOOL_STATE = {
        ".pytest_cache": "v/cache/nodeids",
        ".mypy_cache": "3.12/mod.data.json",
        "__pycache__": "mod.cpython-312.pyc",
        ".git": "config",
    }

    def test_fs_digest_binds_code_but_not_tool_state_under_residue(self):
        for name in self.RESIDUE_DIRS:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write(root, "a.txt", "one\n")
                    before = mechanical_verify.tree_binding(root)[
                        "tree_digest"
                    ]
                    # Tool state is what the run itself
                    # regenerates; it stays unbound so a seal
                    # cannot abort on it.
                    write(
                        root,
                        f"{name}/{self.TOOL_STATE[name]}",
                        "state\n",
                    )
                    self.assertEqual(
                        before,
                        mechanical_verify.tree_binding(root)[
                            "tree_digest"
                        ],
                    )
                    # Planted source binds, and mutating it moves
                    # the digest.
                    write(root, f"{name}/planted/helper.py", "X = 1\n")
                    bound = mechanical_verify.tree_binding(root)[
                        "tree_digest"
                    ]
                    self.assertNotEqual(before, bound)
                    write(root, f"{name}/planted/helper.py", "X = 2\n")
                    self.assertNotEqual(
                        bound,
                        mechanical_verify.tree_binding(root)[
                            "tree_digest"
                        ],
                    )

    def test_fs_digest_binds_any_non_tool_state_under_cache_names(self):
        # Round 2, finding F1: under a cache name, a planted file
        # of ANY shape — a module archive under a .zip name or an
        # arbitrary one, an extensionless script, a collectable
        # data file — is content a sealed run can load by name,
        # so it binds; only the tool's own state stays unbound.
        for name in (".pytest_cache", ".mypy_cache", "__pycache__"):
            for rel in (
                "planted/pkg.zip",
                "planted/bundle",
                "planted/tool",
                "planted/check_data.txt",
            ):
                with self.subTest(name=name, rel=rel):
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        write(root, "a.txt", "one\n")
                        before = mechanical_verify.tree_binding(root)[
                            "tree_digest"
                        ]
                        write(root, f"{name}/{rel}", "payload\n")
                        bound = mechanical_verify.tree_binding(root)[
                            "tree_digest"
                        ]
                        self.assertNotEqual(before, bound)
                        write(root, f"{name}/{rel}", "changed\n")
                        self.assertNotEqual(
                            bound,
                            mechanical_verify.tree_binding(root)[
                                "tree_digest"
                            ],
                        )

    def test_fs_digest_binds_archive_and_hooks_under_dotgit(self):
        # Round 2: under .git the enumerated bind set gains the
        # archive suffixes importlib loads by name (.zip here)
        # and everything under hooks/ (git's own hook scripts).
        # An archive under an ARBITRARY name stays unbound there
        # — the scoped remainder the docs state.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "a.txt", "one\n")
            before = mechanical_verify.tree_binding(root)["tree_digest"]
            write(root, ".git/hooks/pre-commit", "#!/bin/sh\ntrue\n")
            self.assertNotEqual(
                before, mechanical_verify.tree_binding(root)["tree_digest"]
            )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "a.txt", "one\n")
            before = mechanical_verify.tree_binding(root)["tree_digest"]
            write(root, ".git/planted/pkg.zip", "payload\n")
            self.assertNotEqual(
                before, mechanical_verify.tree_binding(root)["tree_digest"]
            )
            write(root, ".git/planted/bundle", "payload\n")
            after = mechanical_verify.tree_binding(root)["tree_digest"]
            write(root, ".git/planted/bundle", "changed\n")
            self.assertEqual(
                after, mechanical_verify.tree_binding(root)["tree_digest"]
            )

    def test_fs_tool_state_mutation_does_not_move_digest(self):
        # Lifecycle guard for the inverted rule: post-seal, the
        # tools' own state files may be (re)written freely — a
        # warm-cache rerun rewrites exactly these — without the
        # digest moving.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "a.txt", "one\n")
            before = mechanical_verify.tree_binding(root)["tree_digest"]
            write(root, ".pytest_cache/v/cache/nodeids", "[]\n")
            write(root, ".pytest_cache/v/cache/lastfailed", "{}\n")
            write(root, ".pytest_cache/CACHEDIR.TAG", "tag\n")
            write(root, ".mypy_cache/3.12/mod.meta.json", "{}\n")
            write(root, "__pycache__/mod.cpython-312.pyc", "cache\n")
            self.assertEqual(
                before, mechanical_verify.tree_binding(root)["tree_digest"]
            )

    def test_fs_digest_binds_native_extension_under_residue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "a.txt", "one\n")
            before = mechanical_verify.tree_binding(root)["tree_digest"]
            write(root, ".mypy_cache/planted/native.so", "elf\n")
            self.assertNotEqual(
                before, mechanical_verify.tree_binding(root)["tree_digest"]
            )

    def test_fs_digest_binds_residue_code_at_any_depth(self):
        cases = [
            "pkg/.pytest_cache/planted/helper.py",
            "node_modules/pkg/__pycache__/helper.py",
            ".git/modules/sub/.mypy_cache/helper.py",
        ]
        for rel in cases:
            with self.subTest(rel=rel):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write(root, "a.txt", "one\n")
                    before = mechanical_verify.tree_binding(root)[
                        "tree_digest"
                    ]
                    write(root, rel, "X = 1\n")
                    self.assertNotEqual(
                        before,
                        mechanical_verify.tree_binding(root)[
                            "tree_digest"
                        ],
                    )
        # Non-code content at depth under a residue name stays
        # unbound (the disclosed data residual).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "a.txt", "one\n")
            before = mechanical_verify.tree_binding(root)["tree_digest"]
            write(root, "pkg/.pytest_cache/v/cache/nodeids", "[]\n")
            self.assertEqual(
                before, mechanical_verify.tree_binding(root)["tree_digest"]
            )

    def _seal_import_fixture(self, root: Path, helper_rel: str) -> Path:
        """A pytest suite whose only test imports a helper from
        *helper_rel*'s directory (validator B1 shape)."""
        helper_dir = str(Path(helper_rel).parent)
        write(root, helper_rel, 'VALUE = "ok"\n')
        write(
            root,
            "test_app.py",
            "import sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, str(Path(__file__).parent / {helper_dir!r}))\n"
            "import helper\n\n\n"
            "def test_helper_value():\n"
            "    assert helper.VALUE == 'ok'\n",
        )
        receipts = root / "r.jsonl"
        proc = verify(root, "1", receipts)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = check(receipts, "1")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("RECEIPTS: PASS", proc.stdout)
        return receipts

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_fs_pytest_cache_helper_mutation_goes_stale(self):
        # Validator B1a.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = self._seal_import_fixture(
                root, ".pytest_cache/planted/helper.py"
            )
            write(
                root,
                ".pytest_cache/planted/helper.py",
                'VALUE = "broken"\n',
            )
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_fs_mypy_cache_helper_mutation_goes_stale(self):
        # Validator B1b.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = self._seal_import_fixture(
                root, ".mypy_cache/planted/helper.py"
            )
            write(
                root, ".mypy_cache/planted/helper.py", 'VALUE = "broken"\n'
            )
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_fs_dotgit_helper_mutation_goes_stale(self):
        # Validator B1c: an fs tree (the .git directory is a plain
        # directory here, not a repository) importing from .git/.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = self._seal_import_fixture(
                root, ".git/planted/helper.py"
            )
            write(root, ".git/planted/helper.py", 'VALUE = "broken"\n')
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_fs_residue_code_tree_reseals_cleanly(self):
        # Lifecycle control: binding planted code must not break
        # the seal lifecycle for a tree that has it — seal, audit,
        # seal again over warm caches, audit again.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = self._seal_import_fixture(
                root, ".mypy_cache/planted/helper.py"
            )
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def _seal_zipimport_fixture(
        self, root: Path, archive_name: str
    ) -> Path:
        """A pytest suite whose only test imports a module from
        a zip archive planted in .pytest_cache (review finding
        F1's shape, driven through the real CLI)."""
        archive = root / ".pytest_cache" / "planted" / archive_name
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("zmod.py", 'VALUE = "ok"\n')
        write(
            root,
            "test_app.py",
            "import sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).parent"
            f" / '.pytest_cache' / 'planted' / {archive_name!r}))\n"
            "import zmod\n\n\n"
            "def test_zmod_value():\n"
            "    assert zmod.VALUE == 'ok'\n",
        )
        receipts = root / "r.jsonl"
        proc = verify(root, "1", receipts)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = check(receipts, "1")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("RECEIPTS: PASS", proc.stdout)
        return receipts

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_fs_zipimport_from_pytest_cache_goes_stale(self):
        # Review finding F1: zipimport loads the module by name
        # from the planted archive; rebuilding the archive with a
        # flipped value must flip the audit to STALE. The
        # arbitrary-filename case (zipimport accepts any name) is
        # the one a suffix list can never close.
        for archive_name in ("pkg.zip", "bundle"):
            with self.subTest(archive_name=archive_name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    receipts = self._seal_zipimport_fixture(
                        root, archive_name
                    )
                    archive = (
                        root
                        / ".pytest_cache"
                        / "planted"
                        / archive_name
                    )
                    with zipfile.ZipFile(archive, "w") as zf:
                        zf.writestr("zmod.py", 'VALUE = "broken"\n')
                    proc = check(receipts, "1")
                    self.assertEqual(
                        proc.returncode, 1, proc.stdout + proc.stderr
                    )
                    self.assertIn("RECEIPTS: STALE", proc.stdout)
                    proc = verify(root, "1", receipts)
                    self.assertEqual(
                        proc.returncode, 1, proc.stdout + proc.stderr
                    )

    def test_git_untracked_non_state_under_residue_blocks_sealing(self):
        # Git-mode parity for the inverted rule: an untracked
        # file the fs binding would cover under a residue name —
        # an archive, an arbitrary data file — counts as dirty;
        # the tools' own state stays ignored.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            write(root, ".pytest_cache/v/cache/nodeids", "[]\n")
            write(root, ".mypy_cache/3.12/mod.data.json", "{}\n")
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            write(root, ".pytest_cache/planted/pkg.zip", "payload\n")
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            (root / ".pytest_cache/planted/pkg.zip").unlink()
            write(root, ".mypy_cache/planted/blob", "payload\n")
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)

    def test_git_untracked_code_under_residue_blocks_sealing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            # Tool state under residue names stays ignored.
            write(root, ".pytest_cache/v/cache/nodeids", "[]\n")
            write(root, "__pycache__/mod.cpython-312.pyc", "cache\n")
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            # Planted code under a residue name is dirty like
            # untracked code anywhere else.
            write(root, ".pytest_cache/planted/helper.py", "X = 1\n")
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)
            (root / ".pytest_cache/planted/helper.py").unlink()
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))

    def test_git_tracked_code_under_residue_binds_via_ls_tree(self):
        # Control (already true pre-fix; pinned so the parity
        # claim stays honest): tracked content under a residue
        # name is in ls-tree, so it binds exactly like tracked
        # content anywhere, and a working-tree edit is dirty.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            commit_file(
                root, ".mypy_cache/planted/helper.py", "X = 1\n", "plant"
            )
            receipts = root / "r.jsonl"
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            first = mechanical_verify.tree_binding(root)["tree_digest"]
            commit_file(
                root, ".mypy_cache/planted/helper.py", "X = 2\n", "change"
            )
            self.assertNotEqual(
                first, mechanical_verify.tree_binding(root)["tree_digest"]
            )
            write(root, ".mypy_cache/planted/helper.py", "X = 3\n")
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))


SWAP_MAKEFILE_H1 = "test:\n\tgit reset --hard HEAD~1\n\ttrue\n"


def swap_fixture(root: Path, swap_body: str, makefile_h0: str) -> None:
    """Panel P0 attack fixture: an npm-test wrapper (swap.sh) runs
    first and may move HEAD; make-test then runs against whatever
    tree HEAD names. At H0 the Makefile is `makefile_h0`."""
    git(root, "init", "-q", "-b", "main")
    write(
        root,
        "package.json",
        json.dumps({"scripts": {"test": "sh swap.sh"}}),
    )
    write(root, "swap.sh", swap_body)
    write(root, "Makefile", makefile_h0)
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-q",
        "-m",
        "H0",
    )


class InRunBindingTests(unittest.TestCase):
    """Bucket A1 (panel SEC-P0-1): the binding is revalidated around
    each command. A command that moves HEAD mid-run — even one that
    restores it before the seal — must abort the run with no
    completion record, so the segment can never validate as a PASS
    for a tree the later commands did not run against."""

    def test_commit_reset_round_trip_aborts_without_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            swap = (
                "#!/bin/sh\n"
                "git config user.name Fixture\n"
                "git config user.email fixture@example.invalid\n"
                "cat > Makefile <<'EOF'\n"
                + SWAP_MAKEFILE_H1
                + "EOF\n"
                "git add Makefile\n"
                "git commit -q -m H1-passing-tree\n"
            )
            # At H0 `make test` fails; only the swapped-in H1 tree
            # (whose recipe resets back to H0, then passes) is green.
            swap_fixture(root, swap, "test:\n\tfalse\n")
            receipts = root / "r.jsonl"
            proc = verify(root, "swap", receipts)
            self.assertNotEqual(
                proc.returncode, 0, proc.stdout + proc.stderr
            )
            self.assertIn("binding changed during the run", proc.stdout)
            kinds = [r.get("kind") for r in read_receipts(receipts)]
            self.assertNotIn("run-complete", kinds)
            proc = check(receipts, "swap")
            self.assertNotEqual(
                proc.returncode, 0, proc.stdout + proc.stderr
            )
            self.assertNotIn("RECEIPTS: PASS", proc.stdout)

    def test_commit_without_reset_aborts_without_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            swap = (
                "#!/bin/sh\n"
                "git config user.name Fixture\n"
                "git config user.email fixture@example.invalid\n"
                "printf 'test:\\n\\ttrue\\n' > Makefile\n"
                "git add Makefile\n"
                "git commit -q -m H1-passing-tree\n"
            )
            swap_fixture(root, swap, "test:\n\tfalse\n")
            receipts = root / "r.jsonl"
            proc = verify(root, "swap", receipts)
            self.assertNotEqual(
                proc.returncode, 0, proc.stdout + proc.stderr
            )
            self.assertIn("binding changed during the run", proc.stdout)
            kinds = [r.get("kind") for r in read_receipts(receipts)]
            self.assertNotIn("run-complete", kinds)

    def test_empty_commit_same_tree_aborts_without_completion(self):
        # HEAD moves while the tree digest stands still: the segment
        # claims the recorded COMMIT, so head alone moving is enough.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            swap = (
                "#!/bin/sh\n"
                "git config user.name Fixture\n"
                "git config user.email fixture@example.invalid\n"
                "git commit -q --allow-empty -m empty-detour\n"
                "git reset --hard HEAD~1\n"
                "git commit -q --allow-empty -m empty-other\n"
            )
            swap_fixture(root, swap, "test:\n\ttrue\n")
            receipts = root / "r.jsonl"
            proc = verify(root, "swap", receipts)
            self.assertNotEqual(
                proc.returncode, 0, proc.stdout + proc.stderr
            )
            self.assertIn("binding changed during the run", proc.stdout)
            kinds = [r.get("kind") for r in read_receipts(receipts)]
            self.assertNotIn("run-complete", kinds)

    def test_no_swap_control_seals_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            swap_fixture(root, "#!/bin/sh\ntrue\n", "test:\n\ttrue\n")
            receipts = root / "r.jsonl"
            proc = verify(root, "swap", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "swap")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)


class PlacementAndStrictTypeTests(unittest.TestCase):
    """Task 8 (overseer remediation R7): (a) verify refuses a receipts
    file that is tracked by git inside the root — evidence must not be
    part of the artifact (P2-1 residue); (b) check_receipts validates
    field TYPES in the selected segment, so a bool wearing an int's
    clothes reads corrupt instead of passing (panel EXP5 / P3-1)."""

    # -- (a) receipts placement ------------------------------------

    def test_verify_refuses_receipts_tracked_in_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = write(root, "r.jsonl", "")
            git(root, "add", "r.jsonl")
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("tracked", proc.stdout)

    def test_verify_refuses_receipts_committed_in_subdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = write(root, "sub/r.jsonl", "")
            git(root, "add", "sub/r.jsonl")
            git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "track the receipts file",
            )
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("tracked", proc.stdout)

    def test_verify_allows_untracked_receipts_inside_root(self):
        # The SDD layout: an untracked receipts file inside the root
        # is explicitly allowed.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    # -- (b) strict field types ------------------------------------

    def _bound_segment(self, root: Path, receipts: Path) -> list[dict]:
        init_git_repo(root)
        proc = verify(root, "1", receipts)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return read_receipts(receipts)

    def test_bool_exit_code_in_selected_segment_is_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "r.jsonl"
            parsed = self._bound_segment(root, receipts)
            receipt = next(r for r in parsed if "exit_code" in r)
            receipt["exit_code"] = False
            rewrite_rechained(receipts, parsed)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("corrupt", proc.stdout)
            self.assertIn("exit_code", proc.stdout)

    def test_bool_duration_ms_in_selected_segment_is_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "r.jsonl"
            parsed = self._bound_segment(root, receipts)
            receipt = next(r for r in parsed if "duration_ms" in r)
            receipt["duration_ms"] = True
            rewrite_rechained(receipts, parsed)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("corrupt", proc.stdout)
            self.assertIn("duration_ms", proc.stdout)

    def test_bool_command_count_in_selected_segment_is_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "r.jsonl"
            parsed = self._bound_segment(root, receipts)
            parsed[-1]["command_count"] = True
            rewrite_rechained(receipts, parsed)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("corrupt", proc.stdout)
            self.assertIn("command_count", proc.stdout)

    def test_wrong_type_in_earlier_segment_does_not_poison_retry(self):
        # Type validation is scoped to the SELECTED segment: an oddity
        # in a superseded segment is audit history, not corruption of
        # the segment under validation.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "r.jsonl"
            parsed = self._bound_segment(root, receipts)
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            parsed = read_receipts(receipts)
            first_segment_receipt = next(
                r for r in parsed if "duration_ms" in r
            )
            first_segment_receipt["duration_ms"] = True
            rewrite_rechained(receipts, parsed)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def test_null_exit_code_spawn_error_then_valid_retry_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            # An interrupted run whose only receipt is a spawn error:
            # exit_code is legitimately null there.
            run_id = "spawn-error-run"
            mechanical_verify.append_run_start(receipts, "1", run_id)
            command = next(
                c
                for c in mechanical_verify.discover_verification_commands(
                    root
                )
                if c.id == "make-test"
            )
            result = VerificationResult(
                command=command,
                exit_code=None,
                timed_out=False,
                duration_ms=0,
                stdout="",
                stderr="",
                output_truncated=False,
            )
            mechanical_verify.append_receipt(
                receipts, "1", result, run_id=run_id
            )
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def test_unknown_field_in_selected_segment_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "r.jsonl"
            parsed = self._bound_segment(root, receipts)
            receipt = next(r for r in parsed if "exit_code" in r)
            receipt["future_field"] = {"anything": [1, 2]}
            rewrite_rechained(receipts, parsed)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_real_bound_segment_with_collected_counts_validates(self):
        # A REAL segment from a fixture verify run — carrying the
        # Task 1/2/4/5 record extensions (binding dict, subreaper
        # bool, env str, tests_collected int) — validates clean under
        # the strict type map: the plan's own records never read as
        # corrupt.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "test_ok.py", "def test_ok():\n    assert True\n")
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "test_ok.py")
            git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "fixture",
            )
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            parsed = read_receipts(receipts)
            self.assertIsInstance(parsed[0]["binding"], dict)
            self.assertIsInstance(parsed[0]["subreaper"], bool)
            self.assertIsInstance(parsed[0]["env"], str)
            receipt = next(r for r in parsed if "exit_code" in r)
            self.assertIsInstance(receipt["tests_collected"], int)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)


class TraversalGateBindingTests(unittest.TestCase):
    """Task 12 (paperthin validation 3, breach B-NEW), git-mode
    instance: the planted file lives inside the repository's
    real .git directory, where git status never looks and the
    git-mode binding's enumerated .git set (code files, module
    archives, hooks) does not reach a .txt data file. Pre-fix
    the tree sealed with the planted item in the count and
    check-receipts kept passing after it was mutated; the
    traversal gate refuses the leg at discovery, so nothing
    seals. The fs-mode instance and the gate's unit matrix are
    in test_mechanical_verify.py (TraversalGateTests)."""

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_n7a_fixture_refused_in_git_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pytest.ini",
                "[pytest]\nnorecursedirs = *.egg\n",
            )
            write(
                root,
                "conftest.py",
                "import pytest\n\n\n"
                "class TxtFile(pytest.File):\n"
                "    def collect(self):\n"
                "        yield TxtItem.from_parent(self, name='planted')\n\n\n"
                "class TxtItem(pytest.Item):\n"
                "    def runtest(self):\n"
                "        namespace = {}\n"
                "        exec(self.path.read_text(), namespace)\n"
                "        namespace['test_planted']()\n\n\n"
                "def pytest_collect_file(file_path, parent):\n"
                "    if file_path.suffix == '.txt' and "
                "file_path.name.startswith('check_'):\n"
                "        return TxtFile.from_parent(parent, path=file_path)\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "pytest.ini", "conftest.py", "test_ok.py")
            git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "fixture",
            )
            # Planted inside the real .git: invisible to git
            # status, outside the enumerated bind set there.
            write(
                root,
                ".git/collected/check_a.txt",
                "def test_planted():\n    assert True\n",
            )
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(
                proc.returncode, 2, proc.stdout + proc.stderr
            )
            self.assertIn(
                "no verification commands discovered", proc.stdout
            )
            self.assertFalse(receipts.exists())


class NonRegularFileBindingTests(unittest.TestCase):
    """Task 12 (paperthin validation 3, note N4): the fs digest
    content-read every non-symlink file, so a FIFO in the tree
    blocked verify — and check_receipts, which recomputes the
    digest — forever. Only regular files are content-read now;
    any other non-directory, non-symlink entry (FIFO, socket,
    device) contributes its (path, mode) entry without being
    opened: presence and type stay bound, no read can hang.
    Git mode never opens working-tree files (its digest comes
    from git object metadata), so it was always immune."""

    def test_fs_digest_binds_fifo_by_presence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "a.txt", "one\n")
            before = mechanical_verify.tree_binding(root)["tree_digest"]
            os.mkfifo(root / "pipe")
            bound = mechanical_verify.tree_binding(root)["tree_digest"]
            self.assertNotEqual(before, bound)
            # Recomputing neither hangs nor drifts.
            self.assertEqual(
                bound,
                mechanical_verify.tree_binding(root)["tree_digest"],
            )
            # A type change at the same path moves the digest.
            (root / "pipe").unlink()
            write(root, "pipe", "payload\n")
            self.assertNotEqual(
                bound,
                mechanical_verify.tree_binding(root)["tree_digest"],
            )

    def test_fifo_under_cache_name_binds_by_presence(self):
        # The residue walk has the same read site: under a
        # cache name a FIFO is not tool state, so it binds —
        # by presence, without being opened.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "a.txt", "one\n")
            write(root, ".pytest_cache/v/cache/nodeids", "[]\n")
            before = mechanical_verify.tree_binding(root)["tree_digest"]
            os.mkfifo(root / ".pytest_cache" / "pipe")
            self.assertNotEqual(
                before,
                mechanical_verify.tree_binding(root)["tree_digest"],
            )

    def test_fifo_tree_verifies_and_audits_to_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            two_command_fixture(root)
            os.mkfifo(root / "pipe")
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(
                proc.returncode, 0, proc.stdout + proc.stderr
            )
            proc = check(receipts, "1")
            self.assertEqual(
                proc.returncode, 0, proc.stdout + proc.stderr
            )
            self.assertIn("RECEIPTS: PASS", proc.stdout)


class SuperpowersCleanlinessTests(unittest.TestCase):
    """Task 13 (paperthin validation 4, breach B-A): in git
    mode, untracked entries under `.superpowers/` were dropped
    from the cleanliness gate UNCONDITIONALLY — the one name
    whose drop was not conditioned the way the residue names'
    drop is (Task 10's parity rule). A committed test
    importing a helper planted untracked under `.superpowers/`
    executed unbound code under the seal; mutating the helper
    left check-receipts at PASS (the fs-mode control of the
    identical fixture went STALE, isolating the drop itself).

    The drop is now conditioned on code shape, with the same
    loads-by-name set the .git bind set enumerates (source and
    native extension suffixes, module archives): an untracked
    CODE-shaped file under `.superpowers/` counts as dirty
    like untracked content anywhere else — it must be
    committed (which binds it via ls-tree) or removed before
    the tree can seal. The workflow's bookkeeping is not
    code-shaped — ledgers, briefs, and receipt-shaped records
    keep waving through, which is what the SDD verify flow in
    git mode depends on."""

    TEST_MAIN = (
        "import sys\n"
        "from pathlib import Path\n\n"
        "sys.path.insert(0, str(Path(__file__).parent"
        " / '.superpowers' / 'x'))\n\n"
        "import helper\n\n\n"
        "def test_helper_value():\n"
        "    assert helper.VALUE == 'good'\n"
    )

    def _repo(self, root: Path) -> None:
        git(root, "init", "-q", "-b", "main")
        write(root, "test_main.py", self.TEST_MAIN)
        git(root, "add", "test_main.py")
        git(
            root,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture",
        )

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_untracked_code_under_superpowers_blocks_sealing(self):
        # The validator's B-A fixture rebuilt: pre-fix the
        # seal waved the planted helper through (verify rc 0,
        # audit PASS after mutation); the tree is dirty now.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            write(root, ".superpowers/x/helper.py", "VALUE = 'good'\n")
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)

    def test_untracked_archive_under_superpowers_blocks_sealing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            write(root, ".superpowers/x/bundle.zip", "not a real zip\n")
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_committed_superpowers_helper_seals_and_mutation_dirties(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            commit_file(
                root,
                ".superpowers/x/helper.py",
                "VALUE = 'good'\n",
                "add helper",
            )
            receipts = root / "r.jsonl"
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)
            # Mutating the now-tracked helper is a tracked
            # change: the audit reports the tree dirty.
            write(root, ".superpowers/x/helper.py", "VALUE = 'evil'\n")
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: DIRTY", proc.stdout)

    def test_superpowers_bookkeeping_still_waves_through(self):
        # The workflow control: untracked non-code bookkeeping
        # under .superpowers/ — a ledger, a brief, chained
        # record files at depth — keeps the tree clean, or the
        # SDD verify flow in git mode breaks.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            receipts = root / "r.jsonl"
            write(root, ".superpowers/sdd/ledger.md", "progress\n")
            write(root, ".superpowers/sdd/brief.html", "<p>brief</p>\n")
            write(root, ".superpowers/sdd/records.jsonl", "{}\n")
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_fs_mode_superpowers_helper_mutation_is_stale(self):
        # The fs-mode control of the B-A fixture: fs mode binds
        # .superpowers/ content like any other directory, so
        # the same plant-and-mutate shape goes STALE — the
        # parity the git-mode conditioning now matches for
        # code-shaped files.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "test_main.py", self.TEST_MAIN)
            write(root, ".superpowers/x/helper.py", "VALUE = 'good'\n")
            receipts = base / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)
            write(root, ".superpowers/x/helper.py", "VALUE = 'evil'\n")
            proc = check_bound(receipts, "1", root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: STALE", proc.stdout)


class SymlinkCleanlinessTests(unittest.TestCase):
    """Task 14 (Task 13 review, finding F2): the
    `.superpowers/` conditioning judged an untracked entry by
    its NAME, and the residue drop judged by the name rules of
    _path_binds_under_residue — but the fs binding attests a
    symlink by its TARGET STRING wherever it sits (see
    _fs_tree_digest and _fs_residue_entries), so a link's
    executed content is independent of its name and both
    drops waved untracked symlinks through: an untracked
    symlink under `.superpowers/` with a bookkeeping name,
    and a symlink under a residue name at a path the name
    rules exclude (a tool-state name, a non-bind name under
    .git). Git-mode seals were blind even to RETARGETING such
    a link — the one event the symlink contract promises
    always registers (the fs control of the review's fixture
    went STALE on retarget). The drops now judge (entry
    type, name): an untracked symlink entry is dropped by
    neither — it counts as dirty until committed, when
    ls-tree binds its target string exactly as it binds code.
    Non-symlink bookkeeping is unchanged (see
    SuperpowersCleanlinessTests).

    The residue-side audit also checked `.git` itself: no
    instance exists there to close — `git status` enumerates
    NOTHING beneath a `.git` directory component (plain file,
    symlink, any depth; verified against git directly), so
    no path under a residue `.git` ever reaches either drop,
    and such content can take effect only through bound code
    loading it by explicit path, the family the docs already
    disclose for the .git remainder. The residue instances
    that DO reach the gate are the cache names', where git
    enumerates normally; they are closed here."""

    def _repo(self, root: Path) -> None:
        git(root, "init", "-q", "-b", "main")
        write(root, "Makefile", "test:\n\ttrue\n")
        git(root, "add", "Makefile")
        git(
            root,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture",
        )

    def test_untracked_symlink_file_under_superpowers_is_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            outside = base / "outside"
            write(outside, "helper.py", "VALUE = 'good'\n")
            self._repo(root)
            (root / ".superpowers").mkdir()
            # A bookkeeping NAME: the name-only conditioning
            # waved this entry through at the parent.
            os.symlink(outside / "helper.py", root / ".superpowers" / "data.txt")
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_untracked_symlinked_dir_under_superpowers_is_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(base / "outside", "helper.py", "VALUE = 'good'\n")
            self._repo(root)
            (root / ".superpowers").mkdir()
            os.symlink(base / "outside", root / ".superpowers" / "x")
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_untracked_symlink_at_tool_state_name_is_dirty(self):
        # The residue-side instance of the same blindness:
        # a symlink AT the lastfailed path is dropped by the
        # name rules (tool state does not bind), but the fs
        # binding attests every symlink under a residue name
        # by its target string — retargeting it post-seal
        # moves the fs digest, so parity counts it dirty
        # until committed. The regular file at the same path
        # is the tool's own state and still waves through.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            self._repo(root)
            receipts = root / "r.jsonl"
            write(
                root,
                ".pytest_cache/v/cache/lastfailed",
                '{"test_ok.py::test_ok": true}',
            )
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            target = write(base, "planted.json", "{}\n")
            link = root / ".pytest_cache" / "v" / "cache" / "lastfailed"
            link.unlink()
            os.symlink(target, link)
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_untracked_symlink_at_pyc_name_is_dirty(self):
        # The __pycache__ instance of the residue blindness:
        # a symlink wearing a .pyc name is the tool's own
        # state by the name rules (dropped at the parent),
        # but the fs binding attests it by target string
        # like every symlink under a residue name.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            self._repo(root)
            target = write(base / "outside", "blob.bin", "bytes\n")
            cache = root / "pkg" / "__pycache__"
            cache.mkdir(parents=True)
            os.symlink(target, cache / "helper.cpython-312.pyc")
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_symlinked_superpowers_dir_end_to_end(self):
        # The review's F2 fixture: a Makefile leg whose
        # recipe runs a committed script importing a helper
        # THROUGH an untracked symlinked .superpowers/x.
        # At the parent the tree sealed (rc 0), the audit
        # stayed PASS after the target's content mutated,
        # and stayed PASS after the link was RETARGETED to
        # a different directory with identical content —
        # while the fs control went STALE on the retarget.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(base / "outside1", "helper.py", "VALUE = 'good'\n")
            write(base / "outside2", "helper.py", "VALUE = 'good'\n")
            write(
                root,
                "Makefile",
                "test:\n\tpython3 check_import.py\n",
            )
            write(
                root,
                "check_import.py",
                "import sys\n"
                "sys.path.insert(0, '.superpowers/x')\n"
                "import helper\n"
                "assert helper.VALUE == 'good'\n",
            )
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "Makefile", "check_import.py")
            git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "fixture",
            )
            (root / ".superpowers").mkdir()
            link = root / ".superpowers" / "x"
            os.symlink(base / "outside1", link)
            receipts = root / "r.jsonl"
            # Untracked link: the tree is dirty, nothing seals.
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)
            # Commit the link: ls-tree binds its target
            # string, and the tree seals.
            git(root, "add", ".superpowers/x")
            git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "link",
            )
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)
            # Retarget the committed link at an identical-
            # content directory: the working tree no longer
            # matches the bound target string, so the audit
            # reports the tree dirty — the registration the
            # fs control showed and the parent missed.
            link.unlink()
            os.symlink(base / "outside2", link)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: DIRTY", proc.stdout)


class CacheSelectionBindingTests(unittest.TestCase):
    """Task 13 (paperthin validation 4, breach B-B), git-mode
    instance (B-B3): the bound files are committed, the
    lastfailed plant is untracked tool state the cleanliness
    gate drops — pre-fix the tree sealed a subset PASS in git
    mode exactly as in fs mode. The steering gate refuses the
    leg at discovery (see CacheSelectionGateTests in
    test_mechanical_verify.py for the gate matrix and the
    fs-mode instance), so nothing seals here either."""

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_last_failed_subset_cannot_seal_in_git_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pytest.ini",
                "[pytest]\naddopts = --last-failed\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            write(
                root,
                "test_bad.py",
                "def test_bad():\n    assert False\n",
            )
            git(root, "init", "-q", "-b", "main")
            git(root, "add", "pytest.ini", "test_ok.py", "test_bad.py")
            git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "fixture",
            )
            write(
                root,
                ".pytest_cache/v/cache/lastfailed",
                '{"test_ok.py::test_ok": true}',
            )
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(
                proc.returncode, 2, proc.stdout + proc.stderr
            )
            self.assertIn(
                "no verification commands discovered", proc.stdout
            )
            self.assertFalse(receipts.exists())


if __name__ == "__main__":
    unittest.main()
