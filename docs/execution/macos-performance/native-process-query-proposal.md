# Proposal: consolidate native process queries

Status: Proposed; not authorized or implemented.

The [complete presentation comparison](presentation-results.md) reports 25.26
percent less Summary CPU and 33.86 percent less tray CPU. Both 50 percent targets
remain unmet. Four complete candidate comparisons have now missed those targets
(initial collector, argument guard, collector bookkeeping/HID, presentation).
The repository requires the next decision after three unsuccessful requirement
attempts to be Blocking. Passing preservation does not pass the CPU requirements.

## Measured basis

The separate tray CPU profile attributes 287 of 1,156 sampled milliseconds to
sysinfo process refresh. This inclusive cost is not an estimate of removable
work. The earlier guarded stage probe measured about 18.2 CPU milliseconds per
process refresh. Sysinfo update_process currently obtains BSD identity data,
thread data and task counters with separate calls. The application needs fresh
identities, CPU, memory, I/O and user information every sample.

## Requested next action

Authorize one bounded investigation and, only if supported, implementation of
consolidated native process queries. Extend the existing sysinfo patch scope
beyond its argument-read guard to this process refresh path and directly
necessary tests/provenance. Application collector integration remains in scope.

1. Probe the native combined BSD/task query against the current separate calls
   using the same PID set. Measure thread CPU outside scored application runs.
   Compare identities, counter units, fields, access failures, missing/reused
   PIDs and returned structure sizes. Retain all results, including failures.
2. Proceed with a patch only if the probe shows a useful reduction while
   preserving required fields and truthful failure behavior. Keep existing
   reads where combination is unsupported or changes access semantics. Do not
   add a retry path that silently raises overhead for denied processes.
3. Preserve one-second reads, all processes and metrics, actual query windows,
   identity invalidation, history, interaction and the agreed reference.
   Do not cache failed data or present an unrefreshed value as current.
4. Run focused tests, Linux/Mac checks, native preservation and the same complete
   twelve-observation gate. If the probe fails its go/no-go conditions, retain
   it as evidence and stop without implementing a speculative patch.

No service, framework redesign, wider dependency upgrade, slower interval or
reduced coverage is included. This proposal does not predict a 50 percent
reduction. Any later step remains governed by scope and the attempt rule.
If declined, preserve the verified current changes with both CPU targets open;
do not lower the targets or call the commitment complete.
