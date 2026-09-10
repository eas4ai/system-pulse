"""Validate retained Windows runtime observations against the committed source."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from performance_compare import require
from performance_verify import ROOT, check_harness, same_production

HARNESSES = ("windows_runtime.ps1", "windows_runtime_collect.py")
SCREENSHOTS = ("summary.png", "gpu.png", "thermals.png", "energy.png", "processes.png",
               "restored-settings.png", "diagnostic-menu.png", "normal-menu.png")
ARTIFACTS = (*SCREENSHOTS, "initial.json", "final.json", "saved-state.json",
             "diagnostic.stdout", "diagnostic.stderr", "normal.stdout", "normal.stderr")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_interactions(record):
    require(record["status"] == "PASS" and record["elevated"] is False,
            "native runtime did not pass as a standard user")
    require(re.fullmatch(r"[a-f0-9]{32}", record["run_id"]), "missing run identity")
    require([screen["screen"] for screen in record["screens"]] ==
            ["Summary", "CPU", "Memory", "GPU", "Disks", "Network", "Energy", "Thermals", "Processes", "Settings"]
            and all(screen["selected"] is True for screen in record["screens"]),
            "native navigation is incomplete")
    pid = record["diagnostic_pid"]
    require(isinstance(pid, int) and pid > 0, "invalid diagnostic process identity")
    filtered = record["filtered_rows"]
    require(len(filtered) == 1 and filtered[0]["pid"] == pid and
            filtered[0]["name"] == "system-pulse.exe", "native process filtering failed")
    sorted_rows = record["sorted_rows"]
    require(len(sorted_rows) == 2, "missing PID sort directions")
    for rows, descending in zip(sorted_rows, (False, True)):
        pids = [row["pid"] for row in rows]
        require(len(pids) > 1 and len(pids) == len(set(pids)) and
                pids == sorted(pids, reverse=descending), "native PID order is incorrect")
    reopen = record["reopen"]
    require(reopen["pid"] == pid and reopen["hidden"] is True and reopen["visible"] is True
            and reopen["old_window"] > 0 and reopen["new_window"] > 0
            and reopen["old_window"] != reopen["new_window"], "tray did not recreate the dashboard")
    normal = record["normal"]
    require(normal["pid"] > 0 and normal["pid"] != pid and normal["diagnostics_enabled"] is False
            and normal["settings_restored"] is True and len(normal["rows"]) > 1,
            "normal restart, persistence or process data was not verified")
    require(re.fullmatch(r"Live system data.*\d+ readable processes.*2 s update", normal["status"]),
            "normal live status is missing")
    for quit_record, expected_pid in ((record["diagnostic_quit"], pid), (normal["quit"], normal["pid"])):
        require(quit_record == {"pid": expected_pid, "menu_owner": expected_pid, "exit_code": 0},
                "native tray Quit did not exit the tested process cleanly")


def validate_readings(initial, final, record):
    pid = record["diagnostic_pid"]
    require(initial["application_pid"] == final["application_pid"] == pid,
            "diagnostics came from another process")
    require(final["snapshot"]["sequence"] > initial["snapshot"]["sequence"] > 0
            and final["accepted_unix_ns"] > initial["accepted_unix_ns"], "host sampling did not advance")
    for frame in (initial, final):
        snapshot = frame["snapshot"]
        readings = {reading["sensor_id"]: reading for reading in snapshot["readings"]}
        cpu, memory = readings["cpu:host/usage"], readings["memory:host/used"]
        require(cpu["availability"] == memory["availability"] == "Available" and
                0 <= cpu["value"] <= 100 and 0 < memory["value"] <= memory["total"],
                "CPU or memory has no valid live reading")
        require(memory["total"] == record["host"]["visible_memory_bytes"],
                "memory total disagrees with the native OS")
        logical = sum(cpu["NumberOfLogicalProcessors"] for cpu in record["host"]["cpu"])
        require(len([sensor for sensor in snapshot["sensors"]
                     if re.fullmatch(r"cpu:host/core-\d+-usage", sensor["id"])]) == logical,
                "logical CPU count disagrees with the native OS")
        kinds = {monitor["kind"] for monitor in snapshot["monitors"]}
        require({"Cpu", "Memory", "Network", "Volume"} <= kinds, "expected host monitors are missing")
        require("Gpu" not in kinds, "unexpected GPU readings on the unsupported Intel Windows backend")
        for sensor in snapshot["sensors"]:
            if sensor["kind"] in ("Temperature", "Power"):
                require(readings[sensor["id"]]["availability"] != "Available",
                        "unsupported thermal or energy measurement is presented as available")
        own = [process for process in snapshot["processes"] if process["identity"]["pid"] == pid]
        require(len(own) == 1 and own[0]["name"] == "system-pulse.exe" and
                own[0]["memory_bytes"]["value"] > 0, "live process snapshot lacks the running app")
        require(any(item["backend"] == "nvml" and item["availability"] == "Failed"
                    and item["reason"] for item in snapshot["diagnostics"]),
                "unavailable NVIDIA backend was not reported")


def validate_artifacts(evidence, record):
    hashes = record["artifacts_sha256"]
    require(set(ARTIFACTS) <= hashes.keys(), "runtime artifacts are incomplete")
    for name, digest in hashes.items():
        require(Path(name).name == name and name not in (".", ".."), "invalid artifact path")
        require(hashlib.sha256((evidence / name).read_bytes()).hexdigest() == digest,
                "runtime artifact changed: " + name)
    for name in ("diagnostic.stderr", "normal.stderr"):
        require(not (evidence / name).read_text().strip(), "application reported an error: " + name)
    review = read_json(evidence / "visual-review.json")
    require(review["run_id"] == record["run_id"] and review["status"] == "PASS"
            and review["screenshots_sha256"] == {name: hashes[name] for name in SCREENSHOTS},
            "screenshots have not been reviewed for this run")
    require(review["unavailable_screens"] == ["GPU", "Thermals", "Energy"] and
            review["menu_commands"] == ["Open System Pulse", "Quit"],
            "native availability or tray menu review is incomplete")


def main():
    subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s",
                    "scripts/system-pulse", "-p", "test_windows_runtime_verify.py"], cwd=ROOT, check=True)
    evidence = Path(os.environ.get("SYSTEM_PULSE_WINDOWS_RUNTIME_EVIDENCE",
                                  ROOT / "docs/execution/release-candidate-readiness/runtime"))
    record = read_json(evidence / "result.json")
    require(re.fullmatch(r"[a-f0-9]{64}", record["binary_sha256"]), "invalid executable digest")
    same_production(record["source_commit"])
    check_harness(record["harness_sha256"], HARNESSES)
    build_logs = list((ROOT / ".cairn/evidence/REL-001").glob("*.out"))
    matching = [path for path in build_logs
                if hashlib.sha256(path.read_bytes()).hexdigest() == record["build_log_sha256"]]
    require(len(matching) == 1, "runtime is not tied to its retained Windows build")
    log = matching[0].read_text()
    require(f"PASS REL-001 {record['source_commit']}" in log and
            re.search(r"Hash\s*:\s*" + re.escape(record["binary_sha256"]), log, re.IGNORECASE),
            "runtime executable differs from the passing Windows build")
    validate_interactions(record)
    validate_artifacts(evidence, record)
    state = read_json(evidence / "saved-state.json")
    require(state["appearance"] == {"theme": "light", "ui_font": "ibm_plex_sans", "numeric_font": "ibm_plex_mono"}
            and state["interval_ms"] == 2000 and state["screens"]["active"] == "settings",
            "settings were not saved")
    validate_readings(read_json(evidence / "initial.json"), read_json(evidence / "final.json"), record)
    print("cairn: REL-002: pass")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Windows runtime evidence incomplete or invalid: {error}", file=sys.stderr)
        raise SystemExit(1)
