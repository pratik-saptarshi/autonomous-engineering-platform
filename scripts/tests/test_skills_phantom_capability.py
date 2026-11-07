"""Tests for scripts/check_skills_phantom_capability.py (Phase 3).

unittest.TestCase style only: CI runs
``python3 -m unittest discover -s scripts/tests``.

Each test builds a temp skills tree and drives the checker CLI via
subprocess, exactly as the CI job (skills-routing-check) exercises it.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SCRIPT = REPO_ROOT / "scripts" / "check_skills_phantom_capability.py"

HONEST_SKILL = """\
# Craft Anything Protocol

engine not installed in this environment; this protocol governs REA/Ghidra
evidence work under clean-room discipline until runtime authorization.

| Question shape | Route | Why |
|---|---|---|
| JS / Electron app structure, module graph, evidence record | REA (`npx -y rea-agents@6.5.0`) | Already pinned, verified, and cheapest. |

- Use the craft-anything-protocol skill when posture must be recorded.
- Nothing here installs, registers, or calls the craft-anything engine,
  its CLI, or its MCP server.
- The reference snapshot lives at reference/craft-anything/ (see
  pratik-saptarshi/craft-anything, pin 2e4afc5).
"""


class PhantomCapabilityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.skills = Path(self._tmp.name) / "skills"
        (self.skills / "some-skill").mkdir(parents=True)

    def run_check(self, text, name="some-skill/SKILL.md"):
        (self.skills / name).write_text(text)
        return subprocess.run(
            [sys.executable, str(REAL_SCRIPT), "--root", str(self.skills)],
            capture_output=True, text=True)

    def test_honest_skill_passes(self):
        result = self.run_check(HONEST_SKILL)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_cli_artifact_name_fails(self):
        result = self.run_check(
            "Run `craft-anything-cli inspect /path/to/app` first.\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("some-skill/SKILL.md:1", result.stdout)
        self.assertIn("artifact name", result.stdout)

    def test_imperative_instruction_fails(self):
        result = self.run_check(
            "Register the craft-anything MCP server, then call its "
            "study tool.\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("imperative invocation instruction", result.stdout)

    def test_command_position_fails(self):
        result = self.run_check(
            "```console\n$ craft-anything inspect ./app\n```\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("command-position invocation", result.stdout)

    def test_mcp_registration_entry_fails(self):
        result = self.run_check(
            '`"craft-anything": {"command": "craft-anything", '
            '"args": ["mcp"]}`\n')
        self.assertEqual(result.returncode, 1)
        self.assertIn("MCP registration entry", result.stdout)

    def test_negated_statement_passes(self):
        result = self.run_check(
            "Nothing here installs, registers, or calls the "
            "craft-anything engine, its CLI, or its MCP server.\n")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_clean_tree_of_other_skills_passes(self):
        (self.skills / "other").mkdir()
        result = self.run_check(
            "# Other\n\nUse the usual tools; run the test suite.\n",
            name="other/SKILL.md")
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
