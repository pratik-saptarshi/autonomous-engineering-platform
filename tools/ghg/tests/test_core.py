"""Task 2 tests: the slim ledger and budget core.

Stdlib `unittest` only. `snapshot()` fetches are intercepted by a stub
`gh` through the GHG_REAL_GH seam; the stub serves a fixture
`rate_limit` payload from a file and counts its own invocations.
Caps are forced small through the GHG_LIMITS_JSON seam; time is
injected explicitly (`now=`) wherever a window boundary is the point.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

GHG_DIR = Path(__file__).resolve().parents[1]
GHG_PY = GHG_DIR / "ghg.py"

STUB_GH = r"""#!/usr/bin/env python3
import os
import sys

count_path = os.environ.get("GHG_STUB_COUNT")
if count_path:
    try:
        with open(count_path) as f:
            n = int(f.read().strip() or "0")
    except (OSError, ValueError):
        n = 0
    with open(count_path, "w") as f:
        f.write(str(n + 1))

if os.environ.get("GHG_STUB_FAIL"):
    print("stub gh: simulated failure", file=sys.stderr)
    sys.exit(1)

if sys.argv[1:3] == ["api", "rate_limit"]:
    with open(os.environ["GHG_STUB_RATE_LIMIT"]) as f:
        sys.stdout.write(f.read())
    sys.exit(0)

