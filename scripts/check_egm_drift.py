#!/usr/bin/env python3
"""EGM wrapper drift check -- the CI gate for vendored-wrapper consistency.

Bounded claim: this gate proves three mechanical consistencies for the
EGM wrapper skills (``skills/egm-*``) against the vendored bundle:

(a) Each wrapper's hand-written ``skill.yaml`` carries the same ``name``
    and ``description`` as its ``SKILL.md`` frontmatter. The adoption
    spec (D3, item 1) requires the description verbatim; the panel on
    PR #111 (finding J10) found 6 of 7 truncated mid-sentence because
    the spec's own validation (YAML parses, name matches) could not
    catch it. ``skill.yaml`` files are excluded from the skills
    manifest, so no other gate covers them.

(b) The persona-name normalization table in
    ``skills/egm-review-loop/SKILL.md`` agrees with the vendored
    bundle: every ``agents/*.md`` frontmatter ``name`` appears in the
    table, mapped to that file's shortname (filename stem), and the
    table names no persona the bundle does not carry. The table is a
    hand copy of a mapping the bundle's frontmatter already states
    (panel finding J16); this check makes the copy fail loudly when
    the bundle moves.

(c) At every ``egm-review`` call site that pairs a reviewer list with
    a standards map in the same paragraph, every listed reviewer has
    an entry in the map, and every standard the map names exists in
    the bundle's ``resources/document_standards/``. A reviewer absent
    from the map degrades silently at runtime -- its persona treats a
    standard as optional (panel finding J8).

Outside the claim: prose semantics. This gate does not prove a
designated standard is the *right* standard, that a persona's mandate
matches its lens, or that call sites written in a different shape
than the ones above are covered. Review is the control for those.

Usage:

    check_egm_drift.py --root <skills-tree> [--bundle <bundle-tree>]

``--bundle`` defaults to ``<root>/../reference/elephant-goldfish-model``.

Exit 0 iff there are no findings; each finding is printed on its own
line naming the file, the line number, and the rule that fired.
"""

import argparse
import json
import re
import sys
from pathlib import Path

BLOCK_INDICATOR_RE = re.compile(r"^[>|][+-]?[0-9]?$")
TABLE_PAIR_RE = re.compile(r"`(egm-[a-z0-9-]+)`\s*→\s*`([a-z0-9_]+)`")
MAP_PAIR_RE = re.compile(r'"([^"]+)"\s*:\s*"([^"]+)"')
STANDARD_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
BRACKET_LIST_RE = re.compile(r"\[([^\[\]]+)\]")
NAME_TOKEN_RE = re.compile(r"^[a-z0-9_-]+$")


