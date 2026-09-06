# Full Python suite budget correction

Status: correction committed at `61e8ceef`; independent [SPEC and QUALITY reviews passed](linux-python-budget-reviews.md). This is not full preservation or Cairn acceptance.

## Work tracking

- Done: changed the single complete-suite execution budget and ran its exact stage through the real runner.
- Done: focused aggregate checks, affected lint/format, source/evidence binding and all 14 self-audit rules.
- Done: focused commit and independent specification and quality reviews.
- In progress: Task 5 full preservation and remaining native evidence.

## Change and cause

The [recorded finding](linux-python-budget-finding.md) and [Judged decision](../../decisions/bound-the-complete-python-suite-with-its-measured-runtime.md) precede this correction at `906c9f611b1875b1fab9f1f3b7026856c90d6756`. The original aggregate timed out at 30.003 seconds; two retained successful 444-test runs took 34.043 and 34.240 seconds. Only the complete Python suite execution budget in `acceptance.main` changes from 30 to 60 seconds. Exact discovery, mandatory coverage, nonempty-count validation, failure propagation, child cleanup and every individual/native operation bound remain unchanged. No numeric-constant test was added.

## Verification

An external development harness extracts and executes the actual Python `runner.step` call from `acceptance.main` with a real `acceptance.Runner`. It retains the source hash, source call, actual command, 60-second budget, process PID and result. The exact stage command is:

```sh
rtk proxy /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py' -v
```

All **444 tests passed**. Runner recorded **34.573 seconds**, exit **0**, `timed_out=false`, and a nonempty count of 444 from the original combined log. Child PID 1212286 was reaped and its group was absent; outer owner PID 1212267 also exited 0 and was reaped/absent. The original log SHA-256 is `0d2cb346cba5720428696c9b795c1645a61699d167b2a2cdee1f51bace7beecf`.

Focused `test_acceptance.py` and `test_gpu_aggregate.py` checks passed 7 and 6 methods respectively, including timeout cleanup, nonempty selection and mandatory-stage rejection. These methods are also part of the 444-test full suite; counts are not added as distinct coverage. Ruff lint and format checks passed for `acceptance.py`; diff whitespace passed. No Rust build/test, native workload, Mac connection or full preservation rerun was performed.

Original artifacts live at `/home/shawn/workspace2/task-manager-artifacts/gpu-task5/linux-python-budget-correction-20260906`. The [structured correction record](linux-python-budget-correction.json) binds exact commands, lifecycle/stream hashes, the measured runner stage and artifact manifest. The historical failure's 11 originals and the unchanged timing diagnostic were rehashed successfully. Failed preservation and the original Linux freshness failures remain unresolved. Mac F1 and missing Intel/Apple hardware evidence remain pending. No decision realization or acceptance receipt was written.
