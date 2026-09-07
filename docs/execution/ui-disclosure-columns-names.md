# Sensor disclosure, process columns and monitor names

The developer reported ineffective RAM-row collapse, oversized/misaligned process columns, and opaque GPU/network names on 2026-09-07.

Code commit `04fbb14e57a8d04f8aec37fc1f8fae368b1cbd6e` fixes these three issues:

- Number-row clicks already changed state, but there was no separate visible body to fold. Expanded rows now show a larger value below the retained compact summary. Sensor labels align to the left.
- Process columns previously started at 1,745 pixels and grew without a limit to display entire error messages. Their widths are now bounded, headings share the cells' padding and alignment, and tooltips retain full text. Numeric values align to the right. Existing accessibility labels retain complete failure reasons.
- Linux AMD names use the driver product name or udev model metadata, with PCI locations distinguishing identical cards. Network labels use configured aliases or readable types and retain interface names. Stable monitor IDs and saved choices are unchanged.

## Verification

The initial regression tests reproduced invisible Number-row collapse, excessive column width, and the generic AMD label. After the fixes, all 87 application and 99 collector library tests passed. The rendered geometry regression checks all eight heading/data boundaries and retains its disappearing-process case. Formatting and Clippy for both packages and all targets passed with warnings denied. The debug build and `cargo install --path examples/system_pulse --locked --force` passed.

A private X11/DBus replay ran the installed release binary against real host readings at 1,200 pixels wide. Mouse collapse moved the following RAM row upward by 49 pixels; expansion restored its position. All eight columns aligned and the last ended at x=1,089. The two GPUs appeared as Radeon AI PRO R9700 with distinct PCI locations. Expanded/collapsed rows, the process table, and a complete permission-error tooltip were visually inspected.

Evidence is retained at `/home/shawn/workspace2/task-manager-artifacts/ui-row-columns-20260907/`: `verification.json`, `install.json`, and `replay-final/` contain the results, native journal, binary hashes and screenshots. The running replay binary matched the installed binary and release artifact by SHA-256. The user configuration was not modified by the isolated replay. Existing application windows need a restart to load the installed update.

Production self-audit: reviewed all fourteen rules against the changed paths, identity/persistence boundaries, failure fallbacks, width bounds, tests and native behavior. No further revision was identified for these reported issues. This focused verification does not replace the full product acceptance mechanism or claim outstanding platform/GPU acceptance complete.
