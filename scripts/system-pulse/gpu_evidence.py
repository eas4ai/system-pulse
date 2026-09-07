"""Fail-closed validation of retained GPU host evidence, never report PASS flags."""

import hashlib
import json
import math
from pathlib import Path
import re

from host_accuracy import require

CLASSES = {"intel-integrated", "intel-discrete", "apple-silicon"}
ACTIONS = {
    "panel-collapse",
    "sensor-collapse",
    "scroll",
    "interval",
    "meter",
    "restore",
}
ORIGINALS = {
    "host.json",
    "policy.json",
    "inventory.json",
    "observer.jsonl",
    "snapshots.jsonl",
    "actions.json",
    "lifecycle.json",
    "build.json",
    "workspace-before.json",
    "workspace-after.json",
    "workspace-restored.json",
    "native-inventory.json",
    "native-observer.jsonl",
    "diagnostics.jsonl",
    "action-plan.json",
    "phases.json",
    "recovery.json",
    "collector.stdout",
    "observer.stdout",
    "inventory.stdout",
}


def safe_path(root, name):
    require(
        isinstance(name, str) and name and not Path(name).is_absolute(),
        "invalid artifact path",
    )
    p = root / name
    require(
        ".." not in Path(name).parts
        and p.resolve().is_relative_to(root.resolve())
        and not p.is_symlink(),
        "artifact escapes capture directory",
    )
    return p


def artifact(root, record):
    p = safe_path(root, record["path"])
    require(
        p.is_file()
        and type(record["bytes"]) is int
        and 0 <= record["bytes"] <= 1024**3
        and p.stat().st_size == record["bytes"],
        "missing original or artifact size mismatch",
    )
    with p.open("rb") as stream:
        hasher = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
        digest = hasher.hexdigest()
    require(digest == record["sha256"], "artifact hash mismatch")
    return p


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def floating(value):
        result = float(value)
        require(math.isfinite(result), "nonfinite JSON number")
        return result

    return json.loads(
        raw,
        object_pairs_hook=pairs,
        parse_float=floating,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
    )


def read_json(path):
    require(path.stat().st_size <= 64 * 1024**2, "JSON artifact exceeds bound")
    return strict_json(path.read_text())


def read_lines(path):
    require(path.stat().st_size <= 256 * 1024**2, "JSONL artifact exceeds bound")
    rows = []
    with path.open() as stream:
        for line in stream:
            require(
                len(rows) < 100000 and len(line) <= 8 * 1024**2,
                "capture exceeds declared bound",
            )
            rows.append(strict_json(line))
    require(rows, "empty capture")
    return rows


def validate_lifecycle(root, records, hardware_class):
    required = {"collector", "observer", "application"}
    if hardware_class == "apple-silicon":
        required.add("workload")
    require(
        isinstance(records, list) and required <= {r["role"] for r in records},
        "missing process lifecycle evidence",
    )
    require(
        len({r["pid"] for r in records}) == len(records),
        "ambiguous process attribution",
    )
    for r in records:
        require(
            type(r["pid"]) is int
            and r["pid"] > 0
            and r["exit_code"] == 0
            and r["reaped"] is True
            and r["proc_exists"] is False
            and r["started_ns"] < r["finished_ns"] <= r["deadline_ns"],
            "failed process cleanup/deadline",
        )
        if hardware_class == "apple-silicon":
            require(
                r["environment"].get("OBJC_DEBUG_MISSING_POOLS") == "YES",
                "missing pool diagnostic",
            )
        for name in ("stdout", "stderr"):
            path = safe_path(root, r[name])
            require(
                path.is_file() and path.stat().st_size <= 256 * 1024**2,
                "missing process original log",
            )
            text = path.read_text(errors="replace")
            require(
                not re.search(
                    r"autoreleased with no pool|MISSING_POOLS|no autorelease pool",
                    text,
                    re.I,
                ),
                f"missing-pool warning in {r['role']} PID {r['pid']} {name}",
            )


