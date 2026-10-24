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
