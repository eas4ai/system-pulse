import tempfile
from pathlib import Path
import unittest

try:
    from gpu_capture import owned_process, validate_workload, validate_native_frame
except ImportError:
    owned_process = validate_workload = validate_native_frame = None


def interrupt_cleanup_probe(output, fail_finish):
    """Confine SIGINT and orphan reaping to a disposable Linux test process."""
    import ctypes
    import errno
    import json
    import os
    import signal
    import sys
    import threading
    import time
    from unittest.mock import patch
    import gpu_capture

    native = ctypes.CDLL(None, use_errno=True)
    assert native.prctl(36, 1, 0, 0, 0) == 0
    ready = output / "descendant-ready"
    descendant = (
        "import os,signal,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "Path(" + repr(str(ready)) + ").write_text(str(os.getpid())); time.sleep(8)"
    )
    leader = (
        "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"
        + repr(descendant)
        + "]); time.sleep(8)"
    )
    adopted = []

    def interrupt_and_reap():
        deadline = time.monotonic() + 2
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not ready.exists():
            return
        pid = int(ready.read_text())
        os.kill(os.getpid(), signal.SIGINT)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                if os.waitpid(pid, os.WNOHANG)[0]:
                    adopted.append(pid)
                    return
            except ChildProcessError:
                pass
            time.sleep(0.01)

    real_write = Path.write_text

    def write(path, *args, **kwargs):
        if fail_finish and path.name == "probe-finished.json":
            raise OSError(errno.ENOSPC, "injected completion write failure")
        return real_write(path, *args, **kwargs)

    thread = threading.Thread(target=interrupt_and_reap)
    thread.start()
    caught = None
    try:
        with patch.object(Path, "write_text", write):
            try:
                gpu_capture.owned_process(
                    output, "probe", [sys.executable, "-c", leader], 3
                )
            except BaseException as error:
                caught = error
        start = json.loads((output / "probe-started.json").read_text())
        result = dict(
            case="actual_SIGINT",
            fail_finish=fail_finish,
            error=type(caught).__name__,
            leader_pid=start["pid"],
            descendant_pid=int(ready.read_text()),
            group_existed_after_owner=gpu_capture.group_exists(start["pid"]),
            finished_record_exists=(output / "probe-finished.json").exists(),
            capture_errors=getattr(caught, "capture_errors", []),
        )
    finally:
        if (output / "probe-started.json").exists():
            pid = json.loads((output / "probe-started.json").read_text())["pid"]
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        thread.join(timeout=3)
        assert not thread.is_alive()
    result["test_cleanup_reaped_descendant"] = adopted == [result["descendant_pid"]]
    result["test_cleanup_group_absent"] = not gpu_capture.group_exists(
        result["leader_pid"]
    )
    print(json.dumps(result), flush=True)


