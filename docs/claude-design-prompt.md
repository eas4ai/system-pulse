# Claude Design Prompt: Dockable System Monitor

## Project Context

Design a UI concept for a cross-platform desktop system monitor application — the first task manager with a fully user-customizable dockable panel layout. Built with Rust and a GPU-accelerated UI framework that renders at 120fps. This is a native desktop application, not a web app. The design should communicate performance, density, and precision.

The application is also a showcase for a production-grade component library (gpui-component), so the design must demonstrate the range and quality of the UI primitives: smooth scrolling charts, responsive data tables, interactive dock layouts, context menus, and rich theming.

---

## Design Direction

**Think btop meets a Bloomberg terminal.** Dense, data-rich, dark by default. Information-forward. Not flat-design-with-rounded-corners. Not Electron-app-with-whitespace. A native GPU-rendered tool that looks like it runs at 120fps.

Meters should feel alive — charts scrolling, bars filling, numbers ticking. The UI should communicate performance through its aesthetics. Every pixel earns its place.

**Avoid:** excessive whitespace, card-heavy layouts, mobile-influenced design patterns, rounded-everything softness. This is a power tool, not a consumer app.

**Reference mood:** trading terminals, flight instruments, studio DAW interfaces, high-density monitoring dashboards — but cleaner, more modern, without the visual debt of legacy software.

---

## Typography

**UI text (labels, headings, panel titles, menu items):**
Satoshi — geometric, contemporary, clean at small sizes. If unavailable, Inter or Noto Sans as alternatives.

**Numeric / monospace text (meter values, sensor readings, process table data):**
JetBrains Mono — excellent tabular figures, wide glyph coverage, readable at small sizes. Alternatively Noto Sans Mono or Fira Code.

**Typography treatment:**
- Sensor labels: small, subdued, secondary color
- Sensor values: prominent, mono font, primary color
- Panel titles: medium weight, UI font
- Process table: mono font throughout, tight line height
- Units (°C, W, MHz, GB, MB/s): slightly smaller than value, tertiary color

---

## Color Direction

**Primary palette:** dark theme. Deep charcoal or near-black backgrounds. Not pure #000000 — something with slight warmth or coolness that isn't fatiguing.

**Accent color:** a distinctive brand color for active states, selection highlights, and the primary chart line. Consider electric blue, teal, or a warm amber. Needs to read clearly against dark backgrounds and work as a line chart color.

**Sensor value colors:** consider color-coding by sensor health — green/normal, yellow/warning, red/critical thresholds. Subtle, not alarm-like. The app should feel calm when everything is healthy.

**Chart colors:** each data series needs a distinct color. For multi-line charts (RX/TX), use complementary colors. For per-core CPU grids, use a gradient or heatmap scale (cool blue → hot orange/red based on utilization).

**The light theme** should be a full inversion that works, not an afterthought. High contrast, readable, professional.

---

## Screens Needed

### Screen 1: Default Layout — First Launch (Hero Screen)

The hero image. A single application window showing the dock layout with multiple monitors visible simultaneously in a split arrangement.

**Layout:**
- Left side (~60% width), split vertically into two visible panels: CPU above GPU 0. The CPU panel shows an overall utilization line chart (smooth, scrolling, the hero visual) and a grid of mini bars — one per CPU core (imagine 24 cores for a Threadripper, each bar showing its utilization, creating a heatmap-like grid). GPU 0 shows utilization and VRAM below it. Each panel has its own compact header. Neither panel is hidden behind a tab.
- Right side top (~40% width, ~50% height): Memory monitor panel with a horizontal composition bar showing the RAM breakdown (used / cached / free as colored segments with labels), and below it a line chart showing memory usage over time.
- Right side bottom (~40% width, ~50% height): Process table showing PID, Name, CPU%, Memory columns. Rows populated with realistic process names (systemd, firefox, vllm-worker, Xorg, etc.). Sorted by CPU% descending. The table should demonstrate density — many visible rows, tight spacing, monospace numbers, alternating row shading or subtle grid lines.

