"""Task 5 drill: the 2026-10-24 incident shape at small scale.

Stdlib `unittest` only. Everything runs against a counting stub `gh`
through the GHG_REAL_GH seam and a fixture GHG_STATE_DIR; the suite
never touches real GitHub (the Task 5 Step 4 live smoke is a manual
operator step, not part of this suite).

Drill assertions (from the task brief, Step 1):
  (a) 12 concurrent `ghg watch` callers on one run -> the stub sees
      exactly the single poller's scripted poll count (3), not 12x.
  (b) every executed call finalized a ledger row: the `calls` table
      holds exactly the expected number of terminal rows for the
      drill's traffic, and no reservation is left in flight.
  (c) with a fixture core cap forced low via GHG_LIMITS_JSON, excess
      calls exit 75 naming the bucket and never reach the stub.
  (d) shim fallback: a syntax-broken ghg.py copy -> the shim execs the
      stub gh with the translated argv (run's payload past `--`) and
      writes fallback.log in the state dir.
  (e) AC6: >= 20 stub-echo `ghg run` invocations vs direct stub
      invocations — median added latency < 300 ms.
  (f) import scan: every top-level import in ghg.py is in
      sys.stdlib_module_names.

Plus the Task 1 deferred minor, folded in here: a watch whose run
never completes exits 1 with the `timeout after <n>s` line when its
--timeout expires (previously covered only by a manual smoke).
"""

import ast
import json
import os
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

GHG_DIR = Path(__file__).resolve().parents[1]
GHG_PY = GHG_DIR / "ghg.py"
SHIM = GHG_DIR / "bin" / "ghg"

STUB_GH = r"""#!/usr/bin/env python3
import json
import os
import sys
import time

argv = sys.argv[1:]

if argv == ["api", "rate_limit"]:
    # The gateway's free, ungated snapshot fetch: serve the fixture.
    with open(os.environ["GHG_STUB_RATE_LIMIT"]) as f:
        sys.stdout.write(f.read())
    sys.exit(0)


def bump(path):
    try:
        with open(path) as f:
            n = int(f.read().strip() or "0")
    except (OSError, ValueError):
        n = 0
    with open(path, "w") as f:
        f.write(str(n + 1))
    return n


if argv[:2] == ["run", "view"]:
    n = bump(os.environ["GHG_STUB_POLLS"])
    with open(os.environ["GHG_STUB_TIMES"], "a") as f:
        f.write("%.6f\n" % time.time())
    with open(os.environ["GHG_STUB_PLAN"]) as f:
        plan = json.load(f)
    entry = plan[min(n, len(plan) - 1)]
    print(json.dumps({"status": entry["status"],
                      "conclusion": entry.get("conclusion"),
                      "attempt": entry.get("attempt", 1)}))
    sys.exit(0)

bump(os.environ["GHG_STUB_CALLS"])
with open(os.environ["GHG_STUB_ARGV"], "a") as f:
    f.write(json.dumps(argv) + "\n")
print(json.dumps({"argv": argv}))
sys.exit(int(os.environ.get("GHG_STUB_EXIT", "0")))
"""


def rate_limit_payload(core_used=0):
    reset = int(time.time()) + 3600
    return {
        "resources": {
            "core": {"limit": 5000, "used": core_used,
                     "remaining": 5000 - core_used, "reset": reset},
            "graphql": {"limit": 5000, "used": 0, "remaining": 5000,
                        "reset": reset},
            "search": {"limit": 30, "used": 0, "remaining": 30,
                       "reset": reset},
            "code_search": {"limit": 10, "used": 0, "remaining": 10,
                            "reset": reset},
        },
        "rate": {"limit": 5000, "used": core_used,
                 "remaining": 5000 - core_used, "reset": reset},
    }


class DrillTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ghg-drill-")
        self.root = Path(self.tmp.name)
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.poll_file = self.root / "stub-polls"
        self.call_file = self.root / "stub-calls"
        self.argv_file = self.root / "stub-argv.log"
        self.times_file = self.root / "stub-times"
        self.plan_file = self.root / "stub-plan.json"
        self.rate_file = self.root / "rate-limit.json"
        self.rate_file.write_text(json.dumps(rate_limit_payload()))
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

    def env(self, limits=None):
        env = dict(os.environ)
        env["GHG_STATE_DIR"] = str(self.state_dir)
        env["GHG_REAL_GH"] = str(self.stub)
        env["GHG_ACTOR"] = "drill"
        env["GHG_MIN_INTERVAL"] = "1"
        env["GHG_STUB_POLLS"] = str(self.poll_file)
        env["GHG_STUB_CALLS"] = str(self.call_file)
        env["GHG_STUB_ARGV"] = str(self.argv_file)
        env["GHG_STUB_TIMES"] = str(self.times_file)
        env["GHG_STUB_PLAN"] = str(self.plan_file)
        env["GHG_STUB_RATE_LIMIT"] = str(self.rate_file)
        if limits is None:
            env.pop("GHG_LIMITS_JSON", None)
        else:
            env["GHG_LIMITS_JSON"] = json.dumps(limits)
        env.pop("GHG_BYPASS", None)
        return env

    def count(self, path):
        try:
            return int(path.read_text().strip() or "0")
        except (OSError, ValueError):
            return 0

    def ghg(self, argv, env=None, timeout=60):
        proc = subprocess.run(
            [str(SHIM)] + argv,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env or self.env(), timeout=timeout)
        self.assertNotIn("Traceback", proc.stderr)
        return proc

    def spawn_watcher(self, env=None, run_id="42", timeout_s="30"):
        proc = subprocess.Popen(
            [str(SHIM), "watch", "--repo", "octo/demo", "--run", run_id,
             "--interval", "1", "--timeout", timeout_s],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env or self.env())
        self.procs.append(proc)
        return proc

    def ledger(self, sql, params=()):
        db = sqlite3.connect(self.state_dir / "ghg.db")
        try:
            return db.execute(sql, params).fetchall()
        finally:
            db.close()