def stream_cleanup_probe(output):
    """Exercise real handles/processes; isolate actual SIGINT in this probe."""
    import errno
    import json
    import os
    import signal
    import subprocess
    import sys
    import threading
    import time
    from unittest.mock import patch
    import gpu_capture

    class Stream:
        def __init__(self, stream, error):
            self.stream, self.error = stream, error

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            return self

        def close(self):
            self.stream.close()
            if self.error is not None:
                raise self.error

        def __exit__(self, *args):
            self.close()

    real_open, real_write, real_popen = Path.open, Path.write_text, subprocess.Popen
    sentinel = real_popen(
        [sys.executable, "-c", "import time; time.sleep(15)"], start_new_session=True
    )
    cases = [
        (trigger, streams)
        for trigger in ("close_only", "start_write", "actual_SIGINT")
        for streams in (("stdout",), ("stderr",), ("stderr", "stdout"))
    ] + [
        ("stdout_open", ()),
        ("stderr_open", ("stdout",)),
        ("launch", ("stderr", "stdout")),
    ]
    rows = []
    try:
        for index, (trigger, failing_streams) in enumerate(cases):
            directory = output / str(index)
            directory.mkdir()
            close_errors = {
                name: OSError(errno.EIO, "injected " + name + " close failure")
                for name in failing_streams
            }
            original = (
                close_errors[failing_streams[0]]
                if trigger == "close_only"
                else KeyboardInterrupt("injected original SIGINT")
                if trigger == "actual_SIGINT"
                else OSError(errno.ENOSPC, "injected original " + trigger)
            )
            launched, streams = [], []

            def opening(path, mode="r", *args, **kwargs):
                if mode != "x" or path.parent != directory:
                    return real_open(path, mode, *args, **kwargs)
                name = path.suffix[1:]
                if trigger == name + "_open":
                    raise original
                stream = Stream(
                    real_open(path, mode, *args, **kwargs), close_errors.get(name)
                )
                streams.append(stream)
                return stream

            def writing(path, *args, **kwargs):
                if trigger == "start_write" and path.name == "probe-started.json":
                    raise original
                return real_write(path, *args, **kwargs)

            def spawn(*args, **kwargs):
                if trigger == "launch":
                    raise original
                child = real_popen(*args, **kwargs)
                launched.append(child)
                return child

            ready = directory / "child-ready"
            command = [
                sys.executable,
                "-c",
                "print('normal exit')"
                if trigger == "close_only"
                else "from pathlib import Path; import time; Path("
                + repr(str(ready))
                + ").write_text('ready'); time.sleep(2)",
            ]
            thread = None
            old_handler = signal.getsignal(signal.SIGINT)
            if trigger == "actual_SIGINT":

                def handler(signum, frame):
                    raise original

                def interrupt():
                    deadline = time.monotonic() + 1
                    while not ready.exists() and time.monotonic() < deadline:
                        time.sleep(0.005)
                    if ready.exists():
                        os.kill(os.getpid(), signal.SIGINT)

                signal.signal(signal.SIGINT, handler)
                thread = threading.Thread(target=interrupt)
                thread.start()
            caught = None
            try:
                with (
                    patch.object(Path, "open", opening),
                    patch.object(Path, "write_text", writing),
                    patch.object(gpu_capture.subprocess, "Popen", spawn),
                ):
                    try:
                        gpu_capture.owned_process(directory, "probe", command, 1)
                    except BaseException as error:
                        caught = error
                record = getattr(caught, "capture_record", None)
                finished = directory / "probe-finished.json"
                rows.append(
                    dict(
                        trigger=trigger,
                        failing_streams=failing_streams,
                        original_exception_preserved=caught is original,
                        expected_primary_type=type(original).__name__,
                        actual_primary_type=type(caught).__name__,
                        expected_secondary_messages=[
                            str(close_errors[name])
                            for name in failing_streams
                            if close_errors[name] is not original
                        ],
                        capture_errors=getattr(caught, "capture_errors", []),
                        capture_record=record,
                        disk_record_matches=finished.exists()
                        and json.loads(finished.read_text()) == record,
                        children_after_owner=[
                            dict(
                                pid=c.pid,
                                reaped=c.poll() is not None,
                                group_exists=gpu_capture.group_exists(c.pid),
                            )
                            for c in launched
                        ],
                        streams_closed=all(stream.stream.closed for stream in streams),
                        stream_count=len(streams),
                        unrelated_sentinel_running=sentinel.poll() is None,
                    )
                )
            finally:
                if thread is not None:
                    thread.join(timeout=2)
                    assert not thread.is_alive()
                signal.signal(signal.SIGINT, old_handler)
                for child in launched:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait(timeout=3)
                for stream in streams:
                    stream.stream.close()
    finally:
        try:
            os.killpg(sentinel.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        sentinel.wait(timeout=3)
    print(
        json.dumps(
            dict(
                rows=rows,
                sentinel_pid=sentinel.pid,
                sentinel_reaped=sentinel.poll() is not None,
                sentinel_group_absent=not gpu_capture.group_exists(sentinel.pid),
            )
        ),
        flush=True,
    )


class NativeTests(unittest.TestCase):
    def test_stream_cleanup_preserves_execution_and_first_close_errors(self):
        import json
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            script = (
                "from pathlib import Path; from test_gpu_native import stream_cleanup_probe; stream_cleanup_probe(Path("
                + repr(tmp)
                + "))"
            )
            result = subprocess.run(
                [sys.executable, "-B", "-c", script],
                cwd=Path(__file__).parent,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            proof = json.loads(result.stdout)
            print(result.stdout.strip())
            self.assertTrue(proof["sentinel_reaped"])
            self.assertTrue(proof["sentinel_group_absent"])
            self.assertEqual(len(proof["rows"]), 12)
            for row in proof["rows"]:
                with self.subTest(
                    trigger=row["trigger"], streams=row["failing_streams"]
                ):
                    self.assertTrue(row["original_exception_preserved"], row)
                    self.assertEqual(
                        row["actual_primary_type"], row["expected_primary_type"]
                    )
                    self.assertEqual(
                        [e["message"] for e in row["capture_errors"]],
                        row["expected_secondary_messages"],
                    )
                    self.assertTrue(row["streams_closed"])
                    self.assertTrue(row["unrelated_sentinel_running"])
                    launched = row["trigger"] not in (
                        "stdout_open",
                        "stderr_open",
                        "launch",
                    )
                    self.assertEqual(len(row["children_after_owner"]), int(launched))
                    self.assertEqual(
                        row["stream_count"],
                        0
                        if row["trigger"] == "stdout_open"
                        else 1
                        if row["trigger"] == "stderr_open"
                        else 2,
                    )
                    if launched:
                        self.assertTrue(row["disk_record_matches"])
                        self.assertEqual(
                            row["capture_record"]["capture_error"],
                            row["expected_primary_type"],
                        )
                        self.assertTrue(row["capture_record"]["reaped"])
                        self.assertFalse(row["capture_record"]["proc_exists"])
                    else:
                        self.assertIsNone(row["capture_record"])
                    self.assertTrue(
                        all(
                            c["reaped"] and not c["group_exists"]
                            for c in row["children_after_owner"]
                        )
                    )

    def test_start_record_failure_reaps_children_and_preserves_original_error(self):
        import errno
        import json
        import os
        import signal
        import subprocess
        import sys
        from unittest.mock import patch
        import gpu_capture

        for concurrent in (False, True):
            for fail_reporting in (False, True):
                with (
                    self.subTest(concurrent=concurrent, fail_reporting=fail_reporting),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    output = Path(tmp)
                    launched = []
                    original = OSError(errno.ENOSPC, "injected start write failure")
                    real_popen, real_write = subprocess.Popen, Path.write_text

                    def spawn(*args, **kwargs):
                        child = real_popen(*args, **kwargs)
                        launched.append(child)
                        return child

                    def write(path, *args, **kwargs):
                        if path.name.endswith("-started.json"):
                            raise original
                        if fail_reporting and (
                            path.name.endswith("-finished.json")
                            or path.name == "lifecycle.json"
                        ):
                            raise OSError(
                                errno.EIO, "injected secondary recording failure"
                            )
                        return real_write(path, *args, **kwargs)

                    try:
                        with (
                            patch.object(gpu_capture.subprocess, "Popen", spawn),
                            patch.object(Path, "write_text", write),
                        ):
                            with self.assertRaises(OSError) as caught:
                                command = [
                                    sys.executable,
                                    "-c",
                                    "import time; time.sleep(3)",
                                ]
                                if concurrent:
                                    with gpu_capture.CaptureChildren(
                                        output
                                    ) as children:
                                        children.start("probe", command, 0.05)
                                else:
                                    owned_process(output, "probe", command, 0.05)
                        self.assertIs(caught.exception, original)
                        self.assertEqual(len(launched), 1)
                        self.assertIsNotNone(launched[0].poll())
                        self.assertFalse(gpu_capture.group_exists(launched[0].pid))
                        if fail_reporting:
                            self.assertTrue(caught.exception.capture_errors)
                        else:
                            record = json.loads(
                                (output / "probe-finished.json").read_text()
                            )
                            self.assertTrue(record["reaped"])
                            self.assertFalse(record["proc_exists"])
                    finally:
                        before = [
                            dict(
                                pid=c.pid,
                                alive=c.poll() is None,
                                group_exists=gpu_capture.group_exists(c.pid),
                            )
                            for c in launched
                        ]
                        for child in launched:
                            try:
                                os.killpg(child.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            child.wait(timeout=3)
                        print(
                            json.dumps(
                                dict(
                                    case="start_write_failure",
                                    concurrent=concurrent,
                                    fail_reporting=fail_reporting,
                                    after_owner=before,
                                    test_cleanup_groups_absent=all(
                                        not gpu_capture.group_exists(c.pid)
                                        for c in launched
                                    ),
                                )
                            )
                        )

    @unittest.skipUnless(
        __import__("sys").platform.startswith("linux"), "confined Linux subreaper probe"
    )
    def test_actual_interrupt_cleans_descendants_before_preserving_exception(self):
        import json
        import subprocess
        import sys

        for fail_finish in (False, True):
            with (
                self.subTest(fail_finish=fail_finish),
                tempfile.TemporaryDirectory() as tmp,
            ):
                script = (
                    "from pathlib import Path; from test_gpu_native import interrupt_cleanup_probe; interrupt_cleanup_probe(Path("
                    + repr(tmp)
                    + "),"
                    + repr(fail_finish)
                    + ")"
                )
                result = subprocess.run(
                    [sys.executable, "-B", "-c", script],
                    cwd=Path(__file__).parent,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                row = json.loads(result.stdout)
                print(result.stdout.strip())
                self.assertEqual(row["error"], "KeyboardInterrupt")
                self.assertFalse(row["group_existed_after_owner"])
                self.assertTrue(row["test_cleanup_reaped_descendant"])
                self.assertTrue(row["test_cleanup_group_absent"])
                self.assertEqual(row["finished_record_exists"], not fail_finish)
                if fail_finish:
                    self.assertTrue(row["capture_errors"])

    def test_concurrent_cleanup_keeps_ownership_when_start_record_disappears(self):
        import json
        import sys
        import gpu_capture

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            original = RuntimeError("capture body failed")
            with self.assertRaises(RuntimeError) as caught:
                with gpu_capture.CaptureChildren(output) as children:
                    children.start(
                        "probe", [sys.executable, "-c", "import time; time.sleep(3)"], 2
                    )
                    (output / "probe-started.json").unlink()
                    raise original
            self.assertIs(caught.exception, original)
            record = json.loads((output / "probe-finished.json").read_text())
            print(json.dumps(dict(case="missing_start_artifact", record=record)))
            self.assertFalse(record["timed_out"])
            self.assertTrue(record["reaped"])
            self.assertFalse(record["proc_exists"])
            self.assertEqual(
                json.loads((output / "lifecycle.json").read_text()), [record]
            )

    def test_workload_requires_matching_device_completed_commands_and_bounds(self):
        self.assertIsNotNone(validate_workload, "native workload validation missing")
        good = dict(
            registry_id=19,
            bytes=4 * 1024**2,
            commands_completed=3,
            duration_ns=20_000_000,
            max_in_flight=1,
            pid=123,
        )
        validate_workload(good, 19, 1)
        for changes in (
            dict(registry_id=20),
            dict(bytes=2**40),
            dict(commands_completed=0),
            dict(max_in_flight=2),
            dict(duration_ns=2_000_000_000),
        ):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                validate_workload({**good, **changes}, 19, 1)

    def test_owned_process_deadline_retains_logs_and_reaps(self):
        self.assertIsNotNone(owned_process, "bounded native child manager missing")
        with tempfile.TemporaryDirectory() as tmp:
            import sys

            r = owned_process(
                Path(tmp),
                "observer",
                [
                    sys.executable,
                    "-c",
                    "import time; print('original',flush=True); time.sleep(10)",
                ],
                0.05,
            )
            self.assertTrue(r["reaped"])
            self.assertFalse(r["proc_exists"])
            self.assertTrue(r["timed_out"])
            self.assertIn("original", (Path(tmp) / r["stdout"]).read_text())

    def test_owned_process_cleans_descendants_after_leader_exits(self):
        import sys
        import os
        import signal

        with tempfile.TemporaryDirectory() as tmp:
            record = owned_process(
                Path(tmp),
                "observer",
                [
                    sys.executable,
                    "-c",
                    "import subprocess; subprocess.Popen(['sleep','10'])",
                ],
                2,
            )
            try:
                self.assertFalse(record["proc_exists"])
            finally:
                try:
                    os.killpg(record["pid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_ax_cycles_truncation_and_zero_geometry_are_not_display(self):
        self.assertIsNotNone(validate_native_frame, "native frame validation missing")
        for frame in (
            dict(complete=False, elements=[]),
            dict(complete=True, elements=[]),
            dict(
                complete=True,
                elements=[
                    dict(identifier="gpu", frame=[0, 0, 0, 1], clip=[0, 0, 100, 100])
                ],
            ),
        ):
            with self.subTest(frame=frame), self.assertRaises(AssertionError):
                validate_native_frame(frame)

    def test_concurrent_owned_child_is_stopped_when_capture_fails(self):
        import gpu_capture

        self.assertTrue(
            hasattr(gpu_capture, "CaptureChildren"), "concurrent capture owner missing"
        )
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "capture failed"):
                with gpu_capture.CaptureChildren(output) as children:
                    pid = children.start(
                        "application",
                        [sys.executable, "-c", "import time; time.sleep(10)"],
                        5,
                    )
                    self.assertGreater(pid, 0)
                    raise RuntimeError("capture failed")
            import json

            record = json.loads((output / "application-finished.json").read_text())
            self.assertTrue(record["reaped"])
            self.assertFalse(record["proc_exists"])
            self.assertNotEqual(record["exit_code"], 0)

    def test_locked_or_unavailable_console_never_allows_gui_capture(self):
        from gpu_host_capture import console_session

        session = dict(
            kCGSSessionOnConsoleKey=True,
            kCGSessionLoginDoneKey=True,
            CGSSessionScreenIsLocked=True,
        )
        self.assertTrue(console_session([dict(IOConsoleUsers=[session])])["locked"])
        session["CGSSessionScreenIsLocked"] = False
        self.assertFalse(console_session([dict(IOConsoleUsers=[session])])["locked"])
        session.pop("CGSSessionScreenIsLocked")
        with self.assertRaises(AssertionError):
            console_session([dict(IOConsoleUsers=[session])])
        with self.assertRaises(AssertionError):
            console_session([dict(IOConsoleUsers=[])])

    def test_native_hashing_does_not_require_python_311(self):
        self.assertIsNotNone(owned_process, "native child manager missing")
        import hashlib
        from unittest.mock import patch
        import sys

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(hashlib, "file_digest", None),
        ):
            r = owned_process(
                Path(tmp), "observer", [sys.executable, "-c", "print('original')"], 2
            )
            self.assertEqual(r["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