**Window chrome:** standard OS title bar. The dock area fills the rest of the window. Dock dividers visible between the splits — subtle, draggable.

**The feeling:** you're looking at a live system. Charts are mid-scroll. Numbers are plausible. The per-core grid is partially active (some cores hot, most cool). It should be immediately obvious that this layout is customizable — the splits, draggable headers, and panel structure should read as "you can rearrange this."

---

### Screen 2: GPU Monitor Panel — Detailed View

A close-up of a single GPU monitor panel showing the full sensor mix with varied meter types. This demonstrates the visual rhythm of mixed meters within one panel.

**Panel title:** "GPU 0 — Radeon AI PRO R9700"

**Sensors displayed, top to bottom:**
1. **Utilization** — line chart, the hero sensor. Scrolling time-series, ~60 seconds visible. Chart area takes significant vertical space. Current value displayed as large text overlay (e.g., "47%").
2. **VRAM** — horizontal bar. "18.4 GB / 32.0 GB" label. Fill shows proportional usage. Colored segment.
3. **Temperature** — sparkline with current value. "62°C" in large mono text, tiny sparkline trace beside it showing recent history.
4. **Power Draw** — sparkline with current value. "187W" with sparkline trace.
5. **Clock Speed** — plain number. "2,340 MHz" in mono text, small label "Core Clock" above.
6. **Fan Speed** — plain number. "1,820 RPM" in mono text, small label "Fan" above.

**The feeling:** varied visual weight. The line chart dominates and draws the eye. The bar communicates capacity at a glance. The sparklines give trend context without taking much space. The numbers are quiet but present. Not a uniform grid — a deliberately composed vertical stack with visual hierarchy.

---

### Screen 3: Context Menu — Sensor Toggles

A GPU monitor panel with a right-click context menu open, showing the sensor visibility controls.

**Menu items:**
- ✓ Utilization
- ✓ VRAM
- ✓ Temperature
- ✓ Power Draw
- ✓ Clock Speed
- ☐ Fan Speed
- ―――――――――
- Meter Type ▸ (submenu indicator)
- ―――――――――
- Reset to Default

The unchecked "Fan Speed" communicates that the user has disabled it. The menu should look native — not a custom-styled overlay, but a real context menu that matches OS conventions. Clean, tight, no icons in the menu items (checkmarks only).

Show the GPU panel behind the menu with only 5 sensors visible (Fan Speed absent), making the cause-and-effect obvious.

---

### Screen 4: Alternate Layout — User Customized

The same application with the same monitors, but in a completely different spatial arrangement. This screen proves the dock customization is real — not a mockup trick.

**Layout:**
- Top row, horizontal split: GPU 0 (left ~50%) and GPU 1 (right ~50%), both showing utilization line charts and VRAM bars
- Middle row: CPU monitor spanning full width, showing the per-core grid horizontally (all 24 cores in a wide row of mini bars)
- Bottom left (~60%): Process table
- Bottom right (~40%): Memory monitor, compact, composition bar only

**Network monitor** visible as a narrow bottom dock strip showing RX/TX throughput sparklines inline.

**The feeling:** same data, radically different arrangement. A user who cares about GPU workloads built this layout. The dual GPU prominence, the wide CPU bar, the compact memory — it all tells a story about what this user watches. It should be visually obvious that this is the same app as Screen 1, just rearranged.

---

### Screen 5: Settings Panel

The settings panel docked as a right-side panel (approximately 300px wide), demonstrating that settings are a dock panel like any other, not a modal dialog.

**Sections, top to bottom:**

**Theme**
A grid of theme preview swatches — small rectangles showing the color palette of each theme. Options: Dark (default, highlighted), Light, Nord, Solarized Dark, High Contrast. Active theme has a visible selection indicator (border, checkmark, or highlight).

