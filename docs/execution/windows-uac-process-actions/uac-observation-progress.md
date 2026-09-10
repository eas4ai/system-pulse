# Windows UAC observation progress

The fresh [ordinary run](uac-native/ordinary/receipt.json) passed independent
verification from the packaged Windows binary. It covered confirmation
cancellation, cooperative and refusing graceful close, unavailable graceful close,
ordinary Force quit, an exited selection and delayed graceful close. Native traces
recorded zero consent processes and zero elevated action helpers. The dashboard
remained unelevated, the unrelated control remained unchanged, and owned targets,
entry probes and dashboard were cleaned up.

The [trace self-test](native-trace-selftest.json) passed six short-lived malformed
helper lifecycles. The [fault self-test](native-fault-selftest.json) passed native
access denial, termination through a retained handle, heartbeat suspension and
resumption, cleanup of a suspended process through job closure, and an unchanged
unrelated control. These are development checks on disposable processes. They do
not establish real application UAC approval, cancellation or helper failure.

The Python suite passed 562 tests, including the 16 process-evidence tests. Native
C# compilation and PowerShell parsing passed. The latest Windows identity gate
passed after redirecting temporary test files with
`TMPDIR=/home/shawn/workspace2/.system-pulse-test-tmp`: `/tmp` had exhausted its
inodes, causing a Linux collector fixture write to fail. The original failed
Cairn receipt is retained. No test assertion was changed for that failure.

## Next native action

No real UAC case has been started. Arrange a human at `10.66.231.23`, then start
with the administrator consent case below. The human approves the actual Windows
dialog; the harness performs the application confirmation and owns the target.

```sh
rtk proxy env TMPDIR=/home/shawn/workspace2/.system-pulse-test-tmp \
  python3 -B scripts/system-pulse/windows_process_uac_collect.py \
  --host shawn@10.66.231.23 \
  --build-log docs/execution/windows-uac-process-actions/process-actions-preservation/windows-build.log \
  --package-dir /home/shawn/.cache/system-pulse-windows-actions/windows-package-3e6923e3 \
  --case consent-force --operator-ready
```

The remaining native consent/cancellation/stale/failure cases, credential-account
setup and evidence, delayed-approval and resource-lifetime observations, full
acceptance integration and final adversarial review remain pending. The complete
acceptance verifier remains closed while that work is unfinished. The Windows
host has no identified ordinary standard-user test account; do not use its
sandbox or service accounts. Credentials must be entered only into Windows.

All work remains local. No push, hosted CI or release was performed for this work.
