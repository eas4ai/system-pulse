# Intel Linux implementation

Native Intel accuracy remains **unverified**: this development host has AMD hardware. The implementation is a candidate for independent review, not acceptance of GPU-008 or completion of the broader commitment.

## Work tracking

- Complete: physical PCI discovery, alias handling and host integration, with observed red/green tests.
- Complete: independent sysfs fields, checked units, package scope and energy recovery tests.
- Complete: bounded i915/xe DRM region and engine queries, memory semantics and malformed-response tests.
- Complete: direct engine PMU and attributable integrated RAPL collection, retry, baseline and lifecycle tests.
- Complete: collector suite, formatting, strict Clippy, C layout comparison and implementation self-audit.
- Complete: SPEC F1 hwmon identity regression failed as expected, then both hwmon tests passed after correction.
- Complete: SPEC F2 initial and peer metadata regressions failed as expected, then all seven PMU tests passed after correction.
- Complete: SPEC F3 subset regression failed as expected; all seven DRM tests passed after operand validation.
- Complete: SPEC F4 incomplete-zone regression failed as expected; three powercap tests passed, including denied/missing identities.
- Complete: correction collector checks, formatting, strict Clippy and self-audit.
- Complete: first correction commit; independent re-review closed F1/F2/F4 and identified one remaining F3 complementary bound.
- Complete: remaining xe complementary-bound regression reproduced both invalid cases, then passed after correction; all 76 collector tests, formatting and strict Clippy passed.
- In progress: focused correction commit handoff for independent SPEC re-review (root-owned).

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
| `rtk cargo test --locked -p system-pulse-collectors` | Initial implementation: **69 passed** across three suites, zero failures. |
| `rtk cargo fmt -p system-pulse-collectors -- --check` | Final exit 0. An earlier check correctly reported unfinished formatting; rustfmt was applied. |
| `rtk cargo clippy --locked -p system-pulse-collectors --all-targets -- -D warnings` | Final exit 0, no issues. Initial four collapsible-if findings were fixed. |
| `rtk git diff --check` | Exit 0. |
| Independent C UAPI layout check on x86-64 | Exit 0 after removing the kernel-only `__user` annotation with `-D__user=`. Query/region/engine sizes, selected offsets and ioctl constants matched. This is compile evidence, not Intel hardware evidence. |

Required first red/green command:

```sh
rtk cargo test --locked -p system-pulse-collectors --lib host::tests::intel_pci_device_is_discovered_without_card_index_identity -- --exact
```

A RAPL test command initially combined a module filter with `--exact` and executed zero tests. That run is not evidence. It was immediately replaced with the full test name, which executed one failing test before the implementation and passed afterward.

## SPEC-review correction evidence

The independent review record remains unchanged. All four reported falsifiers were reproduced before their corrections:

| Finding | Observed RED | Corrected behavior and focused verification |
| --- | --- | --- |
| F1 retained hwmon identity | Old `i915` whole-card energy published **2 W** after its path became `i915_gt0`. | Fresh provider/channel authorization rejects replacement, missing/malformed names and duplicate providers. Both hwmon tests pass, including recovery warming. A further observed RED showed that an unreadable peer could falsely establish uniqueness; incomplete provider inventories now invalidate hwmon bindings too. |
| F2 PMU discovery coupling | Two failed tests: malformed peer metadata removed the valid engine, and initial malformed discovery reported unavailable. | Seven PMU tests pass. Per-event metadata failures preserve valid peer samples; malformed is failed and denied is unavailable. Injected denial covers both config and unit reads; known event identity survives and recovery warms up. |
| F3 memory subset | The i915 visible-used > whole-used response was accepted. | Seven DRM tests pass. i915 visible free and derived allocated bytes, and xe visible used bytes, must fit their whole local region. The regression covers rejection and valid equality for both drivers. |
| F4 incomplete powercap zones | An unreadable second package still allowed current PP1 power from the first. | Three powercap tests pass. Actual zone-name failures invalidate package/domain uniqueness; path-qualified errors survive, ordinary attribute files are skipped, and recovery warms up. Tests cover malformed bytes, missing identity and injected denial at both zone levels. |

The final correction checks ran successfully: `rtk cargo test --locked -p system-pulse-collectors` (**75 passed**, three suites), `rtk cargo fmt -p system-pulse-collectors -- --check`, `rtk cargo clippy --locked -p system-pulse-collectors --all-targets -- -D warnings`, and `rtk git diff --check`. An intermediate F3 edit landed in the publication function instead of the decoder and failed compilation; it was moved to the decoder before the seven DRM tests passed. That compiler failure is not counted as regression evidence.

Correction self-audit covered binding lifecycle, independent event metadata, preserved error classes, subset arithmetic before publication and complete uniqueness evidence. The subsequent independent review found that the xe complementary capacity bound was still missing; the first correction checks did not establish complete F3 coverage. Native Intel verification is still pending; neither these checks nor the correction commit accepts GPU-008.

## Second correction: xe non-visible capacity

The second independent review was committed before this correction in `8886c6f04f81f9ef709f674f33997b240e6db148`. Its record remains unchanged. The new regression evaluated both reported tuples `(total, used, visible total, visible used)`: `(16384, 4096, 16384, 0)` and `(16384, 12288, 8192, 0)`. The observed RED returned `[false, false]` for the expected rejection results `[true, true]` (one test failed, 74 filtered out).

The xe local-region decoder now also requires `used - visible_used <= total - visible_total`. Earlier operand bounds and short-circuit evaluation make both subtractions safe. The same regression then passed: both contradictory responses are rejected and `(16384, 12288, 8192, 4096)` is accepted with its original operands. This focused change leaves i915 accounting intact.

Verification actually ran after the correction: the focused regression passed; the complete collector suite passed **76 tests across three suites**; formatting check, strict Clippy with `-D warnings`, and `git diff --check` exited zero. Self-audit checked both complementary partition bounds, short-circuit subtraction safety, the valid boundary case and the narrow two-file change. Independent SPEC re-review remains required. Native Intel accuracy and GPU-008 remain unverified.

## Implementation self-audit

Reviewed against the agreed GPU scope and the imported production rules. Changes stay in the collector, focused integration tests, the Linux native dependency entry and these records. Existing AMD/NVIDIA source and the background service are unchanged. Tests exercise mixed-vendor snapshots and the existing vendor suites passed.

Boundary checks reject malformed sizes, counts, reserved data, duplicate identities and unknown units. Native handles are owned, capped by bounded discovery, retried after failure and dropped on proven disappearance. Current readings retain original operands, source scope and query windows. i915 restricted/old-kernel equality does not become zero usage; xe shared bytes do not become a system-RAM capacity. Package, GT, card and RAPL PP1 meanings remain explicit.

Revisions found during this self-audit were made and verified before handoff. The remaining limitations are source/hardware evidence boundaries, documented in the [source and capability record](intel-sources-and-capabilities.md): Intel native accuracy is pending; i915 equal-free accounting is ambiguous; integrated xe/multi-domain RAPL attribution is not claimed. No Sysman dependency was needed.

The broad source decision and commitment remain open. Root owns independent SPEC/QUALITY review, subsequent platform integration, committed Cairn evidence and native acceptance.
