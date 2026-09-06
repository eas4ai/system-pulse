# Resolve pending process reveals by identity at list layout

Level: Judged
Decided by: agent
Rests on: GPU-007 preserves stable process selection and scrolling; independent Task 5 source investigation recorded the deferred numeric-index race before correction.
Would be wrong if: The executable interleaving does not reproduce the mismatch, or the correction scrolls passive snapshots, transfers selection, or weakens native acceptance guards.

## Decision

First reproduce the recorded race in docs/execution/intel-and-apple-gpus/linux-pending-process-reveal-finding.md using real snapshot acceptance, keyboard actions and list layout. Retain an observed failing regression before production changes. If confirmed, keep a pending keyboard reveal intent in MonitorPanel and resolve its stable selected process identity to the current row index immediately before list layout, consuming that intent once. Passive snapshots must not create reveal intent; vanished selection must not scroll to a replacement. Preserve coalesced repaint, horizontal navigation, manual scrolling, existing selection reconciliation and native freshness/recovery bounds. Keep the correction application-local unless an evidenced API limitation requires a separate decision. One implementer, then independent specification and fresh quality review. The original Linux freshness failures, Mac native proof and missing Intel hardware remain open; this source correction does not claim their cause or acceptance.

## Realized by

3ab14ff0bcd9a612a60477b397252bee48b2a48d fix: resolve pending process reveals against current rows
