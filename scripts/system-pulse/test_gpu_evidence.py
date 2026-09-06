import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    from gpu_evidence import (
        artifact,
        validate_manifest,
        validate_lifecycle,
        validate_actions,
        requirement_results,
    )
except ImportError:
    artifact = validate_manifest = validate_lifecycle = validate_actions = (
        requirement_results
    ) = None


def originals_fixture(root):
    from gpu_capture import sha256

    paths = {}

    def put(name, value):
        p = root / name
        p.write_text(json.dumps(value))
        paths[name] = p
        return p

    def lines(name, value):
        p = root / name
        p.write_text(json.dumps(value) + "\n")
        paths[name] = p

    executables = {
        role: "bin/" + role
        for role in ("collector", "observer", "application", "workload")
    }
    report = dict(
        hardware_class="intel-discrete",
        capture_root=str(root),
        executables={r: r + "-digest" for r in executables},
        capture_started_unix_ns=0,
        capture_finished_unix_ns=100,
    )
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
    put("build.json", dict(executables=executables, command=build_command))
    lifecycle = []

    def role(name, pid, command, stdout=None):
        executable = (
            "application"
            if name.startswith("application")
            else "collector"
            if name == "collector"
            else "workload"
            if name == "workload"
            else "observer"
        )
        r = dict(
            role=name,
            pid=pid,
            command=command,
            stdout=stdout or name + ".stdout",
            stderr=name + ".stderr",
            exit_code=0,
            reaped=True,
            proc_exists=False,
            started_ns=1,
            finished_ns=9,
            deadline_ns=10,
            environment=dict(OBJC_DEBUG_MISSING_POOLS="YES"),
            executable_sha256=report["executables"][executable],
            started_unix_ns=31,
            finished_unix_ns=39,
        )
        for key in ("stdout", "stderr"):
            paths[r[key]] = root / r[key]
            paths[r[key]].write_text("")
        lifecycle.append(r)
        return r

    for name, pid in [
        ("collector", 11),
        ("observer", 12),
        ("application", 1),
        ("application-restored", 2),
        ("workload", 15),
        ("inventory", 16),
        ("build", 17),
    ]:
        exe = (
            "application"
            if name.startswith("application")
            else "collector"
            if name == "collector"
            else "observer"
        )
        command = [str(root / executables[exe])]
        if name == "collector":
            command += ["--count", "60", "--interval-ms", "1000"]
        elif name == "observer":
            command += [
                str(root / "source/scripts/system-pulse/gpu_intel_capture.py"),
                "--count",
                "600",
                "--interval-ms",
                "100",
            ]
        elif name == "inventory":
            command += [
                str(root / "source/scripts/system-pulse/gpu_intel_capture.py"),
                "--count",
                "1",
            ]
        elif name == "build":
            command = build_command
        elif name == "workload":
            command = [str(root / "bin/workload"), "0000:01:00.0", "12"]
        role(name, pid, command)
    role(
        "workload-build",
        18,
        [
            "/usr/bin/cc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            str(root / "source/scripts/system-pulse/gpu_intel_workload.c"),
            "-lvulkan",
            "-o",
            str(root / "bin/workload"),
        ],
    )
    for name in ("collector.stdout", "snapshots.jsonl"):
        lines(name, dict(retained="collector"))
    for name in ("observer.stdout", "native-observer.jsonl"):
        lines(name, dict(pid=12, retained="observer process"))
    put("native-inventory.json", dict(pid=16))
    lines("inventory.stdout", dict(pid=16))
    from test_gpu_desktop import action_fixture

    actions, _, _ = action_fixture()
    plan = []
    for index, action in enumerate(actions):
        for side in ("before", "after"):
            name = "state-" + str(index) + "-" + side + ".json"
            put(name, action["state_" + side])
            action["state_" + side + "_path"] = name
        if action["name"] == "restore":
            for side, owner in [("before", 31), ("after", 32)]:
                name = "axrestore" + side + ".stdout"
                action[side]["observer_pid"] = owner
                action[side + "_path"] = name
                role(
                    "axrestore" + side,
                    owner,
                    [
                        str(root / "bin/observer"),
                        str(root / "source/scripts/system-pulse/gpu_linux_ax.py"),
                        str(action[side]["target_pid"]),
                    ],
                    name,
                )
                put(name, action[side])
        else:
            name = "ax" + str(index) + ".stdout"
            owner = 20 + index
            for side in ("before", "after"):
                action[side]["observer_pid"] = owner
            method = "scroll" if action["method"] == "CGEventScroll" else "press"
            step = dict(
                name=action["name"],
                target=action["target"],
                selector=action["selector"],
                method=method,
                phase="load",
            )
            if method == "scroll":
                step["value"] = 1
            plan.append(step)
            command = [
                str(root / "bin/observer"),
                str(root / "source/scripts/system-pulse/gpu_linux_ax.py"),
                str(action["before"]["target_pid"]),
                json.dumps(dict(control=step["target"], selector=step["selector"])),
                method,
            ] + ([str(step["value"])] if method == "scroll" else [])
            role("ax" + str(index), owner, command, name)
            action["native_path"] = name
            put(name, action)
    # Real capture also launches readiness and close helpers. This extra close role
    # has a retained runtime warning, but no action directly names its census.
    r = role(
        "axclose",
        40,
        [
            str(root / "bin/observer"),
            str(root / "source/scripts/system-pulse/gpu_linux_ax.py"),
            "1",
            "close",
        ],
    )
    paths[r["stderr"]].write_text("")
    put(
        "axclose.stdout",
        dict(
            target_pid=1,
            method="WM_DELETE_WINDOW",
            return_code=0,
            before=dict(observer_pid=40, target_pid=1),
        ),
    )
    put("action-plan.json", plan)
    clock = dict(monotonic_before_ns=0, monotonic_after_ns=0, unix_ns=0)
    device = dict(
        monitor_id="gpu", pci="0000:01:00.0", vendor="0x8086", device_id="0x1234"
    )
    field = dict(sensor_id="gpu/usage", source="native-source")
    policy = dict(
        device=device,
        fields=[field],
        workload_seconds=12,
        phases=["idle", "load", "interval", "recovery"],
        action_plan_sha256=sha256(paths["action-plan.json"]),
    )
    put("policy.json", policy)
    work = dict(
        schema=1,
        api="Vulkan",
        pid=15,
        pci=device["pci"],
        vendor_id=0x8086,
        device_id=0x1234,
        identity_extension=True,
        matching_devices=1,
        clock_anchor=clock,
        query_started_ns=31,
        query_finished_ns=32,
        work_started_ns=32,
        work_finished_ns=38,
        duration_ns=6,
        bytes=4 * 1024**2,
        allocation_bytes=4 * 1024**2,
        commands_submitted=5,
        commands_completed=5,
        max_in_flight=1,
        queue_family=0,
        queue_flags=4,
        fence_timeout_ns=500000000,
        devices=[
            dict(
                pci=device["pci"],
                vendor_id=0x8086,
                device_id=0x1234,
                identity_extension=True,
            )
        ],
    )
    put("workload.stdout", work)
    put(
        "observer.jsonl",
        dict(
            clock_anchor=clock,
            samples=[
                dict(
                    sensor_id=field["sensor_id"],
                    source=field["source"],
                    start=34,
                    end=35,
                )
            ],
        ),
    )
    phases = [
        dict(name=name, started_unix_ns=t, finished_unix_ns=t + 10)
        for name, t in zip(policy["phases"], (10, 30, 50, 70))
    ]
    put("phases.json", phases)
    put(
        "recovery.json",
        dict(mode="not-induced", reason="No machine-wide recovery was induced"),
    )
    snapshot = dict(
        clock_anchor=clock,
        readings=[
            dict(
                sensor_id=field["sensor_id"],
                availability="Available",
                observations=[dict(read_started_ns=33, captured_ns=34)],
            )
        ],
    )
    diagnostics = [
        dict(application_pid=pid, accepted_unix_ns=t, snapshot=snapshot)
        for pid, t in [(1, 11), (1, 35), (1, 51), (2, 71)]
    ]
    for r in lifecycle:
        r["stdout_sha256"] = sha256(paths[r["stdout"]])
        r["stderr_sha256"] = sha256(paths[r["stderr"]])
        put(r["role"] + "-finished.json", r)
        put(
            r["role"] + "-started.json",
            {
                k: r[k]
                for k in (
                    "pid",
                    "command",
                    "started_ns",
                    "started_unix_ns",
                    "deadline_ns",
                )
            },
        )
    put("lifecycle.json", lifecycle)
    return paths, report, policy, actions, diagnostics, lifecycle, put


