# Full acceptance after prior-selection focused pass

The committed aggregate against `cb4067242d958dac081523d89b92c35371b195be`
finished **FAIL** during intermediate process navigation. The [record](native-prior-selection-full-failure.json)
retains all 136 artifact hashes, commands/results, host comparisons, native metadata,
bounded failure observations, held-input evidence, final journal and cleanup.
Artifacts: `/home/shawn/workspace2/task-manager-artifacts/tmp/system-pulse-cairn-check-20luq4dm/system-pulse-acceptance-z4iqe4_o`.

All **743 automated tests** passed: 381 Python and 362 Rust. Affected formatting,
vendored AT-SPI formatting, strict all-target Clippy, native build, source guard
and whitespace checks passed. Host verification passed with 2,217 exact readings,
18,278 exact process fields, 44,930 counter brackets, 468 stable totals, no failed
brackets or unverified exit gaps, and independently verified controlled-child exit.

Native launch, two-GPU metrics, collapse, two GPU temperature charts and inner
scrolling passed. All four held/exact-input observers joined; the retained evidence
has multiple accepted sequences and ages below the unchanged two-second limit.
The aggregate did not complete the controlled-child metric/exit, later persistence,
recovery, missing-device and final interaction checks.

| Held input artifact | Observations | Maximum age seconds |
| --- | ---: | ---: |
| held-up-25hz | 53 | 1.298055438 |
| exact-64-up | 33 | 1.340266804 |
| held-table-left | 63 | 1.347774222 |
| held-table-right | 61 | 1.303822717 |

## Process failure

Child `process:1717132:75713821` appeared. There were 98 arrow batches and 98
independent baseline-stat receipts, with no navigation recovery inputs. The last
acknowledged selection was `process:1944648:43459871`; the next two Up keys
expected `process:1944646:43459871`. Observations 284 and 285 saw the prior
selection in publication 147 and latched a competing-selection block. Later
observations saw no instantiated selection; the block remained. Observation 330
expired during panel validation at the existing eight-second batch deadline.
This capture does not establish the hidden model selection or prove that recovery
would have succeeded. The [independent diagnosis](native-prior-visible-endpoint-review.md)
identifies the visible-unselected expected restriction inside the valid prior prefix.

The binary and running executable SHA-256 were both
`7dbcd3adfae54db64e3ed5f32cf728ee55684fd1429c95c1bbd1e72a770340e7`.
Application PID 1709077 was terminated during failure cleanup (exit -15), and the
private transport PID 1709068 exited zero without forced kill. Neither remained.
The native controlled-child exit acceptance was not reached; host child exit is
separate evidence.

Cairn's actual receipts report LIVE-004, LIVE-012 and LIVE-013 pass, with the other
ten requirements unverified. `cairn wake` remains Resolvable for LIVE-001. The
previous focused pass and historical failures retain their own outcomes. Full
acceptance and final review remain open. NVIDIA hardware accuracy, macOS/Windows
native behavior and physical device removal retain their stated limits.
