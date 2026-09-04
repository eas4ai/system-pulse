# Feature Spec: Dockable System Monitor

## Product Vision

A cross-platform, GPU-accelerated desktop system monitor built with Rust, GPUI, and gpui-component. The first system monitor with a fully user-customizable dockable layout. Each monitor (CPU, GPU, Memory, Disk, Network, Processes) is an independent dock panel the user arranges freely — split, stacked, resized. Visible panels appear together; panels are never grouped into tabs. Within each monitor, individual sensors are toggleable and orderable via context menu. Sensor data renders through user-selectable meter types with smart defaults.

The application doubles as the public proof of concept for Same Page, demonstrating spec-driven development with coding agents end to end. It also serves as a showcase for gpui-component's dock system, charting, data tables, and 120fps rendering.

**License:** GPL-3.0-or-later

**Platform:** Linux, macOS, Windows (Linux-primary for development)

**Repository:** Workspace crate within eas4ai/gpui-component

---

## Core Concepts

### Monitor

A panel category corresponding to a hardware subsystem or OS concern. Each monitor is an independent dock panel. Monitors are auto-discovered based on available hardware. One instance per logical unit — GPU 0 and GPU 1 are separate monitors, CPU is one monitor, each disk volume is a separate monitor, each network interface is a separate monitor.

### Sensor

An individual data point within a monitor. Has an identity, a data type, an enabled/disabled state, a display order, and a meter type selection. Examples: GPU 0 / Temperature, CPU / Core 3 Utilization, eth0 / TX Throughput. Sensors are auto-discovered from the backend and shown with sensible defaults. The user customizes via context menu.

### Meter

The visual representation of a sensor value. Multiple meter types exist. Not all meter types are compatible with all sensor data types. Each sensor has a default meter type chosen to balance visual interest, information density, and showcase value.

### Dock Layout

The spatial arrangement of monitor panels, managed by the gpui-component dock system (PaneTree / DockArea). Persisted and restored across sessions. The initial layout is a starting point; users can rearrange it and save it as serialized DockAreaState. Panels can be split horizontally or vertically, dragged to new positions, and resized via dividers. Each enabled panel occupies its own region. Tab grouping and dropping a panel onto another to create tabs are not available. Unconstrained slots flex to fill available space while preserving readable panel sizes. When the arrangement exceeds the viewport, the workspace scrolls instead of hiding panels or compressing them below their minimum sizes.

### Preset

A named snapshot of the entire application state: dock layout, monitor visibility, panel collapse states, sensor configuration (enabled states, ordering, meter types, row collapse states), color theme, and font selections. Users save, rename, recall, and delete presets. The app ships with built-in presets as starting points.

---

## Monitors

### CPU

**Sensors:** overall utilization, per-core utilization (one per logical core), frequency, temperature, load average (1m / 5m / 15m), process count, thread count, uptime

**Hero defaults:** overall utilization as line chart, per-core as mini bar grid

### GPU (one monitor per GPU instance)

**Sensors:** utilization %, VRAM used/total, temperature, power draw (W), clock speed (MHz), fan speed (RPM)

**Hero defaults:** utilization as line chart, VRAM as bar

**Backend:** abstracted trait with platform-specific implementations — NVML (NVIDIA), sysfs/DRM (AMD Linux), DXGI (Windows), IOKit (macOS)

### Memory

**Sensors:** RAM used/total, composition breakdown (app/cached/free), swap used/total, page faults

**Hero defaults:** RAM usage as composition bar, usage over time as line chart

### Disk (one monitor per volume)

**Sensors:** read throughput, write throughput, IOPS, latency, capacity used/total

**Hero defaults:** read/write throughput as stacked sparklines, capacity as bar

### Network (one monitor per interface)

**Sensors:** RX throughput, TX throughput, RX total, TX total, connection count

**Hero defaults:** RX/TX throughput as line chart

### Processes

