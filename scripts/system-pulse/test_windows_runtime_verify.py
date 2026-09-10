"""Reject partial or contradictory native Windows acceptance records."""

import copy
import unittest

from performance_compare import InvalidMeasurement
from windows_runtime_verify import validate_interactions, validate_readings


def interaction_record():
    return {
        "status": "PASS", "elevated": False, "run_id": "a" * 32, "diagnostic_pid": 1234,
        "screens": [{"screen": screen, "selected": True} for screen in
                    ("Summary", "CPU", "Memory", "GPU", "Disks", "Network", "Energy", "Thermals", "Processes", "Settings")],
        "filtered_rows": [{"pid": 1234, "name": "system-pulse.exe"}],
        "sorted_rows": [[{"pid": 1}, {"pid": 2}], [{"pid": 9}, {"pid": 2}]],
        "reopen": {"pid": 1234, "hidden": True, "visible": True, "old_window": 11, "new_window": 22},
        "diagnostic_quit": {"pid": 1234, "menu_owner": 1234, "exit_code": 0},
        "normal": {"pid": 5678, "diagnostics_enabled": False, "settings_restored": True,
                   "rows": [{"pid": 1}, {"pid": 2}], "status": "Live system data · 200 readable processes · 2 s update",
                   "quit": {"pid": 5678, "menu_owner": 5678, "exit_code": 0}},
    }


class WindowsInteractions(unittest.TestCase):
    def test_complete_native_record(self):
        validate_interactions(interaction_record())

    def test_partial_or_wrong_process_observations_fail(self):
        changes = (
            lambda r: r.update(elevated=True),
            lambda r: r["screens"].pop(),
            lambda r: r["filtered_rows"][0].update(pid=9999),
            lambda r: r["sorted_rows"][1].reverse(),
            lambda r: r["reopen"].update(hidden=False),
            lambda r: r["normal"].update(diagnostics_enabled=True),
            lambda r: r["normal"].update(rows=[]),
            lambda r: r["normal"]["quit"].update(exit_code=None),
            lambda r: r["diagnostic_quit"].update(menu_owner=9999),
        )
        for index, change in enumerate(changes):
            with self.subTest(case=index):
                record = interaction_record()
                change(record)
                with self.assertRaises(InvalidMeasurement):
                    validate_interactions(record)


class WindowsReadings(unittest.TestCase):
    def setUp(self):
        self.record = {"diagnostic_pid": 1234, "host": {"visible_memory_bytes": 1024,
                       "cpu": [{"NumberOfLogicalProcessors": 1}]}}
        self.initial = {"application_pid": 1234, "accepted_unix_ns": 10, "snapshot": {
            "sequence": 1,
            "readings": [{"sensor_id": "cpu:host/usage", "availability": "Available", "value": 10},
                         {"sensor_id": "memory:host/used", "availability": "Available", "value": 100, "total": 1024}],
            "sensors": [{"id": "cpu:host/core-0-usage", "kind": "Percentage"}],
            "monitors": [{"kind": kind} for kind in ("Cpu", "Memory", "Network", "Volume")],
            "processes": [{"identity": {"pid": 1234}, "name": "system-pulse.exe", "memory_bytes": {"value": 10}}],
            "diagnostics": [{"backend": "nvml", "availability": "Failed", "reason": "not installed"}],
        }}
        self.final = copy.deepcopy(self.initial)
        self.final["accepted_unix_ns"] = 20
        self.final["snapshot"]["sequence"] = 2

    def test_advancing_native_readings(self):
        validate_readings(self.initial, self.final, self.record)

    def test_frozen_or_inconsistent_readings_fail(self):
        changes = (
            lambda f: f["snapshot"].update(sequence=1),
            lambda f: f.update(application_pid=9999),
            lambda f: f["snapshot"]["readings"][0].update(value=101),
            lambda f: f["snapshot"]["readings"][1].update(total=2048),
            lambda f: f["snapshot"]["monitors"].append({"kind": "Gpu"}),
            lambda f: f["snapshot"].update(processes=[]),
        )
        for index, change in enumerate(changes):
            with self.subTest(case=index):
                final = copy.deepcopy(self.final)
                change(final)
                with self.assertRaises(InvalidMeasurement):
                    validate_readings(self.initial, final, self.record)

    def test_unsupported_temperature_cannot_appear_available(self):
        self.final["snapshot"]["sensors"].append({"id": "cpu:host/temperature", "kind": "Temperature"})
        self.final["snapshot"]["readings"].append({"sensor_id": "cpu:host/temperature", "availability": "Available"})
        with self.assertRaises(InvalidMeasurement):
            validate_readings(self.initial, self.final, self.record)


if __name__ == "__main__":
    unittest.main()
