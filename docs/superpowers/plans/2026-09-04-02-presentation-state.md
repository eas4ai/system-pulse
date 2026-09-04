# System Pulse Presentation State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the pure Rust state and fixture-reading boundary for independent panel/sensor collapse, retained history, and recoverable presentation snapshots.

**Architecture:** A small model crate holds stable-identity presentation maps and timestamped histories separately. The native shell supplies dock JSON, its structural validator, fixture samples, and file storage; this crate never imports GPUI or reads the operating system. Invalid saved input remains available in the session and blocks normal autosave until explicit recovery.

**Tech Stack:** Rust 2024, standard collections, workspace `serde` and `serde_json`, Rust integration tests.

---

## Execution boundary and ownership

Execute in the pinned `eas4ai/gpui-component` worktree prepared by the overview plan, with its root as the working directory. This planning repository contains the specification and these instructions; do not create application files here. The examined framework revision is `ba3433f0740ee5ba2b1db459af49229caf0c1bcc`.

Read [the approved contract](../specs/2026-09-04-workspace-visibility-design.md) before execution. This plan covers WV-05 through WV-09, WV-11, and the data-preservation portion of WV-12. Native layout, actual dock validation, focus, dragging, summary selection, rendering, file writes, and recovery controls are covered by companion plans. The framework and model tasks can be prepared independently, but serialize edits to the shared root `Cargo.toml` and `Cargo.lock`.

Complete each task's tests before marking it complete. Keep exactly one task in progress. Run the commands below from the execution worktree root. Use the real workspace lockfile; do not replace framework dependencies to make an integration check pass.

## File map

| File | Responsibility |
| --- | --- |
| `Cargo.toml` | Add one workspace member. |
| `Cargo.lock` | Workspace dependency resolution produced by Cargo. |
| `examples/system_pulse/model/Cargo.toml` | Pure model package; no GPUI dependency. |
| `examples/system_pulse/model/src/lib.rs` | Public exports consumed by the native example. |
| `examples/system_pulse/model/src/presentation.rs` | Saved panel/sensor choices keyed by stable strings. |
| `examples/system_pulse/model/src/readings.rs` | Bounded timestamped fixture histories and reading status. |
| `examples/system_pulse/model/src/persistence.rs` | Validated restoration and invalid-input autosave gate. |
| `examples/system_pulse/model/tests/presentation.rs` | Independent state, identities, ordering, and old-field defaults. |
| `examples/system_pulse/model/tests/readings.rs` | Live collapsed readings, history wrap, statuses, invalid samples. |
| `examples/system_pulse/model/tests/persistence.rs` | Snapshot/preset roundtrips and recovery preservation. |

## Public contract for the native shell

- `Workspace::new(dock: serde_json::Value)` creates schema 1 with no discovered panels. `panel_mut(stable_id)` and `PanelState::sensor_mut(stable_id)` insert missing defaults without replacing existing choices. Labels and discovery indexes never become identity keys.
- Panel and sensor state fields are public for simple event handlers: change `collapsed`, `visible`, `meter`, or `order` independently. `expanded_size` uses logical pixels and is changed only by expanded resize handling. Defaults are visible and expanded; default dimensions are 420 by 280 and the neutral meter default is `Meter::Number`. The native fixture catalog selects each new row's desired meter without overwriting restored state.
- `PanelState::visible_sensors()` returns rows ordered by saved `order`, then stable identity for equal order. It deliberately does not modify or remove hidden or absent rows. Current hardware presence lives in the native catalog/collector, separate from saved visibility.
- `Sample` contains `at_ms`, optional numeric `value`, formatted `text`, `unit`, and `ReadingStatus::{Current, Stale, Unavailable}`. Timestamps use one monotonic session clock, including unavailable updates. Compound readings may have no chart scalar. Stale text/value remain available to a compact summary; `chart_value()` produces a gap for stale/unavailable samples.
- `HistoryStore::new(capacity)` accepts 1 through 3600 samples per series. `push(monitor, sensor, sample)`, `latest(monitor, sensor)`, and `samples(monitor, sensor)` operate independently of presentation. Fixed native fixtures bound the series count for this proof; this is not the future live collector's discovery/retention policy. No history is persisted in layout or preset JSON.
- `Session { workspace, rejected: None }` starts a fresh session. `Session::restore(raw, fallback, validate_dock)` validates model fields and calls the supplied dock validator before installation. The fallback must be the native shell's known-valid default split arrangement. `RejectedInput` retains exact original text and a recoverable error. `autosave_json()` refuses serialization while rejection is present; `accept_recovery()` is called only by an explicit recovery action.
- Workspace serialization is also the preset snapshot format for this interaction scope. Full named preset CRUD, theme/font settings, meter compatibility, and OS collection are outside this approved contract. The native shell validates newly dumped dock JSON before writing and owns filesystem errors and atomic file replacement; `autosave_json()` does not claim to validate an opaque framework schema.

