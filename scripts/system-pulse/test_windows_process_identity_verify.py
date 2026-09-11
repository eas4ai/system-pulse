"""Reject incomplete or substituted native identity evidence."""

import unittest

from windows_process_identity_verify import NATIVE_TESTS, validate_native_identity


class NativeIdentityEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.commit = "a" * 40
        self.binary = "b" * 64
        self.log = "\n".join([
            f"Source commit: {self.commit}",
            r"Running unittests src\lib.rs (C:\target\system_pulse_collectors-123abc.exe)",
            *(f"test process_control::windows::tests::{name} ... ok" for name in NATIVE_TESTS),
            "test result: ok. 60 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out;",
            f"Hash : {self.binary.upper()}",
            f"PASS REL-001 {self.commit}",
        ])

    def test_complete_native_record_passes(self):
        validate_native_identity(self.log, self.commit, self.binary)

    def test_missing_failed_or_ignored_case_is_rejected(self):
        for name in NATIVE_TESTS:
            for outcome in ("FAILED", "ignored", ""):
                with self.subTest(name=name, outcome=outcome), self.assertRaises(ValueError):
                    validate_native_identity(
                        self.log.replace(f"{name} ... ok", f"{name} ... {outcome}"),
                        self.commit, self.binary)

    def test_wrong_source_binary_or_platform_is_rejected(self):
        for original, replacement in [
            (f"PASS REL-001 {self.commit}", "build incomplete"),
            (self.binary.upper(), "c" * 64),
            (".exe)", ")"),
            ("0 failed", "1 failed"),
            ("0 ignored", "1 ignored"),
        ]:
            with self.subTest(original=original), self.assertRaises(ValueError):
                validate_native_identity(self.log.replace(original, replacement),
                                         self.commit, self.binary)


if __name__ == "__main__":
    unittest.main()
