import contextlib
import hashlib
import io
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
import zlib
from unittest import mock
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


def forge_index_entry(root: Path, name: str, blob_sha_hex: str) -> None:
    """Rewrite the index entry for `name` in place at the byte
    level (Task 16 review, finding F2): the entry keeps its name
    and mode but carries `blob_sha_hex` as its blob and the
    worktree file's GENUINE stat (ctime/mtime to the nanosecond,
    dev, ino, uid, gid, size), extensions stripped, trailer
    checksum recomputed — the strongest lie `git status`'s stat
    cache can be told, indistinguishable from a genuine entry
    without a content read. Index versions 2/3 only (the fixture
    repos' default)."""
    import struct

    index_path = root / ".git" / "index"
    data = index_path.read_bytes()
    assert data[:4] == b"DIRC", data[:4]
    version, count = struct.unpack(">II", data[4:12])
    assert version in (2, 3), version
    st = os.stat(root / name)
    stat_fields = [
        st.st_ctime_ns // 1_000_000_000,
        st.st_ctime_ns % 1_000_000_000,
        st.st_mtime_ns // 1_000_000_000,
        st.st_mtime_ns % 1_000_000_000,
        st.st_dev & 0xFFFFFFFF,
        st.st_ino & 0xFFFFFFFF,
        None,  # mode: keep the entry's own
        st.st_uid & 0xFFFFFFFF,
        st.st_gid & 0xFFFFFFFF,
        st.st_size & 0xFFFFFFFF,
    ]
    out = bytearray(data[:12])
    pos = 12
    replaced = False
    for _ in range(count):
        start = pos
        fixed = data[pos : pos + 62]
        fields = list(struct.unpack(">10I", fixed[:40]))
        flags = struct.unpack(">H", fixed[60:62])[0]
        fixed_len = 62
        if flags & 0x4000:  # extended flags word (v3, or v2 bit set)
            fixed_len = 64
        name_len = flags & 0x0FFF
        raw_name = data[pos + fixed_len : pos + fixed_len + 4096]
        if name_len < 0xFFF:
            entry_name = raw_name[:name_len]
        else:
            entry_name = raw_name.split(b"\0", 1)[0]
        entry_total = (fixed_len + len(entry_name) + 8) // 8 * 8
        entry = bytearray(data[start : start + entry_total])
        if entry_name.decode("utf-8", "surrogateescape") == name:
            for i, value in enumerate(stat_fields):
                if value is None:
                    value = fields[i]
                struct.pack_into(">I", entry, i * 4, value)
            entry[40:60] = bytes.fromhex(blob_sha_hex)
            replaced = True
        out += entry
        pos = start + entry_total
    assert replaced, f"no index entry for {name}"
    out += hashlib.sha1(bytes(out)).digest()
    index_path.write_bytes(bytes(out))


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


