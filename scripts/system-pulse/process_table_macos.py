"""Native Mac process-table resize observations for an owned application."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

from performance_compare import require
from performance_macos import command, digest
from performance_preserve import wait_for
from process_table_verify import HARNESSES, aligned


def geometry(tree):
    rows = tree["rows"]
    headings = [row["bounds"] for row in rows if row.get("AXRole") == "AXCell"
                and row.get("AXTitle", "").startswith("Sort by ")]
    require(len(headings) == 7, "expected seven Mac process column headings")
    require(not any(row.get("AXIdentifier", "").endswith(":cell:6") for row in rows),
            "Mac table exposed a Threads cell")
    viewport = next(row["bounds"] for row in rows
                    if row.get("AXIdentifier") == "processes:viewport")
    process = next(row for row in rows
                   if re.fullmatch(r"process:\d+:\d+", row.get("AXIdentifier", ""))
                   and row["bounds"][1] >= viewport[1]
                   and row["bounds"][1] + row["bounds"][3] <= viewport[1] + viewport[3])
    identity = process["AXIdentifier"]
    cells = [next(row["bounds"] for row in rows
                  if row.get("AXIdentifier") == f"{identity}:cell:{column}")
             for column in (0, 1, 2, 3, 4, 5, 7)]
    window = next(row["bounds"] for row in rows if row.get("AXRole") == "AXWindow")
    frame = {"window_width": window[2], "viewport": viewport,
             "headings": headings, "cells": cells, "identity": identity,
             "heading_titles": [row["AXTitle"] for row in rows if row.get("AXRole") == "AXCell"
                                and row.get("AXTitle", "").startswith("Sort by ")],
             "cell_columns": sorted(int(row["AXIdentifier"].rsplit(":", 1)[1])
                                    for row in rows if row.get("AXIdentifier", "").startswith(identity + ":cell:")),
             "search": next(row["bounds"] for row in rows
                            if row.get("AXRole") == "AXTextField"),
             "actions": [next(row["bounds"] for row in rows
                              if row.get("AXRole") == "AXButton" and row.get("AXTitle") == title)
                         for title in ("End task…", "Force quit…")]}
    aligned(frame, 7)
    return frame


def ordinary_actions(tree, save):
    results = []
    for label, button, confirm, expected in (
            ("end", "End task…", "Confirm end task", -15),
            ("force", "Force quit…", "Confirm force quit", -9)):
        child = subprocess.Popen(["/bin/sleep", "60"])
        try:
            tree("search", str(child.pid))
            def owned_row():
                return next((row["AXIdentifier"] for row in tree()["rows"]
                             if re.fullmatch(r"process:" + str(child.pid) + r":\d+",
                                             row.get("AXIdentifier", ""))), None)
            identity = wait_for(owned_row, "owned action process")
            tree("focus-id", "processes:viewport")
            tree("key", "home")
            wait_for(lambda: any(row.get("AXIdentifier") == "process-details" and
                                 row.get("AXTitle", "").endswith(f", PID {child.pid}")
                                 for row in tree()["rows"]), "owned process selection")
            tree("press-title", button)
            save(label + "-confirmation.json", tree())
            tree("press-title", "Cancel process action")
            require(child.poll() is None, "cancelled confirmation changed process")
            tree("press-title", button)
            tree("press-title", confirm)
            require(child.wait(timeout=10) == expected, "wrong native process signal")
            def sent():
                return next((row.get("AXTitle", "") for row in tree()["rows"]
                             if row.get("AXIdentifier") == "process-action-status" and
                             row.get("AXTitle", "").startswith("Request sent to ")), None)
            notice = wait_for(sent, "successful native process action")
            save(label + "-result.json", tree())
            results.append({"identity": identity, "action": label,
                            "confirmation_cancelled_alive": True,
                            "child_exit": child.returncode, "notice": notice})
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
    tree("search", "")
    return results


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"status": "FAIL", "source_commit": args.commit,
              "binary_sha256": digest(args.binary), "platform": "macos", "frames": []}
    result["harness_sha256"] = {name: digest(Path(__file__).with_name(name))
                                for name in HARNESSES["macos"]}
    process = None
    awake = subprocess.Popen(["caffeinate", "-d", "-i", "-u", "-t", "600"])

    def tree(action="snapshot", *values):
        return json.loads(command([str(args.tree), str(process.pid), action, *map(str, values)]))

    def save(name, value):
        (args.output / name).write_text(json.dumps(value, indent=2) + "\n")

    try:
        state = args.output / "state"
        state.mkdir()
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("SYSTEM_PULSE_")}
        environment["SYSTEM_PULSE_STATE_DIR"] = str(state.resolve())
        with (args.output / "application.log").open("w") as log:
            process = subprocess.Popen([str(args.binary.resolve())], env=environment,
                                       stdout=log, stderr=subprocess.STDOUT)
            wait_for(lambda: any(row.get("AXIdentifier") == "screen-tab:processes"
                                 for row in tree()["rows"]), "process screen tab")
            tree("activate")
            tree("press-id", "screen-tab:processes")
            wait_for(lambda: any(row.get("AXIdentifier") == "processes:viewport"
                                 for row in tree()["rows"]), "process table")
            for width in (1280, 1440, 960, 1280):
                tree("resize", width, 640 if width == 960 else 880)
                time.sleep(0.5)
                snapshot = tree()
                save(f"resize-{width}-{len(result['frames'])}.json", snapshot)
                frame = geometry(snapshot)
                require(abs(frame["window_width"] - width) <= 1, "native resize did not reach requested width")
                if width >= 1280:
                    last, viewport = frame["headings"][-1], frame["viewport"]
                    require(abs(last[0] + last[2] - (viewport[0] + viewport[2] - 1)) <= 1,
                            "table did not fill the window")
                result["frames"].append(frame)
                if width == 960:
                    tree("focus-id", "processes:viewport")
                    for _ in range(6):
                        tree("key", "right")
                        time.sleep(0.1)
                    snapshot = tree()
                    save("minimum-scrolled.json", snapshot)
                    scrolled = geometry(snapshot)
                    last, viewport = scrolled["headings"][-1], scrolled["viewport"]
                    require(last[0] >= viewport[0] and last[0] + last[2] <= viewport[0] + viewport[2],
                            "last column is inaccessible at minimum width")
                    result["narrow_scrolled"] = scrolled
                    for _ in range(6):
                        tree("key", "left")
                        time.sleep(0.1)
            require(result["frames"][1]["headings"][1][2] > result["frames"][0]["headings"][1][2],
                    "Name column did not grow")
            tree("resize", 960, 640)
            tree("search", str(process.pid))
            def process_ids():
                return [row["AXIdentifier"] for row in tree()["rows"]
                        if re.fullmatch(r"process:\d+:\d+", row.get("AXIdentifier", ""))]
            filtered = wait_for(lambda: ids if len(ids := process_ids()) == 1 else None,
                                "PID-filtered process row")
            require(filtered[0].split(":")[1] == str(process.pid), "PID search selected a different process")
            save("search-filtered.json", tree())
            result["search_filter"] = {"pid": process.pid, "identities": filtered}
            tree("search", "")
            cleared = wait_for(lambda: ids if len(ids := process_ids()) > 1 else None,
                               "cleared process search")
            save("search-cleared.json", tree())
            result["search_clear_rows"] = len(cleared)
            tree("resize", 1280, 880)
            tree("press-title", "Sort by User")
            def sorted_users():
                rows = [row for row in tree()["rows"]
                        if re.fullmatch(r"process:\d+:\d+:cell:7", row.get("AXIdentifier", ""))]
                users = [row["AXTitle"].lower() for row in sorted(rows, key=lambda row: row["bounds"][1])]
                return users if users and users == sorted(users) else None
            wait_for(sorted_users, "native User sort")
            result["user_sort"] = "ascending"
            result["navigation"] = {}
            tree("focus-id", "processes:viewport")
            for key in ("home", "end"):
                tree("key", key)
                def selected():
                    rows = tree()["rows"]
                    details = next(row for row in rows if row.get("AXIdentifier") == "process-details")
                    match = re.search(r", PID (\d+)$", details.get("AXTitle", ""))
                    if match is None:
                        return None
                    viewport = next(row["bounds"] for row in rows
                                    if row.get("AXIdentifier") == "processes:viewport")
                    # The Mac bridge omits AXSelected for rows. The native details
                    # panel identifies the selection; require its actual row visible.
                    ids = [row["AXIdentifier"] for row in rows
                           if re.fullmatch(r"process:" + match[1] + r":\d+", row.get("AXIdentifier", ""))
                           and row["bounds"][1] >= viewport[1]
                           and row["bounds"][1] + row["bounds"][3] <= viewport[1] + viewport[3] + 1]
                    return ids[0] if len(ids) == 1 and ids[0] != result["navigation"].get("home") else None
                result["navigation"][key] = wait_for(selected, "native " + key)
                save("navigation-" + key + ".json", tree())
            result["ordinary_actions"] = ordinary_actions(tree, save)
            tree("press-title", "Quit")
            process.wait(timeout=10)
            require(process.returncode == 0, "native Quit failed")
            result["status"] = "PASS"
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        if process is not None and process.poll() is None:
            save("failure-tree.json", tree())
        raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        awake.terminate()
        awake.wait(timeout=5)
        save("result.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "tree", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--commit", required=True)
    run(parser.parse_args())
