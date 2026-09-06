"""Bounded controlled-child inspection using exact prior native acknowledgement."""

import ast
import copy
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import native_replay

import test_native_cells as cells
import test_native_navigation as navigation


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.f = navigation.NavigationTests()
        self.f.setUp()

    def evidence(self, index=5):
        f = self.f
        publication = {
            "application_pid": 500,
            "sequence": 1,
            "render_revision": 1,
            "accepted_unix_ns": 0,
        }
        ack = {"target": f.endpoint, "index": index, "publication": publication}
        return {"acknowledgement": ack, "reference": dict(ack, source="navigation")}

    def observe(self, original_index=5, deadline=8, evidence=None):
        f = self.f
        self.assertIn(
            "inspection", inspect.signature(f.native.navigation_selection).parameters
        )
        return f.native.navigation_selection(
            f.endpoint,
            f.endpoint,
            deadline,
            fresh_panel=True,
            inspection=self.evidence(original_index) if evidence is None else evidence,
        )

    def test_navigation_exports_existing_final_proof_without_another_read(self):
        f = self.f
        self.assertIn(
            "on_acknowledged", inspect.signature(f.native.navigate).parameters
        )
        original = f.native.navigation_selection
        final_frames = []

        def observe(*args, **kwargs):
            result = original(*args, **kwargs)
            if kwargs.get("fresh_panel"):
                final_frames.append(result[1])
                f.native.frame = Mock(side_effect=AssertionError("extra native frame"))
            return result

        f.native.navigation_selection = observe
        acknowledged = Mock()
        selected = f.native.navigate(f.target, on_acknowledged=acknowledged)
        self.assertEqual(selected[0], f.target)
        acknowledged.assert_called_once_with(
            {
                "target": f.target,
                "index": 6,
                "publication": {
                    "application_pid": 500,
                    "sequence": 1,
                    "render_revision": 1,
                    "accepted_unix_ns": final_frames[0]["accepted_unix_ns"],
                },
            }
        )
        f.native.frame.assert_not_called()

    def test_one_row_shift_uses_inspection_reference_and_keeps_ack(self):
        f = self.f
        f.displaced_endpoint()
        f.ids.remove(f.endpoint)
        f.ids.insert(4, f.endpoint)
        f.visible_ids = f.ids[5:8]
        evidence = self.evidence()
        evidence["acknowledgement"]["index"] = 12
        evidence["reference"]["source"] = "child-visible-3.json"
        evidence["reference"]["publication"] = dict(
            evidence["reference"]["publication"], sequence=126
        )
        f.sequence = 132
        before = copy.deepcopy(evidence)
        self.assertEqual(self.observe(evidence=evidence)[0][0], f.endpoint)
        f.native.wheel.assert_called_once_with([400, 360], down=False, deadline=8)
        self.assertEqual(evidence, before)
        record = next(e[1] for e in f.events if e[0] == "inspection-row-reveal")
        self.assertEqual(record["acknowledgement"], before["acknowledgement"])
        self.assertEqual(record["reference"], before["reference"])
        self.assertEqual(record["reference_index"], 5)
        self.assertEqual(record["eligibility_index"], 4)
        self.assertEqual(record["eligibility_span"], [5, 7])
        self.assertEqual(record["deadline"], 8)
        self.assertNotIn("original_index", record)
        self.assertNotIn("endpoint_index", record)
        self.assertFalse(any(e[0] == "key" for e in f.events))
        proof = next(e[1] for e in f.events if e[0] == "inspection-row-reveal-proof")
        self.assertIn("publication", proof)
        self.assertEqual(proof["publication"]["sequence"], 132)
        self.assertEqual(proof["selected"], f.endpoint)
        self.assertEqual(proof["current_index"], 4)
        self.assertEqual(proof["current_span"], [2, 5])
        self.assertEqual(proof["deadline"], 8)

    def test_costed_gesture_reuses_only_established_recovery_links(self):
        # Illustrative costs, not measured native timings. The extra retry case
        # also charges a post-wheel publication rejection to the same five seconds.
        for ordinary_cost, strict_cost, rejection in (
            (1.0, 0.6, None),
            (0.95, 0.55, "publication"),
            (0.95, 0.55, "selected node"),
        ):
            with self.subTest(rejection=rejection):
                self.setUp()
                f = self.f
                f.displaced_endpoint()
                cell_id = f.endpoint + ":cell:4"
                cell = cells.Node(f.clock, cell_id)
                row = f.nodes[f.endpoint]
                row.get_child_count = lambda: 1
                row.get_child_at_index = lambda index: cell if index == 0 else None
                f.native.visible = lambda node: node is cell
                ordinary_scans = []
                walk = f.native.walk

                def costed_walk(root=None, deadline=None, **kwargs):
                    if root is None and not kwargs.get("strict"):
                        ordinary_scans.append(deadline)
                        f.clock.now += ordinary_cost
                    yield from walk(root, deadline, **kwargs)

                f.native.walk = costed_walk
                discover = f.native.navigation_panel

                def costed_discovery(deadline):
                    f.clock.now += strict_cost
                    return discover(deadline)

                f.native.navigation_panel = Mock(side_effect=costed_discovery)
                selected = f.native.selected
                rejected = False

                def changing(*args, **kwargs):
                    nonlocal rejected
                    result = selected(*args, **kwargs)
                    if rejection and f.native.wheel.called and not rejected:
                        rejected = True
                        if rejection == "publication":
                            f.sequence += 1
                        else:
                            result[1].defunct = True
                            replacement = f.nodes[f.endpoint] = f.row(f.endpoint)
                            replacement.get_child_count = lambda: 1
                            replacement.get_child_at_index = (
                                lambda index: cell if index == 0 else None
                            )
                    return result

                f.native.selected = changing
                inspection = native_replay.ProcessInspection(f.native, f.endpoint)
                inspection.acknowledge(self.evidence()["acknowledgement"])
                before = copy.deepcopy(inspection.reference)
                try:
                    with patch("native_replay.time", f.clock):
                        result = native_replay.reveal_process_cell(
                            f.native,
                            cell_id,
                            "Right",
                            5,
                            prepare_missing=inspection.preparation(),
                        )
                except (TimeoutError, AssertionError) as error:
                    self.fail(
                        f"redundant discovery exhausted synthetic five-second gesture: {error}; "
                        f"ordinary={len(ordinary_scans)}, "
                        f"strict={f.native.navigation_panel.call_count}, elapsed={f.clock.now}"
                    )
                self.assertIs(result, cell)
                self.assertEqual(ordinary_scans, [5, 5])
                self.assertEqual(f.native.navigation_panel.call_count, 3)
                self.assertAlmostEqual(f.clock.now, 4.8)
                self.assertEqual(rejected, rejection is not None)
                self.assertEqual(inspection.reference, before)
                f.native.wheel.assert_called_once_with(
                    [400, 360], down=False, deadline=5
                )
                self.assertTrue(
                    any(e[0] == "inspection-row-reveal-proof" for e in f.events)
                )
                self.assertFalse(any(e[0] == "key" for e in f.events))

    def test_initial_and_final_coherence_retries_rediscover_unique_panel(self):
        for rejected_scan in (1, 4):
            with self.subTest(rejected_scan=rejected_scan):
                self.setUp()
                f = self.f
                f.displaced_endpoint()
                selected = f.native.selected
                scans = 0
                discoveries_at_rejection = None

                def duplicate(*args, **kwargs):
                    nonlocal scans, discoveries_at_rejection
                    result = selected(*args, **kwargs)
                    scans += 1
                    if scans == rejected_scan:
                        discoveries_at_rejection = f.native.navigation_panel.call_count
                        f.sequence += 1
                        extra = cells.Node(f.clock, name="processes")
                        f.root.children = lambda: [f.panel, extra]
                    return result

                f.native.selected = duplicate
                with self.assertRaisesRegex(
                    AssertionError, "nonunique native Processes panel"
                ):
                    self.observe()
                self.assertEqual(scans, rejected_scan)
                self.assertEqual(
                    f.native.navigation_panel.call_count, discoveries_at_rejection + 1
                )
                self.assertEqual(
                    f.native.wheel.call_count, 0 if rejected_scan == 1 else 1
                )
                self.assertFalse(
                    any(e[0] == "inspection-row-reveal-proof" for e in f.events)
                )

    def test_post_wheel_incomplete_scan_requires_new_unique_discovery(self):
        f = self.f
        f.displaced_endpoint()
        selected = f.native.selected
        rejected = False
        discoveries_at_rejection = None

        def incomplete(*args, **kwargs):
            nonlocal rejected, discoveries_at_rejection
            if f.native.wheel.called and not rejected:
                rejected = True
                discoveries_at_rejection = f.native.navigation_panel.call_count
                child_at_index = f.viewport.get_child_at_index
                f.viewport.get_child_at_index = lambda index: None
                try:
                    return selected(*args, **kwargs)
                finally:
                    f.viewport.get_child_at_index = child_at_index
                    extra = cells.Node(f.clock, name="processes")
                    f.root.children = lambda: [f.panel, extra]
            return selected(*args, **kwargs)

        f.native.selected = incomplete
        with self.assertRaisesRegex(AssertionError, "nonunique native Processes panel"):
            self.observe()
        self.assertTrue(rejected)
        self.assertEqual(
            f.native.navigation_panel.call_count, discoveries_at_rejection + 1
        )
        f.native.wheel.assert_called_once()
        self.assertFalse(any(e[0] == "inspection-row-reveal-proof" for e in f.events))

    def test_post_wheel_broken_membership_reacquires_replacement_panel(self):
        f = self.f
        f.displaced_endpoint()
        original = f.panel

        def replace(point, down, *, deadline):
            f.reveal_wheel(point, down, deadline=deadline)
            f.panel = cells.Node(
                f.clock, name="processes", children=lambda: [f.viewport]
            )
            f.panel.get_parent = lambda: f.root
            f.panel.get_index_in_parent = lambda: 0

        f.native.wheel.side_effect = replace
        selected, _, path = self.observe()
        self.assertEqual(selected[0], f.endpoint)
        self.assertIs(path[0], f.panel)
        self.assertIsNot(path[0], original)
        self.assertEqual(f.native.navigation_panel.call_count, 4)
        f.native.wheel.assert_called_once()

    def test_missing_or_wrong_acknowledgement_cannot_scroll(self):
        for invalid in ("missing", "wrong", "wrong reference", "missing publication"):
            with self.subTest(invalid=invalid):
                self.setUp()
                f = self.f
                f.displaced_endpoint()
                evidence = self.evidence()
                if invalid == "missing":
                    evidence.pop("acknowledgement")
                elif invalid == "wrong":
                    evidence["acknowledgement"]["target"] = navigation.aid(99)
                elif invalid == "wrong reference":
                    evidence["reference"]["target"] = navigation.aid(99)
                else:
                    evidence["acknowledgement"].pop("publication")
                with self.assertRaisesRegex(AssertionError, "inspection"):
                    self.observe(evidence=evidence)
                f.native.wheel.assert_not_called()

    def test_inspection_reuses_strict_recovery_guards(self):
        guards = (
            "test_reveal_rejects_unchanged_index_and_original_slot_outside_span",
            "test_reveal_rejects_empty_duplicate_unmapped_or_noncontiguous_span",
            "test_reveal_rejects_incomplete_scan_and_invalid_current_membership",
            "test_reveal_rejects_stale_or_changing_frame",
            "test_reveal_requires_clips_and_live_viewport_membership",
            "test_reveal_cannot_accept_selection_transfer_or_duplicate_panel_after_scroll",
            "test_reveal_rejects_duplicate_current_panel_before_any_wheel",
            "test_reveal_membership_replacement_during_geometry_prevents_wheel",
            "test_reveal_publication_change_during_geometry_prevents_wheel",
            "test_reveal_rejected_first_geometry_discards_old_eligibility",
            "test_reveal_rejected_first_geometry_requires_new_unique_discovery",
        )
        for guard in guards:
            with self.subTest(guard=guard):
                self.setUp()
                self.f.observe_displaced = self.observe
                getattr(self.f, guard)()

    def test_observed_competitor_or_unselected_target_fails_before_later_recovery(self):
        for competitor in (False, True):
            with self.subTest(competitor=competitor):
                self.setUp()
                f = self.f
                f.displaced_endpoint()
                f.visible_ids = f.ids[2:6]
                f.selection = [f.visible_ids[1]] if competitor else None
                frames = 0

                def then_target():
                    nonlocal frames
                    frames += 1
                    if frames == 3:
                        f.selection = [f.endpoint]

                f.before_frame = then_target
                with self.assertRaisesRegex(AssertionError, "inspection selection"):
                    self.observe()
                f.native.wheel.assert_not_called()
                self.assertEqual(f.clock.now, 0)

    def test_exact_identity_loss_or_pid_reuse_cannot_scroll(self):
        for reuse in (False, True):
            with self.subTest(reuse=reuse):
                self.setUp()
                f = self.f
                f.displaced_endpoint()
                f.ids.remove(f.endpoint)
                if reuse:
                    f.ids.insert(2, f.endpoint.rsplit(":", 1)[0] + ":101")
                with self.assertRaisesRegex(AssertionError, "target absent"):
                    self.observe()
                f.native.wheel.assert_not_called()

    def test_inspection_journal_delay_prevents_physical_dispatch(self):
        for event in ("inspection-row-reveal", "wheel"):
            with self.subTest(event=event):
                self.setUp()
                f = self.f
                f.displaced_endpoint()
                f.physical_wheel()

                def slow(name, **fields):
                    f.journal(name, **fields)
                    if name == event:
                        f.clock.now += 8

                f.native.journal = slow
                with self.assertRaises((TimeoutError, AssertionError)):
                    self.observe()
                self.assertTrue(any(e[0] == event for e in f.events))
                self.assertEqual(f.physical_inputs, [])


