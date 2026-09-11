import copy
import unittest
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from performance_compare import InvalidMeasurement
from test_windows_process_actions_verify import example_record
from windows_process_uac_verify import (validate_run, validate_handle_selftest, validate_resource_review,
    RESOURCE_REVIEW_CHECKS, REQUIRED_RUNS, ROOT, verify_all)


def observed_run(name="consent-force"):
    ui = example_record()
    ui["dashboard"]["creation_ticks"] = 134335279700000000
    expected = dict(ui["cases"][4])
    expected.update(name=name, ordinary_force_access_error=5, settled_utc="2026-09-10T21:02:00Z")
    ui["cases"] = [expected]
    if name == "consent-cancel":
        expected.update(exited=False, status="Windows authorization was cancelled. No helper action was started.")
    if name == "consent-delayed":
        expected.update(mode="delayed", signal="terminate", exited=False,
                        status="The application did not close. It may need a response or have declined the request.")
    if name == "consent-denied":
        expected.update(exited=False, status="Windows denied the requested process action.")
    if name in ("helper-crash", "helper-timeout"):
        expected.update(mode="refusing-delayed", signal="terminate", exited=False,
                        status="The process-action helper did not confirm an outcome. Check the process list before trying again.",
                        settled_utc="2026-09-10T21:02:00Z")
    observer = dict(status="COLLECTED", ui_task_exit=0, observer_debug_privilege_removed=True,
                    observer=dict(pid=1, creation_ticks=123, elevated=True),
                    target=dict(pid=expected["pid"], creation_ticks=expected["creation_ticks"], elevated=True,
                                administrator_termination_dacl=True, administrator_termination_access_error=0),
                    target_cleaned=True, target_exited_before_cleanup=expected["exited"], events=[])
    events = observer["events"]
    def lifecycle(pid, name, code, **extra):
        events.append(dict(kind="start", pid=pid, name=name, event_ticks=134335279800000000, session_id=1, **extra))
        events.append(dict(kind="stop", pid=pid, name=name[:14], exit_code=code,
                           event_ticks=134335279900000000, session_id=1))
    lifecycle(ui["dashboard"]["pid"], "system-pulse.exe", 1,
              creation_ticks=ui["dashboard"]["creation_ticks"], elevated=False)
    for probe in ui["helper_entry_checks"]:
        lifecycle(probe["pid"], "system-pulse.exe", probe["exit_code"])
    lifecycle(300, "consent.exe", 0)
    if name == "consent-delayed":
        events[-1]["event_ticks"] = events[-2]["event_ticks"] + 100_000_000
        for index, row in enumerate(expected["pending_observations"]):
            ticks = events[-2]["event_ticks"] + (index + 1) * 20_000_000
            row["observed_utc"] = datetime.fromtimestamp(
                (ticks - 116444736000000000) / 10_000_000, timezone.utc).isoformat()
    if name != "consent-cancel":
        code = {"consent-delayed": 28, "consent-denied": 23, "helper-crash": 0xC0000001,
                "helper-timeout": 1}.get(name, 20)
        lifecycle(400, "system-pulse.exe", code,
                  creation_ticks=134335279800000000, elevated=True, elevation_type=2,
                  image=ui["binary_path"], argv=[ui["binary_path"], "--system-pulse-windows-process-action",
                  str(expected["pid"]), str(expected["creation_ticks"]), expected["signal"],
                  str(ui["dashboard"]["pid"]), str(ui["dashboard"]["creation_ticks"])])
    if name == "consent-denied":
        observer["fault_applied"] = dict(kind="deny-termination", pid=expected["pid"],
                                         creation_ticks=expected["creation_ticks"], elevated_access_error=5)
    if name in ("helper-crash", "helper-timeout"):
        observer.update(helper_cleaned=True, helper_exited_before_cleanup=name == "helper-crash",
                        fault_applied=dict(kind=name, pid=400, creation_ticks=134335279800000000,
                                           image=ui["binary_path"], argv=events[-2]["argv"],
                                             suspended_threads=3, utc="2026-09-10T21:00:01Z"))
    ui["resources_acknowledged"] = True
    observer["resources"] = dict(
        passed=True, case=name, dashboard_alive=True, snapshot_released=True,
        dashboard_pid=ui["dashboard"]["pid"], dashboard_creation_ticks=ui["dashboard"]["creation_ticks"],
        captured_utc="2026-09-10T21:02:01Z", scanned_handles=700, unclassified_handles=0,
        process_handles=[dict(pid=expected["pid"], count=1, termination_count=0)]
        + ([] if name == "consent-cancel" else [dict(pid=400, count=0, termination_count=0)]))
    return ui, observer