class GitInstrumentPinTests(unittest.TestCase):
    """Task 16 (paperthin validation 6, breach B-A): the verifier's
    git calls are borrowed instruments, and repo-local git config
    travels with a filesystem-delivered checkout — it is unbound
    state delivered with the artifact under test, not operator
    environment. A primed core.fsmonitor helper answers git
    status's fsmonitor query with a steady token and an empty
    change list, so a modified tracked file is invisible to
    tree_clean and the seal attests HEAD's tree while the
    worktree's file executes. The same file steers the answer
    through sibling keys (an outside core.worktree redirects
    status to another tree entirely; an outside
    core.attributesFile selecting a constant clean filter masks
    a same-size modification; core.excludesFile hides untracked
    code; core.fileMode=false masks a mode change), and the
    index itself carries mask bits (skip-worktree,
    assume-unchanged) that make status report modified files as
    clean BY DESIGN. _git therefore carries command-line pins —
    applied after every config file, include chains and the
    worktree config included — and tree_clean treats a tree
    carrying either index mask bit as not clean.
    """

    def _fsmonitor_repo(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp) / "repo"
        root.mkdir()
        init_git_repo(root)
        commit_file(root, "tracked.py", 'VALUE = "good"\n', "add tracked")
        helper = write(
            root, ".git/fsm-helper", "#!/bin/sh\nprintf 'tok-steady\\0'\n"
        )
        helper.chmod(0o755)
        return root, helper

    def _prime_fsmonitor(self, root: Path) -> None:
        # Two ordinary git invocations on the clean tree, as a
        # real checkout's life supplies: the first records the
        # helper's token in the index, the second round-trips it.
        git(root, "status", "--porcelain")
        git(root, "status", "--porcelain")

    def test_fsmonitor_helper_cannot_mask_tracked_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, helper = self._fsmonitor_repo(tmp)
            git(root, "config", "core.fsmonitor", str(helper))
            self._prime_fsmonitor(root)
            write(root, "tracked.py", 'VALUE = "evil"\n')
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)

    def test_fsmonitor_via_include_chain_is_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, helper = self._fsmonitor_repo(tmp)
            outside = write(
                Path(tmp),
                "included-config",
                f"[core]\n\tfsmonitor = {helper}\n",
            )
            git(root, "config", "include.path", str(outside))
            self._prime_fsmonitor(root)
            write(root, "tracked.py", 'VALUE = "evil"\n')
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_index_mask_bits_count_as_dirty(self):
        for flag in ("--skip-worktree", "--assume-unchanged"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_git_repo(root)
                commit_file(
                    root, "tracked.py", 'VALUE = "good"\n', "add tracked"
                )
                git(root, "update-index", flag, "tracked.py")
                receipts = root / "r.jsonl"
                # The bit alone disqualifies: it asks git not to
                # look at this file's worktree state at all.
                self.assertFalse(mechanical_verify.tree_clean(root, receipts))
                write(root, "tracked.py", 'VALUE = "evil"\n')
                self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_core_worktree_cannot_redirect_the_cleanliness_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            init_git_repo(root)
            commit_file(root, "tracked.py", 'VALUE = "good"\n', "add tracked")
            elsewhere = Path(tmp) / "elsewhere"
            elsewhere.mkdir()
            write(elsewhere, "Makefile", "test:\n\ttrue\n")
            write(elsewhere, "tracked.py", 'VALUE = "good"\n')
            git(root, "config", "core.worktree", str(elsewhere))
            write(root, "tracked.py", 'VALUE = "evil"\n')
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_repo_local_excludes_file_cannot_hide_untracked_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            init_git_repo(root)
            outside = write(Path(tmp), "outside-excludes", "helper.py\n")
            git(root, "config", "core.excludesFile", str(outside))
            write(root, "helper.py", 'VALUE = "ok"\n')
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_repo_local_attributes_file_cannot_mask_tracked_modification(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            init_git_repo(root)
            commit_file(root, "tracked.txt", "good\n", "add tracked")
            outside = write(
                Path(tmp), "outside-attrs", "tracked.txt filter=mask\n"
            )
            git(root, "config", "core.attributesFile", str(outside))
            git(root, "config", "filter.mask.clean", "printf 'good\\n'")
            git(root, "config", "filter.mask.smudge", "cat")
            write(root, "tracked.txt", "evil\n")
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_repo_local_filemode_off_cannot_mask_mode_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            commit_file(root, "run.sh", "#!/bin/sh\ntrue\n", "add script")
            git(root, "config", "core.fileMode", "false")
            (root / "run.sh").chmod(0o755)
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_untracked_cache_does_not_hide_untracked_code(self):
        # Adjudication pin (validation 6 §1): the untracked cache
        # accelerates the untracked half of status's answer and
        # is pinned off like fsmonitor; with it enabled and
        # primed, an untracked code file still counts as dirty.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            git(root, "config", "core.untrackedCache", "true")
            git(root, "update-index", "--untracked-cache")
            git(root, "status", "--porcelain")
            write(root, "helper.py", 'VALUE = "ok"\n')
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_same_size_modification_with_forged_stat_is_dirty(self):
        # Adjudication pin (validation 6, Task 16 brief): a
        # same-size edit whose mtime is forged back to the index's
        # recorded value is still caught — git's racy-stat
        # handling falls back to a content comparison, under the
        # default checkStat the pin restores.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            commit_file(root, "tracked.py", "good\n", "add tracked")
            path = root / "tracked.py"
            st = os.stat(path)
            write(root, "tracked.py", "evil\n")
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))

    def test_git_invocations_carry_config_pins(self):
        captured: dict = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return subprocess.CompletedProcess(argv, 0, b"", b"")

        with mock.patch.object(mechanical_verify.subprocess, "run", fake_run):
            mechanical_verify._git(
                Path("/nonexistent-root"), "status", "--porcelain"
            )
        argv = captured["argv"]
        self.assertLess(argv.index("-c"), argv.index("status"))
        pins = {
            argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "-c"
        }
        self.assertTrue(
            {
                "core.fsmonitor=false",
                "core.untrackedCache=false",
                "core.hooksPath=" + os.devnull,
                "core.attributesFile=" + os.devnull,
                "core.excludesFile=" + os.devnull,
                "core.fileMode=true",
                "status.showUntrackedFiles=all",
            }
            <= pins
        )

    def test_git_invocations_disable_replace_objects(self):
        # Task 17 (Task 16 review, finding F2's family): replace
        # refs are delivered .git state too — a planted
        # refs/replace/<sha> makes ls-tree/cat-file/status read
        # substituted objects, so the seal could attest a tree
        # that is not HEAD's. Every _git invocation carries the
        # opt-out in its environment.
        captured: dict = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["env"] = kwargs.get("env")
            return subprocess.CompletedProcess(argv, 0, b"", b"")

        with mock.patch.object(mechanical_verify.subprocess, "run", fake_run):
            mechanical_verify._git(
                Path("/nonexistent-root"), "status", "--porcelain"
            )
        env = captured["env"] or {}
        self.assertEqual(env.get("GIT_NO_REPLACE_OBJECTS"), "1")

    def test_forged_index_stat_cache_counts_as_dirty(self):
        # Task 17 (Task 16 review, finding F2): `git status`
        # trusts its index stat cache — an entry whose stat
        # matches the worktree file is believed without a
        # content read. A byte-forged entry (HEAD's blob SHA
        # over the modified file's genuine stat) therefore
        # makes a modified tracked file invisible to every pin
        # Task 16 set: there is no -c key for "distrust the
        # stat cache". Git-mode tracked cleanliness is
        # content-exact instead: worktree bytes are compared
        # against HEAD's blob bytes directly.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            commit_file(root, "tracked.py", 'VALUE = "good"\n', "add tracked")
            git(root, "status", "--porcelain")  # prime a genuine index
            head_blob = git(root, "rev-parse", "HEAD:tracked.py").stdout.strip()
            write(root, "tracked.py", 'VALUE = "evil"\n')
            # Age the mtime well behind the index's own write
            # time: an entry whose recorded mtime reaches the
            # index file's mtime is racy and git content-checks
            # it regardless of the stat cache, which would make
            # the forge below fail for a timing reason, not a
            # mechanism reason. (ctime cannot be aged; the forge
            # copies it genuinely from stat after this utime.)
            aged = 1_700_000_000_000_000_000
            os.utime(root / "tracked.py", ns=(aged, aged))
            forge_index_entry(root, "tracked.py", head_blob)
            # The lie holds against plain git: status is empty.
            self.assertEqual(git(root, "status", "--porcelain").stdout, "")
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)

    def test_primed_genuine_index_seals_and_audits(self):
        # The content-exact check must not false-dirty ordinary
        # checkouts: a genuine index (stat cache written by git
        # itself), an executable file, a tracked symlink, and a
        # file in a subdirectory all seal and audit clean.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            commit_file(root, "tracked.py", 'VALUE = "good"\n', "add tracked")
            commit_file(root, "sub/inner.py", 'VALUE = "in"\n', "add inner")
            script = write(root, "run.sh", "#!/bin/sh\ntrue\n")
            script.chmod(0o755)
            git(root, "add", "run.sh")
            (root / "link.py").symlink_to("tracked.py")
            git(root, "add", "link.py")
            git(
                root,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "add script and link",
            )
            git(root, "status", "--porcelain")  # prime the genuine index
            receipts = root / "r.jsonl"
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def test_core_bare_checkout_is_refused(self):
        # Task 17 (Task 16 review, finding F1): the Task 16
        # report adjudicated core.bare as "fails closed" — but
        # the verifier's restated argv (--git-dir/--work-tree)
        # neutralizes bareness, so an honest checkout carrying
        # core.bare=true sealed. The behaviour now matches the
        # claim by refusal instead: a bare declaration in a
        # delivered worktree checkout is anomalous, and git
        # mode refuses it with the reason surfaced, in both the
        # honest and the modified arm.
        for modified in (False, True):
            with self.subTest(modified=modified), \
                    tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_git_repo(root)
                commit_file(
                    root, "tracked.py", 'VALUE = "good"\n', "add tracked"
                )
                git(root, "config", "core.bare", "true")
                if modified:
                    write(root, "tracked.py", 'VALUE = "evil"\n')
                reason = mechanical_verify._repo_local_config_refusal(root)
                self.assertIsNotNone(reason)
                self.assertIn("core.bare", reason)
                receipts = root / "r.jsonl"
                self.assertFalse(
                    mechanical_verify.tree_clean(root, receipts)
                )
                proc = verify(root, "1", receipts)
                self.assertEqual(
                    proc.returncode, 1, proc.stdout + proc.stderr
                )
                self.assertIn("core.bare", proc.stdout)

    def test_repo_local_filter_driver_config_is_refused(self):
        # Task 17 (finding F2's closure condition): filter
        # drivers are program-naming config delivered with the
        # checkout — the fsmonitor kind. A checkout whose
        # repo-local (or worktree) config defines any
        # filter.*.clean/smudge/process key is refused in git
        # mode even when no attribute selects the driver and
        # the tree is otherwise honest: content-exact
        # cleanliness compares raw bytes precisely because no
        # repo-named program may stand between the worktree
        # and the blob.
        for scope in ("local", "worktree"):
            with self.subTest(scope=scope), \
                    tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_git_repo(root)
                commit_file(
                    root, "tracked.py", 'VALUE = "good"\n', "add tracked"
                )
                if scope == "worktree":
                    git(root, "config", "extensions.worktreeConfig", "true")
                    git(
                        root, "config", "--worktree",
                        "filter.wt.smudge", "cat",
                    )
                else:
                    git(root, "config", "filter.mask.clean", "cat")
                reason = mechanical_verify._repo_local_config_refusal(root)
                self.assertIsNotNone(reason)
                self.assertIn("filter.", reason)
                receipts = root / "r.jsonl"
                self.assertFalse(
                    mechanical_verify.tree_clean(root, receipts)
                )
                proc = verify(root, "1", receipts)
                self.assertEqual(
                    proc.returncode, 1, proc.stdout + proc.stderr
                )
                self.assertIn("filter.", proc.stdout)

    def test_replace_ref_cannot_steer_binding_or_cleanliness(self):
        # Task 17 (finding F2's family): a planted replace ref
        # substitutes objects for every unpinned reader. With
        # replace objects disabled on the verifier's git calls,
        # the binding and the cleanliness answer describe the
        # real HEAD while the ref sits in the checkout.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            commit_file(root, "tracked.py", 'VALUE = "good"\n', "add good")
            commit_a = git(root, "rev-parse", "HEAD").stdout.strip()
            commit_file(root, "tracked.py", 'VALUE = "evil"\n', "add evil")
            commit_b = git(root, "rev-parse", "HEAD").stdout.strip()
            evil_blob = git(
                root, "rev-parse", f"{commit_b}:tracked.py"
            ).stdout.strip()
            git(root, "reset", "-q", "--hard", commit_a)
            digest_before = mechanical_verify.tree_binding(root)[
                "tree_digest"
            ]
            git(root, "replace", commit_a, commit_b)
            # Sanity: plain git is steered by the plant.
            self.assertIn(evil_blob, git(root, "ls-tree", "HEAD").stdout)
            self.assertEqual(
                mechanical_verify.tree_binding(root)["tree_digest"],
                digest_before,
            )
            receipts = root / "r.jsonl"
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)


