# Pending process reveal: identity/index race

Status: Recorded before correction; executable falsifier subsequently confirmed.
Correction `3ab14ff0` passed independent [specification](linux-pending-process-reveal-spec-review.md)
and [quality](linux-pending-process-reveal-quality-review.md) review. F1 is closed
for the demonstrated source race; native preservation remains pending.

Independent read-only investigation of the retained
[writer-only navigation failure](gpu-linux-preservation-failure.md#writer-only-syscall-diagnostic)
found an application boundary where selection identity and deferred scrolling
can disagree. This is a source finding, not an attribution of that native run
or either earlier freshness failure. No source correction or regression test
had run when this record was written.

## Finding F1

In `examples/system_pulse/src/panel.rs`, the vertical key handler resolves the
selected process identity against current rows, changes selection to the next
identity, and queues its numeric index through `scroll_to_item`. Repaint is
deferred with `on_next_frame`. Before that frame, `WorkspaceView::accept_snapshot`
can replace the process rows and reconcile selection by stable identity.
Reconciliation clears a vanished identity but does not rebase the pending
numeric scroll request. `crates/base/src/virtual_list.rs` consumes that request
during prepaint against the current row geometry.

A process that remains selected can therefore move to another row while its
pending reveal still targets the old row number. The source locations inspected
were `panel.rs:294,347–354`, `workspace.rs:536,559–563`, `live.rs:324`, and
`virtual_list.rs:113,610`. The existing GPUI seam in `native_tests.rs:1014`
exercises batched navigation, but does not cover interleaved snapshot replacement.

## Required falsifier and correction boundary

Use real snapshot acceptance, keyboard actions and list layout in a deterministic
GPUI test. Start with a selected process at index 1221, insert two rows before
its neighborhood, then send two Up keys without flushing the deferred frame.
Restore the original ordering before drawing. The expected process remains
selected but moves from index 1221 to 1219. Assert both stable identity and a
selected row instantiated within the viewport. Retain unchanged-order snapshot
delivery as a control. An observed failure, with exact test output, must precede
production changes; if this falsifier does not demonstrate the mismatch,
investigate further rather than assuming this explanation.

If confirmed, keep pending keyboard reveal as an application intent and resolve
its selected identity against the current rows immediately before list layout.
Passive snapshots must not create reveal requests. Consume the intent once;
vanished selection must not scroll to a replacement process. Preserve horizontal
navigation, selection reconciliation, coalesced repaint, stable process IDs,
manual scrolling and the existing list API unless a demonstrated limitation
requires a separately justified change. Keep all native recovery guards and
freshness bounds unchanged.

## Evidence limits and review

The native capture's frozen endpoint index was 1219 while instantiated rows
remained 1221–1229. Observation 347 crossed publications 170 and 171, but retained
observations omit those publications' process arrays and internal scroll intent.
They cannot establish the interleaving described above. A passing regression
would establish the specific corrected source behavior; fresh native replay
and full uninstrumented preservation remain required separately.

This is focused Task 5 work under GPU-007 and the preserved LIVE selection and
scrolling contracts. One implementer owns the correction, followed by independent
specification review and then fresh quality review. The Mac pool finding,
original Linux freshness failures and missing hardware evidence remain open.

## Executable follow-up

The [correction record](linux-pending-process-reveal-correction.md) retains the
actual pre-fix failure: the top-edge reordering case lost the instantiated
selected row while the unchanged-order control passed (one failed, one passed;
exit 101). An earlier bottom-edge case passed and is retained as a distinct
characterization. The correction then passed both cases and four focused
behavior tests, with 67 application tests passing. Root independently verified
26 artifact hashes, the 12 recorded check logs, both committed source-file hashes
and the original production-file hash. Those integrity checks do not substitute
for independent reviews or native preservation. Both source reviews subsequently
passed; native preservation remains a separate obligation.
