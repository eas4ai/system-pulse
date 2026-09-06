"""Pending arrow loss is unverified; physical recovery still needs exact ACK."""

import copy
import errno
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import native_pending

import test_native_navigation as fixture

aid = fixture.aid


class PendingEndpointTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.NavigationTests(methodName="runTest")
        self.f.setUp()
        self.f.target = aid(12)
        self.endpoint = aid(17)

    def disappear_before_ack(self):
        f = self.f
        key = f.native.key

        def issue(value, **kwargs):
            key(value, **kwargs)
            if f.pending[1] == self.endpoint:
                f.ids.remove(self.endpoint)
                del f.nodes[self.endpoint]
                f.selection = None
                f.pending = None
                f.sequence += 1

        f.native.key = issue

    def test_two_up_pending_exit_recovers_without_false_ack(self):
        self.disappear_before_ack()
        f = self.f
        self.assertEqual(f.navigate()[0], f.target)
        self.assertEqual(
            [e[1] for e in f.events if e[0] == "key"][:4], ["End", "Up", "Up", "End"]
        )
        self.assertFalse(
            any(
                e[0] == "ack" and e[1]["condition"] == "selected " + self.endpoint
                for e in f.events
            )
        )
        self.assertEqual(
            sum(e[0] == "navigation-batch-interrupted" for e in f.events), 1
        )

    def test_post_ack_absence_is_not_selected_ack(self):
        f = self.f
        f.ids.remove(self.endpoint)
        del f.nodes[self.endpoint]
        selected, _, _ = f.native.navigation_selection(
            self.endpoint,
            f.target,
            8,
            reconcile=True,
            path=[f.panel, f.root],
            endpoint_index=17,
        )
        self.assertIsNone(selected)
        self.assertFalse(any(e[0] == "ack" for e in f.events))

    def test_flag_only_pending_shortcut_must_not_publish_false_ack(self):
        self.disappear_before_ack()
        f = self.f
        observe = f.native.navigation_selection

        def unsafe_flag(*args, **kwargs):
            if args[0] == self.endpoint:
                kwargs["reconcile"] = True
            return observe(*args, **kwargs)

        f.native.navigation_selection = unsafe_flag
        try:
            f.navigate()
        except (TypeError, AssertionError, TimeoutError):
            pass
        self.assertFalse(
            any(
                e[0] == "ack" and e[1]["condition"] == "selected " + self.endpoint
                for e in f.events
            )
        )

    def assert_no_interruption(self):
        self.assertFalse(
            any(e[0] == "navigation-batch-interrupted" for e in self.f.events)
        )
        self.assertFalse(
            any(e[0] == "navigation-boundary-recovery" for e in self.f.events)
        )

    def run_bad_stat(self, stage, mutate):
        f = self.f
        self.disappear_before_ack()
        stat = f.native.navigation_stat

        def observation(expected):
            result = stat(expected)
            if expected == self.endpoint and (
                (stage == "terminal") == (expected not in f.ids)
            ):
                mutate(result)
            return result

        f.native.navigation_stat = observation
        with self.assertRaises((AssertionError, TimeoutError)):
            f.navigate()
        self.assert_no_interruption()

    def test_invalid_independent_evidence_fails_before_recovery(self):
        mutations = {
            "permission": lambda o: o.update(errno=errno.EACCES),
            "other_error": lambda o: o.update(errno=errno.EIO),
            "wrong_source": lambda o: o.update(source="/other/17/stat"),
            "reversed_window": lambda o: o.update(start=o["end"] + 1),
            "future_window": lambda o: o.update(end=o["end"] + 1),
            "missing_window": lambda o: o.pop("start"),
            "wrong_window_type": lambda o: o.update(end=True),
            "missing_namespace": lambda o: o.pop("namespace"),
            "foreign_namespace": lambda o: o["namespace"].update(
                application_pid_namespace="pid:[2]"
            ),
        }
        for stage in ("baseline", "terminal"):
            for name, mutate in mutations.items():
                with self.subTest(stage=stage, invalid=name):
                    self.setUp()
                    self.run_bad_stat(stage, mutate)

    def test_malformed_or_reused_stat_cannot_be_reinterpreted_as_exit(self):
        for stage in ("baseline", "terminal"):
            for invalid in ("raw", "identity", "reuse", "wrong_pid"):
                with self.subTest(stage=stage, invalid=invalid):
                    self.setUp()
                    f = self.f
                    live = f.stat(self.endpoint)

                    def mutate(o):
                        o.update(errno=None, raw=live["raw"], identity=self.endpoint)
                        if invalid == "raw":
                            o["raw"] = "malformed stat"
                        elif invalid == "identity":
                            o["identity"] = None
                        else:
                            other = aid(17, 101) if invalid == "reuse" else aid(18)
                            changed = f.stat(other)
                            if invalid == "reuse":
                                changed["raw"] = live["raw"].replace(" 100 ", " 101 ")
                            o.update(raw=changed["raw"], identity=other)

                    self.run_bad_stat(stage, mutate)

    def test_live_omitted_endpoint_is_not_exit(self):
        live = self.f.stat(self.endpoint)
        self.run_bad_stat(
            "terminal",
            lambda o: o.update(errno=None, raw=live["raw"], identity=self.endpoint),
        )

    def test_pending_requires_a_matching_independent_baseline_and_issue_contract(self):
        for invalid in (
            "missing",
            "gone",
            "wrong_identity",
            "late_baseline",
            "dispatch_order",
            "wrong_index",
            "wrong_publication",
            "boundary_key",
            "unissued_key",
            "wrong_total_deadline",
        ):
            with self.subTest(invalid=invalid):
                self.setUp()
                self.disappear_before_ack()
                f = self.f
                selection = f.native.navigation_selection

                def observe(*args, **kwargs):
                    if args[0] == self.endpoint:
                        pending = copy.deepcopy(kwargs["pending"])
                        if invalid == "missing":
                            pending["baseline"] = None
                        elif invalid == "gone":
                            pending["baseline"].update(
                                errno=errno.ENOENT, raw=None, identity=None
                            )
                        elif invalid == "wrong_identity":
                            pending["baseline"]["identity"] = aid(18)
                        elif invalid == "late_baseline":
                            pending["baseline"]["end"] = pending["dispatch_started"] + 1
                        elif invalid == "dispatch_order":
                            pending["dispatch_started"] = (
                                pending["dispatch_completed"] + 1
                            )
                        elif invalid == "wrong_index":
                            pending["endpoint_index"] += 1
                        elif invalid == "wrong_publication":
                            pending["publication"]["application_pid"] += 1
                        elif invalid == "boundary_key":
                            pending["keys"] = pending["actual_keys"] = ["End"]
                        elif invalid == "unissued_key":
                            pending["actual_keys"] = ["Up"]
                        else:
                            pending["deadline"] = pending["batch_deadline"] - 1
                        kwargs["pending"] = pending
                    return selection(*args, **kwargs)

                f.native.navigation_selection = observe
                with self.assertRaises((AssertionError, TimeoutError)):
                    f.navigate()
                self.assert_no_interruption()

    def test_namespace_change_after_dispatch_fails(self):
        self.run_bad_stat(
            "terminal",
            lambda o: o["namespace"].update(
                pid_namespace="pid:[2]", application_pid_namespace="pid:[2]"
            ),
        )

    def test_native_ineligible_evidence_cannot_authorize_terminal_observation(self):
        for invalid in (
            "target_lost",
            "competitor",
            "multiple_selected",
            "stale",
            "incomplete",
            "detached",
            "duplicate_panel",
            "duplicate_snapshot",
            "duplicate_native_row",
            "reused_snapshot_pid",
        ):
            with self.subTest(invalid=invalid):
                self.setUp()
                f = self.f
                self.disappear_before_ack()
                key = f.native.key
                stat = Mock(wraps=f.native.navigation_stat)
                f.native.navigation_stat = stat

                def issue(value, **kwargs):
                    key(value, **kwargs)
                    if self.endpoint in f.ids:
                        return
                    if invalid == "target_lost":
                        f.ids.remove(f.target)
                    elif invalid == "competitor":
                        f.selection = [aid(18)]
                    elif invalid == "multiple_selected":
                        f.selection = [aid(18), aid(19)]
                    elif invalid == "stale":
                        f.stale = True
                    elif invalid == "incomplete":
                        f.panel.get_child_at_index = lambda index: None
                    elif invalid == "detached":
                        f.root.children = lambda: []
                    elif invalid == "duplicate_panel":
                        extra = fixture.Node(f.clock, name="processes")
                        f.root.children = lambda: [f.panel, extra]
                    elif invalid == "duplicate_snapshot":
                        f.ids.append(aid(18))
                    elif invalid == "duplicate_native_row":
                        f.nodes["duplicate"] = f.row(aid(18))
                    else:
                        f.ids.insert(17, aid(17, 101))

                f.native.key = issue
                with self.assertRaises((AssertionError, TimeoutError)):
                    f.navigate()
                self.assert_no_interruption()
                self.assertEqual(stat.call_count, 1)

    def test_observed_pending_competitor_cannot_be_forgotten_on_fresh_retry(self):
        self.disappear_before_ack()
        f = self.f
        selected = f.native.selected
        seen = []
        clear_on_frame = []

        def transient_competitor(*args, **kwargs):
            first = self.endpoint not in f.ids and not seen
            if first:
                f.selection = [aid(18)]
                seen.append(True)
            result = selected(*args, **kwargs)
            if first:
                clear_on_frame.append(True)
            return result

        def after_selected_validation():
            if clear_on_frame:
                clear_on_frame.clear()
                f.selection = None

        f.before_frame = after_selected_validation
        f.native.selected = transient_competitor
        with self.assertRaisesRegex(AssertionError, "selection transferred"):
            f.navigate()
        self.assert_no_interruption()

    def test_terminal_esrch_authorizes_only_unverified_recovery(self):
        self.disappear_before_ack()
        f = self.f
        stat = f.native.navigation_stat

        def observation(expected):
            result = stat(expected)
            if result["errno"] == errno.ENOENT:
                result["errno"] = errno.ESRCH
            return result

        f.native.navigation_stat = observation
        self.assertEqual(f.navigate()[0], f.target)
        interrupted = next(
            e[1] for e in f.events if e[0] == "navigation-batch-interrupted"
        )
        self.assertEqual(interrupted["terminal"]["errno"], errno.ESRCH)

    def test_terminal_publication_or_membership_change_requires_new_eligibility(self):
        for change in ("publication", "detach", "duplicate", "selection", "target"):
            with self.subTest(change=change):
                self.setUp()
                f = self.f
                self.disappear_before_ack()
                stat = f.native.navigation_stat
                terminal_calls = []

                def observation(expected):
                    result = stat(expected)
                    if expected == self.endpoint and expected not in f.ids:
                        terminal_calls.append(result)
                        if len(terminal_calls) == 1:
                            if change == "publication":
                                f.sequence += 1
                            elif change == "detach":
                                f.root.children = lambda: []
                            elif change == "duplicate":
                                extra = fixture.Node(f.clock, name="processes")
                                f.root.children = lambda: [f.panel, extra]
                            elif change == "selection":
                                f.selection = [aid(18)]
                            else:
                                f.ids.remove(f.target)
                                f.sequence += 1
                    return result

                f.native.navigation_stat = observation
                if change == "publication":
                    self.assertEqual(f.navigate()[0], f.target)
                    # A new complete native bracket proves the new publication;
                    # it need not reread an already terminal independent stat.
                    self.assertEqual(len(terminal_calls), 1)
                else:
                    with self.assertRaises((AssertionError, TimeoutError)):
                        f.navigate()
                    self.assert_no_interruption()

    def ticking_collector_with_discovery_cost(self, seconds):
        f = self.f
        original_text = f.frame_text
        tick = [int(f.clock.now)]

        def collector_tick():
            current = int(f.clock.now)
            if current != tick[0]:
                tick[0] = current
                f.sequence += 1
                f.revision += 1

        def frame_text():
            frame = fixture.json.loads(original_text())
            frame["accepted_unix_ns"] = int(f.clock.now) * 1_000_000_000
            return fixture.json.dumps(frame)

        f.before_frame = collector_tick
        f.frame_text = frame_text
        discover = f.native.navigation_panel
        self.discoveries = []

        def slow_discovery(deadline):
            self.discoveries.append((f.clock.now, deadline))
            if self.endpoint not in f.ids:
                f.clock.now += seconds
            return discover(deadline)

        f.native.navigation_panel = slow_discovery

    def test_post_terminal_discovery_may_span_collector_publications(self):
        for cost in (0, 0.3, 1.1):
            with self.subTest(discovery_seconds=cost):
                self.setUp()
                self.disappear_before_ack()
                self.ticking_collector_with_discovery_cost(cost)
                f = self.f
                self.assertEqual(f.navigate()[0], f.target)
                terminal = [e for e in f.events if e[0] == "navigation-terminal-stat"]
                self.assertEqual(len(terminal), 1)
                interrupted = next(
                    e for e in f.events if e[0] == "navigation-batch-interrupted"
                )
                recovery = next(
                    e for e in f.events if e[0] == "navigation-boundary-recovery"
                )
                self.assertLess(interrupted[2], 8.5)
                self.assertEqual(recovery[1]["batch_deadline"], 8.5)
                self.assertEqual(recovery[1]["deadline"], 180)
                self.assertEqual(
                    interrupted[1]["terminal"], terminal[0][1]["observation"]
                )

    def test_post_terminal_bracket_recomputes_current_identity_and_native_guards(self):
        for invalid in (
            "target_lost",
            "expected_returned",
            "reused_pid",
            "competitor",
            "multiple_selected",
            "duplicate_snapshot",
            "duplicate_row",
            "foreign_row",
            "stale",
            "detached",
            "incomplete",
        ):
            with self.subTest(invalid=invalid):
                self.setUp()
                self.disappear_before_ack()
                f = self.f
                selected = f.native.selected
                changed = []

                def scan(*args, **kwargs):
                    terminal_seen = any(
                        e[0] == "navigation-terminal-stat" for e in f.events
                    )
                    if terminal_seen and not changed:
                        changed.append(True)
                        if invalid == "target_lost":
                            f.ids.remove(f.target)
                        elif invalid == "expected_returned":
                            f.ids.insert(17, self.endpoint)
                        elif invalid == "reused_pid":
                            f.ids.insert(17, aid(17, 101))
                        elif invalid == "competitor":
                            f.selection = [aid(18)]
                        elif invalid == "multiple_selected":
                            f.selection = [aid(18), aid(19)]
                        elif invalid == "duplicate_snapshot":
                            f.ids.append(aid(18))
                        elif invalid == "duplicate_row":
                            f.nodes["duplicate"] = f.row(aid(18))
                        elif invalid == "foreign_row":
                            f.nodes["foreign"] = f.row(aid(42))
                        elif invalid == "stale":
                            f.stale = True
                        elif invalid == "detached":
                            f.root.children = lambda: []
                        else:
                            f.panel.get_child_at_index = lambda index: None
                    return selected(*args, **kwargs)

                f.native.selected = scan
                with self.assertRaises((AssertionError, TimeoutError)):
                    f.navigate()
                self.assertEqual(changed, [True])
                self.assert_no_interruption()

    def test_changed_post_terminal_scan_publication_requires_another_complete_proof(
        self,
    ):
        self.disappear_before_ack()
        f = self.f
        selected = f.native.selected
        rejected = []

        def scan(*args, **kwargs):
            result = selected(*args, **kwargs)
            if (
                any(e[0] == "navigation-terminal-stat" for e in f.events)
                and not rejected
            ):
                rejected.append(True)
                f.sequence += 1
                f.revision += 1
            return result

        f.native.selected = scan
        self.assertEqual(f.navigate()[0], f.target)
        self.assertEqual(rejected, [True])
        self.assertEqual(sum(e[0] == "navigation-terminal-stat" for e in f.events), 2)
        interrupted = next(
            e[1] for e in f.events if e[0] == "navigation-batch-interrupted"
        )
        self.assertEqual(interrupted["native"]["publication"]["sequence"], 3)

    def test_post_terminal_evidence_uses_the_new_snapshot_membership(self):
        self.disappear_before_ack()
        f = self.f
        discover = f.native.navigation_panel
        changed = []

        def replace_publication(deadline):
            if (
                any(e[0] == "navigation-terminal-stat" for e in f.events)
                and not changed
            ):
                changed.append(True)
                f.ids.remove(aid(0))
                del f.nodes[aid(0)]
                f.sequence += 1
                f.revision += 1
            return discover(deadline)

        f.native.navigation_panel = replace_publication
        self.assertEqual(f.navigate()[0], f.target)
        interrupted = next(
            e[1] for e in f.events if e[0] == "navigation-batch-interrupted"
        )
        self.assertEqual(sum(e[0] == "navigation-terminal-stat" for e in f.events), 1)
        self.assertNotIn(aid(0), interrupted["native"]["identities"])
        self.assertNotIn(aid(0), interrupted["native"]["instantiated_identities"])
        self.assertEqual(interrupted["native"]["publication"]["sequence"], 3)

    def test_predispatch_exit_sends_no_old_batch_and_shares_deadline(self):
        f = self.f
        stat = f.native.navigation_stat
        calls = []

        def observation(expected):
            calls.append(expected)
            if len(calls) == 1:
                f.ids.remove(expected)
                del f.nodes[expected]
                f.sequence += 1
                f.clock.now += 2
            return stat(expected)

        f.native.navigation_stat = observation
        selection = Mock(wraps=f.native.navigation_selection)
        f.native.navigation_selection = selection
        self.assertEqual(f.navigate()[0], f.target)
        reconciled = next(
            call for call in selection.call_args_list if call.kwargs.get("reconcile")
        )
        self.assertEqual(reconciled.args[0], aid(19))
        self.assertEqual(reconciled.kwargs["endpoint_index"], 19)
        replan = next(e[1] for e in f.events if e[0] == "navigation-predispatch-replan")
        issue = next(e[1] for e in f.events if e[0] == "navigation-batch")
        self.assertEqual(replan["expected"], self.endpoint)
        self.assertEqual(issue["expected"], aid(16))
        self.assertEqual(replan["batch_deadline"], issue["batch_deadline"])
        self.assertEqual(replan["batch_deadline"], 8.5)
        self.assertEqual(
            [e[1] for e in f.events if e[0] == "key"][:3], ["End", "Up", "Up"]
        )
        self.assertFalse(any(e[0] == "navigation-batch-interrupted" for e in f.events))

    def test_predispatch_exit_never_resets_budget_even_with_unchanged_snapshot(self):
        f = self.f
        live = f.stat(self.endpoint)
        f.native.navigation_stat = lambda expected: {
            **live,
            "errno": errno.ESRCH,
            "raw": None,
            "identity": None,
            "start": f.clock.monotonic_ns(),
            "end": f.clock.monotonic_ns(),
        }
        with self.assertRaisesRegex(AssertionError, "deadline"):
            f.navigate()
        self.assertEqual([e[1] for e in f.events if e[0] == "key"], ["End"])
        self.assertEqual(f.clock.now, 8.5)

    def test_interruption_freezes_issue_and_recovery_uses_remaining_budget(self):
        self.disappear_before_ack()
        f = self.f
        stat = f.native.navigation_stat

        def slow_stat(expected):
            started = f.clock.monotonic_ns()
            f.clock.now += 0.2
            result = stat(expected)
            result["start"] = started
            return result

        f.native.navigation_stat = slow_stat
        frame_text = f.frame_text

        def publication_text():
            # A publication retains its acceptance time between collector ticks.
            frame = fixture.json.loads(frame_text())
            frame["accepted_unix_ns"] = int(f.clock.now) * 1_000_000_000
            return fixture.json.dumps(frame)

        f.frame_text = publication_text
        acknowledged = Mock()
        f.native.navigation_context = {}
        self.assertEqual(
            f.native._navigate(f.target, 180, on_acknowledged=acknowledged)[0], f.target
        )
        event = next(e[1] for e in f.events if e[0] == "navigation-batch-interrupted")
        recovery = next(
            e[1] for e in f.events if e[0] == "navigation-boundary-recovery"
        )
        issue = event["issue"]
        self.assertEqual(event["status"], "interrupted-unverified")
        self.assertEqual(issue["endpoint_index"], 17)
        self.assertEqual(issue["expected"], self.endpoint)
        self.assertEqual(issue["publication"]["sequence"], 1)
        self.assertEqual(issue["actual_keys"], ["Up", "Up"])
        self.assertEqual(issue["keys"], issue["actual_keys"])
        self.assertEqual(issue["batch_deadline"], recovery["batch_deadline"])
        self.assertEqual(issue["deadline"], recovery["deadline"])
        self.assertLessEqual(issue["baseline"]["end"], issue["dispatch_started"])
        self.assertLessEqual(issue["dispatch_completed"], event["terminal"]["start"])
        self.assertGreater(event["terminal"]["end"] - event["terminal"]["start"], 0)
        self.assertEqual(acknowledged.call_args.args[0]["target"], f.target)
        self.assertEqual(acknowledged.call_args.args[0]["index"], f.ids.index(f.target))

    def test_journal_expiry_prevents_recovery_or_arrow_dispatch(self):
        for event in (
            "navigation-baseline-stat",
            "navigation-batch",
            "navigation-batch-interrupted",
            "navigation-boundary-recovery",
        ):
            with self.subTest(event=event):
                self.setUp()
                self.disappear_before_ack()
                f = self.f

                def slow_journal(name, **fields):
                    f.journal(name, **fields)
                    if name == event:
                        f.clock.now = 8.5

                f.native.journal = slow_journal
                with self.assertRaises((AssertionError, TimeoutError)):
                    f.navigate()
                keys = [e[1] for e in f.events if e[0] == "key"]
                self.assertEqual(
                    keys,
                    ["End"]
                    if event in ("navigation-baseline-stat", "navigation-batch")
                    else ["End", "Up", "Up"],
                )

    def test_late_recovery_ack_journal_cannot_start_another_batch(self):
        self.disappear_before_ack()
        f = self.f
        f.native.navigation_context = {}
        acknowledged = Mock()
        delayed = []

        def journal(event, **fields):
            f.journal(event, **fields)
            if (
                event == "ack"
                and fields["condition"] == "selected " + aid(19)
                and any(e[0] == "navigation-boundary-recovery" for e in f.events)
                and not delayed
            ):
                delayed.append(f.clock.now)
                f.clock.now = 8.75

        f.native.journal = journal
        with self.assertRaisesRegex(AssertionError, "deadline"):
            f.native._navigate(f.target, 180, on_acknowledged=acknowledged)
        self.assertEqual(delayed, [1.25])
        self.assertEqual(
            [e[1] for e in f.events if e[0] == "key"], ["End", "Up", "Up", "End"]
        )
        acknowledged.assert_not_called()
        recovery = next(
            e[1] for e in f.events if e[0] == "navigation-boundary-recovery"
        )
        self.assertEqual(recovery["batch_deadline"], 8.5)

    def test_late_final_ack_journal_cannot_return_or_invoke_callback(self):
        for limit in ("batch", "total"):
            with self.subTest(limit=limit):
                self.setUp()
                self.disappear_before_ack()
                f = self.f
                f.native.navigation_context = {}
                acknowledged = Mock()
                selection = f.native.navigation_selection
                final_deadline = []
                delayed = []

                def observe(*args, **kwargs):
                    if kwargs.get("fresh_panel"):
                        final_deadline.append(args[2])
                    return selection(*args, **kwargs)

                def journal(event, **fields):
                    f.journal(event, **fields)
                    if (
                        event == "ack"
                        and fields["condition"] == "selected " + f.target
                        and final_deadline
                    ):
                        delayed.append(f.clock.now)
                        f.clock.now = (
                            final_deadline[0] if limit == "batch" else 180
                        ) + 0.25

                f.native.navigation_selection = observe
                f.native.journal = journal
                with self.assertRaisesRegex(AssertionError, "deadline"):
                    f.native._navigate(f.target, 180, on_acknowledged=acknowledged)
                self.assertEqual(delayed, [2.75])
                self.assertEqual(final_deadline, [10.75])
                self.assertEqual(f.clock.now, 11 if limit == "batch" else 180.25)
                acknowledged.assert_not_called()

    def test_late_absence_journal_cannot_return_an_absence_outcome(self):
        f = self.f
        f.ids.remove(self.endpoint)
        del f.nodes[self.endpoint]

        def journal(event, **fields):
            f.journal(event, **fields)
            if event == "navigation-absence":
                f.clock.now = 8.25

        f.native.journal = journal
        with self.assertRaisesRegex(AssertionError, "deadline"):
            f.native.navigation_selection(
                self.endpoint,
                f.target,
                8,
                reconcile=True,
                path=[f.panel, f.root],
                endpoint_index=17,
            )
        self.assertFalse(any(e[0] == "ack" for e in f.events))

    def test_recovery_ack_loss_is_not_recursively_interrupted(self):
        self.disappear_before_ack()
        f = self.f
        key = f.native.key

        def issue(value, **kwargs):
            key(value, **kwargs)
            if value == "End" and self.endpoint not in f.ids:
                endpoint = f.pending[1]
                f.ids.remove(endpoint)
                del f.nodes[endpoint]
                f.pending = None
                f.selection = None
                f.sequence += 1

        f.native.key = issue
        with self.assertRaises(TimeoutError):
            f.navigate()
        self.assertEqual(
            sum(e[0] == "navigation-batch-interrupted" for e in f.events), 1
        )
        self.assertEqual(
            sum(e[0] == "navigation-boundary-recovery" for e in f.events), 1
        )
        self.assertEqual(f.clock.now, 8.5)

    def test_recovery_uses_total_deadline_and_needs_actual_exact_ack(self):
        self.disappear_before_ack()
        f = self.f
        f.native.navigation_context = {}
        f.ack_delay = 0.75
        with self.assertRaises(TimeoutError):
            f.native._navigate(f.target, 1.5)
        recovery = next(
            e[1] for e in f.events if e[0] == "navigation-boundary-recovery"
        )
        self.assertEqual(recovery["batch_deadline"], 1.5)
        self.assertEqual(f.clock.now, 1.5)

    def test_controlled_target_pending_loss_remains_fatal_without_stat_exception(self):
        self.endpoint = self.f.target
        self.disappear_before_ack()
        f = self.f
        stat = Mock(wraps=f.native.navigation_stat)
        f.native.navigation_stat = stat
        with self.assertRaisesRegex(AssertionError, "target absent"):
            f.navigate()
        self.assertNotIn(f.target, [call.args[0] for call in stat.call_args_list])
        self.assert_no_interruption()

    def test_no_independent_stat_is_needed_for_initial_boundary_or_controlled_endpoint(
        self,
    ):
        f = self.f
        f.target = aid(18)
        f.native.navigation_stat = Mock(
            side_effect=AssertionError("ineligible stat read")
        )
        self.assertEqual(f.navigate()[0], f.target)
        f.native.navigation_stat.assert_not_called()

    def test_physical_key_journal_cannot_cross_deadline(self):
        f = self.f
        f.native.__dict__.pop("key")
        f.native.d = Mock()
        f.native.key.__globals__.update(
            X=SimpleNamespace(KeyPress="press", KeyRelease="release"),
            XK=SimpleNamespace(string_to_keysym=lambda k: k),
            xtest=SimpleNamespace(fake_input=Mock()),
        )

        def journal(name, **fields):
            f.clock.now = 8

        f.native.journal = journal
        with self.assertRaisesRegex(AssertionError, "deadline"):
            f.native.key("End", deadline=8)
        f.native.key.__globals__["xtest"].fake_input.assert_not_called()
        f.native.d.sync.assert_not_called()


