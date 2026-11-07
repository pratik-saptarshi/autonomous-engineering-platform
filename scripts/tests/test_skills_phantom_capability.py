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

    def test_subordinate_clause_negation_does_not_exempt(self):
        # The negation belongs to the if-clause; the main-clause
        # instruction after the comma is unexempted.
        result = self.run_check(
            "If it is not installed, install the Craft Anything "
            "engine.\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("imperative invocation instruction", result.stdout)

    def test_prior_sentence_negation_does_not_exempt(self):
        result = self.run_check(
            "Do not use Ghidra. Instead, invoke the Craft Anything "
            "engine.\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("imperative invocation instruction", result.stdout)

    def test_colon_clause_negation_does_not_exempt(self):
        result = self.run_check(
            "It is not installed: install the Craft Anything engine.\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("imperative invocation instruction", result.stdout)

    def test_guarded_sentence_then_bare_instruction_fails(self):
        # Pairings are evaluated independently: the exempt first
        # sentence does not shelter the bare second one.
        result = self.run_check(
            "Nothing here installs the craft-anything engine. Install "
            "the craft-anything engine.\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("imperative invocation instruction", result.stdout)

    def test_negation_after_noun_does_not_exempt(self):
        result = self.run_check(
            "Install the craft-anything engine, never mind the cost.\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("imperative invocation instruction", result.stdout)

    def test_non_goal_sentence_passes(self):
        # Verbatim guard-dependent line from the protocol skill: the
        # coordinated verb list is governed by "nothing".
        result = self.run_check(
            "No runtime-invocation instructions: nothing here installs, "
            "registers, or calls the craft-anything engine, its CLI, or "
            "its MCP server.\n")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_quoted_status_language_passes(self):
        # Verbatim guard-dependent line from the protocol skill: the
        # in-span "never" exempts the pairing.
        result = self.run_check(
            'Status language for this adoption is "protocol adopted; '
            'engine not installed" — never "craft-anything adopted."\n')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_do_not_verb_list_passes(self):
        result = self.run_check(
            "Do not install, register, or call the craft-anything "
            "engine.\n")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_does_not_verb_list_passes(self):
        result = self.run_check(
            "This skill does not install, register, or call the "
            "craft-anything engine.\n")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_quoted_artifact_name_still_fails(self):
        # Rules (a)-(c) have no negation guard and no quote exemption,
        # by design; quoting the artifact name inside a skill is still
        # a finding.
        result = self.run_check(
            'Quoting the name is no exemption: "craft-anything-cli" '
            "still names the artifact.\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("artifact name", result.stdout)

    def test_clean_tree_of_other_skills_passes(self):
        (self.skills / "other").mkdir()
        result = self.run_check(
            "# Other\n\nUse the usual tools; run the test suite.\n",
            name="other/SKILL.md")
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
