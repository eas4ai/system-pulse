"""Aggregate acceptance must independently reproduce retained process coverage."""

import json
import errno
from pathlib import Path
import tempfile
import unittest

import acceptance
from test_process_exit_policy import write_host_fixture


class ProcessCoverageGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        write_host_fixture(self.output / "host", with_exit=True)
        for filename in (
            "collector-start.json",
            "collector-stopped.json",
            "cleanup.json",
        ):
            (self.output / "host" / filename).write_text("{}")
        self.runner = acceptance.Runner(self.output)
        self.runner.steps["host"] = dict(exit_code=0, timed_out=False)

    def mutate(self, filename, change):
        path = self.output / "host" / filename
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))

    def test_valid_exit_evidence_stays_separate_in_manifest(self):
        artifacts = acceptance.validate_host(self.runner)
        names = {Path(item["path"]).name for item in artifacts}
        self.assertTrue(
            {
                "process-policy.json",
                "process-coverage.json",
                "unverified-exit-gaps.json",
            }
            <= names
        )

    def test_missing_declaration_and_coverage_fail(self):
        for name in (
            "process-policy.json",
            "process-coverage.json",
            "unverified-exit-gaps.json",
        ):
            with self.subTest(name=name):
                path = self.output / "host" / name
                saved = path.read_text()
                path.unlink()
                with self.assertRaises((AssertionError, OSError)):
                    acceptance.validate_host(self.runner)
                path.write_text(saved)

    def test_inconsistent_counts_unknown_classification_and_missing_terminal_fail(self):
        mutations = (
            ("result.json", lambda d: d["counts"].update(counter_brackets=999)),
            ("process-coverage.json", lambda d: d.update(unverified_exit_gaps=0)),
            ("process-coverage.json", lambda d: d.update(controlled=[])),
            (
                "unverified-exit-gaps.json",
                lambda d: d[0].update(classification="verified"),
            ),
            ("unverified-exit-gaps.json", lambda d: d[0].pop("terminal")),
            ("counter-brackets.json", lambda d: d[0].update(classification="unknown")),
            ("process-policy.json", lambda d: d.update(declared_ns=1)),
            ("process-policy.json", lambda d: d.update(version=True)),
            ("process-policy.json", lambda d: d["controlled_identity"].update(pid=99)),
        )
        for name, change in mutations:
            with self.subTest(name=name, change=change):
                path = self.output / "host" / name
                saved = path.read_text()
                self.mutate(name, change)
                with self.assertRaises((AssertionError, KeyError, ValueError)):
                    acceptance.validate_host(self.runner)
                path.write_text(saved)

    def test_existing_fail_is_never_rewritten(self):
        path = self.output / "host/result.json"
        self.mutate("result.json", lambda d: d.update(status="FAIL"))
        before = path.read_bytes()
        with self.assertRaises(AssertionError):
            acceptance.validate_host(self.runner)
        self.assertEqual(path.read_bytes(), before)

    def test_child_evidence_is_required_and_rechecked(self):
        path = self.output / "host/child.json"
        saved = path.read_text()
        mutations = (
            lambda d: d.pop("after"),
            lambda d: d.pop("snapshot_rows"),
            lambda d: d["after"]["stat"].update(errno=errno.EACCES, value=None),
            lambda d: d["after"]["stat"]["value"].update(pid=99),
            lambda d: d["after"]["stat"]["value"].update(start_ticks=999),
            lambda d: d["after"]["stat"]["value"].update(rss_pages=2),
            lambda d: d["after"]["stat"]["value"].update(threads=2),
            lambda d: d["after"]["stat"].update(start=-2, end=-1),
            lambda d: d["snapshot_rows"].clear(),
            lambda d: d["snapshot_rows"][0].update(name="wrong"),
            lambda d: d["snapshot_rows"][0].update(user="wrong"),
            lambda d: d.pop("terminal_stat"),
            lambda d: d["terminal_stat"].update(errno=errno.EACCES),
            lambda d: d["terminal_stat"].update(start=141),
            lambda d: d["terminal_stat"].update(source="/proc/99/stat"),
            lambda d: d.update(exit_code=None),
        )
        for change in mutations:
            with self.subTest(change=change):
                path.write_text(saved)
                self.mutate("child.json", change)
                with self.assertRaises((AssertionError, KeyError)):
                    acceptance.validate_host(self.runner)
                path.write_text(saved)

    def test_matching_but_wrong_retained_and_snapshot_child_rows_fail(self):
        for key, value in (("name", "wrong"), ("user", "wrong")):
            with self.subTest(key=key):
                path = self.output / "host/snapshots.jsonl"
                saved = path.read_text()
                snapshots = [json.loads(line) for line in saved.splitlines()]
                snapshots[0]["processes"][0][key] = value
                path.write_text("".join(json.dumps(s) + "\n" for s in snapshots))
                child_path = self.output / "host/child.json"
                saved_child = child_path.read_text()
                self.mutate(
                    "child.json", lambda d: d["snapshot_rows"][0].update({key: value})
                )
                with self.assertRaisesRegex(AssertionError, "child|parentheses"):
                    acceptance.validate_host(self.runner)
                path.write_text(saved)
                child_path.write_text(saved_child)

    def test_reversed_terminal_window_cannot_pass_with_matching_gap_artifact(self):
        def reverse_terminal(value):
            if isinstance(value, dict):
                if (
                    value.get("source") == "/proc/99/stat"
                    and value.get("errno") == errno.ENOENT
                ):
                    value["start"] = value["end"] + 100
                for child in value.values():
                    reverse_terminal(child)
            elif isinstance(value, list):
                for child in value:
                    reverse_terminal(child)

        for filename in ("external-observations.json", "unverified-exit-gaps.json"):
            self.mutate(filename, reverse_terminal)
        with self.assertRaisesRegex(AssertionError, "window"):
            acceptance.validate_host(self.runner)