**Fonts**
Two dropdown selectors:
- "UI Font" — showing "Satoshi" selected, with a preview line of text below in that font
- "Mono Font" — showing "JetBrains Mono" selected, with a preview line of numbers below (e.g., "1,234.56 MHz 78.9%")

**Presets**
A vertical list of saved presets:
- Default (built-in, indicated)
- Minimal (built-in)
- GPU Focus (built-in)
- "My Inference Setup" (user-created)
- "Development" (user-created)

The active preset is highlighted. Below the list:
- A text input field for naming a new preset
- Buttons: "Save Current" and "Delete"

**Update Interval**
A segmented control or small group of radio-style options: 0.5s | **1s** | 2s | 5s

**The feeling:** clean, organized, not crowded. The settings panel is narrow and functional — it doesn't demand attention, it serves when needed. It looks like a natural part of the dock, not a foreign overlay.

---

### Screen 6 (Optional): Network & Disk Monitors

A supplementary screen showing the Network and Disk monitors to complete the visual catalog.

**Network monitor panel:**
- Interface name: "enp5s0" or "eth0"
- RX throughput: line chart (hero), blue line
- TX throughput: line chart overlaid or stacked, orange/amber line
- Current rates: "↓ 12.4 MB/s  ↑ 1.2 MB/s" in mono text
- RX/TX totals: plain numbers, "↓ 4.2 GB  ↑ 890 MB"

**Disk monitor panel:**
- Volume name: "/" or "nvme0n1p2"
- Read/Write throughput: dual sparklines or stacked line chart
- Current rates: "R: 45 MB/s  W: 12 MB/s"
- Capacity: horizontal bar, "420 GB / 1.0 TB"
- IOPS: plain number

---

## Design Constraints

- **Minimum window size:** approximately 960×640px. Design to this floor — the layout must be legible at this size.
- **Workspace overflow:** keep every enabled panel in its own region at a readable size. When panels exceed the viewport, show scroll affordances so users can reach them. Prefer vertical scrolling; allow horizontal overflow when required by the user's split arrangement. Never substitute tabs, automatically hide panels, or shrink the entire layout to force everything onto one screen. Include an overflow example at the minimum window size.
- **No custom title bar.** Use the standard OS window chrome. The dock area fills everything below it.
- **Dock dividers** should be visible but subtle — thin lines or narrow handles that change cursor on hover to indicate draggability.
- **Panel headers** should be compact: collapse/expand control, panel name, and close button. A collapsed header also retains a compact current summary. Headers act as drag handles, but activating a control must not begin a drag. Visible panels occupy separate regions; do not introduce tab bars or tab groups.
- **Sensor rows** can collapse in place to their label, current value, unit, and expand control. Fold away charts or detailed meters, not the current reading. Show an example with one expanded chart row and one collapsed value row.
- **Collapse defaults:** panels and rows start expanded. Collapse is an explicit user choice, remembered with the layout and presets. Expanding a panel restores its individual row choices; window resizing never collapses content automatically.
- **Context menus** should feel OS-native, not custom-styled. Checkmarks, separators, optional submenus. Clean and fast.
- **All text must be legible at the minimum window size.** Sensor labels at ~11-12px, values at ~13-14px, chart axis labels at ~10px. Nothing below 10px.

---

## What This Design Is Not

- Not a mobile app. No hamburger menus, no bottom navigation, no swipe gestures.
- Not a web dashboard. No cards with drop shadows floating in whitespace.
- Not a settings-first experience. The monitors ARE the app. Settings are secondary.
- Not a splash screen or onboarding flow. The app opens to live data immediately.
- Not skeuomorphic. No fake textures, no bevels, no 3D effects on meters. Modern, flat-but-not-empty.

---

## Deliverables

High-fidelity mockups of screens 1-5 (screen 6 optional). Dark theme for all screens. One additional mockup of screen 1 in light theme to demonstrate theme viability.

Each screen should be a self-contained image that could be used as a reference during implementation — clear enough that a developer can match spacing, colors, typography, and layout proportions from the mockup.
