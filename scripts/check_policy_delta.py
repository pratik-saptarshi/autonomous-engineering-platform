#!/usr/bin/env python3
"""Policy power-differ -- the Phase 1 build of the OpenShell-patterns
adoption plan (docs/plans/2026-11-13-openshell-patterns-adoption-plan.html,
pattern P2 adapted; Phase 0 gate G-P2 passed, see
docs/plans/openshell-patterns-phase0/g-p2/findings.md).

Bounded claim: this tool computes a mechanical delta of *modelled* power
between two git refs over the policy-bearing artefacts AEP already diffs
by eye. It answers one question: "what does this change newly allow, and
what does it newly deny, under the stated model?" It is a differ over a
stated model of each artefact -- it is NOT formally verified, it does not
verify an implementation, and it never approves anything. The CI check
built on it fails closed until a human acknowledges the computed delta;
acknowledgement is a recorded human act, never an approval substitute
and never auto-satisfied by this tool.

Model scope (what the differ sees):

  * scripts/policy.data -- deny-sets by section ([sensitive-paths],
    [env-scrub], ...). A pattern REMOVED from a deny-set is power newly
    allowed; a pattern ADDED is newly denied.
  * tools/ghg/ghg.py -- DEFAULT_LIMITS bucket caps. Direction follows
    ghg's own semantics (classify() emits a fixed bucket set;
    Ledger.fits/reserve_all check a charge against every window of its
    bucket, and a bucket with no entry is uncapped): a cap increase or
    a new bucket (a newly routed call class) is newly allowed; a cap
    decrease or a new window (an additional constraint) is newly
    denied; removing a window or a whole bucket removes a constraint
    and is therefore newly allowed (relaxation). Plus the
    mutating-classification sets (_MUTATING_SUBCOMMANDS /
    _MUTATING_METHODS): an entry REMOVED there
    means those calls escape mutating classification (newly allowed);
    an entry ADDED is newly denied. Any other change to ghg.py is
    reported as an explicit note ("changed, modelled power unchanged")
    -- never as silence. A ghg.py that *mutates* the modelled tables at
    runtime is refused with an error instead: the differ cannot model
    runtime mutation, and reporting a literal-only delta for it would
    be a false statement, not a gap. The ghg tier is therefore a
    whitelist census: the tables (DEFAULT_LIMITS, the classification
    sets, the derived LIMITS) may be bound ONLY by their top-level
    literal/derivation declarations -- every other binding form
    (annotated, chained, nested, conditional, loop/comprehension/
    walrus targets, def/class names, imports) is refused -- and
    runtime mutation (item/augmented assignment, deletion, mutator
    calls) is refused on the tables and on their aliases, tracked
    per scope with shadow-aware resolution (names bound to a table,
    to a lookup rooted at one, to a container holding one, or to a
    local function returning one), as is passing a table to a
    function or class defined in the same file. Mutation via dynamic
    indirection (getattr/setattr/eval/globals()), via imported or
    builtin callables, or through builtin-constructor copies remains
    outside the model and is named as such in every report.
  * .github/skills-sync-scope.txt -- the governed skill set, in the
    file's own three-section grammar: [skills] entries are grants (a
    skill entering scope is newly allowed surface, leaving is newly
    denied); [exclude-paths] and [exclude-content] entries are
    exclusions, which are denials -- an exclusion REMOVED widens what
    syncs (newly allowed), an exclusion ADDED narrows it (newly
    denied).
  * skills/** -- the skill tree. A new skill directory is newly allowed
    capability surface; a removed one is newly denied; a file added to a
    surviving skill is surface expansion; a file removed is contraction.
    Added files that create *executable* surface -- anything under a
    skill's scripts/ directory, server files, start/stop hooks, files
    with the executable bit, and code files -- are additionally listed
    in newly_allowed_executable (this tier exists because the Phase 0
    replay's one real missed delta, PR #58, was exactly this: skills
    silently acquiring runnable servers and executable scripts). A
    surviving file that gains the executable bit is newly allowed
    executable surface; losing it is a contraction. A typechange is
    never silent: a symlink replaced by a regular file is surface
    expansion (executable-classified as above); a regular file
    replaced by a symlink is a contraction. SKILL.md content
    changes in surviving skills are counted in a note as not
    mechanically classifiable.

Not modelled (stated, per the plan): reachability through allowed
hosts, data-level effects of changed skill *content*, content changes
to non-SKILL.md files in surviving skills (mode and type changes ARE
modelled), renames within the skills tree (the new path is reported as
an addition; the old path is not reported as a removal), symlink
retargets in the skills tree, indirect mutation of ghg's modelled
tables via dynamic indirection (getattr/setattr/eval/globals()/vars()),
via imported/builtin callables the tables are passed to, or through
builtin-constructor copies (dict()/list()), and anything outside the
four artefacts above.

Usage:

  check_policy_delta.py diff BASE HEAD [--format json|markdown]
      Print the delta report. Exit 1 when the delta newly allows
      anything, 0 when it does not, 2 on tool error (unknown ref,
      unparsable policy artefact, git failure). Errors never exit 0:
      the gate fails closed.

  check_policy_delta.py check BASE HEAD --body-file PATH
      Fail-closed acknowledgement check for CI. Computes the delta; if
      it newly allows anything, the PR body in PATH must carry the
      acknowledgement token ``policy-delta-sha256: <fingerprint>``,
      where the fingerprint is the SHA-256 of the canonical delta
      (base/head full SHAs + sorted newly-allowed/newly-denied lists)
      as printed by the diff report. A human pastes the token after
      reading the delta; pushing new commits changes the fingerprint
      and voids the acknowledgement. Exit 0 acknowledged or nothing to
      acknowledge, 1 unacknowledged, 2 on tool error.

The tool is a pure function of two git refs plus, for check, the body
file: it writes nothing and keeps no state, so re-running it is
idempotent and a crashed run leaves nothing to recover.
"""

import argparse
import ast
import hashlib
import json
import subprocess
import sys

POLICY_DATA = "scripts/policy.data"
GHG_PY = "tools/ghg/ghg.py"
SCOPE_TXT = ".github/skills-sync-scope.txt"
SKILLS_ROOT = "skills"

MODEL_SCOPE = [
    "scripts/policy.data deny-sets (pattern removed = newly allowed, added = newly denied)",
    "tools/ghg/ghg.py DEFAULT_LIMITS caps and mutating-classification sets (runtime mutation of the modelled tables is refused, not diffed)",
    ".github/skills-sync-scope.txt sections: [skills] grants; [exclude-paths]/[exclude-content] exclusions (removal widens = newly allowed)",
    "skills/** tree grants, newly added executable surface classified separately, executable-bit changes on surviving files",
]
NOT_MODELLED = [
    "reachability through allowed hosts",
    "data-level effects of changed skill content",
    "content changes to non-SKILL.md files in surviving skills (mode and type changes are modelled)",
    "renames within the skills tree (new path reported as an addition only)",
    "symlink retargets in the skills tree",
    "indirect mutation of ghg's modelled tables via dynamic indirection (getattr/setattr/eval/globals()/vars()), via imported/builtin callables the tables are passed to, or through builtin-constructor copies (dict()/list())",
    "anything outside the four modelled artefacts",
]

CODE_SUFFIXES = {
    ".sh", ".bash", ".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl",
    ".ps1", ".bat", ".cmd", ".exe", ".jar", ".go", ".rs",
}


class DifferError(Exception):
    """A tool error: bad ref, unparsable artefact, git failure (exit 2)."""


# --------------------------------------------------------------------- git

class Repo:
    def __init__(self, root):
        if root is None:
            r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise DifferError("not inside a git repository "
                                  "(pass --repo for the repository root)")
            root = r.stdout.strip()
        self.root = root

    def _git(self, *args):
        return subprocess.run(["git", *args], capture_output=True,
                              text=True, cwd=self.root)

    def resolve(self, ref):
        r = self._git("rev-parse", "--verify", f"{ref}^{{commit}}")
        if r.returncode != 0:
            raise DifferError(f"cannot resolve ref {ref!r} to a commit")
        return r.stdout.strip()

    def show(self, sha, path):
        r = self._git("show", f"{sha}:{path}")
        return r.stdout if r.returncode == 0 else None

    def name_status(self, base, head, path):
        """[(status, old_path, new_path)] with -z parsing (rename-safe)."""
        r = self._git("diff", "--name-status", "-z", base, head, "--", path)
        if r.returncode != 0:
            raise DifferError(f"git diff failed for {path}: {r.stderr.strip()}")
        fields = r.stdout.split("\0")
        if fields and fields[-1] == "":
            fields.pop()
        out, i = [], 0
        while i < len(fields):
            status = fields[i]
            i += 1
            if status.startswith(("R", "C")):
                old, new = fields[i], fields[i + 1]
                i += 2
                out.append((status, old, new))
            else:
                out.append((status, None, fields[i]))
                i += 1
        return out

    def tree_files(self, sha, path):
        """{path: mode} for every file under path at sha ({} if absent)."""
        r = self._git("ls-tree", "-r", "-z", sha, "--", path)
        if r.returncode != 0:
            raise DifferError(f"git ls-tree failed for {path}: {r.stderr.strip()}")
        out = {}
        for entry in r.stdout.split("\0"):
            if not entry:
                continue
            meta, p = entry.split("\t", 1)
            out[p] = meta.split()[0]
        return out


# ------------------------------------------------------------ artefact models

def model_policy_data(text):
    if text is None:
        return None
    sections, cur = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1]
            sections.setdefault(cur, set())
        elif cur is None:
            raise DifferError(
                f"{POLICY_DATA}: pattern line outside any [section]: {line!r}")
        else:
            sections[cur].add(line)
    return sections


MODELLED_GHG_NAMES = ("DEFAULT_LIMITS", "_MUTATING_SUBCOMMANDS",
                      "_MUTATING_METHODS")
# Runtime-mutation watch: the three modelled tables plus LIMITS, the
# effective table ghg derives from DEFAULT_LIMITS at import time. The
# differ reads literals; a statement that rewrites any of these at
# runtime changes real power invisibly to a literal diff, so it is
# refused (exit 2), never silently diffed.
GHG_WATCH_NAMES = MODELLED_GHG_NAMES + ("LIMITS",)
# The complete union of Python's built-in container mutators
# (dict: clear/pop/popitem/setdefault/update; set: add/clear/
# difference_update/discard/intersection_update/pop/remove/
# symmetric_difference_update/update; list: append/clear/extend/
# insert/pop/remove/reverse/sort). Matched against any watched root
# regardless of the table's actual type -- over-refusal is the safe
# direction for a tripwire.
_MUTATOR_METHODS = {"add", "append", "clear", "difference_update",
                    "discard", "extend", "insert", "intersection_update",
                    "pop", "popitem", "remove", "reverse", "setdefault",
                    "sort", "symmetric_difference_update", "update",
                    # Explicit special-method spellings of the same
                    # in-place mutations (dict/list/set), plus
                    # __init__: explicitly re-invoking a container's
                    # initializer replaces its contents in place.
                    "__setitem__", "__delitem__", "__iadd__",
                    "__isub__", "__imul__", "__iand__", "__ior__",
                    "__ixor__", "__init__"}

# Read-only lookup methods whose RESULTS are references into the
# container (a bucket's cap list, a view): capturing one is safe,
# but calling the capture hands over a sub-table.
_LOOKUP_METHODS = {"get", "__getitem__", "values", "items", "keys"}


