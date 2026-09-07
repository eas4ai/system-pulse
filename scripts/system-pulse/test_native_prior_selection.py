"""A bounded prior native ACK prefix cannot replace fresh endpoint proof."""

import copy
import json
import unittest
from unittest.mock import Mock, patch

import native_pending
import test_native_navigation as navigation
import test_native_pending_endpoint as pending_fixtures

aid = navigation.aid


class PriorSelectionTests(unittest.TestCase):
    def setUp(self):
        self.f = navigation.NavigationTests(methodName="runTest")
        self.f.setUp()
        f = self.f
        f.displaced_endpoint()
        f.ids = [aid(pid) for pid in range(20)]
        f.visible_ids = list(f.ids)
        f.selection = None
        f.endpoint, f.target = aid(17), aid(12)
        self.prior = aid(19)
        self.active = False
        self.shifted = False
        self.dispatch_at = None
        self.in_batch = False
        self.acknowledgements = []
        self.pending = None
        self.scans = []
        self.shift_after = 0.5
        self.before_selection = lambda: None
        self.mutate_pending = lambda value: None
        key, frame_text = f.native.key, f.frame_text
        observe, selected = f.native.navigation_selection, f.native.selected

        def issue(value, **kwargs):
            key(value, **kwargs)
            if f.pending and f.pending[1] == f.endpoint:
                self.active = True
                self.dispatch_at = f.clock.now
                f.visible_ids = [self.prior]

        def shift():
            if (
                self.active
                and not self.shifted
                and self.shift_after is not None
                and f.clock.now >= self.dispatch_at + self.shift_after
            ):
                self.shift()

        def published_frame():
            result = json.loads(frame_text())
            if self.active and not self.shifted:
                # Two observations share the immutable issued publication tuple.
                publication = self.acknowledgements[-1]["publication"]
                result["accepted_unix_ns"] = publication["accepted_unix_ns"]
            return json.dumps(result)

        def selection(*args, **kwargs):
            if self.in_batch:
                self.before_selection()
            result = selected(*args, **kwargs)
            if self.in_batch:
                self.scans.append(result[0] if result else None)
            return result

        def observation(*args, **kwargs):
            self.in_batch = args[0] == f.endpoint and kwargs.get("pending") is not None
            if self.in_batch:
                kwargs["pending"] = copy.deepcopy(kwargs["pending"])
                self.mutate_pending(kwargs["pending"])
                self.pending = copy.deepcopy(kwargs["pending"])
            result = observe(*args, **kwargs)
            if (
                not isinstance(result, native_pending.InterruptedNavigation)
                and result[0]
            ):
                identity, frame = result[0][0], result[1]
                ids = [
                    aid(row["identity"]["pid"], row["identity"]["start_time_ticks"])
                    for row in frame["snapshot"]["processes"]
                ]
                self.acknowledgements.append(
                    {
                        "identity": identity,
                        "index": ids.index(identity),
                        "publication": native_pending.publication(frame),
                    }
                )
                if identity == f.endpoint:
                    f.visible_ids = list(f.ids)
            self.in_batch = False
            return result

        f.native.key = issue
        f.before_frame = shift
        f.frame_text = published_frame
        f.native.selected = selection
        f.native.navigation_selection = observation
        f.native.navigation_stat = Mock(wraps=f.native.navigation_stat)
        f.native.wheel.side_effect = lambda point, down, *, deadline: setattr(
            f, "visible_ids", f.ids[16:20]
        )

    def shift(self):
        f = self.f
        self.shifted = True
        f.ids.remove(f.endpoint)
        f.ids.insert(16, f.endpoint)
        f.visible_ids = f.ids[17:20]
        f.sequence += 1
        f.revision += 1

    def assert_no_endpoint_ack(self):
        self.assertNotIn(
            self.f.endpoint, [entry["identity"] for entry in self.acknowledgements]
        )

    def test_prior_prefix_then_absence_reindex_requires_actual_expected_ack(self):
        f = self.f
        self.assertEqual(f.navigate()[0], f.target)
        self.assertEqual(self.scans[:2], [self.prior, self.prior])
        self.assertIn(None, self.scans[2:])
        self.assertEqual(self.scans[-1], f.endpoint)
        f.native.wheel.assert_called_once_with([400, 360], down=False, deadline=8.5)
        self.assertEqual(
            [entry["identity"] for entry in self.acknowledgements[:2]],
            [self.prior, f.endpoint],
        )
        self.assertEqual(
            sum(
                call.args == (f.endpoint,)
                for call in f.native.navigation_stat.call_args_list
            ),
            1,
        )

    def test_pending_binds_the_already_returned_positive_ack(self):
        f = self.f
        try:
            f.navigate()
        except (TimeoutError, AssertionError):
            pass
        self.assertIsNotNone(self.pending)
        proof = self.pending.get("prior_acknowledgement")
        self.assertIsNotNone(proof, "pending batch lost the actual returned native ACK")
        for field in ("identity", "index", "publication"):
            self.assertEqual(proof[field], self.acknowledgements[0][field])
        for field in (
            "expected",
            "target",
            "endpoint_index",
            "keys",
            "batch_deadline",
            "deadline",
            "dispatch_started",
            "dispatch_completed",
        ):
            self.assertEqual(proof[field], self.pending[field])

    def test_absent_proof_keeps_the_original_blocking_behavior(self):
        self.before_selection = self.visible_prior_prefix
        self.mutate_pending = lambda pending: pending.pop("prior_acknowledgement", None)
        with self.assertRaises(TimeoutError):
            self.f.navigate()
        self.f.native.wheel.assert_not_called()
        self.assert_no_endpoint_ack()
        self.assertEqual(self.f.clock.now, 8.5)

    def test_persistent_prior_selection_never_authorizes_input_or_ack(self):
        f = self.f
        self.shift_after = None

        def prior():
            f.pending = None
            f.selection = [self.prior]

        self.before_selection = prior
        with self.assertRaisesRegex(AssertionError, "accepted frame stale"):
            f.navigate()
        self.assertTrue(self.scans and all(value == self.prior for value in self.scans))
        f.native.wheel.assert_not_called()
        self.assert_no_endpoint_ack()

    def visible_prior_prefix(self):
        if not self.shifted:
            self.f.visible_ids = self.f.ids[17:20]

    def test_visible_expected_with_persistent_prior_times_out_without_input_or_ack(
        self,
    ):
        f = self.f
        self.shift_after = None
        # A valid supported interval keeps the immutable issue frame fresh through
        # the original eight-second batch deadline; no stale-frame shortcut.
        f.native.interval_ms = 5000

        def prior():
            self.visible_prior_prefix()
            f.pending = None
            f.selection = [self.prior]

        self.before_selection = prior
        with self.assertRaises(TimeoutError):
            f.navigate()
        self.assertTrue(self.scans and all(value == self.prior for value in self.scans))
        self.assertEqual(f.clock.now, 8.5)
        f.native.wheel.assert_not_called()
        self.assert_no_endpoint_ack()

    def test_visible_expected_without_selection_blocks_later_prior_and_absence(self):
        f = self.f

        def returning():
            f.pending = None
            self.visible_prior_prefix()
            f.selection = [self.prior] if len(self.scans) == 1 else []

        self.before_selection = returning
        with self.assertRaises(TimeoutError):
            f.navigate()
        self.assertEqual(self.scans[:3], [None, self.prior, None])
        f.native.wheel.assert_not_called()
        self.assert_no_endpoint_ack()

    def test_prior_returning_after_coherent_absence_stays_blocked(self):
        f = self.f
        self.shift_after = None

        def returning():
            f.pending = None
            step = len(self.scans)
            f.selection = [self.prior] if step in (0, 2) else []
            f.visible_ids = f.ids[17:20] if step in (0, 2) else [self.prior]
            if step == 3:
                self.shift()

        self.before_selection = returning
        with self.assertRaises(TimeoutError):
            f.navigate()
        self.assertEqual(self.scans[:3], [self.prior, None, self.prior])
        f.native.wheel.assert_not_called()
        self.assert_no_endpoint_ack()

    def test_prior_after_publication_advance_is_a_permanent_competitor(self):
        f = self.f

        def returning():
            self.visible_prior_prefix()
            if self.shifted:
                f.pending = None
                f.selection = [self.prior] if len(self.scans) == 2 else []

        self.before_selection = returning
        with self.assertRaises(TimeoutError):
            f.navigate()
        self.assertEqual(self.scans[:3], [self.prior] * 3)
        f.native.wheel.assert_not_called()
        self.assert_no_endpoint_ack()

    def test_visible_expected_prior_prefix_defers_until_fresh_exact_ack(self):
        f = self.f
        prefix = []

        def visible():
            if not self.shifted:
                f.visible_ids = f.ids[17:20]
                prefix.append((list(f.visible_ids), f.native.wheel.call_count))

        self.before_selection = visible
        self.assertEqual(f.navigate()[0], f.target)
        self.assertEqual(self.scans[:2], [self.prior, self.prior])
        self.assertEqual(prefix, [([aid(17), aid(18), self.prior], 0)] * 2)
        self.assertIn(None, self.scans[2:])
        self.assertEqual(self.scans[-1], f.endpoint)
        f.native.wheel.assert_called_once_with([400, 360], down=False, deadline=8.5)
        self.assertEqual(
            [entry["identity"] for entry in self.acknowledgements[:2]],
            [self.prior, f.endpoint],
        )
        self.assertEqual(self.acknowledgements[1]["index"], 16)
        self.assertNotEqual(
            self.acknowledgements[0]["publication"],
            self.acknowledgements[1]["publication"],
        )

    def test_distinct_competitor_cannot_be_excused_as_a_prior_prefix(self):
        f = self.f

        def competitor():
            self.visible_prior_prefix()
            if not self.scans:
                f.pending = None
                f.selection = [aid(18)]
            else:
                f.selection = [self.prior] if len(self.scans) == 1 else []

        self.before_selection = competitor
        with self.assertRaises(TimeoutError):
            f.navigate()
        self.assertEqual(self.scans[:3], [aid(18), self.prior, None])
        f.native.wheel.assert_not_called()
        self.assert_no_endpoint_ack()

    def test_hidden_prior_selection_cannot_manufacture_expected_ack_after_reveal(self):
        f = self.f

        def hidden_prior():
            self.visible_prior_prefix()
            if self.shifted:
                f.pending = None
                f.selection = [self.prior]
                f.visible_ids = f.ids[16:19] if f.native.wheel.called else f.ids[17:19]

        self.before_selection = hidden_prior
        with self.assertRaises(TimeoutError):
            f.navigate()
        f.native.wheel.assert_called_once()
        self.assert_no_endpoint_ack()

    def test_supplied_malformed_ack_or_binding_fails_before_pending_scan(self):
        mutations = {
            "missing proof object": lambda p: p.update(prior_acknowledgement=None),
            "identity": lambda p: p["prior_acknowledgement"].update(identity=aid(18)),
            "index": lambda p: p["prior_acknowledgement"].update(index=18),
            "publication": lambda p: p["prior_acknowledgement"]["publication"].update(
                render_revision=9
            ),
            "expected": lambda p: p["prior_acknowledgement"].update(expected=aid(16)),
            "target": lambda p: p["prior_acknowledgement"].update(target=aid(11)),
            "endpoint index": lambda p: p["prior_acknowledgement"].update(
                endpoint_index=16
            ),
            "direction": lambda p: p["prior_acknowledgement"].update(
                keys=["Down", "Down"]
            ),
            "count": lambda p: p["prior_acknowledgement"].update(keys=["Up"]),
            "start": lambda p: p["prior_acknowledgement"].update(dispatch_started=0),
            "end": lambda p: p["prior_acknowledgement"].update(dispatch_completed=0),
            "batch deadline": lambda p: p["prior_acknowledgement"].update(
                batch_deadline=9
            ),
            "total deadline": lambda p: p["prior_acknowledgement"].update(deadline=181),
            "unbounded identity": lambda p: p["prior_acknowledgement"].update(
                identity="x" * 1000
            ),
            "unbounded index": lambda p: p["prior_acknowledgement"].update(
                index=1 << 100
            ),
            "boolean index": lambda p: p["prior_acknowledgement"].update(index=True),
        }
        for name, mutate in mutations.items():
            with self.subTest(malformed=name):
                self.setUp()
                self.mutate_pending = mutate
                self.before_selection = self.visible_prior_prefix
                with self.assertRaisesRegex(AssertionError, "prior.*acknowledgement"):
                    self.f.navigate()
                self.assertEqual(self.scans, [])
                self.f.native.wheel.assert_not_called()
                self.assert_no_endpoint_ack()

    def test_rejected_publication_advance_cannot_reopen_prefix_on_old_tuple(self):
        f = self.f
        self.shift_after = None
        before_frame = f.before_frame
        after_first_scan = 0

        def restore():
            nonlocal after_first_scan
            before_frame()
            if len(self.scans) == 1 and not self.shifted:
                after_first_scan += 1
                if after_first_scan >= 2:
                    f.sequence = 1

        def advance():
            self.visible_prior_prefix()
            f.pending = None
            if not self.scans:
                f.sequence = 2  # Reject the first scan's publication bracket.
            elif len(self.scans) == 2:
                self.shift()
                f.selection = []

        f.before_frame = restore
        self.before_selection = advance
        with self.assertRaises(TimeoutError):
            f.navigate()
        self.assertEqual(self.scans[:2], [self.prior, self.prior])
        f.native.wheel.assert_not_called()
        self.assert_no_endpoint_ack()

    def test_expiry_in_either_recovery_journal_prevents_physical_input(self):
        for event in ("navigation-endpoint-reveal", "wheel"):
            with self.subTest(event=event):
                self.setUp()
                f = self.f
                self.before_selection = self.visible_prior_prefix
                f.physical_wheel()

                def journal(name, **fields):
                    f.journal(name, **fields)
                    if name == event:
                        f.clock.now = 8.5

                f.native.journal = journal
                with self.assertRaises((AssertionError, TimeoutError)):
                    f.navigate()
                self.assertTrue(any(value[0] == event for value in f.events))
                self.assertEqual(f.physical_inputs, [])
                self.assert_no_endpoint_ack()

    def test_ack_binding_uses_no_journal_or_navigation_history(self):
        f = self.f
        navigate = f.native._navigate

        def without_history(*args, **kwargs):
            f.native.navigation_observations = None
            return navigate(*args, **kwargs)

        f.native._navigate = without_history
        f.native.journal = Mock()
        self.assertEqual(f.navigate()[0], f.target)
        self.assertEqual(self.pending["prior_acknowledgement"]["identity"], self.prior)
        f.native.wheel.assert_called_once()

    def test_publication_or_issue_identity_changes_omit_optional_proof(self):
        try:
            self.f.navigate()
        except (AssertionError, TimeoutError):
            pass
        self.assertIsNotNone(self.pending)
        actual_ack = self.acknowledgements[0]
        ids = [aid(pid) for pid in range(20)]
        changes = (
            "publication",
            "missing prior",
            "duplicate prior",
            "duplicate expected",
            "duplicate target",
            "index",
        )
        for change in changes:
            with self.subTest(change=change):
                pending, issued_ids = copy.deepcopy(self.pending), list(ids)
                if change == "publication":
                    pending["publication"]["render_revision"] += 1
                elif change == "missing prior":
                    issued_ids.remove(self.prior)
                elif change == "index":
                    issued_ids[18], issued_ids[19] = issued_ids[19], issued_ids[18]
                else:
                    issued_ids.append(
                        {
                            "duplicate prior": self.prior,
                            "duplicate expected": self.f.endpoint,
                            "duplicate target": self.f.target,
                        }[change]
                    )
                self.assertIsNone(
                    native_pending.prepare_prior_acknowledgement(
                        actual_ack, pending, issued_ids
                    )
                )

    def test_capture_keeps_only_bounded_values_from_existing_ack_frame(self):
        frame = self.f.native.frame()
        frame["snapshot"]["unrelated"] = [object()] * 1000
        captured = native_pending.capture_acknowledgement(self.prior, frame)
        self.assertEqual(set(captured), {"identity", "index", "publication"})
        frame["accepted_unix_ns"] += 1
        self.assertNotEqual(
            captured["publication"]["accepted_unix_ns"], frame["accepted_unix_ns"]
        )
        self.assertEqual(captured["identity"], self.prior)
        self.assertEqual(captured["index"], 19)
        self.assertLess(len(json.dumps(captured)), 256)

    def test_default_navigation_has_identical_source_input_and_artifact_calls(self):
        runs = []
        capture = native_pending.capture_acknowledgement
        for enabled in (False, True):
            f = navigation.NavigationTests(methodName="runTest")
            f.setUp()
            calls = []
            for index, node in enumerate(
                [f.panel, f.root, f.desktop, *f.nodes.values()]
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
                original = getattr(f.native, name)

                def tracked(*args, _original=original, _name=name, **kwargs):
                    calls.append((_name, args, kwargs))
                    return _original(*args, **kwargs)

                setattr(f.native, name, tracked)
            with patch(
                "native_pending.capture_acknowledgement",
                capture if enabled else lambda *args: None,
            ):
                self.assertEqual(f.navigate()[0], f.target)
            runs.append((calls, f.events, f.native.save.call_args_list, f.clock.now))
        self.assertEqual(runs[0], runs[1])

    def test_interrupted_endpoint_needs_new_positive_boundary_ack_before_binding(self):
        fixture = pending_fixtures.PendingEndpointTests(methodName="runTest")
        fixture.setUp()
        fixture.disappear_before_ack()
        f = fixture.f
        observe = f.native.navigation_selection
        positive = []
        interrupted = []
        proofs = []

        def observation(*args, **kwargs):
            if kwargs.get("pending") is not None:
                proofs.append(
                    copy.deepcopy(kwargs["pending"].get("prior_acknowledgement"))
                )
            result = observe(*args, **kwargs)
            if isinstance(result, native_pending.InterruptedNavigation):
                interrupted.append(result.frame)
            elif result[0] is not None:
                positive.append((result[0][0], result[1]))
            return result

        f.native.navigation_selection = observation
        with patch(
            "native_pending.capture_acknowledgement",
            wraps=native_pending.capture_acknowledgement,
        ) as captured:
            self.assertEqual(f.navigate()[0], f.target)
        self.assertEqual(len(interrupted), 1)
        self.assertGreater(len(proofs), 1)
        self.assertEqual(proofs[1]["identity"], aid(19))
        for call in captured.call_args_list:
            self.assertTrue(
                any(
                    identity == call.args[0] and frame is call.args[1]
                    for identity, frame in positive
                )
            )
            self.assertTrue(all(frame is not call.args[1] for frame in interrupted))

    def test_down_batch_binds_home_ack_without_exempting_boundary_or_final_target(self):
        f = navigation.NavigationTests(methodName="runTest")
        f.setUp()
        observe = f.native.navigation_selection
        calls = []

        def observation(*args, **kwargs):
            calls.append((args, copy.deepcopy(kwargs)))
            return observe(*args, **kwargs)

        f.native.navigation_selection = observation
        self.assertEqual(f.navigate()[0], f.target)
        pending = next(
            kwargs["pending"] for _, kwargs in calls if kwargs.get("pending")
        )
        proof = pending["prior_acknowledgement"]
        self.assertEqual(
            (
                proof["identity"],
                proof["index"],
                proof["expected"],
                proof["endpoint_index"],
                proof["keys"],
            ),
            (aid(0), 0, aid(2), 2, ["Down", "Down"]),
        )
        self.assertNotIn("pending", calls[0][1])
        self.assertTrue(
            all(
                kwargs.get("pending") is None
                for args, kwargs in calls
                if args[0] == f.target or kwargs.get("reconcile")
            )
        )
