"""Reject tampered installer inputs before invoking signing tools."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from package_windows_installer import validate_package, verify_prerequisite

class InstallerInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "system-pulse.exe").write_bytes(b"fixture")
        (self.root / "build.json").write_text(json.dumps({"target": "x86_64-pc-windows-msvc", "source_commit": "a" * 40, "version": "0.1.0", "binary_sha256": hashlib.sha256(b"fixture").hexdigest()}))
        self.manifest()

    def manifest(self):
        (self.root / "package-files.json").write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir() if p.name != "package-files.json"}))

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
        (self.root / "package-files.json").write_text(json.dumps({"../outside": "0" * 64}))
        with self.assertRaises(ValueError): validate_package(self.root)

    def test_wrong_platform_and_binary_provenance(self):
        p = self.root / "build.json"
        d = json.loads(p.read_text()); d["target"] = "aarch64-apple-darwin"; p.write_text(json.dumps(d)); self.manifest()
        with self.assertRaises(ValueError): validate_package(self.root)
        d["target"] = "x86_64-pc-windows-msvc"; d["binary_sha256"] = "0" * 64; p.write_text(json.dumps(d)); self.manifest()
        with self.assertRaises(ValueError): validate_package(self.root)

    def test_prerequisite_must_match_pinned_official_release(self):
        with self.assertRaises(ValueError): verify_prerequisite(self.root / "system-pulse.exe")
