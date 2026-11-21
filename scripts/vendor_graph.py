#!/usr/bin/env python3
"""Derive the AEP vendor graph from provenance blocks and live GitHub compares.

Single source of truth: one-line ``<!-- vendor-freshness: {…} -->`` blocks inside
each top-level ``reference/*/PROVENANCE.md``. No parallel SSOT file exists.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BLOCK_RE = re.compile(r"<!--\s*vendor-freshness:\s*(\{.*?\})\s*-->", re.DOTALL)
COMPARE_JQ = "{ahead_by: .ahead_by, behind_by: .behind_by, status: .status}"


def run_gh(*args):
    """Run gh and return stdout. Mocked by tests."""
    return subprocess.check_output(["gh", *args], text=True, stderr=subprocess.PIPE)


def _compare(repo, base, head):
    try:
        out = run_gh("api", f"repos/{repo}/compare/{base}...{head}", "--jq", COMPARE_JQ)
        return json.loads(out)
    except Exception as exc:  # a failed compare is a finding, not a silent skip
        return {"error": str(exc)[:200]}


def parse_blocks(root):
    """Return (entries, findings) for all top-level reference trees."""
    entries, findings = [], []
    ref = Path(root) / "reference"
    for d in sorted(p for p in ref.iterdir() if p.is_dir()):
        p = d / "PROVENANCE.md"
        if not p.exists():
            findings.append({"tree": d.name, "why": "no PROVENANCE.md"})
            continue
        text = p.read_text(encoding="utf-8")
        m = BLOCK_RE.search(text)
        if not m:
            findings.append({"tree": d.name, "why": "no vendor-freshness block"})
            continue
        try:
            block = json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            findings.append({"tree": d.name, "why": f"malformed vendor-freshness block: {exc}"})
            continue
        if not isinstance(block, dict):
            findings.append({"tree": d.name, "why": "malformed vendor-freshness block: not an object"})
            continue
        # Validate the schema before accepting the entry. Valid JSON with no
        # fields would otherwise keep the entry count at 14 while silently
        # disabling freshness checks, and a missing repo/branch raises KeyError
        # in the live compare, killing the whole weekly report.
        local = block.get("policy") == "local"
        required = ["tree", "policy"] if local else [
            "tree", "pin", "repo", "branch", "parent_branch", "policy", "decision_date", "review_due",
        ]
        invalid = [k for k in required if k not in block or block[k] is None and k != "parent_branch"]
        if local and block.get("pin") is not None:
            invalid.append("local entry must not carry a pin")
        if not local and block.get("pin") is not None and not re.fullmatch(r"[0-9a-f]{7,40}", str(block["pin"])):
            invalid.append("pin")
        if invalid:
            findings.append({"tree": d.name, "why": f"malformed vendor-freshness block: invalid field(s): {', '.join(invalid)}"})
            continue
        found_pin = re.search(r"[0-9a-f]{7,40}", text)
        pin = block.get("pin")
        if pin and found_pin:
            prose = found_pin.group(0)
            if not (pin.startswith(prose) or prose.startswith(pin)):
                findings.append({"tree": d.name, "why": "block pin does not match prose pin"})
        entries.append(block)
    return entries, findings


def build(root, findings=False, live=True):
    entries, problems = parse_blocks(root)
    if live:
        for e in entries:
            if not e.get("pin"):
                continue
            repo, branch = e["repo"], e["branch"]
            e["fork_vs_head"] = _compare(repo, e["pin"], branch)
            if "error" in e["fork_vs_head"]:
                problems.append({
                    "tree": e["tree"],
                    "why": f"compare failed for {repo} {e['pin']}...{branch}: {e['fork_vs_head']['error']}",
                })
            if e.get("parent"):
                owner = repo.split("/")[0]
                e["fork_vs_upstream"] = _compare(
                    e["parent"], e["parent_branch"], f"{owner}:{branch}"
                )
                if "error" in e["fork_vs_upstream"]:
                    problems.append({
                        "tree": e["tree"],
                        "why": f"compare failed for {e['parent']} {e['parent_branch']}...{owner}:{branch}: {e['fork_vs_upstream']['error']}",
                    })
    if findings:
        return {"entries": entries, "findings": problems}
    return entries


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repository root")
    ap.add_argument("--findings", action="store_true", help="wrap output with findings")
    ap.add_argument("--no-live", action="store_true", help="skip GitHub API calls")
    ap.add_argument("--strict", action="store_true", help="exit nonzero on findings or != 14 entries")
    args = ap.parse_args()
    strict_findings = args.findings or args.strict
    result = build(args.root, findings=strict_findings, live=not args.no_live)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.strict and (result["findings"] or len(result["entries"]) != 14):
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
