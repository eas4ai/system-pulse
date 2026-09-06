# Apple collector implementation

## Working state

- Complete: pure conversion, failure, identity and service tests; 96 collector tests passed on Linux.
- In progress: native IOReport, Metal/IOKit, SMC/HID implementation and local verification.
- Pending: committed native compile/run, evidence, self-review and candidate delivery.

## Native source selection before implementation

The exact sources, units, channel IDs and ownership are recorded in [source probes](apple-source-probe.md) and [loaded operands](apple-loaded-source-probe.md). Bind directly to the probed Core Foundation, Metal, IOKit, IOReport and Objective-C C APIs. No monitoring command or network source is used in production. IOReport GPUPH format 2, encoded unit 72058115876454424 (24Mticks), and GPU Energy format 1, encoded unit 216173288919924736 (nJ), must name the enumerated Metal registry ID. Memory comes only from that registry entry's PerformanceStatistics. Persistence uses its physical IODeviceTree parent path, never the runtime registry ID. The pmgr voltage-states9 little-endian frequency/voltage table supplies P-state Hz only where pairing is proven.

Create/copy CF objects and IOReport output dictionaries are owned until released; borrowed entries are read only while their owners live. IOKit matching consumes its dictionary. Services, iterators, parents and SMC connections have scoped release. The existing worker owns all native state. Optional sources are queried independently and retried. The documented M1 SMC keys are Tg05 and Tg0D; inactive-value semantics are not established by the vendor; the explicitly recorded software plausibility policy below governs display. HID GPU MTR Temp Sensor is optional. System fan keys have no proven GPU attribution.

Use target-specific `libloading = =0.8.9`, already present in the workspace lock, to load IOReport and private HID symbols at runtime. A missing private API is a source capability failure with later retry; it must not prevent the application from loading. Stable public CF/IOKit/Metal APIs link as native frameworks. The SMC policy follows the [recorded decision](../../decisions/report-unvalidated-apple-smc-temperatures-as-unavailable.md): a conservative software guard below 15 Celsius preserves raw successful reads but withholds their displayed values. It may withhold real cold readings and is not a hardware validity bit.

Before extending SMC selection, the pinned Stats sensor table was checked for exact GPU keys and generation scopes: M1 at lines 371–374, M2 at 394–395, M3 at 416–423, M4 at 440–450, and M5 at 475–482. Each family selects only those explicit keys; arbitrary Tg/Tf prefixes are rejected. Metal model names select this source profile but never form persistence identity. Only the M1 Pro has native execution evidence in this task; other profiles remain unverified on hardware. The table and its MIT notice are retained by citation and `apple/NOTICE.md`.

## Implemented capabilities and limits

| Field | Source, scope and units | Current outcome and limitation |
| --- | --- | --- |
| Identity | Metal registry ID joined to that IOKit service; physical IODeviceTree sgx parent | Persistence excludes model name, ordinal and runtime registry ID. Same-path ambiguity is rejected. Missing inventory clears baselines; changed instances warm up again. |
| Activity | Matched IOReport GPUPH; active/all state residency, 24Mticks | Checked cumulative subtraction; known OFF/Pn layout, channel format, identity and units required. Unknown nonzero active frequency slots do not invalidate independently valid activity. |
| Frequency | Active-state weighted Hz from the same GPUPH interval and checked pmgr voltage-states9 pairs | Retains original frequency/voltage pair words and table query window. One physical GPU and one pmgr provider are required. Missing/changed table or inactive GPU yields no current frequency. |
| Power | Directly matched GPU Energy in nJ divided by actual elapsed ns | Retains both original counters/query windows. PMGR GPU0 and SRAM energy are neither substituted nor added. Failure, regression, channel change and nonpositive time reset continuity. |
| Memory | Same accelerator PerformanceStatistics: Alloc system memory and In use system memory, bytes | Separate shared-memory scalar sensors; no capacity total. Native hasUnifiedMemory fact is retained. System RAM, another driver, wrong units or different counter meaning are rejected. IOKit property-copy return codes distinguish API failures from absent keys. |
| SMC temperature | Exact model/key profiles from pinned Stats; flt little-endian Celsius | Every key is read independently on every capture. Raw key/type/size/bytes/status/query operands remain in successful reads. Below 15 Celsius is withheld by the named software plausibility guard; no clamp or offset. Other generations have source profiles but no native hardware verification. |
| HID temperature | GPU MTR Temp Sensor followed only by an optional numeric suffix; temperature event Celsius | Independent from SMC. One physical GPU is required to establish device attribution. No such source exists on the tested M1 Pro; CPU/PMU sensors are not substitutes. |
| Fan | SMC system fans | No established GPU attribution. Explicit unavailable reading; no invented RPM. |

