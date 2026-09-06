# GPU acceptance F10 specification re-review

Status: **Historical finding at `eccf56b7`.** The [final specification pass](gpu-acceptance-spec-pass.md)
closes F10 at `50ea29d6`; F1–F9 remain closed. Independent
read-only review of `eccf56b7e5cb34c8a5103cbc36d9583c1383d6dc` found a remaining
Intel provider identity mismatch. This record precedes its correction. Quality
review has not started. The [structured record](gpu-acceptance-f10-spec-review.json)
retains the finding, reproduction, verified portions and original manifest.
Root independently verified all 3,311 external artifact size/hash records.

## F10 — P2: reconcile Intel provider identity with independent inventory

In [gpu_provenance.py](../../../scripts/system-pulse/gpu_provenance.py), line 421,
`host_facts` compares metadata and `inventory.discovery` by monitor-ID set only.
Lines 433–435 then validate each metadata identity against discovery replayed from
that same metadata's nested sysfs. The full returned identity is reconciled with
other copies of host metadata, but not with independent inventory identities.

| Individually corrupted metadata | Independent evidence retained unchanged | Full ingestion outcome |
| --- | --- | --- |
| PCI `0000:01:00.0`, device ID `0x9999` | Inventory device ID `0x1234`, Vulkan device ID 4660 | GPU-008 earned |
| Same PCI, driver `i915`, matching nested driver/DRM/module facts | Independent inventory and raw field sources use `xe` | GPU-008 earned |

Each mutation changes and consistently rehashes all affected host-metadata
originals, owned stdout/completion records and nested observer copies. It preserves
the independent discovery, field operands, policy, consumed values, native actions
and Vulkan work. Both complete Intel and Apple controls pass through the unmodified
`verify_host` route. These are synthetic verifier reports with all 711 actual
committed inputs, not native hardware evidence.

GPU-008 requires provider versions for the actual physical device; GPU-009 rejects
wrong identity/source evidence. Join each metadata provider to its corresponding
independent `inventory.discovery` entry across `pci`, `driver`, `physical_path`,
`monitor_id`, `vendor` and `device_id`. Apply this to the complete physical inventory
while preserving aliases and order independence. Add both full-route rejection
regressions with consistent hashes and restored positive controls.

## Verified scope and retained reproduction

The original missing-host and missing-version attacks now reject. Analogous Apple
registry, lookup, name, kernel-identifier and shared-image attacks reject. The
reviewer passed 56 GPU tests, all seven mandatory development groups, and 24
affected regression cases. F7–F9 ownership, command and completed-work protections
remain intact; F1–F6 implementations are unchanged and their tests ran again.
All 60 reviewed candidate files stayed unchanged. The 20 native helper readiness
originals also verified, without any new native or GUI run.

The complete external record is `gpu-task4/spec-review/f10-eccf56b7/review.md`.
Its `replay-retained-findings.py` invokes unmodified full ingestion on four retained
reports: Intel and Apple positives, wrong Intel device ID and wrong Intel driver.
All four currently accept. The standalone offending reports and original stream
hashes remain in that directory. Exit zero from this replay denotes a successful
defect reproduction. F10 must close before quality review; the missing hardware
matrix and original Linux preservation failures remain pending.
