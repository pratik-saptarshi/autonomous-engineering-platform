import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
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
            write(root, "__pycache__/c.txt", "cache\n")
            receipts = write(root, "r.jsonl", "")
            (root / "link.txt").symlink_to("a.txt")
            binding = mechanical_verify.tree_binding(
                root, receipts_path=receipts
            )
            self.assertEqual(binding["mode"], "fs")
            self.assertIsNone(binding["head"])
            # Excluded content never moves the digest.
            write(root, "__pycache__/c.txt", "changed\n")
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


if __name__ == "__main__":
    unittest.main()
