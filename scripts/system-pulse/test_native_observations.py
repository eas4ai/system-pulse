"""Bounded navigation failure context must preserve the original protocol."""

import unittest
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_native_navigation as fixtures
import test_native_pending_endpoint as pending_fixtures
from test_native_navigation import aid
from native_observations import NavigationObservations, navigation_observation


class NavigationObservationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NavigationTests(methodName="runTest")
        self.fixture.setUp()
        self.native = self.fixture.native

    def test_failure_artifact_error_cannot_replace_navigation_error(self):
        original = AssertionError("original navigation rejection")

        def fail(*args, **kwargs):
            raise original

        self.native._navigate = fail
        self.native.save.side_effect = OSError("failure artifact unavailable")
        with self.assertRaises(BaseException) as caught:
            self.native.navigate(self.fixture.target)
        self.assertIs(caught.exception, original)

    def test_navigation_failure_retains_no_selection_observations(self):
        self.fixture.selection = []

        def observe(target, deadline, **kwargs):
            return self.native.navigation_selection(
                aid(2),
                target,
                8,
                path=[self.fixture.panel, self.fixture.root],
                endpoint_index=2,
            )

        self.native._navigate = observe
        with self.assertRaises(TimeoutError):
            self.native.navigate(self.fixture.target)
        failures = [
            call.args[1]
            for call in self.native.save.call_args_list
            if call.args[0].startswith("navigation-failure-")
        ]
        self.assertEqual(len(failures), 1)
        self.assertIn(
            "observations", failures[0], "navigation observation history missing"
        )
        history = failures[0]["observations"]
        self.assertGreater(history["observed"], 0)
        record = history["records"][-1]
        self.assertEqual(record["expected"], aid(2))
        self.assertEqual(record["navigation_phase"], "enter table")
        self.assertEqual(record["endpoint_index"], 2)
        self.assertEqual(record["batch_deadline_monotonic"], 8)
        self.assertEqual(record["rejection_reason"], "no instantiated selection")
        self.assertEqual(record["scans"][-1]["instantiated_selected_count"], 0)
        self.assertTrue(record["scans"][-1]["complete"])

    def test_partial_walk_keeps_observed_rows_and_selection_without_extra_reads(self):
        original = AssertionError("strict walk interrupted")
        self.fixture.selection = [aid(0)]
        rows = [self.fixture.nodes[aid(index)] for index in (0, 1)]
        for row in rows:
            row.get_accessible_id = Mock(wraps=row.get_accessible_id)
            row.get_state_set = Mock(wraps=row.get_state_set)

        def partial(*args, **kwargs):
            yield from rows
            raise original

        self.native.walk = partial
        self.native._navigate = (
            lambda target, deadline, **kwargs: self.native.navigation_selection(
                aid(2),
                target,
                8,
                path=[self.fixture.panel, self.fixture.root],
                endpoint_index=2,
            )
        )
        with self.assertRaises(AssertionError) as caught:
            self.native.navigate(self.fixture.target)
        self.assertIs(caught.exception, original)
        failure = self.native.save.call_args.args[1]
        self.assertIn("observations", failure)
        record = failure["observations"]["records"][-1]
        self.assertEqual(record["active_phase"], "selection scan")
        self.assertIn("strict walk interrupted", record["exception"])
        scan = record["scans"][-1]
        self.assertFalse(scan["complete"])
        self.assertIsNone(scan["completed_monotonic_ns"])
        self.assertIsNotNone(scan["aborted_monotonic_ns"])
        self.assertEqual(scan["row_count"], 2)
        self.assertEqual(scan["instantiated_selected_count"], 1)
        self.assertEqual(scan["instantiated_selected"], [aid(0)])
        self.assertEqual(scan["mapped_span"], [0, 1])
        for row in rows:
            self.assertEqual(row.get_accessible_id.call_count, 1)
            self.assertEqual(row.get_state_set.call_count, 1)

    def test_partial_discovery_does_not_claim_a_completed_empty_scan(self):
        original = AssertionError("discovery interrupted")
        self.native.walk = Mock(side_effect=original)
        self.native._navigate = (
            lambda target, deadline, **kwargs: self.native.navigation_panel(8)
        )
        with self.assertRaises(AssertionError) as caught:
            self.native.navigate(self.fixture.target)
        self.assertIs(caught.exception, original)
        record = self.native.save.call_args.args[1]["observations"]["records"][-1]
        self.assertEqual(record["active_phase"], "panel discovery")
        self.assertFalse(record["discoveries"][-1]["complete"])
        self.assertIsNone(record["discoveries"][-1]["completed_monotonic_ns"])
        self.assertEqual(record["scans"], [])

    def test_competing_selection_and_changing_publications_remain_distinct(self):
        for changing in (False, True):
            with self.subTest(changing=changing):
                self.setUp()
                self.fixture.selection = [aid(1)]
                if changing:
                    self.fixture.before_children = lambda: setattr(
                        self.fixture, "revision", self.fixture.revision + 1
                    )
                self.native._navigate = (
                    lambda target, deadline, **kwargs: self.native.navigation_selection(
                        aid(2),
                        target,
                        8,
                        path=[self.fixture.panel, self.fixture.root],
                        endpoint_index=2,
                    )
                )
                with self.assertRaises(TimeoutError):
                    self.native.navigate(self.fixture.target)
                record = self.native.save.call_args.args[1]["observations"]["records"][
                    -1
                ]
                self.assertEqual(
                    record["rejection_reason"],
                    "publication changed during selection"
                    if changing
                    else "competing instantiated selection",
                )
                self.assertEqual(record["scans"][-1]["instantiated_selected"], [aid(1)])
                publications = {
                    entry["phase"]: entry for entry in record["publications"]
                }
                before, after = (
                    publications[phase]["render_revision"]
                    for phase in ("before selection", "after selection")
                )
                self.assertEqual(before != after, changing)
                self.assertFalse(
                    any(event[0] == "key" for event in self.fixture.events)
                )

    def test_real_failure_file_contains_bounded_history_and_clears_active_state(self):
        with tempfile.TemporaryDirectory() as directory:
            self.native.output = Path(directory)
            self.native.save = type(self.native).save.__get__(self.native)
            self.native._navigate = (
                lambda target, deadline, **kwargs: self.native.navigation_selection(
                    aid(2),
                    target,
                    8,
                    path=[self.fixture.panel, self.fixture.root],
                    endpoint_index=2,
                )
            )
            with self.assertRaises(TimeoutError):
                self.native.navigate(self.fixture.target)
            artifacts = list(Path(directory).glob("navigation-failure-*.json"))
            self.assertEqual(len(artifacts), 1)
            history = json.loads(artifacts[0].read_text())["observations"]
            self.assertGreater(history["observed"], 0)
            self.assertLessEqual(len(history["records"]), 64)
            self.assertIsNone(self.native.navigation_observations)
            self.assertEqual(self.fixture.clock.now, 8)

    def test_first_recovery_blocking_observation_survives_later_empty_scans(self):
        def before_children():
            self.fixture.selection = [aid(1)] if self.fixture.clock.now == 0 else []

        self.fixture.before_children = before_children
        self.native._navigate = (
            lambda target, deadline, **kwargs: self.native.navigation_selection(
                aid(2),
                target,
                8,
                path=[self.fixture.panel, self.fixture.root],
                endpoint_index=2,
            )
        )
        with self.assertRaises(TimeoutError):
            self.native.navigate(self.fixture.target)
        records = self.native.save.call_args.args[1]["observations"]["records"]
        self.assertGreater(len(records), 1)
        self.assertEqual(records[0]["scans"][-1]["instantiated_selected"], [aid(1)])
        self.assertEqual(records[-1]["scans"][-1]["instantiated_selected"], [])
        for record in records:
            self.assertTrue(record["recovery"]["blocked"])
            self.assertEqual(
                record["recovery"]["blocked_at_observation"],
                records[0]["observation_id"],
            )
            self.assertEqual(
                record["recovery"]["blocked_reason"], "competing instantiated selection"
            )

    def test_partial_mapping_failure_preserves_original_scan_error(self):
        history = NavigationObservations(self.fixture.clock, self.fixture.target, 180)
        native = SimpleNamespace(navigation_observations=history)
        original = AssertionError("scan interrupted")
        with self.assertRaises(AssertionError) as caught:
            with navigation_observation(native, "selection", 8) as record:
                try:
                    with record.stage("scan"):
                        raise original
                except BaseException:
                    record.partial_mapping([aid(0)], {"snapshot": {"processes": [{}]}})
                    raise
        self.assertIs(caught.exception, original)
        scan = history.snapshot()["records"][-1]["scans"][-1]
        self.assertIsNone(scan["mapped_span"])
        self.assertIsNone(scan["complete_span"])
        self.assertIn("KeyError", scan["mapping_error"])

    def assert_malformed_scan_publication_preserves_error(self, *, pending, malformed):
        if pending:
            fixture = pending_fixtures.PendingEndpointTests(methodName="runTest")
            fixture.setUp()
            fixture.disappear_before_ack()
            self.fixture, self.native = fixture.f, fixture.f.native
        else:
            self.native._navigate = (
                lambda target, deadline, **kwargs: self.native.navigation_selection(
                    aid(2),
                    target,
                    8,
                    path=[self.fixture.panel, self.fixture.root],
                    endpoint_index=2,
                )
            )
        phase = (
            "publication before pending scan"
            if pending
            else "publication before selection"
        )
        publication_phase = "before pending scan" if pending else "before selection"
        original = AssertionError("primary strict scan failure")
        frame, walk = self.native.frame, self.native.walk
        interrupted = 0

        def preceding_frame():
            result = frame()
            observation = self.native.navigation_observations.current
            if observation is not None and observation.data["active_phase"] == phase:
                if malformed == "missing processes":
                    result["snapshot"].pop("processes")
                else:
                    result["snapshot"] = None
            return result

        def interrupted_walk(*args, **kwargs):
            nonlocal interrupted
            observation = self.native.navigation_observations.current
            if (
                observation is not None
                and observation.data["active_phase"] == "selection scan"
                and observation.data["publications"][-1]["phase"] == publication_phase
            ):
                interrupted += 1
                yield self.fixture.nodes[aid(0)]
                raise original
            yield from walk(*args, **kwargs)

        self.native.frame, self.native.walk = preceding_frame, interrupted_walk
        with self.assertRaises(AssertionError) as caught:
            self.native.navigate(self.fixture.target)
        self.assertIs(caught.exception, original)
        self.assertEqual(interrupted, 1)
        record = self.native.save.call_args.args[1]["observations"]["records"][-1]
        self.assertEqual(
            record["exception"], "AssertionError: primary strict scan failure"
        )
        scan = record["scans"][-1]
        self.assertFalse(scan["complete"])
        self.assertEqual(scan["row_count"], 1)
        self.assertIsNone(scan["mapped_span"])
        self.assertIsNone(scan["complete_span"])
        self.assertIn(
            "KeyError" if malformed == "missing processes" else "TypeError",
            scan["mapping_error"],
        )
        self.assertLessEqual(len(scan["mapping_error"]), 512)

    def test_interrupted_initial_scan_preserves_error_with_malformed_publication(self):
        for malformed in ("missing processes", "null snapshot"):
            with self.subTest(malformed=malformed):
                self.setUp()
                self.assert_malformed_scan_publication_preserves_error(
                    pending=False, malformed=malformed
                )

    def test_interrupted_pending_scan_preserves_error_with_malformed_publication(self):
        for malformed in ("missing processes", "null snapshot"):
            with self.subTest(malformed=malformed):
                self.setUp()
                self.assert_malformed_scan_publication_preserves_error(
                    pending=True, malformed=malformed
                )

    def test_serialization_failure_preserves_original_180_second_wrapper(self):
        original = RuntimeError("underlying navigation failure")

        def fail(*args, **kwargs):
            self.fixture.clock.now = 180
            raise original

        self.native._navigate = fail
        with patch.object(
            NavigationObservations,
            "snapshot",
            side_effect=TypeError("cannot serialize history"),
        ):
            with self.assertRaises(TimeoutError) as caught:
                self.native.navigate(self.fixture.target)
        self.assertIs(caught.exception.__cause__, original)
        self.assertIn(
            "child navigation original180s deadline expired", str(caught.exception)
        )
        self.assertTrue(
            any("cannot serialize history" in note for note in original.__notes__)
        )
        self.assertEqual(self.fixture.clock.now, 180)

    def test_success_has_identical_native_procfs_input_and_save_calls(self):
        observations = []
        for enabled in (False, True):
            self.setUp()
            calls = []
            for index, node in enumerate(
                [
                    self.fixture.panel,
                    self.fixture.root,
                    self.fixture.desktop,
                    *self.fixture.nodes.values(),
                ]
            ):
                for name in (
                    "clear_cache",
                    "clear_cache_single",
                    "get_accessible_id",
                    "get_state_set",
                    "get_name",
                    "get_role_name",
                    "get_child_count",
                    "get_child_at_index",
                    "get_parent",
                    "get_index_in_parent",
                    "get_process_id",
                ):
                    if hasattr(node, name):
                        original = getattr(node, name)

                        def tracked(
                            *args,
                            _original=original,
                            _name=name,
                            _index=index,
                            **kwargs,
                        ):
                            calls.append((_index, _name, args, kwargs))
                            return _original(*args, **kwargs)

                        setattr(node, name, tracked)
            for name in ("frame", "navigation_stat", "key"):
                original = getattr(self.native, name)

                def tracked(*args, _original=original, _name=name, **kwargs):
                    calls.append((_name, args, kwargs))
                    return _original(*args, **kwargs)

                setattr(self.native, name, tracked)
            original_navigate = self.native._navigate

            def navigate(*args, **kwargs):
                if not enabled:
                    self.native.navigation_observations = None
                return original_navigate(*args, **kwargs)

            self.native._navigate = navigate
            self.assertEqual(
                self.native.navigate(self.fixture.target)[0], self.fixture.target
            )
            observations.append(
                (calls, self.fixture.events, self.native.save.call_args_list)
            )
            self.assertIsNone(self.native.navigation_observations)
        self.assertEqual(observations[0], observations[1])


