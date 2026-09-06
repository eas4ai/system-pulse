import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    from gpu_evidence import (
        artifact,
        validate_manifest,
        validate_lifecycle,
        validate_actions,
        requirement_results,
    )
except ImportError:
    artifact = validate_manifest = validate_lifecycle = validate_actions = (
        requirement_results
    ) = None


class EvidenceTests(unittest.TestCase):
    def test_json_lines_reject_duplicate_keys_and_nonfinite_numbers(self):
        from gpu_evidence import read_lines
        import tempfile
        from pathlib import Path

        for raw in ('{"a":1,"a":2}\n', '{"a":NaN}\n', '{"a":1e999}\n'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "raw.jsonl"
                path.write_text(raw)
                with self.assertRaises((AssertionError, ValueError)):
                    read_lines(path)

    def test_original_hash_size_and_paths(self):
        self.assertIsNotNone(artifact, "GPU artifact verifier is not implemented")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "original").write_bytes(b"original operands\n")
            record = dict(
                path="original",
                bytes=18,
                sha256=hashlib.sha256(b"original operands\n").hexdigest(),
            )
            self.assertEqual(
                artifact(root, record).read_bytes(), b"original operands\n"
            )
            for change in (
                dict(bytes=1),
                dict(sha256="0" * 64),
                dict(path="missing"),
                dict(path="../original"),
            ):
                with (
                    self.subTest(change=change),
                    self.assertRaises((AssertionError, OSError)),
                ):
                    artifact(root, {**record, **change})

    def test_missing_hosts_and_empty_selected_suite_never_pass(self):
        self.assertIsNotNone(requirement_results, "GPU aggregate is not implemented")
        self.assertFalse(any(requirement_results({}, False, False).values()))
        for class_name in ("intel-integrated", "intel-discrete", "apple-silicon"):
            result = requirement_results({class_name: set(range(1, 9))}, True, True)
            self.assertFalse(result[8])
        result = requirement_results(
            {
                n: set(range(1, 9))
                for n in ("intel-integrated", "intel-discrete", "apple-silicon")
            },
            True,
            False,
        )
        self.assertFalse(any(result.values()))

    def test_lifecycle_requires_each_pid_diagnostics_and_reaping(self):
        self.assertIsNotNone(
            validate_lifecycle, "GPU lifecycle verifier is not implemented"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            processes = []
            for n, role in enumerate(
                ("collector", "observer", "workload", "application"), 10
            ):
                (root / (role + ".stdout")).write_text("")
                (root / (role + ".stderr")).write_text("")
                processes.append(
                    dict(
                        role=role,
                        pid=n,
                        exit_code=0,
                        reaped=True,
                        proc_exists=False,
                        started_ns=1,
                        finished_ns=9,
                        deadline_ns=10,
                        environment={"OBJC_DEBUG_MISSING_POOLS": "YES"},
                        stdout=role + ".stdout",
                        stderr=role + ".stderr",
                    )
                )
            validate_lifecycle(root, processes, "apple-silicon")
            for change in (
                dict(reaped=False),
                dict(exit_code=1),
                dict(proc_exists=True),
                dict(finished_ns=11),
                dict(environment={}),
            ):
                altered = copy.deepcopy(processes)
                altered[2].update(change)
                with self.subTest(change=change), self.assertRaises(AssertionError):
                    validate_lifecycle(root, altered, "apple-silicon")
            (root / "workload.stderr").write_text(
                "objc[12]: Object autoreleased with no pool in place - just leaking\n"
            )
            with self.assertRaises(AssertionError):
                validate_lifecycle(root, processes, "apple-silicon")

    def test_no_actual_native_action_and_stale_geometry_fail(self):
        self.assertIsNotNone(validate_actions, "GPU action verifier is not implemented")
        with self.assertRaises(AssertionError):
            validate_actions([], {}, dict(freshness_ns=100))
        action = dict(
            name="panel-collapse",
            method="AXPress",
            return_code=0,
            started_ns=100,
            finished_ns=101,
            before=dict(observed_ns=90, elements=[]),
            after=dict(observed_ns=102, elements=[]),
        )
        with self.assertRaises(AssertionError):
            validate_actions([action], {}, dict(freshness_ns=100))

    def test_complete_manifest_rejects_wrong_source_binary_and_device(self):
        import gpu_evidence
        from gpu_capture import sha256

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in gpu_evidence.ORIGINALS:
                (root / name).write_text("{}")
            (root / "source").mkdir()
            (root / "source/one.py").write_text("print(1)")
            inputs = {"one.py": sha256(root / "source/one.py")}
            executables = {
                role: role + ".binary"
                for role in ("application", "collector", "observer")
            }
            for role, path in executables.items():
                (root / path).write_text(role + " executable")
            (root / "build.stdout").write_text("finished")
            (root / "build.stderr").write_text("")
            field = dict(sensor_id="gpu/usage")
            inventory = dict(
                hardware_class="apple-silicon",
                device=dict(monitor_id="gpu"),
                fields=[field],
                captured_unix_ns=1,
            )
            policy = dict(
                **inventory,
                declared_unix_ns=2,
                phases=["idle", "load", "interval", "recovery"],
                sample_count=4,
                warmup_samples=1,
                retries=0,
                rounding_ulps=4,
                max_query_ns=10,
                max_gap_ns=10,
                freshness_ns=10,
                deadline_ns=100,
                poll_interval_ns=10,
            )
            build = dict(
                inputs=inputs,
                executables=executables,
                exit_code=0,
                source_commit="a" * 40,
                command=[
                    "cargo",
                    "build",
                    "--locked",
                    "-p",
                    "system-pulse",
                    "--bin",
                    "system-pulse",
                    "-p",
                    "system-pulse-collectors",
                    "--bin",
                    "pulse-snapshot",
                ],
                build_stdout="build.stdout",
                build_stderr="build.stderr",
            )
            for name, data in [
                ("policy.json", policy),
                ("inventory.json", inventory),
                ("build.json", build),
            ]:
                (root / name).write_text(json.dumps(data))
            report = dict(
                schema=1,
                mode="native",
                hardware_class="apple-silicon",
                inputs=inputs,
                capture_started_unix_ns=3,
                capture_finished_unix_ns=20,
                executables={r: sha256(root / p) for r, p in executables.items()},
            )

            def manifest():
                return [
                    dict(
                        path=str(p.relative_to(root)),
                        bytes=p.stat().st_size,
                        sha256=sha256(p),
                    )
                    for p in root.rglob("*")
                    if p.is_file()
                ]

            report["artifacts"] = manifest()
            validate_manifest(root, report, inputs)
            changes = [
                lambda r: r["executables"].update(application="0" * 64),
                lambda r: r.update(inputs={"one.py": "0" * 64}),
                lambda r: r.update(hardware_class="intel-discrete"),
                lambda r: r["artifacts"].__setitem__(
                    slice(None),
                    [a for a in r["artifacts"] if a["path"] != "source/one.py"],
                ),
            ]
            for change in changes:
                altered = copy.deepcopy(report)
                change(altered)
                with self.assertRaises(AssertionError):
                    validate_manifest(root, altered, inputs)
            (root / "source/one.py").write_text("print(2)")
            report["artifacts"] = manifest()
            with self.assertRaises(AssertionError):
                validate_manifest(root, report, inputs)

    def test_wrong_source_binary_device_and_omitted_originals(self):
        self.assertIsNotNone(
            validate_manifest, "GPU manifest verifier is not implemented"
        )
        with tempfile.TemporaryDirectory() as tmp:
            for record in (
                {},
                dict(status="PASS", hardware_class="apple-silicon"),
                dict(status="PASS", source_commit="wrong", device="invented"),
            ):
                with (
                    self.subTest(record=record),
                    self.assertRaises((AssertionError, KeyError)),
                ):
                    validate_manifest(Path(tmp), record, {})


if __name__ == "__main__":
    unittest.main()