**Not a sensor panel** — this is a data table.

**Columns:** PID, name, CPU%, memory, disk I/O, threads, user

**Features:** sortable columns, search/filter, context menu to end process, virtual-scrolling table (gpui-component table with virtual rows)

**Hero default:** sorted by CPU% descending

---

## Meter Types

| Meter | Description | Best for |
|-------|-------------|----------|
| Number | Plain value, optional trend indicator (↑↓→) | Low-priority sensors, counters, static values |
| Sparkline | Tiny inline history trace, no axes | Compact trend context alongside other meters |
| Line Chart | Time-series with axes, scrolling window | Hero sensors, active monitoring, primary focus |
| Bar | Horizontal fill against a known max | Utilization, capacity, anything with a ceiling |
| Radial Gauge | Circular gauge with needle or fill | Hero single-value at a glance, prominent display |

### Sensor-to-Meter Compatibility

| SensorKind | Available Meters | Default |
|------------|-----------------|---------|
| Percentage | number, sparkline, line, bar, radial | line |
| Temperature | number, sparkline, line, radial | sparkline |
| Rate (bytes/s, RPM) | number, sparkline, line | sparkline |
| Capacity (used/total) | number, bar | bar |
| Counter | number, sparkline | number |

Logic determines which meter types are available for each sensor based on its data kind. The user selects from the compatible subset. The defaults are chosen to create visual variety within each monitor panel — not uniform, but rhythmic.

---

## User Customization

### Monitor Visibility

Right-click the dock area background or a toolbar area. Context menu lists all discovered monitors with checkmarks. Toggle to show/hide. Hidden monitors retain their sensor configuration and reappear with it intact when re-enabled.

When a monitor is re-enabled, it is added as a separate split region, retaining its panel and sensor-row collapse states. The user drags it to their preferred position. The framework integration must insert it without merging it into another panel.

### Sensor Visibility and Ordering

Right-click a monitor panel. Context menu lists all available sensors for that monitor with checkmarks in their current display order. Click a sensor to toggle its visibility. Drag within the menu to reorder sensors (or drag sensor meter widgets directly within the panel body — to be determined in design phase).

### Meter Type Selection

Right-click a specific sensor/meter within a panel. Context menu shows compatible meter types for that sensor's data kind with a checkmark on the current selection. Click to switch. The meter updates immediately.

### Layout Arrangement

Drag panel headers to rearrange, drop on edges to split, and drag dividers to resize. Panels remain together in separate regions of the workspace; there are no tab bars or tab-merge drop targets. Use the gpui-component dock system for layout behavior. Verify that its integration can enforce these restrictions before implementing the application shell.

### Workspace Overflow

All enabled panels remain in the layout even when they do not fit on screen. Users scroll to reach panels outside the viewport. Prefer vertical scrolling; allow horizontal scrolling when the user's split arrangement exceeds the available width. Resizing the window must not automatically hide, collapse, or group panels, or reduce them below readable minimum sizes. Only an explicit show/hide action changes monitor visibility.

Workspace scrolling reveals whole panels. Content scrolling within a panel, such as the Processes table, remains independent. Both must be reachable through pointer and keyboard interaction without trapping navigation in a nested scroll region.

**Acceptance:** enable enough monitors to exceed the minimum-size window. Every enabled panel must be reachable by scrolling without selecting a tab or changing visibility. Resize the window and verify that the panel set and arrangement remain intact. Repeat with a long Processes table and confirm that both its rows and the other panels remain reachable.

### Panel and Sensor-Row Collapse

Users can collapse either a whole panel or an individual sensor row. Both expand in place:

- **Collapsed panel:** retain its header and a compact current summary, such as `CPU · 34%`. Fold away its body while keeping an expansion control visible.
- **Collapsed sensor row:** retain its label, current value, and unit. Fold away its chart or detailed meter while keeping the row in its current position.

