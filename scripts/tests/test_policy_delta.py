"""Tests for scripts/check_policy_delta.py (OpenShell-patterns Phase 1).

unittest.TestCase style only: CI runs
``python3 -m unittest discover -s scripts/tests``.

The unit classes build synthetic git repositories in temp dirs and drive
the checker CLI via subprocess, exactly as CI would. Three further
classes carry the Phase 0 gate evidence forward as regression tests:

- SeedEscalationTests: the three seeded escalations of gate G-P2
  (docs/plans/openshell-patterns-phase0/g-p2/findings.md), rebuilt
  synthetically so they cannot rot with the live artefacts.
- ReplayCorpusTests: the production differ re-run over the 20 merged
  PRs of the G-P2 replay corpus must reproduce the recorded counts
  exactly. Skipped when the historical commits are not in the local
  object store (CI checkouts are shallow).
- Pr58ExecutableSurfaceTests: PR #58's missed delta -- the differ must
  flag the executable surface (a runnable server, start/stop hooks)
  that the PR's human record never mentioned.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SCRIPT = REPO_ROOT / "scripts" / "check_policy_delta.py"
REPLAY_SUMMARY = (REPO_ROOT / "docs" / "plans" /
                  "openshell-patterns-phase0" / "g-p2" / "replay" /
                  "summary.json")

POLICY_DATA = """\
[sensitive-paths]
*/.ssh
*/.config/gcloud
*/.config/gcloud/*
[env-scrub]
SECRET_*
"""

GHG_PY = """\
DEFAULT_LIMITS = {
    "core": [(3600, 3500)],
    "search": [(60, 20)],
}
_MUTATING_SUBCOMMANDS = {"create", "comment", "merge", "edit"}
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
"""


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip()


class SyntheticRepo(unittest.TestCase):
    """Base: a temp git repo holding the four modelled artefacts."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        git(self.repo, "init", "-q", "-b", "main", ".")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        self.write("scripts/policy.data", POLICY_DATA)
        self.write("tools/ghg/ghg.py", GHG_PY)
        self.write(".github/skills-sync-scope.txt", "alpha\nbeta\n")
        self.write("skills/alpha/SKILL.md", "# Alpha\n")
        self.write("skills/alpha/scripts/run.sh", "echo old\n")
        self.write("skills/beta/SKILL.md", "# Beta\n")
        self.base = self.commit("base")

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", msg)
        return git(self.repo, "rev-parse", "HEAD")

    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, str(REAL_SCRIPT), "--repo", str(self.repo),
             *args],
            capture_output=True, text=True)

    def diff(self, base, head, *extra):
        r = self.run_tool("diff", base, head, *extra)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        return r, json.loads(r.stdout) if r.stdout else None


class CoreDeltaTests(SyntheticRepo):
    def test_deny_pattern_removal_is_newly_allowed(self):
        self.write("scripts/policy.data",
                   POLICY_DATA.replace("*/.config/gcloud\n", ""))
        head = self.commit("head")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("gcloud" in x for x in d["newly_allowed"]))
        self.assertEqual(d["newly_denied"], [])

    def test_deny_pattern_addition_is_newly_denied(self):
        self.write("scripts/policy.data",
                   POLICY_DATA.replace("*/.ssh\n", "*/.ssh\n*/.vault\n"))
        head = self.commit("head")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(any(".vault" in x for x in d["newly_denied"]))
        self.assertEqual(d["newly_allowed"], [])

    def test_cap_increase_and_decrease(self):
        self.write("tools/ghg/ghg.py", GHG_PY.replace(
            '"search": [(60, 20)]', '"search": [(60, 30)]'))
        head = self.commit("up")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("search" in x and "30" in x
                            for x in d["newly_allowed"]))
        self.write("tools/ghg/ghg.py", GHG_PY.replace(
            '"search": [(60, 20)]', '"search": [(60, 5)]'))
        head2 = self.commit("down")
        _, d2 = self.diff(head, head2)
        self.assertTrue(any("search" in x for x in d2["newly_denied"]))

    def test_new_bucket_is_newly_allowed_call_class(self):
        self.write("tools/ghg/ghg.py", GHG_PY.replace(
            '"search": [(60, 20)],',
            '"search": [(60, 20)],\n    "metadata_creds": [(60, 30)],'))
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("metadata_creds" in x
                            for x in d["newly_allowed"]))

    def test_mutating_removal_escapes_classification(self):
        self.write("tools/ghg/ghg.py", GHG_PY.replace(
            '"create", "comment", "merge", "edit"',
            '"create", "comment", "edit"'))
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("'merge'" in x and "mutating" in x
                            for x in d["newly_allowed"]))

    def test_unmodelled_ghg_change_is_a_note_not_silence(self):
        self.write("tools/ghg/ghg.py", GHG_PY + "\n# a comment\n")
        head = self.commit("head")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(d["newly_allowed"], [])
        self.assertTrue(any("modelled power" in n for n in d["notes"]))

    def test_scope_entry_and_exit(self):
        self.write(".github/skills-sync-scope.txt", "alpha\ngamma\n")
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("gamma" in x for x in d["newly_allowed"]))
        self.assertTrue(any("beta" in x for x in d["newly_denied"]))

    def test_empty_diff_exits_zero(self):
        r, d = self.diff(self.base, self.base)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(d["newly_allowed"], [])
        self.assertEqual(d["newly_denied"], [])

    def test_refs_resolved_to_full_shas(self):
        _, d = self.diff("main", "main")
        self.assertEqual(len(d["base"]), 40)
        self.assertEqual(d["base"], d["head"])

    def test_unknown_ref_is_error_exit_2(self):
        r = self.run_tool("diff", "deadbeef", self.base)
        self.assertEqual(r.returncode, 2)

    def test_unparsable_ghg_is_error_exit_2(self):
        self.write("tools/ghg/ghg.py", GHG_PY + "DEFAULT_LIMITS = {\n")
        head = self.commit("broken")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2)
        self.assertIn("ghg", r.stderr)

    def test_ghg_missing_modelled_name_is_error_exit_2(self):
        self.write("tools/ghg/ghg.py",
                   GHG_PY.replace('_MUTATING_METHODS = {"POST", "PUT", '
                                  '"PATCH", "DELETE"}\n', ""))
        head = self.commit("renamed")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2)
        self.assertIn("_MUTATING_METHODS", r.stderr)

    def test_policy_data_pattern_outside_section_is_error(self):
        self.write("scripts/policy.data", "orphan-pattern\n" + POLICY_DATA)
        head = self.commit("bad")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2)

    def test_artefact_creation_is_a_note_not_a_delta(self):
        git(self.repo, "rm", "-q", "scripts/policy.data")
        gone = self.commit("gone")
        self.write("scripts/policy.data", POLICY_DATA)
        back = self.commit("back")
        _, d = self.diff(gone, back)
        self.assertTrue(any("created" in n for n in d["notes"]))
        self.assertEqual(d["newly_allowed"], [])