def _plant_over_readonly(path: Path, data: bytes) -> None:
    """Write *data* over the file at *path*, adding owner-write
    first when the file already exists: git creates object and
    pack files read-only, so an unprivileged run cannot
    overwrite one in place — a root run masks that, which is
    how these plants passed locally while erroring in CI
    (run 40566947790, PermissionError on every plant)."""
    if path.exists():
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
    path.write_bytes(data)


def poison_loose_object(root: Path, sha: str, payload: bytes) -> None:
    """Replace the loose object at `sha` with a zlib payload of
    *payload* framed as a blob — the delivered-store lie of
    paperthin validation 7, breach B-A: the bytes sit at the
    genuine object's path, so every read-path git command
    serves them under the genuine SHA."""
    obj = root / ".git" / "objects" / sha[:2] / sha[2:]
    obj.parent.mkdir(parents=True, exist_ok=True)
    framed = b"blob %d\x00" % len(payload) + payload
    _plant_over_readonly(obj, zlib.compress(framed))


def plant_size_lying_object(
    root: Path, sha: str, declared: int, payload: bytes
) -> None:
    """Replace the loose object at `sha` with a zlib stream
    whose header declares `declared` bytes over a `payload` of
    a different length (Task 18 review, finding F1). With
    declared > len(payload), `git cat-file --batch` frames the
    response with the declared size, serves only the real
    bytes, and waits for the next request. With declared <
    len(payload) the frame desyncs and the pass refuses on
    its framing check."""
    obj = root / ".git" / "objects" / sha[:2] / sha[2:]
    obj.parent.mkdir(parents=True, exist_ok=True)
    _plant_over_readonly(
        obj, zlib.compress(b"blob %d\x00" % declared + payload)
    )


