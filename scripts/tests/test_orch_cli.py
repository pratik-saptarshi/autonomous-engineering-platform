import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orch import cli
from orch.adapters_beads import BeadsAdapter
from orch.adapters_fixture import FixtureAdapter
from orch.claims import lane_name_for
from orch.model import BlockerRef, Issue

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "orch"

SCHEMA_KEYS = {
    "ts",
    "tracker",
    "ready",
    "rejected",
    "ready_wait_s",
    "ready_wait_basis",
    "exits",
    "age_s",
    "points_spent",
    "fetch_count",
    "type_excluded_count",
    "truncated",
}


def beads_spec(**overrides):
    lines = {
        "project_root": "/tmp/orch-cli-test-project",
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


def github_spec(project_root):
    return (
        "---\n"
        f"project_root: {project_root}\n"
        "project_slug: proj\n"
        "tracker: github\n"
        "repo: example/proj\n"
        "assignee: worker-a\n"
        "active_states: [open]\n"
        "terminal_states: [closed]\n"
        "base_ref: main\n"
        "---\nTemplate body.\n"
    )


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


class CliTestCase(unittest.TestCase):
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

    def write_spec(self, text, name="spec.workflow.md"):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def run_cli(self, argv, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(argv, out=out, err=err, **kwargs)
        return code, out.getvalue(), err.getvalue()

    def make_bin(self, tools):
        """A PATH dir holding symlinks/scripts for the named tools."""
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


class DryRunFixtureTests(CliTestCase):
    def fixture_adapter(self):
        blocker = BlockerRef(key="beads:X-9", state="open", is_terminal=False)
        return FixtureAdapter(
            [
                make_issue("A-1", priority=2),
                make_issue(
                    "E-5", priority=1, created_at="2026-01-02T09:00:00Z"
                ),
                make_issue("B-2", blockers=(blocker,)),
                make_issue("C-3", assigned_to_worker=False),
                make_issue("D-4", state="closed"),
            ]
        )

    def test_dispatch_list_and_rejections_match_hand_computed(self):
        spec = self.write_spec(beads_spec())
        code, out, err = self.run_cli(
            ["dry-run", "--workflow", spec],
            adapter_factory=lambda wf: self.fixture_adapter(),
        )
        self.assertEqual(code, 0, err)
        dispatch_section = out.split("would dispatch")[1].split("rejected")[0]
        self.assertLess(
            dispatch_section.index("E-5"), dispatch_section.index("A-1")
        )
        self.assertIn("B-2", out)
        self.assertIn("BLOCKED", out)
        self.assertIn("C-3", out)
        self.assertIn("NOT_ASSIGNED", out)
        self.assertIn("D-4", out)
        self.assertIn("STATE_TERMINAL", out)

    def test_limits_line_present(self):
        spec = self.write_spec(beads_spec())
        code, out, err = self.run_cli(
            ["dry-run", "--workflow", spec],
            adapter_factory=lambda wf: self.fixture_adapter(),
        )
        self.assertEqual(code, 0, err)
        self.assertIn("per-state caps", out)
        self.assertIn("this batch only", out)
        self.assertIn("GitHub blockers reflect label data only", out)
        self.assertIn("no store", out)

    def test_dry_run_creates_no_files_outside_log(self):
        home = self.root / "home"
        home.mkdir()
        spec = self.write_spec(beads_spec())
        log = self.root / "obs" / "log.jsonl"
        before = {str(p) for p in self.root.rglob("*")}
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            code, out, err = self.run_cli(
                ["dry-run", "--workflow", spec, "--log", str(log)],
                adapter_factory=lambda wf: self.fixture_adapter(),
            )
        self.assertEqual(code, 0, err)
        after = {str(p) for p in self.root.rglob("*")}
        new_paths = after - before
        self.assertEqual(
            new_paths,
            {str(log.parent), str(log)},
            f"unexpected files created: {new_paths}",
        )
        self.assertFalse((home / ".local").exists())


class DryRunBeadsPayloadTests(CliTestCase):
    def setUp(self):
        super().setUp()
        # The adapter resolves the bd path even behind the runner seam.
        which = mock.patch(
            "shutil.which",
            side_effect=lambda name, *a, **k: (
                "/fake/bin/bd" if name == "bd" else None
            ),
        )
        which.start()
        self.addCleanup(which.stop)

    class PayloadRunner:
        def __init__(self, payload):
            self._payload = payload
            self.calls = []

        def __call__(self, argv, **kwargs):
            self.calls.append(list(argv))
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(self._payload), stderr=""
            )

    def test_recorded_fixture_payload(self):
        payload = json.loads(
            (FIXTURES / "beads-list.json").read_text(encoding="utf-8")
        )
        runner = self.PayloadRunner(payload)
        spec = self.write_spec(beads_spec())
        code, out, err = self.run_cli(
            ["dry-run", "--workflow", spec],
            adapter_factory=lambda wf: BeadsAdapter(wf, runner=runner),
        )
        self.assertEqual(code, 0, err)
        # Hand-computed from beads-list.json under assignee worker-a,
        # active {open}, terminal {closed}, default type allowlist:
        # dap-test.1 BLOCKED (dap-test.3 open), dap-test.2 STATE_TERMINAL,
        # dap-test.3 NOT_ASSIGNED, dap-test.4 STATE_NOT_ACTIVE,
        # dap-test.5/.6 type-excluded. Nothing dispatches.
        self.assertIn("dap-test.1", out)
        self.assertIn("BLOCKED", out)
        self.assertIn("dap-test.2", out)
        self.assertIn("STATE_TERMINAL", out)
        self.assertIn("dap-test.3", out)
        self.assertIn("NOT_ASSIGNED", out)
        self.assertIn("dap-test.4", out)
        self.assertIn("STATE_NOT_ACTIVE", out)
        self.assertIn("6", out)  # fetch count
        self.assertIn("type-excluded: 2", out)

    def test_dispatch_positive_inline_payload(self):
        payload = [
            {
                "id": "x.2",
                "title": "Second",
                "status": "open",
                "issue_type": "task",
                "priority": 2,
                "assignee": "worker-a",
                "created_at": "2026-01-01T09:00:00Z",
                "updated_at": "2026-01-02T09:00:00Z",
                "dependencies": [],
            },
            {
                "id": "x.1",
                "title": "First",
                "status": "open",
                "issue_type": "bug",
                "priority": 1,
                "assignee": "worker-a",
                "created_at": "2026-01-01T08:00:00Z",
                "updated_at": "2026-01-02T08:00:00Z",
                "dependencies": [],
            },
        ]
        runner = self.PayloadRunner(payload)
        spec = self.write_spec(beads_spec())
        code, out, err = self.run_cli(
            ["dry-run", "--workflow", spec],
            adapter_factory=lambda wf: BeadsAdapter(wf, runner=runner),
        )
        self.assertEqual(code, 0, err)
        dispatch_section = out.split("would dispatch")[1].split("rejected")[0]
        self.assertLess(
            dispatch_section.index("x.1"), dispatch_section.index("x.2")
        )

class DryRunFailureTests(CliTestCase):
    def test_missing_bd_fails_loud_without_traceback(self):
        bin_dir = self.make_bin({"git": shutil.which("git")})
        spec = self.write_spec(beads_spec())
        with mock.patch.dict(os.environ, {"PATH": bin_dir}):
            code, out, err = self.run_cli(["dry-run", "--workflow", spec])
        self.assertNotEqual(code, 0)
        self.assertIn("bd", out + err)
        self.assertNotIn("Traceback", out + err)


class ObservationLogTests(CliTestCase):
    def test_log_appends_schema_conformant_observations(self):
        adapter = FixtureAdapter([make_issue("A-1")])
        spec = self.write_spec(beads_spec())
        log = self.root / "obs.jsonl"
        for _ in range(2):
            code, out, err = self.run_cli(
                ["dry-run", "--workflow", spec, "--log", str(log)],
                adapter_factory=lambda wf: adapter,
            )
            self.assertEqual(code, 0, err)
        lines = log.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)  # appended, not overwritten
        obs = json.loads(lines[0])
        self.assertEqual(set(obs), SCHEMA_KEYS)
        self.assertIsInstance(obs["ts"], str)
        self.assertEqual(obs["tracker"], "beads")
        self.assertEqual(obs["ready"], ["A-1"])
        self.assertEqual(obs["rejected"], {})
        self.assertEqual(set(obs["ready_wait_s"]), {"A-1"})
        self.assertIsInstance(obs["ready_wait_s"]["A-1"], int)
        self.assertEqual(obs["ready_wait_basis"], "updated_at_lb")
        self.assertEqual(obs["exits"], [])
        self.assertEqual(set(obs["age_s"]), {"A-1"})
        self.assertIsNone(obs["points_spent"])
        self.assertIsInstance(obs["fetch_count"], int)
        self.assertIsInstance(obs["type_excluded_count"], int)
        self.assertIs(obs["truncated"], False)

    def test_exits_and_pickup_explained(self):
        adapter = FixtureAdapter([make_issue("X-1"), make_issue("Y-2")])
        spec = self.write_spec(beads_spec())
        log = self.root / "obs.jsonl"
        code, _, err = self.run_cli(
            ["dry-run", "--workflow", spec, "--log", str(log)],
            adapter_factory=lambda wf: adapter,
        )
        self.assertEqual(code, 0, err)
        # X-1 leaves the ready set; a manifest for its lane was claimed
        # in the interval. Y-2 also leaves, with no manifest.
        manifest = {
            "state": "claimed",
            "claimed_at": "2999-01-01T00:00:00+00:00",
            "updated_at": "2999-01-01T00:00:00+00:00",
        }
        # claimed_at far in the future would not be <= now; use now-ish:
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat()
        manifest["claimed_at"] = now_iso
        manifest["updated_at"] = now_iso
        (self.lanes_dir / f"{lane_name_for('X-1')}.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        adapter.remove("beads:X-1")
        adapter.remove("beads:Y-2")
        code, _, err = self.run_cli(
            ["dry-run", "--workflow", spec, "--log", str(log)],
            adapter_factory=lambda wf: adapter,
        )
        self.assertEqual(code, 0, err)
        lines = log.read_text(encoding="utf-8").strip().splitlines()
        obs2 = json.loads(lines[1])
        exits = {e["identifier"]: e["pickup_explained"] for e in obs2["exits"]}
        self.assertEqual(exits, {"X-1": True, "Y-2": False})


class SummarizeTests(CliTestCase):
    def write_log(self, observations):
        log = self.root / "obs.jsonl"
        log.write_text(
            "".join(json.dumps(o) + "\n" for o in observations),
            encoding="utf-8",
        )
        return str(log)

    def base_obs(self, **overrides):
        obs = {
            "ts": "2026-01-01T00:00:00+00:00",
            "tracker": "beads",
            "ready": [],
            "rejected": {},
            "ready_wait_s": {},
            "ready_wait_basis": "updated_at_lb",
            "exits": [],
            "age_s": {},
            "points_spent": None,
            "fetch_count": 0,
            "type_excluded_count": 0,
            "truncated": False,
        }
        obs.update(overrides)
        return obs

    def test_three_observation_metrics_exact(self):
        log = self.write_log(
            [
                self.base_obs(
                    ready=["a", "b"], ready_wait_s={"a": 100, "b": 200}
                ),
                self.base_obs(
                    ts="2026-01-01T01:00:00+00:00",
                    ready=["b", "c"],
                    ready_wait_s={"b": 300, "c": 400},
                    exits=[{"identifier": "a", "pickup_explained": True}],
                ),
                self.base_obs(
                    ts="2026-01-01T02:00:00+00:00",
                    ready=["b"],
                    ready_wait_s={"b": 500},
                    exits=[{"identifier": "c", "pickup_explained": False}],
                ),
            ]
        )
        code, out, err = self.run_cli(["dry-run", "--summarize", log])
        self.assertEqual(code, 0, err)
        self.assertIn("observations: 3", out)
        self.assertIn("window span: 7200s", out)
        self.assertIn("ready-set size: min 1, median 2, max 2", out)
        # churn: {a,b}->{b,c} = 2, {b,c}->{b} = 1 -> mean 1.5
        self.assertIn("mean churn: 1.5", out)
        # waits pooled [100,200,300,400,500]: median 300, p95 (nearest
        # rank, ceil(0.95*5)=5th) = 500; basis labelled indicative only
        self.assertIn("ready-wait basis: updated_at_lb (indicative only)", out)
        self.assertIn("ready-wait: median 300s, p95 500s", out)
        # pickup lag: a first ready at obs1, explained exit at obs2
        self.assertIn("pickup lag: median 3600s over 1 pickup-explained exit", out)
        self.assertIn("non-empty ready fraction: 3/3", out)

    def test_single_observation_churn_na(self):
        log = self.write_log([self.base_obs(ready=["a"])])
        code, out, err = self.run_cli(["dry-run", "--summarize", log])
        self.assertEqual(code, 0, err)
        self.assertIn("observations: 1", out)
        self.assertIn("mean churn: n/a", out)
        self.assertIn("pickup lag: n/a", out)


class PreflightTests(CliTestCase):
    def test_beads_preflight_passes_with_fixture_bd(self):
        bin_dir = self.make_bin(
            {"git": shutil.which("git"), "bd": "script"}
        )
        spec = self.write_spec(beads_spec())
        with mock.patch.dict(os.environ, {"PATH": bin_dir}):
            code, out, err = self.run_cli(["preflight", "--workflow", spec])
        self.assertEqual(code, 0, out + err)
        self.assertIn("bd", out)
        self.assertIn("task, bug, story, spike, chore", out)
        self.assertIn("managed_by: absent", out)
        self.assertIn("preflight: PASS", out)

    def test_github_preflight_fails_loud_without_ghg(self):
        repo = self.root / "proj"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "remote",
                "add",
                "origin",
                "https://github.com/example/proj.git",
            ],
            check=True,
        )
        bin_dir = self.make_bin({"git": shutil.which("git")})
        spec = self.write_spec(github_spec(repo))
        with mock.patch.dict(os.environ, {"PATH": bin_dir}):
            code, out, err = self.run_cli(["preflight", "--workflow", spec])
        self.assertNotEqual(code, 0)
        self.assertIn("ghg", out + err)
        self.assertNotIn("Traceback", out + err)

    def test_github_preflight_projects_hourly_rate(self):
        repo = self.root / "proj"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "remote",
                "add",
                "origin",
                "https://github.com/example/proj.git",
            ],
            check=True,
        )
        bin_dir = self.make_bin(
            {"git": shutil.which("git"), "ghg": "script", "bd": "script"}
        )
        spec = self.write_spec(github_spec(repo))
        with mock.patch.dict(os.environ, {"PATH": bin_dir}):
            code, out, err = self.run_cli(["preflight", "--workflow", spec])
        self.assertEqual(code, 0, out + err)
        # defaults: poll_seconds 300 -> 12 polls/hour; cap 6 calls/poll
        self.assertIn("72", out)
        self.assertIn("preflight: PASS", out)

    def test_preflight_never_prints_resolved_env_value(self):
        bin_dir = self.make_bin(
            {"git": shutil.which("git"), "bd": "script"}
        )
        spec = self.write_spec(beads_spec(managed_by="$ORCH_MB_SENTINEL"))
        env = {"PATH": bin_dir, "ORCH_MB_SENTINEL": "s3cr3t-sentinel-value"}
        with mock.patch.dict(os.environ, env):
            code, out, err = self.run_cli(["preflight", "--workflow", spec])
        self.assertEqual(code, 0, out + err)
        self.assertIn("managed_by: present", out)
        self.assertNotIn("s3cr3t-sentinel-value", out + err)


if __name__ == "__main__":
    unittest.main()
