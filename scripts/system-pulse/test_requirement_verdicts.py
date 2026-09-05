"""Cairn reporting uses final artifacts, never provisional progress."""

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import acceptance
from native_replay import REQUIRED

HOST_IDS = {4, 12, 13}
PRIMARY_IDS = HOST_IDS | {1, 2, 3, 5, 8, 9, 11}


class RequirementVerdictTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.files = set()
        for name in (
            "result.json capabilities.json final-inventory.json stable-totals.json "
            "external-observations.json snapshots.jsonl counter-brackets.json "
            "missing-brackets.json collector-lifecycle.json collector-start.json "
            "collector-stopped.json cleanup.json child.json after-exit.jsonl"
        ).split():
            self.artifact("host/" + name)
        for name in (
            "result.json progress.jsonl private-session.json harness-manifest.json "
            "transport-cleanup.json missing-device-config.json"
        ).split():
            self.artifact("native/" + name)
        for session in (
            "session-01 session-02 session-recovery-schema "
            "session-recovery-schema-restart session-recovery-json "
            "session-recovery-json-restart session-missing-device"
        ).split():
            self.artifact(f"native/{session}/journal.jsonl")
            self.write(f"native/{session}/metadata.json", {"application_pid": 123})
            self.write(
                f"native/{session}/shutdown.json",
                {
                    "exit_code": 0,
                    "before_deadline": True,
                },
            )
            self.write(
                f"native/{session}/cleanup.json",
                [
                    {
                        "pid": 123,
                        "exit_code": 0,
                        "proc_exists": False,
                    }
                ],
            )
        for name in (
            "cpu-visible ram-visible row-compact panel-compact chart-physical-value "
            "ram-capacity child-left child-right gpu-0-visible gpu-0-temperature "
            "child-visible-1 child-visible-2 child-visible-3 child-visible-4 "
            "child-visible-5 child-visible-6 launch-no-tabs split-no-tabs recall-no-tabs"
        ).split():
            for suffix in (".json", ".png"):
                self.artifact("native/session-01/" + name + suffix)
        for name in (
            "split-structure divider-movement outer-movement inner-edge-wheel "
            "chart-history-evidence collapsed-sequences real-child "
            "real-child-cell-discovery deliberate-scroll-sequences held-up-25hz "
            "exact-64-up held-table-left held-table-right held-outer-next "
            "held-outer-prior held-outer-left held-outer-right"
        ).split():
            self.artifact("native/session-01/" + name + ".json")
        for name in (
            "expanded-chart ram-capacity-chart split-divider outer-scroll "
            "inner-scroll child-exited"
        ).split():
            self.artifact("native/session-01/" + name + ".png")
        for mode in ("schema", "json"):
            self.artifact(f"native/session-recovery-{mode}/rejected-specimen.json")
        for name in (
            "missing-native.json",
            "missing-native.png",
            "missing-device-specimen.json",
        ):
            self.artifact("native/session-missing-device/" + name)
        self.write("host/result.json", {"status": "PASS"})
        self.write(
            "native/transport-cleanup.json",
            {
                "pid": 456,
                "exit_code": 0,
                "proc_exists": False,
                "forced_kill": False,
                "errors": [],
            },
        )
        self.native = {
            "status": "PASS",
            "focused_preparation": None,
            "errors": [],
            "cases": {name: True for name in REQUIRED},
        }
        self.native["cases"].update(
            {
                "metrics": {"gpu_count": 1},
                "charts": {
                    "gpu_temperature_count": 1,
                    "gpu_temperature_artifacts": ["gpu-0-temperature"],
                },
                "restart": {"new_discovery": []},
            }
        )
        self.write("native/result.json", self.native)

    def artifact(self, name):
        path = self.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test evidence\n")
        self.files.add(str(path))

    def write(self, name, value):
        self.artifact(name)
        (self.output / name).write_text(json.dumps(value))

    def run_gate(self, failure=None, fail_step="native", zero_tests=False):
        stdout = io.StringIO()
        stderr = io.StringIO()

        def step(runner, name, command, kind=None, timeout=1800):
            # Exercise main and its real artifact checks without live processes.
            runner.progress(name, "RUNNING")
            runner.steps[name] = {"exit_code": 0, "timed_out": False}
            if kind:
                runner.steps[name]["test_count"] = 0 if zero_tests else 1
            if name == fail_step and failure:
                runner.steps[name]["exit_code"] = 1
                raise failure
            runner.progress(name, "PASS")
            self.assertNotIn("cairn:", stdout.getvalue())

        error = None
        with patch.object(acceptance.Runner, "step", step), patch.object(
            acceptance.tempfile, "mkdtemp", return_value=str(self.output)
        ), patch("sys.argv", ["acceptance.py"]), contextlib.redirect_stdout(
            stdout
        ), contextlib.redirect_stderr(
            stderr
        ):
            try:
                acceptance.main()
            except BaseException as caught:
                error = caught
        self.stderr = stderr.getvalue()
        lines = [
            line for line in stdout.getvalue().splitlines() if line.startswith("cairn:")
        ]
        self.assertEqual(len(lines), len(set(lines)), "duplicate verdicts")
        ids = set()
        for line in lines:
            self.assertRegex(line, r"^cairn: LIVE-\d{3}: pass$")
            ids.add(int(line.split()[1][5:-1]))
        return ids, error

    def late_failure(self):
        self.native["status"] = "FAIL"
        self.native["errors"] = ["missing specimen dock changed"]
        del self.native["cases"]["missing-device"]
        self.write("native/result.json", self.native)
        return AssertionError("native exited 1; original failure")

    def test_late_failure_preserves_primary_groups_and_original_error(self):
        failure = self.late_failure()
        ids, error = self.run_gate(failure)
        self.assertEqual(ids, PRIMARY_IDS)
        self.assertIs(error, failure)
        self.assertEqual(
            json.loads((self.output / "failure.json").read_text())["error"],
            str(failure),
        )
        self.assertFalse((self.output / "manifest.json").exists())

    def test_complete_gate_reports_all_once_and_accounts_for_every_artifact(self):
        ids, error = self.run_gate()
        self.assertIsNone(error)
        self.assertEqual(ids, set(range(1, 14)))
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual({a["path"] for a in manifest["artifacts"]}, self.files)

    def test_missing_host_artifact_earns_nothing(self):
        (self.output / "host/counter-brackets.json").unlink()
        ids, error = self.run_gate(self.late_failure())
        self.assertEqual(ids, set())
        self.assertIsNotNone(error)

    def test_missing_primary_artifact_keeps_only_host(self):
        (self.output / "native/session-01/held-up-25hz.json").unlink()
        self.assertEqual(self.run_gate(self.late_failure())[0], HOST_IDS)

    def test_missing_remaining_artifact_prevents_aggregate_success(self):
        (self.output / "native/session-missing-device/missing-native.png").unlink()
        ids, error = self.run_gate()
        self.assertEqual(ids, PRIMARY_IDS)
        self.assertIsNotNone(error)

    def test_failed_transport_keeps_only_host(self):
        self.write(
            "native/transport-cleanup.json",
            {
                "pid": 456,
                "exit_code": 0,
                "proc_exists": True,
                "forced_kill": False,
                "errors": [],
            },
        )
        self.assertEqual(self.run_gate(self.late_failure())[0], HOST_IDS)

    def test_failed_normal_shutdown_keeps_only_host(self):
        self.write(
            "native/session-02/shutdown.json",
            {"exit_code": -15, "before_deadline": False},
        )
        self.assertEqual(self.run_gate(self.late_failure())[0], HOST_IDS)

    def test_failed_session_cleanup_keeps_only_host(self):
        self.write(
            "native/session-01/cleanup.json",
            [{"pid": 123, "exit_code": 0, "proc_exists": True}],
        )
        self.assertEqual(self.run_gate(self.late_failure())[0], HOST_IDS)

    def test_cleanup_and_shutdown_require_integer_exit_codes(self):
        for name in ("shutdown.json", "cleanup.json"):
            path = self.output / "native/session-01" / name
            original = json.loads(path.read_text())
            for value in (False, 0.0):
                with self.subTest(name=name, value=value):
                    record = copy.deepcopy(original)
                    (record[0] if isinstance(record, list) else record)[
                        "exit_code"
                    ] = value
                    path.write_text(json.dumps(record))
                    ids, error = self.run_gate(
                        AssertionError("original native failure")
                    )
                    self.assertEqual(ids, HOST_IDS)
                    self.assertIsInstance(error, AssertionError)
            path.write_text(json.dumps(original))

    def test_cleanup_requires_positive_integer_pid(self):
        for value in (False, 123.0, 0, -1, "123", None):
            with self.subTest(value=value):
                self.write(
                    "native/session-01/cleanup.json",
                    [
                        {
                            "pid": value,
                            "exit_code": 0,
                            "proc_exists": False,
                        }
                    ],
                )
                self.assertEqual(
                    self.run_gate(AssertionError("native failed"))[0], HOST_IDS
                )

    def test_cleanup_pid_must_match_integer_application_pid(self):
        for value in (124, 123.0, True, None):
            with self.subTest(application_pid=value):
                self.write(
                    "native/session-01/metadata.json", {"application_pid": value}
                )
                self.assertEqual(
                    self.run_gate(AssertionError("native failed"))[0], HOST_IDS
                )

    def test_transport_requires_integer_exit_code_and_pid(self):
        path = self.output / "native/transport-cleanup.json"
        original = json.loads(path.read_text())
        for field, value in (
            ("exit_code", False),
            ("exit_code", 0.0),
            ("pid", True),
            ("pid", 456.0),
            ("pid", 0),
        ):
            with self.subTest(field=field, value=value):
                record = dict(original, **{field: value})
                path.write_text(json.dumps(record))
                self.assertEqual(
                    self.run_gate(AssertionError("native failed"))[0], HOST_IDS
                )

    def test_excessively_nested_native_result_preserves_host_and_original_failure(self):
        failure = AssertionError("native exited 1; original failure")
        (self.output / "native/result.json").write_text("[" * 10000 + "0" + "]" * 10000)
        ids, error = self.run_gate(failure)
        self.assertIs(error, failure)
        self.assertEqual(ids, HOST_IDS)
        self.assertEqual(
            json.loads((self.output / "failure.json").read_text())["error"],
            str(failure),
        )
        self.assertIn("Unverified requirement evidence:", self.stderr)

    def test_native_json_recursion_error_preserves_host_and_original_failure(self):
        failure = AssertionError("native exited 1; original failure")
        native_text = (self.output / "native/result.json").read_text()
        original_loads = json.loads

        def load_evidence(text):
            if text == native_text:
                raise RecursionError("native JSON recursion limit")
            return original_loads(text)

        with patch.object(acceptance.json, "loads", side_effect=load_evidence):
            ids, error = self.run_gate(failure)
        self.assertIs(error, failure)
        self.assertEqual(ids, HOST_IDS)
        self.assertEqual(
            json.loads((self.output / "failure.json").read_text())["error"],
            str(failure),
        )
        self.assertIn(
            "Unverified requirement evidence: native JSON recursion limit", self.stderr
        )

    def test_focused_preparation_keeps_only_host(self):
        self.native["focused_preparation"] = "missing-device"
        self.write("native/result.json", self.native)
        self.assertEqual(
            self.run_gate(AssertionError("focused preparation"))[0], HOST_IDS
        )

    def test_missing_primary_case_keeps_only_host(self):
        failure = self.late_failure()
        del self.native["cases"]["restart"]
        self.write("native/result.json", self.native)
        self.assertEqual(self.run_gate(failure)[0], HOST_IDS)

    def test_unknown_native_result_shape_fails_closed(self):
        self.write("native/result.json", {"status": "PASS", "cases": []})
        self.assertEqual(self.run_gate(AssertionError("native failure"))[0], HOST_IDS)

    def test_false_completed_case_fails_closed(self):
        self.native["cases"]["process"] = False
        self.write("native/result.json", self.native)
        ids, error = self.run_gate()
        self.assertEqual(ids, HOST_IDS)
        self.assertIsNotNone(error)

    def test_missing_final_result_cannot_use_progress(self):
        (self.output / "native/result.json").unlink()
        self.assertEqual(self.run_gate(AssertionError("native failed"))[0], HOST_IDS)

    def test_early_failure_emits_no_sentinel(self):
        self.assertEqual(
            self.run_gate(AssertionError("build failed"), "build")[0], set()
        )

    def test_nonzero_test_counts_are_required(self):
        self.assertEqual(self.run_gate(self.late_failure(), zero_tests=True)[0], set())

    def test_host_failure_cannot_earn_host_group(self):
        self.write("host/result.json", {"status": "FAIL"})
        self.assertEqual(self.run_gate(self.late_failure())[0], set())

    def test_host_nonzero_exit_cannot_earn_host_group(self):
        self.assertEqual(self.run_gate(AssertionError("host failed"), "host")[0], set())

    def test_late_nonzero_exit_after_all_cases_never_earns_final_group(self):
        ids, error = self.run_gate(AssertionError("late native failure"))
        self.assertEqual(ids, PRIMARY_IDS)
        self.assertIsNotNone(error)

    def test_manifest_hash_failure_never_emits_final_group(self):
        original = acceptance.sha256
        failure = OSError("manifest hash failed")

        def hash_artifact(path):
            if Path(path).name == "manifest.json":
                raise failure
            return original(path)

        with patch.object(acceptance, "sha256", hash_artifact):
            ids, error = self.run_gate()
        self.assertEqual(ids, PRIMARY_IDS)
        self.assertIs(error, failure)

    def test_remaining_session_shutdown_failure_keeps_primary_groups(self):
        self.write(
            "native/session-recovery-json/shutdown.json",
            {
                "exit_code": -15,
                "before_deadline": False,
            },
        )
        ids, error = self.run_gate()
        self.assertEqual(ids, PRIMARY_IDS)
        self.assertIsNotNone(error)

    def test_malformed_native_fields_fail_closed(self):
        original = copy.deepcopy(self.native)
        for name, value in (
            ("metrics", {"gpu_count": -1}),
            ("metrics", {"gpu_count": True}),
            (
                "charts",
                {
                    "gpu_temperature_count": 2,
                    "gpu_temperature_artifacts": ["gpu-0-temperature"],
                },
            ),
            (
                "charts",
                {
                    "gpu_temperature_count": 1,
                    "gpu_temperature_artifacts": ["../outside"],
                },
            ),
            ("restart", {"new_discovery": None}),
        ):
            with self.subTest(name=name, value=value):
                native = copy.deepcopy(original)
                native["cases"][name] = value
                self.write("native/result.json", native)
                ids, error = self.run_gate()
                self.assertEqual(ids, HOST_IDS)
                self.assertIsNotNone(error)

    def test_unterminated_native_step_cannot_use_final_artifacts(self):
        runner = acceptance.Runner(self.output)
        runner.steps["native"] = {"exit_code": None}
        with self.assertRaisesRegex(AssertionError, "native not terminated"):
            acceptance.read_native_result(runner)


if __name__ == "__main__":
    unittest.main()