Private IOReport/HID APIs load from fixed system library paths and retry after unavailable initialization. Every sample re-enumerates Metal/IOKit devices. Native handles stay inside the existing worker; the factory remains Send, while the locally created collector no longer needs that bound. No unsafe Send implementation, extra poller, monitoring command, remote service or reference-project dependency enters production.

All loops have explicit device/channel/state/service/ancestry bounds. CF create/copy results, subscription outputs, samples, IOKit iterators/services/parents and SMC connections have scoped ownership. CF array/dictionary members are borrowed only while their owner lives. Format-specific getters run only after metadata validation. Native errors preserve their operation/return code; key absence and unsupported APIs use unavailable outcomes. A failed optional source does not disable memory, other temperatures or future attempts.

## Test-first and preliminary native checkpoint

The required 75 percent, 600 MHz and 2 W tests failed against unimplemented conversion bodies before implementation. Identity, baseline reset, SMC guard, native count/layout and collector assembly tests likewise failed before their implementations. The worker Rc regression first failed to compile specifically because of the unnecessary collector Send bound. Later failures exposed negative Celsius classification and acceptance of incorrect memory source/units/meaning; those were corrected before the final native checkpoint.

Linux passed 96 collector tests, strict Clippy, formatting and diff whitespace checks before the final native archive. The preliminary committed source `911848a8f0d6482870d774e91711a152e8819786` compiled on the arm64 M1 Pro and passed 39 native tests. A three-snapshot 500 ms run exited zero and returned the expected physical GPU, idle residency/power, shared-memory counters, guarded SMC values and independent unavailable fields. The preliminary native Clippy run found one unused import; it is corrected in the next checkpoint. Its archive and logs remain separate from final evidence.

Final native test/Clippy/load evidence is pending the corrected committed archive. This implementation checkpoint is not GPU-008 accuracy acceptance, a full GPUI build or a UI/persistence replay.

## Production self-audit

1. Mapped HostCollector, SamplingService, descriptors/raw observations and all native source probes before editing.
2. Added only the Apple adapter, platform dependency, host hook, necessary worker bound change, tests and evidence.
3. Separated pure conversion/state, native ownership, IOReport, device/memory and temperature responsibilities.
4. Checked native counts, nulls, types, layouts, units, identities, elapsed time and scalar meanings; retained the public snapshot schema.
5. Kept per-field failures explicit with operation/key context; no credentials enter source or output.
6. Loads native APIs from fixed system paths; no monitoring wrappers or remote production calls.
7. Clears invalid baselines and absent devices; re-enumerates and retries optional sources each capture.
8. Uses bounded loops and scoped native ownership inside the existing one-slot worker pipeline.
9. Maintains the working-state list above; native final verification remains in progress.
10. Exercises arithmetic, lifecycle, failure/recovery, attribution and worker ownership; records actual native commands and logs separately.
11. Distinguishes preliminary compile/run evidence from native accuracy and untested hardware profiles.
12. Escalated ambiguous SMC semantics and followed the documented resolution without inventing a hardware flag.
13. Reviewed these rules and corrected the known scalar/native-warning findings; final native validation remains the delivery gate.
14. Uses source names, physical units and explicit limitation text in the capability record.