class IndependentStatTests(unittest.TestCase):
    def test_direct_stat_preserves_literal_raw_and_query_cost_without_extra_process_io(
        self,
    ):
        f = fixture.NavigationTests(methodName="runTest")
        f.setUp()
        expected = aid(17)
        raw = f.stat(expected)["raw"]
        ticks = iter((100, 137))
        ns = {
            "device": 1,
            "inode": 2,
            "pid_namespace": "pid:[1]",
            "application_pid_namespace": "pid:[1]",
        }
        with (
            patch.object(native_pending, "namespace", return_value=ns),
            patch.object(native_pending.Path, "read_text", return_value=raw) as read,
            patch("host_capture.time.monotonic_ns", side_effect=lambda: next(ticks)),
        ):
            result = native_pending.read_stat(expected, 500)
        read.assert_called_once_with()
        self.assertEqual(result["raw"], raw)
        self.assertEqual(result["identity"], expected)
        self.assertEqual(result["source"], "/proc/17/stat")
        self.assertEqual(result["end"] - result["start"], 37)

    def test_stat_read_errors_and_malformed_raw_are_retained(self):
        for error in (errno.ENOENT, errno.ESRCH, errno.EACCES, errno.EIO, None):
            with (
                self.subTest(error=error),
                patch.object(native_pending, "namespace", return_value={}),
                patch.object(native_pending.Path, "read_text") as read,
            ):
                if error is None:
                    read.return_value = "invalid literal stat text\n"
                else:
                    read.side_effect = OSError(error, "fixture error")
                result = native_pending.read_stat(aid(17), 500)
                self.assertEqual(result["errno"], error)
                if error is None:
                    self.assertEqual(result["raw"], read.return_value)
                    self.assertIn("parse_error", result)
                else:
                    self.assertEqual(result["error"], "fixture error")
                self.assertIsNone(result["identity"])
