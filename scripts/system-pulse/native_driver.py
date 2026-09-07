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
from native_observations import (
    NavigationObservations,
    current_observation,
    error_text,
    navigation_observation,
)

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


class IncompleteNativeTree(RuntimeError):
    """A changing accessibility subtree cannot prove a row is absent."""


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
    def __init__(self, binary, output, state, *, working_directory=None):
        self.working_directory = working_directory
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
        application_environment = self.diagnostic_environment()
        self.app = subprocess.Popen(
            [str(self.binary)],
            env=application_environment,
            cwd=getattr(self, "working_directory", None),
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
        # Replay pointer coordinates use the window origin. The application may
        # choose a centered first window; place only this private test window.
        self.window().configure(x=0, y=0)
        self.d.sync()
        self.wait(
            lambda: self.window().get_geometry().x == 0
            and self.window().get_geometry().y == 0,
            message="private window at screen origin",
            deadline=startup_deadline,
        )
        self.window().set_input_focus(X.RevertToParent, X.CurrentTime)
        self.d.sync()
        metadata = {
            "application_pid": self.app.pid,
            "publication_timing_instrumented": self.publication_timing_instrumented,
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

    def diagnostic_environment(self):
        environment = dict(
            os.environ,
            SYSTEM_PULSE_STATE_DIR=str(self.state_dir),
            SYSTEM_PULSE_DIAGNOSTICS_PATH=str(self.latest),
            RUST_BACKTRACE="1",
        )
        self.publication_timing_instrumented = (
            environment.get("SYSTEM_PULSE_DIAGNOSTICS_TRACE") == "1"
        )
        if self.publication_timing_instrumented:
            before = time.monotonic_ns()
            wall = time.time_ns()
            after = time.monotonic_ns()
            self.save(
                "publication-timing-metadata.json",
                {
                    "publication_timing_instrumented": True,
                    "sidecar": str(self.latest.with_suffix(".publication-timing.json")),
                    "harness_clock_anchor": {
                        "clock": "Python time.monotonic_ns; not writer Instant offsets",
                        "monotonic_before_ns": before,
                        "unix_ns": wall,
                        "monotonic_after_ns": after,
                    },
                    "coverage": "Worker-produced sidecar retained in place, including failure cleanup. Missing or older sidecars do not prove completion of later stages.",
                },
            )
        return environment

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

    def wait(
        self, fn, seconds=5, message="condition", deadline=None, *, acknowledge=True
    ):
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
                    if acknowledge:
                        self.journal("ack", condition=message)
                    return value
            except (
                IncompleteNativeTree,
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
        observation = {"opened_file": None, "pathname_before_check": None, "errors": {}}

        def mark_time(stage):
            try:
                observation[stage] = time.monotonic_ns()
            except Exception as error:
                observation[stage] = None
                observation["errors"][stage] = f"{type(error).__name__}: {error}"

        mark_time("read_started_monotonic_ns")
        with self.latest.open() as opened:
            contents = opened.read()
            mark_time("read_completed_monotonic_ns")
            frame = json.loads(contents)
            mark_time("parse_completed_monotonic_ns")
            try:
                opened_stat = os.fstat(opened.fileno())
                observation["opened_file"] = {
                    "device": opened_stat.st_dev,
                    "inode": opened_stat.st_ino,
                }
            except Exception as error:
                observation["errors"]["opened_file"] = (
                    f"{type(error).__name__}: {error}"
                )
        try:
            pathname_stat = self.latest.stat()
            observation["pathname_before_check"] = {
                "device": pathname_stat.st_dev,
                "inode": pathname_stat.st_ino,
            }
        except Exception as error:
            observation["errors"]["pathname_before_check"] = (
                f"{type(error).__name__}: {error}"
            )
        mark_time("age_checked_monotonic_ns")
        checked_unix_ns = time.time_ns()
        age = (checked_unix_ns - frame["accepted_unix_ns"]) / 1e9
        require(
            frame["application_pid"] == self.app.pid, "wrong diagnostic PID/session"
        )
        limit = self.interval_ms / 500
        if not 0 <= age <= limit:
            # A failed observation clock must not replace the stale verdict.
            artifact_stamp = observation["age_checked_monotonic_ns"]
            if artifact_stamp is None:
                artifact_stamp = checked_unix_ns
            self.save(
                f"stale-frame-{artifact_stamp}.json",
                {
                    "checked_unix_ns": checked_unix_ns,
                    "age_seconds": age,
                    "limit_seconds": limit,
                    "frame": frame,
                    "observation": observation,
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

    def wheel(self, point, down, *, deadline=None):
        self.journal("wheel", point=point, down=down, count=1)
        if deadline is not None:
            # Include synchronous journal work in the recovery input budget.
            require(time.monotonic() < deadline, "navigation reveal deadline expired")
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

    def walk(
        self,
        root=None,
        deadline=None,
        skip_cells=False,
        strict=False,
        skip_monitor_bodies=False,
        with_identity=False,
    ):
        deadline = deadline or time.monotonic() + 15
        stack = [(root if root is not None else self.root(), None)]
        count = 0
        while stack:
            require(
                time.monotonic() < deadline,
                "native discovery deadline exceeded; incomplete tree",
            )
            node, parent = stack.pop()
            if not self.alive(node):
                if strict:
                    raise IncompleteNativeTree(
                        "incomplete native tree: missing or defunct node"
                    )
                continue
            count += 1
            require(
                count <= BUDGETS["nodes"], "native node bound exceeded; incomplete tree"
            )
            aid = node.get_accessible_id() or ""
            if aid:
                self.cache[aid] = node
            yield (node, aid) if with_identity else node
            if skip_cells and aid.startswith("process:") and ":cell:" not in aid:
                continue
            if (
                skip_monitor_bodies
                and aid.endswith(":viewport")
                and aid != "workspace:viewport"
                and parent is not None
                and node.get_role_name() == "panel"
                and self.alive(parent)
                and parent.get_role_name() == "panel"
            ):
                parent_name = parent.get_name()
                if parent_name and aid == parent_name + ":viewport":
                    # Monitor bodies contain readings/rows, never sibling dock panels.
                    continue
            child_count = node.get_child_count()
            if strict and child_count < 0:
                raise IncompleteNativeTree(
                    "incomplete native tree: negative child count"
                )
            for index in reversed(range(child_count)):
                child = node.get_child_at_index(index)
                if strict and child is None:
                    raise IncompleteNativeTree(
                        f"incomplete native tree: missing child at index {index}"
                    )
                if child is not None:
                    stack.append((child, node))
            if strict and not self.alive(node):
                raise IncompleteNativeTree(
                    "incomplete native tree: node became defunct"
                )

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
        # GetExtents is a live D-Bus request, not an Accessible cache property.
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

    def key(self, *keys, pressed=None, deadline=None):
        self.journal("key", keys=keys, pressed=pressed)
        codes = [self.d.keysym_to_keycode(XK.string_to_keysym(k)) for k in keys]
        require(all(codes), "invalid keysym")
        if pressed is not False:
            require(
                deadline is None or time.monotonic() < deadline,
                "navigation original deadline expired before physical key",
            )
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
        deadline = time.monotonic() + 15

        def inventory():
            rows = []
            try:
                for node, aid in self.walk(
                    deadline=deadline, strict=True, with_identity=True
                ):
                    role = node.get_role_name()
                    label = node.get_name()
                    require(
                        role not in ("page tab", "page tab list"),
                        "native tab role present",
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
            except (GLib.Error, IncompleteNativeTree):
                # A live process can disappear between discovery and bounds.
                # Discard the partial inventory; keep the original deadline.
                return None
            require(rows, "app accessibility tree absent")
            return rows

        rows = self.wait(
            inventory, message="complete native tree inventory", deadline=deadline
        )

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

    def process_cell(self, aid, deadline=None, *, prepare_missing=None):
        """Find a unique cell in its exact PID/start row under one deadline."""
        deadline = deadline if deadline is not None else time.monotonic() + 15
        row_id = aid.rsplit(":cell:", 1)[0]

        def attempt():
            # A cached panel cannot prove current application membership or uniqueness.
            panels = [
                node
                for node in self.walk(
                    deadline=deadline, skip_cells=True, skip_monitor_bodies=True
                )
                if node.get_name() == "processes" and node.get_role_name() == "panel"
            ]
            require(len(panels) <= 1, "nonunique native Processes panel")
            if not panels:
                if prepare_missing is not None:
                    prepare_missing(deadline)
                return None
            panel = self.cache["__panel:processes"] = panels[0]
            # The global cache cannot prove membership or uniqueness in this panel.
            rows = [
                node
                for node in self.walk(panel, deadline, skip_cells=True)
                if node.get_accessible_id() == row_id
            ]
            require(len(rows) <= 1, "nonunique native process row " + row_id)
            if not rows:
                if prepare_missing is not None:
                    prepare_missing(deadline)
                return None
            row = rows[0]
            # Scan this row even when the cell is cached: a live cache entry alone
            # cannot establish membership or uniqueness after a native replacement.
            cells = [
                node
                for node in self.walk(row, deadline, strict=True)
                if node.get_accessible_id() == aid
            ]
            require(len(cells) <= 1, "nonunique native lookup " + aid)
            if (
                cells
                and self.alive(panel)
                and self.alive(row)
                and row.get_accessible_id() == row_id
                and self.alive(cells[0])
                and cells[0].get_accessible_id() == aid
            ):
                return cells[0]
            return None

        return self.wait(attempt, message="find process cell " + aid, deadline=deadline)

    def metric(self, aid, name, visible=True, *, prepare_missing=None):
        # Initial discovery is outside the original per-metric five-second bracket.
        def lookup(deadline=None):
            if aid.startswith("process:"):
                return self.process_cell(
                    aid,
                    deadline,
                    **(
                        {"prepare_missing": prepare_missing}
                        if prepare_missing is not None
                        else {}
                    ),
                )
            return self.find(aid=aid, deadline=deadline)

        node = lookup()
        deadline = time.monotonic() + 5
        attempts = []
        ancestors_saved = False
        while time.monotonic() < deadline:
            try:
                if not ancestors_saved:
                    self.save(name + "-ancestors.json", self.ancestors(node))
                    ancestors_saved = True
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
            age = (time.time_ns() - frame["accepted_unix_ns"]) / 1e9
            sequence = frame["snapshot"]["sequence"]
            if sequence not in seen:
                seen.add(sequence)
                records.append(
                    {
                        "sequence": sequence,
                        "accepted_unix_ns": frame["accepted_unix_ns"],
                        "age": age,
                    }
                )
            return records if len(seen) >= count else None

        return self.wait(poll, seconds, "fresh sequence progression")

    def selected(self, deadline, strict=False, panel=None, scan=None):
        observation = current_observation(self)
        with observation.stage("scan"):
            panel = panel if panel is not None else self.panel("processes")
            matches = []
            if scan is not None:
                scan.update(rows=[], viewports=[])
            for node in self.walk(panel, deadline, skip_cells=True, strict=strict):
                aid = node.get_accessible_id() or ""
                is_row = aid.startswith("process:") and ":cell:" not in aid
                if scan is not None:
                    if is_row:
                        scan["rows"].append(aid)
                    elif aid == "processes:rows-viewport":
                        scan["viewports"].append(node)
                if is_row:
                    observation.row(aid)
                    selected = node.get_state_set().contains(Atspi.StateType.SELECTED)
                    observation.selection(aid, selected)
                    if selected:
                        matches.append((aid, node))
            observation.scan_complete()
            observation.phase("selection uniqueness validation")
            require(len(matches) <= 1, "multiple selected process identities")
            return matches[0] if matches else None

    def wait_for_process_exit(self, aid, before_sequence, deadline):
        def poll():
            snapshot = self.frame()["snapshot"]
            if snapshot["sequence"] <= before_sequence or any(
                identity(row) == aid for row in snapshot["processes"]
            ):
                return False
            path = self.navigation_panel(deadline)
            panel = path[0]
            saw_panel = False
            saw_target = False
            selected_others = []
            for node in self.walk(
                panel, deadline=deadline, skip_cells=True, strict=True
            ):
                saw_panel = saw_panel or node is panel
                node_id = node.get_accessible_id() or ""
                saw_target = saw_target or node_id == aid
                if (
                    node_id.startswith("process:")
                    and ":cell:" not in node_id
                    and node_id != aid
                    and node.get_state_set().contains(Atspi.StateType.SELECTED)
                ):
                    selected_others.append(node_id)
            if not self.navigation_panel_current(path, deadline):
                return False
            require(
                not selected_others,
                f"another process selected after child exit: {selected_others}",
            )
            # This proves absence in the current instantiated tree, not model state.
            return saw_panel and not saw_target

        return self.wait(
            poll, message="child exit snapshot and native tree", deadline=deadline
        )

    def enter_processes(self):
        self.focus(self.find("Hide Processes", "button", root=self.panel("processes")))
        deadline = time.monotonic() + 5
        panel = self.panel("processes")
        table = self.find(aid="processes:viewport", root=panel, deadline=deadline)

        def observe():
            focused = tuple(
                (node.get_accessible_id(), node.get_name(), node.get_role_name())
                for node in self.walk(panel, deadline, skip_cells=True, strict=True)
                if node.get_state_set().contains(Atspi.StateType.FOCUSED)
            )
            table.clear_cache()
            return table.get_state_set().contains(Atspi.StateType.FOCUSED), focused

        previous = self.wait(observe, deadline=deadline, message="process entry focus")
        # Search and enabled task actions precede the table. Acknowledge each
        # focus transition rather than assuming one Tab or racing queued keys.
        for _ in range(8):
            if previous[0]:
                return
            self.key("Tab", deadline=deadline)

            def changed():
                current = observe()
                return current if current != previous else None

            previous = self.wait(
                changed, deadline=deadline, message="Tab focus transition into processes"
            )
        require(previous[0], "Tab did not reach the process table")

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

    def navigation_panel(self, deadline):
        """Discover the unique current panel and retain its application ancestry."""
        with navigation_observation(self, "panel discovery", deadline) as observation:
            with observation.stage("discovery"):
                panels = [
                    node
                    for node in self.walk(
                        deadline=deadline,
                        skip_cells=True,
                        strict=True,
                        skip_monitor_bodies=True,
                    )
                    if node.get_name() == "processes"
                    and node.get_role_name() == "panel"
                ]
                require(len(panels) <= 1, "nonunique native Processes panel")
                if not panels:
                    raise IncompleteNativeTree(
                        "incomplete native tree: Processes panel absent"
                    )
                application = self.root()
                path = [panels[0]]
                while path[-1] != application:
                    require(
                        time.monotonic() < deadline, "navigation panel deadline expired"
                    )
                    require(len(path) < 40, "navigation panel ancestry bound exceeded")
                    parent = path[-1].get_parent()
                    if not self.alive(parent) or parent in path:
                        raise IncompleteNativeTree(
                            "incomplete native tree: panel ancestry"
                        )
                    path.append(parent)
                if not observation.panel(
                    self.navigation_panel_current(path, deadline),
                    "discovery membership",
                ):
                    raise IncompleteNativeTree(
                        "incomplete native tree: panel membership"
                    )
                return path

    def navigation_links_current(self, path, deadline):
        """Validate ordinary child links, including viewport ancestry on recovery."""
        if not path:
            return False
        for child, parent in zip(path, path[1:]):
            require(time.monotonic() < deadline, "navigation panel deadline expired")
            if child is None or parent is None:
                return False
            child.clear_cache_single()
            parent.clear_cache_single()
            if child.get_state_set().contains(
                Atspi.StateType.DEFUNCT
            ) or parent.get_state_set().contains(Atspi.StateType.DEFUNCT):
                return False
            index = child.get_index_in_parent()
            if index < 0 or child.get_parent() != parent:
                return False
            if parent.get_child_at_index(index) != child:
                return False
            child.clear_cache_single()
            if child.get_parent() != parent:
                return False
        return True

    def navigation_panel_current(self, path, deadline):
        """Parent pointers alone do not prove membership after a replacement."""
        if not self.navigation_links_current(path, deadline):
            return False
        # AccessKit registers its application through the desktop socket, while
        # the application Accessible reports Parent=null and IndexInParent=-1.
        # Prove that boundary from the desktop's current children instead.
        desktop = Atspi.get_desktop(0)
        if desktop is None:
            return False
        desktop.clear_cache_single()
        if desktop.get_state_set().contains(Atspi.StateType.DEFUNCT):
            return False
        count = desktop.get_child_count()
        if count < 0:
            return False
        require(count <= BUDGETS["nodes"], "native node bound exceeded")
        matches = []
        for index in range(count):
            require(time.monotonic() < deadline, "navigation panel deadline expired")
            child = desktop.get_child_at_index(index)
            if child is None:
                return False
            child.clear_cache_single()
            if child.get_state_set().contains(Atspi.StateType.DEFUNCT):
                return False
            if child.get_process_id() == self.app.pid:
                matches.append((index, child))
        require(time.monotonic() < deadline, "navigation panel deadline expired")
        require(len(matches) <= 1, "nonunique native application registration")
        if not matches or matches[0][1] != path[-1]:
            return False
        desktop.clear_cache_single()
        if (
            desktop.get_state_set().contains(Atspi.StateType.DEFUNCT)
            or desktop.get_child_count() != count
            or desktop.get_child_at_index(matches[0][0]) != path[-1]
        ):
            return False
        path[-1].clear_cache_single()
        registered = (
            not path[-1].get_state_set().contains(Atspi.StateType.DEFUNCT)
            and path[-1].get_process_id() == self.app.pid
            and path[0].get_name() == "processes"
            and path[0].get_role_name() == "panel"
        )
        require(time.monotonic() < deadline, "navigation panel deadline expired")
        return registered

    def navigation_reveal_clip(self, scan, path, deadline):
        """Intersect the current rows viewport with its native ancestor/window clips."""
        require(len(scan["viewports"]) == 1, "nonunique navigation rows viewport")
        viewport = scan["viewports"][0]
        require(
            self.alive(viewport)
            and viewport.get_accessible_id() == "processes:rows-viewport"
            and viewport.get_role_name() == "panel",
            "invalid navigation rows viewport",
        )
        ancestry = [viewport]
        while ancestry[-1] != path[0]:
            require(time.monotonic() < deadline, "navigation reveal deadline expired")
            require(len(ancestry) < 40, "navigation reveal ancestry bound exceeded")
            parent = ancestry[-1].get_parent()
            if parent is None or parent in ancestry:
                raise IncompleteNativeTree("incomplete navigation viewport ancestry")
            ancestry.append(parent)
        if not self.navigation_links_current(ancestry, deadline):
            raise IncompleteNativeTree("incomplete navigation viewport membership")
        ancestors = self.ancestors(viewport)
        require(
            any(item["id"] == "workspace:viewport" for item in ancestors),
            "workspace clipping rectangle absent from native ancestry",
        )
        geometry = self.window().get_geometry()
        clips = [self.bounds(viewport), [0, 0, geometry.width, geometry.height]]
        clips.extend(
            item["bounds"]
            for item in ancestors
            if (item["id"] or "").endswith(":viewport")
        )
        require(
            all(
                bounds is not None and bounds[2] > 0 and bounds[3] > 0
                for bounds in clips
            ),
            "missing native clipping bounds",
        )
        left, top = max(b[0] for b in clips), max(b[1] for b in clips)
        right = min(b[0] + b[2] for b in clips)
        bottom = min(b[1] + b[3] for b in clips)
        require(
            right > left and bottom > top, "navigation viewport outside native clips"
        )
        if not self.navigation_links_current(ancestry, deadline):
            raise IncompleteNativeTree("replaced navigation viewport")
        require(time.monotonic() < deadline, "navigation reveal deadline expired")
        return left, top, right, bottom

    def navigation_selection(
        self,
        expected,
        target,
        deadline,
        reconcile=False,
        path=None,
        fresh_panel=False,
        endpoint_index=None,
        *,
        inspection=None,
        inspection_missing_row=False,
        pending=None,
    ):
        """Observe exact selection in a complete tree within one fresh publication."""
        from native_pending import (
            InterruptedNavigation,
            PriorSelectionPrefix,
            publication,
            valid_arrow_batch,
            validate_stat,
        )

        require(
            not inspection_missing_row or inspection is not None,
            "missing-row preparation requires inspection evidence",
        )
        if pending is not None:
            pending = json.loads(json.dumps(pending))
            require(
                not reconcile and inspection is None and expected != target,
                "pending interruption requires an intermediate arrow batch",
            )
            require(
                pending["expected"] == expected
                and pending["target"] == target
                and pending["endpoint_index"] == endpoint_index
                and pending["batch_deadline"] == deadline <= pending["deadline"]
                and type(endpoint_index) is int
                and endpoint_index >= 0
                and pending["publication"]["application_pid"] == self.app.pid
                and all(
                    type(pending["publication"].get(key)) is int
                    for key in (
                        "application_pid",
                        "sequence",
                        "render_revision",
                        "accepted_unix_ns",
                    )
                )
                and pending["baseline_completed"]
                <= pending["dispatch_started"]
                <= pending["dispatch_completed"]
                < deadline * 1e9
                and pending["actual_keys"] == pending["keys"]
                and valid_arrow_batch(pending["keys"]),
                "invalid frozen pending navigation batch",
            )
            require(
                validate_stat(
                    pending["baseline"],
                    expected,
                    pending["baseline_started"],
                    pending["baseline_completed"],
                )
                == "live",
                "pending navigation lacks matching independent baseline",
            )
        prior_selection = PriorSelectionPrefix(pending)
        reference_index = endpoint_index
        reveal_event = "navigation-endpoint-reveal"
        if inspection is not None:
            require(
                endpoint_index is None and expected == target,
                "inspection cannot use a keyboard endpoint",
            )
            require(isinstance(inspection, dict), "missing inspection evidence")
            # Copy caller-owned evidence once. Recovery never advances its reference.
            inspection = json.loads(json.dumps(inspection))
            for name in ("acknowledgement", "reference"):
                evidence = inspection.get(name)
                require(isinstance(evidence, dict), "missing inspection " + name)
                require(
                    evidence.get("target") == target,
                    "wrong inspection " + name + " target",
                )
                require(
                    type(evidence.get("index")) is int and evidence["index"] >= 0,
                    "missing inspection " + name + " index",
                )
                publication = evidence.get("publication")
                require(
                    isinstance(publication, dict)
                    and all(
                        type(publication.get(key)) is int
                        for key in (
                            "application_pid",
                            "sequence",
                            "render_revision",
                            "accepted_unix_ns",
                        )
                    )
                    and publication["application_pid"] == self.app.pid,
                    "missing or foreign inspection " + name + " publication",
                )
            reference_index = inspection["reference"]["index"]
            reveal_event = "inspection-row-reveal"
            fresh_panel = True
        recovery = None
        recovery_blocked = False
        recovery_blocked_at = None
        recovery_blocked_reason = None
        recovery_preparing = False
        recovery_proof = False
        recovery_started = False
        pending_preparing = False

        def observe(observation):
            nonlocal \
                path, \
                recovery, \
                recovery_blocked, \
                recovery_blocked_at, \
                recovery_blocked_reason, \
                recovery_preparing, \
                recovery_proof, \
                recovery_started, \
                pending_preparing
            observation.phase("initial publication")
            before = self.frame()
            prior_selection.publication(before)
            observation.publication("initial", before)
            require(
                target in map(identity, before["snapshot"]["processes"]),
                "navigation target absent: " + target,
            )
            retained, path = path, None
            discover_fresh = (
                pending_preparing
                or fresh_panel
                and not recovery_started
                or recovery_preparing
                or recovery_proof
            )
            observation.phase("retained panel validation")
            if (
                discover_fresh
                or retained is None
                or not observation.panel(
                    self.navigation_panel_current(retained, deadline), "retained"
                )
            ):
                retained = self.navigation_panel(deadline)
            observation.phase("panel validation before scan")
            if not observation.panel(
                self.navigation_panel_current(retained, deadline), "before scan"
            ):
                return observation.reject("invalid panel before selection")
            # Panel discovery may span collection intervals; bracket selection
            # itself with one fresh publication after discovery has completed.
            observation.phase("publication before selection")
            before = self.frame()
            prior_selection.publication(before)
            observation.publication("before selection", before)
            scan = {} if reference_index is not None else None
            try:
                selected = self.selected(
                    deadline,
                    strict=True,
                    panel=retained[0],
                    **({"scan": scan} if scan is not None else {}),
                )
            except BaseException:
                observation.partial_mapping(
                    scan.get("rows") if scan is not None else None,
                    before,
                )
                raise
            observation.phase("panel validation after scan")
            if not observation.panel(
                self.navigation_panel_current(retained, deadline), "after scan"
            ):
                return observation.reject("invalid panel after selection")
            observation.phase("selected link validation")
            if selected and not (
                self.alive(selected[1])
                and selected[1].get_accessible_id() == selected[0]
                and selected[1].get_state_set().contains(Atspi.StateType.SELECTED)
            ):
                # The complete scan and post-scan links still validate this panel
                # for pacing, even though the selected row must be observed again.
                path = retained if not discover_fresh else None
                return observation.reject("invalid selected link")
            observation.phase("publication after selection")
            after = self.frame()
            prior_selection.publication(after)
            observation.publication("after selection", after)
            ids = list(map(identity, after["snapshot"]["processes"]))
            require(target in ids, "navigation target absent: " + target)
            if (before["snapshot"]["sequence"], before["render_revision"]) != (
                after["snapshot"]["sequence"],
                after["render_revision"],
            ):
                path = retained if not discover_fresh else None
                return observation.reject("publication changed during selection")
            path = retained
            observed_prior = prior_selection.selection(
                selected[0] if selected else None
            )
            if pending is not None and expected not in ids:
                require(
                    selected is None, "selection transferred during pending navigation"
                )
                require(
                    len(ids) == len(set(ids)), "duplicate pending snapshot identity"
                )
                require(
                    not any(
                        value.split(":")[1] == expected.split(":")[1] for value in ids
                    ),
                    "pending snapshot PID reused",
                )
                require(
                    scan is not None
                    and len(scan["rows"]) == len(set(scan["rows"]))
                    and all(value in ids for value in scan["rows"]),
                    "pending native rows duplicate or outside current snapshot",
                )
                if not pending_preparing:
                    pending_preparing = True
                    path = None
                    return observation.reject("pending exit preparing fresh proof")
                observation.phase("independent terminal stat")
                terminal_started = time.monotonic_ns()
                require(
                    pending["dispatch_completed"] <= terminal_started,
                    "terminal navigation stat precedes dispatch",
                )
                terminal = self.navigation_stat(expected)
                terminal_completed = time.monotonic_ns()
                self.journal(
                    "navigation-terminal-stat",
                    expected=expected,
                    observation=terminal,
                    query_started_monotonic_ns=terminal_started,
                    query_completed_monotonic_ns=terminal_completed,
                )
                status = validate_stat(
                    terminal,
                    expected,
                    terminal_started,
                    terminal_completed,
                    baseline=pending["baseline"],
                )
                require(
                    status == "gone", "live pending endpoint omitted by application"
                )
                # Discovery may span collector publications. Bracket the fresh
                # strict eligibility scan only after global discovery completes;
                # the independently terminal stat remains prior evidence.
                if self.navigation_panel(deadline) != path:
                    path = None
                    return observation.reject("pending panel rediscovery changed")
                observation.phase("pending panel validation")
                if not observation.panel(
                    self.navigation_panel_current(path, deadline), "pending before scan"
                ):
                    path = None
                    return observation.reject("invalid panel before pending scan")
                observation.phase("publication before pending scan")
                current_before = self.frame()
                observation.publication("before pending scan", current_before)
                current_scan = {}
                try:
                    current_selection = self.selected(
                        deadline, strict=True, panel=path[0], scan=current_scan
                    )
                except BaseException:
                    observation.partial_mapping(
                        current_scan.get("rows"),
                        current_before,
                    )
                    raise
                observation.phase("publication after pending scan")
                current = self.frame()
                observation.publication("after pending scan", current)
                current_ids = list(map(identity, current["snapshot"]["processes"]))
                require(target in current_ids, "navigation target absent: " + target)
                if publication(current) != publication(current_before):
                    path = None
                    return observation.reject("publication changed during pending scan")
                observation.phase("pending panel validation after scan")
                if not observation.panel(
                    self.navigation_panel_current(path, deadline), "pending after scan"
                ):
                    path = None
                    return observation.reject("invalid panel after pending scan")
                require(
                    current_selection is None,
                    "selection transferred during pending navigation",
                )
                require(
                    expected not in current_ids,
                    "pending endpoint returned after terminal stat",
                )
                require(
                    len(current_ids) == len(set(current_ids)),
                    "duplicate pending snapshot identity",
                )
                require(
                    not any(
                        value.split(":")[1] == expected.split(":")[1]
                        for value in current_ids
                    ),
                    "pending snapshot PID reused",
                )
                require(
                    len(current_scan["rows"]) == len(set(current_scan["rows"]))
                    and all(value in current_ids for value in current_scan["rows"]),
                    "pending native rows duplicate or outside current snapshot",
                )
                observation.phase("final pending publication")
                final_pending = self.frame()
                observation.publication("final pending", final_pending)
                if publication(current) != publication(final_pending):
                    path = None
                    return observation.reject("publication changed after pending proof")
                require(
                    time.monotonic() < deadline, "pending navigation deadline expired"
                )
                evidence = {
                    "status": "interrupted-unverified",
                    "issue": pending,
                    "terminal": terminal,
                    "terminal_started": terminal_started,
                    "terminal_completed": terminal_completed,
                    "native": {
                        "publication": publication(current),
                        "identities": current_ids,
                        "instantiated_identities": current_scan["rows"],
                        "instantiated_selected": None,
                        "strict_complete_unique_current": True,
                    },
                }
                self.journal("navigation-batch-interrupted", **evidence)
                return InterruptedNavigation(current, path, evidence)
            if scan is not None:
                row_ids = scan["rows"]
                mapped = [ids.index(value) for value in row_ids if value in ids]
                complete_span = (
                    len(mapped) == len(row_ids)
                    and len(set(ids)) == len(ids)
                    and bool(mapped)
                    and mapped == list(range(mapped[0], mapped[-1] + 1))
                )
                observation.mapping(mapped, complete_span)
                observation.phase("reveal eligibility")
                if (
                    selected
                    and selected[0] != expected
                    and not observed_prior
                    or selected is None
                    and expected in row_ids
                ):
                    require(
                        inspection is None, "inspection selection changed without input"
                    )
                    if not recovery_blocked:
                        recovery_blocked_at = observation.number
                        recovery_blocked_reason = (
                            "competing instantiated selection"
                            if selected
                            else "expected row instantiated without selection"
                        )
                    recovery_blocked = True
                if (
                    recovery is None
                    and not recovery_blocked
                    and selected is None
                    and expected in ids
                    and complete_span
                    and not mapped[0] <= ids.index(expected) <= mapped[-1]
                    and ids.index(expected) != reference_index
                    and mapped[0] <= reference_index <= mapped[-1]
                ):
                    if not recovery_preparing and not inspection_missing_row:
                        # Establish uniqueness before the fresh eligibility scan
                        # that will authorize the first physical recovery step.
                        # Missing-row inspection already made that fresh strict
                        # discovery in this observation, before all guards above.
                        recovery_preparing = True
                        path = None
                        return observation.reject(
                            "recovery preparing fresh eligibility"
                        )
                    recovery = {
                        "expected": expected,
                        **(
                            {"original_index": endpoint_index}
                            if inspection is None
                            else {
                                "acknowledgement": inspection["acknowledgement"],
                                "reference": inspection["reference"],
                                "reference_index": reference_index,
                            }
                        ),
                        "eligibility_index": ids.index(expected),
                        "eligibility_span": [mapped[0], mapped[-1]],
                        "eligibility_sequence": after["snapshot"]["sequence"],
                        "eligibility_revision": after["render_revision"],
                    }
                    recovery_preparing = False
                if recovery is not None:
                    require(
                        expected in ids,
                        "navigation recovery endpoint absent: " + expected,
                    )
                    require(
                        selected is None or selected[0] == expected,
                        "selection changed during nonselecting navigation recovery",
                    )
                    if not complete_span or recovery_blocked:
                        return observation.reject(
                            "recovery blocked"
                            if recovery_blocked
                            else "incomplete mapped row span"
                        )
                    observation.phase("reveal clip discovery")
                    left, top, right, bottom = self.navigation_reveal_clip(
                        scan, path, deadline
                    )
                    bounds = self.bounds(selected[1]) if selected else None
                    observation.phase("publication before reveal")
                    current_frame = self.frame()
                    observation.publication("before reveal", current_frame)
                    if (
                        current_frame["snapshot"]["sequence"],
                        current_frame["render_revision"],
                    ) != (
                        after["snapshot"]["sequence"],
                        after["render_revision"],
                    ):
                        return observation.reject("publication changed before reveal")
                    observation.phase("panel validation before reveal")
                    if not observation.panel(
                        self.navigation_panel_current(path, deadline), "before reveal"
                    ):
                        return observation.reject("invalid panel before reveal")
                    require(
                        time.monotonic() < deadline,
                        "navigation reveal deadline expired",
                    )
                    if (
                        selected
                        and bounds[3] > 0
                        and top <= bounds[1]
                        and bounds[1] + bounds[3] <= bottom
                    ):
                        if not recovery_proof:
                            recovery_proof = True
                            path = None
                            return observation.reject("recovery preparing final proof")
                        self.journal(
                            reveal_event + "-proof",
                            **recovery,
                            **(
                                {
                                    "selected": selected[0],
                                    "publication": {
                                        "sequence": current_frame["snapshot"][
                                            "sequence"
                                        ],
                                        **{
                                            key: current_frame[key]
                                            for key in (
                                                "application_pid",
                                                "render_revision",
                                                "accepted_unix_ns",
                                            )
                                        },
                                    },
                                    "current_index": ids.index(expected),
                                    "current_span": [mapped[0], mapped[-1]],
                                    "deadline": deadline,
                                }
                                if inspection is not None
                                else {}
                            ),
                        )
                        return selected, current_frame, path
                    if selected:
                        down = bounds[1] + bounds[3] > bottom
                    elif ids.index(expected) < mapped[0]:
                        down = False
                    elif ids.index(expected) > mapped[-1]:
                        down = True
                    else:
                        return observation.reject(
                            "expected row in span without instantiated selection"
                        )
                    point = [(left + right) / 2, (top + bottom) / 2]
                    self.journal(
                        reveal_event,
                        **recovery,
                        current_index=ids.index(expected),
                        current_span=[mapped[0], mapped[-1]],
                        point=point,
                        down=down,
                        deadline=deadline,
                        action="nonselecting vertical wheel",
                    )
                    observation.phase("existing reveal wheel dispatch")
                    self.wheel(point, down=down, deadline=deadline)
                    recovery_started = True
                    recovery_proof = False
                    return observation.reject(
                        "recovery wheel dispatched; fresh proof required"
                    )
            if reconcile:
                require(
                    selected is None or selected[0] == expected,
                    f"process selection transferred without input: {expected} -> {selected}",
                )
                if expected not in ids:
                    # A complete scan with no instantiated selected row permits
                    # explicit boundary recovery; virtualization cannot prove model
                    # selection cleared automatically.
                    return (
                        (None, after, path)
                        if selected is None
                        else observation.reject(
                            "selected endpoint absent from publication"
                        )
                    )
            if selected and selected[0] == expected and expected in ids:
                return selected, after, path
            if selected:
                return observation.reject(
                    "competing instantiated selection"
                    if selected[0] != expected
                    else "selected endpoint absent from publication"
                )
            if scan is not None and not complete_span:
                return observation.reject("incomplete mapped row span")
            return observation.reject("no instantiated selection")

        def poll():
            nonlocal path, recovery, recovery_preparing
            with navigation_observation(
                self, "selection observation", deadline, expected, endpoint_index
            ) as observation:
                try:
                    result = observe(observation)
                    observation.outcome(
                        "interrupted-unverified"
                        if isinstance(result, InterruptedNavigation)
                        else "returned selection"
                        if result is not None and result[0] is not None
                        else "returned absence"
                        if result is not None
                        else "retry"
                    )
                    return result
                finally:
                    if recovery is not None and not recovery_started:
                        # A rejected pre-input observation is not permission to scroll
                        # later. Freeze eligibility only after dispatching a wheel step.
                        recovery = None
                        recovery_preparing = True
                        path = None
                    observation.recovery(
                        recovery_blocked,
                        recovery_preparing,
                        recovery_started,
                        recovery_proof,
                        recovery_blocked_at,
                        recovery_blocked_reason,
                    )

        result = self.wait(
            poll, message="selected " + expected, deadline=deadline, acknowledge=False
        )
        if not isinstance(result, InterruptedNavigation):
            if result[0] is not None:
                self.journal("ack", condition="selected " + expected)
            else:
                self.journal(
                    "navigation-absence",
                    expected=expected,
                    publication=publication(result[1]),
                    status="no instantiated selected identity",
                )
        require(
            time.monotonic() < deadline,
            "navigation outcome journal exceeded original deadline",
        )
        return result

    def navigate(self, target, *, on_acknowledged=None):
        deadline = time.monotonic() + 180
        self.navigation_context = {
            "target": target,
            "phase": "enter table",
            "original_deadline_monotonic": deadline,
            "last_acknowledged_identity": None,
        }
        self.navigation_observations = NavigationObservations(time, target, deadline)
        try:
            return self._navigate(target, deadline, on_acknowledged=on_acknowledged)
        except BaseException as error:
            context = dict(
                self.navigation_context,
                error=str(error),
                observed_monotonic=time.monotonic(),
            )
            try:
                context["observations"] = self.navigation_observations.snapshot()
                self.save(f"navigation-failure-{time.monotonic_ns()}.json", context)
            except BaseException as evidence_error:
                error.add_note(
                    "Navigation failure artifact: " + error_text(evidence_error)
                )
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"child navigation original180s deadline expired: {context}"
                ) from error
            raise
        finally:
            self.navigation_observations = None

    def navigation_stat(self, expected):
        from native_pending import read_stat

        return read_stat(expected, self.app.pid)

    def navigation_boundary(self, target, frame, path, batch_deadline, deadline):
        from native_pending import publication

        ids = list(map(identity, frame["snapshot"]["processes"]))
        require(target in ids, "navigation target absent: " + target)
        key = "Home" if ids.index(target) < len(ids) / 2 else "End"
        index = 0 if key == "Home" else len(ids) - 1
        self.journal(
            "navigation-boundary-recovery",
            target=target,
            expected=ids[index],
            endpoint_index=index,
            keys=[key],
            publication=publication(frame),
            batch_deadline=batch_deadline,
            deadline=deadline,
        )
        require(
            time.monotonic() < batch_deadline, "navigation original deadline expired"
        )
        self.key(key, deadline=batch_deadline)
        selected, observed, path = self.navigation_selection(
            ids[index], target, batch_deadline, path=path, endpoint_index=index
        )
        return selected, observed, path, index

    def _navigate(self, target, deadline, *, on_acknowledged=None):
        from native_pending import (
            MAX_ARROW_BATCH,
            InterruptedNavigation,
            capture_acknowledgement,
            prepare_prior_acknowledgement,
            publication,
            validate_stat,
        )

        self.enter_processes()
        batch_deadline = min(deadline, time.monotonic() + 8)
        path = self.wait(
            lambda: self.navigation_panel(batch_deadline),
            message="current navigation panel",
            deadline=batch_deadline,
        )
        rows = self.frame()["snapshot"]["processes"]
        ids = list(map(identity, rows))
        require(target in ids, "navigation target absent: " + target)
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
        require(
            time.monotonic() < batch_deadline, "navigation original deadline expired"
        )
        self.key(key)
        endpoint_index = 0 if key == "Home" else len(ids) - 1
        selected, observed, path = self.navigation_selection(
            ids[endpoint_index],
            target,
            batch_deadline,
            path=path,
            endpoint_index=endpoint_index,
        )
        acknowledgement = capture_acknowledgement(selected[0], observed)
        new_batch = True
        while True:
            self.navigation_context.update(
                last_acknowledged_identity=selected[0], phase="next batch"
            )
            if new_batch:
                batch_deadline = min(deadline, time.monotonic() + 8)
                new_batch = False
            require(
                time.monotonic() < batch_deadline,
                "navigation original deadline expired",
            )
            try:
                current = self.navigation_panel_current(path, batch_deadline) and (
                    self.alive(selected[1])
                    and selected[1].get_accessible_id() == selected[0]
                    and selected[1].get_state_set().contains(Atspi.StateType.SELECTED)
                )
            except (GLib.Error, AttributeError, TypeError):
                current = False
                path = None
            frame = self.frame()
            ids = list(map(identity, frame["snapshot"]["processes"]))
            require(target in ids, "navigation target absent: " + target)
            if (
                (frame["snapshot"]["sequence"], frame["render_revision"])
                != (observed["snapshot"]["sequence"], observed["render_revision"])
                or selected[0] not in ids
                or not current
            ):
                self.navigation_context["phase"] = "reconcile previous selection"
                # A positive ACK may observe the identity at a different index
                # from the issued key. Its recorded index is the last proven
                # viewport reference for subsequent passive snapshot changes.
                selected, frame, path = self.navigation_selection(
                    selected[0],
                    target,
                    batch_deadline,
                    reconcile=True,
                    path=None if selected[0] == target else path,
                    endpoint_index=(
                        acknowledgement["index"]
                        if acknowledgement is not None
                        else endpoint_index
                    ),
                )
                ids = list(map(identity, frame["snapshot"]["processes"]))
                if selected is None:
                    selected, observed, path, endpoint_index = self.navigation_boundary(
                        target, frame, path, batch_deadline, deadline
                    )
                    acknowledgement = capture_acknowledgement(selected[0], observed)
                    new_batch = True
                    continue
                acknowledgement = capture_acknowledgement(selected[0], frame)
            if selected[0] == target:
                # Intermediate acknowledgements pace input. Success independently
                # rediscovers the unique current panel and exact selected target.
                selected, acknowledged, _ = self.navigation_selection(
                    target,
                    target,
                    batch_deadline,
                    reconcile=True,
                    fresh_panel=True,
                    endpoint_index=endpoint_index,
                )
                if on_acknowledged is not None:
                    on_acknowledged(
                        {
                            "target": selected[0],
                            "index": list(
                                map(identity, acknowledged["snapshot"]["processes"])
                            ).index(target),
                            "publication": {
                                "sequence": acknowledged["snapshot"]["sequence"],
                                **{
                                    key: acknowledged[key]
                                    for key in (
                                        "application_pid",
                                        "render_revision",
                                        "accepted_unix_ns",
                                    )
                                },
                            },
                        }
                    )
                return selected
            delta = ids.index(target) - ids.index(selected[0])
            self.navigation_context.update(
                target_index=ids.index(target), population=len(ids), distance=abs(delta)
            )
            count = min(abs(delta), MAX_ARROW_BATCH if abs(delta) > 32 else 2)
            require(
                count > 0 and time.monotonic() < deadline,
                "navigation original deadline expired",
            )
            planned_index = ids.index(selected[0]) + (count if delta > 0 else -count)
            expected = ids[planned_index]
            keys = ["Down" if delta > 0 else "Up"] * count
            pending = None
            if expected != target:
                baseline_started = time.monotonic_ns()
                baseline = self.navigation_stat(expected)
                baseline_completed = time.monotonic_ns()
                self.journal(
                    "navigation-baseline-stat",
                    expected=expected,
                    observation=baseline,
                    query_started_monotonic_ns=baseline_started,
                    query_completed_monotonic_ns=baseline_completed,
                )
                status = validate_stat(
                    baseline, expected, baseline_started, baseline_completed
                )
                if status == "gone":
                    self.journal(
                        "navigation-predispatch-replan",
                        expected=expected,
                        endpoint_index=planned_index,
                        publication=publication(frame),
                        keys=keys,
                        baseline=baseline,
                        batch_deadline=batch_deadline,
                        deadline=deadline,
                        status="not dispatched",
                    )
                    require(
                        time.monotonic() < batch_deadline,
                        "navigation original deadline expired",
                    )
                    spin()
                    continue
                pending = {
                    "expected": expected,
                    "target": target,
                    "endpoint_index": planned_index,
                    "publication": publication(frame),
                    "keys": keys,
                    "batch_deadline": batch_deadline,
                    "deadline": deadline,
                    "baseline": baseline,
                    "baseline_started": baseline_started,
                    "baseline_completed": baseline_completed,
                    "actual_keys": [],
                }
                if acknowledgement is not None:
                    pending["issued_selection"] = acknowledgement["identity"]
                prior_acknowledgement = prepare_prior_acknowledgement(
                    acknowledgement, pending, ids
                )
                if prior_acknowledgement is not None:
                    pending["prior_acknowledgement"] = prior_acknowledgement
            self.journal(
                "navigation-batch",
                target=target,
                selected=selected[0],
                expected=expected,
                endpoint_index=planned_index,
                count=count,
                distance=abs(delta),
                sequence=frame["snapshot"]["sequence"],
                deadline=deadline,
                batch_deadline=batch_deadline,
                publication=publication(frame),
                keys=keys,
            )
            if pending is not None:
                pending["dispatch_started"] = time.monotonic_ns()
            for key in keys:
                require(
                    time.monotonic() < batch_deadline,
                    "navigation original deadline expired",
                )
                self.key(key, deadline=batch_deadline)
                if pending is not None:
                    pending["actual_keys"].append(key)
            endpoint_index = planned_index
            if pending is not None:
                pending["dispatch_completed"] = time.monotonic_ns()
                if "prior_acknowledgement" in pending:
                    pending["prior_acknowledgement"].update(
                        dispatch_started=pending["dispatch_started"],
                        dispatch_completed=pending["dispatch_completed"],
                    )
            result = self.navigation_selection(
                expected,
                target,
                batch_deadline,
                path=path,
                endpoint_index=endpoint_index,
                pending=pending,
            )
            if isinstance(result, InterruptedNavigation):
                selected, observed, path, endpoint_index = self.navigation_boundary(
                    target, result.frame, result.path, batch_deadline, deadline
                )
            else:
                selected, observed, path = result
            acknowledgement = capture_acknowledgement(selected[0], observed)
            new_batch = True

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
