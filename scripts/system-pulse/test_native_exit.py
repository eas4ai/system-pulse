"""Check exit acknowledgement without GI, DBus, a host child, or a native app."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from host_accuracy import require


TARGET = "process:42:123"
ROW = {"identity": {"pid": 42, "start_time_ticks": 123}}


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def spin(self):
        self.now += 0.25


class Node:
    def __init__(self, clock, aid="", name="", role="panel", children=None):
        self.clock = clock
        self.aid = aid
        self.name = name
        self.role = role
        self.children = children or (lambda: [])
        self.defunct = False
        self.read_seconds = 0

    def clear_cache(self):
        pass

    def get_state_set(self):
        return SimpleNamespace(contains=lambda state: self.defunct)

    def get_accessible_id(self):
        self.clock.now += self.read_seconds
        return self.aid

    def get_name(self):
        return self.name

    def get_role_name(self):
        return self.role

    def get_child_count(self):
        return len(self.children())

    def get_child_at_index(self, index):
        children = self.children()
        return children[index] if index < len(children) else None


def native_class(clock):
    source = Path(__file__).with_name("native_driver.py")
    nodes = [
        node
        for node in ast.parse(source.read_text()).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name in ("Native", "identity", "IncompleteNativeTree")
    ]
    context = dict(
        time=clock,
        spin=clock.spin,
        require=require,
        json=json,
        GLib=SimpleNamespace(Error=type("TransportError", (Exception,), {})),
        Atspi=SimpleNamespace(StateType=SimpleNamespace(DEFUNCT="defunct")),
        BUDGETS={"nodes": 30000},
    )
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), context)
    return context["Native"], context["identity"]


def replay_exit(context):
    """Run the real replay boundary from its pre-exit sequence through its wait."""
    source = Path(__file__).with_name("native_replay.py")
    tree = ast.parse(source.read_text())
    for parent in ast.walk(tree):
        body = getattr(parent, "body", [])
        if not isinstance(body, list):
            continue
        for start, node in enumerate(body):
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "before_seq"
                    for t in node.targets
                )
                and start + 1 < len(body)
                and isinstance(body[start + 1], ast.Expr)
                and isinstance(body[start + 1].value, ast.Call)
                and isinstance(body[start + 1].value.func, ast.Name)
                and body[start + 1].value.func.id == "stop_child"
            ):
                end = next(
                    i
                    for i in range(start, len(body))
                    if isinstance(body[i], ast.Expr)
                    and isinstance(body[i].value, ast.Call)
                    and isinstance(body[i].value.func, ast.Attribute)
                    and body[i].value.func.attr == "save"
                )
                exec(
                    compile(
                        ast.Module(body=body[start:end], type_ignores=[]),
                        str(source),
                        "exec",
                    ),
                    context,
                )
                return
    raise AssertionError("native replay exit boundary not found")


class NativeExitTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        native, identity = native_class(self.clock)
        self.native = native.__new__(native)
        self.native.app = Mock()
        self.native.app.poll.return_value = None
        self.native.journal = Mock()
        self.stopped = False
        self.snapshot_at = 0.5
        self.native_at = 2.0
        self.sequence = 11
        self.snapshot_child = False
        self.row = Node(self.clock, TARGET, role="table row")
        self.panel = Node(
            self.clock,
            name="processes",
            children=lambda: [self.row] if self.clock.now < self.native_at else [],
        )
        self.root = Node(self.clock, role="application", children=lambda: [self.panel])
        self.native.root = Mock(return_value=self.root)
        self.native.cache = {"__panel:processes": self.panel}
        self.native.frame = self.frame
        self.context = dict(
            app=self.native,
            target=TARGET,
            time=self.clock,
            require=require,
            identity=identity,
            stop_child=self.stop,
            child=object(),
        )

    def frame(self):
        newer = self.stopped and self.clock.now >= self.snapshot_at
        return {
            "snapshot": {
                "sequence": self.sequence if newer else 10,
                "processes": [ROW] if not newer or self.snapshot_child else [],
            }
        }

    def stop(self, child):
        self.stopped = True

    def run_exit(self):
        replay_exit(self.context)

    def test_diagnostic_before_native_waits_until_identity_disappears(self):
        self.run_exit()
        self.assertGreaterEqual(self.clock.now, self.native_at)
        self.assertLess(self.clock.now, 5)
        self.native.journal.assert_called_with(
            "ack", condition="child exit snapshot and native tree"
        )

    def test_retained_identity_fails_at_original_deadline(self):
        self.native_at = 100
        with self.assertRaisesRegex(TimeoutError, "original deadline expired"):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_absent_native_identity_cannot_acknowledge_old_sequence(self):
        self.native_at = 0
        self.sequence = 10
        with self.assertRaises(TimeoutError):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_absent_native_identity_cannot_acknowledge_snapshot_with_child(self):
        self.native_at = 0
        self.snapshot_child = True
        with self.assertRaises(TimeoutError):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_missing_panel_is_not_vacuous_success(self):
        self.native_at = 0
        self.native.cache.clear()
        self.root.children = lambda: []
        with self.assertRaises(TimeoutError):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_defunct_panel_is_not_vacuous_success(self):
        self.native_at = 0
        self.panel.defunct = True
        with self.assertRaises(TimeoutError):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_missing_child_cannot_prove_exit(self):
        self.native_at = 100
        self.panel.get_child_at_index = lambda index: None
        with self.assertRaisesRegex(
            TimeoutError, "incomplete native tree.*missing child"
        ):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_defunct_container_cannot_hide_retained_identity(self):
        container = Node(self.clock, children=lambda: [self.row])
        container.defunct = True
        self.panel.children = lambda: [container]
        with self.assertRaisesRegex(TimeoutError, "incomplete native tree.*defunct"):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_container_becoming_defunct_cannot_prove_exit(self):
        container = Node(self.clock)

        def vanished_children():
            container.defunct = True
            return []

        container.children = vanished_children
        self.panel.children = lambda: [container]
        with self.assertRaisesRegex(TimeoutError, "incomplete native tree.*defunct"):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_negative_child_count_cannot_prove_exit(self):
        self.panel.get_child_count = lambda: -1
        with self.assertRaisesRegex(
            TimeoutError, "incomplete native tree.*negative child count"
        ):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_transient_missing_child_retries_until_complete_removal(self):
        self.panel.get_child_at_index = lambda index: (
            None if self.clock.now < 1 else self.row
        )
        self.run_exit()
        self.assertEqual(self.clock.now, self.native_at)

    def test_permissive_walk_still_skips_missing_and_defunct_children(self):
        defunct = Node(self.clock, children=lambda: [self.row])
        defunct.defunct = True
        self.panel.children = lambda: [None, defunct]
        self.assertEqual(list(self.native.walk(self.panel)), [self.panel])

    def test_exit_scan_skips_known_process_cells(self):
        self.row.aid = "process:42:124"
        self.native_at = 100
        self.row.get_child_count = Mock(
            side_effect=AssertionError("read process cells")
        )
        self.run_exit()
        self.row.get_child_count.assert_not_called()

    def test_exit_scan_keeps_node_bound_failure(self):
        self.native.walk.__func__.__globals__["BUDGETS"]["nodes"] = 1
        self.panel.children = lambda: [Node(self.clock, "unrelated")]
        with self.assertRaisesRegex(AssertionError, "native node bound exceeded"):
            self.run_exit()

    def test_slow_tree_cannot_acknowledge_after_deadline(self):
        self.native_at = 0
        slow = Node(self.clock, "unrelated")
        slow.read_seconds = 5
        self.panel.children = lambda: [slow]
        with self.assertRaisesRegex(AssertionError, "deadline"):
            self.run_exit()

    def test_pid_reuse_with_different_start_ticks_does_not_block_exit(self):
        self.row.aid = "process:42:124"
        self.native_at = 100
        self.run_exit()
        self.assertEqual(self.clock.now, self.snapshot_at)

    def test_deadline_starts_after_child_stop(self):
        def slow_stop(child):
            self.stopped = True
            self.clock.now = 3

        self.context["stop_child"] = slow_stop
        self.native_at = 100
        with self.assertRaises(TimeoutError):
            self.run_exit()
        self.assertEqual(self.clock.now, 8)

    def test_defunct_cached_panel_is_replaced_with_live_panel(self):
        obsolete = Node(self.clock, name="processes")
        obsolete.defunct = True
        self.native.cache["__panel:processes"] = obsolete
        self.native_at = 0
        self.run_exit()
        self.assertIs(self.native.cache["__panel:processes"], self.panel)
        self.assertEqual(self.clock.now, self.snapshot_at)

    def test_panel_vanishing_before_walk_is_not_vacuous_success(self):
        clears = 0

        def clear():
            nonlocal clears
            clears += 1
            if clears == 2:
                self.panel.defunct = True

        self.panel.clear_cache = clear
        self.native_at = 0
        with self.assertRaises(TimeoutError):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_panel_becoming_defunct_during_walk_cannot_acknowledge(self):
        def vanished_children():
            self.panel.defunct = True
            return []

        self.panel.children = vanished_children
        with self.assertRaises(TimeoutError):
            self.run_exit()
        self.assertEqual(self.clock.now, 5)

    def test_application_exit_remains_a_failure(self):
        self.native.app.poll.return_value = 1
        with self.assertRaisesRegex(AssertionError, "app exited"):
            self.run_exit()

    def test_snapshot_validation_failure_remains_a_failure(self):
        frame = self.frame

        def validated_frame():
            require(not self.stopped, "accepted frame stale")
            return frame()

        self.native.frame = validated_frame
        with self.assertRaisesRegex(AssertionError, "accepted frame stale"):
            self.run_exit()


if __name__ == "__main__":
    unittest.main()