## Task 1: Add independent panel and sensor presentation state

**Files:** Create the model manifest, `src/lib.rs`, `src/presentation.rs`, and `tests/presentation.rs`; modify root `Cargo.toml` and generated `Cargo.lock`.

- [ ] **Step 1: Register the crate and add the failing behavior tests.**

Insert this member immediately after `examples/system_monitor` in the root manifest. Preserve other agents' member additions.

```diff
     "examples/system_monitor",
+    "examples/system_pulse/model",
```

Create `examples/system_pulse/model/Cargo.toml` with this complete content:

```toml
[package]
name = "system-pulse-model"
version = "0.1.0"
edition.workspace = true
publish.workspace = true
license = "GPL-3.0-or-later"

[dependencies]
serde.workspace = true
serde_json.workspace = true

[lints]
workspace = true
```

Create `examples/system_pulse/model/src/lib.rs` with this initial content:

```rust
//! Presentation state and fixture readings for System Pulse.
```

Create `examples/system_pulse/model/tests/presentation.rs`:

```rust
use serde_json::json;
use system_pulse_model::{ExpandedSize, Meter, Workspace};

#[test]
fn defaults_expand_panels_and_rows() {
    let mut workspace = Workspace::new(json!({"kind": "split"}));
    let panel = workspace.panel_mut("gpu:pci:0000:03:00.0");
    assert!(panel.visible);
    assert!(!panel.collapsed);
    let sensor = panel.sensor_mut("utilization");
    assert!(sensor.visible);
    assert!(!sensor.collapsed);
    assert_eq!(sensor.meter, Meter::Number);
}

#[test]
fn panel_row_meter_and_visibility_are_independent() {
    let mut workspace = Workspace::new(json!({}));
    let panel = workspace.panel_mut("cpu");
    panel.expanded_size = ExpandedSize {
        width: 600.0,
        height: 320.0,
    };
    panel.sensor_mut("overall").collapsed = true;
    panel.sensor_mut("temperature");
    panel.collapsed = true;
    panel.visible = false;
    panel.sensor_mut("overall").meter = Meter::Bar;
    panel.sensor_mut("overall").visible = false;
    panel.visible = true;
    panel.collapsed = false;
    panel.sensor_mut("overall").visible = true;
    assert!(panel.sensors["overall"].collapsed);
    assert!(!panel.sensors["temperature"].collapsed);
    assert_eq!(panel.sensors["overall"].meter, Meter::Bar);
    assert_eq!(panel.expanded_size.width, 600.0);
    assert_eq!(panel.expanded_size.height, 320.0);
    assert_eq!(
        panel
            .visible_sensors()
            .iter()
            .map(|(id, _)| *id)
            .collect::<Vec<_>>(),
        vec!["overall", "temperature"]
    );
}

#[test]
fn discovery_order_and_missing_devices_do_not_reassign_choices() {
    let mut workspace = Workspace::new(json!({}));
    workspace.panel_mut("gpu:uuid:A").collapsed = true;
    workspace
        .panel_mut("gpu:uuid:A")
        .sensor_mut("temperature")
        .collapsed = true;
    workspace.panel_mut("gpu:uuid:B");
    // A is absent from this discovery pass. Presence is collector data, not saved visibility.
    for id in ["gpu:uuid:B", "cpu"] {
        workspace.panel_mut(id);
    }
    assert!(workspace.panels["gpu:uuid:A"].collapsed);
    assert!(!workspace.panels["gpu:uuid:B"].collapsed);
    assert!(
        workspace
            .panel_mut("gpu:uuid:A")
            .sensor_mut("temperature")
            .collapsed
    );
}

#[test]
fn saved_order_survives_hiding_and_has_a_stable_tie_breaker() {
    let mut workspace = Workspace::new(json!({}));
    let panel = workspace.panel_mut("cpu");
    panel.sensor_mut("a").order = 2;
    panel.sensor_mut("b").order = 0;
    panel.sensor_mut("c").order = 0;
    panel.sensor_mut("b").visible = false;
    assert_eq!(
        panel
            .visible_sensors()
            .iter()
            .map(|(id, _)| *id)
            .collect::<Vec<_>>(),
        vec!["c", "a"]
    );
    panel.sensor_mut("b").visible = true;
    assert_eq!(
        panel
            .visible_sensors()
            .iter()
            .map(|(id, _)| *id)
            .collect::<Vec<_>>(),
        vec!["b", "c", "a"]
    );
}

#[test]
fn older_fields_default_to_expanded_and_dimensions_are_validated() {
    let mut workspace: Workspace = serde_json::from_value(json!({
        "dock": {}, "panels": { "cpu": { "sensors": { "overall": {} } } }
    }))
    .unwrap();
    assert!(!workspace.panels["cpu"].collapsed);
    assert!(!workspace.panels["cpu"].sensors["overall"].collapsed);
    assert!(workspace.validate().is_ok());
    workspace.panel_mut("cpu").expanded_size.width = f32::NAN;
    assert!(workspace.validate().is_err());
    workspace.panel_mut("cpu").expanded_size.width = 0.0;
    assert!(workspace.validate().is_err());
}
```

