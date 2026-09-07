"""Exercise replay failure cleanup without importing GI or launching processes."""

import ast
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock


def cleanup_after_failure(script, **context):
    """Run the real main finally block while an original replay error unwinds."""
    source = Path(__file__).with_name(script)
    main = next(
        node
        for node in ast.parse(source.read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    cleanup = next(
        node for node in main.body if isinstance(node, ast.Try) and node.finalbody
    )
    wrapper = ast.parse("try:\n    raise original_error\nfinally:\n    pass\n")
    wrapper.body[0].finalbody = cleanup.finalbody
    namespace = dict(json=json, subprocess=subprocess, sys=sys, time=time, **context)
    exec(compile(ast.fix_missing_locations(wrapper), str(source), "exec"), namespace)


class TabbedCleanupTests(unittest.TestCase):
    def app(self, screenshot_error=None, close_error=None):
        app = Mock(closed=False)
        app.app.poll.return_value = None
        app.screenshot.side_effect = screenshot_error
        app.close.side_effect = close_error
        return app

    def children(self):
        children = []
        for pid in (101, 102, 103):
            child = Mock(pid=pid)
            child.poll.side_effect = [None, -15]
            children.append(child)
        return children

    def test_replay_screenshot_failure_preserves_error_and_all_cleanup(self):
        for screenshot_error in (None, OSError("screenshot unavailable")):
            with self.subTest(screenshot_error=screenshot_error):
                app = self.app(screenshot_error)
                children = self.children()
                transport = Mock()
                record = {"status": "FAIL", "error": "original replay failure"}
                original = AssertionError("original replay failure")
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory)
                    with self.assertRaises(AssertionError) as raised:
                        cleanup_after_failure(
                            "tabbed_replay.py",
                            app=app,
                            children=children,
                            record=record,
                            started=time.monotonic(),
                            output=output,
                            close_transport=transport,
                            original_error=original,
                        )
                    self.assertIs(raised.exception, original)
                    retained = json.loads((output / "result.json").read_text())
                    self.assertEqual(retained["status"], "FAIL")
                    self.assertEqual(retained["error"], "original replay failure")
                    self.assertEqual(
                        retained["children"],
                        [{"pid": pid, "exit_code": -15} for pid in (101, 102, 103)],
                    )
                    if screenshot_error is not None:
                        self.assertIn("screenshot unavailable", retained["failure_screenshot_error"])
                    app.close.assert_called_once_with()
                    transport.assert_called_once_with(output)
                    for child in children:
                        child.terminate.assert_called_once_with()
                        child.wait.assert_called_once_with(timeout=5)

    def test_package_screenshot_failure_preserves_error_and_all_cleanup(self):
        app = self.app(OSError("screenshot unavailable"))
        transport = Mock()
        original = AssertionError("original package failure")
        output = Path("unused-no-files-written")
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(AssertionError) as raised:
            cleanup_after_failure(
                "package_smoke.py",
                app=app,
                output=output,
                close_transport=transport,
                original_error=original,
            )
        self.assertIs(raised.exception, original)
        self.assertIn("screenshot unavailable", stderr.getvalue())
        app.close.assert_called_once_with()
        transport.assert_called_once_with(output)

    def test_replay_application_cleanup_error_still_reaps_children_and_transport(self):
        app = self.app(close_error=OSError("application cleanup failed"))
        children = self.children()
        transport = Mock()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaisesRegex(OSError, "application cleanup failed"):
                cleanup_after_failure(
                    "tabbed_replay.py",
                    app=app,
                    children=children,
                    record={"status": "FAIL"},
                    started=time.monotonic(),
                    output=output,
                    close_transport=transport,
                    original_error=AssertionError("original replay failure"),
                )
            self.assertTrue((output / "result.json").is_file())
            for child in children:
                child.terminate.assert_called_once_with()
            transport.assert_called_once_with(output)

    def test_package_application_cleanup_error_still_closes_transport(self):
        app = self.app(close_error=OSError("application cleanup failed"))
        transport = Mock()
        output = Path("unused-no-files-written")
        with self.assertRaisesRegex(OSError, "application cleanup failed"):
            cleanup_after_failure(
                "package_smoke.py",
                app=app,
                output=output,
                close_transport=transport,
                original_error=AssertionError("original package failure"),
            )
        transport.assert_called_once_with(output)


if __name__ == "__main__":
    unittest.main()
