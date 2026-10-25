import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orch.adapters_github import (
    BudgetDenied,
    BudgetExceeded,
    GitHubAdapter,
    gated_argv,
)
from orch.engine import Reason, select
from orch.workflow import Workflow

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "orch"
MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "orch" / "adapters_github.py"
)


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_workflow(**overrides):
    values = {
        "project_root": "/projects/octo-test",
        "project_slug": "octo-test",
        "tracker": "github",
        "repo": "octo-org/octo-repo",
        "assignee": "worker-a",
        "active_states": ("open", "in-progress"),
        "terminal_states": ("closed",),
        "priority_labels": {
            "priority:urgent": 0,
            "priority:high": 1,
            "priority:low": 3,
        },
    }
    values.update(overrides)
    return Workflow(**values)


class FakeRunner:
    """Injectable runner stand-in serving the recorded gh payloads.

    Routes on the gated argv's gh arguments: ``api`` answers the @me
    lookup, ``view`` serves per-number payloads (unknown numbers fail
    the way gh fails them), ``list`` serves the candidate payload.
    ``returncode`` forces every call to that exit code (the budget
    denial test uses 75).
    """

    def __init__(self, returncode=0):
        self.calls = []  # list of (argv, kwargs)
        self._returncode = returncode
        self._list_payload = load_fixture("github-issues.json")
        self._view_payloads = {"42": load_fixture("github-issue-42.json")}

    def __call__(self, argv, **kwargs):
        argv = list(argv)
        self.calls.append((argv, kwargs))
        if self._returncode != 0:
            return SimpleNamespace(
                returncode=self._returncode, stdout="", stderr="denied"
            )
        if "api" in argv:
            return SimpleNamespace(returncode=0, stdout="worker-a\n", stderr="")
        if "view" in argv:
            number = argv[argv.index("view") + 1]
            payload = self._view_payloads.get(number)
            if payload is None:
                return SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr=(
                        "Could not resolve to an issue or pull request "
                        f"with the number of {number}."
                    ),
                )
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr=""
            )
        if "list" in argv:
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(self._list_payload), stderr=""
            )
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")

    def calls_matching(self, token):
        return [argv for argv, _ in self.calls if token in argv]


