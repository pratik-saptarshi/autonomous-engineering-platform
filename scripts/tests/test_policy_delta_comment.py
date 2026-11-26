"""Tests for scripts/format_policy_delta_comment.py (issue #154).

unittest.TestCase style only: CI runs
``python3 -m unittest discover -s scripts/tests``.

The helper formats the sticky head-SHA PR comment for the Policy Delta
workflow and picks the existing comment to update (or none, to create).
Everything here is pure stdlib and offline: the workflow itself is
checked statically (no network, no YAML dependency).
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "format_policy_delta_comment.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "policy-delta.yml"

HEAD = "a" * 40
BASE = "b" * 40
RUN_URL = "https://github.com/example/repo/actions/runs/123456"
MARKER = "<!-- aep:policy-delta -->"
BOT = "github-actions[bot]"

REPORT = """\
# Policy delta

Newly allowed (1):
- tools/ghg/ghg.py: bucket `core` cap 3500 -> 4000

Acknowledgement token: `policy-delta-sha256: deadbeef`
"""


def load():
    spec = importlib.util.spec_from_file_location(
        "format_policy_delta_comment", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FormatTests(unittest.TestCase):
    def setUp(self):
        self.m = load()

    def fmt(self, report=REPORT, outcome="ok", **kw):
        return self.m.format_comment(
            report, head_sha=kw.get("head", HEAD),
            base_sha=kw.get("base", BASE),
            run_url=kw.get("run_url", RUN_URL), outcome=outcome)

    def test_normal_report_has_marker_metadata_and_body(self):
        body = self.fmt(outcome="ack-required")
        self.assertEqual(body.count(MARKER), 1)
        self.assertTrue(body.startswith(MARKER))
        self.assertIn(HEAD, body)
        self.assertIn(BASE, body)
        self.assertIn(RUN_URL, body)
        self.assertIn("ack-required", body)
        self.assertIn("bucket `core` cap 3500 -> 4000", body)
        self.assertIn(f"policy-delta-{HEAD}", body)
        self.assertLess(len(body.encode("utf-8")), 65000)

    def test_each_outcome_is_named(self):
        for outcome in ("ok", "ack-required", "differ-error"):
            with self.subTest(outcome=outcome):
                self.assertIn(f"`{outcome}`", self.fmt(outcome=outcome))

    def test_exit2_error_report(self):
        report = ("check_policy_delta: error: tools/ghg/ghg.py: modelled "
                  "power is mutated at runtime (line 9)\n\n**The differ "
                  "errored (exit 2); the acknowledgement check below "
                  "fails closed.**\n")
        body = self.fmt(report=report, outcome="differ-error")
        self.assertIn("differ-error", body)
        self.assertIn("modelled power is mutated at runtime", body)
        self.assertIn("fails closed", body)
        self.assertEqual(body.count(MARKER), 1)

    def test_outcome_from_ack_rc(self):
        m = self.m
        self.assertEqual(m.outcome_from_rc("0"), "ok")
        self.assertEqual(m.outcome_from_rc("1"), "ack-required")
        self.assertEqual(m.outcome_from_rc("2"), "differ-error")
        # Missing / garbage rc (an earlier step failed): fail closed.
        self.assertEqual(m.outcome_from_rc(""), "differ-error")
        self.assertEqual(m.outcome_from_rc(None), "differ-error")
        self.assertEqual(m.outcome_from_rc("137"), "differ-error")

    def test_oversized_report_is_truncated_under_65000_bytes(self):
        # 100 KB of multibyte text: the cut must land on a character
        # boundary and the result must still be valid UTF-8.
        big = ("é" * 50 + "\n") * 2000
        self.assertGreater(len(big.encode("utf-8")), 100_000)
        body = self.fmt(report=big)
        raw = body.encode("utf-8")
        self.assertLess(len(raw), 65000)
        raw.decode("utf-8")  # strict: no split code point
        self.assertIn("truncated", body.lower())
        self.assertIn(f"policy-delta-{HEAD}", body)
        self.assertIn(RUN_URL, body)
        self.assertEqual(body.count(MARKER), 1)

    def test_truncation_never_leaves_an_open_code_fence(self):
        big = "```\n" + ("x" * 79 + "\n") * 3000
        body = self.fmt(report=big)
        self.assertLess(len(body.encode("utf-8")), 65000)
        fences = [ln for ln in body.splitlines()
                  if ln.strip().startswith("```")]
        self.assertEqual(len(fences) % 2, 0, "unbalanced code fence")

    def test_report_just_under_budget_is_not_truncated(self):
        body = self.fmt(report="line\n" * 100)
        self.assertNotIn("truncated", body.lower())

    def test_hostile_report_text_is_neutralised(self):
        # A skill path can carry an @mention or a fake marker; the
        # comment must not notify anyone or forge the upsert marker.
        report = ("- skills/@octocat/run.sh\n"
                  "- <!-- aep:policy-delta -->\n")
        body = self.fmt(report=report)
        self.assertNotIn("@octocat", body)
        self.assertEqual(body.count(MARKER), 1)

    def test_rejects_bad_metadata(self):
        m = self.m
        with self.assertRaises(ValueError):
            m.format_comment(REPORT, head_sha="not-a-sha", base_sha=BASE,
                             run_url=RUN_URL, outcome="ok")
        with self.assertRaises(ValueError):
            m.format_comment(REPORT, head_sha=HEAD, base_sha=BASE,
                             run_url="javascript:alert(1)", outcome="ok")
        with self.assertRaises(ValueError):
            m.format_comment(REPORT, head_sha=HEAD, base_sha=BASE,
                             run_url=RUN_URL, outcome="approved")


class UpsertSelectionTests(unittest.TestCase):
    def setUp(self):
        self.m = load()

    @staticmethod
    def comment(cid, login, body, utype="Bot"):
        return {"id": cid, "body": body,
                "user": {"login": login, "type": utype}}

    def test_no_comments_creates(self):
        self.assertIsNone(self.m.select_upsert_target([]))

    def test_existing_bot_marker_comment_is_updated(self):
        comments = [
            self.comment(1, "alice", "hello", "User"),
            self.comment(2, BOT, f"{MARKER}\nold report"),
            self.comment(3, BOT, "some other bot comment"),
        ]
        self.assertEqual(self.m.select_upsert_target(comments), 2)

    def test_non_bot_comment_with_marker_is_ignored(self):
        # A human (or another app) pasting the marker must never be
        # PATCHed -- and must not block creating our own comment.
        comments = [
            self.comment(7, "mallory", f"{MARKER}\nfake", "User"),
            self.comment(8, "other-app[bot]", f"{MARKER}\nfake"),
        ]
        self.assertIsNone(self.m.select_upsert_target(comments))

    def test_bot_comment_without_marker_is_ignored(self):
        comments = [self.comment(4, BOT, "dependabot says hi")]
        self.assertIsNone(self.m.select_upsert_target(comments))

    def test_lowest_id_wins_when_duplicates_exist(self):
        comments = [self.comment(9, BOT, MARKER),
                    self.comment(5, BOT, MARKER)]
        self.assertEqual(self.m.select_upsert_target(comments), 5)

    def test_accepts_json_text_and_paginated_concatenation(self):
        page1 = json.dumps([self.comment(1, "alice", "x", "User")])
        page2 = json.dumps([self.comment(2, BOT, MARKER)])
        # `gh api --paginate` prints the arrays back to back.
        self.assertEqual(
            self.m.select_upsert_target(page1 + page2), 2)
        self.assertEqual(
            self.m.select_upsert_target(page1 + "\n" + page2), 2)
        self.assertIsNone(self.m.select_upsert_target(""))

    def test_tolerates_malformed_entries(self):
        comments = [None, 3, {"id": 1}, {"id": 2, "body": None,
                                         "user": None},
                    self.comment(6, BOT, MARKER)]
        self.assertEqual(self.m.select_upsert_target(comments), 6)

    def test_plan_noop_when_content_unchanged(self):
        m = self.m
        body = m.format_comment(REPORT, head_sha=HEAD, base_sha=BASE,
                                run_url=RUN_URL, outcome="ack-required")
        # Same content, different workflow run (an `edited` re-run):
        # the stored comment must not be rewritten.
        rerun = m.format_comment(
            REPORT, head_sha=HEAD, base_sha=BASE,
            run_url=RUN_URL.replace("123456", "999999"),
            outcome="ack-required")
        comments = [self.comment(42, BOT, body)]
        self.assertEqual(m.plan_upsert(comments, rerun), ("noop", 42))

    def test_plan_update_when_outcome_changes(self):
        m = self.m
        old = m.format_comment(REPORT, head_sha=HEAD, base_sha=BASE,
                               run_url=RUN_URL, outcome="ack-required")
        new = m.format_comment(REPORT, head_sha=HEAD, base_sha=BASE,
                               run_url=RUN_URL, outcome="ok")
        self.assertEqual(
            m.plan_upsert([self.comment(42, BOT, old)], new),
            ("update", 42))

    def test_plan_update_when_head_changes(self):
        m = self.m
        old = m.format_comment(REPORT, head_sha=HEAD, base_sha=BASE,
                               run_url=RUN_URL, outcome="ok")
        new = m.format_comment(REPORT, head_sha="c" * 40, base_sha=BASE,
                               run_url=RUN_URL, outcome="ok")
        self.assertEqual(
            m.plan_upsert([self.comment(42, BOT, old)], new),
            ("update", 42))

    def test_plan_create_when_no_target(self):
        m = self.m
        new = m.format_comment(REPORT, head_sha=HEAD, base_sha=BASE,
                               run_url=RUN_URL, outcome="ok")
        self.assertEqual(m.plan_upsert([], new), ("create", None))


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True)

    def test_format_and_plan_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "report.md").write_text(REPORT)
            out = td / "comment.md"
            r = self.run_cli(
                "format", "--report", str(td / "report.md"),
                "--head-sha", HEAD, "--base-sha", BASE,
                "--run-url", RUN_URL, "--ack-rc", "1",
                "--output", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            body = out.read_text()
            self.assertIn(MARKER, body)
            self.assertIn("ack-required", body)
            (td / "comments.json").write_text("[]")
            r = self.run_cli("plan", "--comments",
                             str(td / "comments.json"),
                             "--body-file", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.split(), ["action=create"])
            (td / "comments.json").write_text(json.dumps([
                {"id": 77, "body": body,
                 "user": {"login": BOT, "type": "Bot"}}]))
            r = self.run_cli("plan", "--comments",
                             str(td / "comments.json"),
                             "--body-file", str(out))
            self.assertEqual(r.stdout.split(),
                             ["action=noop", "comment_id=77"])

    def test_missing_report_fails_closed_to_differ_error(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "comment.md"
            r = self.run_cli(
                "format", "--report", str(Path(td) / "nope.md"),
                "--head-sha", HEAD, "--base-sha", BASE,
                "--run-url", RUN_URL, "--ack-rc", "",
                "--output", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            body = out.read_text()
            self.assertIn("differ-error", body)
            self.assertIn("report was not produced", body)

    def test_bad_input_exits_2(self):
        r = self.run_cli("format", "--report", "x", "--head-sha", "zz",
                         "--base-sha", BASE, "--run-url", RUN_URL,
                         "--ack-rc", "0", "--output", "/dev/null")
        self.assertEqual(r.returncode, 2)


class WorkflowWiringTests(unittest.TestCase):
    """Static checks on .github/workflows/policy-delta.yml."""

    def setUp(self):
        self.text = WORKFLOW.read_text()
        self.lines = self.text.splitlines()

    def run_blocks(self):
        """Yield the text of every `run:` script block."""
        i = 0
        while i < len(self.lines):
            ln = self.lines[i]
            m = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", ln)
            if m:
                indent = len(m.group(1)) + (2 if ln.lstrip()
                                            .startswith("- ") else 0)
                if m.group(2) in ("|", ">", "|-", ">-"):
                    block = []
                    i += 1
                    while i < len(self.lines) and (
                            not self.lines[i].strip()
                            or len(self.lines[i])
                            - len(self.lines[i].lstrip()) > indent):
                        block.append(self.lines[i])
                        i += 1
                    yield "\n".join(block)
                    continue
                yield m.group(2)
            i += 1

    def test_top_level_permissions_stay_read_only(self):
        self.assertRegex(self.text,
                         r"(?m)^permissions:\n  contents: read\n")

    def test_comment_write_scope_is_job_level_only(self):
        # Exactly one pull-requests: write, indented under the job.
        hits = [ln for ln in self.lines if "pull-requests: write" in ln]
        self.assertEqual(len(hits), 1, hits)
        self.assertTrue(hits[0].startswith("      "), hits[0])
        self.assertNotRegex(self.text,
                            r"(?m)^permissions:\n(?:  .*\n)*?  "
                            r"pull-requests: write")

    def test_no_expression_interpolation_inside_run_scripts(self):
        blocks = list(self.run_blocks())
        self.assertTrue(blocks)
        for block in blocks:
            self.assertNotIn("${{", block, block)

    def test_comment_step_skips_fork_prs_and_never_fails_the_gate(self):
        i = next(n for n, ln in enumerate(self.lines)
                 if "format_policy_delta_comment.py" in ln)
        # The step header sits above its run block.
        start = max(n for n in range(i)
                    if re.match(r"^      - name:", self.lines[n]))
        end = next((n for n in range(i, len(self.lines))
                    if re.match(r"^      - name:", self.lines[n])),
                   len(self.lines))
        step = "\n".join(self.lines[start:end])
        self.assertIn("always()", step)
        self.assertIn(
            "github.event.pull_request.head.repo.full_name"
            " == github.repository", step)
        self.assertIn("continue-on-error: true", step)
        self.assertIn("GH_TOKEN: ${{ github.token }}", step)
        for needed in ("BASE_SHA", "HEAD_SHA", "RUN_URL", "PR_NUMBER",
                       "ACK_RC"):
            self.assertIn(f"{needed}: ${{{{", step)
        self.assertIn("--method PATCH", step)
        self.assertIn("--method POST", step)

    def test_artifact_and_summary_still_publish(self):
        self.assertIn("name: policy-delta-${{ github.event.pull_request"
                      ".head.sha }}", self.text)
        self.assertIn('>> "$GITHUB_STEP_SUMMARY"', self.text)
        # Artifact upload is not gated on fork status.
        up = next(n for n, ln in enumerate(self.lines)
                  if "upload-artifact@" in ln)
        header = "\n".join(self.lines[max(0, up - 4):up + 1])
        self.assertNotIn("head.repo.full_name", header)

    def test_ack_check_is_still_fail_closed(self):
        self.assertIn("check_policy_delta.py check", self.text)
        self.assertRegex(self.text, r'exit "\$rc"')


if __name__ == "__main__":
    unittest.main()
