#!/usr/bin/env python3
"""Tests for scripts/vendor_freshness.py — temp fixtures, mocked gh API."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import vendor_freshness  # noqa: E402
import vendor_graph  # noqa: E402


def fixture_tree(root, name, block, prose=None):
    prose = prose or f"pinned at {block.get('pin') or 'local snapshot'}"
    d = root / "reference" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "PROVENANCE.md").write_text(
        f"# Provenance\n\n{prose}\n\n<!-- vendor-freshness: {json.dumps(block)} -->\n",
        encoding="utf-8",
    )


def block(name, pin="abc1234", policy="repin", review_due="2026-12-19", parent=None):
    return {
        "tree": name, "pin": pin, "repo": f"pratik-saptarshi/{name}", "branch": "develop",
        "parent": parent, "parent_branch": "main", "policy": policy,
        "decision_date": "2026-11-19", "review_due": review_due,
    }


class VendorFreshnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def compare(self, behind=0, ahead=0):
        return json.dumps({"behind_by": behind, "ahead_by": ahead, "status": "identical" if behind == ahead == 0 else "behind"})

    def test_stale_pin_is_a_finding(self):
        fixture_tree(self.root, "alpha", block("alpha"))
        with mock.patch.object(vendor_graph, "run_gh", side_effect=lambda *a, **k: self.compare(behind=5)):
            report = vendor_freshness.build(self.root)
        self.assertTrue(any(f["kind"] == "pin-behind" and f["behind"] == 5 for f in report["findings"]))

    def test_fork_behind_parent_is_a_finding(self):
        b = block("beta", parent="upstream/beta")
        fixture_tree(self.root, "beta", b)
        calls = []

        def fake(*a, **k):
            calls.append(a)
            return self.compare(behind=0) if len(calls) == 1 else self.compare(behind=4)
        with mock.patch.object(vendor_graph, "run_gh", side_effect=fake):
            report = vendor_freshness.build(self.root)
        self.assertTrue(any(f["kind"] == "fork-behind-upstream" and f["behind"] == 4 for f in report["findings"]))

    def test_missing_block_is_a_finding_not_a_skip(self):
        d = self.root / "reference" / "gamma"
        d.mkdir(parents=True)
        (d / "PROVENANCE.md").write_text("# Provenance\n\nno block here\n", encoding="utf-8")
        fixture_tree(self.root, "delta", block("delta"))
        with mock.patch.object(vendor_graph, "run_gh", side_effect=lambda *a, **k: self.compare()):
            report = vendor_freshness.build(self.root)
        self.assertTrue(any(f["kind"] == "missing-block" and f["tree"] == "gamma" for f in report["findings"]))

    def test_current_pin_has_no_finding(self):
        fixture_tree(self.root, "epsilon", block("epsilon"))
        with mock.patch.object(vendor_graph, "run_gh", side_effect=lambda *a, **k: self.compare()):
            report = vendor_freshness.build(self.root)
        self.assertEqual(report["findings"], [])

    def test_local_entry_is_ignored(self):
        fixture_tree(self.root, "neurostrata-ops", {"tree": "neurostrata-ops", "pin": None, "policy": "local"}, prose="local snapshot")
        with mock.patch.object(vendor_graph, "run_gh", side_effect=AssertionError("gh called for local tree")):
            report = vendor_freshness.build(self.root)
        self.assertEqual(report["findings"], [])

    def test_keep_past_due_is_decision_due(self):
        fixture_tree(self.root, "zeta", block("zeta", policy="keep", review_due="2026-01-01"))
        with mock.patch.object(vendor_graph, "run_gh", side_effect=lambda *a, **k: self.compare()):
            report = vendor_freshness.build(self.root)
        self.assertTrue(any(f["kind"] == "decision-due" and f["tree"] == "zeta" for f in report["findings"]))

    def test_issue_body_has_stable_marker(self):
        body = vendor_freshness.issue_body({"findings": [{"kind": "pin-behind", "tree": "alpha", "behind": 5}]})
        self.assertIn("<!-- vendor-freshness-report -->", body)
        self.assertIn("alpha", body)

    def test_test_count_asserted(self):
        src = Path(__file__).read_text(encoding="utf-8")
        needle = "    def " + "test_"
        self.assertEqual(src.count(needle), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
