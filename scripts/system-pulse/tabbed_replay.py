#!/usr/bin/env python3
"""Exercise every tab and real product action in an owned X11/DBus session."""

import argparse
import copy
import json
from pathlib import Path
import subprocess
import time

from application_replay import enter, library, persisted, preset_action, press, process_flows
from host_accuracy import require
from native_driver import Atspi, close_transport, digest, spin
from tabbed_contract import SCREENS, check_metric, expected_metric, device_label
from tabbed_driver import TabbedNative


class MenuChoiceAbsent(Exception):
    pass


def choose_menu(app, label):
    menu = app.find(role="menu")
    items = [node for node in app.walk(menu, strict=True) if node.get_role_name() == "menu item"]
    matches = [index for index, node in enumerate(items) if node.get_name() == label]
    if not matches:
        raise MenuChoiceAbsent(label)
    require(len(matches) == 1, "device menu label must be unique: " + label)
    target = matches[0]
    node = items[target]
    if not app.visible(node):
        selected = [index for index, item in enumerate(items) if item.get_state_set().contains(Atspi.StateType.SELECTED)]
        if not selected:
            app.key("Down")
            current = 0
        else:
            require(len(selected) == 1, "ambiguous menu keyboard selection")
            current = selected[0]
        key = "Down" if target >= current else "Up"
        for _ in range(abs(target - current)):
            app.key(key)
        app.wait(lambda: app.visible(node) and node.get_state_set().contains(Atspi.StateType.SELECTED),
                 message="menu keyboard reveals " + label)
    require(app.visible(node), "menu item is clipped")
    app.click(node)


def metric(app, screen, sensor_id, element_id):
    app.select_screen(screen)
    node = app.find(aid=element_id)

    def matched():
        before = app.frame()
        node.clear_cache()
        actual = node.get_name()
        after = app.frame()
        if before["snapshot"]["sequence"] != after["snapshot"]["sequence"]:
            return None
        if actual != expected_metric(before, sensor_id, app.interval_ms):
            return None
        expected = check_metric(before, sensor_id, actual, app.interval_ms)
        require(app.visible(node), "matched metric is clipped")
        return {"frame": before, "actual": actual, "expected": expected,
                "element_id": element_id, "sensor_id": sensor_id,
                "bounds": app.bounds(node), "ancestors": app.ancestors(node)}

    result = app.wait(matched, 5, "independent physical metric " + sensor_id)
    app.save("metric-" + screen + ".json", result)
    app.screenshot("metric-" + screen + ".png")


def screens_and_devices(app, record):
    app.key("Control_L", "Tab")
    app.wait(lambda: app.selected_screen() == "cpu", message="keyboard works immediately after launch")
    app.resize(1280, 880)
    app.select_screen("summary")
    tabs = [node for node in app.walk(app.find(aid="screen-tabs"), strict=True)
            if (node.get_accessible_id() or "").startswith("screen-tab:")]
    require({node.get_accessible_id() for node in tabs} == {"screen-tab:" + s for s in SCREENS},
            "missing or unexpected tabs")
    require(all(node.get_role() == Atspi.Role.PAGE_TAB for node in tabs), "tabs lack native roles")
    for screen in SCREENS:
        app.select_screen(screen)
        require(app.panel(screen).get_role() == Atspi.Role.SCROLL_PANE, "screen must expose tab panel role")
        app.screenshot("screen-" + screen + ".png")
    # Arrows/Home/End and Control+Tab operate through real keyboard events.
    app.focus(app.find(aid="screen-tab:settings"))
    for keys, expected in [(("Home",), "summary"), (("Right",), "cpu"),
                           (("End",), "settings"), (("Control_L", "Tab"), "summary"),
                           (("Control_L", "Shift_L", "Tab"), "settings")]:
        app.key(*keys)
        app.wait(lambda: app.selected_screen() == expected, message="keyboard screen " + expected)
    metric(app, "cpu", "cpu:host/usage", "hero:cpu:host/usage")
    metric(app, "memory", "memory:host/used", "hero:memory:host/used")
    choices, expected_devices, disappeared = [], [], []
    for screen, kind in (("gpu", "Gpu"), ("disks", "Volume"), ("network", "Network")):
        app.select_screen(screen)
        monitors = [m for m in app.frame()["snapshot"]["monitors"] if m["kind"] == kind]
        expected_devices.extend({"screen": screen, "id": m["id"], "title": m["title"]} for m in monitors)
        for monitor in monitors:
            label = device_label(monitor, app.frame()["snapshot"]["monitors"])
            picker = app.find(aid="screen-device:" + screen)
            app.click(picker)
            try:
                choose_menu(app, label)
            except MenuChoiceAbsent:
                frame = app.frame()
                require(monitor["id"] not in {m["id"] for m in frame["snapshot"]["monitors"]},
                        "available device absent from menu: " + monitor["id"])
                disappeared.append({"choice": {"screen": screen, "id": monitor["id"], "title": monitor["title"]},
                                    "frame": frame})
                app.key("Escape")
                continue
            persisted(app, lambda state: state["screens"]["devices"].get(screen) == monitor["id"],
                      "selected stable device " + monitor["id"])
            choices.append({"screen": screen, "id": monitor["id"], "title": monitor["title"]})
        if monitors:
            app.screenshot("selected-" + screen + ".png")
    record["disappeared_devices"] = disappeared
    record["expected_devices"] = expected_devices
    record["devices"] = choices
    record.setdefault("cases", []).append("screens-devices-metrics")
    record["checks"].append("all ten native tabs, roles, keyboard selection, independently formatted CPU/RAM, every discovered GPU/disk/interface selector")


