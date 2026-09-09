"""Interactive OS authentication checks using bounded, test-owned root sleeps.

Run only with the developer present to respond to system dialogs. On Linux,
use the existing private X11 replay wrapper; the desktop's polkit agent owns
authentication. Never collect a screenshot or tree of a password dialog.
"""

import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import re
import struct
import subprocess

from performance_compare import require
from performance_macos import digest
from performance_preserve import wait_for


def process_identity(pid):
    """Read identity independently of the application collector."""
    if platform.system() == "Linux":
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            fields = stat[stat.rfind(")") + 1:].split()
            if fields[0] == "Z":
                return None
            uid = Path(f"/proc/{pid}").stat().st_uid
            return {"pid": pid, "start_time_ticks": int(fields[19]), "uid": uid}
        except (FileNotFoundError, ProcessLookupError):
            return None
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    library.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                    ctypes.c_void_p, ctypes.c_int]
    library.proc_pidinfo.restype = ctypes.c_int
    # proc_bsdinfo's public ABI: pid at 12, uid at 20, birth timeval at 120.
    data = ctypes.create_string_buffer(136)
    count = library.proc_pidinfo(pid, 3, 0, data, len(data))
    if count <= 0 and ctypes.get_errno() in (2, 3):
        return None
    require(count == len(data), "cannot read the complete native fixture identity")
    require(struct.unpack_from("=I", data, 12)[0] == pid, "native fixture PID differs")
    if struct.unpack_from("=I", data, 4)[0] == 5:  # SZOMB
        return None
    seconds, micros = struct.unpack_from("=QQ", data, 120)
    require(micros < 1_000_000, "invalid native birth time")
    return {"pid": pid, "start_time_ticks": seconds * 1_000_000 + micros,
            "uid": struct.unpack_from("=I", data, 20)[0]}


def fixture_command(duration):
    require(type(duration) is int and duration in (20, 180), "fixture lifetime is not bounded")
    body = f"/bin/sleep {duration} </dev/null >/dev/null 2>&1 & /usr/bin/printf '%s' \"$!\""
    if platform.system() == "Linux":
        return ["/usr/bin/pkexec", "--disable-internal-agent", "/bin/sh", "-c", body]
    return ["/usr/bin/osascript", "-e",
            "on run argv\nreturn do shell script (item 1 of argv) with administrator privileges\nend run",
            "--", body]


def create_fixture(duration):
    print(f"AUTH SETUP: authenticate the OS dialog to create one {duration}-second root sleep.", flush=True)
    result = subprocess.run(fixture_command(duration), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    text = result.stdout.decode("ascii").strip()
    require(text.isdecimal(), "fixture setup did not return one PID")
    identity = process_identity(int(text))
    require(identity is not None and identity["uid"] == 0 and identity["pid"] > 1,
            "fixture is not a live root process")
    return identity


def alive(identity):
    return process_identity(identity["pid"]) == identity


class MacUI:
    def __init__(self, args):
        self.args = args
        self.log = (args.output / "application.log").open("w")
        state = args.output / "state"
        state.mkdir()
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("SYSTEM_PULSE_")}
        environment["SYSTEM_PULSE_STATE_DIR"] = str(state)
        self.app = subprocess.Popen([str(args.binary)], env=environment,
                                    stdout=self.log, stderr=self.log)
        try:
            wait_for(lambda: any(row.get("AXIdentifier") == "screen-tab:processes"
                                 for row in self.tree()["rows"]), "process tab")
            self.tree("activate")
            self.tree("press-id", "screen-tab:processes")
        except BaseException:
            self.close()
            raise

    def tree(self, action="snapshot", *values):
        result = subprocess.run([str(self.args.tree), str(self.app.pid), action, *map(str, values)],
                                capture_output=True, text=True, timeout=15, check=True)
        return json.loads(result.stdout)

    def select(self, identity):
        expected = f"process:{identity['pid']}:{identity['start_time_ticks']}"
        self.selected = identity
        self.tree("search", identity["pid"])
        wait_for(lambda: self.process_ids() == [expected], "only the exact root fixture identity")
        self.tree("focus-id", "processes:viewport")
        self.tree("key", "home")
        wait_for(lambda: any(row.get("AXIdentifier") == "process-details" and
                             row.get("AXTitle", "").endswith(f", PID {identity['pid']}")
                             for row in self.tree()["rows"]), "root fixture selection")

    def process_ids(self):
        return [row["AXIdentifier"] for row in self.tree()["rows"]
                if re.fullmatch(r"process:\d+:\d+", row.get("AXIdentifier", ""))]

    def confirm(self, action):
        identity = self.selected
        require(alive(identity) and self.process_ids() == [f"process:{identity['pid']}:{identity['start_time_ticks']}"],
                "the original root fixture is no longer the only action target")
        self.tree("press-title", "End task…" if action == "terminate" else "Force quit…")
        self.tree("press-title", "Confirm end task" if action == "terminate" else "Confirm force quit")

    def notice(self):
        return next((row.get("AXTitle", "") for row in self.tree()["rows"]
                     if row.get("AXIdentifier") == "process-action-status"), "")

    def close(self):
        if self.app.poll() is None:
            self.app.terminate()
            self.app.wait(timeout=10)
        self.log.close()


