# Apple source observations under a bounded Metal load

Observed 2026-09-06 on the same M1 Pro as the [idle source probe](apple-source-probe.md).
This external probe resolves source questions before Apple implementation. It
does not compare a production collector, establish GUI behavior, or satisfy GPU-008.

## Workload and retained evidence

A task-owned Swift program selected the native Metal device, compiled a small
compute kernel, allocated one 1 MiB shared output buffer and submitted commands
serially for 15 seconds. Every command completed successfully and its sampled
output was finite. The device name was Apple M1 Pro; registry ID 4294969787 matched
the independent Metal/IOKit/IOReport inventory.

The program completed 11,802 commands in 15.000913 seconds. Its first/last GPU
command times were 514570.164468 and 514585.1630225. PID 99967 exited with code 0;
the launcher waited for its process and confirmed exit. A 30-second wait bound
and task-owned process-group cleanup protected against a stuck workload. The
separate compile completed in 3.453 seconds with exit 0.

The [raw captures and manifest](apple-loaded-source-probe.json) contain the
compile/workload reports, before/during/after temperature reads, the IOReport
pair, and 17 artifact hashes. Local transfer verification checked all four
probe exit codes, source hashes and output hashes. Original scripts, logs and
Swift source remain in `/home/shawn/workspace2/task-manager-artifacts/gpu-recon/`.
The remote files remain in the dedicated validation directory documented in the
[Mac baseline](mac-collector-baseline.md).

## Actual source values

| Source | Before workload | During workload | Immediately after workload |
| --- | --- | --- | --- |
| SMC `Tg04` | 0 | 40.7132607 | 44.2560005 |
| SMC `Tg05` | 9.1999998 | 49.9132614 | 53.4560013 |
| SMC `Tg0C` | 0 | 37.3357658 | 41.1063766 |
| SMC `Tg0D` | 9.1999998 | 46.5357666 | 50.3063774 |

These are four-byte little-endian SMC `flt ` values. During the workload the
documented M1 GPU keys `Tg05` and `Tg0D` respond as temperature sources. Their
idle values remain a validity question: both are approximately 9.2 when the
companion keys are zero, and each pair differs by approximately 9.2 under load.
This suggests a source offset or inactive-state behavior, but the probe does
not establish its firmware meaning. Do not invent an offset subtraction, a
temperature floor, or a cached current temperature. The subsequent
[temperature decision](../../decisions/report-unvalidated-apple-smc-temperatures-as-unavailable.md)
adopts OSHI's documented conservative SMC plausibility guard, preserves raw
values and states its cold-reading limitation. This is a software policy, not
a discovered firmware validity bit. The [pinned upstream source record](apple-temperature-policy-source.json)
retains its commit, blob and source-file hash.

HID still exposed no GPU-named temperature service. System fan keys `F0Ac` and
`F1Ac` remained zero; this does not establish GPU fan attribution.

The IOReport pair during load had a query-completion interval of 0.811406875
seconds. The actual raw differences were:

- `GPUPH`: P6 increased by 19,493,270 ticks. OFF and every other state increased
  by zero. Active/all residency is 100%; the observed P6 mapping gives an
  active-weighted frequency of 1,296,000,000 Hz.
- Matched-driver `GPU Energy`: 7,859,418,500 nJ, giving 9.6861621 W from that
  measured interval.
- Separate PMGR `GPU0`: 7,895 mJ, giving 9.7300137 W. `GPU SRAM0` did not advance.

These independent channels are close but have different providers and query
semantics. Their difference is not an accepted tolerance, and they must not be
summed or substituted silently. Native acceptance must predeclare its comparison
windows and bounds before comparing the actual production collector.
