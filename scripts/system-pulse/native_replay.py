"""Executable private-session native acceptance; every declared case is mandatory."""

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from host_accuracy import require
from host_capture import start_child, stop_child, process

REQUIRED = (
    "launch",
    "metrics",
    "collapse",
    "charts",
    "split",
    "outer-scroll",
    "inner-scroll",
    "held-input",
    "process",
    "preset",
    "restart",
    "recovery-schema",
    "recovery-json",
    "missing-device",
)


def result_status(cases, focus, completed, errors):
    required_satisfied = (
        focus in cases if focus is not None else set(cases) == set(REQUIRED)
    )
    return "PASS" if completed and not errors and required_satisfied else "FAIL"


class ProcessInspection:
    """Caller-owned ACK and last successful metric for one controlled child."""

    def __init__(self, app, target):
        self.app = app
        self.target = target
        self.acknowledgement = None
        self.reference = None

    def acknowledge(self, evidence):
        require(evidence["target"] == self.target, "wrong inspection acknowledgement")
        require(self.acknowledgement is None, "inspection already acknowledged")
        self.acknowledgement = copy.deepcopy(evidence)
        self.reference = dict(copy.deepcopy(evidence), source="navigation")

    def preparation(self, *, missing_row=False):
        require(self.acknowledgement is not None, "missing inspection acknowledgement")
        # One frozen observation serves the entire metric or horizontal gesture.
        evidence = copy.deepcopy(
            {
                "acknowledgement": self.acknowledgement,
                "reference": self.reference,
            }
        )

        def prepare(deadline):
            self.app.navigation_selection(
                self.target,
                self.target,
                deadline,
                fresh_panel=True,
                inspection=evidence,
                **({"inspection_missing_row": True} if missing_row else {}),
            )

        return prepare

    def metric(self, aid, name, visible=True):
        require(
            aid.rsplit(":cell:", 1)[0] == self.target, "wrong inspection metric target"
        )
        artifact = self.app.metric(
            aid,
            name,
            visible=visible,
            prepare_missing=self.preparation(missing_row=True),
        )
        frame = artifact["frame"]
        ids = [
            f"process:{row['identity']['pid']}:{row['identity']['start_time_ticks']}"
            for row in frame["snapshot"]["processes"]
        ]
        require(
            artifact["entry"]["element_id"] == aid and ids.count(self.target) == 1,
            "inspection metric does not prove exact target",
        )
        self.reference = {
            "target": self.target,
            "index": ids.index(self.target),
            "source": name + ".json",
            "publication": {
                "sequence": frame["snapshot"]["sequence"],
                **{
                    key: frame[key]
                    for key in (
                        "application_pid",
                        "render_revision",
                        "accepted_unix_ns",
                    )
                },
            },
        }
        return artifact


