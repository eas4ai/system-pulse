"""Violating and corrected examples for WTE-001's actual evidence boundaries."""

import copy
import unittest
import hashlib
import json
import re
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from performance_compare import InvalidMeasurement
from windows_thermal_energy_verify import (
    THERMAL_ID,
    THERMAL_MODULE_SHA256,
    THERMAL_SOURCE_BY_BACKEND,
    validate_thermal,
    validate_power,
    validate_stages,
    validate_independent,
    validate_cpu_identity,
    validate_probe_sources,
    validate_normal,
    verify_hashes,
    validate_platforms,
    validate_installer,
    validate_sensor_ui,
    validate_energy_ui,
)
from windows_thermal_energy_collect import PROBE_SOURCES, signed_build_identity


def thermal(backend="intel"):
    if backend == "intel":
        observation_source = (
            "PawnIO / Intel package digital thermal sensor / signed module 0.2.11"
        )
        operands = dict(
            ia32_temperature_target=100 << 16,
            ia32_package_therm_status=(1 << 31) | (65 << 16),
        )
        value = 35.0
    elif backend == "amd_zen3":
        observation_source = (
            "PawnIO / AMD Zen 3 package Tctl/Tdie / signed module 0.2.11"
        )
        operands = dict(amd_thm_tcon_cur_tmp=401 << 21, amd_reserved=0)
        value = 50.125
    else:
        raise ValueError("unknown fixture backend")
    sensor = dict(
        id=THERMAL_ID,
        monitor_id="cpu:host",
        kind="Temperature",
        unit="Celsius",
        source="PawnIO / fixed Intel DTS or AMD Zen 3 package Tctl/Tdie",
        scope="One approved physical CPU package; not individual cores or ACPI thermal zones",
    )
    reading = dict(
        sensor_id=THERMAL_ID,
        value=value,
        availability="Available",
        reason=None,
        observations=[
            dict(
                source=observation_source,
                captured_ns=1_000_000_000,
                read_started_ns=None,
                integers=dict(
                    **operands,
                    query_before_qpc=10_000_000,
                    query_after_qpc=10_000_100,
                    query_qpc_frequency=10_000_000,
                    helper_sequence=1,
                ),
            )
        ],
    )
    return sensor, reading


def power():
    channel = "RAPL_Package0_PKG"
    instance = "ACPI\\CPU\\0"
    sid = f"cpu:host/emi:{len(instance)}:{instance}:{len(channel)}:{channel}/power"
    sensor = dict(
        id=sid,
        monitor_id="cpu:host",
        title=channel + " power",
        kind="Power",
        unit="Watts",
        source="Windows Energy Meter Interface",
        scope="CPU package energy domain; Microsoft PPM / "
        + instance
        + "; independent overlapping domain, never summed",
    )
    reading = dict(
        sensor_id=sid,
        availability="Available",
        value=3.6,
        reason=None,
        observations=[
            dict(
                captured_ns=n * 1_000_000_000,
                read_started_ns=n * 1_000_000_000 - 100,
                integers=dict(
                    absolute_energy_picowatt_hours=n * 1_000_000_000,
                    absolute_time_100ns=n * 10_000_000,
                ),
            )
            for n in (1, 2)
        ],
    )
    return sensor, reading


def stages(backend="intel"):
    result = []
    sequence = 0
    for name, state, reason in [
        ("off", "Unavailable", "CPU temperature access is off"),
        ("pending", "WarmingUp", "Waiting for CPU temperature authorization"),
        ("denied", "Failed", "CPU temperature authorization was denied or cancelled"),
        ("enabled", "Available", None),
        ("disabled", "Unavailable", "CPU temperature access is off"),
        ("helper-exit", "Failed", "CPU temperature helper exited"),
    ]:
        frames = []
        for i in range(3 if name == "enabled" else 1):
            sequence += 1
            s, r = thermal(backend)
            p, pr = power()
            if state != "Available":
                r.update(availability=state, value=None, reason=reason, observations=[])
            else:
                r["observations"][0]["integers"]["helper_sequence"] = i + 1
            frames.append(
                dict(
                    application_pid=42,
                    elevated=False,
                    qpc=10_000_100 + i * 10_000_000,
                    frequency=10_000_000,
                    observed_utc="2026-09-11T12:00:00+00:00",
                    snapshot=dict(
                        sequence=sequence,
                        capture_finished_ns=2_000_000_000,
                        sensors=[s, p],
                        readings=[r, pr],
                    ),
                )
            )
        result.append(
            dict(
                name=name,
                frames=frames,
                ui=dict(
                    selected_screen="Thermals",
                    pid=42,
                    controls=[
                        dict(
                            name=(
                                "Enable CPU temperatures…"
                                if state == "Unavailable"
                                else "CPU package temperature 35 °C " + str(reason)
                            ),
                            offscreen=False,
                        )
                    ],
                ),
                helper=dict(pid=43, exited=True),
            )
        )
    result[-1]["before_exit"] = copy.deepcopy(result[3]["frames"][-1])
    result[-1]["before_exit"]["snapshot"]["sequence"] = sequence
    result[-1]["frames"][0]["snapshot"]["sequence"] = sequence + 1
    return result


