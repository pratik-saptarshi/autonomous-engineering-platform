import contextlib
import hashlib
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
    VerificationResult,
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


def _fake_pytest_command(
    transcript: str, report_count: int | None, exit_code: int = 0
) -> VerificationCommand:
    """A stand-in pytest leg producing BOTH evidence channels a
    real run produces (issue #53): it prints *transcript* and —
    unless *report_count* is None — writes a junitxml report with
    that many testcases to the --junitxml path run_verification
    appends to the executed argv. A fake that only prints a
    transcript simulates a suppressed report channel, not a real
    run: since the round-2 fix such a leg's count is unproven and
    the count gate fails it, so gate-logic fixtures must write
    the report to stand for a genuine pytest leg.
    """
    lines = [f"print({transcript!r})"]
    if report_count is not None:
        body = (
            '<testsuites><testsuite tests="%d">' % report_count
            + "<testcase classname='x' name='y'/>" * report_count
            + "</testsuite></testsuites>"
        )
        lines += [
            "import sys",
            "_p = next(a.split('=', 1)[1] for a in sys.argv"
            " if a.startswith('--junitxml='))",
            f"open(_p, 'w').write({body!r})",
        ]
    if exit_code:
        lines += ["import sys", f"sys.exit({exit_code})"]
    return VerificationCommand(
        "pytest",
        "Python tests",
        (sys.executable, "-c", "\n".join(lines)),
    )


