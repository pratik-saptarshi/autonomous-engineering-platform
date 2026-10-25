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
                commands[1].argv, ("python3", "-m", "pytest", "-q")
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
                check_rc = mechanical_verify.check_receipts(receipts, "t")
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