def _bound_names(target):
    """Names a binding target actually binds: plain names and
    destructured elements. Attribute/subscript targets mutate an
    object; they bind nothing."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for elt in target.elts for n in _bound_names(elt)]
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    return []


def _pattern_captures(pattern):
    """Names a match-case pattern binds: capture patterns
    (MatchAs), starred captures (MatchStar), and a mapping
    pattern's rest name (MatchMapping). Value/singleton patterns
    and class-pattern attribute names bind nothing."""
    names = []
    for sub in ast.walk(pattern):
        name = None
        if isinstance(sub, getattr(ast, "MatchAs", ())):
            name = sub.name
        elif isinstance(sub, getattr(ast, "MatchStar", ())):
            name = sub.name
        elif isinstance(sub, getattr(ast, "MatchMapping", ())):
            name = sub.rest
        if name:
            names.append(name)
    return names


_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda,
                ast.ClassDef)


def _scope_maps(tree):
    """(scope_of, scope_parent): every node's enclosing scope (the
    nearest def/class/lambda node, None for module level) and each
    scope node's own parent scope."""
    scope_of, scope_parent = {}, {}

    def rec(node, scope):
        scope_of[id(node)] = scope
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                             ast.GeneratorExp)):
            # Comprehensions are their own scope in Python: their
            # targets must not leak into (or shadow within) the
            # enclosing function. The FIRST generator's iterable is
            # evaluated in the enclosing scope; everything else --
            # targets, later iterables, conditions, the yielded
            # expression -- lives in the comprehension scope.
            scope_parent[id(node)] = scope
            for idx, g in enumerate(node.generators):
                scope_of[id(g)] = node
                rec(g.target, node)
                rec(g.iter, scope if idx == 0 else node)
                for cond in g.ifs:
                    rec(cond, node)
            if isinstance(node, ast.DictComp):
                if node.key is not None:
                    rec(node.key, node)
                rec(node.value, node)
            else:
                rec(node.elt, node)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope_parent[id(node)] = scope
            # Header expressions -- decorators, defaults, annotations
            # -- are evaluated in the ENCLOSING scope; only the body
            # lives in the function's own scope.
            for dec in node.decorator_list:
                rec(dec, scope)
            rec(node.args, scope)
            if node.returns is not None:
                rec(node.returns, scope)
            for stmt in node.body:
                rec(stmt, node)
            return
        if isinstance(node, ast.Lambda):
            scope_parent[id(node)] = scope
            rec(node.args, scope)
            rec(node.body, node)
            return
        inner = scope
        if isinstance(node, ast.ClassDef):
            scope_parent[id(node)] = scope
            inner = node
        for ch in ast.iter_child_nodes(node):
            rec(ch, inner)

    rec(tree, None)
    return scope_of, scope_parent