class LinuxUI:
    def __init__(self, args):
        from tabbed_driver import TabbedNative
        self.args = args
        self.native = TabbedNative(args.binary, args.output / "native", args.output / "state")
        self.app = self.native.app
        try:
            self.native.select_screen("processes")
        except BaseException:
            self.close()
            raise

    def select(self, identity):
        from application_replay import enter, process_rows
        expected = f"process:{identity['pid']}:{identity['start_time_ticks']}"
        self.selected = identity
        enter(self.native, "Search name, PID, or user…", str(identity["pid"]))
        self.native.wait(lambda: set(process_rows(self.native)) == {expected},
                         message="only the exact root fixture identity")
        node = self.native.find(aid=expected + ":cell:0")
        self.native.click(node)

    def confirm(self, action):
        from application_replay import press, process_rows
        from native_driver import Atspi
        identity = self.selected
        expected = f"process:{identity['pid']}:{identity['start_time_ticks']}"
        rows = process_rows(self.native)
        require(alive(identity) and set(rows) == {expected} and
                rows[expected].get_state_set().contains(Atspi.StateType.SELECTED),
                "the original root fixture is no longer the only selected action target")
        press(self.native, "End task…" if action == "terminate" else "Force quit…", role="button")
        press(self.native, "Confirm end task" if action == "terminate" else "Confirm force quit", role="button")

    def notice(self):
        return self.native.find(aid="process-action-status").get_name()

    def close(self):
        from native_driver import close_transport
        self.native.close()
        close_transport(self.args.output)


def run(args):
    require(os.getuid() == os.geteuid() != 0, "run the UI and verifier as the normal desktop user")
    require(platform.system() in ("Darwin", "Linux"), "unsupported native authentication host")
    args.binary = args.binary.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    from process_table_verify import HARNESSES
    host = "macos" if platform.system() == "Darwin" else "linux"
    harnesses = {*HARNESSES[host], Path(__file__).name, "performance_macos.py",
                 "performance_preserve.py", "performance_compare.py", "process_table_verify.py"}
    record = {"status": "FAIL", "platform": host,
              "source_commit": args.commit, "binary_sha256": digest(args.binary),
              "harness_sha256": {name: digest(Path(__file__).with_name(name)) for name in sorted(harnesses)},
              "cases": []}
    ui = None
    fixtures = []
    try:
        ui = MacUI(args) if platform.system() == "Darwin" else LinuxUI(args)
        require(process_identity(ui.app.pid)["uid"] == os.getuid(), "the UI is privileged")
        record["ui_pid"] = ui.app.pid
        record["ui_uid"] = os.getuid()
        for action, expired in (("terminate", False), ("kill", False), ("terminate", True)):
            identity = create_fixture(20 if expired else 180)
            fixtures.append(identity)
            ordinary = subprocess.run([str(args.binary), "--system-pulse-process-action",
                                       str(identity["pid"]), str(identity["start_time_ticks"]), action],
                                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, timeout=10)
            require(ordinary.returncode == 11 and alive(identity), "ordinary action was not denied safely")
            ui.select(identity)
            if action == "terminate" and not expired:
                print("AUTH CANCEL: cancel the next SYSTEM authentication dialog.", flush=True)
                ui.confirm(action)
                notice = wait_for(lambda: value if (value := ui.notice()).startswith("Authentication was cancelled.")
                                  else None, "system authentication cancellation", timeout=120)
                require(alive(identity), "cancelled authentication changed the fixture")
                record["cases"].append({"case": "cancel", "identity": identity,
                                        "ordinary_exit": ordinary.returncode, "notice": notice, "alive": True})
            print("AUTH EXPIRED: wait for the EXPIRED message before authenticating." if expired else
                  f"AUTH SUCCESS: authenticate the next system dialog to {action} the root fixture.", flush=True)
            ui.confirm(action)
            if expired:
                wait_for(lambda: not alive(identity), "fixture expiry", timeout=25)
                print("EXPIRED: the original fixture has exited; now authenticate the pending system dialog.", flush=True)
                prefix = "The selected process exited"
            else:
                prefix = "Request sent to "
            notice = wait_for(lambda: value if (value := ui.notice()).startswith(prefix) else None,
                              "authenticated action result", timeout=120)
            wait_for(lambda: not alive(identity), "the original root fixture exit", timeout=5)
            require(process_identity(ui.app.pid)["uid"] == os.getuid(), "the UI became privileged")
            record["cases"].append({"case": "expired" if expired else action, "identity": identity,
                                    "ordinary_exit": ordinary.returncode, "notice": notice, "alive": False})
        record["status"] = "PASS"
    except BaseException as error:
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        # Fixtures terminate by themselves within 180 seconds. Cleanup must not
        # open another auth dialog or signal a PID whose identity has changed.
        cleanup_errors = []
        remaining = []
        for identity in fixtures:
            try:
                if alive(identity):
                    remaining.append(identity)
            except Exception as error:
                cleanup_errors.append(f"Observe fixture {identity['pid']}: {error}")
        record["remaining_bounded_fixtures"] = remaining
        try:
            if ui is not None:
                ui.close()
        except Exception as error:
            cleanup_errors.append(f"Close owned UI: {error}")
        if cleanup_errors:
            record.update(status="FAIL", cleanup_errors=cleanup_errors)
        (args.output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
        if cleanup_errors:
            raise RuntimeError("Native authentication cleanup was incomplete: " + "; ".join(cleanup_errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tree", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--interactive-auth", action="store_true", required=True,
                        help="the developer is present to respond to operating-system dialogs")
    args = parser.parse_args()
    if platform.system() == "Darwin" and args.tree is None:
        parser.error("macOS requires --tree")
    run(args)
