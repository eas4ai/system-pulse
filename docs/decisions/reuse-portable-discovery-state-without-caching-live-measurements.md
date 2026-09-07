# Reuse portable discovery state without caching live measurements

Level: Judged
Decided by: agent
Rests on: PERF-001 PERF-002 PERF-003 PERF-004
Would be wrong if: The change drops discovery or readings, freezes a failure as current, changes identities or interval, accumulates historical state, or fails the measured CPU comparison.

## Decision

Start with the measured portable collector. Retain the sysinfo temperature client and refresh actual readings at each existing sample. Keep enumeration and removals safe; if periodic discovery is used, bound its delay and test recovery. Cache account-name resolution with bounded refresh while retaining per-process current user IDs. Do not reuse disk capacity through a refresh API that silently retains stale fields on failure. Make one coherent change at a time and compare native release CPU against the preserved baseline before expanding scope. Preserve the single worker, live values, physical query windows and one-second benchmark interval.

## Realized by

56038af4b332debc3006db03c3688d78da241011 Reuse Apple temperature connections with failure recovery

The first change retains the Apple Silicon temperature connection in
`crates/collectors/src/host/temperature.rs`. Every sample refreshes readings and
discovery, removes absent entries, and schedules a new connection after a failed
read or empty inventory. Other temperature backends are unchanged. Account-name
reuse remains unbuilt pending the next whole-application measurement.