def independent_fixture(backend="intel"):
    captured = stages(backend)
    enabled = captured[3]["frames"]
    for frame, second in zip(enabled, (0, 5, 10)):
        frame["observed_utc"] = f"2026-09-11T12:00:{second:02}+00:00"

    def reply(data):
        return dict(ok=True, error=0, returned=len(data), hex=data.hex("-"))

    channel = "RAPL_Package0_PKG"
    name = (channel + "\0").encode("utf-16le")
    metadata = (
        bytes(64)
        + b"\x01\x00\x01\x00"
        + bytes(4)
        + len(name).to_bytes(2, "little")
        + name
    )
    emi = dict(
        elevated=False,
        open_error=0,
        instance="ACPI\\CPU\\0",
        path=r"\\?\ACPI#CPU#0#{45bd8344-7ed6-49cf-a440-c276c933b053}",
        version=reply(b"\x02\x00"),
        metadata_size=reply(len(metadata).to_bytes(4, "little")),
        metadata=reply(metadata),
        samples=[
            reply(
                (n * 1_000_000_000).to_bytes(8, "little")
                + (n * 10_000_000).to_bytes(8, "little")
            )
            for n in (1, 2, 3)
        ],
    )
    if backend == "intel":
        sample = {
            name: dict(register=register, ok=True, error=0, returned=8, value=value)
            for name, register, value in (
                ("target", 0x1A2, 100 << 16),
                ("package", 0x1B1, (1 << 31) | (65 << 16)),
            )
        }
    else:
        sample = dict(
            amd_thm_tcon_cur_tmp=dict(
                offset=0x59800, ok=True, error=0, returned=8, value=401 << 21
            ),
            amd_reserved=0,
        )
    thermal = dict(
        elevated=True,
        open_error=0,
        load_error=0,
        backend=backend,
        module_sha256=THERMAL_MODULE_SHA256[backend],
        source=THERMAL_SOURCE_BY_BACKEND[backend],
        processor_family=0x6 if backend == "intel" else 0x19,
        processor_model=0x9A if backend == "intel" else 0x21,
        package_count=1,
        observed_utc="2026-09-11T12:00:08+00:00",
        samples=[
            dict(
                **copy.deepcopy(sample),
                observed_utc=f"2026-09-11T12:00:{second:02}+00:00",
                query_before_qpc=timestamp - 10,
                query_after_qpc=timestamp,
                query_qpc_frequency=10_000_000,
            )
            for second, timestamp in ((2, 19_000_000), (4, 19_500_000), (8, 29_000_000))
        ],
    )
    return captured, dict(
        run_id="a" * 32,
        started_utc="2026-09-11T12:00:00+00:00",
        finished_utc="2026-09-11T12:00:10+00:00",
        emi=emi,
        thermal=thermal,
    )


