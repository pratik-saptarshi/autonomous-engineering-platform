import contextlib
import hashlib
import io
import json
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


def check(receipts: Path, task: str) -> subprocess.CompletedProcess:
    return run_cli(
        "check-receipts", "--receipts", str(receipts), "--task", task
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
            receipts = Path(tmp) / "r.jsonl"
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
            append_receipt(receipts, "1", result)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = check_receipts(receipts, "1")
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
            receipts = Path(tmp) / "r.jsonl"
            mechanical_verify.append_run_start(receipts, "1", "run-a")
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
            receipts = Path(tmp) / "r.jsonl"
            for run_id in ("run-a", "run-b"):
                mechanical_verify.append_run_start(receipts, "1", run_id)
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
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "r.jsonl"
            write(root, "Makefile", "test:\n\ttrue\n")
            proc = verify(root, "A", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            write(root, "Makefile", "test:\n\tfalse\n")
            proc = verify(root, "B", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            proc = check(receipts, "A")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn(
                "RECEIPTS: PASS task A: 1 receipts, chain valid", proc.stdout
            )
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
            root = Path(tmp)
            receipts = root / "r.jsonl"
            write(root, "test_ok.py", MIXED_OK)
            write(
                root,
                "test_good.py",
                "from pathlib import Path\n\n\n"
                "def test_good():\n"
                "    Path('pytest-side.ran').write_text('ran')\n",
            )
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            # The plain pytest function demonstrably executed.
            self.assertTrue((root / "pytest-side.ran").is_file())
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


if __name__ == "__main__":
    unittest.main()
