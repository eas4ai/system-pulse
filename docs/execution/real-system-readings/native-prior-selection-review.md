# Prior selection in intermediate arrows: reviews

Candidate: `a4cab9f764252a691fbdbdff0896886d8ed00b8e`.
Base: `8e392b350682a226d1e622326bbb495c3ba3a28d`.
The [decision](../../decisions/recognize-prior-selection-during-intermediate-arrow-observation.md)
and [implementation](native-prior-selection-implementation.md) define the bounded
exception. The previous capture remains FAIL; successful counterfactual recovery
is not established.

## Specification review

Independent reviewer `prepare_child_inspection` returned **PASS**, with no
findings. The exception is bound to the returned prior native ACK and intermediate
issued batch. Expiry, permanent blocks, fresh recovery guards and exact post-wheel
proof remain intact.

Actual checks:

- All 18 prior-selection, 76 navigation and 30 pending-endpoint tests passed.
- Four independent negative probes passed.
- Scoped Ruff, diff checks and five documentation links passed.

The reviewer changed no source and ran no build, native replay or Cairn action.

## Quality review

Independent reviewer `review_publication_quality` returned **PASS**, with no
findings. ACK provenance, intermediate-only scope, permanent blocking, irreversible
prefix expiry and fresh exact endpoint proof remain intact. Partial dispatch
cannot reach pending observation. Caller mutations cannot alter copied evidence;
interrupted results can seed later proof only through a separately successful
boundary acknowledgement.

Actual checks:

- All 18 prior-selection tests passed.
- Five additional probes passed, including eight malformed-envelope cases:
  partial dispatch, dispatch expiry, publication advance followed by restoration,
  nested evidence mutation and invalid bindings. Prohibited paths produced no
  reveal or endpoint acknowledgement.
- Scoped Ruff lint and three-file formatting, candidate whitespace checks and
  five documentation links passed. All four reviewed files matched candidate bytes.

The reviewer made no edits and ran no build, native replay or Cairn action.
Both reviews are complete. The implementer passed all 381 Python tests against
final source. The [fresh untraced focused replay](native-prior-selection-focused-pass.md)
subsequently passed all sixteen comparisons and controlled exit. It exercised
inspection recovery under fifteen-second discovery, with no navigation recovery
event. The failed capture remains failed. Full aggregate acceptance and final
review remain required.
