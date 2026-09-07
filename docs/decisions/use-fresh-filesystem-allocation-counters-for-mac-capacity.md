# Use fresh filesystem allocation counters for Mac capacity

Level: Judged
Decided by: developer
Rests on: PERF-001 PERF-002 PERF-003 PERF-004
Would be wrong if: The capacity read is cached, a failure becomes zero or current, physical arithmetic is wrong, disk discovery or I/O coverage changes, or native verification fails.

## Decision

The developer approved actual filesystem used/total bytes on macOS, matching the Linux definition, instead of available space including potentially reclaimable files. Native probes measured about 50 milliseconds of process CPU per sample for fresh important-usage capacity queries; clearing Core Foundation caches retains that cost, and keeping them risks old readings. Keep fresh sysinfo disk discovery and I/O each sample with storage queries disabled. Read fresh statvfs counters for each discovered mount, calculate used as (blocks - free_blocks) times fragment_size, retain query windows and raw operands, and report errors or invalid arithmetic explicitly. Preserve monitor and sensor identities, interval, history and disk I/O semantics. No retained disk inventory is introduced.

## Realized by

- a5af944f2573b60ab4df4d2fa98de238dbd43b1a Read fresh Mac filesystem allocation and add paired CPU measurements
