import copy
import unittest


def action_fixture():
    """All required native actions with one independently checked displayed value."""
    clock = dict(monotonic_before_ns=0, monotonic_after_ns=0, unix_ns=0)

    def row(key, parent, identifier, title, role="button", size=10):
        return dict(
            object_key=key,
            parent_key=parent,
            identifier=identifier,
            title=title,
            role=role,
            description="",
            value="",
            frame=[0, 0, size, size],
            clip=[0, 0, 100, 100],
        )

    field = dict(sensor_id="gpu/usage", unit="Percent", kind="Percentage")
    reading = dict(
        sensor_id="gpu/usage",
        value=50.0,
        total=None,
        reason=None,
        availability="Available",
        observations=[dict(captured_ns=0)],
    )
    label = "Intel GPU · Usage · 50.0 %"
    rendered = dict(
        monitor_id="gpu",
        sensor_id="gpu/usage",
        element_id="gpu:value:gpu/usage",
        label=label,
        sample=dict(
            value=50.0, total=None, reason=None, text="50.0", unit="%", status="current"
        ),
    )
    snapshot = dict(
        monitors=[
            dict(id="gpu", kind="Gpu", title="Intel GPU", summary_sensor_id="gpu/usage")
        ],
        sensors=[dict(id="gpu/usage", monitor_id="gpu", title="Usage", unit="Percent")],
        readings=[reading],
    )
    rows = [
        row("panel", None, "gpu", "gpu", "AXWindow", 100),
        row("panelcontrol", "panel", "", "Collapse Intel GPU"),
        row("viewport", "panel", "gpu:viewport", "viewport", "AXScrollArea", 100),
        row("sensorcontrol", "viewport", "", "Collapse Usage"),
        row("value", "viewport", "gpu:value:gpu/usage", label),
        row("metercontrol", "viewport", "", "Meter: Number"),
        row("timer", "panel", "timer", "10:00:00"),
        row("interval", "panel", "workspace:interval:500", "500 ms"),
    ]
    native = dict(
        complete=True,
        elements=rows,
        target_pid=1,
        observed_ns=100,
        clock_anchor=clock,
        census_monitor="gpu",
    )
    state = dict(
        interval_ms=1000,
        panels=dict(
            gpu=dict(
                collapsed=False,
                sensors={"gpu/usage": dict(collapsed=False, meter="number")},
            )
        ),
    )
    actions = []
    for name, target, selector, key, method in (
        (
            "panel-collapse",
            "gpu:collapse",
            dict(within="gpu", label="Collapse Intel GPU"),
            "panelcontrol",
            "AXPress",
        ),
        (
            "sensor-collapse",
            "gpu:row:gpu/usage",
            dict(within="gpu:viewport", label="Collapse Usage"),
            "sensorcontrol",
            "AXPress",
        ),
        (
            "scroll",
            "gpu:viewport",
            dict(identifier="gpu:viewport"),
            "viewport",
            "CGEventScroll",
        ),
        (
            "interval",
            "workspace:interval:500",
            dict(identifier="workspace:interval:500"),
            "interval",
            "AXPress",
        ),
        (
            "meter",
            "gpu:meter:gpu/usage",
            dict(
                within="gpu:viewport",
                label="Meter: Number",
                after="gpu:value:gpu/usage",
            ),
            "metercontrol",
            "AXPress",
        ),
        ("restore", "", {}, None, "restart"),
    ):
        action = dict(
            name=name,
            target=target,
            selector=selector,
            method=method,
            return_code=0,
            started_ns=101,
            finished_ns=103,
            before=copy.deepcopy(native),
            after=copy.deepcopy(native),
            state_before=copy.deepcopy(state),
            state_after=copy.deepcopy(state),
        )
        action["after"]["observed_ns"] = 102
        if key:
            action["resolved_element"] = next(
                e for e in action["before"]["elements"] if e["object_key"] == key
            )
        by_key = {e["object_key"]: e for e in action["after"]["elements"]}
        if name != "restore":
            by_key["timer"]["title"] = "10:00:01"
        if name == "panel-collapse":
            action["state_after"]["panels"]["gpu"]["collapsed"] = True
            by_key[key]["title"] = "Expand Intel GPU"
        elif name == "sensor-collapse":
            action["state_after"]["panels"]["gpu"]["sensors"]["gpu/usage"][
                "collapsed"
            ] = True
            by_key[key]["title"] = "Expand Usage"
        elif name == "scroll":
            by_key["value"]["frame"] = [1, 0, 10, 10]
        elif name == "interval":
            action["state_after"]["interval_ms"] = 500
        elif name == "meter":
            action["state_after"]["panels"]["gpu"]["sensors"]["gpu/usage"]["meter"] = (
                "bar"
            )
            by_key[key]["title"] = "Meter: Bar"
        else:
            action["after"]["target_pid"] = 2
        actions.append(action)
    diagnostics = [
        dict(
            snapshot=snapshot,
            rendered_at_collector_ms=0,
            rendered=[rendered],
            application_pid=pid,
            accepted_unix_ns=90,
        )
        for pid in (1, 2)
    ]
    return (
        actions,
        diagnostics,
        dict(freshness_ns=100, device=dict(monitor_id="gpu"), fields=[field]),
    )


