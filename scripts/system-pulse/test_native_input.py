"""Check input observation ordering and bounds without native input or a session."""

import ast
from pathlib import Path
from types import SimpleNamespace
import threading
import time
import unittest
from unittest.mock import Mock, patch

from native_input import exercise
from test_native_exit import Clock, native_class


class QuickEvent:
    def __init__(self):
        self.event = threading.Event()

    def set(self):
        self.event.set()

    def is_set(self):
        return self.event.is_set()

    def wait(self, seconds):
        return self.event.wait(min(seconds, 0.001))


class InputTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.clock.time_ns = lambda: int(self.clock.now * 1e9)
        self.clock.monotonic_ns = self.clock.time_ns
        self.clock.sleep = self.sleep
        self.clock.spin = self.spin
        native, _ = native_class(self.clock)
        self.app = native.__new__(native)
        self.app.app = None
        self.app.journal = Mock()
        self.app.save = Mock()
        self.app.frame = self.frame
        self.app.key = self.key
        self.app.acknowledge = Mock()
        self.events = []
        self.value = 100
        self.direction = -1
        self.age = 0
        self.fixed_sequence = False
        self.observer_seen = threading.Event()
        self.frames_during_sequences = 0
        self.in_sequences = False
        original_sequences = self.app.sequences

        def sequences():
            self.events.append("sequences")
            self.in_sequences = True
            try:
                return original_sequences()
            finally:
                self.in_sequences = False

        self.app.sequences = sequences
        real_thread = threading.Thread
        seen = self.observer_seen

        class ObservedThread(real_thread):
            def start(self):
                super().start()
                if not seen.wait(1):
                    raise AssertionError("observer did not start")

        self.threading_patch = patch(
            "native_input.threading",
            SimpleNamespace(Event=QuickEvent, Thread=ObservedThread),
        )
        self.threading_patch.start()
        self.addCleanup(self.threading_patch.stop)
        self.time_patch = patch("native_input.time", self.clock)
        self.time_patch.start()
        self.addCleanup(self.time_patch.stop)

    def frame(self):
        if threading.current_thread().name == "input-freshness-observer":
            self.observer_seen.set()
            self.frames_during_sequences += self.in_sequences
        return {
            "snapshot": {
                "sequence": 1 if self.fixed_sequence else int(self.clock.now) + 1
            },
            "accepted_unix_ns": int((self.clock.now - self.age) * 1e9),
        }

    def spin(self):
        self.clock.now += 0.25
        time.sleep(0.002)

    def sleep(self, seconds):
        while seconds > 0:
            step = min(seconds, 1)
            self.clock.now += step
            seconds -= step
            time.sleep(0.002)

    def key(self, *keys, pressed=None):
        self.events.append(("key", keys, pressed))
        if pressed is not True:
            self.value += self.direction

    def measure(self):
        self.events.append("measure")
        return self.value

    def run_input(self, **kwargs):
        return exercise(self.app, "input-case", ("Up",), self.measure, -1, **kwargs)

    def assert_cleaned(self):
        self.assertTrue(self.app.save.call_args.args[1]["observer_joined"])

    def test_movement_is_observed_after_release_before_sequence_wait(self):
        record = self.run_input()
        release = self.events.index(("key", ("Up",), False))
        after = self.events.index("measure", release)
        self.assertLess(release, after)
        self.assertLess(after, self.events.index("sequences"))
        self.assertGreater(self.frames_during_sequences, 0)
        self.assertGreaterEqual(len({o["sequence"] for o in record["observations"]}), 3)
        self.assert_cleaned()

    def test_wrong_signed_movement_still_fails(self):
        self.direction = 1
        with self.assertRaisesRegex(AssertionError, "no signed movement"):
            self.run_input()
        self.assert_cleaned()

    def test_missing_movement_fails_at_original_five_second_deadline(self):
        self.direction = 0
        with self.assertRaises(TimeoutError):
            self.run_input()
        self.assertEqual(self.clock.now, 8)
        self.assertNotIn("sequences", self.events)
        self.assert_cleaned()

    def test_stale_publication_still_fails(self):
        self.age = 3
        with self.assertRaisesRegex(AssertionError, "starved fresh publication"):
            self.run_input()
        self.assert_cleaned()

    def test_missing_three_sequences_still_fails(self):
        self.fixed_sequence = True
        with self.assertRaises(TimeoutError):
            self.run_input()
        self.assertEqual(self.clock.now, 8)
        self.assert_cleaned()

    def test_main_sequence_observation_is_retained_when_watcher_misses_it(self):
        frame = self.app.frame

        def missed():
            result = frame()
            if threading.current_thread().name == "input-freshness-observer":
                if result["snapshot"]["sequence"] > 2:
                    result["snapshot"]["sequence"] = 2
                    result["accepted_unix_ns"] = 1_000_000_000
            return result

        self.app.frame = missed
        record = self.run_input(burst=64, expected_identity="process:36:123")
        self.assertIn(3, {item["sequence"] for item in record["observations"]})
        self.assert_cleaned()

    def test_watcher_errors_survive_merge_with_three_main_observations(self):
        frame = self.app.frame
        failed = False

        def errored():
            nonlocal failed
            result = frame()
            if (
                threading.current_thread().name == "input-freshness-observer"
                and not failed
            ):
                failed = True
                raise RuntimeError("watcher publication failure")
            return result

        self.app.frame = errored
        with self.assertRaisesRegex(AssertionError, "starved fresh publication"):
            self.run_input()
        observations = self.app.save.call_args.args[1]["observations"]
        self.assertIn({"error": "watcher publication failure"}, observations)
        self.assertIn(6, {item.get("sequence") for item in observations})
        self.assert_cleaned()

    def test_sequence_records_capture_age_at_read_time_and_keep_existing_fields(self):
        self.age = 1
        records = self.app.sequences()
        self.assertEqual([item["sequence"] for item in records], [1, 2, 3])
        self.assertEqual(
            [item["accepted_unix_ns"] for item in records],
            [-1_000_000_000, 0, 1_000_000_000],
        )
        self.assertEqual([item["age"] for item in records], [1, 1, 1])
        self.assertEqual(self.clock.now, 2)

    def test_sequence_count_option_remains_compatible(self):
        # Call the production method directly: the fixture's wrapper preserves
        # exercise's existing no-argument call but does not expose options.
        records = type(self.app).sequences(self.app, count=2, seconds=5)
        self.assertEqual(len(records), 2)
        self.assertEqual([item["sequence"] for item in records], [1, 2])
        self.assertEqual(self.clock.now, 1)

    def test_exact_burst_keeps_64_keys_and_expected_identity_acknowledgement(self):
        target = "process:36:123"
        record = self.run_input(burst=64, expected_identity=target)
        keys = [e for e in self.events if isinstance(e, tuple)]
        self.assertEqual(keys, [("key", ("Up",), None)] * 64)
        self.app.acknowledge.assert_called_once_with(target, 5)
        self.assertEqual(record["expected_identity"], target)
        self.assertEqual(record["key_count"], 64)
        self.assertEqual(record["after"], 36)
        self.assert_cleaned()

    def test_failed_exact_endpoint_acknowledgement_still_fails_and_cleans_up(self):
        self.app.acknowledge.side_effect = TimeoutError("wrong endpoint")
        with self.assertRaisesRegex(TimeoutError, "wrong endpoint"):
            self.run_input(burst=64, expected_identity="process:36:123")
        self.assertNotIn("sequences", self.events)
        self.assert_cleaned()

    def test_identity_observation_uses_one_deadline_and_matching_numeric_evidence(self):
        deadlines = []

        def observe(deadline):
            deadlines.append(deadline)
            if self.clock.now == 0:
                return 100, "process:100:123"
            if self.clock.now < 4:
                return None
            return 99, "process:99:456"

        record = self.run_input(observe=observe)
        self.assertEqual(deadlines, [5] + [8] * 5)
        self.assertEqual(
            (record["before"], record["before_identity"]), (100, "process:100:123")
        )
        self.assertEqual(
            (record["after"], record["after_identity"]), (99, "process:99:456")
        )
        self.assertNotIn("measure", self.events)

    def test_absent_selected_observation_is_bounded_failure_not_a_fabricated_pid(self):
        def observe(deadline):
            return (100, "process:100:123") if self.clock.now == 0 else None

        with self.assertRaises(TimeoutError):
            self.run_input(observe=observe)
        self.assertEqual(self.clock.now, 8)
        record = self.app.save.call_args.args[1]
        self.assertNotIn("after", record)
        self.assert_cleaned()

    def test_slow_selected_observation_cannot_extend_movement_deadline(self):
        deadlines = []

        def observe(deadline):
            deadlines.append(deadline)
            if self.clock.now == 0:
                return 100, "process:100:123"
            self.clock.now = deadline
            return 99, "process:99:456"

        with self.assertRaisesRegex(AssertionError, "after deadline"):
            self.run_input(observe=observe)
        self.assertEqual(deadlines, [5, 8])
        self.assertEqual(self.clock.now, 8)
        self.assert_cleaned()

    def test_real_replay_selection_callback_preserves_absence_identity_and_deadline(
        self,
    ):
        source = Path(__file__).with_name("native_replay.py")
        callback = next(
            node
            for node in ast.walk(ast.parse(source.read_text()))
            if isinstance(node, ast.FunctionDef) and node.name == "selected_pid"
        )
        context = {"app": self.app, "time": self.clock}
        exec(
            compile(ast.Module(body=[callback], type_ignores=[]), str(source), "exec"),
            context,
        )
        self.app.selected = Mock(side_effect=[None, ("process:42:987", object())])
        self.assertIsNone(context["selected_pid"](8))
        self.assertEqual(context["selected_pid"](8), (42, "process:42:987"))
        self.assertEqual(
            [call.args for call in self.app.selected.call_args_list], [(8,), (8,)]
        )

    def test_absent_baseline_selection_is_bounded_before_input(self):
        deadlines = []

        def absent(deadline):
            deadlines.append(deadline)
            return None

        with self.assertRaises(TimeoutError):
            self.run_input(observe=absent)
        self.assertEqual(self.clock.now, 5)
        self.assertTrue(deadlines)
        self.assertEqual(set(deadlines), {5})
        self.assertFalse(any(isinstance(e, tuple) for e in self.events))

    def test_replay_held_and_exact_burst_calls_use_identity_observation(self):
        source = Path(__file__).with_name("native_replay.py")
        tree = ast.parse(source.read_text())
        callback = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "selected_pid"
        )
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "exercise"
            and len(node.args) > 1
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in ("held-up-25hz", "exact-64-up")
        ]
        self.assertEqual(len(calls), 2)
        self.app.selected = Mock(return_value=("process:70:123", object()))
        observed_calls = []

        def observed(*args, **kwargs):
            observed_calls.append((args, kwargs, kwargs["observe"](8)))

        context = {
            "app": self.app,
            "exercise": observed,
            "rows": [
                {"identity": {"pid": pid, "start_time_ticks": 123}}
                for pid in range(1, 71)
            ],
            "identity": lambda row: f"process:{row['identity']['pid']}:123",
        }
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(
                        body=[callback] + [ast.Expr(value=call) for call in calls],
                        type_ignores=[],
                    )
                ),
                str(source),
                "exec",
            ),
            context,
        )
        by_name = {
            args[1]: (args, kwargs, result) for args, kwargs, result in observed_calls
        }
        self.assertEqual(by_name["held-up-25hz"][2], (70, "process:70:123"))
        self.assertEqual(by_name["exact-64-up"][1]["burst"], 64)
        self.assertEqual(
            by_name["exact-64-up"][1]["expected_identity"], "process:6:123"
        )
        self.assertEqual(by_name["exact-64-up"][2], (70, "process:70:123"))


if __name__ == "__main__":
    unittest.main()