def ghg_binding_census(tree):
    """Whitelist census of every binding touching the ghg tables.

    Returns (definitions, is_watched, hands_over, local_defs,
    local_methods, is_strong, callee_aliases): definitions maps
    each modelled name to its accepted top-level literal Assign
    node; is_watched resolves a Name occurrence (per scope,
    shadow-aware) to whether it denotes a protected table or an
    alias of one; hands_over is the unified value/receiver
    predicate; local_defs names the functions/classes defined in
    the file and local_methods the methods of classes defined in
    the file; is_strong is is_watched restricted to table-grade
    bindings (see the strong set below); callee_aliases names
    aliases of locally defined functions and methods.

    Posture (the class-level closure for the mutation/rebinding
    escape family): a binding of a protected name -- the modelled
    tables or the derived LIMITS -- is accepted ONLY as its
    declaration form: a top-level Assign whose sole target is the
    name itself (for LIMITS, the value must be the derivation
    DictComp over DEFAULT_LIMITS). A later accepted assignment wins,
    as in Python. Every other binding form of a protected name --
    annotated, chained, nested, conditional, loop / comprehension /
    walrus target, def/class name, import, except/with binding,
    global/nonlocal declaration, deletion -- raises DifferError.
    Bindings of OTHER names to watched values (assignments, loop and
    comprehension targets over watched iterables, walrus, and
    match-pattern captures of a watched subject) are tracked
    as per-scope aliases, so mutations through them refuse in
    ghg_mutation_sites. A `del name` in a class body removes the
    class-local binding and restores the outward resolution for
    later class-body reads. Two capture channels are refused outright: a
    lambda returning a watched table, and a bound mutator method of
    a watched table captured as a value. What remains outside is
    dynamic indirection
    (getattr/setattr/eval/globals()/vars()), imported/builtin
    callables, and builtin-constructor copies -- named in the
    boundary every report carries.
    """
    protected = set(GHG_WATCH_NAMES)
    body_ids = {id(n) for n in tree.body}
    definitions = {}

    def refuse(name, node, form):
        raise DifferError(
            f"{GHG_PY}: table {name} is rebound by {form} "
            f"(line {node.lineno}) — the differ accepts only the "
            "top-level literal/derivation declarations of the ghg "
            "tables and refuses every other binding form")

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for name in (n for t in node.targets
                         for n in _bound_names(t)):
                if name not in protected:
                    continue
                accepted = (
                    id(node) in body_ids and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == name
                    and (name in MODELLED_GHG_NAMES
                         or isinstance(node.value, ast.DictComp)))
                if accepted:
                    if name in MODELLED_GHG_NAMES:
                        definitions[name] = node  # last wins
                else:
                    refuse(name, node, "an assignment")
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            for name in _bound_names(node.target):
                if name in protected:
                    refuse(name, node, "an annotated/augmented assignment")
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            for name in _bound_names(node.target):
                if name in protected:
                    refuse(name, node, "a loop target")
        elif isinstance(node, ast.comprehension):
            for name in _bound_names(node.target):
                if name in protected:
                    refuse(name, node, "a comprehension target")
        elif isinstance(node, ast.NamedExpr):
            if isinstance(node.target, ast.Name) \
                    and node.target.id in protected:
                refuse(node.target.id, node, "a walrus binding")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            if node.name in protected:
                refuse(node.name, node, "a def/class name")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                bound = a.asname or a.name.split(".")[0]
                if bound in protected:
                    refuse(bound, node, "an import")
        elif isinstance(node, ast.ExceptHandler):
            if node.name and node.name in protected:
                refuse(node.name, node, "an except binding")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                if name in protected:
                    refuse(name, node, "a global/nonlocal declaration")
        elif isinstance(node, ast.Delete):
            for t in node.targets:
                for name in _bound_names(t):
                    if name in protected:
                        refuse(name, node, "a deletion")
        elif isinstance(node, ast.withitem):
            if node.optional_vars is not None:
                for name in _bound_names(node.optional_vars):
                    if name in protected:
                        refuse(name, node, "a with binding")
        elif isinstance(node, getattr(ast, "Match", ())):
            for case in node.cases:
                for name in _pattern_captures(case.pattern):
                    if name in protected:
                        refuse(name, node, "a match-pattern capture")

    # Aliases are tracked per scope: a name means a different object
    # in every function, and name-only tracking collapses them (the
    # real ghg.py reuses `bucket`/`pairs` as unrelated locals in many
    # functions). watched holds (scope id or None for module, name).
    # Resolution is shadow-aware: a Name occurrence resolves to the
    # nearest scope that BINDS the name (any binding form, parameters
    # included), and is watched only if that binding is watched.
    scope_of, scope_parent = _scope_maps(tree)
    watched = {(None, name) for name in protected}
    comp_ids = {id(n) for n in ast.walk(tree)
                if isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp,
                                  ast.GeneratorExp))}

    declared = {}  # scope id -> {name: "global" | "nonlocal"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            s = scope_of[id(node)]
            if s is not None:
                kind = "global" if isinstance(node, ast.Global) \
                    else "nonlocal"
                for name in node.names:
                    declared.setdefault(id(s), {})[name] = kind

    def raw_scope(node):
        """The syntactic scope a binding sits in (a walrus target
        inside a comprehension climbs to the nearest enclosing
        non-comprehension scope, PEP 572)."""
        scope = scope_of[id(node)]
        if isinstance(node, ast.NamedExpr):
            while scope is not None and id(scope) in comp_ids:
                scope = scope_parent.get(id(scope))
        return scope

    # Raw bindings first, keyed syntactically; declarations then
    # redirect them to their semantic scope (final map below).
    raw_bound = {}
    raw_bindings = []  # [(raw scope node or None, name)]
    # (class scope id, name) -> [(effect pos, stmt start, stmt end,
    # guaranteed)] for every binding of the name in the class body.
    # "Guaranteed" = a direct-child simple statement of the class
    # body (assign / annotated assign / import / def / class), which
    # certainly executes; bindings nested in if/try/for/with may
    # never execute, so they can decide reads only inside their own
    # statement, never a later class-body read.
    class_bindings = {}
    _simple_forms = (ast.Assign, ast.AnnAssign, ast.Import,
                     ast.ImportFrom, ast.FunctionDef,
                     ast.AsyncFunctionDef, ast.ClassDef)
    direct_simple = {id(stmt) for n in ast.walk(tree)
                     if isinstance(n, ast.ClassDef)
                     for stmt in n.body
                     if isinstance(stmt, _simple_forms)}
    # (class scope id, name) -> [(effect pos, stmt start, stmt end,
    # guaranteed)] for every `del name` in the class body. A
    # deletion REMOVES the class-local binding: later reads fall
    # back to the enclosing scopes again, so a deletion is an event
    # in the same order-aware sequence as the bindings.
    class_deletions = {}
    direct_child = {id(stmt) for n in ast.walk(tree)
                    if isinstance(n, ast.ClassDef)
                    for stmt in n.body}

    def _end_pos(node):
        if node is None:
            return None
        if hasattr(node, "end_lineno"):
            return (node.end_lineno, node.end_col_offset)
        if hasattr(node, "lineno"):
            return (node.lineno, node.col_offset)
        return None

    def _effect_pos(node):
        """(lineno, col) at which a binding takes effect in a class
        body -- binding-form specific. Simple statements (assign,
        import, def/class names): the statement's end, since the
        RHS / header evaluates first. Compound bindings take effect
        mid-statement: a loop target after its iterable evaluates
        (before the body), a with-target after its context
        expression, an except-name after its type expression.
        ast.withitem carries no position of its own."""
        if isinstance(node, (ast.For, ast.AsyncFor)):
            return _end_pos(node.iter)
        if isinstance(node, ast.withitem):
            for part in (node.context_expr, node.optional_vars):
                pos = _end_pos(part)
                if pos is not None:
                    return pos
            return None
        if isinstance(node, ast.ExceptHandler):
            if node.type is not None:
                return _end_pos(node.type)
            return _end_pos(node)
        return _end_pos(node)

    def note_raw(scope, names, node=None):
        if names:
            raw_bound.setdefault(
                id(scope) if scope is not None else None,
                set()).update(names)
            raw_bindings.extend((scope, n) for n in names)
            if isinstance(scope, ast.ClassDef) and node is not None:
                # Class bodies execute imperatively: a read of a
                # name BEFORE the class's first binding of it takes
                # effect falls back to enclosing/global scopes,
                # unlike function scopes' static shadowing.
                eff = _effect_pos(node)
                start = (node.lineno, node.col_offset) \
                    if hasattr(node, "lineno") else None
                end = _end_pos(node)
                if eff is not None and start is not None \
                        and end is not None:
                    entry = (eff, start, end,
                             id(node) in direct_simple)
                    for n in names:
                        class_bindings.setdefault(
                            (id(scope), n), []).append(entry)

    def params_of(node):
        args = node.args
        params = [a.arg for a in (list(args.posonlyargs)
                                  + list(args.args)
                                  + list(args.kwonlyargs))]
        if args.vararg:
            params.append(args.vararg.arg)
        if args.kwarg:
            params.append(args.kwarg.arg)
        return params

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            note_raw(raw_scope(node),
                     [n for t in node.targets
                      for n in _bound_names(t)], node)
        elif isinstance(node, ast.AnnAssign):
            # A value-less annotation in a class body binds NO
            # attribute (it only records __annotations__), so reads
            # keep falling back outward. In a function it still
            # marks a static local, so only the class case skips.
            if not (node.value is None
                    and isinstance(raw_scope(node), ast.ClassDef)):
                note_raw(raw_scope(node), _bound_names(node.target),
                         node)
        elif isinstance(node, (ast.AugAssign, ast.For, ast.AsyncFor)):
            note_raw(raw_scope(node), _bound_names(node.target), node)
        elif isinstance(node, ast.comprehension):
            note_raw(raw_scope(node), _bound_names(node.target), node)
        elif isinstance(node, ast.NamedExpr):
            note_raw(raw_scope(node), _bound_names(node.target), node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            note_raw(raw_scope(node), [node.name], node)
            if not isinstance(node, ast.ClassDef):
                note_raw(node, params_of(node), node)
        elif isinstance(node, ast.Lambda):
            note_raw(node, params_of(node), node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            note_raw(raw_scope(node),
                     [a.asname or a.name.split(".")[0]
                      for a in node.names], node)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                note_raw(raw_scope(node), [node.name], node)
        elif isinstance(node, ast.withitem):
            if node.optional_vars is not None:
                note_raw(raw_scope(node),
                         _bound_names(node.optional_vars), node)
        elif isinstance(node, getattr(ast, "Match", ())):
            note_raw(raw_scope(node),
                     [n for case in node.cases
                      for n in _pattern_captures(case.pattern)], node)
        elif isinstance(node, ast.Delete):
            scope = raw_scope(node)
            if isinstance(scope, ast.ClassDef):
                names = [n for t in node.targets
                         for n in _bound_names(t)]
                eff = _effect_pos(node)
                start = (node.lineno, node.col_offset) \
                    if hasattr(node, "lineno") else None
                end = _end_pos(node)
                if names and eff is not None and start is not None \
                        and end is not None:
                    entry = (eff, start, end,
                             id(node) in direct_child)
                    for n in names:
                        class_deletions.setdefault(
                            (id(scope), n), []).append(entry)

    def nonlocal_target(from_scope, name):
        """The enclosing function scope a `nonlocal name` actually
        binds in: walk outward past comprehension and class scopes
        to the first function scope binding the name, following
        further nonlocal redirections transitively; "MODULE" if a
        global redirection intervenes, None if no scope binds it."""
        s = scope_parent.get(id(from_scope)) \
            if from_scope is not None else None
        while s is not None:
            if not isinstance(s, ast.ClassDef) \
                    and name in raw_bound.get(id(s), ()):
                kind = declared.get(id(s), {}).get(name)
                if kind == "nonlocal":
                    s = scope_parent.get(id(s))
                    continue
                if kind == "global":
                    return "MODULE"
                return s
            s = scope_parent.get(id(s))
        return None

    def final_key_of(scope, name):
        """Semantic scope key for a binding sitting in `scope`:
        declarations redirect it (global -> module, nonlocal -> the
        scope that actually binds the name)."""
        if scope is not None:
            kind = declared.get(id(scope), {}).get(name)
            if kind == "global":
                return None
            if kind == "nonlocal":
                tgt = nonlocal_target(scope, name)
                if tgt == "MODULE":
                    return None
                if tgt is not None:
                    return id(tgt)
        return id(scope) if scope is not None else None

    def binding_key(node, name):
        return final_key_of(raw_scope(node), name)

    bound_in_scope = {}
    for scope, name in raw_bindings:
        bound_in_scope.setdefault(final_key_of(scope, name),
                                  set()).add(name)

    # `strong` is the table-grade subset of `watched`: names bound
    # to a whole table or a mutable sub-table (direct aliases,
    # .values() elements, .items() value positions, parameters,
    # captures). Names bound ONLY by destructuring an iterated
    # element or by iterating .keys() are element-grade -- the
    # modelled structures make those scalars (bucket names, window
    # seconds, caps) that cannot alias a table. Mutation checks use
    # the full watched set; the call-argument check uses strong,
    # since passing a scalar to local code hands over nothing.
    strong = {(None, name) for name in protected}

    def resolve_in(name_node, table):
        # One shadow-aware walk outward. At each function scope, a
        # global/nonlocal declaration for the name redirects the
        # read (to module scope / to the scope that actually binds
        # the name); otherwise a binding in the scope decides.
        # Nearer bindings win -- a comprehension target between the
        # read and the declaring function shadows the declaration.
        # Class namespaces are not lexical scopes for enclosed code
        # (skipped), but a read in the class body itself sees them,
        # subject to execution order: a binding that certainly
        # executed (guaranteed form, or the read is inside its own
        # statement) decides alone, while a merely conditional
        # binding leaves BOTH resolutions possible -- the read is
        # watched if either the class binding or the outward
        # resolution is watched.
        def resolve(scope, first, table):
            while True:
                if scope is None:
                    return name_node.id in bound_in_scope.get(
                        None, ()) and (None, name_node.id) in table
                key = id(scope)
                if not isinstance(scope, ast.ClassDef):
                    kind = declared.get(key, {}).get(name_node.id)
                    if kind == "global":
                        return (None, name_node.id) in table
                    if kind == "nonlocal":
                        tgt = nonlocal_target(scope, name_node.id)
                        if tgt == "MODULE":
                            return (None, name_node.id) in table
                        if tgt is not None:
                            return (id(tgt), name_node.id) in table
                    if name_node.id in bound_in_scope.get(key, ()):
                        return (key, name_node.id) in table
                elif first \
                        and name_node.id in bound_in_scope.get(
                            key, ()):
                    rp = (name_node.lineno, name_node.col_offset)
                    entries = class_bindings.get((key, name_node.id),
                                                  ())
                    # Bindings and deletions form one event
                    # sequence: the LATEST event that certainly
                    # took effect before the read decides. A
                    # guaranteed deletion removes the class
                    # binding, so the read resolves outward alone;
                    # a merely conditional deletion leaves both
                    # resolutions possible (disjunctive).
                    events = [(eff, st, en, guar, True)
                              for eff, st, en, guar in entries]
                    events += [(eff, st, en, guar, False)
                               for eff, st, en, guar in
                               class_deletions.get(
                                   (key, name_node.id), ())]
                    decisive = [e for e in events
                                if e[0] <= rp and (rp <= e[2] or e[3])]
                    if decisive:
                        latest = max(decisive, key=lambda e: e[0])
                        # A conditional event AFTER the latest
                        # decisive one may or may not have executed,
                        # so the state at the read is uncertain
                        # again -- both resolutions stay possible.
                        if any(e[0] > latest[0] and e[0] <= rp
                               for e in events
                               if e not in decisive):
                            return (key, name_node.id) in table \
                                or resolve(scope_parent.get(key),
                                           False, table)
                        if latest[4]:
                            return (key, name_node.id) in table
                        if latest[3]:
                            return resolve(scope_parent.get(key),
                                           False, table)
                        return (key, name_node.id) in table or \
                            resolve(scope_parent.get(key), False, table)
                    if events:
                        return (key, name_node.id) in table or \
                            resolve(scope_parent.get(key), False, table)
                    return (key, name_node.id) in table
                scope = scope_parent.get(key)
                first = False

        return resolve(scope_of[id(name_node)], True, table)

    def is_watched(name_node):
        return resolve_in(name_node, watched)

    def is_strong(name_node):
        return resolve_in(name_node, strong)

    def param_defaults(node):
        """[(param name, default expr)] for a def/lambda node."""
        args = node.args
        positional = list(args.posonlyargs) + list(args.args)
        pairs = [(a.arg, d) for a, d in
                 zip(positional[len(positional) - len(args.defaults):],
                     args.defaults)]
        pairs += [(a.arg, d) for a, d in zip(args.kwonlyargs,
                                             args.kw_defaults)
                  if d is not None]
        return pairs

    # One fixpoint over ALL propagation channels at once -- bindings,
    # function returns, and parameter defaults. Computing any channel
    # in a separate earlier pass misses chains that cross channels
    # (a function returning an assignment alias; a default capturing
    # a table the parameter then shadows).
    returning = set()
    returning_aliases = set()
    lookup_aliases = set()
    # View kinds for lookup captures of view methods
    # (name -> "items"/"keys"/"values"); conflicts drop out.
    lookup_kinds = {}
    lookup_kind_conflicts = set()

    def _value_leaves(v):
        """Leaf values of a binding value through the
        value-transparent wrappers (conditional branches, boolean
        operands, walrus)."""
        if isinstance(v, ast.IfExp):
            yield from _value_leaves(v.body)
            yield from _value_leaves(v.orelse)
        elif isinstance(v, ast.BoolOp):
            for x in v.values:
                yield from _value_leaves(x)
        elif isinstance(v, ast.NamedExpr):
            yield from _value_leaves(v.value)
        else:
            yield v

    # Locally defined properties: property name -> ALL getter
    # nodes with that name across local classes (same-named
    # properties in different classes are distinct getters; an
    # attribute access may reach any of them), from @property
    # decorators and `name = property(fget)` assignments in
    # class bodies. property_returns (filled by the fixpoint)
    # holds the names with a table-handing-over getter -- an
    # attribute access with such a name may yield the table.
    property_getters = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            funcs = {sub.name: sub for sub in node.body
                     if isinstance(sub, (ast.FunctionDef,
                                         ast.AsyncFunctionDef))}
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef,
                                    ast.AsyncFunctionDef)):
                    for dec in sub.decorator_list:
                        if isinstance(dec, ast.Name) \
                                and dec.id == "property":
                            property_getters.setdefault(
                                sub.name, []).append(sub)
                elif isinstance(sub, ast.Assign) and any(
                        isinstance(l, ast.Call)
                        and isinstance(l.func, ast.Name)
                        and l.func.id == "property"
                        and l.args
                        and isinstance(l.args[0], ast.Name)
                        and l.args[0].id in funcs
                        for l in _value_leaves(sub.value)):
                    for t in sub.targets:
                        for n in _bound_names(t):
                            for l in _value_leaves(sub.value):
                                if isinstance(l, ast.Call) \
                                        and isinstance(l.func, ast.Name) \
                                        and l.func.id == "property" \
                                        and l.args \
                                        and isinstance(l.args[0], ast.Name) \
                                        and l.args[0].id in funcs:
                                    property_getters.setdefault(
                                        n, []).append(
                                            funcs[l.args[0].id])
    property_returns = set()
    # The direct subset of property_returns: every table-carrying
    # return of the getter preserves the structural shape. Only
    # direct properties are structural sources.
    property_direct = set()

    # Attribute names bound to watched values in a locally
    # defined class body: the class (and its instances) expose
    # the table through the attribute, so an attribute access
    # with such a name denotes the table.
    class_table_attrs = set()
    # The direct subset of returning: the return/yield expressions
    # denote the table or a sub-table THEMSELVES (structural
    # shape), not a fresh container holding one. Only direct
    # callees are structural sources for callers.
    returning_direct = set()
    returning_direct_aliases = set()
    # View provenance for callees: function name -> the view kind
    # ("items"/"keys"/"values") when its returns are views of that
    # kind (conflicting returns drop the record).
    returning_views = {}
    returning_view_conflicts = set()

    # View provenance for names: a name bound to a table's
    # .items()/.keys()/.values() view keeps the view's kind when
    # it is later iterated (conflicting bindings drop the record).
    view_kinds = {}
    _view_conflicts = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            _v, _ts = node.value, node.targets
        elif isinstance(node, ast.AnnAssign) \
                and node.value is not None:
            _v, _ts = node.value, [node.target]
        else:
            continue
        if isinstance(_v, ast.Call) \
                and isinstance(_v.func, ast.Attribute) \
                and _v.func.attr in ("items", "keys", "values"):
            for t in _ts:
                for n in _bound_names(t):
                    if n in view_kinds \
                            and view_kinds[n] != _v.func.attr:
                        _view_conflicts.add(n)
                    else:
                        view_kinds[n] = _v.func.attr
    for n in _view_conflicts:
        view_kinds.pop(n, None)

    # Locally defined context managers: class name -> its
    # __enter__ method, for the classes whose __enter__ returns a
    # watched table (enter_returning, filled by the fixpoint).
    enter_of = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef,
                                    ast.AsyncFunctionDef)) \
                        and sub.name == "__enter__":
                    enter_of[id(sub)] = node.name
    enter_returning = set()
    instance_names = set()

    # Locally defined class inventory (name-resolved bases and
    # direct __call__ presence), shared by the enter closure in
    # the fixpoint and the callable-class census after it.
    _class_bases = {}
    _class_has_call = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef):
            _class_has_call[n.name] = any(
                isinstance(sub, (ast.FunctionDef,
                                 ast.AsyncFunctionDef))
                and sub.name == "__call__" for sub in n.body)
            _class_bases[n.name] = [b.id for b in n.bases
                                    if isinstance(b, ast.Name)]
    # Classes implementing __call__ directly or through a locally
    # defined base: their instances are locally defined callees.
    callable_classes = {name for name, has in _class_has_call.items()
                        if has}
    _cc = True
    while _cc:
        _cc = False
        for _name, _bases in _class_bases.items():
            if _name not in callable_classes \
                    and any(b in callable_classes for b in _bases):
                callable_classes.add(_name)
                _cc = True
    # __call__ implementations per class (own body only), and a
    # resolver walking locally defined bases.
    _own_call = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef):
            for sub in n.body:
                if isinstance(sub, (ast.FunctionDef,
                                    ast.AsyncFunctionDef)) \
                        and sub.name == "__call__":
                    _own_call[n.name] = sub

    def _call_defs(cls):
        seen, out, stack = set(), [], [cls]
        while stack:
            c = stack.pop()
            if c in seen:
                continue
            seen.add(c)
            if c in _own_call:
                out.append(_own_call[c])
            stack.extend(_class_bases.get(c, ()))
        return out

    # Classes whose __call__ hands over a table, and names bound
    # to their instances (filled by the fixpoint).
    call_returning_classes = set()
    instance_returning_names = set()

    # Name inventories for the factory census: definitions,
    # methods, and lambda-bound names in this file.
    def_names = {n.name for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef,
                                   ast.AsyncFunctionDef, ast.ClassDef))}
    method_names = {sub.name for n in ast.walk(tree)
                    if isinstance(n, ast.ClassDef)
                    for sub in n.body
                    if isinstance(sub, (ast.FunctionDef,
                                        ast.AsyncFunctionDef))}
    lambda_names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            _v, _ts = n.value, n.targets
        elif isinstance(n, ast.AnnAssign) and n.value is not None:
            _v, _ts = n.value, [n.target]
        elif isinstance(n, ast.NamedExpr):
            _v, _ts = n.value, [n.target]
        else:
            continue
        if any(isinstance(l, ast.Lambda)
               for l in _value_leaves(_v)):
            for t in _ts:
                lambda_names.update(_bound_names(t))
    # Functions returning a locally defined callee (factories),
    # filled by the fixpoint.
    returning_callables = set()

    def _callee_value(v):
        if isinstance(v, (ast.IfExp, ast.BoolOp, ast.NamedExpr)):
            return any(_callee_value(leaf)
                       for leaf in _value_leaves(v))
        if isinstance(v, ast.Name):
            return v.id in def_names or v.id in lambda_names \
                or v.id in returning_callables
        if isinstance(v, ast.Attribute):
            return v.attr in method_names
        if isinstance(v, ast.Lambda):
            return True
        if isinstance(v, ast.Call):
            return isinstance(v.func, ast.Name) \
                and v.func.id in callable_classes
        return False

    # Names bound (anywhere) to a fresh container -- a literal, a
    # comprehension, or a container BinOp -- or to another such
    # name. A fresh container can wrap the table itself as an
    # element, so aliases of one are not structural sources even
    # though they are plain names.
    def _fresh_container(v):
        if isinstance(v, (ast.List, ast.Tuple, ast.Set, ast.Dict,
                          ast.ListComp, ast.SetComp, ast.DictComp,
                          ast.GeneratorExp, ast.BinOp)):
            return True
        if isinstance(v, ast.IfExp):
            return _fresh_container(v.body) \
                or _fresh_container(v.orelse)
        if isinstance(v, ast.NamedExpr):
            return _fresh_container(v.value)
        return False

    def _may_wrap(v):
        """The value may yield a fresh container: a fresh
        container itself, or one obtained through subscript /
        attribute layers over a fresh container."""
        if _fresh_container(v):
            return True
        if isinstance(v, (ast.Subscript, ast.Attribute)):
            return _may_wrap(v.value)
        if isinstance(v, ast.Starred):
            return _may_wrap(v.value)
        if isinstance(v, ast.BoolOp):
            return any(_may_wrap(x) for x in v.values)
        if isinstance(v, ast.Await):
            return _may_wrap(v.value)
        return False

    def _core_of(v):
        while isinstance(v, (ast.Subscript, ast.Attribute)):
            v = v.value
        return v

    def _layers_tainted(v, tainted_attrs):
        """Any attribute layer of the value carries a tainted
        name (a wrapper class attribute, or a non-direct
        table-carrying property)."""
        while isinstance(v, (ast.Subscript, ast.Attribute)):
            if isinstance(v, ast.Attribute) \
                    and v.attr in tainted_attrs:
                return True
            v = v.value
        return False

    wrapper_names = set()
    _taint = True
    while _taint:
        _taint = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value, targets = node.value, node.targets
            elif isinstance(node, ast.AnnAssign) \
                    and node.value is not None:
                value, targets = node.value, [node.target]
            elif isinstance(node, ast.NamedExpr):
                value, targets = node.value, [node.target]
            else:
                continue
            if _may_wrap(value) \
                    or _layers_tainted(value, wrapper_names) \
                    or (isinstance(_core_of(value), ast.Name)
                        and _core_of(value).id in wrapper_names):
                for t in targets:
                    for n in _bound_names(t):
                        # The protected tables are themselves
                        # literals -- they are the model, never a
                        # wrapper around it.
                        if n not in wrapper_names \
                                and n not in protected:
                            wrapper_names.add(n)
                            _taint = True

    def structural_source(v):
        """The iteration source has the modelled tables' own shape:
        a table/sub-table access chain, its .items()/.values()/
        .keys() views, or a call to a function returning one -- so
        the shapes of its elements are known. A fresh container
        (literal, BinOp, comprehension, other calls) can wrap the
        table itself as an element and is NOT structural."""
        while isinstance(v, (ast.Subscript, ast.Attribute)):
            if isinstance(v, ast.Attribute) \
                    and v.attr in wrapper_names:
                # The attribute itself is the wrapper-tainted
                # binding (a class attribute holding a wrapper),
                # whatever the receiver's provenance.
                return False
            if isinstance(v, ast.Attribute) \
                    and v.attr in property_returns:
                # A property access's shape is its getter's:
                # structural only when the getter is direct.
                return v.attr in property_direct
            v = v.value
        if isinstance(v, ast.Name):
            return v.id not in wrapper_names
        if isinstance(v, ast.Call):
            if isinstance(v.func, ast.Attribute) \
                    and v.func.attr in ("items", "values", "keys"):
                return structural_source(v.func.value)
            if isinstance(v.func, ast.Name) \
                    and (v.func.id in returning_direct
                         or v.func.id in returning_direct_aliases):
                return True
        return False

    def hands_over(value):
        """The expression hands over (denotes) a watched table --
        ONE predicate for value positions and mutation receivers,
        recursing once per sub-expression. Strip lookup layers
        (subscripts, attributes, method calls on the chain); what
        remains decides: a watched name, a call to a local function
        known to return one, or a value-transparent form carrying
        one -- a conditional's branches, a boolean operand, a
        starred element, an await, a container's elements, or a
        comprehension's yielded value (element references survive a
        pass-through comprehension; a transforming yield like
        list(pairs) is a copy and does not propagate). Plain calls
        are NOT transparent: they produce new objects."""
        expr = value
        while True:
            if isinstance(expr, ast.Attribute) \
                    and (expr.attr in property_returns
                         or expr.attr in class_table_attrs):
                # A locally defined property whose getter hands
                # over a table, or a class attribute bound to one:
                # the attribute access itself IS the table,
                # whatever the receiver.
                return True
            if isinstance(expr, (ast.Subscript, ast.Attribute)):
                expr = expr.value
            elif isinstance(expr, ast.Call) \
                    and isinstance(expr.func, ast.Attribute):
                if expr.func.attr in returning:
                    # A locally defined method returning a table:
                    # the call's result IS the table, not a method
                    # result computed on the receiver.
                    return True
                expr = expr.func.value
            else:
                break
        if isinstance(expr, ast.Name):
            return is_watched(expr)
        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Name):
                return expr.func.id in returning \
                    or expr.func.id in returning_aliases \
                    or expr.func.id in lookup_aliases \
                    or expr.func.id in instance_returning_names
            if isinstance(expr.func, ast.Call) \
                    and isinstance(expr.func.func, ast.Name):
                # A fresh instance of a class whose __call__
                # hands over a table, invoked immediately.
                return expr.func.func.id in call_returning_classes
            if isinstance(expr.func, (ast.IfExp, ast.BoolOp,
                                      ast.NamedExpr)):
                # A callee selected through a conditional /
                # boolean / walrus wrapper: the call hands over
                # a table if ANY alternative callee would --
                # re-ask the same question with each leaf as
                # the callee, so Name, Attribute, and
                # constructor alternatives all get the direct
                # forms' answer (a None alternative answers
                # False, as its direct form does).
                return any(hands_over(ast.Call(func=leaf, args=[],
                                               keywords=[]))
                           for leaf in _value_leaves(expr.func))
            return False
        if isinstance(expr, (ast.ListComp, ast.SetComp,
                             ast.GeneratorExp)):
            return hands_over(expr.elt)
        if isinstance(expr, ast.DictComp):
            # Only the value expression carries yielded objects (a
            # watched table is unhashable and can never be a key).
            return hands_over(expr.value)
        if isinstance(expr, ast.NamedExpr):
            return hands_over(expr.value)
        if isinstance(expr, ast.IfExp):
            return hands_over(expr.body) or hands_over(expr.orelse)
        if isinstance(expr, ast.BoolOp):
            return any(hands_over(v) for v in expr.values)
        if isinstance(expr, ast.Starred):
            return hands_over(expr.value)
        if isinstance(expr, ast.BinOp) \
                and isinstance(expr.op, (ast.Add, ast.Mult,
                                         ast.BitOr)):
            # Container concatenation, repetition, and dict merge
            # build a new container holding the SAME element
            # objects -- references survive, unlike a constructor
            # copy (dict()/list()), so aliasing propagates.
            return hands_over(expr.left) or hands_over(expr.right)
        if isinstance(expr, ast.Await):
            return hands_over(expr.value)
        if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
            return any(hands_over(e) for e in expr.elts)
        if isinstance(expr, ast.Dict):
            return any(hands_over(e) for e in
                       list(expr.keys) + list(expr.values)
                       if e is not None)
        return False

    def _view_kinds_of(v):
        """The set of view kinds an expression may yield: a
        direct view call, a name carrying a view kind, a call to
        a view-returning callee, or the union over conditional /
        boolean branches. Empty = no view provenance; more than
        one = conflicting provenance."""
        if isinstance(v, ast.Call) \
                and isinstance(v.func, ast.Attribute) \
                and v.func.attr in ("items", "keys", "values"):
            return {v.func.attr}
        if isinstance(v, ast.Name):
            k = view_kinds.get(v.id) or lookup_kinds.get(v.id)
            return {k} if k else set()
        if isinstance(v, ast.Call):
            if isinstance(v.func, ast.Name):
                k = returning_views.get(v.func.id) \
                    or lookup_kinds.get(v.func.id)
                return {k} if k else set()
            if isinstance(v.func, ast.Attribute):
                k = returning_views.get(v.func.attr)
                return {k} if k else set()
            if isinstance(v.func, (ast.IfExp, ast.BoolOp,
                                   ast.NamedExpr)):
                # A callee selected through a conditional /
                # boolean / walrus wrapper: the result's view
                # kinds are the union over the alternative
                # callees -- re-ask the same question with each
                # leaf as the callee, so Name, Attribute, and
                # other alternatives all get the direct forms'
                # answer (a None alternative contributes no
                # kind, as its direct form does; differing
                # kinds union to a conflict for the consumers).
                out = set()
                for leaf in _value_leaves(v.func):
                    out |= _view_kinds_of(
                        ast.Call(func=leaf, args=[], keywords=[]))
                return out
            return set()
        if isinstance(v, ast.IfExp):
            return _view_kinds_of(v.body) \
                | _view_kinds_of(v.orelse)
        if isinstance(v, ast.BoolOp):
            out = set()
            for x in v.values:
                out |= _view_kinds_of(x)
            return out
        if isinstance(v, ast.NamedExpr):
            return _view_kinds_of(v.value)
        return set()

    def _value_taints(v):
        """A binding to this value is wrapper-tainted: some
        value-transparent path through it reaches a wrapper (a
        tainted attribute layer, a tainted core name, or a
        returning-but-not-direct callee)."""
        if _layers_tainted(
                v, wrapper_names
                | (property_returns - property_direct)):
            return True
        core = _core_of(v)
        if isinstance(core, ast.Name):
            return core.id in wrapper_names
        if isinstance(core, ast.Call):
            f = core.func
            if isinstance(f, ast.Name):
                return (f.id in returning
                        or f.id in returning_aliases) \
                    and f.id not in returning_direct \
                    and f.id not in returning_direct_aliases
            if isinstance(f, ast.Attribute):
                return f.attr in returning \
                    and f.attr not in returning_direct
            if isinstance(f, (ast.IfExp, ast.BoolOp,
                              ast.NamedExpr)):
                # A callee selected through a conditional /
                # boolean / walrus wrapper: the binding is
                # tainted if ANY alternative callee's result
                # would taint it -- re-ask the same question
                # with each leaf as the callee, so Name,
                # Attribute, and other alternatives all get
                # the direct forms' answer (a None alternative
                # answers False, as its direct form does).
                return any(_value_taints(
                    ast.Call(func=leaf, args=[], keywords=[]))
                    for leaf in _value_leaves(f))
            return False
        for w in (v, core):
            if isinstance(w, ast.BoolOp):
                if any(_value_taints(x) for x in w.values):
                    return True
            elif isinstance(w, ast.IfExp):
                if _value_taints(w.body) \
                        or _value_taints(w.orelse):
                    return True
            elif isinstance(w, (ast.Starred, ast.Await,
                                ast.NamedExpr)):
                if _value_taints(w.value):
                    return True
        return False

    changed = True
    _guard = 0
    while changed:
        _guard += 1
        if _guard > 200:
            # Directness oscillation on a pathological call
            # graph: fall back to no direct callees (the
            # conservative direction -- destructured results of
            # calls stay table-grade).
            returning_direct.clear()
            returning_direct_aliases.clear()
            break
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_enter = id(node) in enter_of
                hits = []
                for sub in ast.walk(node):
                    if isinstance(sub, (ast.Return, ast.Yield,
                                        ast.YieldFrom)) \
                            and sub.value is not None \
                            and hands_over(sub.value):
                        hits.append(sub)
                        if node.name not in returning:
                            returning.add(node.name)
                            changed = True
                        if isinstance(sub, ast.Return):
                            # Conflict markers follow returns, as
                            # they follow bindings (the binding
                            # pass below): a returned leaf whose
                            # view kind already conflicted -- a
                            # name with a dropped kind, or a call
                            # to a conflicted callee -- marks this
                            # function conflicted, since
                            # _view_kinds_of yields no kind for it.
                            _leaf_conflict = False
                            for _leaf in _value_leaves(sub.value):
                                if isinstance(_leaf, ast.Name):
                                    _leaf_conflict = (
                                        _leaf.id in _view_conflicts
                                        or _leaf.id
                                        in returning_view_conflicts
                                        or _leaf.id
                                        in lookup_kind_conflicts)
                                elif isinstance(_leaf, ast.Call):
                                    if isinstance(_leaf.func,
                                                  ast.Name):
                                        _leaf_conflict = \
                                            _leaf.func.id \
                                            in \
                                            returning_view_conflicts
                                    elif isinstance(_leaf.func,
                                                    ast.Attribute):
                                        _leaf_conflict = \
                                            _leaf.func.attr \
                                            in \
                                            returning_view_conflicts
                                if _leaf_conflict:
                                    break
                            _kinds = _view_kinds_of(sub.value)
                            if _leaf_conflict:
                                if node.name not in \
                                        returning_view_conflicts:
                                    returning_view_conflicts.add(
                                        node.name)
                                    changed = True
                                returning_views.pop(node.name,
                                                    None)
                                _kinds = set()
                            if len(_kinds) > 1:
                                returning_view_conflicts.add(
                                    node.name)
                                returning_views.pop(node.name, None)
                                _kinds = set()
                            kind = next(iter(_kinds), None)
                            if kind is not None \
                                    and node.name \
                                    not in \
                                    returning_view_conflicts:
                                if node.name in returning_views \
                                        and returning_views[
                                                node.name] != kind:
                                    returning_view_conflicts.add(
                                        node.name)
                                    returning_views.pop(
                                        node.name, None)
                                elif node.name not in \
                                        returning_views:
                                    returning_views[node.name] \
                                        = kind
                                    changed = True
                            if is_enter \
                                    and enter_of[id(node)] \
                                    not in enter_returning:
                                enter_returning.add(
                                    enter_of[id(node)])
                                changed = True
                # Directness is an ALL-returns property: one
                # wrapper-shaped return revokes it, whenever in
                # the fixpoint that return becomes visible.
                if hits:
                    direct = all(structural_source(s.value)
                                 for s in hits)
                    if direct \
                            and node.name not in returning_direct:
                        returning_direct.add(node.name)
                        changed = True
                    elif not direct \
                            and node.name in returning_direct:
                        returning_direct.discard(node.name)
                        changed = True
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value, targets = node.value, node.targets
            elif isinstance(node, ast.AnnAssign) \
                    and node.value is not None:
                value, targets = node.value, [node.target]
            elif isinstance(node, ast.NamedExpr):
                value, targets = node.value, [node.target]
            else:
                continue
            _leaves = list(_value_leaves(value))
            if any((isinstance(l, ast.Name)
                    and (l.id in returning
                         or l.id in returning_aliases))
                   or (isinstance(l, ast.Attribute)
                       and l.attr in returning)
                   for l in _leaves):
                for t in targets:
                    for n in _bound_names(t):
                        if n not in returning_aliases:
                            returning_aliases.add(n)
                            changed = True
            # Directness is stricter than returning status: the
            # alias is direct only if EVERY leaf is direct (it
            # may resolve to any of them).
            if _leaves and all(
                    (isinstance(l, ast.Name)
                     and (l.id in returning_direct
                          or l.id in returning_direct_aliases))
                    or (isinstance(l, ast.Attribute)
                        and l.attr in returning_direct)
                    for l in _leaves):
                for t in targets:
                    for n in _bound_names(t):
                        if n not in returning_direct_aliases:
                            returning_direct_aliases.add(n)
                            changed = True
            if any((isinstance(l, ast.Name)
                    and l.id in returning_callables)
                   or (isinstance(l, ast.Attribute)
                       and l.attr in returning_callables)
                   for l in _leaves):
                for t in targets:
                    for n in _bound_names(t):
                        if n not in returning_callables:
                            returning_callables.add(n)
                            changed = True
            _src_names = []
            if isinstance(value, ast.Name):
                _src_names = [value.id]
            elif isinstance(value, ast.Attribute):
                _src_names = [value.attr]
            for _sn in _src_names:
                if _sn in returning_views \
                        and _sn not in returning_view_conflicts:
                    for t in targets:
                        for n in _bound_names(t):
                            if n not in returning_views:
                                returning_views[n] = \
                                    returning_views[_sn]
                                changed = True
            if isinstance(value, (ast.IfExp, ast.BoolOp,
                                  ast.NamedExpr)):
                _src_names = []
                for leaf in _value_leaves(value):
                    if isinstance(leaf, ast.Name):
                        _src_names.append(leaf.id)
                    elif isinstance(leaf, ast.Attribute):
                        _src_names.append(leaf.attr)
                _kinds = {returning_views[_sn] for _sn in _src_names
                          if _sn in returning_views
                          and _sn not in returning_view_conflicts}
                _conflicted = any(_sn in returning_view_conflicts
                                  for _sn in _src_names)
                if _conflicted or len(_kinds) > 1:
                    for t in targets:
                        for n in _bound_names(t):
                            if n not in returning_view_conflicts:
                                returning_view_conflicts.add(n)
                                changed = True
                elif _kinds:
                    _kind = next(iter(_kinds))
                    for t in targets:
                        for n in _bound_names(t):
                            if n not in returning_views:
                                returning_views[n] = _kind
                                changed = True
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value, targets = node.value, node.targets
            elif isinstance(node, ast.AnnAssign) \
                    and node.value is not None:
                value, targets = node.value, [node.target]
            elif isinstance(node, ast.NamedExpr):
                value, targets = node.value, [node.target]
            else:
                continue
            _leaves = list(_value_leaves(value))
            if any((isinstance(l, ast.Attribute)
                    and l.attr in _LOOKUP_METHODS
                    and hands_over(l.value))
                   or (isinstance(l, ast.Name)
                       and l.id in lookup_aliases)
                   for l in _leaves):
                for t in targets:
                    for n in _bound_names(t):
                        if n not in lookup_aliases:
                            lookup_aliases.add(n)
                            changed = True
            # View-kind bookkeeping for view-method captures
            # and their alias chains.
            _leaf_kinds = []
            for l in _leaves:
                if isinstance(l, ast.Attribute) \
                        and l.attr in ("items", "keys", "values") \
                        and hands_over(l.value):
                    _k = l.attr
                elif isinstance(l, ast.Name) \
                        and l.id in lookup_kinds:
                    _k = lookup_kinds[l.id]
                else:
                    continue
                if _k not in _leaf_kinds:
                    _leaf_kinds.append(_k)
            for _kind in _leaf_kinds:
                for t in targets:
                    for n in _bound_names(t):
                        if n in lookup_kind_conflicts:
                            continue
                        if n in lookup_kinds \
                                and lookup_kinds[n] != _kind:
                            lookup_kind_conflicts.add(n)
                            lookup_kinds.pop(n, None)
                            changed = True
                        elif n not in lookup_kinds:
                            lookup_kinds[n] = _kind
                            changed = True
        for node in ast.walk(tree):
            # Wrapper provenance through call results: a name
            # bound to the result of a returning-but-not-direct
            # callee (or to another wrapper-tainted name) is
            # wrapper-tainted. Taint is sticky -- a callee not yet
            # proven direct taints conservatively.
            if isinstance(node, ast.Assign):
                value, targets = node.value, node.targets
            elif isinstance(node, ast.AnnAssign) \
                    and node.value is not None:
                value, targets = node.value, [node.target]
            elif isinstance(node, ast.NamedExpr):
                value, targets = node.value, [node.target]
            else:
                continue
            if _value_taints(value):
                for t in targets:
                    for n in _bound_names(t):
                        if n not in wrapper_names \
                                and n not in protected:
                            wrapper_names.add(n)
                            changed = True
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # All class-level statements, including those
                # nested in compound statements (if/try/for/...)
                # -- but not the bodies of methods or nested
                # classes, which are their own scopes.
                stack = list(node.body)
                while stack:
                    sub = stack.pop()
                    if isinstance(sub, (ast.FunctionDef,
                                        ast.AsyncFunctionDef,
                                        ast.ClassDef, ast.Lambda)):
                        continue
                    stack.extend(ast.iter_child_nodes(sub))
                    if isinstance(sub, ast.Assign):
                        _v, _ts = sub.value, sub.targets
                    elif isinstance(sub, ast.AnnAssign) \
                            and sub.value is not None:
                        _v, _ts = sub.value, [sub.target]
                    elif isinstance(sub, (ast.For, ast.AsyncFor)):
                        _v, _ts = sub.iter, [sub.target]
                    else:
                        continue
                    if hands_over(_v):
                        for t in _ts:
                            for n in _bound_names(t):
                                if n not in class_table_attrs:
                                    class_table_attrs.add(n)
                                    changed = True
        for prop, getters in property_getters.items():
            # An access may reach ANY same-named getter: the
            # property hands over a table if any getter does,
            # and it is direct only if every table-carrying
            # getter is structural.
            any_hits = False
            direct_ok = True
            for getter in getters:
                hits = [sub.value for sub in ast.walk(getter)
                        if isinstance(sub, ast.Return)
                        and sub.value is not None
                        and hands_over(sub.value)]
                if hits:
                    any_hits = True
                    if not all(structural_source(v) for v in hits):
                        direct_ok = False
            if any_hits:
                if prop not in property_returns:
                    property_returns.add(prop)
                    changed = True
                if direct_ok:
                    if prop not in property_direct:
                        property_direct.add(prop)
                        changed = True
                elif prop in property_direct:
                    property_direct.discard(prop)
                    changed = True
        for cls in list(_class_bases) + list(_own_call):
            if cls not in call_returning_classes:
                for d in _call_defs(cls):
                    if any(isinstance(s, ast.Return)
                           and s.value is not None
                           and hands_over(s.value)
                           for s in ast.walk(d)):
                        call_returning_classes.add(cls)
                        changed = True
                        break
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value, targets = node.value, node.targets
            elif isinstance(node, ast.AnnAssign) \
                    and node.value is not None:
                value, targets = node.value, [node.target]
            elif isinstance(node, ast.NamedExpr):
                value, targets = node.value, [node.target]
            else:
                continue
            if any((isinstance(l, ast.Call)
                    and isinstance(l.func, ast.Name)
                    and l.func.id in call_returning_classes)
                   or (isinstance(l, ast.Name)
                       and l.id in instance_returning_names)
                   for l in _value_leaves(value)):
                for t in targets:
                    for n in _bound_names(t):
                        if n not in instance_returning_names:
                            instance_returning_names.add(n)
                            changed = True
        for node in ast.walk(tree):
            # View kinds follow bindings: a name bound to a
            # view-yielding expression (a direct view call, a
            # view-carrying name, or a view-returning call)
            # carries the kind, with conflicts dropping out.
            if isinstance(node, ast.Assign):
                value, targets = node.value, node.targets
            elif isinstance(node, ast.AnnAssign) \
                    and node.value is not None:
                value, targets = node.value, [node.target]
            elif isinstance(node, ast.NamedExpr):
                value, targets = node.value, [node.target]
            else:
                continue
            # Conflict markers propagate through bindings: a
            # name bound to a conflicted source is itself
            # conflicted (its kind is already dropped there).
            _src_conflict = False
            if isinstance(value, ast.Name):
                _src_conflict = (
                    value.id in _view_conflicts
                    or value.id in returning_view_conflicts
                    or value.id in lookup_kind_conflicts)
            elif isinstance(value, ast.Call):
                if isinstance(value.func, ast.Name):
                    _src_conflict = value.func.id \
                        in returning_view_conflicts
                elif isinstance(value.func, ast.Attribute):
                    _src_conflict = value.func.attr \
                        in returning_view_conflicts
            _src_returning = isinstance(value, ast.Name) \
                and value.id in returning_view_conflicts
            if isinstance(value, (ast.IfExp, ast.BoolOp,
                                  ast.NamedExpr)):
                # A source selected through a conditional /
                # boolean / walrus wrapper: generalise both
                # tests over the wrapper's leaves, each leaf
                # getting its direct form's answer above (a
                # Name leaf tests the three conflict sets; a
                # Call leaf tests its callee; an Attribute
                # leaf has no source case, as a plain
                # Attribute source does not).
                # _src_returning stays the narrower test,
                # computed independently of _src_conflict:
                # only a Name leaf in
                # returning_view_conflicts -- a Call leaf
                # binds a result, not a callable alias, and
                # gains no returning marker.
                _leaves = list(_value_leaves(value))
                _src_conflict = _src_conflict or any(
                    (isinstance(leaf, ast.Name) and (
                        leaf.id in _view_conflicts
                        or leaf.id in returning_view_conflicts
                        or leaf.id in lookup_kind_conflicts))
                    or (isinstance(leaf, ast.Call) and (
                        (isinstance(leaf.func, ast.Name)
                         and leaf.func.id
                         in returning_view_conflicts)
                        or (isinstance(leaf.func, ast.Attribute)
                            and leaf.func.attr
                            in returning_view_conflicts)))
                    for leaf in _leaves)
                _src_returning = _src_returning or any(
                    isinstance(leaf, ast.Name)
                    and leaf.id in returning_view_conflicts
                    for leaf in _leaves)
            if _src_conflict:
                for t in targets:
                    for n in _bound_names(t):
                        if n not in _view_conflicts:
                            _view_conflicts.add(n)
                            view_kinds.pop(n, None)
                            changed = True
                        if _src_returning \
                                and n not in \
                                returning_view_conflicts:
                            # A callable alias of a
                            # view-conflicted function carries
                            # the conflict in callee position
                            # too: the call-source check
                            # consults only
                            # returning_view_conflicts for a
                            # callee name, never
                            # _view_conflicts. The
                            # _view_conflicts deposit above
                            # (name position) is unchanged.
                            returning_view_conflicts.add(n)
                            changed = True
                continue
            _kinds = _view_kinds_of(value)
            if len(_kinds) > 1:
                for t in targets:
                    for n in _bound_names(t):
                        if n not in _view_conflicts:
                            _view_conflicts.add(n)
                            view_kinds.pop(n, None)
                            changed = True
            elif _kinds:
                kind = next(iter(_kinds))
                for t in targets:
                    for n in _bound_names(t):
                        if n in _view_conflicts:
                            continue
                        if n in view_kinds \
                                and view_kinds[n] != kind:
                            _view_conflicts.add(n)
                            view_kinds.pop(n, None)
                            changed = True
                        elif n not in view_kinds:
                            view_kinds[n] = kind
                            changed = True
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef,
                                 ast.AsyncFunctionDef)) \
                    and node.name not in returning_callables:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) \
                            and sub.value is not None \
                            and _callee_value(sub.value):
                        returning_callables.add(node.name)
                        changed = True
                        break
        # Enter provenance closes over locally defined bases: a
        # subclass of a table-returning context manager is one.
        for _name, _bases in _class_bases.items():
            if _name not in enter_returning \
                    and any(b in enter_returning for b in _bases):
                enter_returning.add(_name)
                changed = True
        for node in ast.walk(tree):
            _v, _ts = None, ()
            if isinstance(node, ast.Assign):
                _v, _ts = node.value, node.targets
            elif isinstance(node, ast.AnnAssign) \
                    and node.value is not None:
                _v, _ts = node.value, [node.target]
            elif isinstance(node, ast.NamedExpr):
                _v, _ts = node.value, [node.target]
            if _v is not None \
                    and any((isinstance(l, ast.Call)
                             and isinstance(l.func, ast.Name)
                             and l.func.id in enter_returning)
                            or (isinstance(l, ast.Name)
                                and l.id in instance_names)
                            for l in _value_leaves(_v)):
                for t in _ts:
                    for n in _bound_names(t):
                        if n not in instance_names:
                            instance_names.add(n)
                            changed = True
            if isinstance(node, ast.withitem) \
                    and node.optional_vars is not None:
                ctx = node.context_expr
                hit = any((isinstance(l, ast.Call)
                           and isinstance(l.func, ast.Name)
                           and l.func.id in enter_returning)
                          or (isinstance(l, ast.Name)
                              and l.id in instance_names)
                          for l in _value_leaves(ctx))
                if hit:
                    for n in _bound_names(node.optional_vars):
                        key = binding_key(node, n)
                        if (key, n) not in watched:
                            watched.add((key, n))
                            strong.add((key, n))
                            changed = True
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.Lambda)):
                for param, default in param_defaults(node):
                    if hands_over(default) \
                            and (id(node), param) not in watched:
                        watched.add((id(node), param))
                        strong.add((id(node), param))
                        changed = True
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value, targets = node.value, node.targets
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                value, targets = node.value, [node.target]
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                value, targets = node.iter, [node.target]
            elif isinstance(node, ast.comprehension):
                value, targets = node.iter, [node.target]
            elif isinstance(node, ast.NamedExpr):
                value, targets = node.value, [node.target]
            elif isinstance(node, getattr(ast, "Match", ())):
                # A case capture binds the matched subject (or a
                # sub-value of it -- a bucket's cap list is itself
                # mutable), so every capture name in every case is
                # an alias when the subject hands over a table.
                if hands_over(node.subject):
                    for case in node.cases:
                        for n in _pattern_captures(case.pattern):
                            key = binding_key(node, n)
                            if (key, n) not in watched:
                                watched.add((key, n))
                                strong.add((key, n))
                                changed = True
                continue
            else:
                continue
            # Element-grade (weak) names for this binding: targets
            # destructured out of an iterated element, and targets
            # iterating .keys() -- both bind scalars of the modelled
            # structures, never a table or sub-table. The exemption
            # applies only to STRUCTURAL sources (the tables' own
            # access chains and views): a fresh wrapper container
            # can yield the table itself as an element, so its
            # destructured components stay table-grade.
            weak = set()
            # A source whose view kind is conflicted (bound to
            # views of different kinds) has no provably scalar
            # component: every candidate kind has a table-grade
            # position, so no component takes the exemption.
            _conflicted = False
            if isinstance(value, ast.Name):
                _conflicted = (
                    value.id in _view_conflicts
                    or value.id in returning_view_conflicts
                    or value.id in lookup_kind_conflicts)
            elif isinstance(value, ast.Call):
                if isinstance(value.func, ast.Name):
                    _conflicted = value.func.id \
                        in returning_view_conflicts
                elif isinstance(value.func, ast.Attribute):
                    _conflicted = value.func.attr \
                        in returning_view_conflicts
            if isinstance(node, (ast.For, ast.AsyncFor,
                                 ast.comprehension)) \
                    and structural_source(value) \
                    and not _conflicted:
                src_attr = None
                if isinstance(value, ast.Call) \
                        and isinstance(value.func, ast.Attribute):
                    src_attr = value.func.attr \
                        if value.func.attr in ("items", "keys",
                                               "values") \
                        else returning_views.get(value.func.attr)
                elif isinstance(value, ast.Call) \
                        and isinstance(value.func, ast.Name):
                    src_attr = returning_views.get(value.func.id)
                elif isinstance(value, ast.Name):
                    src_attr = view_kinds.get(value.id)
                for t in targets:
                    if isinstance(t, (ast.Tuple, ast.List)):
                        if src_attr == "items" and len(t.elts) >= 2:
                            weak.update(_bound_names(t.elts[0]))
                        else:
                            weak.update(_bound_names(t))
                    elif src_attr == "keys":
                        weak.update(_bound_names(t))
            if hands_over(value):
                for t in targets:
                    for n in _bound_names(t):
                        key = binding_key(node, n)
                        if (key, n) not in watched:
                            watched.add((key, n))
                            changed = True
                        if n not in weak \
                                and (key, n) not in strong:
                            strong.add((key, n))
                            changed = True
    # Two capture channels are refused outright rather than tracked:
    # a lambda returning a watched table (an anonymous callable the
    # name-based returning set cannot see), and a bound mutator
    # method captured as a value (`_clear = DEFAULT_LIMITS.clear`),
    # whose later invocation is an unrecognizable bare-name call.
    # Refusing at the capture point closes both channels; read-only
    # method captures (.get/.items) and lambdas returning copies or
    # unrelated values are unaffected.
    call_funcs = {id(n.func) for n in ast.walk(tree)
                  if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda) and hands_over(node.body):
            raise DifferError(
                f"{GHG_PY}: a lambda returns a modelled table "
                f"(line {node.lineno}) — anonymous callables are "
                "outside the census and are refused")
        if isinstance(node, ast.Attribute) \
                and node.attr in _MUTATOR_METHODS \
                and id(node) not in call_funcs \
                and hands_over(node.value):
            raise DifferError(
                f"{GHG_PY}: mutator method .{node.attr} of a modelled "
                f"table is captured as a value (line {node.lineno}) — "
                "bound-method aliases are outside the census and are "
                "refused")
    local_defs = {n.name for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                    ast.ClassDef))}
    # Method names of classes defined in this file: a call through
    # an attribute (`_Uncap.run(table)`) reaches code defined here
    # just as a bare-name call does.
    local_methods = {sub.name for n in ast.walk(tree)
                     if isinstance(n, ast.ClassDef)
                     for sub in n.body
                     if isinstance(sub, (ast.FunctionDef,
                                         ast.AsyncFunctionDef))}
    # (callable_classes is computed before the fixpoint, above.)
    # Aliases of locally defined callees (`_run = _uncap`,
    # `_run = _Uncap.run`): invoking through the alias reaches
    # local code exactly as invoking the definition does.
    callee_aliases = set()
    def _container_has_callee(v):
        """A literal container holds a local callee among its
        elements/values (through nested literal layers)."""
        if isinstance(v, (ast.List, ast.Tuple, ast.Set)):
            return any(_is_callee_form(leaf)
                       for e in v.elts
                       for leaf in _value_leaves(e))
        if isinstance(v, ast.Dict):
            return any(_is_callee_form(leaf)
                       for e in v.values if e is not None
                       for leaf in _value_leaves(e))
        if isinstance(v, ast.Subscript):
            return _container_has_callee(v.value)
        if isinstance(v, ast.IfExp):
            return _container_has_callee(v.body) \
                or _container_has_callee(v.orelse)
        return False

    def _is_callee_form(value):
        if isinstance(value, ast.Subscript):
            # Selecting from a literal container of callees
            # yields a callee.
            return _container_has_callee(value.value)
        return isinstance(value, ast.Lambda) \
            or (isinstance(value, ast.Name)
                and (value.id in local_defs
                     or value.id in callee_aliases)) \
            or (isinstance(value, ast.Attribute)
                and value.attr in local_methods) \
            or (isinstance(value, ast.Call)
                and ((isinstance(value.func, ast.Name)
                      and (value.func.id in callable_classes
                           or value.func.id
                           in returning_callables))
                     or (isinstance(value.func, ast.Attribute)
                         and value.func.attr
                         in returning_callables)))

    _alias = True
    while _alias:
        _alias = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value, targets = node.value, node.targets
            elif isinstance(node, ast.AnnAssign) \
                    and node.value is not None:
                value, targets = node.value, [node.target]
            elif isinstance(node, ast.NamedExpr):
                value, targets = node.value, [node.target]
            else:
                continue
            if any(_is_callee_form(leaf)
                   for leaf in _value_leaves(value)):
                for t in targets:
                    for n in _bound_names(t):
                        if n not in callee_aliases:
                            callee_aliases.add(n)
                            _alias = True
    def _callee_form_any(v):
        """The leaf-aware callee predicate handed to the
        mutation-site check: a value is a local callee form if
        any leaf through the value-transparent wrappers is."""
        return any(_is_callee_form(leaf)
                   for leaf in _value_leaves(v))

    return definitions, is_watched, hands_over, local_defs, \
        local_methods, is_strong, callee_aliases, callable_classes, \
        returning_callables, _callee_form_any


