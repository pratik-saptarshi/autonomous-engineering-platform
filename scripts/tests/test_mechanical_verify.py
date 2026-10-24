import contextlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mechanical_verify
from mechanical_verify import (
    VerificationCommand,
    discover_verification_commands,
    run_all,
    run_verification,
)

SCRIPT = Path(__file__).resolve().parent.parent / "mechanical_verify.py"


def write(root: Path, name: str, content: str = "") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


class DiscoveryTests(unittest.TestCase):
    def test_discovers_go_test_from_go_mod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "go.mod")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["go-test"])
            self.assertEqual(commands[0].argv, ("go", "test", "./..."))

    def test_discovers_cargo_test_from_cargo_toml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Cargo.toml")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["cargo-test"])

    def test_discovers_npm_test_only_with_real_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "package.json", json.dumps({"scripts": {"test": "node --test"}}))
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["npm-test"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "package.json",
                json.dumps(
                    {"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}
                ),
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], [])

    def test_discovers_pytest_from_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pyproject.toml", "[project]\nname = 'x'\n")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertIn("pytest", ids)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertIn("pytest", ids)

    def test_discovers_unittest_from_test_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "test_x.py", "import unittest\n")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, ["unittest"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "y_test.py", "from unittest import TestCase\n")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, ["unittest"])

    def test_discovers_pytest_fallback_when_test_files_lack_unittest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "test_x.py", "def test_a():\n    assert True\n")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, ["pytest"])

    def test_discovers_mixed_styles_partitioned_by_runner(self):
        # A suite mixing unittest-style modules with plain pytest-style
        # modules needs BOTH runners: the unittest command names only
        # the unittest-style modules, and the remaining modules fall to
        # the pytest command — otherwise plain test functions in the
        # non-unittest modules are silently never collected.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "test_ok.py", "import unittest\n")
            write(root, "test_bad.py", "def test_bad():\n    assert True\n")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest", "pytest"])
            self.assertEqual(
                commands[0].argv,
                ("python3", "-m", "unittest", "-v", "test_ok"),
            )
            self.assertEqual(
                commands[1].argv, ("python3", "-m", "pytest", "-q")
            )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "ok_test.py", "from unittest import TestCase\n")
            write(root, "plain_test.py", "def test_plain():\n    assert True\n")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest", "pytest"])
            self.assertEqual(
                commands[0].argv,
                ("python3", "-m", "unittest", "-v", "ok_test"),
            )

    def test_discovers_make_test_from_makefile_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\ttrue\n")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, ["make-test"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "build:\n\ttrue\n")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])

    def test_discovers_markdownlint_when_tool_on_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, ".markdownlint.yaml", "default: true\n")
            bin_dir = base / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "markdownlint-cli2"
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
            env_path = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
            with mock.patch.dict(os.environ, {"PATH": env_path}):
                commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["markdownlint"])
            self.assertEqual(
                commands[0].argv,
                (
                    "markdownlint-cli2",
                    "**/*.md",
                    "!reference/esf/**/*.md",
                    "!skills/archify/**/*.md",
                ),
            )

    def test_discovers_scripts_unittest_from_scripts_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "scripts/tests/test_sample.py", "import unittest\n")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["scripts-unittest"])
            self.assertEqual(
                commands[0].argv,
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

    def test_scripts_tests_empty_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts" / "tests").mkdir(parents=True)
            self.assertEqual(discover_verification_commands(root), ())

    def test_scripts_tests_without_test_files_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "scripts/tests/helper.py", "VALUE = 1\n")
            write(root, "scripts/tests/fixtures.txt", "data\n")
            self.assertEqual(discover_verification_commands(root), ())

    def test_scripts_tests_symlink_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            external = base / "external"
            write(external, "test_real.py", "import unittest\n")
            (root / "scripts").mkdir(parents=True)
            os.symlink(external, root / "scripts" / "tests")
            self.assertEqual(discover_verification_commands(root), ())

    def test_scripts_tests_symlinked_test_file_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            foreign = write(base / "elsewhere", "test_real.py", "import unittest\n")
            tests_dir = root / "scripts" / "tests"
            tests_dir.mkdir(parents=True)
            os.symlink(foreign, tests_dir / "test_sample.py")
            self.assertEqual(discover_verification_commands(root), ())

    def test_no_scripts_directory_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "src/app.py", "VALUE = 1\n")
            self.assertEqual(discover_verification_commands(root), ())

    def test_no_markers_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(discover_verification_commands(Path(tmp)), ())