def reveal_process_cell(app, aid, key, deadline, *, prepare_missing=None):
    cell = None

    def observe(read):
        nonlocal cell
        current, cell = cell, None
        # Keep this gesture's node only after a complete, live, exact-ID read.
        # An interrupted read leaves it unset so the next poll reacquires it.
        if not app.alive(current) or current.get_accessible_id() != aid:
            current = app.process_cell(
                aid,
                deadline,
                **(
                    {"prepare_missing": prepare_missing}
                    if prepare_missing is not None
                    else {}
                ),
            )
        value = read(current)
        if not app.alive(current) or current.get_accessible_id() != aid:
            return None
        cell = current
        return current, value

    def poll():
        observation = observe(lambda node: (app.visible(node), app.bounds(node)))
        if observation is None:
            return None
        current, (visible, old) = observation
        if visible:
            return current
        require(time.monotonic() < deadline, "child cell movement deadline exceeded")
        app.key(key)

        def moved():
            observation = observe(app.bounds)
            return observation is not None and observation[1] != old

        app.wait(moved, message="child horizontal cell movement", deadline=deadline)
        return None

    return app.wait(poll, message="child cell visibility", deadline=deadline)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--inside", action="store_true")
    parser.add_argument(
        "--trace-publication",
        action="store_true",
        help="retain diagnostic publication timings; ineligible for final acceptance",
    )
    parser.add_argument(
        "--focus",
        choices=(
            "launch",
            "metrics",
            "collapse",
            "process",
            "split",
            "restart",
            "recovery",
            "missing-device",
        ),
    )
    args = parser.parse_args()
    args.trace_publication = (
        args.trace_publication
        or os.environ.get("SYSTEM_PULSE_DIAGNOSTICS_TRACE") == "1"
    )
    if args.trace_publication:
        os.environ["SYSTEM_PULSE_DIAGNOSTICS_TRACE"] = "1"
    if not args.inside:
        require(not args.output.exists(), "native output directory must be fresh")
        args.output.mkdir(parents=True)
        if args.trace_publication:
            (args.output / "publication-timing-metadata.json").write_text(
                json.dumps(
                    {
                        "publication_timing_instrumented": True,
                        "purpose": "supporting diagnostic only; final acceptance requires an untraced run",
                    },
                    indent=2,
                )
            )
        for command in ("xvfb-run", "Xvfb", "dbus-run-session", "xset"):
            require(shutil.which(command), f"missing native prerequisite {command}")
        icd = Path("/usr/share/vulkan/icd.d/lvp_icd.json")
        require(icd.is_file(), "missing lavapipe ICD")
        harness = args.output / "harness"
        harness.mkdir()
        harness_manifest = {}
        import hashlib

        for source in sorted(Path(__file__).parent.glob("*.py")):
            target = harness / source.name
            shutil.copy2(source, target)
            harness_manifest[source.name] = hashlib.sha256(
                target.read_bytes()
            ).hexdigest()
        (args.output / "harness-manifest.json").write_text(
            json.dumps(harness_manifest, indent=2)
        )
        command = [
            "xvfb-run",
            "-a",
            "-s",
            "-screen 0 1440x1000x24 -nolisten tcp",
            "dbus-run-session",
            "--",
            "env",
            "WAYLAND_DISPLAY=",
            "VK_DRIVER_FILES=" + str(icd),
            "PYTHONDONTWRITEBYTECODE=1",
            "/usr/bin/python3",
            "-B",
            str((harness / "native_replay.py").resolve()),
            "--inside",
            "--output",
            str(args.output.resolve()),
            "--binary",
            str(args.binary.resolve()),
        ]
        if args.trace_publication:
            command += ["--trace-publication"]
        if args.focus:
            command += ["--focus", args.focus]
        with (args.output / "private-session.log").open("w") as log:
            run = subprocess.Popen(
                command, stdout=log, stderr=log, start_new_session=True
            )
            (args.output / "private-session.json").write_text(
                json.dumps({"pid": run.pid, "pgid": run.pid, "command": command})
            )
            try:
                deadline = time.monotonic() + 1200
                cursor = 0
                while run.poll() is None:
                    progress_path = args.output / "progress.jsonl"
                    if progress_path.exists():
                        records = progress_path.read_text().splitlines()
                        for record in records[cursor:]:
                            print(record, flush=True)
                        cursor = len(records)
                    require(
                        time.monotonic() < deadline,
                        "native replay exceeded original 1200-second bound",
                    )
                    try:
                        run.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        pass
                require(
                    run.returncode == 0,
                    "native replay failed; see "
                    + str(args.output / "private-session.log"),
                )
            finally:
                if run.poll() is None:
                    # The session/group is created solely for this run.
                    import signal

                    os.killpg(run.pid, signal.SIGTERM)
                    try:
                        run.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(run.pid, signal.SIGKILL)
                        run.wait(timeout=5)
        result = json.loads((args.output / "result.json").read_text())
        require(result["status"] == "PASS", "missing passing native result")
        if not args.focus:
            require(
                set(result["cases"]) == set(REQUIRED), "required native cases omitted"
            )
        print(json.dumps(result), flush=True)
        return
    from native_driver import Native, identity, close_transport

    output = args.output
    state = output / "state"
    app = None
    child = None
    cases = {}
    completed = False
    errors = []

    def progress(case, status):
        item = {"case": case, "status": status, "monotonic_ns": time.monotonic_ns()}
        with (output / "progress.jsonl").open("a") as out:
            out.write(json.dumps(item) + "\n")
        print(json.dumps(item), flush=True)

    def done(case, evidence=True):
        cases[case] = evidence
        progress(case, "PASS")

    def disclose(mid, title, collapsed, key):
        old = app.state()["panels"][mid]["collapsed"]
        require(old != collapsed, "disclosure setup already in target state")
        control = app.find(
            ("Expand " if old else "Collapse ") + title, "button", root=app.panel(mid)
        )
        app.focus(control)
        app.key(key)
        opposite = ("Expand " if collapsed else "Collapse ") + title
        app.wait(
            lambda: control.get_name() == opposite, message="panel native disclosure"
        )
        saved = app.wait(
            lambda: app.state()
            if app.state()["panels"][mid]["collapsed"] == collapsed
            else None,
            message="panel persisted disclosure",
        )
        return saved

    def row_disclose(collapsed, key):
        control = app.find(
            ("Collapse " if collapsed else "Expand ") + "Overall utilization",
            "button",
            root=app.panel("cpu:host"),
        )
        app.focus(control)
        app.key(key)
        app.wait(
            lambda: control.get_name()
            == ("Expand " if collapsed else "Collapse ") + "Overall utilization",
            message="row native disclosure",
        )
        return app.wait(
            lambda: app.state()
            if app.state()["panels"]["cpu:host"]["sensors"]["cpu:host/usage"][
                "collapsed"
            ]
            == collapsed
            else None,
            message="row persisted disclosure",
        )

    def projection(state):
        return {
            k: copy.deepcopy(state[k])
            for k in ("schema_version", "dock", "panels", "interval_ms")
        }

    def chart_sensor(mid, sid, title, steps, name):
        panel = app.panel(mid)
        row = app.find("Collapse " + title, "button", root=panel)
        app.focus(row)
        row_y = app.bounds(row)[1]
        meters = [
            node
            for node in app.walk(panel)
            if node.get_name() == "Meter: Number"
              and row_y <= app.bounds(node)[1] < row_y + 120
        ]
        require(meters, "missing chart meter " + sid)
        meter = min(meters, key=lambda node: app.bounds(node)[1])
        app.focus(meter)
        for expected in steps:
            app.key("Return")
            app.wait(
                lambda: app.state()["panels"][mid]["sensors"][sid]["meter"] == expected,
                message="physical chart meter " + sid,
            )
        monitor_title = next(
            monitor["title"]
            for monitor in app.frame()["snapshot"]["monitors"]
            if monitor["id"] == mid
        )
        app.focus(app.find("Collapse " + monitor_title, "button", root=panel))
        meter_bounds = app.bounds(meter)
        inner = app.bounds(app.find(aid=mid + ":viewport", root=panel))
        if meter_bounds[1] + meter_bounds[3] + 100 > inner[1] + inner[3]:
            app.wheel([meter_bounds[0] + 100, meter_bounds[1] + 12], down=True)
            app.wait(
                lambda: app.bounds(meter)[1] < meter_bounds[1],
                message="reveal chart inside sensor viewport",
            )
        app.sequences()
        app.metric(mid + ":value:" + sid, name)
        app.screenshot(name + "-chart.png")

    def compare_state(before, after):
        require(
            before["schema_version"] == after["schema_version"]
            and before["interval_ms"] == after["interval_ms"],
            "persistence schema/interval changed",
        )
        require(before["dock"] == after["dock"], "persisted dock projection changed")
        for mid, panel in before["panels"].items():
            require(mid in after["panels"], "saved identity omitted on restore")
            for key in ("visible", "collapsed", "sensors"):
                require(
                    panel[key] == after["panels"][mid][key],
                    f"persisted {mid} {key} changed",
                )
        return sorted(set(after["panels"]) - set(before["panels"]))

    def recovery_case(mode):
        nonlocal app
        case = "recovery-" + mode
        progress(case, "RUNNING")
        app.shutdown()
        app.close()
        original = (state / "workspace.json").read_bytes()
        specimen = json.loads(original)
        specimen["schema_version"] = 999
        rejected = (
            json.dumps(specimen).encode() if mode == "schema" else b"{invalid json"
        )
        (state / "workspace.json").write_bytes(rejected)
        app = Native(args.binary, output / ("session-recovery-" + mode), state)
        app.find("Accept recovered layout", "button")
        require(
            (state / "workspace.json").read_bytes() == rejected,
            "rejected bytes overwritten during launch",
        )
        controls = [
            n
            for n in app.walk(app.panel("cpu:host"))
            if n.get_name() in ("Collapse CPU", "Expand CPU")
        ]
        require(len(controls) == 1, "recovery panel disclosure missing or ambiguous")
        control = controls[0]
        old_name = control.get_name()
        app.focus(control)
        app.key("Return")
        app.wait(
            lambda: control.get_name() != old_name,
            message="recovery native auto-save disclosure",
        )
        app.sequences()
        require(
            (state / "workspace.json").read_bytes() == rejected,
            "auto-save disclosure overwrote rejected bytes",
        )
        app.click(app.find("Save", "button"))
        app.click(app.find("Recall preset", "button"))
        app.interval_ms = saved["interval_ms"]
        app.journal(
            "interval-freshness",
            interval_ms=app.interval_ms,
            accepted_age_limit_seconds=app.interval_ms / 500,
            source="recalled preset during recovery",
        )
        app.sequences()
        require(
            (state / "workspace.json").read_bytes() == rejected,
            "rejected bytes overwritten before explicit accept",
        )
        app.click(app.find("Accept recovered layout", "button"))
        app.wait(
            lambda: (state / "workspace.rejected.json").exists()
            and (state / "workspace.rejected.json").read_bytes() == rejected,
            10,
            "exact rejected archive",
        )
        app.wait(
            lambda: app.state()["schema_version"] == 1,
            10,
            "valid recovered replacement",
        )
        app.key("Tab")
        app.sequences()
        app.save(
            "rejected-specimen.json",
            {
                "original_hex": rejected.hex(),
                "archive_hex": (state / "workspace.rejected.json").read_bytes().hex(),
                "replacement": app.state(),
            },
        )
        recovered = app.save_state()
        app.shutdown()
        app.close()
        app = Native(
            args.binary, output / ("session-recovery-" + mode + "-restart"), state
        )
        compare_state(recovered, app.state())
        app.no_tabs("recovery-restart-no-tabs")
        app.key("Tab")
        app.sequences()
        done(case)
        if app.interval_ms != 1000:
            app.interval(1000)

    def missing_device_case(hidden):
        nonlocal app
        progress("missing-device", "RUNNING")
        app.shutdown()
        app.close()
        # Dock geometry and panel preferences must come from the same capture.
        saved = copy.deepcopy(missing_device_workspace)
        mid = hidden["id"]
        missing = mid + ":saved-absent"
        saved["panels"][missing] = copy.deepcopy(saved["panels"][mid])
        saved["panels"][missing]["visible"] = True
        saved["monitors"][missing] = copy.deepcopy(saved["monitors"][mid])
        saved["monitors"][missing]["id"] = missing
        saved["panels"][mid]["visible"] = False

        def substitute_identity(node):
            if isinstance(node, dict):
                if node.get("monitor_id") == mid:
                    node["monitor_id"] = missing
                for value in node.values():
                    substitute_identity(value)
            elif isinstance(node, list):
                for value in node:
                    substitute_identity(value)

        substitute_identity(saved["dock"])
        # A stopped-app configuration specimen preserves actual device metadata; no measurements are supplied.
        (output / "missing-device-config.json").write_text(json.dumps(saved, indent=2))
        (state / "workspace.json").write_text(json.dumps(saved))
        app = Native(args.binary, output / "session-missing-device", state)
        app.sequences()
        restored = app.save_state()
        require(restored["dock"] == saved["dock"], "missing specimen dock changed")
        require(
            restored["panels"][missing]["sensors"]
            == saved["panels"][missing]["sensors"],
            "missing saved-device sensor preferences lost",
        )
        require(
            restored["monitors"][missing] == saved["monitors"][missing],
            "missing saved-device metadata lost",
        )
        require(
            restored["panels"][missing]["collapsed"]
            == saved["panels"][missing]["collapsed"],
            "missing saved-device preference lost",
        )
        entry = next(
            e
            for e in app.frame()["rendered"]
            if e["monitor_id"] == missing and e["element_id"].endswith(":summary")
        )
        require(
            "Unavailable" in entry["label"],
            "missing saved device presented measured data",
        )
        title = saved["monitors"][missing]["title"]
        app.focus(
            app.find(
                ("Expand " if saved["panels"][missing]["collapsed"] else "Collapse ")
                + title,
                "button",
                root=app.panel(missing),
            )
        )
        app.missing_monitor(missing)
        app.save(
            "missing-device-specimen.json",
            {
                "metadata": saved["monitors"][missing],
                "original_identity": mid,
                "missing_identity": missing,
                "dock": saved["dock"],
                "preferences": saved["panels"][missing],
                "rendered": entry,
                "physical_removal": "UNVERIFIED: stopped-app config specimen used",
            },
        )
        done("missing-device")

    try:
        progress("launch", "RUNNING")
        app = Native(args.binary, output / "session-01", state)
        app.no_tabs("launch-no-tabs")
        missing_device_workspace = copy.deepcopy(app.state())
        done("launch")
        if args.focus == "missing-device":
            hidden = next(
                m
                for m in app.frame()["snapshot"]["monitors"]
                if m["kind"] in ("Gpu", "Network")
            )
            missing_device_case(hidden)
            app.shutdown()
            completed = True
            return
        if args.focus == "restart":
            saved = app.save_state()
            app.shutdown()
            app.close()
            app = Native(args.binary, output / "session-02", state)
            compare_state(saved, app.state())
            app.no_tabs("restart-no-tabs")
            app.shutdown()
            done("restart")
            completed = True
            return
        if args.focus == "recovery":
            app.click(app.find("Save preset", "button"))
            saved = app.wait(
                lambda: app.state("preset.json"), message="recovery setup preset"
            )
            for mode in ("schema", "json"):
                recovery_case(mode)
            app.shutdown()
            done("recovery")
            completed = True
            return
        if args.focus == "launch":
            app.shutdown()
            completed = True
            return
        progress("metrics", "RUNNING")
        app.resize(1440, 1000)
        app.focus(
            app.find(
                "Collapse Overall utilization", "button", root=app.panel("cpu:host")
            )
        )
        app.metric("cpu:host:value:cpu:host/usage", "cpu-visible")
        app.focus(app.find("Collapse Memory", "button", root=app.panel("memory:host")))
        app.metric("memory:host:summary", "ram-visible")
        gpus = [m for m in app.frame()["snapshot"]["monitors"] if m["kind"] == "Gpu"]
        gpu_temperature_artifacts = []
        for index, gpu in enumerate(gpus):
            # First launch shows one GPU. Explicitly enable every discovered
            # adapter before preserving the original all-GPU accuracy checks.
            if not app.state()["panels"][gpu["id"]]["visible"]:
                app.click(app.find("Show " + gpu["title"], "button"))
                app.wait(
                    lambda: app.state()["panels"][gpu["id"]]["visible"],
                    message="enable GPU for physical comparison",
                )
            app.focus(
                app.find(
                    "Collapse " + gpu["title"], "button", root=app.panel(gpu["id"])
                )
            )
            app.metric(gpu["id"] + ":summary", f"gpu-{index}-visible")
        done("metrics", {"gpu_count": len(gpus)})
        if args.focus == "metrics":
            app.shutdown()
            completed = True
            return
        progress("collapse", "RUNNING")
        initial = app.save_state()
        app.save("collapse-baseline-state.json", initial)
        other = copy.deepcopy(initial["panels"]["memory:host"])
        cpu_before = app.bounds(app.panel("cpu:host"))
        row_disclose(True, "Return")
        app.metric("cpu:host:value:cpu:host/usage", "row-compact")
        disclose("cpu:host", "CPU", True, "space")
        app.metric("cpu:host:summary", "panel-compact")
        compact = app.bounds(app.panel("cpu:host"))
        require(compact[3] < cpu_before[3], "panel did not compact")
        after_collapse = app.state()
        app.save("collapse-after-state.json", after_collapse)
        require(
            after_collapse["panels"]["memory:host"] == other,
            "independent Memory choices changed",
        )
        app.save("collapsed-sequences.json", app.sequences())
        disclose("cpu:host", "CPU", False, "Return")
        require(
            app.state()["panels"]["cpu:host"]["sensors"]["cpu:host/usage"]["collapsed"],
            "row choice lost after panel expansion",
        )
        row_disclose(False, "space")
        require(
            app.state()["panels"]["cpu:host"]["sensors"]["cpu:host/usage"]["meter"]
            == initial["panels"]["cpu:host"]["sensors"]["cpu:host/usage"]["meter"],
            "meter choice lost",
        )
        row_disclose(True, "space")
        row_disclose(False, "Return")
        disclose("cpu:host", "CPU", True, "Return")
        disclose("cpu:host", "CPU", False, "space")
        done("collapse")
        if args.focus == "collapse":
            app.shutdown()
            completed = True
            return
        progress("charts", "RUNNING")
        row_control = app.find(
            "Collapse Overall utilization", "button", root=app.panel("cpu:host")
        )
        app.focus(row_control)
        row_y = app.bounds(row_control)[1]
        meters = [
            n
            for n in app.walk(app.panel("cpu:host"))
            if n.get_role_name() == "button"
            and n.get_name() == "Meter: Number"
              and row_y <= app.bounds(n)[1] < row_y + 120
        ]
        require(meters, "CPU usage row meter control absent")
        meter = min(meters, key=lambda n: app.bounds(n)[1])
        app.focus(meter)
        for expected in ("line", "bar", "sparkline"):
            app.key("Return")
            app.wait(
                lambda: app.state()["panels"]["cpu:host"]["sensors"]["cpu:host/usage"][
                    "meter"
                ]
                == expected,
                message="compatible meter " + expected,
            )
        app.key("Alt_L", "Next")
        app.sequences()
        app.metric("cpu:host:value:cpu:host/usage", "chart-physical-value")
        app.screenshot("expanded-chart.png")
        app.save(
            "chart-history-evidence.json",
            {
                "sequences": app.sequences(),
                "scope": "Production history insertion plus required model/app tests and visually reviewed physical chart; latest diagnostic JSON does not expose every retained history point.",
            },
        )
        chart_sensor(
            "memory:host", "memory:host/used", "RAM used", ("bar",), "ram-capacity"
        )
        for index, gpu in enumerate(gpus):
            temperature = next(
                (
                    sensor
                    for sensor in app.frame()["snapshot"]["sensors"]
                    if sensor["monitor_id"] == gpu["id"] and sensor["unit"] == "Celsius"
                ),
                None,
            )
            if temperature is not None:
                chart_sensor(
                    gpu["id"],
                    temperature["id"],
                    temperature["title"],
                    ("sparkline",),
                    f"gpu-{index}-temperature",
                )
                gpu_temperature_artifacts.append(f"gpu-{index}-temperature")
        done(
            "charts",
            {
                "gpu_temperature_count": len(gpu_temperature_artifacts),
                "gpu_temperature_artifacts": gpu_temperature_artifacts,
            },
        )
        progress("inner-scroll", "RUNNING")
        # Navigation preservation uses the canonical PID census. The product
        # defaults to CPU descending, so choose PID ascending through its UI.
        app.focus(app.find("Sort by PID", "button", root=app.panel("processes")))
        app.key("Return")
        app.enter_processes()
        rows = app.frame()["snapshot"]["processes"]
        first = identity(rows[0])
        app.key("Home")
        app.acknowledge(first, time.monotonic() + 8)
        panel_before = app.bounds(app.panel("processes"))
        cell = app.find(aid=first + ":cell:0")
        x = app.bounds(cell)[0]
        app.key("Right")
        app.wait(lambda: app.bounds(cell)[0] < x, message="inner horizontal right")
        require(
            app.bounds(app.panel("processes")) == panel_before,
            "inner scroll moved outer panel",
        )
        x = app.bounds(cell)[0]
        app.key("Left")
        app.wait(lambda: app.bounds(cell)[0] > x, message="inner horizontal left")
        panel = app.panel("processes")
        before = app.bounds(panel)
        header = app.find("Hide Processes", "button", root=panel)
        hb = app.bounds(header)
        app.wheel([hb[0] + hb[2] / 2, hb[1] + hb[3] / 2], down=True)
        shifted = app.wait(
            lambda: app.bounds(panel) if app.bounds(panel)[1] < before[1] else None,
            message="outer wheel establishes travel",
        )
        clip = app.bounds(app.find(aid="processes:rows-viewport"))
        workspace = app.bounds(app.find(aid="workspace:viewport"))
        app.wheel(
            [max(clip[0], workspace[0]) + 30, max(clip[1], workspace[1]) + 30],
            down=False,
        )
        app.wait(
            lambda: app.bounds(panel)[1] > shifted[1],
            message="single inner edge wheel reaches outer viewport",
        )
        app.acknowledge(first, time.monotonic() + 5)
        app.save(
            "inner-edge-wheel.json",
            {
                "selected_identity": first,
                "before": before,
                "after_down": shifted,
                "after_edge_up": app.bounds(panel),
            },
        )
        app.key("Tab")
        before = app.bounds(panel)
        app.key("Alt_L", "Next")
        app.wait(
            lambda: app.bounds(panel)[1] < before[1],
            message="Tab escape outer movement",
        )
        app.key("Alt_L", "Prior")
        app.wait(
            lambda: app.bounds(panel)[1] == before[1],
            message="outer return for retained selection",
        )
        app.acknowledge(first, time.monotonic() + 5)
        app.frame()
        app.screenshot("inner-scroll.png")
        done("inner-scroll")
        progress("held-input", "RUNNING")
        app.resize(1440, 1000)
        app.enter_processes()
        rows = app.frame()["snapshot"]["processes"]
        app.key("End")
        app.acknowledge(identity(rows[-1]), time.monotonic() + 8)
        subprocess.run(
            ["rtk", "proxy", "xset", "r", "rate", "250", "25"], check=True, timeout=5
        )
        from native_input import exercise

        def selected_pid(deadline):
            selected = app.selected(deadline)
            return (int(selected[0].split(":")[1]), selected[0]) if selected else None

        exercise(app, "held-up-25hz", ("Up",), None, -1, observe=selected_pid)
        app.key("End")
        rows = app.frame()["snapshot"]["processes"]
        app.acknowledge(identity(rows[-1]), time.monotonic() + 5)
        require(
            len(rows) > 64,
            "insufficient actual process population for exact64 regression",
        )
        exercise(
            app,
            "exact-64-up",
            ("Up",),
            None,
            -1,
            burst=64,
            expected_identity=identity(rows[-65]),
            observe=selected_pid,
        )
        stable = identity(next(row for row in rows if row["identity"]["pid"] == 1))
        app.navigate(stable)
        cell = app.find(aid=stable + ":cell:0")
        for key, sign in (("Right", -1), ("Left", 1)):
            exercise(
                app,
                "held-table-" + key.lower(),
                (key,),
                lambda: app.bounds(cell)[0],
                sign,
            )
            app.acknowledge(stable, time.monotonic() + 5)
        progress("process", "RUNNING")
        child, info = start_child()
        target = f"process:{child.pid}:{info['stat']['value']['start_ticks']}"
        app.save("real-child-start.json", {"identity": target, "independent": info})
        app.wait(
            lambda: any(
                identity(r) == target for r in app.frame()["snapshot"]["processes"]
            ),
            5,
            "real child appearance",
        )
        inspection = ProcessInspection(app, target)
        selected_row = app.navigate(target, on_acknowledged=inspection.acknowledge)
        cached_cells = [
            node.get_accessible_id()
            for node in app.walk(selected_row[1])
            if (node.get_accessible_id() or "").startswith(target + ":cell:")
        ]
        require(
            set(cached_cells) == {target + f":cell:{column}" for column in range(8)},
            "selected real child does not expose all eight native cells",
        )
        app.save(
            "real-child-cell-discovery.json",
            {
                "identity": target,
                "cell_ids": cached_cells,
                "acknowledgement": inspection.acknowledgement,
            },
        )
        for column in range(8):
            inspection.metric(
                target + f":cell:{column}", f"child-cell-{column}", visible=False
            )
        # Independently match every column again while its full label is actually clipped-visible.
        for column in range(8):
            key = "Left" if column == 0 else "Right"
            name = (
                "child-left"
                if column == 0
                else "child-right"
                if column == 7
                else f"child-visible-{column}"
            )
            deadline = time.monotonic() + 5
            reveal_process_cell(
                app,
                target + f":cell:{column}",
                key,
                deadline,
                prepare_missing=inspection.preparation(missing_row=True),
            )
            inspection.metric(target + f":cell:{column}", name)
        app.sequences()
        deadline = time.monotonic() + 5
        inspection.preparation()(deadline)
        before_seq = app.frame()["snapshot"]["sequence"]
        stop_child(child)
        app.wait_for_process_exit(target, before_seq, time.monotonic() + 5)
        app.save(
            "real-child.json",
            {
                "independent_before": info,
                "pid": child.pid,
                "exit_code": child.returncode,
                "after": process(child.pid),
            },
        )
        app.screenshot("child-exited.png")
        done("process")
        if args.focus == "process":
            app.shutdown()
            completed = True
            return
        progress("split", "RUNNING")
        # CPU and Memory are adjacent real panels in the initial native layout.
        app.resize(1440, 1000)
        app.focus(app.find("Collapse CPU", "button", root=app.panel("cpu:host")))
        summary = app.find(aid="cpu:host:summary")
        app.wait(lambda: app.visible(summary), message="visible draggable CPU header")
        source = app.bounds(summary)
        target = app.bounds(app.panel("memory:host"))
        before = app.state()["dock"]
        missing_device_workspace = copy.deepcopy(app.save_state())
        # No async action may be outstanding when arming a pointer drag.
        source = app.bounds(summary)
        target = app.bounds(app.panel("memory:host"))
        require(
            target[1] >= 0 and target[1] + 60 < 1000,
            "Memory split target is not in the window",
        )
        app.drag(
            [source[0] + min(300, source[2] / 2), source[1] + source[3] / 2],
            [target[0] + target[2] * 0.8, target[1] + target[3] / 2],
        )
        from native_contract import horizontal_pair

        split = app.wait(
            lambda: horizontal_pair(
                app.state()["dock"]["center"], "memory:host", "cpu:host"
            ),
            10,
            "actual horizontal sibling split",
        )
        app.save(
            "split-structure.json",
            {"before": before, "after": app.state()["dock"], "horizontal_pair": split},
        )
        left = app.bounds(app.panel("memory:host"))
        right = app.bounds(app.panel("cpu:host"))
        if right[0] >= 1400:
            app.key("Alt_L", "Right")
            app.wait(
                lambda: app.bounds(app.panel("cpu:host"))[0] < right[0] - 20,
                message="reveal split divider horizontally",
            )
            left = app.bounds(app.panel("memory:host"))
            right = app.bounds(app.panel("cpu:host"))
        require(
            left[0] < right[0] and abs(left[1] - right[1]) < 4,
            "split geometry does not match horizontal siblings",
        )
        divider = (left[0] + left[2] + right[0]) / 2
        require(8 < divider < 1400, "divider is outside actual workspace viewport")
        app.drag(
            [divider, max(260, left[1] + 80)], [divider - 80, max(260, left[1] + 80)]
        )
        app.wait(
            lambda: app.bounds(app.panel("memory:host"))[2] < left[2] - 20,
            message="actual divider drag changed left width",
        )
        app.save(
            "divider-movement.json",
            {
                "left_before": left,
                "right_before": right,
                "left_after": app.bounds(app.panel("memory:host")),
                "right_after": app.bounds(app.panel("cpu:host")),
                "dock": app.save_state()["dock"],
            },
        )
        app.screenshot("split-divider.png")
        app.no_tabs("split-no-tabs")
        done("split")
        if args.focus == "split":
            app.shutdown()
            completed = True
            return
        progress("outer-scroll", "RUNNING")
        app.resize(960, 640)
        anchors = [app.panel("processes"), app.panel("cpu:host")]
        # Establish travel in each direction; signed movements cannot pass at a boundary.
        movement = []
        for keys, axis, sign in [
            (("Alt_L", "Next"), 1, -1),
            (("Alt_L", "Prior"), 1, 1),
            (("Alt_L", "Right"), 0, -1),
            (("Alt_L", "Left"), 0, 1),
        ]:
            before = [app.bounds(n) for n in anchors]
            app.key(*keys)

            def moved():
                after = [app.bounds(n) for n in anchors]
                return (
                    after
                    if all(
                        (b[axis] - a[axis]) * sign > 0 for a, b in zip(before, after)
                    )
                    else None
                )

            after = app.wait(moved, message="outer signed movement " + str(keys))
            app.frame()
            movement.append({"keys": keys, "before": before, "after": after})
        app.save("outer-movement.json", movement)
        app.screenshot("outer-scroll.png")
        app.focus(
            app.find(
                "Collapse Overall utilization", "button", root=app.panel("cpu:host")
            )
        )
        # focus() already requires clipped geometry within its original five-second deadline.
        origin = app.bounds(anchors[0])
        app.key("Alt_L", "Next")
        before = app.wait(
            lambda: app.bounds(anchors[0])
            if app.bounds(anchors[0])[1] < origin[1]
            else None,
            message="acknowledge deliberate scroll before sample persistence",
        )
        app.sequences()
        require(
            app.bounds(anchors[0]) == before,
            "new samples snapped deliberate outer scroll",
        )
        app.save(
            "deliberate-scroll-sequences.json",
            {
                "origin": origin,
                "after_acknowledged_input": before,
                "after_samples": app.bounds(anchors[0]),
            },
        )
        done("outer-scroll")
        app.enter_processes()
        app.key("Home")
        app.acknowledge(stable, time.monotonic() + 5)
        anchor = app.panel("processes")
        for key, axis, sign in (
            ("Next", 1, -1),
            ("Prior", 1, 1),
            ("Right", 0, -1),
            ("Left", 0, 1),
        ):
            exercise(
                app,
                "held-outer-" + key.lower(),
                ("Alt_L", key),
                lambda: app.bounds(anchor)[axis],
                sign,
            )
        app.metric("processes:summary", "after-held-input", visible=False)
        done("held-input")
        progress("preset", "RUNNING")
        app.interval(2000)
        app.resize(960, 640)
        row_disclose(True, "Return")
        disclose("cpu:host", "CPU", True, "space")
        hidden = (
            gpus[0]
            if gpus
            else next(
                m for m in app.frame()["snapshot"]["monitors"] if m["kind"] == "Network"
            )
        )
        hide_control = app.find(
            "Hide " + hidden["title"], "button", root=app.panel(hidden["id"])
        )
        app.focus(hide_control)
        app.key("Return")
        app.wait(
            lambda: not app.state()["panels"][hidden["id"]]["visible"],
            message="real monitor hidden",
        )
        app.click(app.find("Save preset", "button"))
        saved = app.wait(lambda: app.state("preset.json"), 10, "saved preset")
        disclose("cpu:host", "CPU", False, "Return")
        app.click(app.find("Recall preset", "button"))
        app.wait(
            lambda: app.state()["panels"]["cpu:host"]["collapsed"], 10, "preset restore"
        )
        compare_state(saved, app.state())
        app.no_tabs("recall-no-tabs")
        done("preset")
        progress("restart", "RUNNING")
        saved = app.save_state()
        app.shutdown()
        app.close()
        app = Native(args.binary, output / "session-02", state)
        restored = app.wait(lambda: app.state(), 10, "restored state")
        new = compare_state(saved, restored)
        app.no_tabs("restart-no-tabs")
        done("restart", {"new_discovery": new})
        app.interval(1000)
        for mode in ("schema", "json"):
            recovery_case(mode)
        missing_device_case(hidden)
        app.shutdown()
        completed = True
    except BaseException as error:
        errors.append(str(error))
        if app is not None:
            try:
                app.screenshot("failure.png")
                app.save("failure-frame.json", app.frame())
                app.save(
                    "failure-panels.json",
                    {
                        mid: app.bounds(app.panel(mid))
                        for mid in ("cpu:host", "memory:host", "processes")
                    },
                )
            except BaseException as evidence_error:
                errors.append("failure evidence: " + str(evidence_error))
        raise
    finally:
        for resource in (child, app):
            if resource is None:
                continue
            try:
                if resource is child:
                    stop_child(child)
                else:
                    app.close()
            except BaseException as error:
                errors.append("cleanup: " + str(error))
        try:
            close_transport(output)
        except BaseException as error:
            errors.append("transport cleanup: " + str(error))
        status = result_status(cases, args.focus, completed, errors)
        (output / "result.json").write_text(
            json.dumps(
                {
                    "status": status,
                    "errors": errors,
                    "cases": cases,
                    "focused_preparation": args.focus,
                    "publication_timing_instrumented": args.trace_publication,
                    "limits": [
                        "NVIDIA hardware accuracy unverified",
                        "macOS/Windows native unverified",
                        "physical device removal unverified; stopped-app configuration specimen",
                        "history points not directly exposed by latest diagnostic JSON",
                    ],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
