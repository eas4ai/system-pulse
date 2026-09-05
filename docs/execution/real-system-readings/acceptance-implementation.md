# Acceptance implementation work

- In progress: root committed aggregate, including fresh host and complete native execution.
- Verified preparation: executable aggregate and independent host/native harness;
  49 Python regressions, retained host re-analysis, 13 full-run native cases and
  focused final missing-device correction. The complete native run remains FAIL.
- Verified delivery preparation: documentation, self-audit and all listed manifest
  artifact paths, sizes and SHA256 hashes.
- Verified review: independent SPEC and QUALITY passed source `322b05d9`.
- Pending: full aggregate receipts and final adversarial review before Cairn Done.

Preparation checks are not final committed Cairn receipts. No aggregate acceptance
receipt has been earned by this implementation yet.

## Commands and evidence

The required aggregate entry point is:

```sh
rtk proxy python3 -B scripts/system-pulse/verify.py
```

It creates a fresh external run directory and retains complete command logs,
progress records, test counts, subprocess exit statuses, and artifact hashes.
Missing steps, zero executed tests, missing artifacts, failed host comparisons,
and incomplete native replay fail the aggregate. It runs the declared locked
Rust suites, scoped formatting, strict Clippy, binary builds, Python regressions,
fresh host capture, native replay, and `git diff --check`.

Focused preparation commands do not replace that aggregate:

```sh
rtk proxy python3 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py' -v
rtk proxy python3 -B scripts/system-pulse/host_capture.py --output /tmp/pulse-host-fresh --binary target/debug/pulse-snapshot
rtk proxy python3 -B scripts/system-pulse/native_replay.py --output /tmp/pulse-native-fresh --binary target/debug/system-pulse
```

Native execution needs Xvfb, a private DBus session, lavapipe, and system
`/usr/bin/python3` with GI/AT-SPI, python-xlib, and Pillow. The runner uses fresh
temporary application state. It does not read process arguments or environments.

## Independent source and timing rules

The OS capability inventory is collected before descriptor joining. Required
source IDs, physical units, actual accessible files, read errors, and attribution
scope are retained. Gauge arithmetic is checked against original captured
operands; independently sampled gauges are contemporaneous supporting evidence,
not a percentage tolerance between different instants.

Every captured cumulative counter endpoint needs an independent before and after
observation enclosing the entire mapped source-query interval. No PID population
is excluded to obtain a passing run. Missing endpoints fail and retain exact
identity, source, query interval, external intervals, and available error evidence.
PID reuse never joins observations across different start ticks.

External and collector wall-minus-monotonic intervals are intersected separately.
Collector origins are scoped to one collector instance. Disjoint offsets fail as
clock discontinuity; no midpoint estimate is used. The owned collector waits at
an exec gate so its actual PID/start counters can be observed before collection,
then emits exactly four predeclared snapshots. The supervisor immediately sends
SIGSTOP on the fourth newline, acknowledges the actual same PID/start in state T,
and reads final counters while that owned collector remains alive. It preserves
every output byte and fails any complete or partial fifth snapshot. SIGTERM then
SIGCONT reaps that supervised collector with expected status -15; this is distinct
from the native application's required normal status 0. Startup, stop, failure,
and final observations are retained even if an assertion fails.

## Preparation findings and corrections

The first 13 verifier regressions failed before implementation; their full RED
log is `/tmp/system-pulse-verifier-implementation-zpswl3j9/red.log`. Subsequent
regressions challenge aggregate omissions, both rendered copies being wrong,
missing process endpoints, PID reuse, and clipping by an ancestor viewport.

