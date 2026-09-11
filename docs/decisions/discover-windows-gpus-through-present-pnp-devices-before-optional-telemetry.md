# Discover Windows GPUs through present PnP devices before optional telemetry

Level: Judged
Decided by: Codex
Rests on: WGPU-001
Would be wrong if: A healthy adapter disappears when telemetry fails, identities depend on order or runtime LUID, PCI matching merges different devices, shared memory is labeled VRAM, or native observations contradict the reported readings.

## Decision

Enumerate present Windows display-class devices through SetupAPI and key monitors by their complete PnP instance ID. Read the adapter LUID only for current native queries, never persistence. Collect optional Windows graphics scheduler node running times and resident segment bytes through the SDK D3DKMT bindings, following the separation illustrated by LibreHardwareMonitor. Scope utilization to the busiest observed engine and keep shared system memory distinct from dedicated GPU memory; unsupported queries remain explicit. D3DKMT statistics are a system-oriented interface, so keep them behind a small Windows boundary and require native comparison on the available Windows 11 host; discovery must survive failure. Reuse bounded counter derivation with baseline reset on LUID changes, failures and removal. Map optional NVIDIA telemetry to exactly one present NVIDIA PnP adapter using its PCI bus/device/function and NVML PCI domain zero; reject absent or ambiguous matches instead of matching names or indices. Keep NVML behavior unchanged on Linux/macOS. Bound native enumeration, node and segment counts, initialize all native buffers, close owned handles on every path, and never elevate or install sensor drivers. Verify fake vendor/multi-adapter/error boundaries, independent native WMI inventory, graphics readings and the packaged UI, plus current platform preservation. References informed API selection; retain notices if any source is adapted.

## Realized by

(none yet: recorded, not built)
