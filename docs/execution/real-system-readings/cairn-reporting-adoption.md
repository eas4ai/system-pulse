# Explicit Cairn reporting adopted

Installed Cairn: `6879dde`. The production executable resolves to `/home/shawn/workspace2/cairn/bin/cairn.mjs`.

The mechanism now declares `results: per-requirement`. Its command, nine declared inputs, thirteen requirements and existing evidence mapping are unchanged. The kernel records every omitted requirement as unverified even when there are zero result lines, while retaining command execution diagnostics. Historical receipts are unchanged. The earlier failure streak still requires an escalation; this is not a new reporting failure.

Root ran `rtk proxy node --test tests/reporting-mode.test.mjs` in Cairn: all 12 tests passed. Independent review completed SPEC then QUALITY with no findings. The reviewer compared the declaration byte-for-byte after removing the new line, ran isolated thirteen-ID scenarios for no output at exits zero and one, and tested actual host-pass reporter output followed by exit one. Results were respectively thirteen unverified, thirteen unverified, and three passes plus ten unverified, preserving exit and stderr. All 28 existing reporter unit tests also passed. Diff validation passed.

No full host/native acceptance ran during adoption. The latest real capture remains FAIL; see [process exit evidence](host-process-exit-gap.md). The [observation proposal](process-observation-proposal.md) remains Draft and does not alter the agreed requirement or comparison bounds.

The adoption self-audit found no unresolved defect in this configuration change. Final application acceptance and review remain incomplete.
