# Linux linker configuration

The developer requested adoption of `/home/shawn/workspace2/suprnova/.cargo/config.toml` on 2026-09-05. The Rust worktree now selects LLVM lld for `x86_64-unknown-linux-gnu` with `-C link-arg=-fuse-ld=lld`. The existing Windows stack flag remains intact.

The machine's `CARGO_BUILD_RUSTFLAGS` supplies `-L /usr/local/lib/x86_64-linux-gnu`. Target-specific rustflags replace that setting, so the new Linux array retains the same library search path. `ld.lld` resolves through the swiftly installation and reports LLVM LLD 17.0.0. Other repository-specific Suprnova comments and its local-ignore policy were not copied.

The acceptance mechanism now declares `.cargo/config.toml` as an input so the linker change invalidates earlier build evidence. An isolated Cargo project using the exact resulting configuration built offline and its executable printed `lld smoke passed`. The verbose command confirmed both the lld and library-search flags. Artifacts: `/tmp/pulse-lld-config-27c1zl7m/build.log`.

Both System Pulse binaries then built successfully with the locked dependency graph and the adopted configuration. Cargo reported 59.87 seconds; this is one build observation, not a speedup comparison. Source commit, command and binary hashes are retained in [the build record](cargo-linker-build.json). The committed aggregate at `098d2b2e` then passed all 481 tests, formatting, strict Clippy, both binary builds, and host verification with this configuration. Native acceptance stopped during process cell discovery; see [the failure record](native-cell-discovery-failure.md). Full commitment acceptance remains pending.
