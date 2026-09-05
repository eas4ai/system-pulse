"""Adversarial inputs exist only in this verifier test module."""

import copy
import importlib.util
import unittest

spec = importlib.util.find_spec("host_accuracy")
host = None if spec is None else __import__("host_accuracy")


class IndependentVerifierTests(unittest.TestCase):
    def test_even_one_ulp_difference_is_not_exact(self):
        import math

        host.exact(1.0, 1.0, "equal control")
        with self.assertRaises(AssertionError):
            host.exact(math.nextafter(1.0, math.inf), 1.0, "one ulp corruption")

    def test_nonfinite_expected_operand_never_passes_exact_check(self):
        for actual, expected in (
            (1.0, float("inf")),
            (1.0, -float("inf")),
            (1.0, float("nan")),
            (float("inf"), 1.0),
        ):
            with self.assertRaises(AssertionError):
                host.exact(actual, expected, "nonfinite adversarial operand")

    def setUp(self):
        self.assertIsNotNone(host, "independent host verifier has not been implemented")

    def reading(
        self,
        suffix,
        integers=None,
        decimals=None,
        value=0,
        unit="Bytes",
        source="/proc/meminfo",
        total=None,
    ):
        return (
            {"id": "memory:host/" + suffix, "unit": unit, "source": source},
            {
                "sensor_id": "memory:host/" + suffix,
                "value": value,
                "total": total,
                "availability": "Available",
                "reason": None,
                "observations": [
                    {
                        "source": source,
                        "captured_ns": 2000000000,
                        "read_started_ns": None,
                        "integers": integers or {},
                        "decimals": decimals or {},
                    }
                ],
            },
        )

    def test_kibibytes_and_available(self):
        sensor, reading = self.reading(
            "used",
            {"MemTotal": 100, "MemAvailable": 25},
            value=75 * 1024,
            total=100 * 1024,
        )
        host.check_reading(sensor, reading)
        for wrong in (75 * 1000, 100 * 1024):
            bad = dict(reading, value=wrong)
            with self.assertRaises(AssertionError):
                host.check_reading(sensor, bad)

    def test_composition(self):
        sensor, reading = self.reading(
            "cache", {"Cached": 100, "SReclaimable": 20, "Shmem": 30}, value=90 * 1024
        )
        host.check_reading(sensor, reading)
        with self.assertRaises(AssertionError):
            host.check_reading(sensor, dict(reading, value=120 * 1024))

    def test_zero_swap(self):
        host.check_reading(
            *self.reading("swap", {"SwapTotal": 0, "SwapFree": 0}, total=0)
        )

    def test_temperature_conversion_and_negative(self):
        sensor, reading = self.reading(
            "temperature",
            decimals={"value": -2000},
            value=-2,
            unit="Celsius",
            source="/sys/class/hwmon/hwmon0/temp1_input",
        )
        host.check_reading(sensor, reading)
        with self.assertRaises(AssertionError):
            host.check_reading(sensor, dict(reading, value=-2000))

    def test_power_and_zero_clock(self):
        sensor, reading = self.reading(
            "power",
            decimals={"value": 12000000},
            value=12,
            unit="Watts",
            source="/sys/class/drm/card0/device/hwmon/hwmon0/power1_average",
        )
        host.check_reading(sensor, reading)
        with self.assertRaises(AssertionError):
            host.check_reading(sensor, dict(reading, value=12000))
        host.check_reading(
            *self.reading(
                "clock",
                decimals={"value": 0},
                value=0,
                unit="Hertz",
                source="/sys/class/hwmon/hwmon0/freq1_input",
            )
        )

    def test_statvfs_reserved_blocks(self):
        sensor, reading = self.reading(
            "capacity",
            {"blocks": 100, "free_blocks": 30, "fragment_size": 4096},
            value=70 * 4096,
            total=100 * 4096,
            source="statvfs(/)",
        )
        host.check_reading(sensor, reading)
        with self.assertRaises(AssertionError):
            host.check_reading(sensor, dict(reading, value=80 * 4096))

    def test_process_one_core_elapsed_and_rss(self):
        observations = [
            {"captured_ns": 1000000000, "integers": {"utime": 100, "stime": 20}},
            {"captured_ns": 3000000000, "integers": {"utime": 500, "stime": 20}},
        ]
        host.check_process_cpu(200, observations, 100)
        for wrong in (200 / 32, 400, 100):
            with self.assertRaises(AssertionError):
                host.check_process_cpu(wrong, observations, 100)
        stat = "42 (pulse ) probe) S " + " ".join(str(i) for i in range(4, 53))
        parsed = host.parse_process_stat(stat)
        self.assertEqual(parsed["name"], "pulse ) probe")
        self.assertEqual(parsed["start_ticks"], 22)
        self.assertEqual(parsed["rss_pages"], 24)

    def test_counter_bounds_and_entire_window(self):
        samples = [
            {"start": 10, "end": 12, "value": 100},
            {"start": 30, "end": 32, "value": 120},
        ]
        host.check_counter(110, (15, 25), samples)
        for value, window in [
            (99, (15, 25)),
            (121, (15, 25)),
            (110, (11, 25)),
            (110, (15, 31)),
        ]:
            with self.assertRaises(AssertionError):
                host.check_counter(value, window, samples)

    def test_every_process_missing_endpoint_fails_and_pid_reuse_never_joins(self):
        self.assertTrue(
            hasattr(host, "check_process_counter"),
            "identity-aware mandatory process bracket missing",
        )
        current = {"pid": 42, "start_time_ticks": 200}
        samples = [
            {"start": 10, "end": 12, "value": 100, "identity": current},
            {"start": 30, "end": 32, "value": 120, "identity": current},
        ]
        host.check_process_counter(110, (15, 25), current, samples)
        for identity in (current, {"pid": 1234, "start_time_ticks": 1}):
            owned = [dict(s, identity=identity) for s in samples]
            for incomplete in (owned[:1], owned[1:], []):
                with self.assertRaises(AssertionError):
                    host.check_process_counter(110, (15, 25), identity, incomplete)
        old = {"pid": 42, "start_time_ticks": 199}
        with self.assertRaises(AssertionError):
            host.check_process_counter(
                110, (15, 25), current, [dict(s, identity=old) for s in samples]
            )
        with self.assertRaises(AssertionError):
            host.check_process_counter(
                110, (15, 25), current, [dict(samples[0], identity=old), samples[1]]
            )

    def test_clock_interval_mapping_and_step(self):
        self.assertEqual(
            host.clock_intersection([(100, 102, 1000), (110, 112, 1010)]), (898, 900)
        )
        self.assertEqual(
            host.map_window((10, 20), (1000, 1002), (900, 904)), (106, 122)
        )
        with self.assertRaises(AssertionError):
            host.clock_intersection([(100, 102, 1000), (110, 112, 2010)])

    def test_gauge_bounds(self):
        host.check_gauge_domain("Percent", 0)
        host.check_gauge_domain("Celsius", -12)
        host.check_gauge_domain("Hertz", 0)
        for unit, value in [("Percent", 101), ("Bytes", -1), ("Watts", float("nan"))]:
            with self.assertRaises(AssertionError):
                host.check_gauge_domain(unit, value)

    def test_missing_accessible_capability(self):
        expected = {("/proc/stat:cpu0", "Percent"), ("/proc/stat:cpu1", "Percent")}
        actual = [{"source": s, "unit": u} for s, u in expected]
        host.check_capabilities(expected, actual)
        with self.assertRaises(AssertionError):
            host.check_capabilities(expected, actual[:1])

    def test_independent_rendered_number_and_unit(self):
        sample = {
            "value": 2048,
            "total": 4096,
            "unit": "Bytes",
            "availability": "Available",
            "reason": None,
        }
        self.assertEqual(host.format_sample(sample), "2.0 / 4.0 KiB")
        host.check_rendered(sample, "2.0 / 4.0 KiB")
        for corrupt_both_copies in ("2.0 / 4.0 kB", "3.0 / 4.0 KiB"):
            with self.assertRaises(AssertionError):
                host.check_rendered(sample, corrupt_both_copies)

    def test_visible_bounds_reject_toolbar_occlusion_and_nested_clipping(self):
        contract = __import__("native_contract")
        self.assertTrue(
            hasattr(contract, "contained"), "clipped viewport visibility check missing"
        )
        window = [0, 0, 1440, 1000]
        workspace = [8, 250, 1424, 742]
        self.assertTrue(contract.contained([38, 284, 1300, 26], [window, workspace]))
        self.assertFalse(contract.contained([38, 84, 1300, 26], [window, workspace]))
        self.assertFalse(
            contract.contained(
                [38, 284, 1300, 26], [window, workspace, [8, 300, 1424, 400]]
            )
        )
        self.assertFalse(contract.contained([38, 284, 1500, 26], [window, workspace]))

    def test_diagnostic_and_native_copies_cannot_hide_corruption(self):
        spec = importlib.util.find_spec("native_contract")
        self.assertIsNotNone(spec, "independent native contract missing")
        contract = __import__("native_contract")
        sensor, reading = self.reading("total", {"MemTotal": 2}, value=2048)
        sensor.update(monitor_id="memory:host", title="Total")
        entry = {
            "monitor_id": "memory:host",
            "sensor_id": sensor["id"],
            "element_id": "memory:host:value:" + sensor["id"],
            "process_identity": None,
            "label": "Memory · Total · 2.0 KiB",
            "sample": {
                "value": 2048,
                "total": None,
                "text": "2.0",
                "unit": "KiB",
                "status": "current",
                "reason": None,
                "at_ms": 2000,
            },
        }
        frame = {
            "rendered_at_collector_ms": 2000,
            "snapshot": {
                "sensors": [sensor],
                "readings": [reading],
                "monitors": [{"id": "memory:host", "title": "Memory"}],
                "capture_finished_ns": 2000000000,
            },
        }
        self.assertEqual(contract.expected_label(frame, entry), entry["label"])
        for key, value in (("text", "3.0"), ("unit", "kB"), ("value", 3072)):
            broken = copy.deepcopy(entry)
            broken["sample"][key] = value
            broken["label"] = (
                "Memory · Total · "
                + broken["sample"]["text"]
                + " "
                + broken["sample"]["unit"]
            )
            with self.assertRaises(AssertionError):
                contract.expected_label(frame, broken)

    def test_connection_endian_state_and_ownership(self):
        addresses = {"eth0": ["127.0.0.1"], "eth1": ["10.0.0.1"]}
        rows = [
            {"local_address": "0100007F", "state": "01"},
            {"local_address": "00000000", "state": "01"},
            {"local_address": "0100000A", "state": "0A"},
        ]
        self.assertEqual(
            host.connection_counts(addresses, rows, [], "little"),
            {"eth0": 1, "eth1": 0},
        )
        for changed in (
            [dict(rows[0], state="0A")],
            [dict(rows[0], local_address="0100000A")],
        ):
            with self.assertRaises(AssertionError):
                host.check_connection_counts(
                    {"eth0": 1, "eth1": 0}, addresses, changed, [], "little"
                )
        addresses["eth1"].append("127.0.0.1")
        with self.assertRaises(AssertionError):
            host.check_connection_counts(
                {"eth0": 1, "eth1": 0}, addresses, rows, [], "little"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
