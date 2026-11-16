#!/usr/bin/env python3
"""Phase 0 prototype power-differ (THROWAWAY — gate evidence, not the Phase 1 tool).

Computes a mechanical "power delta" between two git refs over the policy-bearing
artefacts AEP already diffs by eye:

  * scripts/policy.data            — deny-sets ([sensitive-paths], [env-scrub]).
                                     A pattern REMOVED from a deny-set is power
                                     NEWLY ALLOWED; a pattern ADDED is NEWLY DENIED.
  * tools/ghg/ghg.py               — DEFAULT_LIMITS bucket caps (cap increase or a
                                     new bucket/window = newly allowed call volume)
                                     and the mutating-classification sets
                                     (_MUTATING_SUBCOMMANDS / _MUTATING_METHODS):
                                     an entry REMOVED there means those calls escape
                                     mutating classification = newly allowed.
                                     Any other change to ghg.py is reported as an
                                     UNMODELLED change (file changed, no modelled
                                     power delta) — never silently treated as none.
  * .github/skills-sync-scope.txt  — skill set; added skill = newly allowed
                                     (enters the governed sync set), removed = denied.
  * skills/**                      — file-set delta per skill: new skill dir = newly
                                     allowed capability surface; removed dir = denied;
                                     added file in an existing skill = surface
                                     expansion; modified SKILL.md = content change,
                                     NOT mechanically classifiable (counted only).

Model boundary (stated, per plan): this differ sees artefact-level grants only.
It does not model reachability, data-level effects of changed skill *content*,
or anything outside the four artefacts above.

Usage:
  power_differ_prototype.py diff <base-ref> <head-ref>   -> JSON delta
  power_differ_prototype.py seeds                        -> run the 3 seeded
        escalations against copies of the current artefacts and report catches
"""
import ast
import json
import subprocess
import sys

REPO = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip()


def git_show(ref, path):
    r = subprocess.run(["git", "show", f"{ref}:{path}"],
                       capture_output=True, text=True, cwd=REPO)
    return r.stdout if r.returncode == 0 else None


def git_name_status(base, head, path):
    r = subprocess.run(["git", "diff", "--name-status", base, head, "--", path],
                       capture_output=True, text=True, cwd=REPO)
    out = []
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out.append((parts[0], parts[-1]))
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
            sections[cur] = set()
        elif cur is not None:
            sections[cur].add(line)
    return sections


def model_ghg(text):
    if text is None:
        return None
    tree = ast.parse(text)
    model = {"limits": {}, "mutating_subcommands": set(), "mutating_methods": set()}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = getattr(node.targets[0], "id", None)
            if name == "DEFAULT_LIMITS":
                model["limits"] = {
                    k: [tuple(p) for p in v]
                    for k, v in ast.literal_eval(node.value).items()
                }
            elif name == "_MUTATING_SUBCOMMANDS":
                model["mutating_subcommands"] = set(ast.literal_eval(node.value))
            elif name == "_MUTATING_METHODS":
                model["mutating_methods"] = set(ast.literal_eval(node.value))
    return model


