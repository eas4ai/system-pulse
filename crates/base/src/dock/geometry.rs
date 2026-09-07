use gpui::{Axis, Pixels, Size, px, size};

use super::{NodeId, PaneNode, PaneRef, PanelId};

/// Application-supplied geometry for a separate dock panel.
/// Both dimensions include the panel header.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PanelExtent {
    minimum: Size<Pixels>,
    preferred: Size<Pixels>,
    height_limit: Option<Pixels>,
}

impl PanelExtent {
    /// Clamp the minimum to at least one pixel and the preference to that minimum.
    pub fn new(minimum: Size<Pixels>, preferred: Size<Pixels>) -> Self {
        let minimum = size(minimum.width.max(px(1.)), minimum.height.max(px(1.)));
        Self {
            minimum,
            preferred: size(
                preferred.width.max(minimum.width),
                preferred.height.max(minimum.height),
            ),
            height_limit: None,
        }
    }

    /// Return header-only geometry, preserving the source expanded preference.
    pub fn collapsed(mut self, header_height: Pixels) -> Self {
        let height = header_height.max(px(1.));
        self.minimum.height = height;
        self.preferred.height = height;
        self.height_limit = Some(height);
        self
    }

    pub fn minimum(&self) -> Size<Pixels> {
        self.minimum
    }

    pub fn preferred(&self) -> Size<Pixels> {
        self.preferred
    }

    pub fn height_limit(&self) -> Option<Pixels> {
        self.height_limit
    }
}

pub(crate) struct MeasuredNode {
    pub(crate) id: NodeId,
    pub(crate) extent: PanelExtent,
    pub(crate) children: Vec<MeasuredNode>,
}

impl MeasuredNode {
    pub(crate) fn find(&self, id: NodeId) -> Option<&Self> {
        if self.id == id {
            return Some(self);
        }
        self.children.iter().find_map(|child| child.find(id))
    }
}

pub(crate) fn growing_child(children: &[MeasuredNode], axis: Axis) -> Option<NodeId> {
    children
        .iter()
        .rfind(|child| axis == Axis::Horizontal || child.extent.height_limit().is_none())
        .map(|child| child.id)
}

/// `None` from `panel` means hidden or absent, not a zero-size live panel.
/// Call with `honor_sizes=false` only for an explicit presentation change.
pub(crate) fn measure_node(
    node: &PaneNode,
    panel: &impl Fn(PanelId) -> Option<PanelExtent>,
    honor_sizes: bool,
) -> Option<MeasuredNode> {
    match node.kind() {
        PaneRef::Tabs { panels, .. } => {
            let extent = panels.iter().find_map(|id| panel(*id))?;
            Some(MeasuredNode {
                id: node.id(),
                extent,
                children: vec![],
            })
        }
        PaneRef::Tiles { .. } => None,
        PaneRef::Split {
            axis,
            children,
            sizes,
        } => {
            let mut measured = Vec::new();
            for (index, child) in children.iter().enumerate() {
                let Some(mut child) = measure_node(child, panel, honor_sizes) else {
                    continue;
                };
                if honor_sizes {
                    if let Some(Some(saved)) = sizes.get(index) {
                        match axis {
                            Axis::Horizontal => {
                                child.extent.preferred.width =
                                    (*saved).max(child.extent.minimum.width);
                            }
                            Axis::Vertical => {
                                child.extent.preferred.height = (*saved)
                                    .max(child.extent.minimum.height)
                                    .min(child.extent.height_limit.unwrap_or(Pixels::MAX));
                            }
                        }
                    }
                }
                measured.push(child);
            }
            if measured.is_empty() {
                return None;
            }
            let mut minimum = size(px(0.), px(0.));
            let mut preferred = minimum;
            let mut all_height_limited = true;
            let mut height_limit = px(0.);
            let grows = growing_child(&measured, axis);
            for child in &measured {
                let extent = child.extent;
                // Rendering fixes every sibling except the final growing one.
                // Ancestors must reserve that space instead of clipping it.
                let allocated_minimum = if Some(child.id) == grows {
                    extent.minimum
                } else {
                    extent.preferred
                };
                match axis {
                    Axis::Horizontal => {
                        minimum.width += allocated_minimum.width;
                        minimum.height = minimum.height.max(extent.minimum.height);
                        preferred.width += extent.preferred.width;
                        preferred.height = preferred.height.max(extent.preferred.height);
                        height_limit = height_limit.max(extent.height_limit.unwrap_or(px(0.)));
                    }
                    Axis::Vertical => {
                        minimum.width = minimum.width.max(extent.minimum.width);
                        minimum.height += allocated_minimum.height;
                        preferred.width = preferred.width.max(extent.preferred.width);
                        preferred.height += extent.preferred.height;
                        height_limit += extent.height_limit.unwrap_or(px(0.));
                    }
                }
                all_height_limited &= extent.height_limit.is_some();
            }
            Some(MeasuredNode {
                id: node.id(),
                extent: PanelExtent {
                    minimum,
                    preferred,
                    height_limit: all_height_limited.then_some(height_limit),
                },
                children: measured,
            })
        }
    }
}
