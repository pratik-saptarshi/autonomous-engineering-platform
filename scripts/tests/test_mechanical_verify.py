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
        # Task 4 named exception: classification follows the runners'
        # collection semantics, so a stub that merely imports unittest
        # no longer discovers the unittest command — the fixtures
        # define real TestCase subclasses, which is what unittest
        # discovery ever meant. Bare-import modules fall to the pytest
        # default (see CollectedCountTests).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_x.py",
                "import unittest\n\n\n"
                "class X(unittest.TestCase):\n"
                "    def test_x(self):\n"
                "        pass\n",
            )
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, ["unittest"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "y_test.py",
                "from unittest import TestCase\n\n\n"
                "class Y(TestCase):\n"
                "    def test_y(self):\n"
                "        pass\n",
            )
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, ["unittest"])

    def test_discovers_unittest_from_aliased_or_indirect_testcase(self):
        # Aliases of TestCase (import-as, assignment) and subclasses of
        # a module-local TestCase subclass are still the unittest leg:
        # the unittest loader collects them all.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_alias.py",
                "from unittest import TestCase as Base\n\n\n"
                "class Sub(Base):\n"
                "    def test_x(self):\n"
                "        pass\n",
            )
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, ["unittest"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_indirect.py",
                "import unittest\n\n\n"
                "class Base(unittest.TestCase):\n"
                "    def test_x(self):\n"
                "        pass\n\n\n"
                "class Sub(Base):\n"
                "    pass\n",
            )
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, ["unittest"])

    def test_pure_testcase_tree_keeps_unittest_argv_byte_identical(self):
        # RC2: a module whose only collectable content is TestCase
        # subclasses does NOT trigger the pytest command, so a
        # pure-unittest tree keeps exactly the argv it had before
        # AST classification.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_a.py",
                "import unittest\n\n\n"
                "class A(unittest.TestCase):\n"
                "    def test_a(self):\n"
                "        pass\n",
            )
            write(
                root,
                "b_test.py",
                "from unittest import TestCase\n\n\n"
                "class B(TestCase):\n"
                "    def test_b(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertEqual(
                commands[0].argv,
                ("python3", "-m", "unittest", "-v", "b_test", "test_a"),
            )

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
        # Fixture modernization (same class as the Task 4 named
        # exception): the unittest-side modules define real TestCase
        # subclasses — import-only stubs no longer classify as
        # unittest under runner collection semantics. Every assertion
        # below is unchanged.
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
            write(root, "test_bad.py", "def test_bad():\n    assert True\n")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest", "pytest"])
            self.assertEqual(
                commands[0].argv,
                ("python3", "-m", "unittest", "-v", "test_ok"),
            )
            self.assertEqual(
                commands[1].argv, ("python3", "-m", "pytest", "-v")
            )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "ok_test.py",
                "from unittest import TestCase\n\n\n"
                "class Ok(TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
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
                    "!reference/neurostrata/**/*.md",
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
    def test_markdownlint_argv_matches_ci_exclusion_set(self):
        # Task 8 (R7, P2-9): the verifier's lint gate must exclude
        # exactly what CI's docs-lint job excludes — the vendored
        # neurostrata tree is not first-party prose.
        self.assertEqual(
            mechanical_verify.MARKDOWNLINT_ARGV,
            (
                "markdownlint-cli2",
                "**/*.md",
                "!reference/esf/**/*.md",
                "!reference/neurostrata/**/*.md",
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


DRIVER = Path(__file__).resolve().parent / "survivor_driver.py"


class SurvivorReapTests(unittest.TestCase):
    """Task 2: a `setsid`-detached descendant must not outlive the run
    that spawned it, on the success path or the timeout path — while a
    bystander process that predates the run is never signalled.

    The verifier runs inside the survivor_driver subprocess so the
    subreaper flag main() sets never touches this test process.
    """

    def run_driver(
        self, base: Path, mode: str, timeout: int = 300, receipts: bool = True
    ) -> dict:
        driver_argv = [
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
            "--helper-pid-file",
            str(base / "helper.pid"),
            "--helper-status-file",
            str(base / "helper.status"),
            "--rc-file",
            str(base / "verify.rc"),
        ]
        if receipts:
            driver_argv += ["--receipts", str(base / "receipts.jsonl")]
        proc = subprocess.run(
            driver_argv,
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
            ]
            if receipts
            else [],
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

    def test_success_path_no_receipts_setsid_survivor_is_reaped(self):
        """A receipts-less verify must reap too: the subreaper flag is
        set for every verify run, not only runs writing receipts."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = self.run_driver(base, "success", receipts=False)
            self.assertEqual(result["rc"], 0)
            writer_pid = result["writer_pid"]
            self.assertTrue(
                _pid_dead(writer_pid),
                f"setsid writer {writer_pid} survived a receipts-less verify",
            )
            size = self.marker_size(base)
            time.sleep(1)
            self.assertEqual(
                self.marker_size(base),
                size,
                "writer kept appending to the marker after the run",
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
                check_rc = mechanical_verify.check_receipts(receipts, "t", root)
            self.assertEqual(check_rc, 0, check_stdout.getvalue())

    def test_scripts_unittest_pass_seals_with_collected_count(self):
        # Composite-verifier step (PR #42 rebase onto #45): the
        # sealed PASS must rest on the count gate being satisfied by
        # the scripts-unittest leg itself — the receipt records the
        # collected count the gate judged, not None.
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
            self.assertEqual(run_receipts[0]["tests_collected"], 1)
            check_stdout = io.StringIO()
            with contextlib.redirect_stdout(check_stdout):
                check_rc = mechanical_verify.check_receipts(receipts, "t", root)
            self.assertEqual(check_rc, 0, check_stdout.getvalue())


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


class CollectedCountTests(unittest.TestCase):
    """Task 4 (overseer remediation R3, closes P1-1): rule 5 proves
    execution, not routing. Classification follows the runners'
    collection semantics, and every Python command must prove a
    collected-test count > 0 — a zero or unparseable count fails the
    command even when the runner exits 0."""

    def run_fixture(self, root: Path):
        commands = discover_verification_commands(root)
        results = []
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = run_all(
                root,
                commands,
                mem_available_kb=lambda: 10**9,
                on_result=results.append,
            )
        return commands, results, rc, stdout.getvalue()

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_decoy_testcase_cannot_shield_failing_plain_function(self):
        # The panel P1-1 decoy: a passing TestCase in the same module
        # must not route the module away from pytest — the failing
        # plain function beside it has to execute.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_decoy.py",
                "import unittest\n\n\n"
                "def test_companion():\n"
                "    assert False, 'plain function beside a TestCase "
                "must run'\n\n\n"
                "class Decoy(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands, _, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["unittest", "pytest"])
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_unittest_mock_import_alone_does_not_route_to_unittest(self):
        # `import unittest.mock` is a mundane trigger of the old
        # substring routing: no TestCase is defined, so there is no
        # unittest leg and the plain function runs under pytest.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_mock.py",
                "import unittest.mock\n\n\n"
                "def test_fails():\n"
                "    assert False, 'plain function must run under "
                "pytest'\n",
            )
            commands, _, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_test_star_class_without_testcase_runs_under_pytest(self):
        # A Test* class that is not a TestCase subclass is collected
        # by pytest only — even when the module imports unittest, the
        # unittest loader would collect nothing from it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_widget.py",
                "import unittest\n\n\n"
                "class TestWidget:\n"
                "    def test_fails(self):\n"
                "        assert False, 'Test* class method must run "
                "under pytest'\n",
            )
            commands, _, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_all_skipped_module_passes_with_positive_collected_count(self):
        # Deliberate ruling: skips count as collected. The guarantee
        # is "routed to a runner that collects the test"; whether a
        # collected test skips is the test author's signal.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_skip.py",
                "import pytest\n\n\n"
                "@pytest.mark.skip(reason='deliberate')\n"
                "def test_skipped():\n"
                "    assert False, 'a skipped test never executes'\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 0)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].tests_collected, 1)
            # The receipt written from this result carries the count.
            receipts = root / "r.jsonl"
            mechanical_verify.append_receipt(receipts, "t", results[0])
            record = json.loads(receipts.read_text().splitlines()[0])
            self.assertEqual(record["tests_collected"], 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_collection_error_module_fails_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_boom.py",
                "raise RuntimeError('import-time failure')\n\n\n"
                "def test_never_collected():\n"
                "    pass\n",
            )
            commands, _, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 1)

    def test_unittest_module_collecting_zero_fails(self):
        # A TestCase subclass with no test methods exits 0 under
        # unittest ("Ran 0 tests") — the count gate must fail it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_empty.py",
                "import unittest\n\n\n"
                "class Empty(unittest.TestCase):\n"
                "    pass\n",
            )
            commands, results, rc, output = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertEqual(rc, 1)
            self.assertIn("zero tests collected", output)
            self.assertEqual(results[0].tests_collected, 0)

    def test_zero_collect_leg_defers_to_remaining_python_leg(self):
        # Count-gate union rule (Codex P2 on the A2 fix): a Python
        # leg whose ONLY failure is a zero collected count does not
        # veto the run while another Python leg remains — the gate
        # judges the union of the legs that ran, and every leg
        # executes before it judges.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commands = [
                VerificationCommand(
                    "unittest",
                    "Python unittest",
                    (
                        sys.executable,
                        "-c",
                        "import sys; print('Ran 0 tests in 0.000s', "
                        "file=sys.stderr)",
                    ),
                ),
                VerificationCommand(
                    "pytest",
                    "Python tests",
                    (sys.executable, "-c", "print('1 passed in 0.01s')"),
                ),
            ]
            results = []
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = run_all(
                    root,
                    commands,
                    mem_available_kb=lambda: 10**9,
                    on_result=results.append,
                )
            self.assertEqual(rc, 0)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].tests_collected, 0)
            self.assertEqual(results[1].tests_collected, 1)

    def test_all_python_legs_zero_collected_still_fails(self):
        # The union rule is not a vacuity hole: when every Python
        # leg collects zero, the run still fails the count gate.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commands = [
                VerificationCommand(
                    "unittest",
                    "Python unittest",
                    (
                        sys.executable,
                        "-c",
                        "import sys; print('Ran 0 tests in 0.000s', "
                        "file=sys.stderr)",
                    ),
                ),
                VerificationCommand(
                    "pytest",
                    "Python tests",
                    (sys.executable, "-c", "print('no tests ran')"),
                ),
            ]
            results = []
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = run_all(
                    root,
                    commands,
                    mem_available_kb=lambda: 10**9,
                    on_result=results.append,
                )
            self.assertEqual(rc, 1)
            self.assertEqual(len(results), 2)
            self.assertIn("zero tests collected", stdout.getvalue())

    def test_zero_or_unparseable_count_fails_despite_zero_exit(self):
        # The count verdict rides on VerificationResult, consulted by
        # run_all exactly like survivors_killed: exit 0 with no
        # parseable count is a failure, for both Python runners.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_verification(
                root,
                VerificationCommand(
                    "pytest",
                    "Python tests",
                    (sys.executable, "-c", "print('no summary here')"),
                ),
            )
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 0)
            self.assertFalse(result.passed)
            result = run_verification(
                root,
                VerificationCommand(
                    "unittest", "Python unittest", ("true",)
                ),
            )
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 0)
            self.assertFalse(result.passed)

    def test_scripts_unittest_count_uses_the_unittest_rule(self):
        # Composite-verifier step (PR #42 rebase onto #45): rule 8's
        # scripts-unittest leg is a unittest-discover run, so the
        # count gate judges it by the unittest rule — before this,
        # _count_collected returned None for the id and the leg's
        # receipts carried no collected count at all.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_verification(
                root,
                VerificationCommand(
                    "scripts-unittest",
                    "Scripts unittest",
                    (
                        sys.executable,
                        "-c",
                        "import sys; sys.stderr.write("
                        "'Ran 2 tests in 0.001s\\n')",
                    ),
                ),
            )
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 2)
            self.assertTrue(result.passed)
            result = run_verification(
                root,
                VerificationCommand(
                    "scripts-unittest",
                    "Scripts unittest",
                    (
                        sys.executable,
                        "-c",
                        "import sys; sys.stderr.write("
                        "'Ran 0 tests in 0.000s\\n')",
                    ),
                ),
            )
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 0)
            self.assertFalse(result.passed)

    def test_diagnostic_no_tests_ran_phrase_does_not_zero_count(self):
        # Codex P2 (round 4): with `addopts = -s`, a passing test's
        # printed diagnostic containing the phrase `no tests ran`
        # must not override the runner's final summary — only the
        # summary line is authoritative for zero collection.
        stdout = (
            "test_diag.py::test_warns PASSED-diagnostic: "
            "no tests ran in the legacy suite\n"
            "============================== 1 passed in 0.00s "
            "==============================\n"
        )
        count = mechanical_verify._count_collected(
            "pytest", stdout, ""
        )
        self.assertEqual(count, 1)

    def test_genuine_no_tests_ran_summary_is_zero(self):
        # The genuine zero-collection outcome is the summary line
        # itself reading `no tests ran in …s` — still 0.
        stdout = (
            "============================= test session starts "
            "==============================\n"
            "collected 0 items\n"
            "============================ no tests ran in 0.01s "
            "=============================\n"
        )
        count = mechanical_verify._count_collected(
            "pytest", stdout, ""
        )
        self.assertEqual(count, 0)

    def test_pytest_argv_keeps_summary_alive_under_quiet_addopts(self):
        # Codex P2 (round 5): pytest verbosity is an additive
        # counter across addopts and the command line. The old
        # discovered argv carried -q, so a project with
        # `addopts = -q` stacked to -qq and pytest suppressed the
        # terminal summary the count parser reads — a passing suite
        # recorded zero collected and was rejected. The discovered
        # argv must net positive verbosity so the summary survives
        # project addopts down to -qq.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pytest.ini", "[pytest]\naddopts = -q\n")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(
                commands[0].argv, ("python3", "-m", "pytest", "-v")
            )

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_quiet_addopts_project_passing_suite_passes_count_gate(self):
        # Codex's exact reproduction, at execution level: pytest.ini
        # with `addopts = -q` and one passing test. Under the old
        # -q argv the run printed only `. [100%]`, collected parsed
        # to zero, and verification was rejected; the counteracted
        # argv restores the summary, so the leg collects 1 and the
        # run passes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pytest.ini", "[pytest]\naddopts = -q\n")
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 0)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].tests_collected, 1)
            self.assertTrue(results[0].passed)

    def test_suppressed_summary_output_still_records_zero(self):
        # Guard against overcorrection: the fix lives in the
        # invocation, not the parser. A dots-only transcript — what
        # a verbosity-suppressed run hands the parser — is not
        # collection evidence and still records zero, so the count
        # gate fails closed if suppression ever reaches it.
        count = mechanical_verify._count_collected(
            "pytest", ". [100%]\n", ""
        )
        self.assertEqual(count, 0)

    def test_pytest_leg_with_diagnostic_phrase_passes_count_gate(self):
        # Run-level shape of the same finding: pytest exits 0, the
        # diagnostic phrase appears in test output, the summary
        # reports 1 passed — the leg collects 1 and passes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_verification(
                root,
                VerificationCommand(
                    "pytest",
                    "Python tests",
                    (
                        sys.executable,
                        "-c",
                        "print('diagnostic: no tests ran in the "
                        "legacy suite'); "
                        "print('1 passed in 0.00s')",
                    ),
                ),
            )
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 1)
            self.assertTrue(result.passed)


class ClassifierUncertaintyTests(unittest.TestCase):
    """Bucket A2 (panel CLASS-P1): classification uncertainty routes
    to MORE execution, never less. The panel's three variant families
    — a TestCase subclass whose base is imported from another module,
    collectable definitions inside compound statements, and content
    past the scan cap — must all execute their tests."""

    def run_fixture(self, root: Path):
        commands = discover_verification_commands(root)
        results = []
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = run_all(
                root,
                commands,
                mem_available_kb=lambda: 10**9,
                on_result=results.append,
            )
        return commands, results, rc, stdout.getvalue()

    def test_cross_module_testcase_base_routes_to_unittest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "shared_base.py",
                "import unittest\n\n\n"
                "class Base(unittest.TestCase):\n"
                "    pass\n",
            )
            write(
                root,
                "test_cross.py",
                "from shared_base import Base\n\n\n"
                "class CrossTests(Base):\n"
                "    def test_fails(self):\n"
                "        assert False, 'cross-module TestCase must run'\n",
            )
            commands, _, rc, _ = self.run_fixture(root)
            unittest_cmds = [c for c in commands if c.id == "unittest"]
            self.assertEqual(len(unittest_cmds), 1)
            self.assertIn("test_cross", unittest_cmds[0].argv)
            self.assertEqual(rc, 1)

    def test_cross_module_testcase_base_passing_variant_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "shared_base.py",
                "import unittest\n\n\n"
                "class Base(unittest.TestCase):\n"
                "    pass\n",
            )
            write(
                root,
                "test_cross.py",
                "from shared_base import Base\n\n\n"
                "class CrossTests(Base):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands, _, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertEqual(rc, 0)

    def test_compound_statement_function_routes_to_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_compound.py",
                "if True:\n"
                "    def test_fails():\n"
                "        assert False, 'function inside a compound "
                "statement must run'\n",
            )
            commands = discover_verification_commands(root)
            self.assertIn("pytest", [c.id for c in commands])

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_compound_statement_function_executes_and_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_compound.py",
                "if True:\n"
                "    def test_fails():\n"
                "        assert False, 'function inside a compound "
                "statement must run'\n",
            )
            _, _, rc, _ = self.run_fixture(root)
            self.assertEqual(rc, 1)

    def test_module_past_scan_cap_routes_to_both_runners(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            padding = "# padding\n" * 8000  # > SCAN_CHARS (65536)
            write(
                root,
                "test_late.py",
                padding
                + "def test_late():\n"
                + "    assert False, 'test past the scan cap must run'\n",
            )
            commands = discover_verification_commands(root)
            ids = [c.id for c in commands]
            self.assertIn("unittest", ids)
            self.assertIn("pytest", ids)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_module_past_scan_cap_executes_and_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            padding = "# padding\n" * 8000  # > SCAN_CHARS (65536)
            write(
                root,
                "test_late.py",
                padding
                + "def test_late():\n"
                + "    assert False, 'test past the scan cap must run'\n",
            )
            _, _, rc, _ = self.run_fixture(root)
            self.assertEqual(rc, 1)

    def test_object_base_routes_to_pytest_only(self):
        # Codex P2 (on the A2 fix): `object` is a KNOWN non-TestCase
        # base — a bare builtin is resolved by the interpreter
        # itself and cannot be a cross-module TestCase. It must not
        # trigger speculative unittest routing.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_sample.py",
                "class TestSample(object):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_object_base_pytest_module_executes_and_passes(self):
        # Codex's exact reproduction: a passing pytest-only module
        # (TestSample(object) with a passing test_ok) must PASS
        # verification, its test executed by pytest — before the
        # fix, speculative unittest collected zero and the count
        # gate failed the run before pytest executed.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_sample.py",
                "class TestSample(object):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 0)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].tests_collected, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_imported_mixin_speculative_leg_does_not_veto_pytest(self):
        # An imported mixin is GENUINE uncertainty (it may be a
        # TestCase in its home module), so both legs still run —
        # the A2 invariant holds. But the speculative unittest leg
        # collecting zero must not veto the run: pytest still
        # executes the module's test and the union of collected
        # counts satisfies the gate.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "shared_mixin.py", "class Mixin:\n    pass\n")
            write(
                root,
                "test_mixed.py",
                "from shared_mixin import Mixin\n\n\n"
                "class TestMixed(Mixin):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertEqual(rc, 0)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].tests_collected, 0)
            self.assertEqual(results[1].tests_collected, 1)

    def test_load_tests_hook_routes_to_unittest(self):
        # Codex P2 (gap-fix round 2, N1): a module that builds its
        # suite via unittest's load_tests protocol declares no
        # TestCase subclass, but only the unittest loader executes
        # load_tests — pytest never calls the hook. The hook alone
        # must select the unittest leg.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_loadtests.py",
                "import unittest\n"
                "\n"
                "\n"
                "def _passing():\n"
                "    pass\n"
                "\n"
                "\n"
                "def load_tests(loader, tests, pattern):\n"
                "    suite = unittest.TestSuite()\n"
                "    suite.addTest(unittest.FunctionTestCase(_passing))\n"
                "    return suite\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertIn("test_loadtests", commands[0].argv)

    def test_load_tests_failing_case_executes_and_fails(self):
        # Codex's exact reproduction: a load_tests module whose
        # suite contains a FAILING FunctionTestCase, beside a
        # passing plain pytest module. Before the fix the module
        # was classified pytest-only; pytest collected nothing from
        # it (it never executes load_tests) and verification PASSed
        # without running the failing case.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_loadtests.py",
                "import unittest\n"
                "\n"
                "\n"
                "def _boom():\n"
                "    raise AssertionError('load_tests case must run')\n"
                "\n"
                "\n"
                "def load_tests(loader, tests, pattern):\n"
                "    suite = unittest.TestSuite()\n"
                "    suite.addTest(unittest.FunctionTestCase(_boom))\n"
                "    return suite\n",
            )
            write(
                root,
                "test_plain.py",
                "def test_ok():\n"
                "    pass\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertIn("unittest", [c.id for c in commands])
            unittest_results = [
                r for r in results if r.command.id == "unittest"
            ]
            self.assertEqual(len(unittest_results), 1)
            self.assertEqual(unittest_results[0].tests_collected, 1)
            self.assertFalse(unittest_results[0].passed)
            self.assertEqual(rc, 1)

    def test_load_tests_passing_suite_passes(self):
        # The passing shape: the unittest leg executes the suite
        # load_tests builds, collects its case, and the run PASSes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_loadtests.py",
                "import unittest\n"
                "\n"
                "\n"
                "def _passing():\n"
                "    pass\n"
                "\n"
                "\n"
                "def load_tests(loader, tests, pattern):\n"
                "    suite = unittest.TestSuite()\n"
                "    suite.addTest(unittest.FunctionTestCase(_passing))\n"
                "    return suite\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertEqual(rc, 0)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].tests_collected, 1)

    def _write_inherited_fixture(self, root: Path, inherited_body: str):
        write(
            root,
            "shared_case.py",
            "import unittest\n\n\n"
            "class SharedCase(unittest.TestCase):\n"
            "    pass\n",
        )
        write(
            root,
            "test_inherited.py",
            "from shared_case import SharedCase\n"
            "\n"
            "\n"
            "class Helper:\n"
            "    def test_inherited(self):\n"
            f"        {inherited_body}\n"
            "\n"
            "\n"
            "class TestInherited(Helper):\n"
            "    pass\n"
            "\n"
            "\n"
            "class Unit(SharedCase):\n"
            "    def test_unit(self):\n"
            "        pass\n",
        )

    def test_inherited_test_methods_keep_pytest_leg(self):
        # Codex P2 (gap-fix round 3): a plain Test* class inheriting
        # its test methods from a local helper declares no literal
        # test methods in its own body. When a sibling class with an
        # imported base (Unit(SharedCase)) selects the unittest leg,
        # the old classifier suppressed pytest entirely — pytest is
        # the only runner that collects the inherited methods, so
        # they silently never ran. A Test* class that is not
        # resolved as a TestCase subclass keeps the pytest leg.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_inherited_fixture(
                root, "assert False, 'inherited test must run'"
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_inherited", commands[0].argv)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_inherited_failing_method_executes_and_fails(self):
        # Codex's exact reproduction: verification returned PASS
        # while a direct pytest run failed the inherited test.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_inherited_fixture(
                root, "assert False, 'inherited test must run'"
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertFalse(pytest_results[0].passed)
            self.assertGreaterEqual(
                pytest_results[0].tests_collected, 1
            )
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_inherited_passing_method_passes_with_pytest_leg(self):
        # The passing shape: both legs execute, the inherited
        # method is collected by pytest, and the run PASSes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_inherited_fixture(root, "pass")
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertTrue(pytest_results[0].passed)
            self.assertGreaterEqual(
                pytest_results[0].tests_collected, 1
            )
            self.assertEqual(rc, 0)

    def _write_imported_fixture(self, root: Path, imported_body: str):
        write(
            root,
            "shared.py",
            "import unittest\n"
            "\n"
            "\n"
            "class SharedCase(unittest.TestCase):\n"
            "    pass\n"
            "\n"
            "\n"
            "def test_failure():\n"
            f"    {imported_body}\n"
            "\n"
            "\n"
            "def helper():\n"
            "    pass\n",
        )
        write(
            root,
            "test_imported.py",
            "from shared import SharedCase, test_failure\n"
            "\n"
            "\n"
            "class Unit(SharedCase):\n"
            "    def test_unit(self):\n"
            "        pass\n",
        )

    def test_imported_test_function_keeps_pytest_leg(self):
        # Codex P2 (gap-fix round 6): pytest collects test_*
        # functions from a module's namespace, imported ones
        # included. The classifier recorded the imported name but
        # never let it trigger the pytest leg, so when a sibling
        # class with an imported base (Unit(SharedCase)) selected
        # the unittest leg, discovery ran unittest alone and the
        # imported test silently never ran.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_imported_fixture(
                root, "assert False, 'imported test must run'"
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_imported", commands[0].argv)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_imported_failing_function_executes_and_fails(self):
        # Codex's exact reproduction: verification returned PASS
        # while a direct pytest run failed on the imported
        # test_failure.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_imported_fixture(
                root, "assert False, 'imported test must run'"
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertFalse(pytest_results[0].passed)
            self.assertGreaterEqual(
                pytest_results[0].tests_collected, 1
            )
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_imported_passing_function_passes_with_pytest_leg(self):
        # The passing shape: both legs execute, the imported
        # function is collected by pytest, and the run PASSes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_imported_fixture(root, "pass")
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertTrue(pytest_results[0].passed)
            self.assertGreaterEqual(
                pytest_results[0].tests_collected, 1
            )
            self.assertEqual(rc, 0)

    def test_imported_function_aliased_to_test_name_keeps_pytest_leg(
        self,
    ):
        # Collection follows the BOUND name — pytest inspects the
        # module namespace, so `helper as test_helper` binds a
        # pytest-collectable name even though the function's own
        # name is not test_*.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "shared.py",
                "import unittest\n"
                "\n"
                "\n"
                "class SharedCase(unittest.TestCase):\n"
                "    pass\n"
                "\n"
                "\n"
                "def helper():\n"
                "    pass\n",
            )
            write(
                root,
                "test_imported.py",
                "from shared import SharedCase\n"
                "from shared import helper as test_helper\n"
                "\n"
                "\n"
                "class Unit(SharedCase):\n"
                "    def test_unit(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )

    def test_imported_non_test_names_do_not_trigger_pytest(self):
        # No overcorrection: an import binding only non-test names
        # (a TestCase base and a plain helper) is not pytest
        # evidence — the module stays unittest-only.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "shared.py",
                "import unittest\n"
                "\n"
                "\n"
                "class SharedCase(unittest.TestCase):\n"
                "    pass\n"
                "\n"
                "\n"
                "def helper():\n"
                "    pass\n",
            )
            write(
                root,
                "test_imported.py",
                "from shared import SharedCase, helper\n"
                "\n"
                "\n"
                "class Unit(SharedCase):\n"
                "    def test_unit(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertIn("test_imported", commands[0].argv)

    def _write_imported_class_fixture(self, root: Path, method_body: str):
        write(
            root,
            "shared.py",
            "import unittest\n"
            "\n"
            "\n"
            "class SharedCase(unittest.TestCase):\n"
            "    pass\n"
            "\n"
            "\n"
            "class TestImported:\n"
            "    def test_failure(self):\n"
            f"        {method_body}\n",
        )
        write(
            root,
            "test_imported_class.py",
            "from shared import SharedCase, TestImported\n"
            "\n"
            "\n"
            "class Unit(SharedCase):\n"
            "    def test_unit(self):\n"
            "        pass\n",
        )

    def test_imported_test_class_keeps_pytest_leg(self):
        # Codex P2 (gap-fix round 8): pytest collects Test*
        # classes from a module's namespace, imported ones
        # included. The classifier recorded the imported Test*
        # name without letting it trigger the pytest leg, so when
        # a sibling class with an imported base (Unit(SharedCase))
        # selected the unittest leg, discovery ran unittest alone
        # and the imported pytest class silently never ran. An
        # imported Test* class cannot be resolved as a TestCase
        # subclass from this module — its definition lives
        # elsewhere — so, like a locally unresolved Test* class,
        # it keeps the pytest leg.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_imported_class_fixture(
                root, "assert False, 'imported test must run'"
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_imported_class", commands[0].argv)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_imported_failing_class_executes_and_fails(self):
        # Codex's exact reproduction: verification returned PASS
        # while a direct pytest run failed on
        # TestImported.test_failure.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_imported_class_fixture(
                root, "assert False, 'imported test must run'"
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertFalse(pytest_results[0].passed)
            self.assertGreaterEqual(
                pytest_results[0].tests_collected, 1
            )
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_imported_passing_class_passes_with_pytest_leg(self):
        # The passing shape: both legs execute, the imported
        # class is collected by pytest, and the run PASSes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_imported_class_fixture(root, "pass")
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertTrue(pytest_results[0].passed)
            self.assertGreaterEqual(
                pytest_results[0].tests_collected, 1
            )
            self.assertEqual(rc, 0)

    def test_imported_testcase_name_does_not_trigger_pytest(self):
        # Guard: importing unittest's own TestCase class — under
        # its own name or an alias — is TestCase-denoting, not
        # pytest evidence; a module whose only class resolves
        # through it stays unittest-only (RC2).
        for import_line, base in (
            ("from unittest import TestCase\n", "TestCase"),
            ("from unittest import TestCase as TestBase\n", "TestBase"),
        ):
            with self.subTest(import_line=import_line):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write(
                        root,
                        "test_direct.py",
                        f"{import_line}"
                        "\n"
                        "\n"
                        f"class Unit({base}):\n"
                        "    def test_unit(self):\n"
                        "        pass\n",
                    )
                    commands = discover_verification_commands(root)
                    self.assertEqual(
                        [c.id for c in commands], ["unittest"]
                    )

    def test_imported_test_name_subclassed_as_testcase_keeps_pytest(self):
        # Ruling: resolution governs the LOCAL class — a class
        # that locally resolves as a TestCase subclass (here via
        # a second, TestCase-denoting base) selects the unittest
        # leg — but it does not consume the import: the imported
        # Test* name is itself in the module namespace, where
        # pytest collects it in its own right, so the binding
        # still triggers the pytest leg.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "shared.py",
                "class TestBase:\n"
                "    def test_shared(self):\n"
                "        pass\n",
            )
            write(
                root,
                "test_subclassed.py",
                "import unittest\n"
                "from shared import TestBase\n"
                "\n"
                "\n"
                "class Unit(TestBase, unittest.TestCase):\n"
                "    pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_subclassed", commands[0].argv)

    def test_plain_module_import_gains_no_pytest_leg(self):
        # Guard: a plain `import shared` binds only the module
        # name — no Test* name enters the namespace — so it is
        # not pytest evidence even though the module it names
        # defines collectable classes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "shared.py",
                "import unittest\n"
                "\n"
                "\n"
                "class SharedCase(unittest.TestCase):\n"
                "    pass\n"
                "\n"
                "\n"
                "class TestImported:\n"
                "    def test_failure(self):\n"
                "        pass\n",
            )
            write(
                root,
                "test_plain.py",
                "import shared\n"
                "\n"
                "\n"
                "class Unit(shared.SharedCase):\n"
                "    def test_unit(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertIn("test_plain", commands[0].argv)

    def _write_dotted_import_fixture(self, root: Path):
        write(
            root,
            "shared.py",
            "import unittest\n"
            "\n"
            "\n"
            "class SharedCase(unittest.TestCase):\n"
            "    pass\n"
            "\n"
            "\n"
            "class TestImported:\n"
            "    def test_failure(self):\n"
            "        pass\n",
        )
        write(
            root,
            "test_dotted_import.py",
            "import shared.TestImported as TestImported\n"
            "from shared import SharedCase\n"
            "\n"
            "\n"
            "class Unit(SharedCase):\n"
            "    def test_unit(self):\n"
            "        pass\n",
        )

    def test_dotted_import_aliased_test_class_keeps_pytest_leg(self):
        # Follow-on to gap-fix round 8: round 8 made an
        # ImportFrom binding a Test* name trigger the pytest leg,
        # but the same binding written as a dotted import with an
        # alias — `import shared.TestImported as TestImported`
        # (ast.Import with asname) — was recorded without the
        # trigger, so a sibling TestCase class again selected
        # unittest alone and the imported class silently never
        # ran. Unlike a star import, the bound name is explicit
        # in the source, so the name-based rule applies the same
        # way.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_dotted_import_fixture(root)
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_dotted_import", commands[0].argv)

    def test_import_asname_test_name_triggers_pytest_leg(self):
        # Ruling: an ast.Import alias binding a Test* name is
        # name-based evidence for pytest, exactly as round 8
        # ruled for ImportFrom. Statically, the import statement
        # alone cannot distinguish `import
        # shared.TestImported as TestImported` (intending the
        # class the dotted path names) from `import shared as
        # TestShared` (a module object under a Test* alias) —
        # what the alias denotes is unresolved from this module,
        # and unresolved Test* bindings keep the pytest leg
        # (uncertainty routes to more execution).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "shared.py",
                "import unittest\n"
                "\n"
                "\n"
                "class SharedCase(unittest.TestCase):\n"
                "    pass\n",
            )
            write(
                root,
                "test_asname_module.py",
                "import shared as TestShared\n"
                "from shared import SharedCase\n"
                "\n"
                "\n"
                "class Unit(SharedCase):\n"
                "    def test_unit(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_asname_module", commands[0].argv)

    def test_dotted_import_without_asname_gains_no_pytest_leg(self):
        # Guard: `import shared.TestImported` with NO alias
        # binds only the top-level name `shared` in the module
        # namespace — no Test* name is bound — so it is not
        # pytest evidence, even though the dotted path names a
        # collectable class.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_dotted_import_fixture(root)
            write(
                root,
                "test_dotted_import.py",
                "import shared.TestImported\n"
                "import unittest\n"
                "\n"
                "\n"
                "class Unit(unittest.TestCase):\n"
                "    def test_unit(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertIn("test_dotted_import", commands[0].argv)

    def test_import_aliased_testcase_gains_no_pytest_leg(self):
        # Guard: `import unittest.TestCase as TestCase` binds
        # unittest's own class under its own name — the same
        # exclusion round 8 applies to ImportFrom — so a module
        # resolving through it stays unittest-only (RC2).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_direct.py",
                "import unittest.TestCase as TestCase\n"
                "\n"
                "\n"
                "class Unit(TestCase):\n"
                "    def test_unit(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])

    def _write_assignment_fixture(
        self, root: Path, fn_body: str, assignment: str
    ):
        write(
            root,
            "shared.py",
            "import unittest\n"
            "\n"
            "\n"
            "class SharedCase(unittest.TestCase):\n"
            "    pass\n",
        )
        write(
            root,
            "test_assigned.py",
            "from shared import SharedCase\n"
            "\n"
            "\n"
            "def failure():\n"
            f"    {fn_body}\n"
            "\n"
            "\n"
            f"{assignment}\n"
            "\n"
            "\n"
            "class Unit(SharedCase):\n"
            "    def test_unit(self):\n"
            "        pass\n",
        )

    def test_assignment_bound_test_function_keeps_pytest_leg(self):
        # Codex P2 (gap-fix round 7): an assignment binding a
        # test_* name (`test_failure = failure`) puts a
        # pytest-collectable function in the module namespace, but
        # assignment targets were checked only for TestCase aliases
        # and load_tests — the binding never triggered the pytest
        # leg, so beside a sibling class with an imported base the
        # module went unittest-only and the assigned test silently
        # never ran.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assignment_fixture(
                root,
                "assert False, 'assigned test must run'",
                "test_failure = failure",
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_assigned", commands[0].argv)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_assignment_bound_failing_function_executes_and_fails(
        self,
    ):
        # Codex's exact reproduction: verification returned PASS
        # while a direct pytest run failed on test_failure.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assignment_fixture(
                root,
                "assert False, 'assigned test must run'",
                "test_failure = failure",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertFalse(pytest_results[0].passed)
            self.assertGreaterEqual(
                pytest_results[0].tests_collected, 1
            )
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_assignment_bound_passing_function_passes_with_pytest_leg(
        self,
    ):
        # The passing shape: both legs execute, the assigned
        # function is collected by pytest, and the run PASSes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assignment_fixture(
                root, "pass", "test_failure = failure"
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertTrue(pytest_results[0].passed)
            self.assertGreaterEqual(
                pytest_results[0].tests_collected, 1
            )
            self.assertEqual(rc, 0)

    def test_non_test_assignment_does_not_trigger_pytest(self):
        # No overcorrection: binding the same function under a
        # non-test name is not pytest evidence — pytest collects
        # the bound name, and `helper` is not collectable.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assignment_fixture(
                root, "pass", "helper = failure"
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertIn("test_assigned", commands[0].argv)

    def test_data_assignment_does_not_trigger_pytest(self):
        # A test_* name bound to literal data (a case table) is
        # provably not a test function — pytest collects callables,
        # not containers — so the module stays unittest-only.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assignment_fixture(
                root, "pass", "test_cases = [('a', 1), ('b', 2)]"
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])

    def _write_assigned_class_fixture(
        self, root: Path, method_body: str, assignment: str
    ):
        write(
            root,
            "shared.py",
            "import unittest\n"
            "\n"
            "\n"
            "class SharedCase(unittest.TestCase):\n"
            "    pass\n",
        )
        write(
            root,
            "test_assigned_class.py",
            "from shared import SharedCase\n"
            "\n"
            "\n"
            "class Helper:\n"
            "    def test_bad(self):\n"
            f"        {method_body}\n"
            "\n"
            "\n"
            f"{assignment}\n"
            "\n"
            "\n"
            "class Unit(SharedCase):\n"
            "    def test_unit(self):\n"
            "        pass\n",
        )

    def test_assignment_bound_test_class_keeps_pytest_leg(self):
        # Codex P2 (gap-fix round 9): an assignment binding a
        # Test* name (`TestGenerated = Helper`) puts a
        # pytest-collectable class in the module namespace, but
        # round 7's assignment rule recognized only test_*
        # function names — beside a sibling class with an imported
        # base the module went unittest-only and the assigned
        # class's tests silently never ran.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assigned_class_fixture(
                root,
                "assert False, 'assigned class test must run'",
                "TestGenerated = Helper",
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_assigned_class", commands[0].argv)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_assignment_bound_failing_class_executes_and_fails(self):
        # Codex's exact reproduction: verification returned PASS
        # while a direct pytest run failed on the assigned class.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assigned_class_fixture(
                root,
                "assert False, 'assigned class test must run'",
                "TestGenerated = Helper",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertFalse(pytest_results[0].passed)
            self.assertGreaterEqual(
                pytest_results[0].tests_collected, 1
            )
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_assignment_bound_passing_class_passes_with_pytest_leg(
        self,
    ):
        # The passing shape: both legs execute, the assigned class
        # is collected by pytest, and the run PASSes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assigned_class_fixture(
                root, "pass", "TestGenerated = Helper"
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertTrue(pytest_results[0].passed)
            self.assertGreaterEqual(
                pytest_results[0].tests_collected, 1
            )
            self.assertEqual(rc, 0)

    def test_annotated_assignment_bound_test_class_keeps_pytest_leg(
        self,
    ):
        # The AnnAssign form binds the same module attribute:
        # `TestGenerated: type = Helper`.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assigned_class_fixture(
                root, "pass", "TestGenerated: type = Helper"
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )

    def test_non_test_class_assignment_does_not_trigger_pytest(self):
        # No overcorrection: binding the same class under a
        # non-Test* name is not pytest evidence — pytest collects
        # the bound name, and `Helper2` is not collectable.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assigned_class_fixture(
                root, "pass", "Helper2 = Helper"
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertIn("test_assigned_class", commands[0].argv)

    def test_data_class_assignment_does_not_trigger_pytest(self):
        # A Test* name bound to literal data is provably not a
        # test class — the round-7 literal exclusion applies to
        # class names uniformly — so the module stays
        # unittest-only.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_assigned_class_fixture(
                root, "pass", "TestData = {'a': 1}"
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])

    def test_testcase_valued_assignment_does_not_trigger_pytest(self):
        # A Test* name bound to TestCase itself denotes unittest's
        # class (the assignment is recorded as a TestCase alias and
        # subclasses resolve through it) — pure-unittest modules
        # keep byte-identical argv (RC2).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_case_alias.py",
                "import unittest\n"
                "\n"
                "\n"
                "TestBase = unittest.TestCase\n"
                "\n"
                "\n"
                "class Unit(TestBase):\n"
                "    def test_unit(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertIn("test_case_alias", commands[0].argv)

    def _write_unpack_fixture(self, root: Path, assignment: str):
        write(
            root,
            "shared.py",
            "import unittest\n"
            "\n"
            "\n"
            "class SharedCase(unittest.TestCase):\n"
            "    pass\n",
        )
        write(
            root,
            "test_unpacked.py",
            "from shared import SharedCase\n"
            "\n"
            "\n"
            "class Helper:\n"
            "    def test_bad(self):\n"
            "        pass\n"
            "\n"
            "\n"
            "class Other:\n"
            "    def test_other(self):\n"
            "        pass\n"
            "\n"
            "\n"
            f"{assignment}\n"
            "\n"
            "\n"
            "class Unit(SharedCase):\n"
            "    def test_unit(self):\n"
            "        pass\n",
        )

    def test_unpacked_assignment_bound_test_classes_keep_pytest_leg(
        self,
    ):
        # Follow-on to round 9 (boundary recorded in its report):
        # an unpacking assignment — `TestA, TestB = Helper,
        # Other` — binds each Test* name to its own value
        # element, and pytest collects both classes; but the
        # whole-value rule saw a single Tuple value, which sits
        # in the provably-non-callable set as a literal display,
        # so neither name triggered the pytest leg and the module
        # went unittest-only beside its sibling TestCase class.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root, "TestA, TestB = Helper, Other"
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_unpacked", commands[0].argv)

    def test_unpacked_assignment_judges_each_element(self):
        # Per-element judgment: a collectable name paired with a
        # class triggers for its own name; a collectable name
        # paired with literal data does not trigger for its own
        # name — the pairing, not the tuple as a whole, decides.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root, "TestA, test_data = Helper, 42"
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root, "test_data, TestTable = 42, {'a': 1}"
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])

    def test_unpacked_literal_assignment_does_not_trigger_pytest(
        self,
    ):
        # Guard: unpacking literal data binds no callables —
        # `test_a, test_b = 1, 2` stays unittest-only (each
        # element is provably non-callable for its own name).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root, "test_a, test_b = 1, 2"
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])

    def test_unpacked_arity_mismatch_uses_whole_value_rule(self):
        # Ruling: where an unpacking level has no one-to-one
        # correspondence — arity mismatch here, a starred
        # element likewise — that level's names fall back to
        # the whole-value rule against that level's value; a
        # tuple display is literal data, so nothing triggers.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root, "TestA, TestB = (Helper,)"
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])

    def test_deselected_is_not_counted_as_collected(self):
        # Judge rider (correctness P2-B): deselected tests were
        # FILTERED OUT by the runner; counting them inflates the
        # collected total the gate relies on.
        count = mechanical_verify._count_collected(
            "pytest", "1 passed, 2 deselected in 0.10s", ""
        )
        self.assertEqual(count, 1)


POLICY_DATA = Path(__file__).resolve().parent.parent / "policy.data"


def _env_scrub_fragments() -> tuple[str, ...]:
    """Independently parse the [env-scrub] section of the repo policy.

    Tests derive fragment-dependent names from the policy file itself
    (never from a hard-coded fragment list), so a policy edit that
    changes the fragments changes the fixtures with it.
    """
    fragments = []
    section = None
    for raw in POLICY_DATA.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            section = line[1:-1]
            continue
        if section == "env-scrub":
            fragments.append(line)
    return tuple(fragments)


class EnvScrubTests(unittest.TestCase):
    def test_policy_env_scrub_reads_repo_policy_fragments(self):
        expected = _env_scrub_fragments()
        self.assertTrue(expected)
        self.assertEqual(
            mechanical_verify.policy_env_scrub(POLICY_DATA), expected
        )

    def test_policy_env_scrub_reads_only_the_env_scrub_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = write(
                Path(tmp),
                "policy.data",
                "# comment\n"
                "[sensitive-paths]\n"
                "*/.ssh\n"
                "NOT_A_FRAGMENT\n"
                "\n"
                "[env-scrub]\n"
                "ALPHA\n"
                "# another comment\n"
                "BETA\n",
            )
            self.assertEqual(
                mechanical_verify.policy_env_scrub(policy),
                ("ALPHA", "BETA"),
            )

    def test_policy_env_scrub_missing_file_returns_no_fragments(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                mechanical_verify.policy_env_scrub(Path(tmp) / "absent.data"),
                (),
            )

    def test_build_run_env_scrubs_every_fragment_case_insensitively(self):
        for fragment in _env_scrub_fragments():
            name = f"AEP_TEST_{fragment.upper()}_MARKER"
            for variant in (name, name.lower()):
                with self.subTest(variant=variant):
                    with mock.patch.dict(
                        os.environ,
                        {variant: "v", "AEP_TEST_PLAIN_KEEP": "v"},
                    ):
                        env = mechanical_verify.build_run_env(POLICY_DATA)
                    self.assertNotIn(variant, env)
                    self.assertIn("AEP_TEST_PLAIN_KEEP", env)

    def test_build_run_env_auth_boundary_rows(self):
        # lane-coord's name_is_sensitive truth table: an AUTH occurrence
        # is exempt when preceded by SSH_ (SSH_AUTH_SOCK) or followed
        # by OR + '_'/end (GIT_AUTHOR_*, ...AUTHOR); AUTHORITY's AUTH
        # is followed by ORI... and is NOT exempt.
        rows = {
            "SSH_AUTH_SOCK": True,
            "GIT_AUTHOR_NAME": True,
            "GIT_AUTHOR_EMAIL": True,
            "SOME_AUTHOR": True,
            "AEP_TEST_AUTHORITY": False,
            "AUTH": False,
            "SSH_AUTH_SOCK_AUTH": False,
        }
        for name, survives in rows.items():
            with self.subTest(name=name):
                with mock.patch.dict(os.environ, {name: "v"}):
                    env = mechanical_verify.build_run_env(POLICY_DATA)
                self.assertEqual(name in env, survives)

    def test_build_run_env_full_env_opt_out_keeps_sentinel(self):
        fragment = _env_scrub_fragments()[0]
        name = f"AEP_TEST_{fragment.upper()}_SENTINEL"
        with mock.patch.dict(
            os.environ, {name: "sentinel", "AEP_VERIFY_FULL_ENV": "1"}
        ):
            env = mechanical_verify.build_run_env(POLICY_DATA)
        self.assertEqual(env.get(name), "sentinel")

    def test_build_run_env_missing_policy_keeps_everything(self):
        fragment = _env_scrub_fragments()[0]
        name = f"AEP_TEST_{fragment.upper()}_SENTINEL"
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {name: "sentinel"}):
                env = mechanical_verify.build_run_env(
                    Path(tmp) / "absent.data"
                )
        self.assertEqual(env.get(name), "sentinel")

    def test_run_env_mode_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "absent.data"
            self.assertEqual(
                mechanical_verify.run_env_mode(missing),
                "unscrubbed (no policy)",
            )
            self.assertEqual(
                mechanical_verify.run_env_mode(POLICY_DATA), "scrubbed"
            )
            with mock.patch.dict(os.environ, {"AEP_VERIFY_FULL_ENV": "1"}):
                self.assertEqual(
                    mechanical_verify.run_env_mode(POLICY_DATA),
                    "full (AEP_VERIFY_FULL_ENV)",
                )

    def test_policy_existing_but_invalid_raises(self):
        # Bucket A3 (panel ENV-P1): an existing policy file that
        # cannot be honored — empty [env-scrub], a misspelled section
        # header, content before any section, an unreadable path —
        # is a hard error under the same grammar lane-coord enforces,
        # never a silent empty fragment list.
        variants = {
            "empty-env-scrub": (
                "[sensitive-paths]\n*/.ssh\n[env-scrub]\n"
            ),
            "misspelled-section": (
                "[sensitive-paths]\n*/.ssh\n[env-scrubb]\nKEY\n"
            ),
            "pre-section-content": (
                "KEY\n[sensitive-paths]\n*/.ssh\n[env-scrub]\nKEY\n"
            ),
            "empty-file": "",
        }
        for name, content in variants.items():
            with self.subTest(variant=name):
                with tempfile.TemporaryDirectory() as tmp:
                    policy = write(Path(tmp), "policy.data", content)
                    with self.assertRaises(
                        mechanical_verify.PolicyError
                    ):
                        mechanical_verify.policy_env_scrub(policy)
                    with self.assertRaises(
                        mechanical_verify.PolicyError
                    ):
                        mechanical_verify.build_run_env(policy)
                    with self.assertRaises(
                        mechanical_verify.PolicyError
                    ):
                        mechanical_verify.run_env_mode(policy)
        with tempfile.TemporaryDirectory() as tmp:
            # A directory as the policy path is unreadable as a file.
            with self.assertRaises(mechanical_verify.PolicyError):
                mechanical_verify.policy_env_scrub(Path(tmp))

    def test_cli_invalid_policy_refuses_before_any_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "Makefile", "test:\n\ttouch ran.marker\n\ttrue\n")
            policy = write(
                base,
                "policy.data",
                "[sensitive-paths]\n*/.ssh\n[env-scrub]\n",
            )
            receipts = base / "receipts.jsonl"
            env = dict(os.environ)
            env.pop("AEP_VERIFY_FULL_ENV", None)
            env["AEP_POLICY_DATA"] = str(policy)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "verify",
                    "--root",
                    str(root),
                    "--task",
                    "badpolicy",
                    "--receipts",
                    str(receipts),
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("policy data invalid", proc.stdout)
            # Fail closed BEFORE any command executes: the Makefile's
            # marker side effect never happened, and no run-start
            # record claimed a scrub.
            self.assertFalse((root / "ran.marker").exists())
            self.assertFalse(receipts.exists())

    def test_run_verification_scrubs_sentinel_end_to_end(self):
        fragment = _env_scrub_fragments()[0]
        name = f"AEP_TEST_{fragment.upper()}_SENTINEL"
        script = (
            "import os, sys; "
            f"sys.stdout.write(os.environ.get({name!r}, 'ABSENT'))"
        )
        command = VerificationCommand(
            "t", "t", (sys.executable, "-c", script)
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.dict(
                os.environ,
                {name: "sentinel-value", "AEP_POLICY_DATA": str(POLICY_DATA)},
            ):
                result = run_verification(root, command)
                self.assertEqual(result.exit_code, 0, result.stderr)
                self.assertEqual(result.stdout, "ABSENT")
                with mock.patch.dict(
                    os.environ, {"AEP_VERIFY_FULL_ENV": "1"}
                ):
                    opted = run_verification(root, command)
                self.assertEqual(opted.exit_code, 0, opted.stderr)
                self.assertEqual(opted.stdout, "sentinel-value")

    def test_cli_run_start_record_states_env_mode(self):
        variants = (
            ("unscrubbed (no policy)", {"AEP_POLICY_DATA": "ABSENT_FILE"}),
            ("scrubbed", {}),
            ("full (AEP_VERIFY_FULL_ENV)", {"AEP_VERIFY_FULL_ENV": "1"}),
        )
        for expected, overrides in variants:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    root = base / "root"
                    root.mkdir()
                    write(root, "Makefile", "test:\n\ttrue\n")
                    receipts = base / "receipts.jsonl"
                    env = dict(os.environ)
                    env.pop("AEP_POLICY_DATA", None)
                    env.pop("AEP_VERIFY_FULL_ENV", None)
                    for key, value in overrides.items():
                        if value == "ABSENT_FILE":
                            env[key] = str(base / "absent.data")
                        else:
                            env[key] = value
                    subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "verify",
                            "--root",
                            str(root),
                            "--task",
                            "envmode",
                            "--receipts",
                            str(receipts),
                        ],
                        capture_output=True,
                        text=True,
                        env=env,
                        timeout=60,
                    )
                    first = json.loads(
                        receipts.read_text(encoding="utf-8").splitlines()[0]
                    )
                    self.assertEqual(first["kind"], "run-start")
                    self.assertEqual(first["env"], expected)


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

    def test_verify_receipts_parent_missing_is_clean_refusal(self):
        # Post-change validation probe: --receipts pointing into a
        # nonexistent directory died with an unhandled
        # FileNotFoundError traceback from the first append — the
        # verifier creates the receipts FILE on append but never its
        # parent directories. A caller error like this is a named,
        # fail-closed refusal (exit 1, like the verifier's other
        # precondition failures), and the directory must NOT be
        # silently created.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "Makefile", "test:\n\ttrue\n")
            missing_dir = root / "no-such-dir"
            receipts = missing_dir / "receipts.jsonl"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "verify",
                    "--root",
                    str(root),
                    "--task",
                    "t",
                    "--receipts",
                    str(receipts),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("VERIFY: FAIL receipts directory", proc.stdout)
            self.assertIn(str(missing_dir), proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertNotIn("VERIFY: make-test", proc.stdout)
            self.assertFalse(missing_dir.exists())

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
