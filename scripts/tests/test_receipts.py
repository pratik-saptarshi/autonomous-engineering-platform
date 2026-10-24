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
            # One command receipt plus the run-completion record.
            self.assertEqual(len(lines), 2)
            self.assertNotIn("MARKER-OUTPUT", lines[0])
            receipt = json.loads(lines[0])
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
            # Two command receipts plus the run-completion record.
            self.assertEqual(len(parsed), 3)
            self.assertEqual(
                [r["command_id"] for r in parsed[:2]],
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
            first = json.loads(lines[0])
            original = first["stdout_sha256"]
            flipped = ("a" if original[0] != "a" else "b") + original[1:]
            first["stdout_sha256"] = flipped
            lines[0] = json.dumps(first)
            receipts.write_text("\n".join(lines) + "\n", encoding="utf-8")
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("RECEIPTS: chain broken at line 1", proc.stdout)

    def test_check_receipts_detects_deleted_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\ttrue\n")
            receipts = root / "r.jsonl"
            for task in ("1", "2", "3"):
                proc = verify(root, task, receipts)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            lines = receipts.read_text(encoding="utf-8").splitlines()
            # Three runs, each one command receipt + completion record.
            self.assertEqual(len(lines), 6)
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
            self.assertEqual(len(parsed), 3)
            completion = parsed[-1]
            self.assertEqual(completion["kind"], "run-complete")
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


if __name__ == "__main__":
    unittest.main()
