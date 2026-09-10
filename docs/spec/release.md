# Release candidate readiness

Status: Agreed 2026-09-09
Prefix: REL

The developer authorized this commitment on 2026-09-09, including Windows
setup/build/runtime verification, binary-build CI and accurate README support
status. The Windows Intel tablet is reachable through SSH; local desktop Codex
is installing Git and CMake. Preserve existing Linux and Mac behavior and the
locked dependency baseline. Dependabot upgrades are separately reviewed work.

[REL-001] System Pulse MUST build and pass applicable model, collector and application tests on Windows x86_64 using the committed lockfile.
Falsifier: documented Windows prerequisites cannot reproduce the release executable, an applicable test fails, or the build requires unrecorded source or dependency changes.
Mechanism: native Windows build and test logs tied to the committed source, toolchain and prerequisites.

[REL-002] The Windows release executable MUST be verified on the Intel tablet with honest sensor availability and working core desktop behavior.
Falsifier: the application cannot launch, render or exit; process data, sorting/filtering, navigation, tray reopening or persistence fail; unsupported GPU or thermal measurements are presented as measured values.
Mechanism: native Windows runtime observations and diagnostic evidence tied to the tested release executable; record hardware and unavailable readings explicitly.

[REL-003] CI MUST build downloadable release binaries for Linux x86_64, macOS arm64 and Windows x86_64 and run applicable automated checks.
Falsifier: a declared platform fails its CI build, artifacts are absent or contain untracked binaries, checks silently skip failures, or distributed archives omit required licenses and source-access instructions.
Mechanism: workflow review and successful hosted workflow runs with retained artifacts and source revisions. Builds run for pull requests and main; manual builds support release preparation without automatically publishing a release.

[REL-004] The README and release instructions MUST accurately describe build prerequisites, artifact use and verified platform support.
Falsifier: instructions name nonexistent artifacts, claim unverified Windows hardware capabilities, omit material platform limitations, or disagree with actual build and runtime evidence.
Mechanism: compare documentation to successful builds, packaged contents and native verification records, then perform final commitment review.
