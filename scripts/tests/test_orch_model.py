import dataclasses
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orch.adapters_fixture import FixtureAdapter
from orch.model import BlockerRef, Issue, TrackerAdapter


def make_issue(key="beads:1", identifier="PROJ-1", **overrides):
    values = {
        "key": key,
        "identifier": identifier,
        "title": "Fix the thing",
        "description": "A complete description.",
        "state": "open",
        "priority": 2,
        "labels": ("Backend", "Needs-Triage"),
        "blockers": (),
        "created_at": "2026-01-01T09:00:00+00:00",
        "updated_at": "2026-01-02T09:00:00+00:00",
        "status_since": "2026-01-02T08:30:00+00:00",
        "url": "https://tracker.example/issues/PROJ-1",
        "branch": "feature/proj-1",
        "assignee": "worker",
        "assigned_to_worker": True,
        "author": "Reporter",
        "author_ok": True,
    }
    values.update(overrides)
    return Issue(**values)


class TestIssueModel(unittest.TestCase):
    def test_labels_and_state_are_normalized_at_construction(self):
        issue = make_issue(state="In_Progress", labels=["Backend", "URGENT"])

        self.assertEqual(issue.state, "in_progress")
        self.assertEqual(issue.labels, ("backend", "urgent"))

    def test_author_and_status_since_are_carried_verbatim(self):
        issue = make_issue(
            author="MixedCaseAuthor",
            status_since="2026-01-02T08:30:00+00:00",
        )

        self.assertEqual(issue.author, "MixedCaseAuthor")
        self.assertEqual(issue.status_since, "2026-01-02T08:30:00+00:00")

    def test_issue_is_frozen(self):
        issue = make_issue()

        with self.assertRaises(dataclasses.FrozenInstanceError):
            issue.title = "Changed"

    def test_blocker_terminal_state_is_derived_from_terminal_set(self):
        terminal = BlockerRef.from_state(
            "beads:99", "Closed", {"closed", "done"}
        )
        active = BlockerRef.from_state(
            "beads:100", "In_Progress", {"closed", "done"}
        )

        self.assertEqual(terminal.state, "closed")
        self.assertTrue(terminal.is_terminal)
        self.assertEqual(active.state, "in_progress")
        self.assertFalse(active.is_terminal)

    def test_blocker_ref_is_frozen(self):
        blocker = BlockerRef("beads:99", "open", False)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            blocker.state = "closed"


class TestFixtureAdapter(unittest.TestCase):
    def setUp(self):
        self.blocker = make_issue(
            key="beads:2",
            identifier="PROJ-2",
            state="closed",
        )
        self.issue = make_issue(
            blockers=(
                BlockerRef.from_state(
                    self.blocker.key, self.blocker.state, {"closed"}
                ),
            )
        )
        self.adapter = FixtureAdapter([self.issue, self.blocker])

    def test_fixture_adapter_satisfies_tracker_adapter_protocol(self):
        self.assertIsInstance(self.adapter, TrackerAdapter)

    def test_fetch_candidates_round_trip(self):
        self.assertEqual(
            self.adapter.fetch_candidates(), [self.issue, self.blocker]
        )

    def test_fetch_by_ids_round_trip_and_omits_missing_keys(self):
        self.assertEqual(
            self.adapter.fetch_by_ids(["beads:2", "beads:missing", "beads:1"]),
            [self.blocker, self.issue],
        )

    def test_fetch_states_round_trip_and_omits_missing_keys(self):
        self.assertEqual(
            self.adapter.fetch_states(
                ["beads:1", "beads:missing", "beads:2"]
            ),
            {"beads:1": "open", "beads:2": "closed"},
        )

    def test_write_methods_are_read_only_in_stage_1(self):
        with self.assertRaisesRegex(
            NotImplementedError, "^read-only in Stage 1$"
        ):
            self.adapter.comment("beads:1", "A comment")

        with self.assertRaisesRegex(
            NotImplementedError, "^read-only in Stage 1$"
        ):
            self.adapter.transition("beads:1", "closed")

    def test_set_state_mutation_is_visible_to_later_fetches(self):
        self.adapter.set_state("beads:1", "In_Progress")

        self.assertEqual(
            self.adapter.fetch_states(["beads:1"]),
            {"beads:1": "in_progress"},
        )
        self.assertEqual(self.adapter.fetch_by_ids(["beads:1"])[0].state,
                         "in_progress")

    def test_remove_mutation_makes_issue_absent(self):
        self.adapter.remove("beads:1")

        self.assertEqual(self.adapter.fetch_by_ids(["beads:1"]), [])
        self.assertEqual(self.adapter.fetch_states(["beads:1"]), {})
        self.assertNotIn(self.issue, self.adapter.fetch_candidates())

    def test_fail_next_fetch_raises_once(self):
        failure = RuntimeError("fixture fetch failed")
        self.adapter.fail_next_fetch(failure)

        with self.assertRaises(RuntimeError) as raised:
            self.adapter.fetch_candidates()
        self.assertIs(raised.exception, failure)
        self.assertEqual(
            self.adapter.fetch_candidates(), [self.issue, self.blocker]
        )


if __name__ == "__main__":
    unittest.main()
