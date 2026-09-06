# Apple native source reconnaissance

Status: Observed on 2026-09-06. This is source reconnaissance on the authorized M1 Pro MacBook, not production collector accuracy or GPU acceptance.

The Mac reports arm64, macOS 26.6.1 (25G76), one Apple M1 Pro Metal device and unified memory. Keyed SSH works. The task-owned keep-awake process is PID 99002, `/usr/bin/caffeinate -i -s -t 14400`, started at approximately 08:58 UTC; it was checked again during these probes. The earlier authorized cleanup removed 23 stale Cargo output trees, increased free space by 129,593,520,128 bytes and preserved three source archives.

## Identity and attribution

`MTLCopyAllDevices` returned one device. Its `registryID`, 4294969787, resolves to `AGXAcceleratorG13X` through `IORegistryEntryIDMatching` and `IOServiceGetMatchingService`. The accelerator's `PerformanceStatistics` and the IOReport `GPU Energy` and `GPUPH` channels name that same registry driver ID. This establishes a direct association on this host; selecting an arbitrary accelerator or relying on its display name is unnecessary.

The registry ID is a runtime join key. Persistence should use the physical device-tree path obtained by following the accelerator's parent: `IODeviceTree:/arm-io/sgx@4000000`. Its accelerator path is `IOService:/AppleARMPE/arm-io/AppleT600xIO/sgx@4000000/AGXAcceleratorG13X`. Native re-enumeration and injected renumbering tests must preserve the physical path while replacing runtime handles and counter baselines when the registry instance changes.

