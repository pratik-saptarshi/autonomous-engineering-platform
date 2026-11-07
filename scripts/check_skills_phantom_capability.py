#!/usr/bin/env python3
"""Skills phantom-capability check -- the CI routing gate for skill claims.

Bounded claim: this gate proves that no file under ``skills/`` contains
(a) the Craft Anything runtime's artifact names (its CLI or MCP server
binaries), (b) a command-position invocation of the engine binary, (c) an
MCP-server registration entry for it, or (d) a direct imperative
instruction to run / invoke / install / register / use the Craft Anything
engine, CLI, or MCP server, where the instruction is not negated earlier
on the same line. It is a tripwire against phantom-capability drift -- a
skill silently gaining instructions to invoke a runtime that is not
authorized here -- not a semantic proof that no paraphrase could instruct
invocation.

Why it exists: the craft-anything adoption (plan v2.1, Phase 3; wringer
Risk condition (c)) adopted a protocol, not the engine. The protocol
skill's header state -- "engine not installed in this environment" -- is
the model of honest phrasing this gate protects. A one-time grep is not
enough; this check recurs on every PR. It is lifted only as part of an
authorized runtime plan, never by editing a skill alone.

Honest, negated statements are not findings: a line that negates the
instruction before the verb ("nothing here installs, registers, or calls
the craft-anything engine") is how a skill states the boundary, and the
negation guard exempts it from rule (d). Rules (a)-(c) have no guard:
honest prose never needs the binary names, a command position, or a
registration entry. The skill's own name is never a finding: the noun
pattern refuses a trailing hyphen or word character, so
"craft-anything-protocol" (and the "owner/repo" form, which carries a
trailing slash) cannot match.

Usage:

    check_skills_phantom_capability.py --root <skills-tree>

Exit 0 iff there are no findings; each finding is printed on its own line
naming the file, the line number, and the rule that fired.
"""

import argparse
import re
import sys
from pathlib import Path

ARTIFACT_LITERALS = ("craft-anything-cli", "craft-anything-mcp")

COMMAND_RE = re.compile(
    r"(?:^|[\`$]\s*|&&\s*|;\s*|[-*]\s+)(?:npx\s+|node\s+)?"
    r"craft-anything\s+\S",
    re.IGNORECASE,
)

REGISTRATION_RE = re.compile(r'"craft-anything"\s*:')

IMPERATIVE_RE = re.compile(
    r"\b(run|invoke|execute|launch|start|call|install|register|use|"
    r"enable|connect)(s|es|ing|ed|d)?\b"
    r"[^.]{0,60}?"
    r"craft[- ]anything(?![-\w/])",
    re.IGNORECASE,
)

NEGATION_RE = re.compile(r"\b(no|not|never|nothing|none|without)\b|n['’]t\b",
                         re.IGNORECASE)


def check_line(line):
    """Return the name of the first rule that fires on this line, or None."""
    lowered = line.lower()
    for literal in ARTIFACT_LITERALS:
        if literal in lowered:
            return f"artifact name {literal!r}"
    if COMMAND_RE.search(line):
        return "command-position invocation"
    if REGISTRATION_RE.search(line):
        return "MCP registration entry"
    match = IMPERATIVE_RE.search(line)
    if match and not NEGATION_RE.search(line[: match.start()]):
        return "imperative invocation instruction"
    return None


def iter_files(root):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            yield path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fail if any skill instructs invoking the "
                    "unauthorized craft-anything runtime.")
    parser.add_argument("--root", required=True,
                        help="skills tree to scan")
    args = parser.parse_args(argv)

    root = Path(args.root)
    findings = []
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_bytes().decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            rule = check_line(line)
            if rule is not None:
                findings.append(
                    f"{rel}:{lineno}: {rule}: {line.strip()[:120]}")

    for line in findings:
        print(line)
    if findings:
        print(f"{len(findings)} phantom-capability finding(s)")
        return 1
    print(f"OK: no skill under {root} instructs invoking the "
          f"craft-anything runtime")
    return 0


if __name__ == "__main__":
    sys.exit(main())
