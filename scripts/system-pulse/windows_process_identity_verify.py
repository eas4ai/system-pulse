"""WUAC-001: require source-bound native Windows identity and targeting tests."""

import json
import re
import subprocess
import sys

from performance_compare import require
from performance_macos import digest
from performance_verify import ROOT, same_production

NATIVE_TESTS = (
    "denied_safety_verification_does_not_request_authorization",
    "native_collection_preserves_all_creation_ticks_and_rejects_one_tick_mismatch",
    "native_exited_and_protected_targets_are_refused",
    "native_pinned_process_and_file_identity_survive_path_aliases",
    "native_graceful_close_honors_refusal_and_never_messages_an_unrelated_process",
)


def validate_native_identity(contents, commit, binary_hash):
    require(re.fullmatch(r"[a-f0-9]{40}", commit) is not None, "missing source identity")
    require(re.fullmatch(r"[a-f0-9]{64}", binary_hash) is not None, "missing binary identity")
    require(f"Source commit: {commit}" in contents and f"PASS REL-001 {commit}" in contents,
            "Windows build did not complete for this source")
    require(re.search(r"Hash\s*:\s*" + binary_hash, contents, re.IGNORECASE) is not None,
            "Windows build and observed binary differ")
    require(re.search(r"Running unittests .*system_pulse_collectors-[a-f0-9]+\.exe", contents)
            is not None, "collector tests did not run as a native Windows executable")
    for name in NATIVE_TESTS:
        require(re.search(r"^test process_control::windows::tests::" + name + r" \.\.\. ok\s*$",
                          contents, re.MULTILINE) is not None,
                "missing passing native identity case: " + name)
    summaries = re.findall(
        r"test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored;", contents)
    require(bool(summaries) and all(status == "ok" and failed == ignored == "0"
                                  for status, _, failed, ignored in summaries),
            "native tests failed or were ignored")


def main():
    subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s",
                    "scripts/system-pulse", "-p", "test_windows_process_identity_verify.py"],
                   cwd=ROOT, check=True)
    subprocess.run(["cargo", "test", "--locked", "-p", "system-pulse-collectors"],
                   cwd=ROOT, check=True)
    evidence = ROOT / "docs/execution/windows-uac-process-actions/upgrade"
    record = json.loads((evidence / "windows-runtime/result.json").read_text())
    same_production(record["source_commit"])
    log = evidence / "windows-build.log"
    require(digest(log) == record["build_log_sha256"], "native build log changed")
    validate_native_identity(log.read_text(encoding="utf-8", errors="replace"),
                             record["source_commit"], record["binary_sha256"])
    print("PASS WUAC-001")


if __name__ == "__main__":
    main()