class ReadingTests(unittest.TestCase):
    def test_all_stages_reject_stale_or_future_emi_windows(self):
        for index in range(6):
            for end in (100_000_000_000, 500_000_000):
                data = stages()
                frame = data[index]["frames"][0]
                frame["snapshot"]["capture_finished_ns"] = end
                # Preserve a fresh thermal receipt so the EMI boundary is tested.
                reading = frame["snapshot"]["readings"][0]
                if reading["observations"]:
                    reading["observations"][0]["captured_ns"] = end
                with (
                    self.subTest(stage=index, end=end),
                    self.assertRaises(InvalidMeasurement),
                ):
                    validate_stages(data)

    def test_helper_qpc_must_be_current_and_match_observer_frequency(self):
        for backend in ("intel", "amd_zen3"):
            for target in ("enabled", "before_exit"):
                for mutation in ("stale", "future", "frequency"):
                    data = stages(backend)
                    frame = (
                        data[3]["frames"][0]
                        if target == "enabled"
                        else data[-1]["before_exit"]
                    )
                    raw = frame["snapshot"]["readings"][0]["observations"][0]["integers"]
                    if mutation == "stale":
                        frame["qpc"] = 100_000_000_000
                        raw.update(query_before_qpc=1, query_after_qpc=2)
                    elif mutation == "future":
                        raw.update(
                            query_before_qpc=frame["qpc"] + 1,
                            query_after_qpc=frame["qpc"] + 2,
                        )
                    else:
                        frame["frequency"] = 1
                    with (
                        self.subTest(backend=backend, target=target, mutation=mutation),
                        self.assertRaises(InvalidMeasurement),
                    ):
                        validate_stages(data)

    def test_before_exit_also_rejects_stale_emi(self):
        data = stages()
        frame = data[-1]["before_exit"]
        frame["snapshot"]["capture_finished_ns"] = 100_000_000_000
        frame["snapshot"]["readings"][0]["observations"][0]["captured_ns"] = (
            100_000_000_000
        )
        with self.assertRaises(InvalidMeasurement):
            validate_stages(data)

    def test_fresh_current_emi_cannot_reuse_a_98_second_baseline(self):
        data = stages()
        frame = data[0]["frames"][0]
        frame["snapshot"]["capture_finished_ns"] = 100_000_000_000
        current = frame["snapshot"]["readings"][1]["observations"][1]
        current.update(captured_ns=100_000_000_000, read_started_ns=99_999_999_900)
        with self.assertRaises(InvalidMeasurement):
            validate_stages(data)

    def test_helper_exit_needs_a_fresh_success_after_disable(self):
        data = stages()
        data[-1]["before_exit"]["snapshot"]["sequence"] = 1
        with self.assertRaises(InvalidMeasurement):
            validate_stages(data)

    def test_platform_receipts_require_actual_tests_and_completed_clippy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tests = (
                "test result: ok. 23 passed; 0 failed; 0 ignored; finished in 0.5s\n"
            )
            clippy = "Finished `dev` profile [unoptimized] target(s) in 0.3s\n"
            (root / "tests.log").write_bytes(tests.encode("utf-8"))
            (root / "clippy.log").write_bytes(clippy.encode("utf-8"))
            checks = {
                name: dict(
                    exit_code=0,
                    command=[
                        "cargo",
                        command,
                        "--locked",
                        "-p",
                        "system-pulse",
                        "-p",
                        "system-pulse-model",
                        "-p",
                        "system-pulse-collectors",
                    ],
                    log=name + ".log",
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                )
                for name, command, text in (
                    ("tests", "test", tests),
                    ("clippy", "clippy", clippy),
                )
            }
            record = {
                name: dict(source_commit="a" * 40, checks=copy.deepcopy(checks))
                for name in ("linux", "macos", "windows")
            }
            with patch("performance_verify.same_production"):
                validate_platforms(root, record)
                for change in (
                    lambda r: r["linux"]["checks"]["tests"].update(exit_code=1),
                    lambda r: r["macos"]["checks"]["tests"]["command"].remove(
                        "system-pulse-collectors"
                    ),
                    lambda r: r["windows"]["checks"]["clippy"].update(sha256="0" * 64),
                ):
                    bad = copy.deepcopy(record)
                    change(bad)
                    with self.assertRaises(InvalidMeasurement):
                        validate_platforms(root, bad)

    def test_valid_temperature_recomputes_target_minus_delta(self):
        self.assertEqual(
            validate_thermal(*thermal(), 1_100_000_000, 11_000_000, 10_000_000), 35.0
        )

    def test_valid_amd_temperature_recomputes_tctl_with_range_correction(self):
        sensor, reading = thermal("amd_zen3")
        self.assertEqual(
            validate_thermal(sensor, reading, 1_100_000_000, 11_000_000, 10_000_000),
            50.125,
        )
        for raw, expected in (
            ((401 << 21) | (1 << 19), 1.125),
            ((401 << 21) | (3 << 16), 1.125),
        ):
            with self.subTest(raw=raw):
                sensor, reading = thermal("amd_zen3")
                reading["observations"][0]["integers"]["amd_thm_tcon_cur_tmp"] = raw
                reading["value"] = expected
                self.assertEqual(
                    validate_thermal(
                        sensor, reading, 1_100_000_000, 11_000_000, 10_000_000
                    ),
                    expected,
                )

    def test_amd_temperature_rejects_wrong_backend_operands_noninteger_and_range(self):
        mutations = (
            lambda s, r: r["observations"][0]["integers"].update(
                amd_thm_tcon_cur_tmp=401.0
            ),
            lambda s, r: r["observations"][0]["integers"].update(amd_reserved=1),
            lambda s, r: r["observations"][0]["integers"].update(
                amd_thm_tcon_cur_tmp=1001 << 21
            ),
            lambda s, r: r["observations"][0]["integers"].update(
                amd_thm_tcon_cur_tmp=1 << 32
            ),
            lambda s, r: r["observations"][0]["integers"].update(
                ia32_temperature_target=100 << 16,
                ia32_package_therm_status=(1 << 31) | (65 << 16),
            ),
            lambda s, r: r["observations"][0].update(
                source="PawnIO / Intel package digital thermal sensor / signed module 0.2.11"
            ),
            lambda s, r: r["observations"][0]["integers"].update(
                amd_extra_operand=1
            ),
        )
        for change in mutations:
            sensor, reading = thermal("amd_zen3")
            change(sensor, reading)
            with self.subTest(change=change), self.assertRaises(InvalidMeasurement):
                validate_thermal(sensor, reading, 1_100_000_000, 11_000_000, 10_000_000)

    def test_temperature_rejects_wrong_unit_scope_invalid_bits_and_stale_operands(self):
        for change in (
            lambda s, r: s.update(unit="Watts"),
            lambda s, r: s.update(monitor_id="gpu:0"),
            lambda s, r: s.update(scope="One physical Intel CPU package"),
            lambda s, r: r["observations"][0].update(
                source="PawnIO / AMD Zen 3 package Tctl/Tdie / signed module 0.2.11"
            ),
            lambda s, r: r.update(value=0),
            lambda s, r: r["observations"][0]["integers"].update(
                ia32_package_therm_status=65 << 16
            ),
            lambda s, r: r["observations"][0].update(captured_ns=0),
            lambda s, r: r["observations"][0]["integers"].update(query_qpc_frequency=0),
        ):
            s, r = thermal()
            change(s, r)
            with self.assertRaises(InvalidMeasurement):
                validate_thermal(s, r, 3_100_000_000, 11_000_000, 10_000_000)

    def test_temperature_backend_cannot_switch_between_enabled_frames(self):
        data = stages()
        sensor, reading = thermal("amd_zen3")
        data[3]["frames"][1]["snapshot"]["sensors"][0] = sensor
        data[3]["frames"][1]["snapshot"]["readings"][0] = reading
        with self.assertRaises(InvalidMeasurement):
            validate_stages(data)

    def test_emi_uses_integer_deltas_not_accumulated_energy_as_watts(self):
        self.assertAlmostEqual(validate_power(*power(), 2_000_000_000), 3.6)

    def test_emi_rejects_wrong_value_time_scope_baseline_and_fabricated_zero(self):
        for change in (
            lambda s, r: r.update(value=100),
            lambda s, r: s.update(unit="Joules"),
            lambda s, r: s.update(scope="Battery discharge"),
            lambda s, r: r["observations"][0]["integers"].update(
                absolute_energy_picowatt_hours=0
            ),
            lambda s, r: r["observations"][1]["integers"].update(
                absolute_time_100ns=10_000_000
            ),
            lambda s, r: r["observations"].pop(),
        ):
            s, r = power()
            change(s, r)
            with self.assertRaises(InvalidMeasurement):
                validate_power(s, r, 2_000_000_000)

    def test_unsupported_requires_absent_value_and_reason(self):
        s, r = power()
        r.update(
            availability="Unavailable",
            value=None,
            reason="EMI counter has not established nonzero energy support",
            observations=[],
        )
        self.assertIsNone(validate_power(s, r, 2_000_000_000))
        r["value"] = 0
        with self.assertRaises(InvalidMeasurement):
            validate_power(s, r, 2_000_000_000)
        r.update(value=None, reason="")
        with self.assertRaises(InvalidMeasurement):
            validate_power(s, r, 2_000_000_000)

    def test_missing_stages_cannot_establish_acceptance(self):
        with self.assertRaises(InvalidMeasurement):
            validate_stages([])

    def test_complete_lifecycle_has_real_values_and_clears_after_exit(self):
        validate_stages(stages())

    def test_complete_amd_lifecycle_has_real_values_and_clears_after_exit(self):
        validate_stages(stages("amd_zen3"))

    def test_lifecycle_rejects_elevation_omission_duplicate_identity_and_old_value(
        self,
    ):
        for change in (
            lambda x: x.pop(),
            lambda x: x[0]["frames"][0].update(elevated=True),
            lambda x: x[3]["frames"][0]["snapshot"]["sensors"].append(
                x[3]["frames"][0]["snapshot"]["sensors"][0]
            ),
            lambda x: x[-1]["frames"][0]["snapshot"]["readings"][0].update(value=35),
            lambda x: x[1]["frames"][0]["snapshot"].update(sequence=1),
            lambda x: x[3]["ui"].update(controls=[]),
        ):
            value = stages()
            change(value)
            with self.assertRaises(InvalidMeasurement):
                validate_stages(value)

    def test_current_independent_sources_agree(self):
        frames, probe = independent_fixture()
        validate_independent(frames, probe, "a" * 32)

    def test_current_amd_independent_smn_source_agrees_and_rejects_bad_evidence(self):
        frames, probe = independent_fixture("amd_zen3")
        validate_independent(frames, probe, "a" * 32)
        mutations = (
            lambda p: p["thermal"].update(backend="intel"),
            lambda p: p["thermal"].update(source=THERMAL_SOURCE_BY_BACKEND["intel"]),
            lambda p: p["thermal"].update(module_sha256="0" * 64),
            lambda p: p["thermal"].update(processor_family=0x17),
            lambda p: p["thermal"].update(processor_model=0x31),
            lambda p: p["thermal"].update(package_count=2),
            lambda p: p["thermal"]["samples"][0]["amd_thm_tcon_cur_tmp"].update(
                offset=0x59804
            ),
            lambda p: p["thermal"]["samples"][0]["amd_thm_tcon_cur_tmp"].update(
                value=401.0
            ),
            lambda p: p["thermal"]["samples"][0].update(amd_reserved=1),
            lambda p: p["thermal"]["samples"][0]["amd_thm_tcon_cur_tmp"].update(
                value=1001 << 21
            ),
            lambda p: p["thermal"]["samples"][0].update(
                target=dict(register=0x1A2, ok=True, error=0, returned=8, value=100 << 16)
            ),
            lambda p: p["thermal"]["samples"][0].update(
                observed_utc="2026-09-10T12:00:02+00:00"
            ),
            lambda p: p["thermal"]["samples"][0].update(query_before_qpc=0),
            lambda p: p["thermal"]["samples"][0].update(query_after_qpc=18_999_990),
            lambda p: p["thermal"]["samples"][1].update(
                query_before_qpc=18_500_000, query_after_qpc=18_500_010
            ),
            lambda p: p["thermal"]["samples"][1].update(
                query_before_qpc=20_999_999, query_after_qpc=21_000_000
            ),
            lambda p: p["thermal"]["samples"][0].update(
                query_qpc_frequency=1_000_000
            ),
        )
        for change in mutations:
            bad_frames, bad_probe = independent_fixture("amd_zen3")
            change(bad_probe)
            with self.subTest(change=change), self.assertRaises(InvalidMeasurement):
                validate_independent(bad_frames, bad_probe, "a" * 32)

    def test_native_pawnio_probe_keeps_fixed_vendor_reads_and_clock_evidence(self):
        source_path = Path(__file__).resolve().parents[2] / PROBE_SOURCES[
            "pawnio-temperature-probe.ps1"
        ]
        source = source_path.read_text(encoding="utf-8")
        for required in (
            "ioctl_read_msr",
            "0x1A2",
            "0x19C",
            "0x1B1",
            "ioctl_read_smn",
            "TemperatureOffset = 0x59800",
            r"Global\Access_PCI",
            "WaitOne(250)",
            "GetLogicalProcessorInformationEx",
            "RelationProcessorPackage = 3",
            "query_before_qpc",
            "query_after_qpc",
            "query_qpc_frequency",
            "d6ed85d65ab17a22f813ef98207d6d537155ee2ded5976a21cb48413c9b92e5f",
            "dae74615761b78bdf064dfb3e136252ddcc6fc727d88f14738d0e5800d427a91",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertNotIn("ReadAmdTemperature(SafeFileHandle handle, ulong", source)
        self.assertEqual(source.count("GetLogicalProcessorInformationEx(\n   RelationProcessorPackage"), 1)
        self.assertIn(
            "GetLogicalProcessorInformationEx(RelationProcessorPackage, buffer, ref length)",
            source,
        )
        self.assertLess(
            source.index("if ($packageCount -ne 1)"),
            source.index("$handle = [ThermalProbe]::CreateFile"),
        )

        module_assignments = re.findall(
            r"\$backend = '(intel|amd_zen3)'\s*\r?\n\s*"
            r"\$module = Join-Path \$PSScriptRoot '([^']+)'\s*\r?\n\s*"
            r"\$moduleHash = '([0-9a-f]{64})'",
            source,
        )
        self.assertEqual(
            {backend for backend, _, _ in module_assignments},
            set(THERMAL_MODULE_SHA256),
        )
        for backend, relative_path, expected_hash in module_assignments:
            with self.subTest(backend=backend):
                module_path = source_path.parent.joinpath(
                    *relative_path.replace("\\", "/").split("/")
                ).resolve()
                self.assertTrue(module_path.is_file(), str(module_path))
                self.assertEqual(expected_hash, THERMAL_MODULE_SHA256[backend])
                self.assertEqual(
                    hashlib.sha256(module_path.read_bytes()).hexdigest(), expected_hash
                )

    def test_thermal_cpu_identity_binds_supported_backend_and_one_package(self):
        amd_thermal = dict(
            backend="amd_zen3", processor_family=0x19, processor_model=0x21
        )
        validate_cpu_identity(
            [dict(Manufacturer="AuthenticAMD", ProcessorId="178BFBFF00A20F12")],
            amd_thermal,
        )
        validate_cpu_identity(
            [dict(Manufacturer="AuthenticAMD", ProcessorId="00A20F12178BFBFF")],
            amd_thermal,
        )
        intel_thermal = dict(backend="intel", processor_family=0x6, processor_model=0x9A)
        validate_cpu_identity(
            [dict(Manufacturer="GenuineIntel", ProcessorId="BFEBFBFF000906A3")],
            intel_thermal,
        )
        validate_cpu_identity(
            [dict(Manufacturer="GenuineIntel", ProcessorId="000906A3BFEBFBFF")],
            intel_thermal,
        )
        for cpu_inventory, thermal in (
            (
                [
                    dict(Manufacturer="AuthenticAMD", ProcessorId="178BFBFF00A20F12"),
                    dict(Manufacturer="AuthenticAMD", ProcessorId="178BFBFF00A20F12"),
                ],
                amd_thermal,
            ),
            ([dict(Manufacturer="AuthenticAMD", ProcessorId="178BFBFF00A20F12")], intel_thermal),
            ([dict(Manufacturer="AuthenticAMD", ProcessorId="178BFBFF000906A3")], amd_thermal),
            ([dict(Manufacturer="Unknown", ProcessorId="178BFBFF00A20F12")], amd_thermal),
            ([dict(Manufacturer="AuthenticAMD", ProcessorId="invalid")], amd_thermal),
            (
                [dict(Manufacturer="AuthenticAMD", ProcessorId="178BFBFF00A20F12")],
                dict(backend="amd_zen3", processor_family=0x19, processor_model=0x17),
            ),
        ):
            with self.subTest(cpu_inventory=cpu_inventory, thermal=thermal), self.assertRaises(
                InvalidMeasurement
            ):
                validate_cpu_identity(cpu_inventory, thermal)

    def test_probe_source_hashes_bind_the_receipt_independent_file_and_commit(self):
        root = Path(__file__).resolve().parents[2]
        hashes = {
            name: hashlib.sha256((root / path).read_bytes()).hexdigest()
            for name, path in PROBE_SOURCES.items()
        }

        def show_committed(command, **_kwargs):
            relative_path = command[2].split(":", 1)[1]
            return SimpleNamespace(
                returncode=0,
                stdout=(root / relative_path).read_bytes(),
            )

        with patch("windows_thermal_energy_verify.subprocess.run", side_effect=show_committed):
            validate_probe_sources(hashes, hashes, "a" * 40, PROBE_SOURCES)
            with self.assertRaises(InvalidMeasurement):
                validate_probe_sources(
                    {**hashes, "pawnio-temperature-probe.ps1": "0" * 64},
                    hashes,
                    "a" * 40,
                    PROBE_SOURCES,
                )

        with patch(
            "windows_thermal_energy_verify.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=b"other committed script"),
        ):
            with self.assertRaises(InvalidMeasurement):
                validate_probe_sources(hashes, hashes, "a" * 40, PROBE_SOURCES)

    def test_historical_probe_wrong_register_and_source_failures_do_not_pass(self):
        for change in (
            lambda p: p.update(run_id="b" * 32),
            lambda p: p.update(started_utc="2026-09-10T12:00:00+00:00"),
            lambda p: p["thermal"]["samples"][0]["package"].update(register=0x19C),
            lambda p: p["thermal"].update(open_error=5),
            lambda p: p["emi"].update(elevated=True),
            lambda p: p["emi"]["samples"][0].update(returned=8),
            lambda p: p["emi"].update(instance="OTHER"),
        ):
            frames, probe = independent_fixture()
            change(probe)
            with self.assertRaises(InvalidMeasurement):
                validate_independent(frames, probe, "a" * 32)

    def test_independent_values_reject_wrong_package_temperature_and_watts(self):
        frames, probe = independent_fixture()
        for frame in frames[3]["frames"]:
            frame["snapshot"]["readings"][0]["value"] = 90
        with self.assertRaises(InvalidMeasurement):
            validate_independent(frames, probe, "a" * 32)

    def test_relabeling_old_emi_probe_utc_cannot_hide_old_raw_clock(self):
        frames, probe = independent_fixture()
        for reply in probe["emi"]["samples"]:
            data = bytearray.fromhex(reply["hex"].replace("-", ""))
            data[8:16] = (
                10_000_000_000 + int.from_bytes(data[8:16], "little")
            ).to_bytes(8, "little")
            reply["hex"] = data.hex("-")
        with self.assertRaises(InvalidMeasurement):
            validate_independent(frames, probe, "a" * 32)
        frames, probe = independent_fixture()
        for frame in frames[3]["frames"]:
            frame["snapshot"]["readings"][1]["value"] = 90
        with self.assertRaises(InvalidMeasurement):
            validate_independent(frames, probe, "a" * 32)

    def test_signed_identity_preserves_both_binary_hashes(self):
        build = dict(
            source_commit="a" * 40,
            target="x86_64-pc-windows-msvc",
            unsigned_binary_sha256="b" * 64,
            binary_sha256="c" * 64,
            authenticode=dict(status="Valid", subject="Publisher", thumbprint="D" * 40),
        )
        signed_build_identity(build, "a" * 40, "b" * 64, "c" * 64)
        for key, value in (
            ("unsigned_binary_sha256", "c" * 64),
            ("binary_sha256", "b" * 64),
            ("source_commit", "f" * 40),
        ):
            bad = copy.deepcopy(build)
            bad[key] = value
            with self.assertRaises(InvalidMeasurement):
                signed_build_identity(bad, "a" * 40, "b" * 64, "c" * 64)

    def test_installer_receipts_bind_both_lifecycles_and_shared_driver(self):
        signature = dict(status="Valid", subject="Publisher", thumbprint="D" * 40)
        manifest = dict(
            source_commit="a" * 40,
            binary_sha256="b" * 64,
            installer_sha256="c" * 64,
            application_signature=signature,
            installer_signature=signature,
            pawnio_signature=signature,
            pawnio_sha256="1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032",
        )
        driver = dict(
            version="2.2.0.0",
            start_mode="Manual",
            state="Running",
            location="PawnIO",
            driver_path="PawnIO.sys",
        )
        result = dict(
            status="PASS",
            installer_sha256="c" * 64,
            binary_sha256="b" * 64,
            install_exit=0,
            existing_driver_install_exit=0,
            uninstall_exit=0,
            owned_directory_removed=True,
            shared_driver_before=driver,
            shared_driver_after=driver,
            fresh_driver_installed=False,
            installer_signer="Publisher",
            application_signer="Publisher",
            uninstaller_signer="Publisher",
        )
        good = {
            "manifest.json": manifest,
            "existing/result.json": result,
            "fresh/result.json": dict(
                result, shared_driver_before=None, fresh_driver_installed=True
            ),
        }
        mutations = [
            lambda d: d["fresh/result.json"].update(status="FAIL"),
            lambda d: d["fresh/result.json"].update(install_exit=1),
            lambda d: d["existing/result.json"].update(existing_driver_install_exit=1),
            lambda d: d["existing/result.json"].update(uninstall_exit=1),
            lambda d: d["existing/result.json"].update(owned_directory_removed=False),
            lambda d: d["existing/result.json"].update(shared_driver_after=None),
            lambda d: d["existing/result.json"].update(
                shared_driver_after=dict(driver, location="Different installation")
            ),
            lambda d: d["existing/result.json"]["shared_driver_after"].update(
                state="Stopped"
            ),
            lambda d: d["fresh/result.json"].update(shared_driver_before=driver),
            lambda d: d["fresh/result.json"].update(fresh_driver_installed=False),
            lambda d: d["existing/result.json"].update(installer_sha256="d" * 64),
            lambda d: d["manifest.json"].update(binary_sha256="d" * 64),
            lambda d: d["manifest.json"].update(pawnio_sha256="d" * 64),
            lambda d: d["manifest.json"]["installer_signature"].update(
                status="NotSigned"
            ),
        ]
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch("performance_verify.same_production"),
        ):
            root = Path(temporary)

            def write(data):
                hashes = {}
                for name, value in data.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(value))
                    hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
                harness = Path(__file__).with_name("windows_installer_verify.ps1")
                receipt = dict(
                    source_commit="a" * 40,
                    signed_binary_sha256="b" * 64,
                    harness_sha256={
                        harness.name: hashlib.sha256(harness.read_bytes()).hexdigest()
                    },
                    artifacts_sha256=hashes,
                )
                (root / "receipt.json").write_text(json.dumps(receipt))

            write(good)
            validate_installer(root, "b" * 64)
            for mutate in mutations:
                with self.subTest(mutate=mutate):
                    bad = copy.deepcopy(good)
                    mutate(bad)
                    write(bad)
                    with self.assertRaises(InvalidMeasurement):
                        validate_installer(root, "b" * 64)
            write(good)
            (root / "manifest.json").write_text("{}")
            with self.assertRaises(InvalidMeasurement):
                validate_installer(root, "b" * 64)
            write(good)
            receipt_path = root / "receipt.json"
            receipt = json.loads(receipt_path.read_text())
            receipt["harness_sha256"]["windows_installer_verify.ps1"] = "0" * 64
            receipt_path.write_text(json.dumps(receipt))
            with self.assertRaises(InvalidMeasurement):
                validate_installer(root, "b" * 64)
            write(good)
            (root / "receipt.json").unlink()
            with self.assertRaises(InvalidMeasurement):
                validate_installer(root, "b" * 64)

    def test_artifact_hashes_reject_missing_tampered_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data.json").write_text("observed")
            good = hashlib.sha256(b"observed").hexdigest()
            verify_hashes(root, {"data.json": good})
            for name, digest in (
                ("../data.json", good),
                ("missing", good),
                ("data.json", "0" * 64),
            ):
                with self.assertRaises(InvalidMeasurement):
                    verify_hashes(root, {name: digest})

    def test_normal_preservation_is_unelevated_and_has_gpu_processes_and_quit(self):
        ui = dict(
            selected_screen="GPU",
            pid=42,
            controls=[
                dict(name=name, offscreen=False)
                for name in (
                    "Intel Iris",
                    "GPU utilization",
                    "Dedicated GPU memory",
                    "Shared GPU memory",
                )
            ],
        )
        record = dict(
            elevated=False,
            diagnostics_enabled=False,
            gpu=ui,
            normal_gpu=ui,
            diagnostic_rows=[dict(pid=42, name="pulse")],
            normal_rows=[dict(pid=42, name="pulse")],
            quit=dict(pid=42, menu_owner=42, exit_code=0),
        )
        validate_normal(record, [dict(Name="Intel Iris")])
        for change in (
            lambda r: r.update(elevated=True),
            lambda r: r.update(normal_rows=[]),
            lambda r: r["quit"].update(exit_code=1),
            lambda r: r["normal_gpu"].update(controls=[]),
            lambda r: r["normal_gpu"]["controls"].append(
                dict(name="GPU temperature Unavailable", offscreen=False)
            ),
        ):
            bad = copy.deepcopy(record)
            change(bad)
            with self.assertRaises(InvalidMeasurement):
                validate_normal(bad, [dict(Name="Intel Iris")])

    def test_readable_power_labels_and_hidden_unavailable_cards(self):
        labels = [
            "CPU package power",
            "Memory power",
            "CPU cores power",
            "Integrated GPU power",
        ]
        ui = dict(
            selected_screen="Energy",
            pid=42,
            controls=[dict(name=label + " 12 W", offscreen=False) for label in labels],
        )
        validate_energy_ui(ui)
        for i, domain in enumerate(("PKG", "DRAM", "PP0", "PP1")):
            bad = copy.deepcopy(ui)
            bad["controls"][i]["name"] = "RAPL_Package0_" + domain + " 12 W"
            with self.subTest(domain=domain), self.assertRaises(InvalidMeasurement):
                validate_energy_ui(bad)
        for screen in ("Energy", "Thermals", "GPU", "CPU", "Memory", "Summary"):
            bad = copy.deepcopy(ui)
            bad["selected_screen"] = screen
            bad["controls"].append(
                dict(name="Unused sensor Unavailable", offscreen=False)
            )
            with self.subTest(screen=screen), self.assertRaises(InvalidMeasurement):
                validate_sensor_ui(bad)
            bad["controls"][-1]["offscreen"] = True
            validate_sensor_ui(bad)
        for labels in (["CPU package power"], ["12 W"]):
            bad = dict(
                ui, controls=[dict(name=name, offscreen=False) for name in labels]
            )
            with self.assertRaises(InvalidMeasurement):
                validate_energy_ui(bad)

    def test_off_sensor_card_must_be_hidden_but_diagnostics_keep_reason(self):
        good = stages()
        validate_stages(good)
        for index in (0, 4):
            bad = copy.deepcopy(good)
            bad[index]["ui"]["controls"].append(
                dict(
                    name="CPU package temperature Unavailable CPU temperature access is off",
                    offscreen=False,
                )
            )
            with self.subTest(stage=index), self.assertRaises(InvalidMeasurement):
                validate_stages(bad)
            bad[index]["ui"]["controls"][-1]["name"] = "CPU package temperature"
            with self.assertRaises(InvalidMeasurement):
                validate_stages(bad)
            bad[index]["ui"]["controls"] = []
            with self.assertRaises(InvalidMeasurement):
                validate_stages(bad)


if __name__ == "__main__":
    unittest.main()
