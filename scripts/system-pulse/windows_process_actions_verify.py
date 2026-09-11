"""Verify ordinary action observations; this alone cannot accept the UAC commitment."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from performance_compare import require
from performance_verify import check_harness, same_production
from release_ci_verify import archive_files, verify_archive
from windows_process_actions_collect import HARNESS_FILES, ORDINARY_CASES, build_identity, packaged_binary_hash


def validate_ordinary_actions(record):
    require(record.get("status") == "PASS", "native ordinary actions did not pass")
    dashboard = record.get("dashboard", {})
    require(dashboard.get("elevated_before") is False and dashboard.get("elevation_type") in (1, 3)
            and dashboard.get("pid", 0) > 0 and dashboard.get("creation_ticks", 0) > 0,
            "missing unelevated dashboard identity")
    require(record.get("signing_status") in ("NotSigned", "Valid"), "packaged signature is invalid")
    path = record.get("binary_path", "")
    require(" " in path and any(ord(char) > 127 for char in path),
            "spaces and non-ASCII executable path were not exercised")
    expected_probes = {"unelevated-helper": 29, "extra-helper-argument": 29, "legacy-helper-mode": 13}
    probes = record.get("helper_entry_checks", [])
    require(len(probes) == len(expected_probes)
            and {probe.get("name") for probe in probes} == set(expected_probes),
            "missing native helper entry refusals")
    for probe in probes:
        require(probe.get("exit_code") == expected_probes[probe["name"]]
                and probe.get("target_alive") is True and probe.get("state_created") is False
                and probe.get("diagnostics_created") is False,
                "native helper bypassed entry checks or initialized the dashboard")
    cases = record.get("cases", [])
    require([case.get("name") for case in cases] == [case["name"] for case in ORDINARY_CASES],
            "ordinary action cases are missing or duplicated")
    control = record.get("unrelated_control", {})
    require(control.get("pid", 0) > 0 and control.get("creation_ticks", 0) > 0,
            "missing unrelated control identity")
    for case, expected in zip(cases, ORDINARY_CASES):
        require(case.get("mode") == expected["mode"] and case.get("signal") == expected["signal"],
                "native action semantics differ from the required case")
        pid, ticks = case.get("pid"), case.get("creation_ticks")
        require(type(pid) is int and pid > 0 and pid not in (dashboard["pid"], control["pid"])
                and type(ticks) is int and ticks > 0 and case.get("collected_creation_ticks") == ticks,
                "target identity differs from independent native creation time")
        confirmation = case.get("confirmation", "")
        require(f"PID {pid})?" in confirmation, "confirmation omitted the selected process")
        require(("Unsaved work may be lost" if expected["signal"] == "kill"
                 else "Request graceful closure") in confirmation,
                "confirmation omitted action semantics")
        require(case.get("exited") is expected["expected_exit"], "target lifetime disagrees with the action")
        require(case.get("dashboard_elevated_after") is False, "dashboard became elevated")
        require(case.get("unrelated_control_alive") is True
                and case.get("unrelated_control_messages") == "ready\n",
                "an unrelated process was affected")
        require(case.get("sequence_after", 0) > case.get("sequence_before", 0) > 0,
                "sampling did not advance during native verification")
        if expected.get("cancel_confirmation"):
            require(case.get("status") == "confirmation cancelled", "confirmation cancellation was not observed")
        else:
            require(re.search(expected["expected_status"], case.get("status", "")),
                    "native result text disagrees with target lifetime")
            require(case.get("duplicate_activation") in ("delivered", "control removed", "control disabled"),
                    "duplicate native activation was not exercised")
        if expected.get("verify_responsive"):
            pending = case.get("pending_observations", [])
            require(case.get("pending_screen_changes") == ["Summary", "Processes"] and len(pending) >= 2,
                    "native dashboard responsiveness was not observed while pending")
            require(all(item.get("actions_disabled") == [True, True] for item in pending)
                    and pending[-1].get("sequence", 0) > pending[0].get("sequence", 0),
                    "pending action allowed duplicates or stopped sampling")
    cleanup = record.get("owned_target_cleanup", [])
    observed_pids = {control["pid"], *(case["pid"] for case in cases), *(probe["pid"] for probe in probes)}
    require(observed_pids <= {item.get("pid") for item in cleanup}
            and all(item.get("exited") is True for item in cleanup)
            and record.get("dashboard_cleaned") is True and not record.get("cleanup_error"),
            "native owned process cleanup was incomplete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--build-log", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads((args.evidence / "result.json").read_text(encoding="utf-8-sig"))
    revision, binary_hash = build_identity(args.build_log.read_text(errors="replace"))
    require(record.get("source_commit") == revision
            and record.get("build_log_sha256") == hashlib.sha256(args.build_log.read_bytes()).hexdigest(),
            "native action receipt is not bound to the passing build")
    same_production(revision)
    package = verify_archive(args.package_dir, "x86_64-pc-windows-msvc", revision)
    require(record.get("package") == package, "native action receipt names a different package")
    files = archive_files(args.package_dir / package["archive"])
    signed_hash = packaged_binary_hash(files, binary_hash)
    require(record.get("binary_sha256") == signed_hash,
            "packaged executable differs from the observed native action binary")
    if signed_hash != binary_hash:
        require(record.get("signing_status") == "Valid", "signed candidate did not verify on the native host")
    check_harness(record.get("harness_sha256", {}), HARNESS_FILES)
    validate_ordinary_actions(record)
    hashes = record.get("artifacts_sha256", {})
    screenshots = {case["name"] + suffix for case in ORDINARY_CASES
                   for suffix in ("-confirmation.png", "-result.png")}
    require(screenshots | {"app.stderr"} <= set(hashes), "native action artifacts are missing")
    for name, digest in hashes.items():
        path = Path(name)
        require(not path.is_absolute() and ".." not in path.parts, "invalid artifact path")
        require(hashlib.sha256((args.evidence / path).read_bytes()).hexdigest() == digest,
                "native action artifact changed: " + name)
    require(not (args.evidence / "app.stderr").read_text().strip(),
            "application reported an error during native action verification")
    print("PASS ordinary Windows process-action observations; UAC evidence remains separate")


if __name__ == "__main__":
    main()