- [ ] **Step 2: Confirm the new tests fail before implementation.**

```bash
rtk cargo test -p system-pulse-model --test presentation
```

Expected: compilation fails on unresolved `ExpandedSize`, `Meter`, and `Workspace` imports. This establishes the absent public API; the assertions then verify actual state transitions once it exists. Dependency-fetch or unrelated workspace errors do not count as the expected failure.

- [ ] **Step 3: Implement the complete presentation module and exports.**

Create `examples/system_pulse/model/src/presentation.rs`:

```rust
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Meter {
    #[default]
    Number,
    Sparkline,
    Line,
    Bar,
    Radial,
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct ExpandedSize {
    pub width: f32,
    pub height: f32,
}

impl Default for ExpandedSize {
    fn default() -> Self {
        Self {
            width: 420.0,
            height: 280.0,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct SensorState {
    pub visible: bool,
    pub collapsed: bool,
    pub order: u32,
    pub meter: Meter,
}

impl Default for SensorState {
    fn default() -> Self {
        Self {
            visible: true,
            collapsed: false,
            order: 0,
            meter: Meter::Number,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct PanelState {
    pub visible: bool,
    pub collapsed: bool,
    pub expanded_size: ExpandedSize,
    pub sensors: BTreeMap<String, SensorState>,
}

impl Default for PanelState {
    fn default() -> Self {
        Self {
            visible: true,
            collapsed: false,
            expanded_size: ExpandedSize::default(),
            sensors: BTreeMap::new(),
        }
    }
}

impl PanelState {
    pub fn sensor_mut(&mut self, id: &str) -> &mut SensorState {
        let order = self
            .sensors
            .values()
            .map(|sensor| sensor.order)
            .max()
            .map_or(0, |order| order.saturating_add(1));
        self.sensors
            .entry(id.to_owned())
            .or_insert_with(|| SensorState {
                order,
                ..SensorState::default()
            })
    }

    pub fn visible_sensors(&self) -> Vec<(&str, &SensorState)> {
        let mut rows: Vec<_> = self
            .sensors
            .iter()
            .filter(|(_, sensor)| sensor.visible)
            .map(|(id, sensor)| (id.as_str(), sensor))
            .collect();
        rows.sort_by(|(id_a, a), (id_b, b)| a.order.cmp(&b.order).then_with(|| id_a.cmp(id_b)));
        rows
    }
}

fn schema_version() -> u32 {
    1
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Workspace {
    #[serde(default = "schema_version")]
    pub schema_version: u32,
    pub dock: Value,
    #[serde(default)]
    pub panels: BTreeMap<String, PanelState>,
}

impl Workspace {
    pub fn new(dock: Value) -> Self {
        Self {
            schema_version: schema_version(),
            dock,
            panels: BTreeMap::new(),
        }
    }

    pub fn panel_mut(&mut self, id: &str) -> &mut PanelState {
        self.panels.entry(id.to_owned()).or_default()
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != schema_version() {
            return Err(format!(
                "Unsupported presentation schema {}",
                self.schema_version
            ));
        }
        for (id, panel) in &self.panels {
            if id.trim().is_empty() {
                return Err("Empty monitor identity".into());
            }
            for value in [panel.expanded_size.width, panel.expanded_size.height] {
                if !value.is_finite() || value <= 0.0 || value > 16384.0 {
                    return Err(format!("Invalid preferred expanded size for {id}"));
                }
            }
            if panel.sensors.keys().any(|id| id.trim().is_empty()) {
                return Err(format!("Empty sensor identity in {id}"));
            }
        }
        Ok(())
    }
}
```

