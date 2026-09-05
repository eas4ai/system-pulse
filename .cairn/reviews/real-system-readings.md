commitment: real-system-readings
commit: 2af88777383dd82139846cc23d00cf4dbacf98ea
examined:
  - LIVE-013 revised process-exit observation policy
  - scripts/system-pulse/host_capture.py
  - scripts/system-pulse/host_accuracy.py
  - scripts/system-pulse/acceptance.py
  - scripts/system-pulse/test_process_attribution.py
  - scripts/system-pulse/test_supplemental_processes.py
findings:
  - open: verify_capture fails all missing brackets and lacks independently proven exit classification retaining lower bounds and identity continuity.
  - open: child_info is unused by verify_capture; controlled CPU and I/O endpoint coverage is not mandatory per snapshot or declared before capture.
  - open: ordinary-only process identities can disappear without a retained terminal stat observation; census absence is insufficient.
  - open: aggregate host validation does not validate controlled coverage, separate verified and unverified counts, or exit-gap evidence artifacts.
  - open: cumulative SPEC review found aggregate replay accepts missing or malformed controlled child identity, metadata and terminal exit artifacts.
  - open: cumulative SPEC review found the exit classifier accepts reversed terminal observation windows.

## Mechanism review for revised LIVE-013

Requirement digest: sha256:ca3fad2f6558d9d189fefaa74561f534b8fc04b3c8cab886496f044ea45919f4

Independent read-only review found the four mismatches above. No code changed during review and no tests or native capture ran. Corrective implementation is a separate action. The agreed specification and plan describe the approved change; this review is not final commitment acceptance.

Preserve exact arithmetic and check_counter. A permitted missing after comparison requires matching independent before evidence, an actual later terminal stat read, consistent PID/start identity, no relevant permission or conflicting identity, and satisfaction of observed lower bounds. Never infer a counter from exit. Controlled child and non-process comparisons remain mandatory. Retain ordinary-only disappearance attempts in the existing bounded observation path, and validate new coverage artifacts before reporting host passes.

## First correction review

Candidate: `37bc9c37`, with build configuration `6e6963b3`. Independent SPEC review ran 61 focused tests successfully but reproduced both additional findings above: a child artifact lacking mandatory fields or containing permission failure/wrong rows was accepted; a terminal stat window with start after end was classified as proven exit. Corrective work is separate from this read-only review. QUALITY review has not started.
