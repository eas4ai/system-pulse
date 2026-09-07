# Usable Linux application checkpoint

The Linux product acceptance passed on 2026-09-07 against committed source `e5838365931efb6b07ecf412a433c34302ee5c26`. This is the scoped Linux handoff allowed by [the commitment](../commitments/finish-application.md). Intel/Apple hardware acceptance and Mac F1 remain open; the complete cross-platform commitment is not Done.

## Deliverable

Package: `system-pulse-0.1.0-linux-x86_64-e5838365931e.tar.gz` (25,426,484 bytes).

The package is in `/home/shawn/workspace2/task-manager-artifacts/finish-application/final-acceptance-inventory-repeat-20260907/evidence/package/`. Its adjacent extracted directory contains the runnable `system-pulse` executable. Extract the archive and run `./system-pulse`, or follow the included README and run `python3 install.py` for user-local installation. The [package guide](../../examples/system_pulse/package/README.md) records runtime requirements, configuration paths, removal and update instructions. This build targets Ubuntu 26.04 x86-64 with glibc 2.43; it is not a portable static Linux binary.

| Artifact | SHA-256 |
| --- | --- |
| Package archive | `e779c1662145ec43c418512b40c59c361f7c6168aaaf642b063c9b8d82579479` |
| Packaged and installed executable | `0e4552e761839ab2056381036f78f450076c6c30cfbfadb569e7ab68deecc328` |
| Application acceptance manifest | `5ab8567fe740963c997494bf3273908b4170b60e7ebd4028c417f139a6865826` |
| Preservation manifest | `aa0c34f814f6bde780f06dc010685850240e56e420584d720c17a73ffb976334` |

## Verification

The actual committed mechanism was `cairn check APP-001`, with `SYSTEM_PULSE_APPLICATION_OUTPUT` set to the evidence directory above and `SYSTEM_PULSE_CARGO_ABOUT` set to the task-owned cargo-about 0.9.2 executable. The external supervisor retained stdout/stderr and reaped descendants. All five application acceptance steps exited zero without timeout:

- Preservation: 922 tests, source guard, formatting, strict Clippy, build, independent host comparisons and all fourteen native cases.
- Input focus: ten additional component tests, for **932 automated tests total**.
- Packaging: release executable, 540 dependency notices, embedded fonts, installer and committed source archive.
- Packaged application: process name/PID search, physical sorting and identity selection; context cancellation, SIGTERM/SIGKILL on owned children and protected-process errors; sensor/monitor context controls; themes, both font roles, intervals and named preset operations; normal shutdown and restoration.
- Installed application: archive extraction, installation and repeat, parsed desktop launcher, launch from an empty working directory, minimum window, light theme/bundled fonts, restart and normal shutdown, then removal preserving configuration and unowned files.

The 922 preservation tests comprise Python 465, base dock 206, resizable 13, component dock 19, model 32, application 86, collectors 99 and AT-SPI 2. Native preservation took 232.605 seconds. The packaged product replay took 46.2 seconds and installed smoke took 8.43 seconds. Freshness predicates and original deadlines remained unchanged; no publication timing instrumentation or focused preparation was enabled.

Cairn recorded passing evidence for APP-001 through APP-008 and LIVE-001 through LIVE-013. Its enclosing CLI exited 1 because the then-present `.cairn/in-progress` marker required reconciliation after recording the passes. This was not an acceptance-step failure: `application-manifest.json` and all five step exit statuses are PASS/zero. The marker was removed and the next wake named GPU-001, for which native evidence remains absent.

Root verified all 154 preservation artifacts, stage-log hashes, 66 copied harness files, 14 package-manifest files and all 15 archive files. The source archive's commit header matches and all 2,671 archived Git blobs match the committed tree. Packaged and installed process-executable hashes agree with the build manifest. All 57 recorded supervisor/descendant PIDs were absent after cleanup; the owner retained no children. See `root-verification.json` and `source-archive-verification.json` beside the evidence directory.

The previous focus-growth and complete-tree inventory failures remain retained. The focus defect has a failing-then-passing regression. The inventory deadline did not reproduce in the isolated unchanged probe or this full repeat; its original event ordering remains unproven. No failed artifact was overwritten or relabeled.

## Direct final review

This review was performed by the implementing agent. It is not an independent or final GPU commitment review. [Recorded findings](finish-application-review-findings.md) cover the live network preset mismatch, inherited session-output pipes and dynamic focused-control width. Their source corrections and affected regressions passed, followed by the complete current aggregate.

The direct source review examined numeric process projection, PID/start identity and pidfd signaling, protected targets, confirmation and visible failure paths, preset validation/durable publication, corrupted-input preservation, first-launch initialization, physical memory composition, theme/font application, focus scrolling and installer path/overwrite/removal handling. No open Linux source finding remains.

Visual review inspected the actual packaged first-launch, protected-process error and preset captures, plus installed minimum-window and light-theme captures. CPU, memory, GPU and processes remain separate and readable; the minimum window retains scrolling for the larger saved dock canvas. Selected controls, physical values and error text are readable in both themes. These captures are under `evidence/application/native/` and `evidence/installed/native/`; no screenshot is presented as a substitute for interaction tests.

## Production self-audit

| Rule | Review result |
| --- | --- |
| 1. Understand before editing | Original product scope, APP/LIVE/GPU contracts and retained workspace paths governed the changes. |
| 2. Smallest coherent change | Features stay in the existing GPUI app; fixes address demonstrated failures. |
| 3. Maintainability | Process projection/control, settings, presets, layout, package and replay responsibilities remain separate. |
| 4. Boundary contracts | Physical values, stable identities, compatible meters, validated presets and backward-compatible saved state are preserved. |
| 5. Errors and secrets | Denied/protected/exited actions and rejected configuration stay visible; no process arguments or environments are collected. |
| 6. Security | Process handles bind targets; actions require confirmation; installer validates paths and refuses unrelated overwrites. |
| 7. Survivable state | Durable writes, legacy import, rejected originals, repeat installation and configuration-preserving removal are covered. |
| 8. Reliability | Collection and actions run off the UI thread; histories/work remain bounded; owned test processes are reaped. |
| 9. Todo tracking | Linux implementation and verification are complete; exactly one item remains active for retained hardware/Mac obligations. |
| 10. Verification | Actual source, native, packaged and installed checks passed; unavailable hardware is identified below. |
| 11. Honest reporting | Earlier failures, the enclosing Cairn exit reason and the scoped handoff are explicit. No full commitment completion is claimed. |
| 12. Partnership | The usable Linux checkpoint follows the requested finish-the-app direction and the agreed commitment. |
| 13. Release self-audit | No further revision is required for this tested Linux checkpoint; hardware acceptance remains a separate open gate. |
| 14. Plain English | Package usage, errors, evidence and remaining limits use the project's monitor/sensor/meter/preset terms. |

## Remaining scope

Intel integrated/discrete and Apple native evidence, Mac F1 autorelease-pool proof/review, GPU aggregate receipts and final GPU review remain required. NVIDIA hardware accuracy, other native platforms and physical device removal retain their earlier limits. No merge, push, deployment or public release was performed.
