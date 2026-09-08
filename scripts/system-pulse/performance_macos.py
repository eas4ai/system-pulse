"""Run the fixed, isolated release CPU comparison on the native MacBook."""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import time

from performance_compare import compare


class TaskInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ("virtual_size", "resident_size", "total_user", "total_system",
                 "threads_user", "threads_system")] + [
                    (name, ctypes.c_int32) for name in
                    ("policy", "faults", "pageins", "cow_faults", "messages_sent",
                     "messages_received", "syscalls_mach", "syscalls_unix", "csw",
                     "threadnum", "numrunning", "priority")]


def command(args):
    return subprocess.check_output(args, text=True, timeout=15).strip()


def host():
    power = command(["pmset", "-g", "batt"]).splitlines()[0]
    match = re.search(r"'([^']+)'", power)
    if not match:
        raise RuntimeError("Could not establish current power source")
    return {"chip": command(["sysctl", "-n", "machdep.cpu.brand_string"]),
            "logical_cpus": int(command(["sysctl", "-n", "hw.logicalcpu"])),
            "os_version": command(["sw_vers", "-productVersion"]),
            "power_source": match[1]}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def census():
    monitors, conflicts = [], []
    for line in command(["ps", "-axo", "pid=,ppid=,comm="]).splitlines():
        pid, parent, executable = line.strip().split(None, 2)
        name = Path(executable).name
        if name.startswith("system-pulse"):
            monitors.append(int(pid))
        # macOS keeps its own spindump service running under launchd even when
        # no profiling session exists. A separately launched profiler conflicts.
        system_spindump = parent == "1" and executable == "/usr/sbin/spindump"
        if not system_spindump and name in {"cargo", "rustc", "swiftc", "swift-frontend", "clang", "clang++",
                    "sample", "spindump", "xctrace", "stress", "stress-ng", "yes",
                    "pulse-snapshot", "pulse-discovery-probe", "capacity-probe"}:
            conflicts.append({"pid": int(pid), "name": name})
    return sorted(monitors), conflicts


def cpu_counter(library, process, binary):
    if process.poll() is not None:
        raise RuntimeError("Owned monitor exited during measurement")
    path = ctypes.create_string_buffer(4096)
    if library.proc_pidpath(process.pid, path, len(path)) <= 0:
        raise RuntimeError("Could not read executable identity")
    if Path(os.fsdecode(path.value)).resolve() != binary.resolve():
        raise RuntimeError("Process executable changed")
    info = TaskInfo()
    start = time.monotonic_ns()
    size = library.proc_pidinfo(process.pid, 4, 0, ctypes.byref(info), ctypes.sizeof(info))
    end = time.monotonic_ns()
    if size != ctypes.sizeof(info):
        raise RuntimeError("Could not read complete native process CPU counters")
    return info.total_user + info.total_system, (start + end) // 2


