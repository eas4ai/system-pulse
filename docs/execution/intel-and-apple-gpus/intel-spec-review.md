# Intel specification review

## First review — changes required

Independent reviewer: `intel_gpu_spec`, 2026-09-06. Candidate:
`d9d2be80f9bfb4205b9534eeabda3f89b6c12da7` (`feat: collect Intel Linux GPU readings`).
The reviewer inspected unchanged production code and reproduced four defects.
This record precedes fixes. Task 1 remains in progress; quality review follows a
passing specification re-review.

1. **P1: retained hwmon paths can cross scope and counter baselines.**
   `collectors/src/intel/sysfs.rs:291,364` merges discovered fields but validates
   only card associations; hwmon fields have no card association. Reusing
   `hwmon91` from `name=i915`, energy 1000000 at 1 s to `name=i915_gt0`, energy
   4000000 at 2.5 s emits the old whole-card energy sensor as Available at 2 W,
   alongside a new warming GT sensor. Invalidate prior bindings and baselines on
   provider replacement, ambiguity, or failed provider identity reads. Verify
   that none of those cases can produce a successful reading under the old
   attribution. Applies to GPU-002/004/006/007.
2. **P2: one invalid i915 event suppresses independent engines.**
   `collectors/src/intel/pmu.rs:328,88,170` propagates an individual event error
   through the whole specification result. Valid `rcs0-busy` config `0x0`, unit
   `ns`, plus `bcs0-busy` config `0x1000`, unit `MHz` yields global InvalidData;
   initial discovery labels it Unavailable instead of Failed. Preserve sampling
   of valid peer engines, the failing field's actual error, and independent
   recovery. Test malformed and denied peer events. Applies to GPU-002/006.
3. **P2: inconsistent CPU-visible allocation is accepted.**
   `collectors/src/intel/drm.rs:285` accepts a correctly sized xe local-memory
   response with page size 4096, total 16384, used 4096, CPU-visible total 16384,
   and CPU-visible used 8192. The reported subset exceeds its enclosing used
   allocation. Validate this relation in xe and the corresponding i915
   free-to-used conversion; inconsistent operands must not yield a successful
   reading. Applies to GPU-004 and collector-side GPU-005.
4. **P2: failed powercap identities can create false package uniqueness.**
   `collectors/src/intel/rapl.rs:12,28` drops failed package and domain name
   reads. An accessible package-0 with an uncore child plus another package
   whose name is invalid UTF-8 still yields attributed graphics power. Failed
   identity reads for actual zone candidates must invalidate uniqueness and
   retain their error. Ordinary non-zone sysfs entries must not count as zones.
   Applies to GPU-002/004/006.

Paths above are relative to `examples/system_pulse/` at the candidate commit.
Source semantics checked against the kernel's [i915 hwmon ABI](https://github.com/torvalds/linux/blob/master/Documentation/ABI/testing/sysfs-driver-intel-i915-hwmon),
[xe UAPI](https://github.com/torvalds/linux/blob/master/include/uapi/drm/xe_drm.h),
and [xe allocator accounting](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/xe/xe_ttm_vram_mgr.c).

## Verification actually performed

- Candidate collector source and lockfile comparison before and after review:
  unchanged.
- `rtk cargo test --locked -p system-pulse-collectors intel -- --nocapture`:
  26 passed, 43 filtered out.
- Collector-only compile supplied cached dependency artifacts for a temporary
  Rust harness. The harness compiled unchanged production function bodies with
  probe callers and reproduced all four defects; final compilation and probes
  exited zero. Temporary artifacts were removed.
- No repository edits, full workspace build, UI/SSH acceptance, or Cairn
  acceptance were performed by the reviewer. Intel integrated/discrete native
  accuracy and GPU-008 remain unverified.

## Resolution

Pending implementation and independent re-review. The original implementer
must retain observed failing regression tests, passing fixes, affected checks,
and the resolving commit before this record can report closure.
