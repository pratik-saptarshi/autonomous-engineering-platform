"""Task 3 (Track B) tests: orch dry-run ticks emit telemetry spans.

``orch dry-run`` must execute inside a telemetry span named
``orch.dry_run``; ``preflight`` stays untraced. Telemetry must never
change any exit code, stdout, or stderr on any path.

Stdlib ``unittest`` only, modelled on ``test_orch_cli.py`` (fixture
spec helpers + FixtureAdapter via ``main(..., adapter_factory=...,
out=io.StringIO(), err=io.StringIO())``).

CI runs these tests WITHOUT the OpenTelemetry SDK installed: the
off / SDK-absent / byte-identical assertions are unconditional, and
every real-SDK assertion is guarded by ``skipUnless`` on SDK
importability.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orch import cli, telemetry
from orch.adapters_fixture import FixtureAdapter
from orch.model import Issue


def _sdk_importable():
    try:
        import opentelemetry.sdk  # noqa: F401
        return True
    except Exception:
        return False


SDK_AVAILABLE = _sdk_importable()


def beads_spec(**overrides):
    lines = {
        "project_root": "/tmp/orch-telemetry-test-project",
        "project_slug": "proj",
        "tracker": "beads",
        "assignee": "worker-a",
        "active_states": "[open]",
        "terminal_states": "[closed]",
        "base_ref": "main",
    }
    lines.update(overrides)
    body = "\n".join(f"{key}: {value}" for key, value in lines.items())
    return f"---\n{body}\n---\nTemplate body.\n"


def make_issue(identifier, **overrides):
    values = {
        "key": f"beads:{identifier}",
        "identifier": identifier,
        "title": f"Title {identifier}",
        "state": "open",
        "priority": 1,
        "created_at": "2026-01-01T09:00:00Z",
        "updated_at": "2026-01-02T09:00:00Z",
        "assigned_to_worker": True,
        "author_ok": True,
    }
    values.update(overrides)
    return Issue(**values)


def fresh_fixture_adapter(workflow):
    return FixtureAdapter([make_issue("A-1")])


class OrchTelemetryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.lanes_dir = self.root / "lanes"
        self.lanes_dir.mkdir()
        self._env = mock.patch.dict(
            os.environ, {"AEP_LANES_DIR": str(self.lanes_dir)}
        )
        self._env.start()
        self.addCleanup(self._env.stop)
        os.environ.pop(telemetry.ENV_VAR, None)
        os.environ.pop("ORCH_FAKE_SECRET_CANARY", None)

    # -- harness (modelled on test_orch_cli.CliTestCase) -------------

    def write_spec(self, text, name="spec.workflow.md"):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def run_cli(self, argv, **kwargs):
        kwargs.setdefault("adapter_factory", fresh_fixture_adapter)
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(argv, out=out, err=err, **kwargs)
        return code, out.getvalue(), err.getvalue()

    def make_bin(self, tools):
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        for name, target in tools.items():
            dest = bin_dir / name
            if target == "script":
                dest.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                dest.chmod(0o755)
            else:
                dest.symlink_to(target)
        return str(bin_dir)

    def dry_run_tick(self, spec):
        return self.run_cli(["dry-run", "--workflow", spec])

    def assert_normal_tick(self, result):
        code, out, err = result
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertIn("would dispatch (1):", out)
        self.assertIn("A-1", out)
        self.assertIn("per-state caps", out)

    def read_records(self, path):
        text = Path(path).read_text(encoding="utf-8")
        return [json.loads(ln) for ln in text.splitlines() if ln.strip()]

    # -- module contract (unconditional; no SDK needed) --------------

    def test_constants_and_filter(self):
        self.assertEqual(telemetry.ENV_VAR, "ORCH_OTEL_FILE")
        self.assertEqual(
            telemetry.ALLOWED_ATTRIBUTES,
            frozenset({"operation", "exit_code", "duration_ms"}),
        )
        out = telemetry.filter_attributes(
            {
                "operation": "dry_run",
                "exit_code": 0,
                "duration_ms": 1.5,
                "actor": "someone",
                "gate_verdict": "allowed",
                "resolved_env_value": "x",
            }
        )
        self.assertEqual(
            out,
            {"operation": "dry_run", "exit_code": 0, "duration_ms": 1.5},
        )
        # Non-scalar values are dropped even for allowlisted keys.
        out = telemetry.filter_attributes(
            {"operation": ["dry_run"], "exit_code": None,
             "duration_ms": 2.0}
        )
        self.assertEqual(out, {"duration_ms": 2.0})

    # -- off (unconditional) ------------------------------------------

    def test_off_env_unset_no_file_and_normal_output(self):
        os.environ.pop(telemetry.ENV_VAR, None)
        spec = self.write_spec(beads_spec())
        target = self.root / "spans.jsonl"
        self.assert_normal_tick(self.dry_run_tick(spec))
        self.assertFalse(target.exists())
        self.assertFalse(telemetry.enabled())

    # -- SDK-absent (unconditional; the CI case) ----------------------

    def test_sdk_absent_no_file_and_normal_output(self):
        # The CLI wiring imported the real module; the no-op below
        # must come from the availability probe, not a missing import.
        self.assertIsNotNone(cli._telemetry)
        target = self.root / "spans.jsonl"
        os.environ[telemetry.ENV_VAR] = str(target)
        spec = self.write_spec(beads_spec())
        with mock.patch.object(
            telemetry, "sdk_available", return_value=False
        ):
            self.assertFalse(telemetry.enabled())
            result = self.dry_run_tick(spec)
        self.assert_normal_tick(result)
        self.assertFalse(target.exists())

    # -- byte-identical (unconditional) -------------------------------

    def test_byte_identical_off_vs_sdk_blocked(self):
        spec = self.write_spec(beads_spec())
        os.environ.pop(telemetry.ENV_VAR, None)
        off = self.dry_run_tick(spec)
        self.assert_normal_tick(off)
        target = self.root / "spans.jsonl"
        os.environ[telemetry.ENV_VAR] = str(target)
        with mock.patch.object(
            telemetry, "sdk_available", return_value=False
        ):
            blocked = self.dry_run_tick(spec)
        # exit code + stdout + stderr, byte-equal
        self.assertEqual(off, blocked)
        self.assertFalse(target.exists())

    # -- on (real SDK only) -------------------------------------------

    @unittest.skipUnless(SDK_AVAILABLE, "opentelemetry-sdk not installed")
    def test_on_emits_exactly_one_dry_run_span(self):
        target = self.root / "spans.jsonl"
        os.environ[telemetry.ENV_VAR] = str(target)
        self.assertTrue(telemetry.enabled())
        spec = self.write_spec(beads_spec())
        self.assert_normal_tick(self.dry_run_tick(spec))
        records = self.read_records(target)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["name"], "orch.dry_run")
        self.assertIsInstance(rec["trace_id"], str)
        self.assertIsInstance(rec["span_id"], str)
        self.assertIn("parent_span_id", rec)
        self.assertIsInstance(rec["start_time"], int)
        self.assertIsInstance(rec["end_time"], int)
        self.assertIsInstance(rec["status"], str)
        attrs = rec["attributes"]
        self.assertEqual(attrs["operation"], "dry_run")
        self.assertEqual(attrs["exit_code"], 0)
        self.assertIn("duration_ms", attrs)
        self.assertIsInstance(attrs["duration_ms"], float)
        self.assertGreaterEqual(attrs["duration_ms"], 0)
        self.assertLessEqual(
            set(attrs), {"operation", "exit_code", "duration_ms"}
        )

    @unittest.skipUnless(SDK_AVAILABLE, "opentelemetry-sdk not installed")
    def test_error_tick_records_exit_code_1(self):
        target = self.root / "spans.jsonl"
        os.environ[telemetry.ENV_VAR] = str(target)
        missing = str(self.root / "nope.workflow.md")
        code, out, err = self.run_cli(["dry-run", "--workflow", missing])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("error:"), err)
        self.assertNotIn("Traceback", out + err)
        records = self.read_records(target)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "orch.dry_run")
        self.assertEqual(records[0]["attributes"]["exit_code"], 1)
        self.assertEqual(records[0]["attributes"]["operation"], "dry_run")

    @unittest.skipUnless(SDK_AVAILABLE, "opentelemetry-sdk not installed")
    def test_preflight_creates_no_telemetry_file(self):
        target = self.root / "spans.jsonl"
        os.environ[telemetry.ENV_VAR] = str(target)
        bin_dir = self.make_bin(
            {"git": shutil.which("git"), "bd": "script"}
        )
        spec = self.write_spec(beads_spec())
        with mock.patch.dict(os.environ, {"PATH": bin_dir}):
            code, out, err = self.run_cli(
                ["preflight", "--workflow", spec]
            )
        self.assertEqual(code, 0, out + err)
        self.assertIn("preflight: PASS", out)
        self.assertFalse(target.exists())

    @unittest.skipUnless(SDK_AVAILABLE, "opentelemetry-sdk not installed")
    def test_canary_never_leaks(self):
        target = self.root / "spans.jsonl"
        os.environ[telemetry.ENV_VAR] = str(target)
        # Token-shaped canary assembled from fragments at runtime;
        # never a literal token-shaped string in source (gitleaks).
        canary = "gh" + "p_" + "Zz4" * 12
        os.environ["ORCH_FAKE_SECRET_CANARY"] = canary
        with telemetry.operation("dry_run") as handle:
            handle.set_attribute("resolved_env_value", canary)
            handle.finish(0)
        raw = Path(target).read_bytes()
        self.assertNotIn(canary.encode(), raw)
        records = self.read_records(target)
        self.assertEqual(len(records), 1)
        self.assertNotIn(
            "resolved_env_value", records[0]["attributes"]
        )


if __name__ == "__main__":
    unittest.main()
