# Complete desktop application

Status: Agreed 2026-09-06
Prefix: APP

The developer asked to finish the application on 2026-09-06. These requirements make the remaining behavior in the original [product specification](../../../../task-manager/docs/feature-spec-dockable-system-monitor.md) executable. They preserve the existing LIVE and GPU contracts; no missing hardware is declared verified. Linux is the first usable build, consistent with the original development platform. Cross-platform and GPU verification obligations remain open until their evidence exists or the developer changes that release boundary.

[APP-001] The process table MUST support case-insensitive name, PID and user search and sorting by every displayed column using physical numeric values, with CPU descending as the default.
Falsifier: A numeric column sorts formatted text lexically, unavailable values outrank measured values, a search shows unrelated rows, or changing order selects a different process identity.
Mechanism: process projection unit tests, GPUI input/sort/selection tests and native search/sort replay.

[APP-002] The process table MUST offer End task and Force quit for the selected process, preserve its PID/start identity through confirmation and execution, and visibly report denied, exited or unsupported operations without requesting elevated privileges.
Falsifier: Cancel sends a signal, PID reuse targets a replacement process, the UI blocks on an operation, or an unsuccessful operation appears successful.
Mechanism: identity-bound process-operation tests with task-owned subprocesses, cancellation/error tests and native context-menu interaction.

[APP-003] The app MUST expose monitor visibility and sensor visibility, ordering and compatible meter selection through context controls while preserving separate dock panels, explicit collapse and saved choices.
Falsifier: An incompatible meter is selected, a reordered or hidden sensor loses its identity/state, or a context action prevents keyboard access to a panel.
Mechanism: model ordering/compatibility tests and GPUI/native context-menu and restoration replay.

[APP-004] The dockable Settings panel MUST apply and persist dark/light themes, curated bundled UI and numeric fonts, and the existing global sampling intervals immediately.
Falsifier: Settings require restart, a selected font is absent from the package, numeric values use the wrong font role, a theme leaves unreadable controls, or a saved choice is lost after restart.
Mechanism: settings serialization/default tests, embedded font checks and native appearance/restart inspection.

[APP-005] The app MUST save, overwrite, rename, delete and recall named user presets containing dock layout, monitor/sensor choices, collapse state, appearance and interval, alongside protected Default, Minimal, GPU Focus and Developer presets.
Falsifier: A preset operation corrupts another preset, deletes a built-in, silently overwrites an existing name, loses appearance/collapse state or bypasses rejected-configuration preservation.
Mechanism: preset CRUD/validation/legacy import/atomic persistence tests and native preset replay.

[APP-006] First launch MUST show a readable balanced CPU/GPU/Memory/Processes layout with live hero readings, a per-core CPU view and physical memory composition, while leaving disk/network monitors available to add.
Falsifier: First launch shows a placeholder or fabricated reading, misses an available primary monitor, forces a tab group, hides panels during resize, or loses existing saved layout choices by applying defaults on restart.
Mechanism: layout/default tests, physical composition tests and native first-launch and minimum-window captures.

[APP-007] The Linux deliverable MUST include a runnable application, desktop launcher/icon, bundled assets and license notices, installation/removal instructions and an installable package that preserves user configuration.
Falsifier: The packaged app depends on a source-checkout asset path, installation requires root, removal deletes saved state, or a fresh isolated launch cannot render its controls and readings.
Mechanism: package contents/license checks, isolated installation and launch/shutdown smoke test.

[APP-008] Application completion MUST retain the complete existing Linux preservation checks and verify the new user flows against committed source before a release claim.
Falsifier: A missing test, failed native flow or unperformed package launch is counted as a pass, or a previous failed artifact is overwritten to manufacture success.
Mechanism: application acceptance plus unchanged LIVE acceptance, final review and explicit platform limits.