`host-03` initially reported a pass while exempting 16 missing process brackets.
That exemption was incorrect and has been removed. The corrected result is FAIL;
`host-03/corrected-result.json` and `corrected-missing-brackets.json` retain the
correction. All 16 missing endpoints were first observations of the harness's
new `rtk` and `pulse-snapshot` processes. The exec gate fixes that startup race.
The later `host-04` and `host-05` runs correctly fail on remaining short process
lifetimes; passing comparisons do not override those failures. `host-06` exposed
unreadable final zombie IO; its early external evidence was not saved, also a
harness defect. The live-stop lifecycle and unconditional evidence persistence
correct these defects. The coordinated `host-07` run completed that lifecycle and
verified the controlled child, but correctly failed 48 missing endpoints across
seven other process identities. Its 41,288 passing counter brackets, 2,218 exact
sensor comparisons, and 16,014 process field comparisons remain partial evidence.
The read-only diagnosis found new PIDs already in the external census waited
42–46 ms behind old process reads and gauge work. A general sampler correction
moves the census/process sweep first, samples newly enumerated PIDs before old
ones without dropping any, and removes the unnecessary 50 ms sleep within a
35-second/2,048-sweep bound. Its ordering regression first failed, then passed.
The single coordinated `host-08` capture passed 41,744 independent brackets,
2,219 sensor checks, 16,240 process-field checks, and 96 interface checks with
zero missing endpoints. A separate frozen-verifier review reconstructed every
endpoint and all 41 complete sweeps. These are focused preparation results;
the final committed aggregate must still perform its own fresh capture.

Review then found an undocumented four-ULP arithmetic allowance, including an
infinite-expected-value false positive. Regressions now reject either nonfinite
operand and a one-ULP change. CPU arithmetic uses the declared multiplication and
division order, and every numeric comparison requires exact equality. A separate
frozen-script re-analysis of the retained `host-08` inputs passed all 18,915 finite
numeric comparisons with zero unequal values and unchanged bracket/field counts.
This is strict re-analysis of the original capture, not a new host run. The report
is `/tmp/pulse-host08-exact-audit-vvll5mix/strict-final/report.md`.

SPEC review of `b3f3b9f7` subsequently demonstrated two further verifier gaps:
an incorrect collector MemTotal could agree with its own derived reading, and
an invented extra GPU could pass a one-way capability join. That prior PASS did
not establish independent stable-total equality or reverse device completeness.
Eight new tests challenge those cases, zero swap, wrong VRAM/volume totals,
missing/changed total brackets, extra logical CPUs, duplicate IDs, monitor-only
extras, wrong monitor kinds and attribution, raw source substitution, and changed
final inventory. The first run retained five failures plus its correct control in
`host-inventory-red.log`; all 37 Python tests now pass.

Correction `6a52d1a2` requires exact independently bracketed RAM, swap, VRAM and
filesystem totals; exact sensor and monitor identity sets; sensor-to-monitor and
descriptor-to-raw source attribution; and explicit failure on unobserved discovery.
Fresh captures retain a second independent inventory and fail changes between
initial and final inventories. Re-analysis of the original `host-08` artifacts
passed 468 stable-total comparisons and unchanged earlier comparison counts,
recorded under `host08-inventory-reanalysis/`. Its scope explicitly remains the
retained initial inventory; no final inventory was fabricated for that old capture.

Native preparation captured exact CPU, RAM, and AMD labels plus independently
collapsed rows and panels. Root visual review found that one AMD header lay
behind the toolbar despite being inside the window bounds. The native-06/08
two-GPU visibility claims are invalid. A clipping regression preserves this
finding. The separately reviewed product follow-up `217941e5` exposes workspace,
sensor, and nested process clipping bounds. `native-09` focused metric evidence
then passed true ancestor containment and root screenshot review; it is not a
normal-exit or full-replay receipt. Later replay failures retain truthful FAIL
results even when completed cases precede a run or cleanup failure.

Root review of `native-15` found constant 35 °C history displayed on padded
34–36 °C axes under an inaccurate “Observed range” caption. The separate
one-literal correction `48308ee5` labels these display bounds “Scale”. Numeric
bounds and readings are unchanged. Existing 45 app tests, formatting, strict
Clippy, locked build, and diff checks passed in `caption-candidate/`; independent
SPEC and QUALITY reviews both passed. Native input/table checks run before the
real horizontal dock split, while the initial Processes pane has inner overflow;
outer overflow and held Alt checks run after the split. This order preserves all
required interactions without manufacturing layout state.