def _pytest_on_path() -> bool:
    # Local twin of _path_pytest_available (defined later in the
    # file) for the early DiscoveryTests class: the verifier's
    # pytest command is literal `python3 -m pytest`.
    try:
        proc = subprocess.run(
            ["python3", "-m", "pytest", "--version"],
            capture_output=True,
            timeout=30,
        )
    except OSError:
        return False
    return proc.returncode == 0


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
            resolved = str(root.resolve())
            self.assertEqual(
                commands[1].argv,
                ("python3", "-m", "pytest", "-v")
                + (
                    "-c",
                    os.devnull,
                    "--rootdir",
                    resolved,
                    "--confcutdir",
                    resolved,
                ),
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

    # Issue #61: a symlinked root-level test file is not
    # classified or scheduled by either runner leg — the tree
    # binding records only the link's target string, never the
    # target's contents, so external content must never be read
    # for classification or named to a runner.

    def test_symlinked_test_file_with_unittest_content_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(
                base,
                "external/test_ext.py",
                "import unittest\n\n\n"
                "class Ext(unittest.TestCase):\n"
                "    def test_ext(self):\n"
                "        pass\n",
            )
            os.symlink(external, root / "test_ext.py")
            self.assertEqual(discover_verification_commands(root), ())

    def test_symlinked_suffix_test_file_with_unittest_content_discovers_nothing(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(
                base,
                "external/ext.py",
                "from unittest import TestCase\n\n\n"
                "class Ext(TestCase):\n"
                "    def test_ext(self):\n"
                "        pass\n",
            )
            os.symlink(external, root / "ext_test.py")
            self.assertEqual(discover_verification_commands(root), ())

    def test_symlinked_test_file_with_pytest_content_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(
                base, "external/test_ext.py", "def test_a():\n    assert True\n"
            )
            os.symlink(external, root / "test_ext.py")
            self.assertEqual(discover_verification_commands(root), ())

    def test_symlinked_suffix_test_file_with_pytest_content_discovers_nothing(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(
                base, "external/plain.py", "def test_plain():\n    assert True\n"
            )
            os.symlink(external, root / "plain_test.py")
            self.assertEqual(discover_verification_commands(root), ())

    def test_symlinked_test_file_does_not_steer_mixed_partition(self):
        # A real module's routing is unchanged by a symlinked
        # sibling: the link contributes no classification of its
        # own in either direction. In the pytest direction the
        # observable result is now [] rather than the bare leg:
        # issue #62 disqualifies that leg whenever a symlinked
        # collectable file sits in its collection scope, because
        # the leg collects by traversal, not by name — the link
        # still classifies nothing, but the leg it would share
        # the run with cannot be sealed over it.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(
                root,
                "test_ok.py",
                "import unittest\n\n\n"
                "class Ok(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            external = write(
                base, "external/test_ext.py", "def test_a():\n    assert True\n"
            )
            os.symlink(external, root / "test_ext.py")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertEqual(
                commands[0].argv,
                ("python3", "-m", "unittest", "-v", "test_ok"),
            )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "test_ok.py", "def test_ok():\n    assert True\n")
            external = write(
                base,
                "external/ext.py",
                "import unittest\n\n\n"
                "class Ext(unittest.TestCase):\n"
                "    def test_ext(self):\n"
                "        pass\n",
            )
            os.symlink(external, root / "ext_test.py")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], [])

    def test_symlinked_test_file_with_in_tree_target_discovers_nothing(self):
        # The rule is on the entry, not the target's location: a
        # link to a real file inside the tree is still a link,
        # and the target does not classify under the link's name
        # (it does not match a test pattern under its own name).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "helper_mod.py",
                "import unittest\n\n\n"
                "class Helper(unittest.TestCase):\n"
                "    def test_helper(self):\n"
                "        pass\n",
            )
            os.symlink(root / "helper_mod.py", root / "test_link.py")
            self.assertEqual(discover_verification_commands(root), ())

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

    # Issues #63/#64: a symlinked marker or pytest config does not
    # schedule, gate, or steer its leg — the tree binding records
    # only the link's target string, never the target's contents,
    # so external content must never constitute a verification leg.

    def test_symlinked_go_mod_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(base, "external/go.mod", "module x\n")
            os.symlink(external, root / "go.mod")
            self.assertEqual(discover_verification_commands(root), ())

    def test_symlinked_cargo_toml_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(base, "external/Cargo.toml", "[package]\n")
            os.symlink(external, root / "Cargo.toml")
            self.assertEqual(discover_verification_commands(root), ())

    def test_symlinked_package_json_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(
                base,
                "external/package.json",
                json.dumps({"scripts": {"test": "node --test"}}),
            )
            os.symlink(external, root / "package.json")
            self.assertEqual(discover_verification_commands(root), ())

    def test_symlinked_makefile_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(base, "external/Makefile", "test:\n\ttrue\n")
            os.symlink(external, root / "Makefile")
            self.assertEqual(discover_verification_commands(root), ())

    def test_symlinked_markdownlint_config_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(base, "external/.markdownlint.yaml", "default: true\n")
            os.symlink(external, root / ".markdownlint.yaml")
            bin_dir = base / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "markdownlint-cli2"
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
            env_path = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
            with mock.patch.dict(os.environ, {"PATH": env_path}):
                commands = discover_verification_commands(root)
            self.assertEqual(commands, ())

    def test_symlinked_pytest_configs_discover_nothing(self):
        for name in ("pytest.ini", "pyproject.toml", "setup.cfg"):
            with self.subTest(config=name):
                with tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    root = base / "root"
                    root.mkdir()
                    external = write(base, f"external/{name}", "[pytest]\n")
                    os.symlink(external, root / name)
                    ids = [
                        c.id for c in discover_verification_commands(root)
                    ]
                    self.assertNotIn("pytest", ids)

    def test_marker_policy_applies_below_a_symlinked_root(self):
        # The caller-selected root may itself be a symlink (it is
        # the boundary the binding canonicalizes); the policy
        # applies to entries below it, so a real marker inside a
        # root reached through a link still schedules its leg.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "go.mod", "module x\n")
            root_link = base / "root_link"
            os.symlink(root, root_link)
            ids = [c.id for c in discover_verification_commands(root_link)]
            self.assertEqual(ids, ["go-test"])

    def test_symlinked_pytest_config_insulates_tests_dir_leg(self):
        # The leg is scheduled by the real tests/ directory, but the
        # config pytest would read is a symlink: the command must
        # pin an empty config so the unbound file cannot steer.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            external = write(base, "external/pytest.ini", "[pytest]\n")
            os.symlink(external, root / "pytest.ini")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertIn("-c", commands[0].argv)
            self.assertIn(os.devnull, commands[0].argv)

    def test_real_pytest_ini_wins_over_symlinked_setup_cfg(self):
        # pytest selects the real pytest.ini; the symlinked
        # setup.cfg is never read. The leg is not insulated
        # against the real config: the pinned argv names it, so
        # it steers exactly as the gates judged it (Task 15).
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "pytest.ini", "[pytest]\n")
            external = write(base, "external/setup.cfg", "[tool:pytest]\n")
            os.symlink(external, root / "setup.cfg")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            # The pin names the selected real config (Task 15's
            # literal argv shape is pinned in RootBoundaryTests);
            # the leg is insulated only against the symlink.
            argv = commands[0].argv
            self.assertEqual(
                argv[argv.index("-c") + 1],
                str((root / "pytest.ini").resolve()),
            )
            self.assertNotIn(os.devnull, argv)

    def test_unselected_real_pyproject_leaves_symlinked_setup_cfg_candidate(
        self,
    ):
        # A real pyproject.toml without [tool.pytest.ini_options]
        # is not pytest's inifile, so selection falls to setup.cfg;
        # that candidate is a symlink, so the leg is insulated.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "pyproject.toml", "[project]\nname = 'x'\n")
            external = write(base, "external/setup.cfg", "[tool:pytest]\n")
            os.symlink(external, root / "setup.cfg")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertIn("-c", commands[0].argv)

    def test_selected_real_pyproject_wins_over_symlinked_setup_cfg(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(
                root,
                "pyproject.toml",
                "[tool.pytest.ini_options]\n",
            )
            external = write(base, "external/setup.cfg", "[tool:pytest]\n")
            os.symlink(external, root / "setup.cfg")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            argv = commands[0].argv
            self.assertEqual(
                argv[argv.index("-c") + 1],
                str((root / "pyproject.toml").resolve()),
            )
            self.assertNotIn(os.devnull, argv)

    # Round 2 (#63, #64): the candidate set is pytest's FULL
    # inifile list — pytest.toml, .pytest.toml, pytest.ini,
    # .pytest.ini, pyproject.toml, tox.ini, setup.cfg, in the
    # precedence order of _pytest.config.findpaths.locate_config
    # (pytest 9). Round 1 covered only pytest.ini, pyproject.toml,
    # setup.cfg; symlinked pytest.toml and tox.ini demonstrably
    # steered a sealed run through the gap.

    _ADDED_CONFIG_CONTENTS = {
        "pytest.toml": "[pytest]\n",
        ".pytest.toml": "[pytest]\n",
        ".pytest.ini": "[pytest]\n",
        "tox.ini": "[pytest]\n",
    }

    def test_symlinked_added_pytest_configs_discover_nothing(self):
        for name, text in self._ADDED_CONFIG_CONTENTS.items():
            with self.subTest(config=name):
                with tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    root = base / "root"
                    root.mkdir()
                    external = write(base, f"external/{name}", text)
                    os.symlink(external, root / name)
                    ids = [
                        c.id for c in discover_verification_commands(root)
                    ]
                    self.assertNotIn("pytest", ids)

    def test_real_added_pytest_configs_trigger_the_leg(self):
        for name, text in self._ADDED_CONFIG_CONTENTS.items():
            with self.subTest(config=name):
                with tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    root = base / "root"
                    root.mkdir()
                    write(root, name, text)
                    ids = [
                        c.id for c in discover_verification_commands(root)
                    ]
                    self.assertEqual(ids, ["pytest"])

    def test_symlinked_added_pytest_configs_insulate_tests_dir_leg(
        self,
    ):
        for name, text in self._ADDED_CONFIG_CONTENTS.items():
            with self.subTest(config=name):
                with tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    root = base / "root"
                    (root / "tests").mkdir(parents=True)
                    external = write(base, f"external/{name}", text)
                    os.symlink(external, root / name)
                    commands = discover_verification_commands(root)
                    self.assertEqual([c.id for c in commands], ["pytest"])
                    self.assertIn("-c", commands[0].argv)
                    self.assertIn(os.devnull, commands[0].argv)

    def test_real_added_pytest_configs_behave_as_before(self):
        # Real files with qualifying content are the config the
        # leg reads: the pinned argv names the file itself
        # (Task 15), so its steering is exactly what the gates
        # judged — the leg is insulated against nothing here.
        for name, text in self._ADDED_CONFIG_CONTENTS.items():
            with self.subTest(config=name):
                with tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    root = base / "root"
                    (root / "tests").mkdir(parents=True)
                    write(root, name, text)
                    commands = discover_verification_commands(root)
                    self.assertEqual([c.id for c in commands], ["pytest"])
                    argv = commands[0].argv
                    self.assertEqual(
                        argv[argv.index("-c") + 1],
                        str((root / name).resolve()),
                    )
                    self.assertNotIn(os.devnull, argv)

    def test_real_pytest_toml_wins_over_symlinked_pytest_ini(self):
        # pytest.toml outranks pytest.ini and is a config source
        # even when empty; the real file is selected, so the
        # symlinked pytest.ini is never read and the leg is NOT
        # insulated.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "pytest.toml", "")
            external = write(base, "external/pytest.ini", "[pytest]\n")
            os.symlink(external, root / "pytest.ini")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            argv = commands[0].argv
            self.assertEqual(
                argv[argv.index("-c") + 1],
                str((root / "pytest.toml").resolve()),
            )
            self.assertNotIn(os.devnull, argv)

    def test_real_tox_ini_wins_over_symlinked_setup_cfg(self):
        # A real tox.ini holding [pytest] outranks setup.cfg; the
        # symlinked setup.cfg is never read.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "tox.ini", "[pytest]\n")
            external = write(base, "external/setup.cfg", "[tool:pytest]\n")
            os.symlink(external, root / "setup.cfg")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            argv = commands[0].argv
            self.assertEqual(
                argv[argv.index("-c") + 1],
                str((root / "tox.ini").resolve()),
            )
            self.assertNotIn(os.devnull, argv)

    def test_sectionless_tox_ini_leaves_symlinked_setup_cfg_candidate(
        self,
    ):
        # A tox.ini without a [pytest] section is not pytest's
        # inifile (pytest 9 findpaths), so selection falls through
        # to setup.cfg; that candidate is a symlink, so the leg is
        # insulated.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "tox.ini", "[tox]\n")
            external = write(base, "external/setup.cfg", "[tool:pytest]\n")
            os.symlink(external, root / "setup.cfg")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertIn("-c", commands[0].argv)
            self.assertIn(os.devnull, commands[0].argv)

    def test_real_pyproject_tool_pytest_table_wins_over_symlinked_setup_cfg(
        self,
    ):
        # A [tool.pytest] table with keys of its own qualifies
        # pyproject.toml in TOML mode (pytest 9 findpaths), not
        # only [tool.pytest.ini_options]: the real file is
        # selected and the symlinked setup.cfg is never read.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(
                root,
                "pyproject.toml",
                '[tool.pytest]\nminversion = "6.0"\n',
            )
            external = write(base, "external/setup.cfg", "[tool:pytest]\n")
            os.symlink(external, root / "setup.cfg")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            argv = commands[0].argv
            self.assertEqual(
                argv[argv.index("-c") + 1],
                str((root / "pyproject.toml").resolve()),
            )
            self.assertNotIn(os.devnull, argv)

    def test_empty_tool_pytest_table_falls_through_to_symlinked_setup_cfg(
        self,
    ):
        # An empty [tool.pytest] table (no keys, no ini_options)
        # does not qualify during pytest's scan, so selection
        # falls through to the symlinked setup.cfg and the leg
        # is insulated.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "pyproject.toml", "[tool.pytest]\n")
            external = write(base, "external/setup.cfg", "[tool:pytest]\n")
            os.symlink(external, root / "setup.cfg")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertIn("-c", commands[0].argv)
            self.assertIn(os.devnull, commands[0].argv)

    def test_pytest_config_selected_content_conditions(self):
        # tox.ini counts only with a [pytest] section and
        # setup.cfg only with a [tool:pytest] section (pytest 9
        # findpaths); sectionless files are not pytest's inifile.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "tox.ini", "[tox]\n")
            self.assertIsNone(
                mechanical_verify._pytest_config_selected(root)
            )
            write(root, "tox.ini", "[pytest]\n")
            self.assertEqual(
                mechanical_verify._pytest_config_selected(root),
                root / "tox.ini",
            )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "setup.cfg", "[build]\n")
            self.assertIsNone(
                mechanical_verify._pytest_config_selected(root)
            )
            write(root, "setup.cfg", "[tool:pytest]\n")
            self.assertEqual(
                mechanical_verify._pytest_config_selected(root),
                root / "setup.cfg",
            )

    # Round 3 (#63, #64): the per-name content conditions are
    # judged on PARSED structure (tomllib / configparser),
    # never on raw text. Round 2 matched the section names as
    # substrings, so a header appearing in a COMMENT made the
    # walk stop one candidate early: it selected the real file,
    # left the argv unpinned, and real pytest — which parses —
    # fell through to a symlinked setup.cfg and read it through
    # the link (review fixtures A and B, both demonstrated
    # end-to-end).

    def test_pytest_config_content_conditions_use_parsed_structure(
        self,
    ):
        # Headers in comments or string values are not sections
        # or tables; real ones still qualify, in both formats.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "tox.ini", "# [pytest]\n[testenv]\n")
            self.assertIsNone(
                mechanical_verify._pytest_config_selected(root)
            )
            write(
                root,
                "tox.ini",
                '[testenv]\ncommands = echo "[pytest]"\n',
            )
            self.assertIsNone(
                mechanical_verify._pytest_config_selected(root)
            )
            write(
                root,
                "tox.ini",
                "[testenv]\ncommands =\n    echo hi\n    [pytest]\n",
            )
            self.assertIsNone(
                mechanical_verify._pytest_config_selected(root)
            )
            write(root, "tox.ini", "[pytest]\n")
            self.assertEqual(
                mechanical_verify._pytest_config_selected(root),
                root / "tox.ini",
            )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pyproject.toml",
                '# [tool.pytest.ini_options]\n[project]\nname = "x"\n',
            )
            self.assertIsNone(
                mechanical_verify._pytest_config_selected(root)
            )
            write(
                root,
                "pyproject.toml",
                '[project]\ndescription = "[tool.pytest.ini_options]"\n',
            )
            self.assertIsNone(
                mechanical_verify._pytest_config_selected(root)
            )
            write(
                root, "pyproject.toml", "[tool.pytest.ini_options]\n"
            )
            self.assertEqual(
                mechanical_verify._pytest_config_selected(root),
                root / "pyproject.toml",
            )
            write(
                root,
                "pyproject.toml",
                '[tool]\npytest = { minversion = "6.0" }\n',
            )
            self.assertEqual(
                mechanical_verify._pytest_config_selected(root),
                root / "pyproject.toml",
            )
            write(root, "pyproject.toml", "[tool.pytest\nbroken = \n")
            self.assertIsNone(
                mechanical_verify._pytest_config_selected(root)
            )

    def test_commented_tox_ini_section_leaves_symlinked_setup_cfg_candidate(
        self,
    ):
        # Review fixture A: the only [pytest] in tox.ini is a
        # comment, so tox.ini does not qualify; selection falls
        # through to the symlinked setup.cfg and the leg is
        # insulated.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "tox.ini", "# [pytest]\n\n[testenv]\ndeps = pytest\n")
            external = write(base, "external/setup.cfg", "[tool:pytest]\n")
            os.symlink(external, root / "setup.cfg")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertIn("-c", commands[0].argv)
            self.assertIn(os.devnull, commands[0].argv)

    def test_commented_pyproject_ini_options_leaves_symlinked_setup_cfg_candidate(
        self,
    ):
        # Review fixture B: the only
        # [tool.pytest.ini_options] in pyproject.toml is a
        # comment; the symlinked setup.cfg is the selected
        # candidate and the leg is insulated.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(
                root,
                "pyproject.toml",
                '# [tool.pytest.ini_options]\n[project]\nname = "x"\n',
            )
            external = write(base, "external/setup.cfg", "[tool:pytest]\n")
            os.symlink(external, root / "setup.cfg")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertIn("-c", commands[0].argv)
            self.assertIn(os.devnull, commands[0].argv)

    def test_unparseable_pyproject_falls_through_to_symlinked_setup_cfg(
        self,
    ):
        # An unparseable candidate does not qualify (real
        # pytest would abort on it rather than use it), so the
        # walk continues to the symlinked setup.cfg and
        # insulates the leg.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "pyproject.toml", "[tool.pytest\nbroken = \n")
            external = write(base, "external/setup.cfg", "[tool:pytest]\n")
            os.symlink(external, root / "setup.cfg")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertIn("-c", commands[0].argv)
            self.assertIn(os.devnull, commands[0].argv)

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_commented_tox_ini_cannot_mask_symlinked_setup_cfg_steering(
        self,
    ):
        # Review fixture A, end to end: pre-fix the walk
        # selected the comment-fooled tox.ini, left the argv
        # unpinned, and pytest fell through to the symlinked
        # setup.cfg — the foreign suite ran and passed.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "tests/test_ok.py", "def test_ok():\n    assert True\n")
            steered = base / "external" / "steered"
            write(
                steered,
                "test_steered.py",
                "def test_steered():\n    assert True\n",
            )
            write(
                base,
                "external/setup.cfg",
                f"[tool:pytest]\ntestpaths = {steered}\n",
            )
            os.symlink(base / "external" / "setup.cfg", root / "setup.cfg")
            write(root, "tox.ini", "# [pytest]\n\n[testenv]\ndeps = pytest\n")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            result = run_verification(root, commands[0])
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 1)
            self.assertIn("test_ok", result.stdout)
            self.assertNotIn("test_steered", result.stdout)

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_commented_pyproject_cannot_mask_symlinked_setup_cfg_steering(
        self,
    ):
        # Review fixture B, end to end: the comment-fooled
        # pyproject.toml masked the symlinked setup.cfg the
        # same way.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "tests/test_ok.py", "def test_ok():\n    assert True\n")
            steered = base / "external" / "steered"
            write(
                steered,
                "test_steered.py",
                "def test_steered():\n    assert True\n",
            )
            write(
                base,
                "external/setup.cfg",
                f"[tool:pytest]\ntestpaths = {steered}\n",
            )
            os.symlink(base / "external" / "setup.cfg", root / "setup.cfg")
            write(
                root,
                "pyproject.toml",
                '# [tool.pytest.ini_options]\n[project]\nname = "x"\n',
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            result = run_verification(root, commands[0])
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 1)
            self.assertIn("test_ok", result.stdout)
            self.assertNotIn("test_steered", result.stdout)

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_symlinked_pytest_toml_cannot_steer_collection(self):
        # The reviewer's round-2 fixture: pytest.toml outranks
        # every round-1 name, so a symlinked one steered the
        # sealed run to a foreign suite. After the fix the leg
        # (scheduled by the real tests/ directory) collects only
        # the in-tree test.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "tests/test_ok.py", "def test_ok():\n    assert True\n")
            steered = base / "external" / "steered"
            write(
                steered,
                "test_steered.py",
                "def test_steered():\n    assert True\n",
            )
            write(
                base,
                "external/pytest.toml",
                f'[pytest]\ntestpaths = ["{steered}"]\n',
            )
            os.symlink(base / "external" / "pytest.toml", root / "pytest.toml")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            result = run_verification(root, commands[0])
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 1)
            self.assertIn("test_ok", result.stdout)
            self.assertNotIn("test_steered", result.stdout)

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_symlinked_tox_ini_cannot_steer_collection(self):
        # The reviewer's other round-2 fixture: a symlinked
        # tox.ini holding [pytest] + testpaths steered the sealed
        # run because the round-1 walk never considered the name.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "tests/test_ok.py", "def test_ok():\n    assert True\n")
            steered = base / "external" / "steered"
            write(
                steered,
                "test_steered.py",
                "def test_steered():\n    assert True\n",
            )
            write(
                base,
                "external/tox.ini",
                f"[pytest]\ntestpaths = {steered}\n",
            )
            os.symlink(base / "external" / "tox.ini", root / "tox.ini")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            result = run_verification(root, commands[0])
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 1)
            self.assertIn("test_ok", result.stdout)
            self.assertNotIn("test_steered", result.stdout)

    @unittest.skipUnless(shutil.which("make"), "no make on PATH")
    def test_symlinked_makefile_test_recipe_never_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            marker = base / "make-ran.marker"
            external = write(
                base, "external/Makefile", f"test:\n\ttouch {marker}\n"
            )
            os.symlink(external, root / "Makefile")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], [])
            if commands:
                run_all(root, commands, mem_available_kb=lambda: 10**9)
            self.assertFalse(marker.exists())

    @unittest.skipUnless(shutil.which("npm"), "no npm on PATH")
    def test_symlinked_package_json_test_script_never_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            marker = base / "npm-ran.marker"
            external = write(
                base,
                "external/package.json",
                json.dumps({"scripts": {"test": f"touch {marker}"}}),
            )
            os.symlink(external, root / "package.json")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], [])
            if commands:
                run_all(root, commands, mem_available_kb=lambda: 10**9)
            self.assertFalse(marker.exists())

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_symlinked_pytest_config_cannot_steer_collection(self):
        # The external config redirects collection to a foreign
        # suite via testpaths. Before the fix the sealed run
        # collects the foreign test; after, the leg (scheduled by
        # the real tests/ directory) collects only the in-tree
        # test — the unbound config defines nothing.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            write(root, "tests/test_ok.py", "def test_ok():\n    assert True\n")
            steered = base / "external" / "steered"
            write(
                steered,
                "test_steered.py",
                "def test_steered():\n    assert True\n",
            )
            write(
                base,
                "external/pytest.ini",
                f"[pytest]\ntestpaths = {steered}\n",
            )
            os.symlink(base / "external" / "pytest.ini", root / "pytest.ini")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            result = run_verification(root, commands[0])
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 1)
            self.assertIn("test_ok", result.stdout)
            self.assertNotIn("test_steered", result.stdout)

    # Issue #62: the bare pytest leg is disqualified when its
    # collection scope contains a symlink. Pytest collection
    # traverses linked directories and executes symlinked
    # collectable files, while the tree binding records only a
    # link's target string — so a sealed PASS must never rest on
    # content reached through a link. Directories are in scope
    # anywhere below root (the .git subtree excepted); files are
    # in scope by pytest's collection names (test_*.py,
    # *_test.py, conftest.py). Other legs are unaffected, and
    # the caller-selected root itself may remain a symlink.

    def test_symlinked_tests_directory_disqualifies_bare_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(root, "go.mod")
            external = base / "external"
            write(
                external,
                "test_ext.py",
                "def test_ext():\n    assert True\n",
            )
            os.symlink(external, root / "tests")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, ["go-test"])

    def test_symlinked_scripts_directory_disqualifies_bare_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            external = base / "external"
            write(
                external,
                "test_ext.py",
                "def test_ext():\n    assert True\n",
            )
            os.symlink(external, root / "scripts")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])

    def test_nested_symlinked_directory_disqualifies_bare_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "tests/test_local.py",
                "def test_local():\n    assert True\n",
            )
            external = base / "external"
            write(
                external,
                "test_ext.py",
                "def test_ext():\n    assert True\n",
            )
            os.symlink(external, root / "tests" / "sub")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])

    def test_symlinked_conftest_disqualifies_bare_pytest(self):
        # A conftest steers collection through its hooks; pytest
        # imports it from every directory it collects in, at the
        # root and nested alike.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "test_local.py",
                "def test_local():\n    assert True\n",
            )
            external = write(base, "external/conftest.py", "# ext\n")
            os.symlink(external, root / "conftest.py")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "tests/test_local.py",
                "def test_local():\n    assert True\n",
            )
            external = write(base, "external/conftest.py", "# ext\n")
            os.symlink(external, root / "tests" / "conftest.py")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])

    def test_symlinked_collectable_test_file_disqualifies_bare_pytest(
        self,
    ):
        # The file form of the same mechanism (Task 6 review §4):
        # the leg, once scheduled by independent evidence,
        # executes symlinked test modules through pytest's own
        # traversal — at the root and nested, under both of
        # pytest's test-file name shapes.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            external = write(
                base,
                "external/test_ext.py",
                "def test_ext():\n    assert True\n",
            )
            os.symlink(external, root / "test_link.py")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "tests/test_local.py",
                "def test_local():\n    assert True\n",
            )
            external = write(
                base,
                "external/test_ext.py",
                "def test_ext():\n    assert True\n",
            )
            os.symlink(external, root / "tests" / "test_link.py")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "tests/test_local.py",
                "def test_local():\n    assert True\n",
            )
            external = write(
                base,
                "external/plain.py",
                "def test_plain():\n    assert True\n",
            )
            os.symlink(external, root / "tests" / "plain_test.py")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])

    def test_symlinked_non_collectable_files_keep_bare_pytest(self):
        # The file rule's boundary (restated in Task 11
        # round 3): symlinks pytest would never import — a
        # non-.py name that is not a collectable name either
        # (a data file, a README) — do not disqualify the leg.
        # A symlinked .py file under ANY name does; see
        # test_symlinked_py_module_disqualifies_bare_pytest.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "tests/test_local.py",
                "def test_local():\n    assert True\n",
            )
            notes = write(base, "external/notes.txt", "data\n")
            blob = write(base, "external/blob.bin", "data\n")
            os.symlink(notes, root / "notes_link.txt")
            os.symlink(blob, root / "blob_link.bin")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, ["pytest"])

    def test_symlinked_py_module_disqualifies_bare_pytest(self):
        # Round 3 (Task 11 re-review §4): the scope walk's
        # file rule extends to every symlinked .py file,
        # whatever its name. Collection executes an aimed .py
        # file under any name (the re-review's linktest.py),
        # and a collected module imports a .py module by name
        # from a sys.path directory — prepend import mode puts
        # every collected test's directory there — so no .py
        # name is provably outside the execution scope. The
        # link is the policy object: an in-tree target
        # disqualifies exactly like an external one.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "tests/test_local.py",
                "def test_local():\n    assert True\n",
            )
            helper = write(base, "external/helper.py", "VALUE = 1\n")
            os.symlink(helper, root / "helper_link.py")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])
        # Nested, under a tools.py-style name.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "tests/test_local.py",
                "def test_local():\n    assert True\n",
            )
            helper = write(base, "external/tools.py", "VALUE = 1\n")
            os.symlink(helper, root / "tests" / "tools_link.py")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])
        # In-tree target: still the link that disqualifies.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "tests/test_local.py",
                "def test_local():\n    assert True\n",
            )
            write(root, "real_module.py", "VALUE = 1\n")
            os.symlink(root / "real_module.py", root / "module_link.py")
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertEqual(ids, [])

    def test_bare_pytest_scope_clean_below_symlinked_root(self):
        # The caller-selected root itself may be a symlink (it is
        # the boundary the binding canonicalizes); a clean scope
        # below it still schedules the leg.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "tests/test_local.py",
                "def test_local():\n    assert True\n",
            )
            root_link = base / "root_link"
            os.symlink(root, root_link)
            ids = [
                c.id for c in discover_verification_commands(root_link)
            ]
            self.assertEqual(ids, ["pytest"])

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

    def test_scripts_symlink_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            external = base / "external"
            write(external, "tests/test_real.py", "import unittest\n")
            root.mkdir()
            os.symlink(external, root / "scripts")
            self.assertEqual(discover_verification_commands(root), ())

    def test_scripts_symlink_to_inside_root_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            write(root, "elsewhere/tests/test_real.py", "import unittest\n")
            os.symlink(root / "elsewhere", root / "scripts")
            self.assertEqual(discover_verification_commands(root), ())

    def test_scripts_tests_mixed_real_and_symlinked_test_file_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            foreign = write(
                base / "external", "test_foreign.py", "import unittest\n"
            )
            tests_dir = root / "scripts" / "tests"
            write(root, "scripts/tests/test_sample.py", "import unittest\n")
            os.symlink(foreign, tests_dir / "test_foreign.py")
            self.assertEqual(discover_verification_commands(root), ())

    def test_scripts_tests_symlinked_package_dir_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            external_pkg = base / "external" / "pkg"
            write(external_pkg, "__init__.py", "")
            write(external_pkg, "test_external.py", "import unittest\n")
            write(root, "scripts/tests/test_sample.py", "import unittest\n")
            os.symlink(
                external_pkg, root / "scripts" / "tests" / "pkg"
            )
            self.assertEqual(discover_verification_commands(root), ())

    def test_scripts_tests_symlinked_nested_subpackage_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            external_sub = base / "external" / "sub"
            write(external_sub, "__init__.py", "")
            write(external_sub, "test_external.py", "import unittest\n")
            write(root, "scripts/tests/test_sample.py", "import unittest\n")
            write(root, "scripts/tests/pkg/__init__.py", "")
            os.symlink(
                external_sub, root / "scripts" / "tests" / "pkg" / "sub"
            )
            self.assertEqual(discover_verification_commands(root), ())

    def test_scripts_tests_symlinked_descendant_test_file_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            foreign = write(
                base / "external", "test_external.py", "import unittest\n"
            )
            write(root, "scripts/tests/test_sample.py", "import unittest\n")
            write(root, "scripts/tests/pkg/__init__.py", "")
            os.symlink(
                foreign, root / "scripts" / "tests" / "pkg" / "test_external.py"
            )
            self.assertEqual(discover_verification_commands(root), ())

    def test_scripts_tests_symlinked_init_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            foreign_init = write(base / "external", "__init__.py", "")
            write(root, "scripts/tests/test_sample.py", "import unittest\n")
            write(root, "scripts/tests/pkg/test_local.py", "import unittest\n")
            os.symlink(
                foreign_init, root / "scripts" / "tests" / "pkg" / "__init__.py"
            )
            self.assertEqual(discover_verification_commands(root), ())

    def test_scripts_tests_symlinked_helper_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            foreign_helper = write(
                base / "external", "helper.py", "VALUE = 1\n"
            )
            write(
                root,
                "scripts/tests/test_sample.py",
                "import unittest\nimport helper\n",
            )
            os.symlink(
                foreign_helper, root / "scripts" / "tests" / "helper.py"
            )
            self.assertEqual(discover_verification_commands(root), ())

    @unittest.skipIf(
        os.geteuid() == 0, "root bypasses directory permission checks"
    )
    def test_scripts_tests_unlistable_subtree_discovers_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            foreign_helper = write(
                base / "external", "helper.py", "VALUE = 99\n"
            )
            write(root, "scripts/tests/test_sample.py", "import unittest\n")
            write(root, "scripts/tests/zzz_pkg/__init__.py", "")
            pkg = root / "scripts" / "tests" / "zzz_pkg"
            os.symlink(foreign_helper, pkg / "helper.py")
            pkg.chmod(0o111)
            try:
                self.assertEqual(discover_verification_commands(root), ())
            finally:
                pkg.chmod(0o755)

    def test_root_symlink_discovers_scripts_unittest(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            write(root, "scripts/tests/test_sample.py", "import unittest\n")
            root_link = base / "root_link"
            os.symlink(root, root_link)
            commands = discover_verification_commands(root_link)
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


class BarePytestSymlinkScopeTests(unittest.TestCase):
    """Issue #62 end to end: a sealed PASS never rests on tests
    the bare pytest leg collected through a symlinked directory.
    The fs binding records a symlink's target string, never the
    target's contents, so pre-fix this shape sealed a PASS over
    external bytes and kept blessing it after those bytes were
    mutated (the stale-PASS escape)."""

    def _verify(self, root: Path, receipts: Path):
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
        records = []
        if receipts.exists():
            records = [
                json.loads(line)
                for line in receipts.read_text().splitlines()
            ]
        return rc, records, stdout.getvalue()

    def _check(self, receipts: Path, root: Path):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = mechanical_verify.check_receipts(receipts, "t", root)
        return rc, stdout.getvalue()

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_sealed_pass_refused_after_tests_dir_replaced_by_symlink(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "tests/test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            # Seal over the all-real tree; the unmutated tree
            # still verifies and audits clean.
            rc, records, output = self._verify(root, receipts)
            self.assertEqual(rc, 0, output)
            pytest_receipts = [
                r for r in records if r.get("command_id") == "pytest"
            ]
            self.assertEqual(len(pytest_receipts), 1)
            self.assertEqual(pytest_receipts[0]["exit_code"], 0)
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 0, output)
            self.assertIn("RECEIPTS: PASS", output)
            # Mutate: the real directory is replaced by a symlink
            # to external content (passing bytes the seal never
            # bound). The audit of the OLD receipt against the
            # mutated tree refuses — STALE, because the fs digest
            # no longer matches the segment: the directory's
            # entries were replaced by a single link entry.
            external = base / "external"
            write(
                external,
                "test_ext.py",
                "def test_ext():\n    assert True\n",
            )
            shutil.rmtree(root / "tests")
            os.symlink(external, root / "tests")
            rc, output = self._check(receipts, root)
            self.assertNotEqual(rc, 0, output)
            self.assertIn("STALE", output)
            self.assertIn("live tree digest does not match", output)
            # And the mutated tree's own verify path cannot seal a
            # fresh PASS over the linked content: discovery
            # disqualifies the leg, leaving no commands at all.
            ids = [c.id for c in discover_verification_commands(root)]
            self.assertNotIn("pytest", ids)
            rc, _, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)
            self.assertIn("no verification commands discovered", output)

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_symlinked_tests_dir_tree_seals_no_pytest_pass(self):
        # The escape tree itself: the only test content lives
        # outside the tree, reached through a tests symlink.
        # Pre-fix this sealed a PASS (and kept blessing it after
        # the external bytes changed); now the leg is disqualified
        # at discovery, verify finds no commands, and nothing is
        # sealed.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            write(root, "pytest.ini", "[pytest]\n")
            external = base / "external"
            write(
                external,
                "test_ext.py",
                "def test_ext():\n    assert True\n",
            )
            os.symlink(external, root / "tests")
            rc, _, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)
            self.assertIn("no verification commands discovered", output)
            self.assertFalse(receipts.exists())

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_config_aim_at_symlinked_file_seals_no_pytest_pass(self):
        # Round 3 (Task 11 re-review §4): the re-reviewer's
        # fixture end to end. The tree's only test content is
        # an outside file reached through a symlink whose name
        # matches no test pattern; the bound config aims
        # collection at it. Pre-fix the leg executed the
        # external test under a seal (receipt: collected 1)
        # and the audit kept blessing it after the target was
        # mutated — neither the aim gate (the aim resolves
        # textually inside the root) nor the scope walk (the
        # name is outside its patterns) refused. Now the aim
        # itself refuses the leg and nothing seals.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            external = write(
                base,
                "outside/linked.py",
                "def test_linked():\n    assert True\n",
            )
            os.symlink(external, root / "linktest.py")
            write(
                root,
                "pytest.ini",
                "[pytest]\ntestpaths = linktest.py\n",
            )
            rc, _, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)
            self.assertIn("no verification commands discovered", output)
            self.assertFalse(receipts.exists())


