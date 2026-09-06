//! Built-in dock templates resolved against discovered monitor identities.
use gpui::{Axis, px};
use gpui_base::dock::{DockAreaState, PanelInfo, PanelState};
use system_pulse_model::{BuiltinPreset, MonitorDescriptor, Workspace};

pub(crate) fn is_gpu(id: &str) -> bool {
    ["gpu:", "nvidia:", "amdgpu:", "intel:"]
        .into_iter()
        .any(|prefix| id.starts_with(prefix))
}

fn leaf(id: &str) -> PanelState {
    let mut leaf = PanelState::new("SystemPulseMonitor");
    leaf.info = PanelInfo::panel(serde_json::json!({"monitor_id":id}));
    PanelState {
        panel_name: "TabPanel".into(),
        children: vec![leaf],
        info: PanelInfo::tabs(0),
    }
}
fn stack(axis: Axis, children: Vec<PanelState>, extent: f32) -> PanelState {
    PanelState {
        panel_name: "StackPanel".into(),
        info: PanelInfo::stack(vec![px(extent); children.len()], axis),
        children,
    }
}

pub(crate) fn preset(kind: BuiltinPreset, catalog: &[MonitorDescriptor]) -> Workspace {
    let cpu = catalog
        .iter()
        .find(|m| matches!(m.id.as_str(), "cpu:host" | "cpu"));
    let memory = catalog
        .iter()
        .find(|m| matches!(m.id.as_str(), "memory:host" | "memory"));
    let gpus: Vec<_> = catalog.iter().filter(|m| is_gpu(&m.id)).collect();
    let processes = catalog.iter().find(|m| m.id == "processes");
    let mut left = Vec::new();
    let mut right = Vec::new();
    match kind {
        BuiltinPreset::Default => {
            left.extend(cpu);
            left.extend(gpus.first().copied());
            right.extend(memory);
            right.extend(processes);
        }
        BuiltinPreset::Minimal => {
            left.extend(cpu);
            left.extend(memory);
            right.extend(processes);
        }
        BuiltinPreset::GpuFocus => {
            left.extend(gpus);
            right.extend(memory);
            right.extend(processes);
        }
        BuiltinPreset::Developer => {
            left.extend(cpu);
            left.extend(memory);
            left.extend(
                catalog
                    .iter()
                    .filter(|m| m.id.starts_with("interface:") || m.id.starts_with("volume:")),
            );
            right.extend(processes);
            right.extend(gpus.first().copied());
        }
    }
    let visible: std::collections::BTreeSet<_> =
        left.iter().chain(&right).map(|m| m.id.clone()).collect();
    let columns: Vec<_> = [left, right]
        .into_iter()
        .filter(|column| !column.is_empty())
        .map(|column| {
            stack(
                Axis::Vertical,
                column.iter().map(|m| leaf(&m.id)).collect(),
                300.,
            )
        })
        .collect();
    let dock = DockAreaState {
        version: Some(1),
        center: stack(Axis::Horizontal, columns, 440.),
        left_dock: None,
        right_dock: None,
        bottom_dock: None,
    };
    let mut workspace =
        Workspace::new(serde_json::to_value(dock).expect("built-in dock serializes"));
    crate::live::discover(&mut workspace, catalog);
    for (id, panel) in &mut workspace.panels {
        panel.visible = visible.contains(id);
    }
    workspace
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn builtins_resolve_independent_valid_dock_panels_and_protect_hidden_devices() {
        let catalog = crate::fixture::catalog();
        for kind in BuiltinPreset::ALL {
            let workspace = preset(kind, &catalog);
            workspace.validate().unwrap();
            super::super::workspace::validate_dock_mode(&workspace.dock, true).unwrap();
            assert!(workspace.panels["processes"].visible);
            assert!(!workspace.panels["settings"].visible);
        }
        let default = preset(BuiltinPreset::Default, &catalog);
        assert!(default.panels["gpu:fixture-a"].visible);
        assert!(!default.panels["gpu:fixture-b"].visible);
        assert!(!default.panels["volume:fixture-home"].visible);
        let minimal = preset(BuiltinPreset::Minimal, &catalog);
        assert!(!minimal.panels["gpu:fixture-a"].visible);
        let gpu = preset(BuiltinPreset::GpuFocus, &catalog);
        assert!(gpu.panels["gpu:fixture-a"].visible && gpu.panels["gpu:fixture-b"].visible);
        let developer = preset(BuiltinPreset::Developer, &catalog);
        assert!(developer.panels["interface:fixture-lan"].visible);
    }
}
