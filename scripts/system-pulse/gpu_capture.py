"""Bounded task-owned subprocesses shared by GPU native capture commands."""

import json
import hashlib
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
from threading import Event
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


def clean_group(child, errors):
    """Escalate even if waiting or signaling is interrupted; reap the leader."""
    signals = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            child.poll()
            if not group_exists(child.pid):
                break
            try:
                os.killpg(child.pid, sig)
                signals.append(sig.name)
            except ProcessLookupError:
                break
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                child.poll()
                if not group_exists(child.pid):
                    break
                time.sleep(0.02)
        except BaseException as error:
            errors.append(("process-group cleanup", error))
    try:
        child.wait(timeout=3)
    except BaseException as error:
        errors.append(("leader reap", error))
    exists = True
    try:
        exists = group_exists(child.pid)
        require(not exists, "native process group survived bounded cleanup")
    except BaseException as error:
        errors.append(("process-group absence", error))
    return signals, exists


def retain_errors(primary, errors):
    """Expose secondary failures without replacing the original exception."""
    rows = [
        dict(stage=stage, type=type(error).__name__, message=str(error))
        for stage, error in errors
        if error is not primary
    ]
    if rows:
        primary.capture_errors = getattr(primary, "capture_errors", []) + rows
        try:
            print(json.dumps(dict(capture_errors=rows)), file=sys.stderr, flush=True)
        except BaseException:
            pass


def owned_process(output, role, command, timeout, env=None, stop_event=None):
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
    child, primary, record = None, None, None
    errors = []
    timed_out = False
    # Ownership begins before Popen, including publication and stream closure.
    try:
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
            deadline = started / 1e9 + timeout
            while child.poll() is None:
                if stop_event is not None and stop_event.is_set():
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    child.wait(timeout=min(remaining, 0.1))
                except subprocess.TimeoutExpired:
                    pass
    except BaseException as error:
        primary = error
    finally:
        if child is not None:
            cleanup_signals, exists = clean_group(child, errors)
            record = dict(
                role=role,
                pid=child.pid,
                command=command,
                exit_code=child.returncode,
                executable_sha256=executable_digest,
                timed_out=timed_out,
                reaped=child.returncode is not None,
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
            )
            for name in (stdout, stderr):
                try:
                    record[name.rsplit(".", 1)[1] + "_sha256"] = sha256(output / name)
                except BaseException as error:
                    errors.append(("log hashing", error))
            if primary is not None or errors:
                record["capture_error"] = type(primary or errors[0][1]).__name__
            try:
                (output / (role + "-finished.json")).write_text(
                    json.dumps(record, indent=2)
                )
            except BaseException as error:
                errors.append(("completion recording", error))
    if primary is None and errors:
        primary = errors[0][1]
    if primary is not None:
        primary.capture_record = record
        retain_errors(primary, errors)
        raise primary
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
        self.stops = {}
        self.records = []

    def __enter__(self):
        return self

    def start(self, role, command, timeout, env=None):
        require(role not in self.jobs, "duplicate native process role")
        stop_event = Event()
        future = self.pool.submit(
            owned_process, self.output, role, command, timeout, env, stop_event
        )
        self.stops[role] = stop_event
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
        if stop:
            self.stops[role].set()
        try:
            record = future.result(timeout=3610)
        except BaseException as error:
            record = getattr(error, "capture_record", None)
            if record is not None and record not in self.records:
                self.records.append(record)
            raise
        if record not in self.records:
            self.records.append(record)
        return record

    def __exit__(self, exception_type, exception, traceback):
        errors = []
        primary = exception
        if exception_type is not None:
            for stop_event in self.stops.values():
                stop_event.set()
        for role in self.jobs:
            try:
                self.finish(role, stop=primary is not None)
            except BaseException as error:
                if primary is None:
                    primary = error
                    for stop_event in self.stops.values():
                        stop_event.set()
                errors.append((role + " cleanup", error))
        try:
            self.pool.shutdown(wait=True)
        except BaseException as error:
            errors.append(("worker shutdown", error))
        try:
            (self.output / "lifecycle.json").write_text(
                json.dumps(self.records, indent=2) + "\n"
            )
        except BaseException as error:
            errors.append(("lifecycle recording", error))
        if errors:
            try:
                (self.output / "cleanup-errors.json").write_text(
                    json.dumps(
                        [
                            dict(
                                stage=stage,
                                type=type(error).__name__,
                                message=str(error),
                            )
                            for stage, error in errors
                        ],
                        indent=2,
                    )
                    + "\n"
                )
            except BaseException as error:
                errors.append(("cleanup-error recording", error))
        if primary is None and errors:
            primary = errors[0][1]
        if primary is not None:
            retain_errors(primary, errors)
            if exception is None:
                raise primary
