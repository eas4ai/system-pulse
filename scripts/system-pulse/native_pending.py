"""Independent evidence for an unverified pending arrow interruption."""

from dataclasses import dataclass
import errno
import os
from pathlib import Path

from host_accuracy import parse_process_stat, require
from host_capture import observe


@dataclass(frozen=True)
class InterruptedNavigation:
    frame: dict
    path: list
    evidence: dict


def publication(frame):
    return {
        "sequence": frame["snapshot"]["sequence"],
        **{
            key: frame[key]
            for key in ("application_pid", "render_revision", "accepted_unix_ns")
        },
    }


def namespace(application_pid):
    root = Path("/proc").stat()
    driver = os.readlink("/proc/self/ns/pid")
    application = os.readlink(f"/proc/{application_pid}/ns/pid")
    require(driver == application, "navigation procfs PID namespace differs")
    return {
        "device": root.st_dev,
        "inode": root.st_ino,
        "pid_namespace": driver,
        "application_pid_namespace": application,
    }


def read_stat(expected, application_pid):
    pid = int(expected.split(":")[1])
    before = namespace(application_pid)
    source = f"/proc/{pid}/stat"
    result = observe(source, lambda: Path(source).read_text())
    result["raw"] = result.pop("value")
    result["namespace"] = before
    require(namespace(application_pid) == before, "navigation procfs namespace changed")
    result["identity"] = None
    if result["errno"] is None:
        try:
            parsed = parse_process_stat(result["raw"])
            result["identity"] = f"process:{parsed['pid']}:{parsed['start_ticks']}"
        except (ValueError, IndexError, TypeError) as error:
            result["parse_error"] = f"{type(error).__name__}: {error}"
    return result


def validate_stat(observation, expected, started, completed, baseline=None):
    require(isinstance(observation, dict), "missing independent navigation stat")
    start, end = observation.get("start"), observation.get("end")
    require(
        type(start) is int
        and type(end) is int
        and started <= start <= end <= completed,
        "invalid independent navigation stat window",
    )
    require(
        observation.get("source") == f"/proc/{int(expected.split(':')[1])}/stat",
        "wrong independent navigation stat source",
    )
    ns = observation.get("namespace")
    require(
        isinstance(ns, dict)
        and type(ns.get("device")) is int
        and type(ns.get("inode")) is int
        and isinstance(ns.get("pid_namespace"), str)
        and ns["pid_namespace"] == ns.get("application_pid_namespace"),
        "missing independent navigation stat namespace",
    )
    if baseline is not None:
        require(ns == baseline["namespace"], "navigation procfs namespace changed")
    error = observation.get("errno")
    if error in (errno.ENOENT, errno.ESRCH):
        require(
            observation.get("raw") is None and observation.get("identity") is None,
            "terminal navigation stat includes live evidence",
        )
        return "gone"
    require(
        error is None, "independent navigation stat read failed: " + str(observation)
    )
    require(
        isinstance(observation.get("raw"), str) and not observation.get("parse_error"),
        "malformed independent navigation stat",
    )
    try:
        parsed = parse_process_stat(observation["raw"])
    except (ValueError, IndexError, TypeError) as error:
        raise AssertionError("malformed independent navigation stat") from error
    actual = f"process:{parsed['pid']}:{parsed['start_ticks']}"
    require(
        observation.get("identity") == actual == expected,
        "independent navigation stat identity differs (PID reuse)",
    )
    return "live"
