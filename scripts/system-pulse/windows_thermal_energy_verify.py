"""Fail-closed native acceptance for Windows package temperature and EMI power."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime
from performance_compare import require, InvalidMeasurement

THERMAL_ID = "cpu:host/windows-package-temperature"
DOMAINS = {
    "PKG": "CPU package energy domain",
    "DRAM": "DRAM energy domain",
    "PP0": "CPU cores energy domain",
    "PP1": "Integrated GPU energy domain under CPU package",
}


def integer(value, name):
    require(
        type(value) is int and 0 <= value <= 2**64 - 1,
        "invalid integer operand: " + name,
    )
    return value


def available(reading):
    if reading["availability"] == "Available":
        require(
            type(reading["value"]) in (float, int) and math.isfinite(reading["value"]),
            "nonfinite reading",
        )
        require(reading["observations"], "measured reading lacks source operands")
        return True
    require(
        reading["availability"] in ("Unavailable", "WarmingUp", "Failed")
        and reading["value"] is None
        and isinstance(reading["reason"], str)
        and reading["reason"].strip(),
        "unsupported source is fabricated or unexplained",
    )
    return False


def temperature(target, status):
    target = integer(target, "temperature target")
    status = integer(status, "package status")
    tjmax = (target >> 16) & 255
    result = tjmax - ((status >> 16) & 127)
    require(
        status & (1 << 31) and 50 <= tjmax <= 125 and -40 <= result <= 125,
        "invalid package thermal bits or target",
    )
    return result


def validate_thermal(sensor, reading, snapshot_ns, observer_qpc, observer_frequency):
    integer(snapshot_ns, "snapshot finish")
    integer(observer_qpc, "observer QPC")
    integer(observer_frequency, "observer QPC frequency")
    require(observer_frequency > 0, "observer QPC frequency is zero")
    require(
        sensor["id"] == reading["sensor_id"] == THERMAL_ID
        and sensor["monitor_id"] == "cpu:host",
        "wrong package temperature identity",
    )
    require(
        sensor["kind"] == "Temperature"
        and sensor["unit"] == "Celsius"
        and "PawnIO" in sensor["source"]
        and sensor["scope"]
        == "One physical Intel CPU package; not individual cores or ACPI thermal zones",
        "wrong temperature source, unit or scope",
    )
    if not available(reading):
        return None
    require(
        len(reading["observations"]) == 1, "temperature needs one exact raw observation"
    )
    observation = reading["observations"][0]
    v = observation["integers"]
    for key in (
        "query_before_qpc",
        "query_after_qpc",
        "query_qpc_frequency",
        "helper_sequence",
    ):
        integer(v[key], key)
    require(
        v["query_qpc_frequency"] > 0
        and v["helper_sequence"] > 0
        and 0
        <= v["query_after_qpc"] - v["query_before_qpc"]
        <= v["query_qpc_frequency"],
        "invalid temperature query window",
    )
    # These are the same machine-wide QPC clock, unlike collector-relative ns.
    require(
        v["query_qpc_frequency"] == observer_frequency
        and 0 <= observer_qpc - v["query_after_qpc"] <= 3 * observer_frequency,
        "helper query is stale, in the future or uses a different QPC frequency",
    )
    captured = integer(observation["captured_ns"], "receipt time")
    require(
        0 <= snapshot_ns - captured <= 3_000_000_000
        and observation["read_started_ns"] is None,
        "temperature is stale or QPC was mislabeled as collector time",
    )
    expected = temperature(v["ia32_temperature_target"], v["ia32_package_therm_status"])
    require(reading["value"] == expected, "temperature differs from raw MSR operands")
    return expected


def power_identity(sensor):
    identity = sensor["id"]
    require(
        identity.startswith("cpu:host/emi:") and identity.endswith("/power"),
        "wrong EMI identity",
    )
    rest = identity[len("cpu:host/emi:") :]
    size, rest = rest.split(":", 1)
    require(size.isascii() and size.isdigit(), "invalid EMI instance length")
    size = int(size)
    instance = rest[:size]
    require(size > 0 and rest[size : size + 1] == ":", "invalid EMI instance boundary")
    length, channel = rest[size + 1 :].split(":", 1)
    channel = channel.removesuffix("/power")
    require(
        length.isascii() and length.isdigit() and int(length) == len(channel),
        "invalid EMI channel length",
    )
    match = re.fullmatch(r"RAPL_Package[0-9]+_(PKG|DRAM|PP0|PP1)", channel)
    require(
        match is not None and instance == instance.upper(), "unknown EMI channel domain"
    )
    require(
        sensor["scope"].startswith(DOMAINS[match[1]] + "; ")
        and (
            " / " + instance + "; independent overlapping domain, never summed"
        ).casefold()
        in sensor["scope"].casefold(),
        "mislabeled or summed EMI scope",
    )
    return instance, channel


def validate_power(sensor, reading, snapshot_ns):
    integer(snapshot_ns, "snapshot finish")
    require(
        sensor["id"] == reading["sensor_id"]
        and sensor["monitor_id"] == "cpu:host"
        and sensor["kind"] == "Power"
        and sensor["unit"] == "Watts"
        and sensor["source"] == "Windows Energy Meter Interface",
        "wrong EMI unit, source or owner",
    )
    power_identity(sensor)
    if not available(reading):
        return None
    observations = reading["observations"]
    require(len(observations) == 2, "EMI watts need two retained integer observations")
    a, b = observations
    av, bv = a["integers"], b["integers"]
    for observation in observations:
        integer(observation["read_started_ns"], "EMI read start")
        integer(observation["captured_ns"], "EMI capture time")
    for v in (av, bv):
        for key in ("absolute_energy_picowatt_hours", "absolute_time_100ns"):
            integer(v[key], key)
    energy = bv["absolute_energy_picowatt_hours"] - av["absolute_energy_picowatt_hours"]
    ticks = bv["absolute_time_100ns"] - av["absolute_time_100ns"]
    require(
        av["absolute_energy_picowatt_hours"] > 0 and energy >= 0 and ticks > 0,
        "EMI source is unestablished, reset or nonadvancing",
    )
    require(
        0
        <= a["read_started_ns"]
        <= a["captured_ns"]
        < b["read_started_ns"]
        <= b["captured_ns"],
        "invalid EMI read windows",
    )
    # HostCollector writes capture_finished_ns after all backend reads. Bound
    # against that end, never the snapshot's earlier capture_started_ns.
    require(
        0 <= snapshot_ns - b["captured_ns"] <= 3_000_000_000,
        "EMI current observation is stale or in the future",
    )
    require(
        all(
            o["captured_ns"] - o["read_started_ns"] <= 1_000_000_000
            for o in observations
        ),
        "EMI source query exceeded one second",
    )
    # The app supports a maximum five-second sampling interval; permit one
    # additional second of query margin, but never reuse a long-dead baseline.
    require(
        b["captured_ns"] - a["captured_ns"] <= 6_000_000_000,
        "EMI power interval uses a stale baseline",
    )
    expected = energy * 0.036 / ticks
    require(
        math.isclose(reading["value"], expected, rel_tol=1e-9, abs_tol=1e-9),
        "watts differ from EMI energy/time deltas",
    )
    return expected


def validate_stages(stages):
    names = [s["name"] for s in stages]
    require(
        names == ["off", "pending", "denied", "enabled", "disabled", "helper-exit"],
        "missing or reordered native lifecycle stages",
    )
    previous = 0
    pid = None
    stable = None
    last_helper_sequence = 0
    for stage in stages:
        require(
            stage["frames"]
            and (stage["name"] != "enabled" or len(stage["frames"]) >= 3),
            "insufficient native stage frames",
        )
        for frame in stage["frames"]:
            require(
                frame["elevated"] is False and frame["application_pid"] > 0,
                "dashboard observation is elevated or has no process",
            )
            if pid is None:
                pid = frame["application_pid"]
            require(
                frame["application_pid"] == pid, "stage switched application identity"
            )
            snapshot = frame["snapshot"]
            require(snapshot["sequence"] > previous, "native sampling did not advance")
            previous = snapshot["sequence"]
            sensors = {s["id"]: s for s in snapshot["sensors"]}
            readings = {r["sensor_id"]: r for r in snapshot["readings"]}
            require(
                len(sensors) == len(snapshot["sensors"])
                and len(readings) == len(snapshot["readings"])
                and THERMAL_ID in sensors
                and THERMAL_ID in readings,
                "duplicate or omitted sensor/reading",
            )
            identity = {sid for sid in sensors if sid.startswith("cpu:host/emi:")} | {
                THERMAL_ID
            }
            require(len(identity) > 1, "no EMI domain was exposed")
            if stable is None:
                stable = identity
            require(
                identity == stable,
                "thermal/energy sensor identity changed between stages",
            )
            for sid, sensor in sensors.items():
                if sensor["kind"] in ("Power", "Temperature"):
                    available(readings[sid])
                if sid.startswith("cpu:host/emi:"):
                    validate_power(
                        sensor, readings[sid], snapshot["capture_finished_ns"]
                    )
            value = validate_thermal(
                sensors[THERMAL_ID],
                readings[THERMAL_ID],
                snapshot["capture_finished_ns"],
                frame["qpc"],
                frame["frequency"],
            )
            reading = readings[THERMAL_ID]
            name = stage["name"]
            expected = {
                "off": "Unavailable",
                "pending": "WarmingUp",
                "denied": "Failed",
                "enabled": "Available",
                "disabled": "Unavailable",
                "helper-exit": "Failed",
            }[name]
            require(
                reading["availability"] == expected, "wrong availability after " + name
            )
            if name == "enabled":
                require(
                    value is not None,
                    "unsupported-only output cannot establish sensor collection",
                )
                seq = reading["observations"][0]["integers"]["helper_sequence"]
                require(
                    seq > last_helper_sequence, "enabled helper sample did not advance"
                )
                last_helper_sequence = seq
            if name in ("off", "disabled"):
                require(
                    "off" in reading["reason"].lower(), "off state lacks explanation"
                )
            if name == "denied":
                require(
                    any(
                        s in reading["reason"].lower() for s in ("denied", "cancelled")
                    ),
                    "denial was not actually observed",
                )
        if stage["name"] != "pending":
            ui = stage["ui"]
            require(
                ui["selected_screen"] == "Thermals" and ui["pid"] == pid,
                "wrong native Thermals page",
            )
            visible = " ".join(c["name"] for c in ui["controls"] if not c["offscreen"])
            require(
                "CPU package temperature" in visible,
                "CPU package temperature is absent from UI",
            )
            if stage["name"] == "enabled":
                require("°C" in visible, "Celsius unit absent from UI")
            else:
                require(
                    reading["reason"] in visible,
                    "availability explanation absent from native Thermals UI",
                )
        if stage["name"] == "helper-exit":
            before = stage["before_exit"]
            disabled_sequence = stages[4]["frames"][-1]["snapshot"]["sequence"]
            require(
                before["application_pid"] == pid
                and before["elevated"] is False
                and disabled_sequence
                < before["snapshot"]["sequence"]
                < stage["frames"][0]["snapshot"]["sequence"]
                and stage["helper"]["pid"] != pid
                and stage["helper"]["exited"] is True,
                "helper exit was not observed",
            )
            thermal = next(
                r
                for r in before["snapshot"]["readings"]
                if r["sensor_id"] == THERMAL_ID
            )
            require(
                thermal["availability"] == "Available" and thermal["value"] is not None,
                "helper never supplied a value before exit",
            )
            sensor = next(
                s for s in before["snapshot"]["sensors"] if s["id"] == THERMAL_ID
            )
            validate_thermal(
                sensor,
                thermal,
                before["snapshot"]["capture_finished_ns"],
                before["qpc"],
                before["frequency"],
            )
            before_readings = {
                r["sensor_id"]: r for r in before["snapshot"]["readings"]
            }
            for before_sensor in before["snapshot"]["sensors"]:
                if before_sensor["id"].startswith("cpu:host/emi:"):
                    validate_power(
                        before_sensor,
                        before_readings[before_sensor["id"]],
                        before["snapshot"]["capture_finished_ns"],
                    )
        if stage["name"] == "disabled":
            require(
                stage["helper"]["pid"] != pid and stage["helper"]["exited"] is True,
                "helper survived disabling collection",
            )
    return stable


def utc(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "observation lacks timezone")
    return result.timestamp()


def reply_bytes(reply, size=None):
    require(
        reply["ok"] is True and reply["error"] == 0, "independent native source failed"
    )
    try:
        data = bytes.fromhex(reply["hex"].replace("-", ""))
    except ValueError as e:
        raise InvalidMeasurement("invalid independent reply hex") from e
    require(
        len(data) == reply["returned"] and (size is None or len(data) == size),
        "independent native reply length mismatch",
    )
    return data


def emi_channels(probe):
    require(
        probe["elevated"] is False and probe["open_error"] == 0,
        "EMI independent source was elevated or failed",
    )
    version = int.from_bytes(reply_bytes(probe["version"], 2), "little")
    require(version == 2, "tablet EMI evidence must identify version 2")
    metadata = reply_bytes(probe["metadata"])
    require(
        len(metadata)
        == int.from_bytes(reply_bytes(probe["metadata_size"], 4), "little")
        and 68 <= len(metadata) <= 65536,
        "invalid independent EMI metadata size",
    )
    count = int.from_bytes(metadata[66:68], "little")
    require(0 < count <= 64, "invalid independent EMI channel count")
    offset = 68
    channels = []
    for _ in range(count):
        require(
            offset + 6 <= len(metadata) and metadata[offset : offset + 4] == bytes(4),
            "EMI is not picowatt-hours",
        )
        size = int.from_bytes(metadata[offset + 4 : offset + 6], "little")
        offset += 6
        require(
            size > 0 and size % 2 == 0 and offset + size <= len(metadata),
            "truncated independent EMI channel",
        )
        text = metadata[offset : offset + size].decode("utf-16le")
        offset += size
        name, separator, padding = text.partition("\0")
        require(
            name and separator and not padding.strip("\0") and name not in channels,
            "ambiguous EMI channel name",
        )
        channels.append(name)
    require(offset == len(metadata), "trailing independent EMI metadata")
    return channels


def validate_independent(stages, independent, run_id):
    require(independent["run_id"] == run_id, "independent probe belongs to another run")
    enabled = next(s for s in stages if s["name"] == "enabled")["frames"]
    start = utc(independent["started_utc"])
    end = utc(independent["finished_utc"])
    require(
        0 < end - start <= 120
        and utc(enabled[0]["observed_utc"]) <= start
        and end <= utc(enabled[-1]["observed_utc"]),
        "independent probes are not contemporaneous with enabled app frames",
    )
    thermal = independent["thermal"]
    require(
        thermal["elevated"] is True
        and thermal["open_error"] == 0
        and thermal["load_error"] == 0
        and start <= utc(thermal["observed_utc"]) <= end,
        "independent thermal source failed or is historical",
    )
    temperatures = []
    require(len(thermal["samples"]) >= 3, "too few independent temperatures")
    for sample in thermal["samples"]:
        for key, register in (("target", 0x1A2), ("package", 0x1B1)):
            raw = sample[key]
            require(
                raw["register"] == register
                and raw["ok"] is True
                and raw["error"] == 0
                and raw["returned"] == 8,
                "wrong independent thermal register or failed read",
            )
        temperatures.append(
            temperature(sample["target"]["value"], sample["package"]["value"])
        )
    observed = [
        next(
            r["value"]
            for r in f["snapshot"]["readings"]
            if r["sensor_id"] == THERMAL_ID
        )
        for f in enabled
        if start <= utc(f["observed_utc"]) <= end
    ]
    require(
        len(observed) >= 3
        and min(observed) <= max(temperatures) + 5
        and max(observed) >= min(temperatures) - 5,
        "independent CPU package temperature disagrees",
    )
    emi = independent["emi"]
    channels = emi_channels(emi)
    instance = emi["instance"].upper()
    require(
        instance and instance.replace("\\", "#").lower() in emi["path"].lower(),
        "EMI instance differs from opened interface",
    )
    require(len(emi["samples"]) >= 3, "too few independent EMI samples")
    samples = []
    for reply in emi["samples"]:
        data = reply_bytes(reply, len(channels) * 16)
        samples.append(
            [
                (
                    int.from_bytes(data[i : i + 8], "little"),
                    int.from_bytes(data[i + 8 : i + 16], "little"),
                )
                for i in range(0, len(data), 16)
            ]
        )
    supported = 0
    for index, channel in enumerate(channels):
        if not re.fullmatch(r"RAPL_Package[0-9]+_(PKG|DRAM|PP0|PP1)", channel):
            continue
        sid = f"cpu:host/emi:{len(instance)}:{instance}:{len(channel)}:{channel}/power"
        values = []
        for a, b in zip(samples, samples[1:]):
            ae, at = a[index]
            be, bt = b[index]
            require(
                bt > at and be >= ae,
                "independent EMI counter reset or nonadvancing clock",
            )
            if ae > 0:
                values.append((be - ae) * 0.036 / (bt - at))
        readings = [
            next((r for r in f["snapshot"]["readings"] if r["sensor_id"] == sid), None)
            for f in enabled
            if start <= utc(f["observed_utc"]) <= end
        ]
        require(
            all(r is not None for r in readings),
            "independently observable EMI channel was omitted",
        )
        app_times = [
            o["integers"]["absolute_time_100ns"]
            for r in readings
            for o in r["observations"]
        ]
        probe_times = [sample[index][1] for sample in samples]
        require(
            app_times
            and min(app_times) <= max(probe_times) + 20_000_000
            and max(app_times) >= min(probe_times) - 20_000_000,
            "independent EMI raw clock is historical or from another capture",
        )
        current = [r["value"] for r in readings if r["availability"] == "Available"]
        if values:
            supported += 1
            require(len(current) >= 3, "supported EMI source never became current")
            tolerance = max(2.0, max(values) * 0.2)
            require(
                min(current) <= max(values) + tolerance
                and max(current) >= min(values) - tolerance,
                "independent EMI watts disagree",
            )
        else:
            require(
                not current
                and all(r["value"] is None and r["reason"] for r in readings),
                "unsupported zero EMI counter became measured power",
            )
    require(
        supported > 0, "unsupported-only EMI output cannot establish real collection"
    )


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def artifact(root, name):
    path = Path(name)
    require(
        isinstance(name, str)
        and name
        and not path.is_absolute()
        and not any(part in ("..", "") for part in path.parts)
        and "\\" not in name
        and ":" not in name,
        "unsafe evidence artifact path",
    )
    resolved = (root / path).resolve()
    require(
        resolved.is_relative_to(root.resolve())
        and (root / path).is_file()
        and not (root / path).is_symlink(),
        "missing or redirected evidence artifact: " + name,
    )
    return root / path


def verify_hashes(root, hashes):
    require(isinstance(hashes, dict) and hashes, "artifact hashes are missing")
    for name, digest in hashes.items():
        require(
            re.fullmatch(r"[a-f0-9]{64}", digest) is not None
            and hashlib.sha256(artifact(root, name).read_bytes()).hexdigest() == digest,
            "artifact changed: " + name,
        )


def validate_platforms(root, record):
    from performance_verify import same_production

    for platform in ("linux", "macos", "windows"):
        entry = record[platform]
        same_production(entry["source_commit"])
        for name in ("tests", "clippy"):
            check = entry["checks"][name]
            require(
                check["exit_code"] == 0 and type(check["exit_code"]) is int,
                "platform check failed: " + platform + "/" + name,
            )
            command = check["command"]
            require(
                isinstance(command, list)
                and command[:2] == ["cargo", "test" if name == "tests" else "clippy"]
                and "--locked" in command,
                "wrong preservation command",
            )
            require(
                all(
                    package in command
                    for package in (
                        "system-pulse",
                        "system-pulse-model",
                        "system-pulse-collectors",
                    )
                ),
                "platform check omitted preserved packages",
            )
            verify_hashes(root, {check["log"]: check["sha256"]})
            log = artifact(root, check["log"]).read_text(errors="replace")
            require(
                not re.search(r"test result: FAILED|error: could not compile", log),
                "platform log contains a failure",
            )
            if name == "tests":
                counts = [
                    int(n) for n in re.findall(r"test result: ok\. (\d+) passed", log)
                ]
                require(sum(counts) > 0, "platform tests have no actual passing cases")
            else:
                require(
                    "Finished `" in log or "cargo clippy: No issues found" in log,
                    "Clippy completion is missing",
                )


def validate_capture_time(frame):
    snapshot = frame["snapshot"]
    anchor = snapshot["clock_anchor"]
    middle = (anchor["monotonic_before_ns"] + anchor["monotonic_after_ns"]) / 2
    capture = (anchor["unix_ns"] + snapshot["capture_finished_ns"] - middle) / 1e9
    require(
        -0.1 <= utc(frame["observed_utc"]) - capture <= 3,
        "diagnostic frame is stale relative to its own clock anchor",
    )


def visible(ui):
    return " ".join(c["name"] for c in ui["controls"] if not c["offscreen"])


def validate_normal(record, inventory):
    require(
        record["elevated"] is False and record["diagnostics_enabled"] is False,
        "normal UI was elevated or diagnostic",
    )
    for key in ("normal_rows", "diagnostic_rows"):
        rows = record[key]
        require(
            rows
            and any(type(r["pid"]) is int and r["pid"] > 0 for r in rows)
            and all(r["pid"] >= 0 and r["name"] for r in rows),
            "native process rows were lost",
        )
    for key in ("gpu", "normal_gpu"):
        ui = record[key]
        text = visible(ui)
        require(
            ui["selected_screen"] == "GPU" and ui["pid"] > 0,
            "normal GPU page was not observed",
        )
        require(
            all(
                label in text
                for label in (
                    "GPU utilization",
                    "Dedicated GPU memory",
                    "Shared GPU memory",
                    "Unavailable",
                )
            )
            and any(device["Name"] in text for device in inventory),
            "native GPU labels or adapter disappeared",
        )
    quit_result = record["quit"]
    require(
        quit_result["exit_code"] == 0
        and quit_result["pid"]
        == quit_result["menu_owner"]
        == record["normal_gpu"]["pid"],
        "normal tray Quit did not close its own application",
    )


def validate_installer(root, binary_hash):
    from performance_verify import same_production, check_harness

    receipt = load(artifact(root, "receipt.json"))
    same_production(receipt["source_commit"])
    require(
        receipt["signed_binary_sha256"] == binary_hash,
        "installer lifecycle used a different application",
    )
    check_harness(receipt["harness_sha256"], ("windows_installer_verify.ps1",))
    hashes = receipt["artifacts_sha256"]
    require(
        {"manifest.json", "fresh/result.json", "existing/result.json"} <= hashes.keys(),
        "installer lifecycle artifacts are incomplete",
    )
    verify_hashes(root, hashes)
    manifest = load(root / "manifest.json")
    require(
        manifest["source_commit"] == receipt["source_commit"]
        and manifest["binary_sha256"] == binary_hash
        and re.fullmatch(r"[a-f0-9]{64}", manifest["installer_sha256"]),
        "installer manifest identity differs from lifecycle receipt",
    )
    require(
        manifest["pawnio_sha256"]
        == "1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032",
        "installer prerequisite differs from pinned official PawnIO",
    )
    for name in ("application_signature", "installer_signature", "pawnio_signature"):
        signature = manifest[name]
        require(
            signature["status"] == "Valid"
            and signature["subject"]
            and re.fullmatch(r"[A-Fa-f0-9]{40}", signature["thumbprint"]),
            "installer component signature is invalid",
        )
    for name, fresh in (("fresh", True), ("existing", False)):
        result = load(root / name / "result.json")
        require(
            result["status"] == "PASS"
            and all(
                type(result[key]) is int and result[key] == 0
                for key in (
                    "install_exit",
                    "existing_driver_install_exit",
                    "uninstall_exit",
                )
            )
            and result["owned_directory_removed"] is True,
            "installer lifecycle failed or left application files",
        )
        require(
            result["binary_sha256"] == binary_hash
            and result["installer_sha256"] == manifest["installer_sha256"]
            and result["installer_signer"] == manifest["installer_signature"]["subject"]
            and result["application_signer"]
            == manifest["application_signature"]["subject"]
            and result["uninstaller_signer"]
            == manifest["application_signature"]["subject"],
            "installed component identity differs from signed manifest",
        )
        before, after = result["shared_driver_before"], result["shared_driver_after"]
        require(
            result["fresh_driver_installed"] is fresh
            and isinstance(after, dict)
            and (before is None if fresh else before == after)
            and after.get("version") == "2.2.0.0"
            and after.get("start_mode") == "Manual"
            and after.get("state") == "Running"
            and after.get("driver_path")
            and after.get("location"),
            "installer removed or changed the shared PawnIO driver",
        )


def validate_evidence(evidence):
    from performance_verify import ROOT, same_production, check_harness
    from release_ci_verify import archive_files, verify_archive
    from windows_thermal_energy_collect import HARNESSES, signed_build_identity
    from windows_process_actions_collect import (
        HARNESS_FILES,
        ORDINARY_CASES,
        build_identity,
    )
    from windows_process_actions_verify import validate_ordinary_actions
    from windows_gpu_verify import (
        validate_snapshot,
        validate_scheduler,
        validate_memory,
    )

    record = load(evidence / "receipt.json")
    same_production(record["source_commit"])
    require(
        re.fullmatch(r"[a-f0-9]{32}", record["run_id"]) is not None
        and record["status"] == "PASS"
        and record["elevated"] is False
        and record["cleanup"] is True,
        "native run did not finish unelevated and cleanly",
    )
    check_harness(record["harness_sha256"], HARNESSES)
    verify_hashes(evidence, record["artifacts_sha256"])
    screenshots = {
        "off.png",
        "denied.png",
        "enabled.png",
        "disabled.png",
        "helper-exit.png",
        "energy.png",
        "gpu.png",
        "normal-energy.png",
        "normal-thermals.png",
        "normal-gpu.png",
    }
    required = screenshots | {
        "result.json",
        "stages.json",
        "independent.json",
        "inventory.json",
        "preservation.json",
        "energy-ui.json",
        "build.json",
        "package.json",
        "windows-build.log",
    }
    require(
        required <= record["artifacts_sha256"].keys(),
        "native thermal artifacts are incomplete",
    )
    result = load(evidence / "result.json")
    for key in (
        "run_id",
        "source_commit",
        "binary_sha256",
        "started_utc",
        "finished_utc",
        "elevated",
        "cleanup",
        "signature",
    ):
        require(
            result[key] == record[key],
            "receipt differs from original native observation",
        )
    revision, unsigned = build_identity(
        (evidence / "windows-build.log").read_text(errors="replace")
    )
    require(revision == record["source_commit"], "native build source differs")
    package = verify_archive(evidence / "package", "x86_64-pc-windows-msvc", revision)
    require(
        package == load(evidence / "package.json"),
        "verified package differs from observation",
    )
    files = archive_files(evidence / "package" / package["archive"])
    build = load(evidence / "build.json")
    require(
        build == json.loads(files["build.json"]),
        "build receipt differs from signed package",
    )
    signed = hashlib.sha256(files["system-pulse.exe"]).hexdigest()
    signed_build_identity(build, revision, unsigned, signed)
    require(
        signed == record["binary_sha256"]
        and result["signature"] == build["authenticode"],
        "native signature or executable differs from package",
    )
    validate_installer(evidence / "installer", signed)
    stages = load(evidence / "stages.json")
    validate_stages(stages)
    inventory = load(evidence / "inventory.json")
    require(
        len(inventory["cpu"]) == 1 and "Intel" in inventory["cpu"][0]["Manufacturer"],
        "tablet physical package scope differs",
    )
    finished = 0
    for stage in stages:
        chronological_frames = (
            [stage["before_exit"], *stage["frames"]]
            if stage["name"] == "helper-exit"
            else stage["frames"]
        )
        for frame in chronological_frames:
            validate_capture_time(frame)
            require(
                frame["snapshot"]["capture_finished_ns"] > finished,
                "collector clock did not advance",
            )
            finished = frame["snapshot"]["capture_finished_ns"]
            validate_snapshot(frame["snapshot"], inventory["gpu"])
    enabled = next(s for s in stages if s["name"] == "enabled")["frames"]
    for reading in enabled[-1]["snapshot"]["readings"]:
        sid = reading["sensor_id"]
        if sid.startswith("windows-gpu:"):
            if sid.endswith("/usage"):
                validate_scheduler(reading)
            elif sid.endswith(("/vram", "/shared-used")):
                validate_memory(reading, sid.endswith("/shared-used"))
    independent = load(evidence / "independent.json")
    validate_independent(stages, independent, record["run_id"])
    probes = independent["probe_sha256"]
    require(
        set(probes) == {"emi-probe.ps1", "pawnio-temperature-probe.ps1"},
        "independent probe provenance missing",
    )
    for name, digest in probes.items():
        require(
            hashlib.sha256(
                (ROOT / "docs/execution/windows-thermal-energy" / name).read_bytes()
            ).hexdigest()
            == digest,
            "independent probe source changed",
        )
    preservation = load(evidence / "preservation.json")
    validate_normal(preservation, inventory["gpu"])
    for ui in (load(evidence / "energy-ui.json"), preservation["normal_energy"]):
        require(
            ui["selected_screen"] == "Energy"
            and "RAPL_Package" in visible(ui)
            and re.search(r"\bW\b", visible(ui)),
            "native Energy domains or watts absent",
        )
    require(
        preservation["normal_thermals"]["selected_screen"] == "Thermals"
        and "CPU package temperature" in visible(preservation["normal_thermals"])
        and "off" in visible(preservation["normal_thermals"]).lower(),
        "normal launch retained privileged thermal access",
    )
    review = load(evidence / "visual-review.json")
    require(
        review["source_commit"] == revision
        and review["binary_sha256"] == signed
        and review["reviewer"],
        "visual review is not bound to candidate",
    )
    for name in screenshots:
        item = review["screenshots"][name]
        require(
            item["sha256"] == record["artifacts_sha256"][name]
            and item["readable"] is True
            and item["findings"] == [],
            "native screenshot lacks clean independent review: " + name,
        )
    platforms = load(evidence / "platform-preservation.json")
    validate_platforms(evidence, platforms)
    action_root = artifact(
        evidence, platforms["windows"]["process_actions"]["receipt"]
    ).parent
    action_record = load(
        artifact(evidence, platforms["windows"]["process_actions"]["receipt"])
    )
    require(
        hashlib.sha256(
            artifact(
                evidence, platforms["windows"]["process_actions"]["receipt"]
            ).read_bytes()
        ).hexdigest()
        == platforms["windows"]["process_actions"]["sha256"],
        "process-action receipt changed",
    )
    same_production(action_record["source_commit"])
    require(
        action_record["binary_sha256"] == signed,
        "process controls exercised another binary",
    )
    require(
        action_record["package"] == package
        and action_record["build_log_sha256"]
        == record["artifacts_sha256"]["windows-build.log"],
        "process controls used another package/build receipt",
    )
    check_harness(action_record["harness_sha256"], HARNESS_FILES)
    action_artifacts = {
        case["name"] + suffix
        for case in ORDINARY_CASES
        for suffix in ("-confirmation.png", "-result.png")
    } | {"app.stderr"}
    require(
        action_artifacts <= action_record["artifacts_sha256"].keys(),
        "process-action artifacts are incomplete",
    )
    verify_hashes(action_root, action_record["artifacts_sha256"])
    require(
        not artifact(action_root, "app.stderr").read_text().strip(),
        "native process-action app reported an error",
    )
    validate_ordinary_actions(action_record)


def main():
    from performance_verify import ROOT

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=ROOT / "docs/execution/windows-thermal-energy/native",
    )
    args = parser.parse_args()
    subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "scripts/system-pulse",
            "-p",
            "test_windows_thermal_energy_verify.py",
        ],
        cwd=ROOT,
        check=True,
    )
    validate_evidence(args.evidence)
    print(
        "PASS WTE-001: source-bound native package temperature, EMI watts, consent lifecycle and platform preservation"
    )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        StopIteration,
        InvalidMeasurement,
    ) as error:
        print(
            "Windows thermal/energy evidence incomplete or invalid: " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(1)
