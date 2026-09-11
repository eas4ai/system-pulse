"""Require actual, source-bound Windows UAC observations; missing cases stay pending."""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from performance_compare import require
from performance_verify import ROOT, check_harness, same_production
from release_ci_verify import archive_files, verify_archive
from windows_process_actions_collect import build_identity
from windows_process_actions_verify import validate_ordinary_actions
from windows_process_uac_collect import CASES, HARNESS_FILES
from gpui_kit_upgrade_verify import validate_native as validate_platform_preservation
from windows_process_identity_verify import validate_native_identity


REQUIRED_RUNS = (
    "ordinary", "consent-force", "consent-graceful", "consent-refused",
    "consent-cancel", "consent-stale", "consent-delayed", "consent-denied",
    "helper-crash", "helper-timeout",
)
RESOURCE_REVIEW_SOURCES = (
    "crates/collectors/src/process_control/windows.rs",
    "crates/collectors/src/process_control/windows_protocol.rs",
    "crates/collectors/src/process_control.rs",
    "src/main.rs",
)
RESOURCE_REVIEW_CHECKS = (
    "helper_handle", "caller_target_handles", "token_handles", "restart_manager",
    "com_apartment", "entry_isolation", "no_debug_privilege",
)
HANDLE_SELFTEST_SOURCES = tuple("scripts/system-pulse/" + name for name in (
    "windows_process_handles.cs", "windows_process_handles_selftest.ps1",
    "windows_process_fault.cs", "windows_process_fixture.cs",
))


def validate_handle_selftest(proof, source_hashes):
    require(proof.get("sources_sha256") == source_hashes,
            "native handle positive controls used different source")
    result = proof.get("result", {})
    require(result.get("status") == "PASS" and result.get("target_cleaned") is True
            and result.get("observer_debug_privilege_removed") is True
            and not result.get("error") and not result.get("cleanup_error"),
            "native handle positive controls or cleanup failed")
    samples = result.get("samples", [])
    require(len(samples) == 3 and {s.get("access") for s in samples} == {0x100000, 0x101000, 0x101001},
            "native handle controls omitted synchronization, query or termination rights")
    for sample in samples:
        snapshots = [sample[key] for key in ("before", "open", "after")]
        require(all(s.get("snapshot_released") is True and s.get("dashboard_alive") is True
                    and s.get("unclassified_handles") == 0 and s.get("scanned_handles", 0) > 0
                    and len(s.get("process_handles", [])) == 1 for s in snapshots),
                "native handle positive control snapshot was incomplete")
        before, opened, after = [s["process_handles"][0] for s in snapshots]
        require(before["pid"] == opened["pid"] == after["pid"]
                and opened["count"] == before["count"] + 1 and after["count"] == before["count"]
                and opened["termination_count"] == before["termination_count"] + (sample["access"] & 1)
                and after["termination_count"] == before["termination_count"],
                "native counter did not detect the deliberately retained and released handle")
    foreign = result.get("foreign_snapshot", {})
    require(foreign.get("snapshot_released") is True and foreign.get("dashboard_alive") is True
            and foreign.get("scanned_handles", 0) > 0 and foreign.get("unclassified_handles") == 0,
            "native counter did not verify a foreign owned process snapshot")


def native_identity(value, description):
    require(isinstance(value, dict) and type(value.get("pid")) is int and value["pid"] > 0
            and type(value.get("creation_ticks")) is int and value["creation_ticks"] > 0,
            "missing full native " + description + " identity")
    return value["pid"], value["creation_ticks"]


def validate_consent_interval(ui, observer, case_name, consent, events):
    stop = next(row for row in events if row.get("kind") == "stop" and row.get("pid") == consent["pid"])
    # Native event TIME_CREATED uses UTC FILETIME units, not Unix seconds.
    begin, end = consent["event_ticks"], stop["event_ticks"]
    def filetime(utc):
        value = datetime.fromisoformat(utc.replace("Z", "+00:00"))
        require(value.utcoffset() is not None, "consent observation has no timezone")
        return int(value.timestamp() * 10_000_000) + 116444736000000000
    if case_name == "consent-stale":
        require(begin <= filetime(observer["fault_applied"]["utc"]) < end,
                "owned target did not exit while the consent prompt was pending")
    else:
        require(end - begin >= 80_000_000, "delayed approval did not wait at the actual consent prompt")
        pending = [row for row in ui["cases"][0].get("pending_observations", [])
                   if begin <= filetime(row["observed_utc"]) < end]
        require(len(pending) >= 2 and pending[-1]["sequence"] > pending[0]["sequence"],
                "dashboard sampling did not advance during actual consent")


