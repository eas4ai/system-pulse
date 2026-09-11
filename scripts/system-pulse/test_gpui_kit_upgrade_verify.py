"""Reject old, mixed and unpatched dependency graphs before native acceptance."""

import copy
from pathlib import Path
import unittest

from gpui_kit_upgrade_verify import KIT_PACKAGES, LOCAL_PATCHES, validate_graph


class UpgradeGraphTests(unittest.TestCase):
    def metadata(self):
        packages = []
        for name in dict.fromkeys(["system-pulse", *KIT_PACKAGES, *LOCAL_PATCHES, "gpui-pre"]):
            version = "0.6.1" if name in KIT_PACKAGES else "0.3.2" if name.startswith("gpui-pre") else "1.0.0"
            packages.append({"id": name, "name": name, "version": version,
                             "source": None if name in LOCAL_PATCHES else "registry",
                             "manifest_path": str(Path("/test") / LOCAL_PATCHES.get(name, "Cargo.toml"))})
        return {"packages": packages, "resolve": {"root": "system-pulse", "nodes": [
            {"id": p["id"], "dependencies": [q["id"] for q in packages if q != p]
             if p["name"] == "system-pulse" else []} for p in packages]}}

    def test_selected_release_and_local_patches(self):
        self.assertEqual(validate_graph(self.metadata(), Path("/test")),
                         dict.fromkeys(KIT_PACKAGES, "0.6.1"))

    def test_old_release_missing_patch_and_wrong_runtime_fail(self):
        for name, field, value in (("gpui-kit", "version", "0.6.0"),
                                   ("gpui-base", "source", "registry"),
                                   ("gpui-component", "manifest_path", "/elsewhere/Cargo.toml"),
                                   ("gpui-pre", "version", "0.3.3")):
            with self.subTest(name=name):
                metadata = self.metadata()
                next(p for p in metadata["packages"] if p["name"] == name)[field] = value
                with self.assertRaises((ValueError, RuntimeError)):
                    validate_graph(metadata, Path("/test"))

    def test_duplicate_runtime_fails_even_at_the_same_version(self):
        metadata = self.metadata()
        duplicate = copy.deepcopy(next(p for p in metadata["packages"] if p["name"] == "gpui-pre"))
        duplicate["id"] = "another-gpui-pre-source"
        metadata["packages"].append(duplicate)
        metadata["resolve"]["nodes"].append({"id": duplicate["id"], "dependencies": []})
        metadata["resolve"]["nodes"][0]["dependencies"].append(duplicate["id"])
        with self.assertRaises((ValueError, RuntimeError)):
            validate_graph(metadata, Path("/test"))

    def test_older_transitive_sysinfo_does_not_replace_collectors_patch(self):
        metadata = self.metadata()
        metadata["packages"].append({"id": "older-sysinfo", "name": "sysinfo", "version": "0.34.2",
                                     "source": "registry", "manifest_path": "/registry/sysinfo/Cargo.toml"})
        metadata["resolve"]["nodes"].append({"id": "older-sysinfo", "dependencies": []})
        metadata["resolve"]["nodes"][0]["dependencies"].append("older-sysinfo")
        validate_graph(metadata, Path("/test"))


if __name__ == "__main__":
    unittest.main()
