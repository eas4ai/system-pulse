# Intel and Apple GPU support

Status: Agreed 2026-09-06
Slug: intel-and-apple-gpus
Requirements: GPU-001, GPU-002, GPU-003, GPU-004, GPU-005, GPU-006, GPU-007, GPU-008, GPU-009

## Goal

Add Intel integrated/discrete GPU collection on Linux and Apple Silicon GPU collection on macOS to the real System Pulse workspace, with accurate memory scopes and evidence of native behavior. The agreed contract is [GPU-001 through GPU-009](../spec/gpu-collection.md).

The developer confirmed the detailed requirements and falsifiers on 2026-09-06. This commitment follows the completed LIVE acceptance; it does not claim GPU hardware support before verification.

## Deliverables

1. Focused Intel and Apple adapters under `examples/system_pulse/collectors/src/`, integrated through `HostCollector`; physical types and the current service remain the common boundary.
2. GPU memory/source semantics in descriptors and existing model/UI formatting, including additive persistence compatibility where required.
3. Deterministic adapter and integration tests; a separate GPU acceptance entry point under `scripts/system-pulse/` with explicit results per requirement.
4. Cited API/capability decisions, independent reviews, native captures and reproducible commands under `docs/execution/intel-and-apple-gpus/`.

The [implementation plan](../plans/intel-and-apple-gpus.md) assigns source tasks; the [acceptance plan](../plans/intel-and-apple-gpu-acceptance.md) names their proof. One source implementer works at a time, followed by independent specification and quality review. Final commitment review records what the checks could miss before any resulting fixes.

## Done when

- The confirmed GPU requirements have passing evidence against committed source.
- Required Intel and Apple fields have implementation or evidenced API/permission/attribution limits.
- Intel integrated, Intel discrete and Apple Silicon native reports satisfy the declared coverage; absent hardware does not count as pass.
- Existing Linux collection and workspace acceptance still pass.
- Independent reviews have no open findings and Cairn returns Done for this commitment.

Intel Windows support is the separately tracked follow-on described in the contract. This iteration does not silently include Windows acceptance or per-process GPU statistics.