Replace `examples/system_pulse/model/src/lib.rs` with:

```rust
//! Presentation state and fixture readings for System Pulse.
mod presentation;
pub use presentation::{ExpandedSize, Meter, PanelState, SensorState, Workspace};
```

- [ ] **Step 4: Format and verify presentation behavior.**

```bash
rtk cargo fmt -p system-pulse-model
rtk cargo test -p system-pulse-model --test presentation
```

Expected: five tests pass, including saved-row independence, stable device identity, ordering after hiding, and defaults for omitted fields. Formatting must exit successfully.

- [ ] **Step 5: Commit the verified model foundation.**

```bash
rtk git add Cargo.toml Cargo.lock examples/system_pulse/model/Cargo.toml examples/system_pulse/model/src/lib.rs examples/system_pulse/model/src/presentation.rs examples/system_pulse/model/tests/presentation.rs
rtk git commit -m "feat: model independent monitor and sensor presentation"
```

## Task 2: Keep fixture readings live and bounded across collapse

**Files:** Create `src/readings.rs` and `tests/readings.rs`; modify `src/lib.rs` within `examples/system_pulse/model/`.

- [ ] **Step 1: Add the history and reading-status tests.**

Create `examples/system_pulse/model/tests/readings.rs`:

```rust
use serde_json::json;
use system_pulse_model::{HistoryStore, Meter, ReadingStatus, Sample, Workspace};

fn current(at_ms: u64, value: f64) -> Sample {
    Sample {
        at_ms,
        value: Some(value),
        text: format!("{value}"),
        unit: "%".into(),
        status: ReadingStatus::Current,
    }
}

#[test]
fn collapse_hide_and_meter_changes_preserve_live_bounded_history() {
    let mut workspace = Workspace::new(json!({}));
    let mut history = HistoryStore::new(3).unwrap();
    for tick in 1..=5 {
        let panel = workspace.panel_mut("cpu");
        panel.collapsed = tick >= 2;
        panel.sensor_mut("overall").collapsed = true;
        panel.sensor_mut("overall").visible = false;
        panel.sensor_mut("overall").meter = Meter::Bar;
        history
            .push("cpu", "overall", current(tick * 1000, tick as f64))
            .unwrap();
    }
    let samples = history.samples("cpu", "overall").unwrap();
    assert_eq!(
        samples.iter().map(|s| s.at_ms).collect::<Vec<_>>(),
        vec![3000, 4000, 5000]
    );
    assert_eq!(history.latest("cpu", "overall").unwrap().text, "5");
    workspace.panel_mut("cpu").collapsed = false;
    assert_eq!(history.samples("cpu", "overall").unwrap().len(), 3);
    assert!(workspace.panels["cpu"].sensors["overall"].collapsed);
}

#[test]
fn unavailable_and_stale_are_explicit_history_gaps() {
    let mut history = HistoryStore::new(4).unwrap();
    history.push("gpu:A", "util", current(1000, 34.0)).unwrap();
    let stale = Sample {
        at_ms: 2000,
        status: ReadingStatus::Stale,
        ..current(2000, 34.0)
    };
    history.push("gpu:A", "util", stale).unwrap();
    assert_eq!(history.latest("gpu:A", "util").unwrap().text, "34");
    assert_eq!(history.latest("gpu:A", "util").unwrap().chart_value(), None);
    history
        .push(
            "gpu:A",
            "util",
            Sample {
                at_ms: 3000,
                value: None,
                text: "Unavailable".into(),
                unit: "%".into(),
                status: ReadingStatus::Unavailable,
            },
        )
        .unwrap();
    assert_eq!(
        history
            .samples("gpu:A", "util")
            .unwrap()
            .iter()
            .map(Sample::chart_value)
            .collect::<Vec<_>>(),
        vec![Some(34.0), None, None]
    );
}

#[test]
fn fixture_serialization_retains_values_units_timestamps_and_status() {
    let sample: Sample = serde_json::from_str(
        r#"{
        "at_ms": 500, "value": 12.5, "text": "12.5", "unit": "MiB/s", "status": "current"
    }"#,
    )
    .unwrap();
    assert_eq!(sample.at_ms, 500);
    assert_eq!(sample.unit, "MiB/s");
    assert_eq!(sample.chart_value(), Some(12.5));
    assert_eq!(
        serde_json::from_str::<Sample>(&serde_json::to_string(&sample).unwrap()).unwrap(),
        sample
    );
}

#[test]
fn invalid_and_out_of_order_samples_do_not_mutate_history() {
    assert!(HistoryStore::new(0).is_err());
    assert!(HistoryStore::new(3601).is_err());
    let mut history = HistoryStore::new(2).unwrap();
    history.push("cpu", "overall", current(2000, 4.0)).unwrap();
    for invalid in [
        current(1000, 2.0),
        current(2000, 5.0),
        current(3000, f64::NAN),
        Sample {
            status: ReadingStatus::Unavailable,
            ..current(3000, 6.0)
        },
    ] {
        assert!(history.push("cpu", "overall", invalid).is_err());
    }
    assert_eq!(history.samples("cpu", "overall").unwrap().len(), 1);
    assert_eq!(history.latest("cpu", "overall").unwrap().value, Some(4.0));
    assert!(history.push("", "overall", current(3000, 2.0)).is_err());
}
```

