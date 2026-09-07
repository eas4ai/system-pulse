"""Adversarial process attribution dictionaries stay inside verifier tests."""

import copy
import os
import unittest

import host_capture
from test_host_inventory import capture


def process_capture():
    observer, snapshots = capture()
    hz = os.sysconf("SC_CLK_TCK")
    page_size = os.sysconf("SC_PAGE_SIZE")
    for snapshot in snapshots:
        row = snapshot["processes"][0]
        for field, value, endpoint, filename in (
            (
                "cpu_percent",
                100.0 * 20.0 / float(hz) / 1e-8,
                lambda n: dict(
                    utime_ticks=n,
                    stime_ticks=n,
                    start_time_ticks=1,
                    ticks_per_second=hz,
                ),
                "stat",
            ),
            (
                "memory_bytes",
                page_size,
                lambda n: dict(rss_pages=1, page_size=page_size),
                "stat",
            ),
            ("read_bytes_per_second", 1e9, lambda n: dict(bytes=n), "io"),
            ("write_bytes_per_second", 1e9, lambda n: dict(bytes=n), "io"),
        ):
            reading = row[field]
            reading.update(availability="Available", reason=None, value=value)
            reading["observations"] = [
                dict(
                    source=f"/proc/42/{filename}",
                    read_started_ns=n,
                    captured_ns=n,
                    integers=endpoint(n),
                    decimals={},
                )
                for n in ((20,) if field == "memory_bytes" else (10, 20))
            ]
    for sample in observer.samples:
        timing = sample["sources"]["/proc/stat"]
        value = timing["value"]["cpu"]["user"]
        sample["sources"]["/proc"] = dict(
            source="/proc",
            start=timing["start"],
            end=timing["end"],
            errno=None,
            value=[42],
        )
        sample["processes"]["42"] = {
            "stat": dict(
                source="/proc/42/stat",
                start=timing["start"],
                end=timing["end"],
                errno=None,
                value=dict(pid=42, start_ticks=1, utime=value, stime=value),
            ),
            "io": dict(
                source="/proc/42/io",
                start=timing["start"],
                end=timing["end"],
                errno=None,
                value=dict(read_bytes=value, write_bytes=value),
            ),
        }
    return observer, snapshots


class ProcessAttributionTests(unittest.TestCase):
    def test_control_has_actual_cpu_and_io_brackets(self):
        observer, snapshots = process_capture()
        result = host_capture.verify_capture(observer, snapshots, None)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["counts"]["counter_brackets"], 72)

    def test_each_field_rejects_wrong_pid_start_suffix_or_source(self):
        for field in (
            "cpu_percent",
            "memory_bytes",
            "read_bytes_per_second",
            "write_bytes_per_second",
            "threads",
        ):
            for mutation in ("pid", "start", "suffix", "source_pid", "source_file"):
                with self.subTest(field=field, mutation=mutation):
                    observer, snapshots = process_capture()
                    for snapshot in snapshots:
                        reading = snapshot["processes"][0][field]
                        if mutation == "pid":
                            reading["sensor_id"] = reading["sensor_id"].replace(
                                "process:42:", "process:999:"
                            )
                        elif mutation == "start":
                            reading["sensor_id"] = reading["sensor_id"].replace(
                                ":1/", ":123/"
                            )
                        elif mutation == "suffix":
                            reading["sensor_id"] += "-wrong"
                        else:
                            for observation in reading["observations"]:
                                observation["source"] = (
                                    observation["source"].replace("/42/", "/999/")
                                    if mutation == "source_pid"
                                    else "/proc/42/status"
                                )
                    with self.assertRaises(AssertionError):
                        host_capture.verify_capture(observer, snapshots, None)

    def test_row_identity_and_duplicate_rows_rejected(self):
        for mutation in ("pid", "start", "duplicate", "same_pid_new_start"):
            with self.subTest(mutation=mutation):
                observer, snapshots = process_capture()
                for snapshot in snapshots:
                    row = snapshot["processes"][0]
                    if mutation == "pid":
                        row["identity"]["pid"] = 999
                    elif mutation == "start":
                        row["identity"]["start_time_ticks"] = 123
                    else:
                        duplicate = copy.deepcopy(row)
                        if mutation == "same_pid_new_start":
                            duplicate["identity"]["start_time_ticks"] = 123
                        snapshot["processes"].append(duplicate)
                with self.assertRaises(AssertionError):
                    host_capture.verify_capture(observer, snapshots, None)

    def test_unavailable_field_still_belongs_to_its_row(self):
        observer, snapshots = capture()
        for snapshot in snapshots:
            snapshot["processes"][0]["memory_bytes"]["sensor_id"] = (
                "process:999:123/memory"
            )
        with self.assertRaises(AssertionError):
            host_capture.verify_capture(observer, snapshots, None)
