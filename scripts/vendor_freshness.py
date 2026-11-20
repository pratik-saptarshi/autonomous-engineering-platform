#!/usr/bin/env python3
"""Weekly vendor freshness detector. Non-gating; reports drift and decisions due.

Reads the freshness blocks in reference/*/PROVENANCE.md via vendor_graph.py,
derives live divergences from GitHub, and emits a deterministic report plus a
Markdown issue body with a stable marker for issue dedup.
"""

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import vendor_graph

MARKER = "<!-- vendor-freshness-report -->"


def _problem_finding(problem):
    why = problem.get("why", "")
    kind = "missing-block" if "no vendor-freshness block" in why or "no PROVENANCE" in why else "malformed-block"
    return {"kind": kind, "tree": problem.get("tree"), "why": why}


def build(root=".", today=None):
    """Return {'entries': [...], 'findings': [...]} for one live pass."""
    today = today or date.today().isoformat()
    raw = vendor_graph.build(root, findings=True, live=True)
    findings = [_problem_finding(p) for p in raw["findings"]]
    for e in raw["entries"]:
        if e.get("policy") == "local" or not e.get("pin"):
            continue
        head = e.get("fork_vs_head", {})
        # compare(pin...branch): ahead_by = commits in the branch but not in the
        # pin — i.e. how far the pin trails the fork head. behind_by is always 0
        # for a pinned ancestor and would make this check never fire.
        if head.get("ahead_by", 0):
            findings.append({
                "kind": "pin-behind", "tree": e["tree"], "behind": head["ahead_by"],
                "repo": e.get("repo"), "policy": e.get("policy"),
            })
        up = e.get("fork_vs_upstream", {})
        if up.get("behind_by", 0):
            findings.append({
                "kind": "fork-behind-upstream", "tree": e["tree"], "behind": up["behind_by"],
                "parent": e.get("parent"), "policy": e.get("policy"),
            })
        if e.get("policy") == "keep" and e.get("review_due") and e["review_due"] <= today:
            findings.append({
                "kind": "decision-due", "tree": e["tree"], "due": e["review_due"],
                "policy": "keep",
            })
        if head.get("error") or up.get("error"):
            findings.append({
                "kind": "compare-error", "tree": e["tree"],
                "error": head.get("error") or up.get("error"),
            })
    # A removed tree has no block to parse, so parse_blocks sees nothing wrong.
    # Cross-check against the manifests still present in the repository.
    manifests = list((Path(root) / ".github").glob("vendor-*.sha256"))
    if manifests and len(raw["entries"]) < len(manifests):
        findings.append({
            "kind": "missing-tree",
            "expected": len(manifests),
            "found": len(raw["entries"]),
        })
    findings.sort(key=lambda f: (f["kind"], f.get("tree", "")))
    return {"entries": raw["entries"], "findings": findings, "checked_on": today}


def issue_body(report):
    findings = report.get("findings", [])
    lines = [MARKER, "# Vendor pin freshness", "", f"Checked: {report.get('checked_on', 'unknown')}", ""]
    if not findings:
        lines += ["No drift or decisions due.", ""]
    else:
        lines += [f"{len(findings)} finding(s):", ""]
        for f in findings:
            if f["kind"] == "pin-behind":
                text = f"- **{f['tree']}**: pin is {f['behind']} commits behind `{f.get('repo')}`"
            elif f["kind"] == "fork-behind-upstream":
                text = f"- **{f['tree']}**: fork is {f['behind']} commits behind `{f.get('parent')}`"
            elif f["kind"] == "decision-due":
                text = f"- **{f['tree']}**: recorded keep decision due for review on {f['due']}"
            elif f["kind"] == "missing-tree":
                text = f"- **tree set**: only {f['found']} provenance blocks for {f['expected']} manifests — a tree disappeared"
            elif f["kind"] in ("missing-block", "malformed-block"):
                text = f"- **{f.get('tree')}**: {f['kind']} — {f.get('why')}"
            else:
                text = f"- **{f.get('tree')}**: {f['kind']} — {f.get('error')}"
            lines.append(text)
        lines.append("")
    lines += [
        "Owner: AEP maintainer. SLA: 7 days from detection. This detector is",
        "non-gating and never auto-syncs or auto-merges. Keep decisions are",
        "review triggers, not permanent exemptions.",
        "",
        "— Terminator3000-DarkCrouton",
    ]
    return "\n".join(lines)


def self_test():
    tests = Path(__file__).resolve().parent / "tests" / "test_vendor_freshness.py"
    return subprocess.call([sys.executable, "-m", "unittest", str(tests), "-v"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--issue-body", action="store_true", help="print the Markdown issue body")
    ap.add_argument("--self-test", action="store_true", help="run the mutation tests and exit")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD) for reproducible tests")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    report = build(args.root, today=args.today)
    print(issue_body(report) if args.issue_body else json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