class SkillsTierTests(SyntheticRepo):
    def test_new_skill_is_newly_allowed(self):
        self.write("skills/delta/SKILL.md", "# Delta\n")
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("'delta'" in x for x in d["newly_allowed"]))

    def test_removed_skill_is_newly_denied(self):
        git(self.repo, "rm", "-q", "-r", "skills/beta")
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("'beta'" in x for x in d["newly_denied"]))

    def test_added_server_script_is_executable_surface(self):
        self.write("skills/alpha/scripts/server.cjs", "require('http')\n")
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("server.cjs" in x
                            for x in d["newly_allowed_executable"]))

    def test_added_start_stop_hooks_are_executable_surface(self):
        self.write("skills/alpha/scripts/start-server.sh", "#!/bin/sh\n")
        self.write("skills/alpha/scripts/stop-server.sh", "#!/bin/sh\n")
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        ex = d["newly_allowed_executable"]
        self.assertTrue(any("start-server.sh" in x for x in ex))
        self.assertTrue(any("stop-server.sh" in x for x in ex))

    def test_added_doc_is_surface_but_not_executable(self):
        self.write("skills/alpha/notes.md", "notes\n")
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("notes.md" in x for x in d["newly_allowed"]))
        self.assertFalse(any("notes.md" in x
                             for x in d["newly_allowed_executable"]))

    def test_new_skill_with_code_is_flagged_executable(self):
        self.write("skills/delta/SKILL.md", "# Delta\n")
        self.write("skills/delta/tool.py", "print(1)\n")
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("'delta'" in x
                            for x in d["newly_allowed_executable"]))

    def test_executable_bit_alone_is_executable_surface(self):
        p = self.repo / "skills/alpha/helper"
        p.write_text("#!/bin/sh\n")
        p.chmod(0o755)
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("helper" in x
                            for x in d["newly_allowed_executable"]))

    def test_removed_file_is_contraction(self):
        git(self.repo, "rm", "-q", "skills/alpha/scripts/run.sh")
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("run.sh" in x for x in d["newly_denied"]))

    def test_skillmd_content_change_is_a_note(self):
        self.write("skills/alpha/SKILL.md", "# Alpha v2\n")
        head = self.commit("head")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(any("SKILL.md" in n for n in d["notes"]))


