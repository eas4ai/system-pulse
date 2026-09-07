"""Validate native CPU receipts before comparing the two release binaries."""

import math
import re


class InvalidMeasurement(ValueError):
    """A receipt cannot support a performance claim."""


def require(condition, message):
    if not condition:
        raise InvalidMeasurement(message)


def number(value, label):
    require(type(value) in (int, float), f"{label}: expected a number")
    require(math.isfinite(value) and value >= 0, f"{label}: invalid number")
    return value


def compare(receipt):
    require(receipt.get("version") == 1, "unsupported receipt version")
    host = receipt.get("host", {})
    require(host.get("logical_cpus") == 8, "wrong comparison hardware")
    require(host.get("chip") == "Apple M1 Pro", "wrong comparison chip")
    require(bool(host.get("os_version")), "missing OS version")
    require(bool(host.get("power_source")), "missing power source")
    binaries = receipt.get("binaries", {})
    require(set(binaries) == {"reference", "candidate"}, "missing binary identity")
    for label, binary in binaries.items():
        require(re.fullmatch(r"[a-f0-9]{64}", binary.get("sha256", "")),
                f"{label}: invalid binary hash")
        require(re.fullmatch(r"[a-f0-9]{40}", binary.get("commit", "")),
                f"{label}: invalid source commit")
        require(binary.get("release_locked") is True, f"{label}: wrong build")
    require(binaries["reference"]["commit"] ==
            "af243cf2dba5eb6c4cb19397c522c38eda640f45", "wrong reference revision")
    runs = receipt.get("runs", [])
    require(len(runs) == 12, "exactly twelve observations are required")
    totals = {(mode, label): [0.0, 0.0]
              for mode in ("summary", "tray") for label in binaries}
    seen = set()
    last_end = -1
    for index, run in enumerate(runs):
        mode, label, repetition = run.get("mode"), run.get("binary"), run.get("repetition")
        require(mode in ("summary", "tray") and label in binaries, "wrong run mode or binary")
        require(type(repetition) is int and 1 <= repetition <= 3, "wrong repetition")
        key = (mode, label, repetition)
        require(key not in seen, "duplicate observation")
        seen.add(key)
        require(run.get("host") == host, "comparison host or power source changed")
        require(run.get("binary_sha256_before") == binaries[label]["sha256"] ==
                run.get("binary_sha256_after"), "binary identity mismatch")
        require(run.get("interval_seconds") == 1, "wrong sampling interval")
        require(number(run.get("warmup_seconds"), "warmup") >= 30, "short warmup")
        require(run.get("diagnostics_enabled") is False, "diagnostic writer enabled")
        require(run.get("process_survived") is True, "process exited during observation")
        require(type(run.get("pid")) is int and run["pid"] > 0, "invalid process identity")
        require(bool(run.get("process_start")), "missing process start identity")
        for boundary in ("before", "after"):
            require(run.get(f"monitor_pids_{boundary}") == [run["pid"]],
                    "another monitor process was present")
            require(run.get(f"conflicting_processes_{boundary}") == [],
                    "compiler, profiler or stress process was present")
            windows = run.get(f"windows_{boundary}")
            expected = [{"width": 1280, "height": 880, "screen": "Summary"}]
            require(windows == (expected if mode == "summary" else []), "wrong window state")
        start = number(run.get("monotonic_before_ns"), "start time")
        end = number(run.get("monotonic_after_ns"), "end time")
        require(start > last_end and end > start, "overlapping or regressing clock")
        last_end = end
        elapsed = (end - start) / 1e9
        require(elapsed >= 60, "short observation")
        cpu_start = number(run.get("cpu_before_ns"), "starting CPU counter")
        cpu_end = number(run.get("cpu_after_ns"), "ending CPU counter")
        require(cpu_end >= cpu_start, "regressing CPU counter")
        cpu = (cpu_end - cpu_start) / 1e9
        require(cpu <= elapsed * host["logical_cpus"], "impossible CPU time")
        totals[(mode, label)][0] += cpu
        totals[(mode, label)][1] += elapsed
        # Each mode has three adjacent pairs; reverse the order of the middle pair.
        expected_mode = "summary" if index < 6 else "tray"
        pair_index = (index % 6) // 2
        order = ("candidate", "reference") if pair_index == 1 else ("reference", "candidate")
        require((mode, repetition, label) == (expected_mode, pair_index + 1, order[index % 2]),
                "observations do not follow the paired alternating protocol")
    result = {}
    for mode in ("summary", "tray"):
        reference_cpu, reference_wall = totals[(mode, "reference")]
        candidate_cpu, candidate_wall = totals[(mode, "candidate")]
        require(reference_cpu > 0, "zero reference CPU time")
        reference = reference_cpu / reference_wall
        candidate = candidate_cpu / candidate_wall
        ratio = candidate / reference
        require(math.isfinite(ratio), "non-finite comparison")
        result[mode] = {"reference_percent": reference * 100,
                        "candidate_percent": candidate * 100,
                        "ratio": ratio, "passed": ratio <= 0.5}
    return result
