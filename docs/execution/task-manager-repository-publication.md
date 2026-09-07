# Task-manager repository publication

The developer instructed on 2026-09-07 that the application belongs in `/home/shawn/workspace2/task-manager` and must have its own repository, not be published into the GPUI framework fork.

Merge `0ff9ae139e39bdd73fb6ef556795ee4fbac0a02f` combines the existing task-manager project history with verified application branch commit `5e23977e350d99a2796151c091ad4bcb7c647bda`. The merge required no application source or lockfile changes. The newer framework-origin dependency migration was not imported. Its trial merge was aborted in a separate worktree, and the framework origin was not pushed.

The task-manager checkout now contains the application, its local framework crates, native patches, tests, packaging scripts and existing design/specification records. The root Cargo workspace defaults to System Pulse, so `cargo run --locked` starts the application. Root documentation and agent guidance now describe this repository. The existing task-manager ignore patterns, including `reference/`, are preserved. Original local agent/ignore files are backed up under the external publication evidence directory.

## Verification

- Cargo metadata resolves `/home/shawn/workspace2/task-manager` as the workspace root, its `target/` as the build directory and `system-pulse` as the only default package.
- All application, framework, native adapter and verification source files, `.cargo/` and `Cargo.lock` match the verified application branch byte for byte.
- `cargo test --locked -p system-pulse --lib` passed all 86 tests from the correct repository root.
- `cargo build --locked` passed from that root and produced `target/debug/system-pulse`.
- The root README and relocated active specification links were checked. Historical evidence retains the original source commit and paths.

The earlier [full Linux checkpoint](linux-application-checkpoint.md) remains evidence for its named source: 932 tests, fourteen native cases and packaged/installed flows. This publication performs the root build and application tests above; it does not claim a new full native run or close missing Intel/Apple/Mac verification.

Publication evidence and the task checklist are retained at `/home/shawn/workspace2/task-manager-artifacts/finish-application/github-merge-20260907`. The new GitHub origin is the standalone `eas4ai/task-manager` repository.

Production self-audit: reviewed the move against all fourteen rules. The merge preserves both histories, runtime code, dependencies, licenses, local reference material and untracked design files. The documented root commands ran and passed. Source review is limited to repository configuration/documentation because runtime code is unchanged. No remaining issue blocks this repository placement and publication; existing hardware limits remain explicit.
