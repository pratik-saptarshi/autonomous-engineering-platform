"""Tests for the ops/tool-adoption scripts.

Each test class covers one shipped script under ``ops/tool-adoption/``.
The tests extract the relevant function / caller text from the shipped
script and execute it under stubs, so they regress if the shipped code
reverts. Later findings append their own test classes to this file.
"""

import os
import shlex
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PLANNOTATOR_INSTALL = REPO_ROOT / "ops" / "tool-adoption" / "plannotator" / "install.sh"
ISOLATION_INSTALL = REPO_ROOT / "ops" / "tool-adoption" / "isolation" / "install.sh"
SANDBOX_RUN = (
    REPO_ROOT / "ops" / "tool-adoption" / "isolation" / "bin" / "sandbox-run"
)


def _extract_function(text, name):
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.startswith(f"{name}() {{"):
            start = idx
            break
    if start is None:
        raise AssertionError(f"function {name}() not found")
    for idx in range(start + 1, len(lines)):
        if lines[idx] == "}":
            return "\n".join(lines[start : idx + 1]) + "\n"
    raise AssertionError(f"function {name}() has no closing brace")


def _extract_caller_block(text):
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if "if verify_attestation" in line:
            start = idx
            break
    if start is None:
        raise AssertionError("caller block 'if verify_attestation' not found")
    for idx in range(start + 1, len(lines)):
        if lines[idx] == "  fi":
            return "\n".join(lines[start : idx + 1]) + "\n"
    raise AssertionError("caller block has no closing '  fi'")


class PlannotatorAttestationTests(unittest.TestCase):
    """Finding 1: attestation rejection must fail closed.

    verify_attestation() must distinguish gh absent (1) from gh present
    but verification failed (2) from verified (0), and the caller must
    only take the pinned-checksum proceed path when gh is absent.
    """

    @classmethod
    def setUpClass(cls):
        cls.install_text = PLANNOTATOR_INSTALL.read_text()
        cls.function_text = _extract_function(cls.install_text, "verify_attestation")
        cls.caller_text = _extract_caller_block(cls.install_text)

    def _run_sh(self, body, gh_mode):
        """Run body under /bin/sh with a stub gh controlled by gh_mode.

        gh_mode: "accept" (stub exits 0), "reject" (stub exits 1),
        or "absent" (no gh on PATH).
        """
        with tempfile.TemporaryDirectory() as tmp:
            stub_dir = Path(tmp) / "bin"
            stub_dir.mkdir()
            if gh_mode in ("accept", "reject"):
                gh = stub_dir / "gh"
                exit_code = "0" if gh_mode == "accept" else "1"
                gh.write_text(f"#!/bin/sh\nexit {exit_code}\n")
                gh.chmod(0o755)
                path = str(stub_dir)
            elif gh_mode == "absent":
                path = str(stub_dir)
            else:  # pragma: no cover - guard against typos in tests
                raise ValueError(gh_mode)
            env = dict(os.environ)
            env["PATH"] = path
            result = subprocess.run(
                ["/bin/sh", "-c", body],
                capture_output=True,
                text=True,
                env=env,
            )
            return result

    def _caller_body(self, expected):
        return (
            'say() { printf \'%s\\n\' "$*"; }\n'
            'die() { printf \'%s\\n\' "DIE: $*"; exit 99; }\n'
            'REPO="backnotprop/plannotator"\n'
            'TAG="v0.28.63"\n'
            'SIGNER_WORKFLOW="backnotprop/plannotator/.github/workflows/release.yml"\n'
            f'EXPECTED="{expected}"\n'
            'PLATFORM="linux-x64"\n'
            'ASSET="plannotator-linux-x64"\n'
            'staging="/tmp"\n'
            + self.function_text
            + self.caller_text
        )

    def _direct_body(self):
        return (
            'say() { printf \'%s\\n\' "$*"; }\n'
            'die() { printf \'%s\\n\' "DIE: $*"; exit 99; }\n'
            'REPO="backnotprop/plannotator"\n'
            'TAG="v0.28.63"\n'
            'SIGNER_WORKFLOW="backnotprop/plannotator/.github/workflows/release.yml"\n'
            + self.function_text
            + 'verify_attestation "/tmp/plannotator-linux-x64"\n'
            + 'printf \'RC:%s\\n\' "$?"\n'
        )

    # --- caller cases -------------------------------------------------

    def test_caller_accept_verified(self):
        result = self._run_sh(self._caller_body("abc123"), "accept")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("attestation verified", output)
        self.assertNotIn("DIE:", output)

    def test_caller_reject_with_expected_dies(self):
        result = self._run_sh(self._caller_body("abc123"), "reject")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 99, output)
        self.assertIn("DIE:", output)
        self.assertNotIn(
            "proceeding on the pinned checksum anchor", output
        )

    def test_caller_reject_without_expected_dies(self):
        result = self._run_sh(self._caller_body(""), "reject")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 99, output)
        self.assertIn("DIE:", output)

    def test_caller_absent_with_expected_proceeds(self):
        result = self._run_sh(self._caller_body("abc123"), "absent")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("proceeding on the pinned checksum anchor", output)
        self.assertNotIn("DIE:", output)

    def test_caller_absent_without_expected_dies(self):
        result = self._run_sh(self._caller_body(""), "absent")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 99, output)
        self.assertIn("DIE:", output)

    # --- direct return-code assertions --------------------------------

    def test_return_code_absent_is_1(self):
        result = self._run_sh(self._direct_body(), "absent")
        output = result.stdout + result.stderr
        self.assertIn("RC:1", output)

    def test_return_code_reject_is_2(self):
        result = self._run_sh(self._direct_body(), "reject")
        output = result.stdout + result.stderr
        self.assertIn("RC:2", output)

    def test_return_code_accept_is_0(self):
        result = self._run_sh(self._direct_body(), "accept")
        output = result.stdout + result.stderr
        self.assertIn("RC:0", output)


