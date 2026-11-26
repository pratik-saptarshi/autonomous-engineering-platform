#!/usr/bin/env python3
"""Verify every vendored tree under reference/ against its pinned SHA-256 manifest.

Replaces the hand-enumerated per-tree ``run:`` blocks in CI. Adding a tree under
``reference/`` without a manifest (or leaving a stale manifest behind) now fails
here by construction, instead of silently going unchecked.

Checks:
  1. Three-way set equality, by tree name:
       reference/<name>/ dirs  ==  .github/vendor-<name>.sha256 manifests
                               ==  trees containing reference/<name>/PROVENANCE.md
     (the PROVENANCE.md set matches scripts/vendor_graph.py's view).
  2. Per tree: every manifest entry exists and hashes to its recorded SHA-256.
  3. Per tree: no regular file exists that the manifest does not list
     (the old ``comm -23`` semantics; symlinks are not regular files).
  4. Per tree: no broken symlinks.

Stdlib only. Exit 0 = clean, 1 = any finding (all findings are printed).
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path

MANIFEST_PREFIX = "vendor-"
MANIFEST_SUFFIX = ".sha256"


def discover_trees(root: Path):
    ref = root / "reference"
    if not ref.is_dir():
        return set()
    return {p.name for p in ref.iterdir() if p.is_dir()}


def discover_manifests(root: Path):
    gh = root / ".github"
    if not gh.is_dir():
        return set()
    return {
        p.name[len(MANIFEST_PREFIX):-len(MANIFEST_SUFFIX)]
        for p in gh.glob(f"{MANIFEST_PREFIX}*{MANIFEST_SUFFIX}")
        if p.is_file()
    }


def discover_provenance(root: Path, trees):
    return {n for n in trees if (root / "reference" / n / "PROVENANCE.md").is_file()}


def parse_manifest(path: Path):
    """Return ({relpath: sha}, [parse errors]). Handles sha256sum text format.

    Line = ``<64 hex><space><space or *><path>``; the path is everything after
    the two-character separator, so spaces in names are preserved. A leading
    ``./`` is stripped. A leading backslash on the line marks an escaped name
    (``\\n``/``\\\\``) as sha256sum emits it; those are unescaped.
    """
    entries, errors = {}, []
    text = path.read_bytes().decode("utf-8")
    for lineno, line in enumerate(text.split("\n"), 1):
        if not line:
            continue
        escaped = line.startswith("\\")
        body = line[1:] if escaped else line
        if len(body) < 67 or body[64] != " " or body[65] not in (" ", "*"):
            errors.append(f"{path.name}:{lineno}: malformed manifest line")
            continue
        digest, name = body[:64].lower(), body[66:]
        if any(c not in "0123456789abcdef" for c in digest):
            errors.append(f"{path.name}:{lineno}: malformed SHA-256 digest")
            continue
        if escaped:
            name = name.replace("\\\\", "\x00").replace("\\n", "\n").replace("\x00", "\\")
        if name.startswith("./"):
            name = name[2:]
        entries[name] = digest
    return entries, errors


def sha256_file(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_tree(root: Path, name: str):
    findings = []
    tree = root / "reference" / name
    manifest = root / ".github" / f"{MANIFEST_PREFIX}{name}{MANIFEST_SUFFIX}"
    entries, errors = parse_manifest(manifest)
    findings.extend(f"[{name}] {e}" for e in errors)

    for rel, digest in sorted(entries.items()):
        p = tree / rel
        if not p.is_file():  # follows symlinks, like sha256sum -c
            findings.append(f"[{name}] missing listed file: {rel}")
            continue
        if sha256_file(p) != digest:
            findings.append(f"[{name}] SHA-256 mismatch: {rel}")

    regular, broken = set(), []
    for dirpath, dirnames, filenames in os.walk(tree, followlinks=False):
        dp = Path(dirpath)
        for entry in dirnames + filenames:
            p = dp / entry
            rel = p.relative_to(tree).as_posix()
            if p.is_symlink():
                if not p.exists():
                    broken.append(rel)
            elif p.is_file():
                regular.add(rel)
    for rel in sorted(regular - set(entries)):
        findings.append(f"[{name}] unlisted file (not in {manifest.name}): {rel}")
    for rel in sorted(broken):
        findings.append(f"[{name}] broken symlink: {rel}")
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".", help="repository root (default: .)")
    args = ap.parse_args(argv)
    root = Path(args.root)

    trees = discover_trees(root)
    manifests = discover_manifests(root)
    provenance = discover_provenance(root, trees)

    findings = []
    if not trees:
        findings.append("no vendored trees found under reference/")
    for n in sorted(trees - manifests):
        findings.append(
            f"reference/{n}/ has no manifest: expected .github/{MANIFEST_PREFIX}{n}{MANIFEST_SUFFIX}"
        )
    for n in sorted(manifests - trees):
        findings.append(
            f".github/{MANIFEST_PREFIX}{n}{MANIFEST_SUFFIX} is stale: reference/{n}/ does not exist"
        )
    for n in sorted(trees - provenance):
        findings.append(f"reference/{n}/ has no PROVENANCE.md")
    for n in sorted(provenance - trees):  # unreachable by construction; kept for symmetry
        findings.append(f"reference/{n}/PROVENANCE.md without tree")

    checked = sorted(trees & manifests)
    for n in checked:
        findings.extend(check_tree(root, n))

    if findings:
        for f in findings:
            print(f"ERROR: {f}")
        print(f"FAIL: vendor integrity: {len(findings)} finding(s) across {len(checked)} checked tree(s)")
        return 1
    print(f"OK: vendor integrity: {len(checked)} trees verified: {', '.join(checked)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