def ghg_mutation_sites(tree, is_watched, hands_over, local_defs,
                       local_methods=(), is_strong=None,
                       callee_aliases=(), callable_classes=(),
                       returning_callables=(), is_callee_form=None):
    """[(lineno, description)] for runtime mutations of watched tables:
    item/augmented assignment, deletion, and mutator calls on a
    watched table or any alias of one (aliases resolve per scope;
    receivers may also be calls to functions returning a table), and
    a watched table passed to a function or class defined IN this
    file (the callee can mutate it; the differ cannot rule it out,
    so it refuses). Passing a table to an imported or builtin
    callable (list(), json.dumps(), sorted(), ...) is ordinary
    read/copy use in this file's style and is named in the boundary
    instead. Read-only aliasing and read-only method calls on the
    tables (.get/.items/iteration) are not sites."""

    def hands_over_strong(expr):
        """The expression hands over a table-grade reference: a
        table or mutable sub-table itself, as opposed to a
        container that merely holds watched scalars (a list of
        window dicts built from iterated keys is watched, but
        storing or passing it hands over no table)."""
        if isinstance(expr, ast.Name):
            return is_strong(expr) if is_strong is not None \
                else hands_over(expr)
        if isinstance(expr, ast.Subscript):
            return hands_over_strong(expr.value)
        if isinstance(expr, ast.Attribute):
            # An attribute access is table-grade when the access
            # itself yields a table (property / class-attribute
            # provenance, inside hands_over) or its root is one.
            return hands_over(expr)
        if isinstance(expr, ast.Call):
            return hands_over(expr)
        if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
            return any(hands_over_strong(e) for e in expr.elts)
        if isinstance(expr, ast.Dict):
            return any(hands_over_strong(e) for e in
                       list(expr.keys) + list(expr.values)
                       if e is not None)
        if isinstance(expr, ast.Starred):
            return hands_over_strong(expr.value)
        if isinstance(expr, ast.BinOp) \
                and isinstance(expr.op, (ast.Add, ast.Mult,
                                         ast.BitOr)):
            return hands_over_strong(expr.left) \
                or hands_over_strong(expr.right)
        if isinstance(expr, ast.IfExp):
            return hands_over_strong(expr.body) \
                or hands_over_strong(expr.orelse)
        if isinstance(expr, ast.BoolOp):
            return any(hands_over_strong(v) for v in expr.values)
        if isinstance(expr, ast.Await):
            return hands_over_strong(expr.value)
        if isinstance(expr, ast.NamedExpr):
            return hands_over_strong(expr.value)
        if isinstance(expr, (ast.ListComp, ast.SetComp,
                             ast.GeneratorExp)):
            return hands_over_strong(expr.elt)
        if isinstance(expr, ast.DictComp):
            return hands_over_strong(expr.value)
        return False

    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            if hands_over(node.value):
                sites.append((node.lineno, "item assignment"))
        elif isinstance(node, ast.AugAssign):
            target = node.target
            if (isinstance(target, ast.Name) and is_watched(target)) \
                    or (isinstance(target, ast.Subscript)
                        and hands_over(target.value)):
                sites.append((node.lineno, "augmented assignment"))
        elif isinstance(node, ast.Delete):
            for t in node.targets:
                if (isinstance(t, ast.Name) and is_watched(t)) or \
                        (isinstance(t, ast.Subscript)
                         and hands_over(t.value)):
                    sites.append((node.lineno, "deletion"))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) \
                and node.value is not None:
            # Storing a table-grade value through a subscript or
            # attribute target creates an alias inside a container
            # the census does not track (the target binds no name).
            # Stores into a watched container are already the item
            # assignment site above.
            targets = node.targets if isinstance(node, ast.Assign) \
                else [node.target]
            for t in targets:
                stored = False
                for sub in ast.walk(t):
                    if isinstance(sub, (ast.Subscript, ast.Attribute)) \
                            and isinstance(sub.ctx, ast.Store):
                        root = sub
                        while isinstance(root, (ast.Subscript,
                                                ast.Attribute)):
                            root = root.value
                        if not hands_over(root) \
                                and hands_over_strong(node.value):
                            sites.append(
                                (node.lineno,
                                 "watched value stored into a container"))
                            stored = True
                            break
                if stored:
                    break
        elif isinstance(node, ast.Call):
            # The mutator and local-definition checks are
            # independent: a locally defined method may itself be
            # named like a container mutator, and either check can
            # be the one that fires.
            args = list(node.args) + [kw.value for kw in node.keywords]
            desc = None
            if isinstance(node.func, ast.Attribute) \
                    and node.func.attr in _MUTATOR_METHODS:
                if hands_over(node.func.value):
                    desc = f".{node.func.attr}() call"
                elif any(hands_over_strong(a) for a in args):
                    desc = "watched value stored into a container"
            if desc is None \
                    and ((isinstance(node.func, ast.Name)
                          and (node.func.id in local_defs
                               or node.func.id in callee_aliases))
                         or (isinstance(node.func, ast.Attribute)
                             and node.func.attr in local_methods)
                         or isinstance(node.func, ast.Lambda)
                         or (isinstance(node.func, ast.Call)
                             and isinstance(node.func.func, ast.Name)
                             and (node.func.func.id
                                  in callable_classes
                                  or node.func.func.id
                                  in returning_callables))
                         or (isinstance(node.func, ast.Subscript)
                             and is_callee_form is not None
                             and is_callee_form(node.func))
                         or (isinstance(node.func, (ast.IfExp,
                                                   ast.BoolOp))
                             and is_callee_form is not None
                             and is_callee_form(node.func))):
                if any(hands_over_strong(a) for a in args):
                    desc = "modelled table passed as a call argument"
            if desc is not None:
                sites.append((node.lineno, desc))
    return sites


