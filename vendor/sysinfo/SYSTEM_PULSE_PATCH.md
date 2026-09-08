# System Pulse patch to sysinfo 0.37.2

Upstream: <https://github.com/GuillaumeGomez/sysinfo>

Registry release: sysinfo 0.37.2, crate SHA-256
`16607d5caffd1c07ce073528f9ed972d88db15dd44023fa57142963be3feb11f`.
Upstream revision: `067dd61372205880dda017c942fec0042421e45e`.
The original MIT license and copyright notices are retained in `LICENSE`.

Local changes:

- `src/unix/apple/macos/process.rs`: skip KERN_PROCARGS2 for a retained process
  name when none of the requested executable, command or environment fields
  needs updating. Other refresh stages and failure paths remain upstream code.
- `src/unix/apple/macos/process_refresh_tests.rs`: native regression tests for
  refresh flags, missing metadata, retained counters, replacement identity,
  same-PID exec and owned-process exit.
- `Cargo.toml`: an empty workspace declaration permits independent upstream
  test runs from the vendored package. Dependency versions are unchanged.

On macOS, run the focused tests with:

```sh
cargo test --manifest-path vendor/sysinfo/Cargo.toml --locked --lib process_argument_refresh_tests
```

The application resolves this package through the root Cargo patch and lockfile.
Its release continues to use the application's dependency graph; the standalone
upstream test command uses the retained upstream Cargo.lock.

Approved scope and evidence:
`docs/execution/macos-performance/process-refresh-proposal.md` and
`docs/decisions/skip-unrequested-mac-process-arguments-in-retained-sysinfo-entries.md`.
