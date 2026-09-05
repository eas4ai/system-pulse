"""Process exit and mandatory coverage fixtures never reach a live collector."""

import copy
import errno
import json
import unittest

import host_capture
from test_process_attribution import process_capture
from process_evidence import declare_policy


def controlled_capture(with_exit=False):
    observer, snapshots = process_capture()
    child = copy.deepcopy(observer.samples[0]["processes"]["42"])
    child["stat"].update(start=-4, end=-3)
    observer.process_policy = declare_policy(child, -2)
    if with_exit:
        for snapshot in snapshots:
            ordinary = json.loads(
                json.dumps(snapshot["processes"][0])
                .replace("process:42:", "process:99:")
                .replace("/proc/42/", "/proc/99/")
            )
            ordinary["identity"]["pid"] = 99
            snapshot["processes"].append(ordinary)
        ordinary = json.loads(
            json.dumps(observer.samples[0]["processes"]["42"]).replace(
                "/proc/42/", "/proc/99/"
            )
        )
        ordinary["stat"]["value"]["pid"] = 99
        observer.samples[0]["processes"]["99"] = ordinary
        terminal = copy.deepcopy(ordinary)
        for raw in terminal.values():
            raw.update(start=30, end=31, errno=errno.ENOENT, value=None)
        observer.supplemental = [
            dict(
                census=observer.samples[-1]["sources"]["/proc"],
                processes=[dict(pid=99, readings=terminal)],
            )
        ]
    return observer, snapshots, child


def write_host_fixture(directory, with_exit=False):
    """Retain truthful recomputable verifier evidence for aggregate-only tests."""
    directory.mkdir(parents=True, exist_ok=True)
    observer, snapshots, child = controlled_capture(with_exit)
    result = host_capture.verify_capture(observer, snapshots, child)
    artifacts = {
        "process-policy.json": observer.process_policy,
        "capabilities.json": dict(capabilities=observer.capabilities, scope_limits=[]),
        "final-inventory.json": dict(capabilities=observer.capabilities),
        "external-observations.json": dict(
            anchors=observer.anchors,
            samples=observer.samples,
            supplemental=getattr(observer, "supplemental", []),
            disks=[],
        ),
        "child.json": dict(
            before=child, identity=observer.process_policy["controlled_identity"]
        ),
        "collector-lifecycle.json": dict(gate_opened_ns=-1),
    }
    for key, filename in (
        ("brackets", "counter-brackets.json"),
        ("missing_brackets", "missing-brackets.json"),
        ("unverified_exit_gaps", "unverified-exit-gaps.json"),
        ("process_coverage", "process-coverage.json"),
        ("stable_totals", "stable-totals.json"),
    ):
        artifacts[filename] = result.pop(key)
    result.update(
        snapshots=len(snapshots),
        child_identity=observer.process_policy["controlled_identity"],
        child_exit_verified=True,
    )
    # A final inventory is retained, so the replay checks it as well.
    result["inventory_scope"] = "initial and final independent inventories"
    artifacts["result.json"] = result
    for filename, value in artifacts.items():
        (directory / filename).write_text(json.dumps(value))
    (directory / "snapshots.jsonl").write_text(
        "".join(json.dumps(s) + "\n" for s in snapshots)
    )
    (directory / "after-exit.jsonl").write_text(json.dumps(dict(processes=[])))
    return result


def exited_capture():
    observer, snapshots = process_capture()
    after = observer.samples[-1]
    terminal = after["processes"].pop("42")
    for source in ("stat", "io"):
        terminal[source].update(errno=errno.ENOENT, value=None, error="exited")
    observer.supplemental = [
        dict(
            census=after["sources"]["/proc"],
            processes=[dict(pid=42, readings=terminal)],
        )
    ]
    return observer, snapshots


