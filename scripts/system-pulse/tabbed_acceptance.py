"""Aggregate gate for the tabbed UI, preserving collector and compatibility checks."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from acceptance import ROOT, Runner, run_automated, sha256, validate_automated_steps, validate_host
from host_accuracy import require
from native_contract import check_transport_record
from native_session import private_session
from tabbed_contract import SCREENS, check_replay, check_metric


def validate_tabbed(runner, binary, output=None):
    output = output or runner.output / "native"
    result = json.loads((output / "result.json").read_text())
    check_replay(result, sha256(binary))
    check_transport_record(json.loads((output / "transport-cleanup.json").read_text()))
    paths = [output / "result.json", output / "transport-cleanup.json"]
    for session in ("native", "restart", "missing", "recovery", "recovered"):
        shutdown = json.loads((output / session / "shutdown.json").read_text())
        require(shutdown == {"exit_code": 0, "before_deadline": True}, "normal shutdown not verified")
        cleanup = json.loads((output / session / "cleanup.json").read_text())
        require(cleanup and all(item["exit_code"] == 0 and not item["proc_exists"] for item in cleanup),
                "owned application was not cleaned up normally")
        paths.extend(output / session / name for name in ("shutdown.json", "cleanup.json", "metadata.json"))
    paths.extend(sorted(output.rglob("*.png")))
    paths.extend(output / "native" / ("metric-" + screen + ".json") for screen in ("cpu", "memory"))
    required_images = [output / "native" / f"{prefix}-{screen}.png"
                       for prefix in ("screen", "minimum") for screen in SCREENS]
    require(all(path.is_file() and path.stat().st_size > 0 for path in required_images), "missing screen evidence")
    for screen in ("cpu", "memory"):
        metric = json.loads((output / "native" / f"metric-{screen}.json").read_text())
        check_metric(metric["frame"], metric["sensor_id"], metric["actual"], 1000)
        require(metric["actual"] == metric["expected"], "metric evidence disagrees")
    return [runner.artifact(path) for path in paths]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="system-pulse-tabbed-"))
    if args.output:
        output.mkdir(parents=True, exist_ok=False)
    require(not output.is_relative_to(ROOT), "acceptance output must be outside checkout")
    runner = Runner(output)
    result = {"status": "FAIL", "steps": runner.steps,
              "source_commit": subprocess.check_output(["rtk", "proxy", "git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    try:
        run_automated(runner)
        validate_automated_steps(runner)
        runner.step("host", [sys.executable, "-B", "scripts/system-pulse/host_capture.py",
                    "--output", str(output / "host"), "--binary", str(ROOT / "target/debug/pulse-snapshot")], timeout=90)
        artifacts = validate_host(runner)
        binary = ROOT / "target/debug/system-pulse"
        runner.step("native", private_session(ROOT / "scripts/system-pulse/tabbed_replay.py",
                    "--output", output / "native", "--binary", binary, log=output / "native.session.log"), timeout=600)
        artifacts.extend(validate_tabbed(runner, binary))
        result.update(status="PASS", binary_sha256=sha256(binary), artifacts=artifacts,
                      test_count=sum(step.get("test_count", 0) for step in runner.steps.values()))
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Tabbed acceptance: PASS; {result['test_count']} executed tests; evidence={output}", flush=True)


if __name__ == "__main__":
    main()
