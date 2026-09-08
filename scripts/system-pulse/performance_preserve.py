"""Native Mac preservation checks, run outside the scored CPU windows."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

from performance_compare import require
from performance_macos import command, digest


def wait_for(operation, description, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = operation()
        if value:
            return value
        time.sleep(0.15)
    raise RuntimeError("Timed out waiting for " + description)


def read_json(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None


def history_seconds(tree):
    rows = [row for row in tree["rows"]
            if row.get("AXIdentifier") == "history:cpu:host/usage"]
    require(len(rows) == 1, "missing native CPU history")
    match = re.search(r"(\d+\.\d+) s history", rows[0].get("AXTitle", ""))
    require(match is not None, "missing CPU history duration")
    return float(match[1])


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"status": "FAIL", "source_commit": args.commit,
              "binary_sha256": digest(args.candidate),
              "reference_sha256": digest(args.reference)}
    result["preservation_harness_sha256"] = {
        name: digest(Path(__file__).with_name(name))
        for name in ("performance_preserve.py", "performance_tree.swift")
    }
    process = None
    awake = subprocess.Popen(["caffeinate", "-d", "-i"])

    def tree(action="snapshot", value=None):
        argv = [str(args.tree), str(process.pid), action]
        if value is not None:
            argv.append(value)
        return json.loads(command(argv))

    def quit_owned():
        if process is not None and process.poll() is None:
            tree("press-title", "Quit")
            process.wait(timeout=10)
            require(process.returncode == 0, "native Quit failed")

    def frame(path, minimum=3):
        def ready():
            value = read_json(path)
            return value if value and value["snapshot"]["sequence"] >= minimum else None
        return wait_for(ready, "fresh collector frame")

    def save(name, value):
        (args.output / name).write_text(json.dumps(value, indent=2) + "\n")

    try:
        frames = {}
        for label, binary in (("reference", args.reference), ("candidate", args.candidate)):
            state = args.output / (label + "-state")
            state.mkdir()
            diagnostic = args.output / (label + "-latest.json")
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith("SYSTEM_PULSE_")}
            environment.update(SYSTEM_PULSE_STATE_DIR=str(state.resolve()),
                               SYSTEM_PULSE_DIAGNOSTICS_PATH=str(diagnostic.resolve()))
            with (args.output / (label + ".log")).open("w") as log:
                process = subprocess.Popen([str(binary.resolve())], env=environment,
                                           stdout=log, stderr=subprocess.STDOUT)
                current = frame(diagnostic, 6)
                tree()  # Activate the native accessibility bridge before inspection.
                time.sleep(0.3)
                frames[label] = current
                save(label + "-frame.json", current)
                if label == "reference":
                    quit_owned()
                    continue
                result["pid"] = process.pid
                result["initial_history_seconds"] = history_seconds(tree())
                require(any(p["identity"]["pid"] == process.pid for p in current["snapshot"]["processes"]),
                        "the actual app process is absent from the snapshot")
                for name in ("monitors", "sensors"):
                    before = {row["id"] for row in frames["reference"]["snapshot"][name]}
                    after = {row["id"] for row in current["snapshot"][name]}
                    require(before == after, f"native {name} coverage or identities changed")
                    result[name + "_count"] = len(after)
                capacities = []
                readings = {row["sensor_id"]: row for row in current["snapshot"]["readings"]}
                for monitor in current["snapshot"]["monitors"]:
                    if monitor["kind"] != "Volume":
                        continue
                    reading = readings[monitor["id"] + "/capacity"]
                    native = os.statvfs(monitor["title"])
                    require(reading["availability"] == "Available", "native capacity unavailable")
                    raw = reading["observations"][0]
                    values = raw["integers"]
                    total = values["blocks"] * values["fragment_size"]
                    used = (values["blocks"] - values["free_blocks"]) * values["fragment_size"]
                    independent_total = native.f_blocks * native.f_frsize
                    independent_used = (native.f_blocks - native.f_bfree) * native.f_frsize
                    require(reading["value"] == used and reading["total"] == total,
                            "capacity does not match its raw native operands")
                    require(total == independent_total, "independent native total differs")
                    require(abs(used - independent_used) <= 16 * 1024 * 1024,
                            "independent used space differs by more than the 16 MiB capture-skew allowance")
                    require(raw["read_started_ns"] <= raw["captured_ns"] <= current["snapshot"]["capture_finished_ns"],
                            "capacity query window is invalid")
                    capacities.append({"id": monitor["id"], "reading": reading,
                                       "independent_total": independent_total,
                                       "independent_used": independent_used})
                require(capacities, "no native volumes were checked")
                result["capacities"] = capacities
                tree("press-id", "screen-tab:settings")
                time.sleep(0.5)
                tree("press-title", "Light")
                workspace = state / "workspace.json"
                wait_for(lambda: (read_json(workspace) or {}).get("appearance", {}).get("theme") == "light",
                         "saved light appearance")
                tree("press-id", "screen-tab:memory")
                wait_for(lambda: (read_json(workspace) or {}).get("screens", {}).get("active") == "memory",
                         "saved Memory screen")
                saved = read_json(workspace)
                start = frame(diagnostic)["snapshot"]["sequence"]
                tree("close")
                require(tree()["windows"] == 0, "dashboard did not close to tray")
                hidden = frame(diagnostic, start + 4)
                save("hidden-frame.json", hidden)
                require(tree()["windows"] == 0 and process.poll() is None, "background lifetime failed")
                result["hidden_start_sequence"] = start
                result["hidden_end_sequence"] = hidden["snapshot"]["sequence"]
                result["hidden_windows"] = 0
                tree("press-title", "Open System Pulse")
                wait_for(lambda: tree()["windows"] == 1, "reopened dashboard")
                reopened = read_json(workspace)
                require(reopened["screens"] == saved["screens"] and
                        reopened["appearance"] == saved["appearance"], "reopen lost settings")
                result["saved_settings"] = {key: saved[key] for key in ("screens", "appearance", "interval_ms")}
                result["reopened_settings"] = {key: reopened[key] for key in result["saved_settings"]}
                tree("press-id", "screen-tab:cpu")
                time.sleep(0.3)
                require(any(row.get("AXIdentifier") == "screen:cpu" for row in tree()["rows"]),
                        "native interaction failed after reopening")
                tree("press-id", "screen-tab:summary")
                time.sleep(0.3)
                reopened_tree = tree()
                save("reopened-tree.json", reopened_tree)
                result["reopened_history_seconds"] = history_seconds(reopened_tree)
                require(result["reopened_history_seconds"] >= result["initial_history_seconds"] + 3,
                        "background history was lost")
                save("reopened-frame.json", frame(diagnostic, hidden["snapshot"]["sequence"] + 1))
                quit_owned()
                result["quit_exit_code"] = process.returncode
                result["process_survived_quit"] = False
        result["status"] = "PASS"
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        if process is not None and process.poll() is None:
            try:
                quit_owned()
            except (OSError, subprocess.SubprocessError, ValueError):
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        awake.terminate()
        awake.wait(timeout=5)
        save("result.json", result)
    print("Native Mac preservation: PASS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for label in ("reference", "candidate", "tree", "output"):
        parser.add_argument("--" + label, type=Path, required=True)
    parser.add_argument("--commit", required=True)
    run(parser.parse_args())
