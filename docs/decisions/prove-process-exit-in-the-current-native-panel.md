# Prove process exit in the current native panel

Level: Judged
Decided by: agent
Rests on: LIVE-003 requires actual native child disappearance. A deterministic reviewer probe acknowledged a detached empty cached panel while the current panel retained the target.
Would be wrong if: The correction accepts detached or ambiguous panels, loses strict traversal or snapshot prerequisites, extends the five-second deadline, or treats invisible rows as observed model state.
History: The earlier navigation decision was reversed because virtualized native absence was overstated as model-clear evidence. This raises scrutiny of this same proof boundary: the new decision explicitly distinguishes complete current visible-tree evidence from model state and requires an actual detached-cache falsifier before correction. The level remains Judged because this bounded verifier correction preserves the agreed requirement, product behavior and deadlines and reuses reviewed membership code; it does not alter the developer contract.

## Decision

Independent review reproduced false exit acknowledgement at 0.5 seconds with a live detached empty cached Processes panel while the current replacement panel still contained the exact child. Replace the exit proof cache shortcut with navigation_panel(deadline) on each proof attempt. Traverse that unique current panel with existing strict cell-pruned scanning, record target presence without early return, reject any other instantiated selected process identity, and validate navigation_panel_current(path, deadline) after the scan before success. Preserve the fresh newer child-free snapshot prerequisite and the same original five-second absolute deadline. Reuse established ancestry/application registration helpers. Add detached-cache, replacement-during-scan, duplicate-current-panel and incomplete-membership regressions. This is a verifier correction, not a product or requirement change. Preserve failed evidence and pass focused/full tests, independent SPEC then QUALITY review, and fresh actual acceptance.

## Realized by

- 1790fe53506439b8c897421aa91be15598586162 test(system-pulse): prove selection clearing and current native exit
