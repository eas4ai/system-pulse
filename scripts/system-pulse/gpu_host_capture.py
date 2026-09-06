#!/usr/bin/env python3
"""Build and retain one bounded native GPU attempt outside the source checkout.

Run on the target host from a clean committed checkout. --action-plan contains
predeclared semantic controls and scoped native selectors and press/scroll operations; every action
is performed by the platform helper and checked against actual persisted state.
Failed and locked-desktop attempts remain on disk and never earn acceptance.
"""

import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import threading
import time

from gpu_capture import CaptureChildren, owned_process, sha256, validate_native_frame
from gpu_evidence import read_json, read_lines, verify_host
from gpu_verify import ROOT, committed_inputs, outside_output
from host_accuracy import require
from gpu_intel_capture import anchor


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def action_plan(path):
    plan = read_json(path)
    require(
        isinstance(plan, list) and 6 <= len(plan) <= 60,
        "action plan count outside bound",
    )
    required = {"panel-collapse", "sensor-collapse", "scroll", "interval", "meter"}
    require(
        required <= {a["name"] for a in plan},
        "action plan omits required native operations",
    )
    for step in plan:
        require(
            isinstance(step.get("selector"), dict) and step["selector"],
            "missing predeclared native selector",
        )
        require(
            step["name"] in required
            and step["method"] in ("press", "scroll")
            and isinstance(step["target"], str)
            and 0 < len(step["target"]) <= 4096,
            "invalid native plan step",
        )
        require(
            step.get("phase", "load") in ("idle", "load", "interval", "recovery"),
            "invalid action phase",
        )
        if step["method"] == "scroll":
            require(
                type(step["value"]) is int and 0 < abs(step["value"]) <= 100,
                "invalid native scroll amount",
            )
    return plan


def retain_sources(output, inputs):
    for name, digest in inputs.items():
        source = ROOT / name
        target = output / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        require(sha256(target) == digest, "committed source changed while copying")


def build(output, target, inputs, records):
    command = [
        "cargo",
        "build",
        "--locked",
        "-p",
        "system-pulse",
        "--bin",
        "system-pulse",
        "-p",
        "system-pulse-collectors",
        "--bin",
        "pulse-snapshot",
    ]
    record = owned_process(
        output, "build", command, 3600, {"CARGO_TARGET_DIR": str(target)}
    )
    records.append(record)
    require(record["exit_code"] == 0, "native build failed")
    (output / "bin").mkdir()
    executables = {}
    for role, name in [
        ("application", "system-pulse"),
        ("collector", "pulse-snapshot"),
    ]:
        destination = output / "bin" / role
        shutil.copy2(target / "debug" / name, destination)
        executables[role] = str(destination.relative_to(output))
    if platform.system() == "Darwin":
        executable = output / "bin/observer"
        command = [
            "/usr/bin/clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fobjc-arc",
            "-framework",
            "Foundation",
            "-framework",
            "Metal",
            "-framework",
            "IOKit",
            "-framework",
            "ApplicationServices",
            str(output / "source/scripts/system-pulse/gpu_apple_native.m"),
            str(output / "source/scripts/system-pulse/gpu_apple_ax.m"),
            "-o",
            str(executable),
        ]
        record = owned_process(output, "helper-build", command, 60)
        records.append(record)
        require(record["exit_code"] == 0, "native helper compilation failed")
    else:
        shutil.copy2(Path("/usr/bin/python3").resolve(), output / "bin/observer")
        workload = output / "bin/workload"
        command = [
            "/usr/bin/cc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            str(output / "source/scripts/system-pulse/gpu_intel_workload.c"),
            "-lvulkan",
            "-o",
            str(workload),
        ]
        record = owned_process(output, "workload-build", command, 60)
        records.append(record)
        require(
            record["exit_code"] == 0,
            "Intel Vulkan workload prerequisite unavailable: compiler, headers or loader; see workload-build.stderr",
        )
        executables["workload"] = "bin/workload"
    executables["observer"] = "bin/observer"
    write(
        output / "build.json",
        dict(
            inputs=inputs,
            exit_code=0,
            executables=executables,
            source_commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            command=records[0]["command"],
            build_stdout=records[0]["stdout"],
            build_stderr=records[0]["stderr"],
        ),
    )
    return executables