class ResidueConfigAimTests(unittest.TestCase):
    """Task 11 (paperthin validation 2, probe B2): a bound config
    must not aim the bare pytest leg into a residue directory.

    Task 11 binds code files under the residue names in the tree
    digest, which covers the collected .py shape of B2 at audit
    time. The leg is additionally refused at discovery when the
    config pytest would select — a real, bound file — aims
    testpaths or pythonpath into a residue-named path: collection
    or import machinery can execute shapes no extension set can
    enumerate there (a bound conftest registering a custom
    collector for non-.py files is the proven instance), so the
    aim itself disqualifies the leg, in the fail-closed posture
    of issue #62. A symlinked config is NOT read for this check:
    it is already insulated by the -c pin (issue #64), and its
    options define nothing.

    Round 2 (Task 11 review, findings F2/F3): the gate reads the
    config's FULL aiming surface, not two keys — addopts entries
    are prepended argv, so their positional tokens are collection
    aims too, and --pyargs retargets collection at installed
    packages. And an aim is refused on either boundary of the
    attested set: into a residue directory, or anywhere outside
    the root, whose content the seal does not describe at all.

    Round 3 (Task 11 re-review §4): an aim at — or through — a
    symlink is refused on the same principle. The binding
    records a link's target string, never its content, so an
    aimed symlinked file executes unattested bytes whatever
    its name; a non-pattern name (linktest.py) is collectable
    precisely because the config aims at it, which is the
    population this gate exists to judge."""

    def _verify(self, root: Path, receipts: Path):
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
        records = []
        if receipts.exists():
            records = [
                json.loads(line)
                for line in receipts.read_text().splitlines()
            ]
        return rc, records, stdout.getvalue()

    def _ids(self, root: Path) -> list[str]:
        return [c.id for c in discover_verification_commands(root)]

    def test_testpaths_into_residue_disqualifies_bare_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pytest.ini",
                "[pytest]\ntestpaths = .mypy_cache/collected\n",
            )
            write(
                root,
                ".mypy_cache/collected/test_planted.py",
                "def test_planted():\n    assert True\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))
            # Control: the same tree aimed at a bound directory
            # schedules the leg.
            write(root, "pytest.ini", "[pytest]\ntestpaths = tests\n")
            self.assertIn("pytest", self._ids(root))

    def test_pythonpath_into_residue_disqualifies_bare_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pyproject.toml",
                "[tool.pytest.ini_options]\n"
                'pythonpath = [".pytest_cache/planted"]\n',
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))
            write(
                root,
                "pyproject.toml",
                "[tool.pytest.ini_options]\n"
                'pythonpath = ["src"]\n',
            )
            self.assertIn("pytest", self._ids(root))

    def test_pyproject_toml_mode_testpaths_into_residue_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pyproject.toml",
                "[tool.pytest]\n"
                'testpaths = [".git/collected"]\n',
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_pytest_toml_testpaths_into_residue_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pytest.toml",
                "[pytest]\n"
                'testpaths = [".pytest_cache/collected"]\n',
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_setup_cfg_testpaths_into_residue_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "setup.cfg",
                "[tool:pytest]\ntestpaths = .mypy_cache/collected\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_residue_component_at_depth_or_via_dotdot_disqualifies(self):
        for aimed in (
            "pkg/.pytest_cache/collected",
            "pkg/../.mypy_cache/collected",
            "__pycache__",
        ):
            with self.subTest(aimed=aimed):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write(
                        root,
                        "pytest.ini",
                        f"[pytest]\ntestpaths = {aimed}\n",
                    )
                    self.assertNotIn("pytest", self._ids(root))

    def test_symlinked_config_aiming_into_residue_stays_insulated(self):
        # The refusal never reads through a link: a symlinked
        # config is already neutralized by the -c pin (issue #64),
        # so the leg is scheduled and pinned, not disqualified.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = base / "external.ini"
            external.write_text(
                "[pytest]\ntestpaths = .mypy_cache/collected\n"
            )
            os.symlink(external, root / "pytest.ini")
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            commands = discover_verification_commands(root)
            pytest_commands = [c for c in commands if c.id == "pytest"]
            self.assertEqual(len(pytest_commands), 1)
            self.assertIn("-c", pytest_commands[0].argv)

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_b2_tree_seals_no_pytest_pass(self):
        # Validator B2 end to end: pre-fix this tree sealed a
        # PASS over a test collected from .mypy_cache and kept
        # blessing it after the test was mutated; now the leg is
        # disqualified at discovery and nothing seals.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            write(
                root,
                "pytest.ini",
                "[pytest]\ntestpaths = .mypy_cache/collected\n",
            )
            write(
                root,
                ".mypy_cache/collected/test_planted.py",
                "def test_planted():\n    assert True\n",
            )
            rc, _, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)
            self.assertIn("no verification commands discovered", output)
            self.assertFalse(receipts.exists())

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_custom_collector_shape_aimed_into_residue_is_refused(self):
        # The shape part 1's extension set cannot see: a bound
        # conftest registers a pytest_collect_file hook that
        # executes a non-.py file, and bound testpaths aims
        # collection at the residue directory holding it. Real
        # pytest executes the planted file; the refusal is what
        # keeps it out of a sealed run.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            write(
                root,
                "pytest.ini",
                "[pytest]\ntestpaths = .mypy_cache/collected\n",
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
                ".mypy_cache/collected/check_planted.txt",
                "def test_planted():\n    assert True\n",
            )
            rc, _, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)
            self.assertIn("no verification commands discovered", output)
            self.assertFalse(receipts.exists())

    def test_addopts_positional_into_residue_disqualifies(self):
        # Finding F2: addopts entries are prepended argv — a bare
        # positional there is a collection aim the two-key gate
        # never read.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pytest.ini",
                "[pytest]\naddopts = .mypy_cache/collected\n",
            )
            write(
                root,
                ".mypy_cache/collected/test_planted.py",
                "def test_planted():\n    assert True\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_addopts_pyargs_disqualifies(self):
        # --pyargs retargets collection at installed packages —
        # outside the bound set by construction.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pytest.ini", "[pytest]\naddopts = --pyargs\n")
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_aims_outside_root_disqualify(self):
        # Finding F3: an aim that resolves outside the root
        # collects or imports content the seal does not describe.
        cases = [
            ("[pytest]\ntestpaths = ../outside\n", None),
            ("[pytest]\naddopts = ../outside\n", None),
            (None, "[tool.pytest.ini_options]\n"
             'pythonpath = ["../outside"]\n'),
        ]
        for ini, toml in cases:
            with self.subTest(ini=ini, toml=toml):
                with tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    root = base / "root"
                    root.mkdir()
                    if ini is not None:
                        write(root, "pytest.ini", ini)
                    if toml is not None:
                        write(root, "pyproject.toml", toml)
                    write(
                        root,
                        "test_ok.py",
                        "def test_ok():\n    assert True\n",
                    )
                    self.assertNotIn("pytest", self._ids(root))
        # Absolute form.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            outside = base / "outside"
            write(
                root,
                "pytest.ini",
                f"[pytest]\ntestpaths = {outside}\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_toml_addopts_into_residue_disqualifies(self):
        for addopts in (
            'addopts = ".mypy_cache/collected"\n',
            'addopts = [".mypy_cache/collected"]\n',
        ):
            with self.subTest(addopts=addopts):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write(
                        root,
                        "pyproject.toml",
                        "[tool.pytest.ini_options]\n" + addopts,
                    )
                    write(
                        root,
                        "test_ok.py",
                        "def test_ok():\n    assert True\n",
                    )
                    self.assertNotIn("pytest", self._ids(root))

    def test_addopts_controls_still_schedule(self):
        # Ordinary addopts define no unattested aim: flags,
        # =-form options, the consumed values of value-taking
        # options (even values outside the root — a basetemp or
        # report path is not a collection aim), and an in-tree
        # positional all leave the leg scheduled.
        for addopts in (
            "-q --tb=short -k smoke",
            "tests",
            "--basetemp /tmp/aep-verifier-basetemp -q",
            "--junit-xml /tmp/aep-report.xml",
        ):
            with self.subTest(addopts=addopts):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write(
                        root,
                        "pytest.ini",
                        f"[pytest]\naddopts = {addopts}\n",
                    )
                    write(
                        root,
                        "tests/test_ok.py",
                        "def test_ok():\n    assert True\n",
                    )
                    self.assertIn("pytest", self._ids(root))

    def test_testpaths_through_residue_to_bound_dir_still_schedules(self):
        # Positive control (round-1 review): the aim normalizes
        # to bound content, so the leg is scheduled.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pytest.ini",
                "[pytest]\ntestpaths = .mypy_cache/../tests\n",
            )
            write(
                root,
                "tests/test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertIn("pytest", self._ids(root))

    def test_testpaths_aim_at_symlinked_file_disqualifies(self):
        # Round 3: the aim's named path is itself a symlink.
        # linktest.py matches no test-name pattern, so only the
        # config's aim makes it collectable — and the content
        # it would execute is the link target's, bound nowhere.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(
                base,
                "outside/linked.py",
                "def test_linked():\n    assert True\n",
            )
            os.symlink(external, root / "linktest.py")
            write(
                root,
                "pytest.ini",
                "[pytest]\ntestpaths = linktest.py\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))
            # Control: the same aim at a REAL file under the
            # same non-pattern name schedules the leg — an
            # explicitly aimed file is collected whatever its
            # name, and its content is bound.
            (root / "linktest.py").unlink()
            write(
                root,
                "linktest.py",
                "def test_linked():\n    assert True\n",
            )
            self.assertIn("pytest", self._ids(root))

    def test_addopts_aim_at_symlinked_file_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = write(
                base,
                "outside/linked.py",
                "def test_linked():\n    assert True\n",
            )
            os.symlink(external, root / "linktest.py")
            write(
                root,
                "pytest.ini",
                "[pytest]\naddopts = linktest.py\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_aim_at_symlink_to_in_tree_file_disqualifies(self):
        # The link is the policy object, not its target: an
        # aim at a symlink whose target is a real in-tree file
        # is refused the same way (the posture of Tasks 6/7 —
        # a symlinked test file contributes nothing, wherever
        # it points).
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(
                root,
                "real/test_real.py",
                "def test_real():\n    assert True\n",
            )
            os.symlink(
                root / "real" / "test_real.py", root / "linktest.py"
            )
            write(
                root,
                "pytest.ini",
                "[pytest]\ntestpaths = linktest.py\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_aim_through_symlinked_component_disqualifies(self):
        # A component check, not just the final name: the aim
        # crosses a symlinked directory to reach a non-pattern
        # file inside it. (The scope walk's directory rule
        # refuses this tree too; this pins the composition —
        # the leg is refused, by whichever gate fires.)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = base / "outside"
            write(
                external,
                "inner.py",
                "def test_inner():\n    assert True\n",
            )
            os.symlink(external, root / "linkdir")
            write(
                root,
                "pytest.ini",
                "[pytest]\ntestpaths = linkdir/inner.py\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_custom_collector_shape_aimed_via_addopts_is_refused(self):
        # Finding F2 end to end: B2's custom-collector shape with
        # the aim carried by an addopts positional instead of
        # testpaths. Pre-fix the leg sealed over the planted .txt.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            write(
                root,
                "pytest.ini",
                "[pytest]\naddopts = .mypy_cache/collected\n",
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
                ".mypy_cache/collected/check_planted.txt",
                "def test_planted():\n    assert True\n",
            )
            rc, _, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)
            self.assertIn("no verification commands discovered", output)
            self.assertFalse(receipts.exists())

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_ordinary_testpaths_control_still_seals(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            write(root, "pytest.ini", "[pytest]\ntestpaths = tests\n")
            write(
                root,
                "tests/test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            rc, records, output = self._verify(root, receipts)
            self.assertEqual(rc, 0, output)
            pytest_receipts = [
                r for r in records if r.get("command_id") == "pytest"
            ]
            self.assertEqual(len(pytest_receipts), 1)
            self.assertEqual(pytest_receipts[0]["exit_code"], 0)


class CacheSelectionGateTests(unittest.TestCase):
    """Task 13 (paperthin validation 4, breach B-B): the cache
    tools' state files are excluded from the binding as
    write-side residue, but pytest's cacheprovider also READS
    that state — a bound `addopts = --last-failed` makes the
    set of tests the sealed run executes a function of the
    planted, unbound `.pytest_cache/v/cache/lastfailed` bytes:
    a one-test subset PASS for a tree whose full suite fails,
    in both modes. The executed set of an attested run must be
    a function of bound content alone, so the steering gate
    refuses the bare pytest leg when the selected config's
    addopts arms a cache-SELECTION flag — the family
    enumerated from the installed pytest's own registrations
    (cacheprovider.py and stepwise.py): --lf/--last-failed
    and --sw/--stepwise, --sw-skip/--stepwise-skip (the skip
    forms imply stepwise and share its deselection path).

    Adjudicated NOT selection, by source and by probe against
    the installed pytest, and therefore not refused:
    --ff/--failed-first only reorders (LFPlugin concatenates
    the previously-failed and previously-passed partitions —
    every collected test still runs, and with -x the run still
    stops ON a failure, never before one; its one narrowing
    combination, --ff with --last-failed-no-failures=none on
    an EMPTY lastfailed, deselects everything and exits 5,
    never a PASS); --lfnf/--last-failed-no-failures is a
    modifier that is inert on its own (the LF plugin is
    inactive without --lf/--ff); --sw-reset/--stepwise-reset
    DISCARDS the stepwise state before selection, so a PASS
    under it means the full collected set ran; --nf/--new-first
    reorders by cache/nodeids and selects nothing; nested
    `-o addopts=...` inside addopts does not re-expand (the
    run's addopts are fixed at preparse), so no recursion
    channel exists for the scanner to miss."""

    def _verify(self, root: Path, receipts: Path):
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
        records = []
        if receipts.exists():
            records = [
                json.loads(line)
                for line in receipts.read_text().splitlines()
            ]
        return rc, records, stdout.getvalue()

    def _ids(self, root: Path) -> list[str]:
        return [c.id for c in discover_verification_commands(root)]

    def _config_tree(self, root: Path, config_name: str, config: str):
        write(root, config_name, config)
        write(
            root,
            "test_ok.py",
            "def test_ok():\n    assert True\n",
        )

    def test_last_failed_addopts_disqualifies_bare_pytest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config_tree(
                root,
                "pytest.ini",
                "[pytest]\naddopts = --last-failed\n",
            )
            self.assertNotIn("pytest", self._ids(root))
            # Control: the same tree without the flag schedules.
            self._config_tree(root, "pytest.ini", "[pytest]\n")
            self.assertIn("pytest", self._ids(root))

    def test_cache_selection_spellings_disqualify(self):
        for flag in (
            "--lf",
            "--stepwise",
            "--sw",
            "--stepwise-skip",
            "--sw-skip",
        ):
            with self.subTest(flag=flag):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self._config_tree(
                        root,
                        "pytest.ini",
                        f"[pytest]\naddopts = {flag}\n",
                    )
                    self.assertNotIn("pytest", self._ids(root))

    def test_cache_selection_in_toml_list_addopts_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config_tree(
                root,
                "pyproject.toml",
                "[tool.pytest.ini_options]\n"
                'addopts = ["--last-failed"]\n',
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_cache_selection_in_setup_cfg_addopts_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config_tree(
                root,
                "setup.cfg",
                "[tool:pytest]\naddopts = --stepwise\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_cache_selection_in_tox_ini_addopts_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config_tree(
                root,
                "tox.ini",
                "[pytest]\naddopts = --sw\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_selection_flag_after_double_dash_disqualifies(self):
        # Task 13 review, finding F1: the premise this test
        # originally pinned — "`--` ends option processing" —
        # is false for pytest 9. Its parser re-reads the
        # post-separator remainder as a fresh stream, so a
        # registered spelling arms after one `--` exactly as
        # before it (proven against the raw binary:
        # `-- --last-failed` runs the planted subset). The scanner
        # judges every spelling anywhere in the stream, so the
        # leg is refused here too; see AddoptsGrammarTests.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config_tree(
                root,
                "pytest.ini",
                "[pytest]\naddopts = -- --last-failed\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_selection_spelling_as_option_value_is_not_armed(self):
        # A selection spelling swallowed as a value-taking
        # option's value is not an armed flag either — real
        # pytest rejects the run in that shape, so the leg
        # fails closed on its own.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config_tree(
                root,
                "pytest.ini",
                "[pytest]\naddopts = --basetemp --last-failed\n",
            )
            self.assertIn("pytest", self._ids(root))

    def test_failed_first_is_not_refused(self):
        for flag in ("--failed-first", "--ff"):
            with self.subTest(flag=flag):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self._config_tree(
                        root,
                        "pytest.ini",
                        f"[pytest]\naddopts = {flag}\n",
                    )
                    self.assertIn("pytest", self._ids(root))

    def test_lfnf_modifier_alone_is_not_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config_tree(
                root,
                "pytest.ini",
                "[pytest]\naddopts = --last-failed-no-failures none\n",
            )
            self.assertIn("pytest", self._ids(root))

    def test_stepwise_reset_is_not_refused(self):
        for flag in ("--sw-reset", "--stepwise-reset"):
            with self.subTest(flag=flag):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self._config_tree(
                        root,
                        "pytest.ini",
                        f"[pytest]\naddopts = {flag}\n",
                    )
                    self.assertIn("pytest", self._ids(root))

    def test_new_first_is_not_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config_tree(
                root,
                "pytest.ini",
                "[pytest]\naddopts = --new-first\n",
            )
            self.assertIn("pytest", self._ids(root))

    def _subset_fixture(self, root: Path, addopts: str) -> None:
        write(
            root,
            "pytest.ini",
            f"[pytest]\naddopts = {addopts}\n",
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
        write(
            root,
            ".pytest_cache/v/cache/lastfailed",
            '{"test_ok.py::test_ok": true}',
        )

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_last_failed_subset_cannot_seal(self):
        # Validator B-B1, fs mode: pre-fix this sealed a
        # one-test PASS (tests_collected = 1) for a tree whose
        # full suite fails; the leg is now refused at discovery.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            self._subset_fixture(root, "--last-failed")
            rc, records, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)
            self.assertIn("no verification commands discovered", output)
            self.assertFalse(receipts.exists())

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_stepwise_subset_cannot_seal(self):
        # Validator B-B, stepwise instance: the planted
        # stepwise state resumes AT test_ok, deselecting the
        # failing test_bad (collected before it) — pre-fix a
        # subset PASS; the leg is refused at discovery now.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            self._subset_fixture(root, "--stepwise")
            write(
                root,
                ".pytest_cache/v/cache/stepwise",
                '{"last_failed": "test_ok.py::test_ok", '
                '"last_test_count": 2, '
                '"last_cache_date_str": "2026-01-01T00:00:00"}',
            )
            rc, records, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)
            self.assertIn("no verification commands discovered", output)
            self.assertFalse(receipts.exists())

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_failed_first_runs_the_full_set(self):
        # The --ff adjudication, end to end: with the same
        # planted lastfailed that subsets a --lf run, a --ff
        # run still executes the failing test and the leg
        # records its failure — no PASS seals.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            self._subset_fixture(root, "--failed-first")
            rc, records, output = self._verify(root, receipts)
            self.assertEqual(rc, 1, output)
            pytest_receipts = [
                r for r in records if r.get("command_id") == "pytest"
            ]
            self.assertEqual(len(pytest_receipts), 1)
            self.assertNotEqual(pytest_receipts[0]["exit_code"], 0)
            self.assertEqual(pytest_receipts[0]["tests_collected"], 2)

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_stepwise_reset_runs_the_full_set(self):
        # The --sw-reset adjudication, end to end: the flag
        # discards the planted stepwise state before selection,
        # so the failing test runs and the leg fails; on a
        # passing tree the full collected set seals.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            self._subset_fixture(root, "--sw-reset")
            write(
                root,
                ".pytest_cache/v/cache/stepwise",
                '{"last_failed": "test_ok.py::test_ok", '
                '"last_test_count": 2, '
                '"last_cache_date_str": "2026-01-01T00:00:00"}',
            )
            rc, records, output = self._verify(root, receipts)
            self.assertNotEqual(rc, 0, output)
            write(root, "test_bad.py", "def test_bad():\n    assert True\n")
            rc, records, output = self._verify(root, receipts)
            self.assertEqual(rc, 0, output)
            pytest_receipts = [
                r for r in records if r.get("command_id") == "pytest"
            ]
            self.assertEqual(pytest_receipts[-1]["tests_collected"], 2)


class AddoptsGrammarTests(unittest.TestCase):
    """Task 14 (Task 13 review, finding F1): the addopts
    scanners shared one false premise — that `--` ends option
    processing, so tokens after it are positional aims and no
    option spelling there can arm. Pytest 9's parser does not
    stop at the separator: it parses the stream in two passes
    (argparse's intermixed parsing; on pre-3.12.8 Pythons a
    fallback that splits the leftovers the same way), the
    first pass consumes the separator and hands the remainder
    to the second pass as a fresh stream, so a registered
    option spelling arms wherever it appears — before,
    between, or after positionals, and after one `--` as
    surely as before it. Proven against the raw binary with a
    planted lastfailed naming the passing test of a two-test
    tree: `--last-failed`, `-- --last-failed`, `-- --lf`,
    `--debug --lf`, and `--debug=x --lf` each run ONLY the
    planted test (rc 0, full suite would fail); `-- 
    --stepwise` resumes from a genuine stepwise plant; `-- 
    --pyargs json` arms (rc 5, collected 0); `-- 
    --doctest-glob=*.rst` and the space form both collect the
    .rst doctest. Two separators restore the positional
    reading (`-- -- --last-failed` errors rc 4, "file or
    directory not found: --last-failed"), which the
    both-readings composition covers by refusing on the
    option reading anyway — the fail-closed direction.

    The fix is one tokenization for every addopts consumer
    (_addopts_token_stream): `--` is skipped, never a
    terminator, and every remaining token is judged under
    both readings the parser could give it — an option
    spelling as an option, a bare token as an aim. A known
    value-taking option consumes the following token
    verbatim, separators and spellings included: where the
    parser accepts the stream it consumes that token the
    same way, and where the scanner's reading is one the
    parser rejects (`-k -- test_ok`, `-c --lf` — both proven
    rc 4, "expected one argument"), the run errors and the
    leg fails closed on its own. Options whose value is
    OPTIONAL (nargs="?") never consume in the scanner: the
    parser takes the next token as the value only when it
    does not look like an option (`--debug --lf` arms --lf —
    the same premise in value-consumption form), so the
    token keeps both readings. There are exactly two such
    options in the installed parser, --debug and
    --cache-show; the pin test below re-derives the value
    set from the installed parser so a future pytest that
    changes either set fails loudly."""

    def test_cache_selection_arms_after_separator(self):
        scan = mechanical_verify._addopts_cache_selection
        self.assertTrue(scan(["--", "--last-failed"]))
        self.assertTrue(scan(["--", "--lf"]))
        self.assertTrue(scan(["--", "--stepwise"]))
        self.assertTrue(scan(["sub", "--", "--sw-skip"]))

    def test_cache_selection_arms_after_double_separator(self):
        # After two separators the raw parser reads the
        # spelling as a path and errors (rc 4) — but the
        # option reading is one of the readings the token
        # carries, and the scanner takes the reading that
        # refuses.
        self.assertTrue(
            mechanical_verify._addopts_cache_selection(
                ["--", "--", "--last-failed"]
            )
        )

    def test_cache_selection_arms_after_optional_value_option(self):
        scan = mechanical_verify._addopts_cache_selection
        # --debug and --cache-show take an OPTIONAL value:
        # an option-looking token after them is not their
        # value, it is an armed option.
        self.assertTrue(scan(["--debug", "--lf"]))
        self.assertTrue(scan(["--cache-show", "--lf"]))
        # With the value attached, the next token is judged
        # on its own as before.
        self.assertTrue(scan(["--debug=trace.txt", "--lf"]))

    def test_cache_selection_value_consumption_still_applies(self):
        scan = mechanical_verify._addopts_cache_selection
        # A spelling consumed as a REQUIRED value is not an
        # armed flag; the parser rejects those streams (rc 4)
        # so the leg fails closed on its own either way.
        self.assertFalse(scan(["--basetemp", "--last-failed"]))
        self.assertFalse(scan(["-k", "--lf"]))
        self.assertFalse(scan(["-c", "--lf"]))
        # A separator swallowed as a value does not stop the
        # scan either: the spelling after it is still judged.
        self.assertTrue(scan(["-k", "--", "--last-failed"]))

    def test_aims_pyargs_after_separator(self):
        aims, pyargs = mechanical_verify._addopts_aims(
            ["--", "--pyargs", "json"]
        )
        self.assertTrue(pyargs)
        self.assertEqual(aims, ["json"])

    def test_aims_positional_after_separator_is_an_aim(self):
        # The positional reading of a post-separator token is
        # real — the raw parser collects the path — so it
        # stays an aim for the aim gate to judge.
        aims, pyargs = mechanical_verify._addopts_aims(
            ["--", ".pytest_cache/collected"]
        )
        self.assertEqual(aims, [".pytest_cache/collected"])
        self.assertFalse(pyargs)

    def test_aims_option_after_separator_consumes_its_value(self):
        # `-- -k test_ok` against the raw binary: -k arms
        # with its filter (1 passed, 1 deselected) — the
        # value is the option's, not an aim.
        aims, pyargs = mechanical_verify._addopts_aims(
            ["--", "-k", "test_ok"]
        )
        self.assertEqual(aims, [])
        self.assertFalse(pyargs)

    def test_aims_interleaved_positionals_and_options(self):
        aims, pyargs = mechanical_verify._addopts_aims(
            ["tests/unit", "--lf", "tests/other"]
        )
        self.assertEqual(aims, ["tests/unit", "tests/other"])
        self.assertFalse(pyargs)

    def test_doctest_globs_after_separator(self):
        globs = mechanical_verify._addopts_doctest_globs
        self.assertEqual(
            globs(["--", "--doctest-glob=*.rst"]), ["*.rst"]
        )
        self.assertEqual(
            globs(["--", "--doctest-glob", "*.rst"]), ["*.rst"]
        )
        self.assertEqual(globs(["--doctest-glob=*.rst"]), ["*.rst"])

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_value_options_match_installed_parser(self):
        # The scanner's value-taking set must be exactly the
        # installed parser's REQUIRED-value options (an
        # option whose action stores or appends one value):
        # an option missing from the set lets its "value" be
        # misjudged as an aim or an armed spelling, and an
        # option wrongly in the set (an optional-value one,
        # like --debug was) lets it swallow the token after
        # it. Recompute from the installed parser, the way
        # TraversalGateTests pins the norecursedirs default.
        from _pytest.config import get_config

        parser = get_config()._parser
        expected = {
            option_string
            for action in parser.optparser._actions
            for option_string in action.option_strings
            if action.nargs is None
        }
        self.assertEqual(
            set(mechanical_verify._PYTEST_VALUE_OPTIONS), expected
        )

    def _ids(self, root: Path) -> list[str]:
        return [c.id for c in discover_verification_commands(root)]

    def _config_tree(self, root: Path, addopts: str):
        write(
            root,
            "pytest.ini",
            f"[pytest]\naddopts = {addopts}\n",
        )
        write(
            root,
            "test_ok.py",
            "def test_ok():\n    assert True\n",
        )

    def test_pyargs_after_separator_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config_tree(root, "-- --pyargs json")
            self.assertNotIn("pytest", self._ids(root))
            # Control: the plain separator alone schedules.
            self._config_tree(root, "--")
            self.assertIn("pytest", self._ids(root))

    def test_debug_then_selection_flag_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config_tree(root, "--debug --lf")
            self.assertNotIn("pytest", self._ids(root))

    def _verify(self, root: Path, receipts: Path):
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
        return rc, stdout.getvalue()

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_last_failed_after_separator_cannot_seal(self):
        # The Task 13 review's F1 fixture end to end: the
        # validator's B-B1 tree with `addopts = -- 
        # --last-failed` sealed a one-test subset PASS at the
        # parent (audit PASS); the leg is refused now.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            write(
                root,
                "pytest.ini",
                "[pytest]\naddopts = -- --last-failed\n",
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
            write(
                root,
                ".pytest_cache/v/cache/lastfailed",
                '{"test_ok.py::test_ok": true}',
            )
            rc, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)
            self.assertIn(
                "no verification commands discovered", output
            )
            self.assertFalse(receipts.exists())


class TraversalGateTests(unittest.TestCase):
    """Task 12 (paperthin validation 3, breach B-NEW): a bound
    config's `norecursedirs` REPLACES pytest's default traversal
    exclusion list, so a list that drops `.*` lets the DEFAULT
    collection walk enter `.git` — no aim, no testpaths — and a
    bound conftest's custom collector executes a planted file
    the bindings cannot see there (check_a.txt sits outside the
    .git bind set). Validation 3 sealed that shape with the
    planted item in the count and check_receipts kept blessing
    it after a post-seal mutation, in fs AND git modes. The
    aim gate now judges the effective norecursedirs, and the
    scope walk judges symlinked files by the EFFECTIVE
    collection patterns (the config's python_files and the
    doctest globs) — which also closes a pre-existing hole in
    the walk itself: a symlinked test*.txt executes as a
    doctest textfile under a fully default run, and the walk's
    hardcoded default collectable set never named it."""

    COLLECTOR = (
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
        "        return TxtFile.from_parent(parent, path=file_path)\n"
    )

    def _verify(self, root: Path, receipts: Path):
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
        records = []
        if receipts.exists():
            records = [
                json.loads(line)
                for line in receipts.read_text().splitlines()
            ]
        return rc, records, stdout.getvalue()

    def _ids(self, root: Path) -> list[str]:
        return [c.id for c in discover_verification_commands(root)]

    def _n7a_tree(self, root: Path, ini_body: str) -> None:
        write(root, "pytest.ini", f"[pytest]\n{ini_body}")
        write(root, "conftest.py", self.COLLECTOR)
        write(
            root,
            ".git/collected/check_a.txt",
            "def test_planted():\n    assert True\n",
        )
        write(root, "test_ok.py", "def test_ok():\n    assert True\n")

    def test_norecursedirs_judgement_matches_pytest_semantics(self):
        # fnmatch_ex, as _pytest.main applies it: a slash-free
        # pattern judges the basename; a pattern with a
        # separator judges the path, so it covers a name only
        # when it matches at every depth the walk could meet it.
        excludes = mechanical_verify._norecursedirs_excludes
        self.assertTrue(excludes(["*.egg", ".*"], ".git"))
        self.assertTrue(excludes([".*"], ".pytest_cache"))
        self.assertTrue(excludes([".*"], ".mypy_cache"))
        self.assertFalse(excludes(["*.egg"], ".git"))
        self.assertFalse(excludes(["build", "dist"], ".git"))
        self.assertFalse(excludes([], ".git"))
        self.assertTrue(excludes([".git"], ".git"))
        self.assertFalse(excludes([".git"], ".pytest_cache"))
        self.assertTrue(excludes(["*/.git"], ".git"))
        self.assertFalse(excludes(["sub/.git"], ".git"))
        self.assertTrue(excludes(["**"], ".git"))

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_installed_pytest_default_norecursedirs_covers_residue(self):
        # The pin the breach demands: when the selected config
        # does not set norecursedirs, the gate relies on
        # pytest's default list excluding the residue names.
        # Judge the INSTALLED pytest's registered default: a
        # future pytest whose default stops excluding one of
        # them fails here loudly instead of silently opening
        # the traversal route.
        from _pytest.config import get_config

        _help, _type, default = get_config()._parser._inidict[
            "norecursedirs"
        ]
        excludes = mechanical_verify._norecursedirs_excludes
        for name in (".git", ".pytest_cache", ".mypy_cache"):
            self.assertTrue(
                excludes(list(default), name),
                f"installed default {default!r} no longer "
                f"excludes {name}",
            )

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_pytest_ground_truth_traversal_rules(self):
        # Two facts of pytest 9 the gate is built on, proven
        # against the installed pytest itself: an ini-set
        # norecursedirs is operative (it replaces the default,
        # so traversal enters .git), and __pycache__ is pruned
        # by a hardcoded check in pytest_ignore_collect that no
        # config value can reopen (so the gate never requires
        # the list to cover it).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pytest.ini", "[pytest]\nnorecursedirs = *.egg\n")
            write(root, "conftest.py", self.COLLECTOR)
            write(
                root,
                ".git/collected/check_a.txt",
                "def test_planted():\n    assert True\n",
            )
            write(
                root,
                "__pycache__/collected/check_b.txt",
                "def test_planted():\n    assert False\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            proc = subprocess.run(
                ["python3", "-m", "pytest", "--collect-only", "-q"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("check_a.txt", proc.stdout)
            self.assertNotIn("check_b.txt", proc.stdout)

    def test_norecursedirs_dropping_dotstar_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pytest.ini",
                "[pytest]\nnorecursedirs = *.egg\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_norecursedirs_covering_every_residue_name_keeps_leg(self):
        cases = {
            "keeps dotstar": "*.egg .* build",
            "names each one": ".git .pytest_cache .mypy_cache *.egg",
            "separated catch-all": "*/.git .pytest_cache .mypy_cache",
            "multi-line value": "\n    *.egg\n    .*",
        }
        for label, value in cases.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write(
                        root,
                        "pytest.ini",
                        f"[pytest]\nnorecursedirs = {value}\n",
                    )
                    write(
                        root,
                        "test_ok.py",
                        "def test_ok():\n    assert True\n",
                    )
                    self.assertIn("pytest", self._ids(root))

    def test_norecursedirs_partial_coverage_disqualifies(self):
        cases = {
            "only .git named": ".git",
            "empty value": "",
            "scoped separator": "sub/.git .pytest_cache .mypy_cache",
        }
        for label, value in cases.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    write(
                        root,
                        "pytest.ini",
                        f"[pytest]\nnorecursedirs = {value}\n",
                    )
                    write(
                        root,
                        "test_ok.py",
                        "def test_ok():\n    assert True\n",
                    )
                    self.assertNotIn("pytest", self._ids(root))

    def test_norecursedirs_toml_list_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pyproject.toml",
                "[tool.pytest.ini_options]\n"
                'norecursedirs = ["*.egg"]\n',
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertNotIn("pytest", self._ids(root))

    def test_symlinked_config_traversal_widening_stays_insulated(self):
        # The gate never reads through a link: a symlinked
        # config is neutralized by the -c pin (issue #64), so a
        # widened norecursedirs inside it defines nothing and
        # the leg is scheduled, pinned — not disqualified.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            external = base / "external.ini"
            external.write_text("[pytest]\nnorecursedirs = *.egg\n")
            os.symlink(external, root / "pytest.ini")
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            commands = discover_verification_commands(root)
            pytest_commands = [c for c in commands if c.id == "pytest"]
            self.assertEqual(len(pytest_commands), 1)
            self.assertIn("-c", pytest_commands[0].argv)

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_n7a_fixture_refused_in_fs_mode(self):
        # Validation 3's breach fixture end to end: pre-fix
        # this sealed with tests_collected 2 and check_receipts
        # kept passing after the planted file was mutated.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            self._n7a_tree(root, "norecursedirs = *.egg\n")
            rc, _, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)
            self.assertIn("no verification commands discovered", output)
            self.assertFalse(receipts.exists())

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_n7a_fixture_with_covering_list_seals_collected_one(self):
        # The same fixture with a norecursedirs that still
        # excludes every residue name: the leg runs, traversal
        # stays out of .git, and only the real test collects.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            self._n7a_tree(root, "norecursedirs = *.egg .*\n")
            rc, records, output = self._verify(root, receipts)
            self.assertEqual(rc, 0, output)
            pytest_receipts = [
                r for r in records if r.get("command_id") == "pytest"
            ]
            self.assertEqual(len(pytest_receipts), 1)
            self.assertEqual(pytest_receipts[0]["exit_code"], 0)
            self.assertEqual(pytest_receipts[0]["tests_collected"], 1)

    @unittest.skipUnless(_pytest_on_path(), "no pytest on PATH")
    def test_addopts_override_ini_does_not_widen_traversal(self):
        # Ground-truth pin: pytest applies -o overrides once,
        # before addopts are prepended, so an `-o` assignment
        # inside addopts never reaches the ini store — the
        # effective norecursedirs stays the default and the
        # breach fixture steered this way collects only the
        # real test. The gate therefore judges the ini key,
        # not addopts text.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            receipts = base / "receipts.jsonl"
            self._n7a_tree(root, "addopts = -o norecursedirs=*.egg\n")
            rc, records, output = self._verify(root, receipts)
            self.assertEqual(rc, 0, output)
            pytest_receipts = [
                r for r in records if r.get("command_id") == "pytest"
            ]
            self.assertEqual(len(pytest_receipts), 1)
            self.assertEqual(pytest_receipts[0]["tests_collected"], 1)

    def test_symlinked_default_doctest_textfile_disqualifies(self):
        # The walk's own pre-existing hole: under pytest's
        # DEFAULT doctest glob (test*.txt) a symlinked textfile
        # is collected and its doctests execute through the
        # link, under a fully default run with no config at
        # all. The effective-patterns rule closes it.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            outside = write(
                base,
                "outside.txt",
                ">>> 1 + 1\n2\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            os.symlink(outside, root / "test_notes.txt")
            self.assertNotIn("pytest", self._ids(root))

    def test_symlinked_txt_with_widened_doctest_glob_disqualifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            outside = write(base, "outside.txt", "payload\n")
            write(
                root,
                "pytest.ini",
                "[pytest]\naddopts = --doctest-glob=*.txt\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            os.symlink(outside, root / "data.txt")
            self.assertNotIn("pytest", self._ids(root))

    def test_symlinked_txt_matching_no_glob_stays(self):
        # Boundary pin: a symlinked .txt matching neither the
        # default doctest glob nor any configured pattern is
        # not executed by pytest's own machinery, so the leg
        # stays (a bound conftest executing it by choice is the
        # disclosed in-tree family, not this gate's).
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            outside = write(base, "outside.txt", "payload\n")
            write(root, "pytest.ini", "[pytest]\n")
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            os.symlink(outside, root / "data.txt")
            self.assertIn("pytest", self._ids(root))

    def test_real_doctest_textfile_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_notes.txt",
                ">>> 1 + 1\n2\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertIn("pytest", self._ids(root))

    def test_widened_python_files_symlink_disqualifies(self):
        # The brief's shape: the selected config widens
        # python_files to *.txt; a symlinked file the widened
        # pattern names disqualifies exactly like a
        # default-pattern collectable.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            outside = write(base, "outside.txt", "payload\n")
            write(
                root,
                "pytest.ini",
                "[pytest]\npython_files = *.txt\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            os.symlink(outside, root / "check_data.txt")
            self.assertNotIn("pytest", self._ids(root))

    def test_widened_python_files_real_file_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pytest.ini",
                "[pytest]\npython_files = *.txt\n",
            )
            write(root, "check_data.txt", "payload\n")
            write(
                root,
                "test_ok.py",
                "def test_ok():\n    assert True\n",
            )
            self.assertIn("pytest", self._ids(root))


def _pid_dead(pid: int) -> bool:
    """Gone entirely, or a zombie (dead, awaiting reaping by init)."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return True
    state = stat.rsplit(")", 1)[1].split()[0]
    return state == "Z"


class RootBoundaryTests(unittest.TestCase):
    """Task 15 (paperthin validation 5, breach B-A): every
    binding is scoped to the verify root, but the runners
    resolve ACROSS it. When the root carries no qualifying
    pytest inifile, pytest's search ascends: an ancestor's
    pytest.ini becomes the run's config, an ancestor's
    conftest.py executes (rootdir/confcutdir move up), and an
    ancestor's non-qualifying pyproject.toml still anchors
    rootdir. A parent go.work puts a sealed go run in
    workspace mode; a parent node_modules supplies a sealed
    npm run's module; cargo ascends for workspace membership
    and for .cargo config alike. In every instance the
    skeleton is the batch's own: seal rc 0, mutate only the
    outside content, audit PASS, fresh verify FAIL.

    Closures, each pinned below and each derived from live
    probes against the installed tools (pytest 9.0.3,
    go 1.27.2, node 24, cargo 1.75 — the cargo semantics
    exercised are the long-stable discovery rules):

    - pytest: the leg's argv pins the selection to the root
      in ALL cases — -c names the selected in-tree config
      (or os.devnull when there is none or it is a symlink),
      --rootdir and --confcutdir name the root itself. Each
      element is load-bearing: -c alone derives rootdir from
      the config file's directory (/dev for os.devnull, an
      unbounded confcutdir), --confcutdir alone leaves the
      config search ascending. Defence in depth: a run whose
      transcript names a rootdir other than the attested
      root attested a different tree, so its collected count
      is unproven and the leg fails the count gate.
    - go: the leg's environment forces GOWORK=off, assigned
      after the caller's environment is composed, so neither
      an ancestor go.work nor a caller-supplied GOWORK can
      put the run in workspace mode; GOFLAGS cannot carry
      workspace mode (probed).
    - node: no flag confines node's upward resolution, so
      the npm leg is disqualified when ANY ancestor of the
      root carries a node_modules directory.
    - cargo: the cargo leg is disqualified when an
      ancestor's .cargo/config.toml or .cargo/config could
      steer the build (a rustc-wrapper fires even under a
      self-anchored root — config discovery does not stop at
      the workspace boundary), when an ancestor workspace
      would claim the crate (members covering it, or the
      membership question the members list cannot settle —
      a non-member under a workspace directory errors in
      cargo, but a path dependency of a member auto-enrolls
      a crate the members list never names, so any
      non-excluding ancestor workspace disqualifies), or
      when the root manifest declares an outside workspace
      (package.workspace). A root whose own manifest carries
      a [workspace] table self-anchors against the workspace
      axis, and an ancestor workspace that excludes the
      crate's relative path leaves it standalone (probed).
    - make reads no parent file (probed: a parent Makefile's
      test target never fires), and the unittest legs read
      no configuration at all; a root-level sitecustomize.py
      does NOT execute at either Python leg's startup under
      the verifier's -m argv shapes (probed — it fires only
      through PYTHONPATH, the disclosed caller-environment
      channel, or an explicit import by bound code), and it
      is bound as ordinary root content regardless (pinned
      in test_receipts.py).
    """

    def _verify(self, root: Path, receipts: Path):
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
        records = []
        if receipts.exists():
            records = [
                json.loads(line)
                for line in receipts.read_text().splitlines()
            ]
        return rc, records, stdout.getvalue()

    def _check(self, receipts: Path, root: Path):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = mechanical_verify.check_receipts(receipts, "t", root)
        return rc, stdout.getvalue()

    def _ids(self, root: Path) -> list[str]:
        return [c.id for c in discover_verification_commands(root)]

    def _pinned(self, root: Path, config: str):
        resolved = str(root.resolve())
        return mechanical_verify.PYTEST_ARGV + (
            "-c",
            config,
            "--rootdir",
            resolved,
            "--confcutdir",
            resolved,
        )

    def _hostile_parent(self, ancestor: Path, with_cache_plant: bool):
        write(ancestor, "pytest.ini", "[pytest]\naddopts = --last-failed\n")
        write(
            ancestor,
            "conftest.py",
            "from pathlib import Path\n\n\n"
            "def pytest_collection_modifyitems(config, items):\n"
            "    Path(config.rootpath, 'sentinel.txt')"
            ".write_text('ancestor conftest ran')\n"
            "    items[:] = [i for i in items"
            " if 'test_bad' not in i.nodeid]\n",
        )
        if with_cache_plant:
            write(
                ancestor,
                ".pytest_cache/v/cache/lastfailed",
                '{"tree/test_ok.py::test_ok": true}',
            )

    # -- the pytest argv pin ------------------------------------

    def test_pytest_argv_pins_root_and_devnull_without_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(
                commands[0].argv, self._pinned(root, os.devnull)
            )

    def test_pytest_argv_pins_the_selected_real_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pytest.ini", "[pytest]\n")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(
                commands[0].argv,
                self._pinned(root, str((root / "pytest.ini").resolve())),
            )

    def test_pytest_argv_symlink_config_pins_devnull_and_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            (root / "tests").mkdir(parents=True)
            external = write(base, "external/pytest.ini", "[pytest]\n")
            os.symlink(external, root / "pytest.ini")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(
                commands[0].argv, self._pinned(root, os.devnull)
            )

    # -- pytest: the validator's instances flip -----------------

    @unittest.skipUnless(_pytest_on_path(), "pytest not available")
    def test_ancestor_config_cache_and_conftest_cannot_steer(self):
        # Validation 5, B-A1: the ancestor's pytest.ini arms
        # --last-failed against its own planted cache, and its
        # conftest deselects the failing test. Unpinned, the
        # bare tree seals a subset PASS; pinned, the full
        # in-tree set runs and the failing test fails the run.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ancestor = base / "ancestor"
            root = ancestor / "tree"
            root.mkdir(parents=True)
            self._hostile_parent(ancestor, with_cache_plant=True)
            write(root, "test_ok.py", "def test_ok():\n    assert True\n")
            write(root, "test_bad.py", "def test_bad():\n    assert False\n")
            receipts = base / "receipts.jsonl"
            rc, _records, output = self._verify(root, receipts)
            self.assertEqual(rc, 1, output)
            self.assertFalse((ancestor / "sentinel.txt").exists())

    @unittest.skipUnless(_pytest_on_path(), "pytest not available")
    def test_passing_tree_under_hostile_parent_seals_full_set(self):
        # The ancestor's config is benign text; its conftest
        # alone would deselect a passing test and shrink the
        # sealed count. Pinned, the seal attests the FULL
        # in-tree set and the ancestor conftest never runs.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ancestor = base / "ancestor"
            root = ancestor / "tree"
            root.mkdir(parents=True)
            write(ancestor, "pytest.ini", "[pytest]\n")
            write(
                ancestor,
                "conftest.py",
                "from pathlib import Path\n\n\n"
                "def pytest_collection_modifyitems(config, items):\n"
                "    Path(config.rootpath, 'sentinel.txt')"
                ".write_text('ancestor conftest ran')\n"
                "    items[:] = [i for i in items"
                " if 'test_more' not in i.nodeid]\n",
            )
            write(root, "test_ok.py", "def test_ok():\n    assert True\n")
            write(root, "test_more.py", "def test_more():\n    assert True\n")
            receipts = base / "receipts.jsonl"
            rc, records, output = self._verify(root, receipts)
            self.assertEqual(rc, 0, output)
            pytest_records = [
                r for r in records if r.get("command_id") == "pytest"
            ]
            self.assertEqual(len(pytest_records), 1)
            self.assertEqual(pytest_records[0]["tests_collected"], 2)
            self.assertFalse((ancestor / "sentinel.txt").exists())

    @unittest.skipUnless(_pytest_on_path(), "pytest not available")
    def test_ancestor_pyproject_fallback_cannot_anchor_rootdir(self):
        # Validation 5, B-A3: a non-qualifying ancestor
        # pyproject.toml anchors rootdir by fallback, admitting
        # the ancestor's conftest. Pinned, the run never sees
        # either.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ancestor = base / "ancestor"
            root = ancestor / "tree"
            root.mkdir(parents=True)
            write(
                ancestor,
                "pyproject.toml",
                '[build-system]\nrequires = ["setuptools"]\n',
            )
            write(
                ancestor,
                "conftest.py",
                "def pytest_collection_modifyitems(config, items):\n"
                "    items[:] = [i for i in items"
                " if 'test_bad' not in i.nodeid]\n",
            )
            write(root, "test_ok.py", "def test_ok():\n    assert True\n")
            write(root, "test_bad.py", "def test_bad():\n    assert False\n")
            receipts = base / "receipts.jsonl"
            rc, _records, output = self._verify(root, receipts)
            self.assertEqual(rc, 1, output)

    @unittest.skipUnless(_pytest_on_path(), "pytest not available")
    def test_in_tree_nonqualifying_pyproject_does_not_anchor(self):
        # The precedence pair, first half (validation 5): the
        # tree's own NON-qualifying pyproject.toml does not
        # anchor rootdir against the parent's pytest.ini — the
        # parent inifile won and steered. Pinned, the walk's
        # no-config judgement is what runs: the parent's
        # --last-failed and conftest never engage and the
        # failing test fails the run.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ancestor = base / "ancestor"
            root = ancestor / "tree"
            root.mkdir(parents=True)
            self._hostile_parent(ancestor, with_cache_plant=True)
            write(
                root,
                "pyproject.toml",
                '[build-system]\nrequires = ["setuptools"]\n',
            )
            write(root, "test_ok.py", "def test_ok():\n    assert True\n")
            write(root, "test_bad.py", "def test_bad():\n    assert False\n")
            receipts = base / "receipts.jsonl"
            rc, _records, output = self._verify(root, receipts)
            self.assertEqual(rc, 1, output)
            self.assertFalse((ancestor / "sentinel.txt").exists())

    @unittest.skipUnless(_pytest_on_path(), "pytest not available")
    def test_in_tree_config_keeps_hostile_parent_inert(self):
        # The precedence pair, second half: a tree carrying
        # its own qualifying config was already safe — the
        # parent's deselect of a passing test changed nothing
        # — and the pin keeps it so, with the run's rootdir on
        # the tree.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ancestor = base / "ancestor"
            root = ancestor / "tree"
            root.mkdir(parents=True)
            write(
                ancestor,
                "pytest.ini",
                "[pytest]\naddopts = --deselect test_ok.py::test_ok\n",
            )
            write(
                ancestor,
                "conftest.py",
                "def pytest_collection_modifyitems(config, items):\n"
                "    items[:] = [i for i in items"
                " if 'test_ok' not in i.nodeid]\n",
            )
            write(root, "pytest.ini", "[pytest]\n")
            write(root, "test_ok.py", "def test_ok():\n    assert True\n")
            write(root, "test_more.py", "def test_more():\n    assert True\n")
            receipts = base / "receipts.jsonl"
            rc, records, output = self._verify(root, receipts)
            self.assertEqual(rc, 0, output)
            pytest_records = [
                r for r in records if r.get("command_id") == "pytest"
            ]
            self.assertEqual(pytest_records[0]["tests_collected"], 2)

    @unittest.skipUnless(_pytest_on_path(), "pytest not available")
    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_git_mode_ancestor_config_cannot_steer(self):
        # Validation 5, B-A2: the tree as its own committed
        # worktree under the hostile parent — ls-tree and
        # tree_clean see only the clean worktree, but the
        # unpinned run still resolves into the parent.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ancestor = base / "ancestor"
            root = ancestor / "tree"
            root.mkdir(parents=True)
            self._hostile_parent(ancestor, with_cache_plant=True)
            write(root, "test_ok.py", "def test_ok():\n    assert True\n")
            write(root, "test_bad.py", "def test_bad():\n    assert False\n")

            def git(*args):
                return subprocess.run(
                    ["git", "-C", str(root), *args],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=60,
                )

            git("init", "-q", "-b", "main")
            git("add", "test_ok.py", "test_bad.py")
            git(
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-q",
                "-m",
                "fixture",
            )
            receipts = base / "receipts.jsonl"
            rc, _records, output = self._verify(root, receipts)
            self.assertEqual(rc, 1, output)
            self.assertFalse((ancestor / "sentinel.txt").exists())

    # -- defence in depth: the transcript's rootdir -------------

    def test_transcript_rootdir_parsing(self):
        parse = mechanical_verify._pytest_transcript_rootdir
        self.assertEqual(parse("rootdir: /a/b\nconfigfile: x\n"), "/a/b")
        # The pre-8 header carried the inifile on the same line.
        self.assertEqual(parse("rootdir: /a/b, inifile: y\n"), "/a/b")
        self.assertIsNone(parse("platform linux\n"))
        self.assertIsNone(parse(""))

    def test_foreign_rootdir_transcript_makes_count_unproven(self):
        # A run whose header names another rootdir attested a
        # different tree than the one the binding covers: its
        # count — however consistent its two channels are —
        # proves nothing about this root.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = _fake_pytest_command(
                "rootdir: /elsewhere/entirely\n2 passed in 0.01s", 2
            )
            result = run_verification(root, command)
            self.assertIsNone(result.tests_collected)
            self.assertFalse(result.passed)

    def test_matching_rootdir_transcript_keeps_the_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = _fake_pytest_command(
                f"rootdir: {root.resolve()}\n2 passed in 0.01s", 2
            )
            result = run_verification(root, command)
            self.assertEqual(result.tests_collected, 2)
            self.assertTrue(result.passed)

    # -- go: GOWORK forced off in the leg's environment ---------

    def _gowork_probe(self, wanted: str) -> VerificationCommand:
        code = (
            "import os, sys; "
            f"sys.exit(0 if os.environ.get('GOWORK') == {wanted!r} else 1)"
        )
        return VerificationCommand(
            "go-test", "Go tests", (sys.executable, "-c", code)
        )

    def test_go_leg_forces_gowork_off_over_the_caller_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.dict(
                os.environ, {"GOWORK": "/somewhere/else/go.work"}
            ):
                result = run_verification(root, self._gowork_probe("off"))
            self.assertEqual(result.exit_code, 0)

    def test_non_go_leg_leaves_the_caller_gowork_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            probe = self._gowork_probe("/somewhere/else/go.work")
            probe = VerificationCommand("make-test", probe.label, probe.argv)
            with mock.patch.dict(
                os.environ, {"GOWORK": "/somewhere/else/go.work"}
            ):
                result = run_verification(root, probe)
            self.assertEqual(result.exit_code, 0)

    @unittest.skipUnless(shutil.which("go"), "go not available")
    def test_go_ancestor_workspace_cannot_supply_code(self):
        # Validation 5, §1.2: the parent go.work puts the run
        # in workspace mode and the outside module executes.
        # With GOWORK forced off, the import cannot resolve in
        # module mode and the leg fails honestly.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write(base, "go.work", "go 1.27\n\nuse (\n\t./lib\n\t./tree\n)\n")
            write(base, "lib/go.mod", "module example.com/lib\n\ngo 1.27\n")
            write(
                base,
                "lib/pkg/pkg.go",
                "package pkg\n\nfunc Value() int { return 1 }\n",
            )
            root = base / "tree"
            write(root, "go.mod", "module example.com/tree\n\ngo 1.27\n")
            write(
                root,
                "main_test.go",
                "package main\n\nimport (\n\t\"testing\"\n\n"
                "\t\"example.com/lib/pkg\"\n)\n\n"
                "func TestValue(t *testing.T) {\n"
                "\tif pkg.Value() != 1 {\n"
                "\t\tt.Fatal(\"wrong value\")\n\t}\n}\n",
            )
            receipts = base / "receipts.jsonl"
            rc, _records, output = self._verify(root, receipts)
            self.assertEqual(rc, 1, output)

    # -- node: ancestor node_modules disqualifies ---------------

    def _node_tree(self, root: Path):
        write(
            root,
            "package.json",
            '{"name": "tree", "scripts": {"test": "node test.js"}}\n',
        )
        write(root, "test.js", "console.log('fine');\n")

    def test_npm_leg_disqualified_by_ancestor_node_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "node_modules").mkdir()
            root = base / "tree"
            root.mkdir()
            self._node_tree(root)
            self.assertNotIn("npm-test", self._ids(root))

    def test_npm_leg_disqualified_by_grandparent_node_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "node_modules").mkdir()
            root = base / "mid" / "tree"
            root.mkdir(parents=True)
            self._node_tree(root)
            self.assertNotIn("npm-test", self._ids(root))

    def test_npm_leg_with_clean_ancestors_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tree"
            root.mkdir()
            self._node_tree(root)
            write(root, "node_modules/leftpad/package.json", "{}\n")
            self.assertIn("npm-test", self._ids(root))

    @unittest.skipUnless(shutil.which("npm"), "npm not available")
    def test_npm_ancestor_instance_leaves_no_commands(self):
        # Validation 5, §1.3 end-to-end: the parent module
        # supplied the sealed run's require. Disqualified, the
        # tree schedules nothing at all.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ancestor = base / "ancestor"
            root = ancestor / "tree"
            root.mkdir(parents=True)
            write(
                ancestor,
                "node_modules/leftpad/package.json",
                '{"name": "leftpad", "main": "index.js"}\n',
            )
            write(
                ancestor,
                "node_modules/leftpad/index.js",
                'module.exports = () => "ok";\n',
            )
            write(
                root,
                "package.json",
                '{"name": "tree", "scripts": {"test": "node test.js"}}\n',
            )
            write(
                root,
                "test.js",
                'const lp = require("leftpad");\n'
                'if (lp() !== "ok") { process.exit(1); }\n',
            )
            receipts = base / "receipts.jsonl"
            rc, _records, output = self._verify(root, receipts)
            self.assertEqual(rc, 2, output)

    @unittest.skipUnless(shutil.which("npm"), "npm not available")
    def test_npm_in_tree_node_modules_seals_and_binds(self):
        # The negative: in-tree node_modules with clean
        # ancestors seals, and mutating the in-tree module
        # stales the audit — the content was inside the root
        # all along.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "tree"
            root.mkdir()
            write(
                root,
                "package.json",
                '{"name": "tree", "scripts": {"test": "node test.js"}}\n',
            )
            write(
                root,
                "test.js",
                'const lp = require("leftpad");\n'
                'if (lp() !== "ok") { process.exit(1); }\n',
            )
            write(
                root,
                "node_modules/leftpad/package.json",
                '{"name": "leftpad", "main": "index.js"}\n',
            )
            index = write(
                root,
                "node_modules/leftpad/index.js",
                'module.exports = () => "ok";\n',
            )
            receipts = root / "receipts.jsonl"
            rc, _records, output = self._verify(root, receipts)
            self.assertEqual(rc, 0, output)
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 0, output)
            index.write_text('module.exports = () => "evil";\n')
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 1, output)
            self.assertIn("STALE", output)

    # -- cargo: ancestor state disqualifies ---------------------

    _ROOT_MANIFEST = '[package]\nname = "tree"\nversion = "0.1.0"\n'

    def _cargo_ids(self, root: Path) -> list[str]:
        return self._ids(root)

    def test_cargo_leg_disqualified_by_covering_ancestor_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write(
                base,
                "Cargo.toml",
                '[workspace]\nmembers = ["tree"]\n',
            )
            root = base / "tree"
            root.mkdir()
            write(root, "Cargo.toml", self._ROOT_MANIFEST)
            self.assertNotIn("cargo-test", self._cargo_ids(root))

    def test_cargo_leg_disqualified_by_unlisted_ancestor_workspace(self):
        # The members list does not name the crate: cargo
        # errors for the plain shape, but a path dependency of
        # a member auto-enrolls a crate the list never names —
        # membership cannot be settled from the list alone, so
        # a non-excluding ancestor workspace disqualifies.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write(
                base,
                "Cargo.toml",
                '[workspace]\nmembers = ["other"]\n',
            )
            root = base / "tree"
            root.mkdir()
            write(root, "Cargo.toml", self._ROOT_MANIFEST)
            self.assertNotIn("cargo-test", self._cargo_ids(root))

    def test_cargo_leg_allowed_when_ancestor_workspace_excludes_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write(
                base,
                "Cargo.toml",
                '[workspace]\nmembers = ["other"]\nexclude = ["tree"]\n',
            )
            root = base / "tree"
            root.mkdir()
            write(root, "Cargo.toml", self._ROOT_MANIFEST)
            self.assertIn("cargo-test", self._cargo_ids(root))

    def test_cargo_leg_allowed_when_root_self_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write(
                base,
                "Cargo.toml",
                '[workspace]\nmembers = ["tree"]\n',
            )
            root = base / "tree"
            root.mkdir()
            write(
                root,
                "Cargo.toml",
                self._ROOT_MANIFEST + "\n[workspace]\n",
            )
            self.assertIn("cargo-test", self._cargo_ids(root))

    def test_cargo_leg_disqualified_by_declared_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "tree"
            root.mkdir()
            write(
                root,
                "Cargo.toml",
                '[package]\nname = "tree"\nversion = "0.1.0"\n'
                'workspace = ".."\n',
            )
            self.assertNotIn("cargo-test", self._cargo_ids(root))

    def test_cargo_leg_disqualified_by_ancestor_cargo_config(self):
        # Config discovery does not stop at the workspace
        # boundary: the root self-anchors and the ancestor
        # config still steers (a rustc-wrapper fires).
        for name in ("config.toml", "config"):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp)
                    write(base, f".cargo/{name}", "[build]\n")
                    root = base / "tree"
                    root.mkdir()
                    write(
                        root,
                        "Cargo.toml",
                        self._ROOT_MANIFEST + "\n[workspace]\n",
                    )
                    self.assertNotIn("cargo-test", self._cargo_ids(root))

    def test_cargo_leg_with_plain_ancestor_manifest_schedules(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write(base, "Cargo.toml", self._ROOT_MANIFEST)
            root = base / "tree"
            root.mkdir()
            write(root, "Cargo.toml", self._ROOT_MANIFEST)
            self.assertIn("cargo-test", self._cargo_ids(root))

    # -- interpreter startup surface ----------------------------

    @unittest.skipUnless(_pytest_on_path(), "pytest not available")
    def test_sitecustomize_does_not_execute_at_leg_startup(self):
        # Probed adjudication (see the class docstring): a
        # root-level sitecustomize.py raising at import would
        # crash the leg if the interpreter executed it at
        # startup; under the verifier's argv it never runs.
        # The file is bound content regardless — its mutation
        # stales the seal (pinned in test_receipts.py).
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "tree"
            root.mkdir()
            write(root, "sitecustomize.py", "raise RuntimeError('startup')\n")
            write(root, "test_ok.py", "def test_ok():\n    assert True\n")
            receipts = base / "receipts.jsonl"
            rc, _records, output = self._verify(root, receipts)
            self.assertEqual(rc, 0, output)


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

    def _receipt_record(self, root: Path, result) -> dict:
        receipts = root / "r.jsonl"
        mechanical_verify.append_receipt(receipts, "t", result)
        return json.loads(receipts.read_text().splitlines()[0])

    def test_receipt_stdout_hash_covers_raw_non_utf8_bytes(self):
        # Issue #38: stdout_sha256 must cover the exact raw capped
        # bytes the runner retained — not the lossy UTF-8 decode,
        # which rewrites every invalid sequence to U+FFFD before the
        # hash is taken.
        payload = b"prefix \xff\xfe\x80 invalid \xc3\x28 tail\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_verification(
                root,
                VerificationCommand(
                    "t",
                    "t",
                    (
                        sys.executable,
                        "-c",
                        f"import sys; sys.stdout.buffer.write({payload!r}); "
                        "sys.stdout.buffer.flush()",
                    ),
                ),
            )
            self.assertEqual(result.exit_code, 0)
            record = self._receipt_record(root, result)
            self.assertEqual(
                record["stdout_sha256"], hashlib.sha256(payload).hexdigest()
            )
            self.assertNotEqual(
                record["stdout_sha256"],
                hashlib.sha256(
                    payload.decode("utf-8", errors="replace").encode("utf-8")
                ).hexdigest(),
            )

    def test_receipt_stderr_hash_covers_raw_non_utf8_bytes(self):
        # Issue #38, stderr twin: stderr_sha256 gets the same
        # raw-bytes treatment as stdout_sha256.
        payload = b"err \xff\xfe\x80 invalid \xc3\x28 tail\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_verification(
                root,
                VerificationCommand(
                    "t",
                    "t",
                    (
                        sys.executable,
                        "-c",
                        f"import sys; sys.stderr.buffer.write({payload!r}); "
                        "sys.stderr.buffer.flush()",
                    ),
                ),
            )
            self.assertEqual(result.exit_code, 0)
            record = self._receipt_record(root, result)
            self.assertEqual(
                record["stderr_sha256"], hashlib.sha256(payload).hexdigest()
            )

    def test_receipt_hash_unchanged_for_pure_ascii_output(self):
        # Control: decode-then-encode is the identity on pure ASCII,
        # so the raw-bytes hash equals what receipts recorded before
        # issue #38 — ASCII receipts are unaffected by the change.
        payload = b"all plain ascii\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_verification(
                root,
                VerificationCommand(
                    "t",
                    "t",
                    (
                        sys.executable,
                        "-c",
                        f"import sys; sys.stdout.buffer.write({payload!r}); "
                        "sys.stdout.buffer.flush()",
                    ),
                ),
            )
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.stdout, payload.decode("utf-8"))
            record = self._receipt_record(root, result)
            self.assertEqual(
                record["stdout_sha256"], hashlib.sha256(payload).hexdigest()
            )

    def test_receipt_stdout_hash_covers_capped_raw_tail(self):
        # Issue #38 at the cap: when output exceeds OUTPUT_CAP_BYTES
        # the receipt hash covers exactly the raw bytes the tail
        # buffer retained (the last OUTPUT_CAP_BYTES) — including a
        # non-UTF-8 tail the decode would have mangled and a leading
        # codepoint the cap may have split.
        cap = mechanical_verify.OUTPUT_CAP_BYTES
        payload = b"a" * (cap + 1000) + b"\xff\xfe" * 500
        retained = payload[-cap:]
        source = (
            f"import sys; sys.stdout.buffer.write("
            f"b'a' * {cap + 1000} + b'\\xff\\xfe' * 500); "
            "sys.stdout.buffer.flush()"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_verification(
                root,
                VerificationCommand("t", "t", (sys.executable, "-c", source)),
            )
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.output_truncated)
            record = self._receipt_record(root, result)
            self.assertEqual(
                record["stdout_sha256"], hashlib.sha256(retained).hexdigest()
            )


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
                _fake_pytest_command("1 passed in 0.01s", 1),
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
                _fake_pytest_command("no tests ran", 0),
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

    def test_exit5_zero_collect_unittest_leg_defers_to_pytest(self):
        # Issue #56: on CPython ≥3.12 the unittest CLI exits 5
        # (_NO_TESTS_EXITCODE) for the same "Ran 0 tests" transcript
        # older versions exit 0 on. The exit-5 presentation of a
        # clean zero collection must defer exactly as exit 0 does —
        # before the fix the run stopped at the unittest leg and
        # the pytest leg never executed.
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
                        "file=sys.stderr); sys.exit(5)",
                    ),
                ),
                _fake_pytest_command("1 passed in 0.01s", 1),
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
            self.assertEqual(results[0].exit_code, 5)
            self.assertEqual(results[0].tests_collected, 0)
            self.assertEqual(results[1].tests_collected, 1)

    def test_genuinely_empty_discovery_with_exit5_presentation_still_fails(
        self,
    ):
        # The exit-5 deferral is not a vacuity hole either: when
        # the remaining Python leg also collects zero, the union is
        # empty and the run still fails the count gate — the
        # unittest leg defers, the final leg's zero fails.
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
                        "file=sys.stderr); sys.exit(5)",
                    ),
                ),
                _fake_pytest_command("no tests ran", 0),
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

    def test_unittest_leg_collecting_and_failing_blocks_run(self):
        # A unittest leg that collected tests and failed is a real
        # failure, not a routing question: no deferral, the run
        # stops, the pytest leg never executes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commands = [
                VerificationCommand(
                    "unittest",
                    "Python unittest",
                    (
                        sys.executable,
                        "-c",
                        "import sys; print('Ran 3 tests in 0.001s', "
                        "file=sys.stderr); sys.exit(1)",
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
            self.assertEqual(rc, 1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].tests_collected, 3)

    def test_unittest_import_error_presentation_does_not_defer(self):
        # A broken unittest leg never presents as a clean zero:
        # the loader fabricates a _FailedTest for an unimportable
        # module, which RUNS — the transcript is "Ran 1 test" with
        # "FAILED (errors=1)" and exit 1 (verified against CPython
        # 3.12.3). Count 1 + exit 1 must not defer: the run stops
        # at the broken leg.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commands = [
                VerificationCommand(
                    "unittest",
                    "Python unittest",
                    (
                        sys.executable,
                        "-c",
                        "import sys; print('Ran 1 test in 0.000s', "
                        "file=sys.stderr); sys.exit(1)",
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
            self.assertEqual(rc, 1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].tests_collected, 1)

    def test_unittest_exit5_with_positive_count_does_not_defer(self):
        # The parsed count wins over the exit code: a leg that
        # reports collected tests is judged on what it ran, even
        # if its process happens to exit 5 — deferral requires the
        # count to be zero.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commands = [
                VerificationCommand(
                    "unittest",
                    "Python unittest",
                    (
                        sys.executable,
                        "-c",
                        "import sys; print('Ran 2 tests in 0.001s', "
                        "file=sys.stderr); sys.exit(5)",
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
            self.assertEqual(rc, 1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].tests_collected, 2)

    def test_unittest_exit5_without_ran_summary_does_not_defer(self):
        # Exit 5 alone is not the signal: a unittest leg that dies
        # before printing its "Ran N tests" summary parses to zero
        # only via the count parser's no-match fallback, and a
        # fallback zero is not evidence of a clean zero collection.
        # The deferral requires the genuinely parsed "Ran 0 tests"
        # line alongside exit 5.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commands = [
                VerificationCommand(
                    "unittest",
                    "Python unittest",
                    (sys.executable, "-c", "import sys; sys.exit(5)"),
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
            self.assertEqual(rc, 1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].tests_collected, 0)

    def test_zero_or_unparseable_count_fails_despite_zero_exit(self):
        # The count verdict rides on VerificationResult, consulted by
        # run_all exactly like survivors_killed: exit 0 without a
        # proven count is a failure, for both Python runners. For
        # pytest the unproven presentation is an honest None (issue
        # #53, round 2): a leg whose report channel produced
        # nothing has no count of record — never a transcript-only
        # number, and never a fabricated 0 standing in for evidence
        # that does not exist.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_verification(
                root,
                _fake_pytest_command("no summary here", None),
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIsNone(result.tests_collected)
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
        # project addopts down to -qq. (The argv also carries
        # Task 15's root pin; the -v element is what this test
        # pins.)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pytest.ini", "[pytest]\naddopts = -q\n")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            resolved = str(root.resolve())
            self.assertEqual(
                commands[0].argv,
                ("python3", "-m", "pytest", "-v")
                + (
                    "-c",
                    str((root / "pytest.ini").resolve()),
                    "--rootdir",
                    resolved,
                    "--confcutdir",
                    resolved,
                ),
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
        # diagnostic phrase appears in test output, and both
        # evidence channels report 1 collected (summary and
        # junitxml report, as a real run produces) — the leg
        # collects 1 and passes.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_verification(
                root,
                _fake_pytest_command(
                    "diagnostic: no tests ran in the legacy suite\n"
                    "1 passed in 0.00s",
                    1,
                ),
            )
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.tests_collected, 1)
            self.assertTrue(result.passed)


class PytestJunitXmlCountTests(unittest.TestCase):
    """Issue #53: the pytest leg's collected count must not depend
    on terminal verbosity. The count comes from the junitxml report
    the same run writes to a tempfile outside the tree, cross-checked
    against the transcript summary whenever verbosity left one: the
    two channels of the same run must agree, or the count is 0
    (fail closed). A missing report makes the count unproven
    (None) and fails the gate — the transcript is never believed
    on its own (round 2)."""

    PASS3 = (
        "def test_a():\n    pass\n\n\n"
        "def test_b():\n    pass\n\n\n"
        "def test_c():\n    pass\n"
    )

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

    # -- the composition rule, unit level --------------------------

    def test_count_composition_rule(self):
        count = mechanical_verify._pytest_collected_count
        summary3 = "===== 3 passed in 0.01s =====\n"
        summary999 = "===== 999 passed in 0.01s =====\n"
        no_summary = ". [100%]\n"
        # Report and summary agree: the count stands.
        self.assertEqual(count(3, summary3, ""), 3)
        self.assertEqual(count(0, "==== no tests ran in 0.00s ====\n", ""), 0)
        # Verbosity suppressed the summary: the report stands alone.
        self.assertEqual(count(3, no_summary, ""), 3)
        self.assertEqual(count(0, no_summary, ""), 0)
        # The channels of the same run disagree: the run proves
        # nothing and the count fails closed — in both directions.
        self.assertEqual(count(999, summary3, ""), 0)
        self.assertEqual(count(3, "", summary999), 0)
        # No report (channel suppressed or never written): the
        # count is unproven whatever the transcript says — the
        # transcript is never believed on its own (round 2; the
        # blocked-plugin fixtures below pin it at run level).
        self.assertIsNone(count(None, "2 passed in 0.01s\n", ""))
        self.assertIsNone(count(None, no_summary, ""))

    def test_junitxml_count_parses_reports(self):
        parse = mechanical_verify._junitxml_count
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            def report(name, text):
                path = base / name
                path.write_text(text)
                return path

            xunit2 = report(
                "x2.xml",
                "<testsuites><testsuite tests='2'>"
                "<testcase classname='a' name='t1'/>"
                "<testcase classname='a' name='t2'><skipped/>"
                "</testcase></testsuite></testsuites>",
            )
            self.assertEqual(parse(xunit2), 2)
            xunit1 = report(
                "x1.xml",
                "<testsuite tests='1'>"
                "<testcase classname='a' name='t1'/></testsuite>",
            )
            self.assertEqual(parse(xunit1), 1)
            empty = report("empty.xml", "<testsuites></testsuites>")
            self.assertEqual(parse(empty), 0)
            self.assertIsNone(parse(report("junk.xml", "not xml <")))
            self.assertIsNone(
                parse(report("wrong.xml", "<html><testcase/></html>"))
            )
            self.assertIsNone(parse(report("blank.xml", "")))
            self.assertIsNone(parse(base / "absent.xml"))

    # -- the defect: stacked quiet levels --------------------------

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_addopts_stacked_quiet_levels_still_collect_count_and_pass(self):
        # The #53 acceptance fixture: addopts stack three quiet
        # levels, suppressing the terminal summary outright. The
        # suite passes and must seal its true collected count.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pytest.ini", "[pytest]\naddopts = -qqq\n")
            write(root, "test_ok.py", self.PASS3)
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 0)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].tests_collected, 3)
            receipts = root / "r.jsonl"
            mechanical_verify.append_receipt(receipts, "t", results[0])
            record = json.loads(receipts.read_text().splitlines()[0])
            self.assertEqual(record["tests_collected"], 3)
            self.assertTrue(
                record["argv"][-1].startswith("--junitxml=")
            )

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_addopts_stacked_quiet_levels_failing_suite_is_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pytest.ini", "[pytest]\naddopts = -qqq\n")
            write(
                root,
                "test_ok.py",
                self.PASS3.replace(
                    "def test_c():\n    pass",
                    "def test_c():\n    assert False",
                ),
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 1)
            self.assertEqual(results[0].tests_collected, 3)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_zero_collection_with_quiet_addopts_fails_closed(self):
        # A genuinely empty suite under -qqq: the report is written
        # with zero testcases, the count is a proven 0, and the run
        # still fails closed.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "pytest.ini", "[pytest]\naddopts = -qqq\n")
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 1)
            self.assertEqual(results[0].exit_code, 5)
            self.assertEqual(results[0].tests_collected, 0)

    # -- channel placement and hygiene ----------------------------

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_pytest_leg_records_executed_argv_and_leaves_tree_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "test_ok.py", "def test_a():\n    pass\n")
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            before = mechanical_verify._fs_tree_digest(root)
            result = run_verification(root, commands[0])
            after = mechanical_verify._fs_tree_digest(root)
            # The evidence artifact never lands inside the tree:
            # the fs digest (which excludes only tool caches) is
            # identical across the run.
            self.assertEqual(before, after)
            self.assertEqual(result.tests_collected, 1)
            flag = result.command.argv[-1]
            self.assertTrue(flag.startswith("--junitxml="))
            report = Path(flag.split("=", 1)[1])
            self.assertFalse(report.is_relative_to(root))
            # The tempfile is consumed and removed by the run.
            self.assertFalse(report.exists())

    # -- adversarial fixtures --------------------------------------

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_forged_report_disagreeing_with_summary_fails_closed(self):
        # A conftest hook overwrites the report file at session
        # finish with 999 fabricated testcases. The transcript
        # summary of the same run says 3 — the channels disagree,
        # so the count is 0 and the leg fails closed rather than
        # sealing the forged number.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "conftest.py",
                "import pytest\n\n"
                "FAKE = '<?xml version=\"1.0\"?>"
                "<testsuites><testsuite tests=\"999\">'\n"
                "FAKE += '<testcase classname=\"x\" name=\"y\"/>'"
                " * 999\n"
                "FAKE += '</testsuite></testsuites>'\n\n\n"
                "@pytest.hookimpl(trylast=True)\n"
                "def pytest_sessionfinish(session, exitstatus):\n"
                "    path = session.config.option.xmlpath\n"
                "    if path:\n"
                "        with open(path, 'w') as fh:\n"
                "            fh.write(FAKE)\n",
            )
            write(root, "test_ok.py", self.PASS3)
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(results[0].tests_collected, 0)
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_forged_summary_disagreeing_with_report_fails_closed(self):
        # The mirror forgery against the transcript channel: a
        # terminal-summary hook writes a fake '999 passed' line to
        # fd 2, after the real summary. The report of the same run
        # says 3 — disagreement, count 0, fail closed. (The
        # transcript-only parser seals 999 here today.)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "conftest.py",
                "import os\nimport pytest\n\n\n"
                "@pytest.hookimpl(trylast=True)\n"
                "def pytest_terminal_summary(terminalreporter,"
                " exitstatus, config):\n"
                "    os.write(2, b'======= 999 passed in 0.01s"
                " =======\\n')\n",
            )
            write(root, "test_ok.py", self.PASS3)
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(results[0].tests_collected, 0)
            self.assertEqual(rc, 1)

    # -- channel suppression is self-defeating (round 2) -----------

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_blocked_junitxml_plugin_makes_the_count_unproven(self):
        # Round 2: addopts blocks the junitxml plugin — a passive
        # bound-config line switches the verifier's evidence
        # channel off. The run completes honestly (3 pass, true
        # summary in the transcript), but the count of record is
        # unproven (None): the transcript is never believed on its
        # own, so the gate fails the leg. Before round 2 this
        # degraded to the transcript count 3 and the run passed.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root, "pytest.ini", "[pytest]\naddopts = -p no:junitxml\n"
            )
            write(root, "test_ok.py", self.PASS3)
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(results[0].exit_code, 0)
            self.assertIsNone(results[0].tests_collected)
            self.assertFalse(results[0].passed)
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_suppressed_report_plus_forged_summary_seals_no_false_pass(
        self,
    ):
        # The task-9 review's Probe A, verbatim: the report
        # channel is suppressed by passive addopts, a conftest
        # deselects all 3 tests (zero execute), writes a fake
        # '999 passed' summary to fd 2 at terminal-summary, and
        # forces exit status 0 at session-finish. At the round-1
        # composition this sealed a false PASS — the transcript
        # fallback believed the one forged channel (count 999,
        # rc 0). Round 2: no report, no proven count, gate fails.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root, "pytest.ini", "[pytest]\naddopts = -p no:junitxml\n"
            )
            write(
                root,
                "conftest.py",
                "import os\n"
                "import pytest\n"
                "\n"
                "\n"
                "def pytest_collection_modifyitems(session, config,"
                " items):\n"
                "    deselected = list(items)\n"
                "    items[:] = []\n"
                "    config.hook.pytest_deselected(items=deselected)\n"
                "\n"
                "\n"
                "@pytest.hookimpl(trylast=True)\n"
                "def pytest_terminal_summary(terminalreporter,"
                " exitstatus, config):\n"
                "    os.write(2, b'======= 999 passed in 0.01s"
                " =======\\n')\n"
                "\n"
                "\n"
                "@pytest.hookimpl(trylast=True)\n"
                "def pytest_sessionfinish(session, exitstatus):\n"
                "    session.exitstatus = 0\n",
            )
            write(root, "test_ok.py", self.PASS3)
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(results[0].exit_code, 0)
            self.assertIsNone(results[0].tests_collected)
            self.assertFalse(results[0].passed)
            self.assertEqual(rc, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_addopts_cannot_redirect_the_report(self):
        # A project addopts --junitxml loses to the verifier's
        # command-line flag (addopts are prepended; the later
        # option wins), so passive config cannot steer the report
        # away from the verifier's tempfile.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "tree"
            root.mkdir()
            evil = base / "evil.xml"
            write(
                root,
                "pytest.ini",
                f"[pytest]\naddopts = --junitxml={evil}\n",
            )
            write(root, "test_ok.py", self.PASS3)
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 0)
            self.assertEqual(results[0].tests_collected, 3)
            self.assertFalse(evil.exists())

    # -- report absent, run already failing: no verdict change ----

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_usage_error_fails_on_exit_code_with_unproven_count(self):
        # A bogus option in the bound config aborts pytest before
        # any session exists (exit 4): no report is written and
        # the count is unproven, but the count gate is not what
        # fails the run — the exit status is, exactly as before
        # round 2. (Round 2 changes verdicts only for runs the
        # count gate itself was carrying.)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pytest.ini",
                "[pytest]\naddopts = --definitely-bogus-option\n",
            )
            write(root, "test_ok.py", self.PASS3)
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(results[0].exit_code, 4)
            self.assertIsNone(results[0].tests_collected)
            self.assertFalse(results[0].passed)
            self.assertEqual(rc, 1)

    def test_killed_pytest_run_fails_on_timeout_not_on_count(self):
        # A run killed at its timeout never writes a report, so
        # its count is unproven — but the failure is the timeout,
        # not the count gate: timed_out alone already fails the
        # result, exactly as before round 2.
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
                        "import time; time.sleep(30)",
                    ),
                ),
                timeout_seconds=1,
            )
            self.assertTrue(result.timed_out)
            self.assertIsNone(result.tests_collected)
            self.assertFalse(result.passed)

    # -- equivalence with the summary channel on ordinary shapes ---

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_deselected_tests_are_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "pytest.ini",
                "[pytest]\naddopts = --deselect test_ok.py::test_c\n",
            )
            write(root, "test_ok.py", self.PASS3)
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 0)
            self.assertEqual(results[0].tests_collected, 2)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_collection_error_count_is_the_sessions_reported_items(self):
        # Count semantics on collection error, pinned: the session
        # reports exactly one item — the erroring module, as a
        # testcase bearing <error> — identical to the transcript
        # parser's error-group counting. The leg fails on its
        # exit code; the count is evidence either way.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_boom.py",
                "raise RuntimeError('import-time failure')\n\n\n"
                "def test_never():\n    pass\n",
            )
            write(
                root,
                "test_ok.py",
                "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["pytest"])
            self.assertEqual(rc, 1)
            self.assertEqual(results[0].tests_collected, 1)


class DeferredZeroReceiptTests(unittest.TestCase):
    # Issue #56, audit side: run_all defers a clean-zero unittest
    # leg (exit 5 on CPython ≥3.12) and seals its receipt with
    # that exit code. check_receipts must accept exactly the
    # segments whose deferral the segment itself proves sound —
    # a later Python leg collected tests and exited 0 — and keep
    # rejecting every other non-zero receipt.

    def _result(self, command_id, exit_code, collected, *, timed_out=False):
        return VerificationResult(
            command=VerificationCommand(command_id, command_id, ("true",)),
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=1,
            stdout="",
            stderr="",
            output_truncated=False,
            tests_collected=collected,
        )

    def _seal(self, base: Path, results):
        root = base / "root"
        root.mkdir()
        write(root, "placeholder.txt", "fixture\n")
        receipts = base / "receipts.jsonl"
        binding = mechanical_verify.tree_binding(root, receipts)
        run_id = "deferred-zero-test"
        mechanical_verify.append_run_start(
            receipts, "t", run_id, binding=binding
        )
        for result in results:
            mechanical_verify.append_receipt(
                receipts, "t", result, run_id=run_id
            )
        mechanical_verify.append_completion(
            receipts,
            "t",
            [r.command for r in results],
            run_id=run_id,
            binding=binding,
        )
        return root, receipts

    def _check(self, receipts, root):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = mechanical_verify.check_receipts(receipts, "t", root)
        return rc, stdout.getvalue()

    def test_deferred_zero_receipt_passes_check_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("unittest", 5, 0),
                    self._result("pytest", 0, 1),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 0, output)
            self.assertIn("RECEIPTS: PASS", output)

    def test_exit5_receipt_without_collecting_leg_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("unittest", 5, 0),
                    self._result("pytest", 0, 0),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 1)
            self.assertIn("receipt failed: unittest", output)

    def test_exit5_receipt_with_positive_count_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("unittest", 5, 2),
                    self._result("pytest", 0, 1),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 1)
            self.assertIn("receipt failed: unittest", output)

    def test_exit5_pytest_receipt_is_not_a_deferred_zero(self):
        # The no-tests exit presentation is excused only for the
        # unittest leg whose deferral run_all performs; a pytest
        # receipt carrying exit 5 remains a failed receipt.
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("pytest", 5, 0),
                    self._result("unittest", 0, 1),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 1)
            self.assertIn("receipt failed: pytest", output)

    def test_collecting_leg_must_follow_the_deferred_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("pytest", 0, 1),
                    self._result("unittest", 5, 0),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 1)
            self.assertIn("receipt failed: unittest", output)

    def test_exit5_receipt_with_timed_out_collecting_leg_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("unittest", 5, 0),
                    self._result("pytest", 0, 1, timed_out=True),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 1)
            self.assertIn("receipt failed: unittest", output)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_mixed_fixture_seals_and_check_receipts_passes(self):
        # End to end (the issue's scenario through the CLI path):
        # the speculative unittest leg collects zero and exits 5,
        # run_all defers, pytest collects and passes, the segment
        # seals — and the audit accepts it.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "shared_mixin.py", "class Mixin:\n    pass\n")
            write(
                root,
                "test_mixed.py",
                "from shared_mixin import Mixin\n\n\n"
                "class TestMixed(Mixin):\n"
                "    def test_ok(self):\n"
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
            records = [
                json.loads(line) for line in receipts.read_text().splitlines()
            ]
            unittest_receipts = [
                r for r in records if r.get("command_id") == "unittest"
            ]
            self.assertEqual(len(unittest_receipts), 1)
            self.assertEqual(unittest_receipts[0]["exit_code"], 5)
            self.assertEqual(unittest_receipts[0]["tests_collected"], 0)
            check_rc, check_output = self._check(receipts, root)
            self.assertEqual(check_rc, 0, check_output)


class SpeculativeZeroReceiptTests(unittest.TestCase):
    # Issue #51, round 3 (R1): run_all excuses a speculative
    # leg's clean zero against the union of the run — any
    # Python leg's pass, in any position (round 2). The receipts
    # path must reach the same verdict for the runs that excuse
    # creates: append_receipt records the leg's speculative mark
    # in the segment (an additive field, covered by the chain),
    # and check_receipts accepts a marked zero only when the
    # segment itself proves another Python leg genuinely passed.
    # Receipts without the mark — everything sealed before this
    # field existed, and every deterministic leg — default to
    # deterministic and stay fail-closed.

    def _result(
        self, command_id, exit_code, collected, *, speculative=False
    ):
        return VerificationResult(
            command=VerificationCommand(
                command_id, command_id, ("true",), speculative=speculative
            ),
            exit_code=exit_code,
            timed_out=False,
            duration_ms=1,
            stdout="",
            stderr="",
            output_truncated=False,
            tests_collected=collected,
        )

    def _seal(self, base: Path, results):
        root = base / "root"
        root.mkdir()
        write(root, "placeholder.txt", "fixture\n")
        receipts = base / "receipts.jsonl"
        binding = mechanical_verify.tree_binding(root, receipts)
        run_id = "speculative-zero-test"
        mechanical_verify.append_run_start(
            receipts, "t", run_id, binding=binding
        )
        for result in results:
            mechanical_verify.append_receipt(
                receipts, "t", result, run_id=run_id
            )
        mechanical_verify.append_completion(
            receipts,
            "t",
            [r.command for r in results],
            run_id=run_id,
            binding=binding,
        )
        return root, receipts

    def _check(self, receipts, root):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = mechanical_verify.check_receipts(receipts, "t", root)
        return rc, stdout.getvalue()

    def _verify_via_main(self, base: Path):
        root = base / "root"
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
        records = [
            json.loads(line) for line in receipts.read_text().splitlines()
        ]
        return root, receipts, rc, records, stdout.getvalue()

    def test_speculative_pytest_zero_receipt_passes_check_receipts(self):
        # The round-2 headline presentation in receipt form: the
        # speculative pytest zero is excused by an EARLIER leg's
        # pass (the position Task 2's acceptor cannot mirror).
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("unittest", 0, 1),
                    self._result("pytest", 5, 0, speculative=True),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 0, output)
            self.assertIn("RECEIPTS: PASS", output)

    def test_speculative_pytest_zero_receipt_excused_by_later_leg(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("pytest", 5, 0, speculative=True),
                    self._result("unittest", 0, 1),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 0, output)
            self.assertIn("RECEIPTS: PASS", output)

    def test_speculative_unittest_zero_receipt_passes_check_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("pytest", 0, 1),
                    self._result("unittest", 5, 0, speculative=True),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 0, output)
            self.assertIn("RECEIPTS: PASS", output)

    def test_unmarked_pytest_zero_receipt_still_fails(self):
        # A zero receipt with no speculative mark — a
        # deterministic leg, or any receipt sealed before the
        # mark existed — is a failed receipt, exactly as before.
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("unittest", 0, 1),
                    self._result("pytest", 5, 0),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 1)
            self.assertIn("receipt failed: pytest", output)

    def test_deterministic_zero_receipt_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("pytest", 5, 0, speculative=False),
                    self._result("unittest", 0, 1),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 1)
            self.assertIn("receipt failed: pytest", output)

    def test_speculative_zero_without_passing_python_leg_fails(self):
        # The excuse is against the union: no Python leg in the
        # segment collected anything, so the marked zero has
        # nothing to be excused by.
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("pytest", 5, 0, speculative=True),
                    self._result("unittest", 0, 0),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 1)
            self.assertIn("receipt failed: pytest", output)

    def test_speculative_receipt_with_positive_count_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, receipts = self._seal(
                Path(tmp),
                [
                    self._result("unittest", 0, 1),
                    self._result("pytest", 5, 2, speculative=True),
                ],
            )
            rc, output = self._check(receipts, root)
            self.assertEqual(rc, 1)
            self.assertIn("receipt failed: pytest", output)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_headline_fixture_seals_and_check_receipts_passes(self):
        # End to end, the round-1 F1 fixture: an open module
        # (star import, helper-only shared) beside a passing
        # TestCase carrying `__test__ = False`. The speculative
        # pytest leg collects literally zero and exits 5; the
        # run seals on the unittest leg's pass — and the audit
        # must now reach the same verdict.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "shared.py", "def helper():\n    pass\n")
            write(
                root,
                "test_star.py",
                "import unittest\n"
                "\n"
                "from shared import *\n"
                "\n"
                "\n"
                "class StarTests(unittest.TestCase):\n"
                "    __test__ = False\n"
                "\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            root, receipts, rc, records, output = self._verify_via_main(
                base
            )
            self.assertEqual(rc, 0, output)
            pytest_receipts = [
                r for r in records if r.get("command_id") == "pytest"
            ]
            self.assertEqual(len(pytest_receipts), 1)
            self.assertEqual(pytest_receipts[0]["exit_code"], 5)
            self.assertEqual(pytest_receipts[0]["tests_collected"], 0)
            self.assertIs(pytest_receipts[0].get("speculative"), True)
            check_rc, check_output = self._check(receipts, root)
            self.assertEqual(check_rc, 0, check_output)
            self.assertIn("RECEIPTS: PASS", check_output)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_mixin_shape_fixture_seals_and_check_receipts_passes(self):
        # The round-2 review's probe (a) shape, end to end: a
        # Test* class on an imported plain mixin (unresolved
        # base) schedules the speculative pytest leg; a real
        # TestCase module passes under unittest; BOTH classes
        # carry `__test__ = False`, so pytest collects literally
        # zero and exits 5. Sealed on the union — audit agrees.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            root.mkdir()
            write(root, "shared_mixin.py", "class Mixin:\n    pass\n")
            write(
                root,
                "test_mixin.py",
                "from shared_mixin import Mixin\n"
                "\n"
                "\n"
                "class TestFromMixin(Mixin):\n"
                "    __test__ = False\n"
                "\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            write(
                root,
                "test_real.py",
                "import unittest\n"
                "\n"
                "\n"
                "class RealTests(unittest.TestCase):\n"
                "    __test__ = False\n"
                "\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            root, receipts, rc, records, output = self._verify_via_main(
                base
            )
            self.assertEqual(rc, 0, output)
            by_id = {
                r["command_id"]: r
                for r in records
                if r.get("command_id") in ("unittest", "pytest")
            }
            self.assertEqual(by_id["unittest"]["exit_code"], 0)
            self.assertEqual(by_id["unittest"]["tests_collected"], 1)
            self.assertEqual(by_id["pytest"]["exit_code"], 5)
            self.assertEqual(by_id["pytest"]["tests_collected"], 0)
            self.assertIs(by_id["pytest"].get("speculative"), True)
            check_rc, check_output = self._check(receipts, root)
            self.assertEqual(check_rc, 0, check_output)
            self.assertIn("RECEIPTS: PASS", check_output)


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

    def test_annotated_assignment_bound_test_function_keeps_pytest_leg(
        self,
    ):
        # Issue #57: the AnnAssign sub-form for test_*
        # FUNCTIONS — `test_ann: object = _impl` binds the
        # same module attribute as the plain assignment, so
        # beside a TestCase sibling the module keeps the
        # pytest leg (the class form above pins Test* names;
        # this pins the function form).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_annassign_function.py",
                "import unittest\n"
                "\n"
                "\n"
                "def _impl():\n"
                "    pass\n"
                "\n"
                "\n"
                "test_ann: object = _impl\n"
                "\n"
                "\n"
                "class Unit(unittest.TestCase):\n"
                "    def test_unit(self):\n"
                "        pass\n",
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

    def test_unpacked_arity_mismatch_judges_paired_elements(self):
        # Issue #52 supersedes round 9's whole-value ruling
        # for sequence values: an arity mismatch no longer
        # falls back to judging the tuple as literal data.
        # Each plainly-bound element is judged against its
        # corresponding value element — TestA pairs with
        # Helper and triggers for its own name; TestB has no
        # corresponding element and triggers nothing by
        # itself. (The line is a runtime ValueError, so both
        # legs fail on it at collection; scheduling the leg
        # cannot produce a false pass.)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root, "TestA, TestB = (Helper,)"
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )

    def test_unpacked_arity_mismatch_testcase_element_is_alias(
        self,
    ):
        # Issue #52, per-element judgment under arity
        # mismatch: an element that plainly denotes TestCase
        # is an alias for its paired name (no trigger for
        # that name), while the next element decides its own
        # name — a class element triggers, literal data does
        # not.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root,
                "TestAlias, TestB = unittest.TestCase, Helper, Other",
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root,
                "TestAlias, TestB = unittest.TestCase, 42, Other",
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])

    def test_unpacked_starred_assignment_judges_plainly_bound_names(
        self,
    ):
        # Issue #52's example: `TestA, *rest = Helper,
        # Other`. The starred element no longer sends the
        # whole level to the whole-value rule — TestA is
        # plainly bound to Helper and is judged against it,
        # so the pytest leg is kept.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root, "TestA, *rest = Helper, Other"
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_unpacked", commands[0].argv)

    def test_unpacked_starred_remainder_with_testcase_value_triggers(
        self,
    ):
        # Issue #52's starred-remainder ruling: the starred
        # target binds a list of the remaining values, and
        # it triggers when at least one remaining value
        # denotes a TestCase. The plainly-bound prefix
        # element here (`first` = 42) triggers nothing, so
        # the remainder alone decides.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root, "first, *TestRemainder = 42, unittest.TestCase"
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )

    def test_unpacked_starred_remainder_of_plain_values_does_not_trigger(
        self,
    ):
        # Negative control for the remainder ruling: a
        # starred remainder of plain (non-TestCase-denoting)
        # values does not trigger by itself, and neither
        # does the literal-bound prefix element.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_unpack_fixture(
                root, "first, *TestRemainder = 42, Helper, Other"
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["unittest"])

    def test_star_import_beside_testcase_gains_pytest_leg(self):
        # Issue #51: a star import makes the module's binding
        # set OPEN — the names it binds are statically
        # unknowable, so pytest-collectable test_* functions it
        # brings in are invisible to every name-based channel.
        # Beside a statically known TestCase class the module
        # must not classify as unittest-only: it gains the
        # speculative pytest leg through the same uncertainty
        # channel as the imported-mixin case.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "shared.py", "def helper():\n    pass\n")
            write(
                root,
                "test_star.py",
                "import unittest\n"
                "\n"
                "from shared import *\n"
                "\n"
                "\n"
                "class StarTests(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_star", commands[0].argv)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_star_imported_pytest_function_executes_and_fails(self):
        # Issue #51, the harm itself: the module's only pytest
        # content is a test_* function arriving via the star
        # import, and it FAILS. Before the fix the module
        # classified unittest-only, the passing TestCase sealed
        # the run, and the failing function never executed.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "shared.py",
                "def test_from_shared():\n"
                "    assert False, 'star-imported test must run'\n",
            )
            write(
                root,
                "test_star.py",
                "import unittest\n"
                "\n"
                "from shared import *\n"
                "\n"
                "\n"
                "class StarTests(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertEqual(rc, 1)
            pytest_results = [
                r for r in results if r.command.id == "pytest"
            ]
            self.assertEqual(len(pytest_results), 1)
            self.assertFalse(pytest_results[0].passed)
            # The TestCase test (re-collected by pytest) plus
            # the star-imported function.
            self.assertEqual(pytest_results[0].tests_collected, 2)

    def test_star_import_without_test_marker_changes_nothing(self):
        # Issue #51 bound: an open module with NO statically
        # known test marker classifies exactly as a closed one
        # — a star import of non-test helpers beside no test
        # content gains no unittest leg and keeps only the
        # no-leg pytest default.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "shared.py", "def helper():\n    pass\n")
            write(
                root,
                "test_plain.py",
                "from shared import *\n"
                "\n"
                "\n"
                "class Helper:\n"
                "    pass\n"
                "\n"
                "\n"
                "def helper_fn():\n"
                "    pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual([c.id for c in commands], ["pytest"])

    def test_star_import_with_visible_test_function_behaves_as_today(
        self,
    ):
        # Issue #51 guard: a visible test_* function triggers
        # the pytest leg deterministically, star import or not —
        # the openness rule must not change this shape.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "shared.py", "def helper():\n    pass\n")
            write(
                root,
                "test_star.py",
                "import unittest\n"
                "\n"
                "from shared import *\n"
                "\n"
                "\n"
                "def test_visible():\n"
                "    pass\n"
                "\n"
                "\n"
                "class StarTests(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands = discover_verification_commands(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertIn("test_star", commands[0].argv)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_star_import_speculative_leg_does_not_veto_unittest(self):
        # Issue #51, the non-veto invariant for this shape —
        # the mirror of the imported-mixin test above. The star
        # import here brings NO pytest content (shared exports
        # only a helper), so the speculative pytest leg adds no
        # collection of its own; it must not veto the passing
        # deterministic unittest leg. (pytest still re-collects
        # the module's TestCase test under its own collection
        # semantics — the counts pin that: the leg collects 1,
        # not zero. The LITERAL-zero presentation is pinned by
        # the next test.)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "shared.py", "def helper():\n    pass\n")
            write(
                root,
                "test_star.py",
                "import unittest\n"
                "\n"
                "from shared import *\n"
                "\n"
                "\n"
                "class StarTests(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertEqual(rc, 0)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].tests_collected, 1)
            self.assertEqual(results[1].tests_collected, 1)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_star_import_speculative_leg_with_literal_zero_does_not_veto(
        self,
    ):
        # Issue #51, round 2: the LITERAL-zero presentation of
        # the non-veto invariant. The TestCase carries pytest's
        # documented opt-out marker `__test__ = False` (idiomatic
        # for shared/abstract bases): the unittest loader ignores
        # the marker and collects the passing test, while pytest
        # collects literally zero and exits 5. The speculative
        # leg sits LAST here, so no deferral to a later leg can
        # rescue it — the non-veto must come from the verdict
        # composition itself: a speculative leg's clean zero
        # never vetoes a run a deterministic Python leg already
        # passed. (On the round-1 code this run failed rc 1:
        # the speculative leg vetoed.)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "shared.py", "def helper():\n    pass\n")
            write(
                root,
                "test_star.py",
                "import unittest\n"
                "\n"
                "from shared import *\n"
                "\n"
                "\n"
                "class StarTests(unittest.TestCase):\n"
                "    __test__ = False\n"
                "\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertEqual(rc, 0)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].tests_collected, 1)
            self.assertTrue(results[0].passed)
            self.assertEqual(results[1].tests_collected, 0)
            self.assertEqual(results[1].exit_code, 5)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_deterministic_pytest_leg_with_literal_zero_still_vetoes(
        self,
    ):
        # Issue #51, round 2 guard: the non-veto belongs to
        # SPECULATIVE legs only. A closed module whose visible
        # test_* function triggers the pytest leg
        # deterministically presents the same literal zero
        # (module-level `__test__ = False` suppresses pytest
        # collection while the TestCase passes under unittest) —
        # and that zero still vetoes: a deterministic leg
        # collecting zero is the genuinely-empty signal the
        # count gate exists to catch.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "test_closed.py",
                "import unittest\n"
                "\n"
                "__test__ = False\n"
                "\n"
                "\n"
                "def test_visible():\n"
                "    pass\n"
                "\n"
                "\n"
                "class ClosedTests(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertEqual(rc, 1)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].tests_collected, 1)
            self.assertEqual(results[1].tests_collected, 0)
            self.assertEqual(results[1].exit_code, 5)

    def _speculative_zero_result(self, command_id, exit_code, stdout):
        return VerificationResult(
            command=VerificationCommand(
                command_id, command_id, ("true",), speculative=True
            ),
            exit_code=exit_code,
            timed_out=False,
            duration_ms=1,
            stdout=stdout,
            stderr="",
            output_truncated=False,
            tests_collected=0,
        )

    def test_speculative_clean_zero_pytest_binds_to_collection_evidence(
        self,
    ):
        # Issue #51, round 3 (R2): a pytest leg's (0, 5) pair is
        # clean only when the transcript's own collection line
        # positively reports zero collection. Exit 5 alone is
        # not conclusive: a tree-supplied conftest can
        # manufacture the pair (see the end-to-end test below).
        clean = self._speculative_zero_result(
            "pytest", 5, "collecting ... collected 0 items\n"
        )
        self.assertTrue(
            mechanical_verify._speculative_clean_zero(
                clean.command, clean
            )
        )
        contradicted = self._speculative_zero_result(
            "pytest", 5, "collecting ... collected 2 items\n"
        )
        self.assertFalse(
            mechanical_verify._speculative_clean_zero(
                contradicted.command, contradicted
            )
        )
        silent = self._speculative_zero_result("pytest", 5, "")
        self.assertFalse(
            mechanical_verify._speculative_clean_zero(
                silent.command, silent
            )
        )

    def test_speculative_clean_zero_unittest_requires_ran_zero_line(self):
        # Re-pin (round 3): the unittest side's transcript
        # requirement is unchanged — the genuine "Ran 0 tests"
        # line, never the fallback zero of a dead runner.
        genuine = self._speculative_zero_result(
            "unittest", 5, "Ran 0 tests in 0.000s\n"
        )
        self.assertTrue(
            mechanical_verify._speculative_clean_zero(
                genuine.command, genuine
            )
        )
        dead = self._speculative_zero_result("unittest", 5, "")
        self.assertFalse(
            mechanical_verify._speculative_clean_zero(dead.command, dead)
        )
        historic = self._speculative_zero_result("unittest", 0, "")
        self.assertTrue(
            mechanical_verify._speculative_clean_zero(
                historic.command, historic
            )
        )

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_conftest_manufactured_pytest_zero_is_not_excused(self):
        # Issue #51, round 3 (R2), end to end — the round-2
        # reviewer's fixture: the shared module exports a real
        # passing test ONLY the speculative pytest leg can run,
        # and a tree-supplied conftest aborts collection via
        # pytest.exit(returncode=5) AFTER printing "collected 2
        # items". The parsed pair (0, 5) is manufactured: the
        # routed tests never ran, so the leg is judged on its
        # merits and the run fails.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "shared.py",
                "def test_from_helpers():\n    assert True\n",
            )
            write(
                root,
                "test_star.py",
                "import unittest\n"
                "\n"
                "from shared import *\n"
                "\n"
                "\n"
                "class StarTests(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            write(
                root,
                "conftest.py",
                "import pytest\n"
                "\n"
                "\n"
                "def pytest_collection_modifyitems(items):\n"
                "    pytest.exit('blocked by conftest', returncode=5)\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertTrue(commands[1].speculative)
            self.assertEqual(rc, 1)
            self.assertEqual(len(results), 2)
            self.assertTrue(results[0].passed)
            self.assertEqual(results[1].tests_collected, 0)
            self.assertEqual(results[1].exit_code, 5)
            self.assertIn("collected 2 items", results[1].stdout)

    @unittest.skipUnless(_path_pytest_available(), "no pytest on PATH")
    def test_conftest_free_star_import_fixture_still_passes(self):
        # Control for the fixture above: without the conftest,
        # the same tree's speculative leg really collects the
        # star-imported test and the run passes on merits.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                "shared.py",
                "def test_from_helpers():\n    assert True\n",
            )
            write(
                root,
                "test_star.py",
                "import unittest\n"
                "\n"
                "from shared import *\n"
                "\n"
                "\n"
                "class StarTests(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual(
                [c.id for c in commands], ["unittest", "pytest"]
            )
            self.assertEqual(rc, 0)
            self.assertEqual(results[1].tests_collected, 2)
            self.assertEqual(results[1].exit_code, 0)

    def test_uncertain_class_only_module_collecting_zero_fails_closed(
        self,
    ):
        # Issue #51, round 2 boundary: the imported-mixin
        # speculative leg in LAST (here: only) position. The
        # uncertain class's name is not Test*, so no pytest leg
        # is scheduled; the speculative unittest leg collects
        # zero because the imported base is not a TestCase.
        # With no deterministic Python leg passing — no verdict
        # for the non-veto to preserve — the run still fails
        # closed, exactly like a genuinely empty discovery.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "shared_mixin.py", "class Mixin:\n    pass\n")
            write(
                root,
                "test_mixin_only.py",
                "from shared_mixin import Mixin\n"
                "\n"
                "\n"
                "class CheckHelpers(Mixin):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            commands, results, rc, _ = self.run_fixture(root)
            self.assertEqual([c.id for c in commands], ["unittest"])
            self.assertEqual(rc, 1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].tests_collected, 0)

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
