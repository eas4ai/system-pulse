# Process observation proposal

Status: Draft — developer decision required. The agreed specification is unchanged.

## Problem

The current plan requires independent before/after counter observations for every collector observation. The latest [failed capture](host-process-exit-gap.md) includes a process that exited after the collector read it and before the next independent read. Its fast sampling remained active. A later counter value cannot be recovered from ENOENT, even when an earlier value matches.

## Proposed boundary

Keep exact source, PID/start identity, unit, normalization and counter arithmetic checks for every available process reading. Keep mandatory successful independent brackets for non-process counters and a controlled live child workload whose lifetime covers the capture. Predeclare that workload and required comparisons before running; do not select a successful subset afterward.

For other real processes, attempt the same independent comparisons and retain all observations. Only an independently documented identity exit may explain a missing after-counter bracket. Retain its raw readings, query windows and terminal stat evidence, and label the missing comparison unverified. Do not estimate the absent value, count it as a successful comparison, or change the numeric bounds. Census absence alone is insufficient terminal evidence; permission errors, identity ambiguity, missing before observations and unexplained gaps still block acceptance.

The aggregate may complete with these explicitly disclosed exited-process coverage gaps if the predeclared controlled workload and every other mandatory comparison pass. This is a change to the acceptance evidence boundary, not a claim that those unobserved values were verified. Add regression tests that reject fabricated values, surviving-process gaps, permission failures and ambiguous PID reuse, and distinguish proven exit from those failures.

## Scope and alternatives

This proposal changes only how independently proven process exit affects host acceptance. It does not change production collection, process visibility, native exit verification, or metric semantics. Independent SPEC and QUALITY review and fresh host/native acceptance remain required.

The alternative is to retain the universal bracket condition and leave acceptance blocked whenever an uncontrolled process exits in the observation gap. Another blind rerun may pass under quieter conditions, but cannot establish that the observer handles the same exit reliably. Seeding every initial process into faster sampling also increases the existing 4,096-observation budget pressure and does not remove the gap.

No code or agreed requirement has been changed to implement this proposal.