def settings_and_presets(app, record):
    app.select_screen("settings")
    sensor_path = lambda state: state["panels"]["cpu:host"]["sensors"]["cpu:host/usage"]
    require(not any("Visible sensors" in node.get_name()
                    for node in app.walk(app.panel("settings"), strict=True)),
            "removed sensor controls remain in Settings")
    for name in ("Light", "IBM Plex Sans", "IBM Plex Mono", "2 s"):
        press(app, name, root=app.panel("settings"))
    expected = {"theme": "light", "ui_font": "ibm_plex_sans", "numeric_font": "ibm_plex_mono"}
    persisted(app, lambda state: state["appearance"] == expected and state["interval_ms"] == 2000,
              "appearance and interval saved")
    app.interval_ms = 2000
    app.screenshot("settings-light.png")
    name_input = "New preset name or rename target…"
    enter(app, name_input, "safefirst")
    press(app, "Save current workspace")
    app.wait(lambda: "safefirst" in library(app), 10, "first preset saved")
    first = copy.deepcopy(library(app)["safefirst"])
    require(first["appearance"] == expected and first["screens"]["active"] == "settings", "preset lost screen or appearance")
    press(app, "Dark", root=app.panel("settings"))
    persisted(app, lambda state: state["appearance"]["theme"] == "dark", "dark saved")
    enter(app, name_input, "safesecond")
    press(app, "Save current workspace")
    app.wait(lambda: "safesecond" in library(app), 10, "second preset saved")
    second = copy.deepcopy(library(app)["safesecond"])
    enter(app, name_input, "saferenamed")
    preset_action(app, "safefirst", "Rename")
    app.wait(lambda: "saferenamed" in library(app) and "safefirst" not in library(app), 10, "preset renamed")
    require(library(app)["saferenamed"] == first and library(app)["safesecond"] == second, "rename altered preset data")
    for action in ("Overwrite…", "Delete…"):
        before = copy.deepcopy(library(app))
        preset_action(app, "saferenamed", action)
        press(app, "Cancel", role="button")
        require(library(app) == before, "Cancel changed presets")
        preset_action(app, "saferenamed", action)
        press(app, "Confirm", role="button")
        app.wait(lambda: (library(app)["saferenamed"]["appearance"]["theme"] == "dark")
                 if action == "Overwrite…" else "saferenamed" not in library(app),
                 10, "confirmed " + action)
        require(library(app)["safesecond"] == second, "action changed another preset")
    press(app, "Use Minimal")
    app.wait(lambda: app.selected_screen() == "summary", message="builtin selects Summary")
    app.key("Control_L", "Tab")
    app.wait(lambda: app.selected_screen() == "cpu", message="keyboard works immediately after builtin recall")
    app.select_screen("settings")
    press(app, "Use safesecond")
    persisted(app, lambda state: state["appearance"] == second["appearance"]
              and state["screens"] == second["screens"] and sensor_path(state) == sensor_path(second),
              "named preset restores screens and sensors")
    app.interval_ms = second["interval_ms"]
    record["checks"].append("removed sensor controls, appearance/interval, named preset save/rename/overwrite/delete with Cancel, builtin and named recall")
    record.setdefault("cases", []).append("settings-presets")
    return copy.deepcopy(library(app))


def minimum_window(app, record):
    app.resize(960, 640)
    for screen in SCREENS:
        app.select_screen(screen)
        app.screenshot("minimum-" + screen + ".png")
    app.select_screen("processes")
    table = app.find(aid="processes:viewport")
    app.focus(table)
    for key in ("End", "Home"):
        app.key(key)
        def selected_visible():
            rows = [node for node in app.walk(app.panel("processes"), strict=True)
                    if (node.get_accessible_id() or "").startswith("process:")
                    and ":cell:" not in node.get_accessible_id()
                    and node.get_state_set().contains(Atspi.StateType.SELECTED)]
            return len(rows) == 1 and app.visible(app.find(aid=rows[0].get_accessible_id() + ":cell:0"))
        app.wait(selected_visible, message="minimum process " + key)
    app.screenshot("minimum-process-keyboard.png")
    record.setdefault("cases", []).append("minimum-window")
    app.resize(1280, 880)
    record["checks"].append("all ten screens at minimum window, process Home/End visibly selects rows")


