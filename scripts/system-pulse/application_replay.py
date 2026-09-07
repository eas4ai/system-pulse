#!/usr/bin/env python3
"""Native product flows; run inside an owned private X11/DBus session."""

import argparse
import copy
import json
from pathlib import Path
import subprocess

from host_accuracy import require
from native_driver import (
    Native,
    Atspi,
    X,
    xtest,
    close_transport,
    digest,
    identity,
    spin,
)


def press(app, name, *, root=None, role=None):
    node = app.find(name, role, root=root)
    if name == "Settings & presets":
        app.click(node)
    else:
        app.focus(node)
        app.key("Return")


def enter(app, placeholder, value):
    node = app.find(placeholder)
    require(node.get_component_iface().grab_focus(), "input focus rejected")
    # The AT-SPI focus request and X11 typing use different event queues.
    # Let the native focus action reach the editor before dispatching a key burst.
    spin(0.1)
    # Focus transfers from the semantic frame to its internal text editor.
    # AT-SPI does not expose that internal focus node; actual typing below
    # must produce the expected projection or stored preset name.
    app.wait(lambda: app.visible(node), message="input revealed after native focus")
    app.key("Control_L", "a")
    app.key("BackSpace")
    for char in value:
        key = {" ": "space", "-": "minus"}.get(char, char.lower())
        app.key(*(["Shift_L", key] if char.isupper() else [key]))
    # AccessKit exposes this input without an AT-SPI Text interface.
    # The following projection/library checks acknowledge the actual input effect.
    spin(0.1)
    app.journal("typed-input", value=value, attributes=node.get_attributes())


def persisted(app, predicate, label):
    return app.wait(lambda: predicate(app.state()), 10, label)


def library(app):
    return app.state("presets.json")["presets"]


def sensor(app):
    return app.state()["panels"]["cpu:host"]["sensors"]["cpu:host/usage"]


def sensor_menu(app, command):
    press(app, "Options for Overall utilization")
    # Menu items have their own keyboard focus semantics.
    app.click(app.find(command))


def preset_action(app, name, action):
    anchor = app.find("Use " + name)
    app.focus(anchor)
    y = app.bounds(anchor)[1]
    matches = [
        node
        for node in app.walk(app.panel("settings"))
        if node.get_name() == action
        and node.get_role_name() == "button"
        and abs(app.bounds(node)[1] - y) < 2
    ]
    require(len(matches) == 1, "preset action must uniquely belong to " + name)
    app.click(matches[0])


def process_rows(app):
    return {
        node.get_accessible_id(): node
        for node in app.walk(app.panel("processes"), strict=True)
        if (node.get_accessible_id() or "").startswith("process:")
        and ":cell:" not in node.get_accessible_id()
    }


