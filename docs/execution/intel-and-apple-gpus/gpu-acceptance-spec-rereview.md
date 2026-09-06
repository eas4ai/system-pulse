# GPU acceptance specification re-review

Status: **Historical findings — F10 was open at `ece89eae`.** The
[later F10 review](gpu-acceptance-f10-spec-review.md) records the remaining identity
join after the missing-version correction. Independent read-only re-review of correction
`ece89eaec5c7e0775b44583dcefaa92661cc46ca` closes F1–F9 from the
[initial review](gpu-acceptance-spec-review.md). Quality review has not started.
The [structured record](gpu-acceptance-spec-rereview.json) retains the complete
finding, per-finding closure evidence and original artifact hashes. Root verified
all 1,611 records in the external review manifest before committing this finding.

## F10 — P2: mandatory native host and provider version evidence is absent

At the reviewed commit, [gpu_evidence.py](../../../scripts/system-pulse/gpu_evidence.py),
line 263, does not require `host.json`. The full `verify_host` route at lines
384–421 does not consume host metadata before awarding GPU-008. GPU-008 requires
per-host hardware/driver/API versions; GPU-009 rejects missing mandatory evidence.

The independent synthetic reproduction invokes the unmodified full `verify_host`
route with all 709 actual committed source inputs, matching binary/source hashes,
two same-name Intel physical GPUs, original inventory/observer replay, three
independently compared memory fields, complete field labels, six native actions,
complete lifecycle/commands and a Vulkan work receipt with measurement overlap.
Its positive passes. Removing `host.json` and raw `os_release`/`machine` metadata,
while preserving consistent original hashes, still earns requirements
1, 2, 4, 5, 6, 7 and 8. A wrong application hash rejects; restoring that hash makes
the metadata-absent report pass again. This is a verifier fixture, not hardware
evidence.

The capture's current host record contains system name, kernel release,
architecture, Python version and timestamp. It does not establish the full OS
product/build or deployed provider versions. Driver names, PCI/registry IDs and
formula names identify providers and devices. Header/build provenance establishes
the compilation interface. Neither substitutes for native provider versions.
The Vulkan helper queries `apiVersion` but does not retain that value or the
queried driver version; Apple observations likewise omit provider-build metadata.

Require original native host/OS build evidence and relevant selected-device
driver/API provenance before awarding GPU-008. Retain actual queryable versions
with their raw sources. Where a provider exposes no standalone version, record
that explicit limitation and its exact owning OS/framework/driver build. Do not
invent version identifiers for IOReport, HID, SMC or Metal. Cover absent,
mismatched and truthful complete metadata through full report ingestion.

The external reproduction and complete review are retained under
`gpu-task4/spec-review/corrected-ece89eae`, including
`full-host-metadata-boundary.py`, its stdout/result, the complete fixture,
`review.md` and `review.json`. This finding is committed before its correction.

## F1–F9 closure

| Finding | Independent evidence at the corrected commit |
| --- | --- |
| F1 | Full original attack plus 24 i915/xe operand mutations reject; both physical-memory positives pass. |
| F2 | Timer-only collapse rejects; changing the targeted native control accepts. |
| F3 | All 709 inputs across seven build roots are bound; four independently omitted dependency roots reject. |
| F4 | Same-name full-ID labels accept in either order, including full host ingestion. |
| F5 | Each of seven absent and seven empty groups fails the actual CLI; the restored seven-group run passes without Cairn output. |
| F6 | A missing second physical GPU rejects; complete/reordered two-device inventories pass. |
| F7 | Auxiliary warnings reject; deleting only their lifecycle entry cannot hide them; clean originals pass. |
| F8 | Wrong PIDs, commands, scripts, modes, registry arguments and helper sources reject; Intel/Apple positives pass. |
| F9 | Zero work, incomplete submissions, wrong devices and missing measurement overlap reject; full Intel/Apple work positives pass. |

The reviewer independently passed all 54 GPU tests and the seven mandatory
groups, inspected native Vulkan API/resource bounds, verified 31 retained Apple
helper originals and six Khronos/header originals, and confirmed all 58 reviewed
candidate files remained unchanged. Those checks establish verifier behavior
and source integrity. No new native workload, build, GUI, full preservation or
Cairn acceptance ran. The hardware matrix and retained Linux failures remain
pending. Correct F10, obtain specification approval, then begin quality review.