class MissingRowTests(unittest.TestCase):
    def setUp(self):
        self.f = cells.NativeCellTests()
        self.f.setUp()

    def lookup(self, callback, deadline=5):
        self.assertIn(
            "prepare_missing", inspect.signature(self.f.native.process_cell).parameters
        )
        return self.f.native.process_cell(
            cells.CELL, deadline, prepare_missing=callback
        )

    def test_missing_row_prepares_before_lookup_spends_deadline_then_retries(self):
        f = self.f
        f.panel.children = lambda: [f.other]
        calls = []

        def prepare(deadline):
            calls.append((deadline, f.clock.now))
            f.clock.now += 1
            f.panel.children = lambda: [f.other, f.row]
            return f.other  # A preparation return value is never a cell result.

        self.assertIs(self.lookup(prepare), f.cells[0])
        self.assertEqual(calls, [(5, 0)])
        self.assertLess(f.clock.now, 5)

    def test_missing_panel_triggers_preparation_and_success_path_does_not(self):
        f = self.f
        callback = Mock()
        self.assertIs(self.lookup(callback), f.cells[0])
        callback.assert_not_called()
        f.root.children = lambda: []
        callback.side_effect = lambda deadline: setattr(
            f.root, "children", lambda: [f.panel]
        )
        self.assertIs(self.lookup(callback), f.cells[0])
        callback.assert_called_once_with(5)

    def test_callback_cannot_return_a_cell_or_restart_expired_budget(self):
        f = self.f
        f.panel.children = lambda: []

        def expire(deadline):
            f.clock.now = deadline
            return f.cells[0]

        with self.assertRaises(TimeoutError):
            self.lookup(expire)
        self.assertGreaterEqual(f.clock.now, 5)

    def test_default_discovery_resolves_one_fifteen_second_deadline(self):
        f = self.f
        f.panel.children = lambda: []
        calls = []

        def expire(deadline):
            calls.append(deadline)
            f.clock.now = deadline

        with self.assertRaises(TimeoutError):
            self.lookup(expire, None)
        self.assertEqual(calls, [15])