class ObservationBoundsTests(unittest.TestCase):
    def test_history_and_individual_fields_are_bounded_and_never_retain_handles(self):
        clock = SimpleNamespace(monotonic_ns=lambda: 1)
        history = NavigationObservations(clock, "t" * 5000, 180)
        native = SimpleNamespace(navigation_observations=history)
        for index in range(70):
            with navigation_observation(
                native, "p" * 5000, 8, "e" * 5000, index
            ) as record:
                for _ in range(5):
                    with record.stage("scan"):
                        for row in range(50):
                            record.row("r" * 5000)
                            record.selection("s" * 5000, True)
                    with record.stage("discovery"):
                        pass
                for _ in range(20):
                    record.publication(
                        "p" * 5000,
                        {
                            "application_pid": 1,
                            "render_revision": index,
                            "accepted_unix_ns": 0,
                            "snapshot": {
                                "sequence": index,
                                "processes": [object()] * 1000,
                            },
                        },
                    )
                    record.panel(True, "c" * 5000)
                record.reject("error" * 5000)
        snapshot = history.snapshot()
        self.assertEqual(
            (snapshot["observed"], snapshot["evicted"], len(snapshot["records"])),
            (70, 6, 64),
        )
        self.assertEqual(snapshot["records"][0]["endpoint_index"], 6)
        record = snapshot["records"][-1]
        self.assertEqual(record["publication_count"], 20)
        self.assertEqual(len(record["publications"]), 6)
        self.assertEqual(len(record["panel_checks"]), 8)
        self.assertEqual(record["scan_count"], 5)
        self.assertEqual(record["discovery_count"], 5)
        self.assertEqual(len(record["scans"]), 2)
        self.assertEqual(len(record["discoveries"]), 2)
        scan = record["scans"][-1]
        self.assertEqual(
            (scan["row_count"], scan["instantiated_selected_count"]), (50, 50)
        )
        self.assertEqual(len(scan["row_identity_sample"]), 8)
        self.assertEqual(len(scan["instantiated_selected"]), 8)

        def inspect(value):
            if isinstance(value, dict):
                self.assertNotIn("processes", value)
                for child in value.values():
                    inspect(child)
            elif isinstance(value, list):
                self.assertLessEqual(len(value), 64)
                for child in value:
                    inspect(child)
            elif isinstance(value, str):
                self.assertLessEqual(len(value), 512)
            else:
                self.assertIn(type(value), (int, float, bool, type(None)))

        inspect(snapshot)
        json.dumps(snapshot)
