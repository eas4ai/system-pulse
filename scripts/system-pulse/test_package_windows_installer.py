"""Reject tampered installer inputs before invoking signing tools."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from package_windows_installer import validate_package, verify_prerequisite
from release_ci_verify import REQUIRED

class InstallerInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "system-pulse.exe").write_bytes(b"fixture")
        (self.root / "build.json").write_text(json.dumps({"target": "x86_64-pc-windows-msvc", "source_commit": "a" * 40, "version": "0.1.0", "binary_sha256": hashlib.sha256(b"fixture").hexdigest()}))
        for name in REQUIRED - {"build.json"}:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("a" * 40)
        for name in ("PawnIO-IntelMSR-COPYING", "PawnIO-IntelMSR-NOTICE.md", "PawnIO-driver-COPYING", "PawnIO-driver-NOTICE.md", "PawnIO-driver-README.md"):
            (self.root / "notices" / name).write_text("license fixture")
        p = self.root / "build.json"
        build = json.loads(p.read_text())
        build["source_archive_sha256"] = hashlib.sha256((self.root / "source.tar.gz").read_bytes()).hexdigest()
        p.write_text(json.dumps(build))
        self.manifest()

    def manifest(self):
        (self.root / "package-files.json").write_text(json.dumps({p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob("*") if p.is_file() and p.name != "package-files.json"}))

    def test_intact_package_and_tampered_binary(self):
        self.assertEqual(validate_package(self.root)["source_commit"], "a" * 40)
        (self.root / "system-pulse.exe").write_bytes(b"changed")
        with self.assertRaises(ValueError): validate_package(self.root)

    def test_extra_missing_and_escaping_paths(self):
        (self.root / "extra.exe").write_bytes(b"extra")
        with self.assertRaises(ValueError): validate_package(self.root)
        (self.root / "extra.exe").unlink()
        (self.root / "system-pulse.exe").unlink()
        with self.assertRaises(ValueError): validate_package(self.root)
        (self.root / "system-pulse.exe").write_bytes(b"fixture")
        self.manifest()
        p = self.root / "package-files.json"
        manifest = json.loads(p.read_text()); manifest["../outside"] = "0" * 64
        p.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "unsafe path"): validate_package(self.root)

    def test_wrong_platform_and_binary_provenance(self):
        p = self.root / "build.json"
        d = json.loads(p.read_text()); d["target"] = "aarch64-apple-darwin"; p.write_text(json.dumps(d)); self.manifest()
        with self.assertRaises(ValueError): validate_package(self.root)
        d["target"] = "x86_64-pc-windows-msvc"; d["binary_sha256"] = "0" * 64; p.write_text(json.dumps(d)); self.manifest()
        with self.assertRaises(ValueError): validate_package(self.root)

    def test_prerequisite_must_match_pinned_official_release(self):
        with self.assertRaises(ValueError): verify_prerequisite(self.root / "system-pulse.exe")

    def test_source_and_licenses_are_required_even_with_updated_manifest(self):
        for name in ("source.tar.gz", "COPYING", "notices/PawnIO-driver-COPYING"):
            with self.subTest(name=name):
                path = self.root / name
                content = path.read_bytes()
                path.unlink(); self.manifest()
                with self.assertRaises(ValueError): validate_package(self.root)
                path.write_bytes(content); self.manifest()

    def test_source_hash_and_revision_are_validated(self):
        (self.root / "source.tar.gz").write_bytes(b"different source")
        self.manifest()
        with self.assertRaises(ValueError): validate_package(self.root)
        (self.root / "source.tar.gz").write_text("a" * 40)
        (self.root / "SOURCE.txt").write_text("wrong revision")
        self.manifest()
        with self.assertRaises(ValueError): validate_package(self.root)