The harness source candidate is `b3f3b9f7`. Its 29 Python regressions, Ruff
format/check, and diff check passed; complete logs are in `candidate-checks/`
under `/tmp/system-pulse-verifier-implementation-zpswl3j9`.

`native-20` remains FAIL at restart discovery despite completed child, split,
overflow, eight held-input cases, preset and first normal-exit checks. Its frozen
outer-width preparation was 640 pixels. Root reviewed its real child's eight
visible fields and independent exit evidence; these do not turn that run into
full acceptance. `native-restart-01` also preserves the failed per-restart AT-SPI
transport approach. A single private transport shared across application sessions
then passed focused `native-restart-02`. Focused `native-recovery-01` passed both
invalid-schema and invalid-JSON recovery, unchanged original bytes through
disclosure/Save/Recall, explicit recovery archival, normal exits, and subsequent
keyboard/restart checks. The complete 960-pixel replay is a separate required run.

`native-21`, from committed `b3f3b9f7`, ran the complete 960-pixel sequence and
passed launch, metrics, collapse, charts, inner scroll, the real child, actual dock
split/divider, both outer axes, all eight held-input cases, preset, restart and
both recovery modes. Its final result is FAIL: the missing-device specimen
inherited a 2,848-pixel dock while its workspace clip was 1,424 pixels. The full
accessible summary bounds failed containment although the short unavailable text
was visibly correct. That failure remains preserved and is not counted as PASS.

`native-missing-01` exposed the need to put the absent saved identity explicitly
in the specimen dock. The corrected shared function restores the real pre-split
dock, substitutes the absent identity for its original actual GPU panel, and
keeps that original actual GPU saved-hidden. It supplies no measurements. Focused
`native-missing-02` passed exact dock, metadata and sensor preferences, five-second
same-frame native equality and full ancestor containment, followed by normal exit
and private transport cleanup. Its `missing-device-config.json` retains the exact
stopped-app specimen. Root reviewed the unavailable header screenshot and bounds.

The first correction source was paused at `6a52d1a2` for independent review. Its verification
is in `correction-checks/`: 37 Python tests passed, formatting passed, the first
Ruff run reported one lambda-style issue, its correction passed Ruff, and the
final diff check passed. No extra full replay was run after the focused correction;
the root's mandatory Cairn aggregate must execute every case together and obtain
normal status 0 for every native session. Preparation receipts never substitute
for that committed aggregate.

QUALITY review then demonstrated that process fields could name a different PID
or raw `/proc` source from their enclosing row, and duplicate rows could pass.
It also showed that an already-exited private accessibility transport with status
42 could return normally and leave a misleading native PASS. Correction
`322b05d9` binds all five process fields to the enclosing PID/start identity,
expected field suffix and exact stat/IO path, including unavailable fields, and
rejects duplicate PIDs. Transport cleanup now requires observed status 0 and no
surviving process, records forced termination and errors before failing, and
has its artifact content checked by the aggregate.

Four process regression tests first produced 26 failing mutation subcases while
the actual CPU/IO counter control passed. Four cleanup tests first produced four
failures and two errors, retaining the normal-zero control. Both corrections then
passed; all 45 Python tests, Ruff formatting/lint and diff checks passed in
`quality-correction-checks/`. Cleanup tests isolate the actual Python function
without launching native prerequisites. Retained host re-analysis in
`host08-process-reanalysis/` passes the unchanged 41,744 counter brackets, 2,219
sensor checks, 16,240 process fields, 96 interfaces and 468 stable totals, still
limited to the original independent inventory. No new capture, build or native
run was performed for these narrow verifier corrections. The source is paused
at `322b05d9` for the final independent review follow-up.

## Supplemental process observation repair

The first committed Cairn aggregate passed 396 tests, formatting, Clippy and
build checks, then failed two required CPU counter brackets for a real short-lived
process that appeared between all ordinary external censuses. It did not reach
native replay. The root-owned [aggregate attempt report](aggregate-attempt-2026-09-05.md)
preserves that failed receipt and diagnosis; this was an observer sampling gap,
not evidence of incorrect application readings.