def visible(element):
    frame = element["frame"]
    clip = element["clip"]
    require(
        len(frame) == len(clip) == 4
        and all(type(v) in (int, float) and math.isfinite(v) for v in frame + clip),
        "invalid AX geometry",
    )
    x, y, w, h = frame
    a, b, c, d = clip
    return (
        w > 0
        and h > 0
        and c > 0
        and d > 0
        and x >= a
        and y >= b
        and x + w <= a + c
        and y + h <= b + d
    )


def validate_actions(actions, diagnostics, policy):
    require(
        isinstance(actions, list) and ACTIONS <= {a["name"] for a in actions},
        "missing actual native interactions",
    )
    seen = set()
    for action in actions:
        require(
            action["name"] in ACTIONS
            and action["method"]
            in (
                "AXPress",
                "AXSetValue",
                "CGEventScroll",
                "ATSPIAction",
                "XTestScroll",
                "restart",
            )
            and action["return_code"] == 0
            and 0
            <= action["finished_ns"] - action["started_ns"]
            <= policy["freshness_ns"],
            "failed/unbounded native action",
        )
        frames = []
        for side in ("before", "after"):
            observation = action[side]
            require(
                observation["complete"] is True and observation["elements"],
                "truncated/empty native census",
            )
            from gpu_desktop import anchored_time

            action_clock = action.get("clock_anchor", action["before"]["clock_anchor"])
            started = anchored_time(action["started_ns"], action_clock)
            observed = anchored_time(
                observation["observed_ns"], observation["clock_anchor"]
            )
            require(
                max(abs(observed[0] - started[1]), abs(observed[1] - started[0]))
                <= policy["freshness_ns"],
                "stale native observation",
            )
            frames.append(
                {e["identifier"]: e for e in observation["elements"] if visible(e)}
            )
        if action["name"] != "restore":
            require(
                frames[0] != frames[1],
                "native action has no observable before/after effect",
            )
        if action["name"] != "restore":
            from gpu_desktop import resolve_selector

            require(
                resolve_selector(action["before"]["elements"], action["selector"])
                == action["resolved_element"],
                "native action target was not resolved from the actual census",
            )
        seen.add(action["name"])
    require(seen >= ACTIONS, "native interaction coverage incomplete")
    from gpu_desktop import validate_display

    validate_display(actions, diagnostics, policy)


