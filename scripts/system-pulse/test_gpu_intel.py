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


def physical_fixture(driver="xe"):
    from gpu_intel_sources import Sysfs, sysfs_fields
    from gpu_intel_capture import independent_inventory, normalize_observer

    rawfs = dict(
        files={},
        directories={
            "/sys/class/drm": dict(names=["card0", "card1"]),
            "/sys/bus/event_source/devices": dict(names=[]),
        },
        resolved={},
    )
    for index in (0, 1):
        alias = "/sys/class/drm/card" + str(index)
        physical = "/sys/devices/pci0000:00/0000:0" + str(index + 1) + ":00.0"
        rawfs["directories"][physical] = dict(
            names=["device", "driver", "vendor", "hwmon"]
        )
        rawfs["directories"][physical + "/hwmon"] = dict(names=[])
        for path, text in [
            (physical + "/vendor", "0x8086"),
            (physical + "/device", "0x1234"),
            (alias + "/dev", "226:" + str(index)),
        ]:
            rawfs["files"][path] = dict(data_hex=text.encode().hex(), start=1, end=2)
        rawfs["resolved"][alias + "/device"] = physical
        rawfs["resolved"][physical + "/driver"] = "/sys/bus/pci/drivers/" + driver
    fs = Sysfs(rawfs)
    devices = discover(Path("/"), fs)
    for device in devices:
        device["sysfs_fields"], device["source_errors"] = sysfs_fields(device, fs)
        device.update(
            perf_fields=[],
            integrated=False,
            drm=dict(
                memory=dict(raw_hex=regions(driver).hex(), start=40, end=41),
                engines=dict(error="no test engine source"),
            ),
        )
    clock = dict(monotonic_before_ns=0, monotonic_after_ns=0, unix_ns=0)
    raw = dict(
        schema=1,
        mode="native",
        root="/",
        clock_anchor=clock,
        devices=devices,
        sysfs=rawfs,
        perf=[],
        pid=100,
    )
    inv = independent_inventory(raw, devices[0]["pci"])
    first = normalize_observer(raw, inv)
    later = copy.deepcopy(raw)
    for d in later["devices"]:
        d["drm"]["memory"].update(start=60, end=61)
    second = normalize_observer(later, inv)
    mid = inv["device"]["monitor_id"]
    sensors = []
    readings = []
    region = decode_regions(driver, regions(driver))[0]
    for f in inv["fields"]:
        sensors.append(
            dict(
                id=f["sensor_id"],
                monitor_id=mid,
                title=f["sensor_id"],
                **{k: f[k] for k in ("source", "scope", "unit", "kind")},
            )
        )
        r = dict(
            sensor_id=f["sensor_id"],
            reason=None,
            total=None,
            value=None,
            availability="Unavailable",
            observations=[],
        )
        if f.get("limitation"):
            r["reason"] = "Independent source is absent"
        else:
            metric = f["memory_metric"]
            r.update(
                availability="Available",
                value=float(
                    region["total_bytes"]
                    if metric == "total"
                    else region["count_bytes"]
                ),
                total=None
                if metric == "total"
                else float(
                    region["cpu_visible_total_bytes"]
                    if metric == "cpu-visible"
                    else region["total_bytes"]
                ),
                observations=[
                    dict(
                        source=f["source"],
                        integers=region,
                        read_started_ns=50,
                        captured_ns=51,
                    )
                ],
            )
        readings.append(r)
    snapshot = dict(
        sequence=1,
        clock_anchor=clock,
        monitors=[
            dict(
                id=mid,
                title="Intel GPU",
                kind="Gpu",
                summary_sensor_id=inv["fields"][0]["sensor_id"],
            )
        ],
        sensors=sensors,
        readings=readings,
    )
    snapshot["monitors"] = [
        dict(
            id=d["monitor_id"],
            kind="Gpu",
            title="Intel GPU",
            summary_sensor_id=inv["fields"][0]["sensor_id"],
        )
        for d in devices
    ]
    return raw, inv, [first, second], snapshot


