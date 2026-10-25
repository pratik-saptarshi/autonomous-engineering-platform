"""Task 4 tests: `ghg check` (flow pre-flight), `ghg status`
(reconciliation + drift), `ghg prune`, and the reaping housekeeping
the controller requires on every verb.

Stdlib `unittest` only. Every GitHub call is intercepted by a stub
`gh` through the GHG_REAL_GH seam (the stub serves a fixture
`rate_limit` payload and counts non-rate_limit invocations).

Scenario map (from the brief, Step 1, plus carried controller notes):
  - check: fits -> 0 and writes no `calls`/reservation rows; exceeds
    -> 75 with the denial line and nothing written either.
  - check/status/prune reap stale reservations (housekeeping writes
    are the brief's allowed exception to check's no-rows rule).
  - drift: fixture ledger 100, snapshot core used 130 -> `+30` with
    the confounder line; used <= ledger -> no drift line; core spend
    is read on its 3600 window only (the seed rule).
  - bypass count surfaces (JSON and human output).
  - GraphQL drift is labeled coarse; omitted when there is no
    movement.
  - prune removes a 31-day-old row, keeps a 29-day-old one.
"""

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

GHG_DIR = Path(__file__).resolve().parents[1]
GHG_PY = GHG_DIR / "ghg.py"

STUB_GH = r"""#!/usr/bin/env python3
import os
import sys

if sys.argv[1:3] == ["api", "rate_limit"]:
    with open(os.environ["GHG_STUB_RATE_LIMIT"]) as f:
        sys.stdout.write(f.read())
    sys.exit(0)

count_path = os.environ["GHG_STUB_COUNT"]
try:
    with open(count_path) as f:
        n = int(f.read().strip() or "0")
except (OSError, ValueError):
    n = 0
with open(count_path, "w") as f:
    f.write(str(n + 1))
print("{}")
sys.exit(0)
"""


