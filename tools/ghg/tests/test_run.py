"""Task 3 tests: `ghg run` — the gated pass-through — and the real
`gated_gh` behind Task 1's watcher.

Stdlib `unittest` only. Every GitHub call is intercepted by a stub `gh`
through the GHG_REAL_GH seam. The stub serves a fixture `rate_limit`
payload for `api rate_limit` (uncounted — that fetch is ungated and
unledgered by design), counts every other invocation, logs the argv it
received, echoes it as JSON, and exits with $GHG_STUB_EXIT (default 0).

Scenario map (from the task brief, Step 1, plus carried rulings):
  - argv fidelity + exit propagation: stub exiting 3 -> exit 3, the
    stub saw the exact argv, and the reservation is finalized to a
    terminal outcome (`error` for a non-zero child, per the brief's
    Interfaces: finalize with ok/error from the child exit; a zero
    child finalizes `ok`).
  - denial: an exhausted bucket -> exit 75 naming bucket + cap, the
    gated call never reaches the stub, exactly one `denied` row.
  - multi-bucket atomicity: a mutating graphql call denied on
    `content` takes no graphql reservation.
  - bypass: GHG_BYPASS=1 past the cap executes, warns, settles
    `bypass`.
  - fail-open: the DB path is a directory -> the call still executes
    and a fallback.log line appears.
  - settle failure: finalize raising after exec preserves the child's
    exit code and prints a warning (Risk #15).
  - `run watch` refusal: exit 64 with the pointer to `ghg watch`.
  - Ruling R1's deferred test: a gate denial mid-watch makes
    `ghg watch` exit 75 with the denial line.
  - actor precedence: --actor > $GHG_ACTOR.
  - --wait: a still-denied call denies after the bound expires.
"""

import contextlib
import importlib.util
import io
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
import json
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
argv_path = os.environ.get("GHG_STUB_ARGV")
if argv_path:
    with open(argv_path, "a") as f:
        f.write(json.dumps(sys.argv[1:]) + "\n")
