# Fresh full Linux preservation pass

The complete uninstrumented Linux preservation command passed on 2026-09-06 against committed HEAD `f39e52d2a8cae5248b5e48681e131378552b356c`, with source candidate `61e8ceef4db8ce4c6f3114cc25437f9cd9ad3e5a`. It includes the independently reviewed process-reveal correction `3ab14ff0` and [complete-suite budget correction](linux-python-budget-reviews.md).

**870 tests passed**: Python 444, base docking 205, resizable 13, component docking 19, model 24, app 67, collectors 96 and AT-SPI 2. All declared formatting, strict Clippy, build and diff checks passed. Independent live host comparisons passed. The full native replay passed all 14 cases, including process navigation, held input, scrolling, charts, presets, restart, saved-state recovery and the missing-device specimen. Native execution took 458.935 seconds. No publication tracing or focused preparation was enabled; the two-second freshness limit and all comparison bounds were unchanged.

```sh
rtk proxy /home/linuxbrew/.linuxbrew/opt/python@3.14/bin/python3.14 -B scripts/system-pulse/verify.py --output /home/shawn/workspace2/task-manager-artifacts/gpu-task5/linux-preservation-61e8ceef-reap-20260906
```

The command ran through the [corrected external supervisor](gpu-linux-preservation-failure.md#external-supervisor-correction-after-the-budget-fix), exited zero and emitted passes for LIVE-001 through LIVE-013. Those are command results, not newly recorded Cairn GPU receipts. Root verified all 154 manifest artifacts, stage-log hashes, all 734 unchanged source input hashes, owner streams and the absence of all 18 recorded supervisor process IDs/groups. The supervisor had no remaining children. Native transport cleanup exited zero without forced kill or errors.

Original output is at `/home/shawn/workspace2/task-manager-artifacts/gpu-task5/linux-preservation-61e8ceef-reap-20260906`. Its `manifest.json` SHA-256 is `d9869443db67e995aef9cc11652481a739624feb66f32a60d15ba3932df6ce07`. The adjacent `-setup`, `-owner` and `-root-verification.json` retain source, command and cleanup bindings.

This establishes fresh Linux preservation on the current AMD host. Historical freshness failures remain retained and their exact original event ordering remains unattributed. It does not verify Intel integrated/discrete or Apple hardware. Mac F1, unlocked native desktop proof, required hardware reports, aggregate GPU receipts and final commitment review remain open. GPU Task 5 is still the single item in progress; no commitment completion, merge, push or deployment is claimed.

Production self-audit: all fourteen rules were checked for this checkpoint. The bounded source corrections and their independent reviews are complete; actual verification and external limitations are distinguished. Source is unchanged by this record. The broader delivery remains incomplete for the named hardware and Mac proof obligations.
