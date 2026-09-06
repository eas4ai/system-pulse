# Apple collector implementation

## Working state

- Complete: pure conversion, failure, identity and service tests; 90 collector tests passed on Linux.
- In progress: native IOReport, Metal/IOKit, SMC/HID implementation and local verification.
- Pending: committed native compile/run, evidence, self-review and candidate delivery.

## Native source selection before implementation

The exact sources, units, channel IDs and ownership are recorded in [source probes](apple-source-probe.md) and [loaded operands](apple-loaded-source-probe.md). Bind directly to the probed Core Foundation, Metal, IOKit, IOReport and Objective-C C APIs. No monitoring command or network source is used in production. IOReport GPUPH format 2, encoded unit 72058115876454424 (24Mticks), and GPU Energy format 1, encoded unit 216173288919924736 (nJ), must name the enumerated Metal registry ID. Memory comes only from that registry entry's PerformanceStatistics. Persistence uses its physical IODeviceTree parent path, never the runtime registry ID. The pmgr voltage-states9 little-endian frequency/voltage table supplies P-state Hz only where pairing is proven.

Create/copy CF objects and IOReport output dictionaries are owned until released; borrowed entries are read only while their owners live. IOKit matching consumes its dictionary. Services, iterators, parents and SMC connections have scoped release. The existing worker owns all native state. Optional sources are queried independently and retried. The documented M1 SMC keys are Tg05 and Tg0D; inactive-value semantics are not established by the vendor; the explicitly recorded software plausibility policy below governs display. HID GPU MTR Temp Sensor is optional. System fan keys have no proven GPU attribution.

Use target-specific `libloading = =0.8.9`, already present in the workspace lock, to load IOReport and private HID symbols at runtime. A missing private API is a source capability failure with later retry; it must not prevent the application from loading. Stable public CF/IOKit/Metal APIs link as native frameworks. The SMC policy follows the [recorded decision](../../decisions/report-unvalidated-apple-smc-temperatures-as-unavailable.md): a conservative software guard below 15 Celsius preserves raw successful reads but withholds their displayed values. It may withhold real cold readings and is not a hardware validity bit.