def validate_trace(ui, observer, case_name):
    """Correlate exact start events with possibly truncated stop names by PID."""
    events = observer.get("events", [])
    require(isinstance(events, list) and events, "native process trace is missing")
    require(all(not any(row.get(key) for key in (
        "observation_error", "token_close_failed", "process_close_failed", "argv_free_failed"))
                for row in events), "native trace observation or resource cleanup failed")
    starts = [row for row in events if row.get("kind") == "start"]
    require(len({row.get("pid") for row in starts}) == len(starts),
            "duplicate start or PID reuse makes this short observation ambiguous")
    dashboard_pid, dashboard_ticks = native_identity(ui.get("dashboard"), "dashboard")
    probes = ui.get("helper_entry_checks", [])
    probe_codes = {"unelevated-helper": 29, "extra-helper-argument": 29, "legacy-helper-mode": 13}
    require(len(probes) == 3 and {row.get("name") for row in probes} == set(probe_codes),
            "native helper entry probes are missing")
    known = {dashboard_pid, *(row.get("pid") for row in probes)}
    require(len(known) == 4, "helper entry and dashboard identities overlap")
    app_starts = [row for row in starts if row.get("name", "").lower() == "system-pulse.exe"]
    require(known <= {row.get("pid") for row in app_starts}, "trace missed dashboard or entry probes")
    dashboard = next(row for row in app_starts if row["pid"] == dashboard_pid)
    require(dashboard.get("creation_ticks") == dashboard_ticks and dashboard.get("elevated") is False,
            "independent trace did not observe the unelevated dashboard")
    require(type(dashboard.get("session_id")) is int and dashboard["session_id"] > 0
            and all(row.get("session_id") == dashboard["session_id"] for row in app_starts),
            "application processes did not share the interactive desktop session")
    helper_starts = [row for row in app_starts if row["pid"] not in known]
    expected_helpers = 0 if case_name in ("ordinary", "consent-cancel") else 1
    require(len(helper_starts) == expected_helpers, "missing, duplicate or unsolicited elevated helper")
    consent_starts = [row for row in starts if row.get("name", "").lower() == "consent.exe"]
    require(len(consent_starts) == (0 if case_name == "ordinary" else 1),
            "unexpected prompt count or missing actual Windows consent process")
    for start in [*app_starts, *consent_starts]:
        stops = [row for row in events if row.get("kind") == "stop" and row.get("pid") == start["pid"]]
        require(len(stops) == 1 and type(start.get("event_ticks")) is int
                and type(stops[0].get("event_ticks")) is int
                and stops[0]["event_ticks"] >= start["event_ticks"],
                "missing, duplicate or out-of-order native process exit")
        # This host reports zero SessionID and ParentProcessID on stop events,
        # including for the independently observed session-1 dashboard. Use the
        # start's native session; a nonzero conflicting stop remains invalid.
        require(stops[0].get("session_id") in (0, start.get("session_id")), "process trace session changed")
    if case_name in ("consent-delayed", "consent-stale"):
        validate_consent_interval(ui, observer, case_name, consent_starts[0], events)
    for probe in probes:
        stop = next(row for row in events if row.get("kind") == "stop" and row.get("pid") == probe["pid"])
        require(probe.get("exit_code") == stop.get("exit_code") == probe_codes[probe["name"]]
                and probe.get("target_alive") is True and probe.get("state_created") is False
                and probe.get("diagnostics_created") is False,
                "native helper entry was accepted or initialized application state")
    if helper_starts:
        helper = helper_starts[0]
        stop = next(row for row in events if row.get("kind") == "stop" and row.get("pid") == helper["pid"])
        case = ui["cases"][0]
        # Very short helpers can exit before the provider delivers their start.
        # The delayed case must supply the full live token and argument evidence.
        if case_name == "consent-delayed" or "argv" in helper:
            require(helper.get("elevated") is True and helper.get("elevation_type") == 2,
                    "helper elevation was not independently observed")
            require(helper.get("image", "").casefold() == ui.get("binary_path", "").casefold(),
                    "helper executed a different image")
            require(helper.get("argv") == [ui["binary_path"], "--system-pulse-windows-process-action",
                    str(case["pid"]), str(case["creation_ticks"]), case["signal"],
                    str(dashboard_pid), str(dashboard_ticks)],
                    "helper argument vector differs from the confirmed one-shot request")
        exit_codes = {"consent-force": 20, "consent-graceful": 20,
                      "consent-refused": 28, "consent-stale": 26, "consent-delayed": 28,
                      "consent-denied": 23, "helper-crash": 0xC0000001}
        require(case_name == "helper-timeout" or
                (case_name in exit_codes and stop.get("exit_code") == exit_codes[case_name]),
                "native helper exit code differs from the observed action")
        if case_name in ("helper-crash", "helper-timeout"):
            fault = observer.get("fault_applied", {})
            require(fault.get("kind") == case_name
                    and native_identity(fault, "faulted helper") == native_identity(helper, "observed helper")
                    and fault.get("image") == helper.get("image") and fault.get("argv") == helper.get("argv")
                    and observer.get("helper_cleaned") is True,
                    "helper fault or cleanup was not bound to the observed request")
            require(observer.get("helper_exited_before_cleanup") is (case_name == "helper-crash"),
                    "helper lifetime does not demonstrate the requested crash or timeout")
            if case_name == "helper-timeout":
                require(type(fault.get("suspended_threads")) is int and fault["suspended_threads"] > 0,
                        "timeout did not suspend the owned helper")
                started = datetime.fromisoformat(fault["utc"])
                settled = datetime.fromisoformat(case["settled_utc"])
                require(started.utcoffset() is not None and settled.utcoffset() is not None
                        and 115 <= (settled - started).total_seconds() <= 140,
                        "native helper timeout was not observed for its bounded wait")