class IntelTests(unittest.TestCase):
    def test_complete_physical_discovery_rejects_missing_duplicate_and_unstable_ids(
        self,
    ):
        from gpu_intel_capture import independent_inventory, normalize_observer
        from gpu_samples import verify_series

        policy = dict(
            warmup_samples=0, max_query_ns=10, max_gap_ns=100, rounding_ulps=4
        )
        raw, inventory, observer, snapshot = physical_fixture()
        verify_series([snapshot], inventory, observer, policy)
        reordered = copy.deepcopy(snapshot)
        reordered["monitors"].reverse()
        reordered["monitors"].append(dict(id="amdgpu:other", kind="Gpu"))
        verify_series([reordered], inventory, observer, policy)
        for label, monitors in (
            ("missing", snapshot["monitors"][:1]),
            ("duplicate", snapshot["monitors"] + [snapshot["monitors"][1]]),
            (
                "unstable",
                [
                    snapshot["monitors"][0],
                    dict(snapshot["monitors"][1], id="intel-pci:changed"),
                ],
            ),
        ):
            with self.subTest(label=label), self.assertRaises(AssertionError):
                verify_series(
                    [dict(snapshot, monitors=monitors)], inventory, observer, policy
                )
        self.assertEqual(len(inventory["discovery"]), 2)
        aliased = copy.deepcopy(raw)
        fs = aliased["sysfs"]
        alias = "/sys/class/drm/renderD128"
        fs["directories"]["/sys/class/drm"]["names"].insert(0, "renderD128")
        fs["resolved"][alias + "/device"] = raw["devices"][0]["physical_path"]
        fs["files"][alias + "/dev"] = dict(data_hex=b"226:128".hex(), start=1, end=2)
        aliased["devices"][0]["aliases"].append(dict(path=alias, dev="226:128"))
        aliased["devices"].reverse()
        replay = independent_inventory(aliased, inventory["device"]["pci"])
        self.assertEqual(replay["discovery"], inventory["discovery"])
        self.assertEqual(
            normalize_observer(aliased, inventory)["discovery"], inventory["discovery"]
        )

    def test_every_memory_operand_is_compared_through_complete_series(self):
        from gpu_samples import verify_series
        from gpu_intel_arithmetic import calculate

        clock = dict(monotonic_before_ns=0, monotonic_after_ns=0, unix_ns=0)
        for driver in ("i915", "xe"):
            raw = decode_regions(driver, regions(driver))[0]
            fields = [
                dict(
                    sensor_id="gpu/" + metric,
                    source="memory region 3",
                    scope="device-local",
                    unit="Bytes",
                    kind="Counter" if metric == "total" else "Capacity",
                    formula="intel-memory",
                    driver=driver,
                    region_class=1,
                    region_instance=3,
                    memory_metric=metric,
                    precision=0,
                )
                for metric in ("allocation", "total", "cpu-visible")
            ]
            sensors = [
                dict(
                    id=f["sensor_id"],
                    monitor_id="gpu",
                    title=f["memory_metric"],
                    **{k: f[k] for k in ("source", "scope", "unit", "kind")},
                )
                for f in fields
            ]
            readings = []
            for field in fields:
                reading = dict(
                    sensor_id=field["sensor_id"],
                    availability="Available",
                    reason=None,
                    observations=[
                        dict(
                            source=field["source"],
                            read_started_ns=50,
                            captured_ns=51,
                            integers=copy.deepcopy(raw),
                        )
                    ],
                )
                value, total, _, _ = calculate(field, reading)
                reading.update(
                    value=float(value), total=None if total is None else float(total)
                )
                readings.append(reading)
            snapshots = [
                dict(
                    sequence=n,
                    clock_anchor=clock,
                    monitors=[
                        dict(id="gpu", kind="Gpu", summary_sensor_id="gpu/allocation")
                    ],
                    sensors=sensors,
                    readings=copy.deepcopy(readings),
                )
                for n in range(1, 5)
            ]
            inventory = dict(
                hardware_class="intel-discrete",
                device=dict(monitor_id="gpu"),
                discovery=[dict(monitor_id="gpu")],
                fields=fields,
            )
            observer = [
                dict(
                    clock_anchor=clock,
                    discovery=inventory["discovery"],
                    samples=[
                        dict(
                            source=f["source"],
                            sensor_id=f["sensor_id"],
                            start=t,
                            end=t + 1,
                            values=copy.deepcopy(raw),
                        )
                        for f in fields
                        for t in (40, 60)
                    ],
                )
            ]
            policy = dict(
                warmup_samples=0, max_query_ns=10, max_gap_ns=100, rounding_ulps=4
            )
            self.assertEqual(
                verify_series(snapshots, inventory, observer, policy),
                dict.fromkeys([f["sensor_id"] for f in fields], 4),
            )
            for metric, key, value in (
                ("allocation", "total_bytes", 32768),
                ("allocation", "cpu_visible_total_bytes", 12288),
                ("cpu-visible", "cpu_visible_total_bytes", 12288),
                ("cpu-visible", "total_bytes", 32768),
                ("total", "count_bytes", 8192),
                ("allocation", "count_bytes", 8192),
            ):
                changed = copy.deepcopy(snapshots)
                index = next(
                    i for i, f in enumerate(fields) if f["memory_metric"] == metric
                )
                for snapshot in changed:
                    reading = snapshot["readings"][index]
                    reading["observations"][0]["integers"][key] = value
                    expected, total, _, _ = calculate(fields[index], reading)
                    reading.update(
                        value=float(expected),
                        total=None if total is None else float(total),
                    )
                with (
                    self.subTest(driver=driver, metric=metric, key=key),
                    self.assertRaises(AssertionError),
                ):
                    verify_series(changed, inventory, observer, policy)

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
