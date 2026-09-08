"""Real RTK/private-session completion with a descendant holding output open."""

import ctypes
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest

from application_acceptance import private_session


@unittest.skipUnless(
    sys.platform == "linux"
    and all(shutil.which(tool) for tool in ("rtk", "xvfb-run", "dbus-run-session")),
    "requires the Linux native acceptance tools",
)
class PrivateSessionOutputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.previous = ctypes.c_int()
        self.assertEqual(self.libc.prctl(37, ctypes.byref(self.previous), 0, 0, 0), 0)
        self.assertEqual(self.libc.prctl(36, 1, 0, 0, 0), 0)
        self.addCleanup(self.libc.prctl, 36, self.previous.value, 0, 0, 0)

    def run_session(self, source):
        script = self.root / "session.py"
        script.write_text(source)
        log = self.root / "session.log"
        pid_file = self.root / "child.pid"
        command = private_session(script, pid_file, log=log)
        child = subprocess.Popen(
            ["rtk", "proxy", *command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = child.communicate(timeout=10)
            descendant_alive = False
            if pid_file.exists():
                pid = int(pid_file.read_text())
                descendant_alive = os.waitpid(pid, os.WNOHANG) == (0, 0)
            return child.returncode, stdout, stderr, log.read_text(), descendant_alive
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.communicate(timeout=5)
            if pid_file.exists():
                try:
                    os.waitpid(int(pid_file.read_text()), 0)
                except ChildProcessError:
                    pass

    def test_descendant_output_does_not_hold_the_proxy_after_session_exit(self):
        result = self.run_session(
            "import subprocess, sys\n"
            "from pathlib import Path\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "Path(sys.argv[1]).write_text(str(child.pid))\n"
            "print('session completed', flush=True)\n"
            "print('retained stderr', file=sys.stderr, flush=True)\n"
        )
        status, stdout, stderr, log, descendant_alive = result
        self.assertEqual(status, 0, stderr)
        self.assertTrue(descendant_alive, "fixture must still hold its output open")
        self.assertIn("Native session output:", stdout)
        self.assertIn("session completed", log)
        self.assertIn("retained stderr", log)

    def test_nonzero_session_result_is_preserved(self):
        status, _, stderr, log, _ = self.run_session(
            "import sys\nprint('session failed', flush=True)\nsys.exit(7)\n"
        )
        self.assertEqual(status, 7, stderr)
        self.assertIn("session failed", log)

    def test_display_survives_between_application_connections(self):
        status, _, stderr, log, _ = self.run_session(
            "from Xlib import display, Xatom\n"
            "import time\n"
            "d = display.Display()\n"
            "atom = d.intern_atom('SYSTEM_PULSE_SESSION_MARKER')\n"
            "d.screen().root.change_property(atom, Xatom.STRING, 8, b'private session')\n"
            "d.sync()\n"
            "d.close()\n"
            "time.sleep(.02)\n"
            "d = display.Display()\n"
            "atom = d.intern_atom('SYSTEM_PULSE_SESSION_MARKER')\n"
            "value = d.screen().root.get_full_property(atom, Xatom.STRING)\n"
            "assert value is not None and value.value == b'private session', 'display reset between connections'\n"
            "d.close()\n"
            "print('display session retained', flush=True)\n"
        )
        self.assertEqual(status, 0, stderr + log)
        self.assertIn("display session retained", log)


if __name__ == "__main__":
    unittest.main()
