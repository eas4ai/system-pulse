import copy
import unittest

from tabbed_contract import REQUIRED_CASES, check_replay, check_metric, clipped_visible, expected_metric


def frame(value=0.0, *, unit="Percent", total=None):
    integers = {"value": value} if total is None else {"used": value, "total": total}
    return {
        "rendered_at_collector_ms": 1000,
        "snapshot": {
            "capture_finished_ns": 1_000_000_000,
            "sensors": [{"id": "test/value", "unit": unit}],
            "readings": [{"sensor_id": "test/value", "value": value, "total": total,
                          "availability": "Available", "reason": None,
                          "observations": [{"source": "native gauge", "captured_ns": 1_000_000_000,
                                            "integers": integers, "decimals": {}}]}],
        },
    }


class TabbedContractTests(unittest.TestCase):
    def test_replay_rejects_missing_cases_devices_children_and_wrong_binary(self):
        valid = {"status": "PASS", "binary_sha256": "tested", "cases": sorted(REQUIRED_CASES),
                 "checks": ["description"] * 6, "devices": [{"id": "gpu:a", "screen": "gpu", "title": "GPU"}],
                 "expected_devices": [{"id": "gpu:a", "screen": "gpu", "title": "GPU"}], "disappeared_devices": [],
                 "children": [{"exit_code": 0}] * 3}
        check_replay(valid, "tested")
        lost = {"choice": valid["devices"][0], "frame": {"snapshot": {"monitors": []}}}
        removed = dict(valid, devices=[], disappeared_devices=[lost])
        check_replay(removed, "tested")
        lost["frame"]["snapshot"]["monitors"] = [{"id": "gpu:a"}]
        with self.assertRaises(AssertionError):
            check_replay(removed, "tested")
        for key, value in (("status", "FAIL"), ("binary_sha256", "different"),
                           ("cases", ["restart"] * 6), ("devices", []),
                           ("children", [{"exit_code": None}] * 3)):
            broken = dict(valid, **{key: value})
            with self.subTest(key=key), self.assertRaises(AssertionError):
                check_replay(broken, "tested")

    def test_zero_missing_and_stale_cannot_be_confused(self):
        sample = frame()
        self.assertEqual(expected_metric(sample, "test/value", 1000), "0.0 %")
        with self.assertRaises(AssertionError):
            check_metric(sample, "test/value", "Unavailable", 1000)
        unavailable = copy.deepcopy(sample)
        unavailable["snapshot"]["readings"][0].update(value=None, availability="Unavailable", reason="device gone")
        self.assertEqual(expected_metric(unavailable, "test/value", 1000), "Unavailable")
        with self.assertRaises(AssertionError):
            check_metric(unavailable, "test/value", "0.0 %", 1000)
        sample["rendered_at_collector_ms"] = 3001
        self.assertEqual(expected_metric(sample, "test/value", 1000), "0.0 % · stale")
        self.assertEqual(expected_metric(sample, "test/value", 2000), "0.0 %")
        with self.assertRaises(AssertionError):
            check_metric(sample, "test/value", "0.0 %", 1000)

    def test_capacity_prefix_and_raw_operands_are_independent(self):
        sample = frame(1024 ** 3, unit="Bytes", total=2 * 1024 ** 3)
        self.assertEqual(expected_metric(sample, "test/value", 1000), "1.0 / 2.0 GiB")
        for wrong in ("1.0 / 2.0 B", "1.0 / 2.0 GB", "50.0 %"):
            with self.assertRaises(AssertionError):
                check_metric(sample, "test/value", wrong, 1000)
        sample["snapshot"]["readings"][0]["value"] += 1
        with self.assertRaises(AssertionError):
            expected_metric(sample, "test/value", 1000)

    def test_clipping_intersects_screen_and_nested_viewports(self):
        ancestors = [{"id": "screen:processes", "bounds": [0, 100, 960, 500]},
                     {"id": "processes:rows-viewport", "bounds": [0, 150, 800, 300]}]
        window = [0, 0, 960, 640]
        self.assertTrue(clipped_visible([10, 160, 100, 20], window, ancestors))
        for hidden in ([10, 130, 100, 20], [790, 160, 100, 20], [10, 445, 100, 20]):
            self.assertFalse(clipped_visible(hidden, window, ancestors))
        ancestors[1]["bounds"] = None
        with self.assertRaises(AssertionError):
            clipped_visible([10, 160, 100, 20], window, ancestors)


if __name__ == "__main__":
    unittest.main()