print(json.dumps({"argv": sys.argv[1:]}))
sys.exit(int(os.environ.get("GHG_STUB_EXIT", "0")))
"""


def load_ghg_module():
    spec = importlib.util.spec_from_file_location("ghg", GHG_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ghg = load_ghg_module()


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


class RunTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ghg-run-")
        self.root = Path(self.tmp.name)
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.db_file = self.state_dir / "ghg.db"
        self.count_file = self.root / "stub-count"
        self.argv_file = self.root / "stub-argv.log"
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
        env["GHG_STUB_ARGV"] = str(self.argv_file)
        env["GHG_STUB_RATE_LIMIT"] = str(self.rate_file)
        env.pop("GHG_LIMITS_JSON", None)
        env.pop("GHG_BYPASS", None)
        env.pop("GHG_ACTOR", None)
        env.pop("GHG_STUB_EXIT", None)
        if extra:
            env.update(extra)
        return env

    def run_cli(self, args, extra_env=None):
        return subprocess.run(
            [sys.executable, str(GHG_PY)] + args,
            capture_output=True, text=True, timeout=60,
            env=self.base_env(extra_env))

    def stub_calls(self):
        try:
            return int(self.count_file.read_text().strip() or "0")
        except (OSError, ValueError):
            return 0

    def stub_argv(self):
        try:
            return [json.loads(line) for line in
                    self.argv_file.read_text().splitlines() if line]
        except OSError:
            return []

    def call_rows(self):
        conn = sqlite3.connect(str(self.db_file))
        try:
            return conn.execute(
                "SELECT actor, bucket, cost, argv, outcome FROM calls"
                " ORDER BY id").fetchall()
        finally:
            conn.close()


class TestRunPassThrough(RunTestCase):
    def test_argv_fidelity_exit_3_and_finalized_row(self):
        proc = self.run_cli(
            ["run", "--", "pr", "view", "12", "--json", "title"],
            {"GHG_STUB_EXIT": "3"})
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(self.stub_argv(),
                         [["pr", "view", "12", "--json", "title"]])
        rows = self.call_rows()
        # pr view -> one graphql charge; the row is finalized (not left
        # reserved) and reflects the child's non-zero exit.
        self.assertEqual([(r[1], r[4]) for r in rows],
                         [("graphql", "error")])

    def test_exit_zero_finalizes_ok(self):
        proc = self.run_cli(["run", "--", "repo", "view"])
        self.assertEqual(proc.returncode, 0)
        rows = self.call_rows()
        self.assertEqual([(r[1], r[4]) for r in rows], [("core", "ok")])

    def test_gated_gh_returns_captured_stdout(self):
        env = self.base_env()
        saved = dict(os.environ)
        os.environ.clear()
        os.environ.update(env)
        try:
            code, out = ghg.gated_gh(["pr", "view", "7"], "tester")
        finally:
            os.environ.clear()
            os.environ.update(saved)
        self.assertEqual(code, 0)
        self.assertIn('"pr"', out)
        self.assertIn('"view"', out)
        rows = self.call_rows()
        self.assertEqual([(r[0], r[4]) for r in rows],
                         [("tester", "ok")])

    def test_actor_precedence_flag_over_env(self):
        proc = self.run_cli(["run", "--actor", "alice", "--",
                             "repo", "view"], {"GHG_ACTOR": "bob"})
        self.assertEqual(proc.returncode, 0)
        proc = self.run_cli(["run", "--", "repo", "view"],
                            {"GHG_ACTOR": "bob"})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual([r[0] for r in self.call_rows()],
                         ["alice", "bob"])


class TestDenial(RunTestCase):
    def test_denial_never_execs_and_writes_denied_row(self):
        limits = {"search": [[60, 1]]}
        env = {"GHG_LIMITS_JSON": json.dumps(limits)}
        proc = self.run_cli(["run", "--", "search", "repos", "q"], env)
        self.assertEqual(proc.returncode, 0)
        proc = self.run_cli(["run", "--", "search", "repos", "q"], env)
        self.assertEqual(proc.returncode, 75)
        self.assertIn("ghg: DENIED bucket=search", proc.stderr)
        self.assertIn("cap=1", proc.stderr)
        self.assertIn("reset=", proc.stderr)
        self.assertEqual(self.stub_calls(), 1)  # gated call never ran
        denied = [r for r in self.call_rows() if r[4] == "denied"]
        self.assertEqual([(r[1], r[2]) for r in denied],
                         [("search", 0)])

    def test_multi_bucket_denial_is_atomic(self):
        limits = {"core": [[3600, 100]], "graphql": [[3600, 100]],
                  "content": [[60, 1], [3600, 300]]}
        env = {"GHG_LIMITS_JSON": json.dumps(limits)}
        argv = ["run", "--", "api", "graphql", "-f", "q=x"]
        proc = self.run_cli(argv, env)
        self.assertEqual(proc.returncode, 0)
        proc = self.run_cli(argv, env)
        self.assertEqual(proc.returncode, 75)
        self.assertIn("ghg: DENIED bucket=content", proc.stderr)
        rows = self.call_rows()
        self.assertEqual([r for r in rows if r[4] == "reserved"], [])
        # Only the first call's graphql charge was ever settled.
        self.assertEqual(
            [(r[1], r[2], r[4]) for r in rows if r[1] == "graphql"],
            [("graphql", 2, "ok")])

    def test_wait_expires_then_denies(self):
        limits = {"search": [[60, 1]]}
        env = {"GHG_LIMITS_JSON": json.dumps(limits)}
        proc = self.run_cli(["run", "--", "search", "repos", "q"], env)
        self.assertEqual(proc.returncode, 0)
        start = time.monotonic()
        proc = self.run_cli(
            ["run", "--wait", "1", "--", "search", "repos", "q"], env)
        elapsed = time.monotonic() - start
        self.assertEqual(proc.returncode, 75)
        self.assertGreaterEqual(elapsed, 0.9)
        self.assertLess(elapsed, 30)
        self.assertEqual(self.stub_calls(), 1)

    def test_run_watch_is_refused(self):
        proc = self.run_cli(["run", "--", "run", "watch", "42"])
        self.assertEqual(proc.returncode, 64)
        self.assertIn("ghg watch", proc.stderr)
        self.assertEqual(self.stub_calls(), 0)


class TestBypassAndFailOpen(RunTestCase):
    def test_bypass_past_cap_settles_bypass(self):
        limits = {"search": [[60, 1]]}
        env = {"GHG_LIMITS_JSON": json.dumps(limits)}
        proc = self.run_cli(["run", "--", "search", "repos", "q"], env)
        self.assertEqual(proc.returncode, 0)
        proc = self.run_cli(["run", "--", "search", "repos", "q"],
                            dict(env, GHG_BYPASS="1"))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("BYPASS", proc.stderr)
        self.assertEqual(self.stub_calls(), 2)
        bypass = [r for r in self.call_rows() if r[4] == "bypass"]
        self.assertEqual([(r[1], r[2]) for r in bypass],
                         [("search", 1)])

    def test_broken_db_fails_open_with_fallback_log(self):
        # The DB path itself is a directory: no ledger can open.
        self.db_file.mkdir()
        proc = self.run_cli(["run", "--", "pr", "view", "1"])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.stub_calls(), 1)
        log = self.state_dir / "fallback.log"
        self.assertTrue(log.exists())
        self.assertIn("ungated", log.read_text())


class TestSettleFailure(RunTestCase):
    def test_finalize_failure_preserves_child_exit_and_warns(self):
        env = self.base_env({"GHG_STUB_EXIT": "3"})
        saved = dict(os.environ)
        os.environ.clear()
        os.environ.update(env)
        original = ghg.Ledger.finalize

        def boom(self, row_ids, outcome):
            raise RuntimeError("simulated settle failure")

        ghg.Ledger.finalize = boom
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code, _out = ghg.gated_gh(["pr", "view", "9"], "tester")
        finally:
            ghg.Ledger.finalize = original
            os.environ.clear()
            os.environ.update(saved)
        self.assertEqual(code, 3)  # child's exit, never masked
        self.assertIn("WARNING", err.getvalue())
        self.assertIn("finalize", err.getvalue())


class TestWatchDenial(RunTestCase):
    """Ruling R1's deferred test, landed with the real gate."""

    def test_gate_denial_mid_watch_exits_75(self):
        env = self.base_env({
            "GHG_LIMITS_JSON": json.dumps({"core": [[3600, 0]]}),
            "GHG_MIN_INTERVAL": "1",
        })
        proc = subprocess.run(
            [sys.executable, str(GHG_PY), "watch",
             "--repo", "owner/repo", "--run", "42",
             "--interval", "1", "--timeout", "15"],
            capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(proc.returncode, 75)
        self.assertIn("ghg: DENIED bucket=core", proc.stderr)
        self.assertEqual(self.stub_calls(), 0)  # the poll never exec'd


if __name__ == "__main__":
    unittest.main()
