# System Pulse patch to sysinfo 0.37.2

Upstream: <https://github.com/GuillaumeGomez/sysinfo>

Registry release: sysinfo 0.37.2, crate SHA-256
`16607d5caffd1c07ce073528f9ed972d88db15dd44023fa57142963be3feb11f`.
Upstream revision: `067dd61372205880dda017c942fec0042421e45e`.
The original MIT license and copyright notices are retained in `LICENSE`.

Local changes:

- `src/unix/apple/macos/process.rs`: skip KERN_PROCARGS2 for a retained process
  name when none of the requested executable, command or environment fields
  needs updating. Retain BSD birth-time microseconds and compare that precision
  when detecting PID reuse, so process actions can verify the selected identity.
- `src/unix/apple/macos/process_identity.rs`: read complete KERN_PROC_PID
  metadata when full BSD records are permission-denied, preserving root-process
  birth identity and credentials without elevating the collector. Native SDK
  accessor comparisons are in `tests/macos_process_identity.c`.
- `src/common/system.rs`: expose the retained macOS birth-time microseconds
  without an additional process query; the existing seconds API is unchanged.
- `src/windows/process.rs`: retain all 64 creation-time FILETIME bits from the
  existing native process query, including its limited-information handle fallback.
  `src/common/system.rs` exposes `start_time_filetime()` on Windows without an
  additional query. The existing seconds API is unchanged. System Pulse uses
  these full ticks for process-action identity, never the rounded seconds.
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
The process-identity extension is covered by PROC-004/PROC-005 and
`docs/decisions/authenticate-one-identity-bound-process-action-through-the-operating-system.md`.
The Windows extension is covered by WUAC-001 and
`docs/decisions/windows-process-action-identity-and-elevation.md`; its native
collector tests compare against independent GetProcessTimes observations and
reject a one-tick mismatch without changing the owned target.
