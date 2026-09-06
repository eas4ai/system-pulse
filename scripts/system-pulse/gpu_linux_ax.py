#!/usr/bin/env python3
"""Bounded AT-SPI census/actions attached to one PID in a native X11 session."""

import argparse
import json
import os
import time

from gpu_intel_capture import anchor
from host_accuracy import require
from gpu_desktop import resolve_selector


def object_identity(node):
    # GetId is optional and can be zero for every node. AT-SPI object paths
    # identify distinct live objects within one application's transport.
    require(
        isinstance(node.path, str) and node.path.startswith("/"),
        "native object has no transport identity",
    )
    return node.get_process_id(), node.path


def main():
    import gi

    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi, GLib
    from Xlib import X, display, protocol
    from Xlib.ext import xtest

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("target", nargs="?")
    parser.add_argument("method", nargs="?", choices=("press", "scroll"))
    parser.add_argument("value", nargs="?", type=int)
    args = parser.parse_args()
    require(args.pid > 0, "invalid native PID")
    Atspi.init()
    Atspi.set_timeout(250, 250)
    clock = anchor()
    deadline = time.monotonic() + 15
    desktop = Atspi.get_desktop(0)
    roots = [desktop.get_child_at_index(n) for n in range(desktop.get_child_count())]
    roots = [r for r in roots if r and r.get_process_id() == args.pid]
    require(len(roots) == 1, "no unique native accessibility root for PID")

    def owned_window(d):
        windows = [
            w
            for w in d.screen().root.query_tree().children
            if (
                p := w.get_full_property(
                    d.intern_atom("_NET_WM_PID"), X.AnyPropertyType
                )
            )
            is not None
            and int(p.value[0]) == args.pid
        ]
        require(len(windows) == 1, "no unique PID-owned X11 window")
        return windows[0]

    d = display.Display()
    try:
        window = owned_window(d)
        geometry = window.get_geometry()
        position = d.screen().root.translate_coords(window, 0, 0)
        window_evidence = dict(
            id=window.id,
            pid=args.pid,
            geometry=dict(
                width=geometry.width,
                height=geometry.height,
                x=geometry.x,
                y=geometry.y,
                border_width=geometry.border_width,
            ),
            screen_position=dict(x=position.x, y=position.y),
            frame=[position.x, position.y, geometry.width, geometry.height],
        )
    finally:
        d.close()

    def census():
        nodes = {}
        elements = []
        stack = [(roots[0], window_evidence["frame"], 0, None)]
        visited = set()
        while stack:
            require(
                time.monotonic() < deadline and len(elements) < 30000,
                "native census bound exceeded",
            )
            node, clip, depth, parent = stack.pop()
            require(node is not None and depth < 64, "incomplete native tree")
            key = object_identity(node)
            require(key not in visited, "native accessibility cycle")
            visited.add(key)
            node.clear_cache()
            require(
                not node.get_state_set().contains(Atspi.StateType.DEFUNCT),
                "defunct native node",
            )
            identifier = node.get_accessible_id() or ""
            component = node.get_component_iface()
            bounds = None
            if component:
                r = component.get_extents(Atspi.CoordType.SCREEN)
                bounds = [r.x, r.y, r.width, r.height]
            role = node.get_role_name()
            if (
                bounds
                and bounds[2] > 0
                and bounds[3] > 0
                and role in ("frame", "window")
            ):
                clip = bounds
            bounds = bounds or [0, 0, 0, 0]
            elements.append(
                dict(
                    identifier=identifier,
                    role=role,
                    title=node.get_name(),
                    description=node.get_description() or "",
                    value="",
                    frame=bounds,
                    clip=clip,
                    object_key=node.path,
                    parent_key=parent,
                )
            )
            nodes[node.path] = node
            if identifier.endswith(":viewport"):
                x = max(clip[0], bounds[0])
                y = max(clip[1], bounds[1])
                clip = [
                    x,
                    y,
                    max(0, min(clip[0] + clip[2], bounds[0] + bounds[2]) - x),
                    max(0, min(clip[1] + clip[3], bounds[1] + bounds[3]) - y),
                ]
            monitor = os.environ.get("SYSTEM_PULSE_GPU_MONITOR_ID", "")
            if (
                monitor
                and identifier.endswith(":viewport")
                and identifier not in ("workspace:viewport", monitor + ":viewport")
            ):
                if bounds and elements:
                    elements[-1]["children_excluded"] = True
                continue
            count = node.get_child_count()
            require(0 <= count <= 30000, "incomplete native child count")
            for n in reversed(range(count)):
                stack.append((node.get_child_at_index(n), clip, depth + 1, node.path))
        return dict(
            complete=True,
            native_window=window_evidence,
            elements=elements,
            target_pid=args.pid,
            observer_pid=os.getpid(),
            observed_ns=time.monotonic_ns(),
            clock_anchor=clock,
            census_monitor=os.environ.get("SYSTEM_PULSE_GPU_MONITOR_ID", ""),
        ), nodes

    before, nodes = census()
    if args.target is None:
        print(json.dumps(before))
        return
    if args.target == "close":
        d = display.Display()
        try:
            w = owned_window(d)
            event = protocol.event.ClientMessage(
                window=w,
                client_type=d.intern_atom("WM_PROTOCOLS"),
                data=(32, [d.intern_atom("WM_DELETE_WINDOW"), X.CurrentTime, 0, 0, 0]),
            )
            w.send_event(event)
            d.sync()
            print(
                json.dumps(
                    dict(
                        target_pid=args.pid,
                        method="WM_DELETE_WINDOW",
                        return_code=0,
                        before=before,
                    )
                )
            )
        finally:
            d.close()
        return
    request = json.loads(args.target)
    row = resolve_selector(before["elements"], request["selector"])
    start = time.monotonic_ns()
    node = nodes[row["object_key"]]
    if args.method == "press":
        iface = node.get_action_iface()
        require(iface is not None, "native target lacks action interface")
        indices = [
            i
            for i in range(iface.get_n_actions())
            if iface.get_action_name(i) in ("click", "press", "activate")
        ]
        require(
            len(indices) == 1 and iface.do_action(indices[0]), "native press failed"
        )
        method = "ATSPIAction"
    else:
        require(
            args.method == "scroll" and args.value and -100 <= args.value <= 100,
            "invalid native scroll",
        )
        x, y, w, h = row["frame"]
        d = display.Display()
        try:
            xtest.fake_input(d, X.MotionNotify, x=int(x + w / 2), y=int(y + h / 2))
            for _ in range(abs(args.value)):
                button = 4 if args.value > 0 else 5
                xtest.fake_input(d, X.ButtonPress, button)
                xtest.fake_input(d, X.ButtonRelease, button)
            d.sync()
        finally:
            d.close()
        method = "XTestScroll"
    until = time.monotonic() + 0.5
    context = GLib.MainContext.default()
    while time.monotonic() < until:
        while context.pending():
            context.iteration(False)
        time.sleep(0.01)
    after, _ = census()
    print(
        json.dumps(
            dict(
                target=request["control"],
                selector=request["selector"],
                resolved_element=row,
                method=method,
                return_code=0,
                started_ns=start,
                finished_ns=time.monotonic_ns(),
                before=before,
                after=after,
            )
        )
    )


if __name__ == "__main__":
    main()