def model_ghg(text):
    if text is None:
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise DifferError(f"{GHG_PY}: unparsable Python ({e})") from e
    definitions, is_watched, hands_over, local_defs, \
        local_methods, is_strong, callee_aliases, \
        callable_classes, returning_callables, is_callee_form = \
        ghg_binding_census(tree)
    sites = ghg_mutation_sites(tree, is_watched, hands_over,
                               local_defs, local_methods, is_strong,
                               callee_aliases, callable_classes,
                               returning_callables, is_callee_form)
    if sites:
        detail = "; ".join(f"line {ln}: {desc}" for ln, desc in sites[:5])
        raise DifferError(
            f"{GHG_PY}: modelled power is mutated at runtime ({detail}) — "
            "the differ cannot model runtime mutation and refuses rather "
            "than reporting a literal-only delta")
    found = {}
    for name, node in definitions.items():
        try:
            found[name] = ast.literal_eval(node.value)
        except (ValueError, SyntaxError) as e:
            raise DifferError(
                f"{GHG_PY}: {name} is not a literal ({e})") from e
    missing = set(MODELLED_GHG_NAMES) - set(found)
    if missing:
        raise DifferError(
            f"{GHG_PY}: modelled names missing at this ref: "
            f"{', '.join(sorted(missing))}")
    return {
        "limits": {k: [tuple(p) for p in v]
                   for k, v in found["DEFAULT_LIMITS"].items()},
        "mutating_subcommands": set(found["_MUTATING_SUBCOMMANDS"]),
        "mutating_methods": set(found["_MUTATING_METHODS"]),
    }


