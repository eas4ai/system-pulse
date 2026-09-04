# Workspace Visibility and Collapse

Date: 2026-09-04
Status: Approved by the user on 2026-09-04. Implementation planning is authorized; implementation has not started.

## Purpose

Keep enabled monitors together in a customizable workspace. Users can scroll through the arrangement and choose how much detail each panel or sensor row shows.

This spec records the user's corrections to the earlier brainstorming output: panels never form tab groups; overflow is reached by scrolling; panels and sensor rows can collapse in place while retaining useful readings.

Related inputs: [feature spec](../../feature-spec-dockable-system-monitor.md), [design prompt](../../claude-design-prompt.md), and [reference review](../research/2026-09-04-reference-review.md).

## Scope

This contract covers separate panel regions, workspace overflow, panel collapse, sensor-row collapse, and persistence of those presentation choices. It applies to all monitor panels; Settings also supports panel collapse but needs only its title and controls in the collapsed header.

A sensor row is a sensor's label, value, and meter. It is not a process-table row. Process hierarchy expansion, sensor ordering controls, metric backend definitions, and complete preset management belong to separate specs.

## Workspace behavior

**WV-01 — Separate regions.** Every enabled panel has its own region. Users can move panels by their headers, create horizontal or vertical splits, and resize dividers. No action creates a tab group. Dropping on a destination that would merge panels is rejected without moving or losing the source panel.

**WV-02 — Scrollable overflow.** Preserve readable panel sizes when the workspace exceeds the viewport. Prefer vertical scrolling; allow horizontal scrolling when the user's split arrangement requires it. A window resize never changes which panels are enabled or which panels or rows are collapsed. Content outside the viewport remains reachable by scrolling.

**WV-03 — Explicit hiding.** Show/hide controls change whether a monitor or sensor appears. Collapse controls change its presentation while keeping its header or compact row visible. Re-enabling a monitor inserts a separate region and retains its collapse choices.

**WV-04 — Nested scrolling.** Workspace scrolling and panel-content scrolling remain independently reachable. A long Processes table must not prevent users from reaching other panels. Pointer and keyboard navigation must support both. Keyboard focus moving to an offscreen control scrolls that control into view.

## Collapse behavior

**WV-05 — Initial state.** Without saved presentation state, all panels and sensor rows start expanded. A saved layout or recalled preset restores the user's recorded choices.

**WV-06 — Panel collapse.** A panel's collapse control folds away its body and retains the header, title, expansion control, close control, and a compact current summary. For example, a CPU header can show `CPU · 34%`. The summary uses the panel's primary reading; unavailable or stale readings retain their status instead of appearing as measured zero. Settings retains its title and controls without a metric summary.

| Panel | Compact summary |
| --- | --- |
| CPU | Overall utilization |
| GPU | That device's utilization |
| Memory | RAM used / total |
| Disk volume | Capacity used / total |
| Network interface | RX and TX throughput |
| Processes | Current total process count |

Summary selection is fixed for this interaction scope and does not change when a sensor row is hidden. It uses existing collector readings. The metric specs define units and platform-specific availability.

Collapse removes the body's size request and retains the preferred expanded size separately. Expansion occurs in the same logical region and restores that preferred size subject to layout constraints. If the expanded arrangement does not fit, the workspace scrolls. It does not hide another panel to make room.

**WV-07 — Sensor-row collapse.** A collapsed row retains its label, formatted current value, unit, reading status, and expansion control. Its chart or detailed meter is folded away. The row keeps its relative position among other sensors. Expansion restores the selected meter in place. The compact representation is also valid when the chosen meter is already numeric and little space is saved.

**WV-08 — Independent state.** Collapsing a panel does not change its rows' collapse states. Expanding the panel restores the same mix of compact and detailed rows. Changing a row's meter does not reset its collapse state. Hiding and re-enabling a sensor retains its row state.