class Diagnostics:
    def __init__(self, output):
        self.output = output
        self.stop = threading.Event()
        self.error = None
        self.thread = threading.Thread(
            target=self.collect, name="retained-gpu-diagnostics"
        )

    def collect(self):
        seen = set()
        size = 0
        try:
            with (self.output / "diagnostics.jsonl").open("x") as stream:
                while not self.stop.wait(0.05):
                    try:
                        path = self.output / "latest.json"
                        require(
                            path.stat().st_size <= 32 * 1024**2,
                            "diagnostic original exceeds size bound",
                        )
                        raw = path.read_text()
                        frame = json.loads(raw)
                    except FileNotFoundError:
                        continue
                    key = (frame["application_pid"], frame["render_revision"])
                    if key in seen:
                        continue
                    seen.add(key)
                    size += len(raw.encode())
                    require(
                        len(seen) <= 2000 and size <= 256 * 1024**2,
                        "diagnostic retention bound exceeded",
                    )
                    stream.write(json.dumps(frame, separators=(",", ":")) + "\n")
                    stream.flush()
        except BaseException as error:
            self.error = error

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, kind, value, traceback):
        self.stop.set()
        self.thread.join(timeout=5)
        require(not self.thread.is_alive(), "diagnostic reader did not stop")
        if self.error and kind is None:
            raise self.error


def state(output):
    return read_json(output / "state/workspace.json")


