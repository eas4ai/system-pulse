# Verify Intel GPU load with a bounded native Vulkan helper

Level: Judged
Decided by: agent
Rests on: GPU-008/009 and the agreed Intel idle/load protocol; recorded F9 proves that the current mechanism accepts a correctly hashed zero-work command without selected-device work or measurement overlap.
Would be wrong if: The selected API cannot establish exact physical PCI identity and completed bounded GPU work, validation silently accepts unavailable prerequisites or nonoverlapping measurements, or the helper requires a production collector change or unrelated SDK upgrade.

## Decision

Use a small acceptance-only native Vulkan workload for Intel Linux captures. Match exactly one Vulkan physical device to the independently selected PCI domain/bus/device/function through VkPhysicalDevicePCIBusInfoPropertiesEXT; validate the native API and extension contract against retained primary-source/header evidence before implementation. Do not infer identity from a device name, ordinal, or an arbitrary workload command.

Use a fixed small device buffer, serial buffer-fill submissions and completed fences, with bounded duration, enumeration, allocations and an external process-group deadline. Retain the selected native device, source/binary hashes, exact command, query/work timing, submission/completion counts, errors and cleanup. Require independent measurements to overlap the actual completed-work interval. Apply the overlap requirement consistently to the existing Metal path without inventing a utilization-rise threshold.

Keep the helper outside production collection and include all new inputs in the GPU mechanism and native source transfer. Use available headers and loader facilities without an unrelated SDK or dependency-graph upgrade. Missing loader, headers, device or required identity extension is an explicit validation prerequisite failure and cannot satisfy native load acceptance; it does not reclassify a supported collector reading as unsupported. An arbitrary command or self-reported unbound receipt cannot replace verified workload implementation and execution provenance.

This corrects recorded Task 4 specification finding F9. The existing Task 4 implementer owns the focused helper and regressions, followed by independent specification re-review and then quality review. Actual Intel hardware accuracy remains unverified until the required hosts are measured.

## Realized by

(none yet: recorded, not built)
