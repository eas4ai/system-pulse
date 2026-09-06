"""Exercise the real navigation protocol without a host process or native session."""

from contextlib import nullcontext
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from test_native_exit import Clock, Node, native_class


def aid(pid, start=100):
    return f"process:{pid}:{start}"


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.clock.monotonic_ns = lambda: int(self.clock.now * 1e9)
        self.clock.time_ns = self.clock.monotonic_ns
        native, _ = native_class(self.clock)
        native.frame.__globals__["os"] = SimpleNamespace(
            fstat=lambda descriptor: SimpleNamespace(st_dev=1, st_ino=1)
        )
        native.selected.__globals__["Atspi"].StateType.SELECTED = "selected"
        self.native = native.__new__(native)
        self.native.app = Mock(pid=500)
        self.native.app.poll.return_value = None
        self.native.interval_ms = 1000
        self.native.save = Mock()
        self.native.enter_processes = Mock()
        self.native.journal = self.journal
        self.native.key = self.key
        self.native.navigation_stat = self.stat
        self.native.latest = SimpleNamespace(
            open=lambda: nullcontext(
                SimpleNamespace(read=self.frame_text, fileno=lambda: 0)
            ),
            stat=lambda: SimpleNamespace(st_dev=1, st_ino=1),
        )
        self.ids = [aid(pid) for pid in range(20)]
        self.target = aid(6)
        self.selection = None
        self.pending = None
        self.ack_delay = 0.5
        self.sequence = 1
        self.revision = 1
        self.stale = False
        self.events = []
        self.after_ack = lambda identity: None
        self.before_frame = lambda: None
        self.before_children = lambda: None
        self.nodes = {identity: self.row(identity) for identity in self.ids}
        self.panel = Node(self.clock, name="processes", children=self.children)
        self.root = Node(self.clock, role="application", children=lambda: [self.panel])
        self.desktop = Node(self.clock, children=lambda: [self.root])
        native.selected.__globals__["Atspi"].get_desktop = lambda index: self.desktop
        # The pinned AccessKit application is registered with the desktop socket,
        # but its own Accessible Parent is null and GetIndexInParent is -1.
        self.root.get_parent = lambda: None
        self.root.get_index_in_parent = lambda: -1
        self.root.get_process_id = lambda: 500
        self.desktop.clear_cache_single = lambda: None
        self.root.clear_cache_single = lambda: None
        self.panel.clear_cache_single = lambda: None
        self.panel.get_parent = lambda: self.root
        self.panel.get_index_in_parent = lambda: 0
        self.native.root = Mock(return_value=self.root)
        self.native.cache = {"__panel:processes": self.panel}

    def stat(self, expected):
        pid, start = map(int, expected.split(":")[1:])
        fields = ["S"] + ["0"] * 21
        fields[19] = str(start)
        raw = f"{pid} (synthetic fixture) " + " ".join(fields) + "\n"
        gone = expected not in self.ids
        return {
            "source": f"/proc/{pid}/stat",
            "raw": None if gone else raw,
            "identity": None if gone else expected,
            "errno": 2 if gone else None,
            "start": self.clock.monotonic_ns(),
            "end": self.clock.monotonic_ns(),
            "namespace": {
                "device": 1,
                "inode": 2,
                "pid_namespace": "pid:[1]",
                "application_pid_namespace": "pid:[1]",
            },
        }

    def row(self, identity):
        node = Node(self.clock, identity, role="table row")

        def states():
            self.publish_selection()
            return SimpleNamespace(
                contains=lambda state: node.defunct
                if state == "defunct"
                else identity in (self.selection or [])
            )

        node.get_state_set = states
        node.get_child_count = Mock(side_effect=AssertionError("visited process cells"))
        return node

    def children(self):
        self.before_children()
        return list(self.nodes.values())

    def publish_selection(self):
        if self.pending and self.clock.now >= self.pending[0]:
            self.selection = [self.pending[1]]
            self.pending = None

    def frame_text(self):
        self.before_frame()
        return json.dumps(
            {
                "application_pid": 500,
                "accepted_unix_ns": int(
                    (self.clock.now - (3 if self.stale else 0)) * 1e9
                ),
                "render_revision": self.revision,
                "snapshot": {
                    "sequence": self.sequence,
                    "processes": [
                        {
                            "identity": {
                                "pid": int(i.split(":")[1]),
                                "start_time_ticks": int(i.split(":")[2]),
                            }
                        }
                        for i in self.ids
                    ],
                },
            }
        )

    def key(self, key, *, deadline=None):
        self.publish_selection()
        # Two keys in a batch are allowed; another batch must wait for its ACK.
        before = self.pending[1] if self.pending else (self.selection or [None])[0]
        if key == "Home":
            after = self.ids[0]
        elif key == "End":
            after = self.ids[-1]
        else:
            after = self.ids[self.ids.index(before) + (1 if key == "Down" else -1)]
        self.pending = (self.clock.now + self.ack_delay, after)
        self.events.append(("key", key, self.clock.now))

    def journal(self, event, **fields):
        self.events.append((event, fields, self.clock.now))
        if event == "ack" and fields["condition"].startswith("selected process:"):
            self.after_ack(fields["condition"].removeprefix("selected "))

    def navigate(self):
        return self.native.navigate(self.target)

    def application_membership(self, deadline=8):
        return self.native.navigation_panel_current([self.panel, self.root], deadline)

    def pacing_observation(self):
        return self.native.navigation_selection(
            aid(2), self.target, 8, path=[self.panel, self.root]
        )

    def displaced_endpoint(self):
        """The key's slot 5 stays onscreen while its exact identity shifts to 2."""
        self.endpoint = aid(5)
        self.ids.remove(self.endpoint)
        self.ids.insert(2, self.endpoint)
        self.selection = [self.endpoint]
        self.visible_ids = self.ids[5:8]
        self.viewport = Node(
            self.clock,
            "processes:rows-viewport",
            children=lambda: [self.nodes[value] for value in self.visible_ids],
        )
        self.viewport.get_parent = lambda: self.panel
        self.viewport.get_index_in_parent = lambda: 0
        self.panel.children = lambda: [self.viewport]
        self.native.window = Mock(
            return_value=SimpleNamespace(
                get_geometry=lambda: SimpleNamespace(width=800, height=600)
            )
        )
        self.native.ancestors = Mock(
            return_value=[
                {"id": "workspace:viewport", "bounds": [0, 220, 800, 350]},
                {"id": "processes:viewport", "bounds": [100, 200, 600, 300]},
            ]
        )
        self.row_bounds = [100, 230, 1200, 20]
        self.native.bounds = Mock(
            side_effect=lambda node: [100, 200, 600, 300]
            if node == self.viewport
            else self.row_bounds
        )
        self.native.wheel = Mock(side_effect=self.reveal_wheel)
        self.native.navigation_panel = Mock(wraps=self.native.navigation_panel)

    def reveal_wheel(self, point, down, *, deadline=None):
        self.events.append(("reveal-wheel", {"point": point, "down": down}))
        self.visible_ids = self.ids[2:6]

    def observe_displaced(self, original_index=5, deadline=8):
        return self.native.navigation_selection(
            self.endpoint,
            self.target,
            deadline,
            path=[self.panel, self.root],
            endpoint_index=original_index,
        )

    def physical_wheel(self, on_input=None):
        """Run the real wheel method with only the XTest transport replaced."""
        self.native.__dict__.pop("wheel", None)
        self.native.d = Mock()
        self.physical_inputs = []

        def fake_input(display, event, *args, **kwargs):
            self.assertIs(display, self.native.d)
            self.physical_inputs.append((event, args, kwargs, self.clock.now))
            if on_input:
                on_input(event)

        self.native.wheel.__globals__.update(
            X=SimpleNamespace(
                MotionNotify="motion", ButtonPress="press", ButtonRelease="release"
            ),
            xtest=SimpleNamespace(fake_input=fake_input),
        )

    def test_reveal_slow_journal_prevents_physical_dispatch(self):
        for event in ("navigation-endpoint-reveal", "wheel"):
            for delay in (7.75, 8):
                with self.subTest(event=event, delay=delay):
                    self.setUp()
                    self.displaced_endpoint()
                    self.physical_wheel()

                    def slow_journal(name, **fields):
                        self.journal(name, **fields)
                        if name == event:
                            self.clock.now += delay

                    self.native.journal = slow_journal
                    with self.assertRaises((TimeoutError, AssertionError)):
                        self.observe_displaced()
                    self.assertTrue(any(e[0] == event for e in self.events))
                    self.assertEqual(self.physical_inputs, [])
                    self.native.d.sync.assert_not_called()

    def test_reveal_physical_dispatch_under_deadline_finishes_fresh_proof(self):
        self.displaced_endpoint()
        self.physical_wheel(
            lambda event: self.reveal_wheel([400, 360], False)
            if event == "release"
            else None
        )

        def slow_journal(event, **fields):
            self.journal(event, **fields)
            if event in ("navigation-endpoint-reveal", "wheel"):
                self.clock.now += 3

        self.native.journal = slow_journal
        self.assertEqual(self.observe_displaced()[0][0], self.endpoint)
        self.assertEqual(
            self.physical_inputs,
            [
                ("motion", (), {"x": 400, "y": 360}, 6.25),
                ("press", (4,), {}, 6.25),
                ("release", (4,), {}, 6.25),
            ],
        )
        self.native.d.sync.assert_called_once_with()
        self.assertEqual(self.selection, [self.endpoint])
        self.assertEqual(self.native.navigation_panel.call_count, 2)
        self.assertTrue(
            any(e[0] == "navigation-endpoint-reveal-proof" for e in self.events)
        )
        self.assertLess(self.clock.now, 8)

    def test_reveal_releases_pressed_wheel_if_dispatch_consumes_deadline(self):
        self.displaced_endpoint()
        self.physical_wheel(
            lambda event: setattr(self.clock, "now", self.clock.now + 8)
            if event == "press"
            else None
        )
        with self.assertRaises(TimeoutError):
            self.observe_displaced()
        self.assertEqual(
            [item[0] for item in self.physical_inputs], ["motion", "press", "release"]
        )
        self.assertLess(self.physical_inputs[1][3], 8)
        self.assertGreaterEqual(self.physical_inputs[2][3], 8)
        self.native.d.sync.assert_called_once_with()

    def test_generic_wheel_keeps_unbounded_dispatch_and_release(self):
        for down, button in ((False, 4), (True, 5)):
            with self.subTest(down=down):
                self.setUp()
                self.physical_wheel()
                self.clock.now = 200
                self.native.wheel([12.9, 34.8], down)
                self.assertEqual(
                    self.physical_inputs,
                    [
                        ("motion", (), {"x": 12, "y": 34}, 200),
                        ("press", (button,), {}, 200),
                        ("release", (button,), {}, 200),
                    ],
                )
                self.assertEqual(
                    self.events,
                    [("wheel", {"point": [12.9, 34.8], "down": down, "count": 1}, 200)],
                )
                self.native.d.sync.assert_called_once_with()

    def test_displaced_endpoint_reveal_preserves_identity_and_fresh_unique_proof(self):
        self.displaced_endpoint()
        result, _, _ = self.observe_displaced()
        self.assertEqual(result[0], self.endpoint)
        self.assertEqual(self.selection, [self.endpoint])
        self.assertFalse(any(event[0] == "key" for event in self.events))
        self.native.wheel.assert_called_once_with([400, 360], down=False, deadline=8)
        self.assertEqual(self.native.navigation_panel.call_count, 2)
        self.assertTrue(
            all(
                call.args == (8,)
                for call in self.native.navigation_panel.call_args_list
            )
        )
        recovery = next(
            e[1] for e in self.events if e[0] == "navigation-endpoint-reveal"
        )
        self.assertEqual(recovery["original_index"], 5)
        self.assertEqual(recovery["eligibility_index"], 2)
        self.assertEqual(recovery["eligibility_span"], [5, 7])
        self.assertLess(self.clock.now, 8)

    def test_reveal_rejects_unchanged_index_and_original_slot_outside_span(self):
        for original in (2, 4, 8):
            with self.subTest(original=original):
                self.setUp()
                self.displaced_endpoint()
                with self.assertRaises(TimeoutError):
                    self.observe_displaced(original)
                self.native.wheel.assert_not_called()

    def test_reveal_rejects_visible_unselected_or_foreign_selected_endpoint(self):
        for foreign in (False, True):
            with self.subTest(foreign=foreign):
                self.setUp()
                self.displaced_endpoint()
                if foreign:
                    self.selection = [self.visible_ids[0]]
                else:
                    self.visible_ids = self.ids[2:6]
                    self.selection = None
                with self.assertRaises(TimeoutError):
                    self.observe_displaced()
                self.native.wheel.assert_not_called()

    def test_reveal_rejects_missing_reused_target_or_endpoint_identity(self):
        for removed in (aid(5), self.target):
            with self.subTest(removed=removed):
                self.setUp()
                self.displaced_endpoint()
                self.ids[self.ids.index(removed)] = removed.rsplit(":", 1)[0] + ":101"
                self.visible_ids = [
                    value for value in self.visible_ids if value != removed
                ]
                with self.assertRaises((TimeoutError, AssertionError)):
                    self.observe_displaced()
                self.native.wheel.assert_not_called()

    def test_reveal_rejects_empty_duplicate_unmapped_or_noncontiguous_span(self):
        for span in ([], [aid(4), aid(4)], [aid(4), aid(7)], [aid(40)]):
            with self.subTest(span=span):
                self.setUp()
                self.displaced_endpoint()
                self.nodes[aid(40)] = self.row(aid(40))
                self.visible_ids = span
                with self.assertRaises((TimeoutError, AssertionError)):
                    self.observe_displaced()
                self.native.wheel.assert_not_called()

    def test_reveal_rejects_incomplete_scan_and_invalid_current_membership(self):
        for incomplete in (True, False):
            with self.subTest(incomplete=incomplete):
                self.setUp()
                self.displaced_endpoint()
                if incomplete:
                    self.viewport.get_child_at_index = lambda index: None
                else:
                    self.panel.get_parent = lambda: None
                with self.assertRaises(TimeoutError):
                    self.observe_displaced()
                self.native.wheel.assert_not_called()

    def test_reveal_rejects_stale_or_changing_frame(self):
        for stale in (True, False):
            with self.subTest(stale=stale):
                self.setUp()
                self.displaced_endpoint()
                self.stale = stale
                if not stale:
                    self.before_frame = lambda: setattr(
                        self, "sequence", self.sequence + 1
                    )
                with self.assertRaises((TimeoutError, AssertionError)):
                    self.observe_displaced()
                self.native.wheel.assert_not_called()

    def test_reveal_requires_clips_and_live_viewport_membership(self):
        for invalid in ("workspace", "offscreen", "detached", "duplicate"):
            with self.subTest(invalid=invalid):
                self.setUp()
                self.displaced_endpoint()
                if invalid == "workspace":
                    self.native.ancestors.return_value = []
                elif invalid == "offscreen":
                    self.native.ancestors.return_value[0]["bounds"] = [900, 900, 1, 1]
                elif invalid == "detached":
                    self.viewport.get_parent = lambda: None
                else:
                    extra = Node(self.clock, "processes:rows-viewport")
                    self.panel.children = lambda: [self.viewport, extra]
                with self.assertRaises((TimeoutError, AssertionError)):
                    self.observe_displaced()
                self.native.wheel.assert_not_called()

    def test_reveal_slow_geometry_or_action_cannot_extend_original_deadline(self):
        for operation in ("bounds", "wheel"):
            with self.subTest(operation=operation):
                self.setUp()
                self.displaced_endpoint()
                original = getattr(self.native, operation).side_effect

                def slow(*args, **kwargs):
                    self.clock.now += 8
                    return original(*args, **kwargs)

                getattr(self.native, operation).side_effect = slow
                with self.assertRaises((TimeoutError, AssertionError)):
                    self.observe_displaced()
                if operation == "bounds":
                    self.native.wheel.assert_not_called()
                else:
                    self.native.wheel.assert_called_once()

    def test_reveal_fractional_vertical_visibility_uses_same_eligibility_record(self):
        self.displaced_endpoint()
        steps = 0

        def fractional(point, down, *, deadline):
            nonlocal steps
            steps += 1
            self.visible_ids = self.ids[
                1:4
            ]  # Original slot is now outside our scrolled span.
            self.row_bounds[1] = 210 if steps == 1 else 230

        self.native.wheel.side_effect = fractional
        self.assertEqual(self.observe_displaced()[0][0], self.endpoint)
        self.assertEqual(steps, 2)
        records = [e[1] for e in self.events if e[0] == "navigation-endpoint-reveal"]
        self.assertTrue(all(record["eligibility_span"] == [5, 7] for record in records))

    def test_reveal_cannot_accept_selection_transfer_or_duplicate_panel_after_scroll(
        self,
    ):
        for invalid in ("selection", "panel"):
            with self.subTest(invalid=invalid):
                self.setUp()
                self.displaced_endpoint()

                def changed(point, down, *, deadline):
                    self.reveal_wheel(point, down)
                    if invalid == "selection":
                        self.selection = [self.visible_ids[0], self.visible_ids[1]]
                    else:
                        extra = Node(self.clock, name="processes")
                        self.root.children = lambda: [self.panel, extra]

                self.native.wheel.side_effect = changed
                with self.assertRaises(AssertionError):
                    self.observe_displaced()
                self.native.wheel.assert_called_once()

    def test_reveal_actual_key_batch_keeps_issue_snapshot_index(self):
        self.displaced_endpoint()
        self.ids = [aid(pid) for pid in range(20)]
        self.visible_ids = list(self.ids)
        self.selection = None
        self.target = aid(2)
        key = self.native.key

        def moved(value, **kwargs):
            key(value, **kwargs)
            if self.pending[1] == self.target:
                self.ids.remove(self.target)
                self.ids.insert(0, self.target)
                self.visible_ids = self.ids[2:5]
                self.sequence += 1

        self.native.key = moved
        self.native.wheel.side_effect = lambda point, down, *, deadline: setattr(
            self, "visible_ids", list(self.ids)
        )
        self.assertEqual(self.navigate()[0], self.target)
        self.assertEqual(
            [event[1] for event in self.events if event[0] == "key"],
            ["Home", "Down", "Down"],
        )
        recovery = next(
            event[1]
            for event in self.events
            if event[0] == "navigation-endpoint-reveal"
        )
        self.assertEqual(recovery["expected"], self.target)
        self.assertEqual(recovery["original_index"], 2)
        self.assertEqual(recovery["eligibility_index"], 0)
        self.assertEqual(recovery["eligibility_span"], [2, 4])

    def final_navigation_shift(self, current_index=1, span_start=2, ack_index=2):
        """Shift only on entry to real final proof, after the batch was acknowledged."""
        self.displaced_endpoint()
        self.ids = [aid(pid) for pid in range(20)]
        self.visible_ids = list(self.ids)
        self.selection = None
        self.target = self.endpoint = aid(2)
        self.final_entry = None
        self.final_frame = None
        self.acknowledged = Mock()
        self.native.navigation_context = {}
        key = self.native.key

        def issued(value, **kwargs):
            key(value, **kwargs)
            if self.pending[1] == self.target and ack_index != 2:
                self.ids.remove(self.target)
                self.ids.insert(ack_index, self.target)
                self.visible_ids = list(self.ids)
                self.sequence += 1

        self.native.key = issued
        self.native.wheel.side_effect = lambda point, down, *, deadline: setattr(
            self, "visible_ids", list(self.ids)
        )
        observe = self.native.navigation_selection

        def final_shift(*args, **kwargs):
            final = kwargs.get("fresh_panel", False)
            if final:
                self.assertIsNone(self.final_entry)
                self.assertEqual(self.selection, [self.target])
                self.assertEqual(self.ids.index(self.target), ack_index)
                self.assertTrue(
                    any(
                        e[0] == "ack" and e[1]["condition"] == "selected " + self.target
                        for e in self.events
                    )
                )
                self.final_entry = (args, kwargs, self.clock.now)
                self.ids.remove(self.target)
                self.ids.insert(current_index, self.target)
                self.visible_ids = self.ids[span_start : span_start + 3]
                self.sequence += 1
                self.revision += 1
            result = observe(*args, **kwargs)
            if final:
                self.final_frame = result[1]
            return result

        self.native.navigation_selection = final_shift

    def test_final_navigation_reveal_retains_issued_index_and_exports_current_proof(
        self,
    ):
        # The intermediate ACK can itself be at a different index from key issue.
        for ack_index in (2, 3):
            with self.subTest(ack_index=ack_index):
                self.setUp()
                self.final_navigation_shift(ack_index=ack_index)
                result = self.native._navigate(
                    self.target, 180, on_acknowledged=self.acknowledged
                )
                self.assertEqual(result[0], self.target)
                args, kwargs, started = self.final_entry
                self.assertEqual(args, (self.target, self.target, 9))
                self.assertEqual(started, 1)
                self.assertEqual(kwargs["endpoint_index"], 2)
                self.assertTrue(kwargs["reconcile"])
                self.assertTrue(kwargs["fresh_panel"])
                self.assertEqual(
                    [e[1] for e in self.events if e[0] == "key"],
                    ["Home", "Down", "Down"],
                )
                self.native.wheel.assert_called_once_with(
                    [400, 360], down=False, deadline=9
                )
                recovery = next(
                    e[1] for e in self.events if e[0] == "navigation-endpoint-reveal"
                )
                self.assertEqual(recovery["original_index"], 2)
                self.assertEqual(recovery["eligibility_index"], 1)
                self.assertEqual(recovery["eligibility_span"], [2, 4])
                final = self.final_frame
                self.acknowledged.assert_called_once_with(
                    {
                        "target": self.target,
                        "index": 1,
                        "publication": {
                            "sequence": final["snapshot"]["sequence"],
                            **{
                                key: final[key]
                                for key in (
                                    "application_pid",
                                    "render_revision",
                                    "accepted_unix_ns",
                                )
                            },
                        },
                    }
                )
                self.assertEqual(self.clock.now, 1.75)

    def test_final_navigation_rejects_unchanged_index_and_original_slot_outside_span(
        self,
    ):
        for current_index in (2, 1):
            with self.subTest(current_index=current_index):
                self.setUp()
                self.final_navigation_shift(current_index=current_index, span_start=3)
                with self.assertRaises(TimeoutError):
                    self.native._navigate(
                        self.target, 180, on_acknowledged=self.acknowledged
                    )
                self.assertEqual(self.final_entry[0][2], 9)
                self.assertEqual(self.clock.now, 9)
                self.native.wheel.assert_not_called()
                self.acknowledged.assert_not_called()

    def test_final_navigation_rejected_scan_rechecks_freshness_uniqueness_and_membership(
        self,
    ):
        for invalid in ("duplicate", "detached", "stale"):
            with self.subTest(invalid=invalid):
                self.setUp()
                self.final_navigation_shift()
                selected = self.native.selected
                rejected = []

                def reject(*args, **kwargs):
                    result = selected(*args, **kwargs)
                    if self.final_entry and not rejected:
                        rejected.append(self.native.navigation_panel.call_count)
                        self.sequence += 1
                        if invalid == "duplicate":
                            extra = Node(self.clock, name="processes")
                            self.root.children = lambda: [self.panel, extra]
                        elif invalid == "detached":
                            self.root.children = lambda: []
                        else:
                            self.stale = True
                    return result

                self.native.selected = reject
                error = {
                    "duplicate": "nonunique native Processes panel",
                    "detached": "Processes panel absent",
                    "stale": "accepted frame stale",
                }[invalid]
                with self.assertRaisesRegex((AssertionError, TimeoutError), error):
                    self.native._navigate(
                        self.target, 180, on_acknowledged=self.acknowledged
                    )
                self.assertEqual(len(rejected), 1)
                if invalid != "stale":
                    self.assertGreater(
                        self.native.navigation_panel.call_count, rejected[0]
                    )
                self.native.wheel.assert_not_called()
                self.acknowledged.assert_not_called()
                self.assertLessEqual(self.clock.now, 9)

    def test_final_navigation_reveal_still_requires_unique_panel_after_wheel(self):
        self.final_navigation_shift()
        reveal = self.native.wheel.side_effect

        def duplicate(*args, **kwargs):
            reveal(*args, **kwargs)
            extra = Node(self.clock, name="processes")
            self.root.children = lambda: [self.panel, extra]

        self.native.wheel.side_effect = duplicate
        with self.assertRaisesRegex(AssertionError, "nonunique native Processes panel"):
            self.native._navigate(self.target, 180, on_acknowledged=self.acknowledged)
        self.native.wheel.assert_called_once()
        self.acknowledged.assert_not_called()

    def test_reveal_rejects_duplicate_current_panel_before_any_wheel(self):
        self.displaced_endpoint()
        extra = Node(self.clock, name="processes")
        self.root.children = lambda: [self.panel, extra]
        with self.assertRaisesRegex(AssertionError, "nonunique native Processes panel"):
            self.observe_displaced()
        self.native.wheel.assert_not_called()

    def test_reveal_does_not_erase_an_observed_visible_unselected_endpoint(self):
        self.displaced_endpoint()
        self.visible_ids = self.ids[2:6]
        self.selection = None
        selected = self.native.selected

        def becomes_absent(*args, **kwargs):
            result = selected(*args, **kwargs)
            self.visible_ids = self.ids[5:8]
            self.selection = [self.endpoint]
            return result

        self.native.selected = becomes_absent
        with self.assertRaises(TimeoutError):
            self.observe_displaced()
        self.native.wheel.assert_not_called()

    def test_reveal_membership_replacement_during_geometry_prevents_wheel(self):
        self.displaced_endpoint()

        def detached(node):
            self.panel.children = lambda: []
            return [100, 200, 600, 300]

        self.native.bounds.side_effect = detached
        with self.assertRaises(TimeoutError):
            self.observe_displaced()
        self.native.wheel.assert_not_called()

    def test_reveal_publication_change_during_geometry_prevents_wheel(self):
        self.displaced_endpoint()

        def changing(node):
            self.sequence += 1
            return [100, 200, 600, 300]

        self.native.bounds.side_effect = changing
        with self.assertRaises(TimeoutError):
            self.observe_displaced()
        self.native.wheel.assert_not_called()

    def test_reveal_rejected_first_geometry_discards_old_eligibility(self):
        for raises in (False, True):
            with self.subTest(geometry_exception=raises):
                self.setUp()
                self.displaced_endpoint()
                original = self.native.bounds.side_effect
                changed = False

                def replaced(node):
                    nonlocal changed
                    if not changed:
                        changed = True
                        self.ids = [aid(pid) for pid in range(20)]
                        self.visible_ids = self.ids[8:11]
                        self.sequence += 1
                        if raises:
                            raise FileNotFoundError("geometry observation replaced")
                    return original(node)

                self.native.bounds.side_effect = replaced
                self.native.wheel.side_effect = (
                    lambda point, down, *, deadline: setattr(
                        self, "visible_ids", list(self.ids)
                    )
                )
                with self.assertRaises(TimeoutError):
                    self.observe_displaced()
                self.assertTrue(changed)
                self.assertEqual(self.ids.index(self.endpoint), 5)
                self.native.wheel.assert_not_called()

    def test_reveal_rejected_first_geometry_requires_new_unique_discovery(self):
        self.displaced_endpoint()
        original = self.native.bounds.side_effect
        changed = False

        def duplicate(node):
            nonlocal changed
            if not changed:
                changed = True
                extra = Node(self.clock, name="processes")
                self.root.children = lambda: [self.panel, extra]
                self.sequence += 1
            return original(node)

        self.native.bounds.side_effect = duplicate
        with self.assertRaisesRegex(AssertionError, "nonunique native Processes panel"):
            self.observe_displaced()
        self.native.wheel.assert_not_called()

    def test_reveal_downward_shift_uses_down_wheel(self):
        self.displaced_endpoint()
        self.ids.remove(self.endpoint)
        self.ids.insert(10, self.endpoint)
        self.visible_ids = self.ids[4:7]
        self.native.wheel.side_effect = lambda point, down, *, deadline: setattr(
            self, "visible_ids", self.ids[9:12]
        )
        self.assertEqual(self.observe_displaced()[0][0], self.endpoint)
        self.native.wheel.assert_called_once_with([400, 360], down=True, deadline=8)

    def test_pacing_frame_retries_reuse_valid_panel_without_discovery_cost(self):
        self.selection = [aid(2)]
        selected = self.native.selected
        scans = 0

        def changing(*args, **kwargs):
            nonlocal scans
            result = selected(*args, **kwargs)
            scans += 1
            self.clock.now += 0.3
            if scans <= 5:
                self.sequence += 1
            return result

        discover = self.native.navigation_panel

        def slow_discovery(deadline):
            self.clock.now += 1
            return discover(deadline)

        self.native.selected = changing
        self.native.navigation_panel = Mock(side_effect=slow_discovery)
        result, frame, _ = self.pacing_observation()
        self.assertEqual(result[0], aid(2))
        self.assertEqual(frame["snapshot"]["sequence"], self.sequence)
        self.assertEqual(scans, 6)
        self.native.navigation_panel.assert_not_called()
        self.assertLess(self.clock.now, 8)

    def test_pacing_replaced_selected_nodes_do_not_invalidate_valid_panel(self):
        self.selection = [aid(2)]
        selected = self.native.selected
        scans = 0

        def replaced(*args, **kwargs):
            nonlocal scans
            result = selected(*args, **kwargs)
            scans += 1
            if scans <= 2:
                result[1].defunct = True
                self.nodes[aid(2)] = self.row(aid(2))
            return result

        self.native.selected = replaced
        self.native.navigation_panel = Mock(wraps=self.native.navigation_panel)
        result, _, _ = self.pacing_observation()
        self.assertIs(result[1], self.nodes[aid(2)])
        self.assertEqual(scans, 3)
        self.native.navigation_panel.assert_not_called()

    def test_final_proof_rediscovery_rejects_duplicate_after_coherence_retry(self):
        selected = self.native.selected
        self.native.navigation_panel = Mock(wraps=self.native.navigation_panel)
        changed = False

        def duplicate(*args, **kwargs):
            nonlocal changed
            result = selected(*args, **kwargs)
            if (
                result
                and result[0] == self.target
                and self.native.navigation_panel.call_count >= 2
                and not changed
            ):
                changed = True
                self.sequence += 1
                extra = Node(self.clock, name="processes")
                self.root.children = lambda: [self.panel, extra]
            return result

        self.native.selected = duplicate
        with self.assertRaisesRegex(AssertionError, "nonunique native Processes panel"):
            self.navigate()
        self.assertTrue(changed)

    def test_incomplete_pacing_scan_requires_panel_reacquisition(self):
        self.selection = [aid(2)]
        selected = self.native.selected
        child_at_index = self.panel.get_child_at_index
        self.panel.get_child_at_index = lambda index: None

        def incomplete(*args, **kwargs):
            try:
                return selected(*args, **kwargs)
            finally:
                self.panel.get_child_at_index = child_at_index

        self.native.selected = incomplete
        self.native.navigation_panel = Mock(wraps=self.native.navigation_panel)
        self.assertEqual(self.pacing_observation()[0][0], aid(2))
        self.native.navigation_panel.assert_called_once_with(8)

    def test_exception_after_scan_requires_panel_reacquisition(self):
        self.selection = [aid(2)]
        original_frame = self.native.frame
        reads = 0

        def transient_frame():
            nonlocal reads
            reads += 1
            if reads == 3:
                raise FileNotFoundError("transient frame replacement")
            return original_frame()

        self.native.frame = transient_frame
        self.native.navigation_panel = Mock(wraps=self.native.navigation_panel)
        self.assertEqual(self.pacing_observation()[0][0], aid(2))
        self.native.navigation_panel.assert_called_once_with(8)

    def test_failed_post_scan_membership_requires_panel_reacquisition(self):
        self.selection = [aid(2)]
        selected = self.native.selected
        discover = self.native.navigation_panel
        scans = 0

        def detach(*args, **kwargs):
            nonlocal scans
            result = selected(*args, **kwargs)
            scans += 1
            if scans == 1:
                self.root.children = lambda: []
            return result

        def reattached(deadline):
            self.root.children = lambda: [self.panel]
            return discover(deadline)

        self.native.selected = detach
        self.native.navigation_panel = Mock(side_effect=reattached)
        self.assertEqual(self.pacing_observation()[0][0], aid(2))
        self.native.navigation_panel.assert_called_once_with(8)
        self.assertEqual(scans, 2)

    def test_pacing_coherence_retries_keep_original_deadline(self):
        self.selection = [aid(2)]
        selected = self.native.selected

        def changing(*args, **kwargs):
            result = selected(*args, **kwargs)
            self.sequence += 1
            return result

        self.native.selected = changing
        self.native.navigation_panel = Mock(wraps=self.native.navigation_panel)
        with self.assertRaises(TimeoutError):
            self.pacing_observation()
        self.assertEqual(self.clock.now, 8)
        self.native.navigation_panel.assert_not_called()
        self.assertFalse(any(e[0] == "key" for e in self.events))

    def test_application_registration_does_not_require_parent_or_index(self):
        self.assertTrue(self.application_membership())
        self.assertEqual(self.navigate()[0], self.target)

    def test_unregistered_application_is_rejected(self):
        self.desktop.children = lambda: []
        self.assertFalse(self.application_membership())

    def test_duplicate_application_registration_is_rejected(self):
        self.desktop.children = lambda: [self.root, self.root]
        with self.assertRaisesRegex(AssertionError, "nonunique native application"):
            self.application_membership()

    def replacement_application(self, pid=500):
        replacement = Node(self.clock, role="application")
        replacement.clear_cache_single = lambda: None
        replacement.get_process_id = lambda: pid
        return replacement

    def test_distinct_application_with_same_pid_cannot_replace_registered_identity(
        self,
    ):
        replacement = self.replacement_application()
        self.desktop.children = lambda: [replacement]
        self.assertFalse(self.application_membership())

    def test_multiple_application_objects_for_pid_are_rejected(self):
        replacement = self.replacement_application()
        self.desktop.children = lambda: [self.root, replacement]
        with self.assertRaisesRegex(AssertionError, "nonunique native application"):
            self.application_membership()

    def test_wrong_application_pid_is_rejected(self):
        self.root.get_process_id = lambda: 501
        self.assertFalse(self.application_membership())

    def test_missing_desktop_child_cannot_prove_unique_registration(self):
        self.desktop.children = lambda: [self.root, None]
        self.assertFalse(self.application_membership())

    def test_defunct_desktop_cannot_prove_registration(self):
        self.desktop.defunct = True
        self.assertFalse(self.application_membership())

    def test_defunct_registration_cannot_prove_membership(self):
        self.root.defunct = True
        self.assertFalse(self.application_membership())

    def test_negative_registration_count_is_incomplete(self):
        self.desktop.get_child_count = lambda: -1
        self.assertFalse(self.application_membership())

    def test_desktop_registration_keeps_node_bound(self):
        self.desktop.get_child_count = lambda: 30001
        with self.assertRaisesRegex(AssertionError, "native node bound exceeded"):
            self.application_membership()

    def test_application_replaced_during_enumeration_is_rejected(self):
        replacement = self.replacement_application()
        calls = 0

        def replacing(index):
            nonlocal calls
            calls += 1
            return self.root if calls == 1 else replacement

        self.desktop.get_child_at_index = replacing
        self.assertFalse(self.application_membership())

    def test_slow_desktop_enumeration_cannot_acknowledge_after_deadline(self):
        def slow(index):
            self.clock.now += 8
            return self.root

        self.desktop.get_child_at_index = slow
        with self.assertRaisesRegex(AssertionError, "deadline"):
            self.application_membership()

    def exit_after_ack(self, identity=aid(2), clear_at=0):
        def exited(selected):
            if selected != identity:
                return
            self.after_ack = lambda selected: None
            self.ids.remove(identity)
            self.sequence += 1
            self.revision += 1

            def remove():
                if self.clock.now >= clear_at:
                    self.selection = None
                    self.nodes.pop(identity, None)
                    self.before_children = lambda: None

            self.before_children = remove

        self.after_ack = exited

    def test_fresh_unchanged_sequence_allows_multiple_batches(self):
        self.assertEqual(self.navigate()[0], self.target)
        self.assertEqual(self.sequence, 1)
        self.assertEqual(
            [e[1] for e in self.events if e[0] == "key"], ["Home"] + ["Down"] * 6
        )
        self.assertLess(self.clock.now, 8)

    def test_355_row_distance_with_one_second_panel_discovery_fits_total_budget(self):
        self.ids = [aid(pid) for pid in range(800)]
        self.target = aid(355)
        self.nodes = {identity: self.row(identity) for identity in self.ids}
        walk = self.native.walk
        discoveries = []

        def timed_walk(root=None, *args, **kwargs):
            if root is None:
                discoveries.append(self.clock.now)
                self.clock.now += 1
            else:
                self.clock.now += 0.3
            yield from walk(root, *args, **kwargs)

        self.native.walk = timed_walk
        self.assertEqual(self.navigate()[0], self.target)
        self.assertLess(self.clock.now, 180)
        self.assertLessEqual(len(discoveries), 3)

    def test_collection_during_slow_discovery_does_not_starve_coherent_selection(self):
        self.target = aid(0)
        walk = self.native.walk

        def timed_walk(root=None, *args, **kwargs):
            self.clock.now += 1.25 if root is None else 0.1
            yield from walk(root, *args, **kwargs)

        self.native.walk = timed_walk
        self.before_frame = lambda: setattr(self, "sequence", int(self.clock.now) + 1)
        self.assertEqual(self.navigate()[0], self.target)
        self.assertLess(self.clock.now, 8)

    def test_no_next_batch_before_exact_endpoint_acknowledgement(self):
        self.navigate()
        pending_keys = 0
        for event, fields, _ in self.events:
            if event == "key":
                pending_keys += 1
                self.assertLessEqual(pending_keys, 2)
            if event == "ack" and fields["condition"].startswith("selected process:"):
                pending_keys = 0
        self.assertEqual(pending_keys, 0)

    def test_selected_exit_requires_physical_boundary_recovery(self):
        self.exit_after_ack()
        self.assertEqual(self.navigate()[0], self.target)
        self.assertEqual(sum(e[:2] == ("key", "Home") for e in self.events), 2)

    def test_delayed_native_clear_waits_without_more_keys(self):
        self.exit_after_ack(clear_at=3)
        self.assertEqual(self.navigate()[0], self.target)
        homes = [e[2] for e in self.events if e[:2] == ("key", "Home")]
        self.assertGreaterEqual(homes[1], 3)

    def test_spontaneous_selection_transfer_is_failure(self):
        self.exit_after_ack(clear_at=100)
        prior = self.after_ack

        def transfer(selected):
            prior(selected)
            if selected == aid(2):
                self.selection = [aid(3)]

        self.after_ack = transfer
        with self.assertRaisesRegex(AssertionError, "selection transferred"):
            self.navigate()

    def test_reused_selected_pid_is_not_the_exited_identity(self):
        self.exit_after_ack(clear_at=100)
        prior = self.after_ack

        def reuse(selected):
            prior(selected)
            if selected == aid(2):
                replacement = aid(2, 101)
                self.ids.insert(2, replacement)
                self.nodes[replacement] = self.row(replacement)
                self.selection = [replacement]

        self.after_ack = reuse
        with self.assertRaisesRegex(AssertionError, "selection transferred"):
            self.navigate()

    def test_target_disappearance_is_explicit_failure(self):
        self.ids.remove(self.target)
        with self.assertRaisesRegex(AssertionError, "navigation target absent"):
            self.navigate()

    def test_reused_target_pid_is_not_accepted(self):
        self.ids[self.ids.index(self.target)] = aid(6, 101)
        with self.assertRaisesRegex(AssertionError, "navigation target absent"):
            self.navigate()

    def test_target_exit_after_endpoint_ack_is_rejected(self):
        self.after_ack = (
            lambda selected: self.ids.remove(self.target)
            if selected == self.target
            else None
        )
        with self.assertRaisesRegex(AssertionError, "navigation target absent"):
            self.navigate()

    def test_stale_frames_remain_failures(self):
        self.stale = True
        with self.assertRaisesRegex(AssertionError, "accepted frame stale"):
            self.navigate()
        self.assertFalse(any(e[0] == "key" for e in self.events))

    def test_cached_selected_endpoint_cannot_hide_multiple_selection(self):
        self.native.cache.update(self.nodes)

        def multiple():
            if self.pending and self.clock.now >= self.pending[0]:
                self.selection = [self.pending[1], aid(19)]
                self.pending = None

        self.publish_selection = multiple
        with self.assertRaisesRegex(AssertionError, "multiple selected"):
            self.navigate()

    def test_incomplete_tree_cannot_prove_selection_cleared(self):
        self.exit_after_ack()
        prior = self.after_ack

        def missing(selected):
            prior(selected)
            if selected == aid(2):
                self.panel.get_child_at_index = lambda index: None

        self.after_ack = missing
        with self.assertRaisesRegex(TimeoutError, "incomplete native tree"):
            self.navigate()
        self.assertEqual(sum(e[:2] == ("key", "Home") for e in self.events), 1)
        self.assertLessEqual(self.clock.now, 9)

    def test_retained_exited_native_selection_uses_one_batch_deadline(self):
        self.exit_after_ack(clear_at=100)
        with self.assertRaises(TimeoutError):
            self.navigate()
        self.assertEqual(self.clock.now, 9)

    def test_slow_acknowledgement_keeps_eight_second_bound(self):
        self.ack_delay = 9
        with self.assertRaises(TimeoutError):
            self.navigate()
        self.assertEqual(self.clock.now, 8)

    def test_total_deadline_caps_reconciliation(self):
        self.exit_after_ack(clear_at=1000)
        prior = self.after_ack

        def late_exit(selected):
            prior(selected)
            if selected == aid(2):
                self.clock.now = 179

        self.after_ack = late_exit
        with self.assertRaisesRegex(TimeoutError, "original180s deadline"):
            self.navigate()
        self.assertEqual(self.clock.now, 180)

    def test_publication_change_during_observation_retries_before_keys(self):
        self.exit_after_ack(clear_at=100)
        prior = self.after_ack

        def race(selected):
            prior(selected)
            if selected == aid(2):
                reads = 0

                def changing():
                    nonlocal reads
                    reads += 1
                    if reads <= 8:
                        self.sequence += 1
                    else:
                        self.selection = None
                        self.nodes.pop(aid(2), None)
                        self.before_frame = lambda: None

                self.before_frame = changing

        self.after_ack = race
        self.assertEqual(self.navigate()[0], self.target)
        self.assertGreater(self.sequence, 3)

    def test_detached_live_panel_with_old_parent_pointer_is_reacquired(self):
        old = self.panel

        def detach(selected):
            if selected != aid(2):
                return
            self.after_ack = lambda selected: None
            replacement = Node(self.clock, name="processes", children=self.children)
            replacement.clear_cache_single = lambda: None
            replacement.get_parent = lambda: self.root
            replacement.get_index_in_parent = lambda: 0
            self.root.children = lambda: [replacement]
            old.children = Mock(side_effect=AssertionError("scanned detached panel"))

        self.after_ack = detach
        self.assertEqual(self.navigate()[0], self.target)

    def test_detached_ancestor_cannot_validate_old_panel(self):
        ancestor = Node(self.clock, children=lambda: [self.panel])
        ancestor.clear_cache_single = lambda: None
        ancestor.get_parent = lambda: self.root
        ancestor.get_index_in_parent = lambda: 0
        self.panel.get_parent = lambda: ancestor
        self.root.children = lambda: [ancestor]

        def detach(selected):
            if selected == aid(2):
                self.root.children = lambda: []

        self.after_ack = detach
        with self.assertRaisesRegex(TimeoutError, "Processes panel absent"):
            self.navigate()
        self.assertEqual(
            [e[1] for e in self.events if e[0] == "key"], ["Home", "Down", "Down"]
        )

    def test_duplicate_current_panels_fail_final_target_proof(self):
        duplicate = Node(self.clock, name="processes")
        key = self.native.key

        def add_duplicate(value, **kwargs):
            key(value, **kwargs)
            if self.pending[1] == self.target:
                self.root.children = lambda: [self.panel, duplicate]

        self.native.key = add_duplicate
        with self.assertRaisesRegex(AssertionError, "nonunique native Processes panel"):
            self.navigate()

    def test_duplicate_initial_panels_fail_before_input(self):
        duplicate = Node(self.clock, name="processes")
        self.root.children = lambda: [self.panel, duplicate]
        with self.assertRaisesRegex(AssertionError, "nonunique native Processes panel"):
            self.navigate()
        self.assertFalse(any(e[0] == "key" for e in self.events))

    def test_changed_native_selection_without_publication_does_not_allow_input(self):
        def transfer(selected):
            if selected == aid(2):
                self.selection = [aid(3)]

        self.after_ack = transfer
        with self.assertRaisesRegex(AssertionError, "selection transferred"):
            self.navigate()
        self.assertEqual(
            [e[1] for e in self.events if e[0] == "key"], ["Home", "Down", "Down"]
        )

    def test_slow_reconciliation_and_boundary_ack_share_batch_deadline(self):
        self.exit_after_ack(clear_at=8.75)
        with self.assertRaises(TimeoutError):
            self.navigate()
        self.assertEqual(self.clock.now, 9)

    def test_negative_parent_index_is_not_python_last_child(self):
        self.panel.get_index_in_parent = lambda: -1
        with self.assertRaisesRegex(TimeoutError, "panel membership"):
            self.navigate()
        self.assertFalse(any(e[0] == "key" for e in self.events))

    def test_parent_replacement_during_child_lookup_is_rejected(self):
        original = self.root.get_child_at_index

        def reparent(index):
            child = original(index)
            self.panel.get_parent = lambda: self.desktop
            return child

        self.root.get_child_at_index = reparent
        with self.assertRaises(TimeoutError):
            self.navigate()
        self.assertFalse(any(e[0] == "key" for e in self.events))

    def test_link_validation_does_not_recursively_clear_application(self):
        self.root.clear_cache = Mock(
            side_effect=AssertionError("recursive cache clear")
        )
        self.assertTrue(
            self.native.navigation_panel_current([self.panel, self.root], 8)
        )

    def test_slow_link_checks_cannot_extend_total_deadline(self):
        def delay(selected):
            if selected == aid(2):
                self.clock.now = 179

                def slow():
                    self.clock.now += 2
                    return self.root

                self.panel.get_parent = slow

        self.after_ack = delay
        with self.assertRaisesRegex(TimeoutError, "original180s deadline"):
            self.navigate()
        self.assertEqual(
            [e[1] for e in self.events if e[0] == "key"], ["Home", "Down", "Down"]
        )

    def test_publication_change_during_scan_cannot_accept_selection_transfer(self):
        def changed():
            if self.selection == [aid(2)]:
                self.sequence += 1
                self.selection = [aid(3)]
                self.before_children = lambda: None

        def prepare(selected):
            if selected == aid(2):
                self.sequence += 1
                self.before_children = changed

        self.after_ack = prepare
        with self.assertRaisesRegex(AssertionError, "selection transferred"):
            self.navigate()


if __name__ == "__main__":
    unittest.main()
