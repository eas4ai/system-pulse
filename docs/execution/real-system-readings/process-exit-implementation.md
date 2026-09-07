# Process-exit evidence implementation

Implemented the approved [LIVE-013 process-exit policy](../../spec/live-collection.md#process-exit-observation-policy). This is source and verifier-test evidence. Independent review and fresh host/native acceptance remain required.

## Capture and classification

`scripts/system-pulse/process_evidence.py` declares the owned child's PID/start identity and mandatory CPU utime/stime and read/write counter operands. `host_capture.py` writes `process-policy.json` before opening the collector gate and retains the gate timestamp. The initial controlled sample may contain the collector's exact one-operand warmup state and reason. Later controlled samples require Available readings with two operands. Every controlled operand requires its own independent bracket, including the initial warmup operand.

An ordinary process may have a missing after-counter comparison labeled `unverified_exit_gap` only with a matched before observation, an observed lower bound that contains the collector value, and later terminal stat ENOENT/ESRCH evidence with consistent identity. Attempts from ordinary and supplemental reads are assessed by their actual times. Relevant permission errors, conflicting PID/start identity, terminal observations before the query, or successful stat reads after terminal evidence prevent that classification. Census absence supplies no exit proof. Missing before observations, non-process gaps, controlled-child gaps, and known out-of-bound counters still fail.

The observer remembers ordinary process identities. At the next ordinary census, a missing previously observed PID enters the existing supplemental terminal-observation path. A retained terminal stat read retires it. This does not seed every initial PID into supplemental reads or add another loop or thread. The existing 20 ms supplemental schedule, 35-second deadline, 2,048 full-sweep cap and 4,096 supplemental-read cap remain unchanged.

## Retained evidence and aggregate acceptance

The existing artifact manifest now also requires:

- `process-policy.json`: the declaration made before the collector gate opens.
- `process-coverage.json`: every controlled snapshot/field's required and verified bracket counts, plus separate verified, failed and unverified totals.
- `unverified-exit-gaps.json`: raw collector queries, source and identity, independent attempts and windows, matched before evidence and terminal stat proof. It contains no invented after counter or upper bound.

`counter-brackets.json` contains only verified comparisons. `missing-brackets.json` retains unexplained failures. Aggregate acceptance reconstructs the observer from retained artifacts and runs the same `verify_capture` logic, then compares the retained summaries, classifications, coverage and bracket artifacts against that replay. This is read-only. A retained FAIL is rejected before replay and is never rewritten or promoted. Existing artifacts and all 13 requirement-reporting semantics remain required.

Independent SPEC review found two gaps in the initial implementation: replay did not enforce all retained child obligations, and exit classification accepted reversed terminal windows. The correction shares the child identity, appearance, name, RSS, threads and user checks between capture and replay. `child.json` must contain the matching snapshot rows, accessible before/after identity evidence, the owned exit code, and an actual terminal stat observation. Replay also checks that the after observation follows capture completion. Census absence in the post-exit snapshot remains required alongside terminal proof. Process query, counter and attempt windows must contain ordered integer timestamps; booleans and floating-point timestamps fail.

## Verification

The exact gate interpreter was `/home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14`, always with `-B`. The original 108-test suite passed before implementation. RED runs demonstrated the missing exit classification, lower-bound enforcement, controlled availability coverage, ordinary-only terminal retention and aggregate artifact validation. Further RED/GREEN cases covered IO permission timing, early terminal evidence, conflicting retained identity and malformed policy types.

Final executed checks:

- Full Python discovery after the SPEC correction: 130 tests passed.
- Focused exit-policy, coverage-gate, supplemental-observer and requirement-reporting suites: 61 tests passed.
- Ruff check: passed on the eight initially touched Python files and the four changed by the SPEC correction.
- `git diff --check`: passed before commit.

Synthetic dictionaries remain confined to verifier tests. No Rust build, live host capture, native run or Cairn mechanism was run for this implementation step. Existing child appearance, RSS, threads, user and disappearance checks remain in place. This implementation claims no new hardware accuracy and does not change any retained failed capture.

## Production self-audit

Reviewed the correction against all 14 production rules: the approved scope and evidence boundaries are preserved; shared validators keep capture and replay consistent; capture resources remain bounded; aggregate input failures remain failures; original artifact requirements and reporting are preserved; and tests cover the permitted case and disallowed gaps. Both SPEC findings have reproducing RED/GREEN regressions. No known source defect remains from this self-audit. Independent re-review and committed-tree acceptance are still pending.
