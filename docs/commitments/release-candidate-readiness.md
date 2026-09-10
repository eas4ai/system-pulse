# Release candidate readiness

Status: Agreed 2026-09-09
Slug: release-candidate-readiness
Requirements: REL-001, REL-002, REL-003, REL-004

The developer explicitly approved establishing this commitment after requesting
Windows release readiness and binary-build CI. See [contract](../spec/release.md).

Scope: Windows build prerequisites and necessary platform fixes, native Windows
verification on the Intel tablet, hosted Linux/macOS/Windows binary CI, required
archive/license support, README and build/release instructions. Preserve the
locked baseline where possible; do not merge Dependabot updates as part of setup.

Done requires committed-source native Windows build/test/runtime evidence,
successful hosted CI artifacts for all declared targets, accurate documentation
and a clean final review. Tagging or publishing a public release is a subsequent
developer action. Earlier incomplete commitments retain their status.
