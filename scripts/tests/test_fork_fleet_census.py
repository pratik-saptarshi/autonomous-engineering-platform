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

    def test_consistency_failed_row_preserves_attribution(self):
        # A consistency-failed observation has unknown statuses but
        # non-null (rejected) heads. Attribution must not run on
        # rejected measurements: previous M/N stand.
        rows1, _ = ffc.build_rows(census_doc([census_row()]), [], {}, "2026-11-16T09:00:00-06:00")
        rejected = census_row(
            mirror_status="unknown", develop_status="unknown",
            mirror_behind=None, mirror_unique=None,
            develop_behind=None, develop_fork_local=None,
            mirror_head=SHA_D, upstream_head=None, develop_head=SHA_D,
            error="mirror-head mismatch between compares",
        )
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-17T08:00:00-06:00"}}}
        rows2, _ = ffc.build_rows(census_doc([rejected]), rows1, record, "2026-11-17T09:00:00-06:00")
        self.assertEqual(rows2[0][13], "fork-fleet-census")  # N preserved
        self.assertEqual(rows2[0][12], "")  # M not stamped from the record
        self.assertEqual(rows2[0][6], SHA_A[:12])  # baseline head preserved

    def test_mirror_attribution_independent_of_develop_failure(self):
        # Mirror measured and moved; develop compare failed. The
        # mirror movement is attributable on its own axis: fork-sync
        # moves mirrors only, so the develop failure must not defer
        # (and thereby permanently lose) the attribution.
        t1 = "2026-11-16T09:00:00-06:00"
        rows1, _ = ffc.build_rows(census_doc([census_row()]), [], {}, t1)
        partial = census_row(
            mirror_head=SHA_D, mirror_behind=2,
            develop_status="unknown", develop_behind=None,
            develop_fork_local=None, develop_head=None,
            error="develop-compare: HTTP 500",
        )
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-17T08:00:00-06:00"}}}
        rows2, _ = ffc.build_rows(census_doc([partial]), rows1, record, "2026-11-17T09:00:00-06:00")
        self.assertEqual(rows2[0][6], SHA_D[:12])  # G advances
        self.assertEqual(rows2[0][13], "fork-sync")  # attributed tonight
        self.assertEqual(rows2[0][12], "2026-11-17T08:00:00-06:00")
        self.assertEqual(rows2[0][8], "unknown")  # develop axis placeholder
        self.assertEqual(rows2[0][14], t1)  # stamp frozen (an axis failed)
        # Recovery night: nothing moves; attribution must not flip.
        rows3, _ = ffc.build_rows(
            census_doc([census_row(mirror_head=SHA_D, mirror_behind=2)]),
            rows2, record, "2026-11-18T09:00:00-06:00")
        self.assertEqual(rows3[0][13], "fork-sync")

    def test_consumed_sync_record_is_not_reused(self):
        # Night 2 attributes a sync during a develop failure (stamp
        # frozen, M set). Night 3: an EXTERNAL push moves the mirror
        # again. The same record still postdates the frozen stamp,
        # but it was already consumed -- M is the watermark -- so the
        # external movement must not be re-attributed to fork-sync.
        t1 = "2026-11-16T09:00:00-06:00"
        rows1, _ = ffc.build_rows(census_doc([census_row()]), [], {}, t1)
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-17T08:00:00-06:00"}}}
        partial = census_row(
            mirror_head=SHA_D, mirror_behind=2,
            develop_status="unknown", develop_behind=None,
            develop_fork_local=None, develop_head=None,
            error="develop-compare: HTTP 500",
        )
        rows2, _ = ffc.build_rows(census_doc([partial]), rows1, record, "2026-11-17T09:00:00-06:00")
        self.assertEqual(rows2[0][13], "fork-sync")
        self.assertEqual(rows2[0][12], "2026-11-17T08:00:00-06:00")
        external = census_row(mirror_head="e" * 40, mirror_behind=1)
        rows3, _ = ffc.build_rows(census_doc([external]), rows2, record, "2026-11-18T09:00:00-06:00")
        self.assertEqual(rows3[0][13], "unknown (external change)")
        self.assertEqual(rows3[0][12], "2026-11-17T08:00:00-06:00")  # M kept

    def test_develop_attribution_independent_of_mirror_failure(self):
        # Mirror image of the develop-failure case: the mirror
        # compare fails but the develop compare succeeds and reports
        # a changed develop head. Column L advances to the measured
        # head tonight, so the movement must be attributed tonight --
        # on recovery the head already matches the previous row, and
        # the external movement would never be recorded in column N.
        t1 = "2026-11-16T09:00:00-06:00"
        rows1, _ = ffc.build_rows(census_doc([census_row()]), [], {}, t1)
        self.assertEqual(rows1[0][13], "fork-fleet-census")
        partial = census_row(
            mirror_status="unknown", mirror_behind=None,
            mirror_unique=None, mirror_head=None, upstream_head=None,
            develop_head=SHA_D, develop_behind=4,
            error="mirror-compare: HTTP 500",
        )
        rows2, _ = ffc.build_rows(census_doc([partial]), rows1, {}, "2026-11-17T09:00:00-06:00")
        self.assertEqual(rows2[0][11], SHA_D[:12])  # L advances tonight
        self.assertEqual(rows2[0][13], "unknown (external change)")  # attributed tonight
        self.assertEqual(rows2[0][6], SHA_A[:12])  # mirror baseline kept
        self.assertEqual(rows2[0][14], t1)  # stamp frozen (an axis failed)
        # Recovery night: both axes measured, nothing moves; the
        # attribution must stand, not revert or vanish.
        recovered = census_row(develop_head=SHA_D, develop_behind=4)
        rows3, _ = ffc.build_rows(census_doc([recovered]), rows2, {}, "2026-11-18T09:00:00-06:00")
        self.assertEqual(rows3[0][13], "unknown (external change)")

    def test_develop_move_after_sync_does_not_retain_fork_sync(self):
        # A row previously attributed to fork-sync: a later develop
        # movement measured while the mirror compare fails must
        # replace the attribution -- the stale fork-sync stamp must
        # not survive a movement fork-sync cannot have made (it
        # moves mirrors only). Column M still records the last sync.
        t1 = "2026-11-16T09:00:00-06:00"
        rows1, _ = ffc.build_rows(census_doc([census_row()]), [], {}, t1)
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-17T08:00:00-06:00"}}}
        synced = census_row(mirror_head=SHA_D, mirror_behind=2)
        rows2, _ = ffc.build_rows(census_doc([synced]), rows1, record, "2026-11-17T09:00:00-06:00")
        self.assertEqual(rows2[0][13], "fork-sync")
        self.assertEqual(rows2[0][12], "2026-11-17T08:00:00-06:00")
        partial = census_row(
            mirror_status="unknown", mirror_behind=None,
            mirror_unique=None, mirror_head=None, upstream_head=None,
            develop_head="e" * 40, develop_behind=1,
            error="mirror-compare: HTTP 500",
        )
        rows3, _ = ffc.build_rows(census_doc([partial]), rows2, record, "2026-11-18T09:00:00-06:00")
        self.assertEqual(rows3[0][13], "unknown (external change)")
        self.assertEqual(rows3[0][12], "2026-11-17T08:00:00-06:00")  # M kept

    def test_attribution_window_uses_measurement_time_not_run_completion(self):
        # fork-sync overlaps the census: the repo is measured at
        # 19:45, fork-sync applies at 19:50, the run completes at
        # 20:00. Column O must carry the repo's own measurement
        # time, not the completion time -- otherwise the 19:50 sync
        # predates the stamp, fails the next census's window check,
        # and the recovered movement is mislabeled external.
        measured1 = census_row(measured_at="2026-11-18T19:45:00-06:00")
        rows1, _ = ffc.build_rows(
            census_doc([measured1]), [], {}, "2026-11-18T20:00:00-06:00"
        )
        self.assertEqual(rows1[0][14], "2026-11-18T19:45:00-06:00")  # O = measured_at
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-18T19:50:00-06:00"}}}
        measured2 = census_row(
            mirror_head=SHA_D, mirror_behind=2,
            measured_at="2026-11-19T19:45:00-06:00",
        )
        rows2, _ = ffc.build_rows(
            census_doc([measured2]), rows1, record, "2026-11-19T20:00:00-06:00"
        )
        self.assertEqual(rows2[0][13], "fork-sync")
        self.assertEqual(rows2[0][12], "2026-11-18T19:50:00-06:00")

    def test_simultaneous_develop_move_is_not_stamped_fork_sync(self):
        # fork-sync advances the mirror and a user advances develop
        # in the same window. The sync is real -- column M records
        # it -- but fork-sync never touches develop, so column N
        # must not claim the bot made the last change: the observed
        # movements cannot all be attributed to fork-sync, and the
        # develop movement would otherwise never be stamped at all.
        t1 = "2026-11-16T09:00:00-06:00"
        rows1, _ = ffc.build_rows(census_doc([census_row()]), [], {}, t1)
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-17T08:00:00-06:00"}}}
        both = census_row(mirror_head=SHA_D, mirror_behind=2,
                          develop_head="e" * 40, develop_behind=1)
        rows2, _ = ffc.build_rows(census_doc([both]), rows1, record, "2026-11-17T09:00:00-06:00")
        self.assertEqual(rows2[0][12], "2026-11-17T08:00:00-06:00")  # M records the sync
        self.assertEqual(rows2[0][13], "unknown (external change)")  # N does not over-claim
        # A later quiet observation must not revert the stamp.
        rows3, _ = ffc.build_rows(census_doc([both]), rows2, record, "2026-11-18T09:00:00-06:00")
        self.assertEqual(rows3[0][13], "unknown (external change)")

    def test_load_sync_record_semantics(self):
        # Missing file degrades to {} (no record yet, plan S3); a
        # file that exists but cannot be parsed is fatal, never a
        # silent degrade that would misattribute the night's syncs.
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            self.assertEqual(ffc._load_sync_record(td / "nope.json"), {})
            good = td / "record.json"
            good.write_text('{"repos": {}}')
            self.assertEqual(ffc._load_sync_record(good), {"repos": {}})
            bad = td / "bad.json"
            bad.write_text("{not json")
            with self.assertRaises(ffc.CensusFatal):
                ffc._load_sync_record(bad)

    def test_sync_record_is_refreshed_after_measurement(self):
        # fork-sync overlaps the census: it applies a sync and
        # updates the record file while the census is measuring.
        # main must re-read the record after measurement -- the
        # pre-census copy predates the sync, so the movement would
        # be labeled external and the stored head advanced past it,
        # losing the sync attribution permanently.
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            record_path = td / "record.json"
            record_path.write_text(json.dumps({"repos": {}}))
            rows1, _ = ffc.build_rows(
                census_doc([census_row()]), [], {}, "2026-11-18T09:00:00-06:00"
            )
            prev_path = td / "prev.json"
            prev_path.write_text(json.dumps(rows1))
            out_path = td / "rows.json"
            census_path = td / "census.json"

            table = good_table()
            table[("repo", "list", "pratik-saptarshi", "--limit", "300",
                    "--json", "nameWithOwner,isFork,defaultBranchRef")] = (
                [{"nameWithOwner": "pratik-saptarshi/x", "isFork": True,
                  "defaultBranchRef": {"name": "develop"}}], None, 0)
            # The census measures the mirror at its NEW head: the
            # sync landed before this repo's compares ran.
            table[mirror_args()] = (compare(2, 0, SHA_D, "b" * 7), None, 0)
            table[develop_args()] = (compare(9, 0, SHA_C, "d" * 7), None, 0)

            class SyncDuringCensus(FakeRunner):
                def __call__(self, args):
                    result = super().__call__(args)
                    if tuple(args)[0] == "repo":
                        # fork-sync's record update lands while the
                        # census is still running.
                        record_path.write_text(json.dumps({"repos": {
                            "pratik-saptarshi/x": {
                                "last_applied_at": "2026-11-18T09:30:00-06:00"}}}))
                    return result

            original = ffc.ghg_runner
            ffc.ghg_runner = SyncDuringCensus(table)
            try:
                code = ffc.main([
                    "--prev-rows", str(prev_path),
                    "--sync-record", str(record_path),
                    "--output", str(census_path),
                    "--rows-output", str(out_path),
                ])
            finally:
                ffc.ghg_runner = original
            self.assertEqual(code, 0)
            derived = json.loads(out_path.read_text())
            row = derived["rows"][0]
            self.assertEqual(row[13], "fork-sync")
            self.assertEqual(row[12], "2026-11-18T09:30:00-06:00")

    def test_sync_record_after_measurement_is_not_consumed(self):
        # The refreshed record can describe a sync applied AFTER
        # this repo was measured (fork-sync overlapped the census
        # and reached this repo while later repos were still being
        # processed). That record cannot explain the movement this
        # observation measured, so it must stay unconsumed: the
        # measured (external) movement is stamped external, M is
        # untouched, and the next census -- which measures the
        # synced head -- attributes the sync to fork-sync.
        rows1, _ = ffc.build_rows(
            census_doc([census_row()]), [], {}, "2026-11-18T09:00:00-06:00"
        )
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-18T10:30:00-06:00"}}}
        external = census_row(
            mirror_head="e" * 40, mirror_behind=1,
            measured_at="2026-11-18T10:00:00-06:00",
        )
        rows2, _ = ffc.build_rows(
            census_doc([external]), rows1, record, "2026-11-18T10:45:00-06:00"
        )
        self.assertEqual(rows2[0][13], "unknown (external change)")
        self.assertEqual(rows2[0][12], "")  # future sync NOT consumed
        synced = census_row(
            mirror_head=SHA_D, mirror_behind=2,
            measured_at="2026-11-19T10:00:00-06:00",
        )
        rows3, _ = ffc.build_rows(
            census_doc([synced]), rows2, record, "2026-11-19T10:45:00-06:00"
        )
        self.assertEqual(rows3[0][13], "fork-sync")
        self.assertEqual(rows3[0][12], "2026-11-18T10:30:00-06:00")

    def test_first_observation_does_not_consume_a_future_sync_record(self):
        # A newly discovered repo measured at 10:00, with the
        # refreshed record showing a sync applied at 10:30: copying
        # that record into column M on first observation would
        # consume it before its movement can be observed, and the
        # next census would label the synced head external (the
        # record no longer postdates M). The measurement-time upper
        # bound applies to the first-observation branch too.
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-18T10:30:00-06:00"}}}
        first = census_row(measured_at="2026-11-18T10:00:00-06:00")
        rows1, _ = ffc.build_rows(
            census_doc([first]), [], record, "2026-11-18T10:45:00-06:00"
        )
        self.assertEqual(rows1[0][12], "")  # future sync NOT consumed
        self.assertEqual(rows1[0][13], "fork-fleet-census")
        # A record inside the window is still copied, as before.
        early = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-18T09:30:00-06:00"}}}
        rows1b, _ = ffc.build_rows(
            census_doc([first]), [], early, "2026-11-18T10:45:00-06:00"
        )
        self.assertEqual(rows1b[0][12], "2026-11-18T09:30:00-06:00")
        # Next census measures the synced head: the unconsumed
        # record now attributes it to fork-sync.
        synced = census_row(
            mirror_head=SHA_D, mirror_behind=2,
            measured_at="2026-11-19T10:00:00-06:00",
        )
        rows2, _ = ffc.build_rows(
            census_doc([synced]), rows1, record, "2026-11-19T10:45:00-06:00"
        )
        self.assertEqual(rows2[0][13], "fork-sync")
        self.assertEqual(rows2[0][12], "2026-11-18T10:30:00-06:00")

    def test_first_measurement_after_blank_baseline_is_initialization(self):
        # A newly discovered fork whose first census fails outright
        # (repo info unreadable) gets a sheet row with blank head
        # cells -- no measured baseline on either axis. On recovery
        # the branches have NOT moved; there was simply nothing to
        # compare against. The first successful measurement of an
        # axis is initialization: it establishes the baseline, and
        # must not be stamped as an external movement -- and no
        # false attribution may appear on later unchanged
        # observations either.
        failed = census_row(
            upstream=None, mirror_branch=None,
            mirror_status="unknown", develop_status="unknown",
            mirror_behind=None, mirror_unique=None,
            develop_behind=None, develop_fork_local=None,
            mirror_head=None, upstream_head=None, develop_head=None,
            error="repo-info: HTTP 500",
        )
        rows1, _ = ffc.build_rows(
            census_doc([failed], generated_at="2026-11-16T09:00:00-06:00"),
            [], {}, "2026-11-16T09:00:00-06:00",
        )
        self.assertEqual(rows1[0][6], "")  # no mirror baseline
        self.assertEqual(rows1[0][11], "")  # no develop baseline
        self.assertEqual(rows1[0][13], "fork-fleet-census")
        self.assertEqual(rows1[0][12], "")
        rows2, _ = ffc.build_rows(
            census_doc([census_row()], generated_at="2026-11-17T09:00:00-06:00"),
            rows1, {}, "2026-11-17T09:00:00-06:00",
        )
        self.assertEqual(rows2[0][6], SHA_A[:12])  # baseline established
        self.assertEqual(rows2[0][11], SHA_C[:12])
        self.assertEqual(rows2[0][13], "fork-fleet-census")  # NOT external
        self.assertEqual(rows2[0][12], "")  # M untouched
        # A later unchanged observation keeps the initialization
        # stamp: the false attribution never appears or persists.
        rows3, _ = ffc.build_rows(
            census_doc([census_row()], generated_at="2026-11-18T09:00:00-06:00"),
            rows2, {}, "2026-11-18T09:00:00-06:00",
        )
        self.assertEqual(rows3[0][13], "fork-fleet-census")
        self.assertEqual(rows3[0][12], "")

    def test_movement_after_blank_baseline_attributes_normally(self):
        # Baselines are per-axis. Night 1 measures develop but the
        # mirror compare fails, so only the mirror baseline is
        # blank. Night 2 measures the mirror for the first time
        # (initialization, not movement) while develop genuinely
        # moves against its real baseline -- the develop movement
        # still attributes. Night 3: the mirror genuinely moves
        # against the baseline night 2 established, with a sync
        # record inside the window -- attributed to fork-sync.
        t1 = "2026-11-16T09:00:00-06:00"
        partial = census_row(
            mirror_status="unknown", mirror_behind=None,
            mirror_unique=None, mirror_head=None, upstream_head=None,
            error="mirror-compare: HTTP 500",
        )
        rows1, _ = ffc.build_rows(census_doc([partial]), [], {}, t1)
        self.assertEqual(rows1[0][6], "")  # mirror baseline absent
        self.assertEqual(rows1[0][11], SHA_C[:12])  # develop baselined
        moved = census_row(develop_head=SHA_D, develop_behind=4)
        rows2, _ = ffc.build_rows(
            census_doc([moved], generated_at="2026-11-17T09:00:00-06:00"),
            rows1, {}, "2026-11-17T09:00:00-06:00",
        )
        self.assertEqual(rows2[0][6], SHA_A[:12])  # mirror baseline set
        self.assertEqual(rows2[0][13], "unknown (external change)")
        record = {"repos": {"pratik-saptarshi/x": {"last_applied_at": "2026-11-18T08:00:00-06:00"}}}
        synced = census_row(mirror_head=SHA_B, mirror_behind=2,
                            develop_head=SHA_D, develop_behind=4)
        rows3, _ = ffc.build_rows(
            census_doc([synced], generated_at="2026-11-18T09:00:00-06:00"),
            rows2, record, "2026-11-18T09:00:00-06:00",
        )
        self.assertEqual(rows3[0][13], "fork-sync")
        self.assertEqual(rows3[0][12], "2026-11-18T08:00:00-06:00")
