"""Exercise the native cleanup function without launching GI, DBus or an app."""

import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

import native_contract


def cleanup_function(child):
    source = Path(__file__).with_name("native_driver.py")
    node = next(
        n
        for n in ast.parse(source.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "close_transport"
    )
    context = dict(
        TRANSPORT=child,
        Path=Path,
        json=json,
        subprocess=subprocess,
        check_transport_record=getattr(native_contract, "check_transport_record", None),
    )
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), context
    )
    return context["close_transport"]


class NativeCleanupTests(unittest.TestCase):
    def child(self, code=0, pid=99999999):
        child = Mock(pid=pid, returncode=code)
        child.poll.return_value = code
        return child

    def test_normal_observed_exit_zero_control(self):
        with tempfile.TemporaryDirectory() as directory:
            cleanup_function(self.child())(Path(directory))
            record = json.loads(Path(directory, "transport-cleanup.json").read_text())
            self.assertEqual(record["exit_code"], 0)
            self.assertFalse(record["proc_exists"])

    def test_nonzero_exit_or_surviving_pid_fails(self):
        for child in (self.child(42), self.child(-15), self.child(0, os.getpid())):
            with self.subTest(pid=child.pid, code=child.returncode):
                with tempfile.TemporaryDirectory() as directory:
                    with self.assertRaises(AssertionError):
                        cleanup_function(child)(Path(directory))
                    self.assertTrue(Path(directory, "transport-cleanup.json").is_file())

    def test_forced_kill_and_termination_error_preserve_failure_record(self):
        for error in (
            subprocess.TimeoutExpired("private transport", 5),
            OSError("termination failed"),
        ):
            with self.subTest(error=str(error)):
                child = self.child(None)
                child.wait.side_effect = [error, -9]
                child.kill.side_effect = lambda: setattr(child, "returncode", -9)
                with tempfile.TemporaryDirectory() as directory:
                    with self.assertRaises((AssertionError, OSError)):
                        cleanup_function(child)(Path(directory))
                    record = json.loads(
                        Path(directory, "transport-cleanup.json").read_text()
                    )
                    self.assertTrue(record["errors"])
                    self.assertTrue(record["forced_kill"])

    def test_aggregate_rejects_bad_or_missing_transport_fields(self):
        self.assertTrue(hasattr(native_contract, "check_transport_record"))
        good = dict(exit_code=0, proc_exists=False, forced_kill=False, errors=[])
        native_contract.check_transport_record(good)
        for key, value in (
            ("exit_code", 42),
            ("proc_exists", True),
            ("forced_kill", True),
            ("errors", ["cleanup failed"]),
        ):
            with self.subTest(key=key):
                with self.assertRaises(AssertionError):
                    native_contract.check_transport_record(dict(good, **{key: value}))
                missing = dict(good)
                del missing[key]
                with self.assertRaises((AssertionError, KeyError)):
                    native_contract.check_transport_record(missing)
