#!/usr/bin/env python3
"""Tests for scripts/vendor_graph.py (stdlib unittest, temp fixtures only)."""

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import vendor_graph  # noqa: E402

BLOCK = "<!-- vendor-freshness: {payload} -->"

TREES = [
    ("craft-anything", {"tree": "craft-anything", "pin": "2e4afc5", "repo": "pratik-saptarshi/craft-anything", "branch": "develop", "parent": "storytold/craft-anything", "parent_branch": "main", "policy": "keep", "decision_date": "2026-11-19", "review_due": "2026-11-19"}),
    ("docs-mcp-server", {"tree": "docs-mcp-server", "pin": "506f27b", "repo": "pratik-saptarshi/docs-mcp-server", "branch": "develop", "parent": "arabold/docs-mcp-server", "parent_branch": "main", "policy": "sync-then-repin", "decision_date": "2026-11-19", "review_due": "2026-12-19"}),
    ("elephant-goldfish-model", {"tree": "elephant-goldfish-model", "pin": "e9e1f06", "repo": "pratik-saptarshi/elephant-goldfish-model", "branch": "develop", "parent": "google/elephant-goldfish-model", "parent_branch": "main", "policy": "repin", "decision_date": "2026-11-19", "review_due": "2026-12-19"}),
    ("esf", {"tree": "esf", "pin": "388583d", "repo": "pratik-saptarshi/esf", "branch": "develop", "parent": "mitkox/esf", "parent_branch": "master", "policy": "sync-then-repin", "decision_date": "2026-11-19", "review_due": "2026-12-19"}),
    ("grim-prompter", {"tree": "grim-prompter", "pin": "076ec0d", "repo": "pratik-saptarshi/grim-prompter", "branch": "develop", "parent": "jmanico/grim-prompter", "parent_branch": "main", "policy": "repin", "decision_date": "2026-11-19", "review_due": "2026-12-19"}),
    ("harness-profiler", {"tree": "harness-profiler", "pin": "847bd8f", "repo": "afurmanov/harness-profiler", "branch": "main", "parent": None, "parent_branch": None, "policy": "repin", "decision_date": "2026-11-19", "review_due": "2026-12-19"}),
    ("harness2", {"tree": "harness2", "pin": "e5cda48", "repo": "pratik-saptarshi/harness2", "branch": "develop", "parent": "google-research/harness2", "parent_branch": "main", "policy": "keep", "decision_date": "2026-11-19", "review_due": "2026-12-19"}),
    ("homebrew-install", {"tree": "homebrew-install", "pin": "7986efa", "repo": "pratik-saptarshi/install", "branch": "main", "parent": "Homebrew/install", "parent_branch": "main", "policy": "sync-then-repin", "decision_date": "2026-11-19", "review_due": "2026-12-19"}),
    ("humanizer", {"tree": "humanizer", "pin": "0ef9fe5", "repo": "pratik-saptarshi/humanizer", "branch": "develop", "parent": "blader/humanizer", "parent_branch": "main", "policy": "repin", "decision_date": "2026-11-19", "review_due": "2026-12-19"}),
    ("neurostrata", {"tree": "neurostrata", "pin": "0754125", "repo": "pratik-saptarshi/NeuroStrata", "branch": "develop", "parent": "Cognilogical/NeuroStrata", "parent_branch": "main", "policy": "keep", "decision_date": "2026-11-19", "review_due": "2027-02-19"}),
    ("security-audit-skill", {"tree": "security-audit-skill", "pin": "c1c8a8c", "repo": "pratik-saptarshi/security-audit-skill", "branch": "develop", "parent": "cloudflare/security-audit-skill", "parent_branch": "main", "policy": "repin", "decision_date": "2026-11-19", "review_due": "2026-12-19"}),
    ("ub-mode", {"tree": "ub-mode", "pin": "57a8bdd", "repo": "pratik-saptarshi/ub-mode", "branch": "develop", "parent": "unclebob/ub-mode", "parent_branch": "master", "policy": "repin", "decision_date": "2026-11-19", "review_due": "2026-12-19"}),
    ("neurostrata-ops", {"tree": "neurostrata-ops", "pin": None, "repo": None, "branch": None, "parent": None, "parent_branch": None, "policy": "local", "decision_date": None, "review_due": None}),
]


class VendorGraphTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name, block in TREES:
            d = self.root / "reference" / name
            d.mkdir(parents=True)
            (d / "PROVENANCE.md").write_text(
                "# Provenance\n\npinned at deadbeef\n\n"
                + BLOCK.format(payload=json.dumps(block)) + "\n",
                encoding="utf-8",
            )
        nested = self.root / "reference" / "harness2" / "third_party" / "jb_runner"
        nested.mkdir(parents=True)
        (nested / "PROVENANCE.md").write_text("# nested\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def fake_gh(self, *args, **kwargs):
        return json.dumps({"ahead_by": 0, "behind_by": 0, "status": "identical"})

    def test_parses_all_top_level_blocks_and_ignores_nested(self):
        with mock.patch.object(vendor_graph, "run_gh", side_effect=self.fake_gh):
            graph = vendor_graph.build(self.root)
        self.assertEqual(len(graph), 13, graph)
        names = {e["tree"] for e in graph}
        self.assertIn("neurostrata-ops", names)
        self.assertNotIn("jb_runner", names)
        local = next(e for e in graph if e["tree"] == "neurostrata-ops")
        self.assertIsNone(local["pin"])
        self.assertEqual(local["policy"], "local")

    def test_block_pin_mismatch_with_prose_is_a_finding(self):
        # The test fixture writes prose "deadbeef" against block pin 388583d:
        # the parser must report the mismatch, not silently return the block.
        with mock.patch.object(vendor_graph, "run_gh", side_effect=self.fake_gh):
            report = vendor_graph.build(self.root, findings=True)
        self.assertTrue(any(f.get("tree") == "esf" and "pin" in f.get("why", "") for f in report["findings"]))

    def test_malformed_block_is_a_finding_not_a_skip(self):
        p = self.root / "reference" / "esf" / "PROVENANCE.md"
        p.write_text(p.read_text().replace('"pin": "388583d"', '"pin":'), encoding="utf-8")
        with mock.patch.object(vendor_graph, "run_gh", side_effect=self.fake_gh):
            report = vendor_graph.build(self.root, findings=True)
        self.assertTrue(any(f.get("tree") == "esf" and "block" in f.get("why", "") for f in report["findings"]))

    def test_missing_block_is_a_finding(self):
        (self.root / "reference" / "esf" / "PROVENANCE.md").unlink()
        with mock.patch.object(vendor_graph, "run_gh", side_effect=self.fake_gh):
            report = vendor_graph.build(self.root, findings=True)
        self.assertTrue(any(f.get("tree") == "esf" for f in report["findings"]))

    def test_live_divergence_is_recorded(self):
        def fake(*args, **kwargs):
            return json.dumps({"ahead_by": 5, "behind_by": 57, "status": "diverged"})
        with mock.patch.object(vendor_graph, "run_gh", side_effect=fake):
            graph = vendor_graph.build(self.root)
        esf = next(e for e in graph if e["tree"] == "esf")
        self.assertEqual(esf["fork_vs_head"]["behind_by"], 57)

    def test_test_count_asserted(self):
        # Count assertion mirrors the repo's CI gate: deleting a test fails this.
        src = Path(__file__).read_text(encoding="utf-8")
        needle = "    def " + "test_"
        self.assertEqual(src.count(needle), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
