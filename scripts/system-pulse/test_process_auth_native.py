"""Boundary checks for the interactive verifier; never request authentication."""

import ctypes
import os
import struct
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import process_auth_native as native
from performance_compare import InvalidMeasurement


class AuthNativeTests(unittest.TestCase):
    def test_fixture_command_only_allows_fixed_short_lifetimes(self):
        for duration in (0, -1, 181, "180; true", 20.0, True):
            with self.assertRaises(InvalidMeasurement):
                native.fixture_command(duration)
        for platform in ("Linux", "Darwin"):
            with patch.object(native.platform, "system", return_value=platform):
                command = native.fixture_command(180)
            self.assertIn("/bin/sleep 180 </dev/null >/dev/null 2>&1", command[-1])
            self.assertEqual(command[0], "/usr/bin/pkexec" if platform == "Linux" else "/usr/bin/osascript")
            if platform == "Linux":
                self.assertIn("--disable-internal-agent", command)

    def test_actual_owned_child_identity_and_exit(self):
        child = subprocess.Popen(["/bin/sleep", "10"])
        try:
            identity = native.process_identity(child.pid)
            self.assertEqual(identity["uid"], os.getuid())
            self.assertEqual(identity["pid"], child.pid)
            self.assertGreater(identity["start_time_ticks"], 0)
            self.assertTrue(native.alive(identity))
            self.assertFalse(native.alive(dict(identity, start_time_ticks=identity["start_time_ticks"] + 1)))
            child.terminate()
            child.wait(timeout=5)
            self.assertIsNone(native.process_identity(child.pid))
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)

    @unittest.skipUnless(native.platform.system() == "Darwin", "native Mac identity")
    def test_root_identity_is_readable_without_elevation(self):
        identity = native.process_identity(1)
        self.assertEqual(identity["pid"], 1)
        self.assertEqual(identity["uid"], 0)
        self.assertGreater(identity["start_time_ticks"], 0)

    def test_mac_identity_rejects_incomplete_and_invalid_kernel_records(self):
        def observe(size=648, result=0, pid=42, seconds=123, micros=456, status=3):
            def sysctl(_mib, _length, output, output_size, _new, _new_size):
                data = bytearray(648)
                struct.pack_into("=qi", data, 0, seconds, micros)
                struct.pack_into("=i", data, 40, pid)
                data[36] = status
                ctypes.memmove(output, bytes(data), len(data))
                ctypes.cast(output_size, ctypes.POINTER(ctypes.c_size_t))[0] = size
                return result
            library = SimpleNamespace(sysctl=Mock(side_effect=sysctl))
            with patch.object(native.platform, "system", return_value="Darwin"), \
                    patch.object(native.ctypes, "CDLL", return_value=library):
                return native.process_identity(42)

        self.assertEqual(observe()["start_time_ticks"], 123_000_456)
        self.assertIsNone(observe(size=0))
        self.assertIsNone(observe(status=5))
        for values in ({"size": 647}, {"size": 649}, {"result": -1}, {"pid": 43},
                       {"seconds": 0}, {"seconds": -1}, {"micros": -1}, {"micros": 1_000_000}):
            with self.subTest(values=values), self.assertRaises(InvalidMeasurement):
                observe(**values)

    def test_mac_initialization_failure_closes_only_its_owned_app(self):
        child = Mock()
        child.pid = 4242
        child.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(output=Path(directory), binary=Path("/unused"), tree=Path("/unused"))
            with patch.object(native.subprocess, "Popen", return_value=child), \
                    patch.object(native, "wait_for", side_effect=RuntimeError("no native tree")):
                with self.assertRaisesRegex(RuntimeError, "no native tree"):
                    native.MacUI(args)
        child.terminate.assert_called_once_with()
        child.wait.assert_called_once_with(timeout=10)

    def test_mac_confirm_refuses_a_different_or_missing_fixture(self):
        ui = object.__new__(native.MacUI)
        ui.selected = {"pid": 4242, "start_time_ticks": 123, "uid": 0}
        ui.tree = Mock()
        ui.process_ids = Mock(return_value=["process:4242:124"])
        with patch.object(native, "alive", return_value=True):
            with self.assertRaises(InvalidMeasurement):
                ui.confirm("kill")
        ui.tree.assert_not_called()


if __name__ == "__main__":
    unittest.main()
