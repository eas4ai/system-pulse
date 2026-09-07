# System Pulse

A native desktop system monitor built with Rust and GPUI. This repository contains the application and the local framework components it uses.

System Pulse provides live CPU, memory, GPU, disk, network and process readings in separate dockable panels. It includes process search and sorting, confirmed task actions, configurable sensor meters, named presets, bundled fonts, dark/light themes and persistent layouts.

## Run

From this repository root:

```sh
cargo run --locked
```

Build an optimized executable with `cargo build --release --locked -p system-pulse`. The executable is `target/release/system-pulse`.

Application source is in [examples/system_pulse](examples/system_pulse/). The model and collectors are separate crates beneath that directory. [Application documentation](examples/system_pulse/README.md) describes controls, configuration and diagnostics; the [package guide](examples/system_pulse/package/README.md) covers installation and removal.

Linux is the verified platform. The [Linux checkpoint](docs/execution/linux-application-checkpoint.md) records 932 passing tests, fourteen native preservation cases and packaged/installed verification against its named source commit. Intel/Apple native hardware validation and the Mac F1 review remain open.

## Verify

```sh
cargo test --locked -p system-pulse
python3 -B scripts/system-pulse/application_acceptance.py
```

The full acceptance command requires the native Linux tools and pinned cargo-about generator described in the [application guide](examples/system_pulse/README.md). It runs against a committed tree and writes evidence outside the checkout. The repository relocation is documented in [the publication record](docs/execution/task-manager-repository-publication.md).

## Project records

Start with the [product specification](docs/feature-spec-dockable-system-monitor.md), [current roadmap](docs/spec/roadmap.md) and [execution plan](docs/plans/finish-application.md). Historical records retain their original worktree paths and source commits.

## Licenses

System Pulse is GPL-3.0-or-later; see [COPYING](COPYING) and the application crate manifests. The bundled GPUI framework retains its [Apache license](LICENSE-APACHE). Third-party code, fonts and native adapters retain their own notices and licenses. The package includes dependency notices and corresponding source.
