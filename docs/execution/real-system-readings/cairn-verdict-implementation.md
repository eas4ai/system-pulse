# Cairn verdict adapter implementation

The adapter follows [the predeclared mapping](cairn-verdict-mapping.md).
`acceptance.py` shares host, primary native, remaining native, session, case and
automated-step checks between aggregate validation and partial reporting.
The existing artifact lists, dynamic GPU evidence, screenshot accounting and
aggregate checks remain mandatory. Normal native session cleanup now also requires
the single app process to have exit code zero and no remaining `/proc` entry.

Reporting happens after subprocess termination. Native progress records cannot
earn passes. A focused native result cannot earn either native group; independently
validated host evidence can still earn LIVE-004, LIVE-012 and LIVE-013.
Malformed, missing or failed evidence leaves the affected group omitted.
No free-text exception is translated into an individual requirement failure.

The exception path retains `failure.json` and re-raises the original aggregate
error after reporting earned host and primary requirements. Complete reporting
runs only after every aggregate check, manifest write and manifest hash succeeds.
Each earned requirement is emitted once. Output artifact schemas are unchanged.

## Verification

The initial focused regression run executed 15 tests with 12 expected failures
because the previous gate emitted no requirement lines. Shared validation made all
15 pass. Further checks cover malformed case fields, late native failure and the
termination boundary. An injected manifest hash failure first reproduced duplicate
verdict publication; moving complete publication after the aggregate success path
made that regression pass.

Final commands run from the repository root:

```sh
rtk proxy python -B -m unittest discover -s scripts/system-pulse -p test_requirement_verdicts.py -v
rtk proxy python -B -m unittest discover -s scripts/system-pulse -p 'test_*.py' -v
rtk proxy python -m black --check scripts/system-pulse/acceptance.py scripts/system-pulse/test_requirement_verdicts.py
rtk proxy python -B scripts/system-pulse/acceptance.py --source-guard
rtk git diff --check
```

Results: 22 focused tests passed; all 73 Python tests passed in 5.280 seconds;
Black, source guard and diff checks passed. Fixtures use temporary files and a
controlled `Runner.step`; aggregate artifact validation and manifest generation
run normally. These tests do not claim live measurements.

A read-only interpretation of the retained failed aggregate at
`/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb`
validated LIVE-001, LIVE-002, LIVE-003, LIVE-004, LIVE-005, LIVE-008, LIVE-009,
LIVE-011, LIVE-012 and LIVE-013. Its aggregate step check still failed on the
native process exit. No retained evidence was changed and no Cairn result was
published by that interpretation.

## Limits and release review

No live host capture, native replay, Cairn command, Rust suite or complete aggregate
ran during this adapter work. The parent workflow owns independent review and the
next complete live gate. An early failure with no earned requirement emits no
sentinel: Cairn's legacy exit-code fallback still cannot represent an entirely
unverified run.

Production self-audit covered all 14 rules: scope and existing contracts were
traced before editing; the change is confined to reporting, shared validation and
its tests; helpers have one purpose; malformed final evidence fails closed; the
original error survives; artifact-derived names cannot escape their directory;
publication follows durable evidence; no processes, retries or dependencies were
added; work was tracked through regression, implementation and verification;
checks above actually ran; unavailable live checks are explicit; the declared
mapping remains authoritative; the final diff was reviewed; and this report uses
the repository's terms. No unresolved defect was identified in that review.
