# Host GPU preflight

Read-only probe, 2026-09-04. Two AMD Radeon AI PRO R9700 devices use amdgpu, PCI vendor/device 1002:7551, subsystem1458:242f.

| Physical identity | Discovery |
| --- | --- |
| amdgpu:5e741f6f7b767945 | PCI0000:03:00.0; card1 |
| amdgpu:0f772d80b40ac56f | PCI0000:06:00.0; card0 |

Identity comes from device/unique_id, not card or hwmon enumeration. All required measurements were readable without privilege: gpu_busy_percent (%); mem_info_vram_used/total (bytes); hwmon temp*_input (m°C); power1_average (µW); freq*_input (Hz); fan1_input (RPM). Discover hwmon dynamically and retain labels. Average power is average SoC power, not instantaneous board power. Zero graphics clock is valid in deep sleep.

power1_input is absent; instantaneous power is unsupported by that interface. fan1_enable returns EINVAL, but RPM works. serial_number/product_name are absent, while unique_id works. No required measurement returned permission denial. NVIDIA hardware was not discovered; nvidia-smi is absent and installed NVML initialization reports Driver Not Loaded.

Sources: [identity](https://docs.kernel.org/gpu/amdgpu/driver-misc.html), [sensor units](https://docs.kernel.org/gpu/amdgpu/thermal.html), [DRM client accounting limits](https://docs.kernel.org/gpu/drm-usage-stats.html). Generic client fdinfo is not proof of complete device-wide utilization or VRAM accounting.

This probe establishes accessible sources. It is not collector or app acceptance evidence.
