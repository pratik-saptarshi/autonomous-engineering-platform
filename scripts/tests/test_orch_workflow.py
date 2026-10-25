import dataclasses
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orch.workflow import FIELD_CONSUMERS, Workflow, WorkflowError, load_workflow


def fake_remote(url=None, branch="main"):
    return lambda root: (url, branch)


FULL_SPEC = """---
project_root: /tmp/orch-proj
project_slug: orch-proj
tracker: github
repo: octo/orch-proj
managed_by: orchestrator
assignee: pratik
author_association: member
active_states: [open, in_progress]
terminal_states: [closed, done]
done_state: done
transition_on_success: true
poll_seconds: 120
max_calls_per_poll: 4
github_fetch_limit: 250
max_candidates: 5000
cap_global: 3
cap_per_state:
  open: 2
  in_progress: 1
priority_labels: [priority:urgent=0, priority:high=1]
issue_types: [task, bug]
run_deadline_s: 1800
stall_s: 120
cancel_grace_s: 15
hook_timeout_s: 45
backoff_base_s: 5
backoff_cap_s: 240.5
max_infra_attempts: 3
hooks:
  after_create: ./hooks/setup.sh
  before_run: $ORCH_HOOK_CMD
  after_run: null
agent_command: [agent, run, --fast]
agent_result_file: /tmp/orch-proj/result.json
agent_heartbeat_file: /tmp/orch-proj/hb
base_ref: develop
workspace_on_terminal: release-clean
workspace_max_age_h: 12
allow_repo_remote_mismatch: false
---
Body line 1.
Body line 2.
"""

MINIMAL_SPEC = """---
project_root: /tmp/orch-proj
project_slug: orch-proj
tracker: beads
assignee: pratik
active_states: [open]
terminal_states: [closed]
---
Template body.
"""


class WorkflowLoadCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def load(self, text, remote_of=None):
        path = self.dir / "workflow.md"
        path.write_text(text, encoding="utf-8")
        if remote_of is None:
            remote_of = fake_remote()
        return load_workflow(str(path), remote_of=remote_of)

    def load_error(self, text, remote_of=None):
        with self.assertRaises(WorkflowError) as ctx:
            self.load(text, remote_of=remote_of)
        return str(ctx.exception)


class TestFullSpec(WorkflowLoadCase):
    def test_every_field_lands_typed(self):
        wf = self.load(FULL_SPEC, remote_of=fake_remote(url="https://github.com/octo/orch-proj.git"))
        self.assertEqual(wf.project_root, os.path.realpath("/tmp/orch-proj"))
        self.assertEqual(wf.project_slug, "orch-proj")
        self.assertEqual(wf.tracker, "github")
        self.assertEqual(wf.repo, "octo/orch-proj")
        self.assertEqual(wf.managed_by, "orchestrator")
        self.assertEqual(wf.assignee, "pratik")
        self.assertEqual(wf.author_association, "member")
        self.assertEqual(wf.active_states, ("open", "in_progress"))
        self.assertEqual(wf.terminal_states, ("closed", "done"))
        self.assertEqual(wf.done_state, "done")
        self.assertIs(wf.transition_on_success, True)
        self.assertEqual(wf.poll_seconds, 120)
        self.assertEqual(wf.max_calls_per_poll, 4)
        self.assertEqual(wf.github_fetch_limit, 250)
        self.assertEqual(wf.max_candidates, 5000)
        self.assertEqual(wf.cap_global, 3)
        self.assertEqual(wf.cap_per_state, {"open": 2, "in_progress": 1})
        self.assertEqual(wf.priority_labels, {"priority:urgent": 0, "priority:high": 1})
        self.assertEqual(wf.issue_types, ("task", "bug"))
        self.assertEqual(wf.run_deadline_s, 1800)
        self.assertEqual(wf.stall_s, 120)
        self.assertEqual(wf.cancel_grace_s, 15)
        self.assertEqual(wf.hook_timeout_s, 45)
        self.assertEqual(wf.backoff_base_s, 5.0)
        self.assertIsInstance(wf.backoff_base_s, float)
        self.assertEqual(wf.backoff_cap_s, 240.5)
        self.assertEqual(wf.max_infra_attempts, 3)
        self.assertEqual(
            wf.hooks,
            {
                "after_create": "./hooks/setup.sh",
                "before_run": "$ORCH_HOOK_CMD",
                "after_run": None,
                "before_remove": None,
            },
        )
        self.assertEqual(wf.agent_command, ("agent", "run", "--fast"))
        self.assertEqual(wf.agent_result_file, "/tmp/orch-proj/result.json")
        self.assertEqual(wf.agent_heartbeat_file, "/tmp/orch-proj/hb")
        self.assertEqual(wf.base_ref, "develop")
        self.assertEqual(wf.workspace_on_terminal, "release-clean")
        self.assertEqual(wf.workspace_max_age_h, 12.0)
        self.assertIsInstance(wf.workspace_max_age_h, float)
        self.assertIs(wf.allow_repo_remote_mismatch, False)
        self.assertEqual(wf.prompt_template, "Body line 1.\nBody line 2.\n")

    def test_workflow_is_frozen(self):
        wf = self.load(MINIMAL_SPEC)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            wf.assignee = "someone-else"


