# Diagnostic publication trace

The diagnostic-only traced run is retained at
`/home/shawn/workspace2/task-manager-artifacts/diagnostic-trace/native-run`.
Its frozen harness only prefixes app launch with strace; the binary hash
is unchanged. A controlled probe verified PID/parent preservation and
tracer cleanup. No write payloads were recorded.

The trace did not reproduce the earlier publication stall. The longest
observed fsync was 52.977 ms. The run stopped on an exact-64-up movement
timeout, so it is neither successful acceptance nor proof of the earlier
stall's specific cause. Tracing can alter scheduling. Original evidence
remains unchanged.

Source inspection confirms diagnostic publication shares the durable
configuration save path: write, sync_all, rename. Diagnostic snapshots
need complete atomic replacement and revision ordering; workspace and
preset saves retain their durability requirement. Removing the diagnostic
flush dependency is a narrow publication improvement, not a claim that
this trace identified the earlier stalled syscall. Fresh untraced
acceptance is still mandatory.
