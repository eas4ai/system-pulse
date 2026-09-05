# System Pulse live Linux workspace

System Pulse displays real Linux host snapshots in independently docked monitor panels. CPU, memory, discovered GPUs, volumes, network interfaces, and processes use physical quantities and stable identities. Unavailable or failed sources retain truthful status; simulated readings are confined to tests.

From the fork workspace root:

```sh
rtk proxy cargo run --locked -p system-pulse
rtk proxy cargo test --locked -p system-pulse --lib
rtk proxy python3 -B scripts/system-pulse/verify.py
```

The mandatory verifier builds and checks the affected packages, exercises independent proc/sysfs arithmetic and counter brackets, and replays native interactions in a private Xvfb/DBus session. It writes complete logs and fresh host/native evidence outside the checkout. Missing steps or counter brackets fail the aggregate. See [acceptance implementation status](../../docs/execution/real-system-readings/acceptance-implementation.md); a passing aggregate has not yet been earned.

`SYSTEM_PULSE_STATE_DIR` selects an isolated configuration directory. `SYSTEM_PULSE_DIAGNOSTICS_PATH` optionally exports the accepted live snapshot and rendered entries for acceptance inspection. Process arguments and environments are not collected. The process table uses PID and start ticks together, so an exited identity cannot silently become a reused PID.

Drag a panel title to an edge to split it. Panel and sensor disclosure controls respond to Return and Space and retain independent choices. Compact values continue updating; bounded histories continue while hidden or collapsed. Compatible meters retain physical units and scales. Alt+PageUp/PageDown scrolls the workspace vertically and Alt+Left/Right horizontally. The process table uses Up/Down/Home/End and Left/Right; Tab leaves it.

Configuration saves preserve panel choices and dock layout. One preset slot supports Save preset and Recall preset. Invalid layout bytes remain untouched through ordinary interactions until explicit Accept recovered layout archives them and writes a valid replacement. Final styling, process operations, full preset CRUD, and packaging are outside this collection commitment.

Linux is the primary validation platform. NVIDIA adapter tests do not establish hardware accuracy without an actual GPU comparison; DriverNotLoaded is not an accuracy pass. macOS, Windows, and physical device removal remain unverified where unavailable. The [historical fixture acceptance](NATIVE_ACCEPTANCE.md) records the earlier deterministic interaction proof and does not establish live-reading accuracy.
