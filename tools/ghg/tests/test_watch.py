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
                      run_id="42"):
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
             "--repo", "owner/repo", "--run", run_id,
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