class TestFleetDrill(DrillTestCase):
    def test_a_b_twelve_watchers_plus_thirty_mixed_calls(self):
        self.plan_file.write_text(json.dumps([
            {"status": "in_progress", "conclusion": None},
            {"status": "in_progress", "conclusion": None},
            {"status": "completed", "conclusion": "success"},
        ]))
        watchers = [self.spawn_watcher() for _ in range(12)]

        mixed = (
            [["api", "repos/octo/demo"]] * 10
            + [["pr", "view", "7", "--repo", "octo/demo"]] * 8
            + [["search", "repos", "demo"]] * 4
            + [["search", "code", "demo"]] * 2
            + [["issue", "create", "--repo", "octo/demo",
                "--title", "drill"]] * 6
        )
        self.assertEqual(len(mixed), 30)
        for argv in mixed:
            proc = self.ghg(["run", "--"] + argv)
            self.assertEqual(proc.returncode, 0, proc.stderr)

        for proc in watchers:
            out, err = proc.communicate(timeout=60)
            self.assertNotIn("Traceback", err)
            self.assertEqual(proc.returncode, 0, err)
            self.assertIn("ghg watch: run 42 completed conclusion=success",
                          out)

        # (a) one poller: the stub was polled exactly the scripted 3
        # times, independent of the 12 callers.
        self.assertEqual(self.count(self.poll_file), 3)
        # Every mixed call reached the stub exactly once.
        self.assertEqual(self.count(self.call_file), 30)

        # (b) every executed call finalized a ledger row. Expected
        # terminal rows: watch polls 3 x (core,1); api 10 x (core,1);
        # pr view 8 x (graphql,2); search 4 x (search,1);
        # search code 2 x (code_search,1);
        # issue create 6 x [(core,1), (content,1)] = 39 rows.
        rows = self.ledger(
            "SELECT bucket, cost, outcome FROM calls")
        terminal = [r for r in rows
                    if r[2] in ("ok", "error", "bypass")]
        self.assertEqual(len(rows), len(terminal),
                         "non-terminal rows left behind: %r" % (rows,))
        self.assertEqual(len(terminal), 39)
        by_bucket = {}
        for bucket, cost, _outcome in terminal:
            by_bucket[bucket] = by_bucket.get(bucket, 0) + cost
        self.assertEqual(by_bucket, {
            "core": 3 + 10 + 6, "graphql": 16, "search": 4,
            "code_search": 2, "content": 6})
        in_flight = self.ledger(
            "SELECT COUNT(*) FROM calls WHERE outcome = 'reserved'")
        self.assertEqual(in_flight[0][0], 0)

    def test_c_low_core_cap_denies_excess(self):
        env = self.env(limits={"core": [[3600, 3]]})
        codes = []
        for _ in range(5):
            proc = self.ghg(["run", "--", "api", "repos/octo/demo"],
                            env=env)
            codes.append(proc.returncode)
            if proc.returncode == 75:
                self.assertIn("DENIED bucket=core", proc.stderr)
                self.assertIn("cap=3", proc.stderr)
        self.assertEqual(codes, [0, 0, 0, 75, 75])
        # The denied calls never reached the stub.
        self.assertEqual(self.count(self.call_file), 3)
        denied = self.ledger(
            "SELECT COUNT(*) FROM calls WHERE outcome = 'denied'")
        self.assertEqual(denied[0][0], 2)

    def test_watch_timeout_expiry_exits_1(self):
        # Task 1 deferred minor: --timeout expiry previously had only
        # manual-smoke evidence. The run never completes.
        self.plan_file.write_text(json.dumps([
            {"status": "in_progress", "conclusion": None},
        ]))
        proc = self.spawn_watcher(timeout_s="3")
        out, err = proc.communicate(timeout=30)
        self.assertNotIn("Traceback", err)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("ghg watch: run 42 timeout after 3s", out)


