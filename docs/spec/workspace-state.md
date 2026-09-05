# Workspace state as implemented

Status: Observed
Prefix: STATE

[STATE-001] The presentation model MUST store panel and sensor collapse independently from visibility and meter selection.
Falsifier: changing one choice silently resets another choice.
Mechanism: `cargo test --locked -p system-pulse-model --test presentation` and the native collapse/history regression.
Evidence: [state types](../../examples/system_pulse/model/src/presentation.rs:34), [tests](../../examples/system_pulse/model/tests/presentation.rs).

[STATE-002] Session MUST retain the original invalid workspace input when restoration falls back.
Falsifier: failed parsing or dock validation discards or alters the original input.
Mechanism: `cargo test --locked -p system-pulse-model --test persistence`; native invalid-input recovery replay.
Evidence: [Session::restore](../../examples/system_pulse/model/src/persistence.rs:18), [native record](../../examples/system_pulse/NATIVE_ACCEPTANCE.md:19).

[STATE-003] The current dock validator MUST reject monitor identities outside the fixture catalog.
Falsifier: a valid-shaped dock leaf with an unknown real device identity passes validation.
Mechanism: inspect `validate_dock`; LIVE-007 proposes replacing catalog-specific identity validation while retaining structural validation.
Evidence: [validator](../../examples/system_pulse/src/workspace.rs:94).

[STATE-004] The storage resolver MUST use the fixture configuration directory unless SYSTEM_PULSE_STATE_DIR overrides it.
Falsifier: a normal launch reads the intended live application's separate state location.
Mechanism: inspect `storage::directory`; LIVE-007 names the migration acceptance condition.
Evidence: [storage resolver](../../examples/system_pulse/src/storage.rs:12).