SCOPE_SECTIONS = ("skills", "exclude-paths", "exclude-content")


def model_scope(text):
    """Section -> entry set, in the scope file's own grammar (or None)."""
    if text is None:
        return None
    sections, cur = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1].strip()
            if cur not in SCOPE_SECTIONS:
                raise DifferError(
                    f"{SCOPE_TXT}: unknown section [{cur}] "
                    f"(grammar is: {', '.join(SCOPE_SECTIONS)})")
            sections.setdefault(cur, set())
        elif cur is None:
            raise DifferError(
                f"{SCOPE_TXT}: entry outside any [section]: {line!r}")
        else:
            sections[cur].add(line)
    return sections


# ------------------------------------------------------------------- diffing

def diff_policy(base, head):
    newly_allowed, newly_denied = [], []
    if base is None and head is None:
        return newly_allowed, newly_denied, []
    if base is None:
        return [], [], ["policy.data created (whole deny-set is new; "
                        "no prior power baseline)"]
    if head is None:
        for sec, pats in sorted(base.items()):
            newly_allowed += [
                f"policy.data[{sec}] deny pattern removed (file deleted): {p}"
                for p in sorted(pats)]
        return newly_allowed, newly_denied, []
    for sec in sorted(set(base) | set(head)):
        b, h = base.get(sec, set()), head.get(sec, set())
        newly_allowed += [
            f"policy.data[{sec}]: deny pattern removed -> newly allowed: {p}"
            for p in sorted(b - h)]
        newly_denied += [
            f"policy.data[{sec}]: deny pattern added -> newly denied: {p}"
            for p in sorted(h - b)]
    return newly_allowed, newly_denied, []


