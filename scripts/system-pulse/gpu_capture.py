"""Bounded task-owned subprocesses shared by GPU native capture commands."""

import json
import hashlib
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from host_accuracy import require
from gpu_evidence import visible


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def group_exists(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def clean_group(pid):
    signals = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not group_exists(pid):
            break
        try:
            os.killpg(pid, sig)
            signals.append(sig.name)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + 2
        while group_exists(pid) and time.monotonic() < deadline:
            time.sleep(0.02)
    return signals, group_exists(pid)


def owned_process(output, role, command, timeout, env=None):
    require(
        0 < timeout <= 3600 and role.replace("-", "").isalnum(),
        "invalid child bounds/name",
    )
    started = time.monotonic_ns()
    started_unix_ns = time.time_ns()
    environment = dict(os.environ)
    environment.update(env or {})
    environment["OBJC_DEBUG_MISSING_POOLS"] = "YES"
    environment.pop("SYSTEM_PULSE_DIAGNOSTICS_TRACE", None)
    stdout, stderr = role + ".stdout", role + ".stderr"
    executable = shutil.which(command[0])
    require(executable is not None, "native executable not found")
    executable_digest = sha256(executable)
    timed_out = False
    with (output / stdout).open("x") as out, (output / stderr).open("x") as err:
        child = subprocess.Popen(
            command, stdout=out, stderr=err, env=environment, start_new_session=True
        )
        (output / (role + "-started.json")).write_text(
            json.dumps(
                dict(
                    pid=child.pid,
                    command=command,
                    started_ns=started,
                    started_unix_ns=started_unix_ns,
                    deadline_ns=started + int(timeout * 1e9),
                )
            )
        )
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=3)
    cleanup_signals, exists = clean_group(child.pid)
    record = dict(
        role=role,
        pid=child.pid,
        command=command,
        exit_code=child.returncode,
        executable_sha256=executable_digest,
        timed_out=timed_out,
        reaped=child.poll() is not None,
        proc_exists=exists,
        cleanup_signals=cleanup_signals,
        started_ns=started,
        finished_ns=time.monotonic_ns(),
        started_unix_ns=started_unix_ns,
        finished_unix_ns=time.time_ns(),
        deadline_ns=started + int(timeout * 1e9),
        stdout=stdout,
        stderr=stderr,
        environment={
            k: environment[k]
            for k in (
                "OBJC_DEBUG_MISSING_POOLS",
                "SYSTEM_PULSE_GPU_MONITOR_ID",
                "SYSTEM_PULSE_STATE_DIR",
                "SYSTEM_PULSE_DIAGNOSTICS_PATH",
            )
            if k in environment
        },
        stdout_sha256=sha256(output / stdout),
        stderr_sha256=sha256(output / stderr),
    )
    (output / (role + "-finished.json")).write_text(json.dumps(record, indent=2))
    return record


def validate_workload(record, registry_id, seconds):
    require(
        record["registry_id"] == registry_id
        and type(record["pid"]) is int
        and record["pid"] > 0
        and 0 < record["bytes"] <= 64 * 1024**2
        and type(record["commands_completed"]) is int
        and record["commands_completed"] > 0
        and record["max_in_flight"] == 1
        and 0 < record["duration_ns"] <= seconds * 1e9,
        "unbounded, incomplete or wrong-device Metal workload",
    )


def validate_native_frame(frame):
    require(
        frame["complete"] is True
        and frame["elements"]
        and any(visible(e) for e in frame["elements"]),
        "no complete visible native frame",
    )
    from gpu_desktop import validate_native_geometry

    validate_native_geometry(frame)


class CaptureChildren:
    """Every concurrent native child still uses the bounded, retained runner."""

    def __init__(self, output):
        self.output = Path(output)
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.jobs = {}
        self.records = []

    def __enter__(self):
        return self

    def start(self, role, command, timeout, env=None):
        require(role not in self.jobs, "duplicate native process role")
        future = self.pool.submit(
            owned_process, self.output, role, command, timeout, env
        )
        self.jobs[role] = future
        started = self.output / (role + "-started.json")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if future.done():
                future.result()
            try:
                return json.loads(started.read_text())["pid"]
            except (FileNotFoundError, json.JSONDecodeError):
                time.sleep(0.01)
        raise TimeoutError("native child did not publish its owned PID")

    def finish(self, role, stop=False):
        future = self.jobs[role]
        if stop and not future.done():
            started = json.loads((self.output / (role + "-started.json")).read_text())
            try:
                os.killpg(started["pid"], signal.SIGTERM)
            except ProcessLookupError:
                pass
        record = future.result(timeout=3606)
        if record not in self.records:
            self.records.append(record)
        return record

    def __exit__(self, exception_type, exception, traceback):
        errors = []
        for role in self.jobs:
            try:
                self.finish(role, stop=exception_type is not None)
            except BaseException as error:
                errors.append(str(error))
        self.pool.shutdown(wait=True)
        (self.output / "lifecycle.json").write_text(
            json.dumps(self.records, indent=2) + "\n"
        )
        if errors:
            (self.output / "cleanup-errors.json").write_text(
                json.dumps(errors, indent=2) + "\n"
            )
            if exception_type is None:
                raise RuntimeError("native cleanup failed: " + "; ".join(errors))