def model_scope(text):
    if text is None:
        return None
    return {ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")}


# ------------------------------------------------------------------- diffing

def diff_policy(base, head):
    """Both are section->{patterns} deny-set models (or None)."""
    newly_allowed, newly_denied = [], []
    if base is None and head is None:
        return newly_allowed, newly_denied, []
    if base is None:
        return [], [], ["policy.data created (whole deny-set is new; no prior power baseline)"]
    if head is None:
        for sec, pats in base.items():
            newly_allowed += [f"policy.data[{sec}] deny pattern removed (file deleted): {p}"
                              for p in sorted(pats)]
        return newly_allowed, newly_denied, []
    for sec in sorted(set(base) | set(head)):
        b, h = base.get(sec, set()), head.get(sec, set())
        newly_allowed += [f"policy.data[{sec}]: deny pattern removed -> newly allowed: {p}"
                          for p in sorted(b - h)]
        newly_denied += [f"policy.data[{sec}]: deny pattern added -> newly denied: {p}"
                         for p in sorted(h - b)]
    return newly_allowed, newly_denied, []


def diff_ghg(base, head, base_text, head_text):
    newly_allowed, newly_denied, notes = [], [], []
    if base is None and head is None:
        return newly_allowed, newly_denied, notes
    if base is None:
        return [], [], ["ghg.py created (whole gateway is new; no prior power baseline)"]
    if base_text != head_text and base == head:
        notes.append("ghg.py changed but modelled power (caps + classification) unchanged")
    bl, hl = base["limits"], head["limits"]
    for bucket in sorted(set(bl) | set(hl)):
        if bucket not in bl:
            newly_allowed.append(f"ghg caps: NEW bucket '{bucket}' {hl[bucket]} -> newly allowed call class")
            continue
        if bucket not in hl:
            newly_denied.append(f"ghg caps: bucket '{bucket}' removed -> newly denied call class")
            continue
        bmap, hmap = dict(bl[bucket]), dict(hl[bucket])
        for w in sorted(set(bmap) | set(hmap)):
            if w not in bmap:
                newly_allowed.append(f"ghg caps: bucket '{bucket}' new window {w}s cap {hmap[w]} -> newly allowed")
            elif w not in hmap:
                newly_denied.append(f"ghg caps: bucket '{bucket}' window {w}s removed -> newly denied")
            elif hmap[w] > bmap[w]:
                newly_allowed.append(f"ghg caps: bucket '{bucket}' window {w}s cap {bmap[w]} -> {hmap[w]} -> newly allowed volume")
            elif hmap[w] < bmap[w]:
                newly_denied.append(f"ghg caps: bucket '{bucket}' window {w}s cap {bmap[w]} -> {hmap[w]} -> newly denied volume")
    for key, label in (("mutating_subcommands", "subcommand"), ("mutating_methods", "method")):
        for item in sorted(base[key] - head[key]):
            newly_allowed.append(f"ghg classify: '{item}' leaves mutating {label} set -> newly allowed (escapes mutating classification)")
        for item in sorted(head[key] - base[key]):
            newly_denied.append(f"ghg classify: '{item}' joins mutating {label} set -> newly denied (now classified mutating)")
    return newly_allowed, newly_denied, notes


def diff_scope(base, head):
    if base is None and head is None:
        return [], [], []
    if base is None:
        return [], [], ["skills-sync-scope.txt created (whole scope set is new)"]
    newly_allowed = [f"skills scope: '{s}' enters sync scope -> newly allowed surface"
                     for s in sorted(head - base)]
    newly_denied = [f"skills scope: '{s}' leaves sync scope -> newly denied surface"
                    for s in sorted(base - head)]
    return newly_allowed, newly_denied, []


def diff_skills(base, head):
    newly_allowed, newly_denied, notes = [], [], []
    changes = git_name_status(base, head, "skills")
    base_skills, head_skills = {}, {}
    for ref, acc in ((base, base_skills), (head, head_skills)):
        r = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref, "--", "skills"],
                           capture_output=True, text=True, cwd=REPO)
        for p in r.stdout.splitlines():
            parts = p.split("/")
            if len(parts) >= 2:
                acc.setdefault(parts[1], set()).add(p)
    for skill in sorted(set(head_skills) - set(base_skills)):
        newly_allowed.append(f"skills: NEW skill '{skill}' ({len(head_skills[skill])} files) -> newly allowed capability surface")
    for skill in sorted(set(base_skills) - set(head_skills)):
        newly_denied.append(f"skills: skill '{skill}' removed -> newly denied capability surface")
    modified_skillmd = 0
    for status, path in changes:
        parts = path.split("/")
        if len(parts) < 2:
            continue
        skill = parts[1]
        if skill in base_skills and skill in head_skills:
            if status == "A":
                newly_allowed.append(f"skills: file added to existing skill '{skill}': {path} -> surface expansion")
            elif status == "D":
                newly_denied.append(f"skills: file removed from existing skill '{skill}': {path} -> surface contraction")
            elif status == "M" and path.endswith("SKILL.md"):
                modified_skillmd += 1
    if modified_skillmd:
        notes.append(f"{modified_skillmd} SKILL.md content change(s) in surviving skills — "
                     "not mechanically classifiable as grant/denial by this model")
    return newly_allowed, newly_denied, notes