def _scalar(lines, key):
    """Value of a top-level YAML ``key`` in ``lines``, or None.

    Handles the scalar shapes the EGM files actually use: a plain
    single-line value, a double-quoted single-line value, and a
    ``>``/``|`` block scalar with indented continuation lines.
    """
    for idx, line in enumerate(lines):
        match = re.match(rf"^{re.escape(key)}:\s*(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if BLOCK_INDICATOR_RE.match(value):
            parts = []
            for continuation in lines[idx + 1:]:
                if continuation.startswith((" ", "\t")) and continuation.strip():
                    parts.append(continuation.strip())
                else:
                    break
            if value.startswith(">"):
                return " ".join(parts)
            return "\n".join(parts)
        if value.startswith('"'):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value.strip('"')
        return value
    return None


def frontmatter_lines(text):
    """The lines between the opening and closing ``---`` of frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    collected = []
    for line in lines[1:]:
        if line.strip() in ("---", "..."):
            break
        collected.append(line)
    return collected


def check_yaml_parity(root, findings):
    """Rule (a): skill.yaml name/description == SKILL.md frontmatter."""
    for skill_dir in sorted(root.glob("egm-*")):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        skill_yaml = skill_dir / "skill.yaml"
        for required in (skill_md, skill_yaml):
            if not required.is_file():
                findings.append(
                    f"{skill_dir.name}: missing {required.name}")
        if not (skill_md.is_file() and skill_yaml.is_file()):
            continue
        fm_lines = frontmatter_lines(skill_md.read_text(encoding="utf-8"))
        yaml_lines = skill_yaml.read_text(encoding="utf-8").splitlines()
        for key in ("name", "description"):
            fm_value = _scalar(fm_lines, key)
            yaml_value = _scalar(yaml_lines, key)
            if fm_value != yaml_value:
                findings.append(
                    f"{skill_dir.name}/skill.yaml: {key} differs from "
                    f"SKILL.md frontmatter (yaml: {yaml_value!r}; "
                    f"frontmatter: {fm_value!r})")


def check_normalization_table(root, bundle, findings):
    """Rule (b): loop normalization table == bundle agent frontmatter."""
    agents_dir = bundle / "agents"
    expected = {}
    if agents_dir.is_dir():
        for agent_file in sorted(agents_dir.glob("*.md")):
            fm_lines = frontmatter_lines(
                agent_file.read_text(encoding="utf-8"))
            name = _scalar(fm_lines, "name")
            if name:
                expected[name] = agent_file.stem
    loop_file = root / "egm-review-loop" / "SKILL.md"
    if not loop_file.is_file():
        findings.append("egm-review-loop: missing SKILL.md")
        return
    loop_text = loop_file.read_text(encoding="utf-8")
    table = {}
    for match in TABLE_PAIR_RE.finditer(loop_text):
        lineno = loop_text.count("\n", 0, match.start()) + 1
        table[match.group(1)] = (match.group(2), lineno)
    for name, stem in expected.items():
        if name not in table:
            findings.append(
                f"egm-review-loop/SKILL.md: persona {name!r} "
                f"(agents/{stem}.md) has no normalization-table entry")
        elif table[name][0] != stem:
            findings.append(
                f"egm-review-loop/SKILL.md:{table[name][1]}: "
                f"normalization table maps {name!r} to "
                f"{table[name][0]!r}, but the persona file is "
                f"agents/{stem}.md")
    for name, (shortname, lineno) in table.items():
        if name not in expected:
            findings.append(
                f"egm-review-loop/SKILL.md:{lineno}: normalization "
                f"table names {name!r} -> {shortname!r}, but no agent "
                f"file carries that frontmatter name")


def _paragraph_blocks(text):
    """Yield (start_lineno, block_text) for blank-line-separated blocks."""
    blocks = []
    current = []
    start = 1
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if not current:
                start = lineno
            current.append(line)
        elif current:
            blocks.append((start, "\n".join(current)))
            current = []
    if current:
        blocks.append((start, "\n".join(current)))
    return blocks


def check_standards_coverage(root, bundle, findings):
    """Rule (c): egm-review call-site standards maps cover their reviewers."""
    review_file = root / "egm-review" / "SKILL.md"
    if not review_file.is_file():
        findings.append("egm-review: missing SKILL.md")
        return
    standards_dir = bundle / "resources" / "document_standards"
    text = review_file.read_text(encoding="utf-8")
    for start, block in _paragraph_blocks(text):
        maps = []
        for brace in re.findall(r"\{[^{}]*\}", block):
            pairs = MAP_PAIR_RE.findall(brace)
            # A standards map maps reviewer names to standard shortnames;
            # brace groups whose values are prose (e.g. gate-question
            # JSON) are not standards maps.
            if pairs and all(STANDARD_NAME_RE.match(value)
                             for _, value in pairs):
                maps.append(dict(pairs))
        if not maps:
            continue
        reviewers = []
        for bracket in BRACKET_LIST_RE.findall(block):
            tokens = [token.strip() for token in bracket.split(",")]
            if tokens and all(NAME_TOKEN_RE.match(t) for t in tokens):
                reviewers.extend(tokens)
        covered = set()
        for standards_map in maps:
            covered.update(standards_map)
            for standard in standards_map.values():
                if not (standards_dir / f"{standard}.md").is_file():
                    findings.append(
                        f"egm-review/SKILL.md:{start}: standard "
                        f"{standard!r} has no file in "
                        f"resources/document_standards/")
        for reviewer in reviewers:
            if reviewer not in covered:
                findings.append(
                    f"egm-review/SKILL.md:{start}: reviewer "
                    f"{reviewer!r} has no entry in the call site's "
                    f"standards map")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fail if the EGM wrapper skills drift from the "
                    "vendored bundle or from their own frontmatter.")
    parser.add_argument("--root", required=True,
                        help="skills tree to scan")
    parser.add_argument("--bundle",
                        help="vendored EGM bundle tree (default: "
                             "<root>/../reference/elephant-goldfish-model)")
    args = parser.parse_args(argv)

    root = Path(args.root)
    bundle = (Path(args.bundle) if args.bundle
              else root.parent / "reference" / "elephant-goldfish-model")

    findings = []
    check_yaml_parity(root, findings)
    check_normalization_table(root, bundle, findings)
    check_standards_coverage(root, bundle, findings)

    for line in findings:
        print(line)
    if findings:
        print(f"{len(findings)} EGM drift finding(s)")
        return 1
    print(f"OK: EGM wrappers under {root} are consistent with their "
          f"frontmatter and the bundle at {bundle}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