def process_flows(app, children, record):
    rows = app.wait(
        lambda: [
            row
            for row in app.frame()["snapshot"]["processes"]
            if row["identity"]["pid"] in [child.pid for child in children]
        ]
        or None,
        message="owned processes collected",
    )
    require(len(rows) == len(children), "all owned processes must be collected")
    ids = {row["identity"]["pid"]: identity(row) for row in rows}
    record["owned_process_identities"] = ids
    search = "Search name, PID, or user…"
    enter(app, search, "PULSE-AUDIT-")
    app.wait(
        lambda: set(process_rows(app)) == set(ids.values()),
        message="case-insensitive process name projection",
    )
    first, second = children[:2]
    app.click(app.find(aid=ids[first.pid] + ":cell:0"))
    for descending in (False, True):
        press(app, "Sort by PID", role="button", root=app.panel("processes"))

        def sorted_and_selected():
            visible = process_rows(app)
            if set(visible) != set(ids.values()):
                return False
            actual = sorted(ids, key=lambda pid: app.bounds(visible[ids[pid]])[1])
            selected = (
                visible[ids[first.pid]]
                .get_state_set()
                .contains(Atspi.StateType.SELECTED)
            )
            return actual == sorted(ids, reverse=descending) and selected

        app.wait(sorted_and_selected, message="physical PID sort retains selection")
    app.screenshot("process-search-sort.png")
    enter(app, search, str(first.pid))
    app.wait(
        lambda: set(process_rows(app)) == {ids[first.pid]},
        message="exact PID search projection",
    )
    cell = app.find(aid=ids[first.pid] + ":cell:0")
    app.click(cell)
    x, y, width, height = app.bounds(cell)
    xtest.fake_input(app.d, X.MotionNotify, x=int(x + width / 2), y=int(y + height / 2))
    xtest.fake_input(app.d, X.ButtonPress, 3)
    xtest.fake_input(app.d, X.ButtonRelease, 3)
    app.d.sync()
    app.click(app.find("End task…", "menu item"))
    press(app, "Cancel process action")
    spin(0.2)
    require(first.poll() is None, "Cancel signaled the owned process")
    press(app, "End task…", role="button")
    press(app, "Confirm end task")
    app.wait(lambda: first.poll() is not None, message="owned child ended")
    require(first.returncode == -15, "End task did not send SIGTERM")
    enter(app, search, str(second.pid))
    app.wait(
        lambda: set(process_rows(app)) == {ids[second.pid]},
        message="second owned child projected",
    )
    app.click(app.find(aid=ids[second.pid] + ":cell:0"))
    press(app, "Force quit…", role="button")
    press(app, "Confirm force quit")
    app.wait(lambda: second.poll() is not None, message="owned child force quit")
    require(second.returncode == -9, "Force quit did not send SIGKILL")
    require(children[2].poll() is None, "unselected owned process changed")
    own = next(
        row
        for row in app.frame()["snapshot"]["processes"]
        if row["identity"]["pid"] == app.app.pid
    )
    enter(app, search, str(app.app.pid))
    app.wait(
        lambda: set(process_rows(app)) == {identity(own)},
        message="protected application selected by exact identity",
    )
    app.click(app.find(aid=identity(own) + ":cell:0"))
    press(app, "End task…", role="button")
    press(app, "Confirm end task")
    error = app.find(aid="process-action-status")
    app.wait(lambda: error.get_name() == "This process is protected from task actions"
             and app.visible(error), message="visible accessible process error")
    require(app.app.poll() is None, "protected application was signaled")
    app.screenshot("protected-process-error.png")
    enter(app, search, "")
    record["checks"].append(
        "native process name/PID search, PID sort, identity selection, context Cancel, SIGTERM/SIGKILL, protected-process error"
    )


