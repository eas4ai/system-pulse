"""Instrumented publication evidence must never become final acceptance."""

import json
import ast
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import acceptance
import native_replay


class PublicationTimingHarnessTests(unittest.TestCase):
    def test_application_keeps_the_private_transport_environment(self):
        import threading
        import time

        source = Path(__file__).with_name("native_driver.py")
        native = next(
            node
            for node in ast.parse(source.read_text()).body
            if isinstance(node, ast.ClassDef) and node.name == "Native"
        )
        methods = [
            node
            for node in native.body
            if isinstance(node, ast.FunctionDef) and node.name == "_initialize"
        ]

        class ApplicationLaunch(Exception):
            pass

        subprocess = Mock()
        subprocess.Popen.side_effect = [SimpleNamespace(), ApplicationLaunch]
        namespace = dict(
            Path=Path,
            os=os,
            time=time,
            threading=threading,
            json=json,
            display=Mock(),
            subprocess=subprocess,
            TRANSPORT=None,
            Atspi=Mock(),
            spin=lambda _: None,
        )
        exec(
            compile(ast.Module(body=methods, type_ignores=[]), str(source), "exec"),
            namespace,
        )

        def no_saved_state():
            raise FileNotFoundError

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ, {"AT_SPI_BUS_ADDRESS": "stale-session-address"}, clear=True
            ),
        ):
            app = SimpleNamespace(state=no_saved_state)
            app.diagnostic_environment = lambda: self.environment_method()(app)
            try:
                with self.assertRaises(ApplicationLaunch):
                    namespace["_initialize"](
                        app, "/app", Path(directory, "native"), Path(directory, "state")
                    )
                environment = subprocess.Popen.call_args.kwargs["env"]
                self.assertNotIn("AT_SPI_BUS_ADDRESS", environment)
            finally:
                app.log.close()

    def environment_method(self):
        source = Path(__file__).with_name("native_driver.py")
        native = next(
            node
            for node in ast.parse(source.read_text()).body
            if isinstance(node, ast.ClassDef) and node.name == "Native"
        )
        methods = [
            node
            for node in native.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "diagnostic_environment"
        ]
        self.assertEqual(
            len(methods), 1, "native trace environment integration missing"
        )
        import time

        namespace = dict(os=os, time=time)
        exec(
            compile(ast.Module(body=methods, type_ignores=[]), str(source), "exec"),
            namespace,
        )
        return namespace["diagnostic_environment"]

    def test_explicit_opt_in_retains_early_metadata_without_reading_the_sidecar(self):
        configure = self.environment_method()
        for enabled in (False, True):
            with self.subTest(enabled=enabled), patch.dict(os.environ, {}, clear=True):
                if enabled:
                    os.environ["SYSTEM_PULSE_DIAGNOSTICS_TRACE"] = "1"
                saved = {}
                app = SimpleNamespace(
                    latest=Path("/evidence/latest.json"),
                    state_dir=Path("/state"),
                    save=lambda name, record: saved.update({name: record}),
                )
                environment = configure(app)
                self.assertEqual(app.publication_timing_instrumented, enabled)
                self.assertEqual(
                    environment["SYSTEM_PULSE_DIAGNOSTICS_PATH"], str(app.latest)
                )
                self.assertEqual(bool(saved), enabled)
                if enabled:
                    record = saved["publication-timing-metadata.json"]
                    self.assertEqual(
                        record["sidecar"], "/evidence/latest.publication-timing.json"
                    )
                    self.assertTrue(record["publication_timing_instrumented"])
                    anchor = record["harness_clock_anchor"]
                    self.assertLessEqual(
                        anchor["monotonic_before_ns"], anchor["monotonic_after_ns"]
                    )

    def test_cli_forwards_opt_in_into_the_private_session(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "native")

            class CapturedCommand(Exception):
                pass

            with (
                patch.dict(os.environ, {}, clear=True),
                patch(
                    "sys.argv",
                    [
                        "native_replay.py",
                        "--output",
                        str(output),
                        "--binary",
                        "/app",
                        "--trace-publication",
                    ],
                ),
                patch.object(native_replay.shutil, "which", return_value="tool"),
                patch.object(Path, "is_file", return_value=True),
                patch.object(
                    native_replay.subprocess, "Popen", side_effect=CapturedCommand
                ) as launch,
            ):
                with self.assertRaises(CapturedCommand):
                    native_replay.main()
                self.assertIn("--trace-publication", launch.call_args.args[0])
                self.assertTrue(
                    json.loads(
                        (output / "publication-timing-metadata.json").read_text()
                    )["publication_timing_instrumented"]
                )


class PublicationTimingAcceptanceTests(unittest.TestCase):
    def test_session_metadata_cannot_hide_instrumentation(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = acceptance.Runner(Path(directory))
            session = Path(directory, "native", "session-01")
            session.mkdir(parents=True)
            for name, content in {
                "metadata.json": {
                    "application_pid": 123,
                    "publication_timing_instrumented": True,
                },
                "shutdown.json": {"exit_code": 0, "before_deadline": True},
                "cleanup.json": [{"pid": 123, "exit_code": 0, "proc_exists": False}],
                "journal.jsonl": {"op": "launch"},
            }.items():
                (session / name).write_text(json.dumps(content))
            with self.assertRaisesRegex(AssertionError, "instrumented"):
                acceptance.validate_sessions(runner, ["session-01"])

    def test_instrumented_native_result_is_rejected_even_when_all_cases_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = acceptance.Runner(Path(directory))
            runner.steps["native"] = {"exit_code": 0}
            native = Path(directory, "native")
            native.mkdir()
            result = {
                "status": "PASS",
                "focused_preparation": None,
                "cases": {},
                "errors": [],
                "publication_timing_instrumented": True,
            }
            (native / "result.json").write_text(json.dumps(result))
            with self.assertRaisesRegex(AssertionError, "instrumented"):
                acceptance.read_native_result(runner)

    def test_untraced_result_keeps_existing_acceptance_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = acceptance.Runner(Path(directory))
            runner.steps["native"] = {"exit_code": 0}
            native = Path(directory, "native")
            native.mkdir()
            result = {
                "status": "PASS",
                "focused_preparation": None,
                "cases": {},
                "errors": [],
            }
            (native / "result.json").write_text(json.dumps(result))
            self.assertEqual(acceptance.read_native_result(runner), result)