def unavailable_and_recovery(binary, output, saved, record):
    state = output / "missing-state"
    state.mkdir()
    missing = copy.deepcopy(saved)
    missing["screens"]["active"] = "gpu"
    missing["screens"]["devices"]["gpu"] = "gpu:disconnected-acceptance-device"
    (state / "workspace.json").write_text(json.dumps(missing))
    app = TabbedNative(binary, output / "missing", state)
    try:
        require(app.selected_screen() == "gpu", "missing device lost selected screen")
        picker = app.find(aid="screen-device:gpu")
        require("Unavailable" in picker.get_name() and "gpu:disconnected-acceptance-device" in picker.get_name(),
                "missing device silently became a different device")
        require(app.state()["screens"]["devices"]["gpu"] == missing["screens"]["devices"]["gpu"],
                "missing saved device identity changed")
        app.screenshot("missing-selected-device.png")
        app.shutdown()
    finally:
        app.close()
    state = output / "recovery-state"
    state.mkdir()
    original = b'{"schema_version":'
    (state / "workspace.json").write_bytes(original)
    for accept in (False, True):
        app = TabbedNative(binary, output / ("recovered" if accept else "recovery"), state)
        try:
            recovery = app.find(aid="accept-screen-recovery")
            spin(1)
            require((state / "workspace.json").read_bytes() == original, "invalid input overwritten before acceptance")
            if accept:
                require(app.visible(recovery), "recovery control clipped")
                app.click(recovery)
                app.wait(lambda: app.state().get("schema_version") == 1, 10, "explicit recovery saved")
                app.key("Control_L", "Tab")
                app.wait(lambda: app.selected_screen() == "cpu", message="keyboard works immediately after recovery")
            app.screenshot("accepted.png" if accept else "retained.png")
            app.shutdown()
            if not accept:
                require((state / "workspace.json").read_bytes() == original, "shutdown overwrote invalid input")
        finally:
            app.close()
    record.setdefault("cases", []).append("unavailable-recovery")
    record["checks"].append("missing selected device stays unavailable; corrupt input survives shutdown and restart until explicit recovery")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = {"status": "FAIL", "checks": [], "binary_sha256": digest(args.binary)}
    children, app = [], None
    started = time.monotonic()
    try:
        for suffix in "abc":
            name = "pulse-audit-" + suffix
            children.append(subprocess.Popen([
                "/usr/bin/python3", "-c", "import ctypes,time; ctypes.CDLL(None).prctl(15,b"
                + repr(name) + ",0,0,0); time.sleep(600)",
            ]))
        app = TabbedNative(args.binary.resolve(), output / "native", output / "state")
        spin(1)
        screens_and_devices(app, record)
        app.select_screen("processes")
        process_flows(app, children, record)
        record.setdefault("cases", []).append("process-actions")
        app.find(aid="process-details")
        presets = settings_and_presets(app, record)
        minimum_window(app, record)
        app.select_screen("gpu")
        saved = copy.deepcopy(app.save_state())
        app.shutdown()
        app.close()
        app = TabbedNative(args.binary.resolve(), output / "restart", output / "state")
        require(app.selected_screen() == "gpu", "restart lost active screen")
        for key in ("screens", "appearance", "interval_ms"):
            require(app.state()[key] == saved[key], "restart lost " + key)
        require(library(app) == presets, "restart changed named presets")
        app.screenshot("restart-gpu.png")
        app.shutdown()
        app.close()
        record.setdefault("cases", []).append("restart")
        record["checks"].append("normal shutdown/restart retains active tab, selected devices, settings and presets")
        unavailable_and_recovery(args.binary.resolve(), output, saved, record)
        record["status"] = "PASS"
        print("Tabbed native replay: PASS", flush=True)
    except BaseException as error:
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        try:
            if app is not None:
                try:
                    if not app.closed and app.app is not None and app.app.poll() is None:
                        app.screenshot("failure.png")
                except Exception as error:
                    record["failure_screenshot_error"] = f"{type(error).__name__}: {error}"
                finally:
                    app.close()
        finally:
            try:
                for child in children:
                    if child.poll() is None:
                        child.terminate()
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait(timeout=5)
                record["children"] = [{"pid": child.pid, "exit_code": child.poll()} for child in children]
                record["seconds"] = time.monotonic() - started
                (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
            finally:
                close_transport(output)


if __name__ == "__main__":
    main()
