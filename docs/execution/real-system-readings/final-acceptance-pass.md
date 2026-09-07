# Real system readings: full committed acceptance

The committed aggregate against `bb87134b978f8c2400ff1cbed755ca5ee9615d28`
passed on 2026-09-06. Cairn receipts `20260906T060609244Z` record **PASS for
LIVE-001 through LIVE-013**. The final independent review subsequently passed and Cairn returned Done;
see the [completion record](completion.md).

[Complete record](final-acceptance-pass.json): commands, test counts, native cases,
seven session identities and cleanup, sixteen controlled-child metrics, eight
held-input summaries, recovery observations, host exit gaps and 242 artifact hashes.
Root independently checked all 154 declared artifact sizes/hashes and all command
log hashes, then verified source/executable identity and mandatory child evidence.

Artifact directory:
`/home/shawn/workspace2/task-manager-artifacts/tmp/system-pulse-cairn-check-7bza_d7_/system-pulse-acceptance-pr8gjqwq`.

## Automated and host verification

All **745 tests** passed: 383 Python and 362 Rust. The Rust suites cover 205 base
dock, 13 resizable, 19 component dock, 24 model, 56 app, 43 collector and two
vendored AT-SPI tests. Source guard, affected and vendored formatting, strict
all-target Clippy, native build and whitespace checks passed.

Independent host capture passed 2,218 exact readings, 18,284 process fields,
44,948 counter brackets, 96 interface checks and 468 stable-total comparisons.
Initial/final device inventories agreed; every accessible required capability
was accounted for. Controlled host child `1850500:75857376` retained mandatory
coverage and independently verified exit. There were zero failed brackets.

Four ordinary-process CPU endpoints remain explicitly **unverified exit gaps**:
utime and stime for `1850753:75857681` and `1850759:75857685`. Each has retained
independent before observations and later matching terminal ENOENT evidence.
These are disclosed exceptions under the developer's [agreed exit policy](../../spec/live-collection.md#process-exit-observation-policy),
not successful counter comparisons. Controlled coverage and all other mandatory
comparisons passed; no process population was excluded.

## Complete native replay

The 420.67-second full replay passed launch, real metrics on both AMD GPUs,
independent panel/sensor collapse, physical charts, inner scrolling, process
appearance/identity/metrics/exit, split resizing, outer scrolling, held input,
preset recall, restart, schema/JSON recovery and absent saved-device restoration.

Native child `1858492:75867120` passed all sixteen comparisons: eight initial cells,
left, six visible columns and right. Fresh exact selected-child proof preceded
termination. Native and snapshot exit acknowledgement agreed with independent
terminal ENOENT; the child exited -15 as requested by the harness.

Seven application sessions and the private transport all exited zero with no
remaining process. Every session retained the same reviewed executable SHA-256:
`7dbcd3adfae54db64e3ed5f32cf728ee55684fd1429c95c1bbd1e72a770340e7`.
The run was untraced and not a focused preparation run.

All eight held/exact-input observers joined and saw at least three accepted
sequences. Maximum observed age was 1.380016235 seconds under the primary
session's two-second limit. Exact 64 Up matched the expected PID/start identity.
Restored two-second sampling uses the predeclared four-second age limit.

Two intermediate navigation recoveries were exercised. Each saw the expected
identity reindex just above the instantiated span, used two nonselecting upward
wheels and obtained fresh exact endpoint selection proof before its original
eight-second deadline. An additional child-inspection recovery used the existing
fifteen-second discovery deadline. No interrupted batch occurred. These observed
recoveries do not reconstruct every earlier failed run or prove a five-second
inspection recovery measurement.

Root inspected the captured [physical GPU chart](final-screenshots/gpu-0-temperature-chart.png)
and [recalled separate workspace](final-screenshots/recall-no-tabs.png). The chart
shows temperature in degrees C and a physical scale; the workspace retains
separate panels and the saved collapse/sampling choices. Final visual styling is
outside this collection commitment.

## Verification limits

NVIDIA adapter conversion/discovery/failure tests passed, and this AMD-only host
records `NVML init: DriverNotLoaded`. Live NVIDIA hardware accuracy remains
unverified. macOS/Windows native behavior and physical device removal remain
unverified. Missing-device restoration uses a stopped-app saved configuration
specimen with no fabricated measurements. The latest diagnostic JSON does not
expose every history point; history evidence combines model/app checks, accepted
sequences and the inspected physical chart.

Historical failed captures retain their original results. See the
[implementation plan](../../plans/real-system-readings.md) and
[final review](../../../.cairn/reviews/real-system-readings.md) for commitment closure.
