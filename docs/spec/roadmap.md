# System Pulse roadmap

> Current UI direction (2026-09-07): [reference-based tabbed screens](../superpowers/specs/2026-09-07-tabbed-screens-design.md). The earlier dock layout below is historical.
Status: Agreed 2026-09-04. Not normative.

Current: process-table-improvements

## Real system readings

The developer confirmed LIVE-001 through LIVE-013 and their falsifiers on 2026-09-04. Replace runtime simulation with host collection, physical meter semantics, real process snapshots, stable identities, and native host verification while preserving the completed workspace behavior. [Commitment](../commitments/real-system-readings.md).

The historical READ/VIEW/STATE observations remain records of the starting point, not requirements to keep fixture behavior. Remaining product areas are listed in the [overview](overview.md); this commitment does not claim them complete.

Completed 2026-09-06: [passing acceptance, final review and Cairn Done](../execution/real-system-readings/completion.md). The developer confirmed the next commitment below on 2026-09-06.

## Intel and Apple GPU support

The developer confirmed GPU-001 through GPU-009 and their falsifiers on 2026-09-06. Add Intel integrated/discrete Linux and Apple Silicon collectors with accurate memory scope, independent adapter reviews and native evidence. [Contract](gpu-collection.md), [commitment](../commitments/intel-and-apple-gpus.md), [acceptance plan](../plans/intel-and-apple-gpu-acceptance.md).

Intel Windows support follows separately; a tablet is available for future validation. Intel Linux access and a discrete Intel test device remain to be established.

## Finish the application

The developer asked to finish the application on 2026-09-06. Complete the remaining original product features and a usable Linux package under [finish-application](../commitments/finish-application.md). The GPU work remains incomplete and its requirements remain included; this change of active work does not claim hardware acceptance or change the pending platform-priority decision.

## Reduce Mac monitoring overhead

The developer approved the [Mac performance commitment](../commitments/macos-performance.md) on 2026-09-07: at least 50 percent less release CPU in both Summary and tray-only modes on the same MacBook, preserving one-second readings and behavior. The earlier finish-application and GPU commitments remain incomplete; this new current commitment does not erase their pending evidence or historical scope findings.

## Process table improvements

On 2026-09-08 the developer agreed to stop Mac optimization after the running
comparison and move to the requested process-table work. The performance
commitment remains incomplete: Summary CPU fell 21.7% and tray-only CPU 34.0%,
below its 50% targets. The new [commitment](../commitments/process-table-improvements.md)
and [contract](process-table.md) cover table expansion, compact search, Mac
Threads visibility and authenticated privileged process controls.
