import unittest
import hashlib
import json

from performance_compare import InvalidMeasurement
from windows_process_actions_collect import build_identity, packaged_binary_hash


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


class SignedPackageIdentityTests(unittest.TestCase):
    def test_unsigned_and_signed_artifact_remain_bound_to_native_build(self):
        unsigned = hashlib.sha256(b"native").hexdigest()
        self.assertEqual(packaged_binary_hash({"system-pulse.exe": b"native"}, unsigned), unsigned)
        signed = hashlib.sha256(b"signed native").hexdigest()
        build = {"binary_sha256": signed, "unsigned_binary_sha256": unsigned,
                 "authenticode": {"status": "Valid", "thumbprint": "c" * 40}}
        files = {"system-pulse.exe": b"signed native", "build.json": json.dumps(build).encode()}
        self.assertEqual(packaged_binary_hash(files, unsigned), signed)
        for field, value in (("unsigned_binary_sha256", "d" * 64), ("binary_sha256", "e" * 64),
                             ("authenticode", {"status": "NotSigned"})):
            modified = dict(build); modified[field] = value
            files["build.json"] = json.dumps(modified).encode()
            with self.subTest(field=field), self.assertRaises(InvalidMeasurement):
                packaged_binary_hash(files, unsigned)


if __name__ == "__main__":
    unittest.main()