def settings_and_presets(app, record):
    sensor_menu(app, "Line")
    app.wait(
        lambda: sensor(app)["meter"] == "line", 10, "explicit line meter persisted"
    )
    old_order = sensor(app)["order"]
    sensor_menu(app, "Move down")
    app.wait(lambda: sensor(app)["order"] > old_order, 10, "sensor moved by identity")
    sensor_menu(app, "Collapse meter")
    app.wait(lambda: sensor(app)["collapsed"], 10, "meter collapsed")
    sensor_menu(app, "Hide sensor")
    app.wait(lambda: not sensor(app)["visible"], 10, "sensor hidden")
    press(app, "Show Overall utilization")
    app.wait(lambda: sensor(app)["visible"], 10, "sensor restored")
    press(app, "Options for CPU")
    app.click(app.find("Hide monitor"))
    persisted(
        app,
        lambda state: not state["panels"]["cpu:host"]["visible"],
        "CPU hidden by menu",
    )
    app.click(app.find("Show CPU", "button"))
    persisted(app, lambda state: state["panels"]["cpu:host"]["visible"], "CPU restored")
    record["checks"].append(
        "native sensor meter, movement, collapse, hide/show and monitor context visibility"
    )
    press(app, "Settings & presets")
    for name in ("Light", "IBM Plex Sans", "IBM Plex Mono"):
        press(app, name, root=app.panel("settings"))
    expected = {
        "theme": "light",
        "ui_font": "ibm_plex_sans",
        "numeric_font": "ibm_plex_mono",
    }
    persisted(
        app,
        lambda state: state["appearance"] == expected,
        "bundled appearance persisted",
    )
    press(app, "2 s", root=app.panel("settings"))
    persisted(
        app, lambda state: state["interval_ms"] == 2000, "settings interval persisted"
    )
    app.interval_ms = 2000
    name_input = "New preset name or rename target…"
    enter(app, name_input, "safefirst")
    press(app, "Save current workspace")
    app.wait(lambda: "safefirst" in library(app), 10, "first named preset")
    first = copy.deepcopy(library(app)["safefirst"])
    require(
        first["appearance"] == expected and first["interval_ms"] == 2000,
        "preset did not capture settings",
    )
    require(
        first["panels"]["cpu:host"]["sensors"]["cpu:host/usage"] == sensor(app),
        "preset lost sensor controls",
    )
    press(app, "Dark", root=app.panel("settings"))
    persisted(app, lambda state: state["appearance"]["theme"] == "dark", "dark applied")
    enter(app, name_input, "safesecond")
    press(app, "Save current workspace")
    app.wait(lambda: "safesecond" in library(app), 10, "second named preset")
    second = copy.deepcopy(library(app)["safesecond"])
    enter(app, name_input, "saferenamed")
    preset_action(app, "safefirst", "Rename")
    app.wait(
        lambda: "saferenamed" in library(app) and "safefirst" not in library(app),
        10,
        "rename exact preset",
    )
    require(
        library(app)["saferenamed"] == first and library(app)["safesecond"] == second,
        "rename changed another workspace",
    )
    preset_action(app, "saferenamed", "Overwrite…")
    press(app, "Cancel", role="button")
    require(library(app)["saferenamed"] == first, "cancel overwrote preset")
    preset_action(app, "saferenamed", "Overwrite…")
    press(app, "Confirm", role="button")
    app.wait(
        lambda: library(app)["saferenamed"]["appearance"]["theme"] == "dark",
        10,
        "confirmed overwrite",
    )
    require(library(app)["safesecond"] == second, "overwrite changed another preset")
    preset_action(app, "saferenamed", "Delete…")
    press(app, "Cancel", role="button")
    require("saferenamed" in library(app), "cancel deleted preset")
    preset_action(app, "saferenamed", "Delete…")
    press(app, "Confirm", role="button")
    app.wait(lambda: set(library(app)) == {"safesecond"}, 10, "confirmed exact delete")
    press(app, "Use Minimal")
    persisted(
        app,
        lambda state: not state["panels"]["settings"]["visible"],
        "builtin preset applied",
    )
    press(app, "Settings & presets")
    press(app, "Use safesecond")
    persisted(
        app,
        lambda state: state["appearance"] == second["appearance"]
        and state["interval_ms"] == second["interval_ms"]
        and state["panels"]["cpu:host"]["sensors"]
        == second["panels"]["cpu:host"]["sensors"],
        "named preset restored settings and sensors",
    )
    app.interval_ms = second["interval_ms"]
    app.screenshot("settings-presets.png")
    record["checks"].append(
        "native fonts/theme/interval, two presets, rename, overwrite/delete with Cancel, builtin and named recall"
    )
    return copy.deepcopy(library(app))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    record = {"status": "FAIL", "checks": [], "binary_sha256": digest(args.binary)}
    children = []
    app = None
    try:
        for suffix in "abc":
            name = "pulse-audit-" + suffix
            children.append(
                subprocess.Popen(
                    [
                        "/usr/bin/python3",
                        "-c",
                        "import ctypes, time; ctypes.CDLL(None).prctl(15, b"
                        + repr(name)
                        + ", 0, 0, 0); time.sleep(600)",
                    ]
                )
            )
        app = Native(args.binary.resolve(), output / "native", output / "state")
        spin(1)
        app.screenshot("first-launch.png")
        process_flows(app, children, record)
        presets = settings_and_presets(app, record)
        saved = app.save_state()
        app.shutdown()
        app.close()
        app = Native(args.binary.resolve(), output / "restart", output / "state")
        require(
            app.state()["appearance"] == saved["appearance"], "restart lost appearance"
        )
        require(
            app.state()["panels"]["cpu:host"]["sensors"]
            == saved["panels"]["cpu:host"]["sensors"],
            "restart lost sensor state",
        )
        require(library(app) == presets, "restart changed preset library")
        app.find(aid="cpu:host:hero")
        app.screenshot("restart.png")
        app.shutdown()
        app.close()
        record["checks"].append(
            "normal shutdown and restart preserve settings, sensors and named library"
        )
        record["status"] = "PASS"
        print("Native application replay: PASS", flush=True)
    except BaseException as error:
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        if app is not None:
            if not app.closed and app.app is not None and app.app.poll() is None:
                app.screenshot("failure.png")
            app.close()
        for child in children:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
        record["children"] = [
            {"pid": child.pid, "exit_code": child.poll()} for child in children
        ]
        (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
        close_transport(output)


if __name__ == "__main__":
    main()
