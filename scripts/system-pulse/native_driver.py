# ruff: noqa: E402
"""Bounded native transport on the replay's private X11/DBus session."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib
from PIL import ImageGrab
from Xlib import X, XK, display, protocol
from Xlib.ext import xtest

from host_accuracy import require
from native_contract import expected_label, contained, check_transport_record

BUDGETS = {
    "startup": 15,
    "discovery": 15,
    "condition": 5,
    "metric": 5,
    "freshness": 2,
    "batch": 8,
    "navigation": 180,
    "appearance": 5,
    "exit": 5,
    "persistence": 10,
    "shutdown": 10,
    "nodes": 30000,
}


def spin(seconds=0.025):
    deadline = time.monotonic() + seconds
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(min(0.005, max(0, deadline - time.monotonic())))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(row):
    i = row["identity"]
    return f"process:{i['pid']}:{i['start_time_ticks']}"


TRANSPORT = None


def close_transport(output):
    global TRANSPORT
    if TRANSPORT is None:
        return
    child = TRANSPORT
    TRANSPORT = None
    errors = []
    forced_kill = False
    try:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
    except BaseException as error:
        errors.append(str(error))
        try:
            forced_kill = True
            child.kill()
            child.wait(timeout=5)
        except BaseException as cleanup_error:
            errors.append("forced cleanup: " + str(cleanup_error))
    record = {
        "pid": child.pid,
        "exit_code": child.returncode,
        "proc_exists": Path(f"/proc/{child.pid}").exists(),
        "forced_kill": forced_kill,
        "errors": errors,
    }
    Path(output, "transport-cleanup.json").write_text(json.dumps(record, indent=2))
    check_transport_record(record)


class Native:
    def __init__(self, binary, output, state):
        self.app = None
        self.a11y = None
        self.d = None
        self.log = None
        self.closed = False
        self.output = Path(output)
        try:
            self._initialize(binary, output, state)
        except BaseException:
            self.close()
            raise

    def _initialize(self, binary, output, state):
        startup_deadline = time.monotonic() + 15
        self.binary = Path(binary)
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.state_dir = Path(state)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.interval_ms = 1000
        try:
            saved = self.state()
            if saved.get("schema_version") == 1:
                self.interval_ms = saved["interval_ms"]
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        self.cache = {}
        self.app = None
        self.a11y = None
        self.lock = threading.Lock()
        self.case = 0
        self.log = (self.output / "application.log").open("w")
        self.latest = self.output / "latest.json"
        self.d = display.Display()
        global TRANSPORT
        if TRANSPORT is None:
            os.environ.pop("AT_SPI_BUS_ADDRESS", None)
            TRANSPORT = subprocess.Popen(
                [
                    "/usr/libexec/at-spi-bus-launcher",
                    "--launch-immediately",
                    "--a11y=1",
                    "--screen-reader=1",
                ],
                env=dict(os.environ, GSETTINGS_BACKEND="memory"),
                stdout=self.log,
                stderr=self.log,
            )
            spin(0.3)
            Atspi.init()
            Atspi.set_timeout(250, 250)
        self.a11y = TRANSPORT
        self.app = subprocess.Popen(
            [str(self.binary)],
            env=dict(
                os.environ,
                SYSTEM_PULSE_STATE_DIR=str(self.state_dir),
                SYSTEM_PULSE_DIAGNOSTICS_PATH=str(self.latest),
                RUST_BACKTRACE="1",
            ),
            stdout=self.log,
            stderr=self.log,
        )
        self.journal("launch", pid=self.app.pid, binary=str(self.binary))
        self.wait(
            lambda: self.frame(),
            message="first fresh snapshot",
            deadline=startup_deadline,
        )
        self.wait(
            lambda: self.root(),
            message="new session native PID root",
            deadline=startup_deadline,
        )
        self.window().set_input_focus(X.RevertToParent, X.CurrentTime)
        self.d.sync()
        metadata = {
            "application_pid": self.app.pid,
            "binary": str(self.binary),
            "binary_sha256": digest(self.binary),
            "proc_exe_sha256": digest(f"/proc/{self.app.pid}/exe"),
            "source_commit": subprocess.check_output(
                ["rtk", "proxy", "git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "budgets": BUDGETS,
            "sampling_interval_ms": self.interval_ms,
            "accepted_age_limit_seconds": self.interval_ms / 500,
        }
        require(
            metadata["binary_sha256"] == metadata["proc_exe_sha256"],
            "running binary differs",
        )
        self.save("metadata.json", metadata)

    def journal(self, op, **fields):
        with self.lock:
            with (self.output / "journal.jsonl").open("a") as out:
                out.write(
                    json.dumps(
                        {"op": op, "monotonic_ns": time.monotonic_ns(), **fields}
                    )
                    + "\n"
                )

    def save(self, name, value):
        path = self.output / name
        with path.open("x") as out:
            json.dump(value, out, indent=2)
        return path

    def wait(self, fn, seconds=5, message="condition", deadline=None):
        deadline = deadline if deadline is not None else time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            require(
                self.app is None or self.app.poll() is None,
                f"app exited during {message}",
            )
            try:
                value = fn()
                if value is not None and value is not False:
                    require(
                        time.monotonic() < deadline,
                        "condition completed after deadline",
                    )
                    self.journal("ack", condition=message)
                    return value
            except (
                GLib.Error,
                FileNotFoundError,
                json.JSONDecodeError,
                AttributeError,
                TypeError,
            ) as error:
                last = str(error)
            spin()
        raise TimeoutError(
            f"{message}: original deadline expired; last transient={last}"
        )

    def frame(self):
        frame = json.loads(self.latest.read_text())
        checked_unix_ns = time.time_ns()
        age = (checked_unix_ns - frame["accepted_unix_ns"]) / 1e9
        require(
            frame["application_pid"] == self.app.pid, "wrong diagnostic PID/session"
        )
        limit = self.interval_ms / 500
        if not 0 <= age <= limit:
            self.save(
                f"stale-frame-{time.monotonic_ns()}.json",
                {
                    "checked_unix_ns": checked_unix_ns,
                    "age_seconds": age,
                    "limit_seconds": limit,
                    "frame": frame,
                },
            )
        require(0 <= age <= limit, f"accepted frame stale: {age:.3f}s (limit {limit}s)")
        return frame

    def interval(self, milliseconds):
        require(
            milliseconds in (500, 1000, 2000, 5000), "unsupported sampling interval"
        )
        previous = self.frame()["snapshot"]["sequence"]
        label = {500: "0.5 s", 1000: "1 s", 2000: "2 s", 5000: "5 s"}[milliseconds]
        self.action(self.find(label, "button"))
        self.wait(
            lambda: self.state()["interval_ms"] == milliseconds,
            message="sampling preference " + label,
        )
        self.journal(
            "interval-freshness",
            interval_ms=milliseconds,
            accepted_age_limit_seconds=milliseconds / 500,
        )
        self.wait(
            lambda: self.frame()["snapshot"]["sequence"] > previous,
            seconds=6,
            message="sample after interval transition",
        )
        self.interval_ms = milliseconds

    def wheel(self, point, down):
        self.journal("wheel", point=point, down=down, count=1)
        xtest.fake_input(self.d, X.MotionNotify, x=int(point[0]), y=int(point[1]))
        xtest.fake_input(self.d, X.ButtonPress, 5 if down else 4)
        xtest.fake_input(self.d, X.ButtonRelease, 5 if down else 4)
        self.d.sync()

    def root(self):
        desktop = Atspi.get_desktop(0)
        desktop.clear_cache()
        for i in range(desktop.get_child_count()):
            try:
                node = desktop.get_child_at_index(i)
                if self.alive(node) and node.get_process_id() == self.app.pid:
                    return node
            except GLib.Error:
                continue
        return None

    def alive(self, node):
        if node is None:
            return False
        node.clear_cache()
        return not node.get_state_set().contains(Atspi.StateType.DEFUNCT)

    def walk(self, root=None, deadline=None, skip_cells=False):
        deadline = deadline or time.monotonic() + 15
        stack = [root if root is not None else self.root()]
        count = 0
        while stack:
            require(
                time.monotonic() < deadline,
                "native discovery deadline exceeded; incomplete tree",
            )
            node = stack.pop()
            if not self.alive(node):
                continue
            count += 1
            require(
                count <= BUDGETS["nodes"], "native node bound exceeded; incomplete tree"
            )
            aid = node.get_accessible_id() or ""
            if aid:
                self.cache[aid] = node
            yield node
            if skip_cells and aid.startswith("process:") and ":cell:" not in aid:
                continue
            for index in reversed(range(node.get_child_count())):
                child = node.get_child_at_index(index)
                if child is not None:
                    stack.append(child)

    def find(self, name=None, role=None, aid=None, root=None, deadline=None):
        deadline = deadline or time.monotonic() + 15
        if aid and self.alive(self.cache.get(aid)):
            return self.cache[aid]

        def attempt():
            matches = [
                n
                for n in self.walk(root, deadline)
                if (name is None or n.get_name() == name)
                and (role is None or n.get_role_name() == role)
                and (aid is None or (n.get_accessible_id() or "") == aid)
            ]
            require(
                len(matches) <= 1,
                f"nonunique native lookup {name or aid}: {len(matches)}",
            )
            return matches[0] if matches else None

        return self.wait(attempt, message="find " + str(name or aid), deadline=deadline)

    def panel(self, mid):
        key = "__panel:" + mid
        if self.alive(self.cache.get(key)):
            return self.cache[key]
        self.cache[key] = self.find(name=mid, role="panel")
        return self.cache[key]

    def bounds(self, node):
        node.clear_cache()
        b = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        return [b.x, b.y, b.width, b.height]

    def window(self):
        windows = [
            w
            for w in self.d.screen().root.query_tree().children
            if w.get_attributes().map_state == X.IsViewable
            and w.get_geometry().width > 100
        ]
        require(
            len(windows) == 1, f"expected one private app window, got {len(windows)}"
        )
        return windows[0]

    def ancestors(self, node):
        result = []
        for _ in range(40):
            node = node.get_parent()
            if node is None:
                return result
            node.clear_cache()
            result.append(
                {
                    "id": node.get_accessible_id(),
                    "name": node.get_name(),
                    "role": node.get_role_name(),
                    "bounds": self.bounds(node)
                    if node.get_component_iface() is not None
                    else None,
                }
            )
        raise AssertionError("ancestor depth exceeded")

    def visible(self, node):
        geometry = self.window().get_geometry()
        clips = [{"id": "window", "bounds": [0, 0, geometry.width, geometry.height]}]
        clips.extend(
            a for a in self.ancestors(node) if (a["id"] or "").endswith(":viewport")
        )
        require(
            any(a["id"] == "workspace:viewport" for a in clips),
            "workspace clipping rectangle absent from native ancestry",
        )
        require(
            all(a["bounds"] is not None for a in clips),
            "missing native clipping bounds",
        )
        return contained(self.bounds(node), [a["bounds"] for a in clips])

    def focus(self, node):
        deadline = time.monotonic() + 5
        self.journal(
            "focus",
            name=node.get_name(),
            id=node.get_accessible_id(),
            deadline=deadline,
        )
        require(node.get_component_iface().grab_focus(), "focus rejected")
        self.wait(
            lambda: self.alive(node)
            and node.get_state_set().contains(Atspi.StateType.FOCUSED)
            and self.visible(node),
            message="native focus and clipped visibility",
            deadline=deadline,
        )
        self.journal(
            "focus-visible",
            bounds=self.bounds(node),
            clip_ancestors=self.ancestors(node),
        )

    def action(self, node):
        self.journal("action", name=node.get_name(), id=node.get_accessible_id())
        require(node.get_action_iface().do_action(0), "native action rejected")

    def click(self, node):
        bounds = self.bounds(node)
        geometry = self.window().get_geometry()
        require(
            contained(bounds, [[0, 0, geometry.width, geometry.height]]),
            "pointer control outside window",
        )
        self.journal("pointer-click", name=node.get_name(), bounds=bounds)
        xtest.fake_input(
            self.d,
            X.MotionNotify,
            x=int(bounds[0] + bounds[2] / 2),
            y=int(bounds[1] + bounds[3] / 2),
        )
        xtest.fake_input(self.d, X.ButtonPress, 1)
        xtest.fake_input(self.d, X.ButtonRelease, 1)
        self.d.sync()

    def key(self, *keys, pressed=None):
        self.journal("key", keys=keys, pressed=pressed)
        codes = [self.d.keysym_to_keycode(XK.string_to_keysym(k)) for k in keys]
        require(all(codes), "invalid keysym")
        if pressed is not False:
            for code in codes:
                xtest.fake_input(self.d, X.KeyPress, code)
        if pressed is not True:
            for code in reversed(codes):
                xtest.fake_input(self.d, X.KeyRelease, code)
        self.d.sync()

    def resize(self, width, height):
        self.journal("resize", width=width, height=height)
        self.window().configure(width=width, height=height)
        self.d.sync()
        self.wait(
            lambda: self.window().get_geometry().width == width
            and self.window().get_geometry().height == height,
            message="window resize",
        )

    def drag(self, start, end):
        self.journal("drag", start=start, end=end)

        def move(point):
            xtest.fake_input(self.d, X.MotionNotify, x=int(point[0]), y=int(point[1]))
            self.d.sync()

        move(start)
        xtest.fake_input(self.d, X.ButtonPress, 1)
        self.d.sync()
        try:
            for i in range(1, 21):
                move([start[j] + (end[j] - start[j]) * i / 20 for j in (0, 1)])
                spin(0.025)
        finally:
            xtest.fake_input(self.d, X.ButtonRelease, 1)
            self.d.sync()

    def screenshot(self, name):
        path = self.output / name
        require(not path.exists(), "artifact overwrite")
        ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).save(path)
        self.journal("screenshot", path=str(path), sha256=digest(path))
        return str(path)

    def state(self, file="workspace.json"):
        return json.loads((self.state_dir / file).read_text())

    def save_state(self):
        path = self.state_dir / "workspace.json"

        def read_version():
            with path.open() as stream:
                content = json.load(stream)
                stat = os.fstat(stream.fileno())
                return (
                    stat.st_dev,
                    stat.st_ino,
                    stat.st_mtime_ns,
                    stat.st_ctime_ns,
                ), content

        before = read_version()[0] if path.exists() else None
        self.click(self.find("Save", "button"))

        def changed():
            version, content = read_version()
            return content if version != before else None

        return self.wait(
            changed,
            10,
            "newly written saved workspace",
        )

    def no_tabs(self, name):
        rows = []
        for node in self.walk():
            role = node.get_role_name()
            label = node.get_name()
            aid = node.get_accessible_id() or ""
            require(
                role not in ("page tab", "page tab list"), "native tab role present"
            )
            require(
                not any(
                    token in (label + " " + aid).lower()
                    for token in (
                        "advance fixture",
                        "fixture-a",
                        "fixture-b",
                        "fixture-home",
                        "fixture-lan",
                        "connect fake",
                        "reverse discovery",
                    )
                ),
                "fixture control/identity present",
            )
            rows.append(
                {
                    "id": aid,
                    "role": role,
                    "name": label,
                    "bounds": self.bounds(node)
                    if node.get_component_iface() is not None
                    else None,
                }
            )
        require(rows, "app accessibility tree absent")

        def check(node):
            if isinstance(node, dict):
                if node.get("panel_name") == "TabPanel":
                    require(len(node["children"]) <= 1, "tab wrapper groups monitors")
                for value in node.values():
                    check(value)
            elif isinstance(node, list):
                for value in node:
                    check(value)

        check(self.save_state()["dock"])
        self.save(name + ".json", rows)
        self.screenshot(name + ".png")

    def metric(self, aid, name, visible=True):
        # Initial discovery is outside the original per-metric five-second bracket.
        def lookup(deadline=None):
            if aid.startswith("process:"):
                row_id = aid.rsplit(":cell:", 1)[0]
                row = self.cache.get(row_id)
                if not self.alive(row):
                    row = next(
                        (
                            candidate
                            for candidate in self.walk(
                                self.panel("processes"), deadline, skip_cells=True
                            )
                            if candidate.get_accessible_id() == row_id
                        ),
                        None,
                    )
                require(row is not None, "required real process row absent")
                return self.find(aid=aid, root=row, deadline=deadline)
            return self.find(aid=aid, deadline=deadline)

        node = lookup()
        self.save(name + "-ancestors.json", self.ancestors(node))
        deadline = time.monotonic() + 5
        attempts = []
        while time.monotonic() < deadline:
            try:
                before = self.frame()
                node.clear_cache()
                if not self.alive(node):
                    self.cache.pop(aid, None)
                    node = lookup(deadline)
                    continue
                actual = node.get_name()
                bounds = self.bounds(node)
                after = self.frame()
                stable = (
                    before["application_pid"]
                    == after["application_pid"]
                    == self.app.pid
                    and before["snapshot"]["sequence"] == after["snapshot"]["sequence"]
                    and before["render_revision"] == after["render_revision"]
                )
                attempts.append(
                    {
                        "stable": stable,
                        "actual": actual,
                        "sequence": before["snapshot"]["sequence"],
                        "revision": before["render_revision"],
                    }
                )
                if stable:
                    entry = next(
                        e for e in before["rendered"] if e["element_id"] == aid
                    )
                    expected = expected_label(before, entry)
                    if actual != expected:
                        spin()
                        continue
                    if visible and not self.visible(node):
                        spin()
                        continue
                    require(time.monotonic() < deadline, "metric deadline exceeded")
                    artifact = {
                        "entry": entry,
                        "bounds": bounds,
                        "clip_ancestors": self.ancestors(node),
                        "visible": visible,
                        "attempts": attempts,
                        "frame": before,
                        "after_metadata": {
                            k: after[k]
                            for k in (
                                "application_pid",
                                "render_revision",
                                "accepted_unix_ns",
                            )
                        },
                    }
                    self.save(name + ".json", artifact)
                    if visible:
                        self.screenshot(name + ".png")
                    return artifact
            except (GLib.Error, AttributeError, TypeError):
                self.cache.pop(aid, None)
                node = lookup(deadline)
            spin()
        self.save(
            name + "-failure.json",
            {"attempts": attempts, "bounds": self.bounds(node), "frame": self.frame()},
        )
        self.screenshot(name + "-failure.png")
        raise TimeoutError("original five-second metric bracket failed")

    def missing_monitor(self, mid):
        aid = mid + ":summary"
        node = self.find(aid=aid, root=self.panel(mid))
        deadline = time.monotonic() + 5
        attempts = []
        while time.monotonic() < deadline:
            before = self.frame()
            node.clear_cache()
            text = node.get_name()
            after = self.frame()
            if (before["snapshot"]["sequence"], before["render_revision"]) != (
                after["snapshot"]["sequence"],
                after["render_revision"],
            ):
                spin()
                continue
            entry = next(
                item for item in before["rendered"] if item["element_id"] == aid
            )
            require(
                all(monitor["id"] != mid for monitor in before["snapshot"]["monitors"]),
                "missing-device specimen is actually present",
            )
            require(
                entry["sample"] is None or entry["sample"]["value"] is None,
                "missing-device specimen has a measured value",
            )
            require(
                "Unavailable" in entry["label"],
                "missing-device specimen lacks truthful unavailable status",
            )
            visible = self.visible(node)
            attempts.append(
                {
                    "sequence": before["snapshot"]["sequence"],
                    "revision": before["render_revision"],
                    "native_text": text,
                    "expected_text": entry["label"],
                    "bounds": self.bounds(node),
                    "clip_ancestors": self.ancestors(node),
                    "visible": visible,
                }
            )
            if text == entry["label"] and visible:
                self.save(
                    "missing-native.json",
                    {
                        "entry": entry,
                        "frame": before,
                        "bounds": self.bounds(node),
                        "clip_ancestors": self.ancestors(node),
                        "attempts": attempts,
                    },
                )
                self.screenshot("missing-native.png")
                return entry
            spin()
        self.save("missing-native-failure.json", {"attempts": attempts})
        raise TimeoutError(
            "missing native monitor did not match within original five seconds"
        )

    def sequences(self, count=3, seconds=5):
        seen = set()
        records = []

        def poll():
            frame = self.frame()
            sequence = frame["snapshot"]["sequence"]
            if sequence not in seen:
                seen.add(sequence)
                records.append(
                    {
                        "sequence": sequence,
                        "accepted_unix_ns": frame["accepted_unix_ns"],
                    }
                )
            return records if len(seen) >= count else None

        return self.wait(poll, seconds, "fresh sequence progression")

    def selected(self, deadline):
        matches = []
        for node in self.walk(self.panel("processes"), deadline, skip_cells=True):
            aid = node.get_accessible_id() or ""
            if (
                aid.startswith("process:")
                and ":cell:" not in aid
                and node.get_state_set().contains(Atspi.StateType.SELECTED)
            ):
                matches.append((aid, node))
        require(len(matches) <= 1, "multiple selected process identities")
        return matches[0] if matches else None

    def enter_processes(self):
        self.focus(self.find("Hide Processes", "button", root=self.panel("processes")))
        self.key("Tab")

    def acknowledge(self, aid, deadline):
        def poll():
            self.frame()
            cached = self.cache.get(aid)
            if self.alive(cached) and cached.get_state_set().contains(
                Atspi.StateType.SELECTED
            ):
                return aid, cached
            selected = self.selected(deadline)
            return selected if selected and selected[0] == aid else None

        return self.wait(poll, message="selected " + aid, deadline=deadline)

    def navigate(self, target):
        deadline = time.monotonic() + 180
        self.navigation_context = {
            "target": target,
            "phase": "enter table",
            "original_deadline_monotonic": deadline,
            "last_acknowledged_identity": None,
        }
        try:
            return self._navigate(target, deadline)
        except BaseException as error:
            context = dict(
                self.navigation_context,
                error=str(error),
                observed_monotonic=time.monotonic(),
            )
            self.save(f"navigation-failure-{time.monotonic_ns()}.json", context)
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"child navigation original180s deadline expired: {context}"
                ) from error
            raise

    def _navigate(self, target, deadline):
        self.enter_processes()
        rows = self.frame()["snapshot"]["processes"]
        ids = list(map(identity, rows))
        index = ids.index(target)
        self.save(
            "navigation-start-" + target.replace(":", "-") + ".json",
            {
                "target": target,
                "index": index,
                "population": len(ids),
                "identities": ids,
                "deadline_monotonic": deadline,
            },
        )
        key = "Home" if index < len(ids) / 2 else "End"
        self.navigation_context.update(
            phase="initial boundary acknowledgement",
            target_index=index,
            population=len(ids),
            distance=min(index, len(ids) - 1 - index),
        )
        self.key(key)
        selected = self.acknowledge(
            ids[0 if key == "Home" else -1], min(deadline, time.monotonic() + 8)
        )
        while selected[0] != target:
            self.navigation_context.update(
                last_acknowledged_identity=selected[0], phase="next batch"
            )
            frame = self.frame()
            ids = list(map(identity, frame["snapshot"]["processes"]))
            delta = ids.index(target) - ids.index(selected[0])
            self.navigation_context.update(
                target_index=ids.index(target), population=len(ids), distance=abs(delta)
            )
            count = min(abs(delta), 2)
            require(
                count > 0 and time.monotonic() < deadline,
                "navigation original deadline expired",
            )
            expected = ids[ids.index(selected[0]) + (count if delta > 0 else -count)]
            self.journal(
                "navigation-batch",
                target=target,
                selected=selected[0],
                expected=expected,
                count=count,
                distance=abs(delta),
                sequence=frame["snapshot"]["sequence"],
                deadline=deadline,
            )
            for _ in range(count):
                self.key("Down" if delta > 0 else "Up")
            selected = self.acknowledge(expected, min(deadline, time.monotonic() + 8))
            self.navigation_context.update(
                last_acknowledged_identity=selected[0],
                phase="newer snapshot before next batch",
            )
            self.wait(
                lambda: self.frame()["snapshot"]["sequence"]
                > frame["snapshot"]["sequence"],
                message="fresh next navigation snapshot",
                deadline=min(deadline, time.monotonic() + 8),
            )
        return selected

    def shutdown(self):
        if self.app.poll() is not None:
            raise AssertionError("app exited before normal shutdown")
        self.journal("WM_DELETE_WINDOW")
        window = self.window()
        event = protocol.event.ClientMessage(
            window=window,
            client_type=self.d.intern_atom("WM_PROTOCOLS"),
            data=(32, [self.d.intern_atom("WM_DELETE_WINDOW"), X.CurrentTime, 0, 0, 0]),
        )
        window.send_event(event)
        self.d.sync()
        deadline = time.monotonic() + 10
        while self.app.poll() is None and time.monotonic() < deadline:
            spin()
        result = {
            "exit_code": self.app.poll(),
            "before_deadline": time.monotonic() < deadline,
        }
        self.save("shutdown.json", result)
        require(
            result["exit_code"] == 0 and result["before_deadline"],
            "normal shutdown failed",
        )

    def close(self):
        if self.closed:
            return
        self.closed = True
        cleanup = []
        for child in (self.app,):
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
            if child is not None:
                cleanup.append(
                    {
                        "pid": child.pid,
                        "exit_code": child.poll(),
                        "proc_exists": Path(f"/proc/{child.pid}").exists(),
                    }
                )
        if self.d is not None:
            self.d.close()
        if self.log is not None:
            self.log.close()
        if self.output.is_dir():
            self.save("cleanup.json", cleanup)
