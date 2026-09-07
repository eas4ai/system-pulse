"""Installer tests own every file under their temporary prefix."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).parents[2] / "examples/system_pulse/package/install.py"
spec = importlib.util.spec_from_file_location("pulse_install", MODULE)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class PackageInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / "package"
        self.package.mkdir()
        self.prefix = self.root / "prefix with spaces"
        files = {
            "system-pulse": b"owned test binary",
            "icon.svg": b"<svg/>",
            "install.py": b"# owned installer",
        }
        for name, data in files.items():
            (self.package / name).write_bytes(data)
        (self.package / "package-files.json").write_text(
            json.dumps(
                {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
            )
        )

    def test_install_is_repeatable_and_removal_preserves_configuration_and_unowned_files(
        self,
    ):
        self.prefix.mkdir()
        config = self.prefix / ".config/system-pulse/workspace.json"
        config.parent.mkdir(parents=True)
        config.write_text("saved layout")
        installer.install(self.package, self.prefix)
        binary = self.prefix / "bin/system-pulse"
        self.assertEqual(binary.read_bytes(), b"owned test binary")
        self.assertTrue(binary.is_symlink())
        self.assertEqual(
            installer.install(self.package, self.prefix), "already installed"
        )
        kept = self.prefix / "lib/system-pulse/user-note.txt"
        kept.write_text("keep this")
        self.assertEqual(installer.uninstall(self.prefix), [])
        self.assertFalse(binary.exists())
        self.assertEqual(config.read_text(), "saved layout")
        self.assertEqual(kept.read_text(), "keep this")
        self.assertEqual(installer.uninstall(self.prefix), [])

    def test_missing_or_changed_binary_and_conflicting_installation_write_nothing(self):
        (self.package / "system-pulse").unlink()
        with self.assertRaises((ValueError, OSError)):
            installer.install(self.package, self.prefix)
        self.assertFalse(self.prefix.exists())
        (self.package / "system-pulse").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            installer.install(self.package, self.prefix)
        self.assertFalse(self.prefix.exists())
        (self.package / "system-pulse").write_bytes(b"owned test binary")
        self.prefix.joinpath("bin").mkdir(parents=True)
        self.prefix.joinpath("bin/system-pulse").write_text("another application")
        with self.assertRaises(FileExistsError):
            installer.install(self.package, self.prefix)
        self.assertEqual(
            self.prefix.joinpath("bin/system-pulse").read_text(), "another application"
        )
        self.assertFalse(self.prefix.joinpath("lib").exists())

    def test_path_escape_and_symlinked_parents_are_rejected(self):
        manifest = self.package / "package-files.json"
        original = manifest.read_text()
        manifest.write_text(json.dumps({"../outside": "0" * 64}))
        with self.assertRaises(ValueError):
            installer.install(self.package, self.prefix)
        manifest.write_text(original)
        self.prefix.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        self.prefix.joinpath("lib").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            installer.install(self.package, self.prefix)
        self.assertEqual(list(outside.iterdir()), [])

    def test_write_failure_rolls_back_only_files_created_by_this_install(self):
        real_link = installer.os.link
        calls = []

        def fail_second(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise OSError("owned disk failure")
            return real_link(source, target)

        with patch.object(installer.os, "link", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "owned disk failure"):
                installer.install(self.package, self.prefix)
        self.assertFalse(self.prefix.exists())
        self.assertEqual(installer.install(self.package, self.prefix), "installed")

    def test_modified_installed_files_are_retained(self):
        installer.install(self.package, self.prefix)
        binary = self.prefix / "lib/system-pulse/system-pulse"
        binary.write_bytes(b"user replaced binary")
        retained = installer.uninstall(self.prefix)
        self.assertIn("lib/system-pulse/system-pulse", retained)
        self.assertEqual(binary.read_bytes(), b"user replaced binary")


if __name__ == "__main__":
    unittest.main()
