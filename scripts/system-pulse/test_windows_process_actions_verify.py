import copy
import unittest

from performance_compare import InvalidMeasurement
from windows_process_actions_collect import ORDINARY_CASES
from windows_process_actions_verify import validate_ordinary_actions


def example_record():
    cases = []
    for index, expected in enumerate(ORDINARY_CASES):
        pid = 100 + index
        ticks = 134_335_279_792_573_971 + index
        cases.append(dict(
            name=expected["name"], mode=expected["mode"], signal=expected["signal"],
            pid=pid, creation_ticks=ticks, collected_creation_ticks=ticks,
            confirmation=f"Request graceful closure (PID {pid})? Unsaved work may be lost",
            exited=expected["expected_exit"], dashboard_elevated_after=False,
            unrelated_control_alive=True, unrelated_control_messages="ready\n",
            sequence_before=10, sequence_after=20,
            status=expected.get("expected_status", "confirmation cancelled"),
            duplicate_activation="delivered", pending_screen_changes=["Summary", "Processes"],
            pending_observations=[dict(sequence=10, actions_disabled=[True, True]),
                                  dict(sequence=13, actions_disabled=[True, True])],
        ))
    probes = [dict(name=name, pid=pid, exit_code=code, target_alive=True,
                   state_created=False, diagnostics_created=False)
              for name, pid, code in [("unelevated-helper", 50, 29),
                                     ("extra-helper-argument", 51, 29),
                                     ("legacy-helper-mode", 52, 13)]]
    return dict(status="PASS", dashboard=dict(pid=10, creation_ticks=100, elevated_before=False,
                                              elevation_type=3), signing_status="NotSigned",
                binary_path="C:\\Packaged app ü\\system-pulse.exe", cases=cases,
                unrelated_control=dict(pid=20, creation_ticks=200), helper_entry_checks=probes,
                dashboard_cleaned=True,
                owned_target_cleanup=[dict(pid=pid, exited=True)
                                      for pid in [20, 50, 51, 52, *range(100, 107)]])


class OrdinaryActionReceiptTests(unittest.TestCase):
    def test_accepts_valid_signing_but_rejects_broken_signatures(self):
        record = example_record()
        record["signing_status"] = "Valid"
        validate_ordinary_actions(record)
        for status in ("HashMismatch", "NotTrusted", "UnknownError"):
            record["signing_status"] = status
            with self.assertRaises(InvalidMeasurement):
                validate_ordinary_actions(record)

    def test_complete_ordinary_receipt(self):
        validate_ordinary_actions(example_record())

    def test_rejects_truncated_identity_and_different_confirmation(self):
        for field, value in [("collected_creation_ticks", 13433527979),
                             ("creation_ticks", 0), ("pid", 20),
                             ("confirmation", "Force quit (PID 999)? Unsaved work may be lost")]:
            record = example_record()
            record["cases"][0][field] = value
            with self.subTest(field=field), self.assertRaises(InvalidMeasurement):
                validate_ordinary_actions(record)

    def test_rejects_false_success_elevation_or_collateral_action(self):
        for field, value in [("exited", False), ("dashboard_elevated_after", True),
                             ("unrelated_control_alive", False),
                             ("unrelated_control_messages", "ready\nquery-end-session\n"),
                             ("status", "Sending request…"), ("duplicate_activation", "not tested")]:
            record = example_record()
            record["cases"][4][field] = value
            with self.subTest(field=field), self.assertRaises(InvalidMeasurement):
                validate_ordinary_actions(record)

    def test_rejects_missing_cases_helper_bypass_and_cleanup(self):
        baseline = example_record()
        mutations = [
            lambda r: r["cases"].pop(),
            lambda r: r["helper_entry_checks"].pop(),
            lambda r: r["helper_entry_checks"][0].update(exit_code=20),
            lambda r: r["helper_entry_checks"][0].update(state_created=True),
            lambda r: r.update(dashboard_cleaned=False),
            lambda r: r["owned_target_cleanup"].pop(),
            lambda r: r["owned_target_cleanup"][0].update(exited=False),
            lambda r: r["cases"][-1].update(pending_screen_changes=[]),
            lambda r: r["cases"][-1]["pending_observations"][-1].update(sequence=10),
            lambda r: r["cases"][-1]["pending_observations"][0].update(actions_disabled=[False, True]),
        ]
        for index, mutate in enumerate(mutations):
            record = copy.deepcopy(baseline)
            mutate(record)
            with self.subTest(index=index), self.assertRaises(InvalidMeasurement):
                validate_ordinary_actions(record)


if __name__ == "__main__":
    unittest.main()
