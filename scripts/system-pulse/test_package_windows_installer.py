"""Reject tampered installer inputs before invoking signing tools."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from package_binary import WINDOWS_AMD_NOTICE_FILES
from package_linux import ROOT
from package_windows_installer import validate_package, verify_prerequisite
from release_ci_verify import REQUIRED


def amd_source_archive(module=None):
    output = io.BytesIO()
    if module is None:
        module = (ROOT / "vendor/pawnio-amd-smn/AMDFamily17.bin").read_bytes()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        entry = tarfile.TarInfo("system-pulse-source/vendor/pawnio-amd-smn/AMDFamily17.bin")
        entry.size = len(module)
        bundle.addfile(entry, io.BytesIO(module))
    return output.getvalue()

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
        for name in WINDOWS_AMD_NOTICE_FILES:
            source = {
                "notices/PawnIO-AMDFamily17-COPYING": "vendor/pawnio-intel-msr/COPYING",
                "notices/PawnIO-AMDFamily17-NOTICE.md": "vendor/pawnio-amd-smn/README.md",
                "notices/PawnIO-AMDFamily17-source-upstream.tar.gz": "vendor/pawnio-intel-msr/source-upstream.tar.gz",
            }[name]
            (self.root / name).write_bytes((ROOT / source).read_bytes())
        (self.root / "notices/PawnIO-IntelMSR-COPYING").write_bytes(
            (ROOT / "vendor/pawnio-intel-msr/COPYING").read_bytes()
        )
        (self.root / "source.tar.gz").write_bytes(amd_source_archive())
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
        for name in (
            "source.tar.gz",
            "COPYING",
            "notices/PawnIO-driver-COPYING",
            "notices/PawnIO-AMDFamily17-COPYING",
            "notices/PawnIO-AMDFamily17-source-upstream.tar.gz",
        ):
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
        (self.root / "source.tar.gz").write_bytes(amd_source_archive())
        (self.root / "SOURCE.txt").write_text("wrong revision")
        self.manifest()
        with self.assertRaises(ValueError): validate_package(self.root)

    def test_amd_notice_upstream_archive_and_embedded_module_are_pinned(self):
        for name, content in (
            ("notices/PawnIO-AMDFamily17-NOTICE.md", b"notice changed"),
            ("notices/PawnIO-AMDFamily17-source-upstream.tar.gz", b"source changed"),
            ("notices/PawnIO-AMDFamily17-COPYING", b"license changed"),
            ("source.tar.gz", amd_source_archive(b"module changed")),
        ):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(content)
                if name == "source.tar.gz":
                    build_path = self.root / "build.json"
                    build = json.loads(build_path.read_text())
                    build["source_archive_sha256"] = hashlib.sha256(content).hexdigest()
                    build_path.write_text(json.dumps(build))
                self.manifest()
                with self.assertRaises(ValueError):
                    validate_package(self.root)
                path.write_bytes(original)
                if name == "source.tar.gz":
                    build_path = self.root / "build.json"
                    build = json.loads(build_path.read_text())
                    build["source_archive_sha256"] = hashlib.sha256(original).hexdigest()
                    build_path.write_text(json.dumps(build))
                self.manifest()
