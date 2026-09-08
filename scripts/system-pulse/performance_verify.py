"""Cairn gate: require native paired CPU and preservation evidence for this source."""

import json
import os
import re
from pathlib import Path
import subprocess
import sys

from performance_compare import compare, require
from performance_macos import digest

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ["Cargo.toml", "Cargo.lock", ".cargo/config.toml", "src", "tests",
              "crates", "vendor", "assets"]


def same_production(commit):
    require(isinstance(commit, str) and re.fullmatch(r"[a-f0-9]{40}", commit), "missing tested source commit")
    result = subprocess.run(["git", "diff", "--quiet", commit, "HEAD", "--", *PRODUCTION], cwd=ROOT)
    require(result.returncode == 0, "tested production source differs from current source")


def check_harness(hashes, names):
    require(set(hashes) == set(names), "missing native harness provenance")
    for name in names:
        require(hashes[name] == digest(ROOT / "scripts/system-pulse" / name),
                "native harness changed after measurement: " + name)


def validate_preservation(record, candidate_hash):
    require(record.get("status") == "PASS", "native preservation did not pass")
    require(record.get("binary_sha256") == candidate_hash, "wrong preservation binary")
    same_production(record.get("source_commit"))
    check_harness(record.get("preservation_harness_sha256", {}),
                  ("performance_preserve.py", "performance_tree.swift"))
    require(record.get("hidden_windows") == 0, "dashboard remained open")
    require(record["hidden_end_sequence"] >= record["hidden_start_sequence"] + 4,
            "background sampling did not continue")
    require(record["reopened_history_seconds"] >= record["initial_history_seconds"] + 3,
            "background history was not retained")
    require(record["saved_settings"] == record["reopened_settings"], "settings changed on reopen")
    require(record["saved_settings"]["interval_ms"] == 1000, "preservation used a slower interval")
    require(record.get("quit_exit_code") == 0 and record.get("process_survived_quit") is False,
            "native Quit did not exit cleanly")
    require(record.get("monitors_count", 0) > 0 and record.get("sensors_count", 0) > 0,
            "native coverage comparison is missing")
    require(bool(record.get("capacities")), "independent native capacity checks are missing")
    for capacity in record["capacities"]:
        reading = capacity["reading"]
        require(reading["availability"] == "Available", "native capacity is not current")
        observation = reading["observations"][0]
        raw = observation["integers"]
        require(observation["source"] == "statvfs filesystem capacity", "wrong capacity source")
        require(raw["fragment_size"] > 0 and raw["blocks"] >= raw["free_blocks"], "invalid block counts")
        require(reading["total"] == raw["blocks"] * raw["fragment_size"] == capacity["independent_total"],
                "native capacity total disagrees")
        require(reading["value"] == (raw["blocks"] - raw["free_blocks"]) * raw["fragment_size"],
                "native used-space arithmetic disagrees")
        require(abs(reading["value"] - capacity["independent_used"]) <= 16 * 1024 * 1024,
                "independent native used space disagrees")


def main():
    subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s",
                    "scripts/system-pulse", "-p", "test_performance_compare.py"], cwd=ROOT, check=True)
    print("cairn: PERF-006: pass", flush=True)
    evidence = Path(os.environ.get("SYSTEM_PULSE_PERFORMANCE_EVIDENCE",
                                  ROOT / "docs/execution/macos-performance/evidence"))
    measurement = json.loads((evidence / "measurements.json").read_text())
    comparison = compare(measurement)
    candidate = measurement["binaries"]["candidate"]
    same_production(candidate["commit"])
    check_harness(measurement.get("measurement_harness_sha256", {}),
                  ("performance_macos.py", "performance_ax.swift"))
    build = json.loads((evidence / "native-build.json").read_text())
    require(build["commit"] == candidate["commit"] and build["sha256"] == candidate["sha256"],
            "native build does not match measured binary")
    require(set(build["checks"]) == {"tests", "clippy", "release"} and
            all(check["exit_code"] == 0 for check in build["checks"].values()), "native build checks failed")
    preservation = json.loads((evidence / "native-preservation/result.json").read_text())
    validate_preservation(preservation, candidate["sha256"])
    require(preservation["reference_sha256"] == measurement["binaries"]["reference"]["sha256"],
            "coverage used a different reference binary")
    linux = json.loads((evidence / "linux-application-manifest.json").read_text())
    require(linux["status"] == "PASS", "Linux native/package preservation did not pass")
    same_production(linux["source_commit"])
    for requirement in ("PERF-003", "PERF-004", "PERF-005"):
        print(f"cairn: {requirement}: pass", flush=True)
    passed = True
    for mode, requirement in (("summary", "PERF-001"), ("tray", "PERF-002")):
        result = comparison[mode]
        print(f"{mode}: {result['reference_percent']:.3f}% -> {result['candidate_percent']:.3f}% "
              f"of one CPU; ratio={result['ratio']:.6f}", flush=True)
        if result["passed"]:
            print(f"cairn: {requirement}: pass", flush=True)
        else:
            passed = False
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Performance evidence incomplete or invalid: {error}", file=sys.stderr)
        raise SystemExit(2)
