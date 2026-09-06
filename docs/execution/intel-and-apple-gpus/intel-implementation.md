# Intel Linux implementation

Native Intel accuracy remains **unverified**: this development host has AMD hardware. The implementation is a candidate for independent review, not acceptance of GPU-008 or completion of the broader commitment.

## Work tracking

- Complete: physical PCI discovery, alias handling and host integration, with observed red/green tests.
- Complete: independent sysfs fields, checked units, package scope and energy recovery tests.
- Complete: bounded i915/xe DRM region and engine queries, memory semantics and malformed-response tests.
- Complete: direct engine PMU and attributable integrated RAPL collection, retry, baseline and lifecycle tests.
- Complete: collector suite, formatting, strict Clippy, C layout comparison and implementation self-audit.
- In progress: handoff for independent SPEC review followed by independent QUALITY review, owned by root orchestration.

No independent review has been self-approved. No native Intel/full-workspace acceptance or Cairn aggregate was run in this task.

## Verification actually performed

| Command or case | Observed result |
| --- | --- |
| Required exact host discovery command before production edits | 0 passed, **1 failed**, 42 filtered out. Assertion reported zero GPU monitors where one Intel monitor was required. |
| Same exact discovery command after implementation | **1 passed**, 42 filtered out. |
| Initial sysfs Intel host group | 1 passed, **3 failed** for missing fields, then **4 passed**. |
| Initial DRM decode cases | 1 passed, **3 failed** for missing decoding, then **4 passed**. |
| Memory publication, native query buffer, PMU arithmetic/configuration/retry, perf response, RAPL source and power arithmetic | Each implementation addition had an observed failing selection followed by a passing selection. |
| Self-audit regressions | Observed failures for transient identity loss, reused alias association, unbounded negative status negation, shared allocation tied to system capacity, missing-source reporting, proven vendor replacement, and incomplete inventory falsely establishing RAPL uniqueness. These cases pass in the final suite. |
| `rtk cargo test --locked -p system-pulse-collectors` | Final **69 passed** across three suites, zero failures. |
| `rtk cargo fmt -p system-pulse-collectors -- --check` | Final exit 0. An earlier check correctly reported unfinished formatting; rustfmt was applied. |
| `rtk cargo clippy --locked -p system-pulse-collectors --all-targets -- -D warnings` | Final exit 0, no issues. Initial four collapsible-if findings were fixed. |
| `rtk git diff --check` | Exit 0. |
| Independent C UAPI layout check on x86-64 | Exit 0 after removing the kernel-only `__user` annotation with `-D__user=`. Query/region/engine sizes, selected offsets and ioctl constants matched. This is compile evidence, not Intel hardware evidence. |

Required first red/green command:

```sh
rtk cargo test --locked -p system-pulse-collectors --lib host::tests::intel_pci_device_is_discovered_without_card_index_identity -- --exact
```

A RAPL test command initially combined a module filter with `--exact` and executed zero tests. That run is not evidence. It was immediately replaced with the full test name, which executed one failing test before the implementation and passed afterward.

## Implementation self-audit

Reviewed against the agreed GPU scope and the imported production rules. Changes stay in the collector, focused integration tests, the Linux native dependency entry and these records. Existing AMD/NVIDIA source and the background service are unchanged. Tests exercise mixed-vendor snapshots and the existing vendor suites passed.

Boundary checks reject malformed sizes, counts, reserved data, duplicate identities and unknown units. Native handles are owned, capped by bounded discovery, retried after failure and dropped on proven disappearance. Current readings retain original operands, source scope and query windows. i915 restricted/old-kernel equality does not become zero usage; xe shared bytes do not become a system-RAM capacity. Package, GT, card and RAPL PP1 meanings remain explicit.

Revisions found during this self-audit were made and verified before handoff. The remaining limitations are source/hardware evidence boundaries, documented in the [source and capability record](intel-sources-and-capabilities.md): Intel native accuracy is pending; i915 equal-free accounting is ambiguous; integrated xe/multi-domain RAPL attribution is not claimed. No Sysman dependency was needed.

The broad source decision and commitment remain open. Root owns independent SPEC/QUALITY review, subsequent platform integration, committed Cairn evidence and native acceptance.
