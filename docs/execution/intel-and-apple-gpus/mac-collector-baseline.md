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
