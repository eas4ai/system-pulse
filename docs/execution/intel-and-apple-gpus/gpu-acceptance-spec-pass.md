# GPU acceptance specification pass

**Verdict: SPEC PASS** for candidate `50ea29d6653d42ceafc8b3f246b9a18ae721b612`, reviewed against `eccf56b7e5cb34c8a5103cbc36d9583c1383d6dc`. The remaining F10 finding is closed. F1–F9 and the previously verified portions of F10 remain closed; no new concrete specification finding was identified in this focused correction.

## Why the correction closes F10

`scripts/system-pulse/gpu_provenance.py:421` now compares maps of complete physical identities, keyed by monitor ID, rather than sets of IDs alone. Each metadata-discovered device is projected through the six authoritative fields supplied by the independent inventory: `pci`, `driver`, `physical_path`, `monitor_id`, `vendor`, and `device_id`. The other map comes from every `inventory.discovery` entry. That inventory has already been regenerated from independent raw native observations and checked by `verify_series` before provenance validation runs.

The existing surrounding checks require complete provider counts, unique provider rows and exact agreement with discovery replayed from metadata sysfs. Together these checks reject missing or duplicate providers as well as conflicting fields. Incidental alias lists and enumeration order are excluded from the cross-inventory identity projection, preserving physical identity across those differences. The Apple branch and native helper sources are unchanged.

## Original full-route attack replays

I made new copies of the four frozen reviewer reports from `f10-eccf56b7`. Only the committed source files and their source-binding fields in `build.json` and `report.json` were refreshed to the new candidate. Every report retains all **106 non-source originals byte-for-byte**. The original reports remain untouched. Each refreshed report includes the actual 711 committed inputs.

| Frozen report | Full unmodified `verify_host` outcome |
| --- | --- |
| Intel complete positive | Accepted |
| Apple complete positive | Accepted |
| Selected Intel metadata device ID `0x9999` versus independent `0x1234` | Rejected: `Linux provider identity differs from independent physical inventory` |
| Selected Intel metadata driver `i915` versus independent `xe` | Rejected with the same identity error |

The failures occur at the intended identity join, not because of stale source or artifact hashes. `replay-frozen-originals.py`, its exact command record and stdout/stderr, and `frozen-replay-results.json` retain the complete results. The result file includes the frozen/new report hashes and SHA-256 of every preserved non-source original. The four refreshed report directories remain available for inspection.

## Independent boundary checks

Using the copied Intel positive and full `verify_host` ingestion, I consistently changed and re-hashed nested host metadata across all its native streams while keeping independent top-level device/field observations and the Vulkan workload unchanged. All of the following rejected with the intended identity error:

- Wrong device ID, driver or physical path on the selected GPU.
- Wrong device ID, driver or physical path on the second GPU.
- A missing selected provider or missing second provider.
- A duplicate provider row.

Reversing device enumeration and alias order accepted. Adding a second DRM alias for the same physical GPU while also reversing order accepted. The original positive was restored and revalidated after every case, and all its original bytes were restored at the end. These 11 cases are retained in `independent-identity-boundaries.py`, its command/log records and `independent-identity-results.json`.

## Verification and preserved scope

- All **57 GPU verifier tests passed**. The seven mandatory development groups passed with counts **6/5/6/8/15/10/7**, with no Cairn acceptance output. Exact commands, runtimes and original log hashes are in `initial-checks.json`.
- Source comparison confirms only `gpu_provenance.py` and `test_gpu_evidence.py` changed under first-party code/mechanism paths since the prior reviewed candidate. The production change is the six-line identity-map replacement. F1–F9's implementations, the rest of F10, production Rust and native helpers are unchanged. The full GPU test run and intact Apple/full-report positives supplement their existing independent closure evidence; a new native readiness or massive repetition of unaffected attack families was not needed.
- Final integrity checks confirmed all 60 reviewed candidate files still match their initial hashes and commit `50ea29d6`, with a clean worktree. The later root HEAD is documentation only. This review changed no source, index, marker, plan or decision.
- `review-artifact-manifest.json` records and verifies hashes for all retained review artifacts. No unrun test or helper-readiness claim is introduced by this review.

This is a specification pass for the committed acceptance mechanism. It does not establish native Intel integrated, Intel discrete or Apple GUI accuracy; complete hardware reports and Task 5 remain pending. The workstation's possible UHD770 BIOS enablement is not observed Intel evidence. Existing Linux untraced freshness failures remain failed. No native workload, GUI operation, SDK change, build, preservation attempt or Cairn acceptance was run during this review. Independent quality review may now proceed.

The [structured source record](gpu-acceptance-spec-pass.json) binds the full external
review and its artifact manifest. Root independently verified all 3,304 recorded
file sizes and hashes before committing this specification verdict.
