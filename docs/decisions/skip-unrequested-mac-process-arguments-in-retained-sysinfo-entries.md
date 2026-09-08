# Skip unrequested Mac process arguments in retained sysinfo entries

Level: Judged
Decided by: developer
Rests on: PERF-001 PERF-002 PERF-003 PERF-004
Would be wrong if: The patch drops requested metadata, breaks new or reused PID handling, alters fresh CPU memory I/O or user behavior, or fails native preservation.

## Decision

Developer confirmed the scoped dependency proposal on 2026-09-08. Retain sysinfo 0.37.2 with a narrow local guard around unrequested process argument reads and targeted tests. Current upstream still performs the reads, so avoid a wider dependency upgrade. Extend the current commitment to the vendored dependency, Cargo patch/lock and necessary provenance/package notices. Preserve all performance targets and fresh paired verification.

## Realized by

- d45a086f6ac960bf8f22a2d4e8820d1f5e01c621 Skip unrequested Mac process metadata reads in sysinfo
