# Apple collector specification review

Status: SPEC PASS for Task 2 on 2026-09-06. No actionable findings.
Independent quality review may proceed. This is not commitment acceptance.

## Reviewed source

Reviewer: independent `apple_gpu_spec`, read-only.

- Base: `2eebd6a2e77509279606605bbf9ae30e0b2df62b`.
- Candidate: `a7518cbe077aa390e960926dd616dba4e386ae2a`.
- Native-tested collector: `df2300f2a6af5a9e6bf0ebe60d725379096c2b46`.

The reviewer independently compared all 12 changed collector, notice, manifest
and lock files across the native-tested commit, candidate and working tree.
They matched exactly. Root policy, comparison-procedure and plan-only commits
were separated from source review. The [implementation record](apple-implementation.md)
and [native evidence manifest](apple-native-implementation-evidence.json) identify
the changes and retained originals.

## Attacks and result

The reviewer checked Metal/IOKit association, stable physical identity,
ambiguity, instance changes and baseline eviction; same-device allocation and
in-use memory with scalar byte semantics; IOReport channel formats, units,
state layout, checked deltas, weighted frequency, raw operands and query timing.

Inspection covered CF/IOKit ownership, partial-return cleanup, subscription
output ownership and library/object destruction order. Optional SMC and HID
paths, exact thermal profiles, independent failures, fan attribution limits,
retry behavior and the minimal worker Send-bound correction were also checked.

The [adopted SMC policy](../../decisions/report-unvalidated-apple-smc-temperatures-as-unavailable.md)
was verified at the exact boundary, for negative finite values, raw retention,
failed reads, recovery and unaffected HID. Profile keys matched the pinned
Stats source; local macmon inspection confirmed GPU table frequencies in Hz.
No missing, extra or misunderstood requirement was found within Task 2.

## Independent verification

- `rtk cargo test --locked -p system-pulse-collectors`: 96 passed.
- All 42 retained local artifact byte counts and SHA-256 hashes matched.
- Independent Python arithmetic reconstructed 257 measured values and checked
  12 guarded temperatures across the complete 40-frame native capture. Expected
  values used original state deltas/table words, energy/timing, SMC bytes and
  memory integers; no production conversion function supplied the expectation.
- Original native test logs contained 44 passes and zero failures. Native
  build/check provenance was inspected.

Root separately confirmed those artifact hashes, regenerated the source archive
from the committed tree, checked unchanged collector/lock bytes and counted the
Linux/native test logs. Its external report is
`/home/shawn/workspace2/task-manager-artifacts/apple-collector/root-candidate-artifact-check.json`.

No source edit, commit, SSH session, workload or UI action occurred during the
independent review. These checks establish specification compliance and evidence
consistency for this collector task. External native accuracy, other Apple
hardware, sleep/wake, UI/persistence and aggregate acceptance remain pending.