def swap_pack_idx_entries(root: Path, sha_a: str, sha_b: str) -> None:
    """Swap two blobs' offset+CRC entries in the pack index
    (validation 7's packed form of B-A): cat-file then serves
    each blob's payload under the other's SHA, CRC-consistent,
    and only fsck would notice."""
    pack_dir = root / ".git" / "objects" / "pack"
    idx_path = next(pack_dir.glob("*.idx"))
    data = bytearray(idx_path.read_bytes())
    assert data[:4] == b"\xfftOc", data[:4]
    (version,) = struct.unpack(">I", data[4:8])
    assert version == 2, version
    fanout = struct.unpack(">256I", data[8 : 8 + 1024])
    count = fanout[255]
    sha_off = 8 + 1024
    crc_off = sha_off + 20 * count
    off_off = crc_off + 4 * count
    shas = [
        bytes(data[sha_off + 20 * i : sha_off + 20 * (i + 1)])
        for i in range(count)
    ]
    ia = shas.index(bytes.fromhex(sha_a))
    ib = shas.index(bytes.fromhex(sha_b))
    for base in (crc_off, off_off):
        entry_a = bytes(data[base + 4 * ia : base + 4 * ia + 4])
        entry_b = bytes(data[base + 4 * ib : base + 4 * ib + 4])
        data[base + 4 * ia : base + 4 * ia + 4] = entry_b
        data[base + 4 * ib : base + 4 * ib + 4] = entry_a
    data[-20:] = hashlib.sha1(bytes(data[:-20])).digest()
    _plant_over_readonly(idx_path, bytes(data))


class ObjectStoreIntegrityTests(unittest.TestCase):
    """Task 18 (paperthin validation 7, breach B-A): the
    content-exact pass believed the object store by name. Git
    streams blob payloads without hashing them on the read
    path (loose, packed, alternates alike — only fsck
    checks), so a poisoned blob served under HEAD's blob SHA,
    composed with Task 17's forged index, made the pass
    compare evil worktree bytes against evil "HEAD" bytes and
    call it clean. Every payload is now hashed inside the
    pass, framed under the repo's own object format, and must
    equal its claimed SHA before it is compared; a mismatch
    is named as an object-store integrity failure in the
    gate's message, on the verify path and the audit path
    alike."""

    AGED_NS = 1_700_000_000_000_000_000

    def _repo(self, tmp: str) -> tuple[Path, str]:
        root = Path(tmp) / "repo"
        root.mkdir()
        init_git_repo(root)
        commit_file(
            root, "test_ok.py", "def test_ok():\n    assert True\n",
            "add test",
        )
        sha = git(root, "rev-parse", "HEAD:test_ok.py").stdout.strip()
        return root, sha

    def _forge_evil(
        self, root: Path, evil: bytes, sha: str
    ) -> None:
        (root / "test_ok.py").write_bytes(evil)
        os.utime(root / "test_ok.py", ns=(self.AGED_NS, self.AGED_NS))
        forge_index_entry(root, "test_ok.py", sha)
        status = git(root, "status", "--porcelain").stdout
        tracked = [
            line for line in status.splitlines()
            if not line.startswith("??")
        ]
        self.assertEqual(tracked, [])

    def test_loose_poison_with_forged_index_is_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo(tmp)
            evil = b"def test_ok():\n    assert False\n"
            poison_loose_object(root, sha, evil)
            # The lie holds against plain git first.
            self.assertEqual(
                git(root, "cat-file", "-p", sha).stdout.encode(), evil
            )
            self._forge_evil(root, evil, sha)
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            detail = mechanical_verify._object_store_failure_detail()
            self.assertIsNotNone(detail)
            self.assertIn("object store integrity failure", detail)
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("object store integrity failure", proc.stdout)

    @unittest.skipUnless(
        _path_pytest_available(), "python3 on PATH has no pytest module"
    )
    def test_post_seal_poison_flips_audit_to_dirty(self):
        # The validator's audit-path arm: honest seal and audit,
        # THEN poison + forge + modify — the audit must stop
        # blessing the segment and name the store.
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo(tmp)
            outside = Path(tmp) / "outside"
            outside.mkdir()
            write(outside, "helper.py", 'VALUE = "evil"\n')
            sentinel = Path(tmp) / "sentinel"
            evil = (
                "import sys\n"
                "from pathlib import Path\n"
                f"sys.path.insert(0, {str(outside)!r})\n"
                "import helper\n\n\n"
                "def test_ok():\n"
                "    assert helper.VALUE == 'evil'\n"
                f"    Path({str(sentinel)!r}).write_text('ran')\n"
            ).encode()
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            poison_loose_object(root, sha, evil)
            self._forge_evil(root, evil, sha)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: DIRTY", proc.stdout)
            self.assertIn("object store integrity failure", proc.stdout)

    def test_packed_poison_with_forged_index_is_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo(tmp)
            evil = b"def test_ok():\n    assert False\n"
            # The donor blob genuinely holds the evil bytes; it
            # is committed then removed so at HEAD it is not a
            # tracked path (the swap poisons its entry in the
            # other direction, and a tracked donor would be
            # compared too).
            commit_file(root, "donor.py", evil.decode(), "add donor")
            donor_sha = git(
                root, "rev-parse", "HEAD:donor.py"
            ).stdout.strip()
            git(root, "rm", "-q", "donor.py")
            git(
                root,
                "-c", "user.name=Fixture",
                "-c", "user.email=fixture@example.invalid",
                "commit", "-q", "-m", "remove donor",
            )
            git(root, "repack", "-a", "-d", "-q")
            git(root, "prune")
            loose = root / ".git" / "objects" / sha[:2] / sha[2:]
            self.assertFalse(loose.exists())
            swap_pack_idx_entries(root, sha, donor_sha)
            self.assertEqual(
                git(root, "cat-file", "-p", sha).stdout.encode(), evil
            )
            self._forge_evil(root, evil, sha)
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            detail = mechanical_verify._object_store_failure_detail()
            self.assertIsNotNone(detail)
            self.assertIn("object store integrity failure", detail)

    def test_alternates_poison_with_forged_index_is_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo(tmp)
            evil = b"def test_ok():\n    assert False\n"
            donor = Path(tmp) / "donor"
            donor.mkdir()
            git(donor, "init", "-q", "-b", "main")
            commit_file(donor, "donor.py", evil.decode(), "donor")
            poison_loose_object(donor, sha, evil)
            (root / ".git" / "objects" / sha[:2] / sha[2:]).unlink()
            alt = root / ".git" / "objects" / "info" / "alternates"
            alt.parent.mkdir(parents=True, exist_ok=True)
            alt.write_text(str(donor / ".git" / "objects") + "\n")
            self.assertEqual(
                git(root, "cat-file", "-p", sha).stdout.encode(), evil
            )
            self._forge_evil(root, evil, sha)
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            detail = mechanical_verify._object_store_failure_detail()
            self.assertIsNotNone(detail)
            self.assertIn("object store integrity failure", detail)

    def test_sha256_repo_payloads_verified_with_sha256(self):
        # The framing hash is the repo's own format: a sha256
        # repo's payloads verify with sha256, not an opaque
        # sha1 refusal. Function-level, because the index forge
        # helper speaks the sha1 entry layout.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            git(
                root, "init", "-q", "-b", "main",
                "--object-format=sha256",
            )
            commit_file(root, "tracked.py", 'VALUE = "good"\n', "tracked")
            sha = git(
                root, "rev-parse", "HEAD:tracked.py"
            ).stdout.strip()
            self.assertEqual(len(sha), 64)
            self.assertTrue(
                mechanical_verify._tracked_content_matches_head(
                    root
                )
            )
            evil = b'VALUE = "evil"\n'
            (root / "tracked.py").write_bytes(evil)
            # Honest store: the modification is caught.
            self.assertFalse(
                mechanical_verify._tracked_content_matches_head(
                    root
                )
            )
            # Poisoned store: the same comparison believed the
            # served bytes before this task.
            poison_loose_object(root, sha, evil)
            self.assertEqual(
                git(root, "cat-file", "-p", sha).stdout.encode(), evil
            )
            self.assertFalse(
                mechanical_verify._tracked_content_matches_head(
                    root
                )
            )
            detail = mechanical_verify._object_store_failure_detail()
            self.assertIsNotNone(detail)
            self.assertIn("sha256", detail)

    def test_large_blob_honest_store_seals_and_audits(self):
        # Payload verification must accept genuine objects,
        # large ones included: a 3 MiB blob seals and audits
        # exactly like a small one.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            (root / "blob.bin").write_bytes(
                bytes(range(256)) * (3 * 1024 * 1024 // 256)
            )
            git(root, "add", "blob.bin")
            git(
                root,
                "-c", "user.name=Fixture",
                "-c", "user.email=fixture@example.invalid",
                "commit", "-q", "-m", "add blob",
            )
            git(root, "status", "--porcelain")  # prime the index
            receipts = root / "r.jsonl"
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def test_git_invocations_disable_lazy_fetch_and_ext(self):
        # Task 18 (validation 7, breach B-B's environment and
        # pin layers): no verifier git call ever fetches, and
        # the ext:: transport is pinned off on the argv.
        captured: dict = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["env"] = kwargs.get("env")
            return subprocess.CompletedProcess(argv, 0, b"", b"")

        with mock.patch.object(mechanical_verify.subprocess, "run", fake_run):
            mechanical_verify._git(
                Path("/nonexistent-root"), "status", "--porcelain"
            )
        env = captured["env"] or {}
        self.assertEqual(env.get("GIT_NO_LAZY_FETCH"), "1")
        argv = captured["argv"]
        pins = {
            argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "-c"
        }
        self.assertIn("protocol.ext.allow=never", pins)


