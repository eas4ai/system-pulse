# System Pulse repository cleanup

Verified source: `3ccaf1afcb1cf67ea8d75509386d71941b98bdf8` (2026-09-07).

The application is the root Cargo package. Its source, assets, tests and package support are at `src/`, `assets/`, `tests/` and `package/`; its model and collectors are under `crates/`. Run `cargo run --locked` or install with `cargo install --path . --locked --force`.

Removed the inherited website, galleries, other example applications, shell and webview runtimes, framework skills, theme collection, framework documentation, funding configuration and framework release workflows. The dependency graph contains the application, model, collectors and four required GPUI library crates. Both native adapter patches and their licenses remain. Cargo pruned 279 unused packages without adding or upgrading a package.

Two retained library tests now own the Markdown and theme fixtures they previously loaded from deleted directories. The complete workspace tests also exposed a duration conversion error: scaling 100 ms through f32 seconds extended the deadline by one nanosecond. Transition and presence calculations now retain the exact duration at a factor of one; the existing completion tests pass without relaxed assertions.

## Verification

- `cargo fmt --all -- --check`: pass.
- `cargo test --locked --workspace`: 1,442 passed; two existing macro doctests ignored.
- Application, collector, model and gpui-base Clippy checks, all targets with warnings denied: pass.
- Complete Python verification and packaging unit suite: 465 passed. GPU provenance tests also passed after the final fixture relocation.
- Root debug build, release package build and `cargo install --path . --locked --force`: pass.
- Package generated notices for 540 dependencies and included corresponding source with the root application layout.
- Isolated package test: extraction, install/reinstall, desktop launcher, launch from an empty directory, minimum window, fonts/light theme, restart, shutdown and removal preserving configuration and unrelated files all passed.
- Installed native GPU check: unavailable instantaneous power row absent, available rows (including zero values) present, raw unavailable diagnostics and saved sensor visibility retained.

External logs, native screenshots, package and results are in `/home/shawn/workspace2/task-manager-artifacts/repository-cleanup-20260907/`. The installed and packaged executable SHA-256 is `6cd9328c2a2f0d4f6f3bf6182771595bec632304914857cf158dbac096a18470`.

This is Linux cleanup and package verification. It does not repeat the full live preservation/product replay or establish Intel/Apple hardware acceptance. Historical receipts retain the paths and revisions they tested. Remote CI is configured to run the application workspace checks; its configuration is not a completed remote run.
