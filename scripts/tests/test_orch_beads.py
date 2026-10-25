import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orch.adapters_beads import BeadsAdapter, BeadsError, FetchCeilingExceeded
from orch.workflow import Workflow

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "orch"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_workflow(**overrides):
    values = {
        "project_root": "/projects/dap-test",
        "project_slug": "dap-test",
        "tracker": "beads",
        "assignee": "worker-a",
        "active_states": ("open", "in_progress", "blocked", "deferred", "hooked"),
        "terminal_states": ("closed",),
    }
    values.update(overrides)
    return Workflow(**values)


class FakeRunner:
    """Injectable ``subprocess.run`` stand-in serving fixture payloads."""

    def __init__(self, returncode=0, stderr=""):
        self.calls = []  # list of (argv, kwargs)
        self._returncode = returncode
        self._stderr = stderr
        self._list_payload = load_fixture("beads-list.json")
        self._show_payload = load_fixture("beads-show.json")

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        if "list" in argv:
            payload = self._list_payload
        elif "show" in argv:
            payload = self._show_payload
        else:
            payload = []
        return SimpleNamespace(
            returncode=self._returncode,
            stdout=json.dumps(payload),
            stderr=self._stderr,
        )


class PerIdShowRunner:
    """Runner whose ``bd show`` outcome depends on the requested id.

    Serves the recorded payloads for present ids. ``missing_ids`` fail
    with the real CLI's not-found shape (exit 1, a JSON error object on
    stdout, ``Issue <id> not found`` on stderr); ``broken_ids`` fail
    with an unrelated error.
    """

    def __init__(self, missing_ids=(), broken_ids=()):
        self.calls = []
        self._missing_ids = set(missing_ids)
        self._broken_ids = set(broken_ids)
        self._list_payload = load_fixture("beads-list.json")
        self._show_payload = load_fixture("beads-show.json")

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        if "list" in argv:
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(self._list_payload), stderr=""
            )
        if "show" in argv:
            raw_id = argv[argv.index("show") + 1]
            if raw_id in self._missing_ids:
                return SimpleNamespace(
                    returncode=1,
                    stdout=json.dumps(
                        {
                            "error": "no issues found matching the provided IDs",
                            "hint": "try 'bd list' to see available issues",
                            "schema_version": 1,
                        }
                    ),
                    stderr=f"Issue {raw_id} not found",
                )
            if raw_id in self._broken_ids:
                return SimpleNamespace(
                    returncode=1, stdout="", stderr="database is locked"
                )
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(self._show_payload), stderr=""
            )
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")


