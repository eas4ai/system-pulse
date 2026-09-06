import tempfile
from pathlib import Path
import unittest

try:
    from gpu_verify import validate_preservation, selected_test_count, outside_output
except ImportError:
    validate_preservation = selected_test_count = outside_output = None


class AggregateTests(unittest.TestCase):
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
