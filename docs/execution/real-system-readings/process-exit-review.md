# Process-exit acceptance review

## Candidates

Agreed contract and initial mechanism review: `87f40f22`.
Implementation: `37bc9c37`.
User-requested linker configuration: `6e6963b3`.
First review correction: `9e12415cebb77e9989fe13a73c46b275585e59e7`.

## SPEC review

The first review passed 61 focused tests but found two important false acceptances: aggregate replay skipped retained controlled-child obligations, and an invalid terminal window could prove exit. These findings were recorded before correction in the commitment review. The linker configuration preserved the Windows stack flag, native library search path, and declared-input tracking.

The correction shares controlled-child appearance and exit validators between capture and replay, requires complete child artifacts, and validates integer ordered observation windows. Independent SPEC re-review passed 65 focused tests and reran the original probes: missing/contradictory child evidence and reversed terminal timing now reject, while complete retained evidence still passes. Existing arithmetic bounds and observation budgets remain unchanged. No specification blocker remained.

## QUALITY review

Independent QUALITY review passed with no actionable findings. The reviewer ran 59 focused host/verifier tests plus all 28 reporter tests under exact Python 3.14. Eight additional negative probes rejected wrong or contradictory terminal evidence, permission failure, mismatched before source/identity, invalid query windows, and premature policy declaration. Diff checks passed. The review confirmed bounded retention, shared validators, separate unverified accounting, read-only replay and preserved numeric bounds.

Cumulative SPEC and QUALITY status is PASS at `9e12415cebb77e9989fe13a73c46b275585e59e7`. Fresh committed host/native acceptance and final commitment review remain pending. Focused unit checks and the separate successful lld build are not final acceptance evidence.