- [ ] **Step 2: Confirm the reading API is absent.**

```bash
rtk cargo test -p system-pulse-model --test readings
```

Expected: unresolved imports for `HistoryStore`, `ReadingStatus`, and `Sample`. Tests assert bounded chronological retention while presentation changes, truthful stale/unavailable status, fixture serialization, and rejection without mutation.

- [ ] **Step 3: Implement the complete reading module and exports.**

Create `examples/system_pulse/model/src/readings.rs`:

```rust
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, VecDeque};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReadingStatus {
    Current,
    Stale,
    Unavailable,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Sample {
    /// Milliseconds on one session's monotonic fixture/collector clock.
    pub at_ms: u64,
    /// Optional scalar for the chosen chart; text can describe compound values.
    pub value: Option<f64>,
    pub text: String,
    pub unit: String,
    pub status: ReadingStatus,
}

impl Sample {
    pub fn chart_value(&self) -> Option<f64> {
        if self.status == ReadingStatus::Current {
            self.value
        } else {
            None
        }
    }

    fn validate(&self) -> Result<(), String> {
        if self.value.is_some_and(|value| !value.is_finite()) {
            return Err("Reading contains a non-finite chart value".into());
        }
        if self.status == ReadingStatus::Unavailable && self.value.is_some() {
            return Err("Unavailable reading cannot contain a measured value".into());
        }
        Ok(())
    }
}

#[derive(Debug)]
pub struct HistoryStore {
    capacity: usize,
    series: BTreeMap<(String, String), VecDeque<Sample>>,
}

impl HistoryStore {
    pub fn new(capacity: usize) -> Result<Self, String> {
        if !(1..=3600).contains(&capacity) {
            return Err("History capacity must be between 1 and 3600 samples".into());
        }
        Ok(Self {
            capacity,
            series: BTreeMap::new(),
        })
    }

    pub fn push(&mut self, monitor: &str, sensor: &str, sample: Sample) -> Result<(), String> {
        if monitor.trim().is_empty() || sensor.trim().is_empty() {
            return Err("Reading requires stable monitor and sensor identities".into());
        }
        sample.validate()?;
        let key = (monitor.to_owned(), sensor.to_owned());
        if self
            .series
            .get(&key)
            .and_then(|series| series.back())
            .is_some_and(|previous| sample.at_ms <= previous.at_ms)
        {
            return Err("Reading timestamps must increase within each series".into());
        }
        let series = self.series.entry(key).or_default();
        if series.len() == self.capacity {
            series.pop_front();
        }
        series.push_back(sample);
        Ok(())
    }

    pub fn latest(&self, monitor: &str, sensor: &str) -> Option<&Sample> {
        self.samples(monitor, sensor)
            .and_then(|series| series.back())
    }

    pub fn samples(&self, monitor: &str, sensor: &str) -> Option<&VecDeque<Sample>> {
        self.series.get(&(monitor.to_owned(), sensor.to_owned()))
    }
}
```