def _pid_dead(pid: int) -> bool:
    """Gone entirely, or a zombie (dead, awaiting reaping by init)."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return True
    state = stat.rsplit(")", 1)[1].split()[0]
    return state == "Z"


class RunVerificationTests(unittest.TestCase):
    def test_run_captures_pass_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ok = run_verification(root, VerificationCommand("t", "t", ("true",)))
            self.assertTrue(ok.passed)
            self.assertEqual(ok.exit_code, 0)
            bad = run_verification(root, VerificationCommand("t", "t", ("false",)))
            self.assertFalse(bad.passed)
            self.assertEqual(bad.exit_code, 1)

    def test_run_enforces_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_verification(
                Path(tmp),
                VerificationCommand("t", "t", ("sleep", "5")),
                timeout_seconds=1,
            )
            self.assertTrue(result.timed_out)
            self.assertFalse(result.passed)
            self.assertNotIn(result.exit_code, (None, 0))
            self.assertLess(result.duration_ms, 3000)

    def test_timeout_kills_sigterm_ignoring_descendant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "child.pid"
            child_src = (
                "import os, signal, sys, time\n"
                "from pathlib import Path\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "Path(sys.argv[1]).write_text(str(os.getpid()))\n"
                "time.sleep(60)\n"
            )
            parent_src = (
                "import subprocess, sys, time\n"
                "subprocess.Popen([sys.executable, '-c', "
                + repr(child_src)
                + ", sys.argv[1]])\n"
                "time.sleep(60)\n"
            )
            result = run_verification(
                root,
                VerificationCommand(
                    "t",
                    "t",
                    (sys.executable, "-c", parent_src, str(marker)),
                ),
                timeout_seconds=1,
            )
            self.assertTrue(result.timed_out)
            child_pid = int(marker.read_text())
            try:
                # The leader dies on SIGTERM (default handler); the child
                # ignores it. The verifier's post-grace escalation must
                # still SIGKILL the group.
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not _pid_dead(child_pid):
                    time.sleep(0.05)
                self.assertTrue(
                    _pid_dead(child_pid),
                    f"SIGTERM-ignoring descendant {child_pid} survived",
                )
            finally:
                if not _pid_dead(child_pid):
                    os.kill(child_pid, signal.SIGKILL)

    def test_run_caps_output_at_65536_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_verification(
                Path(tmp),
                VerificationCommand(
                    "t",
                    "t",
                    ("python3", "-c", "import sys; sys.stdout.write('x' * 200000)"),
                ),
            )
            self.assertLessEqual(len(result.stdout.encode()), 65536)
            self.assertTrue(result.output_truncated)


DRIVER = Path(__file__).resolve().parent / "survivor_driver.py"


class SurvivorReapTests(unittest.TestCase):
    """Task 2: a `setsid`-detached descendant must not outlive the run
    that spawned it, on the success path or the timeout path — while a
    bystander process that predates the run is never signalled.

    The verifier runs inside the survivor_driver subprocess so the
    subreaper flag main() sets never touches this test process.
    """

    def run_driver(self, base: Path, mode: str, timeout: int = 300) -> dict:
        proc = subprocess.run(
            [
                sys.executable,
                str(DRIVER),
                "--root",
                str(base / "root"),
                "--mode",
                mode,
                "--timeout",
                str(timeout),
                "--marker",
                str(base / "marker.log"),
                "--writer-pid-file",
                str(base / "writer.pid"),
                "--receipts",
                str(base / "receipts.jsonl"),
                "--helper-pid-file",
                str(base / "helper.pid"),
                "--helper-status-file",
                str(base / "helper.status"),
                "--rc-file",
                str(base / "verify.rc"),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            proc.returncode, 0, f"driver failed:\n{proc.stdout}\n{proc.stderr}"
        )
        result = {
            "rc": int((base / "verify.rc").read_text()),
            "writer_pid": int((base / "writer.pid").read_text()),
            "helper_pid": int((base / "helper.pid").read_text()),
            "helper_status": (base / "helper.status").read_text(),
            "receipts": [
                json.loads(line)
                for line in (base / "receipts.jsonl")
                .read_text()
                .splitlines()
                if line.strip()
            ],
        }
        # Never leak a surviving writer into later tests when running
        # against a verifier that does not reap yet.
        if not _pid_dead(result["writer_pid"]):
            os.kill(result["writer_pid"], signal.SIGKILL)
        return result

    def marker_size(self, base: Path) -> int:
        marker = base / "marker.log"
        return marker.stat().st_size if marker.exists() else 0

    def test_success_path_setsid_survivor_is_reaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = self.run_driver(base, "success")
            self.assertEqual(result["rc"], 0)
            writer_pid = result["writer_pid"]
            self.assertTrue(
                _pid_dead(writer_pid),
                f"setsid writer {writer_pid} survived a successful verify",
            )
            size = self.marker_size(base)
            time.sleep(1)
            self.assertEqual(
                self.marker_size(base),
                size,
                "writer kept appending to the marker after the run",
            )
            command_receipts = [
                r for r in result["receipts"] if r.get("command_id") == "make-test"
            ]
            self.assertEqual(len(command_receipts), 1)
            self.assertIn(
                writer_pid, command_receipts[0].get("survivors_killed", [])
            )

    def test_timeout_path_setsid_survivor_is_reaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = self.run_driver(base, "timeout", timeout=2)
            self.assertEqual(result["rc"], 1)
            writer_pid = result["writer_pid"]
            self.assertTrue(
                _pid_dead(writer_pid),
                f"setsid writer {writer_pid} survived a timed-out verify",
            )
            size = self.marker_size(base)
            time.sleep(1)
            self.assertEqual(self.marker_size(base), size)

    def test_bystander_predating_the_run_is_never_signalled(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = self.run_driver(base, "success")
            self.assertEqual(result["helper_status"], "alive")
            for record in result["receipts"]:
                self.assertNotIn(
                    result["helper_pid"], record.get("survivors_killed", [])
                )


class UnittestExecutionTests(unittest.TestCase):
    """The executed unittest set must equal the discovered set: rule 5
    discovers both test_*.py and *_test.py files."""

    def run_fixture(self, root: Path) -> int:
        commands = discover_verification_commands(root)
        self.assertEqual([c.id for c in commands], ["unittest"])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            return run_all(root, commands, mem_available_kb=lambda: 10**9)

    def test_failing_suffix_named_test_file_fails_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_ok.py",
                "import unittest\n\n\n"
                "class Ok(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            write(
                root,
                "broken_test.py",
                "import unittest\n\n\n"
                "class Broken(unittest.TestCase):\n"
                "    def test_broken(self):\n"
                "        self.fail('suffix-named failure must run')\n",
            )
            self.assertEqual(self.run_fixture(root), 1)

    def test_passing_suffix_named_test_file_actually_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "marker_test.py",
                "import unittest\n"
                "from pathlib import Path\n\n\n"
                "class Marker(unittest.TestCase):\n"
                "    def test_marker(self):\n"
                "        Path('marker.ran').write_text('ran')\n",
            )
            self.assertEqual(self.run_fixture(root), 0)
            self.assertTrue((root / "marker.ran").is_file())


class ScriptsUnittestExecutionTests(unittest.TestCase):
    def test_scripts_tests_only_fixture_verifies_and_records_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(
                root,
                "scripts/tests/test_sample.py",
                "import unittest\n\n\n"
                "class Sample(unittest.TestCase):\n"
                "    def test_sample(self):\n"
                "        pass\n",
            )
            receipts = base / "receipts.jsonl"
            stdout = io.StringIO()
            with mock.patch.object(
                mechanical_verify, "available_memory_kb", return_value=10**9
            ):
                with contextlib.redirect_stdout(stdout):
                    rc = mechanical_verify.main(
                        [
                            "verify",
                            "--root",
                            str(root),
                            "--task",
                            "t",
                            "--receipts",
                            str(receipts),
                        ]
                    )
            self.assertEqual(rc, 0, stdout.getvalue())
            self.assertIn("VERIFY: scripts-unittest PASS", stdout.getvalue())
            records = [
                json.loads(line) for line in receipts.read_text().splitlines()
            ]
            run_receipts = [
                r for r in records if r.get("command_id") == "scripts-unittest"
            ]
            self.assertEqual(len(run_receipts), 1)
            self.assertEqual(run_receipts[0]["exit_code"], 0)
            self.assertFalse(run_receipts[0]["timed_out"])
            check_stdout = io.StringIO()
            with contextlib.redirect_stdout(check_stdout):
                check_rc = mechanical_verify.check_receipts(receipts, "t")
            self.assertEqual(check_rc, 0, check_stdout.getvalue())


class CliTests(unittest.TestCase):
    def run_cli(self, root: Path, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "verify", "--root", str(root), "--task", "t"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

    def test_markdownlint_skipped_when_tool_missing(self):
        # Fixture deviation (controller ruling 2): PATH carries symlinks for
        # python3 AND make -- make-test spawns `make`, so a python3-only PATH
        # could never pass. A `true` symlink is also required in practice:
        # GNU make execs the simple recipe `true` directly (no shell), so it
        # resolves `true` through PATH too (verified: "make: true: No such
        # file or directory"). Still no markdownlint-cli2 anywhere on it.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, ".markdownlint.yaml", "default: true\n")
            write(root, "Makefile", "test:\n\ttrue\n")
            bin_dir = base / "bin"
            bin_dir.mkdir()
            os.symlink(sys.executable, bin_dir / "python3")
            os.symlink(shutil.which("make"), bin_dir / "make")
            os.symlink(shutil.which("true"), bin_dir / "true")
            proc = self.run_cli(root, env={"PATH": str(bin_dir)})
            self.assertIn("VERIFY: markdownlint SKIPPED tool missing", proc.stdout)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_verify_stops_at_first_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "package.json", json.dumps({"scripts": {"test": "false"}}))
            write(root, "Makefile", "test:\n\ttrue\n")
            proc = self.run_cli(root)
            self.assertIn("VERIFY: npm-test FAIL", proc.stdout)
            self.assertIn("VERIFY: stopped at first failure (npm-test)", proc.stdout)
            self.assertNotIn("VERIFY: make-test", proc.stdout)
            self.assertEqual(proc.returncode, 1)

    def test_verify_no_commands_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_cli(Path(tmp))
            self.assertIn("VERIFY: no verification commands discovered", proc.stdout)
            self.assertEqual(proc.returncode, 2)

    def test_verify_memory_refusal_exit_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\ttrue\n")
            stdout = io.StringIO()
            with mock.patch.object(
                mechanical_verify, "available_memory_kb", return_value=100000
            ):
                with contextlib.redirect_stdout(stdout):
                    # main() returns the exit code (Step 3); sys.exit turns it
                    # into the SystemExit the CLI entry point raises.
                    with self.assertRaises(SystemExit) as ctx:
                        sys.exit(
                            mechanical_verify.main(
                                ["verify", "--root", str(root), "--task", "t"]
                            )
                        )
            self.assertEqual(ctx.exception.code, 3)
            self.assertIn(
                "VERIFY: insufficient memory available (97 MiB < 512 MiB); "
                "refusing to run",
                stdout.getvalue(),
            )

    def test_verify_budget_zero_stops(self):
        commands = (VerificationCommand("t", "t", ("true",)),)
        seen = []
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(stdout):
                rc = run_all(
                    Path(tmp),
                    commands,
                    budget_seconds=0,
                    on_result=seen.append,
                )
        self.assertEqual(rc, 1)
        self.assertIn("VERIFY: budget exhausted (0s)", stdout.getvalue())
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
