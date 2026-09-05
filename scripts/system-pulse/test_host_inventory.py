"""Synthetic dictionaries are verifier regressions only, never application input."""

import copy
import types
import unittest
import host_capture


def capture():
    fields = host_capture.CPU_FIELDS

    def obs(source, n, values):
        return dict(
            source=source,
            read_started_ns=n,
            captured_ns=n,
            integers=values,
            decimals={},
        )

    def reading(sid, value, observations):
        return dict(
            sensor_id=sid,
            value=value,
            total=None,
            observations=observations,
            availability="Available" if value is not None else "WarmingUp",
            reason=None if value is not None else "first sample",
        )

    mem = reading(
        "memory:host/total", 102400, [obs("/proc/meminfo", 20, dict(MemTotal=100))]
    )
    cpu = reading(
        "cpu:host/usage",
        75.0,
        [obs("/proc/stat:cpu", n, dict.fromkeys(fields, n)) for n in (10, 20)],
    )
    row = dict(identity=dict(pid=42, start_time_ticks=1))
    for key, suffix in [
        ("cpu_percent", "cpu"),
        ("memory_bytes", "memory"),
        ("read_bytes_per_second", "read"),
        ("write_bytes_per_second", "write"),
    ]:
        row[key] = reading("process:42:1/" + suffix, None, [])
    row["threads"] = reading(
        "process:42:1/threads", 1, [obs("/proc/42/stat", 20, dict(value=1))]
    )
    query = dict(read_started_ns=1, captured_ns=2, availability="Available")
    net = dict(
        interface_addresses=dict(query=query, interfaces={}),
        tcp_v4=dict(
            query=query, rows=[], address_family="Ipv4", word_byte_order="LittleEndian"
        ),
        tcp_v6=dict(
            query=query, rows=[], address_family="Ipv6", word_byte_order="LittleEndian"
        ),
    )
    base = dict(
        capture_started_ns=0,
        capture_finished_ns=25,
        clock_anchor=dict(monotonic_before_ns=0, monotonic_after_ns=0, unix_ns=100),
        monitors=[
            dict(id="cpu:host", kind="Cpu"),
            dict(id="memory:host", kind="Memory"),
        ],
        sensors=[
            dict(
                id="memory:host/total",
                monitor_id="memory:host",
                source="/proc/meminfo",
                unit="Bytes",
            ),
            dict(
                id="cpu:host/usage",
                monitor_id="cpu:host",
                source="/proc/stat:cpu",
                unit="Percent",
            ),
        ],
        readings=[mem, cpu],
        processes=[row],
        network_attribution=net,
    )
    samples = []
    for start, end, value in [(0, 1, 0), (30, 31, 30)]:
        samples.append(
            dict(
                sources={
                    "/proc/stat": dict(
                        start=start,
                        end=end,
                        errno=None,
                        value={"cpu": dict.fromkeys(fields, value)},
                    ),
                    "/proc/meminfo": dict(
                        start=start, end=end, errno=None, value=dict(MemTotal=100)
                    ),
                },
                processes={},
            )
        )
    observer = types.SimpleNamespace(
        failure=None,
        anchors=[(0, 0, 100)],
        capabilities=[
            dict(
                id="memory:host/total",
                monitor_id="memory:host",
                source="/proc/meminfo",
                unit="Bytes",
                probe=dict(errno=None, value=dict(MemTotal=100)),
            )
        ],
        errors=[],
        samples=samples,
        disks=set(),
    )
    snapshots = [dict(copy.deepcopy(base), sequence=n) for n in (1, 2, 3)]
    observer.capabilities.append(
        dict(
            id="cpu:host/usage",
            source="/proc/stat:cpu",
            unit="Percent",
            probe=dict(errno=None, value=1),
        )
    )
    return observer, snapshots


