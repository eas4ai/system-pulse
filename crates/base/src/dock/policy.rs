//! Optional layout restrictions owned by DockArea, not by individual panels.

use anyhow::{Result, ensure};
use std::collections::HashSet;

use super::{DockAreaState, DockPlacement, PaneRef, PaneTree, PanelInfo, PanelState};

/// Layout rules enforced by a dock area when installing, moving, or restoring panels.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum PanelPolicy {
    /// Preserve the framework's tab groups and tiles.
    #[default]
    Tabbed,
    /// Every panel occupies one singleton leaf within a split arrangement.
    Separate,
}

impl PanelPolicy {
    /// Whether panels may share tab groups. Enabled by default.
    pub fn allows_merging(self) -> bool {
        self == Self::Tabbed
    }

    /// Check persisted input before constructing panels or changing live state.
    /// The caller retains the original input when this returns an error.
    pub fn validate_state(self, state: &DockAreaState) -> Result<()> {
        if self == Self::Tabbed {
            return Ok(());
        }
        self.validate_panel_state(&state.center)?;
        for (expected, dock) in [
            (DockPlacement::Left, state.left_dock.as_ref()),
            (DockPlacement::Right, state.right_dock.as_ref()),
            (DockPlacement::Bottom, state.bottom_dock.as_ref()),
        ] {
            if let Some(dock) = dock {
                ensure!(
                    dock.placement() == expected,
                    "dock placement does not match its field"
                );
                ensure!(
                    f32::from(dock.size()).is_finite() && f32::from(dock.size()) > 0.,
                    "invalid dock size"
                );
                self.validate_panel_state(dock.panel())?;
            }
        }
        Ok(())
    }

    fn validate_panel_state(self, root: &PanelState) -> Result<()> {
        let mut pending = vec![root];
        while let Some(node) = pending.pop() {
            match &node.info {
                PanelInfo::Stack { sizes, axis } => {
                    ensure!(*axis <= 1, "invalid split axis");
                    ensure!(
                        sizes.len() == node.children.len(),
                        "split size count does not match children"
                    );
                    ensure!(
                        sizes
                            .iter()
                            .all(|size| f32::from(*size).is_finite() && f32::from(*size) >= 0.),
                        "invalid split size"
                    );
                }
                PanelInfo::Tabs { active_index } => {
                    ensure!(
                        node.children.len() <= 1 && *active_index == 0,
                        "separate panels require singleton groups"
                    );
                    ensure!(
                        node.children
                            .first()
                            .is_none_or(|child| matches!(child.info, PanelInfo::Panel(_))),
                        "a singleton group must contain a panel"
                    );
                }
                PanelInfo::Panel(_) => {
                    ensure!(
                        node.children.is_empty(),
                        "panel leaf contains layout children"
                    );
                }
                PanelInfo::Tiles { .. } => anyhow::bail!("tiles are not separate split regions"),
            }
            pending.extend(node.children.iter());
        }
        Ok(())
    }

    pub(crate) fn validate_tree(self, tree: &PaneTree) -> Result<()> {
        if self == Self::Tabbed {
            return Ok(());
        }
        let mut ids = HashSet::new();
        let mut pending = vec![tree.root()];
        while let Some(node) = pending.pop() {
            match node.kind() {
                PaneRef::Tabs { panels, .. } => {
                    ensure!(
                        panels.len() <= 1,
                        "separate panels require singleton groups"
                    );
                    for panel in panels {
                        ensure!(ids.insert(*panel), "panel occupies more than one region");
                    }
                }
                PaneRef::Tiles { .. } => anyhow::bail!("tiles are not separate split regions"),
                PaneRef::Split {
                    children, sizes, ..
                } => {
                    pending.extend(children);
                    ensure!(
                        children.len() == sizes.len(),
                        "split size count does not match children"
                    );
                    ensure!(
                        sizes.iter().all(|size| {
                            size.is_none_or(|size| {
                                f32::from(size).is_finite() && size >= gpui::px(0.)
                            })
                        }),
                        "invalid split size"
                    );
                }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dock::{DockAreaState, DockPlacement, PanelInfo, PanelState};
    use gpui::px;

    fn group(names: &[&str]) -> PanelState {
        PanelState {
            panel_name: "TabPanel".into(),
            children: names.iter().map(|name| PanelState::new(*name)).collect(),
            info: PanelInfo::tabs(0),
        }
    }

    fn state(center: PanelState) -> DockAreaState {
        DockAreaState {
            center,
            ..Default::default()
        }
    }

    #[test]
    fn separate_policy_rejects_multigroup_without_changing_input() {
        let input = state(group(&["CPU", "GPU"]));
        let original = input.clone();
        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
        assert_eq!(input, original);
        assert!(PanelPolicy::Tabbed.validate_state(&input).is_ok());
    }

    #[test]
    fn separate_policy_accepts_vertical_singletons_and_empty_workspace() {
        let input = state(PanelState {
            panel_name: "StackPanel".into(),
            children: vec![group(&["CPU"]), group(&["GPU"])],
            info: PanelInfo::Stack {
                sizes: vec![px(320.), px(240.)],
                axis: 1,
            },
        });
        assert!(PanelPolicy::Separate.validate_state(&input).is_ok());
        let empty = state(PanelState {
            panel_name: "StackPanel".into(),
            children: vec![],
            info: PanelInfo::Stack {
                sizes: vec![],
                axis: 1,
            },
        });
        assert!(PanelPolicy::Separate.validate_state(&empty).is_ok());
    }

    #[test]
    fn separate_policy_rejects_nested_and_side_dock_incompatibilities() {
        let invalid = group(&["CPU", "GPU"]);
        let mut input = state(group(&["Memory"]));
        input.left_dock = Some(super::super::DockState::new(
            invalid,
            DockPlacement::Left,
            px(240.),
            true,
        ));
        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
        input.left_dock = None;
        input.center.children = vec![group(&["CPU"])];
        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
    }

    #[test]
    fn separate_policy_rejects_tiles_and_bad_geometry() {
        let mut input = state(PanelState {
            panel_name: "Tiles".into(),
            children: vec![],
            info: PanelInfo::Tiles { metas: vec![] },
        });
        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
        input.center = PanelState {
            panel_name: "StackPanel".into(),
            children: vec![group(&["CPU"])],
            info: PanelInfo::Stack {
                sizes: vec![px(f32::NAN)],
                axis: 1,
            },
        };
        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
        input.center.info = PanelInfo::Stack {
            sizes: vec![px(20.)],
            axis: 2,
        };
        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
        input.center.info = PanelInfo::Stack {
            sizes: vec![],
            axis: 1,
        };
        assert!(PanelPolicy::Separate.validate_state(&input).is_err());
    }
}
