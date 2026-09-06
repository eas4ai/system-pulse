import copy
import struct
import tempfile
from pathlib import Path
import unittest

try:
    from gpu_intel_capture import (
        decode_regions,
        decode_engines,
        parse_perf,
        query_buffer,
        discover,
    )
    from gpu_intel_arithmetic import calculate, delta_bracket
except ImportError:
    decode_regions = decode_engines = parse_perf = query_buffer = discover = (
        calculate
    ) = delta_bracket = None


def regions(driver, local=True):
    header = 16 if driver == "i915" else 8
    data = bytearray(header + 88)
    struct.pack_into("=I", data, 0, 1)
    struct.pack_into(
        "=HHIQQQQ",
        data,
        header,
        int(local),
        3,
        0 if driver == "i915" else 4096,
        16384,
        4096,
        8192,
        4096,
    )
    return bytes(data)


class IntelTests(unittest.TestCase):
    def test_drm_original_buffers_sizes_reserved_and_subset_bounds(self):
        self.assertIsNotNone(decode_regions, "Intel independent DRM decoder missing")
        self.assertEqual(decode_regions("xe", regions("xe"))[0]["count_bytes"], 4096)
        self.assertEqual(
            decode_regions("i915", regions("i915"))[0]["total_bytes"], 16384
        )
        for driver in ("xe", "i915"):
            for data in (
                regions(driver)[:-1],
                regions(driver) + b"\0",
                b"",
                b"\xff" * 100,
            ):
                with (
                    self.subTest(driver=driver, data=data),
                    self.assertRaises(AssertionError),
                ):
                    decode_regions(driver, data)
        data = bytearray(regions("xe"))
        struct.pack_into("=Q", data, 8 + 16, 12288)
        struct.pack_into("=Q", data, 8 + 32, 0)
        with self.assertRaises(AssertionError):
            decode_regions("xe", data)

    def test_query_two_calls_reject_status_size_changes_and_allocations(self):
        self.assertIsNotNone(query_buffer, "Intel native query boundary missing")
        self.assertEqual(
            query_buffer(
                lambda b: 4 if b is None else (b.__setitem__(slice(None), b"abcd") or 4)
            ),
            b"abcd",
        )
        for length in (-13, 0, 1024 * 1024 + 1):
            with self.assertRaises(AssertionError):
                query_buffer(lambda b: length)
        with self.assertRaises(AssertionError):
            query_buffer(lambda b: 4 if b is None else 3)

    def test_perf_original_layout_and_scheduling(self):
        self.assertIsNotNone(parse_perf, "Intel independent perf decoder missing")
        raw = struct.pack("=5Q", 2, 100, 100, 75, 100)
        self.assertEqual(parse_perf(raw, 2)["active"], 75)
        for value, count in (
            (raw, 1),
            (raw[:-1], 2),
            (struct.pack("=5Q", 2, 100, 101, 75, 100), 2),
        ):
            with self.assertRaises(AssertionError):
                parse_perf(value, count)

    def test_no_intel_hardware_does_not_become_empty_valid_inventory(self):
        self.assertIsNotNone(discover, "Intel physical discovery missing")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "sys/class/drm").mkdir(parents=True)
            with self.assertRaises(AssertionError):
                discover(Path(tmp))

    def test_perf_delta_origins_cancel_but_wrong_native_activity_fails(self):
        self.assertIsNotNone(
            delta_bracket, "Intel independent interval bracket missing"
        )
        samples = [
            dict(start=t, end=t + 1, value=v)
            for t, v in [(8, 1000), (12, 1010), (18, 1050), (22, 1060)]
        ]
        policy = dict(max_query_ns=10, max_gap_ns=10)
        delta_bracket(50, (10, 11), (20, 21), samples, policy)
        with self.assertRaises(AssertionError):
            delta_bracket(70, (10, 11), (20, 21), samples, policy)

    def test_irregular_perf_and_explicit_memory_scope(self):
        self.assertIsNotNone(calculate, "Intel arithmetic missing")
        a = dict(
            captured_ns=1_000_000_000,
            integers=dict(
                active=100,
                total=0,
                enabled_ns=100,
                running_ns=100,
                ticks=0,
                capacity=1,
                config_active=0,
                config_total=0,
                pmu_type=17,
                cpu=0,
                energy_denominator=0,
            ),
        )
        b = copy.deepcopy(a)
        b["captured_ns"] = 2_500_000_000
        b["integers"].update(
            active=750_000_100, enabled_ns=1_500_000_100, running_ns=1_500_000_100
        )
        field = dict(
            formula="intel-perf",
            ticks=0,
            capacity=1,
            config_active=0,
            config_total=0,
            pmu_type=17,
            cpu=0,
            energy_denominator=0,
        )
        self.assertEqual(calculate(field, dict(observations=[a, b]))[0], 50.0)
        for key, value in [
            ("capacity", 2),
            ("running_ns", 1),
            ("config_active", 1),
            ("energy_denominator", 1),
        ]:
            bad = copy.deepcopy(b)
            bad["integers"][key] = value
            with self.assertRaises(AssertionError):
                calculate(field, dict(observations=[a, bad]))

    def test_intel_sysfs_inventory_distinguishes_actual_requested_and_package_scope(
        self,
    ):
        import gpu_intel_capture

        self.assertTrue(
            hasattr(gpu_intel_capture, "capture_inventory"),
            "Intel source inventory missing",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            physical = root / "sys/devices/pci0000:00/0000:00:02.0"
            physical.mkdir(parents=True)
            driver = root / "sys/bus/pci/drivers/i915"
            driver.mkdir(parents=True)
            (physical / "driver").symlink_to(driver)
            (physical / "vendor").write_text("0x8086")
            (physical / "device").write_text("0x1234")
            card = root / "sys/class/drm/card7"
            (card / "gt/gt0").mkdir(parents=True)
            (card / "device").symlink_to(physical)
            (card / "dev").write_text("226:0")
            (card / "gt/gt0/rps_act_freq_mhz").write_text("300")
            (card / "gt/gt0/rps_cur_freq_mhz").write_text("600")
            hw = physical / "hwmon/hwmon4"
            hw.mkdir(parents=True)
            (hw / "name").write_text("i915")
            (hw / "temp1_input").write_text("42000")
            raw = gpu_intel_capture.capture_inventory(root)
            self.assertEqual(raw["mode"], "development")
            fields = raw["devices"][0]["sysfs_fields"]
            self.assertEqual(len(fields), 3)
            self.assertEqual(
                {f["scope"] for f in fields if f["unit"] == "Hertz"},
                {"GT gt0; actual clock", "GT gt0; requested clock"},
            )
            self.assertIn(
                "Package", next(f["scope"] for f in fields if f["unit"] == "Celsius")
            )

    def test_rapl_requires_unique_integrated_association_and_exact_units(self):
        import gpu_intel_sources

        self.assertTrue(
            hasattr(gpu_intel_sources, "rapl_perf"),
            "independent RAPL inventory missing",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pmu = root / "sys/bus/event_source/devices/power"
            (pmu / "events").mkdir(parents=True)
            (pmu / "format").mkdir()
            values = {
                "type": "19",
                "cpumask": "0",
                "format/event": "config:0-7",
                "events/energy-gpu": "event=0x04",
                "events/energy-gpu.unit": "Joules",
                "events/energy-gpu.scale": str(1 / 2**32),
            }
            for path, value in values.items():
                (pmu / path).write_text(value)
            topology = root / "sys/devices/system/cpu/cpu0/topology"
            topology.mkdir(parents=True)
            for name in ("physical_package_id", "die_id"):
                (topology / name).write_text("0")
            device = dict(pci="0000:00:02.0", monitor_id="intel-pci:0000:00:02.0")
            with self.assertRaises(AssertionError):
                gpu_intel_sources.rapl_perf(
                    device, False, gpu_intel_sources.Sysfs(), root
                )
            field = gpu_intel_sources.rapl_perf(
                device, True, gpu_intel_sources.Sysfs(), root
            )
            self.assertEqual(field["energy_denominator"], 2**32)
            (pmu / "events/energy-gpu.unit").write_text("Watts")
            with self.assertRaises(AssertionError):
                gpu_intel_sources.rapl_perf(
                    device, True, gpu_intel_sources.Sysfs(), root
                )


if __name__ == "__main__":
    unittest.main()
