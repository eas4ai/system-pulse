import unittest

from performance_compare import InvalidMeasurement
from windows_process_actions_collect import build_identity


class NativeBuildIdentityTests(unittest.TestCase):
    def setUp(self):
        self.commit = "a" * 40
        self.digest = "b" * 64
        self.log = ("Embedded Windows manifest: asInvoker; uiAccess=false\n"
                    f"Hash : {self.digest.upper()}\nPASS REL-001 {self.commit}\n")

    def test_accepts_one_verified_build(self):
        self.assertEqual(build_identity(self.log), (self.commit, self.digest))

    def test_rejects_missing_or_ambiguous_provenance(self):
        for log in ("", self.log.replace("PASS REL-001", "FAIL REL-001"),
                    self.log + f"Hash : {'c' * 64}\n",
                    self.log + f"PASS REL-001 {'d' * 40}\n",
                    self.log.replace("asInvoker", "requireAdministrator"),
                    self.log.replace("uiAccess=false", "uiAccess=true")):
            with self.subTest(log=log), self.assertRaises(InvalidMeasurement):
                build_identity(log)


if __name__ == "__main__":
    unittest.main()
