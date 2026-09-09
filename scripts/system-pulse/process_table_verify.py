"""Cairn process-table gate: validate committed tests and native geometry."""

import json
import re
import subprocess
import sys

from performance_compare import require
from performance_verify import ROOT, check_harness, same_production

from process_table_harnesses import HARNESSES


def aligned(frame, column_count=8):
    headings, cells = frame["headings"], frame["cells"]
    require(len(headings) == len(cells) == column_count, "missing native columns")
    for heading, cell in zip(headings, cells):
        require(len(heading) == len(cell) == 4 and heading[2] > 0 and cell[2] > 0,
                "invalid native bounds")
        require(abs(heading[0] - cell[0]) <= 1 and abs(heading[2] - cell[2]) <= 1,
                "native headers and rows disagree")


def validate_geometry(record, platform):
    require(record["status"] == "PASS" and record["platform"] == platform,
            "native geometry did not pass on the required platform")
    frames = record["frames"]
    widths = [1280, 1800 if platform == "linux" else 1440, 960, 1280]
    require(len(frames) == len(widths), "missing native resize observations")
    for frame, width in zip(frames, widths):
        aligned(frame, 7 if platform == "macos" else 8)
        require(abs(frame["window_width"] - width) <= 1, "wrong native window width")
        last, viewport = frame["headings"][-1], frame["viewport"]
        if width >= 1280:
            require(abs(last[0] + last[2] - (viewport[0] + viewport[2] - 1)) <= 1,
                    "native table leaves unused width")
    require(frames[1]["headings"][1][2] > frames[0]["headings"][1][2], "Name did not expand")
    require(abs(frames[0]["headings"][1][2] - frames[3]["headings"][1][2]) <= 1,
            "Name did not shrink after resizing back")
    scrolled = record["narrow_scrolled"]
    aligned(scrolled, 7 if platform == "macos" else 8)
    require(scrolled["window_width"] == 960, "scroll observation is not at minimum width")
    last, viewport = scrolled["headings"][-1], scrolled["viewport"]
    require(last[0] >= viewport[0] and last[0] + last[2] <= viewport[0] + viewport[2],
            "last column is inaccessible at minimum width")
    require(scrolled["headings"][0][0] < frames[2]["headings"][0][0],
            "horizontal scrolling did not move the columns")


def validate_search(record):
    for frame in record["frames"]:
        search, viewport = frame["search"], frame["viewport"]
        require(abs(search[2] - 280) <= 1, "search expands with the window")
        require(len(frame["actions"]) == 2, "missing process toolbar actions")
        for control in [search, *frame["actions"]]:
            require(control[0] >= viewport[0] and
                    control[0] + control[2] <= viewport[0] + viewport[2],
                    "process toolbar clips")
    filtered = record["search_filter"]
    require(len(filtered["identities"]) == 1 and
            filtered["identities"][0].split(":")[1] == str(filtered["pid"]),
            "PID filter did not show the owned process")
    require(record["search_clear_rows"] > 1, "clearing search did not restore rows")


def validate_columns(record, platform):
    titles = ["PID", "Name", "CPU (one core)", "Memory", "Read I/O", "Write I/O"]
    columns = [0, 1, 2, 3, 4, 5]
    if platform == "linux":
        titles.append("Threads")
        columns.append(6)
    titles.append("User")
    columns.append(7)
    for frame in record["frames"]:
        require(frame["heading_titles"] == ["Sort by " + title for title in titles],
                "native process headers disagree with the platform")
        require(frame["cell_columns"] == columns, "native process cells disagree with the platform")
    require(record["user_sort"] == "ascending", "native User sort was not verified")
    navigation = record["navigation"]
    require(set(navigation) == {"home", "end"} and
            all(re.fullmatch(r"process:\d+:\d+", identity) for identity in navigation.values()) and
            navigation["home"] != navigation["end"],
            "native keyboard selection is incomplete")


def main():
    subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s",
                    "scripts/system-pulse", "-p", "test_process_table_geometry.py"], cwd=ROOT, check=True)
    subprocess.run(["cargo", "test", "--locked", "-p", "system-pulse"], cwd=ROOT, check=True)
    evidence = ROOT / "docs/execution/process-table-improvements/evidence"
    for platform in ("linux", "macos"):
        record = json.loads((evidence / platform / "result.json").read_text())
        validate_geometry(record, platform)
        validate_search(record)
        validate_columns(record, platform)
        same_production(record["source_commit"])
        build = json.loads((evidence / platform / "build.json").read_text())
        require(build["source_commit"] == record["source_commit"] and
                build["binary_sha256"] == record["binary_sha256"] and build["exit_code"] == 0,
                "native observation does not match its build")
        check_harness(record["harness_sha256"], HARNESSES[platform])
    print("cairn: PROC-001: pass", flush=True)
    print("cairn: PROC-002: pass", flush=True)
    print("cairn: PROC-003: pass", flush=True)
    # Other requirements remain unverified until their own checks are implemented.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
