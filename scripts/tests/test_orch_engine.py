import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orch.claims import LanesDirMissing, ManifestClaimView, lane_name_for
from orch.engine import Reason, select
from orch.model import BlockerRef, Issue
from orch.workflow import Workflow

LANE_GRAMMAR = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def make_workflow(**overrides):
    values = {
        "project_root": "/tmp/project",
        "project_slug": "project",
        "tracker": "beads",
        "assignee": "worker",
        "active_states": ("open", "in_progress"),
        "terminal_states": ("closed", "done"),
    }
    values.update(overrides)
    return Workflow(**values)


def make_issue(identifier="PROJ-1", **overrides):
    values = {
        "key": f"beads:{identifier}",
        "identifier": identifier,
        "title": "Fix the thing",
        "state": "open",
        "priority": 1,
        "created_at": "2026-01-01T09:00:00+00:00",
        "assigned_to_worker": True,
        "author_ok": True,
    }
    values.update(overrides)
    return Issue(**values)


class StubClaimView:
    def __init__(self, claimed=(), running=None):
        self._claimed = set(claimed)
        self._running = dict(running or {})
        self.warnings = []

    def claimed_lanes(self):
        return set(self._claimed)

    def running_by_state(self):
        return dict(self._running)


class LaneNameForTests(unittest.TestCase):
    def test_dotted_identifier_maps_to_grammar_valid_name(self):
        name = lane_name_for("dap-jo9.1.6.4")
        self.assertEqual(name, "dap-jo9-1-6-4")
        self.assertRegex(name, LANE_GRAMMAR)

    def test_uppercase_is_lowercased(self):
        name = lane_name_for("DAP-Jo9.1")
        self.assertEqual(name, "dap-jo9-1")
        self.assertRegex(name, LANE_GRAMMAR)

    def test_long_identifier_truncates_to_48_with_hash_suffix(self):
        identifier = "a" * 60
        name = lane_name_for(identifier)
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        self.assertEqual(len(name), 48)
        self.assertEqual(name[:41], "a" * 41)
        self.assertEqual(name[41], "-")
        self.assertEqual(name[42:], digest[:6])
        self.assertRegex(name, LANE_GRAMMAR)

    def test_hash_suffix_uses_original_identifier(self):
        identifier = "A" * 60
        name = lane_name_for(identifier)
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        self.assertTrue(name.endswith(digest[:6]))

    def test_unmappable_identifier_uses_x_prefix_and_hash(self):
        identifier = "!!!"
        name = lane_name_for(identifier)
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        self.assertEqual(name, f"x-{digest[:6]}")
        self.assertRegex(name, LANE_GRAMMAR)

    def test_empty_identifier_uses_x_prefix_and_hash(self):
        digest = hashlib.sha256("".encode("utf-8")).hexdigest()
        self.assertEqual(lane_name_for(""), f"x-{digest[:6]}")


class ManifestClaimViewTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lanes_dir = Path(self._tmp.name) / ".lanes"
        self.lanes_dir.mkdir()

    def write_manifest(self, lane, state, raw=None):
        path = self.lanes_dir / f"{lane}.json"
        if raw is not None:
            path.write_text(raw)
        else:
            path.write_text(json.dumps({"name": lane, "state": state}))
        return path

    def test_claimed_manifest_counts_as_claimed(self):
        self.write_manifest("dap-1", "claimed")
        view = ManifestClaimView(str(self.lanes_dir))
        self.assertEqual(view.claimed_lanes(), {"dap-1"})
        self.assertEqual(view.warnings, [])

    def test_settled_manifests_do_not_block(self):
        for lane, state in (
            ("lane-a", "released"),
            ("lane-b", "reaped"),
            ("lane-c", "cleaned"),
        ):
            self.write_manifest(lane, state)
        view = ManifestClaimView(str(self.lanes_dir))
        self.assertEqual(view.claimed_lanes(), set())

    def test_unparseable_manifest_warns_and_blocks_nothing(self):
        self.write_manifest("broken", None, raw="this is not json")
        view = ManifestClaimView(str(self.lanes_dir))
        self.assertEqual(view.claimed_lanes(), set())
        self.assertEqual(len(view.warnings), 1)
        self.assertIn("broken.json", view.warnings[0])

    def test_manifest_without_state_warns_and_blocks_nothing(self):
        self.write_manifest("nostate", None, raw=json.dumps({"name": "nostate"}))
        view = ManifestClaimView(str(self.lanes_dir))
        self.assertEqual(view.claimed_lanes(), set())
        self.assertEqual(len(view.warnings), 1)

    def test_missing_lanes_dir_raises(self):
        missing = str(Path(self._tmp.name) / "does-not-exist")
        with self.assertRaises(LanesDirMissing):
            ManifestClaimView(missing)

    def test_non_manifest_files_are_ignored(self):
        (self.lanes_dir / "dap-1.log").write_text('{"state": "claimed"}')
        (self.lanes_dir / "dap-1.fence").write_text("")
        (self.lanes_dir / "dap-1.json.tmp.123").write_text('{"state": "claimed"}')
        view = ManifestClaimView(str(self.lanes_dir))
        self.assertEqual(view.claimed_lanes(), set())
        self.assertEqual(view.warnings, [])

    def test_running_by_state_is_empty(self):
        self.write_manifest("dap-1", "claimed")
        view = ManifestClaimView(str(self.lanes_dir))
        self.assertEqual(view.running_by_state(), {})

    def test_env_var_resolution(self):
        self.write_manifest("dap-9", "claimed")
        with mock.patch.dict(os.environ, {"AEP_LANES_DIR": str(self.lanes_dir)}):
            view = ManifestClaimView()
        self.assertEqual(view.claimed_lanes(), {"dap-9"})

    def test_env_var_missing_dir_raises(self):
        missing = str(Path(self._tmp.name) / "nope")
        with mock.patch.dict(os.environ, {"AEP_LANES_DIR": missing}):
            with self.assertRaises(LanesDirMissing):
                ManifestClaimView()


