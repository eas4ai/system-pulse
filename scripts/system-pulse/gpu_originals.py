"""Bind normalized GPU report entries to retained commands, binaries and originals."""

import plistlib
from gpu_capture import sha256

from gpu_evidence import read_json, read_lines, strict_json
from host_accuracy import require


def validate_commands(paths, report, build, by_role, actions):
    apple = report["hardware_class"] == "apple-silicon"
    root = report["capture_root"]
    binaries = {role: root + "/" + name for role, name in build["executables"].items()}
    source = root + "/source/scripts/system-pulse/"
    build_command = [
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
    expected = {
        "build": build_command,
        "application": [binaries["application"]],
        "application-restored": [binaries["application"]],
        "collector": [binaries["collector"], "--count", "60", "--interval-ms", "1000"],
        "inventory": [binaries["observer"]]
        + (
            ["observe", "1", "100"]
            if apple
            else [source + "gpu_intel_capture.py", "--count", "1"]
        ),
        "observer": [binaries["observer"]]
        + (
            ["observe", "600", "100"]
            if apple
            else [
                source + "gpu_intel_capture.py",
                "--count",
                "600",
                "--interval-ms",
                "100",
            ]
        ),
    }
    require(
        build["command"] == build_command,
        "retained build command differs from required build",
    )
    if apple:
        expected["helper-build"] = [
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
            source + "gpu_apple_native.m",
            source + "gpu_apple_ax.m",
            "-o",
            binaries["observer"],
        ]
        expected["console-session"] = [
            "/usr/sbin/ioreg",
            "-a",
            "-l",
            "-w",
            "0",
            "-d",
            "1",
            "-k",
            "IOConsoleUsers",
        ]
        policy = read_json(paths["policy.json"])
        expected["workload"] = [
            binaries["observer"],
            "workload",
            str(policy["device"]["registry_id"]),
            str(policy["workload_seconds"]),
        ]
    else:
        policy = read_json(paths["policy.json"])
        expected["workload-build"] = [
            "/usr/bin/cc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            source + "gpu_intel_workload.c",
            "-lvulkan",
            "-o",
            binaries["workload"],
        ]
        expected["workload"] = [
            binaries["workload"],
            policy["device"]["pci"],
            str(policy["workload_seconds"]),
        ]
    require(set(expected) <= set(by_role), "missing executed native command role")
    for role, command in expected.items():
        require(
            by_role[role]["command"] == command, "wrong complete command for " + role
        )
    for role, name in [
        ("inventory", "native-inventory.json"),
        ("observer", "native-observer.jsonl"),
    ]:
        frames = (
            [read_json(paths[name])] if role == "inventory" else read_lines(paths[name])
        )
        require(
            all(
                type(f["pid"]) is int and f["pid"] == by_role[role]["pid"]
                for f in frames
            ),
            "raw native stream PID differs from owned " + role,
        )
    pids = {by_role[r]["pid"] for r in ("application", "application-restored")}
    action_paths = {a["native_path"] for a in actions if a["name"] != "restore"}
    for role, record in by_role.items():
        if role in expected or role == "workload":
            continue
        require(role.startswith("ax"), "unknown retained native process role")
        command = record["command"]
        require(
            len(command) >= 3
            and command[:2]
            == [binaries["observer"], "ax" if apple else source + "gpu_linux_ax.py"]
            and command[2] in {str(pid) for pid in pids},
            "wrong native accessibility implementation or target",
        )
        original = read_json(paths[record["stdout"]])
        if record["stdout"] in action_paths:
            continue  # Exact plan/action suffix and before/after PIDs are checked below.
        if len(command) == 3:
            frames = [original]
        else:
            require(
                command[3:] == ["close"]
                and original["return_code"] == 0
                and original["target_pid"] == int(command[2])
                and original["method"]
                == ("AXPressCloseButton" if apple else "WM_DELETE_WINDOW"),
                "unbound native census/close command or result",
            )
            frames = [original["before"]]
        require(
            all(
                f["observer_pid"] == record["pid"]
                and f["target_pid"] == int(command[2])
                for f in frames
            ),
            "native readiness/close/restore census PID differs from executed helper",
        )


def validate_originals(paths, report, policy, actions, diagnostics):
    from gpu_capture import validate_workload

    lifecycle = read_json(paths["lifecycle.json"])
    by_role = {r["role"]: r for r in lifecycle}
    require(len(by_role) == len(lifecycle), "duplicate native process role")
    roles = set(by_role)
    root = paths["lifecycle.json"].parent
    actual = list(root.iterdir())
    require(len(actual) <= 10000, "native artifact directory exceeds bound")
    for suffix in ("-started.json", "-finished.json", ".stdout", ".stderr"):
        manifested = {
            name for name in paths if "/" not in name and name.endswith(suffix)
        }
        retained = {path.name for path in actual if path.name.endswith(suffix)}
        require(
            manifested == retained
            and {name[: -len(suffix)] for name in manifested} == roles,
            "retained process census differs from manifest/lifecycle: " + suffix,
        )
    for role, record in by_role.items():
        start = read_json(paths[role + "-started.json"])
        require(
            start
            == {
                k: record[k]
                for k in (
                    "pid",
                    "command",
                    "started_ns",
                    "started_unix_ns",
                    "deadline_ns",
                )
            },
            "process start differs from completion/lifecycle",
        )
        for stream in ("stdout", "stderr"):
            name = role + "." + stream
            require(
                record[stream] == name
                and sha256(paths[name]) == record[stream + "_sha256"],
                "process log identity or original digest differs",
            )
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
            else "workload"
            if role == "workload" and report["hardware_class"] != "apple-silicon"
            else "observer"
        )
        runtime = role in (
            "collector",
            "observer",
            "inventory",
            "application",
            "application-restored",
        ) or role.startswith("ax")
        if role == "workload":
            runtime = True
        if runtime:
            require(
                record["executable_sha256"] == report["executables"][executable]
                and record["command"][0]
                == report["capture_root"] + "/" + build["executables"][executable],
                "executed native binary differs from committed build artifact",
            )
    validate_commands(paths, report, build, by_role, actions)
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
    if report["hardware_class"] == "apple-silicon":
        validate_workload(
            workload[0], policy["device"]["registry_id"], policy["workload_seconds"]
        )
    else:
        from gpu_workload import validate_intel_work

        validate_intel_work(workload[0], policy["device"], policy["workload_seconds"])
    from gpu_workload import validate_overlap

    validate_overlap(
        workload[0],
        by_role["workload"],
        diagnostics,
        read_lines(paths["observer.jsonl"]),
        policy,
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
