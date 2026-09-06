# GPU acceptance specification review

Historical initial review: **nine findings, now closed by the
[re-review](gpu-acceptance-spec-rereview.md).** That re-review records new open
finding F10. The initial independent read-only review covered
Task 4 source `c014522d23aae011cfe2e88627320e07740b4ebc`, before corrective
implementation. Intervening commits contain only orchestration documents.
No source or acceptance policy was changed during the review.

The reviewer independently ran all 42 committed GPU verifier tests, an isolated
missing-group experiment, three adversarial scripts and offline Cargo metadata.
The existing tests passed, while the attacks below exposed acceptance gaps.
Original scripts, logs and metadata are retained under
`/home/shawn/workspace2/task-manager-artifacts/gpu-task4/spec-review`.
The [artifact record](gpu-acceptance-spec-review.json) binds the final evidence.
These are synthetic boundary tests, not native hardware accuracy reports.

## F1 — P1: Intel capacity operands escape independent comparison

[gpu_intel_arithmetic.py](../../../scripts/system-pulse/gpu_intel_arithmetic.py),
lines 129–145, computes allocation from production capacity and count operands
but selects only the count for native comparison. The complete `verify_series`
path accepts allocation capacity changed from 16,384 to 32,768 bytes and its
derived allocation from 12,288 to 28,672 bytes across four snapshots. Independent
observations and the separate total sensor remain at 16,384 bytes. The incorrect
28/32 KiB label also passes; no later cross-reading check repairs the omission.

GPU-004/005/009 require comparison of every contributing capacity/count operand
against its independently observed physical region. Reproduction: `attacks.py`.

## F2 — P1: Sensor collapse lacks proof of its visible effect

[gpu_desktop.py](../../../scripts/system-pulse/gpu_desktop.py), lines 263–269,
checks the persisted sensor-collapse toggle but reserves the subsequent visible
control check for meter changes. Complete `validate_actions` accepts all six
required actions when the targeted sensor/control/rows remain unchanged and
only unrelated timer text changes. Original binding validates those same
observations and saved states; it does not add the missing effect check.

GPU-007/008 and the native protocol require the targeted sensor's corresponding
visible change. Reproduction: `attacks.py`.

## F3 — P1: Source binding omits actual first-party build dependencies

[The mechanism declaration](../../../.cairn/mechanisms/gpu-acceptance), line 9,
binds selected dock/resizable paths instead of the application's complete
relevant first-party dependency inputs. Offline Cargo metadata and tracked-file
comparison established the following regular build dependencies:

| Package | Tracked files | Bound files |
| --- | ---: | ---: |
| gpui-base | 222 | 35 |
| gpui-component | 236 | 7 |
| gpui-component-assets | 108 | 0 |
| gpui-component-macros | 4 | 0 |

All four manifests are unbound. `committed_inputs()` can therefore accept changes
to code that Cargo compiles into the executable. Binary hash agreement does not
establish the missing source provenance. GPU-008/009 require the relevant source,
manifest, build-script and asset closure. Evidence: `attacks.py`, offline metadata
and `unbound-build-dependencies.json`.

## F4 — P2: Valid same-name GPU labels are rejected

[gpu_desktop.py](../../../scripts/system-pulse/gpu_desktop.py), lines 170–177,
constructs expected labels from the collector title. Production
[live.rs](../../../examples/system_pulse/src/live.rs), lines 243–253, appends the
full stable identity when names collide. A correct disambiguated label is
rejected as an independent display mismatch.

GPU-001's same-name integration case requires the verifier to independently
reproduce that defined disambiguation. Reproduction: `attacks.py`.

## F5 — P1: A mandatory verifier group can disappear unnoticed

[gpu_verify.py](../../../scripts/system-pulse/gpu_verify.py), line 135, marks
automation successful after wildcard discovery and an aggregate nonempty-test
check. Removing only `test_gpu_arithmetic.py` in an isolated script copy leaves
36 passing tests and exit zero through the same development gate. Later
requirement results use that automation boolean without requiring the omitted
group. The experiment emitted no Cairn acceptance lines.

