#!/usr/bin/env python3
"""Skills phantom-capability check -- the CI routing gate for skill claims.

Bounded claim: this gate proves that no file under ``skills/`` contains
(a) the Craft Anything runtime's artifact names (its CLI or MCP server
binaries), (b) a command-position invocation of the engine binary, (c) an
MCP-server registration entry for it, or (d) a direct imperative
instruction to run / invoke / install / register / use the Craft Anything
engine, CLI, or MCP server, where no negation in the instruction's own
clause governs it (see below). Rule (d) is evaluated over logical lines:
prose wrapped across physical lines is joined (whitespace normalized)
before matching, so ordinary Markdown hard-wrapping neither hides an
instruction nor strands a governing negation on another line; a rule (d)
finding names the physical line where the matched verb starts. Rules
(a)-(c) match per physical line. It is a tripwire against
phantom-capability drift -- a skill silently gaining instructions to
invoke a runtime that is not authorized here -- not a semantic proof
that no paraphrase could instruct invocation.

Outside the claim: rule (b) remains wrap-sensitive in the other
direction -- a bare binary name alone on a console line, its arguments
wrapped onto the next line, is not detected. Nor is adversarial
obfuscation of the target phrase itself: emphasis or comment splitting
inside it, HTML entities, zero-width characters, soft hyphens, or the
phrase split across a table cell or a JSON boundary. This gate guards
against drift in honestly written prose; review, not this gate, is the
control for adversarial content.

Why it exists: the craft-anything adoption (plan v2.1, Phase 3; wringer
Risk condition (c)) adopted a protocol, not the engine. The protocol
skill's header state -- "engine not installed in this environment" -- is
the model of honest phrasing this gate protects. A one-time grep is not
enough; this check recurs on every PR. It is lifted only as part of an
authorized runtime plan, never by editing a skill alone.

Honest, negated statements are not findings: a statement that negates
the instruction in the instruction's own clause ("nothing here installs,
registers, or calls the craft-anything engine") is how a skill states
the boundary, and the negation guard exempts it from rule (d). The
guard is scoped to the clause, not the line: a negation governs a
verb->target pairing only when it sits inside the pairing's own span or
before the verb within the same clause -- clauses end at . ! ? ; :,
and a negation does not carry past a comma that closes a subordinate
clause ("if it is not installed, install ..."), nor does a negation in
an earlier sentence exempt a later instruction. Every verb->target
pairing in the logical line is evaluated independently. Rules (a)-(c) have no guard:
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

VERB_RE = re.compile(
    r"\b(run|invoke|execute|launch|start|call|install|register|use|"
    r"enable|connect)(s|es|ing|ed|d)?\b",
    re.IGNORECASE,
)

SUBORDINATOR_RE = re.compile(
    r"\b(if|when|once|unless|although|while|because|since)\b",
    re.IGNORECASE,
)

CLAUSE_BOUNDARIES = ".!?;:"

FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}(?:\s|$)")
TABLE_ROW_RE = re.compile(r"^\s*\|")
THEMATIC_BREAK_RE = re.compile(
    r"^\s{0,3}(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$")
LIST_ITEM_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d{1,9}[.)])\s+\S")
BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?(.*)$")
FRONTMATTER_END_RE = re.compile(r"^(?:---|\.\.\.)$")


def _negation_governs(line, match):
    """True if a negation scopes over this verb->target pairing.

    A negation governs when it sits inside the matched span itself, or
    before the verb within the same clause. Clauses end at . ! ? ; :,
    and a negation does not carry past a comma that closes a
    subordinate clause -- a comma whose preceding clause text contains
    a subordinator such as "if" or "when" -- because that negation
    belongs to the subordinate clause, not to what follows the comma.
    """
    if NEGATION_RE.search(line[match.start():match.end()]):
        return True
    start = match.start()
    clause_start = max(line.rfind(b, 0, start)
                       for b in CLAUSE_BOUNDARIES) + 1
    effective_start = clause_start
    pos = clause_start
    while True:
        comma = line.find(",", pos, start)
        if comma == -1:
            break
        if SUBORDINATOR_RE.search(line[clause_start:comma]):
            effective_start = comma + 1
        pos = comma + 1
    return bool(NEGATION_RE.search(line[effective_start:start]))


def check_rules_abc(line):
    """Rules (a)-(c), evaluated per physical line exactly as shipped."""
    lowered = line.lower()
    for literal in ARTIFACT_LITERALS:
        if literal in lowered:
            return f"artifact name {literal!r}"
    if COMMAND_RE.search(line):
        return "command-position invocation"
    if REGISTRATION_RE.search(line):
        return "MCP registration entry"
    return None


def imperative_match(text):
    """First unexempted verb->target pairing in text, or None (rule (d))."""
    for verb in VERB_RE.finditer(text):
        match = IMPERATIVE_RE.match(text, verb.start())
        if match and not _negation_governs(text, match):
            return match
    return None


def iter_logical_lines(lines):
    """Yield (text, segments) for each logical line in a file's lines.

    Consecutive prose lines in the same block are joined with a single
    space, whitespace runs normalized and punctuation preserved, so rule
    (d) sees through ordinary Markdown hard-wrapping. A logical line
    terminates at a blank line, a fence delimiter or any fenced line
    (no joining inside fences -- each shell line stays its own unit), a
    heading, a table row, a thematic break, or any frontmatter line
    (frontmatter is never joined); a new list-item start closes the
    previous item, whose indented or lazy continuations join it.
    Blockquote markers are stripped per line and consecutive quote
    lines join. ``segments`` maps positions in the joined text back to
    physical lines: a list of (start_offset, lineno), one per segment.
    """
    blocks = []
    current = None
    current_kind = None

    def flush():
        nonlocal current, current_kind
        if current:
            blocks.append(current)
        current = None
        current_kind = None

    def singleton(lineno, text):
        flush()
        blocks.append([(lineno, text)])

    in_frontmatter = False
    in_fence = False
    for idx, raw in enumerate(lines):
        lineno = idx + 1
        stripped = raw.strip()
        if idx == 0 and stripped == "---":
            in_frontmatter = True
            singleton(lineno, raw)
            continue
        if in_frontmatter:
            singleton(lineno, raw)
            if FRONTMATTER_END_RE.match(stripped):
                in_frontmatter = False
            continue
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            singleton(lineno, raw)
            continue
        if in_fence:
            singleton(lineno, raw)
            continue
        if not stripped:
            flush()
            continue
        if (HEADING_RE.match(raw) or TABLE_ROW_RE.match(raw)
                or THEMATIC_BREAK_RE.match(raw)):
            singleton(lineno, raw)
            continue
        quote = BLOCKQUOTE_RE.match(raw)
        if quote is not None:
            if not quote.group(1).strip():
                flush()
                continue
            if current_kind != "quote":
                flush()
                current = []
                current_kind = "quote"
            current.append((lineno, quote.group(1)))
            continue
        if LIST_ITEM_RE.match(raw):
            flush()
            current = [(lineno, raw)]
            current_kind = "prose"
            continue
        if current_kind != "prose":
            flush()
            current = []
            current_kind = "prose"
        current.append((lineno, raw))
    flush()

    for block in blocks:
        segments = []
        parts = []
        offset = 0
        for lineno, seg_text in block:
            normalized = " ".join(seg_text.split())
            if not normalized:
                continue
            segments.append((offset, lineno))
            parts.append(normalized)
            offset += len(normalized) + 1
        if parts:
            yield " ".join(parts), segments


def physical_line_for_offset(segments, offset):
    """Physical line number of the segment containing offset."""
    lineno = segments[0][1]
    for start, seg_lineno in segments:
        if start > offset:
            break
        lineno = seg_lineno
    return lineno


def check_text(text):
    """All findings in one file's text, as (lineno, rule, excerpt)."""
    lines = text.splitlines()
    findings = []
    for lineno, line in enumerate(lines, start=1):
        rule = check_rules_abc(line)
        if rule is not None:
            findings.append((lineno, rule, line.strip()[:120]))
    for joined, segments in iter_logical_lines(lines):
        match = imperative_match(joined)
        if match is not None:
            lineno = physical_line_for_offset(segments, match.start())
            findings.append((lineno, "imperative invocation instruction",
                             lines[lineno - 1].strip()[:120]))
    findings.sort(key=lambda finding: finding[0])
    return findings


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
        for lineno, rule, excerpt in check_text(text):
            findings.append(f"{rel}:{lineno}: {rule}: {excerpt}")

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