class TestDefaults(WorkflowLoadCase):
    def test_defaults_applied_for_omitted_fields(self):
        wf = self.load(MINIMAL_SPEC)
        self.assertIsNone(wf.repo)
        self.assertIsNone(wf.managed_by)
        self.assertEqual(wf.author_association, "owner")
        self.assertIsNone(wf.done_state)
        self.assertIs(wf.transition_on_success, False)
        self.assertEqual(wf.poll_seconds, 300)
        self.assertEqual(wf.max_calls_per_poll, 6)
        self.assertEqual(wf.github_fetch_limit, 500)
        self.assertEqual(wf.max_candidates, 10000)
        self.assertIsNone(wf.cap_global)
        self.assertEqual(wf.cap_per_state, {})
        self.assertEqual(wf.priority_labels, {})
        self.assertEqual(wf.issue_types, ("task", "bug", "story", "spike", "chore"))
        self.assertEqual(wf.run_deadline_s, 3600)
        self.assertEqual(wf.stall_s, 300)
        self.assertEqual(wf.cancel_grace_s, 30)
        self.assertEqual(wf.hook_timeout_s, 60)
        self.assertEqual(wf.backoff_base_s, 10.0)
        self.assertIsInstance(wf.backoff_base_s, float)
        self.assertEqual(wf.backoff_cap_s, 300.0)
        self.assertEqual(wf.max_infra_attempts, 5)
        self.assertEqual(
            wf.hooks,
            {"after_create": None, "before_run": None, "after_run": None, "before_remove": None},
        )
        self.assertEqual(wf.agent_command, ())
        self.assertIsNone(wf.agent_result_file)
        self.assertIsNone(wf.agent_heartbeat_file)
        self.assertEqual(wf.base_ref, "main")
        self.assertEqual(wf.workspace_on_terminal, "keep")
        self.assertEqual(wf.workspace_max_age_h, 0.0)
        self.assertIs(wf.allow_repo_remote_mismatch, False)
        self.assertEqual(wf.prompt_template, "Template body.\n")


class TestCensus(WorkflowLoadCase):
    def test_field_consumers_matches_dataclass_fields_both_directions(self):
        field_names = {f.name for f in dataclasses.fields(Workflow)}
        self.assertEqual(set(FIELD_CONSUMERS), field_names)
        for consumer in FIELD_CONSUMERS.values():
            self.assertIsInstance(consumer, str)
            self.assertTrue(consumer)


