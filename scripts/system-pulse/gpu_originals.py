"""Bind normalized GPU report entries to retained commands, binaries and originals."""

import plistlib
from gpu_capture import sha256

from gpu_evidence import read_json, read_lines, strict_json
from host_accuracy import require


def validate_originals(paths, report, policy, actions, diagnostics):
    from gpu_capture import validate_workload

    lifecycle = read_json(paths["lifecycle.json"])
    by_role = {r["role"]: r for r in lifecycle}
    require(len(by_role) == len(lifecycle), "duplicate native process role")
    build = read_json(paths["build.json"])
    require(
        read_lines(paths["collector.stdout"]) == read_lines(paths["snapshots.jsonl"])
        and read_lines(paths["observer.stdout"])
        == read_lines(paths["native-observer.jsonl"])
        and read_lines(paths["inventory.stdout"])
        == [read_json(paths["native-inventory.json"])],
        "normalized capture differs from retained native stdout",
    )
    required = {
        "collector",
        "observer",
        "application",
        "application-restored",
        "workload",
        "inventory",
        "build",
    }
    require(required <= set(by_role), "missing native process or restored application")
    for role, record in by_role.items():
        require(
            read_json(paths[role + "-finished.json"]) == record,
            "lifecycle differs from original completion record",
        )
        for name in ("stdout", "stderr"):
            require(
                record[name] in paths,
                "process original log is absent from artifact manifest",
            )
        executable = (
            "application"
            if role.startswith("application")
            else "collector"
            if role == "collector"
            else "observer"
        )
        runtime = role in (
            "collector",
            "observer",
            "inventory",
            "application",
            "application-restored",
        ) or role.startswith("ax")
        if report["hardware_class"] == "apple-silicon" and role == "workload":
            runtime = True
        if runtime:
            require(
                record["executable_sha256"] == report["executables"][executable]
                and record["command"][0]
                == report["capture_root"] + "/" + build["executables"][executable],
                "executed native binary differs from committed build artifact",
            )
    if report["hardware_class"] == "apple-silicon":
        from gpu_host_capture import console_session

        session = console_session(
            plistlib.loads(paths["console-session.stdout"].read_bytes())
        )
        require(
            session == read_json(paths["console-session.json"])
            and session["locked"] is False,
            "native visible capture used unavailable/locked desktop",
        )
        workload = read_lines(paths["workload.stdout"])
        require(
            len(workload) == 1 and workload[0]["pid"] == by_role["workload"]["pid"],
            "wrong workload PID/original",
        )
        validate_workload(
            workload[0], policy["device"]["registry_id"], policy["workload_seconds"]
        )
    application_pids = {
        by_role[r]["pid"] for r in ("application", "application-restored")
    }
    require(
        {d["application_pid"] for d in diagnostics} == application_pids,
        "missing/wrong application diagnostic PID",
    )
    for action in actions:
        if action["name"] == "restore":
            require(
                read_json(paths[action["before_path"]]) == action["before"]
                and read_json(paths[action["after_path"]]) == action["after"],
                "restore census differs from originals",
            )
        else:
            original = read_json(paths[action["native_path"]])
            require(
                all(action.get(k) == v for k, v in original.items())
                and {
                    "before",
                    "after",
                    "return_code",
                    "target",
                    "selector",
                    "resolved_element",
                    "started_ns",
                    "finished_ns",
                    "method",
                }
                <= set(original),
                "native action differs from actual helper stdout",
            )
        for side in ("before", "after"):
            require(
                action[side]["target_pid"] in application_pids,
                "native action targets another application",
            )
            require(
                read_json(paths[action["state_" + side + "_path"]])
                == action["state_" + side],
                "saved action state differs from retained original",
            )
    require(
        sha256(paths["action-plan.json"]) == policy["action_plan_sha256"],
        "predeclared action plan hash differs",
    )
    plan = read_json(paths["action-plan.json"])
    scheduled = [
        s for phase in policy["phases"] for s in plan if s.get("phase", "load") == phase
    ]
    performed = [a for a in actions if a["name"] != "restore"]
    require(
        len(scheduled) == len(performed)
        and all(
            a["name"] == s["name"]
            and a["target"] == s["target"]
            and a["selector"] == s["selector"]
            for a, s in zip(performed, scheduled)
        ),
        "native interactions differ from predeclared action plan",
    )
    for action, step in zip(performed, scheduled):
        owners = [r for r in lifecycle if r["stdout"] == action["native_path"]]
        require(len(owners) == 1, "native action stdout has no unique helper owner")
        owner = owners[0]
        command = owner["command"]
        suffix = [step["method"]] + ([str(step["value"])] if "value" in step else [])
        require(
            len(command) == 4 + len(suffix)
            and command[2] == str(action["before"]["target_pid"])
            and strict_json(command[3])
            == dict(control=step["target"], selector=step["selector"])
            and command[4:] == suffix
            and all(
                action[side]["observer_pid"] == owner["pid"]
                for side in ("before", "after")
            ),
            "native action differs from executed helper command or PID",
        )
    for action in actions:
        if action["name"] == "restore":
            for side in ("before", "after"):
                owners = [r for r in lifecycle if r["stdout"] == action[side + "_path"]]
                require(
                    len(owners) == 1
                    and owners[0]["pid"] == action[side]["observer_pid"],
                    "restore census has no unique native helper owner",
                )
    phases = read_json(paths["phases.json"])
    require(
        [p["name"] for p in phases] == policy["phases"],
        "missing original measurement phase",
    )
    previous = report["capture_started_unix_ns"]
    for phase in phases:
        require(
            previous
            <= phase["started_unix_ns"]
            < phase["finished_unix_ns"]
            <= report["capture_finished_unix_ns"],
            "overlapping, unbounded or missing measurement phase",
        )
        previous = phase["finished_unix_ns"]
        require(
            any(
                phase["started_unix_ns"]
                <= d["accepted_unix_ns"]
                <= phase["finished_unix_ns"]
                for d in diagnostics
            ),
            "measurement phase has no consumed native snapshot",
        )
    load = next(p for p in phases if p["name"] == "load")
    require(
        load["started_unix_ns"] <= by_role["workload"]["started_unix_ns"]
        and by_role["workload"]["finished_unix_ns"] <= load["finished_unix_ns"],
        "workload was outside declared load phase",
    )
    recovery = read_json(paths["recovery.json"])
    require(
        recovery["mode"] == "not-induced" and recovery["reason"],
        "missing explicit native failure-recovery limitation",
    )
    return lifecycle