def wait_populated(output, pid, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            frame = read_json(output / "latest.json")
            if frame["application_pid"] == pid and frame["snapshot"]["sequence"] >= 2:
                state(output)
                return frame
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(0.1)
    raise TimeoutError("native application did not populate before deadline")


def console_session(original):
    require(
        isinstance(original, list) and len(original) == 1,
        "ambiguous native console registry",
    )
    sessions = original[0]["IOConsoleUsers"]
    active = [
        s
        for s in sessions
        if s.get("kCGSSessionOnConsoleKey") is True
        and s.get("kCGSessionLoginDoneKey") is True
    ]
    require(len(active) == 1, "native desktop has no unique logged-in console session")
    lock = original[0].get("IOConsoleLocked", active[0].get("CGSSessionScreenIsLocked"))
    require(type(lock) is bool, "native desktop lock state is not explicitly available")
    require(
        active[0].get("CGSSessionScreenIsLocked", lock) is lock,
        "contradictory native console lock facts",
    )
    return dict(locked=lock, on_console=True, login_done=True)


def native_attempt(output, executables, inputs, args, records):
    apple = platform.system() == "Darwin"
    observer = [str(output / executables["observer"])]
    if not apple:
        observer += [str(output / "source/scripts/system-pulse/gpu_intel_capture.py")]
    result = owned_process(
        output,
        "host-metadata",
        [str(output / executables["observer"]), "host"]
        if apple
        else observer + ["--host"],
        15,
    )
    records.append(result)
    require(
        result["exit_code"] == 0, "native host/provider metadata prerequisite failed"
    )
    host = read_lines(output / result["stdout"])
    require(len(host) == 1, "ambiguous native host metadata")
    write(output / "host.json", host[0])
    inventory_command = observer + (
        ["observe", "1", "100"] if apple else ["--count", "1"]
    )
    result = owned_process(output, "inventory", inventory_command, 15)
    records.append(result)
    require(result["exit_code"] == 0, "native independent inventory failed")
    raw = read_lines(output / result["stdout"])
    require(len(raw) == 1, "independent inventory emitted wrong frame count")
    write(output / "native-inventory.json", raw[0])
    if apple:
        from gpu_apple_capture import independent_inventory, normalize_observer

        inventory = independent_inventory(raw[0])
        ax = [str(output / executables["observer"]), "ax"]
    else:
        from gpu_intel_capture import independent_inventory, normalize_observer

        require(args.pci, "Intel capture requires independently selected --pci")
        inventory = independent_inventory(raw[0], args.pci)
        ax = [
            str(output / executables["observer"]),
            str(output / "source/scripts/system-pulse/gpu_linux_ax.py"),
        ]
    write(output / "inventory.json", inventory)
    if not apple:
        result = owned_process(
            output,
            "workload-provider",
            [
                str(output / executables["workload"]),
                "--metadata",
                inventory["device"]["pci"],
            ],
            15,
        )
        records.append(result)
        require(
            result["exit_code"] == 0,
            "Vulkan deployed provider version prerequisite failed",
        )
        provider = read_lines(output / result["stdout"])
        require(len(provider) == 1, "ambiguous Vulkan provider metadata")
        write(output / "workload-provider.json", provider[0])
    if apple:
        result = owned_process(
            output,
            "console-session",
            [
                "/usr/sbin/ioreg",
                "-a",
                "-l",
                "-w",
                "0",
                "-d",
                "1",
                "-k",
                "IOConsoleUsers",
            ],
            5,
        )
        records.append(result)
        require(result["exit_code"] == 0, "native console-session query failed")
        session = console_session(
            plistlib.loads((output / result["stdout"]).read_bytes())
        )
        write(output / "console-session.json", session)
        require(
            session["locked"] is False,
            "native desktop is locked; unlock the logged-in console before visible UI capture",
        )
    plan = action_plan(args.action_plan)
    write(output / "action-plan.json", plan)
    policy = dict(
        hardware_class=inventory["hardware_class"],
        device=inventory["device"],
        fields=inventory["fields"],
        declared_unix_ns=time.time_ns(),
        phases=["idle", "load", "interval", "recovery"],
        sample_count=60,
        warmup_samples=2,
        poll_interval_ns=100_000_000,
        max_query_ns=2_000_000_000,
        max_gap_ns=2_000_000_000,
        freshness_ns=5_000_000_000,
        deadline_ns=120_000_000_000,
        retries=0,
        rounding_ulps=4,
        workload_seconds=12,
        action_plan_sha256=sha256(output / "action-plan.json"),
    )
    write(output / "policy.json", policy)
    started = time.time_ns()
    actions = []
    phases = []
    (output / "state").mkdir()
    env = {
        "SYSTEM_PULSE_STATE_DIR": str(output / "state"),
        "SYSTEM_PULSE_DIAGNOSTICS_PATH": str(output / "latest.json"),
    }
    ax_index = 0
    with CaptureChildren(output) as children, Diagnostics(output):
        children.records.extend(records)

        def native(pid, tail):
            nonlocal ax_index
            role = "ax" + str(ax_index)
            ax_index += 1
            result = owned_process(
                output,
                role,
                ax + [str(pid)] + tail,
                20,
                {"SYSTEM_PULSE_GPU_MONITOR_ID": inventory["device"]["monitor_id"]},
            )
            children.records.append(result)
            require(
                result["exit_code"] == 0,
                "native action/census failed; originals retained",
            )
            parsed = read_lines(output / result["stdout"])
            require(len(parsed) == 1, "native helper emitted ambiguous result")
            return parsed[0], result["stdout"]

        def ready_native(pid):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                frame, path = native(pid, [])
                validate_native_frame(frame)
                if any(
                    e["identifier"] == inventory["device"]["monitor_id"] + ":summary"
                    for e in frame["elements"]
                ):
                    return frame, path
                time.sleep(0.1)
            raise TimeoutError(
                "native GPU tree did not populate before readiness deadline"
            )

        children.start(
            "observer",
            observer
            + (
                ["observe", "600", "100"]
                if apple
                else ["--count", "600", "--interval-ms", "100"]
            ),
            100,
        )
        time.sleep(0.5)
        children.start(
            "collector",
            [
                str(output / executables["collector"]),
                "--count",
                "60",
                "--interval-ms",
                "1000",
            ],
            90,
        )
        pid = children.start(
            "application", [str(output / executables["application"])], 110, env
        )
        wait_populated(output, pid)
        initial, initial_path = ready_native(pid)
        validate_native_frame(initial)
        require(
            any(
                e["identifier"] == inventory["device"]["monitor_id"] + ":summary"
                for e in initial["elements"]
            ),
            "native GPU tree has not populated",
        )
        write(output / "workspace-before.json", state(output))
        for phase in policy["phases"]:
            phase_start = time.time_ns()
            if phase == "load":
                if apple:
                    workload = observer + [
                        "workload",
                        str(inventory["device"]["registry_id"]),
                        str(policy["workload_seconds"]),
                    ]
                else:
                    workload = [
                        str(output / executables["workload"]),
                        inventory["device"]["pci"],
                        str(policy["workload_seconds"]),
                    ]
                children.start("workload", workload, 20)
            for step in [s for s in plan if s.get("phase", "load") == phase]:
                before = state(output)
                state_before_path = "action-" + str(len(actions)) + "-before.json"
                write(output / state_before_path, before)
                tail = [
                    json.dumps(dict(control=step["target"], selector=step["selector"])),
                    step["method"],
                ] + ([str(step["value"])] if "value" in step else [])
                result, path = native(pid, tail)
                time.sleep(0.5)
                after_state = state(output)
                state_after_path = "action-" + str(len(actions)) + "-after.json"
                write(output / state_after_path, after_state)
                result.update(
                    name=step["name"],
                    native_path=path,
                    state_before=before,
                    state_after=after_state,
                    state_before_path=state_before_path,
                    state_after_path=state_after_path,
                )
                actions.append(result)
            time.sleep(3 if phase in ("idle", "recovery") else 1)
            if phase == "load":
                require(
                    children.finish("workload")["exit_code"] == 0,
                    "native workload failed",
                )
            phases.append(
                dict(
                    name=phase,
                    started_unix_ns=phase_start,
                    finished_unix_ns=time.time_ns(),
                )
            )
        saved = state(output)
        write(output / "workspace-after.json", saved)
        before, before_path = native(pid, [])
        restart_anchor = anchor()
        restart_start = time.monotonic_ns()
        native(pid, ["close"])
        require(
            children.finish("application")["exit_code"] == 0,
            "native application did not close cleanly",
        )
        restored_pid = children.start(
            "application-restored", [str(output / executables["application"])], 30, env
        )
        wait_populated(output, restored_pid)
        after, after_path = ready_native(restored_pid)
        restored = state(output)
        write(output / "workspace-restored.json", restored)
        actions.append(
            dict(
                name="restore",
                method="restart",
                clock_anchor=restart_anchor,
                target="",
                return_code=0,
                started_ns=restart_start,
                finished_ns=time.monotonic_ns(),
                before=before,
                after=after,
                state_before=saved,
                state_after=restored,
                before_path=before_path,
                after_path=after_path,
                state_before_path="workspace-after.json",
                state_after_path="workspace-restored.json",
            )
        )
        native(restored_pid, ["close"])
        require(
            children.finish("application-restored")["exit_code"] == 0,
            "restored application did not close cleanly",
        )
        require(
            children.finish("collector")["exit_code"] == 0, "native collector failed"
        )
        require(children.finish("observer")["exit_code"] == 0, "native observer failed")
    shutil.copyfile(output / "collector.stdout", output / "snapshots.jsonl")
    shutil.copyfile(output / "observer.stdout", output / "native-observer.jsonl")
    with (output / "observer.jsonl").open("x") as stream:
        for frame in read_lines(output / "native-observer.jsonl"):
            stream.write(json.dumps(normalize_observer(frame, inventory)) + "\n")
    write(output / "actions.json", actions)
    write(output / "phases.json", phases)
    write(
        output / "recovery.json",
        dict(
            mode="not-induced",
            reason="No machine-wide sleep or driver permission transition was performed in this task-owned capture. Recovery phase follows workload completion; native API failure/reset sequences require the deterministic adapter suite.",
        ),
    )
    return dict(
        schema=1,
        mode="native",
        inputs=inputs,
        capture_root=str(output),
        hardware_class=inventory["hardware_class"],
        capture_started_unix_ns=started,
        capture_finished_unix_ns=time.time_ns(),
        executables={role: sha256(output / path) for role, path in executables.items()},
    )


def manifest(output, report):
    report["artifacts"] = [
        dict(path=str(p.relative_to(output)), bytes=p.stat().st_size, sha256=sha256(p))
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.name != "report.json"
    ]
    write(output / "report.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--action-plan", type=Path, required=True)
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--pci")
    args = parser.parse_args()
    args.action_plan = args.action_plan.resolve()
    args.target_dir = args.target_dir.resolve()
    action_plan(args.action_plan)
    require(platform.system() in ("Darwin", "Linux"), "unsupported native host")
    os.chdir(ROOT)
    inputs = committed_inputs()
    output = outside_output(args.output)
    records = []
    report = dict(schema=1, mode="failed-attempt", inputs=inputs)
    try:
        retain_sources(output, inputs)
        write(
            output / "launcher-host.json",
            dict(
                system=platform.system(),
                release=platform.release(),
                machine=platform.machine(),
                python=sys.version,
                started_unix_ns=time.time_ns(),
            ),
        )
        executables = build(output, args.target_dir, inputs, records)
        report = native_attempt(output, executables, inputs, args, records)
    except BaseException as error:
        write(
            output / "failure.json", dict(type=type(error).__name__, error=str(error))
        )
        if not (output / "lifecycle.json").exists():
            write(output / "lifecycle.json", records)
        manifest(output, report)
        print("FAILED native attempt retained at " + str(output), file=sys.stderr)
        return 1
    manifest(output, report)
    try:
        hardware, earned, counts = verify_host(output, inputs)
    except (AssertionError, KeyError, ValueError, TypeError, OSError) as error:
        print(
            "UNVERIFIED native attempt: " + str(error) + "; originals=" + str(output),
            file=sys.stderr,
        )
        return 1
    print(
        "Validated original "
        + hardware
        + " evidence: "
        + str(sum(counts.values()))
        + " comparisons; "
        + str(output)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