Replace `examples/system_pulse/model/src/lib.rs` with:

```rust
//! Presentation state and fixture readings for System Pulse.
mod presentation;
mod readings;
pub use presentation::{ExpandedSize, Meter, PanelState, SensorState, Workspace};
pub use readings::{HistoryStore, ReadingStatus, Sample};
```

The native fixture generator calls `push` on every collection tick regardless of panel/row visibility. Summary rendering calls `latest` using fixed primary sensor IDs even when the corresponding row is hidden. Do not create a polling loop inside a collapsed header.

- [ ] **Step 4: Verify the history contract and previous state tests.**

```bash
rtk cargo fmt -p system-pulse-model
rtk cargo test -p system-pulse-model --test readings
rtk cargo test -p system-pulse-model --test presentation
```

Expected: four reading tests and five presentation tests pass. Invalid/out-of-order samples leave the existing series unchanged. Chart gaps preserve chronological entries rather than injecting zero measurements.

- [ ] **Step 5: Commit the verified fixture-history boundary.**

```bash
rtk git add examples/system_pulse/model/src/lib.rs examples/system_pulse/model/src/readings.rs examples/system_pulse/model/tests/readings.rs
rtk git commit -m "feat: retain bounded readings across presentation changes"
```

## Task 3: Restore snapshots without destroying incompatible input

**Files:** Create `src/persistence.rs` and `tests/persistence.rs`; modify `src/lib.rs` within `examples/system_pulse/model/`.

- [ ] **Step 1: Add restoration, preset roundtrip, and autosave-gate tests.**

Create `examples/system_pulse/model/tests/persistence.rs`:

