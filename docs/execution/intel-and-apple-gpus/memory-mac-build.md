# Committed GPU integration Mac build

The actual M1 Pro Mac built source `4db68c71304d368977265e31ba365b121fcfd9f0`
and passed all 63 application library tests on 2026-09-06. This prepares the
application for independent native GPU acceptance; no GUI, accuracy or
sleep/wake acceptance was performed by this build.

[Exact build record](memory-mac-build.json) contains committed source, archive,
lockfile and binary hashes, command logs, task-owned process identities and
cleanup. The source archive was created with `git archive`, transferred to the
authorized Mac and SHA-256 verified before extraction into the new
`/Users/shawnmcallister/system-pulse-gpu-validation-03rjwxl7/source-4db68c71/`.
Existing source archives were preserved. The build used the existing target
cache and two Cargo jobs, with an 1800-second process-group deadline per command.

| Native command | Result |
| --- | --- |
| `cargo build --locked -p system-pulse -p system-pulse-collectors --bins` | Passed in 23.092 seconds; PID 4112 exited zero and was reaped |
| `cargo test --locked -p system-pulse --lib` | 63 passed in a 65.2-second command; PID 4267 exited zero and was reaped |

Cargo.lock remained SHA-256
`0da1662a18c6bde6a1a98021cfa16e9eb2684466bc245043aa4452560bf2aec9`.
The System Pulse executable is SHA-256
`c3a4a7a71ee911b1e675fba566498d1092ea199ed96db6cde7044147c393b2b6`;
`pulse-snapshot` is SHA-256
`32c705a3bb77cb7850445dc40eac053b01a1c7fb52df98c19e0b4e0690be9e6f`.

Root downloaded both original logs and the report, verified their SHA-256 values,
checked source/archive and before/after lockfile agreement, and parsed the actual
63 passing native test results. Originals, the bounded build wrapper and the
verification manifest remain under
`/home/shawn/workspace2/task-manager-artifacts/gpu-memory-integration/4db68c71304d368977265e31ba365b121fcfd9f0/mac-build/`.
No application session or Metal workload was launched by this preparation.
