# Native monitoring overhead

Status: Agreed 2026-09-07
Prefix: PERF

The developer approved this focused collector optimization after reviewing the
proposal on 2026-09-07. The comparison host is the developer's eight-core M1 Pro
MacBook. CPU percentages below use one logical CPU as 100 percent. The unchanged
reference is application revision `af243cf2dba5eb6c4cb19397c522c38eda640f45` built
with the locked native release configuration.

The [measurement protocol](../plans/macos-performance.md) fixes the workload and
comparison before implementation. The preliminary 30-second observations in the
[recon](../recon.md) locate the cost; they do not satisfy the three-run gate.

[PERF-001] The optimized release MUST consume at most half the reference release's CPU time per elapsed second with Summary visible on the comparison MacBook.
Falsifier: the aggregate of three valid 60-second candidate observations exceeds 50 percent of the aggregate of three matching reference observations, or a required observation is absent.
Mechanism: native `macos-performance` paired measurement and comparison, with source and binary hashes, all raw counters, window state, and each repetition retained.

[PERF-002] The optimized release MUST consume at most half the reference release's CPU time per elapsed second in tray-only mode on the comparison MacBook.
Falsifier: the aggregate of three valid 60-second candidate observations exceeds 50 percent of the aggregate of three matching reference observations, a dashboard window remains open, or a required observation is absent.
Mechanism: native `macos-performance` paired measurement with native window-close confirmation, process-lifetime checks and the same retained evidence as PERF-001.

[PERF-003] The collector MUST preserve the selected sampling interval, live metric coverage, measured counter windows, stable identities and truthful reading availability while reducing overhead.
Falsifier: the optimization obtains its reduction by slowing the one-second measurement workload, dropping readings or processes, freezing a value, inventing a zero, reusing an invalid baseline, or labeling a failed or old read current.
Mechanism: collector regression tests, native snapshot inspection and existing model/application tests for sampling, availability, physical units and process identity.

[PERF-004] Any reused collector inventory MUST recover from missing devices and failed reads without unbounded retained state or loss of discovery.
Falsifier: removal or failure leaves a successful cached reading, reappearance cannot recover, an identity is attached to another device, or cache growth follows historical rather than current identities without a bound.
Mechanism: controlled cache/discovery/failure/recovery tests and native collector smoke checks; retain the current disk path if its API cannot establish fresh successful reads safely.

[PERF-005] The optimization MUST preserve continuous background history, native interaction, saved settings and orderly tray shutdown.
Falsifier: closing the window stops collection, reopening loses history or settings, a slow collector blocks interaction, or an owned sampler/window survives application quit.
Mechanism: existing collector lifecycle and application tests, Linux native preservation, and native Mac close/reopen/quit checks outside timed measurement windows.

[PERF-006] The performance verifier MUST reject invalid or non-comparable observations rather than report them as an improvement.
Falsifier: missing runs, wrong binary identity, wrong mode or interval, a short run, a regressing counter, non-finite arithmetic, or a deliberately insufficient reduction passes.
Mechanism: negative verifier tests with safe altered receipts, followed by fresh native runs; no profiler or diagnostic snapshot writer runs during scored CPU windows.