def _effective_caps(pairs):
    """window -> effective cap. ghg enforces EVERY (window, cap)
    pair conjunctively (Ledger.fits / reserve_all iterate the whole
    list), so when a duration appears more than once the MINIMUM
    cap is the binding constraint. Collapsing pairs with dict()
    (last wins) would silently drop the strictest cap."""
    out = {}
    for w, c in pairs:
        out[w] = min(out[w], c) if w in out else c
    return out


def diff_ghg(base, head, base_text, head_text):
    newly_allowed, newly_denied, notes = [], [], []
    if base is None and head is None:
        return newly_allowed, newly_denied, notes
    if base is None:
        return [], [], ["ghg.py created (whole gateway is new; "
                        "no prior power baseline)"]
    if head is None:
        raise DifferError(f"{GHG_PY}: present at base but deleted at head; "
                          "gateway removal is outside the differ's model")
    if base_text != head_text and base == head:
        notes.append("ghg.py changed but modelled power "
                     "(caps + classification) unchanged")
    bl, hl = base["limits"], head["limits"]
    for bucket in sorted(set(bl) | set(hl)):
        if bucket not in bl:
            newly_allowed.append(
                f"ghg caps: NEW bucket '{bucket}' {hl[bucket]} "
                "-> newly allowed call class")
            continue
        if bucket not in hl:
            # classify() emits a fixed bucket set; a bucket with no
            # limits entry is checked against zero windows, i.e. it is
            # uncapped. Removing the entry relaxes, it does not deny.
            newly_allowed.append(
                f"ghg caps: bucket '{bucket}' removed -> calls in it "
                "are now uncapped -> newly allowed (constraint removed)")
            continue
        bmap, hmap = _effective_caps(bl[bucket]), \
            _effective_caps(hl[bucket])
        for w in sorted(set(bmap) | set(hmap)):
            # Windows are a conjunction of constraints (Ledger.fits /
            # reserve_all iterate the window list; a missing window
            # imposes no cap). Adding one tightens; removing one
            # relaxes -- the reverse of the grant direction.
            if w not in bmap:
                newly_denied.append(
                    f"ghg caps: bucket '{bucket}' new window {w}s "
                    f"cap {hmap[w]} -> newly denied (additional constraint)")
            elif w not in hmap:
                newly_allowed.append(
                    f"ghg caps: bucket '{bucket}' window {w}s removed "
                    "-> newly allowed (constraint removed)")
            elif hmap[w] > bmap[w]:
                newly_allowed.append(
                    f"ghg caps: bucket '{bucket}' window {w}s cap "
                    f"{bmap[w]} -> {hmap[w]} -> newly allowed volume")
            elif hmap[w] < bmap[w]:
                newly_denied.append(
                    f"ghg caps: bucket '{bucket}' window {w}s cap "
                    f"{bmap[w]} -> {hmap[w]} -> newly denied volume")
    for key, label in (("mutating_subcommands", "subcommand"),
                       ("mutating_methods", "method")):
        for item in sorted(base[key] - head[key]):
            newly_allowed.append(
                f"ghg classify: '{item}' leaves mutating {label} set "
                "-> newly allowed (escapes mutating classification)")
        for item in sorted(head[key] - base[key]):
            newly_denied.append(
                f"ghg classify: '{item}' joins mutating {label} set "
                "-> newly denied (now classified mutating)")
    return newly_allowed, newly_denied, notes


