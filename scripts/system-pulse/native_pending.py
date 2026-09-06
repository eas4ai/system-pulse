"""Native acknowledgement and independent exit evidence for pending arrow batches."""

from dataclasses import dataclass
import errno
import math
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


_MAX_VALUE = (1 << 64) - 1
_PRIOR_BINDINGS = (
    "expected",
    "target",
    "endpoint_index",
    "keys",
    "batch_deadline",
    "deadline",
    "dispatch_started",
    "dispatch_completed",
)


def _bounded_integer(value):
    return type(value) is int and 0 <= value <= _MAX_VALUE


def _bounded_number(value):
    return (
        type(value) in (int, float)
        and 0 <= value <= _MAX_VALUE
        and math.isfinite(value)
    )


def _bounded_identity(value):
    if not isinstance(value, str) or len(value) > 64:
        return False
    parts = value.split(":")
    return (
        len(parts) == 3
        and parts[0] == "process"
        and all(
            part.isascii() and part.isdecimal() and _bounded_integer(int(part))
            for part in parts[1:]
        )
    )


def _valid_publication(value):
    return (
        isinstance(value, dict)
        and set(value)
        == {"application_pid", "sequence", "render_revision", "accepted_unix_ns"}
        and all(_bounded_integer(field) for field in value.values())
    )


def capture_acknowledgement(identity, frame):
    """Summarize an already returned positive native ACK without retaining its frame."""
    if not _bounded_identity(identity):
        return None
    try:
        published = publication(frame)
        rows = frame["snapshot"]["processes"]
        if not _valid_publication(published) or not isinstance(rows, list):
            return None
        index, count = None, 0
        for position, row in enumerate(rows):
            current = row["identity"]
            if f"process:{current['pid']}:{current['start_time_ticks']}" == identity:
                index, count = position, count + 1
        if count != 1 or not _bounded_integer(index):
            return None
        return {"identity": identity, "index": index, "publication": published}
    except (KeyError, TypeError):
        return None


def prepare_prior_acknowledgement(acknowledgement, pending, issued_ids):
    """Optionally bind an ACK to existing issue-frame identities before dispatch."""
    if (
        acknowledgement is None
        or acknowledgement["publication"] != pending["publication"]
    ):
        return None
    previous, index = acknowledgement["identity"], acknowledgement["index"]
    expected, target = pending["expected"], pending["target"]
    endpoint, keys = pending["endpoint_index"], pending["keys"]
    if (
        previous != pending["issued_selection"]
        or not all(_bounded_identity(value) for value in (previous, expected, target))
        or len({previous, expected, target}) != 3
        or not all(
            issued_ids.count(value) == 1 for value in (previous, expected, target)
        )
        or not 0 <= index < len(issued_ids)
        or not 0 <= endpoint < len(issued_ids)
        or issued_ids[index] != previous
        or issued_ids[endpoint] != expected
        or keys not in (["Up"], ["Up", "Up"], ["Down"], ["Down", "Down"])
    ):
        return None
    direction = 1 if keys[0] == "Down" else -1
    if endpoint != index + direction * len(keys) or direction * (
        issued_ids.index(target) - index
    ) <= len(keys):
        return None
    return {
        **acknowledgement,
        **{
            field: pending[field]
            for field in _PRIOR_BINDINGS
            if not field.startswith("dispatch_")
        },
        "keys": list(keys),
    }


class PriorSelectionPrefix:
    """A same-publication prior ACK prefix can only prevent a new competing block."""

    def __init__(self, pending):
        self.active = False
        self.identity = None
        self.issued = None
        if pending is None or "prior_acknowledgement" not in pending:
            return
        proof = pending["prior_acknowledgement"]
        require(
            isinstance(proof, dict)
            and set(proof) == {"identity", "index", "publication", *_PRIOR_BINDINGS}
            and _bounded_identity(proof["identity"])
            and _bounded_integer(proof["index"])
            and _valid_publication(proof["publication"])
            and proof["identity"] == pending.get("issued_selection")
            and proof["publication"] == pending["publication"]
            and all(proof[field] == pending[field] for field in _PRIOR_BINDINGS)
            and all(_bounded_identity(proof[field]) for field in ("expected", "target"))
            and len({proof["identity"], proof["expected"], proof["target"]}) == 3
            and _bounded_integer(proof["endpoint_index"])
            and all(
                _bounded_integer(proof[field])
                for field in ("dispatch_started", "dispatch_completed")
            )
            and all(
                _bounded_number(proof[field])
                for field in ("batch_deadline", "deadline")
            )
            and proof["keys"] in (["Up"], ["Up", "Up"], ["Down"], ["Down", "Down"])
            and proof["endpoint_index"]
            == proof["index"]
            + (1 if proof["keys"][0] == "Down" else -1) * len(proof["keys"]),
            "invalid prior native acknowledgement binding",
        )
        self.identity, self.issued, self.active = (
            proof["identity"],
            proof["publication"],
            True,
        )

    def publication(self, frame):
        if not self.active:
            return
        try:
            self.active = publication(frame) == self.issued
        except (KeyError, TypeError):
            self.active = False

    def selection(self, identity):
        if self.active and identity == self.identity:
            return True
        self.active = False
        return False


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