```rust
use serde_json::{Value, json};
use system_pulse_model::{Meter, Session, Workspace};

// This small test protocol exercises the injected adapter, not GPUI's JSON schema.
fn validate_dock(value: &Value) -> Result<(), String> {
    if value.get("kind").and_then(Value::as_str) == Some("split") {
        Ok(())
    } else {
        Err("A split layout is required; tab groups are incompatible".into())
    }
}

fn fallback() -> Workspace {
    Workspace::new(json!({"kind": "split", "panels": ["cpu"]}))
}

#[test]
fn layout_and_preset_roundtrips_keep_both_collapse_levels_and_geometry() {
    let mut workspace = fallback();
    workspace.dock = json!({"kind": "split", "axis": "vertical", "panels": ["cpu", "gpu:A"]});
    let panel = workspace.panel_mut("gpu:A");
    panel.collapsed = true;
    panel.expanded_size.width = 650.0;
    let sensor = panel.sensor_mut("utilization");
    sensor.collapsed = true;
    sensor.visible = false;
    sensor.meter = Meter::Line;
    sensor.order = 4;
    let preset = serde_json::to_string(&workspace).unwrap();
    let mut session = Session::restore(&preset, fallback(), validate_dock);
    assert!(session.rejected.is_none());
    assert_eq!(session.workspace, workspace);
    // Recall restores the same snapshot without modifying current readings.
    session.workspace.panel_mut("gpu:A").collapsed = false;
    session = Session::restore(&preset, fallback(), validate_dock);
    assert_eq!(session.workspace, workspace);
    assert_eq!(
        serde_json::from_str::<Workspace>(&session.autosave_json().unwrap()).unwrap(),
        workspace
    );
}

#[test]
fn incompatible_layout_retains_exact_input_and_blocks_autosave_until_recovery() {
    let original =
        " {\n \"dock\": {\"kind\":\"tabs\",\"panels\":[\"cpu\",\"gpu:A\"]}, \"panels\": {} } ";
    let mut session = Session::restore(original, fallback(), validate_dock);
    assert_eq!(session.workspace, fallback());
    assert_eq!(session.rejected.as_ref().unwrap().original, original);
    assert!(
        session
            .rejected
            .as_ref()
            .unwrap()
            .error
            .contains("tab groups")
    );
    session.workspace.panel_mut("cpu").collapsed = true;
    assert!(session.autosave_json().is_err());
    assert_eq!(session.rejected.as_ref().unwrap().original, original);
    session.accept_recovery();
    assert!(session.rejected.is_none());
    assert!(session.autosave_json().is_ok());
}

#[test]
fn malformed_json_future_schema_and_invalid_dimensions_are_retained() {
    for original in [
        "not json".to_string(),
        json!({"schema_version": 42, "dock": {"kind":"split"}}).to_string(),
        json!({"dock":{"kind":"split"}, "panels":{"cpu":{"expanded_size":{"width":-1,"height":280}}}}).to_string(),
    ] {
        let session = Session::restore(&original, fallback(), validate_dock);
        assert_eq!(session.workspace, fallback());
        assert_eq!(session.rejected.as_ref().unwrap().original, original);
        assert!(session.autosave_json().is_err());
    }
}

#[test]
fn autosave_revalidates_presentation_and_legacy_defaults_remain_expanded() {
    let mut session = Session::restore(
        r#"{"dock":{"kind":"split"},"panels":{"cpu":{"sensors":{"overall":{}}}}}"#,
        fallback(),
        validate_dock,
    );
    assert!(session.rejected.is_none());
    assert!(!session.workspace.panels["cpu"].collapsed);
    assert!(!session.workspace.panels["cpu"].sensors["overall"].collapsed);
    session.workspace.panel_mut("cpu").expanded_size.height = 0.0;
    assert!(session.autosave_json().is_err());
}
```

The test validator deliberately uses a tiny synthetic dock protocol. It proves validation injection and failure preservation; it does not claim that the actual GPUI dock schema uses a `kind` field. The native plan must supply its real `DockAreaState` deserialization and separate-region validator.

- [ ] **Step 2: Confirm restoration tests fail before implementation.**

```bash
rtk cargo test -p system-pulse-model --test persistence
```

Expected: unresolved `Session` import. A syntax error in the test data or a dependency failure is not the expected result.

- [ ] **Step 3: Implement restoration and explicit recovery.**

Create `examples/system_pulse/model/src/persistence.rs`:

```rust
use crate::Workspace;
use serde_json::Value;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RejectedInput {
    pub original: String,
    pub error: String,
}

#[derive(Debug)]
pub struct Session {
    pub workspace: Workspace,
    pub rejected: Option<RejectedInput>,
}

impl Session {
    /// The UI supplies a known-valid default split arrangement and dock validator.
    pub fn restore(
        raw: &str,
        fallback: Workspace,
        validate_dock: impl Fn(&Value) -> Result<(), String>,
    ) -> Self {
        let restored = serde_json::from_str::<Workspace>(raw)
            .map_err(|error| format!("Cannot read saved workspace: {error}"))
            .and_then(|workspace| {
                workspace.validate()?;
                validate_dock(&workspace.dock)?;
                Ok(workspace)
            });
        match restored {
            Ok(workspace) => Self {
                workspace,
                rejected: None,
            },
            Err(error) => Self {
                workspace: fallback,
                rejected: Some(RejectedInput {
                    original: raw.to_owned(),
                    error,
                }),
            },
        }
    }

    pub fn autosave_json(&self) -> Result<String, String> {
        if self.rejected.is_some() {
            return Err(
                "Autosave is blocked until explicit recovery of the saved workspace".into(),
            );
        }
        self.workspace.validate()?;
        serde_json::to_string_pretty(&self.workspace).map_err(|error| error.to_string())
    }

    /// Called only by the UI's explicit recovery action, never an autosave timer.
    pub fn accept_recovery(&mut self) {
        self.rejected = None;
    }
}
```