def load_ghg_module():
    spec = importlib.util.spec_from_file_location("ghg", GHG_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ghg = load_ghg_module()


def rate_limit_payload(core_used=0, graphql_used=0):
    reset = int(time.time()) + 3600
    return {
        "resources": {
            "core": {"limit": 5000, "used": core_used,
                     "remaining": 5000 - core_used, "reset": reset},
            "graphql": {"limit": 5000, "used": graphql_used,
                        "remaining": 5000 - graphql_used,
                        "reset": reset},
            "search": {"limit": 30, "used": 0, "remaining": 30,
                       "reset": reset},
            "code_search": {"limit": 10, "used": 0, "remaining": 10,
                            "reset": reset},
        },
        "rate": {"limit": 5000, "used": core_used,
                 "remaining": 5000 - core_used, "reset": reset},
    }


class StatusTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ghg-status-")
        self.root = Path(self.tmp.name)
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.db_file = self.state_dir / "ghg.db"
        self.count_file = self.root / "stub-count"
        self.rate_file = self.root / "rate-limit.json"
        self.rate_file.write_text(json.dumps(rate_limit_payload()))
        self.stub = self.root / "stub-gh"
        self.stub.write_text(STUB_GH)
        self.stub.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    # -- helpers ---------------------------------------------------------

    def base_env(self, extra=None):
        env = dict(os.environ)
        env["GHG_STATE_DIR"] = str(self.state_dir)
        env["GHG_REAL_GH"] = str(self.stub)
        env["GHG_STUB_COUNT"] = str(self.count_file)
        env["GHG_STUB_RATE_LIMIT"] = str(self.rate_file)
        env.pop("GHG_LIMITS_JSON", None)
        env.pop("GHG_BYPASS", None)
        env.pop("GHG_ACTOR", None)
        if extra:
            env.update(extra)
        return env

    def run_cli(self, args, extra_env=None):
        return subprocess.run(
            [sys.executable, str(GHG_PY)] + args,
            capture_output=True, text=True, timeout=60,
            env=self.base_env(extra_env))

    def make_db(self):
        """Create the schema in the fixture state dir (no calls)."""
        saved = os.environ.get("GHG_STATE_DIR")
        os.environ["GHG_STATE_DIR"] = str(self.state_dir)
        try:
            with ghg.Ledger():
                pass
        finally:
            if saved is None:
                del os.environ["GHG_STATE_DIR"]
            else:
                os.environ["GHG_STATE_DIR"] = saved

    def sql(self, statement, params=()):
        conn = sqlite3.connect(str(self.db_file))
        try:
            cur = conn.execute(statement, params)
            conn.commit()
            return cur.fetchall()
        finally:
            conn.close()

    def insert_call(self, ts, actor, bucket, cost, outcome):
        self.sql(
            "INSERT INTO calls (ts, actor, bucket, cost, argv, outcome)"
            " VALUES (?, ?, ?, ?, 'fixture', ?)",
            (ts, actor, bucket, cost, outcome))

    def set_meta(self, key, value):
        self.sql("INSERT OR REPLACE INTO meta (key, value)"
                 " VALUES (?, ?)", (key, str(value)))

    def call_rows(self):
        if not self.db_file.exists():
            return []
        return self.sql(
            "SELECT actor, bucket, cost, outcome FROM calls ORDER BY id")

    def seed_snapshot_fixture(self, core_used, graphql_used=0,
                              ledger_core=100):
        """A DB whose seed is already established (seed_core=0 at
        now-100) with `ledger_core` of post-seed core spend and a
        fresh cached snapshot reporting the given `used` figures —
        so status's drift is used − (seed-adjusted ledger spend)."""
        now = int(time.time())
        self.make_db()
        self.set_meta("seed_core", 0)
        self.set_meta("seeded_at", now - 100)
        self.set_meta("seed_reset", now + 3600)
        payload = rate_limit_payload(core_used=core_used,
                                     graphql_used=graphql_used)
        self.set_meta("rate_limit", json.dumps(payload))
        self.set_meta("rate_limit_fetched_at", now)
        if ledger_core:
            self.insert_call(now - 10, "alice", "core", 60, "ok")
            self.insert_call(now - 10, "alice", "core",
                             ledger_core - 60, "ok")
        return now


class TestCheck(StatusTestCase):
    def test_check_fits_returns_0_and_writes_no_call_rows(self):
        proc = self.run_cli(["check", "--", "pr", "view", "12"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.call_rows(), [])  # meta writes excepted

    def test_check_exceeds_returns_75_and_writes_nothing(self):
        limits = {"search": [[60, 1]]}
        env = {"GHG_LIMITS_JSON": json.dumps(limits)}
        proc = self.run_cli(["run", "--", "search", "repos", "q"], env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        before = self.call_rows()
        proc = self.run_cli(["check", "--", "search", "repos", "q"],
                            env)
        self.assertEqual(proc.returncode, 75)
        self.assertIn("ghg: DENIED bucket=search", proc.stderr)
        self.assertIn("cap=1", proc.stderr)
        # No denied row, no reservation — rows exactly as before.
        self.assertEqual(self.call_rows(), before)
        self.assertEqual([r for r in self.call_rows()
                          if r[3] == "denied"], [])

    def test_check_seeds_core_headroom_from_snapshot(self):
        # A fresh DB seeds from GitHub's current `used` at first
        # use: with used=50 against a fixture cap of 10, even the
        # first check must deny — never grant fresh headroom inside
        # a window GitHub counts as spent.
        self.rate_file.write_text(
            json.dumps(rate_limit_payload(core_used=50)))
        env = {"GHG_LIMITS_JSON": json.dumps({"core": [[3600, 10]]})}
        proc = self.run_cli(["check", "--", "repo", "view"], env)
        self.assertEqual(proc.returncode, 75)
        self.assertIn("ghg: DENIED bucket=core", proc.stderr)
        self.assertEqual(self.call_rows(), [])

    def test_check_reaps_stale_reservations(self):
        now = int(time.time())
        self.make_db()
        self.insert_call(now - 700, "alice", "core", 1, "reserved")
        proc = self.run_cli(["check", "--", "repo", "view"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = self.call_rows()
        self.assertEqual([(r[1], r[3]) for r in rows],
                         [("core", "abandoned")])


class TestStatusDrift(StatusTestCase):
    def test_drift_arithmetic_with_confounder_line(self):
        self.seed_snapshot_fixture(core_used=130)
        proc = self.run_cli(["status"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(
            "drift: +30 core calls not through ghg"
            " (includes interactive and connector-path use)",
            proc.stdout)
        entries = [
            json.loads(line) for line in
            (self.state_dir / "drift.jsonl").read_text().splitlines()
            if line]
        core_entries = [e for e in entries if e["bucket"] == "core"]
        self.assertEqual(core_entries[-1]["drift"], 30)

    def test_no_drift_line_when_used_le_ledger(self):
        self.seed_snapshot_fixture(core_used=90)
        proc = self.run_cli(["status"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("core calls not through ghg", proc.stdout)

    def test_status_json_shape_and_github_truth(self):
        self.seed_snapshot_fixture(core_used=130)
        proc = self.run_cli(["status", "--json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        for bucket in ("core", "graphql", "search", "code_search",
                       "content"):
            self.assertIn(bucket, data["buckets"])
        core = data["buckets"]["core"]
        self.assertEqual(core["github"]["used"], 130)
        self.assertEqual(core["windows"][0]["cap"], 3500)
        self.assertEqual(core["windows"][0]["spend"], 100)
        self.assertEqual(data["drift"]["core"], 30)
        self.assertEqual(data["top_actors"][0]["actor"], "alice")
        self.assertEqual(data["top_actors"][0]["spend"], 100)


class TestStatusBypassAndGraphql(StatusTestCase):
    def test_bypass_count_surfaces(self):
        now = self.seed_snapshot_fixture(core_used=100)
        self.insert_call(now - 5, "bob", "core", 1, "bypass")
        self.insert_call(now - 5, "bob", "core", 1, "bypass")
        proc = self.run_cli(["status", "--json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["buckets"]["core"]["bypass"], 2)
        proc = self.run_cli(["status"])
        self.assertIn("bypass=2", proc.stdout)

    def test_graphql_drift_is_labeled_coarse(self):
        now = self.seed_snapshot_fixture(core_used=100,
                                         graphql_used=500,
                                         ledger_core=100)
        self.insert_call(now - 10, "alice", "graphql", 100, "ok")
        proc = self.run_cli(["status"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        graphql_lines = [line for line in proc.stdout.splitlines()
                         if "graphql" in line and "drift" in line]
        self.assertEqual(len(graphql_lines), 1)
        self.assertIn("+400", graphql_lines[0])
        self.assertIn("coarse", graphql_lines[0])

    def test_graphql_drift_omitted_when_no_movement(self):
        self.seed_snapshot_fixture(core_used=100, graphql_used=0)
        proc = self.run_cli(["status"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("graphql", " ".join(
            line for line in proc.stdout.splitlines()
            if "drift" in line))

    def test_status_reaps_stale_reservations(self):
        now = int(time.time())
        self.make_db()
        self.insert_call(now - 700, "alice", "core", 1, "reserved")
        proc = self.run_cli(["status"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = self.call_rows()
        self.assertEqual([(r[1], r[3]) for r in rows],
                         [("core", "abandoned")])


class TestPrune(StatusTestCase):
    def test_prune_removes_31d_keeps_29d(self):
        now = int(time.time())
        self.make_db()
        self.insert_call(now - 31 * 86400, "alice", "core", 1, "ok")
        self.insert_call(now - 29 * 86400, "alice", "core", 1, "ok")
        proc = self.run_cli(["prune"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = self.call_rows()
        self.assertEqual(len(rows), 1)

    def test_prune_reaps_stale_reservations(self):
        now = int(time.time())
        self.make_db()
        self.insert_call(now - 700, "alice", "core", 1, "reserved")
        proc = self.run_cli(["prune"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = self.call_rows()
        self.assertEqual([(r[1], r[3]) for r in rows],
                         [("core", "abandoned")])


if __name__ == "__main__":
    unittest.main()
