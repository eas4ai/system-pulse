#!/usr/bin/env python3
"""Exercise the real tray protocol and window lifetime on an owned desktop bus."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import time

from gi.repository import Gio, GLib
from PIL import Image

from application_replay import persisted, press
from host_accuracy import require
from native_driver import X, close_transport, digest, protocol, spin
from tabbed_driver import TabbedNative

WATCHER = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
ITEM = "org.kde.StatusNotifierItem"
ITEM_PATH = "/StatusNotifierItem"
MENU = "com.canonical.dbusmenu"
XML = """<node><interface name="org.kde.StatusNotifierWatcher">
<method name="RegisterStatusNotifierItem"><arg type="s" direction="in"/></method>
<property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
<property name="RegisteredStatusNotifierItems" type="as" access="read"/>
<property name="ProtocolVersion" type="i" access="read"/>
</interface></node>"""


class Host:
    def __init__(self):
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.items = []
        self.host_present = True
        self.registration = self.connection.register_object(
            WATCHER_PATH, Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0],
            self.method, self.property, None,
        )
        result = self.call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                           "org.freedesktop.DBus", "RequestName", "(su)", (WATCHER, 0))
        require(result[0] == 1, "private watcher name already owned")

    def method(self, connection, sender, path, interface, method, parameters, invocation):
        require(method == "RegisterStatusNotifierItem", "unexpected watcher method")
        name = parameters.unpack()[0]
        if name not in self.items:
            self.items.append(name)
        invocation.return_value(None)

    def property(self, connection, sender, path, interface, name):
        return {
            "IsStatusNotifierHostRegistered": GLib.Variant("b", self.host_present),
            "RegisteredStatusNotifierItems": GLib.Variant("as", self.items),
            "ProtocolVersion": GLib.Variant("i", 0),
        }[name]

    def call(self, destination, path, interface, method, signature=None, arguments=()):
        return self.connection.call_sync(
            destination, path, interface, method,
            GLib.Variant(signature, arguments) if signature else None,
            None, Gio.DBusCallFlags.NONE, 1500, None,
        ).unpack()

    def get(self, name, property_name):
        return self.call(name, ITEM_PATH, "org.freedesktop.DBus.Properties", "Get",
                         "(ss)", (ITEM, property_name))[0]

    def close(self):
        self.connection.unregister_object(self.registration)
        self.call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                  "ReleaseName", "(s)", (WATCHER,))


def windows(app):
    return [window for window in app.d.screen().root.query_tree().children
            if window.get_attributes().map_state == X.IsViewable
            and window.get_geometry().width > 100]


def close_window(app):
    window = app.window()
    event = protocol.event.ClientMessage(
        window=window, client_type=app.d.intern_atom("WM_PROTOCOLS"),
        data=(32, [app.d.intern_atom("WM_DELETE_WINDOW"), X.CurrentTime, 0, 0, 0]),
    )
    window.send_event(event)
    app.d.sync()
    app.wait(lambda: not windows(app), message="native window closed to tray")
    require(app.app.poll() is None, "closing the window stopped the app")


def prepare_reopened_window(app):
    # Xvfb has no window manager to place or focus newly created windows.
    # Match Native's initial-window setup before replaying physical input.
    app.window().configure(x=0, y=0)
    app.window().set_input_focus(X.RevertToParent, X.CurrentTime)
    app.d.sync()
    app.cache.clear()


def cpu_history(app):
    label = app.find(aid="history:cpu:host/usage").get_name()
    match = re.search(r"(\d+\.\d+) s history", label)
    require(match is not None, "CPU history span missing")
    return label, float(match[1])


def icon(host, name, path):
    pixmaps = host.get(name, "IconPixmap")
    require(len(pixmaps) == 1, "expected one combined CPU icon")
    width, height, argb = pixmaps[0]
    require((width, height) == (32, 32) and len(argb) == 4096, "invalid tray raster")
    pixels = bytes(argb)
    require(all(alpha == 255 for alpha in pixels[::4]), "graph is not opaque")
    rgba = bytes(channel for i in range(0, len(pixels), 4)
                 for channel in (pixels[i + 1], pixels[i + 2], pixels[i + 3], pixels[i]))
    Image.frombytes("RGBA", (width, height), rgba).save(path)
    return hashlib.sha256(pixels).hexdigest()


def run(binary, output):
    host, app = None, None
    record = {"status": "FAIL", "binary_sha256": digest(binary), "checks": []}
    try:
        host = Host()
        app = TabbedNative(binary, output / "app", output / "state")
        name = app.wait(lambda: next((name for name in host.items
                                     if name.startswith(f"org.kde.StatusNotifierItem-{app.app.pid}-")), None),
                        message="native tray registration")
        app.wait(lambda: app.frame()["snapshot"]["sequence"] >= 5, 10, "CPU history")
        record["first_icon_sha256"] = icon(host, name, output / "cpu-icon.png")

        def matched_tooltip():
            before = app.frame()["snapshot"]
            tooltip = host.get(name, "ToolTip")[3]
            after = app.frame()["snapshot"]
            reading = next(r for r in before["readings"] if r["sensor_id"] == "cpu:host/usage")
            if before["sequence"] == after["sequence"] and reading["availability"] == "Available":
                return tooltip if tooltip == f"System Pulse · CPU {reading['value']:.1f}%" else None
            return None

        record["tooltip"] = app.wait(matched_tooltip, 5, "tray CPU matches aggregate host reading")
        record["initial_history"], initial_span = cpu_history(app)
        app.select_screen("settings")
        press(app, "Light", root=app.panel("settings"))
        persisted(app, lambda state: state["appearance"]["theme"] == "light", "light saved")
        app.select_screen("memory")
        saved = app.save_state()
        sequence = app.frame()["snapshot"]["sequence"]
        close_window(app)
        app.wait(lambda: app.frame()["snapshot"]["sequence"] >= sequence + 4, 10,
                 "single collector continues with no window")
        require(not windows(app), "window returned while the tray host remained available")
        record["background_icon_sha256"] = icon(host, name, output / "cpu-icon-background.png")
        require(record["first_icon_sha256"] != record["background_icon_sha256"],
                "CPU graph did not advance")
        require(app.state()["screens"] == saved["screens"], "closed app lost saved screen")
        host.call(name, ITEM_PATH, ITEM, "Activate", "(ii)", (0, 0))
        app.wait(lambda: len(windows(app)) == 1, message="tray activation reopens dashboard")
        prepare_reopened_window(app)
        app.wait(lambda: app.selected_screen() == "memory", message="reopened active tab")
        require(app.state()["appearance"] == saved["appearance"], "reopen lost appearance")
        app.key("Control_L", "Tab")
        app.wait(lambda: app.selected_screen() == "gpu", message="keyboard works after reopen")
        app.select_screen("summary")
        graph, reopened_span = cpu_history(app)
        require(reopened_span >= initial_span + 3 * app.interval_ms / 1000,
                "reopened CPU history did not retain background samples")
        record["reopened_history"] = graph
        app.screenshot("reopened.png")
        record["checks"].append("aggregate CPU icon, close retains sampling/history/preferences, activation and keyboard reopen")

        close_window(app)
        host.host_present = False
        app.wait(lambda: len(windows(app)) == 1, 6, "missing host restores dashboard")
        prepare_reopened_window(app)
        host.host_present = True
        # The library checks availability every two seconds; allow two checks
        # while continuing to pump native messages before another close.
        spin(4.2)
        close_window(app)
        spin(.4)
        require(not windows(app), "host return did not restore close-to-tray")
        record["checks"].append("host loss restores dashboard; host return restores tray behavior")

        properties = host.call(name, "/Menu", MENU, "GetGroupProperties", "(aias)", ([], []))[0]
        quit_ids = [item_id for item_id, properties in properties if properties.get("label") == "Quit"]
        require(len(quit_ids) == 1, "Quit menu entry missing or ambiguous")
        host.call(name, "/Menu", MENU, "Event", "(isvu)",
                  (quit_ids[0], "clicked", GLib.Variant("i", 0), 0))
        deadline = time.monotonic() + 10
        while app.app.poll() is None and time.monotonic() < deadline:
            spin(.05)
        require(app.app.poll() is not None, "tray Quit did not exit")
        require(app.app.returncode == 0, "tray Quit failed")
        require(app.state()["screens"]["active"] == "summary", "final state was not saved")
        app.close()
        host.close()
        host = None

        app = TabbedNative(binary, output / "no-host", output / "no-host-state")
        app.shutdown()
        app.close()
        record["checks"].append("tray Quit persists and exits; absent host retains ordinary close-to-exit")
        record["status"] = "PASS"
    except BaseException as error:
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        if app is not None:
            app.close()
        if host is not None:
            host.close()
        close_transport(output)
        (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print("CPU tray native replay: PASS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    run(args.binary.resolve(), args.output.resolve())
