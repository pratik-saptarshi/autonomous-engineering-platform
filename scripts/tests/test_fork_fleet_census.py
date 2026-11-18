"""Tests for scripts/fork_fleet_census.py.

unittest.TestCase style only: CI runs
``python3 -m unittest discover -s scripts/tests``.

The census's GitHub reads are exercised through a fake ghg runner
injected into the module, so classification, compare-direction,
unknown-state, consistency, attribution and diff behaviour are all
pinned without network access. The CLI contract (``--check``) is
exercised via subprocess, as the nightly agent run exercises it.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "fork_fleet_census.py"

spec = importlib.util.spec_from_file_location("fork_fleet_census", SCRIPT)
ffc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ffc)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_D = "d" * 40


def compare(ahead, behind, base_sha, head_abbrev, owner="pratik-saptarshi", repo="x"):
    return {
        "status": "ahead" if ahead else ("behind" if behind else "identical"),
        "ahead_by": ahead,
        "behind_by": behind,
        "base_commit": {"sha": base_sha},
        "permalink_url": (
            f"https://github.com/{owner}/{repo}/compare/"
            f"{owner}:{base_sha[:7]}...{owner}:{head_abbrev}"
        ),
    }


def repo_info(parent_full_name=None, parent_default="main"):
    info = {"full_name": "pratik-saptarshi/x"}
    if parent_full_name is not None:
        info["parent"] = {
            "full_name": parent_full_name,
            "default_branch": parent_default,
        }
    return info


class FakeRunner:
    """Maps ghg argument tuples to (obj, err, rc); records calls."""

    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, args):
        self.calls.append(tuple(args))
        key = tuple(args)
        if key in self.table:
            return self.table[key]
        for pattern, value in self.table.items():
            if pattern[-1] == "*" and key[: len(pattern) - 1] == pattern[:-1]:
                return value
        return None, "not found", 1


def info_args(repo="pratik-saptarshi/x"):
    return ("api", f"repos/{repo}")


def mirror_args(repo="pratik-saptarshi/x", upstream="up/x", branch="main"):
    owner = upstream.split("/")[0]
    return ("api", f"repos/{repo}/compare/{branch}...{owner}:{branch}")


def develop_args(repo="pratik-saptarshi/x", branch="main"):
    return ("api", f"repos/{repo}/compare/develop...{branch}")


def branch_args(full_name, branch="main"):
    return ("api", f"repos/{full_name}/branches/{branch}")


def good_table():
    return {
        info_args(): (repo_info("up/x"), None, 0),
        mirror_args(): (compare(5, 0, SHA_A, "b" * 7), None, 0),
        develop_args(): (compare(9, 0, SHA_C, "a" * 7), None, 0),
        branch_args("up/x"): ({"commit": {"sha": SHA_B}}, None, 0),
    }


class ClassificationTests(unittest.TestCase):
    def test_mirror_classification(self):
        self.assertEqual(ffc.classify_mirror(0, 0), "current")
        self.assertEqual(ffc.classify_mirror(4, 0), "behind")
        self.assertEqual(ffc.classify_mirror(0, 2), "blocked-diverged")
        self.assertEqual(ffc.classify_mirror(4, 2), "blocked-diverged")

    def test_develop_classification(self):
        self.assertEqual(ffc.classify_develop(0, 0), "current")
        self.assertEqual(ffc.classify_develop(4, 0), "ff-ready")
        self.assertEqual(ffc.classify_develop(0, 2), "fork-local")
        self.assertEqual(ffc.classify_develop(4, 2), "fork-local")


class CensusRepoTests(unittest.TestCase):
    def census_one(self, table):
        runner = FakeRunner(table)
        return ffc.census_repo("pratik-saptarshi/x", runner), runner

    def test_happy_path(self):
        row, _ = self.census_one(good_table())
        self.assertEqual(row["upstream"], "up/x")
        self.assertEqual(row["mirror_branch"], "main")
        self.assertEqual(row["mirror_status"], "behind")
        self.assertEqual(row["mirror_behind"], 5)
        self.assertEqual(row["mirror_unique"], 0)
        self.assertEqual(row["mirror_head"], SHA_A)
        self.assertEqual(row["upstream_head"], SHA_B)
        self.assertEqual(row["develop_status"], "ff-ready")
        self.assertEqual(row["develop_behind"], 9)
        self.assertEqual(row["develop_fork_local"], 0)
        self.assertEqual(row["develop_head"], SHA_C)

    def test_compare_transposition_fixture(self):
        # Asymmetric counts pin the direction: the develop compare's
        # ahead_by is the lag (mirror commits not in develop) and its
        # behind_by is fork-local. Swapping the fixture must swap the
        # census fields, never reinterpret them.
        table = good_table()
        table[develop_args()] = (compare(7, 3, SHA_C, "a" * 7), None, 0)
        row, _ = self.census_one(table)
        self.assertEqual(row["develop_behind"], 7)
        self.assertEqual(row["develop_fork_local"], 3)
        self.assertEqual(row["develop_status"], "fork-local")
        table = good_table()
        table[develop_args()] = (compare(3, 7, SHA_C, "a" * 7), None, 0)
        row, _ = self.census_one(table)
        self.assertEqual(row["develop_behind"], 3)
        self.assertEqual(row["develop_fork_local"], 7)

    def test_mirror_current_skips_upstream_branch_call(self):
        table = good_table()
        table[mirror_args()] = (compare(0, 0, SHA_A, "a" * 7), None, 0)
        row, runner = self.census_one(table)
        self.assertEqual(row["mirror_status"], "current")
        self.assertEqual(row["upstream_head"], SHA_A)
        self.assertNotIn(branch_args("up/x"), runner.calls)

    def test_unknown_never_zero(self):
        # Mirror compare fails but the branch probe succeeds: the axis
        # is unknown and its counts are None, never a fabricated 0.
        table = good_table()
        table[mirror_args()] = (None, "HTTP 500", 1)
        table[branch_args("pratik-saptarshi/x")] = (
            {"commit": {"sha": SHA_A}},
            None,
            0,
        )
        row, _ = self.census_one(table)
        self.assertEqual(row["mirror_status"], "unknown")
        self.assertIsNone(row["mirror_behind"])
        self.assertIsNone(row["mirror_unique"])
        # Develop compare fails too: same treatment on that axis.
        table = good_table()
        table[develop_args()] = (None, "HTTP 500", 1)
        row, _ = self.census_one(table)
        self.assertEqual(row["develop_status"], "unknown")
        self.assertIsNone(row["develop_behind"])
        self.assertIsNone(row["develop_fork_local"])

    def test_no_mirror_branch(self):
        table = good_table()
        table[mirror_args()] = (None, "404 Not Found", 1)
        table[branch_args("pratik-saptarshi/x")] = (None, "404 Not Found", 1)
        table[develop_args()] = (None, "404 Not Found", 1)
        row, _ = self.census_one(table)
        self.assertEqual(row["mirror_status"], "no-mirror")
        self.assertIsNone(row["mirror_behind"])

    def test_no_parent_is_skip(self):
        table = {info_args(): (repo_info(None), None, 0)}
        row, _ = self.census_one(table)
        self.assertEqual(row["mirror_status"], "skip")
        self.assertEqual(row["develop_status"], "skip")

    def test_consistency_mismatch_marks_row_unknown(self):
        # The develop compare's head (the mirror tip, via permalink)
        # disagrees with the mirror compare's base: publish neither
        # axis rather than two disagreeing figures.
        table = good_table()
        table[develop_args()] = (compare(9, 0, SHA_C, "d" * 7), None, 0)
        row, _ = self.census_one(table)
        self.assertEqual(row["mirror_status"], "unknown")
        self.assertEqual(row["develop_status"], "unknown")
        self.assertIsNone(row["mirror_behind"])
        self.assertIsNone(row["develop_behind"])
        self.assertIn("mismatch", row["error"])

    def test_budget_denial_aborts(self):
        table = {info_args(): (None, "budget denied", 75)}
        runner = FakeRunner(table)
        with self.assertRaises(ffc.BudgetDenied):
            ffc.census_repo("pratik-saptarshi/x", runner)


def census_doc(rows, generated_at="2026-11-18T09:00:00-06:00"):
    return {
        "version": 1,
        "actor": "fork-fleet-census",
        "generated_at": generated_at,
        "repos": rows,
    }


def census_row(repo="pratik-saptarshi/x", **kw):
    row = {
        "repo": repo,
        "upstream": "up/x",
        "mirror_branch": "main",
        "mirror_status": "behind",
        "mirror_behind": 5,
        "mirror_unique": 0,
        "mirror_head": SHA_A,
        "upstream_head": SHA_B,
        "develop_status": "ff-ready",
        "develop_behind": 9,
        "develop_fork_local": 0,
        "develop_head": SHA_C,
        "error": None,
    }
    row.update(kw)
    return row


class BuildRowsTests(unittest.TestCase):
    def test_first_observation_rows(self):
        rows, changed = ffc.build_rows(census_doc([census_row()]), [], {}, "T1")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row[0], "pratik-saptarshi/x")
        self.assertEqual(row[3], "behind")
        self.assertEqual(row[4], 5)
        self.assertEqual(row[6], SHA_A[:12])  # sheet shows short SHAs
        self.assertEqual(row[13], "fork-fleet-census")  # column N
        self.assertEqual(row[14], "T1")  # column O, verified at
        self.assertEqual(changed, [0])

    def test_idempotent_diff(self):
        doc = census_doc([census_row()])
        rows1, _ = ffc.build_rows(doc, [], {}, "T1")
        rows2, changed = ffc.build_rows(doc, rows1, {}, "T2")
        self.assertEqual(changed, [])
        # Only the verified-at stamp moves.
        self.assertEqual(rows2[0][14], "T2")
        self.assertEqual(rows2[0][:14], rows1[0][:14])
        self.assertEqual(rows2[0][15], rows1[0][15])

    def test_unknown_counts_become_blank_cells(self):
        doc = census_doc(
            [
                census_row(
                    mirror_status="unknown",
                    mirror_behind=None,
                    mirror_unique=None,
                    mirror_head=None,
                    upstream_head=None,
                )
            ]
        )
        rows, _ = ffc.build_rows(doc, [], {}, "T1")
        self.assertEqual(rows[0][4], "")
        self.assertEqual(rows[0][5], "")
        self.assertNotEqual(rows[0][4], 0)

    def test_attribution_fork_sync_from_run_record(self):
        doc1 = census_doc([census_row()])
        rows1, _ = ffc.build_rows(doc1, [], {}, "2026-11-18T09:00:00-06:00")
        doc2 = census_doc(
            [census_row(mirror_head=SHA_D, mirror_behind=2)],
            generated_at="2026-11-19T09:00:00-06:00",
        )
        record = {
            "repos": {
                "pratik-saptarshi/x": {
                    "last_applied_at": "2026-11-19T08:00:00-06:00"
                }
            }
        }
        rows2, changed = ffc.build_rows(
            doc2, rows1, record, "2026-11-19T09:00:00-06:00"
        )
        self.assertEqual(changed, [0])
        self.assertEqual(rows2[0][13], "fork-sync")  # column N
        self.assertEqual(rows2[0][12], "2026-11-19T08:00:00-06:00")  # M

    def test_attribution_unknown_external_change(self):
        doc1 = census_doc([census_row()])
        rows1, _ = ffc.build_rows(doc1, [], {}, "T1")
        doc2 = census_doc([census_row(develop_head=SHA_D, develop_behind=4)])
        rows2, _ = ffc.build_rows(doc2, rows1, {}, "T2")
        self.assertEqual(rows2[0][13], "unknown (external change)")

    def test_retired_repo_kept_and_marked(self):
        doc1 = census_doc([census_row()])
        rows1, _ = ffc.build_rows(doc1, [], {}, "T1")
        rows2, changed = ffc.build_rows(census_doc([]), rows1, {}, "T2")
        self.assertEqual(len(rows2), 1)
        self.assertEqual(rows2[0][3], "retired")
        self.assertEqual(rows2[0][8], "retired")
        self.assertEqual(changed, [0])


class ValidateTests(unittest.TestCase):
    def test_valid_census_passes(self):
        self.assertEqual(ffc.validate_census(census_doc([census_row()])), [])

    def test_fabricated_zero_rejected(self):
        bad = census_row(mirror_status="unknown", mirror_behind=0)
        errors = ffc.validate_census(census_doc([bad]))
        self.assertTrue(any("mirror_behind" in e for e in errors))

    def test_bad_status_rejected(self):
        bad = census_row(mirror_status="sideways")
        errors = ffc.validate_census(census_doc([bad]))
        self.assertTrue(any("mirror_status" in e for e in errors))


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *argv],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_check_mode(self):
        with tempfile.TemporaryDirectory() as td:
            good = Path(td) / "good.json"
            good.write_text(json.dumps(census_doc([census_row()])))
            bad = Path(td) / "bad.json"
            bad.write_text(json.dumps(census_doc([census_row(mirror_status="x")])))
            self.assertEqual(self.run_cli("--check", str(good)).returncode, 0)
            self.assertEqual(self.run_cli("--check", str(bad)).returncode, 1)
            self.assertEqual(
                self.run_cli("--check", str(Path(td) / "missing.json")).returncode,
                2,
            )


if __name__ == "__main__":
    unittest.main()


class ReviewRegressionTests(unittest.TestCase):
    """Regressions pinned by the independent whole-branch review."""

    def census_one(self, table):
        return ffc.census_repo("pratik-saptarshi/x", FakeRunner(table))

    def test_retired_is_idempotent(self):
        rows1, _ = ffc.build_rows(census_doc([census_row()]), [], {}, "2026-11-18T09:00:00-06:00")
        rows2, changed1 = ffc.build_rows(census_doc([]), rows1, {}, "2026-11-19T09:00:00-06:00")
        self.assertEqual(changed1, [0])
        rows3, changed2 = ffc.build_rows(census_doc([]), rows2, {}, "2026-11-20T09:00:00-06:00")
        self.assertEqual(changed2, [])
        self.assertEqual(rows3[0][15], rows2[0][15])  # note not re-appended

    def test_attribution_develop_only_move_is_not_fork_sync(self):
        rows1, _ = ffc.build_rows(census_doc([census_row()]), [], {}, "2026-11-18T09:00:00-06:00")
        doc2 = census_doc([census_row(develop_head=SHA_D, develop_behind=4)],
                          generated_at="2026-11-19T09:00:00-06:00")
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-19T08:00:00-06:00"}}}
        rows2, _ = ffc.build_rows(doc2, rows1, record, "2026-11-19T09:00:00-06:00")
        self.assertEqual(rows2[0][13], "unknown (external change)")
        self.assertEqual(rows2[0][12], rows1[0][12])  # M untouched

    def test_attribution_unknown_row_keeps_actor(self):
        rows1, _ = ffc.build_rows(census_doc([census_row()]), [], {}, "T1")
        doc2 = census_doc([census_row(mirror_status="unknown", develop_status="unknown",
                                      mirror_behind=None, mirror_unique=None,
                                      develop_behind=None, develop_fork_local=None,
                                      mirror_head=None, upstream_head=None,
                                      develop_head=None, error="mirror-compare: HTTP 500")])
        rows2, _ = ffc.build_rows(doc2, rows1, {}, "T2")
        self.assertEqual(rows2[0][13], "fork-fleet-census")

    def test_upstream_head_failure_is_partial(self):
        table = good_table()
        table[branch_args("up/x")] = (None, "HTTP 500", 1)
        row = self.census_one(table)
        self.assertEqual(row["mirror_status"], "behind")
        self.assertIsNone(row["upstream_head"])
        self.assertTrue(row.get("partial"))
        self.assertEqual(ffc.census_exit_code(census_doc([row])), 1)

    def test_no_mirror_requires_a_404_probe(self):
        table = good_table()
        table[mirror_args()] = (None, "HTTP 500", 1)
        table[branch_args("pratik-saptarshi/x")] = (None, "HTTP 500", 1)
        table[develop_args()] = (None, "HTTP 500", 1)
        row = self.census_one(table)
        self.assertEqual(row["mirror_status"], "unknown")

    def test_build_rows_truncates_wide_prev_rows(self):
        wide = ["pratik-saptarshi/x"] + ["v"] * 17  # 18 columns incl. Q:R
        rows, _ = ffc.build_rows(census_doc([]), [wide], {}, "T1")
        self.assertEqual(len(rows[0]), 16)
        rows, _ = ffc.build_rows(census_doc([census_row()]), [wide], {}, "T1")
        self.assertEqual(len(rows[0]), 16)


class CliIoFailureTests(unittest.TestCase):
    def run_cli(self, *argv):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *argv],
            capture_output=True, text=True, timeout=30,
        )

    def test_missing_prev_rows_is_exit_2(self):
        result = self.run_cli("--prev-rows", "/nonexistent/prev.json",
                              "--rows-output", "/tmp/rows-out.json")
        self.assertEqual(result.returncode, 2)

    def test_corrupt_sync_record_is_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "record.json"
            bad.write_text("{not json")
            result = self.run_cli("--sync-record", str(bad),
                                  "--rows-output", "/tmp/rows-out.json")
            self.assertEqual(result.returncode, 2)


class CodexRegressionTests(unittest.TestCase):
    """Regressions pinned by the Codex review of PR #167."""

    def census_one(self, table):
        return ffc.census_repo("pratik-saptarshi/x", FakeRunner(table))

    def test_gateway_launch_failure_is_fatal(self):
        # A missing gateway executable raises OSError inside
        # subprocess.run; it must surface as CensusFatal (exit 2),
        # not a traceback the agent reads as a partial census.
        original = ffc.GHG
        ffc.GHG = "/nonexistent/ghg"
        try:
            with self.assertRaises(ffc.CensusFatal):
                ffc.ghg_runner(("api", "repos/pratik-saptarshi/x"))
        finally:
            ffc.GHG = original

    def test_upstream_head_must_match_compare_permalink(self):
        # The branches lookup races the compare: if upstream moved
        # in between, the returned head does not match the compare's
        # permalink prefix and the mirror axis must go unknown
        # rather than publish counts against the wrong SHA.
        table = good_table()
        table[branch_args("up/x")] = ({"commit": {"sha": SHA_D}}, None, 0)
        row = self.census_one(table)
        self.assertEqual(row["mirror_status"], "unknown")
        self.assertIsNone(row["mirror_behind"])
        self.assertIsNone(row["mirror_unique"])
        self.assertIsNone(row["upstream_head"])
        self.assertEqual(row["mirror_head"], SHA_A)  # fork tip still known
        self.assertEqual(row["develop_status"], "ff-ready")  # axis intact
        self.assertIn("moved during measurement", row["error"])

    def test_unknown_placeholder_preserves_attribution_baseline(self):
        # Night 1: measured. Night 2: measurement fails (unknown) --
        # the placeholder must keep the measured heads and the
        # verification stamp, so a sync applied that night is still
        # attributable on night 3's recovery.
        t1 = "2026-11-16T09:00:00-06:00"
        rows1, _ = ffc.build_rows(census_doc([census_row()]), [], {}, t1)
        unknown = census_row(
            mirror_status="unknown", develop_status="unknown",
            mirror_behind=None, mirror_unique=None,
            develop_behind=None, develop_fork_local=None,
            mirror_head=None, upstream_head=None, develop_head=None,
            error="mirror-compare: HTTP 500",
        )
        rows2, _ = ffc.build_rows(census_doc([unknown]), rows1, {}, "2026-11-17T09:00:00-06:00")
        self.assertEqual(rows2[0][3], "unknown")
        self.assertEqual(rows2[0][4], "")  # counts blank
        self.assertEqual(rows2[0][6], SHA_A[:12])  # baseline head kept
        self.assertEqual(rows2[0][14], t1)  # verification stamp NOT advanced
        # Night 3: recovered, mirror moved, sync applied on night 2.
        doc3 = census_doc([census_row(mirror_head=SHA_D, mirror_behind=2)],
                          generated_at="2026-11-18T09:00:00-06:00")
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-17T08:00:00-06:00"}}}
        rows3, _ = ffc.build_rows(doc3, rows2, record, "2026-11-18T09:00:00-06:00")
        self.assertEqual(rows3[0][13], "fork-sync")
        self.assertEqual(rows3[0][12], "2026-11-17T08:00:00-06:00")
