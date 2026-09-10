import copy
import unittest

from performance_compare import InvalidMeasurement
from test_windows_process_actions_verify import example_record
from windows_process_uac_verify import validate_run


def observed_run(name="consent-force"):
    ui = example_record()
    ui["dashboard"]["creation_ticks"] = 134335279700000000
    expected = dict(ui["cases"][4])
    expected.update(name=name, ordinary_force_access_error=5)
    ui["cases"] = [expected]
    if name == "consent-cancel":
        expected.update(exited=False, status="Windows authorization was cancelled. No helper action was started.")
    if name == "consent-delayed":
        expected.update(mode="delayed", signal="terminate", exited=False,
                        status="The application did not close. It may need a response or have declined the request.")
    observer = dict(status="COLLECTED", ui_task_exit=0, observer=dict(pid=1, creation_ticks=123, elevated=True),
                    target=dict(pid=expected["pid"], creation_ticks=expected["creation_ticks"], elevated=True),
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
    if name != "consent-cancel":
        lifecycle(400, "system-pulse.exe", 28 if name == "consent-delayed" else 20,
                  creation_ticks=134335279800000000, elevated=True, elevation_type=2,
                  image=ui["binary_path"], argv=[ui["binary_path"], "--system-pulse-windows-process-action",
                  str(expected["pid"]), str(expected["creation_ticks"]), expected["signal"],
                  str(ui["dashboard"]["pid"]), str(ui["dashboard"]["creation_ticks"])])
    return ui, observer


class NativeUacReceiptTests(unittest.TestCase):
    def test_accepts_complete_force_cancel_and_delayed_observations(self):
        for name in ("consent-force", "consent-cancel", "consent-delayed"):
            with self.subTest(name=name):
                validate_run(*observed_run(name), name)

    def test_stop_name_truncation_does_not_lose_lifecycle(self):
        ui, observer = observed_run()
        self.assertIn("system-pulse.e", [row["name"] for row in observer["events"]])
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
        ]
        for index, mutate in enumerate(changes):
            ui, observer = observed_run()
            mutate(ui, observer)
            with self.subTest(index=index), self.assertRaises(InvalidMeasurement):
                validate_run(ui, observer, "consent-force")


if __name__ == "__main__":
    unittest.main()