class TestEnvResolution(WorkflowLoadCase):
    def test_env_reference_resolves_for_plain_field(self):
        spec = MINIMAL_SPEC.replace("assignee: pratik", "assignee: $ORCH_TEST_USER")
        with mock.patch.dict(os.environ, {"ORCH_TEST_USER": "carol"}):
            wf = self.load(spec)
        self.assertEqual(wf.assignee, "carol")

    def test_unset_env_variable_is_load_error_naming_the_variable(self):
        spec = MINIMAL_SPEC.replace("assignee: pratik", "assignee: $ORCH_DEFINITELY_UNSET_XYZ")
        env = {k: v for k, v in os.environ.items() if k != "ORCH_DEFINITELY_UNSET_XYZ"}
        with mock.patch.dict(os.environ, env, clear=True):
            msg = self.load_error(spec)
        self.assertIn("ORCH_DEFINITELY_UNSET_XYZ", msg)

    def test_env_token_embedded_in_longer_string_stays_literal(self):
        spec = MINIMAL_SPEC.replace("assignee: pratik", "assignee: pre-$ORCH_TEST_USER")
        with mock.patch.dict(os.environ, {"ORCH_TEST_USER": "carol"}):
            wf = self.load(spec)
        self.assertEqual(wf.assignee, "pre-$ORCH_TEST_USER")

    def test_hook_command_matching_env_token_is_not_resolved(self):
        spec = MINIMAL_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\nhooks:\n  before_run: $ORCH_UNSET_HOOK_CMD",
        )
        env = {k: v for k, v in os.environ.items() if k != "ORCH_UNSET_HOOK_CMD"}
        with mock.patch.dict(os.environ, env, clear=True):
            wf = self.load(spec)
        self.assertEqual(wf.hooks["before_run"], "$ORCH_UNSET_HOOK_CMD")

    def test_agent_command_entry_matching_env_token_is_not_resolved(self):
        spec = MINIMAL_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\nagent_command: [$ORCH_UNSET_AGENT, run]",
        )
        env = {k: v for k, v in os.environ.items() if k != "ORCH_UNSET_AGENT"}
        with mock.patch.dict(os.environ, env, clear=True):
            wf = self.load(spec)
        self.assertEqual(wf.agent_command, ("$ORCH_UNSET_AGENT", "run"))

    def test_tilde_expansion_on_plain_value(self):
        spec = MINIMAL_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\nagent_result_file: ~/orch-result.json",
        )
        wf = self.load(spec)
        self.assertEqual(wf.agent_result_file, os.path.expanduser("~/orch-result.json"))
        self.assertTrue(os.path.isabs(wf.agent_result_file))

    def test_tilde_expansion_on_resolved_env_value(self):
        spec = MINIMAL_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\nagent_result_file: $ORCH_RESULT_HOME",
        )
        with mock.patch.dict(os.environ, {"ORCH_RESULT_HOME": "~/orch-home/result.json"}):
            wf = self.load(spec)
        self.assertEqual(wf.agent_result_file, os.path.expanduser("~/orch-home/result.json"))


class TestGrammar(WorkflowLoadCase):
    def test_tab_indentation_is_load_error_naming_the_line(self):
        spec = MINIMAL_SPEC.replace("assignee: pratik", "\tassignee: pratik")
        msg = self.load_error(spec)
        self.assertIn("line 5", msg)

    def test_three_level_nesting_is_load_error_naming_the_line(self):
        spec = MINIMAL_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\nhooks:\n  after_create:\n      cmd: ./x.sh",
        )
        msg = self.load_error(spec)
        self.assertIn("line 10", msg)

    def test_unclosed_list_is_load_error_naming_the_line(self):
        spec = MINIMAL_SPEC.replace("active_states: [open]", "active_states: [open")
        msg = self.load_error(spec)
        self.assertIn("line 6", msg)

    def test_colon_in_key_is_load_error_naming_the_line(self):
        spec = MINIMAL_SPEC.replace("assignee: pratik", "priority:urgent: 0")
        msg = self.load_error(spec)
        self.assertIn("line 5", msg)

    def test_duplicate_key_is_load_error_naming_the_line(self):
        spec = MINIMAL_SPEC.replace(
            "assignee: pratik", "assignee: pratik\nassignee: other"
        )
        msg = self.load_error(spec)
        self.assertIn("line 6", msg)

    def test_missing_opening_delimiter_is_load_error(self):
        msg = self.load_error("project_root: /tmp/x\n---\nbody\n")
        self.assertIn("line 1", msg)

    def test_missing_closing_delimiter_is_load_error(self):
        msg = self.load_error("---\nproject_root: /tmp/x\n")
        self.assertIn("closing", msg)

    def test_comments_parse_away_cleanly(self):
        spec = (
            "---\n"
            "# a full-line comment\n"
            "project_root: /tmp/orch-proj  # trailing comment\n"
            "project_slug: orch-proj\n"
            "tracker: beads # tracker comment\n"
            "  # an indented comment line\n"
            "assignee: pratik\n"
            "active_states: [open] # states comment\n"
            "terminal_states: [closed]\n"
            "---\n"
            "Body.\n"
        )
        wf = self.load(spec)
        self.assertEqual(wf.project_root, os.path.realpath("/tmp/orch-proj"))
        self.assertEqual(wf.tracker, "beads")
        self.assertEqual(wf.active_states, ("open",))
        self.assertEqual(wf.prompt_template, "Body.\n")