All panels and sensor rows start expanded when there is no saved configuration. Collapse is always an explicit user action; window resizing never triggers it. Collapsing a panel preserves its individual row states. Expanding it restores those states. Collection and bounded history continue, so current values remain live and expansion does not restart the history.

Collapse does not disable a monitor or sensor. Explicitly hiding a monitor or sensor removes it from view; collapsing retains its header or value row. Save both collapse levels with the layout and include them in presets. The focused interaction contract is in [Workspace Visibility and Collapse](superpowers/specs/2026-09-04-workspace-visibility-design.md).

### Persistence

All customization persists across sessions:

- **Dock layout** — serialized via `DockAreaState` (JSON)
- **Panel presentation** — collapsed/expanded state and preferred expanded size, stored alongside dock layout
- **Sensor configuration** — enabled states, display order, meter type, and collapsed/expanded row state per sensor, stored alongside dock layout
- **Settings** — color theme, font selections, update interval
- **Active preset** — which preset is currently loaded

Saved on change, debounced to avoid excessive writes during drag operations.

---

## Settings Panel

The settings panel is itself a dockable panel — it can be placed beside other panels, resized, or closed like any monitor panel. It does not join a tab group and is not a modal dialog.

### Color Themes

Dark theme default. Light theme available. Additional themes possible (high contrast, solarized, nord-style). Uses gpui-component's theme system — `ThemeColor` semantic tokens, not hardcoded colors. Themes apply globally and immediately on selection.

### Typography

Font selection for two categories:

- **UI text** — labels, headings, menu items, panel titles. Candidates: Satoshi, Noto Sans, Inter
- **Numeric / monospace text** — meter values, process table data, sensor readings. Candidates: JetBrains Mono, Noto Sans Mono, Fira Code

Selection via dropdown from a curated list of bundled fonts. Not a system font picker. Font changes apply immediately.

### Presets

A named snapshot capturing the entire application state:

- Dock layout (which monitors are visible and where, plus panel collapse states)
- Sensor configuration per monitor (enabled states, ordering, meter types, row collapse states)
- Color theme
- Font selections

**Operations:**

- **Save** current state as a new named preset
- **Overwrite** an existing preset with current state
- **Rename** an existing preset
- **Delete** a user-created preset
- **Recall** a preset (applies immediately, replacing current state)

**Built-in presets** ship with the app as starting points. They can be duplicated and modified but not deleted. Examples:

- **Default** — balanced layout showing CPU, GPU, Memory, and Processes
- **Minimal** — CPU and Memory only, compact arrangement
- **GPU Focus** — all GPU instances prominent with full sensor display
- **Developer** — Processes table large, CPU and Memory supporting

### Update Interval

Polling rate for sensor data. Global setting, not per-monitor.

Options: 0.5s, 1s (default), 2s, 5s

---

## Default First Launch

On first launch with no saved state:

1. Auto-detect all available hardware (CPUs, GPUs, disks, network interfaces)
2. Generate a default layout that demonstrates visual range and dock capability
3. Apply the "Default" built-in preset

**Default layout concept:**

- Left ~60% top: CPU monitor (hero line chart + core grid)
- Left ~60% bottom: first GPU monitor, visible at the same time as CPU; when no GPU is available, CPU fills the left region
- Right ~40% top: Memory monitor (composition bar + usage line chart)
- Right ~40% bottom: Processes table (sorted by CPU%)

Network and Disk monitors are discovered and available in the monitor list but not shown in the initial layout to avoid clutter. The user adds them via context menu.

The defaults are chosen to showcase the range of meter types, the dock layout system, and the rendering performance — line charts scrolling, bars filling, per-core grids animating, the process table scrolling smoothly through hundreds of rows.

---

## Technical Architecture

### Data Layer

**System metrics:** `sysinfo` crate for cross-platform CPU, memory, disk, network, and process data.

**GPU metrics:** abstracted behind a `GpuBackend` trait with platform-specific implementations:

