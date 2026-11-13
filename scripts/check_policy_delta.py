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
                    "sort", "symmetric_difference_update", "update"}


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

    Returns (definitions, is_watched, hands_over, local_defs):
    definitions maps each modelled name to its accepted top-level
    literal Assign node; is_watched resolves a Name occurrence (per
    scope, shadow-aware) to whether it denotes a protected table or
    an alias of one; hands_over is the unified value/receiver
    predicate; local_defs names the functions/classes defined in
    the file.

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
    comprehension targets over watched iterables, walrus) are tracked
    as per-scope aliases, so mutations through them refuse in
    ghg_mutation_sites. Two capture channels are refused outright: a
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

    def is_watched(name_node):
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
        def resolve(scope, first):
            while True:
                if scope is None:
                    return name_node.id in bound_in_scope.get(
                        None, ()) and (None, name_node.id) in watched
                key = id(scope)
                if not isinstance(scope, ast.ClassDef):
                    kind = declared.get(key, {}).get(name_node.id)
                    if kind == "global":
                        return (None, name_node.id) in watched
                    if kind == "nonlocal":
                        tgt = nonlocal_target(scope, name_node.id)
                        if tgt == "MODULE":
                            return (None, name_node.id) in watched
                        if tgt is not None:
                            return (id(tgt), name_node.id) in watched
                    if name_node.id in bound_in_scope.get(key, ()):
                        return (key, name_node.id) in watched
                elif first \
                        and name_node.id in bound_in_scope.get(
                            key, ()):
                    rp = (name_node.lineno, name_node.col_offset)
                    entries = class_bindings.get((key, name_node.id),
                                                  ())
                    if any(eff <= rp and (rp <= en or guar)
                           for eff, st, en, guar in entries):
                        return (key, name_node.id) in watched
                    if entries:
                        return (key, name_node.id) in watched or \
                            resolve(scope_parent.get(key), False)
                    return (key, name_node.id) in watched
                scope = scope_parent.get(key)
                first = False

        return resolve(scope_of[id(name_node)], True)

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
            if isinstance(expr, (ast.Subscript, ast.Attribute)):
                expr = expr.value
            elif isinstance(expr, ast.Call) \
                    and isinstance(expr.func, ast.Attribute):
                expr = expr.func.value
            else:
                break
        if isinstance(expr, ast.Name):
            return is_watched(expr)
        if isinstance(expr, ast.Call):
            return isinstance(expr.func, ast.Name) \
                and expr.func.id in returning
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
        if isinstance(expr, ast.Await):
            return hands_over(expr.value)
        if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
            return any(hands_over(e) for e in expr.elts)
        if isinstance(expr, ast.Dict):
            return any(hands_over(e) for e in
                       list(expr.keys) + list(expr.values)
                       if e is not None)
        return False

    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name not in returning:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) \
                            and sub.value is not None \
                            and hands_over(sub.value):
                        returning.add(node.name)
                        changed = True
                        break
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.Lambda)):
                for param, default in param_defaults(node):
                    if hands_over(default) \
                            and (id(node), param) not in watched:
                        watched.add((id(node), param))
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
            else:
                continue
            if hands_over(value):
                for t in targets:
                    for n in _bound_names(t):
                        key = binding_key(node, n)
                        if (key, n) not in watched:
                            watched.add((key, n))
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
    return definitions, is_watched, hands_over, local_defs


def ghg_mutation_sites(tree, is_watched, hands_over, local_defs):
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
        elif isinstance(node, ast.Call) \
                and isinstance(node.func, ast.Attribute) \
                and node.func.attr in _MUTATOR_METHODS:
            if hands_over(node.func.value):
                sites.append((node.lineno, f".{node.func.attr}() call"))
        elif isinstance(node, ast.Call) \
                and isinstance(node.func, ast.Name) \
                and node.func.id in local_defs:
            args = list(node.args) + [kw.value for kw in node.keywords]
            if any(hands_over(a) for a in args):
                sites.append((node.lineno,
                              "modelled table passed as a call argument"))
    return sites


def model_ghg(text):
    if text is None:
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise DifferError(f"{GHG_PY}: unparsable Python ({e})") from e
    definitions, is_watched, hands_over, local_defs = \
        ghg_binding_census(tree)
    sites = ghg_mutation_sites(tree, is_watched, hands_over,
                               local_defs)
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
