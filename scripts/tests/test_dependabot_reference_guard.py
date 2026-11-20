"""Tests for scripts/dependabot_reference_guard.py.

unittest.TestCase style only: CI runs
``python3 -m unittest discover -s scripts/tests``.

Each test drives the guard CLI via subprocess in dry-run mode (the mode
the workflow's decision step uses) with a fixture changed-files list, so
the CLI contract -- author + file list in, JSON action plan out -- is
exercised exactly as the workflow exercises it. No network, no gh calls:
dry-run never applies actions.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "dependabot_reference_guard.py"

BOT = "dependabot[bot]"
HUMAN = "pratik-saptarshi"


def run_guard(author, files, pr=147):
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False
    ) as fh:
        fh.write("\n".join(files))
        files_path = fh.name
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--pr",
            str(pr),
            "--author",
            author,
            "--files",
            files_path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"guard exited {proc.returncode}: {proc.stderr.strip()}"
        )
    return json.loads(proc.stdout)


class GuardDecisionTests(unittest.TestCase):
    def test_bot_pr_touching_reference_is_routed(self):
        plan = run_guard(BOT, ["reference/docs-mcp-server/package-lock.json"])
        kinds = [a["action"] for a in plan["actions"]]
        self.assertEqual(kinds, ["label", "comment", "close"])
        label = plan["actions"][0]
        self.assertEqual(label["label"], "vendor-refresh-needed")
        comment = plan["actions"][1]["body"]
        # The comment must name the sanctioned route: re-vendoring.
        self.assertIn("re-vendor", comment)

    def test_bot_pr_touching_reference_among_other_files_is_routed(self):
        plan = run_guard(
            BOT,
            ["skills/archify/package.json", "reference/esf/uv.lock"],
        )
        kinds = [a["action"] for a in plan["actions"]]
        self.assertEqual(kinds, ["label", "comment", "close"])

    def test_bot_pr_not_touching_reference_is_untouched(self):
        plan = run_guard(BOT, ["skills/archify/package.json"])
        self.assertEqual(plan["actions"], [])

    def test_human_pr_touching_reference_is_untouched(self):
        plan = run_guard(HUMAN, ["reference/neurostrata/Cargo.toml"])
        self.assertEqual(plan["actions"], [])

    def test_bot_pr_with_no_files_is_untouched(self):
        plan = run_guard(BOT, [])
        self.assertEqual(plan["actions"], [])


if __name__ == "__main__":
    unittest.main()
