"""Tests for scripts/check_egm_drift.py.

unittest.TestCase style only: CI runs
``python3 -m unittest discover -s scripts/tests``.

Each test builds a temp skills tree plus bundle fixture and drives
the checker CLI via subprocess, exactly as the CI job
(skills-routing-check) exercises it.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SCRIPT = REPO_ROOT / "scripts" / "check_egm_drift.py"

DESCRIPTION = "Alpha skill description, complete and untruncated."


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class EgmDriftTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.skills = self.base / "skills"
        self.bundle = self.base / "reference" / "elephant-goldfish-model"
        self._build_clean_tree()

    def _build_clean_tree(self):
        _write(
            self.skills / "egm-alpha" / "SKILL.md",
            "---\n"
            "name: egm-alpha\n"
            "description: >-\n"
            "  Alpha skill description, complete and\n"
            "  untruncated.\n"
            "---\n\n# Alpha\n")
        _write(
            self.skills / "egm-alpha" / "skill.yaml",
            'name: "egm-alpha"\n'
            f'description: "{DESCRIPTION}"\n')
        _write(
            self.skills / "egm-review-loop" / "SKILL.md",
            "---\n"
            "name: egm-review-loop\n"
            "description: Loop.\n"
            "---\n\n"
            "Normalize: `egm-alpha` → `alpha`, `egm-beta` →\n"
            "`beta`.\n")
        _write(
            self.skills / "egm-review-loop" / "skill.yaml",
            'name: "egm-review-loop"\ndescription: "Loop."\n')
        _write(
            self.skills / "egm-review" / "SKILL.md",
            "---\n"
            "name: egm-review\n"
            "description: Review.\n"
            "---\n\n"
            "Invoke with reviewers `[egm-alpha, egm-beta]`, standards "
            '`{"egm-alpha": "std-one", "egm-beta": "std-one"}`.\n')
        _write(
            self.skills / "egm-review" / "skill.yaml",
            'name: "egm-review"\ndescription: "Review."\n')
        for stem, name in (("alpha", "egm-alpha"), ("beta", "egm-beta")):
            _write(
                self.bundle / "agents" / f"{stem}.md",
                f"---\nname: {name}\ndescription: Persona.\n---\n")
        _write(
            self.bundle / "resources" / "document_standards" / "std-one.md",
            "# Standard\n")

    def run_check(self):
        return subprocess.run(
            [sys.executable, str(REAL_SCRIPT),
             "--root", str(self.skills), "--bundle", str(self.bundle)],
            capture_output=True, text=True)

    def test_clean_tree_passes(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_truncated_yaml_description_fails(self):
        yaml_path = self.skills / "egm-alpha" / "skill.yaml"
        yaml_path.write_text(
            yaml_path.read_text(encoding="utf-8").replace(
                "complete and untruncated.", "complete and"),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("description differs", result.stdout)

    def test_single_quoted_yaml_description_passes(self):
        # Re-quoting the description with single quotes changes no
        # character of the value; the old _scalar returned the quotes
        # as part of the value and flagged it as drift.
        yaml_path = self.skills / "egm-alpha" / "skill.yaml"
        yaml_path.write_text(
            yaml_path.read_text(encoding="utf-8").replace(
                f'description: "{DESCRIPTION}"',
                f"description: '{DESCRIPTION}'"),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        # A changed word inside the single quotes is still drift.
        yaml_path.write_text(
            yaml_path.read_text(encoding="utf-8").replace(
                "complete and untruncated", "complete and shortened"),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("description differs", result.stdout)

    def test_wrong_table_shortname_fails(self):
        loop_path = self.skills / "egm-review-loop" / "SKILL.md"
        loop_path.write_text(
            loop_path.read_text(encoding="utf-8").replace(
                "`egm-alpha` → `alpha`", "`egm-alpha` → `alfa`"),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("normalization table maps", result.stdout)

    def test_missing_table_entry_fails(self):
        _write(
            self.bundle / "agents" / "gamma.md",
            "---\nname: egm-gamma\ndescription: Persona.\n---\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no normalization-table entry", result.stdout)

    def test_prose_pair_cannot_rescue_deleted_table_row(self):
        # Delete the egm-beta row from the table but mention the same
        # pair in prose elsewhere in the file. The whole-file scan —
        # the old rule (b) behaviour — is masked by the prose pair;
        # the anchored scan must still report the missing row.
        loop_path = self.skills / "egm-review-loop" / "SKILL.md"
        loop_path.write_text(
            loop_path.read_text(encoding="utf-8").replace(
                ", `egm-beta` →\n`beta`", "")
            + "\nElsewhere, prose mentions `egm-beta` → `beta`.\n",
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no normalization-table entry", result.stdout)

    def test_extra_table_persona_fails(self):
        # Reverse direction: the table names a persona the bundle
        # does not carry.
        loop_path = self.skills / "egm-review-loop" / "SKILL.md"
        loop_path.write_text(
            loop_path.read_text(encoding="utf-8").replace(
                "`beta`.", "`beta`, `egm-ghost` → `ghost`."),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no agent file carries that frontmatter name",
                      result.stdout)

    def test_duplicate_table_entry_fails(self):
        loop_path = self.skills / "egm-review-loop" / "SKILL.md"
        loop_path.write_text(
            loop_path.read_text(encoding="utf-8").replace(
                "`egm-alpha` → `alpha`",
                "`egm-alpha` → `alpha`, `egm-alpha` → `alpha`"),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("more than once", result.stdout)

    def test_reviewer_missing_from_standards_map_fails(self):
        review_path = self.skills / "egm-review" / "SKILL.md"
        review_path.write_text(
            review_path.read_text(encoding="utf-8").replace(
                ', "egm-beta": "std-one"', ""),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no entry in the call site's standards map",
                      result.stdout)

    def test_unknown_standard_fails(self):
        review_path = self.skills / "egm-review" / "SKILL.md"
        review_path.write_text(
            review_path.read_text(encoding="utf-8").replace(
                '"egm-beta": "std-one"', '"egm-beta": "std-missing"'),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no file in", result.stdout)

    def test_pooled_block_omission_fails(self):
        # Two call sites in ONE paragraph block (no blank line between
        # them): the second site's map omits egm-beta, which the first
        # site's map covers. Pooling the block's maps — the old rule
        # (c) behaviour — would mask the omission.
        review_path = self.skills / "egm-review" / "SKILL.md"
        review_path.write_text(
            review_path.read_text(encoding="utf-8").replace(
                "Invoke with reviewers `[egm-alpha, egm-beta]`, standards "
                '`{"egm-alpha": "std-one", "egm-beta": "std-one"}`.',
                "Invoke `[egm-alpha, egm-beta]`, standards "
                '`{"egm-alpha": "std-one", "egm-beta": "std-one"}`; '
                "invoke again `[egm-alpha, egm-beta]`, standards "
                '`{"egm-alpha": "std-one"}`.'),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no entry in the call site's standards map",
                      result.stdout)

    def test_malformed_standard_name_fails(self):
        # A snake_case standard name is the natural drift shape; the
        # old rule (c) discarded the whole map as prose and passed.
        review_path = self.skills / "egm-review" / "SKILL.md"
        review_path.write_text(
            review_path.read_text(encoding="utf-8").replace(
                '"egm-beta": "std-one"', '"egm-beta": "std_one"'),
            encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("is malformed", result.stdout)


if __name__ == "__main__":
    unittest.main()