class InspectionWiringTests(unittest.TestCase):
    def setUp(self):
        self.f = cells.NativeCellTests()
        self.f.setUp()
        self.app = self.f.native
        self.ack = {
            "target": cells.TARGET,
            "index": 1,
            "publication": {
                "application_pid": 77,
                "sequence": 10,
                "render_revision": 9,
                "accepted_unix_ns": 1,
            },
        }

    def inspection(self):
        self.assertTrue(
            hasattr(native_replay, "ProcessInspection"),
            "caller-owned ProcessInspection missing",
        )
        inspection = native_replay.ProcessInspection(self.app, cells.TARGET)
        inspection.acknowledge(self.ack)
        return inspection

    def frame(self, index=0):
        rows = [{"identity": {"pid": 42, "start_time_ticks": 123}}]
        if index:
            rows.insert(0, {"identity": {"pid": 1, "start_time_ticks": 1}})
        return {
            "application_pid": 77,
            "snapshot": {"sequence": 11, "processes": rows},
            "render_revision": 10,
            "accepted_unix_ns": 2,
            "rendered": [{"element_id": cells.CELL}],
        }

    def artifact(self, index=0):
        return {"entry": {"element_id": cells.CELL}, "frame": self.frame(index)}

    def test_missing_acknowledgement_cannot_start_inspection(self):
        self.assertTrue(hasattr(native_replay, "ProcessInspection"))
        inspection = native_replay.ProcessInspection(self.app, cells.TARGET)
        self.app.metric.return_value = self.artifact()
        with self.assertRaisesRegex(AssertionError, "acknowledgement"):
            inspection.metric(cells.CELL, "unacknowledged")
        self.app.metric.assert_not_called()

    def test_acknowledgement_copies_caller_evidence_and_rejects_wrong_or_second_ack(
        self,
    ):
        inspection = self.inspection()
        original = copy.deepcopy(inspection.acknowledgement)
        self.ack["publication"]["sequence"] = 100
        self.assertEqual(inspection.acknowledgement, original)
        with self.assertRaisesRegex(AssertionError, "already acknowledged"):
            inspection.acknowledge(self.ack)
        fresh = native_replay.ProcessInspection(self.app, "process:42:124")
        with self.assertRaisesRegex(AssertionError, "wrong inspection acknowledgement"):
            fresh.acknowledge(self.ack)
        self.assertIsNone(fresh.acknowledgement)

    def test_failed_metric_identity_check_cannot_advance_reference(self):
        inspection = self.inspection()
        positive = copy.deepcopy(inspection.reference)
        artifact = self.artifact()
        artifact["entry"]["element_id"] = "process:42:124:cell:0"
        self.app.metric.return_value = artifact
        with self.assertRaisesRegex(AssertionError, "exact target"):
            inspection.metric(cells.CELL, "wrong-artifact")
        self.assertEqual(inspection.reference, positive)

    def test_reference_advances_only_after_successful_metric_and_freezes_per_call(self):
        inspection = self.inspection()
        before = copy.deepcopy(inspection.reference)
        callbacks = []
        observed = []
        self.app.navigation_selection = lambda *args, **kwargs: observed.append(
            kwargs["inspection"]
        )
        self.app.process_cell = Mock(side_effect=AssertionError("recursive lookup"))

        def metric(aid, name, *, visible, prepare_missing):
            callbacks.append(prepare_missing)
            self.assertEqual(inspection.reference, before)
            self.assertIsNone(prepare_missing(5))
            return self.artifact()

        self.app.metric = metric
        artifact = inspection.metric(cells.CELL, "child-visible-3", visible=True)
        self.assertEqual(artifact, self.artifact())
        self.assertEqual(inspection.acknowledgement, self.ack)
        self.assertEqual(inspection.reference["index"], 0)
        self.assertEqual(inspection.reference["source"], "child-visible-3.json")
        self.assertEqual(inspection.reference["publication"]["sequence"], 11)
        callbacks[0](5)
        self.assertTrue(all(record["reference"] == before for record in observed))
        self.app.process_cell.assert_not_called()
        positive = copy.deepcopy(inspection.reference)

        def fail(aid, name, *, visible, prepare_missing):
            prepare_missing(9)
            raise TimeoutError("metric failed")

        self.app.metric = fail
        with self.assertRaisesRegex(TimeoutError, "metric failed"):
            inspection.metric(cells.CELL, "failed")
        self.assertEqual(inspection.reference, positive)
        self.assertEqual(observed[-1]["reference"], positive)
        self.assertEqual(inspection.acknowledgement, self.ack)

    def test_real_metric_propagates_preparation_to_initial_and_in_bracket_lookup(self):
        f = self.f
        self.assertIn(
            "prepare_missing", inspect.signature(type(self.app).metric).parameters
        )
        self.app.__dict__.pop("metric")
        self.app.app = Mock(pid=77)
        self.app.app.poll.return_value = None
        self.app.save = Mock()
        self.app.ancestors = Mock(return_value=[])
        self.app.screenshot = Mock()
        self.app.metric.__func__.__globals__["expected_label"] = lambda frame, entry: ""
        f.panel.children = lambda: []
        original = f.cells[0]
        calls = []

        def prepare(deadline):
            calls.append((deadline, f.clock.now))
            f.clock.now += 1
            f.panel.children = lambda: [f.row]

        def frame():
            if not original.defunct:
                original.defunct = True
                f.cells[0] = cells.Node(f.clock, cells.CELL)
                f.cells[0].x = 0
                f.panel.children = lambda: []
            return self.frame()

        self.app.frame = frame
        result = self.app.metric(
            cells.CELL, "replacement", visible=False, prepare_missing=prepare
        )
        self.assertEqual(result["entry"]["element_id"], cells.CELL)
        self.assertEqual(calls, [(15, 0), (6.25, 1.25)])
        self.app.save.assert_any_call("replacement.json", result)

    def test_reveal_forwards_callback_on_initial_lookup_and_replacement(self):
        f = self.f
        self.assertIn(
            "prepare_missing",
            inspect.signature(native_replay.reveal_process_cell).parameters,
        )
        f.panel.children = lambda: []
        deadlines = []

        def prepare(deadline):
            deadlines.append(deadline)
            f.panel.children = lambda: [f.row]

        def move(key):
            f.cells[0].defunct = True
            f.cells[0] = cells.Node(f.clock, cells.CELL)
            f.cells[0].x = 0
            f.panel.children = lambda: []

        self.app.key.side_effect = move
        with patch("native_replay.time", f.clock):
            result = native_replay.reveal_process_cell(
                self.app, cells.CELL, "Right", 5, prepare_missing=prepare
            )
        self.assertIs(result, f.cells[0])
        self.assertEqual(deadlines, [5, 5])
        self.assertLess(f.clock.now, 5)

    def test_actual_replay_wires_navigation_and_all_sixteen_comparisons(self):
        self.inspection()  # Fail clearly before extracting the not-yet-wired boundary.
        source = Path(native_replay.__file__)
        tree = ast.parse(source.read_text())
        statements = None
        for node in ast.walk(tree):
            body = getattr(node, "body", [])
            if not isinstance(body, list):
                continue
            for start, statement in enumerate(body):
                if isinstance(statement, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "inspection"
                    for target in statement.targets
                ):
                    end = next(
                        i
                        for i in range(start, len(body))
                        if isinstance(body[i], ast.Expr)
                        and isinstance(body[i].value, ast.Call)
                        and isinstance(body[i].value.func, ast.Attribute)
                        and body[i].value.func.attr == "sequences"
                    )
                    statements = body[start:end]
        self.assertIsNotNone(statements, "controlled-child inspection boundary missing")
        self.app.save = Mock()
        self.app.navigate = Mock(
            side_effect=lambda target, *, on_acknowledged: (
                on_acknowledged(copy.deepcopy(self.ack)) or (target, self.f.row)
            )
        )
        calls = []
        self.app.navigation_selection = Mock()

        def metric(aid, name, *, visible, prepare_missing):
            calls.append((aid, name, visible, prepare_missing))
            prepare_missing(5)
            artifact = self.artifact()
            artifact["entry"]["element_id"] = aid
            return artifact

        def reveal(app, aid, key, deadline, *, prepare_missing):
            prepare_missing(deadline)

        self.app.metric = metric
        context = dict(
            vars(native_replay),
            app=self.app,
            target=cells.TARGET,
            time=self.f.clock,
            reveal_process_cell=reveal,
        )
        with patch("native_replay.time", self.f.clock):
            exec(
                compile(
                    ast.Module(body=statements, type_ignores=[]), str(source), "exec"
                ),
                context,
            )
        self.assertEqual(
            [c[0] for c in calls], [cells.TARGET + f":cell:{i}" for i in range(8)] * 2
        )
        self.assertEqual([c[2] for c in calls], [False] * 8 + [True] * 8)
        self.assertTrue(all(callable(c[3]) for c in calls))
        self.assertEqual(self.app.navigation_selection.call_count, 24)
        self.assertTrue(
            all(
                call.kwargs.get("inspection_missing_row") is True
                for call in self.app.navigation_selection.call_args_list
            )
        )
        self.app.navigate.assert_called_once()
        inspection = context["inspection"]
        self.assertEqual(inspection.reference["source"], "child-right.json")
        self.assertEqual(inspection.acknowledgement, self.ack)


