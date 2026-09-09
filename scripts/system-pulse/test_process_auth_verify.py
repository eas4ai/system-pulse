"""Reject contradictory authentication evidence before reporting PROC-004."""

import copy
import hashlib
import unittest
from unittest.mock import patch

from performance_compare import InvalidMeasurement
from process_auth_verify import check_harness_revision, validate_authentication, validate_authentication_source


def receipt():
    cases = []
    for name, pid in (("cancel", 100), ("terminate", 100), ("kill", 101), ("expired", 102)):
        notice = ("Authentication was cancelled." if name == "cancel" else
                  "The selected process exited before the request." if name == "expired" else
                  f"Request sent to sleep (PID {pid}). Waiting for the process list to update.")
        cases.append({"case": name, "identity": {"pid": pid, "start_time_ticks": pid * 10, "uid": 0},
                      "ordinary_exit": 11, "notice": notice, "alive": name == "cancel"})
    return {"status": "PASS", "platform": "linux", "ui_uid": 1000, "ui_pid": 99,
            "remaining_bounded_fixtures": [], "cases": cases}


class AuthenticationReceiptTests(unittest.TestCase):
    def test_complete_receipts_on_both_hosts(self):
        for platform in ("linux", "macos"):
            record = receipt()
            record["platform"] = platform
            validate_authentication(record, platform)

    def test_rejects_wrong_host_privileged_ui_and_incomplete_run(self):
        for update in ({"status": "FAIL"}, {"platform": "macos"}, {"ui_uid": 0},
                       {"ui_uid": True}, {"ui_pid": 0}, {"cases": []},
                       {"remaining_bounded_fixtures": [{}]}, {"cleanup_errors": ["failed"]},
                       {"error": "timed out"}):
            with self.subTest(update=update):
                record = receipt()
                record.update(update)
                with self.assertRaises(InvalidMeasurement):
                    validate_authentication(record, "linux")

    def test_rejects_incorrect_lifetime_denial_and_notice(self):
        for index in range(4):
            for key, value in (("alive", index != 0), ("ordinary_exit", 0), ("notice", "failed")):
                with self.subTest(index=index, key=key):
                    record = receipt()
                    record["cases"][index][key] = value
                    with self.assertRaises(InvalidMeasurement):
                        validate_authentication(record, "linux")

    def test_rejects_unknown_unprivileged_or_changed_identity(self):
        for key, value in (("pid", 0), ("pid", 99), ("uid", 1000), ("start_time_ticks", 0),
                           ("start_time_ticks", 1001)):
            with self.subTest(key=key, value=value):
                record = receipt()
                record["cases"][0]["identity"][key] = value
                with self.assertRaises(InvalidMeasurement):
                    validate_authentication(record, "linux")

    def test_rejects_success_notice_for_another_pid(self):
        record = receipt()
        record["cases"][1]["notice"] = "Request sent to sleep (PID 999)."
        with self.assertRaises(InvalidMeasurement):
            validate_authentication(record, "linux")

    def test_rejects_duplicate_finished_fixture(self):
        record = receipt()
        record["cases"][3]["identity"] = copy.deepcopy(record["cases"][2]["identity"])
        with self.assertRaises(InvalidMeasurement):
            validate_authentication(record, "linux")

    def test_generic_linux_failure_requires_matching_os_cancellation_witness(self):
        record = receipt()
        record["cases"][0]["notice"] = (
            "Authentication failed or no system authentication agent is available. "
            "The process was not changed.")
        with self.assertRaises(InvalidMeasurement):
            validate_authentication(record, "linux")
        witness = {"agent": "polkit-kde-auth", "application_identity": {
            "pid": 99, "start_time_ticks": 500, "uid": 1000},
            "dialog_cancelled_us": 10_000_000, "authorization_failed_us": 10_000_010}
        record["cases"][0]["cancellation_witness"] = witness
        validate_authentication(record, "linux")
        for update in ({"agent": "unknown"}, {"authorization_failed_us": 1},
                       {"application_identity": {"pid": 98, "uid": 1000, "start_time_ticks": 500}}):
            record["cases"][0]["cancellation_witness"] = {**witness, **update}
            with self.assertRaises(InvalidMeasurement):
                validate_authentication(record, "linux")

    @patch("process_auth_verify.subprocess.check_output", return_value=b"committed observer")
    @patch("process_auth_verify.same_production")
    def test_observer_digest_must_match_the_exact_committed_tree(self, production, git):
        digest = hashlib.sha256(b"committed observer").hexdigest()
        check_harness_revision({"observer.py": digest}, {"observer.py"}, "a" * 40)
        production.assert_called_once_with("a" * 40)
        self.assertEqual(git.call_args.args[0][2], "a" * 40 + ":scripts/system-pulse/observer.py")
        for hashes, names, commit in (({"observer.py": "b" * 64}, {"observer.py"}, "a" * 40),
                                      ({}, {"observer.py"}, "a" * 40), ({}, {}, "HEAD")):
            with self.assertRaises(InvalidMeasurement):
                check_harness_revision(hashes, names, commit)

    @patch("process_auth_verify.check_harness_revision")
    @patch("process_auth_verify.same_production")
    def test_requires_matching_build_and_observer_provenance(self, source, harness):
        record = {"source_commit": "a" * 40, "binary_sha256": "b" * 64, "harness_sha256": {},
                  "harness_commit": "c" * 40}
        build = {**record, "exit_code": 0}
        validate_authentication_source(record, build, "linux")
        source.assert_called_once_with(record["source_commit"])
        names = harness.call_args.args[1]
        self.assertIn("process_auth_native.py", names)
        self.assertIn("process_table_harnesses.py", names)
        for update in ({"source_commit": "c" * 40}, {"binary_sha256": "d" * 64}, {"exit_code": 1}):
            with self.subTest(update=update), self.assertRaises(InvalidMeasurement):
                validate_authentication_source(record, {**build, **update}, "linux")


if __name__ == "__main__":
    unittest.main()