Replace `examples/system_pulse/model/src/lib.rs` with:

```rust
//! Presentation state and fixture readings for System Pulse.
mod persistence;
mod presentation;
mod readings;
pub use persistence::{RejectedInput, Session};
pub use presentation::{ExpandedSize, Meter, PanelState, SensorState, Workspace};
pub use readings::{HistoryStore, ReadingStatus, Sample};
```

The native adapter must construct a replacement session completely before installing a recalled preset. It must show `rejected.error`, retain the original file, and skip writes when `autosave_json` returns its recovery error. Ordinary collapse/resize handlers never call `accept_recovery`. Read failures other than file-not-found belong to the native storage error path and must not silently create an autosaving empty session.

- [ ] **Step 4: Run all model checks.**

```bash
rtk cargo fmt -p system-pulse-model
rtk cargo fmt -p system-pulse-model -- --check
rtk cargo test -p system-pulse-model
rtk cargo clippy -p system-pulse-model --all-targets -- -D warnings
```

Expected: all 13 integration tests pass, plus empty library/doc-test harnesses; formatting and Clippy exit successfully. A future schema, malformed JSON, invalid dimensions, and rejected dock geometry each retain their original text and block autosave. Explicit recovery clears the gate.

- [ ] **Step 5: Commit the verified restoration contract.**

```bash
rtk git add examples/system_pulse/model/src/lib.rs examples/system_pulse/model/src/persistence.rs examples/system_pulse/model/tests/persistence.rs
rtk git commit -m "feat: preserve invalid workspace input until explicit recovery"
```

## Evidence and handoff

| Contract | Model evidence | Required native evidence |
| --- | --- | --- |
| WV-05 | Default and omitted fields expand panels and rows. | First-run and restored views reflect those fields. |
| WV-06–WV-08 | Panel, row, meter, visibility, order, and expanded dimensions remain independent. | Header/body geometry, fixed summaries, and in-place expansion. |
| WV-09 | History continues across collapse/hide and remains bounded; stale/unavailable points stay explicit. | Native timer continues; expanded charts use the same series. |
| WV-11 | Stable-ID maps retain absent choices; layout and preset JSON preserve both collapse levels and dimensions. | Actual framework geometry roundtrip and hardware-catalog reconciliation. |
| WV-12 | Injected rejection preserves exact source and blocks autosave until explicit recovery. | Actual multi-panel dock rejection, recoverable message, and protected original file. |

Source lessons informing this design: TuxManager `src/historybuffer.h:114` retains a bounded ring; its process widget gates refresh work at `src/processeswidget.cpp:357`. Neohtop `src-tauri/src/monitoring/process_monitor.rs:98` demonstrates why PID/index-only identity and unpruned caches cannot substitute for the application's stable hardware/sensor keys. See the [reference review](../research/2026-09-04-reference-review.md) for snapshot roots and scope limits.

Planning-time verification: the full Rust snippets were assembled in a temporary standalone Rust 2024 crate with `serde` and `serde_json`. Each task's test suite was first run against missing exports and failed as specified; implementations then passed all 13 integration tests. `cargo fmt -- --check` and `cargo clippy --all-targets -- -D warnings` also passed on that standalone crate. This validates the embedded model code, not the future GPUI workspace build or native acceptance scenarios. Run the actual workspace commands during execution; do not claim this planning proof completes the approved feature.