class IndependentInventoryTests(unittest.TestCase):
    def test_monitor_only_extra_kind_and_sensor_attribution_fail(self):
        for mutation in ("extra", "kind", "attribution", "raw_source"):
            observer, snapshots = capture()
            for snapshot in snapshots:
                if mutation == "extra":
                    snapshot["monitors"].append(
                        dict(
                            id="amdgpu:invented",
                            kind="Gpu",
                            summary_sensor="memory:host/total",
                        )
                    )
                elif mutation == "kind":
                    snapshot["monitors"][0]["kind"] = "Gpu"
                elif mutation == "attribution":
                    snapshot["sensors"][0]["monitor_id"] = "cpu:host"
                else:
                    snapshot["readings"][1]["observations"][0]["source"] = (
                        "/proc/stat:cpu999"
                    )
            with self.assertRaises(AssertionError):
                host_capture.verify_capture(observer, snapshots, None)

    def test_changed_final_inventory_fails_with_discovery_evidence(self):
        observer, snapshots = capture()
        observer.final_capabilities = copy.deepcopy(observer.capabilities)
        self.assertEqual(
            host_capture.verify_capture(observer, snapshots, None)["inventory_scope"],
            "initial and final independent inventories",
        )
        observer.final_capabilities.pop()
        with self.assertRaisesRegex(AssertionError, "inventory changed"):
            host_capture.verify_capture(observer, snapshots, None)

    def test_control(self):
        observer, snapshots = capture()
        self.assertEqual(
            host_capture.verify_capture(observer, snapshots, None)["status"], "PASS"
        )

    def test_wrong_independent_ram_total_rejected_even_if_raw_and_reading_agree(self):
        observer, snapshots = capture()
        for snapshot in snapshots:
            snapshot["readings"][0]["observations"][0]["integers"]["MemTotal"] = 200
            snapshot["readings"][0]["value"] = 204800
        with self.assertRaises(AssertionError):
            host_capture.verify_capture(observer, snapshots, None)

    def test_unobserved_gpu_rejected(self):
        observer, snapshots = capture()
        for snapshot in snapshots:
            snapshot["monitors"].append(dict(id="amdgpu:invented", kind="Gpu"))
            snapshot["sensors"].append(
                dict(
                    id="amdgpu:invented/usage",
                    monitor_id="amdgpu:invented",
                    source="/sys/class/drm/card999/device/gpu_busy_percent",
                    unit="Percent",
                )
            )
            snapshot["readings"].append(
                dict(
                    sensor_id="amdgpu:invented/usage",
                    value=10.0,
                    total=None,
                    availability="Available",
                    reason=None,
                    observations=[
                        dict(
                            source="/sys/class/drm/card999/device/gpu_busy_percent",
                            captured_ns=20,
                            read_started_ns=19,
                            integers={},
                            decimals={"value": 10.0},
                        )
                    ],
                )
            )
        with self.assertRaises(AssertionError):
            host_capture.verify_capture(observer, snapshots, None)

    def test_extra_cpu_and_duplicate_ids_rejected(self):
        for duplicate in (False, True):
            observer, snapshots = capture()
            for snapshot in snapshots:
                sensor = copy.deepcopy(snapshot["sensors"][1])
                reading = copy.deepcopy(snapshot["readings"][1])
                if not duplicate:
                    sensor["id"] = reading["sensor_id"] = "cpu:host/core-999-usage"
                snapshot["sensors"].append(sensor)
                snapshot["readings"].append(reading)
            with self.assertRaises(AssertionError):
                host_capture.verify_capture(observer, snapshots, None)

    def test_stable_total_missing_changed_and_wrong_device_fail(self):
        for mutation in ("before", "after", "changed", "source"):
            observer, snapshots = capture()
            samples = observer.samples
            if mutation == "before":
                samples[0]["sources"].pop("/proc/meminfo")
            elif mutation == "after":
                samples[1]["sources"].pop("/proc/meminfo")
            elif mutation == "changed":
                samples[1]["sources"]["/proc/meminfo"]["value"]["MemTotal"] = 101
            else:
                for snapshot in snapshots:
                    snapshot["readings"][0]["observations"][0]["source"] = (
                        "/proc/other/meminfo"
                    )
            with self.assertRaises(AssertionError):
                host_capture.verify_capture(observer, snapshots, None)

    def test_swap_vram_and_volume_totals(self):
        for kind in ("swap", "vram", "volume"):
            observer, snapshots = capture()
            sid, mid, source, integers, value, total = {
                "swap": (
                    "memory:host/swap",
                    "memory:host",
                    "/proc/meminfo",
                    {"SwapTotal": 0, "SwapFree": 0},
                    0,
                    0,
                ),
                "vram": (
                    "amdgpu:actual/vram",
                    "amdgpu:actual",
                    "/sys/class/drm/card0/device/mem_info_vram_used; /sys/class/drm/card0/device/mem_info_vram_total",
                    {"used": 5, "total": 100},
                    5,
                    100,
                ),
                "volume": (
                    "volume:actual/capacity",
                    "volume:actual",
                    "statvfs(/actual)",
                    {"blocks": 100, "free_blocks": 20, "fragment_size": 4096},
                    80 * 4096,
                    100 * 4096,
                ),
            }[kind]
            observer.capabilities.append(
                dict(
                    id=sid, source=source, unit="Bytes", probe=dict(errno=None, value=1)
                )
            )
            for sample in observer.samples:
                if kind == "swap":
                    sample["sources"][source]["value"]["SwapTotal"] = 0
                else:
                    path = source.split("; ")[-1]
                    sample["sources"][path] = dict(
                        start=sample["sources"]["/proc/meminfo"]["start"],
                        end=sample["sources"]["/proc/meminfo"]["end"],
                        errno=None,
                        value=100 if kind == "vram" else [4096, 4096, 100, 20, 10],
                    )
            for snapshot in snapshots:
                if kind != "swap":
                    snapshot["monitors"].append(
                        dict(id=mid, kind="Gpu" if kind == "vram" else "Volume")
                    )
                snapshot["sensors"].append(
                    dict(id=sid, monitor_id=mid, source=source, unit="Bytes")
                )
                snapshot["readings"].append(
                    dict(
                        sensor_id=sid,
                        value=value,
                        total=total,
                        availability="Available",
                        reason=None,
                        observations=[
                            dict(
                                source=source,
                                captured_ns=20,
                                read_started_ns=19,
                                integers=copy.deepcopy(integers),
                                decimals={},
                            )
                        ],
                    )
                )
            self.assertEqual(
                host_capture.verify_capture(observer, snapshots, None)["status"], "PASS"
            )
            for snapshot in snapshots:
                r = snapshot["readings"][-1]
                key = {"swap": "SwapTotal", "vram": "total", "volume": "blocks"}[kind]
                r["observations"][0]["integers"][key] += 1
                factor = {"swap": 1024, "vram": 1, "volume": 4096}[kind]
                r["total"] += factor
                if kind != "vram":
                    r["value"] += factor
            with self.assertRaises(AssertionError):
                host_capture.verify_capture(observer, snapshots, None)
