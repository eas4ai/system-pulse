"""Check the real frame reader with local files and no native session."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from host_accuracy import require
from test_native_exit import Clock, native_class


class NativeFrameTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "latest.json"
        self.frame = {
            "application_pid": 500,
            "accepted_unix_ns": 7_000_000_000,
            "render_revision": 4,
            "snapshot": {"sequence": 23},
        }
        self.path.write_text(json.dumps(self.frame))
        self.events = []
        self.after_read = lambda: None
        self.after_parse = lambda: None
        self.clock = Clock()
        self.clock.monotonic_ns = Mock(side_effect=self.monotonic_ns)
        self.clock.time_ns = Mock(side_effect=self.time_ns)
        native, _ = native_class(self.clock)
        self.native = native.__new__(native)
        self.native.app = SimpleNamespace(pid=500)
        self.native.interval_ms = 1000
        self.native.save = Mock()
        self.native.latest = Mock(wraps=self.path)
        self.native.latest.open.side_effect = self.open_frame
        self.native.latest.stat.side_effect = self.path_stat
        self.context = self.native.frame.__globals__
        self.context.update(
            os=SimpleNamespace(fstat=Mock(side_effect=self.opened_stat)),
            json=SimpleNamespace(loads=Mock(side_effect=self.parse)),
            require=self.validate,
        )
        self.handle = None
        self.contents_read = Mock(side_effect=self.read)

    def monotonic_ns(self):
        self.events.append("monotonic")
        return len(self.events) * 100

    def time_ns(self):
        self.events.append("wall-check")
        return 10_000_000_000

    @contextmanager
    def open_frame(self):
        self.events.append("open")
        with self.path.open() as self.handle:
            yield SimpleNamespace(read=self.contents_read, fileno=self.handle.fileno)
        self.events.append("close")

    def read(self):
        self.events.append("read")
        value = self.handle.read()
        self.after_read()
        return value

    def parse(self, value):
        self.events.append("parse")
        frame = json.loads(value)
        self.after_parse()
        return frame

    def opened_stat(self, descriptor):
        self.events.append("fstat")
        return os.fstat(descriptor)

    def path_stat(self):
        self.events.append("path-stat")
        return self.path.stat()

    def validate(self, condition, message):
        self.events.append("pid-check" if "PID" in message else "age-check")
        require(condition, message)

    def reject_stale(self):
        with self.assertRaisesRegex(AssertionError, "accepted frame stale"):
            self.native.frame()
        self.native.save.assert_called_once()
        name, artifact = self.native.save.call_args.args
        self.assertTrue(name.startswith("stale-frame-"))
        self.assertEqual(artifact["frame"], self.frame)
        self.assertEqual(artifact["checked_unix_ns"], 10_000_000_000)
        self.assertEqual(artifact["age_seconds"], 3)
        self.assertEqual(artifact["limit_seconds"], 2)
        return artifact

    def test_stale_retains_ordered_stages_and_exactly_one_read(self):
        artifact = self.reject_stale()
        self.assertIn("observation", artifact)
        observation = artifact["observation"]
        keys = (
            "read_started_monotonic_ns",
            "read_completed_monotonic_ns",
            "parse_completed_monotonic_ns",
            "age_checked_monotonic_ns",
        )
        stamps = [observation[key] for key in keys]
        self.assertTrue(all(a < b for a, b in zip(stamps, stamps[1:])))
        events = self.events
        for stamp, stage in zip(stamps, ("open", "parse", "fstat", "wall-check")):
            self.assertEqual(events[stamp // 100 - 1], "monotonic")
            self.assertLess(stamp // 100 - 1, events.index(stage))
        self.assertLess(events.index("read"), stamps[1] // 100 - 1)
        self.assertLess(events.index("parse"), stamps[2] // 100 - 1)
        self.assertLess(events.index("fstat"), events.index("path-stat"))
        self.assertLess(events.index("path-stat"), events.index("wall-check"))
        self.assertLess(events.index("wall-check"), events.index("pid-check"))
        self.assertLess(events.index("pid-check"), events.index("age-check"))
        expected = {"device": self.path.stat().st_dev, "inode": self.path.stat().st_ino}
        self.assertEqual(observation["opened_file"], expected)
        self.assertEqual(observation["pathname_before_check"], expected)
        self.assertEqual(observation["errors"], {})
        self.native.latest.open.assert_called_once_with()
        self.contents_read.assert_called_once_with()
        self.context["json"].loads.assert_called_once()
        self.native.latest.stat.assert_called_once_with()
        self.context["os"].fstat.assert_called_once()
        self.clock.time_ns.assert_called_once_with()
        self.assertTrue(self.handle.closed)

    def test_atomic_replacement_before_check_retains_opened_and_path_identities(self):
        for stage in ("read", "parse"):
            with self.subTest(stage=stage):
                self.setUp()
                original = self.path.stat()
                replacement = self.path.with_name("replacement.json")
                fresh = dict(self.frame, accepted_unix_ns=10_000_000_000)
                fresh["snapshot"] = {"sequence": 24}
                replacement.write_text(json.dumps(fresh))
                published = replacement.stat()

                def replace():
                    replacement.replace(self.path)
                    self.events.append("replace")

                setattr(self, f"after_{stage}", replace)
                artifact = self.reject_stale()
                self.assertIn("observation", artifact)
                observation = artifact["observation"]
                self.assertEqual(
                    observation["opened_file"],
                    {"device": original.st_dev, "inode": original.st_ino},
                )
                self.assertEqual(
                    observation["pathname_before_check"],
                    {"device": published.st_dev, "inode": published.st_ino},
                )
                self.assertNotEqual(original.st_ino, published.st_ino)
                self.assertLess(
                    self.events.index("replace"), self.events.index("path-stat")
                )
                self.assertLess(
                    self.events.index("path-stat"), self.events.index("wall-check")
                )
                self.assertEqual(json.loads(self.path.read_text()), fresh)
                self.contents_read.assert_called_once_with()
                self.native.latest.open.assert_called_once_with()

    def test_fresh_boundaries_future_and_stale_verdicts_are_unchanged(self):
        for interval in (250, 1000, 5000):
            limit_ns = interval * 2_000_000
            for age_ns in (-1, 0, limit_ns - 1, limit_ns, limit_ns + 1):
                with self.subTest(interval=interval, age_ns=age_ns):
                    self.native.interval_ms = interval
                    self.frame["accepted_unix_ns"] = 10_000_000_000 - age_ns
                    self.path.write_text(json.dumps(self.frame))
                    self.native.save.reset_mock()
                    if 0 <= age_ns <= limit_ns:
                        self.assertEqual(self.native.frame(), self.frame)
                        self.native.save.assert_not_called()
                    else:
                        with self.assertRaisesRegex(
                            AssertionError, "accepted frame stale"
                        ):
                            self.native.frame()
                        self.native.save.assert_called_once()
                        artifact = self.native.save.call_args.args[1]
                        self.assertEqual(artifact["age_seconds"], age_ns / 1e9)
                        self.assertEqual(artifact["limit_seconds"], interval / 500)

    def test_wrong_pid_keeps_priority_over_stale_and_metadata_errors(self):
        self.context["os"].fstat.side_effect = OSError("metadata unavailable")
        self.frame["application_pid"] = 501
        self.path.write_text(json.dumps(self.frame))
        with self.assertRaisesRegex(AssertionError, "wrong diagnostic PID/session"):
            self.native.frame()
        self.native.save.assert_not_called()

    def test_stat_errors_are_retained_without_changing_stale_verdict(self):
        self.context["os"].fstat.side_effect = OSError(
            "descriptor metadata unavailable"
        )
        self.native.latest.stat.side_effect = FileNotFoundError("path disappeared")
        artifact = self.reject_stale()
        self.assertIn("observation", artifact)
        observation = artifact["observation"]
        self.assertIsNone(observation["opened_file"])
        self.assertIsNone(observation["pathname_before_check"])
        self.assertEqual(
            observation["errors"],
            {
                "opened_file": "OSError: descriptor metadata unavailable",
                "pathname_before_check": "FileNotFoundError: path disappeared",
            },
        )

    def test_unavailable_timing_is_retained_and_stale_verdict_survives(self):
        self.clock.monotonic_ns.side_effect = OSError("clock unavailable")
        with self.assertRaises(Exception) as raised:
            self.native.frame()
        self.assertIsInstance(raised.exception, AssertionError)
        self.assertIn("accepted frame stale", str(raised.exception))
        artifact = self.native.save.call_args.args[1]
        observation = artifact["observation"]
        for stage in (
            "read_started",
            "read_completed",
            "parse_completed",
            "age_checked",
        ):
            key = f"{stage}_monotonic_ns"
            self.assertIsNone(observation[key])
            self.assertEqual(observation["errors"][key], "OSError: clock unavailable")
        self.assertEqual(
            self.native.save.call_args.args[0], "stale-frame-10000000000.json"
        )

    def test_fresh_frame_returns_unchanged_when_metadata_is_unavailable(self):
        self.frame["accepted_unix_ns"] = 10_000_000_000
        self.path.write_text(json.dumps(self.frame))
        self.clock.monotonic_ns.side_effect = OSError("clock unavailable")
        self.context["os"].fstat.side_effect = OSError(
            "descriptor metadata unavailable"
        )
        self.native.latest.stat.side_effect = FileNotFoundError("path disappeared")
        self.assertEqual(self.native.frame(), self.frame)
        self.native.save.assert_not_called()

    def test_real_open_read_and_parse_errors_propagate(self):
        for operation, error in (
            ("open", FileNotFoundError("missing frame")),
            ("read", OSError("read failed")),
            ("parse", json.JSONDecodeError("invalid JSON", "!", 0)),
        ):
            with self.subTest(operation=operation):
                self.setUp()
                if operation == "open":
                    self.native.latest.open.side_effect = error
                elif operation == "read":
                    self.contents_read.side_effect = error
                else:
                    self.path.write_text("!")
                with self.assertRaises(type(error)) as raised:
                    self.native.frame()
                if operation != "parse":
                    self.assertIs(raised.exception, error)
                self.native.save.assert_not_called()
                self.clock.time_ns.assert_not_called()
                if self.handle is not None:
                    self.assertTrue(self.handle.closed)


if __name__ == "__main__":
    unittest.main()