Correction `8ffa088b` adds prospective 20 ms census refresh scheduling to the
existing single observer thread. It checks between ordinary process reads and
after gauges, immediately observes new PIDs, and rereads them until the next full
census takes over. Every ordinary census PID still receives its normal read.
Supplemental census, stat, UID and IO observations retain actual source windows
and clock anchors in an append-only array. The verifier includes every retained
supplemental counter observation in its PID/start identity join. Old captures
without the optional array remain readable. Missing brackets still fail.

The original 35-second and 2,048-full-sweep limits remain enforced, with a declared
4,096 supplemental process observation cap. Exhaustion fails instead of dropping
data. Partial ordinary/supplemental records survive failure. Scheduling records
retain actual lateness and skipped slots; the nominal cadence is not a promised
20 ms observation bound or a change to counter comparison rules.

Four new timing/matcher tests first failed five assertions, then passed. They
establish supplemental before/after coverage for a birth between full censuses,
no loss of ordinary reads, no overwrite of repeat observations, actual cadence,
deadline/cap failure, and PID-reuse rejection. All 49 Python tests plus Ruff
format/lint and diff checks passed in `supplemental-checks/`. Retained `host-08`
compatibility in `host08-supplemental-compatibility/` preserves its earlier counts
and explicitly remains limited to the old initial inventory.

One coordinated focused `host-09` run passed: four snapshots, 41,440 counter
brackets, 2,216 sensor checks, 16,049 process fields, 96 interfaces and 468 stable
totals, with matching initial/final inventories and verified child exit. It
retained 35 complete full sweeps, 169 supplemental censuses, 103 supplemental
process reads across 30 actual PID/start identities, and 408 clock anchors.
Supplemental census-start intervals were 11.996 ms minimum, 20.001 ms median and
58.094 ms maximum; maximum schedule lateness was 26.222 ms, with six skipped slots.
The selected nearest counter brackets in this run used ordinary observations;
zero supplemental endpoints were needed for those proofs. The independent
regression separately establishes supplemental-only bracket matching. These facts
are preserved in `host-09/supplemental-summary.json` without claiming a cadence
guarantee or replacing the failed aggregate. Source is paused at `8ffa088b` for
independent review before another Cairn run.

NVIDIA hardware accuracy remains UNVERIFIED. `DriverNotLoaded` is a separately
recorded hardware boundary, not an accuracy pass. macOS/Windows native behavior
and physical device removal remain unverified. Configuration fault specimens
carry no simulated measurements. Historical fixture evidence does not satisfy
live acceptance.


## Independent implementation reviews

SPEC and QUALITY both passed source `322b05d9bfe1408f1317068aa66d3af924355762`;
QUALITY also inspected documentation HEAD `b7577afd38a7c944f063b82b057a5129ab89d8f3`.
Each reviewer ran eight focused pure tests. QUALITY independently repeated the
original process controls and five attribution/duplication mutations; controls
passed and every mutation failed. Its transport recheck accepted exit 0 and
rejected 42 and -15 with retained evidence. See
`/tmp/pulse-quality-corrected-transport-vqvaqfww/review.json` and
`/tmp/pulse-task3-spec-stable-total-pqsqqa6x/correction322b05d9-tests.log`.
No reviewer launched a new build, host capture, native session, or Cairn action.
These reviews approve the implementation for the committed aggregate; they do
not promote native21 or focused preparations to complete acceptance.


## Census correction review

Independent SPEC and QUALITY passed source
`8ffa088bffeeac1a4743170cff93bf2eec0847b8`, with documentation HEAD `52968510`.
SPEC ran five pure tests and independently replayed host09: 41,440 brackets,
zero missing endpoints, and 468 stable-total comparisons. QUALITY ran four
supplemental tests and two injected census-error checks, then inspected raw
coverage, anchors, and timing evidence. Every ordinary PID was still attempted.

Host09 selected no supplemental endpoints for its nearest brackets. Deterministic
tests separately establish supplemental-only matching and PID-reuse rejection.
Its maximum measured census interval was 58.094 ms; the 20 ms schedule remains
a target, not a guarantee or relaxed comparison bound. The failed aggregate
receipts remain intact. A fresh committed aggregate is still required.
