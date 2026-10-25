"""Task 1 tests: `ghg watch` — the coalescing run watcher.

Stdlib `unittest` only. Every GitHub call is intercepted by a stub `gh`
script through the GHG_REAL_GH seam (controller ruling R2); the stub serves
a scripted sequence of `run view` JSON responses, counts its own
invocations in a file, and timestamps each call.

Scenario map (from the task brief):
  (a) coalescing — 6 concurrent watchers, one poller, stub called exactly
      as many times as the scripted sequence needs.
  (b) poller SIGKILLed after poll 1 -> a waiter takes over and completes.
  (c) claim race — two watchers at the same instant, no exceptions.
  (d) fencing — a displaced poller (SIGSTOPped past lease expiry) makes no
      further stub calls and no writes after a peer takes over. NOTE: the
      brief's stub-hang framing cannot literally occur under the plan's
      own arithmetic — the per-poll subprocess timeout
      max(interval - 5, 1) is always shorter than the 2 x interval lease —
      so displacement is exercised with a stopped process instead; the
      fencing substance (epoch check before poll/write) is identical.
  (e) interval floor — GHG_MIN_INTERVAL raises a smaller request, with a
      stderr note and >= floor spacing between stub calls; the production
      default floor is 45.
"""

import importlib.util
import json
import os
import signal
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
import json
import os
import sys
import time

if sys.argv[1:3] != ["run", "view"]:
    print("stub gh: unexpected argv %r" % (sys.argv,), file=sys.stderr)
    sys.exit(9)

count_path = os.environ["GHG_STUB_COUNT"]
times_path = os.environ["GHG_STUB_TIMES"]
plan_path = os.environ["GHG_STUB_PLAN"]

try:
    with open(count_path) as f:
        n = int(f.read().strip() or "0")
except (OSError, ValueError):
    n = 0
with open(count_path, "w") as f:
    f.write(str(n + 1))
with open(times_path, "a") as f:
    f.write("%.6f\n" % time.time())

with open(plan_path) as f:
    plan = json.load(f)
entry = plan[min(n, len(plan) - 1)]
if entry.get("sleep"):
    time.sleep(entry["sleep"])
print(json.dumps({"status": entry["status"],
                  "conclusion": entry.get("conclusion"),
                  "attempt": entry.get("attempt", 1)}))
"""

COMBINED_STUB_GH = r"""#!/usr/bin/env python3
import json
import os
import sys
import time

if sys.argv[1:3] == ["api", "rate_limit"]:
    plan_path = os.environ["GHG_STUB_PLAN"]
    api_count = os.path.join(os.path.dirname(plan_path),
                             "stub-api-count")
    try:
        with open(api_count) as f:
            n = int(f.read().strip() or "0")
    except (OSError, ValueError):
        n = 0
    with open(api_count, "w") as f:
        f.write(str(n + 1))
    delay = float(os.environ.get("GHG_STUB_API_SLEEP", "0"))
    if delay:
        time.sleep(delay)
    print(json.dumps({"resources": {"core": {
        "limit": 5000, "used": 1, "remaining": 4999,
        "reset": 9999999999}}}))
    sys.exit(0)

if sys.argv[1:3] != ["run", "view"]:
    print("stub gh: unexpected argv %r" % (sys.argv,), file=sys.stderr)
    sys.exit(9)

count_path = os.environ["GHG_STUB_COUNT"]
times_path = os.environ["GHG_STUB_TIMES"]
plan_path = os.environ["GHG_STUB_PLAN"]

try:
    with open(count_path) as f:
        n = int(f.read().strip() or "0")
except (OSError, ValueError):
    n = 0
with open(count_path, "w") as f:
    f.write(str(n + 1))
with open(times_path, "a") as f:
    f.write("%.6f\n" % time.time())

with open(plan_path) as f:
    plan = json.load(f)
entry = plan[min(n, len(plan) - 1)]
if entry.get("sleep"):
    time.sleep(entry["sleep"])
print(json.dumps({"status": entry["status"],
                  "conclusion": entry.get("conclusion"),
                  "attempt": entry.get("attempt", 1)}))
