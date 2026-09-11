"""Violating and corrected examples for WTE-001's actual evidence boundaries."""

import copy
import unittest
import hashlib
from pathlib import Path
import tempfile
from unittest.mock import patch
from performance_compare import InvalidMeasurement
from windows_thermal_energy_verify import (
    THERMAL_ID,
    validate_thermal,
    validate_power,
    validate_stages,
    validate_independent,
    validate_normal,
    verify_hashes,
    validate_platforms,
)
from windows_thermal_energy_collect import signed_build_identity


def thermal():
    sensor = dict(
        id=THERMAL_ID,
        monitor_id="cpu:host",
        kind="Temperature",
        unit="Celsius",
        source="PawnIO / Intel package digital thermal sensor",
        scope="One physical Intel CPU package; not individual cores or ACPI thermal zones",
    )
    reading = dict(
        sensor_id=THERMAL_ID,
        value=35.0,
        availability="Available",
        reason=None,
        observations=[
            dict(
                captured_ns=1_000_000_000,
                read_started_ns=None,
                integers=dict(
                    ia32_temperature_target=100 << 16,
                    ia32_package_therm_status=(1 << 31) | (65 << 16),
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


def stages():
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
            s, r = thermal()
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
                            name="CPU package temperature 35 °C " + str(reason),
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


def independent_fixture():
    captured = stages()
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
    sample = {
        name: dict(register=register, ok=True, error=0, returned=8, value=value)
        for name, register, value in (
            ("target", 0x1A2, 100 << 16),
            ("package", 0x1B1, (1 << 31) | (65 << 16)),
        )
    }
    thermal = dict(
        elevated=True,
        open_error=0,
        load_error=0,
        observed_utc="2026-09-11T12:00:05+00:00",
        samples=[copy.deepcopy(sample) for _ in range(3)],
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
        for target in ("enabled", "before_exit"):
            for mutation in ("stale", "future", "frequency"):
                data = stages()
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
                    self.subTest(target=target, mutation=mutation),
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
            (root / "tests.log").write_text(tests)
            (root / "clippy.log").write_text(clippy)
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

    def test_temperature_rejects_wrong_unit_scope_invalid_bits_and_stale_operands(self):
        for change in (
            lambda s, r: s.update(unit="Watts"),
            lambda s, r: s.update(monitor_id="gpu:0"),
            lambda s, r: s.update(scope="ACPI zone"),
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
                    "Unavailable",
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
        ):
            bad = copy.deepcopy(record)
            change(bad)
            with self.assertRaises(InvalidMeasurement):
                validate_normal(bad, [dict(Name="Intel Iris")])


if __name__ == "__main__":
    unittest.main()
