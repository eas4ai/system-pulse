"""Tree inventory requires a complete read within one original discovery deadline."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from test_native_exit import Clock, Node, native_class


class TreeInventoryTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.clock.monotonic_ns = lambda: int(self.clock.now * 1e9)
        native, _ = native_class(self.clock)
        self.native = native.__new__(native)
        self.native.app = Mock()
        self.native.app.poll.return_value = None
        self.native.cache = {}
        self.native.journal = Mock()
        self.native.save = Mock()
        self.native.save_state = Mock(return_value={"dock": {}})
        self.native.screenshot = Mock()
        self.error = native.walk.__globals__["GLib"].Error

    def node(self, aid, role="panel"):
        node = Node(self.clock, aid=aid, role=role)
        node.get_component_iface = lambda: SimpleNamespace()
        return node

    def test_defunct_bounds_restart_a_complete_inventory_without_partial_rows(self):
        old, disappearing, fresh = map(self.node, ("old", "gone", "fresh"))
        initial_root, fresh_root = self.node(""), self.node("")
        initial_root.children = lambda: [old, disappearing]
        fresh_root.children = lambda: [fresh]
        self.native.root = Mock(side_effect=[initial_root, fresh_root])

        def bounds(node):
            if node is disappearing:
                raise self.error("object no longer exists")
            return [0, 0, 100, 20]

        self.native.bounds = bounds
        self.native.no_tabs("inventory")
        rows = self.native.save.call_args.args[1]
        self.assertEqual([row["id"] for row in rows if row["id"]], ["fresh"])
        self.assertEqual(self.native.root.call_count, 2)
        self.assertLess(self.clock.now, 15)

    def test_persistent_transport_failure_expires_without_publishing_inventory(self):
        self.native.root = Mock(return_value=self.node("gone"))
        self.native.bounds = Mock(side_effect=self.error("object no longer exists"))
        with self.assertRaises(TimeoutError):
            self.native.no_tabs("inventory")
        self.assertEqual(self.clock.now, 15)
        self.native.save.assert_not_called()
        self.native.save_state.assert_not_called()

    def test_forbidden_roles_and_fixture_ids_fail_without_retry(self):
        for node in (self.node("tab", "page tab"), self.node("fixture-home")):
            with self.subTest(node=node.aid):
                self.native.root = Mock(return_value=node)
                self.native.bounds = Mock(return_value=[0, 0, 100, 20])
                with self.assertRaises(AssertionError):
                    self.native.no_tabs("inventory")
                self.native.root.assert_called_once()
                self.native.save.assert_not_called()

    def test_missing_child_cannot_be_counted_as_a_complete_inventory(self):
        broken = self.node("parent")
        broken.get_child_count = lambda: 1
        broken.get_child_at_index = lambda index: None
        self.native.root = Mock(return_value=broken)
        self.native.bounds = Mock(return_value=[0, 0, 100, 20])
        with self.assertRaises(TimeoutError):
            self.native.no_tabs("inventory")
        self.native.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