class ObjectStoreStallTests(unittest.TestCase):
    """Task 19 (Task 18 review, finding F1): the content pass's
    batch reads are bounded by inactivity. A loose object whose
    header declares more bytes than its payload holds made
    `git cat-file --batch` frame the declared size, serve the
    short payload, and wait for the next request, while the
    pass's unbounded read waited for the remainder — the pass
    hung forever (killed at an external timeout, function level
    and CLI alike) where Task 18's contract promises a named
    object-store integrity failure. Every chunk of the batch
    stream is now awaited under an inactivity bound
    (_BatchReader): progress resets the clock, and silence
    records the same integrity failure, kills the batch, and
    refuses — at the verify gate and the audit gate alike."""

    PAYLOAD = b"SHORT"

    def _repo(self, tmp: str) -> tuple[Path, str]:
        root = Path(tmp) / "repo"
        root.mkdir()
        init_git_repo(root)
        commit_file(root, "data.txt", self.PAYLOAD.decode(), "add data")
        sha = git(root, "rev-parse", "HEAD:data.txt").stdout.strip()
        return root, sha

    def test_oversize_declaration_is_named_failure_not_hang(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo(tmp)
            plant_size_lying_object(root, sha, 999, self.PAYLOAD)
            receipts = root / "r.jsonl"
            # A 1s inactivity bound stands in for the shipped
            # 10s: what is pinned is the bound's semantics, not
            # its size.
            with mock.patch.object(
                mechanical_verify, "_BATCH_STALL_SECONDS", 1.0
            ):
                start = time.monotonic()
                self.assertFalse(
                    mechanical_verify.tree_clean(root, receipts)
                )
                elapsed = time.monotonic() - start
            # The refusal arrived via the bound — promptly,
            # orders of magnitude inside the external timeout
            # the pre-fix pass had to be killed at.
            self.assertLess(elapsed, 20)
            detail = mechanical_verify._object_store_failure_detail()
            self.assertIsNotNone(detail)
            self.assertIn("object store integrity failure", detail)
            self.assertIn("stalled incomplete", detail)

    def test_oversize_declaration_verify_refuses_named(self):
        # CLI arm at the shipped 10s bound: verify refuses with
        # the failure named rather than hanging.
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo(tmp)
            plant_size_lying_object(root, sha, 999, self.PAYLOAD)
            receipts = root / "r.jsonl"
            start = time.monotonic()
            proc = verify(root, "1", receipts)
            elapsed = time.monotonic() - start
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("object store integrity failure", proc.stdout)
            # The bound governed (not an instant error) and the
            # refusal was bounded (not a hang).
            self.assertGreater(elapsed, 5)
            self.assertLess(elapsed, 90)

    def test_oversize_post_seal_plant_flips_audit_to_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo(tmp)
            receipts = root / "r.jsonl"
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            plant_size_lying_object(root, sha, 999, self.PAYLOAD)
            start = time.monotonic()
            proc = check(receipts, "1")
            elapsed = time.monotonic() - start
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: DIRTY", proc.stdout)
            self.assertIn("object store integrity failure", proc.stdout)
            self.assertGreater(elapsed, 5)
            self.assertLess(elapsed, 90)

    def test_undersize_declaration_refuses_promptly(self):
        # The reverse lie refused via the framing check before
        # this task (declared 2, served 5: the trailer byte is
        # payload, not LF). Pin that it still refuses —
        # promptly, without waiting out any inactivity bound,
        # and without an integrity detail: the framing spoke,
        # not the payload hash.
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo(tmp)
            plant_size_lying_object(root, sha, 2, self.PAYLOAD)
            receipts = root / "r.jsonl"
            with mock.patch.object(
                mechanical_verify, "_BATCH_STALL_SECONDS", 5.0
            ):
                start = time.monotonic()
                self.assertFalse(
                    mechanical_verify.tree_clean(root, receipts)
                )
                elapsed = time.monotonic() - start
            self.assertLess(elapsed, 4)
            self.assertIsNone(
                mechanical_verify._object_store_failure_detail()
            )

    def test_batch_reader_slow_but_progressing_stream_completes(self):
        # Inactivity semantics: gaps below the bound, summing
        # past it, must not trip — progress resets the clock.
        # (Chunked git-level delivery cannot be staged — git
        # writes a small object's payload in one write — so
        # the reader is exercised directly over a pipe.)
        rfd, wfd = os.pipe()
        chunks = [b"ab", b"c\nde", b"f\n", b"ghi"]

        def writer() -> None:
            try:
                for chunk in chunks:
                    os.write(wfd, chunk)
                    time.sleep(0.3)
            finally:
                os.close(wfd)

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            reader = mechanical_verify._BatchReader(rfd)
            with mock.patch.object(
                mechanical_verify, "_BATCH_STALL_SECONDS", 1.0
            ):
                self.assertEqual(reader.read_line(), b"abc\n")
                self.assertEqual(reader.read_exactly(2), b"de")
                self.assertEqual(reader.read_line(), b"f\n")
                self.assertEqual(reader.read_exactly(3), b"ghi")
        finally:
            thread.join(timeout=10)
            os.close(rfd)

    def test_batch_reader_stalled_stream_raises(self):
        rfd, wfd = os.pipe()

        def writer() -> None:
            os.write(wfd, b"ab")
            time.sleep(2.0)
            os.close(wfd)

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            reader = mechanical_verify._BatchReader(rfd)
            with mock.patch.object(
                mechanical_verify, "_BATCH_STALL_SECONDS", 0.5
            ):
                start = time.monotonic()
                with self.assertRaises(mechanical_verify._BatchStalled):
                    reader.read_exactly(5)
                self.assertLess(time.monotonic() - start, 1.8)
        finally:
            thread.join(timeout=10)
            os.close(rfd)

    def test_batch_reader_eof_is_short_frame_not_stall(self):
        # A writer that simply goes away is EOF: reads return
        # None (the pass's framing failure), never _BatchStalled.
        rfd, wfd = os.pipe()
        os.write(wfd, b"ab")
        os.close(wfd)
        try:
            reader = mechanical_verify._BatchReader(rfd)
            self.assertIsNone(reader.read_exactly(5))
            self.assertIsNone(reader.read_line())
        finally:
            os.close(rfd)


class SubdirectoryRootTests(unittest.TestCase):
    """Task 21 (Codex P2 on PR #75): for a subdirectory root,
    `ls-tree` answers subtree-scoped with paths relative to
    the invocation directory, but the content-exact pass
    resolved them against the repository toplevel — a clean
    nested project failed tree_clean reading paths that do
    not exist. The instruments' scopes, probed with the
    verifier's own argv: status is whole-tree with
    toplevel-relative paths (it still contaminates a nested
    verdict from outside, unchanged); ls-files and ls-tree
    are subtree-scoped with root-relative paths. The pass now
    resolves ls-tree's paths against the root it invoked
    ls-tree from, matching the mask-bit check's scope and the
    binding digest's — the status half keeps its whole-tree
    judgement on top."""

    def _repo(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp) / "repo"
        root.mkdir()
        init_git_repo(root)
        commit_file(root, "top.py", 'VALUE = "top"\n', "add top")
        sub = root / "sub"
        write(sub, "Makefile", "test:\n\ttrue\n")
        write(sub, "test_x.py", "def test_x():\n    assert True\n")
        git(root, "add", "sub/Makefile", "sub/test_x.py")
        git(
            root,
            "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit",
            "-q",
            "-m", "add sub",
        )
        return root, sub

    def test_clean_subdirectory_root_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sub = self._repo(tmp)
            self.assertTrue(
                mechanical_verify._tracked_content_matches_head(sub)
            )
            receipts = sub / "r.jsonl"
            self.assertTrue(mechanical_verify.tree_clean(sub, receipts))

    def test_subdirectory_root_seals_and_audits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sub = self._repo(tmp)
            receipts = sub / "r.jsonl"
            proc = verify(sub, "1", receipts)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            proc = check(receipts, "1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("RECEIPTS: PASS", proc.stdout)

    def test_modified_inside_subdirectory_root_is_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sub = self._repo(tmp)
            write(sub, "test_x.py", 'VALUE = "evil"\n')
            receipts = sub / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(sub, receipts))
            proc = verify(sub, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("tree not clean at HEAD", proc.stdout)

    def test_outside_modification_contaminates_via_status_not_pass(self):
        # The pre-existing contract, pinned: the status half
        # judges the whole tree, so an outside modification
        # fails a nested root's tree_clean — but the content
        # pass itself scopes to the subtree it was invoked on
        # and still matches HEAD there.
        with tempfile.TemporaryDirectory() as tmp:
            root, sub = self._repo(tmp)
            write(root, "top.py", 'VALUE = "evil"\n')
            self.assertTrue(
                mechanical_verify._tracked_content_matches_head(sub)
            )
            receipts = sub / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(sub, receipts))

    def test_toplevel_root_of_nested_fixture_still_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sub = self._repo(tmp)
            receipts = root / "r.jsonl"
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))


