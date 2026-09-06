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
Independent QUALITY review is pending. Fresh focused untraced replay, full
aggregate acceptance and final review remain required.
