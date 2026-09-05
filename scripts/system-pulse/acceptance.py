"""Mandatory aggregate gate. Complete logs live outside the source checkout."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from host_accuracy import require

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = (
    "gpui-base",
    "gpui-component",
    "system-pulse-model",
    "system-pulse",
    "system-pulse-collectors",
)
SUITES = (
    ("base-dock", "gpui-base", ["--lib", "dock::"]),
    ("base-resizable", "gpui-base", ["--lib", "resizable::"]),
    ("component-dock", "gpui-component", ["--lib", "dock::"]),
    ("model", "system-pulse-model", []),
    ("app", "system-pulse", ["--lib"]),
    ("collectors", "system-pulse-collectors", []),
    ("atspi", "accesskit_atspi_common", ["--lib"]),
)


def test_count(text, kind):
    if kind == "rust":
        results = re.findall(
            r"test result: (ok|FAILED)\. (\d+) passed; (\d+) failed;", text
        )
        require(
            results
            and all(
                status == "ok" and int(failed) == 0
                for status, passed, failed in results
            ),
            "missing/failing Rust test results",
        )
        count = sum(int(passed) for status, passed, failed in results)
    else:
        results = re.findall(r"Ran (\d+) tests? in ", text)
        require(
            results
            and re.search(r"^OK\s*$", text, re.M)
            and not re.search(r"^(FAILED|ERROR|FAIL:)", text, re.M),
            "missing/failing Python test results",
        )
        count = sum(map(int, results))
    require(count > 0, "zero executed tests")
    return count


def require_steps(required, completed):
    require(
        set(completed) == set(required),
        "required aggregate steps omitted or unexpected",
    )
    require(
        all(r["exit_code"] == 0 for r in completed.values()), "nonzero aggregate step"
    )


def sha256(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


class Runner:
    def __init__(self, output):
        self.output = output
        self.steps = {}

    def progress(self, name, status, **fields):
        record = {
            "step": name,
            "status": status,
            "monotonic_ns": time.monotonic_ns(),
            **fields,
        }
        with (self.output / "progress.jsonl").open("a") as f:
            f.write(json.dumps(record) + "\n")
        detail = " ".join(
            f"{key}={fields[key]}"
            for key in ("test_count", "exit_code", "seconds", "log", "sha256")
            if key in fields
        )
        print(f"{status} {name} {detail}".rstrip(), flush=True)

    def step(self, name, command, kind=None, timeout=1800):
        self.progress(name, "RUNNING")
        path = self.output / (name + ".log")
        start = time.monotonic()
        timed_out = False
        with path.open("x") as log:
            child = subprocess.Popen(
                ["rtk", "proxy", *command],
                cwd=ROOT,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                while child.poll() is None:
                    try:
                        child.wait(
                            timeout=min(
                                30, max(0.1, timeout - (time.monotonic() - start))
                            )
                        )
                    except subprocess.TimeoutExpired:
                        if time.monotonic() - start >= timeout:
                            timed_out = True
                            break
                        self.progress(
                            name,
                            "RUNNING",
                            elapsed_seconds=round(time.monotonic() - start, 1),
                            log=str(path),
                        )
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=5)
        result = {
            "exit_code": child.returncode,
            "timed_out": timed_out,
            "command": command,
            "seconds": round(time.monotonic() - start, 3),
            "log": str(path),
            "sha256": sha256(path),
        }
        self.steps[name] = result
        require(not timed_out, f"{name} timeout; see {path}")
        require(
            child.returncode == 0, f"{name} exited {child.returncode}; full log: {path}"
        )
        if kind:
            result["test_count"] = test_count(path.read_text(), kind)
        self.progress(name, "PASS", **result)

    def artifact(self, path):
        require(
            path.is_file() and path.stat().st_size > 0,
            f"missing/empty required artifact: {path}",
        )
        return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def source_guard():
    lib = (ROOT / "examples/system_pulse/src/lib.rs").read_text()
    require(
        "mod fixture;" not in lib or "#[cfg(test)]\nmod fixture;" in lib,
        "production fixture module included",
    )
    for name in (
        "acceptance.py",
        "host_accuracy.py",
        "host_capture.py",
        "native_contract.py",
        "native_driver.py",
        "native_input.py",
        "native_replay.py",
        "test_host_accuracy.py",
        "test_acceptance.py",
        "test_capture_stream.py",
        "test_host_inventory.py",
    ):
        require(
            (ROOT / "scripts/system-pulse" / name).is_file(),
            "missing acceptance source " + name,
        )
    print("PASS fixture production guard and required acceptance sources")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-guard", action="store_true")
    args = parser.parse_args()
    if args.source_guard:
        source_guard()
        return
    if args.output:
        output = args.output.resolve()
        require(not output.exists(), "aggregate output must be fresh")
        output.mkdir(parents=True)
    else:
        output = Path(tempfile.mkdtemp(prefix="system-pulse-acceptance-"))
    require(
        not output.is_relative_to(ROOT), "acceptance artifacts must be outside checkout"
    )
    runner = Runner(output)
    required = {
        "source-guard",
        "python",
        "fmt",
        "fmt-atspi",
        "clippy",
        "build",
        "diff",
        "host",
        "native",
    } | {s[0] for s in SUITES}
    try:
        runner.step(
            "source-guard",
            [sys.executable, "-B", str(Path(__file__).resolve()), "--source-guard"],
            timeout=10,
        )
        runner.step(
            "python",
            [
                sys.executable,
                "-B",
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/system-pulse",
                "-p",
                "test_*.py",
                "-v",
            ],
            "python",
            30,
        )
        for name, package, extra in SUITES:
            runner.step(
                name, ["cargo", "test", "--locked", "-p", package, *extra], "rust"
            )
        packages = [arg for package in PACKAGES for arg in ("-p", package)]
        runner.step("fmt", ["cargo", "fmt", *packages, "--", "--check"])
        runner.step(
            "fmt-atspi",
            [
                "cargo",
                "fmt",
                "--manifest-path",
                "vendor/accesskit_atspi_common/Cargo.toml",
                "--",
                "--check",
            ],
        )
        runner.step(
            "clippy",
            [
                "cargo",
                "clippy",
                "--locked",
                *packages,
                "-p",
                "accesskit_atspi_common",
                "--all-targets",
                "--no-deps",
                "--",
                "-D",
                "warnings",
            ],
        )
        runner.step(
            "build",
            [
                "cargo",
                "build",
                "--locked",
                "-p",
                "system-pulse",
                "-p",
                "system-pulse-collectors",
                "--bins",
            ],
        )
        runner.step("diff", ["git", "diff", "--check"], timeout=30)
        runner.step(
            "host",
            [
                sys.executable,
                "-B",
                "scripts/system-pulse/host_capture.py",
                "--output",
                str(output / "host"),
                "--binary",
                str(ROOT / "target/debug/pulse-snapshot"),
            ],
            timeout=90,
        )
        runner.step(
            "native",
            [
                sys.executable,
                "-B",
                "scripts/system-pulse/native_replay.py",
                "--output",
                str(output / "native"),
                "--binary",
                str(ROOT / "target/debug/system-pulse"),
            ],
            timeout=1250,
        )
        require_steps(required, runner.steps)
        host = json.loads((output / "host/result.json").read_text())
        native = json.loads((output / "native/result.json").read_text())
        require(
            host["status"] == "PASS"
            and native["status"] == "PASS"
            and native["focused_preparation"] is None,
            "focused/missing acceptance mistaken for final run",
        )
        from native_replay import REQUIRED

        require(set(native["cases"]) == set(REQUIRED), "native required cases omitted")
        mandatory = [
            "host/result.json",
            "host/capabilities.json",
            "host/final-inventory.json",
            "host/stable-totals.json",
            "host/external-observations.json",
            "host/snapshots.jsonl",
            "host/counter-brackets.json",
            "host/missing-brackets.json",
            "host/collector-lifecycle.json",
            "host/collector-start.json",
            "host/collector-stopped.json",
            "host/cleanup.json",
            "host/child.json",
            "host/after-exit.jsonl",
            "native/result.json",
            "native/progress.jsonl",
            "native/private-session.json",
            "native/harness-manifest.json",
            "native/transport-cleanup.json",
            "native/missing-device-config.json",
        ]
        artifacts = [runner.artifact(output / p) for p in mandatory]
        for session in (
            "session-01",
            "session-02",
            "session-recovery-schema",
            "session-recovery-schema-restart",
            "session-recovery-json",
            "session-recovery-json-restart",
            "session-missing-device",
        ):
            for filename in (
                "metadata.json",
                "journal.jsonl",
                "shutdown.json",
                "cleanup.json",
            ):
                artifacts.append(
                    runner.artifact(output / "native" / session / filename)
                )
            shutdown = json.loads(
                (output / "native" / session / "shutdown.json").read_text()
            )
            require(
                shutdown["exit_code"] == 0 and shutdown["before_deadline"],
                "required native normal shutdown failed",
            )
        session = output / "native/session-01"
        metric_names = [
            "cpu-visible",
            "ram-visible",
            "row-compact",
            "panel-compact",
            "chart-physical-value",
            "ram-capacity",
            "child-left",
            "child-right",
        ]
        metric_names += [
            f"gpu-{i}-visible" for i in range(native["cases"]["metrics"]["gpu_count"])
        ]
        temperature_artifacts = native["cases"]["charts"]["gpu_temperature_artifacts"]
        require(
            len(temperature_artifacts)
            == native["cases"]["charts"]["gpu_temperature_count"],
            "GPU temperature artifact count mismatch",
        )
        metric_names += temperature_artifacts
        metric_names += [f"child-visible-{i}" for i in range(1, 7)]
        for name in metric_names:
            for suffix in (".json", ".png"):
                artifacts.append(runner.artifact(session / (name + suffix)))
        for name in ("launch-no-tabs", "split-no-tabs", "recall-no-tabs"):
            for suffix in (".json", ".png"):
                artifacts.append(runner.artifact(session / (name + suffix)))
        for name in (
            "split-structure",
            "divider-movement",
            "outer-movement",
            "inner-edge-wheel",
            "chart-history-evidence",
            "collapsed-sequences",
            "real-child",
            "real-child-cell-discovery",
            "deliberate-scroll-sequences",
            "held-up-25hz",
            "exact-64-up",
            "held-table-left",
            "held-table-right",
            "held-outer-next",
            "held-outer-prior",
            "held-outer-left",
            "held-outer-right",
        ):
            artifacts.append(runner.artifact(session / (name + ".json")))
        for name in (
            "expanded-chart",
            "ram-capacity-chart",
            "split-divider",
            "outer-scroll",
            "inner-scroll",
            "child-exited",
        ):
            artifacts.append(runner.artifact(session / (name + ".png")))
        for mode in ("schema", "json"):
            artifacts.append(
                runner.artifact(
                    output
                    / "native"
                    / ("session-recovery-" + mode)
                    / "rejected-specimen.json"
                )
            )
        for name in (
            "missing-native.json",
            "missing-native.png",
            "missing-device-specimen.json",
        ):
            artifacts.append(
                runner.artifact(output / "native/session-missing-device" / name)
            )
        artifacts.extend(
            runner.artifact(p) for p in sorted((output / "native").rglob("*.png"))
        )
        require(
            any(a["path"].endswith("expanded-chart.png") for a in artifacts),
            "missing reviewable physical chart",
        )
        result = {
            "status": "PASS",
            "steps": runner.steps,
            "test_count": sum(s.get("test_count", 0) for s in runner.steps.values()),
            "artifacts": artifacts,
        }
        (output / "manifest.json").write_text(json.dumps(result, indent=2))
        print(
            f"PASS {result['test_count']} executed tests; manifest={output / 'manifest.json'} sha256={sha256(output / 'manifest.json')}"
        )
    except BaseException as error:
        (output / "failure.json").write_text(
            json.dumps(
                {
                    "status": "FAIL",
                    "error": str(error),
                    "completed_steps": runner.steps,
                },
                indent=2,
            )
        )
        print(f"FAIL {error}; evidence={output}", flush=True)
        raise


if __name__ == "__main__":
    main()
