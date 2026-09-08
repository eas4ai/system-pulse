# Proposal: avoid unused presentation work

Status: Approved by the developer on 2026-09-08; implementation and verification recorded in [presentation results](presentation-results.md); both CPU targets remain unmet.

The [latest complete comparison](collector-reuse-results.md) reports 21.4 percent
less Summary CPU and 30.3 percent less tray CPU than the agreed reference. Both
50 percent targets remain unmet after the collector and narrow dependency work.
The reference, workload, interval and acceptance requirements remain unchanged.

## Evidence

The latest tray profile attributes 273 of 1,154 sampled CPU milliseconds to the
main thread. Snapshot delivery includes 116 ms; process-row formatting includes
42 ms. These inclusive weights overlap. The earlier Summary profile also shows
CPU work in layout and drawing. Neither profile establishes how much can be
removed without affecting behavior.

Source inspection identifies an avoidable trigger: every accepted snapshot
formats all process rows and refreshes panel models, including when the window
is closed or Summary is selected. See `WorkspaceView::accept_snapshot_optional`
in `src/workspace.rs` and `process_views` in `src/live.rs`. The Summary process
count does not require formatted table cells.

The collector still accounts for most tray CPU. Moving it into another process
would transfer that cost, not eliminate it. A service could support a separate
lifetime or multiple clients, but those are separate product decisions.

## Requested scope

Extend the current commitment to application snapshot acceptance, derived
presentation and panel notification in `src/`, with their directly affected
tests and verification records. Start with these bounded changes:

1. Keep accepting every available snapshot and advancing every monitored history
   at the selected interval. Retain raw process data and stable identities.
2. Build formatted process-table rows when they are needed for display or
   diagnostic inspection. Use raw identities and counts for selection and Summary.
   Opening Processes must immediately use the latest accepted snapshot and its
   actual age; failed or stale readings must remain visibly failed or stale.
3. Avoid refreshing inactive panel presentation when a snapshot arrives. On
   activation or reopening, prepare the current presentation before it is shown.
   Preserve discovery, settings, selection and continuous history independently
   of whether a panel is displayed.
4. Profile and measure after this coherent change. Do not infer that it reaches
   50 percent; the same complete paired gate must establish that result.

This proposal adds no service process, changes no dependency or GPUI framework,
and does not slow sampling, discard processes, reduce metric coverage or alter
the persisted workspace format. Further architectural changes need a separate
decision supported by the next profile.

## Proof required

Tests must cover fresh snapshots received while closed, immediate reopening,
switching Summary to Processes, process disappearance/PID reuse, stable
selection, truthful stale/failed cells and unchanged background history. Keep
diagnostic inspection meaningful even when a screen is not displayed.

Run the affected application/model/collector tests, formatting, strict Clippy,
full Linux native/package acceptance, native Mac preservation and the same
twelve scored observations. Compare complete process and sensor coverage;
correctness passing without the CPU target remains incomplete.

If this extension is declined, retain the tested current revision and record
the CPU targets as pending. Do not weaken the targets or silently expand into
a service redesign.
