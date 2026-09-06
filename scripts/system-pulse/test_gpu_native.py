import tempfile
from pathlib import Path
import unittest

try:
    from gpu_capture import owned_process, validate_workload, validate_native_frame
except ImportError:
    owned_process = validate_workload = validate_native_frame = None


class NativeTests(unittest.TestCase):
    def test_workload_requires_matching_device_completed_commands_and_bounds(self):
        self.assertIsNotNone(validate_workload, "native workload validation missing")
        good = dict(
            registry_id=19,
            bytes=4 * 1024**2,
            commands_completed=3,
            duration_ns=20_000_000,
            max_in_flight=1,
            pid=123,
        )
        validate_workload(good, 19, 1)
        for changes in (
            dict(registry_id=20),
            dict(bytes=2**40),
            dict(commands_completed=0),
            dict(max_in_flight=2),
            dict(duration_ns=2_000_000_000),
        ):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                validate_workload({**good, **changes}, 19, 1)

    def test_owned_process_deadline_retains_logs_and_reaps(self):
        self.assertIsNotNone(owned_process, "bounded native child manager missing")
        with tempfile.TemporaryDirectory() as tmp:
            import sys

            r = owned_process(
                Path(tmp),
                "observer",
                [
                    sys.executable,
                    "-c",
                    "import time; print('original',flush=True); time.sleep(10)",
                ],
                0.05,
            )
            self.assertTrue(r["reaped"])
            self.assertFalse(r["proc_exists"])
            self.assertTrue(r["timed_out"])
            self.assertIn("original", (Path(tmp) / r["stdout"]).read_text())

    def test_owned_process_cleans_descendants_after_leader_exits(self):
        import sys
        import os
        import signal

        with tempfile.TemporaryDirectory() as tmp:
            record = owned_process(
                Path(tmp),
                "observer",
                [
                    sys.executable,
                    "-c",
                    "import subprocess; subprocess.Popen(['sleep','10'])",
                ],
                2,
            )
            try:
                self.assertFalse(record["proc_exists"])
            finally:
                try:
                    os.killpg(record["pid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_ax_cycles_truncation_and_zero_geometry_are_not_display(self):
        self.assertIsNotNone(validate_native_frame, "native frame validation missing")
        for frame in (
            dict(complete=False, elements=[]),
            dict(complete=True, elements=[]),
            dict(
                complete=True,
                elements=[
                    dict(identifier="gpu", frame=[0, 0, 0, 1], clip=[0, 0, 100, 100])
                ],
            ),
        ):
            with self.subTest(frame=frame), self.assertRaises(AssertionError):
                validate_native_frame(frame)

    def test_concurrent_owned_child_is_stopped_when_capture_fails(self):
        import gpu_capture

        self.assertTrue(
            hasattr(gpu_capture, "CaptureChildren"), "concurrent capture owner missing"
        )
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "capture failed"):
                with gpu_capture.CaptureChildren(output) as children:
                    pid = children.start(
                        "application",
                        [sys.executable, "-c", "import time; time.sleep(10)"],
                        5,
                    )
                    self.assertGreater(pid, 0)
                    raise RuntimeError("capture failed")
            import json

            record = json.loads((output / "application-finished.json").read_text())
            self.assertTrue(record["reaped"])
            self.assertFalse(record["proc_exists"])
            self.assertNotEqual(record["exit_code"], 0)

    def test_locked_or_unavailable_console_never_allows_gui_capture(self):
        from gpu_host_capture import console_session

        session = dict(
            kCGSSessionOnConsoleKey=True,
            kCGSessionLoginDoneKey=True,
            CGSSessionScreenIsLocked=True,
        )
        self.assertTrue(console_session([dict(IOConsoleUsers=[session])])["locked"])
        session["CGSSessionScreenIsLocked"] = False
        self.assertFalse(console_session([dict(IOConsoleUsers=[session])])["locked"])
        session.pop("CGSSessionScreenIsLocked")
        with self.assertRaises(AssertionError):
            console_session([dict(IOConsoleUsers=[session])])
        with self.assertRaises(AssertionError):
            console_session([dict(IOConsoleUsers=[])])

    def test_native_hashing_does_not_require_python_311(self):
        self.assertIsNotNone(owned_process, "native child manager missing")
        import hashlib
        from unittest.mock import patch
        import sys

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(hashlib, "file_digest", None),
        ):
            r = owned_process(
                Path(tmp), "observer", [sys.executable, "-c", "print('original')"], 2
            )
            self.assertEqual(r["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
