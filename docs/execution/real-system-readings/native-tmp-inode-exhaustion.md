# Temporary filesystem inode exhaustion

The focused native run of candidate `98558445` at
`/tmp/pulse-process-lookup-422__d9b/native` passed launch, then could not
write diagnostic and result files: `ENOSPC`. It did not reach the process
lookup correction. `/tmp` had 32 GiB free but all 1,048,576 inodes were used.
No successful native result was produced.

Root moved four owned artifact roots to
`/home/shawn/workspace2/task-manager-artifacts/retained`, comparing SHA-256
of every regular file before removing the temporary copies. Original paths
remain symlinks to the retained artifacts. The roots are
`system-pulse-cairn-check-aoiaislv`, `pulse-process-lookup-422__d9b`,
`system-pulse-cairn-check-wjwz1i2q`, and `system-pulse-cairn-check-8czjw7vp`.
This preserved 563 files and freed temporary inodes. No unrelated files
were removed. Further checks use TMPDIR on the workspace disk.

The failed run remains failed. Fresh focused and aggregate verification
are still required.
