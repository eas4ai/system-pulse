# Apple native comparison protocol

Status: Prepared before production acceptance capture. The Task 4 mechanism and
its independent reviews must implement and verify this procedure. This document
contains no native acceptance result.

The [acceptance plan](../../plans/intel-and-apple-gpu-acceptance.md) and
[GPU contract](../../spec/gpu-collection.md) remain authoritative. Earlier
[source probes](apple-source-probe.md), [loaded probes](apple-loaded-source-probe.md)
and the [baseline build](mac-collector-baseline.md) establish prerequisites.
They do not compare the new production collector.

## Declare before measurement

Write a machine-readable policy file, hash it and retain it before launching the
capture. Record the committed source, Cargo.lock and executable hashes; OS/API
versions; observer source hash; Metal registry ID and physical IODeviceTree path;
and every expected field's source, scope, native unit, formula and availability.
Use independent inventory to establish the expected field set. A collector's
reported subset must not determine what the verifier demands.

Declare the sample count, initial warm-up allowance, polling interval, maximum
observer gap, maximum source-query duration, capture deadline and bounded retry
count. Include idle, sustained Metal load, interval change and recovery phases.
Every attempt is retained. Changes to a policy require a separately identified
new attempt; never widen bounds to turn an existing mismatch into a pass.

Native observations must cover each accessible attributable field. A denied,
missing or ambiguous native source has its actual limitation recorded. An
accessible field missing production implementation is a failure. Native sleep
or source-failure recovery is required where reproducible; disclose operations
that cannot safely be induced on this host and retain deterministic coverage.

## Independent clock and counter evidence

Both the observer and collector record monotonic-before, wall-clock and
monotonic-after anchors. Intersect anchor constraints to map query intervals
between their clock origins. Reject inconsistent anchors, impossible ordering,
nonpositive elapsed time or an observation gap beyond the declared bound.
Python, Rust and Metal uptime values must not be compared as if they share an
origin without evidence. A requested polling delay is never measured elapsed.

The observer reads native absolute residency and energy counters independently
of production conversion code. Match driver/channel identifiers, format, unit
and state labels to the independently discovered physical GPU. Retain the
original integer operands and query start/end times. Verify monotonicity and
channel layout through each compared interval; a regression or source instance
change invalidates that interval and requires a fresh baseline.

First recompute each production reading from its published raw operands using
independent arithmetic. Then compare those operands to independent native
observations that bracket each production query. An observer read wholly before
the mapped production query supplies a lower cumulative-counter bound; a read
wholly after supplies an upper bound. Merely overlapping windows is insufficient
for this ordering claim. Query and anchor uncertainty both count toward gaps.
A counter outside its bracket fails even if the final rounded value is close.

For previous bounds [p_lo, p_hi] and current bounds [c_lo, c_hi], a nonnegative
counter delta lies in [max(0, c_lo - p_hi), c_hi - p_lo]. A negative upper bound
is invalid evidence. Check each residency state separately. Source integer
precision is exact; do not add an arbitrary percentage tolerance.

| Field | Independent arithmetic and scope checks |
| --- | --- |
| Activity | 100 times active residency delta divided by all residency delta. Reject zero total, missing states and unproven state meaning. Frequency mapping failure does not justify losing independently valid activity. |
| Frequency | Sum of each active state's delta times its evidenced frequency in hertz, divided by active residency delta. Reject no-active intervals and any nonzero state without a validated table entry. Maximum table frequency alone is not a measurement. |
| Power | Matched-driver GPU Energy delta in nJ times 1e-9, divided by the actual recorded sampling endpoint interval in seconds. Retain both query windows and independently check endpoint arithmetic. |

The per-state counter bounds also bound activity and active-weighted frequency.
For activity, use the active lower/inactive upper sums for the lower ratio and
the active upper/inactive lower sums for the upper ratio. For frequency, the
verifier must use a proved interval method or compare each raw state within its
bracket before recomputing the weighted result; independent negative tests must
reject a changed mapping or denominator. Bounds with an undefined denominator
cannot establish that value. Keep exact raw-integer checks distinct from any
small, declared floating-point rounding allowance in the recomputed result.

