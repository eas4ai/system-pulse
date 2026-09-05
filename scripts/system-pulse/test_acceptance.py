import importlib.util
import unittest


class AggregateTests(unittest.TestCase):
    def test_timeout_retains_owned_child_exit_status(self):
        import tempfile
        import sys
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            runner = __import__("acceptance").Runner(Path(directory))
            with self.assertRaises(AssertionError):
                runner.step(
                    "timeout-probe",
                    [
                        sys.executable,
                        "-B",
                        "-c",
                        'import time; print("started", flush=True); time.sleep(10)',
                    ],
                    timeout=0.1,
                )
            self.assertIn("timeout-probe", runner.steps)
            self.assertIsNotNone(runner.steps["timeout-probe"]["exit_code"])
            self.assertTrue(runner.steps["timeout-probe"]["timed_out"])

    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("acceptance"), "mandatory aggregate missing"
        )
        self.runner = __import__("acceptance")

    def test_nonzero_executed_rust_tests(self):
        self.assertEqual(
            self.runner.test_count(
                "test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s",
                "rust",
            ),
            3,
        )
        for text in (
            "",
            "test result: ok. 0 passed; 0 failed;",
            "test result: FAILED. 3 passed; 1 failed;",
        ):
            with self.assertRaises(AssertionError):
                self.runner.test_count(text, "rust")

    def test_nonzero_python_tests(self):
        self.assertEqual(
            self.runner.test_count("Ran 14 tests in 0.001s\n\nOK\n", "python"), 14
        )
        for text in (
            "Ran 0 tests in 0s\nOK",
            "Ran 2 tests in 0s\nFAILED (failures=1)",
            "OK",
        ):
            with self.assertRaises(AssertionError):
                self.runner.test_count(text, "python")

    def test_omitted_step_fails(self):
        required = {"tests", "host", "native"}
        self.runner.require_steps(required, {k: {"exit_code": 0} for k in required})
        for completed in (
            {"tests": {"exit_code": 0}},
            {k: {"exit_code": 1 if k == "native" else 0} for k in required},
        ):
            with self.assertRaises(AssertionError):
                self.runner.require_steps(required, completed)


class TruthfulResultTests(unittest.TestCase):
    def test_held_input_requires_fresh_frames_signed_motion_and_exact_burst(self):
        contract = __import__("native_contract")
        self.assertTrue(hasattr(contract, "check_input_record"))
        good = {
            "observations": [{"sequence": n, "age": 1.1} for n in (1, 2, 3)],
            "before": 10,
            "after": 5,
            "sign": -1,
            "key_count": 64,
        }
        contract.check_input_record(good, 64)
        for field, value in (
            ("after", 10),
            ("sign", 1),
            ("key_count", 63),
            ("observations", [{"sequence": 1, "age": 2.1}]),
        ):
            wrong = dict(good)
            wrong[field] = value
            with self.assertRaises(AssertionError):
                contract.check_input_record(wrong, 64)

    def test_split_requires_horizontal_siblings_in_requested_order(self):
        import copy

        contract = __import__("native_contract")
        self.assertTrue(hasattr(contract, "horizontal_pair"))

        def panel(mid):
            return {
                "panel_name": "TabPanel",
                "children": [
                    {
                        "panel_name": "SystemPulseMonitor",
                        "children": [],
                        "info": {"panel": {"monitor_id": mid}},
                    }
                ],
                "info": {"tabs": {"active_index": 0}},
            }

        good = {
            "panel_name": "StackPanel",
            "children": [panel("memory:host"), panel("cpu:host")],
            "info": {"stack": {"axis": 0, "sizes": [300, 300]}},
        }
        self.assertIsNotNone(contract.horizontal_pair(good, "memory:host", "cpu:host"))
        wrong = copy.deepcopy(good)
        wrong["info"]["stack"]["axis"] = 1
        self.assertIsNone(contract.horizontal_pair(wrong, "memory:host", "cpu:host"))
        wrong = copy.deepcopy(good)
        wrong["children"].reverse()
        self.assertIsNone(contract.horizontal_pair(wrong, "memory:host", "cpu:host"))
        wrong = copy.deepcopy(good)
        wrong["children"][0]["children"].extend(wrong["children"].pop()["children"])
        self.assertIsNone(contract.horizontal_pair(wrong, "memory:host", "cpu:host"))

    def test_failure_after_last_case_cannot_report_pass(self):
        runner = __import__("native_replay")
        self.assertTrue(
            hasattr(runner, "result_status"), "truthful native completion state missing"
        )
        cases = {name: True for name in runner.REQUIRED}
        self.assertEqual(runner.result_status(cases, None, True, []), "PASS")
        self.assertEqual(runner.result_status(cases, None, False, []), "FAIL")
        self.assertEqual(
            runner.result_status(cases, None, True, ["shutdown failed"]), "FAIL"
        )
        self.assertEqual(
            runner.result_status({"launch": True}, "launch", True, ["cleanup failed"]),
            "FAIL",
        )