class GatedArgvTests(unittest.TestCase):
    def test_helper_output_shape_exact(self):
        # The gateway executes gh itself; the parts are gh's arguments
        # with no leading "gh" element (controller ruling, Task 1.4).
        self.assertEqual(
            gated_argv(make_workflow(), "issue", "list"),
            ["ghg", "run", "--actor", "orch-octo-test", "--", "issue", "list"],
        )

    def test_subprocess_referenced_only_in_default_runner(self):
        lines = MODULE_PATH.read_text(encoding="utf-8").splitlines()
        referencing = [line for line in lines if "subprocess" in line]
        self.assertTrue(referencing, "module must define a default runner")
        for line in referencing:
            self.assertTrue(
                line.startswith("import subprocess")
                or "runner=subprocess.run" in line,
                f"unexpected subprocess reference: {line}",
            )

    def test_single_runner_call_site(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertEqual(source.count("self._runner("), 1)


class GitHubAdapterTests(unittest.TestCase):
    def setUp(self):
        self.runner = FakeRunner()
        self.adapter = GitHubAdapter(make_workflow(), runner=self.runner)

    def fetch_by_number(self):
        return {
            issue.identifier: issue for issue in self.adapter.fetch_candidates()
        }

    # -- fixture normalization ------------------------------------------

    def test_state_from_status_label_and_default_open(self):
        issues = self.fetch_by_number()
        self.assertEqual(issues["101"].state, "in-progress")
        self.assertEqual(issues["102"].state, "open")

    def test_priority_from_labels_and_none_without(self):
        issues = self.fetch_by_number()
        self.assertEqual(issues["101"].priority, 1)
        self.assertIsNone(issues["102"].priority)

    def test_priority_multiple_labels_lowest_wins(self):
        issues = self.fetch_by_number()
        self.assertEqual(issues["103"].priority, 0)

    def test_assigned_to_worker_from_assignee_logins(self):
        issues = self.fetch_by_number()
        self.assertTrue(issues["101"].assigned_to_worker)
        self.assertFalse(issues["103"].assigned_to_worker)

    def test_key_and_identifier_forms(self):
        issues = self.fetch_by_number()
        self.assertEqual(issues["101"].key, "github:101")
        self.assertEqual(issues["101"].identifier, "101")

    # -- author association ----------------------------------------------

    def test_author_association_owner_default(self):
        issues = self.fetch_by_number()
        self.assertEqual(issues["101"].author, "octo-org")
        self.assertTrue(issues["101"].author_ok)
        self.assertEqual(issues["102"].author, "external-dev")
        self.assertFalse(issues["102"].author_ok)
        # The operator's own login satisfies the rule via @me.
        self.assertTrue(issues["103"].author_ok)

    def test_author_association_any_lifts_the_condition(self):
        adapter = GitHubAdapter(
            make_workflow(author_association="any"), runner=FakeRunner()
        )
        issues = {i.identifier: i for i in adapter.fetch_candidates()}
        self.assertTrue(issues["102"].author_ok)

    # -- @me resolution ----------------------------------------------------

    def test_me_assignee_resolution_is_cached(self):
        runner = FakeRunner()
        adapter = GitHubAdapter(
            make_workflow(assignee="@me"), runner=runner
        )
        first = {i.identifier: i for i in adapter.fetch_candidates()}
        self.assertTrue(first["101"].assigned_to_worker)
        adapter.fetch_candidates()
        self.assertEqual(len(runner.calls_matching("api")), 1)

    # -- by-ids: query by number, never by node id -------------------------

    def test_fetch_by_ids_queries_by_number(self):
        fixture = load_fixture("github-issue-42.json")
        self.assertNotEqual(fixture["id"], str(fixture["number"]))
        issues = self.adapter.fetch_by_ids(["github:42"])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].identifier, "42")
        self.assertEqual(issues[0].key, "github:42")
        self.assertEqual(issues[0].state, "closed")
        view_argv = self.runner.calls_matching("view")[0]
        self.assertIn("42", view_argv)
        self.assertNotIn(fixture["id"], view_argv)

    def test_fetch_states_omits_missing_keys(self):
        states = self.adapter.fetch_states(["github:42", "github:999"])
        self.assertEqual(states, {"github:42": "closed"})

    # -- blockers ------------------------------------------------------------

    def test_blocker_resolved_via_by_ids_with_terminal_state(self):
        issues = self.fetch_by_number()
        blockers = issues["103"].blockers
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0].key, "github:42")
        self.assertEqual(blockers[0].state, "closed")
        self.assertTrue(blockers[0].is_terminal)
        self.assertEqual(issues["101"].blockers, ())

    # -- budget outcomes ------------------------------------------------------

    def test_call_cap_raises_before_the_extra_call_executes(self):
        runner = FakeRunner()
        adapter = GitHubAdapter(
            make_workflow(max_calls_per_poll=1), runner=runner
        )
        with self.assertRaises(BudgetExceeded):
            adapter.fetch_candidates()
        self.assertEqual(len(runner.calls), 1)

    def test_exit_75_raises_budget_denied(self):
        adapter = GitHubAdapter(make_workflow(), runner=FakeRunner(75))
        with self.assertRaises(BudgetDenied):
            adapter.fetch_candidates()

    # -- truncation --------------------------------------------------------------

    def test_truncation_flag_set_at_exactly_the_limit(self):
        adapter = GitHubAdapter(
            make_workflow(github_fetch_limit=3), runner=FakeRunner()
        )
        adapter.fetch_candidates()
        self.assertTrue(adapter.last_truncated)

    def test_truncation_flag_clear_below_the_limit(self):
        self.adapter.fetch_candidates()
        self.assertFalse(self.adapter.last_truncated)

    # -- points accounting ---------------------------------------------------------

    def test_points_seam_sum_returned_verbatim(self):
        adapter = GitHubAdapter(
            make_workflow(), runner=FakeRunner(), points_of=lambda: 7
        )
        self.assertEqual(adapter.points_spent(), 7)

    def test_points_unavailable_ledger_is_none_never_estimated(self):
        adapter = GitHubAdapter(
            make_workflow(), runner=FakeRunner(), points_of=lambda: None
        )
        self.assertIsNone(adapter.points_spent())

    def test_points_default_reads_the_ledger_for_the_orch_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Construct the adapter BEFORE seeding: its poll window
            # opens at construction, so rows stamped afterwards can
            # never fall before the window on a second boundary.
            adapter = GitHubAdapter(make_workflow(), runner=FakeRunner())
            db = Path(tmp) / "ghg.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE calls (id INTEGER PRIMARY KEY, ts INTEGER"
                " NOT NULL, actor TEXT NOT NULL, bucket TEXT NOT NULL,"
                " cost INTEGER NOT NULL, argv TEXT NOT NULL, outcome TEXT)"
            )
            now = int(time.time())
            rows = [
                (now, "orch-octo-test", "graphql", 3, "issue list", "ok"),
                (now, "orch-octo-test", "core", 4, "issue view", "error"),
                # A reservation is not a finalized charge.
                (now, "orch-octo-test", "core", 100, "issue list", "reserved"),
                # Another actor's charges are not this poll's.
                (now, "someone-else", "core", 50, "issue list", "ok"),
            ]
            conn.executemany(
                "INSERT INTO calls (ts, actor, bucket, cost, argv, outcome)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
            conn.close()
            with mock.patch.dict("os.environ", {"GHG_STATE_DIR": tmp}):
                self.assertEqual(adapter.points_spent(), 7)

    def test_points_default_missing_ledger_is_none(self):
        adapter = GitHubAdapter(make_workflow(), runner=FakeRunner())
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {"GHG_STATE_DIR": tmp}):
                self.assertIsNone(adapter.points_spent())

    # -- writes stay off in Stage 1 ------------------------------------------------

    def test_writes_raise_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.adapter.comment("github:101", "hello")
        with self.assertRaises(NotImplementedError):
            self.adapter.transition("github:101", "closed")