**WV-09 — Live readings.** Collapse does not stop collection or reset history. Visible compact readings continue to update at the configured collection cadence. Charts restored on expansion use the existing bounded history. Offscreen and collapsed meter bodies need not render while collection continues.

**WV-10 — Controls.** Collapse/expand controls have accessible names and expose their expanded state. Enter or Space activates a focused control. Activating collapse, expand, or close must not initiate panel dragging. If collapsing would hide the focused descendant, focus moves to that panel's or row's expansion control.

## State ownership and persistence

The application owns panel and sensor presentation state. The docking framework owns split geometry and movement. The collector owns current readings and history. Rendering a compact summary reads existing data; it does not create a second polling loop.

Persist panel collapse state, preferred expanded dimensions, and per-sensor row collapse state alongside the dock layout, keyed by stable monitor and sensor identities. Presets capture the same fields. Missing fields in older state default to expanded. Display-name changes or device enumeration order must not attach saved choices to a different device.

**WV-11 — Round-trip restoration.** Saving and restoring a layout or preset preserves panel placement and both collapse levels. A missing sensor or device does not erase its saved presentation state. Restoring that same identity makes its prior choices available again.

**WV-12 — Invalid state.** Validate persisted layout structure before applying it. A saved multi-panel tab group is incompatible with this product and must not be installed. Retain the original saved data and open a valid default split arrangement with a recoverable error. Normal autosave must not overwrite the retained invalid input before explicit recovery. The broader persistence spec will define storage and recovery mechanics.

## Framework integration constraint

The examined `eas4ai/gpui-component` revision, `ba3433f0740ee5ba2b1db459af49229caf0c1bcc`, does not expose an enforceable policy for separate split regions while retaining normal drag behavior. Its default center-drop and insertion paths can merge panels. Hiding the tab strip does not meet WV-01.

The application-shell plan must include an integration proof and, if needed, a focused framework extension. That work must reject merge targets before removing the source panel, support inserting a panel into a new split, validate restored state, and exercise overflow and collapse geometry. See the [source evidence](../research/2026-09-04-reference-review.md#dock-integration-finding). This finding does not relax the no-tabs requirement.

## Acceptance evidence

| Requirements | Scenario | Required outcome |
| --- | --- | --- |
| WV-01, WV-03 | Move panels to edges; attempt center/header merging; hide and re-enable a monitor. | Valid edge moves work. Merging never occurs. Rejected moves preserve the source; re-enabled monitors have separate regions. |
| WV-02, WV-04 | Enable enough panels to exceed the minimum-size window; use a long process table; resize and navigate with pointer and keyboard. | Every enabled panel and table row is reachable. Panel identity, ordering, and collapse choices remain unchanged by window resizing. |
| WV-05–WV-08 | Start without saved state; collapse one sensor row, collapse its panel, then expand the panel. | Initial content is expanded. The collapsed row keeps its value and position. Panel expansion restores that compact row and the other expanded rows. |
| WV-06, WV-09 | Advance fixture readings while a panel is collapsed, including unavailable and stale states. | Header readings update truthfully; expanding reveals continuous bounded history with appropriate gaps. |
| WV-07–WV-09 | Change a collapsed row's meter; hide/re-enable it; advance several samples. | Meter selection, collapse state, and identity survive; the compact value remains current and history is not reset. |
| WV-10 | Activate controls by keyboard and collapse content containing focus. | Actions occur without dragging, expanded state is exposed, and focus remains on a visible control. |
| WV-11 | Save/reload and save/recall a preset with mixed collapse states; reorder device discovery; temporarily remove a sensor. | Placement and presentation choices remain associated with the correct identities. Missing fields restore expanded. |
| WV-12 | Load state containing a multi-panel group. | No tabs appear. Original input remains recoverable and a valid split arrangement opens with an error. |

Use deterministic state-transition and fixture tests for presentation state, identity, and history continuity. Use native interaction tests for dragging, scrolling, focus, and restored geometry. Screenshots supplement those checks; they do not prove interaction behavior. No implementation or runtime acceptance checks have run yet.