class TestShimFallback(DrillTestCase):
    def test_d_broken_ghg_py_falls_back_with_translated_argv(self):
        broken = self.root / "broken"
        (broken / "bin").mkdir(parents=True)
        shutil.copy(SHIM, broken / "bin" / "ghg")
        (broken / "bin" / "ghg").chmod(0o755)
        (broken / "ghg.py").write_text("def broken(:\n")
        proc = subprocess.run(
            [str(broken / "bin" / "ghg"), "run", "--actor", "drill",
             "--", "api", "repos/octo/demo"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=self.env(), timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # The stub was exec'd directly with the payload past `--`,
        # ghg's own arguments stripped.
        logged = [json.loads(line) for line in
                  self.argv_file.read_text().splitlines()]
        self.assertEqual(logged, [["api", "repos/octo/demo"]])
        fallback = (self.state_dir / "fallback.log").read_text()
        self.assertIn("py_compile", fallback)
        self.assertIn("verb=run", fallback)

    def test_h_fallback_trace_redacts_argv_values(self):
        # FR3-3: the fallback trace line is written on the fail-open
        # path where ghg.py (and its redact_argv) cannot run, so the
        # shim itself must keep sensitive flag values out of
        # fallback.log — in both the separate-token and `=` spellings.
        broken = self.root / "broken"
        (broken / "bin").mkdir(parents=True)
        shutil.copy(SHIM, broken / "bin" / "ghg")
        (broken / "bin" / "ghg").chmod(0o755)
        (broken / "ghg.py").write_text("def broken(:\n")
        proc = subprocess.run(
            [str(broken / "bin" / "ghg"), "run", "--",
             "pr", "create", "--title", "TITLETOK",
             "--body", "PRIVATE_BODY",
             "-H", "Authorization: Bearer BEARERTOK",
             "--header=X-Custom:HEADERTOK",
             "--body=BODYEQTOK",
             "-HCOMBINEDTOK"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=self.env(), timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        fallback = (self.state_dir / "fallback.log").read_text()
        # The trace still records its diagnostic fields.
        self.assertTrue(fallback.split()[0].isdigit(), fallback)
        self.assertIn("py_compile", fallback)
        self.assertIn("verb=run", fallback)
        self.assertIn("pr create", fallback)
        # No secret value survives in any spelling.
        for secret in ("TITLETOK", "PRIVATE_BODY", "BEARERTOK",
                       "HEADERTOK", "BODYEQTOK", "COMBINEDTOK"):
            self.assertNotIn(secret, fallback)
        self.assertIn("<redacted>", fallback)
        self.assertIn("--body <redacted>", fallback)
        self.assertIn("--header=<redacted>", fallback)

    def test_g_run_through_symlink_uses_real_gate(self):
        # The documented fleet install is a symlink (~/go/bin/ghg ->
        # .../tools/ghg/bin/ghg). The shim must resolve $0's symlink
        # chain before locating ghg.py: invoked through a symlink it
        # must run the real gate, not degrade to the raw fallback.
        linkbin = self.root / "linkbin"
        linkbin.mkdir()
        os.symlink(SHIM, linkbin / "ghg")
        proc = subprocess.run(
            [str(linkbin / "ghg"), "run", "--", "api", "repos/octo/demo"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=self.env(), timeout=30)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # The stub saw the call exactly once, with ghg's argv stripped.
        logged = [json.loads(line) for line in
                  self.argv_file.read_text().splitlines()]
        self.assertEqual(logged, [["api", "repos/octo/demo"]])
        # The real gate ran: the call finalized a ledger row (the raw
        # fallback in test_d writes none — it never even creates the
        # ledger, hence the guard).
        try:
            rows = self.ledger("SELECT bucket, cost, outcome FROM calls")
        except sqlite3.OperationalError:
            rows = []
        self.assertEqual(rows, [("core", 1, "ok")])
        # No fallback was taken, so no fallback.log entry exists.
        self.assertFalse((self.state_dir / "fallback.log").exists())


class TestLightweight(DrillTestCase):
    def test_e_median_gate_overhead_under_300ms(self):
        env = self.env()
        reps = 20

        def timed(cmd):
            start = time.perf_counter()
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=env, timeout=30)
            elapsed = time.perf_counter() - start
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return elapsed

        # Paired sampling: direct and gated invocations interleave, so
        # load drift on this shared VM moves both arms together; the
        # statistic is the median per-pair added latency (the AC6
        # definition), not the difference of two block medians.
        diffs_ms = []
        for _ in range(reps):
            direct = timed([str(self.stub), "api", "repos/octo/demo"])
            gated = timed([str(SHIM), "run", "--", "api",
                           "repos/octo/demo"])
            diffs_ms.append((gated - direct) * 1000.0)
        overhead_ms = statistics.median(diffs_ms)
        self.assertLess(
            overhead_ms, 300.0,
            "median gate overhead %.1f ms (per-pair diffs ms: %s)"
            % (overhead_ms,
               ", ".join("%.0f" % d for d in sorted(diffs_ms))))

    def test_f_only_stdlib_imports(self):
        tree = ast.parse(GHG_PY.read_text(), filename=str(GHG_PY))
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0]
                                for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    imported.add(node.module.split(".")[0])
        self.assertTrue(imported, "no top-level imports found — scan "
                                  "is not measuring anything")
        non_stdlib = imported - set(sys.stdlib_module_names)
        self.assertEqual(non_stdlib, set(),
                         "non-stdlib top-level imports: %r" % non_stdlib)


if __name__ == "__main__":
    unittest.main()
