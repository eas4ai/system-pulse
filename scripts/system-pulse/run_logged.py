#!/usr/bin/env python3
"""Keep descendant output in a file instead of inheriting the outer proxy's pipes."""

import argparse
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required")
    # The enclosing Runner owns the original deadline and process group.
    # Session services may outlive the command; they cannot retain proxy pipes.
    with args.log.open("x") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    print(f"Native session output: {args.log}", flush=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
