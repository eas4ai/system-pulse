# Preserve native linker flags and enforce warnings in the explicit lint gate

Level: Judged
Decided by: Codex
Rests on: REL-003
Would be wrong if: The hosted lint step stops rejecting application warnings, a test failure is ignored, or native linker flags are still overridden.

## Decision

The pinned setup-rust-toolchain action defaults to RUSTFLAGS=-D warnings. Hosted run 34436597213 failed on existing vendored macOS sysinfo deprecation and unnecessary-unsafe warnings. That environment variable also overrides .cargo/config.toml, including the Windows 8000000-byte stack and Linux linker configuration. Set the action rustflags input to an empty string so Cargo retains repository target flags. Keep the explicit cargo clippy invocation for the application, collectors and model with --all-targets -- -D warnings, and retain normal failing exit behavior for every test, build and packaging command. Vendored dependency warnings remain visible in logs. Do not migrate unrelated vendor APIs merely to configure CI.

## Realized by

- fc324e874c7ad6a803de7f50e4e38b3ce3e0be64 ci: preserve native linker configuration during toolchain setup
