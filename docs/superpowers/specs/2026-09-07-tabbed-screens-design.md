# Reference-based tabbed screens

## Direction and authority

On 2026-09-07 the developer requested replacing the current UI layout with
screens based on the supplied images, organized into tabs. This supersedes
the earlier separate-panel/no-tabs layout requirement. The reference images
are the visual specification; generic dashboard skill defaults do not override
their composition, colors, segmented meters or chart treatment.

The eight images in `reference/tmog.org/` were inspected: `summary.webp`,
`cpu.webp`, `memory.webp`, `disks.webp`, `network.webp`, `energy.webp`,
`thermals.webp`, and `processes.webp`. They show a dark instrument-like monitor
with restrained borders, wide geometric headings, luminous traces, segmented
bars, dense statistics and a full process table. System Pulse retains its own
name and icons; sample data and TMOG branding are not application assets.

## Navigation

Use a horizontal tab strip: Summary, CPU, Memory, GPU, Disks, Network, Energy,
Thermals, Processes, Settings. Each selects one fixed screen. The reference
sidebars become this single tab strip, leaving more room for the central
screen content. Use a compact application header and bottom status line.
Tabs are never closable, draggable or merged into other panels.

The default interpretation is replacement of the docked canvas. An optional
question about retaining a Custom tab was presented during discovery; no
answer is required to implement the requested replacement. Device selectors
inside GPU, Disks and Network keep all discovered hardware reachable without
creating an unbounded number of top-level tabs. Keyboard tab selection,
selected-state accessibility, visible focus and narrow-window overflow must
work. Preserve each screen's scroll position during a session.

Alternative considered: a three-tab Summary/Performance/Processes shell with
a second navigation rail matches the reference hierarchy more literally but
adds a navigation level. A Custom tab preserves the former visible canvas but
adds a second layout model. The direct screen strip best matches the request
for tabbed screens.

## Screen composition

| Screen | Reference composition and live content |
| --- | --- |
| Summary | Vertical CPU/frequency/temperature/GPU meters, CPU history beside top CPU processes, full-width memory history, compact subsystem strips below. |
| CPU | Overall segmented meter, responsive grid of per-logical-CPU history charts, current utilization/frequency/process/thread/uptime/load statistics. |
| Memory | Purple segmented capacity meter, dominant memory-use history, current capacity and composition statistics below. |
| GPU | Same performance-page visual grammar, device selector, utilization history, VRAM capacity, available temperature/power/clock/fan readings. |
| Disks | Device selector, dominant throughput history and capacity meter, read/write/IOPS/latency/capacity readings with their actual units and scopes. |
| Network | Interface selector, blue meter and dominant receive/transmit history, totals and connection information from that interface. |
| Energy | Yellow power history for a selected measured sensor, clearly named device and power scope, other measured power channels below. No invented whole-system wattage or process energy score. |
| Thermals | Orange temperature history, explicitly named hottest current sensor, temperature sensor chart grid. No inferred thermal-pressure health state. |
| Processes | Full-width sortable/searchable virtual table, row selection, usage shading and current process details below. Preserve identity-safe TERM/KILL actions and failure/cancellation behavior. |
| Settings | Existing appearance, font, sampling and named-preset controls in a fixed screen. |

Each screen has real loading, empty, stale and error states. Unavailable
individual sensor rows remain absent while their raw diagnostics and saved
preferences remain. An entirely unavailable subsystem receives one honest
empty state. Zero is a valid reading. Gaps do not become zeros or connected
history strokes. Charts label units and the displayed time span. Network and
disk pages start with one named device; no unlabeled aggregate or double
counting is introduced to imitate the reference's combined totals.

## Visual contract

At 1280 by 880, use approximately 16-pixel content gutters, 12-pixel section
gaps, 32-36-pixel screen headings, 12-14-pixel labels and dense table rows.
At the existing 960 by 640 minimum, reflow summary sections and CPU/sensor
grids and scroll the screen rather than shrink text. Keep the tab strip and
status line available. Large history charts should dominate each performance
page. Match the reference's neutral charcoal surfaces and subsystem hues:
CPU/disks green, memory purple, GPU/network blue, energy yellow and thermals
orange. Preserve the light theme with readable equivalents.

Segmented meters and grid-backed history charts are the characteristic
visual elements. Use native GPUI drawing, bounded history, real timestamps,
subtle colored area fills and a restrained trace glow. Keep numbers legible;
color is additional information rather than the only label or state cue.

## Integration and persistence

Reuse the existing sampling service, live model, bounded history, process
identity/action handling, storage ordering, error recovery and preset library.
Add the tabbed presentation around this existing controller. Keep legacy dock
metadata intact for configuration compatibility; it is not the visible UI.
Store active screen and selected device IDs with defaulted presentation state
in the existing workspace document. An older document opens at Summary and
retains its settings/sensor choices/presets. Bad configuration remains retained
with autosave blocked until explicit recovery. Selecting a removed device
shows an honest unavailable state or a clearly named available replacement.

Existing dock tests remain compatibility tests. The new production root needs
its own native tests and replay; passing an old dock fixture is not evidence
that the tabbed screen works. Update current product documentation and the
acceptance entry point to distinguish the new screen contract from historical
dock acceptance. Do not enable GitHub CI or Dependabot.

## Verification and delivery

Run model/app regressions for navigation and saved state, chart gaps/scales,
selection and configuration recovery; app compilation, formatting and lint;
collector tests and live source comparison. Use an isolated native display to
exercise every tab, device selection, narrow-window navigation, settings,
process operations and save/restart. Capture all reference-backed screens at
a consistent size and inspect them against the supplied images. Exercise
available zero and unavailable sensors and retain the evidence. Build and
smoke-test the release package, then install that verified binary. Keep the
user's current configuration and desktop process untouched during testing.
