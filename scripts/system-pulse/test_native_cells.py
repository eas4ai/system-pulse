"""Exercise native cell discovery and the real replay boundary without a session."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from host_accuracy import require
from native_replay import reveal_process_cell
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
            dict(
                app=self.native,
                target=TARGET,
                time=self.clock,
                require=require,
                inspection=SimpleNamespace(
                    metric=self.native.metric, preparation=lambda **kwargs: None
                ),
            )
        )

    def test_row_lookup_skips_unrelated_cells(self):
        self.assertIs(self.lookup(), self.cells[0])
        self.other.get_child_count.assert_not_called()

    def monitor_body(self, name="cpu:host", descendants=None):
        body = Node(self.clock, name + ":viewport", children=lambda: descendants or [])
        panel = Node(self.clock, name=name, children=lambda: [body])
        return panel, body

    def unreadable_monitor_body(self):
        panel, body = self.monitor_body()
        body.get_child_count = Mock(
            side_effect=AssertionError("traversed monitor body during panel discovery")
        )
        return panel, body

    def test_panel_discovery_skips_validated_monitor_body_descendants(self):
        monitor, body = self.unreadable_monitor_body()
        self.root.children = lambda: [monitor, self.panel]
        self.assertIs(self.lookup(), self.cells[0])
        body.get_child_count.assert_not_called()

    def test_process_body_is_read_only_for_row_discovery(self):
        self.panel, body = self.monitor_body("processes", [self.other, self.row])
        body.get_child_count = Mock(wraps=body.get_child_count)
        self.assertIs(self.lookup(), self.cells[0])
        self.assertEqual(body.get_child_count.call_count, 1)

    def test_duplicate_sibling_panels_after_monitor_body_still_fail(self):
        monitor, body = self.unreadable_monitor_body()
        duplicate = Node(self.clock, name="processes")
        self.root.children = lambda: [monitor, self.panel, duplicate]
        with self.assertRaisesRegex(AssertionError, "nonunique native Processes panel"):
            self.lookup()
        body.get_child_count.assert_not_called()

    def test_detached_cached_panel_after_monitor_body_still_fails(self):
        monitor, body = self.unreadable_monitor_body()
        replacement = Node(self.clock, name="processes")
        self.root.children = lambda: [monitor, replacement]
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.lookup()
        self.assertEqual(self.clock.now, 5)
        body.get_child_count.assert_not_called()

    def test_mismatched_viewport_parent_cannot_hide_current_panel(self):
        for mismatch in ("parent name", "parent role", "child role", "child id"):
            with self.subTest(mismatch=mismatch):
                monitor, body = self.monitor_body(descendants=[self.panel])
                if mismatch == "parent name":
                    monitor.name = ""
                elif mismatch == "parent role":
                    monitor.role = "frame"
                elif mismatch == "child role":
                    body.role = "section"
                else:
                    body.aid = "gpu:other:viewport"
                self.root.children = lambda: [monitor]
                self.assertIs(self.lookup(), self.cells[0])

    def test_workspace_and_unmatched_layout_viewports_remain_traversable(self):
        workspace, _ = self.monitor_body("workspace", [self.panel])
        layout = Node(self.clock, "layout:viewport", children=lambda: [workspace])
        wrapper = Node(self.clock, children=lambda: [layout])
        self.root.children = lambda: [wrapper]
        self.assertIs(self.lookup(), self.cells[0])

    def test_unmatched_nested_viewport_does_not_hide_duplicate_panel(self):
        duplicate = Node(self.clock, name="processes")
        monitor, body = self.monitor_body(descendants=[duplicate])
        body.aid = "cpu:host:rows-viewport"
        self.root.children = lambda: [self.panel, monitor]
        with self.assertRaisesRegex(AssertionError, "nonunique native Processes panel"):
            self.lookup()

    def test_default_walk_still_descends_monitor_body(self):
        descendant = Node(self.clock, "sensor")
        monitor, body = self.monitor_body(descendants=[descendant])
        self.assertEqual(list(self.native.walk(monitor)), [monitor, body, descendant])

    def test_strict_walk_still_rejects_defunct_monitor_body_descendant(self):
        descendant = Node(self.clock, "sensor")
        descendant.defunct = True
        monitor, _ = self.monitor_body(descendants=[descendant])
        with self.assertRaisesRegex(RuntimeError, "incomplete native tree.*defunct"):
            list(self.native.walk(monitor, strict=True))

    def test_repeated_lookup_keeps_original_deadline_across_monitor_boundaries(self):
        monitor, body = self.monitor_body()
        body.read_seconds = 0.5
        self.root.children = lambda: [monitor, self.panel]
        self.assertIs(self.lookup(deadline=5), self.cells[0])
        self.clock.now = 4.75
        with self.assertRaisesRegex(AssertionError, "deadline"):
            self.lookup(deadline=5)
        self.assertEqual(self.clock.now, 5.25)

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

    def test_detached_live_cached_row_cannot_supply_cell(self):
        self.native.cache.update({TARGET: self.row, CELL: self.cells[0]})
        self.panel.children = lambda: [self.other]
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.lookup()
        self.assertEqual(self.clock.now, 5)
        self.other.get_child_count.assert_not_called()

    def test_duplicate_row_fails_even_with_live_cached_match(self):
        self.native.cache[TARGET] = self.row
        duplicate = Node(self.clock, TARGET, children=lambda: self.cells)
        self.panel.children = lambda: [self.other, self.row, duplicate]
        with self.assertRaisesRegex(AssertionError, "nonunique native process row"):
            self.lookup()
        self.other.get_child_count.assert_not_called()

    def test_panel_reacquisition_ignores_foreign_row_cached_during_discovery(self):
        self.native.cache.clear()
        foreign_cell = Node(self.clock, CELL)
        foreign_row = Node(self.clock, TARGET, children=lambda: [foreign_cell])
        foreign_panel = Node(
            self.clock, name="unrelated", children=lambda: [foreign_row]
        )
        self.root.children = lambda: [self.panel, foreign_panel]
        self.assertIs(self.lookup(), self.cells[0])
        self.assertIs(self.native.cache[TARGET], self.row)
        self.other.get_child_count.assert_not_called()

    def test_defunct_panel_reacquisition_skips_unrelated_cells(self):
        stale = Node(self.clock, name="processes")
        stale.defunct = True
        self.native.cache["__panel:processes"] = stale
        self.assertIs(self.lookup(), self.cells[0])
        self.assertIs(self.native.cache["__panel:processes"], self.panel)
        self.other.get_child_count.assert_not_called()

    def test_detached_live_cached_panel_cannot_supply_cell(self):
        replacement = Node(self.clock, name="processes")
        self.root.children = lambda: [replacement]
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.lookup()
        self.assertEqual(self.clock.now, 5)
        self.assertIs(self.native.cache["__panel:processes"], replacement)

    def test_renamed_live_cached_panel_cannot_supply_cell(self):
        self.panel.name = "unrelated"
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.lookup()
        self.assertEqual(self.clock.now, 5)

    def test_wrong_role_live_cached_panel_cannot_supply_cell(self):
        self.panel.role = "button"
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.lookup()
        self.assertEqual(self.clock.now, 5)

    def test_duplicate_current_panels_fail_even_with_live_cached_match(self):
        duplicate = Node(self.clock, name="processes")
        self.root.children = lambda: [self.panel, duplicate]
        with self.assertRaisesRegex(AssertionError, "nonunique native Processes panel"):
            self.lookup()

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

    def slow_lookup(self):
        lookup = self.native.process_cell

        def delayed(aid, deadline=None):
            self.clock.now += 1
            return lookup(aid, deadline)

        self.native.process_cell = Mock(side_effect=delayed)

    def reveal(self):
        with patch("native_replay.time", self.clock):
            return reveal_process_cell(self.native, CELL, "Right", 5)

    def test_three_movements_with_one_second_lookup_fit_original_deadline(self):
        self.slow_lookup()
        self.cells[0].x = 3

        def move(key):
            self.clock.now += 0.25
            self.cells[0].x -= 1

        self.native.key.side_effect = move
        try:
            revealed = self.reveal()
        except TimeoutError as error:
            self.fail(f"three-movement gesture exhausted its deadline: {error}")
        self.assertIs(revealed, self.cells[0])
        self.assertEqual(self.native.key.call_count, 3)
        self.assertEqual(self.native.process_cell.call_count, 1)
        self.assertLess(self.clock.now, 5)

    def test_replaced_gesture_cell_reacquires_with_same_deadline(self):
        self.slow_lookup()

        def move(key):
            self.cells[0].defunct = True
            self.cells[0] = Node(self.clock, CELL)
            self.cells[0].x = 0

        self.native.key.side_effect = move
        self.assertIs(self.reveal(), self.cells[0])
        self.assertEqual(self.native.process_cell.call_count, 2)
        self.assertEqual(
            [call.args for call in self.native.process_cell.call_args_list],
            [(CELL, 5), (CELL, 5)],
        )
        self.assertLess(self.clock.now, 5)

    def test_wrong_gesture_identity_cannot_acknowledge_visibility(self):
        def move(key):
            self.cells[0].aid = "process:42:124:cell:0"
            self.cells[0].x = 0

        self.native.key.side_effect = move
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.reveal()
        self.assertEqual(self.clock.now, 5)
        self.assertEqual(self.native.key.call_count, 1)

    def test_transient_bounds_error_invalidates_gesture_cell(self):
        self.slow_lookup()
        bounds = self.native.bounds
        transport_error = self.native.wait.__func__.__globals__["GLib"].Error
        failed = False

        def transient(node):
            nonlocal failed
            if not failed:
                failed = True
                raise transport_error("node replaced during bounds read")
            return bounds(node)

        self.native.bounds = transient
        self.assertIs(self.reveal(), self.cells[0])
        self.assertEqual(self.native.process_cell.call_count, 2)
        self.assertLess(self.clock.now, 5)

    def test_slow_replacement_lookup_does_not_restart_gesture_deadline(self):
        self.slow_lookup()

        def move(key):
            self.clock.now = 4
            self.cells[0].defunct = True
            self.cells[0] = Node(self.clock, CELL)
            self.cells[0].x = 0

        self.native.key.side_effect = move
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.reveal()
        self.assertEqual(self.clock.now, 5)

    def test_repeated_geometry_transients_keep_original_gesture_deadline(self):
        self.slow_lookup()
        transport_error = self.native.wait.__func__.__globals__["GLib"].Error
        self.native.bounds = Mock(side_effect=transport_error("geometry unavailable"))
        with self.assertRaisesRegex(TimeoutError, "original deadline"):
            self.reveal()
        self.assertEqual(self.clock.now, 5)
        self.assertEqual(
            [call.args for call in self.native.process_cell.call_args_list],
            [(CELL, 5)] * 4,
        )
        self.native.key.assert_not_called()

    def test_final_metric_rechecks_membership_after_gesture_cell_reuse(self):
        def move(key):
            self.cells[0].x = 0
            self.panel.children = lambda: []

        self.native.key.side_effect = move
        self.native.metric = Mock(wraps=type(self.native).metric.__get__(self.native))
        with self.assertRaisesRegex(TimeoutError, "find process cell"):
            self.replay()
        self.native.metric.assert_called_once_with(CELL, "child-left")

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