class PreExitInspectionTests(unittest.TestCase):
    def setUp(self):
        self.f = navigation.NavigationTests()
        self.f.setUp()
        self.f.displaced_endpoint()
        f = self.f
        self.inspection = native_replay.ProcessInspection(f.native, f.endpoint)
        self.inspection.acknowledge(
            {
                "target": f.endpoint,
                "index": 5,
                "publication": {
                    "application_pid": 500,
                    "sequence": 1,
                    "render_revision": 1,
                    "accepted_unix_ns": 0,
                },
            }
        )
        # The final successful visible metric is the inspection reference.
        self.inspection.reference["source"] = "child-right.json"
        self.reference = copy.deepcopy(self.inspection.reference)
        self.ack = copy.deepcopy(self.inspection.acknowledgement)
        f.native.sequences = Mock(side_effect=lambda: setattr(f.clock, "now", 1))

    def replay_boundary(self):
        """Execute the real post-metric sequence wait and pre-shutdown proof."""
        source = Path(native_replay.__file__)
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            body = getattr(node, "body", [])
            if not isinstance(body, list):
                continue
            for end, statement in enumerate(body):
                if not (
                    isinstance(statement, ast.Assign)
                    and any(
                        isinstance(target, ast.Name) and target.id == "before_seq"
                        for target in statement.targets
                    )
                ):
                    continue
                start = max(
                    i
                    for i in range(end)
                    if isinstance(body[i], ast.Expr)
                    and isinstance(body[i].value, ast.Call)
                    and isinstance(body[i].value.func, ast.Attribute)
                    and body[i].value.func.attr == "sequences"
                )
                context = dict(
                    vars(native_replay),
                    app=self.f.native,
                    target=self.f.endpoint,
                    inspection=self.inspection,
                    time=self.f.clock,
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
        self.fail("controlled-child pre-exit boundary missing")

    def test_detached_cached_selected_target_cannot_override_current_competitor(self):
        f = self.f
        cached = cells.Node(f.clock, f.endpoint, role="table row")
        cached.get_state_set = lambda: SimpleNamespace(
            contains=lambda state: state == "selected"
        )
        f.native.cache[f.endpoint] = cached
        f.selection = [f.visible_ids[0]]
        with self.assertRaisesRegex(AssertionError, "inspection selection"):
            self.replay_boundary()
        f.native.sequences.assert_called_once_with()
        f.native.wheel.assert_not_called()
        self.assertEqual(self.inspection.reference, self.reference)
        self.assertEqual(self.inspection.acknowledgement, self.ack)

    def test_pre_exit_one_row_shift_recovers_with_original_deadline_and_reference(self):
        f = self.f
        f.ids.remove(f.endpoint)
        f.ids.insert(4, f.endpoint)
        f.visible_ids = f.ids[5:8]
        try:
            self.replay_boundary()
        except TimeoutError as error:
            self.fail(
                f"pre-exit proof cannot reveal displaced acknowledged child: {error}"
            )
        f.native.sequences.assert_called_once_with()
        f.native.wheel.assert_called_once_with([400, 360], down=False, deadline=6)
        self.assertEqual(self.inspection.reference, self.reference)
        self.assertEqual(self.inspection.acknowledgement, self.ack)
        self.assertFalse(any(event[0] == "key" for event in f.events))
        proof = next(e[1] for e in f.events if e[0] == "inspection-row-reveal-proof")
        self.assertEqual(proof["reference"], self.reference)
        self.assertEqual(proof["deadline"], 6)
        self.assertLess(f.clock.now, 6)

    def test_pre_exit_rejects_shift_without_valid_reference_slot(self):
        f = self.f
        self.inspection.reference["index"] = 2
        before = copy.deepcopy(self.inspection.reference)
        with self.assertRaises(TimeoutError):
            self.replay_boundary()
        f.native.wheel.assert_not_called()
        self.assertEqual(self.inspection.reference, before)


if __name__ == "__main__":
    unittest.main()
