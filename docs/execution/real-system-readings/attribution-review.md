# Connection attribution evidence review

## Candidate and checks

Collector commit `4d3f156dfa7c743b2618b658e4a584fda6361dcf` adds optional defaulted `Snapshot.network_attribution`. It contains one interface-address map and separate TCP4/TCP6 query records with source windows, statuses/errors, declared native byte order, and local address/state evidence. Per-interface counts derive from these shared captured inputs. No table history or per-reading table copies are retained.

The implementer ran 41 collector tests, all 65 app/model tests, scoped strict collector Clippy and formatting successfully. Actual host capture: `/tmp/pulse-network-attribution-host.jsonl`. Independent Python recomputation: `/tmp/verify-pulse-network-attribution.py`. The spec reviewer independently reran 41 tests and 72 count/status comparisons across three snapshots containing 371 rows, including 75 wildcard and 256 non-established rows.

## Spec finding and fix

The spec reviewer reproduced a P2 privacy-boundary error: malformed `state_hex` evidence retained an unrestricted token such as `DEADBEEF:CAFE`, including an endpoint-shaped port, despite failing the query. Capturing the failed status alone did not remove excluded data.

Fix `247ae5a52ba5098e5c59c668e810276ed1e0bee0` omits invalid address/state tokens as null while retaining source/line/field errors. Valid raw token spelling is preserved. Its serialized-output regression failed before the fix and covers endpoint-shaped state, shifted fields, numeric owner tokens, malformed locals and propagated Reading errors. All 42 collector tests, strict Clippy, formatting and whitespace checks passed. Independent re-review found that a missing leading slot could still make a remote address appear to be local. The exact malformed row `0100007F:1234 DEADBEEF:CAFE 01 00000000:00000000` retained `DEADBEEF` in local evidence. The first fix was therefore insufficient.

Commit `bbfc24905d5566d37e655be2412b105e9edab218` validates the header, slot, both endpoint structures and state before retaining either allowed token. Structurally uncertain rows redact both fields. The implementer observed the new regression fail before implementation, then reported 43 collector tests, strict Clippy, formatting and 72 independent host count/status comparisons passing. The independent spec reviewer passed this revision after rerunning all 43 collector tests, nine malformed-row probes, valid spelling controls and the 72 host comparisons. Independent quality review is in progress.

Native NVIDIA hardware accuracy remains unverified. The actual host capture reports DriverNotLoaded; adapter support and tests remain implemented.
