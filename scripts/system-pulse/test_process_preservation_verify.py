"""Reject missing controls and altered package evidence."""

from pathlib import Path
import tempfile
import unittest

from performance_compare import InvalidMeasurement
from performance_macos import digest
from process_preservation_verify import validate_ordinary_actions, validate_step_logs, verify_artifact


class PreservationReceiptTests(unittest.TestCase):
    def test_ordinary_signals_require_confirmation_cancellation_and_exact_targets(self):
        rows = [{"action": action, "identity": f"process:{pid}:500",
                 "confirmation_cancelled_alive": True, "child_exit": signal,
                 "notice": f"Request sent to sleep (PID {pid})."}
                for action, pid, signal in (("end", 100, -15), ("force", 101, -9))]
        validate_ordinary_actions({"ordinary_actions": rows})
        for update in ({"confirmation_cancelled_alive": False}, {"child_exit": -9},
                       {"notice": "Request sent to sleep (PID 999)."}, {"identity": "process:100:0"}):
            with self.subTest(update=update), self.assertRaises(InvalidMeasurement):
                validate_ordinary_actions({"ordinary_actions": [{**rows[0], **update}, rows[1]]})
        with self.assertRaises(InvalidMeasurement):
            validate_ordinary_actions({"ordinary_actions": rows[:1]})

    def test_artifact_size_and_digest_detect_changed_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text("original")
            record = {"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)}
            self.assertEqual(verify_artifact(record), path)
            path.write_text("tampered")
            with self.assertRaises(InvalidMeasurement):
                verify_artifact(record)

    def test_all_package_stages_must_finish_and_keep_their_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.log"
            path.write_text("PASS\n")
            step = {"exit_code": 0, "timed_out": False, "log": str(path), "sha256": digest(path)}
            validate_step_logs({"package": step}, {"package"})
            for steps in ({}, {"package": {**step, "exit_code": 1}},
                          {"package": {**step, "timed_out": True}},
                          {"package": {**step, "sha256": "0" * 64}}):
                with self.assertRaises(InvalidMeasurement):
                    validate_step_logs(steps, {"package"})


if __name__ == "__main__":
    unittest.main()
