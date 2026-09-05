"""Exercise the real navigation protocol without a host process or native session."""

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
        native.selected.__globals__["Atspi"].StateType.SELECTED = "selected"
        self.native = native.__new__(native)
        self.native.app = Mock(pid=500)
        self.native.app.poll.return_value = None
        self.native.interval_ms = 1000
        self.native.save = Mock()
        self.native.enter_processes = Mock()
        self.native.journal = self.journal
        self.native.key = self.key
        self.native.latest = SimpleNamespace(read_text=self.frame_text)
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
        self.root.get_parent = lambda: self.desktop
        self.root.get_index_in_parent = lambda: 0
        self.root.get_process_id = lambda: 500
        self.desktop.clear_cache_single = lambda: None
        self.root.clear_cache_single = lambda: None
        self.panel.clear_cache_single = lambda: None
        self.panel.get_parent = lambda: self.root
        self.panel.get_index_in_parent = lambda: 0
        self.native.root = Mock(return_value=self.root)
        self.native.cache = {"__panel:processes": self.panel}

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

    def key(self, key):
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

        def add_duplicate(value):
            key(value)
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