Task 4 and GPU-009 require every mandatory group to exist and execute nonempty
successful tests. Evidence: `omitted-suite-result/` and `commands.json`.

## F6 — P1: Native discovery comparison ignores additional GPUs

[gpu_intel_capture.py](../../../scripts/system-pulse/gpu_intel_capture.py),
line 510, reduces the original inventory to the selected PCI device.
[gpu_samples.py](../../../scripts/system-pulse/gpu_samples.py), line 35, checks
only that monitor. An original census of two accessible discrete Intel GPUs
passes inventory replay and snapshot verification with one GPU missing from
the production snapshots. `verify_host` can then satisfy GPU-001 without a
complete inventory comparison.

GPU-001/009 require complete physical discovery comparison separately from the
selected device's accuracy coverage. Reproduction: `inventory-attack.py`.

## F7 — P1: Omitting an auxiliary lifecycle entry hides its failure

[gpu_originals.py](../../../scripts/system-pulse/gpu_originals.py), line 25,
requires fixed primary roles and checks completion records only for listed
lifecycle entries. Action checks cover some AX helpers, but auxiliary readiness
and close helpers can disappear. The attack first rejects an `axclose` missing-
pool warning, then removes only that lifecycle entry. Its original completion
and warning log remain retained, yet original and lifecycle validation pass.
No subsequent host check examines the omitted role.

GPU-008/009 and the all-process diagnostics protocol require reconciliation of
the complete started/finished process census, lifecycle entries and logs.
Reproduction: `originals-attack.py`.

## F8 — P1: Native process identity and full commands remain unbound

[gpu_originals.py](../../../scripts/system-pulse/gpu_originals.py), line 17,
compares stream content without associating its native PID with the owning
lifecycle role. Lines 62–66 check executable identity and only `argv[0]`.
Raw observer PID 999 and inventory PID 998 pass against lifecycle PIDs 12 and
16 because normalization drops those fields. Arbitrary command tails, including
an unbound interpreted script or mode, also pass this boundary.

GPU-008/009 require native PID/stream ownership and complete role-specific
commands to match retained source and lifecycle originals. Reproduction:
`originals-attack.py`.

## F9 — P1: Intel can claim a load phase without GPU work

A subsequent read-only review used an external snapshot of the original
`c014522d` source while F1–F8 corrections were underway. In that source,
[gpu_host_capture.py](../../../scripts/system-pulse/gpu_host_capture.py),
lines 411–423, accepts any nonempty workload argv. Selected-device and
completed-command receipts in
[gpu_originals.py](../../../scripts/system-pulse/gpu_originals.py), lines 73–86,
apply only to Apple. Lines 190–203 independently require a consumed observation
somewhere in the load phase and a workload contained in that phase; they do not
require measurement overlap with actual GPU work.

The synthetic original/lifecycle validation passes an honestly recorded
`["/usr/bin/true"]`, its actual executable hash, empty output, and no physical
GPU or command-completion receipt. A phase observation at time 31 passes even
though the nominal workload window is [39, 40]. No later host check compensates
for the missing work or overlap. The
[acceptance plan](../../plans/intel-and-apple-gpu-acceptance.md) requires Intel
idle/load intervals and predeclared device/measurement coverage, supporting a
GPU-008/009 finding distinct from F8's command-provenance defect.

Require bounded evidence of commands completed on the selected physical GPU
and corresponding measurement overlap. This does not require utilization to
rise by a guessed amount. Reproduction: `intel-load-followup/intel-load-attack.py`;
its manifest records the original source and final synthetic run. The reviewer
did not execute a native workload, including `/usr/bin/true`. This finding is
recorded before any correction addressing it.

## Correction and review order

All nine findings were open at this initial review. Their record-preserving
regressions and corrections at `ece89eae` passed independent re-review. The new
F10 finding remains open; independent quality review still awaits specification
approval.

The separate [Linux freshness failure](gpu-linux-preservation-failure.md),
locked Mac desktop, pending Mac application pool correction and missing Intel
hardware remain unresolved acceptance obligations. This reviewer launched no
native applications or workloads, compiled no Mac helper, ran no full Linux
preservation and issued no Cairn acceptance receipt.