Do not substitute or add PMGR GPU0/GPU SRAM0 energy to matched-driver GPU Energy.
The [earlier loaded capture](apple-loaded-source-probe.md) observed a difference
between these providers; that difference does not define acceptance tolerance.

## Gauges and memory

Temperature and allocation gauges are not monotonic. Collect independently
timed reads before and after the production query and through the declared
comparison window. Retain all values, including mismatches. Compare production
raw bytes/integer values with the observed range using only the predeclared
source representation precision. This is an empirical temporal comparison,
not proof that a nonmonotonic source stayed within that range between reads.
An out-of-range value remains a mismatch or unverified interval; do not invent
extra smoothing or a workload-dependent tolerance after observing it.

SMC checks identify the exact key, returned type, size, raw bytes and status.
Decode the native representation independently. The [SMC policy](../../decisions/report-unvalidated-apple-smc-temperatures-as-unavailable.md)
requires finite values below 15 Celsius to be Unavailable with retained raw
operands and a software-plausibility reason. At the boundary and under load,
otherwise valid values are published unchanged. The policy can withhold a real
cold value; it is not a hardware validity bit. Check HID independently and do
not apply this policy to it. A system fan is not an attributable GPU fan.

Accelerator memory must match the same Metal/IOKit physical GPU and the exact
PerformanceStatistics key. Preserve integer bytes and the distinction between
allocated and in-use shared GPU memory. Require a scalar byte quantity with no
invented capacity total. Total system RAM, Metal process allocated size and
process footprint are invalid replacements. Verify labels and compatible meter
choices in the actual application as well as raw collector data.

## Native application and cleanup

Use the executable whose hash appears in the capture, with an isolated,
task-owned state directory. Wait for the native workspace to populate. Record
actual visible GPU labels and values with native accessibility geometry or a
permitted screenshot, and compare them to the consumed snapshot with an
explicit freshness window. A diagnostic file or SSH process alone is not proof
that a field was displayed. A truncated accessibility tree must not be treated
as a complete GPU-field census.

Exercise panel and sensor collapse, scrolling, sampling interval changes and
restored meter choices. Retain before/after native observations and persisted
state. Launching the app alone does not exercise these operations. Record
bounded history and stale/unavailable outcomes through the existing acceptance
paths. Preserve the complete Linux workspace acceptance separately.

The Metal workload selects the independently identified device, uses bounded
memory and serial commands, and has a fixed duration plus a hard process-group
deadline. Retain its source/binary hashes, PID, start/exit status and command
completion evidence. Stop only task-owned workloads/apps and verify exit.
Task-owned keep-awake assertions are stopped when native work finishes.

Native observer and workload code must scope and drain autoreleased Objective-C
objects, including Metal initialization and repeated command submission. The
[collector correction](apple-autorelease-correction.md) also exposed 57 missing-pool
warnings from the earlier standalone Swift workload; those were retained under
its own PID. The Task 4 helper must correct that lifetime before acceptance use.
Check each native process with `OBJC_DEBUG_MISSING_POOLS=YES`, retain unfiltered
stdout/stderr and PID attribution, and reject remaining missing-pool warnings
from the application, collector, observer, accessibility helper or workload.
An empty collector log cannot clear another process's separate failure. Retain
compiler diagnostics separately with the compiler PID; they are not runtime
diagnostics for the executable being built. The recorded
[full-application finding](apple-gui-preflight-findings.md) remains open until a
fresh run of the corrected application and native interactions clears it.
Preserve this diagnostic as lifecycle evidence;
ordinary accuracy comparisons still require their declared sources and timing.

The final per-host report links policy, originals, independent comparisons,
actual native interactions, commands and cleanup. The aggregate requires the
separate Intel integrated and Intel discrete Linux reports as well as this
Apple report. A valid Apple result cannot fill either missing Intel class.
