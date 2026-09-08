import copy
import unittest
from unittest.mock import patch

from performance_compare import InvalidMeasurement, compare
from performance_macos import census


def receipt():
    host = {"logical_cpus": 8, "chip": "Apple M1 Pro", "os_version": "test",
            "power_source": "AC"}
    binaries = {
        "reference": {"commit": "af243cf2dba5eb6c4cb19397c522c38eda640f45",
                      "sha256": "a" * 64, "release_locked": True},
        "candidate": {"commit": "b" * 40, "sha256": "c" * 64, "release_locked": True},
    }
    runs = []
    for mode in ("summary", "tray"):
        for repetition in (1, 2, 3):
            order = ("candidate", "reference") if repetition == 2 else ("reference", "candidate")
            for label in order:
                start = (len(runs) + 1) * 100_000_000_000
                windows = [{"width": 1280, "height": 880, "screen": "Summary"}] if mode == "summary" else []
                runs.append({
                    "mode": mode, "binary": label, "repetition": repetition,
                    "host": copy.deepcopy(host), "interval_seconds": 1,
                    "warmup_seconds": 30, "diagnostics_enabled": False,
                    "process_survived": True, "pid": 100 + len(runs), "process_start": str(start),
                    "monotonic_before_ns": start, "monotonic_after_ns": start + 60_000_000_000,
                    "cpu_before_ns": 1_000_000_000,
                    "cpu_after_ns": 7_000_000_000 if label == "reference" else 4_000_000_000,
                    **{f"binary_sha256_{b}": binaries[label]["sha256"] for b in ("before", "after")},
                    **{f"monitor_pids_{b}": [100 + len(runs)] for b in ("before", "after")},
                    **{f"conflicting_processes_{b}": [] for b in ("before", "after")},
                    **{f"windows_{b}": windows for b in ("before", "after")},
                })
    return {"version": 1, "host": host, "binaries": binaries, "runs": runs}


class PerformanceComparisonTests(unittest.TestCase):
    def test_census_distinguishes_system_service_from_launched_profiler(self):
        with patch("performance_macos.command", return_value=
                   "636 1 /usr/sbin/spindump\n700 20 /usr/sbin/spindump\n"
                   "800 20 /tmp/system-pulse-candidate\n900 20 /usr/bin/rustc"):
            monitors, conflicts = census()
        self.assertEqual(monitors, [800])
        self.assertEqual(conflicts, [{"pid": 700, "name": "spindump"},
                                     {"pid": 900, "name": "rustc"}])

    def test_exact_half_passes_in_each_mode(self):
        result = compare(receipt())
        for mode in ("summary", "tray"):
            self.assertEqual(result[mode]["ratio"], 0.5)
            self.assertTrue(result[mode]["passed"])

    def test_unchanged_candidate_and_insufficient_reduction_fail(self):
        for cpu in (7_000_000_000, 4_000_000_001):
            data = receipt()
            for run in data["runs"]:
                if run["binary"] == "candidate":
                    run["cpu_after_ns"] = cpu
            self.assertTrue(all(not mode["passed"] for mode in compare(data).values()))

    def test_one_mode_cannot_mask_the_other(self):
        data = receipt()
        for run in data["runs"]:
            if run["binary"] == "candidate" and run["mode"] == "tray":
                run["cpu_after_ns"] = 7_000_000_000
        result = compare(data)
        self.assertTrue(result["summary"]["passed"])
        self.assertFalse(result["tray"]["passed"])

    def test_aggregate_weights_elapsed_time_instead_of_averaging_percentages(self):
        data = receipt()
        run = data["runs"][1]
        run["monotonic_after_ns"] += 30_000_000_000
        run["cpu_after_ns"] = 7_000_000_000
        result = compare(data)["summary"]
        self.assertAlmostEqual(result["candidate_percent"], 100 * 12 / 210)
        self.assertFalse(result["passed"])

    def test_invalid_observations_are_rejected(self):
        alterations = {
            "wrong binary": ("binary_sha256_after", "d" * 64),
            "short warmup": ("warmup_seconds", 29.999),
            "short run": ("monotonic_after_ns", 159_999_999_999),
            "clock regression": ("monotonic_after_ns", 0),
            "counter regression": ("cpu_after_ns", 0),
            "nan": ("cpu_after_ns", float("nan")),
            "infinity": ("cpu_after_ns", float("inf")),
            "boolean counter": ("cpu_after_ns", True),
            "wrong interval": ("interval_seconds", 2),
            "boolean interval": ("interval_seconds", True),
            "diagnostics": ("diagnostics_enabled", True),
            "exited": ("process_survived", False),
            "missing identity": ("process_start", ""),
            "window closed": ("windows_after", []),
            "another instance": ("monitor_pids_before", [100, 999]),
            "compiler": ("conflicting_processes_after", ["rustc"]),
            "different host": ("host", {}),
        }
        for label, (key, value) in alterations.items():
            with self.subTest(label=label):
                data = receipt()
                data["runs"][0][key] = value
                with self.assertRaises(InvalidMeasurement):
                    compare(data)

    def test_missing_duplicate_and_reordered_runs_are_rejected(self):
        for alteration in (lambda r: r.pop(), lambda r: r.__setitem__(1, r[0]),
                           lambda r: r.reverse()):
            data = receipt()
            alteration(data["runs"])
            with self.assertRaises(InvalidMeasurement):
                compare(data)


if __name__ == "__main__":
    unittest.main()
