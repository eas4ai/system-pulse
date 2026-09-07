#!/usr/bin/env python3
"""Exercise an installed archive inside the replay's private X11/DBus session."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

from native_driver import close_transport, digest, spin
from tabbed_driver import TabbedNative as Native
from host_accuracy import require


def run(command, output, name):
    with (output / name).open("x") as log:
        subprocess.run(
            command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    app = None
    try:
        extracted = output / "extracted"
        extracted.mkdir()
        with tarfile.open(args.archive) as archive:
            archive.extractall(extracted, filter="data")
        packages = list(extracted.iterdir())
        require(
            len(packages) == 1 and packages[0].is_dir(), "one package root required"
        )
        package = packages[0]
        build = json.loads((package / "build.json").read_text())
        require(
            digest(package / "system-pulse") == build["binary_sha256"],
            "package binary changed",
        )
        prefix = output / "prefix with spaces"
        sentinel = prefix / ".config/system-pulse/keep.json"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("original saved input")
        install = [sys.executable, str(package / "install.py"), "--prefix", str(prefix)]
        run(install, output, "install.log")
        run(install, output, "repeat-install.log")
        desktop = prefix / "share/applications/org.systempulse.SystemPulse.desktop"
        run(["desktop-file-validate", str(desktop)], output, "desktop-validation.log")
        import gi

        gi.require_version("GioUnix", "2.0")
        from gi.repository import GioUnix, GLib

        launcher = GioUnix.DesktopAppInfo.new_from_filename(str(desktop))
        require(launcher is not None, "desktop launcher could not be parsed")
        binary = prefix / "lib/system-pulse/system-pulse"
        parsed, arguments = GLib.shell_parse_argv(launcher.get_commandline())
        require(
            parsed and arguments == [str(binary)],
            "desktop Exec did not preserve the installation path",
        )
        require(
            (prefix / "bin/system-pulse").resolve() == binary,
            "installed launcher target differs",
        )
        # Remove the extracted package and launch from an empty, unrelated directory.
        shutil.rmtree(extracted)
        working = output / "empty-working-directory"
        working.mkdir()
        state = output / "state"
        app = Native(binary, output / "native", state, working_directory=working)
        spin(2)
        app.find(aid="summary-cpu")
        app.find(aid="summary-memory")
        app.screenshot("installed-first-launch.png")
        app.resize(960, 640)
        spin(0.5)
        app.screenshot("installed-minimum.png")
        app.resize(1280, 880)
        app.select_screen("settings")
        spin(0.5)
        app.click(app.find("Light"))
        app.wait(
            lambda: app.state()["appearance"]["theme"] == "light",
            seconds=10,
            message="light appearance persisted",
        )
        saved = app.save_state()
        require(
            saved["appearance"]["theme"] == "light", "installed appearance did not save"
        )
        app.screenshot("installed-settings-light.png")
        app.shutdown()
        app.close()
        app = Native(binary, output / "restart", state, working_directory=working)
        require(
            app.state()["appearance"]["theme"] == "light", "restart lost appearance"
        )
        require(app.selected_screen() == "settings", "restart lost active tab")
        app.screenshot("restarted-light.png")
        app.shutdown()
        app.close()
        configuration = {
            str(path.relative_to(state)): digest(path)
            for path in state.rglob("*")
            if path.is_file()
        }
        note = prefix / "lib/system-pulse/user-note.txt"
        note.write_text("unowned file")
        run(
            [
                sys.executable,
                str(prefix / "lib/system-pulse/install.py"),
                "--prefix",
                str(prefix),
                "--uninstall",
            ],
            output,
            "uninstall.log",
        )
        require(
            not (prefix / "bin/system-pulse").is_symlink() and not binary.exists(),
            "installed binary was not removed",
        )
        require(
            sentinel.read_text() == "original saved input"
            and note.read_text() == "unowned file",
            "removal changed user files",
        )
        after = {
            str(path.relative_to(state)): digest(path)
            for path in state.rglob("*")
            if path.is_file()
        }
        require(configuration == after, "removal changed actual saved configuration")
        (output / "result.json").write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "archive_sha256": digest(args.archive),
                    "source_commit": build["source_commit"],
                    "binary_sha256": build["binary_sha256"],
                    "configuration": configuration,
                    "installed_launch_cwd": str(working),
                    "checks": [
                        "archive extraction",
                        "install and repeat",
                        "desktop launcher parsing",
                        "isolated installed launch",
                        "minimum window",
                        "bundled fonts and light theme",
                        "restart",
                        "normal shutdown",
                        "removal preserves configuration and unowned files",
                    ],
                },
                indent=2,
            )
            + "\n"
        )
        print("Installed package smoke: PASS", flush=True)
    finally:
        try:
            if app is not None:
                try:
                    if app.app is not None and app.app.poll() is None:
                        app.screenshot("failure.png")
                except Exception as error:
                    print(f"Failure screenshot unavailable: {error}", file=sys.stderr)
                finally:
                    app.close()
        finally:
            close_transport(output)


if __name__ == "__main__":
    main()
