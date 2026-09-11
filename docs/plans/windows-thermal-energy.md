# Windows thermal and energy implementation plan

Use subagent-driven-development for the isolated EMI collector and specification/quality reviews.
Goal: real scoped energy/power and CPU temperatures with an unelevated dashboard.
Architecture: backend-neutral Windows EMI collector plus a fixed-protocol,
opt-in privileged temperature helper using the signed PawnIO IntelMSR module.
Stack: Rust, windows 0.58, existing model/counter types, PowerShell native replay,
Python acceptance, Windows installer and existing signing command.
Approved design: windows-thermal-energy-source-design.md.

- [x] Inspect sources and tablet capabilities; record approved access decision.
- [ ] In progress: implement sources and helper; verify conversion, identity, refresh, protocol and error boundaries.
- [ ] Build and inspect packaged Windows screens; compare independent readings and verify platform preservation.
- [ ] Commit acceptance evidence and complete the final Cairn review.

## Energy collector

Create crates/collectors/src/windows_energy.rs and windows_energy/native.rs with
tests. Integrate lib.rs and host/mod.rs; enable Win32_System_Power and
Win32_System_IO features. Reuse existing collector publication functions.

Enumerate present EMI interfaces with SetupAPI; own handles and bound all
buffers. Validate EMI V1/V2, units, UTF-16 name lengths, channel counts and
complete replies. Key readings by exact device/channel identity; reject
ambiguous duplicate names. Query errors remain explicit.

Derivation test: energy advances by 1_000_000_000 picowatt-hours and time by
10_000_000 ticks, yielding 3.6 watts:

    let watts = (new_energy - old_energy) as f64 * 0.036
        / (new_time - old_time) as f64;
    assert_eq!(watts, 3.6);

Validate progression before subtraction. Zero-only domains remain unavailable
until a nonzero counter establishes support. Never sum package and components.
Retain raw integers; reset on metadata changes, failure and removal. Test malformed
metadata, bad units, duplicate IDs, reset, failed inventory and recovery. Run
failing tests first, implement, then run:
    rtk cargo test --locked -p system-pulse-collectors windows_energy

## Temperature helper

Create a fixed sampling protocol and native PawnIO adapter under collectors,
with app entry handling before GPUI initialization. Reuse Windows process-helper
identity/elevation/lifetime primitives without changing process-action commands.
Authenticate caller/executable, bound output and stop when the caller exits.

The helper permits only these fixed reads:
    0x1a2 temperature target
    0x19c core thermal status
    0x1b1 package thermal status

No caller-controlled register, function or module paths. Validate CPU support,
thermal validity and target; retain raw operands, restore affinity and close
handles. Test short replies, missing driver, denied access, malformed requests,
caller mismatch, helper exit and stale readings; never replace errors with zero.
Verify actual unelevated dashboard plus authorized helper lifetime.

## Dependencies and packaging

Recheck the staged official PawnIO 2.2.0 hash/signature before the approved install.
Pin the official IntelMSR module and retain license/source provenance. Offer the
prerequisite through Windows installation. Use the existing Winboat signing
command and independently verify signatures. Keep signing secrets out of source
and logs. Start Winboat when needed for signing, then shut it down.

## Acceptance

Create scripts/system-pulse/windows_thermal_energy_verify.py and falsifier tests,
plus bounded native replay. Verify actual UI, source operands, helper consent/
denial/exit, stale/error states, package provenance and absence of writes. Run
Linux application/model/collector tests, native Windows tests/build and macOS
preservation. Commit source before cairn check WTE-001 and commit each receipt.
Review without code changes, record limits, finish only when Cairn reports Done.

## Current verification checkpoints

Native Windows thermal tests passed 23 cases at 1717121f, including actual pipe,
caller identity and stalled-operation watchdog termination. The Windows full app
checks and release build are still running. Linux preservation passed 326 tests
and Clippy at 8f640311. Mac preservation passed 282 tests and Clippy at the same
source; nine existing sysinfo warnings and the block future-compatibility notice
remain. These checkpoints do not replace final packaged sensor/UI acceptance.

The developer identified ~/Documents/certs/clipper on the MacBook as a signing
example. Its filenames include developerID_application.cer and
setup-audeeoz-notarization.command. No password content was read. Mac signing
has not been performed or claimed by these preservation checks.
