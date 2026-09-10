# Windows native runtime verification

The native run `8c5e79406d29418d94d2455a092f2699` passed on the Dell XPS tablet
on 2026-09-10 UTC (2026-09-09 local). It used the executable from the
[passing Windows build](windows-build.md), SHA-256
`8f462e175175a19cb02af11a69b1b16d38f6ddaa31c7ca89311388cfe3258da0`.
Its source revision is `fd98c4704cb2d79b5625cb4b8d0a6817fade0046`;
the runtime gate rejects changes to the tested production source.

The [record](runtime/result.json) binds the build log, executable, native harness
and retained artifacts by hash. The [visual review](runtime/visual-review.json)
binds the eight inspected screenshots to this run. Both application runs used
a limited interactive Windows account and an isolated state directory.

## Observed behavior

- All ten screens selected successfully. Summary displayed live charts and
  eight top-CPU process rows; the process table rendered aligned columns.
- A search for `system-pulse.exe` returned exactly the tested process.
  Two PID header activations produced ascending and descending order across
  22 visible rows. The normal run also exposed 22 process rows.
- Closing the dashboard kept the process alive. Invoking the actual Windows
  tray icon created a new visible dashboard window with the settings retained.
- Light theme, IBM Plex Sans, IBM Plex Mono and a two-second sampling interval
  were selected through Windows UI Automation. The state file recorded them,
  and a new process restored all four choices with diagnostics disabled.
- Both runs exited through the native tray's Quit item with exit code 0.
  Both stderr logs were empty. The normal run did not update the diagnostic file.
- Diagnostic sequences advanced. The 12 logical CPUs and 16,853,491,712-byte
  visible memory total agreed with native Windows queries. CPU utilization,
  memory and the running application's process readings were present.

## Hardware and limitations

Windows 11 Pro 10.0.26200; Intel Core i7-1250U (10 cores, 12 threads);
Intel Iris Xe driver 32.0.101.6881. CPU, memory, volume and network monitors
were present. Intel Windows GPU collection is not implemented. GPU,
temperature and power screens explicitly showed no available measurements;
the absent NVIDIA runtime was reported in diagnostics. These observations
do not establish Windows GPU support or per-field accuracy for every sensor.

Windows process thread counts and process-control actions remain unsupported.
Some common sysinfo APIs cannot distinguish inaccessible readings from zero;
this run does not certify protected-process readings. Linux and Mac process
control behavior is covered by their separate native evidence.

The tablet's touch taskbar initially hid the tray. The harness focuses the
Windows shell and uses Win+T before opening hidden icons. The native popup
exposes a UI Automation pane without accessible menu items, so the harness
checks its owning PID, retains a screenshot and clicks the displayed Quit row.
The screenshots independently confirm the two menu commands.

During harness development, a query ran before the reopened accessibility
tree was ready, and an initial table traversal exported no rows. Neither
partial record was accepted. The final harness waits for the ten tabs and
rejects an empty native row observation; the validator separately rejects
missing rows and incorrect sort order.

## Reproduce

Keep the tablet logged in and unlocked, with no System Pulse instance running.
The Windows build verifier must have produced the current executable first.
From the source repository:

```sh
SYSTEM_PULSE_WINDOWS_HOST=user@windows-host python3 -B scripts/system-pulse/windows_runtime_collect.py \
  --build-log .cairn/evidence/REL-001/20260910T014627173Z-1328174.out
```

Use the corresponding successful REL-001 log after a new build. The collector
prints its unique output directory. Inspect its screenshots and create a
`visual-review.json` with the same fields as the retained review, using that
run's identity and screenshot hashes. Never copy a review across runs.

```sh
SYSTEM_PULSE_WINDOWS_RUNTIME_EVIDENCE=/path/to/run python3 -B scripts/system-pulse/windows_runtime_verify.py
```

Retain the accepted artifacts and review in `runtime/`, commit the harness and
evidence, then run `cairn check REL-002`. The gate validates the retained native
observations; it does not pretend to repeat GUI interactions on the checking host.
