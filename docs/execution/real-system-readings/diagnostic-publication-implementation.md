# Diagnostic publication implementation

The [recorded decision](../../decisions/publish-transient-diagnostics-without-a-durability-flush.md)
separates transient diagnostic publication from the durability flush used by
workspace and preset saves. `Storage::write_diagnostic` selects the private
`Durability::Transient` policy; `Storage::write` selects `Durability::Durable`.
The existing atomic writer skips only `File::sync_all` for transient records.
It still writes the complete temporary file before renaming, holds the revision
lock across replacement, updates the saved revision only after success, and
retains replacement error reporting and temporary-file cleanup.

Configuration byte limits and the diagnostic worker's latest-only slot,
serialization and error channel are unchanged. No runtime readings were added.

## Work tracking

- Complete: added regression tests and verified the current flush dependency.
- Complete: implemented the narrow policy change and verified application/model tests,
  scoped formatting, Clippy and the application binary build.
- Complete: self-audited the implementation and prepared the review handoff.
- In progress: independent spec then quality review (root orchestration).
- Pending: fresh untraced acceptance and final commitment review.

## Regression evidence

Three storage tests exercise both save entrypoints, replacement of longer JSON
with a shorter complete record followed by a rejected stale revision, and a
failed diagnostic replacement that preserves the target, removes the temporary
file and permits a lower-revision retry. Existing tests cover bounded
configuration saves, complete latest worker JSON, oversized diagnostics and
worker error reporting.

The flush assertion uses Linux syscall observation of the public storage
entrypoints. The Rust policy test alone checks file outcomes; the trace is
required to distinguish the flush policies. Before changing production code,
the eight storage tests passed, but the trace assertion failed as intended:
workspace, preset and diagnostic paths each invoked `fsync` once. After the
change, workspace and preset paths still invoked `fsync` once each, diagnostics
invoked neither `fsync` nor `fdatasync`, and all three paths successfully renamed
their complete temporary files.

The prebuilt test executable was run with this command, using `before` or
`after` in the trace filename at the corresponding source state:

```sh
rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp strace -f -y -e trace=fsync,fdatasync,rename,renameat,renameat2 -o /home/shawn/workspace2/task-manager-artifacts/diagnostic-publication-after.strace target/debug/deps/system_pulse-c4820b7895b5fc38 --exact storage::tests::diagnostic_publication_and_configuration_saves_use_distinct_flush_policies --test-threads=1
```

The assertion run against each trace (the `before` run exited 1; `after` exited 0):

```sh
rtk proxy python3 - <<'PY'
from pathlib import Path
trace = Path('/home/shawn/workspace2/task-manager-artifacts/diagnostic-publication-after.strace').read_text()
lines = [line for line in trace.splitlines() if 'pulse-flush-policy-' in line]
counts = {name: sum(('fsync(' in line or 'fdatasync(' in line) and f'/{name}.' in line for line in lines) for name in ('workspace', 'preset', 'latest')}
assert counts == {'workspace': 1, 'preset': 1, 'latest': 0}
for name in counts:
    assert sum('rename(' in line and f'/{name}.json"' in line and line.endswith('= 0') for line in lines) == 1
PY
```

The `before` run used the count assertion and stopped there on the expected
failure. The successful `after` run also asserted the three renames above.
The executable suffix is build-specific. Neither trace captures write payloads.
Retained traces live in `/home/shawn/workspace2/task-manager-artifacts/`:

| File | SHA-256 |
| --- | --- |
| `diagnostic-publication-before.strace` | `50764a274148b6a807bacc07a33709a7fde148cab981007643922529fa36926c` |
| `diagnostic-publication-after.strace` | `2e032f19928f3431cceebd6ca4f72a910b300796f78f5ce3ce64e1b326097080` |

## Verification and limits

All Cargo commands below used
`rtk proxy env TMPDIR=/home/shawn/workspace2/task-manager-artifacts/tmp`
as their prefix. The adopted `.cargo/config.toml` lld configuration was retained.

| Command | Result |
| --- | --- |
| `cargo test -p system-pulse --lib storage::tests --no-fail-fast` | 8 passed before and after the change |
| `cargo test -p system-pulse --lib diagnostics::tests --no-fail-fast` | 3 passed |
| `cargo test -p system-pulse -p system-pulse-model` | 48 app tests and 24 model integration tests passed; remaining selected targets had no tests |
| `cargo clippy -p system-pulse -p system-pulse-model --all-targets --no-deps -- -D warnings` | Passed |
| `cargo build -p system-pulse --bin system-pulse` | Passed |
| `rustfmt --edition 2024 --check examples/system_pulse/src/storage.rs` | Passed using the same prefix |

The built `target/debug/system-pulse` SHA-256 is
`082b7b541f55a98014805d30af5725f528e4fc0af540857f649021a8e84d9f83`.
The self-audit checked the production rules, preservation of persistence and
worker contracts, test evidence, scope, and documentation. No implementation
revision remained necessary; independent review remains a separate gate.

These are development checks, not Cairn acceptance evidence. Syscall policy
observation is Linux-only. Native acceptance has not run for this change.
Independent spec then quality review and fresh untraced acceptance remain
required. The earlier syscall stall remains unidentified; the diagnostic trace
did not reproduce it. This change removes a known unnecessary flush dependency
and makes no claim that it resolves the original freshness failure.
