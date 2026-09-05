# Native viewport accessibility review

Source candidate: `217941e52595eea7ef35e15dbe12d68a1e0d6b95`.

## Finding and change

Root screenshot review rejected an earlier second-GPU visibility claim: its label was inside the window but hidden behind the toolbar. Native ancestors omitted the workspace clipping rectangle. Existing workspace, sensor-body, process-table and process-row containers now expose a semantic scroll-view role and stable native identities. Their geometry, children, focus handlers, scroll handles and repaint behavior remain unchanged. Readings and diagnostic schemas are unchanged.

The source regression first failed because the role was absent. All 45 app tests, focused strict Clippy, build and diff checks then passed. Root built the committed candidate with `cargo build --locked -p system-pulse`; its SHA matches the executable used for native-09: `e87f0f8c56481c9c298f03a262ff256eb8621dc6100e6a14238eee540306eeec`. This resolves the native metadata's older pre-commit HEAD.

## Independent reviews

**SPEC PASS** and **QUALITY PASS**, with no open source findings. Each reviewer independently ran the focused accessibility test: one passed. Quality also passed nine actual ancestor-containment assertions across four native metric records. Root inspected all four screenshots: CPU 17.1%, RAM 36.9 / 94.1 GiB and both actual AMD GPU headers are visible within the workspace. The second GPU label settled at y251, below the y250 viewport edge, within the original five-second deadline.

A source review identified suppressed prepaint refresh as a possible focus scheduling risk. The corrected native geometry check did not demonstrate a deadline failure, so no focus behavior change was made.

## Evidence limits

The Rust helper test verifies role and identity. Full verifier clipping regressions, narrow viewport and process-table cases remain part of Task 3 acceptance. Native-09 was a focused metrics run and has no normal-shutdown record; it does not prove full replay or clean window exit. Earlier clipped images and failed host captures remain failures.

[Artifact manifest](viewport-artifact-manifest.json) records 16 existing files and their SHA-256 hashes. Final LIVE acceptance remains pending.
