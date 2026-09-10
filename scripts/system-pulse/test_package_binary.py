"""Artifact integrity and platform checks, independent of native build tools."""

import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from package_binary import TARGETS, check_binary_header, make_archive, main
from package_linux import ROOT, write_source_archive
from release_ci_verify import REQUIRED, archive_files, verify_archive, verify_source


def header(target):
    data = bytearray(256)
    if "linux" in target:
        data[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", data, 18, 62)
    elif "apple" in target:
        data[:4] = b"\xcf\xfa\xed\xfe"
        struct.pack_into("<I", data, 4, 0x0100000C)
    else:
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 60, 128)
        data[128:134] = b"PE\0\0\x64\x86"
    return bytes(data)


class BinaryArchiveTests(unittest.TestCase):
    def test_license_report_is_utf8_with_windows_default_encoding(self):
        report = {"notice": "Copyright \u0141ukasz \u6771\u4eac"}
        encoded = json.dumps(report, ensure_ascii=False).encode("utf-8")
        with self.assertRaises(UnicodeDecodeError):
            encoded.decode("cp1252")

        class ReportReceived(Exception):
            pass

        original_read_text = Path.read_text

        def windows_read_text(path, encoding=None, errors=None):
            return original_read_text(path, encoding=encoding or "cp1252", errors=errors)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            binary = root / "release/system-pulse.exe"
            binary.parent.mkdir()
            binary.write_bytes(header("x86_64-pc-windows-msvc"))

            def run(command, log, timeout):
                if "generate" in command:
                    (output / "license-report.json").write_bytes(encoded)

            with patch("sys.argv", ["package_binary.py", "--target", "x86_64-pc-windows-msvc",
                                    "--output", str(output)]), \
                 patch("package_binary.require_committed_source"), \
                 patch("package_binary.shutil.which", return_value="cargo-about"), \
                 patch("package_binary.capture", side_effect=[
                     "host: x86_64-pc-windows-msvc", "cargo-about 0.9.2", "revision",
                     json.dumps({"target_directory": str(root)})]), \
                 patch("package_binary.run", side_effect=run), \
                 patch("package_binary.write_licenses", side_effect=ReportReceived) as write, \
                 patch.object(Path, "read_text", windows_read_text):
                with self.assertRaises(ReportReceived):
                    main()
                self.assertEqual(write.call_args.args[0], report)

    def test_headers_reject_other_architectures_and_truncation(self):
        for target in TARGETS:
            check_binary_header(header(target), target)
            for other in TARGETS:
                if other != target:
                    with self.assertRaises(ValueError):
                        check_binary_header(header(other), target)
            with self.assertRaises(ValueError):
                check_binary_header(b"", target)
        data = bytearray(header("x86_64-pc-windows-msvc"))
        struct.pack_into("<I", data, 60, 0xFFFFFFFF)
        with self.assertRaises(ValueError):
            check_binary_header(data, "x86_64-pc-windows-msvc")

    def package(self, output, target):
        label, executable = TARGETS[target]
        package = output / ("system-pulse-" + label)
        package.mkdir()
        for name in REQUIRED:
            path = package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"notice")
        (package / executable).write_bytes(header(target))
        (package / "SOURCE.txt").write_text("revision")
        (package / "dependency-licenses.json").write_text(json.dumps({
            "packages": [{"license": "MIT"}], "notices": [{"text": "MIT notice"}]}))
        (package / "build.json").write_text(json.dumps({
            "source_commit": "revision", "target": target, "platform": label,
            "binary_sha256": hashlib.sha256(header(target)).hexdigest(),
            "source_archive_sha256": hashlib.sha256(b"notice").hexdigest(),
            "runtime_libraries": ["system"], "dependency_count": 1, "github_run_id": "123"}))
        files = {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in package.rglob("*") if p.is_file()}
        (package / "package-files.json").write_text(json.dumps(files))
        return package

    def test_all_platform_archives_and_tampering(self):
        for target in TARGETS:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary)
                package = self.package(output, target)
                archive = make_archive(package, output, "windows" in target)
                with patch("release_ci_verify.verify_source") as source:
                    verify_archive(output, target, "revision", "123")
                    source.assert_called_once_with(b"notice", "revision")
                    with self.assertRaisesRegex(ValueError, "another hosted run"):
                        verify_archive(output, target, "revision", "124")
                    with self.assertRaisesRegex(ValueError, "source revision"):
                        verify_archive(output, target, "wrong")
                    (package / TARGETS[target][1]).write_bytes(b"replaced")
                    archive.unlink()
                    make_archive(package, output, "windows" in target)
                    with self.assertRaisesRegex(ValueError, "checksums"):
                        verify_archive(output, target, "revision")
                (output / "SHA256SUMS").write_text("wrong")
                with self.assertRaisesRegex(ValueError, "checksum"):
                    verify_archive(output, target, "revision")

    def test_rejects_path_traversal_and_links_without_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../outside", "bad")
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                archive_files(archive)
            archive = Path(temporary) / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                entry = tarfile.TarInfo("package/link")
                entry.type = tarfile.SYMTYPE
                entry.linkname = "/outside"
                bundle.addfile(entry)
            with self.assertRaisesRegex(ValueError, "nonregular"):
                archive_files(archive)

    def test_source_archive_matches_actual_git_tree(self):
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {
            "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "core.autocrlf", "GIT_CONFIG_VALUE_0": "true",
            "GIT_CONFIG_KEY_1": "core.eol", "GIT_CONFIG_VALUE_1": "crlf",
        }):
            archive = Path(temporary) / "source.tar.gz"
            write_source_archive(archive, revision, Path(temporary) / "source.log")
            data = archive.read_bytes()
        verify_source(data, revision)
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as bundle:
            entry = tarfile.TarInfo("system-pulse-source/Cargo.lock")
            entry.size = 3
            bundle.addfile(entry, io.BytesIO(b"bad"))
        with self.assertRaisesRegex(ValueError, "committed git tree"):
            verify_source(stream.getvalue(), revision)


if __name__ == "__main__":
    unittest.main()