class DesktopTests(unittest.TestCase):
    def test_same_name_gpu_labels_keep_full_identity_across_reordering(self):
        from gpu_desktop import expected_gpu_label

        _, diagnostics, _ = action_fixture()
        frame = copy.deepcopy(diagnostics[0])
        entry = copy.deepcopy(frame["rendered"][0])
        first = frame["snapshot"]["monitors"][0]
        second = dict(first, id="gpu-second-physical-id")
        frame["snapshot"]["monitors"].append(second)
        for order in ([first, second], [second, first]):
            frame["snapshot"]["monitors"] = order
            for element_id, label in (
                ("gpu:value:gpu/usage", "Intel GPU · gpu · Usage · 50.0 %"),
                ("gpu:summary", "Intel GPU · gpu · 50.0 %"),
            ):
                selected = dict(entry, element_id=element_id, label=label)
                with self.subTest(order=order[0]["id"], element=element_id):
                    self.assertEqual(expected_gpu_label(frame, selected, 1000), label)
                wrong = dict(
                    selected,
                    label=label.replace(" · gpu · ", " · gpu-second-physical-id · "),
                )
                with self.assertRaises(AssertionError):
                    expected_gpu_label(frame, wrong, 1000)
        frame["snapshot"]["monitors"] = [first]
        self.assertEqual(expected_gpu_label(frame, entry, 1000), entry["label"])

    def test_sensor_collapse_requires_its_corresponding_native_effect(self):
        from gpu_evidence import validate_actions

        actions, diagnostics, policy = action_fixture()
        validate_actions(actions, diagnostics, policy)
        for replacement in (
            "Collapse Usage",
            "unrelated timer update",
            "Expand Other GPU",
        ):
            changed = copy.deepcopy(actions)
            sensor = next(a for a in changed if a["name"] == "sensor-collapse")
            next(
                e
                for e in sensor["after"]["elements"]
                if e["object_key"] == "sensorcontrol"
            )["title"] = replacement
            with self.subTest(label=replacement), self.assertRaises(AssertionError):
                validate_actions(changed, diagnostics, policy)
        changed = copy.deepcopy(actions)
        sensor = next(a for a in changed if a["name"] == "sensor-collapse")
        next(
            e for e in sensor["after"]["elements"] if e["object_key"] == "sensorcontrol"
        )["object_key"] = "another-native-object"
        with self.assertRaises(AssertionError):
            validate_actions(changed, diagnostics, policy)

    def test_scoped_selector_preserves_empty_native_id_and_rejects_ambiguity(self):
        from gpu_desktop import resolve_selector

        def row(key, parent, identifier="", title=""):
            return dict(
                object_key=key,
                parent_key=parent,
                identifier=identifier,
                title=title,
                description="",
                value="",
                frame=[0, 0, 10, 10],
                clip=[0, 0, 100, 100],
            )

        rows = [
            row("w", None, "window"),
            row("g", "w", title="gpu"),
            row("v", "g", "gpu:viewport"),
            row("s1", "v", "gpu:value:one"),
            row("m1", "v", title="Meter: Number"),
            row("s2", "v", "gpu:value:two"),
            row("m2", "v", title="Meter: Number"),
        ]
        selector = dict(
            within="gpu:viewport", label="Meter: Number", after="gpu:value:one"
        )
        selected = resolve_selector(rows, selector)
        self.assertEqual(selected["object_key"], "m1")
        self.assertEqual(selected["identifier"], "")
        with self.assertRaises(AssertionError):
            resolve_selector(rows, dict(within="gpu:viewport", label="Meter: Number"))
        with self.assertRaises(AssertionError):
            resolve_selector(rows, dict(selector, after="missing"))
        with self.assertRaises(AssertionError):
            resolve_selector(rows, dict(selector, within="other-gpu"))
        rows.insert(5, row("duplicate", "v", title="Meter: Number"))
        with self.assertRaises(AssertionError):
            resolve_selector(rows, selector)

    def test_window_clipping_replays_native_queries_and_ancestry(self):
        from gpu_desktop import validate_native_geometry

        window = dict(
            id=42,
            pid=15,
            geometry=dict(width=100, height=100, x=0, y=0, border_width=0),
            screen_position=dict(x=20, y=30),
            frame=[20, 30, 100, 100],
        )
        root = dict(
            object_key="a",
            parent_key=None,
            identifier="",
            role="application",
            frame=[0, 0, 0, 0],
            clip=[20, 30, 100, 100],
        )
        view = dict(
            object_key="v",
            parent_key="a",
            identifier="gpu:viewport",
            role="panel",
            frame=[20, 40, 90, 50],
            clip=[20, 30, 100, 100],
        )
        leaf = dict(
            object_key="b",
            parent_key="v",
            identifier="",
            role="button",
            frame=[30, 50, 10, 10],
            clip=[20, 40, 90, 50],
        )
        frame = dict(target_pid=15, native_window=window, elements=[root, view, leaf])
        validate_native_geometry(frame)
        offscreen = copy.deepcopy(frame)
        offscreen["elements"][1]["frame"] = [20, 140, 90, 50]
        offscreen["elements"][2]["clip"] = [20, 140, 90, 0]
        validate_native_geometry(offscreen)
        for change in ("pid", "raw_width", "clip"):
            bad = copy.deepcopy(frame)
            if change == "pid":
                bad["native_window"]["pid"] = 16
            elif change == "raw_width":
                bad["native_window"]["geometry"]["width"] = 200
            else:
                bad["elements"][-1]["clip"] = [0, 0, 1000, 1000]
            with self.subTest(change=change), self.assertRaises(AssertionError):
                validate_native_geometry(bad)

    def test_labels_require_consumed_quantity_and_fresh_visible_native_text(self):
        import gpu_desktop

        sensor = dict(id="gpu/shared", title="Shared allocated", unit="Bytes")
        reading = dict(
            sensor_id="gpu/shared",
            value=4096.0,
            total=None,
            availability="Available",
            reason=None,
            observations=[dict(captured_ns=1_000_000_000)],
        )
        entry = dict(
            monitor_id="gpu",
            sensor_id="gpu/shared",
            element_id="gpu:value:gpu/shared",
            label="GPU · Shared allocated · 4.0 KiB",
            sample=dict(
                value=4096.0,
                total=None,
                text="4.0",
                unit="KiB",
                status="current",
                reason=None,
            ),
        )
        frame = dict(
            rendered_at_collector_ms=1000,
            snapshot=dict(
                monitors=[dict(id="gpu", title="GPU")],
                sensors=[sensor],
                readings=[reading],
            ),
        )
        self.assertEqual(
            gpu_desktop.expected_gpu_label(frame, entry, 1000), entry["label"]
        )
        for key, value in [
            ("value", 8192.0),
            ("total", 8192.0),
            ("text", "4.1"),
            ("status", "stale"),
        ]:
            changed = copy.deepcopy(entry)
            changed["sample"][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                gpu_desktop.expected_gpu_label(frame, changed, 1000)

    def test_transport_identity_is_distinct_from_optional_application_id(self):
        import gpu_linux_ax
        from types import SimpleNamespace

        self.assertTrue(
            hasattr(gpu_linux_ax, "object_identity"),
            "native transport identity missing",
        )
        a = SimpleNamespace(path="/node/1", get_process_id=lambda: 10, get_id=lambda: 0)
        b = SimpleNamespace(path="/node/2", get_process_id=lambda: 10, get_id=lambda: 0)
        self.assertNotEqual(
            gpu_linux_ax.object_identity(a), gpu_linux_ax.object_identity(b)
        )
        b.path = None
        with self.assertRaises(AssertionError):
            gpu_linux_ax.object_identity(b)

    def test_independent_native_clock_origins_map_by_anchors(self):
        from gpu_desktop import anchored_time

        a = dict(monotonic_before_ns=10, monotonic_after_ns=12, unix_ns=1000)
        b = dict(monotonic_before_ns=10010, monotonic_after_ns=10012, unix_ns=1000)
        self.assertEqual(anchored_time(20, a), anchored_time(10020, b))
        with self.assertRaises(AssertionError):
            anchored_time(20, dict(a, monotonic_before_ns=13))

    def test_action_semantics_reject_unrelated_live_value_change(self):
        import gpu_desktop

        element = dict(
            identifier="",
            object_key="button",
            parent_key="panel",
            frame=[0, 0, 10, 10],
            clip=[0, 0, 100, 100],
            title="Collapse GPU",
        )
        scope = dict(element, object_key="panel", parent_key=None, title="gpu")
        native = dict(
            complete=True, target_pid=15, observed_ns=100, elements=[element, scope]
        )
        state = dict(
            interval_ms=1000, panels=dict(gpu=dict(collapsed=False, sensors={}))
        )
        action = dict(
            name="panel-collapse",
            method="AXPress",
            target="gpu:collapse",
            selector=dict(within="gpu", label="Collapse GPU"),
            resolved_element=element,
            return_code=0,
            started_ns=101,
            finished_ns=103,
            before=native,
            after=copy.deepcopy(native),
            state_before=state,
            state_after=copy.deepcopy(state),
        )
        action["after"]["observed_ns"] = 103
        action["after"]["elements"][0]["title"] = "live value updated"
        policy = dict(freshness_ns=100, device=dict(monitor_id="gpu"), fields=[])
        with self.assertRaises(AssertionError):
            gpu_desktop.action_effect(action, policy)
        action["state_after"]["panels"]["gpu"]["collapsed"] = True
        action["after"]["elements"][0]["title"] = "Expand GPU"
        gpu_desktop.action_effect(action, policy)


if __name__ == "__main__":
    unittest.main()
