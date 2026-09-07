"""Predeclared controlled coverage and conservative process-exit classification."""

import errno
import json

from host_accuracy import require


CONTROLLED_FIELDS = {
    "cpu_percent": ("utime_ticks", "stime_ticks"),
    "read_bytes_per_second": ("bytes",),
    "write_bytes_per_second": ("bytes",),
}
WARMUP_REASON = "Waiting for a second counter observation"


def validate_window(window, context):
    require(
        len(window) == 2
        and all(type(value) is int for value in window)
        and window[0] <= window[1],
        f"invalid ordered integer window: {context}",
    )


def declare_policy(child_info, declared_ns):
    stat = child_info["stat"]
    validate_window((stat["start"], stat["end"]), "controlled declaration stat")
    require(stat["errno"] is None and stat["value"], "controlled child stat missing")
    identity = dict(
        pid=stat["value"]["pid"], start_time_ticks=stat["value"]["start_ticks"]
    )
    require(
        stat["source"] == f"/proc/{identity['pid']}/stat"
        and stat["end"] <= declared_ns,
        "controlled child declaration lacks prior identity evidence",
    )
    return {
        "version": 1,
        "declared_ns": declared_ns,
        "controlled_identity": identity,
        "required_fields": {
            field: list(keys) for field, keys in CONTROLLED_FIELDS.items()
        },
        "initial_warmup": {
            "availability": "WarmingUp",
            "reason": WARMUP_REASON,
            "operands": 1,
        },
        "later_snapshots": {"availability": "Available", "operands": 2},
        "ordinary_exit_gap": "unverified_after_only_with_matched_before_and_terminal_stat",
        "counter_bound": "before <= collector <= after; no inferred endpoint",
    }


def validate_policy(policy, child_info):
    require(isinstance(policy, dict), "controlled process policy missing")
    require(type(policy.get("declared_ns")) is int, "invalid process policy timestamp")
    require(
        json.dumps(policy, sort_keys=True)
        == json.dumps(
            declare_policy(child_info, policy["declared_ns"]), sort_keys=True
        ),
        "invalid controlled process policy",
    )
    return policy["controlled_identity"]


def controlled_requirements(policy, snapshots):
    """Enumerate each mandatory operand before counting any verified brackets."""
    if policy is None:
        return []
    identity = policy["controlled_identity"]
    required = []
    for index, snapshot in enumerate(snapshots):
        rows = [row for row in snapshot["processes"] if row["identity"] == identity]
        require(len(rows) == 1, "controlled child missing or duplicated")
        for field, keys in CONTROLLED_FIELDS.items():
            reading = rows[0].get(field)
            require(
                isinstance(reading, dict), f"controlled comparison missing: {field}"
            )
            warmup = index == 0 and reading["availability"] == "WarmingUp"
            require(
                (
                    warmup
                    and reading["reason"] == WARMUP_REASON
                    and reading["value"] is None
                )
                or reading["availability"] == "Available",
                f"controlled comparison unavailable: {field}",
            )
            operands = reading["observations"]
            require(
                len(operands) == (1 if warmup else 2),
                f"controlled operand count: {field}",
            )
            for operand in operands:
                require(
                    set(keys) <= operand["integers"].keys(),
                    f"controlled counters missing: {field}",
                )
            required.append(
                {
                    "snapshot_sequence": snapshot["sequence"],
                    "sensor_id": reading["sensor_id"],
                    "field": field,
                    "availability": reading["availability"],
                    "operands": len(operands),
                    "keys": list(keys),
                }
            )
    return required


def comparison_coverage(required, brackets, missing, unverified):
    verified = {
        (b["snapshot_sequence"], b["sensor_id"], b["observation_index"], b["key"])
        for b in brackets
    }
    controlled = []
    for item in required:
        expected = {
            (item["snapshot_sequence"], item["sensor_id"], index, key)
            for index in range(item["operands"])
            for key in item["keys"]
        }
        count = len(expected & verified)
        controlled.append(
            dict(item, required_brackets=len(expected), verified_brackets=count)
        )
    return {
        "verified_brackets": len(brackets),
        "unverified_exit_gaps": len(unverified),
        "failed_brackets": len(missing),
        "controlled": controlled,
        "controlled_complete": bool(controlled)
        and all(c["required_brackets"] == c["verified_brackets"] for c in controlled),
    }


def classify_exit_gap(gap, controlled_identity):
    """Exit proves only absence; it supplies no counter value or upper bound."""
    identity = gap["identity"]
    if identity is None or identity == controlled_identity:
        return False
    window = gap["query_window"]
    validate_window(window, "process query")
    for sample in gap["external_windows"]:
        validate_window((sample["start"], sample["end"]), "process counter")
    for attempt in gap["external_attempts"]:
        for source in ("stat", "io", "process_enumeration"):
            raw = attempt[source]
            if raw is not None:
                validate_window((raw["start"], raw["end"]), source)
    before = [s for s in gap["external_windows"] if s["end"] <= window[0]]
    after = [s for s in gap["external_windows"] if s["start"] >= window[1]]
    if not before or after:
        return False
    before = max(before, key=lambda sample: sample["end"])
    require(
        before["value"] <= gap["value"],
        "counter outside observed lower bound despite exit",
    )
    pid = identity["pid"]
    attempts = sorted(
        gap["external_attempts"],
        key=lambda a: (a["stat"] or a["process_enumeration"])["start"],
    )
    gap["external_attempts"] = attempts
    terminal = None
    seen_terminal = False
    for attempt in attempts:
        io = attempt["io"]
        if (
            io is not None
            and io["end"] >= before["start"]
            and (
                io["source"] != f"/proc/{pid}/io"
                or io["errno"] not in (None, errno.ENOENT, errno.ESRCH)
            )
        ):
            return False
        stat = attempt["stat"]
        if stat is None or stat["end"] < before["start"]:
            continue
        if attempt.get("prior_identity") not in (None, identity):
            return False
        if stat["source"] != f"/proc/{pid}/stat":
            return False
        if stat["errno"] in (errno.ENOENT, errno.ESRCH):
            if stat["value"] is not None or stat["end"] < window[0]:
                return False
            seen_terminal = True
            if terminal is None and stat["start"] >= window[1]:
                terminal = stat
        elif stat["errno"] is not None or not stat["value"]:
            return False
        else:
            value = stat["value"]
            if (
                seen_terminal
                or value["pid"] != pid
                or value["start_ticks"] != identity["start_time_ticks"]
            ):
                return False
    if terminal is None:
        return False
    gap.update(classification="unverified_exit_gap", before=before, terminal=terminal)
    return True
