# Read restricted Mac process birth identity through sysctl

Level: Judged
Decided by: agent
Rests on: PROC-004 PROC-005
Would be wrong if: A fallback combines different process lifetimes, invents identity or credentials, changes ordinary process semantics, or weakens post-authentication identity validation.

## Decision

When the Mac full BSD process record is denied, recover the same microsecond birth identity and available process metadata from a complete validated KERN_PROC_PID record. Validate the SDK ABI and process identity, fail closed on incomplete or invalid data, and preserve the existing full BSD path for ordinary processes. The independent interactive verifier uses its own native sysctl observation. The privileged action helper still validates the original birth identity against its atomic BSD-plus-kernel-version record after OS authentication and signals only by audit token. Root-owned native observations and ordinary process regressions must pass before completion.

## Realized by

- 4f0fd17262647ceb404a77a5005c40ad2e60f34c Recover precise Mac root process identity without elevating collection