Apple documents [Metal registry identity](https://developer.apple.com/documentation/metal/mtldevice/registryid) and [unified memory](https://developer.apple.com/documentation/metal/mtldevice/hasunifiedmemory). The installed native API supplied the actual paths and IDs above. IOKit matching dictionaries are consumed by matching calls; every returned service, parent and iterator needs `IOObjectRelease`. Metal's copied array owns the borrowed device references used during enumeration.

## Measured source inventory

| Field | Native observation | Implementation constraint |
| --- | --- | --- |
| Activity | IOReport group `GPU Stats`, subgroup `GPU Performance States`, channel `GPUPH`; format 2, unit `24Mticks`, driver ID 4294969787. States are `OFF`, then `P1` through `P15`. | Use checked per-state deltas. Active residency divided by total residency gives activity; do not substitute frequency scaling. Verify channel format, unit, identity and layout on each sample. |
| Frequency | `pmgr` property `voltage-states9` contains seven little-endian `(frequency, voltage)` pairs. Frequencies are 0, 388800000, 486000000, 648000000, 777600000, 972000000 and 1296000000 Hz. | Map `P1` through `P6` to the six active frequencies. Slots `P7` through `P15` were all zero in the retained observations. Do not silently discard residency in an unmapped slot. No active residency means active-weighted frequency is undefined. |
| Power | IOReport `Energy Model` / `GPU Energy`; format 1, unit `nJ`, channel ID 76202472785753, driver ID 4294969787. | Compute checked energy delta divided by measured elapsed time. Retain both raw energy observations and query windows. This channel directly matches the Metal accelerator. |
| Other energy channels | `GPU0` and `GPU SRAM0` are `mJ` channels from PMGR driver ID 4294968421. | Do not add these to `GPU Energy` or double-count them. They are distinct source records; SRAM energy is not memory allocation. |
| GPU memory | The matched accelerator exposes `Alloc system memory` and `In use system memory`. One retained sample reports 734461952 and 222199808 bytes respectively. | Publish separately labeled allocation and in-use byte readings with GPU shared-memory scope. Neither has a supported capacity total. Do not substitute system RAM or Metal's process-resource allocation. |
| SMC temperature candidates | `Tg04`, `Tg05`, `Tg0C`, `Tg0D`, type `flt `, four-byte little-endian values. Idle observations decoded to 0, approximately 9.2, 0 and approximately 9.2. | These values require attribution and load validation. A `Tg` prefix alone is a reference-program convention, not proof of a reliable GPU-die temperature. Do not average missing or invalid readings into zero. |
| HID temperature | 64 temperature services were visible. None had the reference program's `GPU MTR Temp Sensor` product name. | Record absence of an attributable GPU source independently from SMC availability. Do not relabel PMU or battery sensors as GPU temperature. |
| Fan | SMC `F0Ac` and `F1Ac` were readable floats and both returned zero in this idle probe. | These are system fan observations. GPU attribution was not established; do not invent a GPU fan reading. |

The native getters `IOReportChannelGetFormat`, `IOReportChannelGetDriverID`, `IOReportChannelGetChannelID` and `IOReportChannelGetUnit` were present and their outputs agreed with the serialized channel metadata. Apple's [IOReport types](https://github.com/apple-oss-distributions/xnu/blob/main/iokit/IOKit/IOReportTypes.h) define format 1 as simple integer data, format 2 as state data, state ticks in their local timebase, and the encoded quantity/unit fields. The implementation should validate these facts before interpreting channel values.

A separate maintained [Stats sensor table](https://github.com/exelban/stats/blob/6ef61b71de53eab400f811456ddeac5bef631308/Modules/Sensors/values.swift#L371) identifies `Tg05` and `Tg0D` as M1-generation GPU temperature sensors. It does not identify the observed zero-valued `Tg04` and `Tg0C` candidates in that table. This narrows the attribution lead; load validation of the approximately 9.2 readings is still required.

The retained idle pairs advanced only `OFF` residency and left the energy counters unchanged. That is consistent with an idle GPU. A subsequent [bounded Metal source probe](apple-loaded-source-probe.md) observed active residency, energy and responding temperature keys under load. Production accuracy and idle temperature validity remain to be established.

## Ownership and boundary checks

Use independent IOReport, accelerator-memory, SMC and HID outcomes. Failure of one source must not disable the others or prevent later retry. A failed/reset/changed channel invalidates its previous sample before a later rate is calculated. Native handles belong to the existing sampling worker.

IOReport copy/create results are owned Core Foundation objects. Keep the actual subscription output dictionary, sample dictionaries and subscription alive as required, and release them on every path. Array members and dictionary values are borrowed. Check null pointers, Core Foundation type IDs, bounded counts, native return codes and response sizes before reading data. The probe bounded channel enumeration, state counts, registry ancestry, SMC key counts and total execution time. Production needs equivalent explicit bounds and deterministic failure tests.

The SMC request layout was 80 bytes on this arm64 host. Read commands 9 (key metadata), 8 (indexed key name) and 5 (value) succeeded; the probe checked method return, response size, result and status. No write or fan-control command was used. All SMC connections and Core Foundation/IOKit handles were released by the probes.

For HID, Apple's [client wrapper](https://raw.githubusercontent.com/apple-oss-distributions/IOHIDFamily/main/HID/HIDEventSystemClient.m) confirms create/copy ownership and direct matching/service enumeration. The private C boundary still needs native compilation and failure tests; a reference declaration alone does not prove ABI or permission behavior across macOS releases.

## Source leads and retained evidence

The supplied MIT [macmon native sources](../../../../../task-manager/reference/macmon-0.8.2/src_lib/sources.rs:144), [frequency-table decoder](../../../../../task-manager/reference/macmon-0.8.2/src_lib/sources.rs:480), [temperature selection](../../../../../task-manager/reference/macmon-0.8.2/src_lib/metrics.rs:312), and [HardwareVisualizer memory reader](../../../../../task-manager/reference/HardwareVisualizer-1.10.1/core/src/infrastructure/providers/macos/io_kit/iokit_info.rs:327) informed these probes. Preserve notices for adapted code. The application must use native interfaces directly, not invoke those monitoring CLIs or inherit their zero defaults, unchecked layouts or arbitrary device selection.

The [source inventory and artifact manifest](apple-source-probe.json) retain the four raw JSON captures. Probe scripts, stdout, stderr and SHA-256/size manifest are also retained outside the checkout at `/home/shawn/workspace2/task-manager-artifacts/gpu-recon/manifest.json`. Twelve declared script/output artifacts cover IOReport metadata/raw samples, Metal/registry/DVFS/memory, SMC and HID. All four retained probe commands exited zero. The manifest SHA-256 is `de2ee3df6ae11fe07c904290d4345ead5ede2983fb8797811c0fa8a6702166ef`; these observations are not Cairn pass receipts.

Desktop preflight found console user 501 and accessibility trust available to the SSH-launched probe. Screen-capture preflight returned false. Actual application launch, visible labels/interactions and capture permissions remain to be established during native validation. The later source probe exercised a controlled GPU load and confirmed its process exited.
