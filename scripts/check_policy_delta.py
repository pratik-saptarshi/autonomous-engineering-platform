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
  * tools/ghg/ghg.py -- DEFAULT_LIMITS bucket caps (a cap increase, a
    new bucket, or a new window is newly allowed call volume; the mirror
    operations are newly denied) and the mutating-classification sets
    (_MUTATING_SUBCOMMANDS / _MUTATING_METHODS): an entry REMOVED there
    means those calls escape mutating classification (newly allowed);
    an entry ADDED is newly denied. Any other change to ghg.py is
    reported as an explicit note ("changed, modelled power unchanged")
    -- never as silence.
  * .github/skills-sync-scope.txt -- the governed skill set; a skill
    entering scope is newly allowed surface, leaving is newly denied.
  * skills/** -- the skill tree. A new skill directory is newly allowed
    capability surface; a removed one is newly denied; a file added to a
    surviving skill is surface expansion; a file removed is contraction.
    Added files that create *executable* surface -- anything under a
    skill's scripts/ directory, server files, start/stop hooks, files
    with the executable bit, and code files -- are additionally listed
    in newly_allowed_executable (this tier exists because the Phase 0
    replay's one real missed delta, PR #58, was exactly this: skills
    silently acquiring runnable servers and executable scripts).
    SKILL.md content changes in surviving skills are counted in a note
    as not mechanically classifiable.

Not modelled (stated, per the plan): reachability through allowed
hosts, data-level effects of changed skill *content*, effects of
modified non-SKILL.md files in surviving skills, renames within the
skills tree (the new path is reported as an addition; the old path is
not reported as a removal), and anything outside the four artefacts
above.

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
    "tools/ghg/ghg.py DEFAULT_LIMITS caps and mutating-classification sets",
    ".github/skills-sync-scope.txt governed skill set",
    "skills/** tree grants, with newly added executable surface classified separately",
]
NOT_MODELLED = [
    "reachability through allowed hosts",
    "data-level effects of changed skill content",
    "content changes to non-SKILL.md files in surviving skills",
    "renames within the skills tree (new path reported as an addition only)",
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


def model_ghg(text):
    if text is None:
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise DifferError(f"{GHG_PY}: unparsable Python ({e})") from e
    found = {}
    for node in tree.body:  # module level only: the artefact contract
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = getattr(node.targets[0], "id", None)
            if name in ("DEFAULT_LIMITS", "_MUTATING_SUBCOMMANDS",
                        "_MUTATING_METHODS"):
                try:
                    found[name] = ast.literal_eval(node.value)
                except (ValueError, SyntaxError) as e:
                    raise DifferError(
                        f"{GHG_PY}: {name} is not a literal ({e})") from e
    missing = {"DEFAULT_LIMITS", "_MUTATING_SUBCOMMANDS",
               "_MUTATING_METHODS"} - set(found)
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


def model_scope(text):
    if text is None:
        return None
    return {ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")}


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
            newly_denied.append(
                f"ghg caps: bucket '{bucket}' removed -> newly denied call class")
            continue
        bmap, hmap = dict(bl[bucket]), dict(hl[bucket])
        for w in sorted(set(bmap) | set(hmap)):
            if w not in bmap:
                newly_allowed.append(
                    f"ghg caps: bucket '{bucket}' new window {w}s "
                    f"cap {hmap[w]} -> newly allowed")
            elif w not in hmap:
                newly_denied.append(
                    f"ghg caps: bucket '{bucket}' window {w}s removed "
                    "-> newly denied")
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
    newly_allowed = [f"skills scope: '{s}' enters sync scope "
                     "-> newly allowed surface" for s in sorted(head - base)]
    newly_denied = [f"skills scope: '{s}' leaves sync scope "
                    "-> newly denied surface" for s in sorted(base - head)]
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
        elif status.startswith("M") and path.endswith("SKILL.md"):
            modified_skillmd += 1
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
    sys.exit(main())
