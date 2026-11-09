"""Tests for the optional OpenTelemetry helper (telemetry.py).

Stdlib `unittest` only. telemetry.py is imported directly by adding
the tools/ghg directory to sys.path (it is a self-contained helper,
not a package module).
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GHG_DIR = Path(__file__).resolve().parents[1]
if str(GHG_DIR) not in sys.path:
    sys.path.insert(0, str(GHG_DIR))

import telemetry  # noqa: E402


def _sdk_importable():
    try:
        import opentelemetry.sdk  # noqa: F401
        return True
    except Exception:
        return False


SDK_AVAILABLE = _sdk_importable()


class TelemetryTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ghg-otel-")
        self.root = Path(self.tmp.name)
        self._saved_env = dict(os.environ)
        os.environ.pop(telemetry.ENV_VAR, None)
        os.environ.pop("GHG_FAKE_SECRET_CANARY", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_env)
        self.tmp.cleanup()

    def otel_file(self, name="spans.jsonl"):
        return self.root / name

    def read_records(self, path):
        text = Path(path).read_text()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines]


class TestFilterAttributes(TelemetryTestCase):
    def test_keeps_allowed_keys(self):
        out = telemetry.filter_attributes(
            {"operation": "check", "actor": "tester", "exit_code": 0,
             "duration_ms": 1.5, "gate_verdict": "allowed"})
        self.assertEqual(out, {"operation": "check", "actor": "tester",
                               "exit_code": 0, "duration_ms": 1.5,
                               "gate_verdict": "allowed"})

    def test_drops_rogue_key(self):
        out = telemetry.filter_attributes(
            {"operation": "check", "resolved_env_value": "x",
             "argv": "y", "token": "z"})
        self.assertEqual(out, {"operation": "check"})

    def test_drops_non_scalar_values(self):
        out = telemetry.filter_attributes(
            {"operation": ["check"], "actor": {"a": 1},
             "exit_code": None, "duration_ms": 2.0,
             "gate_verdict": True})
        # Only scalar values survive; bool is a scalar and is kept.
        self.assertEqual(out, {"duration_ms": 2.0, "gate_verdict": True})

    def test_allowed_attributes_exact(self):
        self.assertEqual(
            telemetry.ALLOWED_ATTRIBUTES,
            frozenset({"operation", "actor", "exit_code",
                       "duration_ms", "gate_verdict"}))
        self.assertEqual(telemetry.ENV_VAR, "GHG_OTEL_FILE")


class TestDisabled(TelemetryTestCase):
    def test_enabled_false_when_env_unset(self):
        os.environ.pop(telemetry.ENV_VAR, None)
        self.assertFalse(telemetry.enabled())

    def test_operation_creates_no_file_when_disabled(self):
        os.environ.pop(telemetry.ENV_VAR, None)
        target = self.otel_file()
        cwd_before = set(Path.cwd().iterdir()) if False else None
        with telemetry.operation("check", actor="tester") as handle:
            handle.set_attribute("operation", "check")
            handle.finish(0)
        self.assertFalse(target.exists())
        # Nothing created in the temp dir either.
        self.assertEqual(list(self.root.iterdir()), [])

    def test_actor_callable_not_invoked_when_disabled(self):
        os.environ.pop(telemetry.ENV_VAR, None)
        called = []

        def actor_fn():
            called.append(True)
            return "tester"

        with telemetry.operation("check", actor=actor_fn) as handle:
            handle.finish(0)
        self.assertEqual(called, [])

    def test_exception_propagates_when_disabled(self):
        os.environ.pop(telemetry.ENV_VAR, None)
        with self.assertRaisesRegex(ValueError, "boom-disabled"):
            with telemetry.operation("check", actor="tester"):
                raise ValueError("boom-disabled")


@unittest.skipUnless(SDK_AVAILABLE, "opentelemetry-sdk not installed")
class TestEnabled(TelemetryTestCase):
    def test_enabled_span_written(self):
        target = self.otel_file()
        os.environ[telemetry.ENV_VAR] = str(target)
        self.assertTrue(telemetry.enabled())
        with telemetry.operation("check", actor="tester") as handle:
            handle.finish(0)
        records = self.read_records(target)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["name"], "ghg.check")
        self.assertIsInstance(rec["trace_id"], str)
        self.assertIsInstance(rec["span_id"], str)
        self.assertTrue("parent_span_id" in rec)
        self.assertIsInstance(rec["start_time"], int)
        self.assertIsInstance(rec["end_time"], int)
        self.assertIsInstance(rec["status"], str)
        attrs = rec["attributes"]
        self.assertEqual(attrs["operation"], "check")
        self.assertEqual(attrs["actor"], "tester")
        self.assertEqual(attrs["exit_code"], 0)
        self.assertEqual(attrs["gate_verdict"], "allowed")
        self.assertIn("duration_ms", attrs)
        self.assertIsInstance(attrs["duration_ms"], float)
        self.assertGreaterEqual(attrs["duration_ms"], 0)
        self.assertTrue(set(attrs.keys()) <= set(telemetry.ALLOWED_ATTRIBUTES))

    def test_actor_callable_invoked_when_enabled(self):
        target = self.otel_file()
        os.environ[telemetry.ENV_VAR] = str(target)
        called = []

        def actor_fn():
            called.append(True)
            return "callable-actor"

        with telemetry.operation("run", actor=actor_fn) as handle:
            handle.finish(0)
        self.assertEqual(called, [True])
        records = self.read_records(target)
        self.assertEqual(records[0]["attributes"]["actor"],
                         "callable-actor")

    def test_denial_verdict(self):
        target = self.otel_file()
        os.environ[telemetry.ENV_VAR] = str(target)
        with telemetry.operation("check", actor="tester") as handle:
            handle.finish(75)
        records = self.read_records(target)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["attributes"]["gate_verdict"], "denied")
        self.assertEqual(records[0]["attributes"]["exit_code"], 75)

    def test_canary_never_leaks(self):
        target = self.otel_file()
        os.environ[telemetry.ENV_VAR] = str(target)
        # Assemble canary from fragments — never a literal token shape.
        canary = "gh" + "p_" + "Ab1" * 12
        os.environ["GHG_FAKE_SECRET_CANARY"] = canary
        with telemetry.operation("check", actor="tester") as handle:
            handle.set_attribute("resolved_env_value", canary)
            handle.finish(0)
        raw = Path(target).read_bytes()
        self.assertNotIn(canary.encode(), raw)
        records = self.read_records(target)
        self.assertEqual(len(records), 1)
        self.assertNotIn("resolved_env_value", records[0]["attributes"])

    def test_exception_propagates_and_span_records_error(self):
        target = self.otel_file()
        os.environ[telemetry.ENV_VAR] = str(target)
        with self.assertRaisesRegex(RuntimeError, "boom-enabled"):
            with telemetry.operation("check", actor="tester") as handle:
                handle.set_attribute("operation", "check")
                raise RuntimeError("boom-enabled")
        records = self.read_records(target)
        self.assertEqual(len(records), 1)
        attrs = records[0]["attributes"]
        self.assertEqual(attrs["gate_verdict"], "error")
        self.assertNotIn("exit_code", attrs)

    def test_unusable_path_degrades_to_noop(self):
        bad = self.root / "missing-dir" / "spans.jsonl"
        os.environ[telemetry.ENV_VAR] = str(bad)
        # Must not raise, and must not create the missing directory.
        with telemetry.operation("check", actor="tester") as handle:
            handle.finish(0)
        self.assertFalse(bad.exists())
        self.assertFalse((self.root / "missing-dir").exists())


class TestSdkAbsent(TelemetryTestCase):
    def test_noop_when_availability_probe_false(self):
        target = self.otel_file()
        os.environ[telemetry.ENV_VAR] = str(target)
        with mock.patch.object(telemetry, "sdk_available",
                               return_value=False):
            self.assertFalse(telemetry.enabled())
            with telemetry.operation("check", actor="tester") as handle:
                handle.set_attribute("operation", "check")
                handle.finish(0)
        self.assertFalse(target.exists())

    def test_actor_callable_not_invoked_when_sdk_absent(self):
        target = self.otel_file()
        os.environ[telemetry.ENV_VAR] = str(target)
        called = []

        def actor_fn():
            called.append(True)
            return "tester"

        with mock.patch.object(telemetry, "sdk_available",
                               return_value=False):
            with telemetry.operation("check", actor=actor_fn) as handle:
                handle.finish(0)
        self.assertEqual(called, [])
        self.assertFalse(target.exists())

    def test_sdk_absent_subprocess(self):
        # Genuinely exercise the absent branch: a fresh interpreter
        # where opentelemetry.sdk imports are blocked via sys.modules.
        target = self.otel_file("subprocess-spans.jsonl")
        script = r"""