def validate_run(ui, observer, case_name):
    require(case_name in CASES, "native case verifier is not implemented: " + case_name)
    require(ui.get("status") == "PASS" and observer.get("status") == "COLLECTED"
            and observer.get("ui_task_exit") == 0, "native UAC observation failed")
    require(not any(observer.get(key) for key in
                    ("error", "cleanup_error", "trace_cleanup_error", "ui_still_running")),
            "native supervisor reported an error or incomplete cleanup")
    native_identity(observer.get("observer"), "observer")
    require(observer["observer"].get("elevated") is True, "observer did not have native observation rights")
    require(observer.get("observer_debug_privilege_removed") is True,
            "native observer could bypass the test target's access checks")
    binary_path = ui.get("binary_path", "")
    require(ui.get("signing_status") == "NotSigned" and " " in binary_path
            and any(ord(char) > 127 for char in binary_path),
            "native signing status or packaged path coverage changed")
    control = native_identity(ui.get("unrelated_control"), "unrelated control")
    cleanup = ui.get("owned_target_cleanup", [])
    owned_pids = {control[0], *(row.get("pid") for row in ui.get("helper_entry_checks", []))}
    require(owned_pids <= {row.get("pid") for row in cleanup}
            and all(row.get("exited") is True for row in cleanup) and not ui.get("cleanup_error"),
            "ordinary fixture or helper entry probe cleanup was incomplete")
    if case_name == "ordinary":
        validate_ordinary_actions(ui)
    else:
        dashboard = ui.get("dashboard", {})
        native_identity(dashboard, "dashboard")
        require(dashboard.get("elevated_before") is False and dashboard.get("elevation_type") == 3,
                "consent case did not start with the administrator's limited token")
        target = native_identity(observer.get("target"), "owned target")
        require(observer["target"].get("elevated") is True and target[0] != dashboard["pid"],
                "owned target was not separately elevated")
        require(observer["target"].get("administrator_termination_dacl") is True
                and observer["target"].get("administrator_termination_access_error") == 0,
                "owned fixture did not establish administrator termination access")
        require(observer.get("target_cleaned") is True and ui.get("dashboard_cleaned") is True,
                "owned elevated target or dashboard survived cleanup")
        cases = ui.get("cases", [])
        require(len(cases) == 1 and cases[0].get("name") == case_name, "missing or ambiguous native case")
        case = cases[0]
        expected = CASES[case_name]
        require(native_identity(case, "confirmed target") == target
                and case.get("collected_creation_ticks") == target[1], "confirmed target identity changed")
        require(case.get("signal") == expected["signal"] and case.get("mode") == expected["mode"],
                "native case used different action semantics")
        if case["signal"] == "kill":
            require(case.get("ordinary_force_access_error") == 5,
                    "ordinary Force quit did not independently report access denied")
        require(case.get("exited") is expected["expected_exit"]
                and observer.get("target_exited_before_cleanup") is expected["expected_exit"]
                and re.search(expected["expected_status"], case.get("status", "")),
                "result text and independently observed target lifetime disagree")
        require(case.get("dashboard_elevated_after") is False and case.get("unrelated_control_alive") is True
                and case.get("unrelated_control_messages") == "ready\n", "dashboard elevated or unrelated target changed")
        require(case.get("sequence_after", 0) > case.get("sequence_before", 0) > 0,
                "dashboard sampling did not advance")
        require(case.get("duplicate_activation") in ("delivered", "control removed", "control disabled"),
                "duplicate submission was not exercised")
        warning = "Unsaved work may be lost" if case["signal"] == "kill" else "Request graceful closure"
        require(f"PID {target[0]})?" in case.get("confirmation", "") and warning in case["confirmation"],
                "native confirmation omitted identity or action semantics")
        if expected.get("verify_responsive"):
            pending = case.get("pending_observations", [])
            require(case.get("pending_screen_changes") == ["Summary", "Processes"] and len(pending) >= 2
                    and pending[-1].get("sequence", 0) > pending[0].get("sequence", 0)
                    and all(row.get("actions_disabled") == [True, True] for row in pending),
                    "pending action did not demonstrate responsiveness and duplicate prevention")
        if case_name == "consent-stale":
            fault = observer.get("fault_applied", {})
            require(fault.get("kind") == "target-exit-during-consent" and native_identity(fault, "stale target") == target,
                    "stale target did not exit during the authorization observation")
        if case_name == "consent-denied":
            fault = observer.get("fault_applied", {})
            require(fault.get("kind") == "deny-termination" and native_identity(fault, "denied target") == target
                    and fault.get("elevated_access_error") == 5,
                    "owned target did not independently deny elevated termination")
    validate_trace(ui, observer, case_name)
    if case_name != "ordinary":
        validate_resources(ui, observer, case_name)