class TestValidation(WorkflowLoadCase):
    def test_missing_assignee_fails_to_load(self):
        spec = MINIMAL_SPEC.replace("assignee: pratik\n", "")
        msg = self.load_error(spec)
        self.assertIn("assignee", msg)

    def test_transition_on_success_without_done_state_fails(self):
        spec = MINIMAL_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\ntransition_on_success: true",
        )
        msg = self.load_error(spec)
        self.assertIn("done_state", msg)

    def test_transition_on_success_with_done_state_loads(self):
        spec = MINIMAL_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\ndone_state: closed\ntransition_on_success: true",
        )
        wf = self.load(spec)
        self.assertIs(wf.transition_on_success, True)
        self.assertEqual(wf.done_state, "closed")

    def test_unknown_tracker_fails(self):
        spec = MINIMAL_SPEC.replace("tracker: beads", "tracker: jira")
        msg = self.load_error(spec)
        self.assertIn("tracker", msg)

    def test_wrong_scalar_type_fails(self):
        spec = MINIMAL_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\npoll_seconds: soon",
        )
        msg = self.load_error(spec)
        self.assertIn("poll_seconds", msg)

    def test_unknown_key_warns_on_stderr_and_loads(self):
        spec = MINIMAL_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\nbogus_key: $ORCH_UNSET_UNKNOWN_KEY",
        )
        path = self.dir / "workflow.md"
        path.write_text(spec, encoding="utf-8")
        err = io.StringIO()
        with redirect_stderr(err):
            wf = load_workflow(str(path), remote_of=fake_remote())
        self.assertIn("bogus_key", err.getvalue())
        self.assertEqual(wf.assignee, "pratik")

    def test_cap_per_state_list_form(self):
        spec = MINIMAL_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\ncap_per_state: [open=2, blocked=1]",
        )
        wf = self.load(spec)
        self.assertEqual(wf.cap_per_state, {"open": 2, "blocked": 1})


class TestRemoteCrossCheck(WorkflowLoadCase):
    GITHUB_SPEC = MINIMAL_SPEC.replace("tracker: beads", "tracker: github\nrepo: octo/orch-proj")

    def test_repo_remote_match_loads_https_and_ssh_forms(self):
        for url in ("https://github.com/octo/orch-proj.git", "git@github.com:octo/orch-proj.git"):
            wf = self.load(self.GITHUB_SPEC, remote_of=fake_remote(url=url))
            self.assertEqual(wf.repo, "octo/orch-proj")

    def test_repo_remote_mismatch_is_load_error(self):
        msg = self.load_error(
            self.GITHUB_SPEC, remote_of=fake_remote(url="https://github.com/octo/other.git")
        )
        self.assertIn("does not match", msg)

    def test_repo_remote_mismatch_loads_when_explicitly_allowed(self):
        spec = self.GITHUB_SPEC.replace(
            "terminal_states: [closed]",
            "terminal_states: [closed]\nallow_repo_remote_mismatch: true",
        )
        wf = self.load(spec, remote_of=fake_remote(url="https://github.com/octo/other.git"))
        self.assertEqual(wf.repo, "octo/orch-proj")

    def test_github_spec_without_repo_fails(self):
        spec = MINIMAL_SPEC.replace("tracker: beads", "tracker: github")
        msg = self.load_error(spec, remote_of=fake_remote(url="https://github.com/octo/x.git"))
        self.assertIn("repo", msg)


class TestBaseRef(WorkflowLoadCase):
    def test_base_ref_resolves_from_injected_seam(self):
        wf = self.load(MINIMAL_SPEC, remote_of=fake_remote(branch="trunk"))
        self.assertEqual(wf.base_ref, "trunk")

    def test_explicit_base_ref_wins_over_seam(self):
        wf = self.load(FULL_SPEC, remote_of=fake_remote(url="https://github.com/octo/orch-proj.git", branch="main"))
        self.assertEqual(wf.base_ref, "develop")

    def test_unresolvable_base_ref_is_load_error(self):
        msg = self.load_error(MINIMAL_SPEC, remote_of=fake_remote(branch=None))
        self.assertIn("default branch", msg)


if __name__ == "__main__":
    unittest.main()
