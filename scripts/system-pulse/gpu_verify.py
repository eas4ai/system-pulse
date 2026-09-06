#!/usr/bin/env python3
"""GPU aggregate: full Linux preservation plus three independent hardware reports.

Native reports are supplied with repeated --report DIRECTORY arguments or the
os.pathsep-separated SYSTEM_PULSE_GPU_REPORTS environment variable. A missing
class remains unverified and makes the default command fail. Use
--development-tests-only for local verifier work; it emits no acceptance lines.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import acceptance
from gpu_capture import sha256
from gpu_evidence import CLASSES, read_json, requirement_results, verify_host
from host_accuracy import require

ROOT = acceptance.ROOT


def selected_test_count(text):
    return acceptance.test_count(text, "python")


def outside_output(path):
    path = path.resolve()
    require(
        not path.is_relative_to(ROOT),
        "GPU artifacts must be outside the source checkout",
    )
    require(not path.exists(), "GPU output directory must be fresh")
    path.mkdir(parents=True)
    return path


def declared_inputs():
    text = (ROOT / ".cairn/mechanisms/gpu-acceptance").read_text()
    section = text.split("inputs:\n", 1)[1].split("requirements:", 1)[0]
    paths = [
        line.strip()[2:]
        for line in section.splitlines()
        if line.strip().startswith("- ")
    ]
    require(paths, "empty declared GPU source inputs")
    return paths


def committed_inputs():
    paths = declared_inputs()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    require(
        not status.stdout.strip(),
        "GPU acceptance requires clean committed declared inputs",
    )
    files = subprocess.run(
        ["git", "ls-files", "-z", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=15,
    ).stdout.split(b"\0")
    result = {os.fsdecode(p): sha256(ROOT / os.fsdecode(p)) for p in files if p}
    require(result, "empty committed GPU source manifest")
    return result


def validate_preservation(directory):
    """Reuse the LIVE validators against originals, including the full native replay."""
    manifest = read_json(directory / "manifest.json")
    require(manifest["status"] == "PASS", "Linux preservation failed")
    runner = acceptance.Runner(directory)
    runner.steps = manifest["steps"]
    acceptance.validate_automated_steps(runner)
    acceptance.validate_host(runner)
    native = acceptance.read_native_result(runner)
    acceptance.validate_primary_native(runner, native)
    acceptance.validate_remaining_native(runner, native)
    for artifact in manifest["artifacts"]:
        path = Path(artifact["path"]).resolve()
        require(
            path.is_relative_to(directory.resolve())
            and path.is_file()
            and path.stat().st_size == artifact["bytes"]
            and sha256(path) == artifact["sha256"],
            "Linux preservation original artifact hash/size mismatch",
        )
    for step in runner.steps.values():
        path = Path(step["log"]).resolve()
        require(
            path.is_relative_to(directory.resolve())
            and sha256(path) == step["sha256"]
            and step["exit_code"] == 0
            and step["timed_out"] is False,
            "Linux preservation command log mismatch",
        )
    return manifest["test_count"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path, action="append", default=[])
    parser.add_argument("--development-tests-only", action="store_true")
    args = parser.parse_args()
    output = (
        outside_output(args.output)
        if args.output
        else Path(tempfile.mkdtemp(prefix="system-pulse-gpu-"))
    )
    runner = acceptance.Runner(output)
    errors = []
    hosts = {}
    preservation = False
    automated = False
    reports = args.report or [
        Path(p)
        for p in os.environ.get("SYSTEM_PULSE_GPU_REPORTS", "").split(os.pathsep)
        if p
    ]
    require(len(reports) <= 3, "at most one report per required hardware class")
    print("GPU evidence directory: " + str(output), flush=True)
    try:
        runner.step(
            "gpu-verifier-tests",
            [
                sys.executable,
                "-B",
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/system-pulse",
                "-p",
                "test_gpu_*.py",
                "-v",
            ],
            "python",
            60,
        )
        automated = True
    except (AssertionError, OSError, ValueError, KeyError, TypeError) as error:
        errors.append("verifier tests: " + str(error))
    if args.development_tests_only:
        result = dict(mode="development", steps=runner.steps, errors=errors)
        (output / "development.json").write_text(json.dumps(result, indent=2))
        print(
            "Development checks only; no GPU acceptance claim. " + str(output),
            flush=True,
        )
        return 0 if automated else 1
    try:
        inputs = committed_inputs()
    except (AssertionError, OSError, subprocess.SubprocessError) as error:
        errors.append("committed inputs: " + str(error))
        inputs = {}
        automated = False
    try:
        runner.step(
            "linux-preservation",
            [
                sys.executable,
                "-B",
                "scripts/system-pulse/verify.py",
                "--output",
                str(output / "linux-preservation"),
            ],
            timeout=3600,
        )
        validate_preservation(output / "linux-preservation")
        preservation = True
    except (AssertionError, OSError, ValueError, KeyError, TypeError) as error:
        errors.append("Linux preservation: " + str(error))
    for directory in reports:
        try:
            require(inputs, "no committed source binding")
            name, earned, counts = verify_host(directory.resolve(), inputs)
            require(name not in hosts, "duplicate hardware-class report")
            hosts[name] = earned
            print(
                f"Validated original {name} comparisons: {sum(counts.values())}",
                flush=True,
            )
        except (
            AssertionError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            OverflowError,
        ) as error:
            errors.append(str(directory) + ": " + str(error))
    for name in sorted(CLASSES - set(hosts)):
        errors.append(name + ": missing valid native report; hardware class unverified")
    results = requirement_results(hosts, preservation, automated)
    for number, passed in results.items():
        print(f"cairn: GPU-{number:03}: {'pass' if passed else 'fail'}", flush=True)
    result = dict(
        schema=1,
        status="PASS" if all(results.values()) else "FAIL",
        inputs=inputs,
        requirements={f"GPU-{n:03}": v for n, v in results.items()},
        hardware={k: sorted(v) for k, v in hosts.items()},
        reports=[str(p.resolve()) for p in reports],
        steps=runner.steps,
        errors=errors,
    )
    (output / "manifest.json").write_text(json.dumps(result, indent=2))
    for error in errors:
        print("Unverified: " + error, file=sys.stderr, flush=True)
    print(
        result["status"] + " GPU aggregate; manifest=" + str(output / "manifest.json"),
        flush=True,
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