def validate_resources(ui, observer, case_name):
    """Require a live-dashboard observation of the actual helper handle closing."""
    resources = observer.get("resources", {})
    dashboard = native_identity(ui.get("dashboard"), "resource dashboard")
    require(ui.get("resources_acknowledged") is True and resources.get("passed") is True
            and resources.get("case") == case_name and resources.get("dashboard_alive") is True
            and resources.get("snapshot_released") is True,
            "missing live dashboard resource acknowledgment or snapshot cleanup")
    require((resources.get("dashboard_pid"), resources.get("dashboard_creation_ticks")) == dashboard,
            "resource observation belongs to another dashboard")
    require(type(resources.get("scanned_handles")) is int and 0 < resources["scanned_handles"] <= 100000
            and type(resources.get("unclassified_handles")) is int and resources["unclassified_handles"] == 0,
            "native handle snapshot was empty or incompletely classified")
    known = {dashboard[0], *(row["pid"] for row in ui["helper_entry_checks"])}
    helpers = {event["pid"] for event in observer["events"]
               if event["kind"] == "start" and event["name"].lower() == "system-pulse.exe"
               and event["pid"] not in known}
    target = native_identity(observer.get("target"), "resource target")[0]
    rows = resources.get("process_handles", [])
    require(len(rows) == len(helpers) + 1 and {row.get("pid") for row in rows} == helpers | {target},
            "resource snapshot omitted or substituted the selected target or helper")
    for row in rows:
        require(type(row.get("count")) is int and row["count"] >= 0
                and type(row.get("termination_count")) is int and 0 <= row["termination_count"] <= row["count"],
                "invalid native process handle count")
        require(row["count"] == 0 if row["pid"] in helpers else row["termination_count"] == 0,
                "dashboard retained a helper or owned termination handle")
    settled = datetime.fromisoformat(ui["cases"][0]["settled_utc"].replace("Z", "+00:00"))
    captured = datetime.fromisoformat(resources["captured_utc"].replace("Z", "+00:00"))
    require(0 <= (captured - settled).total_seconds() <= 20,
            "resource observation was not taken after the settled action")


