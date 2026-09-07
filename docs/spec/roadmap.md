# System Pulse roadmap

> Current UI direction (2026-09-07): [reference-based tabbed screens](../superpowers/specs/2026-09-07-tabbed-screens-design.md). The earlier dock layout below is historical.
Status: Agreed 2026-09-04. Not normative.

Current: finish-application

## Real system readings

The developer confirmed LIVE-001 through LIVE-013 and their falsifiers on 2026-09-04. Replace runtime simulation with host collection, physical meter semantics, real process snapshots, stable identities, and native host verification while preserving the completed workspace behavior. [Commitment](../commitments/real-system-readings.md).

The historical READ/VIEW/STATE observations remain records of the starting point, not requirements to keep fixture behavior. Remaining product areas are listed in the [overview](overview.md); this commitment does not claim them complete.

Completed 2026-09-06: [passing acceptance, final review and Cairn Done](../execution/real-system-readings/completion.md). The developer confirmed the next commitment below on 2026-09-06.

## Intel and Apple GPU support

The developer confirmed GPU-001 through GPU-009 and their falsifiers on 2026-09-06. Add Intel integrated/discrete Linux and Apple Silicon collectors with accurate memory scope, independent adapter reviews and native evidence. [Contract](gpu-collection.md), [commitment](../commitments/intel-and-apple-gpus.md), [acceptance plan](../plans/intel-and-apple-gpu-acceptance.md).

Intel Windows support follows separately; a tablet is available for future validation. Intel Linux access and a discrete Intel test device remain to be established.

## Finish the application

The developer asked to finish the application on 2026-09-06. Complete the remaining original product features and a usable Linux package under [finish-application](../commitments/finish-application.md). The GPU work remains incomplete and its requirements remain included; this change of active work does not claim hardware acceptance or change the pending platform-priority decision.
