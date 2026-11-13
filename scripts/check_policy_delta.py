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
    be a false statement, not a gap. The refusal census covers item /
    augmented assignment, deletion, and mutator calls on the tables
    (DEFAULT_LIMITS, the classification sets, the derived LIMITS),
    the same through aliases (names bound to a table, to a lookup
    rooted at one, to a container holding one, or to a local function
    returning one), and a modelled table passed as a call argument.
    Mutation via dynamic indirection (getattr/setattr/eval/globals())
    remains outside the model and is named as such in every report.
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
and anything outside the four artefacts above.

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
    "indirect mutation of ghg's modelled tables via dynamic indirection (getattr/setattr/eval/globals()/vars())",
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


def _root_name(node):
    """Root Name of a lookup chain: subscripts, attributes, and method
    calls on the chain (``DEFAULT_LIMITS.get("core")`` roots at
    DEFAULT_LIMITS)."""
    while True:
        if isinstance(node, (ast.Subscript, ast.Attribute)):
            node = node.value
        elif isinstance(node, ast.Call) \
                and isinstance(node.func, ast.Attribute):
            node = node.func.value
        else:
            break
    return node.id if isinstance(node, ast.Name) else None


def _value_touches_watched(value, watched):
    """True if an assigned value hands over a watched table (or part of
    it): a bare name, a lookup rooted at one (subscript / method chain),
    or a container literal holding one."""
    if _root_name(value) in watched:
        return True
    if isinstance(value, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return any(isinstance(n, ast.Name) and n.id in watched
                   for n in ast.walk(value))
    return False


def ghg_mutation_sites(tree):
    """[(lineno, description)] for runtime mutations of watched tables.

    Census of the escape family (this list is the class-level closure;
    anything outside it is named in the tool's not-modelled boundary):
    direct item/augmented assignment, deletion, and mutator calls on a
    watched table; the same through aliases -- names bound to a watched
    table, to a lookup rooted at one (``_caps = DEFAULT_LIMITS["x"]``),
    to a container holding one, or to the result of a local function
    that returns one; and a watched table passed as a call argument
    (the callee can mutate it; the differ cannot rule it out, so it
    refuses). Read-only aliasing and read-only method calls on the
    tables (.get/.items/iteration) are not sites.
    """
    watched = set(GHG_WATCH_NAMES)
    # Local functions that return a watched table hand it to callers.
    returning = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and sub.value is not None \
                        and _value_touches_watched(sub.value, watched):
                    returning.add(node.name)
    changed = True
    while changed:  # alias fixpoint: _L = DEFAULT_LIMITS; _M = _L
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id not in watched:
                value = node.value
                if _value_touches_watched(value, watched) or (
                        isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Name)
                        and value.func.id in returning):
                    watched.add(node.targets[0].id)
                    changed = True
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store) \
                and _root_name(node.value) in watched:
            sites.append((node.lineno, "item assignment"))
        elif isinstance(node, ast.AugAssign) \
                and isinstance(node.target, ast.Name) \
                and node.target.id in watched:
            sites.append((node.lineno, "augmented assignment"))
        elif isinstance(node, ast.Delete):
            for t in node.targets:
                if (isinstance(t, ast.Name) and t.id in watched) or \
                        (isinstance(t, ast.Subscript)
                         and _root_name(t.value) in watched):
                    sites.append((node.lineno, "deletion"))
        elif isinstance(node, ast.Call) \
                and isinstance(node.func, ast.Attribute) \
                and node.func.attr in _MUTATOR_METHODS \
                and _root_name(node.func.value) in watched:
            sites.append((node.lineno, f".{node.func.attr}() call"))
        elif isinstance(node, ast.Call):
            args = list(node.args) + [kw.value for kw in node.keywords]
            if any(_value_touches_watched(a, watched) for a in args):
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
    sites = ghg_mutation_sites(tree)
    if sites:
        detail = "; ".join(f"line {ln}: {desc}" for ln, desc in sites[:5])
        raise DifferError(
            f"{GHG_PY}: modelled power is mutated at runtime ({detail}) — "
            "the differ cannot model runtime mutation and refuses rather "
            "than reporting a literal-only delta")
    found = {}
    for node in tree.body:  # module level only: the artefact contract
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = getattr(node.targets[0], "id", None)
            if name in MODELLED_GHG_NAMES:
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
        bmap, hmap = dict(bl[bucket]), dict(hl[bucket])
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
