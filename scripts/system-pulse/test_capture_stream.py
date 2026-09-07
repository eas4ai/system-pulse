"""Real owned subprocesses exercise stream framing and stop acknowledgement."""

import importlib
import io
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch


class CaptureStreamTests(unittest.TestCase):
    def test_forced_cleanup_is_reaped_but_not_a_success(self):
        capture = importlib.import_module("host_capture")
        child = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print("ready",flush=True);time.sleep(30)',
            ],
            stdout=subprocess.PIPE,
        )
        try:
            self.assertEqual(child.stdout.readline(), b"ready\n")
            with self.assertRaises(AssertionError):
                capture.stop_child(child)
            self.assertEqual(child.returncode, -signal.SIGKILL)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            child.stdout.close()

    def test_new_processes_precede_old_ones_without_omitting_any(self):
        capture = importlib.import_module("host_capture")
        self.assertTrue(hasattr(capture.Observer, "capture_processes"))
        observer = capture.Observer.__new__(capture.Observer)
        observer.previous_pids = {10, 20}
        observer.supplemental_pids = set()
        observer.observed_identities = {}
        observer.capture_deadline_ns = None
        called = []

        def read(pid):
            called.append(pid)
            return {
                "stat": {"errno": None, "value": {"pid": pid, "start_ticks": pid + 100}}
            }

        with patch.object(capture, "process", read), patch.object(
            observer, "refresh_processes_if_due", return_value=None
        ):
            result = observer.capture_processes([10, 30, 20, 40])
        self.assertEqual(called, [30, 40, 10, 20])
        self.assertEqual(set(result), {"10", "20", "30", "40"})
        self.assertEqual(observer.previous_pids, {10, 20, 30, 40})

    def setUp(self):
        self.capture = importlib.import_module("host_capture")
        self.assertTrue(
            hasattr(self.capture, "read_four_and_stop"),
            "bounded live collector stop missing",
        )

    def run_child(self, payload):
        code = "import os,time;os.write(1," + repr(payload) + ");time.sleep(60)"
        return subprocess.Popen(
            [sys.executable, "-B", "-c", code], stdout=subprocess.PIPE
        )

    def finish(self, child):
        child.send_signal(signal.SIGTERM)
        child.send_signal(signal.SIGCONT)
        child.wait(timeout=5)
        child.stdout.close()

    def test_four_lines_stop_live_process_and_preserve_all_bytes(self):
        data = b"one\ntwo\nthree\nfour\n"
        child = self.run_child(data)
        out = io.BytesIO()
        try:
            stopped = self.capture.read_four_and_stop(child, out, 3)
            self.assertEqual(out.getvalue(), data)
            self.assertEqual(stopped["stat"]["value"]["state"], "T")
            self.assertIsNone(stopped["io"]["errno"])
        finally:
            self.finish(child)

    def test_extra_line_or_partial_fifth_fails_and_retains_bytes(self):
        for extra in (b"five\n", b"partial"):
            data = b"one\ntwo\nthree\nfour\n" + extra
            child = self.run_child(data)
            out = io.BytesIO()
            try:
                with self.assertRaises(AssertionError):
                    self.capture.read_four_and_stop(child, out, 3)
                self.assertEqual(out.getvalue(), data)
            finally:
                self.finish(child)