class StreamingContentPassTests(unittest.TestCase):
    """Task 21 (Codex P2 on PR #75): the content pass buffered
    every blob whole — the batch payload, its bytes copy, and
    the worktree file's read_bytes — so a clean tree carrying
    one 48 MiB blob died with an uncaught MemoryError under a
    160 MiB address-space cap that satisfies the 512 MiB
    preflight's intent. Payload verification now streams:
    the framed hash and the comparison hash are fed chunk by
    chunk off the batch reader, and the worktree side hashes
    in chunks too, so the pass's peak memory is a small
    constant multiple of the 64 KiB chunk, independent of
    blob size. The capped arms run in a child process under
    RLIMIT_AS because the failure they guard against is the
    pass dying, not returning a verdict."""

    CAP_BYTES = 160 * 1024 * 1024
    BLOB_BYTES = 48 * 1024 * 1024
    GOOD = bytes(range(256)) * (BLOB_BYTES // 256)
    EVIL = bytes(range(255, -1, -1)) * (BLOB_BYTES // 256)
    AGED_NS = 1_700_000_000_000_000_000

    def _repo_with_big_blob(self, tmp: str) -> tuple[Path, str]:
        root = Path(tmp) / "repo"
        root.mkdir()
        init_git_repo(root)
        (root / "big.bin").write_bytes(self.GOOD)
        git(root, "add", "big.bin")
        git(
            root,
            "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit",
            "-q",
            "-m", "add big blob",
        )
        sha = git(root, "rev-parse", "HEAD:big.bin").stdout.strip()
        return root, sha

    def _capped_pass(self, root: Path) -> subprocess.CompletedProcess:
        script = (
            "import resource, sys\n"
            "from pathlib import Path\n"
            f"resource.setrlimit(resource.RLIMIT_AS, "
            f"({self.CAP_BYTES}, {self.CAP_BYTES}))\n"
            f"sys.path.insert(0, {str(SCRIPT.parent)!r})\n"
            "import mechanical_verify\n"
            "root = Path(sys.argv[1])\n"
            "clean = mechanical_verify.tree_clean(root, root / 'r.jsonl')\n"
            "print('clean:', clean)\n"
            "print('detail:', "
            "mechanical_verify._object_store_failure_detail())\n"
        )
        return subprocess.run(
            [sys.executable, "-c", script, str(root)],
            capture_output=True,
            text=True,
            timeout=300,
        )

    def test_clean_large_blob_passes_under_address_space_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._repo_with_big_blob(tmp)
            proc = self._capped_pass(root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("clean: True", proc.stdout)
            self.assertIn("detail: None", proc.stdout)

    def test_poisoned_large_blob_refused_under_address_space_cap(self):
        # Streaming must verify, not stream past: the poisoned
        # store (Task 18's plant at 48 MiB) still records the
        # named integrity failure under the same cap.
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo_with_big_blob(tmp)
            poison_loose_object(root, sha, self.EVIL)
            (root / "big.bin").write_bytes(self.EVIL)
            os.utime(
                root / "big.bin", ns=(self.AGED_NS, self.AGED_NS)
            )
            forge_index_entry(root, "big.bin", sha)
            status = git(root, "status", "--porcelain").stdout
            tracked = [
                line for line in status.splitlines()
                if not line.startswith("??")
            ]
            self.assertEqual(tracked, [])
            proc = self._capped_pass(root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("clean: False", proc.stdout)
            self.assertIn("object store integrity failure", proc.stdout)

    def test_chunk_boundary_payloads_compare_exactly(self):
        # Payloads straddling the 64 KiB chunk boundary compare
        # exactly: clean matches; a flipped byte in the first
        # or last chunk, a truncated file, and an extended file
        # all read dirty to a direct pass.
        size = 3 * 65536 + 123
        payload = bytes(range(256)) * (size // 256) + bytes(
            range(size % 256)
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            init_git_repo(root)
            (root / "blob.bin").write_bytes(payload)
            git(root, "add", "blob.bin")
            git(
                root,
                "-c", "user.name=Fixture",
                "-c", "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m", "add blob",
            )
            self.assertTrue(
                mechanical_verify._tracked_content_matches_head(root)
            )
            flipped_first = bytes([payload[0] ^ 0xFF]) + payload[1:]
            flipped_last = payload[:-1] + bytes([payload[-1] ^ 0xFF])
            for variant in (
                flipped_first,
                flipped_last,
                payload[:-1],
                payload + b"x",
            ):
                (root / "blob.bin").write_bytes(variant)
                self.assertFalse(
                    mechanical_verify._tracked_content_matches_head(
                        root
                    )
                )
            (root / "blob.bin").write_bytes(payload)
            self.assertTrue(
                mechanical_verify._tracked_content_matches_head(root)
            )

    def test_batch_reader_read_chunks_bounds_and_joins(self):
        payload = bytes(range(256)) * 800  # 204800 bytes
        rfd, wfd = os.pipe()

        def writer() -> None:
            view = memoryview(payload)
            while view:
                view = view[os.write(wfd, view):]
            os.close(wfd)

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            reader = mechanical_verify._BatchReader(rfd)
            chunks = list(reader.read_chunks(len(payload)))
            self.assertEqual(b"".join(chunks), payload)
            self.assertTrue(
                all(
                    len(c) <= mechanical_verify._BATCH_CHUNK_BYTES
                    for c in chunks
                )
            )
            self.assertGreater(len(chunks), 1)
        finally:
            thread.join(timeout=10)
            os.close(rfd)

    def test_batch_reader_read_chunks_eof_is_short_frame(self):
        rfd, wfd = os.pipe()
        os.write(wfd, b"ab")
        os.close(wfd)
        try:
            reader = mechanical_verify._BatchReader(rfd)
            with self.assertRaises(
                mechanical_verify._BatchShortFrame
            ):
                list(reader.read_chunks(5))
        finally:
            os.close(rfd)

    def test_batch_reader_read_chunks_stall_raises(self):
        rfd, wfd = os.pipe()

        def writer() -> None:
            os.write(wfd, b"ab")
            time.sleep(2.0)
            os.close(wfd)

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            reader = mechanical_verify._BatchReader(rfd)
            with mock.patch.object(
                mechanical_verify, "_BATCH_STALL_SECONDS", 0.5
            ):
                with self.assertRaises(mechanical_verify._BatchStalled):
                    list(reader.read_chunks(5))
        finally:
            thread.join(timeout=10)
            os.close(rfd)


class PromisorRefusalTests(unittest.TestCase):
    """Task 18 (paperthin validation 7, breach B-B): a
    delivered partial-clone config makes the verifier's own
    git calls fetch a genuinely missing blob through a program
    the checkout's config names (the ext:: transport). The
    delivered shape is refused in _repo_local_config_refusal,
    lazy fetch is disabled in every call's environment, and
    the ext:: transport is pinned off — a missing blob then
    fails closed, never fetched, never sealed over."""

    def _repo(self, tmp: str) -> tuple[Path, str]:
        root = Path(tmp) / "repo"
        root.mkdir()
        init_git_repo(root)
        commit_file(root, "tracked.py", 'VALUE = "good"\n', "add tracked")
        sha = git(root, "rev-parse", "HEAD:tracked.py").stdout.strip()
        return root, sha

    def test_promisor_remote_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._repo(tmp)
            git(root, "config", "remote.origin.promisor", "true")
            reason = mechanical_verify._repo_local_config_refusal(root)
            self.assertIsNotNone(reason)
            self.assertIn("promisor", reason)
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("promisor", proc.stdout)

    def test_partialclone_extension_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._repo(tmp)
            git(root, "config", "extensions.partialclone", "origin")
            reason = mechanical_verify._repo_local_config_refusal(root)
            self.assertIsNotNone(reason)
            self.assertIn("extensions.partialclone", reason)

    def test_ext_transport_url_is_refused(self):
        for key in ("remote.origin.url", "remote.origin.pushurl"):
            with self.subTest(key=key), \
                    tempfile.TemporaryDirectory() as tmp:
                root, _ = self._repo(tmp)
                git(root, "config", key, "ext::/bin/true")
                reason = mechanical_verify._repo_local_config_refusal(
                    root
                )
                self.assertIsNotNone(reason)
                self.assertIn("ext::", reason)

    def test_worktree_scope_promisor_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._repo(tmp)
            git(root, "config", "extensions.worktreeConfig", "true")
            git(
                root, "config", "--worktree",
                "remote.origin.promisor", "true",
            )
            reason = mechanical_verify._repo_local_config_refusal(root)
            self.assertIsNotNone(reason)
            self.assertIn("promisor", reason)

    def test_include_chain_promisor_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._repo(tmp)
            outside = write(
                Path(tmp),
                "included-config",
                "[remote \"origin\"]\n\tpromisor = true\n",
            )
            git(root, "config", "include.path", str(outside))
            reason = mechanical_verify._repo_local_config_refusal(root)
            self.assertIsNotNone(reason)
            self.assertIn("promisor", reason)

    def test_inert_remote_config_is_not_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._repo(tmp)
            git(root, "config", "remote.origin.promisor", "false")
            git(
                root, "config", "remote.origin.url",
                "https://example.invalid/repo.git",
            )
            git(
                root, "config", "remote.origin.pushurl",
                "file:///nonexistent/repo.git",
            )
            self.assertIsNone(
                mechanical_verify._repo_local_config_refusal(root)
            )
            receipts = root / "r.jsonl"
            self.assertTrue(mechanical_verify.tree_clean(root, receipts))

    def test_operator_global_promisor_is_not_judged(self):
        # Delivered scopes only: the operator's own global
        # config is operator environment, never a refusal.
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._repo(tmp)
            home = Path(tmp) / "home"
            home.mkdir()
            write(
                home,
                ".gitconfig",
                "[remote \"origin\"]\n"
                "\tpromisor = true\n"
                "\turl = ext::/bin/true\n"
                "[extensions]\n"
                "\tpartialclone = origin\n",
            )
            with mock.patch.dict(os.environ, {"HOME": str(home)}):
                self.assertIsNone(
                    mechanical_verify._repo_local_config_refusal(root)
                )

    def test_promisor_missing_blob_never_fetches(self):
        # The validator's fixture end-to-end: genuinely absent
        # blob, delivered promisor config on the ext::
        # transport. The sentinel must not fire — the refusal
        # speaks first, and fetch is disabled beneath it.
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo(tmp)
            (root / ".git" / "objects" / sha[:2] / sha[2:]).unlink()
            sentinel = Path(tmp) / "fetch-fired"
            script = write(
                Path(tmp),
                "fetch.sh",
                f"#!/bin/sh\ntouch {sentinel}\nexit 1\n",
            )
            script.chmod(0o755)
            git(root, "config", "extensions.partialclone", "origin")
            git(root, "config", "remote.origin.promisor", "true")
            git(root, "config", "remote.origin.url", f"ext::{script}")
            git(root, "config", "protocol.ext.allow", "always")
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertFalse(sentinel.exists())
            self.assertIn("promisor", proc.stdout + proc.stderr)

    def test_missing_blob_without_promisor_config_fails_closed(self):
        # Plain corruption (no promisor shape): the missing
        # blob fails the pass closed — never a fetch, never a
        # seal over absent bytes.
        with tempfile.TemporaryDirectory() as tmp:
            root, sha = self._repo(tmp)
            (root / ".git" / "objects" / sha[:2] / sha[2:]).unlink()
            self.assertIsNone(
                mechanical_verify._repo_local_config_refusal(root)
            )
            receipts = root / "r.jsonl"
            self.assertFalse(mechanical_verify.tree_clean(root, receipts))
            proc = verify(root, "1", receipts)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)


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
