# System Pulse feature specification

The developer requested reference-based tabbed screens on 2026-09-07. This replaces the previous docked canvas. The [original dockable specification](archive/2026-09-07-original-dockable-spec.md) remains a historical record; its no-tabs rule and panel arrangement controls no longer define the visible product.

## Product

System Pulse is a native desktop system monitor written in Rust with GPUI Kit 0.6. It displays real host readings, timestamped history and identity-bound process information. Linux is the primary verification platform. Platform adapters do not establish hardware accuracy without a recorded native comparison. The application is GPL-3.0-or-later.

## Screens

The fixed navigation strip contains Summary, CPU, Memory, GPU, Disks, Network, Energy, Thermals, Processes and Settings. Tabs cannot be closed, dragged or merged. Summary opens by default; subsequent launches restore the last selected screen. Device selectors distinguish multiple GPUs, volumes, interfaces and environmental sensors by stable identity. A missing saved device stays explicitly unavailable until the user selects another.

The eight images in `reference/tmog.org/` guide the screen compositions, charcoal surfaces, geometric headings, subsystem colors, segmented meters and luminous history traces. See the [detailed design contract](superpowers/specs/2026-09-07-tabbed-screens-design.md).

| Screen | Content |
| --- | --- |
| Summary | Vertical CPU, clock, temperature and GPU meters; CPU history and top processes; memory history; compact subsystem readings. |
| CPU | Overall usage, every available logical processor's history and frequency, load, threads and uptime. |
| Memory | Physical RAM capacity/history, disjoint composition and available memory/swap statistics. |
| GPU | Selected GPU utilization/history, VRAM capacity, available temperature/power/clock/fan readings. |
| Disks | Named volume capacity, backing-device read/write history, available IOPS and latency. |
| Network | Named interface RX/TX history, counters and connection readings. |
| Energy | Named measured power channel and its scope, plus other available power charts. |
| Thermals | Selected temperature history, explicitly named hottest current sensor and available temperature charts. |
| Processes | Searchable, sortable virtual table with PID, name, CPU, memory, read/write throughput, threads and user; selected-process details and confirmed task actions. |
| Settings | Appearance and numeric fonts, sampling interval, sensor visibility, named preset controls. |

## Reading semantics

A monitor identifies a hardware or OS subsystem. A sensor identifies one physical reading within it. Native providers supply timestamps, units, status and provenance; the UI never fabricates readings to reproduce reference-image values.

Current zero remains a real value. Unavailable sensor rows disappear, while failed, stale and warming-up readings remain explicit. Chart gaps break strokes and fills. Charts label their physical scale and actual observed time span. History remains bounded while a screen or sensor is hidden. Dynamic-range segmented meters explain their observed-range scale; only percentage and known-capacity meters represent a fixed fraction.

Memory composition uses non-overlapping Other, Cache, Buffers and Free quantities from one observation. Disk capacity describes the filesystem, while transfer rates describe its backing block device. Network history belongs to the selected interface. Energy never invents whole-system wattage or process energy scores. Thermals never infers a pressure or health state from temperature alone.

## Interaction and state

Click tabs or use Left/Right/Home/End while a tab has focus. Ctrl+Tab and Ctrl+Shift+Tab cycle screens. The 960×640 minimum window keeps navigation available, reflows grids and scrolls content. Each screen retains its scroll position during a session. Process arrows/Home/End select rows; Left/Right scroll columns; Tab leaves the table.

Process selection uses PID plus start identity. Confirmed End task and Force quit operate only on that identity, report errors, and support cancellation. Unsupported platforms report unavailable actions explicitly.

Workspace JSON stores the active screen, selected device IDs, sensor choices, appearance and interval. Presets capture these settings. Old JSON defaults to Summary and preserves existing preferences. Legacy dock metadata remains readable and saved for compatibility, but does not hide fixed screens. Existing preset imports remain supported. Invalid configuration bytes remain untouched and autosave stays blocked until explicit recovery.

## Verification

`python3 -B scripts/system-pulse/verify.py` runs automated compatibility/model/collector/UI checks, independent live source comparisons, and the tabbed native replay. `application_acceptance.py` additionally builds a committed-source package and tests installed behavior. Native evidence covers every tab, device selection, physical labels, process actions, settings, presets, minimum size, restart, missing-device state and recovery. Historical no-tabs replay results apply only to their named old revisions. GitHub automation remains disabled.
