"""Verify the pinned kit graph and source-bound native preservation evidence."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

from performance_compare import require
from performance_macos import digest
from performance_verify import ROOT, check_harness, same_production, validate_preservation
from process_preservation_verify import validate_package, validate_step_logs
from windows_runtime_verify import (
    HARNESSES, read_json, validate_artifacts, validate_interactions, validate_readings,
)

KIT_PACKAGES = ("gpui-kit", "gpui-base", "gpui-component", "gpui-component-macros", "gpui-kit-assets")
LOCAL_PATCHES = {
    "gpui-base": "crates/base/Cargo.toml",
    "gpui-component": "crates/ui/Cargo.toml",
    "gpui-pre-macos": "vendor/gpui_macos/Cargo.toml",
    "accesskit_atspi_common": "vendor/accesskit_atspi_common/Cargo.toml",
    "accesskit_unix": "vendor/accesskit_unix/Cargo.toml",
    "sysinfo": "vendor/sysinfo/Cargo.toml",
}


def validate_graph(metadata, root=ROOT):
    packages = {package["id"]: package for package in metadata["packages"]}
    nodes = {node["id"]: node for node in metadata["resolve"]["nodes"]}
    pending = [metadata["resolve"]["root"]]
    selected = set()
    while pending:
        identity = pending.pop()
        if identity in selected:
            continue
        require(identity in packages and identity in nodes, "incomplete resolved dependency graph")
        selected.add(identity)
        pending.extend(nodes[identity]["dependencies"])
    by_name = {}
    for identity in selected:
        package = packages[identity]
        by_name.setdefault(package["name"], []).append(package)
    for name in KIT_PACKAGES:
        require([p["version"] for p in by_name.get(name, [])] == ["0.6.1"],
                "expected exactly one GPUI Kit 0.6.1 package: " + name)
    for name, values in by_name.items():
        if name.startswith("gpui-pre") and name != "gpui-pre-reqwest":
            require(len(values) == 1 and values[0]["version"] == "0.3.2",
                    "incompatible or duplicate GPUI runtime: " + name)
    for name, relative in LOCAL_PATCHES.items():
        values = by_name.get(name, [])
        patched = [p for p in values if p["source"] is None and
                   Path(p["manifest_path"]).resolve() == (root / relative).resolve()]
        require(len(patched) == 1 and
                sum(p["version"] == patched[0]["version"] for p in values) == 1,
                "local native/library patch is not selected: " + name)
    return {name: by_name[name][0]["version"] for name in KIT_PACKAGES}


def validate_native(evidence):
    linux = read_json(evidence / "linux-application-manifest.json")
    validate_package(linux, {"binary_sha256": linux["binary_sha256"]})
    checks = read_json(evidence / "automated.json")
    same_production(checks["source_commit"])
    require(checks["status"] == "PASS", "automated upgrade checks failed")
    validate_step_logs(checks["steps"], {"format", "workspace-tests", "workspace-clippy", "python-tests"})

    mac = read_json(evidence / "macos-build.json")
    same_production(mac["source_commit"])
    require(mac["status"] == "PASS" and re.fullmatch(r"[a-f0-9]{64}", mac["binary_sha256"]),
            "missing successful native Mac build")
    validate_step_logs(mac["steps"], {"workspace-tests", "workspace-clippy", "release", "dispatcher", "lifetime"})
    preserved = read_json(evidence / "macos-preservation/result.json")
    validate_preservation(preserved, mac["binary_sha256"])

    windows = evidence / "windows-runtime"
    record = read_json(windows / "result.json")
    same_production(record["source_commit"])
    check_harness(record["harness_sha256"], HARNESSES)
    build_log = evidence / "windows-build.log"
    require(digest(build_log) == record["build_log_sha256"], "Windows runtime build log changed")
    contents = build_log.read_text(encoding="utf-8", errors="replace")
    require(f"PASS REL-001 {record['source_commit']}" in contents and
            re.search(r"Hash\s*:\s*" + re.escape(record["binary_sha256"]), contents, re.IGNORECASE),
            "Windows runtime differs from the verified build")
    validate_interactions(record)
    validate_artifacts(windows, record)
    validate_readings(read_json(windows / "initial.json"), read_json(windows / "final.json"), record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-only", action="store_true")
    parser.add_argument("--evidence", type=Path,
                        default=ROOT / "docs/execution/windows-uac-process-actions/upgrade")
    args = parser.parse_args()
    metadata = json.loads(subprocess.check_output(
        ["cargo", "metadata", "--locked", "--offline", "--format-version=1"], cwd=ROOT, text=True))
    print(json.dumps(validate_graph(metadata), sort_keys=True))
    if args.graph_only:
        return
    subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s",
                    "scripts/system-pulse", "-p", "test_gpui_kit_upgrade_verify.py"], cwd=ROOT, check=True)
    validate_native(args.evidence)
    print("PASS WUAC-007")


if __name__ == "__main__":
    main()
