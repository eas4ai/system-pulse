"""Aggregate acceptance must independently reproduce retained process coverage."""

import json
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
