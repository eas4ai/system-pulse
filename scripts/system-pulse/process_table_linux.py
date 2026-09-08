"""Observe process-table geometry through native Linux accessibility."""

import argparse
import json
from pathlib import Path
import re

from host_accuracy import require
from native_driver import Atspi, close_transport, digest, spin
from tabbed_driver import TabbedNative
from process_table_verify import HARNESSES, aligned
from application_replay import enter, press, process_rows


def geometry(app):
    nodes = list(app.walk(app.panel("processes"), strict=True))
    headings = [node for node in nodes if node.get_name().startswith("Sort by ")
                and node.get_role_name() == "table cell"]
    require(len(headings) == 8, "expected eight Linux column headers: " + repr([
        (node.get_name(), node.get_role_name()) for node in nodes
        if node.get_name().startswith("Sort by ")]))
    rows = [node for node in nodes
            if re.fullmatch(r"process:\d+:\d+", node.get_accessible_id() or "")]
    require(rows, "no native process rows")
    viewport = app.bounds(app.find(aid="processes:viewport"))
    row = next((node for node in rows
                if viewport[1] <= app.bounds(node)[1]
                and app.bounds(node)[1] + app.bounds(node)[3] <= viewport[1] + viewport[3]), None)
    require(row is not None, "no visible native process row")
    identity = row.get_accessible_id()
    cells = [app.bounds(app.find(aid=f"{identity}:cell:{column}", root=row))
             for column in range(8)]
    return {"window_width": app.window().get_geometry().width,
            "viewport": viewport,
            "headings": [app.bounds(node) for node in headings],
            "heading_titles": [node.get_name() for node in headings],
            "cell_columns": sorted(int(node.get_accessible_id().rsplit(":", 1)[1])
                                   for node in nodes
                                   if (node.get_accessible_id() or "").startswith(identity + ":cell:")),
            "cells": cells, "identity": identity,
            "search": app.bounds(app.find("Search name, PID, or user…")),
            "actions": [app.bounds(app.find(title, "button"))
                        for title in ("End task…", "Force quit…")]}


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {"status": "FAIL", "source_commit": args.commit,
              "binary_sha256": digest(args.binary), "platform": "linux", "frames": []}
    result["harness_sha256"] = {name: digest(Path(__file__).with_name(name))
                                for name in HARNESSES["linux"]}
    app = None
    try:
        app = TabbedNative(args.binary.resolve(), output / "native", output / "state")
        app.select_screen("processes")
        for width in (1280, 1800, 960, 1280):
            app.resize(width, 640 if width == 960 else 880)
            spin(0.5)
            frame = app.wait(lambda: geometry(app), 15, "stable table geometry")
            aligned(frame)
            if width >= 1280:
                last, viewport = frame["headings"][-1], frame["viewport"]
                require(abs(last[0] + last[2] - (viewport[0] + viewport[2] - 1)) <= 1,
                        "table did not fill the window")
            result["frames"].append(frame)
            app.screenshot(f"resize-{width}-{len(result['frames'])}.png")
            if width == 960:
                app.focus(app.find(aid="processes:viewport"))
                for _ in range(6):
                    app.key("Right")
                    spin(0.1)
                scrolled = app.wait(lambda: geometry(app), 15, "scrolled table geometry")
                aligned(scrolled)
                last, viewport = scrolled["headings"][-1], scrolled["viewport"]
                require(last[0] >= viewport[0] and
                        last[0] + last[2] <= viewport[0] + viewport[2],
                        "last column is inaccessible at minimum width")
                result["narrow_scrolled"] = scrolled
                for _ in range(6):
                    app.key("Left")
                    spin(0.1)
        app.resize(960, 640)
        enter(app, "Search name, PID, or user…", str(app.app.pid))
        filtered = app.wait(lambda: process_rows(app), message="filtered process rows")
        require(len(filtered) == 1 and next(iter(filtered)).split(":")[1] == str(app.app.pid),
                "PID search did not show the owned application")
        result["search_filter"] = {"pid": app.app.pid, "identities": list(filtered)}
        enter(app, "Search name, PID, or user…", "")
        cleared = app.wait(lambda: rows if len(rows := process_rows(app)) > 1 else None,
                           message="cleared process search")
        result["search_clear_rows"] = len(cleared)
        app.resize(1280, 880)
        spin(0.3)
        press(app, "Sort by User", role="button", root=app.panel("processes"))
        spin(0.3)
        def sorted_users():
            rows = process_rows(app)
            users = [app.find(aid=identity + ":cell:7", root=node).get_name().lower()
                     for identity, node in sorted(rows.items(), key=lambda item: app.bounds(item[1])[1])]
            return users if users and users == sorted(users) else None
        app.wait(sorted_users, 15, "native User sort")
        result["user_sort"] = "ascending"
        result["navigation"] = {}
        app.focus(app.find(aid="processes:viewport"))
        for key in ("Home", "End"):
            app.key(key)
            def selected():
                rows = process_rows(app)
                selected = [identity for identity, node in rows.items()
                            if node.get_state_set().contains(Atspi.StateType.SELECTED)]
                return selected[0] if len(selected) == 1 and selected[0] != result["navigation"].get("home") else None
            result["navigation"][key.lower()] = app.wait(selected, 15, "native " + key)
        require(result["frames"][1]["headings"][1][2] > result["frames"][0]["headings"][1][2],
                "Name column did not grow")
        app.shutdown()
        result["status"] = "PASS"
    finally:
        if app is not None:
            app.close()
        close_transport(output)
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    run(parser.parse_args())