def full_diff(base, head):
    pd_b, pd_h = model_policy_data(git_show(base, "scripts/policy.data")), \
                 model_policy_data(git_show(head, "scripts/policy.data"))
    gh_b_text, gh_h_text = git_show(base, "tools/ghg/ghg.py"), git_show(head, "tools/ghg/ghg.py")
    gh_b, gh_h = model_ghg(gh_b_text), model_ghg(gh_h_text)
    sc_b, sc_h = model_scope(git_show(base, ".github/skills-sync-scope.txt")), \
                 model_scope(git_show(head, ".github/skills-sync-scope.txt"))
    a1, d1, n1 = diff_policy(pd_b, pd_h)
    a2, d2, n2 = diff_ghg(gh_b, gh_h, gh_b_text, gh_h_text)
    a3, d3, n3 = diff_scope(sc_b, sc_h)
    a4, d4, n4 = diff_skills(base, head)
    return {
        "base": base, "head": head,
        "newly_allowed": a1 + a2 + a3 + a4,
        "newly_denied": d1 + d2 + d3 + d4,
        "notes": n1 + n2 + n3 + n4,
    }


# --------------------------------------------------------------------- seeds

def run_seeds():
    """Seed 3 synthetic escalations into copies of the CURRENT artefacts and
    check the differ catches each. Returns a list of per-seed results."""
    head = "HEAD"
    pd_text = git_show(head, "scripts/policy.data")
    gh_text = git_show(head, "tools/ghg/ghg.py")
    results = []

    # Seed 1 — new credentialed host: ghg gains a whole new bucket for a
    # metadata/credentials call class that did not exist before.
    gh_s1 = gh_text.replace('"core": [(3600, 3500)],',
                            '"core": [(3600, 3500)],\n    "metadata_creds": [(60, 30)],')
    assert gh_s1 != gh_text
    a, d, _ = diff_ghg(model_ghg(gh_text), model_ghg(gh_s1), gh_text, gh_s1)
    results.append({"seed": "S1 new credentialed host (new ghg bucket 'metadata_creds')",
                    "caught": any("metadata_creds" in x for x in a),
                    "newly_allowed": a, "newly_denied": d})

    # Seed 2 — new method on an allowed host: 'merge' leaves the mutating
    # subcommand set, so merges escape mutating classification.
    gh_s2 = gh_text.replace('"create", "comment", "merge",', '"create", "comment",')
    assert gh_s2 != gh_text
    a, d, _ = diff_ghg(model_ghg(gh_text), model_ghg(gh_s2), gh_text, gh_s2)
    results.append({"seed": "S2 new method on allowed host ('merge' leaves mutating set)",
                    "caught": any("'merge'" in x for x in a),
                    "newly_allowed": a, "newly_denied": d})

    # Seed 3 — metadata-endpoint reach: the cloud-config credential paths
    # leave the sensitive-paths deny-set in policy.data.
    pd_s3 = "\n".join(ln for ln in pd_text.splitlines()
                      if ln.strip() not in ("*/.config/gcloud", "*/.config/gcloud/*")) + "\n"
    assert pd_s3 != pd_text
    a, d, _ = diff_policy(model_policy_data(pd_text), model_policy_data(pd_s3))
    results.append({"seed": "S3 metadata-endpoint reach ('*/.config/gcloud' leaves deny-set)",
                    "caught": any("gcloud" in x for x in a),
                    "newly_allowed": a, "newly_denied": d})
    return results


if __name__ == "__main__":
    if sys.argv[1] == "diff":
        print(json.dumps(full_diff(sys.argv[2], sys.argv[3]), indent=1))
    elif sys.argv[1] == "seeds":
        print(json.dumps(run_seeds(), indent=1))
