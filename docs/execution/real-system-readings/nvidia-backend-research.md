# NVIDIA backend and evidence boundary

The developer explicitly requested NVIDIA support on 2026-09-04. The current host has two AMD GPUs and no NVIDIA device. This note defines implementation inputs, not a hardware acceptance result.

Use optional-runtime NVML initialization so missing libraries or drivers leave other host collectors operational. Published `nvml-wrapper 0.13.0` uses dynamic loading, supports Rust 1.60, and is MIT/Apache-2.0 licensed. Its `libloading` dependency is compatible with the existing locked 0.8.9. Retain one successfully initialized `Nvml`; borrowed device handles cannot outlive it. Persist `nvidia:<UUID>`, never enumeration index.

| Field | API and raw unit | Meaning |
| --- | --- | --- |
| Utilization | `utilization_rates().gpu`, percent | GPU activity; `.memory` is memory activity, not VRAM allocation. |
| VRAM | `memory_info().used/total`, bytes | Memory v2 API; a missing older-driver symbol is an explicit per-field error. |
| Temperature | `temperature(TemperatureSensor::Gpu)`, Celsius | GPU temperature. |
| Power | `power_usage()`, milliwatts | Convert to watts; do not universally label instantaneous. NVIDIA documents averaging on applicable architectures. |
| Clocks | `clock_info(Clock::Graphics/Memory)`, MHz | Convert explicitly if the shared physical schema stores Hz. |
| Fan percent | `fan_speed(index)`, percent | Intended speed; may exceed 100; not measured RPM. |
| Fan RPM | `fan_speed_rpm(index)`, RPM | Independently optional intended RPM; do not merge units into the percent series. |

Tests inject the NVML boundary for initialization and symbol failures, zero/multiple/reordered devices, UUID failure, per-field permission/unsupported status, GPU loss and recovery, valid zero measurements, and unit conversions. Missing device UUID must not create a fake index-based identity. Any failed field retains its source and reason without turning into a successful zero. The absence-path test on this machine is distinct from these deterministic adapter tests.

Live NVIDIA accuracy remains unverified until a real NVIDIA host runs the diagnostic and native acceptance procedure. This limitation does not excuse an absent adapter or omitted tests.

Sources checked during implementation planning: [wrapper API](https://docs.rs/nvml-wrapper/0.13.0/nvml_wrapper/device/struct.Device.html), [initialization](https://docs.rs/nvml-wrapper/0.13.0/nvml_wrapper/), [error variants](https://docs.rs/nvml-wrapper/0.13.0/nvml_wrapper/error/enum.NvmlError.html), and [NVIDIA device queries](https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html).
