"""Private native session command with bounded log transport."""

import sys
from acceptance import ROOT


def private_session(script, *arguments, log):
    return [
        sys.executable,
        "-B",
        str(ROOT / "scripts/system-pulse/run_logged.py"),
        "--log",
        str(log),
        "--",
        "xvfb-run",
        "-a",
        "-s",
        "-screen 0 1440x1000x24 -nolisten tcp",
        "dbus-run-session",
        "--",
        "env",
        "WAYLAND_DISPLAY=",
        "VK_DRIVER_FILES=/usr/share/vulkan/icd.d/lvp_icd.json",
        "PYTHONDONTWRITEBYTECODE=1",
        "/usr/bin/python3",
        "-B",
        str(script),
        *map(str, arguments),
    ]