class _StubClaimView:
    def claimed_lanes(self):
        return set()

    def running_by_state(self):
        return {}


class GitHubTerminalityTests(unittest.TestCase):
    """Panel A1: a closed blocker blocks iff the spec declares it.

    Issue 103 is blocked only by the closed issue 42 (via its
    blocked-by:42 label), so its fate is decided entirely by whose
    terminal vocabulary governs. It is assigned to someone-else.
    """

    def run_selection(self, **overrides):
        workflow = make_workflow(**overrides)
        adapter = GitHubAdapter(workflow, runner=FakeRunner())
        candidates = adapter.fetch_candidates()
        return select(candidates, workflow, _StubClaimView(), set())

    def test_closed_blocker_not_terminal_when_spec_omits_closed(self):
        adapter = GitHubAdapter(
            make_workflow(terminal_states=("done",)), runner=FakeRunner()
        )
        issues = {i.identifier: i for i in adapter.fetch_candidates()}
        blocker = issues["103"].blockers[0]
        self.assertEqual(blocker.key, "github:42")
        self.assertEqual(blocker.state, "closed")
        self.assertFalse(blocker.is_terminal)

    def test_closed_blocker_blocks_when_spec_omits_closed(self):
        result = self.run_selection(
            terminal_states=("done",), assignee="someone-else"
        )
        self.assertNotIn("103", [i.identifier for i in result.dispatch])
        self.assertEqual(result.rejections["103"][0], Reason.BLOCKED)

    def test_closed_blocker_does_not_block_when_spec_declares_closed(self):
        result = self.run_selection(
            terminal_states=("closed",), assignee="someone-else"
        )
        self.assertIn("103", [i.identifier for i in result.dispatch])


if __name__ == "__main__":
    unittest.main()
