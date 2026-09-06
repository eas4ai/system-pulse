# macOS collector baseline

Observed 2026-09-06 on the authorized Apple M1 Pro, arm64, macOS 26.6.1.
The existing collector compiled and its selected tests passed before Apple
production implementation. This is a portability prerequisite, not GPU accuracy
or GUI acceptance.

## Committed input and command

Source: `d9d2be80f9bfb4205b9534eeabda3f89b6c12da7`
(`feat: collect Intel Linux GPU readings`). The transferred `git archive` was
24,412,160 bytes, with SHA-256
`41816c158899458e931fdd0154164c22f62fff5475e6962d870970877f7397c3`.
The remote process verified this hash before extraction into the task-owned
`/Users/shawnmcallister/system-pulse-gpu-validation-03rjwxl7/source` directory.

```sh
cargo test --locked -p system-pulse-collectors
```

Cargo/rustc version: 1.97.1. The command used four build jobs and a target directory
beside the extracted source. The launcher bounded execution to 1800 seconds and
tracked its own process group for timeout cleanup. The host had 167,958,536,192
bytes free before the build.

## Actual result

Exit code 0 after 150.164 seconds. The library passed 22 tests, the snapshot CLI
passed 1 test, and doc-tests selected 0 tests. The process exited normally.
The first build fetched locked workspace Git dependencies, including Zed.

`Cargo.lock` was unchanged; its SHA-256 before and after was
`81c0179aa49af0e221aa0700dc59491e17084bae1e0a8da3df157feac78c4ce0`.
The copied result and full log are retained in
`/home/shawn/workspace2/task-manager-artifacts/gpu-recon/`:

| Artifact | SHA-256 |
| --- | --- |
| `baseline-collector-test.json` | `310deb4741eab21a1cb1f3f172314fc56972995f9fa12a2f8ed11c51d3ec7258` |
| `baseline-collector-test.log` | `deba8584ace21f65f43cc48b395154cc0692c0c92283cc8a94339b17193e6bc6` |

The local result/log hash and successful exit were checked after transfer.
The dedicated source and target directories remain available for the Apple
collector build. No Apple production readings or native application interactions
were tested in this baseline.

## Application build and accessibility preflight

The same committed archive later passed:

```sh
cargo build --locked -p system-pulse --bin system-pulse
```

The two-job native build exited zero after 260.264 seconds. Free space afterward
was 164,250,566,656 bytes. The dependency lockfile remained unchanged. Cargo
reported a future-compatibility warning in the existing dependency `block 0.1.6`;
it did not fail this build.

| Artifact | SHA-256 |
| --- | --- |
| Native `target/debug/system-pulse` | `a71fc9c0d90437aa8821a28b4f04e625ff591cc0a68420703cbb6c25161dbf9f` |
| `baseline-app-build.json` | `1e237748ee90503d641e8dedba1a47f5b55486d1169b48d1d9c4f1f2d31e0992` |
| `baseline-app-build.log` | `78ec36aabd169bc2e1d3ec50fbe9666be569b73547a08b109e1016fd4f86c975` |

The binary launched with a dedicated `SYSTEM_PULSE_STATE_DIR`. A trusted native
accessibility client, restricted to the task-owned process ID, observed a main,
non-minimized `System Pulse` window. Its first tree contained eight window-shell
elements; a subsequent query populated application controls and authored
identifiers. A probe that required the whole tree failed its 1000-node bound.
The next probe explicitly retained a truncated 500-node prefix and observed
`Save`, the sampling-interval buttons, `Collapse Processes`, the real process
summary, and `workspace:viewport` / `processes:viewport` identifiers.

All three attempts are retained separately outside the checkout as
`baseline-ui*` reports, stdout and stderr, with their probe source files. PIDs
2013, 2038 and 2060 were each stopped by their own launcher using SIGTERM; all
were confirmed exited. These launches did not test application shutdown or
configuration restoration. The third probe's intentional truncation establishes
an observation path, not complete field coverage. No GPU labels, native
interactions, screen capture or GPU accuracy passed through this preflight.

The native verifier should wait for accessibility content after window creation
and select the required monitor subtree instead of traversing every process row.
It must also establish visibility/geometry and exercise the specified controls.
