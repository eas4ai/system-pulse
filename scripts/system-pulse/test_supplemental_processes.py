"""Deterministic observer timing tests; no synthetic measurements reach the app."""

import copy
import unittest
from unittest.mock import patch

import host_capture
from test_process_attribution import process_capture


class SupplementalProcessTests(unittest.TestCase):
    def setup_observer(self):
        observer = host_capture.Observer.__new__(host_capture.Observer)
        observer.previous_pids = {1, 2, 3, 4}
        observer.samples = []
        observer.anchors = []
        observer.supplemental = []
        observer.supplemental_count = 0
        observer.supplemental_pids = set()
        observer.full_census_pids = set()
        observer.next_refresh_ns = 20_000_000
        observer.capture_deadline_ns = 35_000_000_000
        return observer

    def run_sweep(self, observer):
        clock = [0]

        def census():
            clock[0] += 2_000_000
            return [1, 2, 3, 4] + ([99] if 20_000_000 <= clock[0] < 70_000_000 else [])

        def read(pid):
            start = clock[0]
            clock[0] += 12_000_000
            stat = dict(
                source=f"/proc/{pid}/stat",
                start=start,
                end=clock[0],
                errno=None,
                value=dict(pid=pid, start_ticks=pid, utime=start, stime=0),
            )
            return dict(
                stat=stat,
                io=dict(
                    source=f"/proc/{pid}/io",
                    start=start,
                    end=clock[0],
                    errno=None,
                    value=dict(read_bytes=start, write_bytes=0),
                ),
            )

        with (
            patch.object(host_capture.time, "monotonic_ns", lambda: clock[0]),
            patch.object(
                host_capture, "anchor", lambda: (clock[0], clock[0], clock[0] + 100)
            ),
            patch.object(host_capture, "proc_pids", census, create=True),
            patch.object(host_capture, "process", read),
        ):
            result = observer.capture_processes([1, 2, 3, 4])
        return result

    def test_short_lived_birth_gets_both_supplemental_windows_without_dropping_full_census(
        self,
    ):
        observer = self.setup_observer()
        result = self.run_sweep(observer)
        self.assertEqual(set(result), {"1", "2", "3", "4"})
        reads = [
            r["readings"]["stat"]
            for sweep in observer.supplemental
            for r in sweep["processes"]
            if r["pid"] == 99
        ]
        self.assertGreaterEqual(len(reads), 2)
        self.assertLessEqual(reads[0]["end"], 45_000_000)
        self.assertGreaterEqual(reads[1]["start"], 45_000_000)
        self.assertNotEqual(reads[0], reads[1])
        self.assertEqual(observer.supplemental_count, len(reads))

    def test_schedule_records_actual_delay_instead_of_claiming_twenty_ms_bound(self):
        observer = self.setup_observer()
        self.run_sweep(observer)
        self.assertTrue(observer.supplemental)
        first = observer.supplemental[0]
        self.assertEqual(first["scheduled_ns"], 20_000_000)
        self.assertEqual(first["check_ns"], 24_000_000)
        self.assertEqual(first["late_ns"], 4_000_000)
        self.assertEqual(first["census"]["start"], 24_000_000)
        self.assertEqual(first["census"]["end"], 26_000_000)
        self.assertEqual(len(first["anchors"]), 2)

    def test_supplemental_limit_and_original_deadline_fail_without_dropping_evidence(
        self,
    ):
        for cap in (True, False):
            with self.subTest(cap=cap):
                observer = self.setup_observer()
                if cap:
                    observer.supplemental_count = 4096
                else:
                    observer.capture_deadline_ns = 1
                with self.assertRaises(AssertionError):
                    self.run_sweep(observer)
                if cap:
                    self.assertTrue(observer.supplemental)
                    self.assertIn("error", observer.supplemental[-1])

    def test_bracket_matching_includes_all_extra_reads_and_never_joins_reused_pid(self):
        observer, snapshots = process_capture()
        observer.supplemental = []
        for sample in observer.samples:
            observer.supplemental.append(
                dict(
                    census=sample["sources"]["/proc"],
                    processes=[dict(pid=42, readings=sample["processes"].pop("42"))],
                )
            )
        result = host_capture.verify_capture(observer, snapshots, None)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["counts"]["counter_brackets"], 72)
        wrong = copy.deepcopy(observer)
        wrong.supplemental[1]["processes"][0]["readings"]["stat"]["value"][
            "start_ticks"
        ] = 123
        self.assertEqual(
            host_capture.verify_capture(wrong, snapshots, None)["status"], "FAIL"
        )