class EvidenceTests(unittest.TestCase):
    def test_apple_commands_bind_observe_workload_and_ax_modes(self):
        from gpu_originals import validate_commands

        with tempfile.TemporaryDirectory() as directory:
            paths, report, policy, actions, diagnostics, records, put = (
                originals_fixture(Path(directory))
            )
            report["hardware_class"] = "apple-silicon"
            root = report["capture_root"]
            build = json.loads(paths["build.json"].read_text())
            del build["executables"]["workload"]
            policy["device"]["registry_id"] = 123
            put("policy.json", policy)
            by_role = {r["role"]: r for r in records if r["role"] != "workload-build"}
            by_role["inventory"]["command"] = [
                root + "/bin/observer",
                "observe",
                "1",
                "100",
            ]
            by_role["observer"]["command"] = [
                root + "/bin/observer",
                "observe",
                "600",
                "100",
            ]
            by_role["workload"]["command"] = [
                root + "/bin/observer",
                "workload",
                "123",
                "12",
            ]
            source = root + "/source/scripts/system-pulse/"
            by_role["helper-build"] = dict(
                command=[
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
                    root + "/bin/observer",
                ]
            )
            by_role["console-session"] = dict(
                command=[
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
            )
            for name, record in by_role.items():
                if name.startswith("ax"):
                    record["command"][1] = "ax"
            close = json.loads(paths["axclose.stdout"].read_text())
            close["method"] = "AXPressCloseButton"
            put("axclose.stdout", close)
            validate_commands(paths, report, build, by_role, actions)
            for role, index, value in (
                ("inventory", 1, "inventory"),
                ("observer", 1, "workload"),
                ("workload", 2, "999"),
                ("helper-build", 14, source + "unrelated.m"),
                ("ax0", 1, "observe"),
                ("axclose", 1, "observe"),
            ):
                record = by_role[role]
                original = record["command"][:]
                record["command"][index] = value
                with self.subTest(role=role), self.assertRaises(AssertionError):
                    validate_commands(paths, report, build, by_role, actions)
                record["command"] = original

    def test_work_receipt_and_consumed_query_must_overlap_actual_completed_work(self):
        from gpu_originals import validate_originals
        from gpu_capture import sha256

        with tempfile.TemporaryDirectory() as directory:
            paths, report, policy, actions, diagnostics, records, put = (
                originals_fixture(Path(directory))
            )
            record = next(r for r in records if r["role"] == "workload")
            original = json.loads(paths["workload.stdout"].read_text())

            def set_work(work):
                put("workload.stdout", work)
                record["stdout_sha256"] = sha256(paths["workload.stdout"])
                put("workload-finished.json", record)
                put("lifecycle.json", records)

            validate_originals(paths, report, policy, actions, diagnostics)
            for change in (
                dict(commands_completed=0),
                dict(commands_submitted=6),
                dict(pci="0000:02:00.0"),
                dict(device_id=0xFFFF),
                dict(identity_extension=False),
                dict(max_in_flight=2),
                dict(allocation_bytes=128 * 1024**2),
                dict(work_started_ns=36, duration_ns=2),
            ):
                set_work(dict(original, **change))
                with self.subTest(change=change), self.assertRaises(AssertionError):
                    validate_originals(paths, report, policy, actions, diagnostics)
            set_work(original)
            for side in ("collector", "observer"):
                changed = copy.deepcopy(diagnostics)
                if side == "collector":
                    changed[1]["snapshot"]["readings"][0]["observations"][0].update(
                        read_started_ns=30, captured_ns=31
                    )
                else:
                    put(
                        "observer.jsonl",
                        dict(
                            clock_anchor=original["clock_anchor"],
                            samples=[
                                dict(
                                    source="native-source",
                                    sensor_id="gpu/usage",
                                    start=30,
                                    end=31,
                                )
                            ],
                        ),
                    )
                with self.subTest(source=side), self.assertRaises(AssertionError):
                    validate_originals(paths, report, policy, actions, changed)

    def test_zero_work_process_fails_original_report_boundary(self):
        from gpu_originals import validate_originals
        from gpu_capture import sha256

        with tempfile.TemporaryDirectory() as directory:
            paths, report, policy, actions, diagnostics, records, put = (
                originals_fixture(Path(directory))
            )
            record = next(r for r in records if r["role"] == "workload")
            record.update(
                command=["/usr/bin/true"], executable_sha256=sha256("/usr/bin/true")
            )
            paths["workload.stdout"].write_text("")
            record["stdout_sha256"] = sha256(paths["workload.stdout"])
            put("workload-finished.json", record)
            put(
                "workload-started.json",
                {
                    k: record[k]
                    for k in (
                        "pid",
                        "command",
                        "started_ns",
                        "started_unix_ns",
                        "deadline_ns",
                    )
                },
            )
            put("lifecycle.json", records)
            validate_lifecycle(Path(directory), records, "intel-discrete")
            with self.assertRaises(AssertionError):
                validate_originals(paths, report, policy, actions, diagnostics)

    def test_originals_bind_raw_process_pids_and_complete_commands(self):
        from gpu_originals import validate_originals
        from gpu_capture import sha256

        with tempfile.TemporaryDirectory() as directory:
            paths, report, policy, actions, diagnostics, records, put = (
                originals_fixture(Path(directory))
            )

            def sync():
                for record in records:
                    for stream in ("stdout", "stderr"):
                        record[stream + "_sha256"] = sha256(paths[record[stream]])
                    put(record["role"] + "-finished.json", record)
                    put(
                        record["role"] + "-started.json",
                        {
                            k: record[k]
                            for k in (
                                "pid",
                                "command",
                                "started_ns",
                                "started_unix_ns",
                                "deadline_ns",
                            )
                        },
                    )
                put("lifecycle.json", records)

            validate_originals(paths, report, policy, actions, diagnostics)
            for name, aliases in (
                ("inventory.stdout", ["native-inventory.json"]),
                ("observer.stdout", ["native-observer.jsonl"]),
            ):
                original = json.loads(paths[name].read_text())
                for key in [name] + aliases:
                    put(key, dict(original, pid=999))
                sync()
                with self.subTest(raw=name), self.assertRaises(AssertionError):
                    validate_originals(paths, report, policy, actions, diagnostics)
                for key in [name] + aliases:
                    put(key, original)
            for role, index, value in (
                ("observer", 1, "/unrelated.py"),
                ("observer", 3, "1"),
                ("inventory", 1, "/unrelated.py"),
                ("inventory", 2, "--other-mode"),
                ("collector", 2, "0"),
                ("application", 0, str(Path(directory) / "bin/collector")),
                ("application-restored", 0, str(Path(directory) / "bin/collector")),
                ("ax0", 1, "/unrelated.py"),
                ("axclose", 1, "/unrelated.py"),
                ("axrestorebefore", 1, "/unrelated.py"),
                ("build", 2, "--offline"),
            ):
                record = next(r for r in records if r["role"] == role)
                original = record["command"][:]
                record["command"][index] = value
                sync()
                with (
                    self.subTest(role=role, index=index),
                    self.assertRaises(AssertionError),
                ):
                    validate_originals(paths, report, policy, actions, diagnostics)
                record["command"] = original
            sync()
            validate_originals(paths, report, policy, actions, diagnostics)

    def test_originals_reconcile_every_started_finished_process_and_log(self):
        from gpu_originals import validate_originals
        from gpu_capture import sha256

        with tempfile.TemporaryDirectory() as directory:
            paths, report, policy, actions, diagnostics, records, put = (
                originals_fixture(Path(directory))
            )
            validate_originals(paths, report, policy, actions, diagnostics)
            omitted = [r for r in records if r["role"] != "axclose"]
            put("lifecycle.json", omitted)
            with self.assertRaises(AssertionError):
                validate_originals(paths, report, policy, actions, diagnostics)
            hidden = {
                name: paths.pop(name)
                for name in list(paths)
                if name.startswith("axclose")
            }
            with self.assertRaises(AssertionError):
                validate_originals(paths, report, policy, actions, diagnostics)
            paths.update(hidden)
            put("lifecycle.json", records)
            for name in (
                "axclose-started.json",
                "axclose-finished.json",
                "axclose.stderr",
            ):
                removed = paths.pop(name)
                with self.subTest(missing=name), self.assertRaises(AssertionError):
                    validate_originals(paths, report, policy, actions, diagnostics)
                paths[name] = removed
            start = json.loads(paths["axclose-started.json"].read_text())
            put("axclose-started.json", dict(start, pid=999))
            with self.assertRaises(AssertionError):
                validate_originals(paths, report, policy, actions, diagnostics)
            put("axclose-started.json", start)
            paths["axclose.stderr"].write_text(
                "objc[40]: Object autoreleased with no pool in place - just leaking\n"
            )
            close = records[-1]
            close["stderr_sha256"] = sha256(paths["axclose.stderr"])
            put("axclose-finished.json", close)
            put("lifecycle.json", records)
            validated = validate_originals(paths, report, policy, actions, diagnostics)
            with self.assertRaises(AssertionError):
                validate_lifecycle(Path(directory), validated, "intel-discrete")

    def test_json_lines_reject_duplicate_keys_and_nonfinite_numbers(self):
        from gpu_evidence import read_lines
        import tempfile
        from pathlib import Path

        for raw in ('{"a":1,"a":2}\n', '{"a":NaN}\n', '{"a":1e999}\n'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "raw.jsonl"
                path.write_text(raw)
                with self.assertRaises((AssertionError, ValueError)):
                    read_lines(path)

    def test_original_hash_size_and_paths(self):
        self.assertIsNotNone(artifact, "GPU artifact verifier is not implemented")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "original").write_bytes(b"original operands\n")
            record = dict(
                path="original",
                bytes=18,
                sha256=hashlib.sha256(b"original operands\n").hexdigest(),
            )
            self.assertEqual(
                artifact(root, record).read_bytes(), b"original operands\n"
            )
            for change in (
                dict(bytes=1),
                dict(sha256="0" * 64),
                dict(path="missing"),
                dict(path="../original"),
            ):
                with (
                    self.subTest(change=change),
                    self.assertRaises((AssertionError, OSError)),
                ):
                    artifact(root, {**record, **change})

    def test_missing_hosts_and_empty_selected_suite_never_pass(self):
        self.assertIsNotNone(requirement_results, "GPU aggregate is not implemented")
        self.assertFalse(any(requirement_results({}, False, False).values()))
        for class_name in ("intel-integrated", "intel-discrete", "apple-silicon"):
            result = requirement_results({class_name: set(range(1, 9))}, True, True)
            self.assertFalse(result[8])
        result = requirement_results(
            {
                n: set(range(1, 9))
                for n in ("intel-integrated", "intel-discrete", "apple-silicon")
            },
            True,
            False,
        )
        self.assertFalse(any(result.values()))

    def test_lifecycle_requires_each_pid_diagnostics_and_reaping(self):
        self.assertIsNotNone(
            validate_lifecycle, "GPU lifecycle verifier is not implemented"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            processes = []
            for n, role in enumerate(
                ("collector", "observer", "workload", "application"), 10
            ):
                (root / (role + ".stdout")).write_text("")
                (root / (role + ".stderr")).write_text("")
                processes.append(
                    dict(
                        role=role,
                        pid=n,
                        exit_code=0,
                        reaped=True,
                        proc_exists=False,
                        started_ns=1,
                        finished_ns=9,
                        deadline_ns=10,
                        environment={"OBJC_DEBUG_MISSING_POOLS": "YES"},
                        stdout=role + ".stdout",
                        stderr=role + ".stderr",
                    )
                )
            validate_lifecycle(root, processes, "apple-silicon")
            for change in (
                dict(reaped=False),
                dict(exit_code=1),
                dict(proc_exists=True),
                dict(finished_ns=11),
                dict(environment={}),
            ):
                altered = copy.deepcopy(processes)
                altered[2].update(change)
                with self.subTest(change=change), self.assertRaises(AssertionError):
                    validate_lifecycle(root, altered, "apple-silicon")
            (root / "workload.stderr").write_text(
                "objc[12]: Object autoreleased with no pool in place - just leaking\n"
            )
            with self.assertRaises(AssertionError):
                validate_lifecycle(root, processes, "apple-silicon")

    def test_no_actual_native_action_and_stale_geometry_fail(self):
        self.assertIsNotNone(validate_actions, "GPU action verifier is not implemented")
        with self.assertRaises(AssertionError):
            validate_actions([], {}, dict(freshness_ns=100))
        action = dict(
            name="panel-collapse",
            method="AXPress",
            return_code=0,
            started_ns=100,
            finished_ns=101,
            before=dict(observed_ns=90, elements=[]),
            after=dict(observed_ns=102, elements=[]),
        )
        with self.assertRaises(AssertionError):
            validate_actions([action], {}, dict(freshness_ns=100))

    def test_complete_manifest_rejects_wrong_source_binary_and_device(self):
        import gpu_evidence
        from gpu_capture import sha256

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in gpu_evidence.ORIGINALS:
                (root / name).write_text("{}")
            (root / "source").mkdir()
            (root / "source/one.py").write_text("print(1)")
            inputs = {"one.py": sha256(root / "source/one.py")}
            executables = {
                role: role + ".binary"
                for role in ("application", "collector", "observer")
            }
            for role, path in executables.items():
                (root / path).write_text(role + " executable")
            (root / "build.stdout").write_text("finished")
            (root / "build.stderr").write_text("")
            field = dict(sensor_id="gpu/usage")
            inventory = dict(
                hardware_class="apple-silicon",
                device=dict(monitor_id="gpu"),
                fields=[field],
                captured_unix_ns=1,
            )
            policy = dict(
                **inventory,
                declared_unix_ns=2,
                phases=["idle", "load", "interval", "recovery"],
                sample_count=4,
                warmup_samples=1,
                retries=0,
                rounding_ulps=4,
                max_query_ns=10,
                max_gap_ns=10,
                freshness_ns=10,
                deadline_ns=100,
                poll_interval_ns=10,
            )
            build = dict(
                inputs=inputs,
                executables=executables,
                exit_code=0,
                source_commit="a" * 40,
                command=[
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
                ],
                build_stdout="build.stdout",
                build_stderr="build.stderr",
            )
            for name, data in [
                ("policy.json", policy),
                ("inventory.json", inventory),
                ("build.json", build),
            ]:
                (root / name).write_text(json.dumps(data))
            report = dict(
                schema=1,
                mode="native",
                hardware_class="apple-silicon",
                inputs=inputs,
                capture_started_unix_ns=3,
                capture_finished_unix_ns=20,
                executables={r: sha256(root / p) for r, p in executables.items()},
            )

            def manifest():
                return [
                    dict(
                        path=str(p.relative_to(root)),
                        bytes=p.stat().st_size,
                        sha256=sha256(p),
                    )
                    for p in root.rglob("*")
                    if p.is_file()
                ]

            report["artifacts"] = manifest()
            validate_manifest(root, report, inputs)
            changes = [
                lambda r: r["executables"].update(application="0" * 64),
                lambda r: r.update(inputs={"one.py": "0" * 64}),
                lambda r: r.update(hardware_class="intel-discrete"),
                lambda r: r["artifacts"].__setitem__(
                    slice(None),
                    [a for a in r["artifacts"] if a["path"] != "source/one.py"],
                ),
            ]
            for change in changes:
                altered = copy.deepcopy(report)
                change(altered)
                with self.assertRaises(AssertionError):
                    validate_manifest(root, altered, inputs)
            (root / "source/one.py").write_text("print(2)")
            report["artifacts"] = manifest()
            with self.assertRaises(AssertionError):
                validate_manifest(root, report, inputs)

    def test_wrong_source_binary_device_and_omitted_originals(self):
        self.assertIsNotNone(
            validate_manifest, "GPU manifest verifier is not implemented"
        )
        with tempfile.TemporaryDirectory() as tmp:
            for record in (
                {},
                dict(status="PASS", hardware_class="apple-silicon"),
                dict(status="PASS", source_commit="wrong", device="invented"),
            ):
                with (
                    self.subTest(record=record),
                    self.assertRaises((AssertionError, KeyError)),
                ):
                    validate_manifest(Path(tmp), record, {})


if __name__ == "__main__":
    unittest.main()
