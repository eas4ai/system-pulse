#!/usr/bin/env python3
"""The mandatory live acceptance aggregate; fixture source guarding is one step."""

from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
runner = root / "scripts/system-pulse/acceptance.py"
if not runner.is_file():
    raise SystemExit("FAIL: mandatory acceptance runner missing")
raise SystemExit(
    subprocess.call(
        ["rtk", "proxy", sys.executable, "-B", str(runner), *sys.argv[1:]], cwd=root
    )
)
