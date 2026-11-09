"""Task 2 (Track B) tests: ghg verb dispatch is wired to telemetry.

`ghg run` / `ghg check` / `ghg watch` must execute inside a telemetry
span named ``ghg.<verb>``; `status` / `prune` stay untraced. Telemetry
must never change any exit code, stdout, or stderr on any path.

Stdlib `unittest` only. Every GitHub call is intercepted by a stub
`gh` through the GHG_REAL_GH seam, modelled on tests/test_run.py.

IMPORTANT: the tools/ghg dir is inserted into sys.path BEFORE
ghg.py is loaded via importlib, so the `import telemetry` inside
ghg.py binds the real module (the neighbouring suites load ghg.py
without that path entry, in which case ghg's guarded import degrades
to a no-op — that path is exercised here by forcing
``ghg._telemetry = None``).
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

GHG_DIR = Path(__file__).resolve().parents[1]
GHG_PY = GHG_DIR / "ghg.py"
if str(GHG_DIR) not in sys.path:
    sys.path.insert(0, str(GHG_DIR))

import telemetry  # noqa: E402

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

ACTOR = "otel-wiring-actor"
CANARY_ENV = "GHG_TEST_CANARY"

_ENV_KEYS = (
    "GHG_STATE_DIR", "GHG_REAL_GH", "GHG_STUB_COUNT", "GHG_STUB_ARGV",
    "GHG_STUB_RATE_LIMIT", "GHG_ACTOR", "GHG_OTEL_FILE",
    "GHG_LIMITS_JSON", "GHG_BYPASS", "GHG_STUB_EXIT", CANARY_ENV,
)


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


@contextlib.contextmanager
def patched_env(overrides):
    saved = dict(os.environ)
    try:
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        os.environ.update(overrides)
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


class WiringTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ghg-wiring-")
        self.root = Path(self.tmp.name)
        self.rate_file = self.root / "rate-limit.json"
        self.rate_file.write_text(json.dumps(rate_limit_payload()))
        self.stub = self.root / "stub-gh"
        self.stub.write_text(STUB_GH)
        self.stub.chmod(0o755)
        self._case_n = 0
        # One frozen epoch for the whole test, so every scenario arm
        # in a byte-identical comparison shares it exactly.
        self._frozen = float(int(time.time()))

    def tearDown(self):
        self.tmp.cleanup()

    # -- helpers ------------------------------------------------------

    def fresh_env(self, otel_file=None, extra=None):
        """A fully independent scenario env (own state dir + stub
        counters), so off/on runs never share ledger state."""
        self._case_n += 1
        case = self.root / ("case-%d" % self._case_n)
        state_dir = case / "state"
        state_dir.mkdir(parents=True)
        env = {
            "GHG_STATE_DIR": str(state_dir),
            "GHG_REAL_GH": str(self.stub),
            "GHG_STUB_COUNT": str(case / "stub-count"),
            "GHG_STUB_ARGV": str(case / "stub-argv.log"),
            "GHG_STUB_RATE_LIMIT": str(self.rate_file),
            "GHG_ACTOR": ACTOR,
        }
        if otel_file is not None:
            env["GHG_OTEL_FILE"] = str(otel_file)
        if extra:
            env.update(extra)
        return env

    def call_main(self, args, env):
        """Run ghg.main() in-process, capturing Python-level
        stdout/stderr; returns (exit_code, stdout, stderr).

        Wall-clock time.time is frozen at scenario start: the denial
        line embeds a `reset=<epoch>` derived from time.time(), so
        two real-clock runs straddling a second boundary differ for
        reasons unrelated to telemetry. Freezing isolates telemetry
        as the only variable in the off/on comparison (time.monotonic
        is untouched, so durations and timeouts still behave)."""
        out, err = io.StringIO(), io.StringIO()
        with patched_env(env):
            with mock.patch.object(time, "time",
                                   return_value=self._frozen):
                with contextlib.redirect_stdout(out), \
                        contextlib.redirect_stderr(err):
                    code = ghg.main(args)
        return code, out.getvalue(), err.getvalue()

    def read_spans(self, path):
        text = Path(path).read_text()
        return [json.loads(line) for line in text.splitlines()
                if line.strip()]

    def check_ok(self, env):
        return self.call_main(["check", "--", "pr", "view", "1"], env)

    def run_denial(self, env):
        """Exhaust the search bucket (cap 1, as in test_run.py's
        denial test), then attempt the denied call. Returns the
        priming result and the denial result."""
        prime = self.call_main(["run", "--", "search", "repos", "q"],
                               env)
        denied = self.call_main(["run", "--", "search", "repos", "q"],
                                env)
        return prime, denied


class TestCheckSpan(WiringTestCase):
    def test_check_ok_emits_one_ghg_check_span(self):
        otel = self.root / "spans-check.jsonl"
        code, _out, _err = self.check_ok(self.fresh_env(otel_file=otel))
        self.assertEqual(code, 0)
        records = self.read_spans(otel)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["name"], "ghg.check")
        attrs = record["attributes"]
        self.assertEqual(attrs["operation"], "check")
        self.assertEqual(attrs["actor"], ACTOR)
        self.assertEqual(attrs["exit_code"], 0)
        self.assertEqual(attrs["gate_verdict"], "allowed")
        self.assertIn("duration_ms", attrs)
        self.assertLessEqual(set(attrs), set(telemetry.ALLOWED_ATTRIBUTES))


class TestByteIdentical(WiringTestCase):
    def test_check_ok_byte_identical_off_vs_on(self):
        otel = self.root / "spans-bi-check.jsonl"
        off = self.check_ok(self.fresh_env())
        on = self.check_ok(self.fresh_env(otel_file=otel))
        self.assertEqual(off[0], 0)
        self.assertEqual(off, on)  # code + stdout + stderr, byte-equal

    def test_run_denial_byte_identical_off_vs_on_and_span_denied(self):
        limits = {"GHG_LIMITS_JSON": json.dumps({"search": [[60, 1]]})}
        otel = self.root / "spans-bi-run.jsonl"
        prime_off, denied_off = self.run_denial(
            self.fresh_env(extra=limits))
        prime_on, denied_on = self.run_denial(
            self.fresh_env(otel_file=otel, extra=limits))
        self.assertEqual(prime_off[0], 0)
        self.assertEqual(prime_on[0], 0)
        self.assertEqual(denied_off[0], 75)
        self.assertEqual(denied_off, denied_on)
        spans = [r for r in self.read_spans(otel)
                 if r["name"] == "ghg.run"]
        self.assertTrue(spans)
        denied_spans = [r for r in spans
                        if r["attributes"].get("exit_code") == 75]
        self.assertEqual(len(denied_spans), 1)
        self.assertEqual(
            denied_spans[0]["attributes"]["gate_verdict"], "denied")
        for span in spans:
            self.assertLessEqual(set(span["attributes"]),
                                 set(telemetry.ALLOWED_ATTRIBUTES))


class TestWatchWiring(WiringTestCase):
    def test_watch_dispatch_is_traced(self):
        original = ghg.cmd_watch
        ghg.cmd_watch = lambda args: 0  # noqa: E731 - dispatch stub
        self.addCleanup(setattr, ghg, "cmd_watch", original)
        otel = self.root / "spans-watch.jsonl"
        code, _out, _err = self.call_main(
            ["watch", "--repo", "o/r", "--run", "1"],
            self.fresh_env(otel_file=otel))
        self.assertEqual(code, 0)
        spans = [r for r in self.read_spans(otel)
                 if r["name"] == "ghg.watch"]
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["attributes"]["exit_code"], 0)
        self.assertEqual(spans[0]["attributes"]["operation"], "watch")


class TestCanary(WiringTestCase):
    def test_canary_env_value_never_reaches_telemetry_file(self):
        # Token-shaped canary assembled from fragments at runtime;
        # never a literal token-shaped string in source.
        canary = "gh" + "p_" + "Xy9" * 12
        otel = self.root / "spans-canary.jsonl"
        env = self.fresh_env(otel_file=otel, extra={CANARY_ENV: canary})
        code, _out, _err = self.check_ok(env)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.read_spans(otel)), 1)
        self.assertNotIn(canary.encode(), Path(otel).read_bytes())


class TestTelemetryAbsent(WiringTestCase):
    def test_none_telemetry_is_noop_and_creates_no_file(self):
        baseline = self.check_ok(self.fresh_env())
        self.assertEqual(baseline[0], 0)
        otel = self.root / "spans-absent.jsonl"
        original = ghg._telemetry
        ghg._telemetry = None
        self.addCleanup(setattr, ghg, "_telemetry", original)
        result = self.check_ok(self.fresh_env(otel_file=otel))
        self.assertEqual(result, baseline)
        self.assertFalse(otel.exists())


if __name__ == "__main__":
    unittest.main()
