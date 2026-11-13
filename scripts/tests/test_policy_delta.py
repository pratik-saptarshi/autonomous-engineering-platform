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
