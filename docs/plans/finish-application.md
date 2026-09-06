# Finish the application

Goal: complete the remaining original product behavior in the existing Rust/GPUI application and produce a usable Linux package.

Implement directly in this worktree. Keep changes in feature-sized commits, run affected tests once per meaningful change, and reuse existing successful evidence until a source change or new failure makes it stale. Existing GPU reviews stay valid within their recorded source scope; missing native hardware remains unverified.

## Todo

- [x] Inspect the product specification and current source; verify the remaining feature gaps against the implementation.
- [ ] **In progress:** process search/sort, pointer selection and identity-bound End task/Force quit with confirmation and visible errors.
- [ ] Docked settings, bundled fonts and dark/light appearance with durable state.
- [ ] Named preset CRUD, protected built-ins and legacy single-preset import.
- [ ] Context menus for monitor/sensor visibility, ordering and explicit compatible meter selection.
- [ ] Balanced first-launch layout, CPU core view and memory composition using existing physical readings.
- [ ] Linux package, launcher, icon, installation/removal instructions and isolated packaged launch.
- [ ] Full application/native acceptance, unchanged Linux preservation and final review. Retain the separate missing Intel/Mac evidence and Mac F1 obligations.

Exactly one todo is active. A feature is checked only after its implementation and affected verification pass. GPU Task 5 is pending within this last item, not a second concurrent implementation task.

## Implementation boundaries and checks

1. Process projection belongs in `examples/system_pulse/src/processes.rs`; it uses raw `ProcessRow` numeric values, never formatted strings. Keep stable PID/start identity through filter/sort and snapshots. Add focused projection tests for numeric ordering, unavailable values, case-insensitive search and selected identity. Integrate the existing virtual list in `panel.rs` with a real input, focusable headers, pointer selection and native context menu. Keep the reviewed deferred identity reveal.
2. Process operations belong in `examples/system_pulse/collectors/src/process_control.rs`, separate from sampling. Linux acquires a pidfd, verifies the process start identity against procfs and signals that handle. Block PID 0/1 and this application. Unsupported platforms fail explicitly. A single background task executes an explicitly confirmed operation; tests use only spawned children and prove wrong identity/cancellation never sends a signal. Preserve permission and process-exit errors.
3. Appearance and named preset data belong in the model (`settings.rs`, `presets.rs`) and existing `Workspace` serialization with backward-compatible defaults. Use bounded, validated preset names and a separate atomic preset-library file; preserve unreadable/corrupt originals. Existing single `preset.json` imports as a named legacy preset without deleting it. Presets capture the whole workspace, and built-ins are templates resolved against current hardware.
4. Build a `SettingsPanel` view under `src/settings.rs` inside the existing monitor dock identity. Use existing gpui-component inputs, buttons, menus and theme tokens. UI/mono font roles use embedded licensed assets with at least two curated choices per role. Theme and interval changes apply immediately and save through existing debounced persistence.
5. Keep context actions and sensor ordering attached to stable IDs. Add model operations for moving a sensor and selecting a compatible meter; retain hidden/collapsed states. Use existing native context-menu components, clear action labels and keyboard-accessible controls.
6. A `layout.rs` module builds Default, Minimal, GPU Focus and Developer dock templates. First-launch defaults only apply when no saved workspace exists. CPU/Memory/Processes are primary; first GPU joins when discovered. Disk/network start hidden. Existing saved dock JSON always wins. Render the actual per-core percentage sensors as a compact grid and actual memory composition operands as a labeled composition bar; retain unavailable states.
7. Package the release binary, licenses and desktop integration under a task-owned output directory outside the checkout. Installer defaults to the user's local prefix, never touches saved state, and supports an isolated test prefix. Embed assets so launch does not depend on the checkout. Verify fresh state, normal shutdown, missing input and configuration preservation.
8. Run affected model/collector/app tests, formatting and strict Clippy during each feature. Extend existing Python native replay for search, sort, safe task-owned process actions, context menus, settings, presets and restart. Retain an actual failing case before implementing each nontrivial behavior. Run the final committed aggregate once after all features and source review; preserve failures and fix demonstrated causes. Do not weaken native freshness, identity or physical-value checks.

## Current evidence and limits

The starting tree passed [870 tests and full Linux preservation](../execution/intel-and-apple-gpus/linux-preservation-pass.md). The product gaps are directly visible in `src/panel.rs` (static process headers and Settings placeholder), `src/workspace.rs` (one preset slot and all-monitor vertical default), and `model/src/presentation.rs` (no appearance or named presets). Paths are relative to `examples/system_pulse/` unless fully qualified above. Source edits will make relevant prior acceptance stale and require the final replay.
