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
line naming the file and the inconsistency, and -- where the finding
is tied to a specific table row or call site -- the line number.
"""

import argparse
import json
import re
import sys
from pathlib import Path

BLOCK_INDICATOR_RE = re.compile(r"^[>|][+-]?[0-9]?$")
TABLE_PAIR_RE = re.compile(r"`(egm-[a-z0-9-]+)`\s*→\s*`([a-z0-9_]+)`")
FRONTMATTER_NAMES_RE = re.compile(r"\*\*Frontmatter Names\*\*")
MAP_PAIR_RE = re.compile(r'"([^"]+)"\s*:\s*"([^"]+)"')
STANDARD_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
BRACKET_LIST_RE = re.compile(r"\[([^\[\]]+)\]")
NAME_TOKEN_RE = re.compile(r"^[a-z0-9_-]+$")


def _scalar(lines, key):
    """Value of a top-level YAML ``key`` in ``lines``, or None.

    Handles the scalar shapes the EGM files actually use: a plain
    single-line value, a double-quoted or single-quoted single-line
    value, and a ``>``/``|`` block scalar with indented continuation
    lines.
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
        if len(value) >= 2 and value.startswith("'") \
                and value.endswith("'"):
            return value[1:-1].replace("''", "'")
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


def _normalization_pairs(text):
    """(pairs, problem) for the normalization table in the loop file.

    The scan reads ONLY the designated block: the paragraph block
    carrying the ``**Frontmatter Names**`` lead-in, which is how the
    loop file itself designates the block that holds the table
    ("Normalize it through this table"). Pairs anywhere else in the
    file are prose: they can neither stand in for a table row nor
    trigger a finding. (An earlier version anchored on the block
    carrying the most pairs; a verbatim roster restated in prose
    could hijack that anchor and silently certify a corrupt table --
    panel finding J117-1.)

    ``problem`` is None on success; otherwise it describes why the
    designated block could not be used, and the caller fails closed.
    """
    designated = [(start, block) for start, block in _paragraph_blocks(text)
                  if FRONTMATTER_NAMES_RE.search(block)]
    if len(designated) != 1:
        return [], (f"found {len(designated)} block(s) carrying the "
                    f"**Frontmatter Names** lead-in")
    start, block = designated[0]
    pairs = [(match.group(1), match.group(2),
              start + block[:match.start()].count("\n"))
             for match in TABLE_PAIR_RE.finditer(block)]
    if not pairs:
        return [], ("the designated **Frontmatter Names** block "
                    "carries no name -> shortname pairs")
    return pairs, None


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
    pairs, problem = _normalization_pairs(loop_text)
    if problem is not None:
        findings.append(
            f"egm-review-loop/SKILL.md: cannot read the normalization "
            f"table: {problem}; rule (b) fails closed rather than "
            f"guessing which block is the table")
        return
    table = {}
    for name, shortname, lineno in pairs:
        if name in table:
            findings.append(
                f"egm-review-loop/SKILL.md:{lineno}: normalization "
                f"table lists {name!r} more than once (first at line "
                f"{table[name][1]}); the later entry silently wins")
        table[name] = (shortname, lineno)
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


def _standards_maps(block):
    """Yield (offset, pairs, malformed) per standards-map-shaped group.

    A brace group is standards-map-shaped when every key is a
    reviewer-name token and every value is a single token (no
    whitespace): standards maps map reviewer names to standard
    identifiers. Groups whose values are prose sentences (e.g.
    gate-question JSON) are not standards maps and are ignored.
    Within a shaped group, ``malformed`` holds the (key, value) pairs
    whose value is not a valid standard identifier; the group still
    counts as a map — a malformed value is a finding, never a reason
    to discard the whole group.
    """
    for match in re.finditer(r"\{[^{}]*\}", block):
        pairs = MAP_PAIR_RE.findall(match.group(0))
        if not pairs:
            continue
        if not all(NAME_TOKEN_RE.match(key) for key, _ in pairs):
            continue
        if any(any(ch.isspace() for ch in value) for _, value in pairs):
            continue
        malformed = [(key, value) for key, value in pairs
                     if not STANDARD_NAME_RE.match(value)]
        yield match.start(), pairs, malformed


def check_standards_coverage(root, bundle, findings):
    """Rule (c): egm-review call-site standards maps cover their reviewers.

    Coverage is judged per call site: within a paragraph block, each
    reviewer bracket list opens a call site, and only the standards
    maps that follow it (up to the next reviewer list) count toward
    its coverage — maps are never pooled across call sites.
    """
    review_file = root / "egm-review" / "SKILL.md"
    if not review_file.is_file():
        findings.append("egm-review: missing SKILL.md")
        return
    standards_dir = bundle / "resources" / "document_standards"
    text = review_file.read_text(encoding="utf-8")
    for start, block in _paragraph_blocks(text):
        maps = list(_standards_maps(block))
        for offset, pairs, malformed in maps:
            line = start + block[:offset].count("\n")
            malformed_pairs = set(malformed)
            for key, value in malformed:
                findings.append(
                    f"egm-review/SKILL.md:{line}: standard name "
                    f"{value!r} for reviewer {key!r} is malformed "
                    f"(expected a kebab-case standard identifier)")
            for key, standard in pairs:
                if (key, standard) in malformed_pairs:
                    continue
                if not (standards_dir / f"{standard}.md").is_file():
                    findings.append(
                        f"egm-review/SKILL.md:{line}: standard "
                        f"{standard!r} has no file in "
                        f"resources/document_standards/")
        sites = []
        for match in BRACKET_LIST_RE.finditer(block):
            tokens = [token.strip() for token in match.group(1).split(",")]
            if tokens and all(NAME_TOKEN_RE.match(t) for t in tokens):
                sites.append((match.start(), tokens))
        for idx, (offset, tokens) in enumerate(sites):
            end = sites[idx + 1][0] if idx + 1 < len(sites) else len(block)
            covered = set()
            for map_offset, pairs, _malformed in maps:
                if offset <= map_offset < end:
                    covered.update(key for key, _ in pairs)
            line = start + block[:offset].count("\n")
            for reviewer in tokens:
                if reviewer not in covered:
                    findings.append(
                        f"egm-review/SKILL.md:{line}: reviewer "
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
