# Reuse collector bookkeeping and GPU HID connection without caching readings

Level: Judged
Decided by: agent
Rests on: PERF-001 PERF-002 PERF-003 PERF-004
Would be wrong if: Retained handles prevent fresh discovery or recovery, a failed read preserves a current value, identity state grows without a bound, or native comparison does not support an improvement.

## Decision

The guarded whole-app profiles show repeated counter-key allocation and native GPU HID setup in the collector. Keep per-sample counter visitation alongside each existing baseline instead of allocating a second set of keys. Retain only the GPU HID API and connection; enumerate services and read every event each sample, discard the connection after failure or empty discovery, and reset it when GPU inventory changes. Preserve all readings, raw counter windows, identities and the one-second interval. Use controlled failure, removal and recovery tests plus native profiles and complete paired acceptance. This does not authorize UI, service or additional dependency changes.

## Realized by

- fe20c031f9b0716387b3a1c0572d3252b2ee07e7 Reuse counter bookkeeping and GPU HID connections between fresh reads
