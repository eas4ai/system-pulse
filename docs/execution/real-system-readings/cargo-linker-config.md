# Linux linker configuration

The developer requested adoption of `/home/shawn/workspace2/suprnova/.cargo/config.toml` on 2026-09-05. The Rust worktree now selects LLVM lld for `x86_64-unknown-linux-gnu` with `-C link-arg=-fuse-ld=lld`. The existing Windows stack flag remains intact.

The machine's `CARGO_BUILD_RUSTFLAGS` supplies `-L /usr/local/lib/x86_64-linux-gnu`. Target-specific rustflags replace that setting, so the new Linux array retains the same library search path. `ld.lld` resolves through the swiftly installation and reports LLVM LLD 17.0.0. Other repository-specific Suprnova comments and its local-ignore policy were not copied.

The acceptance mechanism now declares `.cargo/config.toml` as an input so the linker change invalidates earlier build evidence. An isolated Cargo project using the exact resulting configuration built offline and its executable printed `lld smoke passed`. The verbose command confirmed both the lld and library-search flags. Artifacts: `/tmp/pulse-lld-config-27c1zl7m/build.log`.

The full System Pulse rebuild and acceptance run remain pending. No build-speed measurement is claimed.