class ExitPolicyTests(unittest.TestCase):
    def test_exit_gaps_remain_unverified_with_before_and_terminal_evidence(self):
        observer, snapshots = exited_capture()
        result = host_capture.verify_capture(observer, snapshots, None)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["missing_brackets"], [])
        self.assertEqual(result["counts"]["counter_brackets"], 48)
        self.assertEqual(result["counts"]["unverified_exit_gaps"], 24)
        for gap in result["unverified_exit_gaps"]:
            self.assertEqual(gap["classification"], "unverified_exit_gap")
            self.assertEqual(gap["before"]["identity"], gap["identity"])
            self.assertEqual(gap["terminal"]["errno"], errno.ENOENT)
            self.assertIn("raw_query", gap)
            self.assertNotIn("after", gap)

    def test_missing_before_survival_permissions_and_conflicting_identity_fail(self):
        for mutation in ("before", "survival", "permission", "reuse", "wrong_pid"):
            with self.subTest(mutation=mutation):
                observer, snapshots = exited_capture()
                first = observer.samples[0]["processes"]["42"]
                if mutation == "before":
                    observer.samples[0]["processes"].clear()
                elif mutation == "survival":
                    observer.supplemental.clear()
                else:
                    extra = copy.deepcopy(first)
                    for raw in extra.values():
                        raw.update(start=21, end=22)
                    if mutation == "permission":
                        extra["stat"].update(errno=errno.EACCES, value=None)
                    else:
                        extra["stat"]["value"][
                            "start_ticks" if mutation == "reuse" else "pid"
                        ] = 999
                        extra["stat"]["value"].update(utime=30, stime=30)
                        extra["io"]["value"].update(read_bytes=30, write_bytes=30)
                    # Full reads precede supplemental reads in storage, not time.
                    observer.samples.append(
                        dict(
                            sources=observer.samples[0]["sources"],
                            processes={"42": extra},
                        )
                    )
                result = host_capture.verify_capture(observer, snapshots, None)
                self.assertEqual(result["status"], "FAIL")

    def test_known_lower_bound_violation_despite_exit_fails(self):
        observer, snapshots = exited_capture()
        observer.samples[0]["processes"]["42"]["stat"]["value"]["utime"] = 11
        with self.assertRaisesRegex(AssertionError, "outside|lower bound"):
            host_capture.verify_capture(observer, snapshots, None)

    def test_known_upper_bound_violation_despite_later_exit_fails(self):
        observer, snapshots = process_capture()
        terminal = copy.deepcopy(observer.samples[-1]["processes"]["42"])
        for raw in terminal.values():
            raw.update(start=40, end=41, errno=errno.ENOENT, value=None)
        observer.supplemental = [
            dict(
                census=observer.samples[-1]["sources"]["/proc"],
                processes=[dict(pid=42, readings=terminal)],
            )
        ]
        observer.samples[-1]["processes"]["42"]["stat"]["value"]["utime"] = 19
        with self.assertRaisesRegex(AssertionError, "outside bracket"):
            host_capture.verify_capture(observer, snapshots, None)

    def test_terminal_before_successful_stat_is_not_exit_proof_despite_storage_order(
        self,
    ):
        observer, snapshots = exited_capture()
        alive = copy.deepcopy(observer.samples[0]["processes"]["42"])
        alive["stat"].update(start=40, end=41)
        alive["io"].update(start=42, end=43, errno=errno.ENOENT, value=None)
        observer.samples.append(
            dict(sources=observer.samples[0]["sources"], processes={"42": alive})
        )
        # CPU counters remain bounded; IO lacks an after read but the process survived.
        alive["stat"]["value"].update(utime=30, stime=30)
        result = host_capture.verify_capture(observer, snapshots, None)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["unverified_exit_gaps"])

    def test_io_permission_error_with_stat_before_lower_operand_cannot_be_hidden(self):
        observer, snapshots = exited_capture()
        # A stat read can precede an IO operand, while its IO attempt follows it.
        denied = copy.deepcopy(observer.samples[0]["processes"]["42"])
        denied["stat"].update(start=-2, end=-1)
        denied["io"].update(start=5, end=6, errno=errno.EPERM, value=None)
        observer.samples.append(
            dict(sources=observer.samples[0]["sources"], processes={"42": denied})
        )
        result = host_capture.verify_capture(observer, snapshots, None)
        self.assertEqual(result["status"], "FAIL")

    def test_terminal_before_collector_query_cannot_explain_later_missing_bracket(self):
        observer, snapshots = exited_capture()
        early = copy.deepcopy(observer.supplemental[0])
        for raw in early["processes"][0]["readings"].values():
            raw.update(start=5, end=6)
        observer.supplemental.append(early)
        self.assertEqual(
            host_capture.verify_capture(observer, snapshots, None)["status"], "FAIL"
        )

    def test_conflicting_retained_terminal_identity_cannot_explain_gap(self):
        observer, snapshots = exited_capture()
        observer.supplemental[0]["processes"][0]["prior_identity"] = dict(
            pid=42, start_time_ticks=999
        )
        self.assertEqual(
            host_capture.verify_capture(observer, snapshots, None)["status"], "FAIL"
        )

    def test_controlled_child_unavailable_or_omitted_comparison_fails(self):
        for field in ("cpu_percent", "read_bytes_per_second", "write_bytes_per_second"):
            for mutation in ("unavailable", "omit"):
                with self.subTest(field=field, mutation=mutation):
                    observer, snapshots, child = controlled_capture()
                    reading = snapshots[-1]["processes"][0][field]
                    if mutation == "unavailable":
                        reading.update(
                            availability="Failed",
                            value=None,
                            reason="denied",
                            observations=[],
                        )
                    else:
                        del snapshots[-1]["processes"][0][field]
                    with self.assertRaises((AssertionError, KeyError)):
                        host_capture.verify_capture(observer, snapshots, child)

    def test_controlled_initial_warmup_requires_real_operand_and_later_full_coverage(
        self,
    ):
        observer, snapshots, child = controlled_capture()
        for field in ("cpu_percent", "read_bytes_per_second", "write_bytes_per_second"):
            reading = snapshots[0]["processes"][0][field]
            reading.update(
                availability="WarmingUp",
                value=None,
                reason="Waiting for a second counter observation",
            )
            reading["observations"] = reading["observations"][:1]
        result = host_capture.verify_capture(observer, snapshots, child)
        self.assertTrue(result["process_coverage"]["controlled_complete"])
        self.assertEqual(len(result["process_coverage"]["controlled"]), 9)
        self.assertEqual(
            sum(
                c["verified_brackets"] for c in result["process_coverage"]["controlled"]
            ),
            20,
        )
        snapshots[0]["processes"][0]["cpu_percent"]["observations"] = []
        with self.assertRaisesRegex(AssertionError, "controlled operand"):
            host_capture.verify_capture(observer, snapshots, child)

    def test_controlled_exit_cannot_exempt_missing_brackets(self):
        observer, snapshots, child = controlled_capture()
        terminal_observer, _ = exited_capture()
        observer.supplemental = terminal_observer.supplemental
        observer.samples[-1]["processes"].clear()
        result = host_capture.verify_capture(observer, snapshots, child)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["process_coverage"]["controlled_complete"])
        self.assertFalse(result["unverified_exit_gaps"])

    def test_controlled_each_required_counter_is_mandatory_at_both_endpoints(self):
        for field, keys in (
            ("cpu_percent", ("utime_ticks", "stime_ticks")),
            ("read_bytes_per_second", ("bytes",)),
            ("write_bytes_per_second", ("bytes",)),
        ):
            for key in keys:
                for endpoint in (0, 1):
                    with self.subTest(field=field, key=key, endpoint=endpoint):
                        observer, snapshots, child = controlled_capture()
                        del snapshots[-1]["processes"][0][field]["observations"][
                            endpoint
                        ]["integers"][key]
                        with self.assertRaisesRegex(
                            AssertionError, "controlled counters missing"
                        ):
                            host_capture.verify_capture(observer, snapshots, child)


if __name__ == "__main__":
    unittest.main()