class IsolationInstallDirTests(unittest.TestCase):
    """Finding 2: installed directories need explicit modes.

    place() and the installer's other directory-creation sites must not
    leave install-tree directories at the caller's umask (0700 under
    umask 077); the dropped-privilege payload uid (65534) must be able
    to traverse the whole install chain and read the placed probes.

    The behavioural harness replicates the composite install's
    directory-relevant sequence in order (coordinator addendum,
    option A): the main-flow ensure_dir calls for $WS and $BIN_DIR,
    a placement into $BIN_DIR, the $PILOT_DIR/inner.sh placement,
    then the $PILOT_DIR/probes/probe.py placement.
    """

    @classmethod
    def setUpClass(cls):
        cls.install_text = ISOLATION_INSTALL.read_text()
        cls.sha_of_text = _extract_function(cls.install_text, "sha_of")
        cls.place_text = _extract_function(cls.install_text, "place")
        try:
            cls.ensure_dir_text = _extract_function(
                cls.install_text, "ensure_dir"
            )
        except AssertionError:
            cls.ensure_dir_text = None

    def _harness_body(self, scratch):
        parts = [
            'say() { printf \'%s\\n\' "$*"; }\n',
            'die() { printf \'%s\\n\' "DIE: $*" >&2; exit 99; }\n',
            self.sha_of_text,
        ]
        if self.ensure_dir_text is not None:
            parts.append(self.ensure_dir_text)
        parts.append(self.place_text)
        parts.append(
            "WS=" + shlex.quote(str(scratch / "workspace")) + "\n"
            "BIN_DIR=\"$WS/bin\"\n"
            "PILOT_DIR=\"$WS/isolation-pilot\"\n"
            "SRC=" + shlex.quote(str(scratch / "src")) + "\n"
            "umask 077\n"
            # Guarded so that on the pre-fix tree (no ensure_dir) the
            # place-driven assertions still execute and fail on their
            # own modes, rather than the harness dying on a missing
            # function before any placement happens.
            "if type ensure_dir >/dev/null 2>&1; then\n"
            "  ensure_dir \"$WS\"\n"
            "  ensure_dir \"$BIN_DIR\"\n"
            "fi\n"
            "place \"$SRC/bin_fixture\" \"$BIN_DIR/bin_fixture\" 755\n"
            "place \"$SRC/inner_fixture\" \"$PILOT_DIR/inner.sh\" 755\n"
            "place \"$SRC/probe_fixture\" \"$PILOT_DIR/probes/probe.py\" 755\n"
        )
        return "".join(parts)

    def test_install_chain_directories_are_0755_and_traversable(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            scratch = Path(tmp)
            # The scratch root itself must be traversable by uid 65534,
            # or it confounds the dropped-privilege read below.
            scratch.chmod(0o755)
            src = scratch / "src"
            src.mkdir()
            (src / "bin_fixture").write_text("bin fixture\n")
            (src / "inner_fixture").write_text("inner fixture\n")
            (src / "probe_fixture").write_text("probe fixture\n")

            result = subprocess.run(
                ["/bin/sh", "-c", self._harness_body(scratch)],
                capture_output=True,
                text=True,
            )
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)

            ws = scratch / "workspace"
            bin_dir = ws / "bin"
            pilot_dir = ws / "isolation-pilot"
            probes_dir = pilot_dir / "probes"
            placed = [
                bin_dir / "bin_fixture",
                pilot_dir / "inner.sh",
                probes_dir / "probe.py",
            ]
            for path in placed:
                self.assertTrue(path.is_file(), f"placed file missing: {path}")

            for path in (ws, bin_dir, pilot_dir, probes_dir):
                mode = stat.S_IMODE(path.stat().st_mode)
                self.assertEqual(
                    mode,
                    0o755,
                    f"{path} has mode {oct(mode)}, expected 0o755",
                )

            setpriv = shutil.which("setpriv")
            if setpriv is not None:
                read = subprocess.run(
                    [
                        setpriv,
                        "--reuid=65534",
                        "--regid=65534",
                        "--clear-groups",
                        "cat",
                        str(probes_dir / "probe.py"),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    read.returncode,
                    0,
                    "dropped-privilege read of the probes file failed: "
                    + read.stdout
                    + read.stderr,
                )
                self.assertIn("probe fixture", read.stdout)

    def test_mkdir_p_sites_are_only_audited_exceptions(self):
        # The ensure_dir helper's own internal `mkdir -p "$1"` is the
        # sanctioned creation mechanism, not a creation site: remove
        # the helper's text before auditing the remaining sites, or
        # the audit could never pass with the mandated fix in place.
        audited_text = self.install_text
        if self.ensure_dir_text is not None:
            audited_text = audited_text.replace(self.ensure_dir_text, "")
        allowed = (
            'mkdir -p "$staging/extract"',
            'mkdir -p "$BREW_PREFIX"',
            'brew_as_user mkdir -p "$BREW_PREFIX/bin"',
        )
        offenders = []
        for line in audited_text.splitlines():
            if line.lstrip().startswith("#"):
                # Comment prose (e.g. the ensure_dir header, which
                # mentions mkdir -p by name) is not a creation site.
                continue
            if "mkdir -p" not in line:
                continue
            if any(exception in line for exception in allowed):
                continue
            offenders.append(line.strip())
        self.assertEqual(
            offenders,
            [],
            "unaudited mkdir -p sites remain in isolation/install.sh: "
            + "; ".join(offenders),
        )


class SandboxRunHogtestTests(unittest.TestCase):
    """Finding 3: hogtest must create $PILOT/logs before redirecting into it.

    cmd_hogtest() truncates, appends to, and tees files under
    $PILOT/logs/, but on a fresh install tree nothing creates that
    directory, so every redirection fails with "No such file or
    directory" and the hog workload never runs. The harness runs the
    extracted cmd_hogtest in bash against a fresh PILOT with NO logs/
    subdirectory; a python3 PATH shim that exits 0 immediately stands
    in for the host sentinel, so the memwatch loop's kill -0 fails
    fast. The shim dir goes first on PATH with the rest of PATH kept
    intact for the real coreutils the function uses.
    """

    @classmethod
    def setUpClass(cls):
        cls.sandbox_text = SANDBOX_RUN.read_text()
        cls.hogtest_text = _extract_function(cls.sandbox_text, "cmd_hogtest")

    def test_hogtest_creates_pilot_logs_and_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            pilot = scratch / "pilot"
            pilot.mkdir()
            # Deliberately NO pilot/logs/: a fresh install tree has none.
            run_dir = scratch / "runs" / "test1"
            (run_dir / "worktree").mkdir(parents=True)

            shim_dir = scratch / "shim"
            shim_dir.mkdir()
            python3_stub = shim_dir / "python3"
            python3_stub.write_text("#!/bin/sh\nexit 0\n")
            python3_stub.chmod(0o755)

            body = (
                "PILOT=" + shlex.quote(str(pilot)) + "\n"
                "check_tools() { :; }\n"
                "run_dir_for() { printf '%s\\n' "
                + shlex.quote(str(run_dir))
                + "; }\n"
                'cmd_exec() { printf \'[exec] %s\\n\' "$*"; return 0; }\n'
                'die() { printf \'%s\\n\' "DIE: $*" >&2; exit 99; }\n'
                + self.hogtest_text
                + "cmd_hogtest test1\n"
            )
            env = dict(os.environ)
            env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                ["/bin/bash", "-c", body],
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertNotIn("No such file or directory", result.stderr)
            self.assertTrue(
                (pilot / "logs" / "hog-test1.log").is_file(),
                "hog log missing: " + output,
            )
            self.assertTrue(
                (pilot / "logs" / "hog-summary-test1.txt").is_file(),
                "hog summary missing: " + output,
            )


if __name__ == "__main__":
    unittest.main()
