# Detect Intel Windows GPU and expose available energy and thermal readings

Surfaced from: WUAC-005
Captured: 2026-09-11T10:21:53.093Z

The developer reports missing GPU, Energy and Thermals on the Windows i7-1250U/Iris Xe host. Win32_VideoController identifies Intel Iris Xe with healthy driver 32.0.101.6881. Current and preserved snapshots contain no GPU or energy sensors, NVML cannot load on this non-NVIDIA host, and sysinfo Components reports no temperature providers. HostCollector enables Intel only on Linux. Diagnose supported Windows sources and implement accurate device detection, physical readings and explicit unsupported reasons under a developer-named collector commitment; do not substitute simulated data. This is separate from completing current UAC acceptance.
