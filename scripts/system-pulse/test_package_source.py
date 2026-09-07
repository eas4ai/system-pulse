"""Packaging excludes active Cairn streams, while requiring committed inputs."""

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import package_linux


class PackageSourceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "-q")
        self.write("source.rs", "committed source\n")
        self.git("add", ".")
        self.commit()
        self.patcher = patch.object(package_linux, "ROOT", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        )

    def write(self, name, contents="runtime evidence\n"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    def commit(self):
        self.git(
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=Package test",
            "-c",
            "user.email=package@example.invalid",
            "commit",
            "-qm",
            "fixture",
        )

    def test_active_untracked_cairn_streams_do_not_dirty_committed_source(self):
        # A committed sibling prevents porcelain from collapsing the directory.
        self.write(".cairn/evidence/APP-001/previous")
        self.git("add", ".")
        self.commit()
        self.write(".cairn/in-progress")
        for extension in ("out", "err"):
            self.write(
                f".cairn/evidence/APP-001/20260907T025635676Z-1048805.{extension}"
            )
        package_linux.require_committed_source()

    def test_modified_source_and_untracked_source_remain_rejected(self):
        self.write("source.rs", "uncommitted source\n")
        with self.assertRaisesRegex(ValueError, "source.rs"):
            package_linux.require_committed_source()
        self.git("restore", "source.rs")
        self.write("new.rs")
        with self.assertRaisesRegex(ValueError, "new.rs"):
            package_linux.require_committed_source()

    def test_modified_tracked_evidence_is_not_an_active_untracked_stream(self):
        path = ".cairn/evidence/APP-001/20260907T025635676Z-1048805.out"
        self.write(path)
        self.git("add", ".")
        self.commit()
        self.write(path, "changed committed evidence\n")
        with self.assertRaisesRegex(ValueError, "Commit the source"):
            package_linux.require_committed_source()

    def test_other_untracked_cairn_files_are_not_exempt(self):
        self.write(".cairn/evidence/APP-001/previous")
        self.git("add", ".")
        self.commit()
        self.write(".cairn/evidence/APP-001/unexpected.py")
        with self.assertRaisesRegex(ValueError, "unexpected.py"):
            package_linux.require_committed_source()


if __name__ == "__main__":
    unittest.main()
