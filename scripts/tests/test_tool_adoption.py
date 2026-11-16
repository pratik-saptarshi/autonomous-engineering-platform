"""Tests for the ops/tool-adoption scripts.

Each test class covers one shipped script under ``ops/tool-adoption/``.
The tests extract the relevant function / caller text from the shipped
script and execute it under stubs, so they regress if the shipped code
reverts. Later findings append their own test classes to this file.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PLANNOTATOR_INSTALL = REPO_ROOT / "ops" / "tool-adoption" / "plannotator" / "install.sh"


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


if __name__ == "__main__":
    unittest.main()
