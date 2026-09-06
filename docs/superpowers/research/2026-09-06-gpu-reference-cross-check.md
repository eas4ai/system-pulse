# GPU reference cross-check

The user added these snapshots during real-system-readings acceptance.
This is a focused local source comparison. None was built, launched or
modified, and no upstream-current or hardware-accuracy claim follows.

| Snapshot | Useful source evidence | System Pulse implication |
| --- | --- | --- |
| [nvglances](../../../reference/nvglances-master/src/metrics/gpu.rs) | NVML enumeration, utilization, VRAM, temperature, fan percentage, milliwatt power and MHz clocks; separate compute/graphics process queries. | The required physical metrics use the same NVML APIs in our adapter. Preserve floating-point unit conversion and each query's availability/error. This reference substitutes zero for several failed queries; that behavior is incompatible with the agreed unavailable-reading contract. |
| [amdgpu_top 0.11.5](../../../reference/amdgpu_top-0.11.5/crates/libamdgpu_top/src/stat/sensors.rs) | Optional edge/junction/memory temperatures, separate average/input power, fan RPM, and libdrm clock queries. Idle updates clear unavailable sensor options. | Confirms the distinctions already present in our hwmon descriptors. Its libdrm queries are concrete fallback references if a required field lacks a usable sysfs source on a target device. A fallback requires independent source/unit evidence before adoption. |
| [amdtop 0.2.6](../../../reference/amdtop-0.2.6/src/app.rs) | Rust frontend using pinned libamdgpu_top 0.11.5. Keeps a device record when its backend is absent, checks sleep state, and attempts activation when awake. | Useful for device lifetime and sleep/recovery behavior. It is a different project from the similarly named C snapshot below. |
| [amdtop 1.0.0](../../../reference/amdtop-1.0.0/src/extract_gpuinfo_amdgpu.c) | NVTOP-derived C implementation with libdrm sensor queries and per-field validity flags; includes a separate NVIDIA implementation. | Useful alternative source paths and validity handling. Its README limits the fork's tested hardware and warns about AMD PCIe readings; those readings are not evidence of accurate measurements on this host. |

## Comparison with the current adapters

[AMD collection](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/collectors/src/host/devices.rs)
uses unique ID or PCI identity, independent per-device VRAM, hwmon temperatures,
average and instantaneous power, graphics/memory clocks and measured fan RPM.
It retains the distinction between average SoC power and instantaneous board
power, and represents inaccessible sources explicitly.

[NVIDIA collection](/home/shawn/workspace2/task-manager-worktrees/workspace-visibility/examples/system_pulse/collectors/src/nvidia.rs)
uses GPU UUID, timed NVML queries, byte VRAM, Celsius temperature, milliwatts
to watts and MHz to Hz. Fan percentage and intended RPM are separate sensors.
Initialization, unsupported calls and device loss preserve error evidence.
NVIDIA backend tests exist; live NVIDIA hardware remains unverified on this
AMD host. The new source examples do not change that verification status.

The focused comparison found no reason to replace the current adapters or
change the active publication tracing task. Use these examples when a concrete
source, unit, availability or device-lifetime discrepancy appears. Extra
accelerator engines, per-process GPU attribution and PCIe controls do not enter
the current commitment merely because a reference implements them.

Reference license notices remain untouched. No third-party code was copied.
