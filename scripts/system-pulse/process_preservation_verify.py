"""Preservation receipts must bind ordinary actions and the complete Linux package."""

import json
from pathlib import Path
import re
import subprocess

from acceptance import Runner, validate_automated_steps, validate_host
from performance_compare import require
from performance_macos import digest
from performance_verify import ROOT, same_production
from tabbed_acceptance import validate_tabbed


def validate_ordinary_actions(record):
    actions = record["ordinary_actions"]
    require([row["action"] for row in actions] == ["end", "force"],
            "missing ordinary Mac process actions")
    for row, signal in zip(actions, (-15, -9)):
        require(re.fullmatch(r"process:[1-9]\d*:[1-9]\d*", row["identity"]),
                "ordinary action has no verified process identity")
        require(row["confirmation_cancelled_alive"] is True and row["child_exit"] == signal,
                "ordinary confirmation cancellation or signal changed")
        require(row["notice"].startswith("Request sent to ") and
                f"(PID {row['identity'].split(':')[1]})" in row["notice"],
                "ordinary action notice names another process")
    require(actions[0]["identity"] != actions[1]["identity"], "ordinary actions reused an exited target")


def verify_artifact(record):
    path = Path(record["path"])
    require(path.is_file() and path.stat().st_size == record["bytes"] > 0 and
            digest(path) == record["sha256"], "missing or changed acceptance artifact: " + str(path))
    return path


def validate_step_logs(steps, required):
    require(set(steps) == set(required), "missing or unexpected acceptance stages")
    for name, step in steps.items():
        require(step["exit_code"] == 0 and step["timed_out"] is False,
                "acceptance stage failed: " + name)
        require(digest(Path(step["log"])) == step["sha256"], "acceptance log changed: " + name)


def validate_package(record, native_build):
    require(record["status"] == "PASS" and record["binary_sha256"] == native_build["binary_sha256"],
            "package acceptance did not pass on the native candidate")
    same_production(record["source_commit"])
    result = subprocess.run(["git", "diff", "--quiet", record["source_commit"], "HEAD", "--",
                             "package", "LICENSE*", "about.*",
                             "scripts/system-pulse/package_linux.py",
                             "scripts/system-pulse/package_smoke.py",
                             "scripts/system-pulse/application_acceptance.py",
                             "scripts/system-pulse/tabbed_acceptance.py",
                             "scripts/system-pulse/tabbed_replay.py",
                             "scripts/system-pulse/application_replay.py",
                             "scripts/system-pulse/tray_replay.py"], cwd=ROOT)
    require(result.returncode == 0, "package or native acceptance source changed after verification")
    validate_step_logs(record["steps"], {"preservation", "input-focus", "package", "application", "tray", "installed"})
    paths = {name: verify_artifact(record[name])
             for name in ("archive", "preservation_manifest", "product", "tray", "installed")}
    preserved = json.loads(paths["preservation_manifest"].read_text())
    require(preserved["status"] == "PASS" and preserved["source_commit"] == record["source_commit"],
            "preservation source or result disagrees with package")
    runner = Runner(paths["preservation_manifest"].parent)
    runner.steps = preserved["steps"]
    require({"host", "native"} <= set(runner.steps), "missing live host or native preservation stage")
    validate_automated_steps(runner)
    validate_step_logs(runner.steps, set(runner.steps))
    require(preserved["test_count"] == sum(step.get("test_count", 0) for step in runner.steps.values()),
            "preservation test total disagrees with executed suites")
    for artifact in preserved["artifacts"]:
        verify_artifact(artifact)
    validate_host(runner)
    package = paths["archive"].with_name(paths["archive"].name.removesuffix(".tar.gz"))
    binary = package / "system-pulse"
    require(digest(binary) == record["binary_sha256"], "packaged executable changed")
    validate_tabbed(runner, binary, paths["product"].parent)
    for name in ("tray", "installed"):
        observed = json.loads(paths[name].read_text())
        require(observed["status"] == "PASS" and observed["binary_sha256"] == record["binary_sha256"],
                name + " observation does not match the package")
        if name == "installed":
            require(observed["source_commit"] == record["source_commit"], "installed package source differs")