def write_receipt(path, receipt):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def run(args):
    if platform.system() != "Darwin":
        raise RuntimeError("Native macOS is required")
    args.output.mkdir(parents=True, exist_ok=False)
    receipt_path = args.output / "measurements.json"
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    library.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                    ctypes.c_void_p, ctypes.c_int]
    library.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    receipt = {"version": 1, "host": host(), "binaries": {}, "runs": []}
    receipt["measurement_harness_sha256"] = {
        name: digest(Path(__file__).with_name(name))
        for name in ("performance_macos.py", "performance_ax.swift")
    }
    for label in ("reference", "candidate"):
        binary = getattr(args, label)
        receipt["binaries"][label] = {"commit": getattr(args, label + "_commit"),
                                       "sha256": digest(binary), "release_locked": True}
    awake = subprocess.Popen(["caffeinate", "-d", "-i"])
    try:
        for mode in ("summary", "tray"):
            for repetition in (1, 2, 3):
                order = ("candidate", "reference") if repetition == 2 else ("reference", "candidate")
                for label in order:
                    preflight = census()
                    if any(preflight):
                        receipt["failed_preflight"] = {"monitor_pids": preflight[0],
                                                       "conflicting_processes": preflight[1]}
                        raise RuntimeError("Another monitor, compiler or profiler is running")
                    binary = getattr(args, label).resolve()
                    name = f"{mode}-{repetition}-{label}"
                    state = args.output / (name + "-state")
                    state.mkdir()
                    environment = {key: value for key, value in os.environ.items()
                                   if not key.startswith("SYSTEM_PULSE_")}
                    environment["SYSTEM_PULSE_STATE_DIR"] = str(state.resolve())
                    process = None
                    with (args.output / (name + ".log")).open("w") as log:
                        try:
                            process = subprocess.Popen([str(binary)], env=environment,
                                                       stdout=log, stderr=subprocess.STDOUT)
                            time.sleep(3)
                            subprocess.check_output([str(args.ax), str(process.pid), "prepare"],
                                                    text=True, timeout=30)
                            time.sleep(1)
                            if mode == "tray":
                                command([str(args.ax), str(process.pid), "close"])
                                time.sleep(1)
                            warmup = time.monotonic()
                            time.sleep(30)
                            workspace = json.loads((state / "workspace.json").read_text())
                            if workspace.get("interval_ms") != 1000:
                                raise RuntimeError("The isolated workspace is not sampling at one second")
                            row = {"mode": mode, "binary": label, "repetition": repetition,
                                   "pid": process.pid, "process_start": command(
                                       ["ps", "-p", str(process.pid), "-o", "lstart="]),
                                   "host": host(), "interval_seconds": 1,
                                   "warmup_seconds": time.monotonic() - warmup,
                                   "diagnostics_enabled": False}
                            row["windows_before"] = json.loads(command(
                                [str(args.ax), str(process.pid), "snapshot"]))
                            expected = [{"width": 1280, "height": 880, "screen": "Summary"}] if mode == "summary" else []
                            if row["windows_before"] != expected:
                                raise RuntimeError("Native window does not match the measurement protocol")
                            row["binary_sha256_before"] = digest(binary)
                            row["monitor_pids_before"], row["conflicting_processes_before"] = census()
                            row["cpu_before_ns"], row["monotonic_before_ns"] = cpu_counter(library, process, binary)
                            time.sleep(60)
                            row["cpu_after_ns"], row["monotonic_after_ns"] = cpu_counter(library, process, binary)
                            row["monitor_pids_after"], row["conflicting_processes_after"] = census()
                            row["binary_sha256_after"] = digest(binary)
                            row["windows_after"] = json.loads(command(
                                [str(args.ax), str(process.pid), "snapshot"]))
                            row["process_survived"] = process.poll() is None
                            if json.loads((state / "workspace.json").read_text()).get("interval_ms") != 1000:
                                raise RuntimeError("Sampling interval changed during observation")
                            if row["host"] != host():
                                raise RuntimeError("Power source or host changed during observation")
                            receipt["runs"].append(row)
                            write_receipt(receipt_path, receipt)
                            percent = 100 * (row["cpu_after_ns"] - row["cpu_before_ns"]) / (
                                row["monotonic_after_ns"] - row["monotonic_before_ns"])
                            print(f"{name}: {percent:.3f}% of one CPU", flush=True)
                        finally:
                            if process is not None and process.poll() is None:
                                try:
                                    command([str(args.ax), str(process.pid), "quit"])
                                    process.wait(timeout=10)
                                except (subprocess.SubprocessError, OSError):
                                    process.terminate()
                                    try:
                                        process.wait(timeout=5)
                                    except subprocess.TimeoutExpired:
                                        process.kill()
                                        process.wait(timeout=5)
                                    raise RuntimeError("Native quit failed; owned process was stopped")
        receipt["comparison"] = compare(receipt)
        write_receipt(receipt_path, receipt)
        print(json.dumps(receipt["comparison"], indent=2), flush=True)
    except BaseException as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        awake.terminate()
        awake.wait(timeout=5)
        write_receipt(receipt_path, receipt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for label in ("reference", "candidate"):
        parser.add_argument("--" + label, type=Path, required=True)
        parser.add_argument("--" + label + "-commit", required=True)
    parser.add_argument("--ax", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    run(parser.parse_args())
