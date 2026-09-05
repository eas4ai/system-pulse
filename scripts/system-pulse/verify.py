#!/usr/bin/env python3
"""Aggregate acceptance gate. Missing verification never counts as success."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
lib = (root / "examples/system_pulse/src/lib.rs").read_text()
if "mod fixture;" in lib and "#[cfg(test)]\nmod fixture;" not in lib:
    print("FAIL LIVE-001/LIVE-011: production library includes fixture generation")
    sys.exit(1)
runner = root / "scripts/system-pulse/acceptance.py"
if not runner.is_file():
    print("FAIL: collector, capability, and native acceptance runner has not been implemented")
    sys.exit(1)
sys.exit(subprocess.call(["rtk", "proxy", sys.executable, str(runner)], cwd=root))
