"""Require native, source-bound Windows GPU discovery and reading evidence."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

from performance_compare import require
from performance_verify import ROOT, same_production, check_harness
from windows_process_actions_collect import build_identity
from windows_gpu_collect import HARNESSES


def validate_snapshot(snapshot, inventory):
    expected = {
        "windows-gpu:" + device["PNPDeviceID"].upper()
        for device in inventory
        if device["Status"] == "OK" and re.match(
            r"PCI\\VEN_(8086|1002|10DE)&", device["PNPDeviceID"], re.IGNORECASE)
    }
    require(expected, "independent inventory has no healthy supported adapter")
    monitors = [m for m in snapshot["monitors"] if m["kind"] == "Gpu"]
    ids = [m["id"] for m in monitors]
    require(len(ids) == len(set(ids)), "duplicate GPU monitor")
    require(set(ids) == expected, "GPU discovery differs from independent Windows inventory")
    sensors = {s["id"]: s for s in snapshot["sensors"]}
    readings = {r["sensor_id"]: r for r in snapshot["readings"]}
    require(len(sensors) == len(snapshot["sensors"]), "duplicate sensor identity")
    require(len(readings) == len(snapshot["readings"]), "duplicate reading identity")
    for monitor in monitors:
        require(monitor["summary_sensor_id"] == monitor["id"] + "/usage", "wrong GPU summary identity")
        for suffix in ("usage", "vram", "shared-used", "temperature", "power", "clock-graphics", "clock-memory"):
            sid = monitor["id"] + "/" + suffix
            require(sid in sensors and sid in readings, "missing explicit GPU reading: " + suffix)
            require(sensors[sid]["monitor_id"] == monitor["id"], "sensor belongs to another adapter")
            reading = readings[sid]
            if reading["availability"] == "Available":
                value = reading["value"]
                require(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0,
                        "invalid measured GPU value")
                require(reading["observations"], "GPU reading lacks raw source observations")
                if suffix == "usage":
                    require(value <= 100, "GPU utilization exceeds 100 percent")
                if suffix == "shared-used":
                    require(reading["total"] is None and sensors[sid]["kind"] == "Scalar",
                            "shared memory was represented as dedicated capacity")
                if suffix == "vram" and reading["total"] is not None:
                    require(value <= reading["total"], "dedicated GPU memory exceeds capacity")
            else:
                require(reading["availability"] in ("WarmingUp", "Unavailable", "Failed"),
                        "invalid GPU availability")
                require(reading["value"] is None and reading["reason"],
                        "missing GPU reading is fabricated or unexplained")
    return expected


def validate_scheduler(reading):
    """Recompute busiest-engine usage from the exact retained integer operands."""
    require(reading["availability"] == "Available", "native GPU utilization never became current")
    observations = reading["observations"]
    require(len(observations) >= 2 and len(observations) % 2 == 0, "missing paired scheduler observations")
    percentages = []
    seen = set()
    for previous, current in zip(observations[::2], observations[1::2]):
        a, b = previous["integers"], current["integers"]
        key = (b["adapter_luid"], b["node_id"])
        require(key == (a["adapter_luid"], a["node_id"]) and key not in seen,
                "GPU node identity changed or was repeated")
        seen.add(key)
        elapsed = current["captured_ns"] - previous["captured_ns"]
        ticks = b["running_ticks"] - a["running_ticks"]
        require(elapsed > 0 and ticks >= 0, "invalid scheduler baseline")
        percent = ticks * 10000 / elapsed
        require(percent <= 100.5, "GPU scheduler time exceeds wall time")
        percentages.append(min(percent, 100))
    require(math.isclose(reading["value"], max(percentages), rel_tol=1e-9, abs_tol=1e-9),
            "GPU utilization differs from scheduler operands")


def validate_memory(reading, shared):
    require(reading["availability"] == "Available", "native GPU memory is not current")
    require(len(reading["observations"]) == 1, "missing graphics memory observation")
    values = reading["observations"][0]["integers"]
    field = "shared_bytes" if shared else "dedicated_bytes"
    require(reading["value"] == values[field], "GPU memory differs from resident bytes")
    expected_total = None if shared or values["dedicated_limit_bytes"] == 0 else values["dedicated_limit_bytes"]
    require(reading["total"] == expected_total, "wrong GPU memory capacity scope")


def validate_independent(frames, samples):
    """Compare the capture window with separate Windows performance counters."""
    require(len(samples) >= 8, "insufficient independent counter observations")
    independent = {}
    for sample in samples:
        engines = {}
        for counter in sample["counters"]:
            match = re.search(r"luid_0x([0-9a-f]{8})_0x([0-9a-f]{8})_phys_(\d+)", counter["instance"], re.IGNORECASE)
            if not match or counter["status"] not in (0, 1):
                continue
            luid = (int(match[1], 16) << 32) | int(match[2], 16)
            value = counter["value"]
            require(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0,
                    "invalid independent graphics counter")
            path = counter["path"].lower()
            if path.endswith("\\dedicated usage") or path.endswith("\\shared usage"):
                suffix = "shared-used" if path.endswith("\\shared usage") else "vram"
                independent.setdefault((luid, suffix), []).append(value)
            elif path.endswith("\\utilization percentage"):
                engine = re.search(r"_eng_(\d+)_", counter["instance"], re.IGNORECASE)
                require(engine is not None, "GPU engine counter lacks engine identity")
                key = (luid, int(match[3]), int(engine[1]))
                engines[key] = engines.get(key, 0) + value
        busiest = {}
        for (luid, _, _), value in engines.items():
            busiest[luid] = max(busiest.get(luid, 0), value)
        for luid, value in busiest.items():
            independent.setdefault((luid, "usage"), []).append(value)
    for monitor in [m for m in frames[-1]["monitors"] if m["kind"] == "Gpu"]:
        readings = {r["sensor_id"]: r for r in frames[-1]["readings"]}
        usage = readings[monitor["id"] + "/usage"]
        luid = usage["observations"][-1]["integers"]["adapter_luid"]
        for suffix in ("usage", "vram", "shared-used"):
            reference = independent.get((luid, suffix), [])
            require(len(reference) >= 4, "no independent counters for the detected adapter: " + suffix)
            observed = [r["value"] for frame in frames for r in frame["readings"]
                        if r["sensor_id"] == monitor["id"] + "/" + suffix and r["availability"] == "Available"]
            require(len(observed) >= 3, "insufficient current GPU observations: " + suffix)
            # The two sources are sampled in one short window, not atomically.
            # Compare their observed ranges with fixed rounding/churn tolerances.
            tolerance = 5.0 if suffix == "usage" else 32 * 1024 * 1024
            require(min(observed) <= max(reference) + tolerance and max(observed) >= min(reference) - tolerance,
                    "independent Windows counter range disagrees: " + suffix)


def validate_ui(record, inventory):
    require(record["selected_screen"] == "GPU" and record["pid"] > 0 and record["sequence"] > 0,
            "GPU page was not observed")
    names = [c["name"] for c in record["controls"] if not c["offscreen"]]
    require(any("GPU utilization" in name for name in names), "GPU utilization is absent from native UI")
    require(any("Dedicated GPU memory" in name for name in names), "dedicated memory label is absent")
    require(any("Shared GPU memory" in name for name in names), "shared memory label is absent")
    require(any("Unavailable" in name for name in names), "unsupported vendor readings lack visible availability")
    require(any(device["Name"] in name for device in inventory for name in names), "detected adapter name is absent from UI")


def validate_preservation(record, inventory):
    require(record["diagnostics_enabled"] is False, "normal launch enabled diagnostics")
    for key in ("diagnostic_rows", "normal_rows"):
        rows = record[key]
        require(rows and all(row["pid"] > 0 and row["name"] for row in rows),
                "native process table lost its rows")
    validate_ui(record["normal_gpu"], inventory)
    quit_result = record["quit"]
    require(quit_result["exit_code"] == 0 and quit_result["pid"] == quit_result["menu_owner"]
            == record["normal_gpu"]["pid"], "normal native launch did not quit cleanly")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=ROOT / "docs/execution/windows-gpu-detection/native")
    args = parser.parse_args()
    subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "scripts/system-pulse",
                    "-p", "test_windows_gpu_verify.py"], cwd=ROOT, check=True)
    evidence = args.evidence
    record = json.loads((evidence / "receipt.json").read_text())
    same_production(record["source_commit"])
    revision, binary = build_identity((evidence / "windows-build.log").read_text(errors="replace"))
    require(revision == record["source_commit"] and binary == record["binary_sha256"], "GPU evidence build mismatch")
    require(record["elevated"] is False and record["cleanup"] is True, "native run was elevated or left its process alive")
    check_harness(record["harness_sha256"], HARNESSES)
    for name, digest in record["artifacts_sha256"].items():
        require(Path(name).name == name and name not in (".", ".."), "unsafe GPU artifact path")
        require(hashlib.sha256((evidence / name).read_bytes()).hexdigest() == digest, "GPU artifact changed: " + name)
    # The final collection runner must provide all of these observations. Partial
    # captures deliberately cannot turn an implemented collector into acceptance.
    required = {"inventory.json", "frames.json", "gpu.png", "gpu-ui.json", "normal-gpu.png",
                "independent-readings.json", "preservation.json", "package.json", "windows-build.log"}
    require(required <= record["artifacts_sha256"].keys(), "native GPU evidence is incomplete")
    inventory = json.loads((evidence / "inventory.json").read_text())
    frames = json.loads((evidence / "frames.json").read_text())
    require(len(frames) >= 3, "insufficient native sampling observations")
    previous = 0
    for frame in frames:
        require(frame["sequence"] > previous, "native GPU sampling did not advance")
        previous = frame["sequence"]
        validate_snapshot(frame, inventory)
    for reading in frames[-1]["readings"]:
        if reading["sensor_id"].startswith("windows-gpu:"):
            if reading["sensor_id"].endswith("/usage"):
                validate_scheduler(reading)
            elif reading["sensor_id"].endswith(("/vram", "/shared-used")):
                validate_memory(reading, reading["sensor_id"].endswith("/shared-used"))
    validate_independent(frames, json.loads((evidence / "independent-readings.json").read_text()))
    validate_ui(json.loads((evidence / "gpu-ui.json").read_text()), inventory)
    validate_preservation(json.loads((evidence / "preservation.json").read_text()), inventory)
    package = json.loads((evidence / "package.json").read_text())
    require(package["target"] == "x86_64-pc-windows-msvc" and package["source_commit"] == revision
            and re.fullmatch(r"[a-f0-9]{64}", package["sha256"]), "wrong verified Windows package")
    review = json.loads((evidence / "visual-review.json").read_text())
    require(review["source_commit"] == revision and review["binary_sha256"] == binary,
            "visual review covers another build")
    for name in ("gpu.png", "normal-gpu.png"):
        observed = review["screenshots"][name]
        require(observed["sha256"] == record["artifacts_sha256"][name]
                and observed["readable"] is True and observed["findings"] == [],
                "native GPU screenshot lacks a clean visual review")
    # These tests include non-Windows NVML behavior, Apple/Intel boundaries,
    # persistence and the Windows inventory/telemetry failure demonstrations.
    subprocess.run(["cargo", "test", "--locked", "-p", "system-pulse", "-p",
                    "system-pulse-model", "-p", "system-pulse-collectors"], cwd=ROOT, check=True)
    print("PASS WGPU-001: native inventory, independent readings, packaged UI and preservation")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Windows GPU evidence incomplete or invalid: {error}", file=sys.stderr)
        raise SystemExit(1)
