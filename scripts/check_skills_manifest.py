#!/usr/bin/env python3
"""Skills manifest checker -- the CI freshness gate for repo skill copies.

Bounded claim: This gate proves the repo skills/ tree equals the manifest
generated from the repo tree immediately after the last sync copied from
live -- a consistency claim about the sync's own output, never a freshness
claim against the live tree (CI cannot see live).

All scope and exclusion rules are parsed from
``.github/skills-sync-scope.txt`` in the repo this script lives in; no
rule is hardcoded here. The manifest is
``.github/skills-manifest.sha256`` in that same repo. Both are located
relative to the repo root -- the parent of the directory containing this
script -- never relative to ``--root`` or the current working directory.

Usage (exactly one mode):

    check_skills_manifest.py --root <tree> --check
    check_skills_manifest.py --root <tree> --write

``--root`` is the tree to hash; manifest paths are root-relative and use
the vendor line format ``<sha256hex>  ./<path>`` (two spaces), sorted by
path.

``--write`` walks each in-scope directory under ``--root``, applies the
path exclusions, then the content rule (a file whose bytes contain any
[exclude-content] literal is excluded and reported as
``excluded (content rule): <path>``), writes the manifest, and prints a
summary count.

``--check`` verifies the tree at ``--root`` against the manifest.
Divergences (each printed on its own line naming the path): a listed file
missing under ``--root``; a listed file whose sha256 differs; a listed
file whose bytes contain an [exclude-content] literal, reported as a
stale manifest entry; and any file present under an in-scope directory
that survives the path exclusions but is not listed (an unlisted in-scope
file, flagged whatever its contents -- the content rule does not apply to
unlisted files at check time). Exit 0 iff there are no divergences.
"""

import argparse
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCOPE_FILE = REPO_ROOT / ".github" / "skills-sync-scope.txt"
MANIFEST_FILE = REPO_ROOT / ".github" / "skills-manifest.sha256"


def parse_scope(text):
    """Parse the scope file into {section: [entries]} preserving order."""
    sections = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return sections


def is_path_excluded(rel_posix, exclude_paths):
    """Apply [exclude-paths] entries to a root-relative POSIX path.

    - bare name (no ``/``): matches any file with that basename;
    - entry ending in ``/**``: matches any file whose path contains the
      preceding component (or, if it contains ``/``, lives under that
      prefix);
    - any other entry containing ``/``: matches only that exact path.
    """
    parts = rel_posix.split("/")
    for entry in exclude_paths:
        if entry.endswith("/**"):
            base = entry[: -len("/**")]
            if "/" in base:
                if rel_posix == base or rel_posix.startswith(base + "/"):
                    return True
            elif base in parts:
                return True
        elif "/" in entry:
            if rel_posix == entry:
                return True
        elif parts[-1] == entry:
            return True
    return False


def iter_scope_files(root, skill_dirs):
    """Yield (rel_posix, path) for every regular file under the scope dirs."""
    for name in skill_dirs:
        base = root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.is_symlink():
                yield path.relative_to(root).as_posix(), path


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def contains_any(data, literals):
    return any(lit.encode() in data for lit in literals)


def do_write(root, scope):
    skill_dirs = scope.get("skills", [])
    exclude_paths = scope.get("exclude-paths", [])
    exclude_content = scope.get("exclude-content", [])
    entries = []
    for rel, path in iter_scope_files(root, skill_dirs):
        if is_path_excluded(rel, exclude_paths):
            continue
        data = path.read_bytes()
        if contains_any(data, exclude_content):
            print(f"excluded (content rule): {rel}")
            continue
        entries.append((rel, sha256_hex(data)))
    entries.sort(key=lambda e: e[0])
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{digest}  ./{rel}" for rel, digest in entries]
    MANIFEST_FILE.write_text("\n".join(lines) + ("\n" if lines else ""))
    print(f"wrote {len(entries)} entries to {MANIFEST_FILE}")
    return 0


def parse_manifest(text):
    """Parse vendor-format lines into [(rel_posix, sha256hex)]."""
    entries = []
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        digest, _, path = line.partition("  ")
        rel = path[2:] if path.startswith("./") else path
        entries.append((rel.strip(), digest.strip()))
    return entries


def do_check(root, scope):
    skill_dirs = scope.get("skills", [])
    exclude_paths = scope.get("exclude-paths", [])
    exclude_content = scope.get("exclude-content", [])
    listed = parse_manifest(MANIFEST_FILE.read_text())
    listed_rels = {rel for rel, _ in listed}
    divergences = []

    for rel, expected in listed:
        path = root / rel
        if not path.is_file():
            divergences.append(f"missing: {rel}")
            continue
        data = path.read_bytes()
        if contains_any(data, exclude_content):
            divergences.append(
                f"stale manifest entry: {rel} "
                "(file contains an [exclude-content] literal; "
                "regenerate the manifest during a sync)"
            )
            continue
        if sha256_hex(data) != expected:
            divergences.append(f"hash mismatch: {rel}")

    for rel, _path in iter_scope_files(root, skill_dirs):
        if is_path_excluded(rel, exclude_paths):
            continue
        if rel not in listed_rels:
            divergences.append(f"unlisted in-scope file: {rel}")

    for line in divergences:
        print(line)
    if divergences:
        print(f"{len(divergences)} divergence(s)")
        return 1
    print(f"OK: {len(listed)} manifest entries match the tree at {root}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, help="tree to hash")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="verify tree against the manifest")
    mode.add_argument("--write", action="store_true", help="regenerate the manifest from the tree")
    args = parser.parse_args(argv)

    root = Path(args.root)
    scope = parse_scope(SCOPE_FILE.read_text())
    if args.write:
        return do_write(root, scope)
    return do_check(root, scope)


if __name__ == "__main__":
    sys.exit(main())