class BeadsAdapterTests(unittest.TestCase):
    def setUp(self):
        which = mock.patch("shutil.which", return_value="/fake/bin/bd")
        which.start()
        self.addCleanup(which.stop)
        self.runner = FakeRunner()
        self.adapter = BeadsAdapter(make_workflow(), runner=self.runner)

    def fetch_by_identifier(self):
        return {issue.identifier: issue for issue in self.adapter.fetch_candidates()}

    # -- normalization ---------------------------------------------------

    def test_fixture_parse_produces_normalized_issues(self):
        issues = self.fetch_by_identifier()
        issue = issues["dap-test.1"]
        self.assertEqual(issue.key, "beads:dap-test.1")
        self.assertEqual(issue.identifier, "dap-test.1")
        self.assertEqual(issue.title, "Wire the dispatch dry run")
        self.assertEqual(issue.state, "open")
        self.assertEqual(issue.labels, ("backend",))
        self.assertEqual(issue.created_at, "2026-01-01T09:00:00Z")
        self.assertEqual(issue.updated_at, "2026-01-02T09:00:00Z")

    def test_list_fetch_argv_is_pinned_and_unwindowed(self):
        self.adapter.fetch_candidates()
        argv, kwargs = self.runner.calls[0]
        self.assertEqual(argv[0], "/fake/bin/bd")
        self.assertIn("list", argv)
        self.assertIn("--json", argv)
        self.assertIn("--all", argv)
        limit_index = argv.index("--limit")
        self.assertEqual(argv[limit_index + 1], "0")
        self.assertEqual(kwargs["cwd"], "/projects/dap-test")

    # -- blockers: embedded dependencies only ---------------------------

    def test_blockers_come_from_embedded_blocks_edges(self):
        issue = self.fetch_by_identifier()["dap-test.1"]
        self.assertEqual(len(issue.blockers), 2)
        by_key = {blocker.key: blocker for blocker in issue.blockers}
        closed = by_key["beads:dap-test.2"]
        self.assertEqual(closed.state, "closed")
        self.assertTrue(closed.is_terminal)
        open_blocker = by_key["beads:dap-test.3"]
        self.assertEqual(open_blocker.state, "open")
        self.assertFalse(open_blocker.is_terminal)
        # The parent-child edge to "dap-test" is not a blocker.
        self.assertNotIn("beads:dap-test", by_key)

    def test_record_without_dependencies_key_has_zero_blockers(self):
        issue = self.fetch_by_identifier()["dap-test.4"]
        self.assertEqual(issue.blockers, ())

    def test_closed_blocker_is_terminal_even_with_empty_terminal_states(self):
        adapter = BeadsAdapter(
            make_workflow(terminal_states=()), runner=FakeRunner()
        )
        by_id = {i.identifier: i for i in adapter.fetch_candidates()}
        blocker = by_id["dap-test.1"].blockers[0]
        self.assertEqual(blocker.key, "beads:dap-test.2")
        self.assertTrue(blocker.is_terminal)

    # -- priority / assignee ---------------------------------------------

    def test_priority_passthrough_and_missing_maps_to_none(self):
        issues = self.fetch_by_identifier()
        self.assertEqual(issues["dap-test.1"].priority, 1)
        self.assertEqual(issues["dap-test.3"].priority, 2)
        self.assertIsNone(issues["dap-test.4"].priority)

    def test_assignee_match_and_mismatch(self):
        issues = self.fetch_by_identifier()
        self.assertEqual(issues["dap-test.1"].assignee, "worker-a")
        self.assertTrue(issues["dap-test.1"].assigned_to_worker)
        self.assertEqual(issues["dap-test.3"].assignee, "someone-else")
        self.assertFalse(issues["dap-test.3"].assigned_to_worker)
        self.assertIsNone(issues["dap-test.4"].assignee)
        self.assertFalse(issues["dap-test.4"].assigned_to_worker)

    # -- author (controller ruling: no association rule on this track) --

    def test_author_from_created_by_and_author_ok(self):
        issues = self.fetch_by_identifier()
        self.assertEqual(issues["dap-test.1"].author, "reporter-1")
        self.assertTrue(issues["dap-test.1"].author_ok)
        self.assertIsNone(issues["dap-test.3"].author)
        self.assertTrue(issues["dap-test.3"].author_ok)

    # -- status_since -----------------------------------------------------

    def test_status_since_from_history_and_none_without(self):
        issues = self.fetch_by_identifier()
        # Latest history entry matching the current state wins.
        self.assertEqual(issues["dap-test.4"].status_since, "2026-01-04T09:00:00Z")
        self.assertIsNone(issues["dap-test.1"].status_since)

    # -- type filter + completeness --------------------------------------

    def test_type_filter_excludes_and_counts(self):
        issues = self.adapter.fetch_candidates()
        identifiers = {issue.identifier for issue in issues}
        self.assertNotIn("dap-test.5", identifiers)  # decision
        self.assertNotIn("dap-test.6", identifiers)  # epic
        self.assertEqual(self.adapter.last_fetch_count, 6)
        self.assertEqual(self.adapter.last_type_excluded_count, 2)

    def test_type_filter_includes_when_spec_names_types(self):
        adapter = BeadsAdapter(
            make_workflow(issue_types=("task", "bug", "decision", "epic")),
            runner=FakeRunner(),
        )
        identifiers = {issue.identifier for issue in adapter.fetch_candidates()}
        self.assertIn("dap-test.5", identifiers)
        self.assertIn("dap-test.6", identifiers)
        self.assertEqual(adapter.last_type_excluded_count, 0)

    def test_fetch_ceiling_exceeded(self):
        adapter = BeadsAdapter(
            make_workflow(max_candidates=2), runner=FakeRunner()
        )
        with self.assertRaises(FetchCeilingExceeded):
            adapter.fetch_candidates()

    # -- by-ids: the native id is the human form here ---------------------

    def test_fetch_by_ids_returns_record_for_human_id(self):
        issues = self.adapter.fetch_by_ids(["dap-test.1"])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].identifier, "dap-test.1")
        self.assertEqual(issues[0].key, "beads:dap-test.1")
        show_calls = [argv for argv, _ in self.runner.calls if "show" in argv]
        self.assertEqual(len(show_calls), 1)
        self.assertIn("dap-test.1", show_calls[0])
        self.assertIn("--json", show_calls[0])
        # Blocker states resolve against the same fetch, not the show stub.
        by_key = {b.key: b for b in issues[0].blockers}
        self.assertTrue(by_key["beads:dap-test.2"].is_terminal)
        self.assertFalse(by_key["beads:dap-test.3"].is_terminal)

    def test_fetch_by_ids_omits_missing_id_and_returns_present(self):
        # The Protocol pins absence semantics: fetch_by_ids returns the
        # requested issues that are present. A missing id (bd show's
        # not-found signal) is omitted; the present id is still served.
        runner = PerIdShowRunner(missing_ids={"dap-missing"})
        adapter = BeadsAdapter(make_workflow(), runner=runner)
        issues = adapter.fetch_by_ids(["dap-test.1", "dap-missing"])
        self.assertEqual([issue.identifier for issue in issues], ["dap-test.1"])

    def test_fetch_by_ids_other_show_failure_still_raises(self):
        # Only the not-found signal omits. Any other bd show failure
        # (here: a locked database) stays a loud BeadsError.
        runner = PerIdShowRunner(broken_ids={"dap-test.1"})
        adapter = BeadsAdapter(make_workflow(), runner=runner)
        with self.assertRaises(BeadsError) as ctx:
            adapter.fetch_by_ids(["dap-test.1"])
        self.assertIn("database is locked", str(ctx.exception))

    # -- states -------------------------------------------------------------

    def test_fetch_states_omits_missing_keys(self):
        states = self.adapter.fetch_states(
            ["beads:dap-test.1", "beads:dap-test.2", "beads:dap-nope"]
        )
        self.assertEqual(
            states, {"beads:dap-test.1": "open", "beads:dap-test.2": "closed"}
        )

    # -- loud failures ------------------------------------------------------

    def test_missing_bd_is_a_loud_failure(self):
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(BeadsError) as ctx:
                self.adapter.fetch_candidates()
        message = str(ctx.exception)
        self.assertIn("login shell", message)
        self.assertIn("~/go/bin", message)

    def test_nonzero_bd_exit_is_a_loud_failure(self):
        adapter = BeadsAdapter(
            make_workflow(), runner=FakeRunner(returncode=1, stderr="db locked")
        )
        with self.assertRaises(BeadsError) as ctx:
            adapter.fetch_candidates()
        self.assertIn("db locked", str(ctx.exception))

    # -- read-only surface ---------------------------------------------------

    def test_writes_raise_read_only(self):
        with self.assertRaises(NotImplementedError) as ctx:
            self.adapter.comment("beads:dap-test.1", "hello")
        self.assertEqual(str(ctx.exception), "read-only in Stage 1")
        with self.assertRaises(NotImplementedError) as ctx:
            self.adapter.transition("beads:dap-test.1", "closed")
        self.assertEqual(str(ctx.exception), "read-only in Stage 1")


if __name__ == "__main__":
    unittest.main()
