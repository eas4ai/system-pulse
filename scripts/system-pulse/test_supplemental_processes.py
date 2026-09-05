"""Deterministic observer timing tests; no synthetic measurements reach the app."""

import copy
import errno
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

    def run_sweep(
        self,
        observer,
        clock=None,
        pids=(1, 2, 3, 4),
        exit_ns=70_000_000,
        stat_errno=errno.ENOENT,
        io_errno=None,
    ):
        clock = [0] if clock is None else clock

        def census():
            clock[0] += 2_000_000
            return [1, 2, 3, 4] + ([99] if 20_000_000 <= clock[0] < exit_ns else [])

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
            result = dict(
                stat=stat,
                io=dict(
                    source=f"/proc/{pid}/io",
                    start=start,
                    end=clock[0],
                    errno=None,
                    value=dict(read_bytes=start, write_bytes=0),
                ),
            )
            if pid == 99:
                errors = {"io": io_errno}
                if start >= exit_ns:
                    errors.update(stat=stat_errno, io=errno.ENOENT)
                for source, error in errors.items():
                    if error is not None:
                        result[source].update(
                            errno=error, value=None, error="unavailable"
                        )
            return result

        with (
            patch.object(host_capture.time, "monotonic_ns", lambda: clock[0]),
            patch.object(
                host_capture, "anchor", lambda: (clock[0], clock[0], clock[0] + 100)
            ),
            patch.object(host_capture, "proc_pids", census, create=True),
            patch.object(host_capture, "process", read),
        ):
            result = observer.capture_processes(pids)
        return result

    def supplemental_reads(self, observer):
        return [
            row["readings"]
            for refresh in observer.supplemental
            for row in refresh["processes"]
            if row["pid"] == 99
        ]

    def test_retained_target_brackets_later_query_after_joining_full_census(self):
        observer = self.setup_observer()
        clock = [0]
        self.run_sweep(observer, clock, exit_ns=1_000_000_000)
        before_handoff = len(self.supplemental_reads(observer))
        ordinary = self.run_sweep(
            observer, clock, pids=(1, 2, 3, 4, 99), exit_ns=1_000_000_000
        )
        self.assertEqual(set(ordinary), {"1", "2", "3", "4", "99"})
        self.assertGreater(len(self.supplemental_reads(observer)), before_handoff)
        window = (ordinary["99"]["stat"]["end"] + 1,) * 2
        identity = dict(pid=99, start_time_ticks=99)
        for source, counter in (("stat", "utime"), ("io", "read_bytes")):
            samples = [
                dict(
                    start=read[source]["start"],
                    end=read[source]["end"],
                    value=read[source]["value"][counter],
                    identity=identity,
                )
                for read in self.supplemental_reads(observer)
            ]
            before, after = host_capture.check_process_counter(
                window[0], window, identity, samples
            )
            self.assertLessEqual(before["end"], window[0])
            self.assertGreaterEqual(after["start"], window[1])

    def test_terminal_stat_attempt_is_retained_before_candidate_retirement(self):
        for terminal_errno in (errno.ENOENT, errno.ESRCH):
            with self.subTest(errno=terminal_errno):
                observer = self.setup_observer()
                clock = [0]
                self.run_sweep(observer, clock, stat_errno=terminal_errno)
                self.run_sweep(observer, clock, stat_errno=terminal_errno)
                reads = self.supplemental_reads(observer)
                self.assertEqual(reads[-1]["stat"]["errno"], terminal_errno)
                self.assertEqual(reads[-1]["io"]["errno"], errno.ENOENT)
                self.assertNotIn(99, observer.supplemental_pids)
                count = len(reads)
                self.run_sweep(observer, clock)
                self.assertEqual(len(self.supplemental_reads(observer)), count)

    def test_io_errors_do_not_retire_live_candidate_across_full_census(self):
        for io_errno in (errno.EACCES, errno.EPERM, errno.ENOENT, errno.ESRCH):
            with self.subTest(errno=io_errno):
                observer = self.setup_observer()
                clock = [0]
                self.run_sweep(
                    observer, clock, exit_ns=1_000_000_000, io_errno=io_errno
                )
                count = len(self.supplemental_reads(observer))
                self.run_sweep(
                    observer,
                    clock,
                    pids=(1, 2, 3, 4, 99),
                    exit_ns=1_000_000_000,
                    io_errno=io_errno,
                )
                reads = self.supplemental_reads(observer)
                self.assertGreater(len(reads), count)
                self.assertTrue(all(read["stat"]["errno"] is None for read in reads))
                self.assertTrue(all(read["io"]["errno"] == io_errno for read in reads))

    def test_ordinary_terminal_read_is_kept_before_retirement(self):
        observer = self.setup_observer()
        clock = [0]
        self.run_sweep(observer, clock)
        count = len(self.supplemental_reads(observer))
        ordinary = self.run_sweep(observer, clock, pids=(1, 2, 3, 4, 99))
        self.assertEqual(ordinary["99"]["stat"]["errno"], errno.ENOENT)
        self.assertEqual(ordinary["99"]["io"]["errno"], errno.ENOENT)
        self.assertNotIn(99, observer.supplemental_pids)
        self.assertEqual(len(self.supplemental_reads(observer)), count)

    def test_census_absence_and_nonterminal_stat_error_do_not_retire_candidate(self):
        observer = self.setup_observer()
        clock = [0]
        self.run_sweep(observer, clock, stat_errno=errno.EACCES)
        count = len(self.supplemental_reads(observer))
        self.run_sweep(observer, clock, stat_errno=errno.EACCES)
        self.assertGreater(len(self.supplemental_reads(observer)), count)
        self.assertEqual(
            self.supplemental_reads(observer)[-1]["stat"]["errno"], errno.EACCES
        )

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
        self.assertEqual(first["finished_ns"], 38_000_000)
        self.assertEqual(first["next_scheduled_ns"], 40_000_000)
        self.assertEqual(first["skipped_slots"], 0)
        second = observer.supplemental[1]
        self.assertEqual(second["finished_ns"], 64_000_000)
        self.assertEqual(second["next_scheduled_ns"], 80_000_000)
        self.assertEqual(second["skipped_slots"], 1)

    def test_retained_candidates_fail_at_existing_bounds_with_prior_evidence(self):
        for cap in (True, False):
            with self.subTest(cap=cap):
                observer = self.setup_observer()
                clock = [0]
                self.run_sweep(observer, clock, exit_ns=1_000_000_000)
                prior = copy.deepcopy(observer.supplemental)
                if cap:
                    observer.supplemental_count = 4095
                    failure = "4096 supplemental process observation limit"
                else:
                    # Expire during the next census, after one retained read.
                    observer.capture_deadline_ns = clock[0] + 52_000_000
                    failure = "35-second capture deadline"
                with self.assertRaisesRegex(AssertionError, failure):
                    self.run_sweep(
                        observer, clock, pids=(1, 2, 3, 4, 99), exit_ns=1_000_000_000
                    )
                self.assertEqual(observer.supplemental[: len(prior)], prior)
                self.assertTrue(observer.supplemental[len(prior)]["processes"])
                self.assertIn("error", observer.supplemental[-1])
                self.assertEqual(len(observer.supplemental[-1]["anchors"]), 2)
                if cap:
                    self.assertEqual(observer.supplemental_count, 4096)

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

    def test_terminal_observation_cannot_fill_unobservable_counter_bracket(self):
        observer, snapshots = process_capture()
        after = observer.samples[-1]
        terminal = after["processes"].pop("42")
        for source in ("stat", "io"):
            terminal[source].update(errno=errno.ENOENT, value=None, error="exited")
        observer.supplemental = [
            dict(
                census=after["sources"]["/proc"],
                processes=[dict(pid=42, readings=terminal)],
            )
        ]
        result = host_capture.verify_capture(observer, snapshots, None)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["missing_brackets"])
        for missing in result["missing_brackets"]:
            self.assertTrue(missing["sensor_id"].startswith("process:42:1/"))
            self.assertEqual(
                missing["external_attempts"][-1]["stat"]["errno"], errno.ENOENT
            )
