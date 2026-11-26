#!/usr/bin/env python3
"""Tests for scripts/check_vendor_integrity.py (stdlib unittest, temp fixtures only).

Each test builds a tiny fake repo (reference/<name>/, .github/vendor-<name>.sha256)
and runs the checker as a subprocess, asserting exit code and diagnostics.
"""

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_vendor_integrity.py"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class VendorIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "reference").mkdir()
        (self.root / ".github").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def add_tree(self, name, files=None, provenance=True, manifest=True):
        files = files if files is not None else {"a.txt": b"alpha\n", "sub/b.txt": b"beta\n"}
        tree = self.root / "reference" / name
        tree.mkdir(parents=True)
        if provenance:
            (tree / "PROVENANCE.md").write_text("# provenance\n")
        lines = []
        for rel, data in files.items():
            p = tree / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            lines.append(f"{sha(data)}  ./{rel}")
        if provenance:
            lines.append(sha(b"# provenance\n") + "  ./PROVENANCE.md")
        if manifest:
            (self.root / ".github" / f"vendor-{name}.sha256").write_text("\n".join(sorted(lines)) + "\n")
        return tree

    def run_check(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            capture_output=True, text=True,
        )

    def test_clean_repo_passes(self):
        self.add_tree("alpha")
        self.add_tree("beta-tree")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("alpha", r.stdout)
        self.assertIn("beta-tree", r.stdout)

    def test_filename_with_spaces(self):
        self.add_tree("spacey", {"my file.txt": b"x\n", "dir one/two words.md": b"y\n"})
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_orphan_dir_without_manifest_fails(self):
        self.add_tree("alpha")
        self.add_tree("orphan", manifest=False)
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("orphan", out)
        self.assertIn("vendor-orphan.sha256", out)

    def test_stale_manifest_without_dir_fails(self):
        self.add_tree("alpha")
        (self.root / ".github" / "vendor-ghost.sha256").write_text(f"{sha(b'x')}  ./x\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("ghost", out)
        self.assertIn("reference/ghost", out)

    def test_missing_provenance_fails(self):
        self.add_tree("alpha", provenance=False)
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("alpha", out)
        self.assertIn("PROVENANCE.md", out)

    def test_corrupted_file_byte_fails(self):
        tree = self.add_tree("alpha")
        (tree / "a.txt").write_bytes(b"alphX\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("a.txt", out)
        self.assertIn("alpha", out)

    def test_missing_listed_file_fails(self):
        tree = self.add_tree("alpha")
        (tree / "a.txt").unlink()
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("a.txt", r.stdout + r.stderr)

    def test_unlisted_file_fails(self):
        tree = self.add_tree("alpha")
        (tree / "extra.txt").write_text("smuggled\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("extra.txt", out)
        self.assertIn("unlisted", out)

    def test_broken_symlink_fails(self):
        tree = self.add_tree("alpha")
        os.symlink("does-not-exist", tree / "dangling")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("dangling", out)
        self.assertIn("symlink", out)

    def test_valid_symlink_passes(self):
        tree = self.add_tree("alpha")
        os.symlink("a.txt", tree / "link-ok")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_escaping_symlink_fails(self):
        tree = self.add_tree("alpha")
        outside = self.root / "outside.txt"
        outside.write_text("secret\n")
        os.symlink(str(outside), tree / "escape-link")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("escape-link", out)
        self.assertIn("escapes", out)

    def test_symlinked_tree_root_fails(self):
        # An external directory with matching hashes must not pass as a
        # vendored tree just because the manifest agrees with it.
        ext = self.root / "external" / "gamma"
        ext.mkdir(parents=True)
        (ext / "a.txt").write_bytes(b"alpha\n")
        (ext / "PROVENANCE.md").write_text("# provenance\n")
        lines = [f"{sha(b'alpha\n')}  ./a.txt",
                 f"{sha(b'# provenance\n')}  ./PROVENANCE.md"]
        (self.root / ".github" / "vendor-gamma.sha256").write_text(
            "\n".join(sorted(lines)) + "\n")
        os.symlink(ext, self.root / "reference" / "gamma")
        r = self.run_check()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        out = r.stdout + r.stderr
        self.assertIn("gamma", out)
        self.assertIn("symlink", out)

    def test_duplicate_manifest_entry_fails(self):
        self.add_tree("alpha")
        manifest = self.root / ".github" / "vendor-alpha.sha256"
        existing = manifest.read_text()
        bad_line = f"{'0' * 64}  ./a.txt\n"
        manifest.write_text(bad_line + existing)
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("duplicate manifest entry", out)
        self.assertIn("a.txt", out)

    def test_manifest_path_traversal_and_absolute_fail(self):
        self.add_tree("alpha")
        outside = self.root / "outside.txt"
        outside.write_bytes(b"out\n")
        manifest = self.root / ".github" / "vendor-alpha.sha256"
        existing = manifest.read_text()
        h = sha(b"out\n")
        manifest.write_text(
            existing
            + f"{h}  ../outside.txt\n"
            + f"{h}  {outside}\n"
        )
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("unsafe manifest path", out)
        self.assertIn("../outside.txt", out)
        self.assertIn(str(outside), out)

    def test_non_utf8_manifest_fails_cleanly(self):
        self.add_tree("alpha")
        manifest = self.root / ".github" / "vendor-alpha.sha256"
        manifest.write_bytes(b"\xff\xfe\x00\x01")
        r = self.run_check()
        self.assertEqual(r.returncode, 1)
        out = r.stdout + r.stderr
        self.assertIn("not valid UTF-8", out)
        self.assertNotIn("Traceback", out)

    def test_default_root_is_cwd(self):
        self.add_tree("alpha")
        r = subprocess.run([sys.executable, str(SCRIPT)], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_reference_trees_fails(self):
        r = self.run_check()
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
