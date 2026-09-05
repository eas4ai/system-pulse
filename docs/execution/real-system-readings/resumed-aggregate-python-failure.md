# Resumed aggregate: decoder diagnostic regression

Candidate: `0831810e` (reviewed implementation `5da24b21`).
Artifacts: `/tmp/system-pulse-cairn-check-d2a1yxmf/system-pulse-acceptance-0i3ml8_m`.
Result: FAIL. Source guard passed; 77 Python tests passed and one failed.
No Rust suite, host capture, or native replay ran in this attempt.

The failing test expected the diagnostic to contain `recursion` for a deeply
nested JSON array. The aggregate interpreter decoded an array, and the validator
correctly rejected its shape instead: `Unverified requirement evidence: unknown
native result shape`. The failure was the test's diagnostic assertion, not a
successful acceptance of malformed evidence. Root probes with system Python
3.14.4 and Brew Python 3.14.7 both decoded that payload as a list. The earlier
passing worker command used `python`, resolving to Miniconda CPython 3.13.12;
the aggregate uses `python3`, resolving to Brew CPython 3.14.7. The worker
reproduced the sole regression failure with that exact aggregate executable.

Retain the real-payload fail-closed test without requiring decoder-specific
wording. Separately inject `RecursionError` at the native result read boundary to
verify original exception preservation and the three host-only passes under
all interpreters. Verify using the exact aggregate interpreter before another
Cairn check. No production validator relaxation is authorized or needed.

Cairn's documented zero-result compatibility fallback recorded all thirteen
requirements as failed, because the run earned no requirement verdicts before
the Python stop. It then named LIVE-002 for escalation. The already answered
escalation covered the shared acceptance rerun but named only LIVE-001; root
corrected its Concerns field to the full shared set, preserving its original
question, answer and timestamps, with the developer's current go-ahead quoted.
Cairn then named `implement LIVE-001`. This records an approval-scope correction,
not a new developer answer or a new permission request.

Failed receipts and logs are preserved. Acceptance remains incomplete.

SHA-256:

- `python.log`: `40a7a5c35c5f1938339834bbe4df8c0dccdd0fbec1a4e48e0c99fcd0b89742a3`
- `failure.json`: `ab252583b01459ba131573f15e486f96e82eff136d6368c47241b40cdec0f75c`

## Corrected test evidence

Candidate `eac95a14db8eb5ebff183bc64d3a9af302e634e6` changes only the
regression and its report. Both Python 3.14.7 (the actual aggregate executable)
and Miniconda Python 3.13.12 passed 28 focused and all 79 Python tests.
Independent SPEC then QUALITY each ran the two affected tests on the exact
Brew Python 3.14.7 executable and passed. Both confirm cumulative approval;
production validator and evidence producers are unchanged.

Fresh complete acceptance remains pending.