import os
import sys

# Block the SDK before telemetry is imported.
sys.modules["opentelemetry.sdk"] = None
sys.modules["opentelemetry.sdk.trace"] = None
sys.modules["opentelemetry.sdk.trace.export"] = None
sys.modules["opentelemetry.sdk.resources"] = None

sys.path.insert(0, os.environ["GHG_DIR_FOR_TEST"])
import telemetry

assert telemetry.sdk_available() is False, "sdk should be unavailable"
os.environ[telemetry.ENV_VAR] = os.environ["GHG_OTEL_TARGET"]
assert telemetry.enabled() is False, "enabled should be False without sdk"
called = []
def actor_fn():
    called.append(True)
    return "tester"
with telemetry.operation("check", actor=actor_fn) as handle:
    handle.set_attribute("operation", "check")
    handle.finish(0)
assert called == [], "actor callable must not run on no-op path"
assert not os.path.exists(os.environ["GHG_OTEL_TARGET"]), "no file allowed"
print("SDK-ABSENT-OK")
"""
        env = dict(os.environ)
        env["GHG_DIR_FOR_TEST"] = str(GHG_DIR)
        env["GHG_OTEL_TARGET"] = str(target)
        env.pop(telemetry.ENV_VAR, None)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 0,
                         msg="stdout=%s stderr=%s" % (proc.stdout,
                                                      proc.stderr))
        self.assertIn("SDK-ABSENT-OK", proc.stdout)
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
