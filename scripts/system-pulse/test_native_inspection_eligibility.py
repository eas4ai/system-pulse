"""One fresh missing-row eligibility observation keeps separate post-wheel proof."""

import unittest
from unittest.mock import Mock, patch

import native_replay
import test_native_cells as cells
import test_native_inspection as inspection_fixtures


class MissingRowEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = inspection_fixtures.InspectionTests(methodName="runTest")
        self.fixture.setUp()
        self.f = self.fixture.f

    def observe(self, original_index=5, deadline=8, evidence=None):
        f = self.fixture.f
        return f.native.navigation_selection(
            f.endpoint,
            f.endpoint,
            deadline,
            fresh_panel=True,
            inspection=self.fixture.evidence(original_index)
            if evidence is None
            else evidence,
            inspection_missing_row=True,
        )

    def test_costed_metric_callback_uses_one_fresh_eligibility_and_separate_proof(self):
        # Synthetic costs demonstrate removed work, not measured native latency.
        for cost in (0.7, 0.9):
            with self.subTest(cost=cost):
                self.setUp()
                f = self.f
                f.displaced_endpoint()
                cell_id = f.endpoint + ":cell:4"
                cell = cells.Node(f.clock, cell_id)
                row = f.nodes[f.endpoint]
                row.get_child_count = lambda: 1
                row.get_child_at_index = lambda index: cell if index == 0 else None
                f.native.visible = lambda node: node is cell
                inspection = native_replay.ProcessInspection(f.native, f.endpoint)
                inspection.acknowledge(self.fixture.evidence()["acknowledgement"])
                f.native.metric = Mock(
                    return_value={
                        "entry": {"element_id": cell_id},
                        "frame": f.native.frame(),
                    }
                )
                inspection.metric(cell_id, "callback-fixture")
                prepare_missing = f.native.metric.call_args.kwargs["prepare_missing"]
                ordinary = []
                discoveries = []
                selections = []
                wheels = []
                walk, discover, select = (
                    f.native.walk,
                    f.native.navigation_panel,
                    f.native.selected,
                )

                def costed_walk(root=None, deadline=None, **kwargs):
                    if root is None and not kwargs.get("strict"):
                        ordinary.append(deadline)
                        f.clock.now += cost
                    yield from walk(root, deadline, **kwargs)

                def costed_discovery(deadline):
                    discoveries.append((len(wheels), deadline))
                    f.clock.now += cost
                    return discover(deadline)

                def strict_selection(*args, **kwargs):
                    selections.append((len(wheels), args[0], kwargs["strict"]))
                    return select(*args, **kwargs)

                def wheel(point, down, *, deadline):
                    wheels.append((len(discoveries), len(selections), f.clock.now))
                    f.reveal_wheel(point, down, deadline=deadline)

                f.native.walk = costed_walk
                f.native.navigation_panel = costed_discovery
                f.native.selected = strict_selection
                f.native.wheel.side_effect = wheel
                with patch("native_replay.time", f.clock):
                    result = native_replay.reveal_process_cell(
                        f.native, cell_id, "Right", 5, prepare_missing=prepare_missing
                    )
                self.assertIs(result, cell)
                self.assertEqual(wheels, [(1, 1, 2 * cost)])
                self.assertEqual(discoveries, [(0, 5), (1, 5)])
                self.assertEqual(selections, [(0, 5, True), (1, 5, True), (1, 5, True)])
                self.assertEqual(ordinary, [5, 5])
                self.assertLess(f.clock.now, 5)
                self.assertTrue(
                    any(event[0] == "inspection-row-reveal-proof" for event in f.events)
                )
                self.assertFalse(any(event[0] == "key" for event in f.events))

    def test_opt_in_requires_inspection_evidence(self):
        f = self.f
        f.displaced_endpoint()
        with self.assertRaisesRegex(AssertionError, "missing-row.*inspection"):
            f.native.navigation_selection(
                f.endpoint, f.target, 5, endpoint_index=5, inspection_missing_row=True
            )
        f.native.navigation_panel.assert_not_called()
        f.native.wheel.assert_not_called()

    def test_missing_row_opt_in_preserves_inspection_guards_and_rejection_resets(self):
        # Exercise the same negative native trees through the new opt-in path.
        for name in (
            "test_inspection_reuses_strict_recovery_guards",
            "test_missing_or_wrong_acknowledgement_cannot_scroll",
            "test_observed_competitor_or_unselected_target_fails_before_later_recovery",
            "test_exact_identity_loss_or_pid_reuse_cannot_scroll",
            "test_post_wheel_incomplete_scan_requires_new_unique_discovery",
            "test_inspection_journal_delay_prevents_physical_dispatch",
        ):
            with self.subTest(guard=name):
                self.setUp()
                self.fixture.observe = self.observe
                getattr(self.fixture, name)()

    def test_wrong_pid_and_expired_budget_prevent_first_input(self):
        for invalid in ("pid", "deadline"):
            with self.subTest(invalid=invalid):
                self.setUp()
                f = self.f
                f.displaced_endpoint()
                if invalid == "pid":
                    f.native.app.pid = 999
                else:
                    f.clock.now = 5
                with self.assertRaises((AssertionError, TimeoutError)):
                    self.observe(deadline=5)
                f.native.wheel.assert_not_called()

    def test_post_wheel_stale_clipped_wrong_or_ambiguous_observations_cannot_pass(self):
        for invalid in ("stale", "clipped", "wrong", "ambiguous", "detached"):
            with self.subTest(invalid=invalid):
                self.setUp()
                f = self.f
                f.displaced_endpoint()

                def changed(point, down, *, deadline):
                    f.reveal_wheel(point, down, deadline=deadline)
                    if invalid == "stale":
                        f.stale = True
                    elif invalid == "clipped":
                        f.row_bounds[1] = 210
                    elif invalid == "wrong":
                        f.selection = [f.visible_ids[1]]
                    elif invalid == "ambiguous":
                        extra = cells.Node(f.clock, name="processes")
                        f.root.children = lambda: [f.panel, extra]
                    else:
                        f.root.children = lambda: []

                f.native.wheel.side_effect = changed
                with self.assertRaises((AssertionError, TimeoutError)):
                    self.observe(deadline=5)
                self.assertGreaterEqual(f.native.wheel.call_count, 1)
                self.assertFalse(
                    any(
                        event[0] in ("ack", "inspection-row-reveal-proof")
                        for event in f.events
                    )
                )
                self.assertLessEqual(f.clock.now, 5)

    def test_pre_exit_and_generic_navigation_keep_two_pre_wheel_observations(self):
        for mode in ("pre-exit", "generic"):
            with self.subTest(mode=mode):
                self.setUp()
                f = self.f
                f.displaced_endpoint()
                selected = f.native.selected
                scans_before_wheel = []

                def selection(*args, **kwargs):
                    if not f.native.wheel.called:
                        scans_before_wheel.append((args[0], kwargs["strict"]))
                    return selected(*args, **kwargs)

                f.native.selected = selection
                if mode == "pre-exit":
                    inspection = native_replay.ProcessInspection(f.native, f.endpoint)
                    inspection.acknowledge(self.fixture.evidence()["acknowledgement"])
                    f.native.navigation_selection = Mock(
                        wraps=f.native.navigation_selection
                    )
                    inspection.preparation()(5)
                    self.assertEqual(
                        set(f.native.navigation_selection.call_args.kwargs),
                        {"fresh_panel", "inspection"},
                    )
                else:
                    f.observe_displaced(deadline=5)
                self.assertEqual(scans_before_wheel, [(5, True), (5, True)])
                f.native.wheel.assert_called_once_with(
                    [400, 360], down=False, deadline=5
                )