print("stub gh: unexpected argv %r" % (sys.argv,), file=sys.stderr)
sys.exit(9)
"""


def load_ghg_module():
    spec = importlib.util.spec_from_file_location("ghg", GHG_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ghg = load_ghg_module()


def rate_limit_payload(core_used, core_reset, graphql_used=0):
    return {
        "resources": {
            "core": {"limit": 5000, "used": core_used,
                     "remaining": 5000 - core_used, "reset": core_reset},
            "graphql": {"limit": 5000, "used": graphql_used,
                        "remaining": 5000 - graphql_used,
                        "reset": core_reset},
            "search": {"limit": 30, "used": 0, "remaining": 30,
                       "reset": core_reset},
            "code_search": {"limit": 10, "used": 0, "remaining": 10,
                            "reset": core_reset},
        },
        "rate": {"limit": 5000, "used": core_used,
                 "remaining": 5000 - core_used, "reset": core_reset},
    }


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ghg-core-")
        self.root = Path(self.tmp.name)
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.db_file = self.state_dir / "ghg.db"
        self.count_file = self.root / "stub-count"
        self.rate_file = self.root / "rate-limit.json"
        self.stub = self.root / "stub-gh"
        self.stub.write_text(STUB_GH)
        self.stub.chmod(0o755)
        self._saved_env = dict(os.environ)
        os.environ["GHG_STATE_DIR"] = str(self.state_dir)
        os.environ["GHG_REAL_GH"] = str(self.stub)
        os.environ["GHG_STUB_COUNT"] = str(self.count_file)
        os.environ["GHG_STUB_RATE_LIMIT"] = str(self.rate_file)
        os.environ.pop("GHG_STUB_FAIL", None)
        os.environ.pop("GHG_LIMITS_JSON", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_env)
        self.tmp.cleanup()

    # -- helpers ---------------------------------------------------------

    def make_ledger(self, limits=None):
        if limits is None:
            os.environ.pop("GHG_LIMITS_JSON", None)
        else:
            os.environ["GHG_LIMITS_JSON"] = json.dumps(limits)
        return ghg.Ledger(self.db_file)

    def set_rate_limit(self, payload):
        self.rate_file.write_text(json.dumps(payload))

    def stub_calls(self):
        try:
            return int(self.count_file.read_text().strip() or "0")
        except (OSError, ValueError):
            return 0

    def insert_call(self, bucket, cost, outcome, ts, actor="tester"):
        conn = sqlite3.connect(str(self.db_file))
        try:
            conn.execute(
                "INSERT INTO calls (ts, actor, bucket, cost, argv,"
                " outcome) VALUES (?, ?, ?, ?, 'x', ?)",
                (ts, actor, bucket, cost, outcome))
            conn.commit()
        finally:
            conn.close()

    def call_rows(self, outcome=None):
        conn = sqlite3.connect(str(self.db_file))
        try:
            if outcome is None:
                return conn.execute(
                    "SELECT bucket, cost, argv, outcome FROM calls"
                    " ORDER BY id").fetchall()
            return conn.execute(
                "SELECT bucket, cost, argv, outcome FROM calls"
                " WHERE outcome = ? ORDER BY id", (outcome,)).fetchall()
        finally:
            conn.close()


class TestReserveAndDeny(CoreTestCase):
    def test_reserve_then_deny_at_cap(self):
        ledger = self.make_ledger({"search": [[60, 3]]})
        for _ in range(3):
            ids = ledger.reserve_all([("search", 1)], "tester",
                                     "search repos q")
            self.assertIsNotNone(ids)
            ledger.finalize(ids, "ok")
        self.assertIsNone(
            ledger.reserve_all([("search", 1)], "tester", "search x"))
        denied = self.call_rows("denied")
        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0][0], "search")
        self.assertEqual(denied[0][1], 0)  # denied rows cost nothing

    def test_multi_bucket_denial_reserves_nothing(self):
        ledger = self.make_ledger(
            {"graphql": [[3600, 100]], "content": [[60, 1], [3600, 300]]})
        ids = ledger.reserve_all([("content", 1)], "tester", "pr create")
        ledger.finalize(ids, "ok")  # content minute cap now exhausted
        result = ledger.reserve_all(
            [("graphql", 2), ("content", 1)], "tester", "pr comment")
        self.assertIsNone(result)
        self.assertEqual(self.call_rows("reserved"), [])
        self.assertEqual(
            [r for r in self.call_rows("denied") if r[0] == "content"],
            [("content", 0, "pr comment", "denied")])

    def test_race_twenty_threads_cap_five(self):
        self.make_ledger({"search": [[60, 5]]}).close()
        results = []
        errors = []

        def worker():
            try:
                ledger = ghg.Ledger(self.db_file)
                try:
                    results.append(
                        ledger.reserve_all([("search", 1)], "racer",
                                           "search repos q"))
                finally:
                    ledger.close()
            except Exception as exc:  # noqa: BLE001 - recorded, asserted
                errors.append(exc)

        os.environ["GHG_LIMITS_JSON"] = json.dumps({"search": [[60, 5]]})
        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual(errors, [])
        successes = [r for r in results if r is not None]
        self.assertEqual(len(results), 20)
        self.assertEqual(len(successes), 5)
        self.assertEqual(len(self.call_rows("reserved")), 5)

    def test_rolling_window_boundary(self):
        # Fixed-window counting would reset at the minute boundary;
        # the rolling sum must not. Rows sit 1s before a boundary,
        # the reservation attempt 1s after it, both inside 60s.
        now = int(time.time())
        boundary = now - (now % 60) + 60  # next fixed-minute boundary
        t_before = boundary - 1
        t_after = boundary + 1
        ledger = self.make_ledger({"search": [[60, 20]]})
        for _ in range(20):
            self.insert_call("search", 1, "ok", t_before)
        self.assertEqual(ledger.spend("search", 60, now=t_after), 20)
        self.assertIsNone(ledger.reserve_all(
            [("search", 1)], "tester", "search x", now=t_after))


class TestFinalizeAndReaper(CoreTestCase):
    def test_finalize_transitions_reserved_to_ok(self):
        ledger = self.make_ledger()
        ids = ledger.reserve_all([("core", 2)], "tester", "pr view 1")
        self.assertEqual(ledger.spend("core", 3600), 0)
        self.assertEqual(ledger.in_flight("core", 3600), 2)
        ledger.finalize(ids, "ok")
        rows = self.call_rows()
        self.assertEqual([(r[0], r[1], r[3]) for r in rows],
                         [("core", 2, "ok")])
        self.assertEqual(ledger.spend("core", 3600), 2)
        self.assertEqual(ledger.in_flight("core", 3600), 0)

    def test_reaper_abandons_old_reservations_and_frees_cost(self):
        ledger = self.make_ledger({"search": [[60, 5]]})
        now = int(time.time())
        self.insert_call("search", 5, "reserved", now - 15 * 60)
        reaped = ledger.reap_abandoned(now=now)
        self.assertEqual(reaped, 1)
        rows = self.call_rows()
        self.assertEqual(rows[0][3], "abandoned")
        self.assertEqual(ledger.in_flight("search", 3600, now=now), 0)
        # The freed budget is reservable again.
        self.assertIsNotNone(ledger.reserve_all(
            [("search", 5)], "tester", "search q", now=now))

    def test_reaper_path_under_lock_raises_gatebroken(self):
        # Review probe (Task 2 fix round 1): with the DB exclusively
        # locked and busy_timeout shortened, the reaper path at the
        # head of reserve_all must surface GateBroken — the sole
        # DB/lock failure signal — never a raw sqlite3 error, and it
        # must not produce a `denied` row.
        ledger = self.make_ledger({"search": [[60, 5]]})
        ledger.conn.execute("PRAGMA busy_timeout=50")
        blocker = sqlite3.connect(str(self.db_file),
                                  isolation_level=None, timeout=5)
        blocker.execute("BEGIN EXCLUSIVE")
        try:
            with self.assertRaises(ghg.GateBroken):
                ledger.reap_abandoned(now=int(time.time()))
            with self.assertRaises(ghg.GateBroken):
                ledger.reserve_all([("search", 1)], "tester",
                                   "search q")
        finally:
            blocker.execute("ROLLBACK")
            blocker.close()
        self.assertEqual(self.call_rows("denied"), [])

    def test_reserve_all_reaps_before_checking(self):
        ledger = self.make_ledger({"search": [[3600, 5]]})
        now = int(time.time())
        self.insert_call("search", 5, "reserved", now - 15 * 60)
        ids = ledger.reserve_all([("search", 5)], "tester", "search q",
                                 now=now)
        self.assertIsNotNone(ids)


class TestSeeding(CoreTestCase):
    def test_fresh_db_seeds_core_spend_from_snapshot(self):
        reset = int(time.time()) + 3600
        self.set_rate_limit(rate_limit_payload(4900, reset))
        ledger = self.make_ledger()
        snap = ledger.snapshot()
        self.assertIsNotNone(snap)
        self.assertGreaterEqual(ledger.spend("core", 3600), 4900)
        # 4900 seeded against a 3500 cap: immediate denial.
        self.assertIsNone(
            ledger.reserve_all([("core", 1)], "tester", "api user"))

    def test_seed_discrimination_seed_plus_post_seed_spend(self):
        reset = int(time.time()) + 3600
        self.set_rate_limit(rate_limit_payload(3000, reset))
        ledger = self.make_ledger()
        ledger.snapshot()
        seeded_at = int(ledger.meta_get("seeded_at"))
        for _ in range(6):
            self.insert_call("core", 100, "ok", seeded_at + 1)
        # Exactly seed (3000) + post-seed ledger spend (600), not
        # max(seed, ledger) and not seed + all ledger spend.
        self.assertEqual(ledger.spend("core", 3600), 3600)
        self.assertIsNone(
            ledger.reserve_all([("core", 1)], "tester", "api user"))

    def test_seed_stops_applying_after_reset(self):
        reset = int(time.time()) + 3600
        self.set_rate_limit(rate_limit_payload(3000, reset))
        ledger = self.make_ledger()
        ledger.snapshot()
        after = reset + 10
        self.assertEqual(ledger.spend("core", 3600, now=after), 0)

    def test_seed_refresh_keeps_rolling_window_spend(self):
        reset = int(time.time()) + 120
        self.set_rate_limit(rate_limit_payload(3000, reset))
        ledger = self.make_ledger()
        ledger.snapshot()
        seeded_at = int(ledger.meta_get("seeded_at"))
        for _ in range(6):
            self.insert_call("core", 100, "ok", seeded_at + 1)
        # The first seed's reset passes and a fresh snapshot
        # re-seeds from GitHub's new `used` (10). _maybe_seed is
        # called directly because snapshot() cannot be driven at a
        # synthetic now (it uses wall-clock + a TTL cache).
        t2 = reset + 10
        self.assertLess(t2 - (seeded_at + 1), 3600)
        ledger._maybe_seed(rate_limit_payload(10, t2 + 3600), t2)
        self.assertEqual(int(ledger.meta_get("seed_core")), 10)
        # Rolling semantics: the 600 of pre-reset ledger spend is
        # still inside the 3600s window at t2, so it stays in the
        # cap — spend is max(seed-anchored 10, rolling 600), not
        # the new seed-anchored figure alone.
        self.assertEqual(ledger.spend("core", 3600, now=t2), 600)

    def test_snapshot_cached_within_ttl(self):
        reset = int(time.time()) + 3600
        self.set_rate_limit(rate_limit_payload(10, reset))
        ledger = self.make_ledger()
        ledger.snapshot()
        ledger.snapshot()
        self.assertEqual(self.stub_calls(), 1)

    def test_snapshot_failure_is_tolerated_and_unledgered(self):
        os.environ["GHG_STUB_FAIL"] = "1"
        ledger = self.make_ledger()
        self.assertIsNone(ledger.snapshot())
        self.assertEqual(self.call_rows(), [])


class TestClassify(CoreTestCase):
    def test_classify_table(self):
        cases = [
            (["search", "code", "foo"], [("code_search", 1)]),
            (["search", "repos", "foo"], [("search", 1)]),
            (["pr", "view", "12"], [("graphql", 2)]),
            (["issue", "list"], [("graphql", 2)]),
            (["api", "graphql"], [("graphql", 2)]),
            (["pr", "view", "--paginate"], [("graphql", 10)]),
            (["run", "view", "1", "--log"], [("core", 5)]),
            (["run", "view", "1", "--log-failed"], [("core", 5)]),
            (["api", "repos/x"], [("core", 1)]),
            (["api", "repos/x", "-f", "name=y"],
             [("core", 1), ("content", 1)]),
            (["api", "repos/x", "-X", "DELETE"],
             [("core", 1), ("content", 1)]),
            (["repo", "delete", "x"], [("core", 1), ("content", 1)]),
            (["pr", "create", "--title", "t"],
             [("core", 1), ("content", 1)]),
            (["workflow", "run", "ci.yml"],
             [("core", 1), ("content", 1)]),
            (["pr", "list"], [("graphql", 2)]),
            (["release", "view", "v1"], [("core", 1)]),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(ghg.classify(argv), expected)

    def test_graphql_base_cost_is_two(self):
        charges = ghg.classify(["issue", "view", "3"])
        self.assertEqual(charges, [("graphql", 2)])

    def test_classify_with_inherited_flags(self):
        cases = [
            (["-R", "o/r", "pr", "create"],
             [("core", 1), ("content", 1)]),
            (["-R", "o/r", "pr", "list"], [("graphql", 2)]),
            (["--repo=o/r", "pr", "view", "1"], [("graphql", 2)]),
            (["pr", "--repo", "o/r", "list"], [("graphql", 2)]),
            (["-R", "o/r", "search", "code", "x"],
             [("code_search", 1)]),
            (["-R", "o/r", "api", "graphql", "-f", "query=..."],
             [("graphql", 2), ("content", 1)]),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(ghg.classify(argv), expected)

    def test_classify_api_flags_before_endpoint(self):
        cases = [
            # Value-taking api flags before the endpoint: their
            # values are not the endpoint.
            (["api", "-X", "POST", "graphql", "-f", "query=..."],
             [("graphql", 2), ("content", 1)]),
            (["api", "--method", "POST", "graphql"],
             [("graphql", 2), ("content", 1)]),
            (["api", "-f", "q=1", "-H", "A: b", "graphql"],
             [("graphql", 2), ("content", 1)]),
            (["api", "-H", "A: b", "graphql"], [("graphql", 2)]),
            # Combined spelling: already skipped whole.
            (["api", "--method=POST", "graphql", "-f", "query=..."],
             [("graphql", 2), ("content", 1)]),
            # A REST endpoint behind the same flags stays core.
            (["api", "-X", "POST", "repos/o/r/issues"],
             [("core", 1), ("content", 1)]),
            (["api", "-q", ".x", "repos/o/r"], [("core", 1)]),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(ghg.classify(argv), expected)


class TestIsMutating(CoreTestCase):
    def test_is_mutating_with_inherited_flags(self):
        self.assertTrue(ghg._is_mutating(["-R", "o/r", "pr", "merge"]))
        self.assertTrue(
            ghg._is_mutating(["-R", "o/r", "workflow", "run", "x"]))


class TestRedaction(CoreTestCase):
    def test_redact_both_spellings(self):
        out = ghg.redact_argv(
            ["pr", "create", "--body", "secret text",
             "--title=Hello World", "-m", "msg body"])
        self.assertNotIn("secret", out)
        self.assertNotIn("Hello World", out)
        self.assertNotIn("msg body", out)
        self.assertIn("<redacted len=11>", out)   # "secret text"
        self.assertIn("<redacted len=11>", out)   # "Hello World"
        self.assertIn("<redacted len=8>", out)    # "msg body"

    def test_redact_header_values(self):
        out = ghg.redact_argv(
            ["api", "x", "-H", "Authorization: Bearer SECRET"])
        self.assertNotIn("SECRET", out)
        self.assertIn("<redacted len=28>", out)  # "Authorization: Bearer SECRET"

        out = ghg.redact_argv(
            ["api", "x", "--header", "X-Trace: SECRET"])
        self.assertNotIn("SECRET", out)
        self.assertIn("<redacted len=15>", out)  # "X-Trace: SECRET"

        out = ghg.redact_argv(
            ["api", "x", "--header=Authorization: Bearer SECRET"])
        self.assertNotIn("SECRET", out)
        self.assertIn("--header=<redacted len=28>", out)

    def test_non_flag_equals_token_untouched(self):
        out = ghg.redact_argv(["api", "x", "foo=bar"])
        self.assertIn("foo=bar", out)

    def test_reserved_row_stores_redacted_argv(self):
        ledger = self.make_ledger()
        ledger.reserve_all(
            [("core", 1)], "tester",
            ["pr", "create", "--body", "top secret", "--body-file=/tmp/x"])
        rows = self.call_rows("reserved")
        self.assertEqual(len(rows), 1)
        self.assertNotIn("top secret", rows[0][2])
        self.assertNotIn("/tmp/x", rows[0][2])
        self.assertIn("<redacted len=10>", rows[0][2])


class TestDefaults(CoreTestCase):
    def test_production_limits(self):
        ledger = self.make_ledger()
        self.assertEqual(ledger.limits["core"], [(3600, 3500)])
        self.assertEqual(ledger.limits["graphql"], [(3600, 3500)])
        self.assertEqual(ledger.limits["search"], [(60, 20)])
        self.assertEqual(ledger.limits["code_search"], [(60, 9)])
        self.assertEqual(ledger.limits["content"],
                         [(60, 40), (3600, 300)])


if __name__ == "__main__":
    unittest.main()
