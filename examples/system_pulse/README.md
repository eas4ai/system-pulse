# System Pulse

System Pulse displays real Linux host snapshots in independently docked monitor panels. CPU, memory, discovered GPUs, volumes, network interfaces, and processes use physical quantities and stable identities. Unavailable or failed sources retain truthful status; simulated readings are confined to tests.

From the fork workspace root:

```sh
rtk proxy cargo run --locked -p system-pulse
rtk proxy cargo test --locked -p system-pulse --lib
rtk proxy python3 -B scripts/system-pulse/verify.py
```

The mandatory verifier builds and checks the affected packages, exercises independent proc/sysfs arithmetic and counter brackets, and replays native interactions in a private Xvfb/DBus session. It writes complete logs and fresh host/native evidence outside the checkout. Missing steps or counter brackets fail the aggregate. See [acceptance implementation status](../../docs/execution/real-system-readings/acceptance-implementation.md) for recorded results and remaining verification.

`SYSTEM_PULSE_STATE_DIR` selects an isolated configuration directory. `SYSTEM_PULSE_DIAGNOSTICS_PATH` optionally exports the accepted live snapshot and rendered entries for acceptance inspection. Process arguments and environments are not collected. The process table uses PID and start ticks together, so an exited identity cannot silently become a reused PID.

Drag a panel title to an edge to split it. Panel and sensor disclosure controls respond to Return and Space and retain independent choices. Compact values continue updating; bounded histories continue while hidden or collapsed. Compatible meters retain physical units and scales. Alt+PageUp/PageDown scrolls the workspace vertically and Alt+Left/Right horizontally. The process table uses Up/Down/Home/End and Left/Right; Tab leaves it.

The process table searches name, PID and user and sorts every column using physical values. Select a row for identity-bound End task or Force quit with confirmation and visible errors. Linux uses a process handle and verifies its start identity before signaling; unsupported platforms report that explicitly.

Settings & presets opens a docked panel with dark/light themes, bundled interface/numeric fonts, sampling intervals and named preset creation, recall, rename, overwrite and removal. Built-in Default, Minimal, GPU Focus and Developer layouts resolve against discovered hardware. The top Save preset and Recall preset controls retain the legacy quick slot; existing `preset.json` also imports into the named library as Imported preset when that library is first created.

A fresh workspace shows balanced CPU/GPU and memory/process columns with physical core tiles and memory composition. Existing saved layouts retain their choices. Sensor ⋯ and context menus expose visibility, order and compatible meters. Configuration saves preserve panel choices, appearance and dock layout. Invalid layout bytes remain untouched until explicit Accept recovered layout archives them and writes a valid replacement.

See [Linux package instructions](package/README.md) for installation, removal, runtime requirements and the user guide. Build an archive from a committed tree with `python3 -B scripts/system-pulse/package_linux.py --output /outside/checkout/package-output --cargo-about /path/to/cargo-about`; it builds the release binary, gathers dependency notices, archives source and writes a checksummed installable package. The notice generator is cargo-about 0.9.2 (`cargo install cargo-about --version 0.9.2 --locked --features cli`).

Linux is the primary validation platform. NVIDIA adapter tests do not establish hardware accuracy without an actual GPU comparison; DriverNotLoaded is not an accuracy pass. macOS, Windows, and physical device removal remain unverified where unavailable. The [historical fixture acceptance](NATIVE_ACCEPTANCE.md) records the earlier deterministic interaction proof and does not establish live-reading accuracy.