class ReportAndAckTests(SyntheticRepo):
    def escalate(self):
        self.write("scripts/policy.data",
                   POLICY_DATA.replace("*/.config/gcloud\n", ""))
        return self.commit("head")

    def test_output_is_deterministic(self):
        head = self.escalate()
        r1 = self.run_tool("diff", self.base, head)
        r2 = self.run_tool("diff", self.base, head)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_markdown_report_shape(self):
        head = self.escalate()
        r = self.run_tool("diff", self.base, head, "--format", "markdown")
        self.assertIn("### Newly allowed", r.stdout)
        self.assertIn("gcloud", r.stdout)
        self.assertIn("does not cover", r.stdout)
        self.assertIn("policy-delta-sha256:", r.stdout)

    def fingerprint(self, head):
        r = self.run_tool("diff", self.base, head, "--format", "markdown")
        for line in r.stdout.splitlines():
            if "policy-delta-sha256:" in line:
                return line.split("policy-delta-sha256:")[1].strip()
        self.fail("no fingerprint in markdown report")

    def test_check_fails_closed_without_ack(self):
        head = self.escalate()
        body = self.repo / "body.txt"
        body.write_text("## Summary\n\nRoutine.\n")
        r = self.run_tool("check", self.base, head,
                          "--body-file", str(body))
        self.assertEqual(r.returncode, 1)
        self.assertIn("policy-delta-sha256:", r.stderr)

    def test_check_passes_with_matching_ack(self):
        head = self.escalate()
        body = self.repo / "body.txt"
        body.write_text(f"policy-delta-sha256: {self.fingerprint(head)}\n")
        r = self.run_tool("check", self.base, head,
                          "--body-file", str(body))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_check_rejects_stale_ack_after_new_commit(self):
        head = self.escalate()
        fp = self.fingerprint(head)
        self.write("skills/alpha/notes.md", "more\n")
        head2 = self.commit("more")
        body = self.repo / "body.txt"
        body.write_text(f"policy-delta-sha256: {fp}\n")
        r = self.run_tool("check", self.base, head2,
                          "--body-file", str(body))
        self.assertEqual(r.returncode, 1)

    def test_check_passes_trivially_on_empty_delta(self):
        body = self.repo / "body.txt"
        body.write_text("anything\n")
        r = self.run_tool("check", self.base, self.base,
                          "--body-file", str(body))
        self.assertEqual(r.returncode, 0)

    def test_check_missing_body_file_is_error_exit_2(self):
        head = self.escalate()
        r = self.run_tool("check", self.base, head,
                          "--body-file", str(self.repo / "nope.txt"))
        self.assertEqual(r.returncode, 2)


class SeedEscalationTests(SyntheticRepo):
    """The three G-P2 seeded escalations, rebuilt synthetically."""

    def test_s1_new_credentialed_host_bucket(self):
        self.write("tools/ghg/ghg.py", GHG_PY.replace(
            '"search": [(60, 20)],',
            '"search": [(60, 20)],\n    "metadata_creds": [(60, 30)],'))
        head = self.commit("s1")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("metadata_creds" in x
                            for x in d["newly_allowed"]))

    def test_s2_method_leaves_mutating_set(self):
        self.write("tools/ghg/ghg.py", GHG_PY.replace(
            '"create", "comment", "merge", "edit"',
            '"create", "comment", "edit"'))
        head = self.commit("s2")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("'merge'" in x for x in d["newly_allowed"]))

    def test_s3_metadata_paths_leave_deny_set(self):
        self.write("scripts/policy.data", POLICY_DATA.replace(
            "*/.config/gcloud\n", "").replace("*/.config/gcloud/*\n", ""))
        head = self.commit("s3")
        _, d = self.diff(self.base, head)
        hits = [x for x in d["newly_allowed"] if "gcloud" in x]
        self.assertEqual(len(hits), 2)


def history_available():
    if not REPLAY_SUMMARY.exists():
        return False
    try:
        summary = json.loads(REPLAY_SUMMARY.read_text())
    except (OSError, ValueError):
        return False
    for entry in summary:
        r = subprocess.run(
            ["git", "cat-file", "-e", f"{entry['commit']}^{{commit}}"],
            cwd=REPO_ROOT, capture_output=True)
        if r.returncode != 0:
            return False
    return True


@unittest.skipUnless(history_available(),
                     "replay corpus commits not in the local object store")
class ReplayCorpusTests(unittest.TestCase):
    def run_diff(self, base, head):
        r = subprocess.run(
            [sys.executable, str(REAL_SCRIPT), "--repo", str(REPO_ROOT),
             "diff", base, head], capture_output=True, text=True)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        return json.loads(r.stdout)

    def test_replay_reproduces_phase0_counts(self):
        summary = json.loads(REPLAY_SUMMARY.read_text())
        self.assertEqual(len(summary), 20)
        for entry in summary:
            with self.subTest(pr=entry["pr"]):
                base = git(REPO_ROOT, "rev-parse", f"{entry['commit']}^1")
                d = self.run_diff(base, entry["commit"])
                self.assertEqual(len(d["newly_allowed"]), entry["allowed"])
                self.assertEqual(len(d["newly_denied"]), entry["denied"])
                self.assertEqual(len(d["notes"]), len(entry["notes"]))

    def test_pr58_executable_surface_flagged(self):
        base = git(REPO_ROOT, "rev-parse", "a649e60^1")
        d = self.run_diff(base, "a649e60")
        ex = d["newly_allowed_executable"]
        self.assertEqual(len(d["newly_allowed"]), 40)
        self.assertTrue(any("server.cjs" in x for x in ex))
        self.assertTrue(any("start-server.sh" in x for x in ex))
        self.assertTrue(any("stop-server.sh" in x for x in ex))
        self.assertTrue(any("task-start" in x for x in ex))


if __name__ == "__main__":
    unittest.main()
