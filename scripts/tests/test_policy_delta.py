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
        self.write(".github/skills-sync-scope.txt",
                   "[skills]\nalpha\nbeta\n\n"
                   "[exclude-paths]\nsecret-plans/**\n\n"
                   "[exclude-content]\nINTERNAL-ONLY\n")
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

    def test_window_removed_is_relaxation_newly_allowed(self):
        # ghg checks a charge against every window; a missing window
        # imposes no cap. Removing one relaxes, it does not deny.
        self.write("tools/ghg/ghg.py", GHG_PY.replace(
            '"core": [(3600, 3500)]',
            '"core": [(3600, 3500), (60, 100)]'))
        two = self.commit("two windows")
        self.write("tools/ghg/ghg.py", GHG_PY)
        head = self.commit("one window")
        r, d = self.diff(two, head)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("window 60s removed" in x
                            for x in d["newly_allowed"]))
        self.assertEqual(d["newly_denied"], [])

    def test_window_added_is_tightening_newly_denied(self):
        self.write("tools/ghg/ghg.py", GHG_PY.replace(
            '"core": [(3600, 3500)]',
            '"core": [(3600, 3500), (60, 100)]'))
        head = self.commit("two windows")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(any("new window 60s" in x
                            for x in d["newly_denied"]))
        self.assertEqual(d["newly_allowed"], [])

    def test_bucket_removed_is_relaxation_newly_allowed(self):
        self.write("tools/ghg/ghg.py", GHG_PY.replace(
            '    "search": [(60, 20)],\n', ""))
        head = self.commit("no search bucket")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("'search'" in x and "uncapped" in x
                            for x in d["newly_allowed"]))

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
        self.write(".github/skills-sync-scope.txt",
                   "[skills]\nalpha\ngamma\n\n"
                   "[exclude-paths]\nsecret-plans/**\n\n"
                   "[exclude-content]\nINTERNAL-ONLY\n")
        head = self.commit("head")
        _, d = self.diff(self.base, head)
        self.assertTrue(any("gamma" in x for x in d["newly_allowed"]))
        self.assertTrue(any("beta" in x for x in d["newly_denied"]))

    def test_scope_exclusion_removed_is_newly_allowed(self):
        # Exclusions are denials: removing one widens what syncs.
        self.write(".github/skills-sync-scope.txt",
                   "[skills]\nalpha\nbeta\n\n"
                   "[exclude-paths]\nsecret-plans/**\n\n"
                   "[exclude-content]\n")
        head = self.commit("head")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("INTERNAL-ONLY" in x and "exclusion removed" in x
                            for x in d["newly_allowed"]))

    def test_scope_exclusion_added_is_newly_denied(self):
        self.write(".github/skills-sync-scope.txt",
                   "[skills]\nalpha\nbeta\n\n"
                   "[exclude-paths]\nsecret-plans/**\ndrafts/**\n\n"
                   "[exclude-content]\nINTERNAL-ONLY\n")
        head = self.commit("head")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(any("drafts/**" in x and "exclusion added" in x
                            for x in d["newly_denied"]))
        self.assertEqual(d["newly_allowed"], [])

    def test_scope_unknown_section_is_error_exit_2(self):
        self.write(".github/skills-sync-scope.txt", "[bogus]\nalpha\n")
        head = self.commit("head")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2)

    def test_ghg_indirect_mutation_is_refused_exit_2(self):
        # Mutation through a plain alias of a modelled table.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_L = DEFAULT_LIMITS\n_L["core"] = [(3600, 999999)]\n')
        head = self.commit("alias-mut")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2)
        # Mutation through a chained lookup (.get().append()).
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nDEFAULT_LIMITS.get("core").append((60, 999999))\n')
        head2 = self.commit("chain-mut")
        r = self.run_tool("diff", head, head2)
        self.assertEqual(r.returncode, 2)
        # Mutator call through an alias of a classification set.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_S = _MUTATING_SUBCOMMANDS\n_S.discard("merge")\n')
        head3 = self.commit("alias-discard")
        r = self.run_tool("diff", head2, head3)
        self.assertEqual(r.returncode, 2)

    def test_ghg_nested_alias_mutation_is_refused_exit_2(self):
        # Alias to a nested table (via subscript), then a mutator call.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS["core"]\n_caps.clear()\n')
        head = self.commit("nested-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2)
        # Alias held in a container, mutated through it.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_box = [DEFAULT_LIMITS]\n_box[0]["core"] = [(1, 1)]\n')
        head2 = self.commit("container-alias")
        r = self.run_tool("diff", head, head2)
        self.assertEqual(r.returncode, 2)
        # Modelled table passed as a call argument (callee may mutate).
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _boost(limits):\n    limits["core"] = [(1, 1)]\n'
                   '\n_boost(DEFAULT_LIMITS)\n')
        head3 = self.commit("call-arg")
        r = self.run_tool("diff", head2, head3)
        self.assertEqual(r.returncode, 2)
        # Table returned by a local function, mutated by the caller.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _tbl():\n    return DEFAULT_LIMITS\n'
                   '\n_t = _tbl()\n_t["core"] = [(1, 1)]\n')
        head4 = self.commit("returned-alias")
        r = self.run_tool("diff", head3, head4)
        self.assertEqual(r.returncode, 2)

    def test_ghg_conditional_rebinding_is_refused_exit_2(self):
        # Codex PR #148: `if True: DEFAULT_LIMITS = {}` after the
        # literal leaves the differ reporting the shadowed literal.
        self.write("tools/ghg/ghg.py",
                   GHG_PY + "\nif True:\n    DEFAULT_LIMITS = {}\n")
        head = self.commit("cond-rebind")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2)
        self.assertIn("rebound", r.stderr)

    def test_ghg_binding_census_refuses_unmodelled_binding_forms(self):
        # Codex PR #148, binding-form round: loop-bound aliases,
        # annotated and chained top-level rebindings, and a literal
        # LIMITS rebinding all bypassed the literal extractor. The
        # differ's posture is a whitelist: protected tables may be
        # bound ONLY by their top-level literal/derivation forms.
        cases = {
            "loop-alias": '\nfor _caps in DEFAULT_LIMITS.values():\n'
                          '    _caps.clear()\n',
            "annassign": '\nDEFAULT_LIMITS: dict = {}\n',
            "chained": '\nDEFAULT_LIMITS = _empty = {}\n',
            "limits-literal": '\nLIMITS = {}\n',
            "walrus": '\nif (DEFAULT_LIMITS := {}):\n    pass\n',
        }
        prev = self.base
        for label, snippet in cases.items():
            with self.subTest(form=label):
                self.write("tools/ghg/ghg.py", GHG_PY + snippet)
                head = self.commit(label)
                r = self.run_tool("diff", prev, head)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                prev = head
                self.write("tools/ghg/ghg.py", GHG_PY)

    def test_ghg_alias_propagation_crosses_returns_and_defaults(self):
        # Codex PR #148, fixpoint-completeness round: (a) a function
        # returning an assignment alias was invisible because the
        # returning set was computed before aliases stabilized;
        # (b) a parameter default capturing a table was recorded as
        # a shadow but never marked watched. Both must refuse.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_alias = DEFAULT_LIMITS\n'
                   '\ndef _table():\n    return _alias\n'
                   '\n_t = _table()\n_t.clear()\n')
        head = self.commit("return-alias-chain")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(_limits=DEFAULT_LIMITS):\n'
                   '    _limits.clear()\n\n_uncap()\n')
        head2 = self.commit("default-capture")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Keyword-only and lambda defaults are the same channel.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_f = lambda *, _m=_MUTATING_METHODS: _m.clear()\n')
        head3 = self.commit("lambda-default")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_alias_propagation_scope_and_forwarding(self):
        # Codex PR #148, third fixpoint round: (a) a parameter
        # default must resolve in the ENCLOSING scope -- a default
        # naming an outer alias of the same name captures that alias
        # even though the parameter shadows it inside; (b) a helper
        # returning another watched-returning helper's result is
        # itself a returning function (forwarding chain).
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_alias = DEFAULT_LIMITS\n'
                   '\ndef _uncap(_alias=_alias):\n'
                   '    _alias.clear()\n\n_uncap()\n')
        head = self.commit("default-enclosing-scope")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _table():\n    return DEFAULT_LIMITS\n'
                   '\ndef _forward():\n    return _table()\n'
                   '\n_a = _forward()\n_a.clear()\n')
        head2 = self.commit("forwarding-return")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_mutation_on_returned_table_is_refused(self):
        # Codex PR #148, receiver round: mutating a returning call's
        # result directly (_table().clear(), _table()["x"] = ...)
        # has no name root; receivers resolve through returning calls.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _table():\n    return DEFAULT_LIMITS\n'
                   '\n_table().clear()\n')
        head = self.commit("mutate-return-value")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _table():\n    return DEFAULT_LIMITS\n'
                   '\n_table()["search"] = [(1, 1)]\n')
        head2 = self.commit("store-into-return-value")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_duplicate_window_uses_minimum_cap(self):
        # Codex PR #148: ghg enforces EVERY pair conjunctively, so a
        # duplicated duration's binding cap is the minimum. Dropping
        # the strict duplicate is a real loosening (1 -> 40), not a
        # no-op; dict() last-wins collapsing reported nothing.
        dup = GHG_PY.replace('"search": [(60, 20)]',
                             '"search": [(60, 1), (60, 20)]')
        self.assertNotEqual(dup, GHG_PY)
        self.write("tools/ghg/ghg.py", dup)
        base = self.commit("dup-window")
        self.write("tools/ghg/ghg.py", GHG_PY)
        head = self.commit("drop-strict-dup")
        r, d = self.diff(base, head)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("search" in x and "60s" in x and "20" in x
                            for x in d["newly_allowed"]), d)
        r, d = self.diff(head, base)
        self.assertTrue(any("search" in x and "60s" in x
                            for x in d["newly_denied"]), d)

    def test_ghg_lambda_return_and_mutator_capture_refused(self):
        # Codex PR #148, capture round: a lambda returning a table is
        # an anonymous callable the returning set cannot see, and a
        # captured bound mutator (_c = T.clear) is later invoked as a
        # bare name. Both are refused at the capture point.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_table = lambda: DEFAULT_LIMITS\n_table().clear()\n')
        head = self.commit("lambda-return")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_clear = DEFAULT_LIMITS.clear\n_clear()\n')
        head2 = self.commit("mutator-capture")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_conditional_expression_alias_is_tracked(self):
        # Codex PR #148: `_caps = T if c else {}` -- a branch of a
        # conditional expression hands the table over just as a
        # direct assignment does; the alias must be watched.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS if True else {}\n'
                   '_caps.clear()\n')
        head = self.commit("ifexp-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_comprehension_yielded_alias_is_tracked(self):
        # Codex PR #148: a pass-through comprehension inside a
        # container retains references to the yielded inner lists;
        # a transforming comprehension (list() per element, as in
        # load_limits) produces copies and must stay accepted.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = {"caps": [v for v in DEFAULT_LIMITS.values()]}\n'
                   '_caps["caps"][-1].clear()\n')
        head = self.commit("comp-yield-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_copy = {k: list(v) for k, v in DEFAULT_LIMITS.items()}\n'
                   '_copy.clear()\n')
        head2 = self.commit("comp-transform-copy")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_inline_comprehension_receiver_is_refused(self):
        # Codex PR #148: a pass-through comprehension consumed
        # inline as a mutation receiver has no alias at all; the
        # receiver resolution must see through it.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n[v for v in DEFAULT_LIMITS.values()][-1].clear()\n')
        head = self.commit("inline-comp-receiver")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_census_is_linear_on_nested_literals(self):
        # Codex PR #148: when denotes_watched and hands_over were
        # mutually recursive, each nesting level doubled the work
        # (20 nested lists took ~7s; the unified predicate is
        # linear). An unrelated deeply-nested literal must not stall.
        import time
        nested = "1"
        for _ in range(22):
            nested = f"[{nested}]"
        self.write("tools/ghg/ghg.py", GHG_PY + f"\n_BIG = {nested}\n")
        head = self.commit("nested-literal")
        start = time.monotonic()
        r = self.run_tool("diff", self.base, head)
        elapsed = time.monotonic() - start
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLess(elapsed, 20)

    def test_ghg_walrus_receiver_and_comprehension_scope(self):
        # Codex PR #148: (a) a walrus expression is value-transparent
        # -- (_caps := T).clear() mutates the table inline; (b)
        # comprehension targets live in their own scope -- a comp
        # variable reusing a watched module alias's name inside a
        # helper must not shadow the alias for later statements.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n(_caps := DEFAULT_LIMITS).clear()\n')
        head = self.commit("walrus-receiver")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\ndef _helper():\n'
                   '    _seen = [_caps for _caps in ()]\n'
                   '    _caps.clear()\n')
        head2 = self.commit("comp-scope-shadow")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_comprehension_walrus_binds_enclosing_scope(self):
        # Codex PR #148: PEP 572 -- a walrus target inside a
        # comprehension binds in the enclosing non-comprehension
        # scope, unlike the comprehension's own iteration targets.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_seen = [(_caps := DEFAULT_LIMITS) for _ in (0,)]\n'
                   '_caps.clear()\n')
        head = self.commit("comp-walrus")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_global_declaration_redirects_walrus_binding(self):
        # Codex PR #148: `global _caps` inside a helper redirects a
        # comprehension walrus binding to module scope, where the
        # later mutation lands. Declaration-aware binding keys.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _helper():\n'
                   '    global _caps\n'
                   '    _seen = [(_caps := DEFAULT_LIMITS) for _ in (0,)]\n'
                   '\n_helper()\n_caps.clear()\n')
        head = self.commit("global-walrus")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_nonlocal_target_and_global_reads(self):
        # Codex PR #148: (a) `nonlocal` binds in the enclosing scope
        # that ACTUALLY binds the name, skipping intermediate scopes
        # that do not; (b) a `global` declaration governs READS too --
        # an enclosing function's local shadow must not hide a
        # nested function's explicitly global reference.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _outer():\n'
                   '    _caps = {}\n'
                   '    def _mid():\n'
                   '        def _inner():\n'
                   '            nonlocal _caps\n'
                   '            _caps = DEFAULT_LIMITS\n'
                   '        _inner()\n'
                   '    _mid()\n'
                   '    _caps.clear()\n')
        head = self.commit("nonlocal-target")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\ndef _outer():\n'
                   '    _caps = {}\n'
                   '    def _inner():\n'
                   '        global _caps\n'
                   '        _caps.clear()\n'
                   '    _inner()\n')
        head2 = self.commit("global-read")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_comprehension_binding_beats_enclosing_declaration(self):
        # Codex PR #148: resolution order -- a comprehension target
        # between the read and a declaring function is the nearer
        # binding and wins over the function's nonlocal declaration.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _outer():\n'
                   '    _caps = {}\n'
                   '    def _helper():\n'
                   '        nonlocal _caps\n'
                   '        _seen = [_caps.clear() for _caps in '
                   'DEFAULT_LIMITS.values()]\n'
                   '    _helper()\n')
        head = self.commit("comp-beats-nonlocal")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_class_scope_skipped_for_method_reads(self):
        # Codex PR #148: class namespaces are not lexical scopes
        # for methods -- a class attribute reusing a watched module
        # alias's name does not shadow it inside methods, while a
        # class-body read of a class attribute still resolves there.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\nclass _Uncap:\n'
                   '    _caps = {}\n'
                   '    def run(self):\n'
                   '        _caps.clear()\n')
        head = self.commit("class-scope-skip")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_class_body_read_before_binding_falls_back(self):
        # Codex PR #148: class bodies execute imperatively -- a
        # class-body read of a name before the class's own first
        # binding of it falls back to the enclosing/global binding,
        # unlike function-scope static shadowing.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\nclass _Uncap:\n'
                   '    _caps.clear()\n'
                   '    _caps = {}\n')
        head = self.commit("class-read-before-bind")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # And the reverse order resolves to the class attribute.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\nclass _Cfg:\n'
                   '    _caps = {}\n'
                   '    _caps.clear()\n')
        head2 = self.commit("class-read-after-bind")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_class_rhs_read_and_withitem_positions(self):
        # Codex PR #148: (a) a class binding takes effect at the
        # END of its statement -- `_caps = _caps` reads the RHS from
        # the enclosing binding; (b) ast.withitem has no position of
        # its own and must not crash position tracking.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\nclass _Uncap:\n'
                   '    _caps = _caps\n'
                   '    _caps.clear()\n')
        head = self.commit("class-rhs-read")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nfrom contextlib import nullcontext\n'
                   '\nclass _Cfg:\n'
                   '    with nullcontext({}) as _unrelated:\n'
                   '        pass\n')
        head2 = self.commit("class-withitem")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_class_loop_binding_effect_position(self):
        # Codex PR #148: a class-body loop target takes effect
        # after the iterable evaluates but before the body runs --
        # not at the compound statement's end.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = {}\n'
                   '\nclass _Uncap:\n'
                   '    for _caps in DEFAULT_LIMITS.values():\n'
                   '        _caps.clear()\n')
        head = self.commit("class-loop-effect")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_class_annotation_only_does_not_bind(self):
        # Codex PR #148: `_caps: dict` in a class body records an
        # annotation but binds no attribute; reads still resolve to
        # the outer alias.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\nclass _Uncap:\n'
                   '    _caps: dict\n'
                   '    _caps.clear()\n')
        head = self.commit("class-annotation-only")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_conditional_class_binding_keeps_outer_fallback(self):
        # Codex PR #148: a class binding nested in a conditional
        # may never execute, so it cannot decide a later class-body
        # read -- the outer (watched) possibility is retained.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\nclass _Uncap:\n'
                   '    if False:\n'
                   '        _caps = {}\n'
                   '    _caps.clear()\n')
        head = self.commit("conditional-class-binding")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_conditional_class_capture_retains_both(self):
        # Codex PR #148: the mirror image -- a conditional class
        # binding that DOES execute and captures a table must also
        # be retained: resolution is disjunctive over the class
        # binding and the outer fallback.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = {}\n'
                   '\nclass _Uncap:\n'
                   '    if True:\n'
                   '        _caps = DEFAULT_LIMITS\n'
                   '    _caps.clear()\n')
        head = self.commit("conditional-class-capture")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_class_deletion_restores_outer_fallback(self):
        # Codex PR #148: `del _caps` in a class body removes the
        # class-local binding, so a later class-body read falls
        # back to the outer watched alias -- the earlier class
        # assignment no longer decides the read.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\nclass _Uncap:\n'
                   '    _caps = {}\n'
                   '    del _caps\n'
                   '    _caps.clear()\n')
        head = self.commit("class-deletion-fallback")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # A conditional deletion may not execute, so both
        # resolutions stay possible (disjunctive, like conditional
        # bindings).
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\nclass _Uncap:\n'
                   '    _caps = {}\n'
                   '    if True:\n'
                   '        del _caps\n'
                   '    _caps.clear()\n')
        head2 = self.commit("class-conditional-deletion")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: bind -> delete -> rebind decides again -- the
        # last event before the read wins, and a plain dict is not
        # a table.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = DEFAULT_LIMITS\n'
                   '\nclass _Cfg:\n'
                   '    _caps = {}\n'
                   '    del _caps\n'
                   '    _caps = {}\n'
                   '    _caps.clear()\n')
        head3 = self.commit("class-delete-rebind")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_match_pattern_capture_is_tracked(self):
        # Codex PR #148: a match-case capture binds the matched
        # subject (ordinary local aliasing) but never entered the
        # binding census, so mutations through the capture name
        # escaped.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nmatch DEFAULT_LIMITS:\n'
                   '    case _caps:\n'
                   '        _caps.clear()\n')
        head = self.commit("match-capture")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Captures nested in a pattern bind sub-values of the
        # subject (here a bucket's mutable cap list).
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nmatch DEFAULT_LIMITS:\n'
                   '    case {"core": _caps}:\n'
                   '        _caps.clear()\n')
        head2 = self.commit("match-nested-capture")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Capturing a protected name itself is a refused binding
        # form, like every other non-declaration binding.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nmatch {}:\n'
                   '    case DEFAULT_LIMITS:\n'
                   '        pass\n')
        head3 = self.commit("match-protected-capture")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("rebound", r.stderr)
        # Precision: capturing an unrelated subject is no alias.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nmatch {"core": []}:\n'
                   '    case _caps:\n'
                   '        _caps.clear()\n')
        head4 = self.commit("match-unrelated")
        r = self.run_tool("diff", self.base, head4)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_container_operators_propagate_aliasing(self):
        # Codex PR #148: [DEFAULT_LIMITS] + [] builds a NEW
        # container holding the SAME table object as an element --
        # unlike a constructor copy, concatenation / repetition /
        # dict-merge preserve element references, so aliasing must
        # propagate through them.
        cases = {
            "concat": '\n_caps = [DEFAULT_LIMITS] + []\n'
                      '_caps[0].clear()\n',
            "repeat": '\n_caps = [DEFAULT_LIMITS] * 1\n'
                      '_caps[0].clear()\n',
            "merge": '\n_m = DEFAULT_LIMITS | {}\n'
                     '_m["core"].clear()\n',
        }
        prev = self.base
        for label, snippet in cases.items():
            with self.subTest(form=label):
                self.write("tools/ghg/ghg.py", GHG_PY + snippet)
                head = self.commit(label)
                r = self.run_tool("diff", prev, head)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                prev = head
                self.write("tools/ghg/ghg.py", GHG_PY)
        # Precision: container operators over unrelated values
        # are not aliases.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_caps = [1] + [2]\n_caps.append(3)\n')
        head = self.commit("container-unrelated")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_method_call_argument_is_a_mutation_site(self):
        # Codex PR #148: a watched table passed to a locally
        # defined METHOD (an attribute callee) escaped the
        # local-definition argument check, which only recognized
        # bare-name callees.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Uncap:\n'
                   '    @staticmethod\n'
                   '    def run(caps):\n'
                   '        caps.clear()\n'
                   '\n_Uncap.run(DEFAULT_LIMITS)\n')
        head = self.commit("method-call-arg")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: an attribute callee that is NOT defined in
        # this file (imported callable) stays in the named
        # boundary, not a mutation site.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nimport json\n_s = json.dumps(DEFAULT_LIMITS)\n')
        head2 = self.commit("imported-call-arg")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_watched_store_into_container_is_a_site(self):
        # Codex PR #148: storing a watched table into an existing
        # container creates an alias the fixpoint never sees (the
        # subscript target binds no name), and later mutations
        # through the container escape.
        cases = {
            "subscript-store": '\n_h = {}\n_h["caps"] = DEFAULT_LIMITS\n'
                               '_h["caps"].clear()\n',
            "attribute-store": '\nclass _H:\n    pass\n'
                               '_h = _H()\n_h.caps = DEFAULT_LIMITS\n'
                               '_h.caps.clear()\n',
            "append-store": '\n_h = []\n_h.append(DEFAULT_LIMITS)\n'
                            '_h[0].clear()\n',
        }
        prev = self.base
        for label, snippet in cases.items():
            with self.subTest(form=label):
                self.write("tools/ghg/ghg.py", GHG_PY + snippet)
                head = self.commit(label)
                r = self.run_tool("diff", prev, head)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                prev = head
                self.write("tools/ghg/ghg.py", GHG_PY)
        # Precision: storing unrelated values is ordinary code.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_h = {}\n_h["x"] = 1\n_h["x"] = 2\n')
        head = self.commit("store-unrelated")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_method_return_value_is_tracked(self):
        # Codex PR #148: a locally defined METHOD returning a
        # table was invisible -- stripping the method-call layer
        # discarded the callee before the returning census could
        # be consulted, for receivers and values alike.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Uncap:\n'
                   '    @staticmethod\n'
                   '    def table():\n'
                   '        return DEFAULT_LIMITS\n'
                   '\n_Uncap.table().clear()\n')
        head = self.commit("method-return-receiver")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Uncap:\n'
                   '    @staticmethod\n'
                   '    def table():\n'
                   '        return DEFAULT_LIMITS\n'
                   '\n_t = _Uncap.table()\n_t.clear()\n')
        head2 = self.commit("method-return-value")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a method returning an unrelated value is not
        # a returning-table function.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Cfg:\n'
                   '    @staticmethod\n'
                   '    def table():\n'
                   '        return {}\n'
                   '\n_t = _Cfg.table()\n_t.clear()\n')
        head3 = self.commit("method-return-unrelated")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_destructure_keeps_table_grade(self):
        # Codex PR #148: the element-grade (weak) exemption applies
        # to proven scalar-producing sources only. Destructuring a
        # wrapper container can yield the table itself, so those
        # components stay table-grade.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\nfor _key, _value in [("caps", DEFAULT_LIMITS)]:\n'
                   '    _uncap(_value)\n')
        head = self.commit("wrapper-destructure")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # The proven scalar sources stay exempt: .items() keys and
        # destructured cap-list elements are scalars of the
        # modelled structures and hand over nothing to local code.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket, window_s):\n'
                   '        return bucket\n'
                   '\n_led = _Ledger()\n'
                   'for _bucket, _pairs in DEFAULT_LIMITS.items():\n'
                   '    for _w, _c in _pairs:\n'
                   '        _led.spend(_bucket, _w)\n')
        head2 = self.commit("scalar-grade-args")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_mutator_named_method_still_checks_arguments(self):
        # Codex PR #148: the mutator-call branch consumed calls
        # whose method name collides with a container mutator,
        # so the local-definition argument check never ran when
        # the receiver was unwatched.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Uncap:\n'
                   '    def clear(self, caps):\n'
                   '        caps.clear()\n'
                   '\n_u = _Uncap()\n_u.clear(DEFAULT_LIMITS)\n')
        head = self.commit("mutator-named-method")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: the same shape with an unrelated argument is
        # ordinary code.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Cfg:\n'
                   '    def clear(self, caps):\n'
                   '        caps.clear()\n'
                   '\n_u = _Cfg()\n_u.clear({})\n')
        head2 = self.commit("mutator-named-method-unrelated")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_callee_alias_is_a_local_definition(self):
        # Codex PR #148: invoking a local helper through an
        # assigned alias escaped the local-definition argument
        # check, which only recognized the definition's own name.
        cases = {
            "func-alias": '\ndef _uncap(caps):\n    caps.clear()\n'
                          '\n_run = _uncap\n_run(DEFAULT_LIMITS)\n',
            "method-alias": '\nclass _U:\n'
                            '    @staticmethod\n'
                            '    def run(caps):\n'
                            '        caps.clear()\n'
                            '\n_run = _U.run\n_run(DEFAULT_LIMITS)\n',
        }
        prev = self.base
        for label, snippet in cases.items():
            with self.subTest(form=label):
                self.write("tools/ghg/ghg.py", GHG_PY + snippet)
                head = self.commit(label)
                r = self.run_tool("diff", prev, head)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                prev = head
                self.write("tools/ghg/ghg.py", GHG_PY)
        # Precision: an alias of an imported callable is not a
        # local definition.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nimport json\n_run = json.dumps\n'
                   '_s = _run(DEFAULT_LIMITS)\n')
        head = self.commit("imported-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_alias_keeps_table_grade(self):
        # Codex PR #148: treating every name as a structural
        # source granted the scalar exemption to aliases of
        # wrapper containers; provenance follows the binding.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\n_wrapped = [("caps", DEFAULT_LIMITS)]\n'
                   'for _key, _value in _wrapped:\n'
                   '    _uncap(_value)\n')
        head = self.commit("wrapper-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: an alias of a structural view stays exempt
        # for its scalar components.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\n_led = _Ledger()\n'
                   '_items = DEFAULT_LIMITS.items()\n'
                   'for _bucket, _pairs in _items:\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("view-alias")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_enter_return_value_is_tracked(self):
        # Codex PR #148: a with-target bound from a locally
        # defined context manager whose __enter__ returns a table
        # never entered the alias fixpoint.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ctx:\n'
                   '    def __enter__(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '    def __exit__(self, *a):\n'
                   '        return False\n'
                   '\nwith _Ctx() as _t:\n'
                   '    _t.clear()\n')
        head = self.commit("enter-return")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: an __enter__ returning an unrelated value is
        # not a table source.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ctx:\n'
                   '    def __enter__(self):\n'
                   '        return {}\n'
                   '    def __exit__(self, *a):\n'
                   '        return False\n'
                   '\nwith _Ctx() as _t:\n'
                   '    _t.clear()\n')
        head2 = self.commit("enter-unrelated")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_returning_status_follows_callee_aliases(self):
        # Codex PR #148: calling a table-returning function
        # through an assigned alias lost its returning status,
        # because the returning census holds only definition
        # names.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _table():\n    return DEFAULT_LIMITS\n'
                   '\n_t = _table\n_t().clear()\n')
        head = self.commit("returning-alias-receiver")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _table():\n    return DEFAULT_LIMITS\n'
                   '\n_t = _table\n_x = _t()\n_x.clear()\n')
        head2 = self.commit("returning-alias-value")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: an alias of a function returning an unrelated
        # value is not a returning alias.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _plain():\n    return {}\n'
                   '\n_t = _plain\n_x = _t()\n_x.clear()\n')
        head3 = self.commit("returning-alias-unrelated")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_aliased_items_view_keeps_value_grade(self):
        # Codex PR #148: when an .items() view is assigned to a
        # name before iteration, the view kind was lost and BOTH
        # destructured targets were marked element-grade -- but
        # the value target retains the mutable cap list.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pair):\n    pair.clear()\n'
                   '\n_items = DEFAULT_LIMITS.items()\n'
                   'for _k, _pairs in _items:\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("aliased-items-view")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: the key target of the same aliased view is
        # still a scalar and hands over nothing.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\n_led = _Ledger()\n'
                   '_items = DEFAULT_LIMITS.items()\n'
                   'for _bucket, _pairs in _items:\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("aliased-items-key")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_generator_yields_are_tracked(self):
        # Codex PR #148: a local generator yielding a protected
        # table was invisible -- the returning census only scanned
        # Return nodes, so iteration targets never became watched.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _tables():\n    yield DEFAULT_LIMITS\n'
                   '\nfor _caps in _tables():\n'
                   '    _caps.clear()\n')
        head = self.commit("generator-yield")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _tables():\n    yield DEFAULT_LIMITS\n'
                   '\n_t = _tables()\n'
                   'for _caps in _t:\n'
                   '    _caps.clear()\n')
        head2 = self.commit("generator-bound")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a generator yielding unrelated values is not
        # a table source.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _tables():\n    yield {}\n'
                   '\nfor _caps in _tables():\n'
                   '    _caps.clear()\n')
        head3 = self.commit("generator-unrelated")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_return_is_not_structural(self):
        # Codex PR #148: "returning" only establishes that a
        # return value CONTAINS a table; a function returning a
        # wrapper container is not a structural source, so
        # destructuring its result keeps table grade.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\ndef _wrapped():\n'
                   '    return [("caps", DEFAULT_LIMITS)]\n'
                   '\nfor _key, _value in _wrapped():\n'
                   '    _uncap(_value)\n')
        head = self.commit("wrapper-return")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a function returning the table itself IS a
        # structural source -- its .items() keys stay exempt.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\ndef _table():\n    return DEFAULT_LIMITS\n'
                   '\n_led = _Ledger()\n'
                   'for _bucket, _pairs in _table().items():\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("direct-return-view")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_lambda_callee_is_a_local_definition(self):
        # Codex PR #148: a lambda bound to a name is locally
        # defined code, but the name was absent from both
        # local_defs and callee_aliases, so passing it a table
        # escaped the argument check.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_uncap = lambda caps: caps.clear()\n'
                   '_uncap(DEFAULT_LIMITS)\n')
        head = self.commit("lambda-callee")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: the same lambda called with an unrelated
        # value is ordinary code.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_f = lambda caps: caps.clear()\n_f({})\n')
        head2 = self.commit("lambda-callee-unrelated")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_call_result_keeps_provenance(self):
        # Codex PR #148: a name assigned the result of a
        # wrapper-returning call was not wrapper-tainted, so
        # destructuring through the name wrongly took the scalar
        # exemption.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\ndef _wrapped():\n'
                   '    return [("caps", DEFAULT_LIMITS)]\n'
                   '\n_w = _wrapped()\n'
                   'for _key, _value in _w:\n'
                   '    _uncap(_value)\n')
        head = self.commit("wrapper-call-result")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a name assigned a DIRECT table return keeps
        # structural provenance.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\ndef _table():\n    return DEFAULT_LIMITS\n'
                   '\n_led = _Ledger()\n'
                   '_t = _table()\n'
                   'for _bucket, _pairs in _t.items():\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("direct-call-result")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_dunder_mutator_calls_are_sites(self):
        # Codex PR #148: an explicit special-method call
        # (DEFAULT_LIMITS.__delitem__("core")) mutates the table
        # directly but bypassed the mutator whitelist, which only
        # held the named methods.
        cases = {
            "delitem": '\nDEFAULT_LIMITS.__delitem__("core")\n',
            "setitem": '\nDEFAULT_LIMITS.__setitem__("core", [])\n',
        }
        prev = self.base
        for label, snippet in cases.items():
            with self.subTest(form=label):
                self.write("tools/ghg/ghg.py", GHG_PY + snippet)
                head = self.commit(label)
                r = self.run_tool("diff", prev, head)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                prev = head
                self.write("tools/ghg/ghg.py", GHG_PY)
        # Precision: read-only dunders are not mutators.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_n = DEFAULT_LIMITS.__len__()\n')
        head = self.commit("dunder-readonly")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_view_provenance_through_returns(self):
        # Codex PR #148: when a function returns an .items() view,
        # iterating its call result lost the view kind, so both
        # destructured targets were marked element-grade -- but
        # the value target retains the mutable cap list.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\ndef _entries():\n'
                   '    return DEFAULT_LIMITS.items()\n'
                   '\nfor _bucket, _pairs in _entries():\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("view-through-return")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: the key target of the same returned view is
        # still a scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\ndef _entries():\n'
                   '    return DEFAULT_LIMITS.items()\n'
                   '\n_led = _Ledger()\n'
                   'for _bucket, _pairs in _entries():\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("view-through-return-key")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_captured_lookup_method_result_is_tracked(self):
        # Codex PR #148: capturing a read-only lookup method is
        # allowed (it is not a mutator), but calling the capture
        # returns a sub-table; the call was invisible because the
        # capture name is in no returning census.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_get = DEFAULT_LIMITS.get\n'
                   '_get("core").clear()\n')
        head = self.commit("captured-get")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_get = DEFAULT_LIMITS.get\n'
                   '_caps = _get("core")\n_caps.clear()\n')
        head2 = self.commit("captured-get-value")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a lookup capture returning a copy is safe,
        # and lookups on unwatched containers are ordinary.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_copy = DEFAULT_LIMITS.copy\n'
                   '_c = _copy()\n_c.clear()\n')
        head3 = self.commit("captured-copy")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_mixed_returns_are_not_direct(self):
        # Codex PR #148: one structural return made a function
        # "direct" even when another return wraps the table;
        # directness requires EVERY table-carrying return to
        # preserve the structural shape.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\ndef _tables(flag):\n'
                   '    if flag:\n'
                   '        return DEFAULT_LIMITS\n'
                   '    return [("caps", DEFAULT_LIMITS)]\n'
                   '\nfor _key, _value in _tables(True):\n'
                   '    _uncap(_value)\n')
        head = self.commit("mixed-returns")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_ghg_lookup_alias_chains_propagate(self):
        # Codex PR #148: lookup provenance stopped at the first
        # capture; assigning the capture to another name lost it.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_get = DEFAULT_LIMITS.get\n'
                   '_get_again = _get\n'
                   '_get_again("core").clear()\n')
        head = self.commit("lookup-alias-chain")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a chained COPY capture still returns copies.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_copy = DEFAULT_LIMITS.copy\n'
                   '_copy_again = _copy\n'
                   '_c = _copy_again()\n_c.clear()\n')
        head2 = self.commit("copy-alias-chain")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_provenance_through_subscripts(self):
        # Codex PR #148: obtaining a wrapper through a subscript
        # (`[[("caps", T)]][0]`) marked the destination neither as
        # a fresh container nor as a call result, so its elements
        # wrongly took the structural shape.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\n_wrapped = [[("caps", DEFAULT_LIMITS)]][0]\n'
                   'for _key, _value in _wrapped:\n'
                   '    _uncap(_value)\n')
        head = self.commit("wrapper-subscript")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a subscript of the table itself is the
        # modelled sub-table -- structural, its elements scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\n_led = _Ledger()\n'
                   '_pairs = DEFAULT_LIMITS["core"]\n'
                   'for _w, _c in _pairs:\n'
                   '    _led.spend(_w)\n')
        head2 = self.commit("table-subscript")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_init_reinitialization_is_a_mutator(self):
        # Codex PR #148: list.__init__() explicitly invoked on an
        # existing list clears it in place; the mutator census
        # held only the named methods and item dunders.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nDEFAULT_LIMITS["core"].__init__()\n')
        head = self.commit("init-reinit")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: ordinary construction is not reinitialization.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Cfg:\n'
                   '    def __init__(self):\n'
                   '        self.x = {}\n'
                   '\n_c = _Cfg()\n')
        head2 = self.commit("plain-construction")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_property_return_value_is_tracked(self):
        # Codex PR #148: a locally defined property returning a
        # protected table was invisible -- stripping the attribute
        # layer discarded the getter's provenance.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ctx:\n'
                   '    @property\n'
                   '    def caps(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '\n_Ctx().caps.clear()\n')
        head = self.commit("property-receiver")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ctx:\n'
                   '    @property\n'
                   '    def caps(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '\n_t = _Ctx().caps\n_t.clear()\n')
        head2 = self.commit("property-value")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a property returning an unrelated value is
        # not a table source.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ctx:\n'
                   '    @property\n'
                   '    def caps(self):\n'
                   '        return {}\n'
                   '\n_Ctx().caps.clear()\n')
        head3 = self.commit("property-unrelated")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_class_attribute_table_is_tracked(self):
        # Codex PR #148: a class body assigning a table to an
        # attribute exposes it outside the class; stripping the
        # attribute layer left only the unwatched class name.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Holder:\n'
                   '    caps = DEFAULT_LIMITS\n'
                   '\n_Holder.caps.clear()\n')
        head = self.commit("class-attr-class-access")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Holder:\n'
                   '    caps = DEFAULT_LIMITS\n'
                   '\n_h = _Holder()\n_h.caps.clear()\n')
        head2 = self.commit("class-attr-instance-access")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a class attribute bound to an unrelated
        # value is not a table source.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Cfg:\n'
                   '    caps = {}\n'
                   '\n_Cfg.caps.clear()\n')
        head3 = self.commit("class-attr-unrelated")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_attribute_provenance_in_argument_checks(self):
        # Codex PR #148: the table-grade argument predicate
        # stripped class-attribute / property layers and tested
        # the unrelated receiver, so a table exposed through an
        # attribute could be passed to local code unchecked.
        cases = {
            "class-attr-arg": '\nclass _Holder:\n'
                              '    caps = DEFAULT_LIMITS\n'
                              '\ndef _uncap(caps):\n'
                              '    caps.clear()\n'
                              '\n_uncap(_Holder.caps)\n',
            "property-arg": '\nclass _Ctx:\n'
                            '    @property\n'
                            '    def caps(self):\n'
                            '        return DEFAULT_LIMITS\n'
                            '\ndef _uncap(caps):\n'
                            '    caps.clear()\n'
                            '\n_uncap(_Ctx().caps)\n',
        }
        prev = self.base
        for label, snippet in cases.items():
            with self.subTest(form=label):
                self.write("tools/ghg/ghg.py", GHG_PY + snippet)
                head = self.commit(label)
                r = self.run_tool("diff", prev, head)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                prev = head
                self.write("tools/ghg/ghg.py", GHG_PY)
        # Precision: an attribute carrying an unrelated value is
        # not a table-grade argument.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Cfg:\n'
                   '    caps = {}\n'
                   '\ndef _tally(caps):\n'
                   '    return len(caps)\n'
                   '\n_t = _tally(_Cfg.caps)\n')
        head = self.commit("attr-arg-unrelated")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_inline_lambda_call_is_a_local_definition(self):
        # Codex PR #148: an inline lambda's callee is neither a
        # Name nor an Attribute, so the local-definition argument
        # check skipped it entirely.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n(lambda caps: caps.clear())(DEFAULT_LIMITS)\n')
        head = self.commit("inline-lambda")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: an inline lambda called with an unrelated
        # value is ordinary code.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n(lambda caps: caps.clear())({})\n')
        head2 = self.commit("inline-lambda-unrelated")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_provenance_through_class_attributes(self):
        # Codex PR #148: an iteration source reached through a
        # class attribute lost the wrapper's provenance --
        # stripping the attribute tested the class name, which is
        # not the tainted binding name.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\nclass _Holder:\n'
                   '    wrapped = [("caps", DEFAULT_LIMITS)]\n'
                   '\nfor _key, _value in _Holder.wrapped:\n'
                   '    _uncap(_value)\n')
        head = self.commit("wrapper-class-attr")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a class attribute holding the table itself
        # is structural -- its .items() keys stay exempt.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\nclass _Holder:\n'
                   '    table = DEFAULT_LIMITS\n'
                   '\n_led = _Ledger()\n'
                   'for _bucket, _pairs in _Holder.table.items():\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("table-class-attr")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_compound_class_attribute_is_collected(self):
        # Codex PR #148: the class-attribute census examined only
        # direct class-body statements, missing attributes bound
        # inside compound statements (if/try/...).
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Holder:\n'
                   '    if True:\n'
                   '        caps = DEFAULT_LIMITS\n'
                   '\n_Holder.caps.clear()\n')
        head = self.commit("compound-class-attr")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a conditionally bound unrelated attribute is
        # not a table source.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Cfg:\n'
                   '    if True:\n'
                   '        caps = {}\n'
                   '\n_Cfg.caps.clear()\n')
        head2 = self.commit("compound-class-attr-unrelated")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_callable_instance_is_a_local_definition(self):
        # Codex PR #148: an instance of a locally defined class
        # implementing __call__ is locally defined code, but a
        # name holding the instance was in no callee census.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Uncap:\n'
                   '    def __call__(self, caps):\n'
                   '        caps.clear()\n'
                   '\n_run = _Uncap()\n_run(DEFAULT_LIMITS)\n')
        head = self.commit("callable-instance")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Uncap:\n'
                   '    def __call__(self, caps):\n'
                   '        caps.clear()\n'
                   '\n_Uncap()(DEFAULT_LIMITS)\n')
        head2 = self.commit("callable-instance-direct")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a callable instance invoked with an
        # unrelated value is ordinary code.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Uncap:\n'
                   '    def __call__(self, caps):\n'
                   '        caps.clear()\n'
                   '\n_run = _Uncap()\n_run({})\n')
        head3 = self.commit("callable-instance-unrelated")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_provenance_through_properties(self):
        # Codex PR #148: a property returning a wrapper was a
        # structural source by default -- stripping the attribute
        # never consulted the getter's return shape.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\nclass _Ctx:\n'
                   '    @property\n'
                   '    def wrapped(self):\n'
                   '        return [("caps", DEFAULT_LIMITS)]\n'
                   '\nfor _key, _value in _Ctx().wrapped:\n'
                   '    _uncap(_value)\n')
        head = self.commit("wrapper-property")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a property returning the table itself is a
        # structural source -- its .items() keys stay exempt.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\nclass _Ctx:\n'
                   '    @property\n'
                   '    def table(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '\n_led = _Ledger()\n'
                   'for _bucket, _pairs in _Ctx().table.items():\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("table-property")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_inherited_call_is_a_local_definition(self):
        # Codex PR #148: callable_classes checked only the
        # class's own body, so a subclass inheriting __call__
        # was omitted and its instances escaped the census.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Base:\n'
                   '    def __call__(self, caps):\n'
                   '        caps.clear()\n'
                   '\nclass _Sub(_Base):\n'
                   '    pass\n'
                   '\n_run = _Sub()\n_run(DEFAULT_LIMITS)\n')
        head = self.commit("inherited-call")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: an instance of a non-callable subclass is
        # ordinary data.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Cfg:\n'
                   '    def __init__(self):\n'
                   '        self.x = {}\n'
                   '\nclass _Sub(_Cfg):\n'
                   '    pass\n'
                   '\n_s = _Sub()\n_n = _s.x\n')
        head2 = self.commit("non-callable-subclass")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_taint_through_named_subscripts(self):
        # Codex PR #148: subscripting an already wrapper-tainted
        # name lost the taint -- the passes tested the value's
        # outer form, not its stripped core name.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\n_container = [[("caps", DEFAULT_LIMITS)]]\n'
                   '_wrapped = _container[0]\n'
                   'for _key, _value in _wrapped:\n'
                   '    _uncap(_value)\n')
        head = self.commit("wrapper-named-subscript")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: subscripts through containers holding no
        # table are ordinary data flow.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, value):\n'
                   '        return value\n'
                   '\n_led = _Ledger()\n'
                   '_container = [[("caps", 1)]]\n'
                   '_wrapped = _container[0]\n'
                   'for _key, _value in _wrapped:\n'
                   '    _led.spend(_value)\n')
        head2 = self.commit("scalar-container-subscript")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_provenance_through_attribute_assignment(self):
        # Codex PR #148: assigning a wrapper-valued attribute
        # (property or class attribute) to a name lost the
        # wrapper provenance -- the taint passes tested only the
        # value's core name/call.
        cases = {
            "property-assign": '\nclass _Ctx:\n'
                               '    @property\n'
                               '    def wrapped(self):\n'
                               '        return [("caps", DEFAULT_LIMITS)]\n'
                               '\n_w = _Ctx().wrapped\n',
            "class-attr-assign": '\nclass _Holder:\n'
                                 '    wrapped = [("caps", DEFAULT_LIMITS)]\n'
                                 '\n_w = _Holder.wrapped\n',
        }
        prev = self.base
        for label, snippet in cases.items():
            with self.subTest(form=label):
                self.write("tools/ghg/ghg.py", GHG_PY +
                           '\ndef _uncap(caps):\n    caps.clear()\n' +
                           snippet +
                           'for _key, _value in _w:\n'
                           '    _uncap(_value)\n')
                head = self.commit(label)
                r = self.run_tool("diff", prev, head)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                prev = head
                self.write("tools/ghg/ghg.py", GHG_PY)
        # Precision: a direct property assigned to a name keeps
        # structural provenance.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\nclass _Ctx:\n'
                   '    @property\n'
                   '    def table(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '\n_led = _Ledger()\n'
                   '_t = _Ctx().table\n'
                   'for _bucket, _pairs in _t.items():\n'
                   '    _led.spend(_bucket)\n')
        head = self.commit("direct-property-assign")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_inherited_enter_is_a_context_source(self):
        # Codex PR #148: enter provenance recorded only classes
        # whose own body defines __enter__; a subclass inheriting
        # a table-returning __enter__ was omitted.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Base:\n'
                   '    def __enter__(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '    def __exit__(self, *a):\n'
                   '        return False\n'
                   '\nclass _Sub(_Base):\n'
                   '    pass\n'
                   '\nwith _Sub() as _t:\n'
                   '    _t.clear()\n')
        head = self.commit("inherited-enter")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a subclass inheriting an unrelated
        # __enter__ is not a table source.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Base:\n'
                   '    def __enter__(self):\n'
                   '        return {}\n'
                   '    def __exit__(self, *a):\n'
                   '        return False\n'
                   '\nclass _Sub(_Base):\n'
                   '    pass\n'
                   '\nwith _Sub() as _t:\n'
                   '    _t.clear()\n')
        head2 = self.commit("inherited-enter-unrelated")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_provenance_through_boolops(self):
        # Codex PR #148: a boolean expression can yield the
        # wrapper operand, but the fresh-container test missed
        # BoolOp even though hands_over propagates through it.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\n_wrapped = DEFAULT_LIMITS and '
                   '[("caps", DEFAULT_LIMITS)]\n'
                   'for _key, _value in _wrapped:\n'
                   '    _uncap(_value)\n')
        head = self.commit("wrapper-boolop")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: boolean expressions over table-free values
        # are ordinary data flow.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_flag = True and [("caps", 1)]\n'
                   'for _k, _v in _flag:\n'
                   '    pass\n')
        head2 = self.commit("boolop-scalars")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_factory_returned_callee_is_local(self):
        # Codex PR #148: a local function returning another local
        # function makes its call result a local callee, but the
        # callee census only recognized constructions of callable
        # classes.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\ndef _factory():\n    return _uncap\n'
                   '\n_run = _factory()\n_run(DEFAULT_LIMITS)\n')
        head = self.commit("factory-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\ndef _factory():\n    return _uncap\n'
                   '\n_factory()(DEFAULT_LIMITS)\n')
        head2 = self.commit("factory-direct")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a factory returning an imported callable
        # produces no local callee.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nimport json\n'
                   '\ndef _factory():\n    return json.dumps\n'
                   '\n_run = _factory()\n_s = _run(DEFAULT_LIMITS)\n')
        head3 = self.commit("factory-imported")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_callable_instance_return_is_tracked(self):
        # Codex PR #148: a __call__ returning a table makes the
        # instance a returning callee, but `returning` held only
        # the method name, never the instance's binding name.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Table:\n'
                   '    def __call__(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '\n_t = _Table()\n_t().clear()\n')
        head = self.commit("call-return-receiver")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Table:\n'
                   '    def __call__(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '\n_t = _Table()\n_x = _t()\n_x.clear()\n')
        head2 = self.commit("call-return-value")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a __call__ returning an unrelated value is
        # not a returning instance.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Table:\n'
                   '    def __call__(self):\n'
                   '        return {}\n'
                   '\n_t = _Table()\n_x = _t()\n_x.clear()\n')
        head3 = self.commit("call-return-unrelated")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_view_kind_follows_call_result_bindings(self):
        # Codex PR #148: assigning a view-returning call's result
        # tracked the reference but not the view kind, so the
        # value target of later iteration was marked scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\ndef _entries():\n'
                   '    return DEFAULT_LIMITS.items()\n'
                   '\n_view = _entries()\n'
                   'for _k, _pairs in _view:\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("view-call-binding")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: the key target of the same bound view is
        # still a scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\ndef _entries():\n'
                   '    return DEFAULT_LIMITS.items()\n'
                   '\n_led = _Ledger()\n'
                   '_view = _entries()\n'
                   'for _bucket, _pairs in _view:\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("view-call-binding-key")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_factory_status_follows_aliases(self):
        # Codex PR #148: a factory invoked through an alias
        # produced a result the callee census did not recognize,
        # because factory status never propagated through the
        # alias pass.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\ndef _factory():\n    return _uncap\n'
                   '\n_make = _factory\n'
                   '_run = _make()\n_run(DEFAULT_LIMITS)\n')
        head = self.commit("factory-alias-chain")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: an alias of a non-factory produces no
        # local callee.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _plain():\n    return {}\n'
                   '\n_make = _plain\n_x = _make()\n_x.clear()\n')
        head2 = self.commit("non-factory-alias")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_instance_returning_status_follows_aliases(self):
        # Codex PR #148: table-returning instance status did not
        # propagate when the instance was assigned to another
        # name, so calls through the alias lost provenance.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Table:\n'
                   '    def __call__(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '\n_t = _Table()\n_t2 = _t\n_t2().clear()\n')
        head = self.commit("instance-returning-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: an alias of a non-returning instance is not
        # a returning callee.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Table:\n'
                   '    def __call__(self):\n'
                   '        return {}\n'
                   '\n_t = _Table()\n_t2 = _t\n'
                   '_x = _t2()\n_x.clear()\n')
        head2 = self.commit("instance-nonreturning-alias")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_view_kind_follows_captured_lookup_calls(self):
        # Codex PR #148: calling a captured .items method and
        # assigning the result preserved the watched reference
        # (lookup alias) but not the view kind, so the value
        # target of later iteration was marked scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\n_items = DEFAULT_LIMITS.items\n'
                   '_view = _items()\n'
                   'for _k, _pairs in _view:\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("captured-view-binding")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: the key target of the same captured view is
        # still a scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\n_items = DEFAULT_LIMITS.items\n'
                   '_view = _items()\n'
                   '_led = _Ledger()\n'
                   'for _bucket, _pairs in _view:\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("captured-view-key")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_conflicting_view_kinds_stay_table_grade(self):
        # Codex PR #148: conflicting view bindings dropped the
        # view_kinds entry, and the fallback marked every
        # destructured component scalar-grade -- but each
        # candidate kind (values/items) has a table-grade
        # component, so no component is provably scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\n_view = DEFAULT_LIMITS.values()\n'
                   '_view = DEFAULT_LIMITS.items()\n'
                   'for _k, _pairs in _view:\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("conflicting-view-kinds")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: merely iterating a conflicted view without
        # handing components to local code is not a site.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_view = DEFAULT_LIMITS.values()\n'
                   '_view = DEFAULT_LIMITS.items()\n'
                   'for _k, _pairs in _view:\n'
                   '    pass\n')
        head2 = self.commit("conflicting-view-readonly")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_enter_instance_alias_propagates(self):
        # Codex PR #148: context-manager instance provenance
        # stopped at the constructor binding; assigning the
        # instance to another name lost it.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ctx:\n'
                   '    def __enter__(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '    def __exit__(self, *a):\n'
                   '        return False\n'
                   '\n_ctx = _Ctx()\n_ctx2 = _ctx\n'
                   'with _ctx2 as _t:\n'
                   '    _t.clear()\n')
        head = self.commit("enter-instance-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: an alias of a non-table context manager is
        # not a table source.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ctx:\n'
                   '    def __enter__(self):\n'
                   '        return {}\n'
                   '    def __exit__(self, *a):\n'
                   '        return False\n'
                   '\n_ctx = _Ctx()\n_ctx2 = _ctx\n'
                   'with _ctx2 as _t:\n'
                   '    _t.clear()\n')
        head2 = self.commit("enter-instance-alias-unrelated")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_conditional_callee_alias_is_local(self):
        # Codex PR #148: a callee selected by a conditional
        # expression never entered callee_aliases, because the
        # alias census tested only direct value forms.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\ndef _plain(caps):\n    return caps\n'
                   '\n_run = _uncap if True else _plain\n'
                   '_run(DEFAULT_LIMITS)\n')
        head = self.commit("conditional-callee-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a conditional between imported callables is
        # no local callee.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nimport json\n'
                   '_run = json.dumps if True else json.loads\n'
                   '_s = _run(DEFAULT_LIMITS)\n')
        head2 = self.commit("conditional-imported-alias")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_named_view_return_keeps_view_kind(self):
        # Codex PR #148: returning_views recognized only direct
        # view-call returns; returning a NAME bound to a view
        # lost the kind, so callers' destructured value targets
        # were marked scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\ndef _entries():\n'
                   '    _view = DEFAULT_LIMITS.items()\n'
                   '    return _view\n'
                   '\nfor _k, _pairs in _entries():\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("named-view-return")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: the key target of the same returned view is
        # still a scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\ndef _entries():\n'
                   '    _view = DEFAULT_LIMITS.items()\n'
                   '    return _view\n'
                   '\n_led = _Ledger()\n'
                   'for _bucket, _pairs in _entries():\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("named-view-return-key")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_same_named_properties_are_all_retained(self):
        # Codex PR #148: property_getters keyed by name kept only
        # the last class's getter; an earlier table-returning
        # property of the same name lost its provenance.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Holder:\n'
                   '    @property\n'
                   '    def caps(self):\n'
                   '        return DEFAULT_LIMITS\n'
                   '\nclass _Other:\n'
                   '    @property\n'
                   '    def caps(self):\n'
                   '        return {}\n'
                   '\n_Holder().caps.clear()\n')
        head = self.commit("same-named-properties")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: when every same-named getter returns an
        # unrelated value, the attribute is not a table source.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _A:\n'
                   '    @property\n'
                   '    def caps(self):\n'
                   '        return {}\n'
                   '\nclass _B:\n'
                   '    @property\n'
                   '    def caps(self):\n'
                   '        return {}\n'
                   '\n_A().caps.clear()\n')
        head2 = self.commit("same-named-properties-unrelated")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_view_kind_follows_name_aliases(self):
        # Codex PR #148: assigning a view binding to another
        # name never propagated its view_kinds entry, so the
        # alias's destructured value target was marked scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\n_v1 = DEFAULT_LIMITS.items()\n'
                   '_v2 = _v1\n'
                   'for _k, _pairs in _v2:\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("view-name-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: the key target through the same alias is
        # still a scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\n_v1 = DEFAULT_LIMITS.items()\n'
                   '_v2 = _v1\n'
                   '_led = _Ledger()\n'
                   'for _bucket, _pairs in _v2:\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("view-name-alias-key")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_returning_status_through_conditional_aliases(self):
        # Codex PR #148: a conditional selecting a table-returning
        # function made the destination a callee alias but not a
        # returning alias, so mutations of its result escaped.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _table():\n    return DEFAULT_LIMITS\n'
                   '\ndef _other():\n    return {}\n'
                   '\n_t = _table if True else _other\n'
                   '_t().clear()\n')
        head = self.commit("conditional-returning-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a conditional between non-returning
        # functions is not a returning alias.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _a():\n    return {}\n'
                   '\ndef _b():\n    return {}\n'
                   '\n_t = _a if True else _b\n'
                   '_x = _t()\n_x.clear()\n')
        head2 = self.commit("conditional-nonreturning-alias")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_conditional_alias_directness_requires_all_leaves(self):
        # Codex PR #148: a conditional alias joining
        # returning_direct_aliases when ANY leaf was direct is
        # wrong -- the alias may be the wrapper-returning leaf,
        # so directness requires every leaf to be direct.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\ndef _direct():\n    return DEFAULT_LIMITS\n'
                   '\ndef _wrapper():\n'
                   '    return [("caps", DEFAULT_LIMITS)]\n'
                   '\n_t = _direct if True else _wrapper\n'
                   'for _key, _value in _t():\n'
                   '    _uncap(_value)\n')
        head = self.commit("conditional-alias-mixed-direct")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a conditional between two direct functions
        # stays a structural source.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\ndef _a():\n    return DEFAULT_LIMITS\n'
                   '\ndef _b():\n    return DEFAULT_LIMITS\n'
                   '\n_t = _a if True else _b\n'
                   '_led = _Ledger()\n'
                   'for _bucket, _pairs in _t().items():\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("conditional-alias-all-direct")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_view_conflict_on_call_sources(self):
        # Codex PR #148: the view-conflict guard consulted only
        # Name sources; iterating a conflicted view-returning
        # call directly bypassed it.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\ndef _entries(flag):\n'
                   '    if flag:\n'
                   '        return DEFAULT_LIMITS.values()\n'
                   '    return DEFAULT_LIMITS.items()\n'
                   '\nfor _k, _pairs in _entries(True):\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("view-conflict-call-source")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a single-kind view return through a call is
        # still graded by its kind.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\ndef _entries():\n'
                   '    return DEFAULT_LIMITS.items()\n'
                   '\n_led = _Ledger()\n'
                   'for _bucket, _pairs in _entries():\n'
                   '    _led.spend(_bucket)\n')
        head2 = self.commit("view-single-kind-call")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_callee_through_subscript_is_local(self):
        # Codex PR #148: selecting a local callable from a
        # literal container (`[_uncap][0]`) was not a recognized
        # callee form, so the destination escaped callee_aliases.
        cases = {
            "list-subscript": '\n_run = [_uncap][0]\n',
            "dict-subscript": '\n_run = {"u": _uncap}["u"]\n',
        }
        prev = self.base
        for label, snippet in cases.items():
            with self.subTest(form=label):
                self.write("tools/ghg/ghg.py", GHG_PY +
                           '\ndef _uncap(caps):\n    caps.clear()\n' +
                           snippet + '_run(DEFAULT_LIMITS)\n')
                head = self.commit(label)
                r = self.run_tool("diff", prev, head)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                prev = head
                self.write("tools/ghg/ghg.py", GHG_PY)
        # Precision: a subscript selecting an imported callable
        # is no local callee.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nimport json\n_run = [json.dumps][0]\n'
                   '_s = _run(DEFAULT_LIMITS)\n')
        head = self.commit("subscript-imported")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_direct_subscripted_callee_call_is_local(self):
        # Codex PR #148: invoking a subscript-selected callee
        # directly (`[_uncap][0](DEFAULT_LIMITS)`) bypassed the
        # argument check -- node.func is a Subscript, which no
        # callee branch recognized.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\n[_uncap][0](DEFAULT_LIMITS)\n')
        head = self.commit("direct-subscripted-callee")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a directly subscripted imported callable is
        # not a local callee.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nimport json\n_s = [json.dumps][0](DEFAULT_LIMITS)\n')
        head2 = self.commit("direct-subscripted-imported")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_view_kind_through_conditionals(self):
        # Codex PR #148: a conditional selecting a view lost the
        # view kind entirely (no kind, no conflict), so its
        # destructured components took the scalar exemption by
        # default.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\n_view = DEFAULT_LIMITS.items() if True '
                   'else DEFAULT_LIMITS.items()\n'
                   'for _k, _pairs in _view:\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("view-conditional-same-kind")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Mixed kinds record a conflict (no scalar exemption).
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\n_view = DEFAULT_LIMITS.items() if True '
                   'else DEFAULT_LIMITS.values()\n'
                   'for _k, _pairs in _view:\n'
                   '    _uncap(_pairs)\n')
        head2 = self.commit("view-conditional-mixed")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: the key target of a same-kind conditional
        # items view is still a scalar.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\n_view = DEFAULT_LIMITS.items() if True '
                   'else DEFAULT_LIMITS.items()\n'
                   '_led = _Ledger()\n'
                   'for _bucket, _pairs in _view:\n'
                   '    _led.spend(_bucket)\n')
        head3 = self.commit("view-conditional-key")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_direct_conditional_callee_call_is_local(self):
        # Codex PR #148: invoking a conditional callee directly
        # bypassed the argument check -- node.func is an IfExp,
        # which no callee branch recognized.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(caps):\n    caps.clear()\n'
                   '\ndef _plain(caps):\n    return caps\n'
                   '\n(_uncap if True else _plain)(DEFAULT_LIMITS)\n')
        head = self.commit("direct-conditional-callee")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a conditional between imported callables is
        # no local callee.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nimport json\n'
                   '_s = (json.dumps if True else json.loads)("x")\n')
        head2 = self.commit("direct-conditional-imported")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_view_conflict_follows_aliases(self):
        # Codex PR #148: a conflicted view name's kind is dropped
        # from view_kinds, so aliasing it produced a destination
        # with neither kind nor conflict -- and the use-site
        # guard never fired for the alias.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\n_v1 = DEFAULT_LIMITS.values()\n'
                   '_v1 = DEFAULT_LIMITS.items()\n'
                   '_v2 = _v1\n'
                   'for _k, _pairs in _v2:\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("view-conflict-alias")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: merely iterating a conflicted alias without
        # handing components to local code is not a site.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_v1 = DEFAULT_LIMITS.values()\n'
                   '_v1 = DEFAULT_LIMITS.items()\n'
                   '_v2 = _v1\n'
                   'for _k, _pairs in _v2:\n'
                   '    pass\n')
        head2 = self.commit("view-conflict-alias-readonly")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_table_return_through_conditional_callee(self):
        # Codex PR #148: a table-returning function invoked through
        # a conditional callee escaped hands_over -- the terminal
        # Call handling recognized only Name and Call callees, so
        # the selected callee was never asked whether it returns
        # a table.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _tables():\n    return DEFAULT_LIMITS\n'
                   '\n(_tables if True else None)().clear()\n')
        head = self.commit("conditional-callee-table")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Boolean selection between the table-returning function
        # and a non-returning one hands over the table too.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _tables():\n    return DEFAULT_LIMITS\n'
                   '\ndef _other():\n    return {}\n'
                   '\n(_tables or _other)().clear()\n')
        head2 = self.commit("boolop-callee-table")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Nested conditionals flatten to the same alternatives.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _tables():\n    return DEFAULT_LIMITS\n'
                   '\n((_tables if True else None) if True else '
                   'None)().clear()\n')
        head3 = self.commit("nested-conditional-callee-table")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Control: the direct callee is refused, as before.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _tables():\n    return DEFAULT_LIMITS\n'
                   '\n_tables().clear()\n')
        head4 = self.commit("direct-callee-table")
        r = self.run_tool("diff", self.base, head4)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a conditional callee whose alternatives
        # return no table is not a site.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _other():\n    return {}\n'
                   '\n(_other if True else None)().clear()\n')
        head5 = self.commit("conditional-callee-nonreturning")
        r = self.run_tool("diff", self.base, head5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_view_conflict_through_function_return(self):
        # Codex PR #148: a function returning a name whose view
        # kind already conflicted was never marked conflicted
        # itself -- _view_kinds_of yields the empty set for such
        # a name, so its callers took the scalar exemption for
        # components that are table-grade in some view kind.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\ndef _entries():\n'
                   '    _v = DEFAULT_LIMITS.values()\n'
                   '    _v = DEFAULT_LIMITS.items()\n'
                   '    return _v\n'
                   '\nfor _key, _pairs in _entries():\n'
                   '    _uncap(_pairs)\n')
        head = self.commit("view-conflict-through-return")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # The conflict also travels through a call return: a
        # function returning a conflicted function's result is
        # marked when the fixpoint reaches it.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\ndef _inner():\n'
                   '    _v = DEFAULT_LIMITS.values()\n'
                   '    _v = DEFAULT_LIMITS.items()\n'
                   '    return _v\n'
                   '\ndef _entries():\n'
                   '    return _inner()\n'
                   '\nfor _key, _pairs in _entries():\n'
                   '    _uncap(_pairs)\n')
        head2 = self.commit("view-conflict-chained-return")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Control: the conflicted alias iterated directly is
        # refused, as before.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(pairs):\n    pairs.clear()\n'
                   '\n_v = DEFAULT_LIMITS.values()\n'
                   '_v = DEFAULT_LIMITS.items()\n'
                   'for _key, _pairs in _v:\n'
                   '    _uncap(_pairs)\n')
        head3 = self.commit("view-conflict-alias-direct")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a single-kind return is not conflicted --
        # spending its key component is still scalar use.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\ndef _entries():\n'
                   '    return DEFAULT_LIMITS.items()\n'
                   '\n_led = _Ledger()\n'
                   'for _key, _pairs in _entries():\n'
                   '    _led.spend(_key)\n')
        head4 = self.commit("single-kind-return-key")
        r = self.run_tool("diff", self.base, head4)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_wrapper_taint_through_conditional_callee(self):
        # Codex PR #148 (round 2): a wrapper-returning function
        # invoked through a conditional callee escaped
        # _value_taints -- its Call branch recognized only Name
        # and Attribute callees, so the bound result was never
        # wrapper-tainted, counted as a structural source, and
        # its unpacked value took the scalar exemption even
        # though hands_over (round 1) made the binding watched.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(x):\n    x.clear()\n'
                   '\ndef _wrapper():\n'
                   '    return [("caps", DEFAULT_LIMITS)]\n'
                   '\n_wrapped = (_wrapper if True else None)()\n'
                   'for _key, _value in _wrapped:\n'
                   '    _uncap(_value)\n')
        head = self.commit("wrapper-taint-conditional-callee")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Boolean selection of the wrapper-returning function
        # taints the bound result too.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(x):\n    x.clear()\n'
                   '\ndef _wrapper():\n'
                   '    return [("caps", DEFAULT_LIMITS)]\n'
                   '\ndef _other():\n    return []\n'
                   '\n_wrapped = (_wrapper or _other)()\n'
                   'for _key, _value in _wrapped:\n'
                   '    _uncap(_value)\n')
        head2 = self.commit("wrapper-taint-boolop-callee")
        r = self.run_tool("diff", self.base, head2)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # A walrus-selected wrapper-returning callee taints too.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(x):\n    x.clear()\n'
                   '\ndef _wrapper():\n'
                   '    return [("caps", DEFAULT_LIMITS)]\n'
                   '\n_wrapped = (_f := _wrapper)()\n'
                   'for _key, _value in _wrapped:\n'
                   '    _uncap(_value)\n')
        head3 = self.commit("wrapper-taint-walrus-callee")
        r = self.run_tool("diff", self.base, head3)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Control: the direct callee is refused, as before.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(x):\n    x.clear()\n'
                   '\ndef _wrapper():\n'
                   '    return [("caps", DEFAULT_LIMITS)]\n'
                   '\n_wrapped = _wrapper()\n'
                   'for _key, _value in _wrapped:\n'
                   '    _uncap(_value)\n')
        head4 = self.commit("wrapper-taint-direct-callee")
        r = self.run_tool("diff", self.base, head4)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        # Precision: a conditional callee returning a plain
        # scalar wrapper is not tainted -- its unpacked value
        # is not a table.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _uncap(x):\n    x.clear()\n'
                   '\ndef _plain():\n'
                   '    return [("caps", 42)]\n'
                   '\n_wrapped = (_plain if True else None)()\n'
                   'for _key, _value in _wrapped:\n'
                   '    _uncap(_value)\n')
        head5 = self.commit("wrapper-taint-scalar-wrapper")
        r = self.run_tool("diff", self.base, head5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # Precision: a conditional callee returning a direct
        # items view stays direct -- spending its key component
        # is still scalar use.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nclass _Ledger:\n'
                   '    def spend(self, bucket):\n'
                   '        return bucket\n'
                   '\ndef _items():\n'
                   '    return DEFAULT_LIMITS.items()\n'
                   '\n_wrapped = (_items if True else None)()\n'
                   '_led = _Ledger()\n'
                   'for _key, _pairs in _wrapped:\n'
                   '    _led.spend(_key)\n')
        head6 = self.commit("wrapper-taint-direct-items")
        r = self.run_tool("diff", self.base, head6)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_scope_shadowing_does_not_refuse(self):
        # Precision guard for scope-aware aliasing: unrelated locals
        # that merely reuse watched-adjacent names (bucket/pairs/core)
        # in their own functions are not aliases and must not refuse.
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\ndef _tally():\n'
                   '    bucket, pairs = "core", [(60, 5)]\n'
                   '    charges = [(bucket, 1)]\n'
                   '    charges.append(("content", 1))\n'
                   '    return charges\n')
        head = self.commit("shadowing")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ghg_second_top_level_assignment_still_modelled(self):
        # Straight-line rebinding at top level IS Python's semantics:
        # the last literal wins and the differ models exactly that.
        self.write("tools/ghg/ghg.py", GHG_PY.replace(
            '"search": [(60, 20)]', '"search": [(60, 99)]'))
        head = self.commit("rebind")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("search" in x and "99" in x
                            for x in d["newly_allowed"]))

    def test_ghg_complete_mutator_census_is_refused(self):
        # dict.popitem and list.insert were the census gaps Codex found
        # on PR #148; the refusal list is the full union of built-in
        # container mutators.
        self.write("tools/ghg/ghg.py",
                   GHG_PY + "\nDEFAULT_LIMITS.popitem()\n")
        head = self.commit("popitem")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2)
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\nDEFAULT_LIMITS["core"].insert(0, (60, 1))\n')
        head2 = self.commit("insert")
        r = self.run_tool("diff", head, head2)
        self.assertEqual(r.returncode, 2)

    def test_ghg_readonly_alias_is_not_refused(self):
        self.write("tools/ghg/ghg.py", GHG_PY +
                   '\n_L = DEFAULT_LIMITS\nCORE = _L["core"]\n')
        head = self.commit("alias-read")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(any("modelled power" in n for n in d["notes"]))

    def test_ghg_runtime_mutation_is_refused_exit_2(self):
        # Item assignment rewriting a cap at import time.
        self.write("tools/ghg/ghg.py",
                   GHG_PY + '\nDEFAULT_LIMITS["core"] = [(3600, 999999)]\n')
        head = self.commit("mut1")
        r = self.run_tool("diff", self.base, head)
        self.assertEqual(r.returncode, 2)
        self.assertIn("mutated at runtime", r.stderr)
        # Mutator call escaping mutating classification.
        self.write("tools/ghg/ghg.py",
                   GHG_PY + '\n_MUTATING_SUBCOMMANDS.discard("merge")\n')
        head2 = self.commit("mut2")
        r = self.run_tool("diff", head, head2)
        self.assertEqual(r.returncode, 2)
        # Augmented assignment on a classification set.
        self.write("tools/ghg/ghg.py",
                   GHG_PY + '\n_MUTATING_METHODS -= {"DELETE"}\n')
        head3 = self.commit("mut3")
        r = self.run_tool("diff", head2, head3)
        self.assertEqual(r.returncode, 2)

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

    def test_mode_gain_on_surviving_file_is_executable_grant(self):
        p = self.repo / "skills/alpha/scripts/run.sh"
        p.chmod(0o755)
        head = self.commit("chmod +x")
        r, d = self.diff(self.base, head)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("run.sh" in x and "executable bit" in x
                            for x in d["newly_allowed_executable"]))

    def test_typechange_symlink_to_executable_file_is_grant(self):
        link = self.repo / "skills/alpha/link"
        link.symlink_to("scripts/run.sh")
        git(self.repo, "add", "skills/alpha/link")
        with_link = self.commit("add symlink")
        link.unlink()
        link.write_text("#!/bin/sh\necho hi\n")
        link.chmod(0o755)
        head = self.commit("materialise")
        r, d = self.diff(with_link, head)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("link" in x
                            for x in d["newly_allowed_executable"]))

    def test_typechange_file_to_symlink_is_contraction(self):
        p = self.repo / "skills/alpha/doc.md"
        p.write_text("doc\n")
        with_file = self.commit("add doc")
        p.unlink()
        p.symlink_to("/etc/passwd")
        head = self.commit("to symlink")
        r, d = self.diff(with_file, head)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(any("doc.md" in x and "symlink" in x
                            for x in d["newly_denied"]))

    def test_mode_loss_on_surviving_file_is_contraction(self):
        p = self.repo / "skills/alpha/tool"
        p.write_text("#!/bin/sh\n")
        p.chmod(0o755)
        with_x = self.commit("add tool +x")
        p.chmod(0o644)
        head = self.commit("chmod -x")
        r, d = self.diff(with_x, head)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(any("tool" in x for x in d["newly_denied"]))

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
        # Head-binding, isolated: the second commit is delta-neutral
        # (touches no modelled artefact), so only the head SHA changes.
        # The acknowledgement must still be voided.
        head = self.escalate()
        fp = self.fingerprint(head)
        body = self.repo / "body.txt"
        body.write_text(f"policy-delta-sha256: {fp}\n")
        r = self.run_tool("check", self.base, head,
                          "--body-file", str(body))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.write("unrelated.txt", "not a modelled artefact\n")
        head2 = self.commit("neutral")
        _, d = self.diff(self.base, head2)
        self.assertEqual(len(d["newly_allowed"]), 1)  # delta unchanged
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

    # Documented corrections to the prototype's recorded counts. The
    # Phase 0 summary is evidence of the *prototype's* output and is not
    # rewritten; where the production model is demonstrably more correct
    # (checked against the artefact's own grammar/consumer), the
    # corrected expectation lives here with its reason.
    # - PR #131: the prototype's flat scope model counted
    #   'humanizer/PROVENANCE.md' as "enters sync scope" (allowed). The
    #   entry was in fact added to [exclude-paths] -- an exclusion,
    #   i.e. a denial. Correct: allowed 31, denied 1. (Class found by
    #   the Phase 1 independent review; semantics per
    #   scripts/check_skills_manifest.py.)
    CORRECTIONS = {131: {"allowed": 31, "denied": 1}}

    def test_replay_reproduces_phase0_counts(self):
        summary = json.loads(REPLAY_SUMMARY.read_text())
        self.assertEqual(len(summary), 20)
        for entry in summary:
            with self.subTest(pr=entry["pr"]):
                base = git(REPO_ROOT, "rev-parse", f"{entry['commit']}^1")
                d = self.run_diff(base, entry["commit"])
                want = self.CORRECTIONS.get(entry["pr"], entry)
                self.assertEqual(len(d["newly_allowed"]), want["allowed"])
                self.assertEqual(len(d["newly_denied"]), want["denied"])
                self.assertEqual(len(d["notes"]), len(entry["notes"]))

    def test_pr131_exclusion_classified_as_denial(self):
        base = git(REPO_ROOT, "rev-parse", "0f5b652^1")
        d = self.run_diff(base, "0f5b652")
        self.assertTrue(any("humanizer/PROVENANCE.md" in x
                            and "exclusion added" in x
                            for x in d["newly_denied"]))
        self.assertFalse(any("humanizer/PROVENANCE.md" in x
                             for x in d["newly_allowed"]))

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