- Linux AMD: sysfs/DRM reads (amdgpu driver), referencing `amdgpu-sysfs` crate patterns
- Linux/Windows NVIDIA: NVML via `nvml-wrapper` crate
- Windows: DXGI for GPU enumeration and metrics
- macOS: IOKit for GPU metrics
- Fallback: DRM generic backend for unrecognized GPUs

**Polling:** configurable interval (default 1s). Each monitor's backend collects sensor readings on a timer tick. Sensor values stored in ring buffers for history (sparklines, line charts).

### Panel Layer

Each monitor is a struct implementing `gpui_base::dock::Panel`:

- `panel_name()` returns a stable identifier (e.g., "CpuMonitor", "GpuMonitor:0")
- Owns its sensor list and their configuration (enabled, order, meter type)
- Renders its enabled sensors as meter widgets in display order
- Registered in the panel registry via `register_panel` for layout persistence and restoration

### Meter Layer

Meter widgets are gpui-component elements:

- **Line chart** — gpui-component chart component with scrolling time window
- **Bar** — gpui-component progress bar or custom horizontal fill element
- **Sparkline** — lightweight custom element, minimal overhead
- **Number** — styled text with optional trend indicator
- **Radial gauge** — custom element using GPUI's GPU-accelerated path rendering

Each meter type is a component that accepts a sensor reading (current value + history buffer) and renders accordingly.

### Configuration Layer

Application state serialized as JSON:

- Dock layout via `DockAreaState` serialization (built into gpui-component)
- Sensor states (enabled, order, meter type) per monitor in a companion config file
- Settings (theme, fonts, interval) in the same config
- Presets stored as named state bundles

Config location follows platform conventions (XDG on Linux, Application Support on macOS, AppData on Windows).

Saved on change with debouncing. Loaded on startup.

### Process Management

The Processes monitor supports ending processes via context menu:

- **End task** — sends SIGTERM (Linux/macOS) or TerminateProcess (Windows)
- **Force quit** — sends SIGKILL (Linux/macOS) or forced termination (Windows)

Requires appropriate permissions. The application does not request elevated privileges — if a process cannot be killed due to permissions, the error is shown clearly.

---

## Window

**Minimum window size:** enforced via GPUI WindowOptions. Exact dimensions TBD in design phase — estimated ~960×640 minimum.

**Default theme:** dark

**Title bar:** standard OS title bar (not custom)

---

## Typography Direction

Modern sans-serif for UI elements. Monospace with tabular figures for numeric data.

**UI font candidates:** Satoshi (geometric, contemporary), Noto Sans (broad Unicode coverage, clean), Inter (proven UI font)

**Mono font candidates:** JetBrains Mono (ligatures, wide language support), Noto Sans Mono (matches Noto Sans family), Fira Code (popular, well-hinted)

Final selection in design phase. Fonts are bundled with the application, not loaded from the system.

---

## Out of Scope (Iteration 001)

- Services / startup apps / users panels
- Remote or multi-node monitoring
- Custom user-defined sensors or plugins
- Tray icon / background daemon mode
- Notifications or alerts on sensor thresholds
- Historical data beyond the session ring buffer (no database, no log export)
- System information page (static hardware details)

These may be considered for future iterations via Same Page's `next-iteration` workflow.

---

## Same Page Integration

This project is the proof of concept for eas4ai/same-page. The full Same Page spec set will be generated from this feature spec:

- **Glossary** — monitor, sensor, meter, dock layout, panel, preset (terms defined above)
- **Controlled-language requirements** — each requirement in Same Page Technical English with a falsifier
- **Evidence map** — coverage status and method for each requirement
- **Iteration contract** — scope boundary for iteration 001
- **Drift gate** — audits each development session against the spec

The repository will contain both the application source and the complete Same Page spec set, demonstrating the methodology on a real, non-trivial project.