def diff_scope(base, head):
    if base is None and head is None:
        return [], [], []
    if base is None:
        return [], [], ["skills-sync-scope.txt created "
                        "(whole scope set is new)"]
    if head is None:
        raise DifferError(f"{SCOPE_TXT}: present at base but deleted at "
                          "head; scope removal is outside the differ's model")
    newly_allowed, newly_denied = [], []
    b, h = base.get("skills", set()), head.get("skills", set())
    newly_allowed += [f"skills scope: '{s}' enters sync scope "
                      "-> newly allowed surface" for s in sorted(h - b)]
    newly_denied += [f"skills scope: '{s}' leaves sync scope "
                     "-> newly denied surface" for s in sorted(b - h)]
    # Exclusion sections are denials: removing one widens what syncs.
    for sec in ("exclude-paths", "exclude-content"):
        b, h = base.get(sec, set()), head.get(sec, set())
        newly_allowed += [
            f"skills scope: [{sec}] exclusion removed: '{e}' "
            "-> newly allowed (more content becomes sync-eligible)"
            for e in sorted(b - h)]
        newly_denied += [
            f"skills scope: [{sec}] exclusion added: '{e}' "
            "-> newly denied (content excluded from sync)"
            for e in sorted(h - b)]
    return newly_allowed, newly_denied, []


def executable_reasons(path, mode):
    """Why an added skills/** file is executable surface ([] if it is not)."""
    parts = path.split("/")
    base = parts[-1]
    reasons = []
    if mode == "100755":
        reasons.append("executable bit set")
    if "scripts" in parts[:-1]:
        reasons.append("skill scripts/ directory")
    if base.startswith(("start-", "start_", "stop-", "stop_")):
        reasons.append("start/stop hook")
    if "server" in base:
        reasons.append("server file")
    suffix = "." + base.rsplit(".", 1)[-1] if "." in base else ""
    if suffix in CODE_SUFFIXES:
        reasons.append(f"code file ({suffix})")
    return reasons


def diff_skills(repo, base_sha, head_sha):
    newly_allowed, newly_denied, executable, notes = [], [], [], []
    changes = repo.name_status(base_sha, head_sha, SKILLS_ROOT)
    base_files = repo.tree_files(base_sha, SKILLS_ROOT)
    head_files = repo.tree_files(head_sha, SKILLS_ROOT)

    def by_skill(files):
        out = {}
        for p in files:
            parts = p.split("/")
            if len(parts) >= 2:
                out.setdefault(parts[1], set()).add(p)
        return out

    base_skills, head_skills = by_skill(base_files), by_skill(head_files)
    for skill in sorted(set(head_skills) - set(base_skills)):
        item = (f"skills: NEW skill '{skill}' "
                f"({len(head_skills[skill])} files) "
                "-> newly allowed capability surface")
        ex = [p for p in sorted(head_skills[skill])
              if executable_reasons(p, head_files[p])]
        if ex:
            item += (f" [executable surface: {len(ex)} file(s), e.g. "
                     f"{ex[0].split('/', 2)[-1]}]")
            executable.append(item)
        newly_allowed.append(item)
    for skill in sorted(set(base_skills) - set(head_skills)):
        newly_denied.append(f"skills: skill '{skill}' removed "
                            "-> newly denied capability surface")
    modified_skillmd = 0
    for status, _old, path in changes:
        parts = path.split("/")
        if len(parts) < 2:
            continue
        skill = parts[1]
        if skill not in base_skills or skill not in head_skills:
            continue  # whole-skill add/remove already reported above
        if status == "A" or status.startswith(("R", "C")):
            item = (f"skills: file added to existing skill '{skill}': "
                    f"{path} -> surface expansion")
            reasons = executable_reasons(path, head_files.get(path, "100644"))
            if reasons:
                item += f" [executable surface: {'; '.join(reasons)}]"
                executable.append(item)
            newly_allowed.append(item)
        elif status == "D":
            newly_denied.append(
                f"skills: file removed from existing skill '{skill}': "
                f"{path} -> surface contraction")
        elif status.startswith("T"):
            # Typechange (symlink <-> regular file): never silent -- a
            # materialised regular file is new in-tree surface, and a
            # file replaced by a symlink removes in-tree content.
            head_mode = head_files.get(path, "100644")
            if head_mode == "120000":
                newly_denied.append(
                    f"skills: file replaced by symlink in skill "
                    f"'{skill}': {path} -> surface contraction "
                    "(in-tree content removed)")
            else:
                item = (f"skills: symlink replaced by regular file in "
                        f"skill '{skill}': {path} -> surface expansion")
                reasons = executable_reasons(path, head_mode)
                if reasons:
                    item += (f" [executable surface: "
                             f"{'; '.join(reasons)}]")
                    executable.append(item)
                newly_allowed.append(item)
        elif status.startswith("M") and path.endswith("SKILL.md"):
            modified_skillmd += 1
    # Executable-bit changes on surviving files are grants/contractions
    # in their own right (a chmod +x has no content change to catch).
    for path in sorted(set(base_files) & set(head_files)):
        bm, hm = base_files[path], head_files[path]
        if bm == hm or "120000" in (bm, hm):
            continue
        parts = path.split("/")
        if len(parts) < 2:
            continue
        skill = parts[1]
        if skill not in base_skills or skill not in head_skills:
            continue
        if bm == "100644" and hm == "100755":
            item = (f"skills: file gains executable bit in skill "
                    f"'{skill}': {path} -> newly allowed executable surface")
            newly_allowed.append(item)
            executable.append(item)
        elif bm == "100755" and hm == "100644":
            newly_denied.append(
                f"skills: file loses executable bit in skill '{skill}': "
                f"{path} -> surface contraction")
    if modified_skillmd:
        notes.append(f"{modified_skillmd} SKILL.md content change(s) in "
                     "surviving skills — not mechanically classifiable "
                     "as grant/denial by this model")
    return newly_allowed, newly_denied, executable, notes


def compute_delta(repo, base_ref, head_ref):
    base_sha, head_sha = repo.resolve(base_ref), repo.resolve(head_ref)
    pd_b = model_policy_data(repo.show(base_sha, POLICY_DATA))
    pd_h = model_policy_data(repo.show(head_sha, POLICY_DATA))
    gh_b_text = repo.show(base_sha, GHG_PY)
    gh_h_text = repo.show(head_sha, GHG_PY)
    gh_b, gh_h = model_ghg(gh_b_text), model_ghg(gh_h_text)
    sc_b = model_scope(repo.show(base_sha, SCOPE_TXT))
    sc_h = model_scope(repo.show(head_sha, SCOPE_TXT))
    a1, d1, n1 = diff_policy(pd_b, pd_h)
    a2, d2, n2 = diff_ghg(gh_b, gh_h, gh_b_text, gh_h_text)
    a3, d3, n3 = diff_scope(sc_b, sc_h)
    a4, d4, e4, n4 = diff_skills(repo, base_sha, head_sha)
    return {
        "base": base_sha,
        "head": head_sha,
        "newly_allowed": a1 + a2 + a3 + a4,
        "newly_denied": d1 + d2 + d3 + d4,
        "newly_allowed_executable": e4,
        "notes": n1 + n2 + n3 + n4,
        "model_scope": MODEL_SCOPE,
        "not_modelled": NOT_MODELLED,
    }


def fingerprint(delta):
    canonical = json.dumps(
        {"base": delta["base"], "head": delta["head"],
         "newly_allowed": delta["newly_allowed"],
         "newly_denied": delta["newly_denied"]},
        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ reporting

def render_json(delta):
    return json.dumps(delta, indent=1, sort_keys=True) + "\n"


def render_markdown(delta):
    fp = fingerprint(delta)
    lines = [
        "## Policy delta (machine-generated)",
        "",
        f"Base: `{delta['base'][:12]}`  Head: `{delta['head'][:12]}`",
        "",
        "Computed by `scripts/check_policy_delta.py`. This report states "
        "what the change newly allows and newly denies under the differ's "
        "model. It is not an approval and does not verify an implementation.",
        "",
        "### Model covers",
        "",
    ]
    lines += [f"- {s}" for s in delta["model_scope"]]
    lines += ["", "### Model does not cover", ""]
    lines += [f"- {s}" for s in delta["not_modelled"]]
    lines += ["", "### Newly allowed", ""]
    if delta["newly_allowed"]:
        ex = set(delta["newly_allowed_executable"])
        for item in delta["newly_allowed"]:
            lines.append(f"- {item}" + (" **[executable surface]**"
                                         if item in ex else ""))
    else:
        lines.append("- (none)")
    lines += ["", "### Newly denied", ""]
    if delta["newly_denied"]:
        lines += [f"- {item}" for item in delta["newly_denied"]]
    else:
        lines.append("- (none)")
    if delta["notes"]:
        lines += ["", "### Notes", ""]
        lines += [f"- {n}" for n in delta["notes"]]
    lines += [
        "",
        "### Proposal block (human completes)",
        "",
        "Newly allowed: (summarised above)",
        "Why: ",
        "Expiry / review date: ",
        "",
        "Acknowledgement: a human who has read this delta records it by "
        "placing this token in the PR body (new commits void it):",
        "",
        f"policy-delta-sha256: {fp}",
        "",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Mechanical power delta over AEP's policy artefacts "
                    "between two git refs.")
    ap.add_argument("--repo", default=None,
                    help="repository root (default: discovered from cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_diff = sub.add_parser("diff", help="print the delta report")
    p_diff.add_argument("base")
    p_diff.add_argument("head")
    p_diff.add_argument("--format", choices=("json", "markdown"),
                        default="json")
    p_check = sub.add_parser(
        "check", help="fail-closed acknowledgement check (CI)")
    p_check.add_argument("base")
    p_check.add_argument("head")
    p_check.add_argument("--body-file", required=True,
                         help="file containing the PR body to search for "
                              "the acknowledgement token")
    args = ap.parse_args(argv)

    try:
        repo = Repo(args.repo)
        if args.cmd == "diff":
            delta = compute_delta(repo, args.base, args.head)
            sys.stdout.write(render_json(delta) if args.format == "json"
                             else render_markdown(delta))
            return 1 if delta["newly_allowed"] else 0
        # check
        delta = compute_delta(repo, args.base, args.head)
        if not delta["newly_allowed"]:
            print("policy-delta check: no newly allowed power; "
                  "nothing to acknowledge.")
            return 0
        try:
            with open(args.body_file, encoding="utf-8") as f:
                body = f.read()
        except OSError as e:
            raise DifferError(f"cannot read --body-file: {e}") from e
        fp = fingerprint(delta)
        if f"policy-delta-sha256: {fp}" in body:
            print(f"policy-delta check: delta acknowledged "
                  f"(policy-delta-sha256: {fp}).")
            return 0
        print("policy-delta check: FAIL — this change newly allows "
              f"{len(delta['newly_allowed'])} item(s) and the PR body "
              "does not acknowledge the computed delta.\n"
              "Read the machine-generated policy delta report, then add "
              "this token to the PR body:\n"
              f"policy-delta-sha256: {fp}",
              file=sys.stderr)
        return 1
    except DifferError as e:
        print(f"check_policy_delta: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # Downstream consumer closed the pipe (e.g. `| head`): exit
        # quietly with the family's error code rather than a traceback.
        try:
            sys.stdout.close()
        except OSError:
            pass
        sys.exit(2)