def validate_manifest(root, report, committed):
    require(
        report.get("schema") == 1 and report.get("mode") == "native",
        "not native acceptance evidence",
    )
    require(report["hardware_class"] in CLASSES, "unknown hardware class")
    require(
        report["inputs"] == committed and committed, "wrong committed source inputs"
    )
    records = report["artifacts"]
    require(
        isinstance(records, list) and len(records) <= 10000, "invalid artifact manifest"
    )
    names = [r["path"] for r in records]
    require(
        len(set(names)) == len(names) and ORIGINALS <= set(names),
        "missing/duplicate originals",
    )
    paths = {r["path"]: artifact(root, r) for r in records}
    for name, digest in committed.items():
        source = "source/" + name
        require(
            source in paths
            and next(r["sha256"] for r in records if r["path"] == source) == digest,
            "missing or changed committed source original",
        )
    policy = read_json(paths["policy.json"])
    inventory = read_json(paths["inventory.json"])
    build = read_json(paths["build.json"])
    require(
        build["inputs"] == committed and build["exit_code"] == 0,
        "wrong source/build identity",
    )
    require(
        re.fullmatch(r"[0-9a-f]{40}", build["source_commit"])
        and build["command"]
        == [
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
        and build["build_stdout"] in paths
        and build["build_stderr"] in paths,
        "missing original committed native build provenance",
    )
    executable_roles = {"collector", "application", "observer"}
    if report["hardware_class"] != "apple-silicon":
        executable_roles.add("workload")
    require(
        set(build["executables"]) == set(report["executables"]) == executable_roles,
        "missing/unexpected native executable artifact",
    )
    for role in executable_roles:
        name = build["executables"][role]
        require(
            name in paths
            and report["executables"][role]
            == next(r["sha256"] for r in records if r["path"] == name),
            "wrong executable identity",
        )
    require(
        policy["hardware_class"]
        == report["hardware_class"]
        == inventory["hardware_class"],
        "wrong physical device class",
    )
    require(
        policy["device"] == inventory["device"]
        and policy["fields"] == inventory["fields"]
        and inventory["device"]
        and inventory["fields"],
        "wrong identity or independent required field set",
    )
    require(
        policy["declared_unix_ns"] < report["capture_started_unix_ns"]
        and inventory["captured_unix_ns"] <= policy["declared_unix_ns"],
        "policy not declared before measurement",
    )
    require(
        policy["phases"] == ["idle", "load", "interval", "recovery"],
        "missing measurement phases",
    )
    for key in (
        "max_query_ns",
        "max_gap_ns",
        "freshness_ns",
        "deadline_ns",
        "poll_interval_ns",
    ):
        require(
            type(policy[key]) is int and 0 < policy[key] <= 3600 * 10**9,
            "invalid policy time bound",
        )
    require(
        type(policy["rounding_ulps"]) is int and 0 <= policy["rounding_ulps"] <= 4,
        "invalid declared rounding allowance",
    )
    require(
        0 <= policy["warmup_samples"] <= 10
        and 4 <= policy["sample_count"] <= 100000
        and 0 <= policy["retries"] <= 3,
        "invalid sample/retry bounds",
    )
    require(
        0
        < report["capture_finished_unix_ns"] - report["capture_started_unix_ns"]
        <= policy["deadline_ns"],
        "capture deadline exceeded",
    )
    return paths, policy, inventory


def replay_native(raw_inventory, raw_observer, inventory, observer):
    if inventory["hardware_class"] == "apple-silicon":
        from gpu_apple_capture import independent_inventory, normalize_observer

        expected = independent_inventory(raw_inventory)
    else:
        from gpu_intel_capture import independent_inventory, normalize_observer

        expected = independent_inventory(raw_inventory, inventory["device"]["pci"])
    require(expected == inventory, "required inventory differs from native originals")
    require(
        [normalize_observer(frame, expected) for frame in raw_observer] == observer,
        "observer operands differ from native originals",
    )


def verify_host(root, committed):
    report = read_json(root / "report.json")
    paths, policy, inventory = validate_manifest(root, report, committed)
    snapshots = read_lines(paths["snapshots.jsonl"])
    observer = read_lines(paths["observer.jsonl"])
    replay_native(
        read_json(paths["native-inventory.json"]),
        read_lines(paths["native-observer.jsonl"]),
        inventory,
        observer,
    )
    require(len(snapshots) == policy["sample_count"], "missing selected native samples")
    from gpu_samples import verify_series

    counts = verify_series(snapshots, inventory, observer, policy)
    diagnostics = read_lines(paths["diagnostics.jsonl"])
    actions = read_json(paths["actions.json"])
    from gpu_originals import validate_originals

    lifecycle = validate_originals(paths, report, policy, actions, diagnostics)
    from gpu_provenance import validate_provenance

    validate_provenance(paths, report, inventory, lifecycle)
    for pid in {d["application_pid"] for d in diagnostics}:
        unique = {
            d["snapshot"]["sequence"]: d["snapshot"]
            for d in diagnostics
            if d["application_pid"] == pid
        }
        verify_series([unique[k] for k in sorted(unique)], inventory, observer, policy)
    earned = {1, 4, 6}
    earned.add(3 if report["hardware_class"] == "apple-silicon" else 2)
    validate_lifecycle(root, lifecycle, report["hardware_class"])
    validate_actions(actions, diagnostics, policy)
    require(
        read_json(paths["workspace-after.json"])
        == read_json(paths["workspace-restored.json"]),
        "meter/interval preferences not restored",
    )
    earned.update((5, 7, 8))
    return report["hardware_class"], earned, counts


def requirement_results(hosts, preservation, automated):
    """Every native-dependent requirement keeps its complete hardware matrix."""
    result = {i: False for i in range(1, 10)}
    if not automated:
        return result
    result[9] = True
    dependencies = {
        1: CLASSES,
        2: {"intel-integrated", "intel-discrete"},
        3: {"apple-silicon"},
        4: CLASSES,
        5: CLASSES,
        6: CLASSES,
        7: CLASSES,
        8: CLASSES,
    }
    for number, classes in dependencies.items():
        result[number] = all(number in hosts.get(name, set()) for name in classes)
    result[7] &= preservation
    result[8] &= preservation
    return result
