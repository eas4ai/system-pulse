import tempfile
from pathlib import Path
import unittest

try:
    from gpu_verify import validate_preservation, selected_test_count, outside_output
except ImportError:
    validate_preservation = selected_test_count = outside_output = None


class AggregateTests(unittest.TestCase):
    def test_actual_cli_rejects_each_missing_or_empty_mandatory_group(self):
        import gpu_verify
        import shutil
        import subprocess
        import sys
        import json

        groups = (
            "aggregate",
            "apple_capture",
            "arithmetic",
            "desktop",
            "evidence",
            "intel",
            "native",
        )
        specimen = "import unittest\nclass Specimen(unittest.TestCase):\n    def test_nonempty(self): self.assertEqual(1,1)\n"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            scripts = project / "scripts/system-pulse"
            shutil.copytree(
                gpu_verify.ROOT / "scripts/system-pulse",
                scripts,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            for path in scripts.glob("test_gpu_*.py"):
                path.write_text(specimen)

            def cli(label):
                output = base / label
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(scripts / "gpu_verify.py"),
                        "--development-tests-only",
                        "--output",
                        str(output),
                    ],
                    cwd=project,
                    text=True,
                    capture_output=True,
                    timeout=30,
                )
                self.assertNotIn("cairn:", result.stdout)
                return result, json.loads((output / "development.json").read_text())

            baseline, record = cli("baseline")
            self.assertEqual(baseline.returncode, 0, baseline.stdout + baseline.stderr)
            self.assertFalse(record["errors"])
            for group in groups:
                path = scripts / ("test_gpu_" + group + ".py")
                for operation in ("missing", "empty"):
                    if operation == "missing":
                        path.unlink()
                    else:
                        path.write_text("import unittest\n")
                    try:
                        result, record = cli(group + "-" + operation)
                        with self.subTest(group=group, operation=operation):
                            self.assertNotEqual(result.returncode, 0, result.stdout)
                            self.assertTrue(record["errors"])
                    finally:
                        path.write_text(specimen)

    def test_all_first_party_build_dependencies_are_declared(self):
        import gpu_verify
        import subprocess

        self.assertTrue(
            hasattr(gpu_verify, "build_dependency_roots"),
            "build dependency closure is not validated",
        )
        roots = gpu_verify.build_dependency_roots()
        self.assertNotIn(".", roots)
        self.assertTrue({"Cargo.toml", "src", "assets", "crates/model", "crates/collectors"} <= set(roots))
        self.assertTrue(
            {
                "crates/base",
                "crates/ui",
                "vendor/accesskit_unix",
                "vendor/accesskit_atspi_common",
                "vendor/gpui_macos",
            } <= set(roots),
            "registry facade dependencies must still bind local patched source",
        )
        self.assertNotIn("crates/assets", roots)
        self.assertNotIn("crates/macros", roots)
        tracked = set(
            subprocess.check_output(
                ["git", "ls-files", "--", *roots], cwd=gpu_verify.ROOT, text=True
            ).splitlines()
        )
        declared = set(
            subprocess.check_output(
                ["git", "ls-files", "--", *gpu_verify.declared_inputs()],
                cwd=gpu_verify.ROOT,
                text=True,
            ).splitlines()
        )
        self.assertTrue(tracked <= declared, sorted(tracked - declared))

    def test_changed_or_removed_real_build_inputs_reject_committed_binding(self):
        import gpu_verify
        import subprocess
        import shutil
        from unittest.mock import patch

        original = gpu_verify.ROOT
        package_roots = [
            "crates/base",
            "crates/ui",
            "vendor/accesskit_unix",
            "vendor/accesskit_atspi_common",
            "vendor/gpui_macos",
        ]
        selected = (
            [root + "/Cargo.toml" for root in package_roots]
            + ["crates/base/src/lib.rs", "crates/ui/src/lib.rs"]
            + ["crates/ui/build.rs"]
        )
        selected += [
            "vendor/accesskit_unix/src/atspi/bus.rs",
            "vendor/accesskit_atspi_common/src/node.rs",
            "vendor/gpui_macos/src/dispatcher.rs",
            "src/main.rs",
            "assets/fonts/sources.json",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in [
                ".cairn/mechanisms/gpu-acceptance",
                "Cargo.toml",
                "Cargo.lock",
                *selected,
            ]:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original / name, root / name)

            def git(*args):
                return subprocess.check_output(
                    ["git", *args], cwd=root, stderr=subprocess.DEVNULL
                )

            git("init", "-q")
            git("add", ".")
            git(
                "-c",
                "user.name=GPU verifier test",
                "-c",
                "user.email=gpu-test@localhost",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "isolated input specimen",
            )
            with (
                patch.object(gpu_verify, "ROOT", root),
                patch.object(
                    gpu_verify,
                    "build_dependency_roots",
                    return_value=package_roots + ["Cargo.toml", "src", "assets"],
                    create=True,
                ),
            ):
                gpu_verify.committed_inputs()
                for name in selected:
                    path = root / name
                    raw = path.read_bytes()
                    for operation in ("edit", "remove"):
                        if operation == "edit":
                            path.write_bytes(raw + b"\nchanged build input\n")
                        else:
                            path.unlink()
                        try:
                            with (
                                self.subTest(path=name, operation=operation),
                                self.assertRaises(AssertionError),
                            ):
                                gpu_verify.committed_inputs()
                        finally:
                            path.write_bytes(raw)

    def test_empty_or_wrong_test_selection_fails(self):
        self.assertIsNotNone(selected_test_count, "GPU nonempty selection gate missing")
        self.assertEqual(selected_test_count("Ran 4 tests in 0.1s\n\nOK\n"), 4)
        for text in (
            "Ran 0 tests in 0.1s\n\nOK\n",
            "PASS",
            "Ran 4 tests in 0.1s\n\nFAILED (failures=1)",
        ):
            with self.assertRaises(AssertionError):
                selected_test_count(text)

    def test_preservation_requires_original_full_manifest_not_pass_text(self):
        self.assertIsNotNone(
            validate_preservation, "GPU preservation revalidation missing"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "manifest.json").write_text('{"status":"PASS","test_count":900}')
            with self.assertRaises((AssertionError, KeyError)):
                validate_preservation(p)

    def test_artifacts_cannot_be_written_into_checkout(self):
        self.assertIsNotNone(outside_output, "GPU artifact location gate missing")
        from acceptance import ROOT

        with self.assertRaises(AssertionError):
            outside_output(ROOT / "gpu-proof")


if __name__ == "__main__":
    unittest.main()
