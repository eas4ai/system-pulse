import copy
import unittest


class DesktopTests(unittest.TestCase):
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
