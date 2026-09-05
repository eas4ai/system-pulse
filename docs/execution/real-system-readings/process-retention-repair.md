# Supplemental process retention repair

The observer now keeps a supplemental candidate on its prospective 20 ms
schedule after an ordinary census starts reading that PID. An ordinary or
supplemental `/stat` attempt must return ENOENT or ESRCH before the candidate
is retired. The complete read result is retained first, including `/io` errors.
Census absence, `/stat` permission errors, and any `/io` error do not retire it.

This implements
[the retention decision](../../decisions/retain-supplemental-process-observation-until-exit.md).
It changes only `Observer.refresh_processes_if_due` and
`Observer.capture_processes` in `scripts/system-pulse/host_capture.py`.
Every ordinary census member is still read. The PID set controls scheduling;
actual start ticks in each observation still control verifier identity matching.
Counter comparisons, baseline rules, the single thread, the 35-second deadline,
the 2048 full-sweep limit, and the 4096 supplemental-attempt limit are unchanged.
Actual delays and skipped schedule slots remain explicit.

## Evidence and scope

The prior failed host capture remains unchanged at
`/tmp/system-pulse-cairn-check-co3wh4lm/system-pulse-acceptance-e3kdpb2x/host`.
It missed four endpoints for PID 1322913, start ticks 69430231, sequence 4.
The last collector query ended at monotonic time 694302723635237.
Supplemental refresh 153 still enumerated the PID at
694302761921839–694302766398810, but the sampler had cleared its supplemental
eligibility when the PID joined a full census. No counter read occurred there.
Refresh 154 no longer enumerated it. This identifies a lost observation
opportunity; census presence does not prove which counters could have been read.
No values were inferred or inserted into that failed capture.

The change does not promise observation of every lifetime. A process may exit
before a needed counter read, or scheduling delays may leave a query unbracketed.
Births discovered only by an ordinary census still lack supplemental eligibility.
Long-lived retained candidates use more of the existing supplemental budget;
exhaustion still fails and preserves accumulated evidence. A fixed-timeline
retained-census estimate of 359 extra attempts, compared with 101 actual attempts
and at most 16 active candidates, is illustrative cost analysis only. It neither
predicts fresh cadence nor proves a successful counter bracket.

## Verification

Tests were written before the source change. The focused RED run executed 11
tests and reported 10 failure instances across handoff, terminal observation,
nonterminal errors, and retained-candidate bounds. Existing controls passed.
The GREEN run passed all 11 focused tests using the exact gate interpreter:

```sh
rtk proxy /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p test_supplemental_processes.py -v
rtk proxy /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py' -q
```

The final full Python run passed 86 tests under CPython 3.14.7. The seven added
tests cover retention across a full census with later supplemental-only stat/io
brackets, retirement after a retained supplemental or ordinary terminal read,
continued sampling after io errors or nonterminal stat errors, accumulated
evidence at the existing limits, and failure when an exit makes the counter
bracket unobservable. Existing PID-reuse tests still reject a changed start
identity. The cadence test now also checks actual finish times and skipped slots.

The deadline fixture expires during a census after one retained supplemental
read. The cap fixture begins at 4095 attempts, retains attempt 4096, then fails
before another attempt. Both keep earlier refreshes, the partial failure record,
and its closing anchor. The first full-suite run exposed an ordinary-read test
double without an errno field; checking retirement only for retained candidates
preserves that existing ordering contract without weakening observed error data.

The gate interpreter has no Black module. Existing Black 26.3.1 under Miniconda
Python 3.13.12 was used for formatting only. Unrelated formatting was reverted;
these scoped checks passed:

```sh
rtk proxy python -m black --check --line-ranges 436-501 scripts/system-pulse/host_capture.py
rtk proxy python -m black --check scripts/system-pulse/test_supplemental_processes.py
rtk git diff --check -- scripts/system-pulse/host_capture.py scripts/system-pulse/test_supplemental_processes.py docs/execution/real-system-readings/process-retention-repair.md
```

Self-review confirmed the source diff is confined to the two sampler methods.
`host_capture.py` is 1409 lines / 55402 bytes, nine lines larger than base
`204780f2`. The focused test file is 295 lines / 12757 bytes, 166 added lines.
No dependency, capture artifact, numerical verifier, or OS control path changed.
The implementation was checked against the imported production rules.

No live host capture, native scenario, full aggregate, or Cairn check was run by
the source implementer. Independent SPEC and QUALITY reviews and a fresh
committed aggregate remain required before host acceptance can be claimed.
