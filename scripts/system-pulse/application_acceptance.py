#!/usr/bin/env python3
"""Compose tabbed-screen verification with packaged native product acceptance."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from acceptance import ROOT, Runner, sha256
from host_accuracy import require


from native_session import private_session
from tabbed_acceptance import validate_tabbed


def main():
    requested = os.environ.get("SYSTEM_PULSE_APPLICATION_OUTPUT")
    if requested:
        output = Path(requested).resolve()
        output.mkdir(parents=True, exist_ok=False)
    else:
        output = Path(tempfile.mkdtemp(prefix="system-pulse-application-"))
    require(
        not output.is_relative_to(ROOT), "acceptance output must be outside checkout"
    )
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    runner = Runner(output)
    record = {"status": "FAIL", "source_commit": commit, "steps": runner.steps}
    try:
        # Verify collectors and the current tabbed presentation before packaging.
        runner.step(
            "preservation",
            [
                sys.executable,
                "-B",
                "scripts/system-pulse/verify.py",
                "--output",
                str(output / "preservation"),
            ],
            timeout=2400,
        )
        runner.step(
            "input-focus",
            [
                "cargo",
                "test",
                "--locked",
                "-p",
                "gpui-component",
                "--lib",
                "input::input::tests",
            ],
            "rust",
        )
        runner.step(
            "package",
            [
                sys.executable,
                "-B",
                "scripts/system-pulse/package_linux.py",
                "--output",
                str(output / "package"),
                "--cargo-about",
                os.environ.get("SYSTEM_PULSE_CARGO_ABOUT", "cargo-about"),
            ],
            timeout=1800,
        )
        archives = list((output / "package").glob("*.tar.gz"))
        require(len(archives) == 1, "expected one handover archive")
        archive = archives[0]
        package = archive.with_name(archive.name.removesuffix(".tar.gz"))
        build = json.loads((package / "build.json").read_text())
        binary = package / "system-pulse"
        require(
            build["source_commit"] == commit
            and sha256(binary) == build["binary_sha256"],
            "package does not match acceptance source and binary",
        )
        harness = output / "harness"
        harness.mkdir()
        hashes = {}
        for source in sorted((ROOT / "scripts/system-pulse").glob("*.py")):
            target = harness / source.name
            shutil.copy2(source, target)
            hashes[source.name] = sha256(target)
        (output / "harness-manifest.json").write_text(
            json.dumps(hashes, indent=2) + "\n"
        )
        runner.step(
            "application",
            private_session(
                harness / "tabbed_replay.py",
                "--binary",
                binary,
                "--output",
                output / "application",
                log=output / "application.session.log",
            ),
            timeout=900,
        )
        product = json.loads((output / "application/result.json").read_text())
        require(
            product["status"] == "PASS"
            and product["binary_sha256"] == build["binary_sha256"],
            "native product replay did not pass against packaged binary",
        )
        validate_tabbed(runner, binary, output / "application")
        runner.step(
            "tray",
            private_session(
                harness / "tray_replay.py",
                "--binary",
                binary,
                "--output",
                output / "tray",
                log=output / "tray.session.log",
            ),
            timeout=120,
        )
        tray = json.loads((output / "tray/result.json").read_text())
        require(
            tray["status"] == "PASS"
            and tray["binary_sha256"] == build["binary_sha256"],
            "native tray replay did not pass against packaged binary",
        )
        runner.step(
            "installed",
            private_session(
                harness / "package_smoke.py",
                "--archive",
                archive,
                "--output",
                output / "installed",
                log=output / "installed.session.log",
            ),
            timeout=240,
        )
        installed = json.loads((output / "installed/result.json").read_text())
        require(
            installed["status"] == "PASS"
            and installed["source_commit"] == commit
            and installed["binary_sha256"] == build["binary_sha256"],
            "installed smoke did not pass against committed package",
        )
        record.update(
            status="PASS",
            archive=runner.artifact(archive),
            binary_sha256=build["binary_sha256"],
            preservation_manifest=runner.artifact(
                output / "preservation/manifest.json"
            ),
            product=runner.artifact(output / "application/result.json"),
            tray=runner.artifact(output / "tray/result.json"),
            installed=runner.artifact(output / "installed/result.json"),
        )
    except BaseException as error:
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        (output / "application-manifest.json").write_text(
            json.dumps(record, indent=2) + "\n"
        )
    for number in range(1, 9):
        print(f"cairn: APP-{number:03}: pass", flush=True)
    print(f"Application acceptance: PASS; evidence={output}", flush=True)


if __name__ == "__main__":
    main()
