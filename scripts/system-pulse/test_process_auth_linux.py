"""Generic polkit denial alone cannot prove that a dialog was cancelled."""

import unittest

from performance_compare import InvalidMeasurement
from process_auth_linux import cancellation_witness


def event(message, timestamp=10_000_000):
    return {"MESSAGE": message, "__REALTIME_TIMESTAMP": str(timestamp)}


class LinuxCancellationTests(unittest.TestCase):
    def setUp(self):
        self.identity = {"pid": 42, "start_time_ticks": 123, "uid": 1000}
        self.agent = [event("Initiating authentication"), event("Dialog cancelled")]
        self.authority = [event("Operator FAILED to authenticate to gain authorization for action "
                                "org.freedesktop.policykit.exec for unix-process:42:123 [/app]")]

    def test_matches_os_cancellation_to_the_exact_application_lifetime(self):
        witness = cancellation_witness(self.agent, self.authority, self.identity)
        self.assertEqual(witness["application_identity"], self.identity)
        self.assertEqual(witness["dialog_cancelled_us"], 10_000_000)

    def test_rejects_denial_without_cancellation_and_overlapping_dialogs(self):
        for agent in (self.agent[:1], self.agent + [event("Initiating authentication")],
                      self.agent + [event("Completed:  true")]):
            with self.assertRaises(InvalidMeasurement):
                cancellation_witness(agent, self.authority, self.identity)

    def test_rejects_another_application_lifetime_and_unrelated_event_time(self):
        for identity in ({**self.identity, "pid": 43}, {**self.identity, "start_time_ticks": 124}):
            with self.assertRaises(InvalidMeasurement):
                cancellation_witness(self.agent, self.authority, identity)
        self.authority[0]["__REALTIME_TIMESTAMP"] = "20000000"
        with self.assertRaises(InvalidMeasurement):
            cancellation_witness(self.agent, self.authority, self.identity)


if __name__ == "__main__":
    unittest.main()
