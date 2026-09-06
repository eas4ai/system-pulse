# Add Intel and Apple collectors within the existing physical reading pipeline

Level: Judged
Decided by: agent
Rests on: The developer confirmed GPU-001 through GPU-009 on 2026-09-06; LIVE collection and workspace behavior remain preservation constraints.
Would be wrong if: The selected source cannot establish the declared device, quantity, unit or freshness, or the implementation needs a second polling pipeline to supply it.

## Decision

Implement Intel Linux through direct DRM/sysfs, read-only device queries and documented engine counters, with per-source permission and attribution limits. Keep vendor APIs optional and add a Sysman dependency only if an evidenced required field has no suitable direct source. Implement Apple Silicon through native IOReport/IOKit/SMC/HID observations using the supplied references as source leads; independently validate channel layouts, units, query intervals and physical GPU association. Reuse HostCollector, SamplingService and typed Reading/RawObservation. Own OS handles inside the existing worker; do not introduce a second polling loop or treat missing values as zero. Preserve existing AMD/NVIDIA identities and physical meters. Shared GPU allocations remain distinct from device-local VRAM and system RAM. Split work into Intel, Apple, presentation/integration and acceptance tasks, with one source implementer followed by independent specification and quality review at each stage. Native results remain unverified for each missing hardware class. The executable plan and per-field source records will state exact interfaces and falsifier cases before their implementation.

## Realized by

- 4db68c71304d368977265e31ba365b121fcfd9f0 fix: preserve GPU memory freshness and physical identities

This binds the reviewed collector and memory integration source. Required hardware captures and aggregate GPU acceptance remain incomplete.