class SelectTests(unittest.TestCase):
    def setUp(self):
        self.workflow = make_workflow()
        self.view = StubClaimView()

    def select(self, candidates, workflow=None, view=None, completed=()):
        return select(
            candidates,
            workflow or self.workflow,
            view or self.view,
            set(completed),
        )

    def test_eligible_candidate_dispatches(self):
        issue = make_issue()
        result = self.select([issue])
        self.assertEqual(result.dispatch, [issue])
        self.assertEqual(result.rejections, {})

    def test_terminal_blocker_does_not_block(self):
        blocker = BlockerRef.from_state("beads:X", "closed", ("closed", "done"))
        issue = make_issue(blockers=(blocker,))
        result = self.select([issue])
        self.assertEqual(result.dispatch, [issue])

    def test_open_blocker_blocks_and_carries_key(self):
        blocker = BlockerRef("beads:X", "open", False)
        issue = make_issue(blockers=(blocker,))
        result = self.select([issue])
        self.assertEqual(result.dispatch, [])
        reason, detail = result.rejections["PROJ-1"]
        self.assertEqual(reason, Reason.BLOCKED)
        self.assertEqual(detail, "beads:X")

    def test_blocker_state_absent_from_terminal_set_blocks(self):
        blocker = BlockerRef.from_state("beads:X", "deferred", ("closed", "done"))
        issue = make_issue(blockers=(blocker,))
        result = self.select([issue])
        self.assertEqual(result.rejections["PROJ-1"][0], Reason.BLOCKED)

    def test_terminal_state_rejected(self):
        issue = make_issue(state="closed")
        result = self.select([issue])
        self.assertEqual(result.rejections["PROJ-1"][0], Reason.STATE_TERMINAL)

    def test_inactive_state_rejected(self):
        issue = make_issue(state="deferred")
        result = self.select([issue])
        self.assertEqual(result.rejections["PROJ-1"][0], Reason.STATE_NOT_ACTIVE)

    def test_state_comparison_is_case_and_whitespace_insensitive(self):
        issue = make_issue(state=" Open ")
        result = self.select([issue])
        self.assertEqual(result.dispatch, [issue])

    def test_not_assigned_rejected(self):
        issue = make_issue(assigned_to_worker=False)
        result = self.select([issue])
        reason, detail = result.rejections["PROJ-1"]
        self.assertEqual(reason, Reason.NOT_ASSIGNED)
        self.assertIn("assigned_to_worker", detail)

    def test_author_not_ok_rejected_as_not_assigned(self):
        issue = make_issue(author_ok=False)
        result = self.select([issue])
        reason, detail = result.rejections["PROJ-1"]
        self.assertEqual(reason, Reason.NOT_ASSIGNED)
        self.assertIn("author_ok", detail)

    def test_missing_title_rejected(self):
        issue = make_issue(title="")
        result = self.select([issue])
        reason, detail = result.rejections["PROJ-1"]
        self.assertEqual(reason, Reason.MISSING_FIELDS)
        self.assertIn("title", detail)

    def test_completed_candidate_rejected(self):
        issue = make_issue()
        result = self.select([issue], completed={"beads:PROJ-1"})
        self.assertEqual(result.rejections["PROJ-1"][0], Reason.ALREADY_COMPLETED)
        self.assertEqual(result.dispatch, [])

    def test_per_state_cap_saturates_mid_batch(self):
        workflow = make_workflow(cap_per_state={"open": 2})
        view = StubClaimView(running={"open": 1})
        first = make_issue("PROJ-1", created_at="2026-01-01T00:00:00+00:00")
        second = make_issue("PROJ-2", created_at="2026-01-02T00:00:00+00:00")
        third = make_issue("PROJ-3", created_at="2026-01-03T00:00:00+00:00")
        other = make_issue(
            "PROJ-4", state="in_progress", created_at="2026-01-01T00:00:00+00:00"
        )
        result = self.select([third, second, first, other], workflow, view)
        self.assertEqual(result.dispatch, [first, other])
        for identifier in ("PROJ-2", "PROJ-3"):
            reason, detail = result.rejections[identifier]
            self.assertEqual(reason, Reason.CAP_STATE)
            self.assertEqual(detail, "open")

    def test_global_cap(self):
        workflow = make_workflow(cap_global=1)
        first = make_issue("PROJ-1", created_at="2026-01-01T00:00:00+00:00")
        second = make_issue("PROJ-2", created_at="2026-01-02T00:00:00+00:00")
        result = self.select([second, first], workflow)
        self.assertEqual(result.dispatch, [first])
        self.assertEqual(result.rejections["PROJ-2"][0], Reason.CAP_GLOBAL)

    def test_ordering_priority_then_age_then_identifier(self):
        no_priority = make_issue("PROJ-N", priority=None)
        low = make_issue("PROJ-L", priority=2)
        high_older = make_issue(
            "PROJ-H2", priority=1, created_at="2026-01-02T00:00:00+00:00"
        )
        high_earlier = make_issue(
            "PROJ-H1", priority=1, created_at="2026-01-01T00:00:00+00:00"
        )
        result = self.select([no_priority, low, high_older, high_earlier])
        self.assertEqual(
            result.dispatch, [high_earlier, high_older, low, no_priority]
        )

    def test_every_rejected_candidate_has_exactly_one_reason(self):
        blocked = make_issue(
            "PROJ-B", blockers=(BlockerRef("beads:X", "open", False),)
        )
        terminal = make_issue("PROJ-T", state="done")
        ok = make_issue("PROJ-O")
        result = self.select([blocked, terminal, ok])
        self.assertEqual(result.dispatch, [ok])
        self.assertEqual(set(result.rejections), {"PROJ-B", "PROJ-T"})
        for value in result.rejections.values():
            self.assertIsInstance(value, tuple)
            self.assertEqual(len(value), 2)
            self.assertIsInstance(value[0], Reason)


class SelectWithManifestViewTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lanes_dir = Path(self._tmp.name) / ".lanes"
        self.lanes_dir.mkdir()
        self.workflow = make_workflow()

    def write_manifest(self, lane, state):
        (self.lanes_dir / f"{lane}.json").write_text(
            json.dumps({"name": lane, "state": state})
        )

    def test_actively_claimed_lane_rejected(self):
        issue = make_issue("dap-1")
        self.write_manifest(lane_name_for("dap-1"), "claimed")
        view = ManifestClaimView(str(self.lanes_dir))
        result = select([issue], self.workflow, view, set())
        self.assertEqual(result.dispatch, [])
        self.assertEqual(result.rejections["dap-1"][0], Reason.ALREADY_CLAIMED)

    def test_settled_manifest_for_same_lane_does_not_block(self):
        issue = make_issue("dap-1")
        self.write_manifest(lane_name_for("dap-1"), "released")
        view = ManifestClaimView(str(self.lanes_dir))
        result = select([issue], self.workflow, view, set())
        self.assertEqual(result.dispatch, [issue])
        self.assertEqual(result.rejections, {})

    def test_colliding_identifiers_both_rejected(self):
        dotted = make_issue("dap-1.2")
        dashed = make_issue("dap-1-2")
        view = ManifestClaimView(str(self.lanes_dir))
        result = select([dotted, dashed], self.workflow, view, set())
        self.assertEqual(result.dispatch, [])
        for identifier in ("dap-1.2", "dap-1-2"):
            reason, detail = result.rejections[identifier]
            self.assertEqual(reason, Reason.NAME_COLLISION)
            self.assertEqual(detail, "dap-1-2")


if __name__ == "__main__":
    unittest.main()
