"""Exercise native cell discovery and the real replay boundary without a session."""

import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

from host_accuracy import require
from test_native_exit import Clock, Node, TARGET, native_class


CELL = TARGET + ":cell:0"


def replay_visibility(context):
    """Execute the actual eight-column visibility loop and its module helpers."""
    source = Path(__file__).with_name("native_replay.py")
    tree = ast.parse(source.read_text())
    helpers = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name != "main"
    ]
    loops = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "column"
        and any(
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "key"
                for target in statement.targets
            )
            for statement in node.body
        )
    ]
    require(len(loops) == 1, "replay visibility boundary missing or ambiguous")
    exec(
        compile(ast.Module(body=helpers + loops, type_ignores=[]), str(source), "exec"),
        context,
    )


class NativeCellTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        native, _ = native_class(self.clock)
        self.native = native.__new__(native)
        self.native.app = None
        self.native.journal = Mock()
        self.cells = [Node(self.clock, TARGET + f":cell:{i}") for i in range(8)]
        self.row = Node(self.clock, TARGET, children=lambda: self.cells)
        self.other = Node(self.clock, "process:99:456")
        self.other.get_child_count = Mock(
            side_effect=AssertionError("traversed unrelated process cells")
        )
        self.panel = Node(
            self.clock, name="processes", children=lambda: [self.other, self.row]
        )
        self.root = Node(self.clock, children=lambda: [self.panel])
        self.native.root = Mock(return_value=self.root)
        self.native.cache = {"__panel:processes": self.panel}
        self.native.bounds = lambda node: [node.x, 0, 10, 10]
        self.native.visible = lambda node: node.x == 0
        self.native.key = Mock(side_effect=self.move)
        self.native.metric = Mock()
        for cell in self.cells:
            cell.x = 100

    def move(self, key):
        for cell in self.cells:
            cell.x = 0

    def lookup(self, aid=CELL, deadline=5):
        self.assertTrue(
            hasattr(self.native, "process_cell"), "shared process cell lookup missing"
        )
        return self.native.process_cell(aid, deadline=deadline)

    def replay(self):
        replay_visibility(
            dict(app=self.native, target=TARGET, time=self.clock, require=require)
        )

    def test_row_lookup_skips_unrelated_cells_and_application_tree(self):
        self.assertIs(self.lookup(), self.cells[0])
        self.other.get_child_count.assert_not_called()
        self.native.root.assert_not_called()

    def test_defunct_cached_cell_and_row_reacquire_exact_identity(self):
        for aid in (TARGET, CELL):
            stale = Node(self.clock, aid)
            stale.defunct = True
            self.native.cache[aid] = stale
        self.assertIs(self.lookup(), self.cells[0])

    def test_live_cache_with_wrong_start_identity_is_not_used(self):
        self.native.cache[TARGET] = Node(self.clock, "process:42:124")
        self.native.cache[CELL] = Node(self.clock, "process:42:124:cell:0")
        self.assertIs(self.lookup(), self.cells[0])

    def test_defunct_panel_reacquisition_skips_unrelated_cells(self):
        stale = Node(self.clock, name="processes")
        stale.defunct = True
        self.native.cache["__panel:processes"] = stale
        self.assertIs(self.lookup(), self.cells[0])
        self.assertIs(self.native.cache["__panel:processes"], self.panel)
        self.other.get_child_count.assert_not_called()

    def test_missing_panel_fails_with_original_deadline(self):
        self.native.cache.clear()
        self.root.children = lambda: []
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.lookup()
        self.assertEqual(self.clock.now, 5)

    def test_missing_row_fails_with_original_deadline(self):
        self.panel.children = lambda: [self.other]
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.lookup()
        self.assertEqual(self.clock.now, 5)

    def test_reused_pid_cannot_supply_old_identity(self):
        self.row.aid = "process:42:124"
        self.native.cache[TARGET] = self.row
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.lookup()
        self.assertEqual(self.clock.now, 5)

    def test_missing_cell_fails_with_original_deadline(self):
        self.cells.pop(0)
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.lookup()
        self.assertEqual(self.clock.now, 5)

    def test_duplicate_cell_fails_even_with_live_cached_match(self):
        self.native.cache[CELL] = self.cells[0]
        self.cells.append(Node(self.clock, CELL))
        with self.assertRaisesRegex(AssertionError, "nonunique"):
            self.lookup()

    def test_row_replaced_during_cell_scan_is_reacquired(self):
        stale = self.row

        def replaced_children():
            stale.defunct = True
            self.row = Node(self.clock, TARGET, children=lambda: self.cells)
            return []

        stale.children = replaced_children
        self.assertIs(self.lookup(), self.cells[0])
        self.assertIs(self.native.cache[TARGET], self.row)
        self.assertLess(self.clock.now, 5)

    def test_missing_cell_retries_with_replacement_row(self):
        stale = self.row
        stale.children = lambda: []
        fresh = Node(self.clock, TARGET, children=lambda: self.cells)

        def refresh():
            if self.clock.now >= 1:
                stale.defunct = True

        stale.clear_cache = refresh
        self.panel.children = lambda: [fresh] if self.clock.now >= 1 else [stale]
        self.assertIs(self.lookup(), self.cells[0])
        self.assertEqual(self.clock.now, 1)

    def test_slow_panel_reacquisition_cannot_restart_deadline(self):
        self.native.cache.clear()
        self.root.read_seconds = 5
        with self.assertRaisesRegex(AssertionError, "deadline"):
            self.lookup()
        self.assertEqual(self.clock.now, 5)

    def test_slow_row_read_cannot_succeed_after_deadline(self):
        self.row.read_seconds = 5
        with self.assertRaisesRegex(AssertionError, "deadline"):
            self.lookup()

    def test_cached_row_and_cell_do_not_bypass_expired_deadline(self):
        self.native.cache.update({TARGET: self.row, CELL: self.cells[0]})
        self.clock.now = 5
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.lookup()

    def test_cell_lookup_retains_node_budget(self):
        self.native.walk.__func__.__globals__["BUDGETS"]["nodes"] = 1
        with self.assertRaisesRegex(AssertionError, "native node bound exceeded"):
            self.lookup()

    def test_replay_uses_scoped_discovery_and_keeps_all_metric_columns(self):
        self.replay()
        self.other.get_child_count.assert_not_called()
        self.native.root.assert_not_called()
        self.assertEqual(
            [call.args for call in self.native.metric.call_args_list],
            [
                (
                    TARGET + f":cell:{i}",
                    "child-left"
                    if i == 0
                    else "child-right"
                    if i == 7
                    else f"child-visible-{i}",
                )
                for i in range(8)
            ],
        )

    def test_replay_reacquires_cell_and_row_replaced_by_movement(self):
        def move(key):
            self.row.defunct = True
            for cell in self.cells:
                cell.defunct = True
            self.cells = [Node(self.clock, TARGET + f":cell:{i}") for i in range(8)]
            for cell in self.cells:
                cell.x = 0
            self.row = Node(self.clock, TARGET, children=lambda: self.cells)

        self.native.key.side_effect = move
        self.replay()
        self.assertEqual(self.native.metric.call_count, 8)
        self.assertLess(self.clock.now, 5)

    def test_replay_missing_cell_after_movement_keeps_original_deadline(self):
        def move(key):
            self.clock.now = 4
            self.cells[0].defunct = True
            self.cells.pop(0)

        self.native.key.side_effect = move
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.replay()
        self.assertEqual(self.clock.now, 5)
        self.native.metric.assert_not_called()

    def test_replay_slow_visible_read_cannot_pass_after_deadline(self):
        def visible(node):
            self.clock.now = 5
            return True

        self.native.visible = visible
        with self.assertRaisesRegex(AssertionError, "deadline"):
            self.replay()
        self.native.metric.assert_not_called()

    def test_replay_slow_bounds_cannot_send_movement_after_deadline(self):
        def bounds(node):
            self.clock.now = 5
            return [100, 0, 10, 10]

        self.native.bounds = bounds
        with self.assertRaisesRegex((AssertionError, TimeoutError), "deadline"):
            self.replay()
        self.native.key.assert_not_called()

    def test_metric_uses_shared_lookup_for_initial_and_replacement_cell(self):
        self.assertTrue(hasattr(self.native, "process_cell"), "shared lookup missing")
        lookup = self.native.process_cell
        self.native.process_cell = Mock(wraps=lookup)
        self.native.app = Mock(pid=77)
        self.native.app.poll.return_value = None
        self.native.save = Mock()
        self.native.ancestors = Mock(return_value=[])
        self.native.screenshot = Mock()
        metric = type(self.native).metric.__get__(self.native)
        metric.__func__.__globals__["expected_label"] = lambda frame, entry: ""
        original = self.cells[0]

        def frame():
            if not original.defunct:
                original.defunct = True
                self.cells[0] = Node(self.clock, CELL)
                self.cells[0].x = 0
            return {
                "application_pid": 77,
                "snapshot": {"sequence": 10},
                "render_revision": 9,
                "accepted_unix_ns": 1,
                "rendered": [{"element_id": CELL}],
            }

        self.native.frame = frame
        result = metric(CELL, "replacement", visible=False)
        self.assertEqual(result["entry"]["element_id"], CELL)
        self.assertEqual(self.native.process_cell.call_count, 2)
        self.assertEqual(self.native.process_cell.call_args_list[0].args, (CELL, None))
        self.assertEqual(self.native.process_cell.call_args_list[1].args, (CELL, 5))


if __name__ == "__main__":
    unittest.main()