def verify_receipt(directory, build_log, package_dir):
    receipt = json.loads((directory / "receipt.json").read_text())
    revision, binary_hash = build_identity(build_log.read_text(errors="replace"))
    same_production(revision)
    require(receipt.get("source_commit") == revision and receipt.get("binary_sha256") == binary_hash
            and receipt.get("build_log_sha256") == hashlib.sha256(build_log.read_bytes()).hexdigest(),
            "UAC receipt differs from the passing native build")
    package = verify_archive(package_dir, "x86_64-pc-windows-msvc", revision)
    require(receipt.get("package") == package
            and hashlib.sha256(archive_files(package_dir / package["archive"])["system-pulse.exe"]).hexdigest() == binary_hash,
            "UAC observation did not use the shipped binary")
    check_harness(receipt.get("harness_sha256", {}), HARNESS_FILES)
    artifacts = receipt.get("artifacts_sha256", {})
    require({"observer.json", "evidence/result.json", "evidence/app.stderr"} <= set(artifacts),
            "UAC native artifacts are missing")
    for name, expected_hash in artifacts.items():
        path = Path(name)
        require(not path.is_absolute() and ".." not in path.parts, "unsafe native artifact path")
        require(hashlib.sha256((directory / path).read_bytes()).hexdigest() == expected_hash,
                "native UAC artifact changed: " + name)
    require(not (directory / "evidence/app.stderr").read_text().strip(), "native dashboard reported an error")
    ui = json.loads((directory / "evidence/result.json").read_text(encoding="utf-8-sig"))
    observer = json.loads((directory / "observer.json").read_text(encoding="utf-8-sig"))
    require(ui.get("source_commit") == revision and ui.get("binary_sha256") == binary_hash,
            "UI observation names a different binary")
    validate_run(ui, observer, receipt["case"])
    return receipt["case"]


def validate_resource_review(review, source_hashes):
    require(review.get("status") == "PASS" and review.get("findings") == [],
            "helper resource review has unresolved findings")
    require(review.get("sources_sha256") == source_hashes,
            "helper resource review does not cover the current source")
    checks = review.get("checks", {})
    require(set(checks) == set(RESOURCE_REVIEW_CHECKS)
            and all(isinstance(value, str) and len(value.strip()) >= 20 for value in checks.values()),
            "helper resource review omitted an ownership or isolation boundary")


def verify_all(evidence, build_log, package_dir, preservation, review_path):
    missing = [name for name in REQUIRED_RUNS if not (evidence / name / "receipt.json").is_file()]
    require(not missing, "Native UAC observations remain pending: " + ", ".join(missing))
    require(package_dir is not None, "set SYSTEM_PULSE_WINDOWS_PACKAGE_DIR or pass --package-dir")
    for name in REQUIRED_RUNS:
        require(verify_receipt(evidence / name, build_log, package_dir) == name,
                "native run directory contains a different case: " + name)
    revision, binary_hash = build_identity(build_log.read_text(errors="replace"))
    validate_native_identity(build_log.read_text(errors="replace"), revision, binary_hash)
    validate_platform_preservation(preservation)
    preserved_windows = json.loads((preservation / "windows-runtime/result.json").read_text(encoding="utf-8-sig"))
    require(preserved_windows.get("source_commit") == revision
            and preserved_windows.get("binary_sha256") == binary_hash,
            "Windows preservation used a different native binary")
    proof_path = ROOT / "docs/execution/windows-uac-process-actions/native-handle-selftest.json"
    validate_handle_selftest(json.loads(proof_path.read_text()), {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in HANDLE_SELFTEST_SOURCES
    })
    review = json.loads(review_path.read_text())
    same_production(review.get("source_commit", ""))
    source_hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                     for name in RESOURCE_REVIEW_SOURCES}
    validate_resource_review(review, source_hashes)
    print("PASS WUAC-002 WUAC-003 WUAC-004 WUAC-005 WUAC-006: "
          "administrator consent/cancellation, native actions, released helper handles and platform preservation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path,
                        default=ROOT / "docs/execution/windows-uac-process-actions/uac-native")
    preservation = ROOT / "docs/execution/windows-uac-process-actions/process-actions-preservation"
    parser.add_argument("--build-log", type=Path, default=preservation / "windows-build.log")
    package = os.environ.get("SYSTEM_PULSE_WINDOWS_PACKAGE_DIR")
    parser.add_argument("--package-dir", type=Path, default=Path(package) if package else None)
    parser.add_argument("--preservation", type=Path, default=preservation)
    parser.add_argument("--resource-review", type=Path,
                        default=ROOT / "docs/execution/windows-uac-process-actions/helper-resource-review.json")
    parser.add_argument("--single", action="store_true", help="Verify one observation without accepting requirements")
    args = parser.parse_args()
    if args.single:
        require(args.build_log is not None and args.package_dir is not None, "single observation needs its build and package")
        name = verify_receipt(args.evidence, args.build_log, args.package_dir)
        print("PASS native observation " + name + "; full UAC acceptance remains separate")
        return
    subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "scripts/system-pulse",
                    "-p", "test_windows_process_uac_verify.py"], cwd=ROOT, check=True)
    verify_all(args.evidence, args.build_log, args.package_dir, args.preservation, args.resource_review)


if __name__ == "__main__":
    main()