"""


def load_ghg_module():
    spec = importlib.util.spec_from_file_location("ghg", GHG_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WatchTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ghg-test-")
        self.root = Path(self.tmp.name)
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.count_file = self.root / "stub-count"
        self.times_file = self.root / "stub-times"
        self.plan_file = self.root / "stub-plan.json"
        self.stub = self.root / "stub-gh"
        self.stub.write_text(STUB_GH)
        self.stub.chmod(0o755)
        self.procs = []

    def tearDown(self):
        for proc in self.procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
        self.tmp.cleanup()

    # -- helpers ---------------------------------------------------------

    def set_plan(self, entries):
        self.plan_file.write_text(json.dumps(entries))

    def stub_calls(self):
        try:
            return int(self.count_file.read_text().strip() or "0")
        except (OSError, ValueError):
            return 0

    def wait_for_calls(self, n, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.stub_calls() >= n:
                return True
            time.sleep(0.01)
        return self.stub_calls() >= n

    def spawn_watcher(self, interval="1", timeout_s="30", min_interval="1",
                      run_id="42", repo="owner/repo"):
        env = dict(os.environ)
        env["GHG_STATE_DIR"] = str(self.state_dir)
        env["GHG_REAL_GH"] = str(self.stub)
        env["GHG_STUB_COUNT"] = str(self.count_file)
        env["GHG_STUB_TIMES"] = str(self.times_file)
        env["GHG_STUB_PLAN"] = str(self.plan_file)
        if min_interval is None:
            env.pop("GHG_MIN_INTERVAL", None)
        else:
            env["GHG_MIN_INTERVAL"] = min_interval
        proc = subprocess.Popen(
            [sys.executable, str(GHG_PY), "watch",
             "--repo", repo, "--run", run_id,
             "--interval", interval, "--timeout", timeout_s],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env)
        self.procs.append(proc)
        return proc

    def finish(self, proc, timeout=30.0):
        out, err = proc.communicate(timeout=timeout)
        self.assertNotIn("Traceback", err)
        return proc.returncode, out, err

    def watch_row(self, run_id="42"):
        db = sqlite3.connect(self.state_dir / "ghg.db")
        try:
            return db.execute(
                "SELECT run_key, epoch, poller, heartbeat, status,"
                " conclusion FROM watches WHERE run_key = ?",
                ("owner/repo#" + run_id,)).fetchone()
        finally:
            db.close()


class TestCoalescing(WatchTestCase):
    def test_a_six_watchers_one_poller(self):
        self.set_plan([
            {"status": "in_progress", "conclusion": None},
            {"status": "in_progress", "conclusion": None},
            {"status": "completed", "conclusion": "success"},
        ])
        procs = [self.spawn_watcher() for _ in range(6)]
        for proc in procs:
            code, out, _ = self.finish(proc)
            self.assertEqual(code, 0)
            self.assertIn("ghg watch: run 42 completed conclusion=success",
                          out)
        self.assertEqual(self.stub_calls(), 3)

    def test_c_claim_race_two_watchers(self):
        self.set_plan([{"status": "completed", "conclusion": "success"}])
        procs = [self.spawn_watcher(), self.spawn_watcher()]
        for proc in procs:
            code, out, _ = self.finish(proc)
            self.assertEqual(code, 0)
            self.assertIn("conclusion=success", out)
        self.assertEqual(self.stub_calls(), 1)


class TestTakeover(WatchTestCase):
    def test_b_sigkilled_poller_is_replaced(self):
        self.set_plan([
            {"status": "in_progress", "conclusion": None},
            {"status": "in_progress", "conclusion": None},
            {"status": "completed", "conclusion": "success"},
        ])
        poller = self.spawn_watcher()
        self.assertTrue(self.wait_for_calls(1),
                        "poller never made its first poll")
        waiter = self.spawn_watcher()
        time.sleep(0.3)  # let the waiter settle into the waiter loop
        poller.send_signal(signal.SIGKILL)
        poller.wait(timeout=10)
        poller.communicate(timeout=10)  # reap pipes
        code, out, _ = self.finish(waiter)
        self.assertEqual(code, 0)
        self.assertIn("ghg watch: run 42 completed conclusion=success", out)
        # The fixture completes on poll 3; the brief allows +1 of slack.
        self.assertLessEqual(self.stub_calls(), 4)

    def test_d_displaced_poller_makes_no_further_calls(self):
        self.set_plan([
            {"status": "in_progress", "conclusion": None},
            {"status": "in_progress", "conclusion": None},
            {"status": "in_progress", "conclusion": None},
            {"status": "completed", "conclusion": "success"},
        ])
        stopped = self.spawn_watcher()
        self.assertTrue(self.wait_for_calls(1),
                        "first poller never made its first poll")
        stopped.send_signal(signal.SIGSTOP)
        try:
            time.sleep(2.6)  # lease (2 x interval) expires while it is stopped
            peer = self.spawn_watcher()
            code, out, _ = self.finish(peer)
            self.assertEqual(code, 0)
            self.assertIn("conclusion=success", out)
            self.assertEqual(self.stub_calls(), 4)
            row = self.watch_row()
            self.assertIsNotNone(row)
            self.assertEqual(row[1], 2)  # epoch bumped by the takeover
            self.assertEqual(row[4], "completed")
        finally:
            stopped.send_signal(signal.SIGCONT)
        # The displaced poller wakes, sees it is fenced, and must not poll
        # again: it turns waiter, observes completion, and exits the same.
        code, out, _ = self.finish(stopped)
        self.assertEqual(code, 0)
        self.assertIn("conclusion=success", out)
        self.assertEqual(self.stub_calls(), 4)


class TestOwnerIntervalLease(WatchTestCase):
    """FR3-4: the takeover lease is a property of the CURRENT poller.

    The predicate must compare heartbeat age against 2 x the interval
    stored on the row (the owner's cadence), not 2 x the waiter's
    interval — an owner mid-poll at interval=120 heartbeats, then reads
    for up to ~115s, and a default (45s) waiter must not displace it.
    """

    def _open(self, name="unit.db"):
        ghg = load_ghg_module()
        conn = ghg.open_db(self.root / name)
        self.addCleanup(conn.close)
        return ghg, conn

    def _age_heartbeat(self, conn, run_key, age_s):
        conn.execute(
            "UPDATE watches SET heartbeat = ? WHERE run_key = ?",
            (int(time.time()) - age_s, run_key))

    def test_takeover_uses_stored_owner_interval(self):
        ghg, conn = self._open()
        key = "owner/repo#99"
        claimed, epoch = ghg.try_claim(conn, key, "owner-1", 120)
        self.assertTrue(claimed)
        self.assertEqual(epoch, 1)
        # Heartbeat age 100: past a 45s waiter's 2x lease (90) but well
        # inside the owner's 2x120 lease (240) — no takeover.
        self._age_heartbeat(conn, key, 100)
        claimed, _ = ghg.try_claim(conn, key, "waiter-1", 45)
        self.assertFalse(claimed)
        row = ghg.get_row(conn, key)
        self.assertEqual(row["poller"], "owner-1")
        self.assertEqual(row["interval"], 120)
        # Heartbeat age 250: past the owner's lease — the waiter takes
        # over, and the row now carries the NEW owner's interval.
        self._age_heartbeat(conn, key, 250)
        claimed, epoch = ghg.try_claim(conn, key, "waiter-1", 45)
        self.assertTrue(claimed)
        self.assertEqual(epoch, 2)
        row = ghg.get_row(conn, key)
        self.assertEqual(row["poller"], "waiter-1")
        self.assertEqual(row["interval"], 45)

    def test_open_db_migrates_pre_interval_schema(self):
        path = self.root / "legacy.db"
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE watches("
            " run_key TEXT PRIMARY KEY,"
            " epoch INTEGER NOT NULL,"
            " poller TEXT NOT NULL,"
            " heartbeat INTEGER NOT NULL,"
            " status TEXT,"
            " conclusion TEXT,"
            " updated INTEGER NOT NULL)")
        conn.execute(
            "INSERT INTO watches VALUES (?, 1, ?, ?, NULL, NULL, ?)",
            ("owner/repo#7", "old-poller", 123, 123))
        conn.commit()
        conn.close()
        ghg, conn = self._open("legacy.db")
        cols = [r[1] for r in
                conn.execute("PRAGMA table_info(watches)").fetchall()]
        self.assertIn("interval", cols)
        # Pre-existing rows read the fleet default via the column DEFAULT.
        row = ghg.get_row(conn, "owner/repo#7")
        self.assertEqual(row["interval"], 45)
        # Idempotent: opening the migrated DB again is a no-op.
        conn2 = ghg.open_db(path)
        self.addCleanup(conn2.close)
        row = ghg.get_row(conn2, "owner/repo#7")
        self.assertEqual(row["interval"], 45)


class TestIntervalFloor(WatchTestCase):
    def test_e_floor_raises_interval_and_spaces_polls(self):
        self.set_plan([
            {"status": "in_progress", "conclusion": None},
            {"status": "completed", "conclusion": "success"},
        ])
        proc = self.spawn_watcher(interval="1", min_interval="2")
        code, out, err = self.finish(proc)
        self.assertEqual(code, 0)
        self.assertIn("interval", err.lower())
        self.assertIn("2", err)
        times = [float(line) for line in
                 self.times_file.read_text().splitlines()]
        self.assertEqual(len(times), 2)
        self.assertGreaterEqual(times[1] - times[0], 1.9)

    def test_e_production_default_floor_is_45(self):
        ghg = load_ghg_module()
        self.assertEqual(ghg.DEFAULT_INTERVAL_FLOOR, 45)


class TestCompletedRowRevalidation(WatchTestCase):
    """Adoption Task 2: a completed row is never trusted blindly.

    A watch invocation that finds a pre-existing completed row (the
    original poller process is gone) must revalidate it with exactly
    one gated read before printing anything: a fresh completed payload
    is printed; a not-completed payload means a rerun is in progress,
    so the row is reset and the normal claim/poll flow takes over.
    """

    def api_calls(self):
        try:
            return int((self.root / "stub-api-count").read_text()
                       .strip() or "0")
        except (OSError, ValueError):
            return 0

    def test_rerun_second_watch_revalidates_resets_and_repolls(self):
        self.set_plan([
            {"status": "in_progress", "conclusion": None, "attempt": 1},
            {"status": "completed", "conclusion": "failure", "attempt": 1},
            {"status": "in_progress", "conclusion": None, "attempt": 2},
            {"status": "completed", "conclusion": "success", "attempt": 2},
        ])
        first = self.spawn_watcher()
        code, out, _ = self.finish(first)
        self.assertEqual(code, 1)
        self.assertIn("ghg watch: run 42 completed conclusion=failure",
                      out)
        self.assertEqual(self.stub_calls(), 2)
        row = self.watch_row()
        self.assertEqual(row[4], "completed")
        self.assertEqual(row[5], "failure")
        # The first watcher (and poller) process has exited. GitHub now
        # reports attempt 2 in progress (entries 3-4 of the plan): the
        # second watch must NOT print attempt 1's cached conclusion —
        # it revalidates (1 read), resets, claims, and polls attempt 2
        # to completion (1 poll).
        second = self.spawn_watcher()
        code, out, _ = self.finish(second)
        self.assertEqual(code, 0)
        self.assertNotIn("conclusion=failure", out)
        self.assertIn("ghg watch: run 42 completed conclusion=success",
                      out)
        self.assertEqual(self.stub_calls(), 4)
        row = self.watch_row()
        self.assertEqual(row[4], "completed")
        self.assertEqual(row[5], "success")

    def test_slow_revalidation_honors_watch_timeout(self):
        self.set_plan([
            {"status": "in_progress", "conclusion": None, "attempt": 1},
            {"status": "completed", "conclusion": "success", "attempt": 1},
            {"status": "completed", "conclusion": "success", "attempt": 1,
             "sleep": 2},
        ])
        first = self.spawn_watcher()
        code, out, _ = self.finish(first)
        self.assertEqual(code, 0)
        self.assertIn("ghg watch: run 42 completed conclusion=success",
                      out)
        self.assertEqual(self.stub_calls(), 2)

        started = time.monotonic()
        second = self.spawn_watcher(timeout_s="0.1")
        code, out, _ = self.finish(second)
        elapsed = time.monotonic() - started
        self.assertEqual(code, 1)
        self.assertIn("ghg watch: run 42 timeout after 0.1s", out)
        self.assertNotIn("conclusion=success", out)
        self.assertEqual(self.stub_calls(), 3)
        self.assertLess(elapsed, 1.8,
                        "revalidation read was not bounded promptly: %.3fs"
                        % elapsed)

    def test_no_rerun_second_watch_one_read_zero_polls(self):
        self.set_plan([
            {"status": "in_progress", "conclusion": None, "attempt": 1},
            {"status": "completed", "conclusion": "success", "attempt": 1},
        ])
        first = self.spawn_watcher()
        code, out, _ = self.finish(first)
        self.assertEqual(code, 0)
        self.assertIn("ghg watch: run 42 completed conclusion=success",
                      out)
        self.assertEqual(self.stub_calls(), 2)
        # Second invocation on the still-completed run: exactly one
        # additional stub call — the revalidation read — and no poll
        # sequence (a claim+poll flow would show up as further calls:
        # try_claim never hands out a completed row, so any extra call
        # beyond the one read is a regression).
        second = self.spawn_watcher()
        code, out, _ = self.finish(second)
        self.assertEqual(code, 0)
        self.assertIn("ghg watch: run 42 completed conclusion=success",
                      out)
        self.assertEqual(self.stub_calls(), 3)
        row = self.watch_row()
        self.assertEqual(row[4], "completed")
        self.assertEqual(row[5], "success")

    def test_slow_snapshot_and_revalidation_share_one_deadline(self):
        # Composed regression (FR3-2 clamp follow-through): FR2-2
        # bounded the revalidation read by the remaining budget but
        # passed no budget_s, so the gate's opportunistic snapshot
        # refresh ran ahead of the read on its own unbounded clock.
        # Composed under one revalidation: a 2s refresh (stale cache)
        # followed by a 2s read under --timeout 2.5 must share the
        # shrinking deadline — finish at ~2.5s (+ the sub-second
        # floor), not at the ~4s the two stacked bounds allow. Exit
        # code and output are the same either way; only the elapsed
        # time discriminates.
        self.stub.write_text(COMBINED_STUB_GH)
        self.set_plan([
            {"status": "in_progress", "conclusion": None, "attempt": 1},
            {"status": "completed", "conclusion": "success", "attempt": 1},
            {"status": "completed", "conclusion": "success", "attempt": 1,
             "sleep": 2},
        ])
        first = self.spawn_watcher()
        code, out, _ = self.finish(first)
        self.assertEqual(code, 0)
        self.assertIn("ghg watch: run 42 completed conclusion=success",
                      out)
        self.assertEqual(self.stub_calls(), 2)
        self.assertEqual(self.api_calls(), 1)
        # Backdate the cached snapshot past its 60s TTL so the second
        # watch's revalidation refresh really fetches (and sleeps).
        db = sqlite3.connect(self.state_dir / "ghg.db")
        try:
            db.execute("UPDATE meta SET value = ?"
                       " WHERE key = 'rate_limit_fetched_at'",
                       (str(int(time.time()) - 3600),))
            db.commit()
        finally:
            db.close()
        os.environ["GHG_STUB_API_SLEEP"] = "2"
        self.addCleanup(os.environ.pop, "GHG_STUB_API_SLEEP", None)
        started = time.monotonic()
        second = self.spawn_watcher(timeout_s="2.5")
        code, out, _ = self.finish(second)
        elapsed = time.monotonic() - started
        self.assertEqual(code, 1)
        self.assertIn("ghg watch: run 42 timeout after 2.5s", out)
        self.assertNotIn("conclusion=", out)
        # Both slow steps really ran inside the one revalidation call:
        # exactly one more rate_limit fetch and one more run view call.
        self.assertEqual(self.api_calls(), 2)
        self.assertEqual(self.stub_calls(), 3)
        self.assertLess(elapsed, 3.5,
                        "snapshot + revalidation read were not jointly"
                        " bounded by the watch deadline: %.3fs" % elapsed)


class TestPollDeadline(WatchTestCase):
    """FR3-2: ordinary polling is bounded by the remaining watch
    deadline. FR2-2 bounded the completed-row revalidation read; the
    poll path's gated read — and the opportunistic snapshot refresh
    inside the gate — get the same bound here. The regression shape is
    Codex's repro: a 2s status stub under `--timeout 0.1` returned
    only after ~2s because the read's timeout came from the interval
    (~40s at the default), not from the caller's remaining budget."""

    def api_calls(self):
        try:
            return int((self.root / "stub-api-count").read_text()
                       .strip() or "0")
        except (OSError, ValueError):
            return 0

    def test_slow_poll_honors_watch_timeout(self):
        self.set_plan([
            {"status": "in_progress", "conclusion": None, "sleep": 2},
        ])
        started = time.monotonic()
        proc = self.spawn_watcher(interval="45", timeout_s="0.1")
        code, out, _ = self.finish(proc)
        elapsed = time.monotonic() - started
        self.assertEqual(code, 1)
        self.assertIn("ghg watch: run 42 timeout after 0.1s", out)
        self.assertNotIn("conclusion=", out)
        self.assertEqual(self.stub_calls(), 1)
        self.assertLess(elapsed, 1.8,
                        "poll read was not bounded by the remaining"
                        " deadline: %.3fs" % elapsed)

    def test_slow_snapshot_refresh_honors_watch_timeout(self):
        self.stub.write_text(COMBINED_STUB_GH)
        os.environ["GHG_STUB_API_SLEEP"] = "5"
        self.addCleanup(os.environ.pop, "GHG_STUB_API_SLEEP", None)
        self.set_plan([
            {"status": "in_progress", "conclusion": None},
        ])
        started = time.monotonic()
        proc = self.spawn_watcher(interval="45", timeout_s="2.5")
        code, out, _ = self.finish(proc)
        elapsed = time.monotonic() - started
        self.assertEqual(code, 1)
        self.assertIn("ghg watch: run 42 timeout after 2.5s", out)
        self.assertNotIn("conclusion=", out)
        # The snapshot refresh really was attempted — and bounded:
        # exactly one rate_limit fetch, cut off at the remaining
        # budget instead of running its stub's full 5s sleep.
        self.assertEqual(self.api_calls(), 1)
        self.assertLess(elapsed, 4.0,
                        "snapshot refresh was not bounded by the"
                        " remaining deadline: %.3fs" % elapsed)

    def test_slow_snapshot_and_poll_share_one_deadline(self):
        # Composed regression (FR3-2 fix round): the two tests above
        # bound the snapshot refresh and the poll read separately,
        # each against the cycle-start budget. Composed in one cycle
        # they must share a single shrinking clock: a 2s snapshot
        # refresh followed by a 2s status read under --timeout 2.5
        # must finish at ~2.5s (+ the sub-second floor), not at the
        # ~4s+ the two stacked per-step bounds allow.
        self.stub.write_text(COMBINED_STUB_GH)
        os.environ["GHG_STUB_API_SLEEP"] = "2"
        self.addCleanup(os.environ.pop, "GHG_STUB_API_SLEEP", None)
        self.set_plan([
            {"status": "in_progress", "conclusion": None, "sleep": 2},
        ])
        started = time.monotonic()
        proc = self.spawn_watcher(interval="45", timeout_s="2.5")
        code, out, _ = self.finish(proc)
        elapsed = time.monotonic() - started
        self.assertEqual(code, 1)
        self.assertIn("ghg watch: run 42 timeout after 2.5s", out)
        self.assertNotIn("conclusion=", out)
        # Both slow steps really ran inside this one poll cycle:
        # exactly one rate_limit fetch and one run view call.
        self.assertEqual(self.api_calls(), 1)
        self.assertEqual(self.stub_calls(), 1)
        self.assertLess(elapsed, 3.5,
                        "snapshot + poll read were not jointly"
                        " bounded by the watch deadline: %.3fs"
                        % elapsed)


class TestRepoKeyCanonicalization(WatchTestCase):
    """FR4-2: watch keys are built from the canonical repo identity.

    gh accepts --repo [HOST/]OWNER/REPO, so the same run watched as
    owner/repo and as github.com/owner/repo must coalesce onto ONE
    row — pre-fix the raw spelling made two keys, two owner rows, and
    two independent pollers for the same run.
    """

    def all_rows(self):
        db = sqlite3.connect(self.state_dir / "ghg.db")
        try:
            return db.execute(
                "SELECT run_key, status, conclusion FROM watches"
                " ORDER BY run_key").fetchall()
        finally:
            db.close()

    def test_canonical_repo_segment_rules(self):
        ghg = load_ghg_module()
        self.assertEqual(ghg.canonical_repo("owner/repo"), "owner/repo")
        self.assertEqual(ghg.canonical_repo("github.com/owner/repo"),
                         "owner/repo")
        self.assertEqual(ghg.canonical_repo("Owner/Repo"), "owner/repo")
        self.assertEqual(ghg.canonical_repo("GitHub.com/Owner/Repo"),
                         "owner/repo")
        self.assertEqual(ghg.canonical_repo("  owner/repo  "),
                         "owner/repo")
        # Shapes other than exactly 3 segments pass through
        # (lowercased): no validation gh itself does not do.
        self.assertEqual(ghg.canonical_repo("Repo"), "repo")
        self.assertEqual(ghg.canonical_repo("a/b/c/d"), "a/b/c/d")

    def test_host_spelling_coalesces(self):
        self.set_plan([{"status": "completed", "conclusion": "success"}])
        plain = self.spawn_watcher()
        hosted = self.spawn_watcher(repo="github.com/owner/repo")
        for proc in (plain, hosted):
            code, out, _ = self.finish(proc)
            self.assertEqual(code, 0)
            self.assertIn("conclusion=success", out)
        # One poller for both spellings: exactly one status read, and
        # the second caller issued none of its own.
        self.assertEqual(self.stub_calls(), 1)
        rows = self.all_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "owner/repo#42")

    def test_case_spelling_coalesces(self):
        self.set_plan([{"status": "completed", "conclusion": "success"}])
        upper = self.spawn_watcher(repo="Owner/Repo")
        lower = self.spawn_watcher()
        for proc in (upper, lower):
            code, out, _ = self.finish(proc)
            self.assertEqual(code, 0)
            self.assertIn("conclusion=success", out)
        self.assertEqual(self.stub_calls(), 1)
        rows = self.all_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "owner/repo#42")

    def test_different_repo_gets_its_own_row(self):
        self.set_plan([{"status": "completed", "conclusion": "success"}])
        mine = self.spawn_watcher()
        other = self.spawn_watcher(repo="other/repo")
        for proc in (mine, other):
            code, out, _ = self.finish(proc)
            self.assertEqual(code, 0)
            self.assertIn("conclusion=success", out)
        self.assertEqual(self.stub_calls(), 2)
        rows = self.all_rows()
        self.assertEqual([r[0] for r in rows],
                         ["other/repo#42", "owner/repo#42"])


class TestBrokenDb(WatchTestCase):
    def test_watch_broken_db_exits_70_without_traceback(self):
        # Regression (whole-branch review N1): the DB path itself is a
        # directory, so no ledger can open. Every other verb degrades
        # deliberately (run fail-opens; check/status/prune exit 70);
        # watch must print a ghg: message and exit 70, not traceback
        # with exit 1. (finish() also asserts no Traceback in stderr.)
        (self.state_dir / "ghg.db").mkdir()
        proc = self.spawn_watcher()
        code, _, err = self.finish(proc)
        self.assertEqual(code, 70)
        self.assertIn("ghg:", err)
        self.assertEqual(self.stub_calls(), 0)


if __name__ == "__main__":
    unittest.main()