class NativeUacReceiptTests(unittest.TestCase):
    def test_full_gate_requires_every_case_and_rejects_mislabeled_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("windows_process_uac_verify.verify_receipt") as verify:
                with self.assertRaisesRegex(InvalidMeasurement, "remain pending"):
                    verify_all(root, root / "build.log", root, root, root / "review.json")
                verify.assert_not_called()
                for name in REQUIRED_RUNS:
                    (root / name).mkdir()
                    (root / name / "receipt.json").write_text("{}")
                verify.return_value = "consent-force"
                with self.assertRaisesRegex(InvalidMeasurement, "different case"):
                    verify_all(root, root / "build.log", root, root, root / "review.json")
                verify.assert_called_once()

    def test_delayed_consent_requires_progress_inside_the_actual_prompt(self):
        for change in (
            lambda u, o: o["events"][9].update(event_ticks=o["events"][8]["event_ticks"] + 1),
            lambda u, o: u["cases"][0]["pending_observations"][0].update(observed_utc="2020-01-01T00:00:00Z"),
        ):
            ui, observer = observed_run("consent-delayed")
            change(ui, observer)
            with self.assertRaises(InvalidMeasurement):
                validate_run(ui, observer, "consent-delayed")

    def test_handle_positive_controls_reject_missed_leaks_and_incomplete_cleanup(self):
        proof = json.loads((ROOT / "docs/execution/windows-uac-process-actions/native-handle-selftest.json").read_text())
        hashes = proof["sources_sha256"]
        validate_handle_selftest(proof, hashes)
        for change in (
            lambda p: p.update(sources_sha256={}),
            lambda p: p["result"].update(target_cleaned=False),
            lambda p: p["result"]["samples"].pop(),
            lambda p: p["result"]["samples"][0]["open"]["process_handles"][0].update(count=1),
            lambda p: p["result"]["samples"][2]["after"]["process_handles"][0].update(termination_count=2),
            lambda p: p["result"]["foreign_snapshot"].update(snapshot_released=False),
        ):
            invalid = copy.deepcopy(proof)
            change(invalid)
            with self.assertRaises(InvalidMeasurement):
                validate_handle_selftest(invalid, hashes)

    def test_resource_review_requires_current_sources_and_every_boundary(self):
        review = dict(status="PASS", findings=[], sources_sha256={"file": "hash"},
                      checks={name: "Inspected the boundary and its cleanup paths." for name in RESOURCE_REVIEW_CHECKS})
        validate_resource_review(review, {"file": "hash"})
        for change in (lambda r: r.update(findings=["leak"]),
                       lambda r: r.update(sources_sha256={}),
                       lambda r: r["checks"].pop("token_handles")):
            invalid = copy.deepcopy(review)
            change(invalid)
            with self.assertRaises(InvalidMeasurement):
                validate_resource_review(invalid, {"file": "hash"})

    def test_resource_observation_rejects_leaks_missing_handles_and_dead_dashboard(self):
        changes = [
            lambda u, o: u.update(resources_acknowledged=False),
            lambda u, o: o["resources"].update(dashboard_alive=False),
            lambda u, o: o["resources"].update(snapshot_released=False),
            lambda u, o: o["resources"].update(dashboard_creation_ticks=1),
            lambda u, o: o["resources"].update(unclassified_handles=1),
            lambda u, o: o["resources"].update(scanned_handles=0),
            lambda u, o: o["resources"]["process_handles"].pop(),
            lambda u, o: o["resources"]["process_handles"][1].update(count=1),
            lambda u, o: o["resources"]["process_handles"][0].update(termination_count=1),
            lambda u, o: o["resources"].update(captured_utc="2026-09-10T21:01:59Z"),
        ]
        for index, mutate in enumerate(changes):
            ui, observer = observed_run()
            mutate(ui, observer)
            with self.subTest(index=index), self.assertRaises(InvalidMeasurement):
                validate_run(ui, observer, "consent-force")

    def test_ordinary_actions_have_no_consent_or_elevated_helper(self):
        ui = example_record()
        observer = observed_run()[1]
        observer["events"] = observer["events"][:-4]
        observer["events"][0]["creation_ticks"] = ui["dashboard"]["creation_ticks"]
        validate_run(ui, observer, "ordinary")
        observer["events"].extend(observed_run()[1]["events"][-4:])
        with self.assertRaises(InvalidMeasurement):
            validate_run(ui, observer, "ordinary")

    def test_accepts_complete_force_cancel_and_delayed_observations(self):
        for name in ("consent-force", "consent-cancel", "consent-delayed", "consent-denied", "helper-crash", "helper-timeout"):
            with self.subTest(name=name):
                validate_run(*observed_run(name), name)

    def test_stop_name_truncation_does_not_lose_lifecycle(self):
        ui, observer = observed_run()
        self.assertIn("system-pulse.e", [row["name"] for row in observer["events"]])
        validate_run(ui, observer, "consent-force")

    def test_zero_stop_session_uses_the_observed_start_session(self):
        ui, observer = observed_run()
        for row in observer["events"]:
            if row["kind"] == "stop":
                row["session_id"] = 0
        validate_run(ui, observer, "consent-force")
        observer["events"][-2]["session_id"] = 2
        with self.assertRaises(InvalidMeasurement):
            validate_run(ui, observer, "consent-force")

    def test_rejects_missing_duplicated_or_foreign_lifecycle(self):
        mutations = [
            lambda o: o["events"].pop(),
            lambda o: o["events"].append(copy.deepcopy(o["events"][-2])),
            lambda o: o["events"][-1].update(pid=401),
            lambda o: o["events"][-1].update(session_id=2),
            lambda o: o["events"][-1].update(event_ticks=1),
            lambda o: o["events"][-1].update(exit_code=23),
            lambda o: o["events"].__delitem__(slice(8, 10)),
        ]
        for index, mutate in enumerate(mutations):
            ui, observer = observed_run()
            mutate(observer)
            with self.subTest(index=index), self.assertRaises(InvalidMeasurement):
                validate_run(ui, observer, "consent-force")

    def test_cancel_must_not_start_a_helper_or_change_target(self):
        ui, observer = observed_run("consent-cancel")
        helper_events = observed_run()[1]["events"][-2:]
        observer["events"].extend(helper_events)
        with self.assertRaises(InvalidMeasurement):
            validate_run(ui, observer, "consent-cancel")
        ui, observer = observed_run("consent-cancel")
        ui["cases"][0]["exited"] = True
        with self.assertRaises(InvalidMeasurement):
            validate_run(ui, observer, "consent-cancel")

    def test_live_helper_must_match_confirmed_identity_path_and_arguments(self):
        for field, value in [("elevated", False), ("elevation_type", 3),
                             ("image", "C:\\other.exe"), ("argv", ["cmd.exe", "/c", "exit"])]:
            ui, observer = observed_run("consent-delayed")
            observer["events"][-2][field] = value
            with self.subTest(field=field), self.assertRaises(InvalidMeasurement):
                validate_run(ui, observer, "consent-delayed")
        ui, observer = observed_run("consent-delayed")
        observer["events"][-2]["argv"][3] = str(ui["cases"][0]["creation_ticks"] // 10_000_000)
        with self.assertRaises(InvalidMeasurement):
            validate_run(ui, observer, "consent-delayed")

    def test_target_dashboard_and_cleanup_observations_cannot_be_omitted(self):
        changes = [
            lambda u, o: o.update(target_cleaned=False),
            lambda u, o: o.update(ui_still_running=True),
            lambda u, o: o["target"].update(creation_ticks=1),
            lambda u, o: u["cases"][0].update(ordinary_force_access_error=0),
            lambda u, o: u["cases"][0].update(dashboard_elevated_after=True),
            lambda u, o: u["cases"][0].update(confirmation="Confirm another PID"),
            lambda u, o: u["owned_target_cleanup"].clear(),
            lambda u, o: o["events"][0].update(elevated=True),
            lambda u, o: o["events"][-2].update(process_close_failed=True),
            lambda u, o: o.update(observer_debug_privilege_removed=False),
            lambda u, o: o["target"].pop("administrator_termination_dacl"),
            lambda u, o: o["target"].update(administrator_termination_access_error=5),
        ]
        for index, mutate in enumerate(changes):
            ui, observer = observed_run()
            mutate(ui, observer)
            with self.subTest(index=index), self.assertRaises(InvalidMeasurement):
                validate_run(ui, observer, "consent-force")

    def test_failure_injection_requires_real_denial_and_a_pinned_bounded_fault(self):
        for name, mutate in [
            ("consent-denied", lambda u, o: o["fault_applied"].update(elevated_access_error=0)),
            ("helper-crash", lambda u, o: o["fault_applied"].update(pid=999)),
            ("helper-crash", lambda u, o: o.update(helper_cleaned=False)),
            ("helper-timeout", lambda u, o: o.update(helper_exited_before_cleanup=True)),
            ("helper-timeout", lambda u, o: o["fault_applied"].update(suspended_threads=0)),
            ("helper-timeout", lambda u, o: u["cases"][0].update(settled_utc="2026-09-10T21:00:02Z")),
        ]:
            ui, observer = observed_run(name)
            mutate(ui, observer)
            with self.subTest(name=name), self.assertRaises(InvalidMeasurement):
                validate_run(ui, observer, name)


if __name__ == "__main__":
    unittest.main()
