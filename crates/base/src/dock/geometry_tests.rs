use gpui::{Axis, px, size};

use super::geometry::{PanelExtent, measure_node};
use super::{NodeId, PaneNode, PanelId, layout::NodeKind};

fn leaf(id: u64) -> PaneNode {
    PaneNode::new(
        NodeId::from_u64(id),
        NodeKind::Tabs {
            panels: vec![PanelId::from_u64(id)],
            active_ix: 0,
        },
    )
}

fn column() -> PaneNode {
    PaneNode::new(
        NodeId::from_u64(10),
        NodeKind::Split {
            axis: Axis::Vertical,
            children: vec![leaf(1), leaf(2)],
            sizes: vec![Some(px(480.)), Some(px(280.))],
        },
    )
}

fn expanded() -> PanelExtent {
    PanelExtent::new(size(px(320.), px(220.)), size(px(420.), px(280.)))
}

#[test]
fn collapse_releases_height_without_overwriting_expanded_preference() {
    let source = expanded();
    let collapsed = source.collapsed(px(36.));
    assert_eq!(source.preferred().height, px(280.));
    assert_eq!(collapsed.minimum().height, px(36.));
    assert_eq!(collapsed.preferred().height, px(36.));
    assert_eq!(collapsed.height_limit(), Some(px(36.)));
}

#[test]
fn stale_saved_split_height_cannot_expand_a_collapsed_panel() {
    let measured = measure_node(
        &column(),
        &|id| {
            Some(if id.as_u64() == 1 {
                expanded().collapsed(px(36.))
            } else {
                expanded()
            })
        },
        true,
    )
    .unwrap();
    assert_eq!(measured.extent.preferred(), size(px(420.), px(316.)));
    assert_eq!(measured.extent.minimum(), size(px(320.), px(256.)));
}

#[test]
fn explicit_expansion_reseeds_from_retained_preferences() {
    let preferred = measure_node(&column(), &|_| Some(expanded()), false).unwrap();
    let saved = measure_node(&column(), &|_| Some(expanded()), true).unwrap();
    assert_eq!(preferred.extent.preferred().height, px(560.));
    assert_eq!(saved.extent.preferred().height, px(760.));
}

#[test]
fn hidden_panel_has_no_slot_but_collapsed_panel_retains_header() {
    let measured = measure_node(
        &column(),
        &|id| (id.as_u64() == 1).then(|| expanded().collapsed(px(36.))),
        false,
    )
    .unwrap();
    assert_eq!(measured.children.len(), 1);
    assert_eq!(measured.extent.preferred().height, px(36.));
    assert_eq!(measured.extent.height_limit(), Some(px(36.)));
}

#[test]
fn horizontal_sibling_does_not_force_collapsed_body_to_request_height() {
    let row = PaneNode::new(
        NodeId::from_u64(11),
        NodeKind::Split {
            axis: Axis::Horizontal,
            children: vec![leaf(1), leaf(2)],
            sizes: vec![None, None],
        },
    );
    let measured = measure_node(
        &row,
        &|id| {
            Some(if id.as_u64() == 1 {
                expanded().collapsed(px(36.))
            } else {
                expanded()
            })
        },
        false,
    )
    .unwrap();
    assert_eq!(measured.extent.preferred(), size(px(840.), px(280.)));
    assert_eq!(
        measured
            .find(NodeId::from_u64(1))
            .unwrap()
            .extent
            .height_limit(),
        Some(px(36.))
    );
    assert_eq!(measured.extent.height_limit(), None);
}

#[test]
fn saved_sizes_never_compress_panels_below_readable_minimum() {
    let root = PaneNode::new(
        NodeId::from_u64(12),
        NodeKind::Split {
            axis: Axis::Vertical,
            children: vec![leaf(1)],
            sizes: vec![Some(px(8.))],
        },
    );
    let measured = measure_node(&root, &|_| Some(expanded()), true).unwrap();
    assert_eq!(measured.extent.preferred().height, px(220.));
}

#[test]
fn extent_constructor_enforces_positive_minimum_and_preferred_floor() {
    let extent = PanelExtent::new(size(px(-10.), px(0.)), size(px(0.), px(-1.)));
    assert_eq!(extent.minimum(), size(px(1.), px(1.)));
    assert_eq!(extent.preferred(), extent.minimum());
    assert_eq!(extent.collapsed(px(-3.)).height_limit(), Some(px(1.)));
}

#[test]
fn nested_collapsed_rows_limit_the_whole_column() {
    let row = PaneNode::new(
        NodeId::from_u64(11),
        NodeKind::Split {
            axis: Axis::Horizontal,
            children: vec![leaf(1), leaf(2)],
            sizes: vec![Some(px(600.)), Some(px(500.))],
        },
    );
    let root = PaneNode::new(
        NodeId::from_u64(12),
        NodeKind::Split {
            axis: Axis::Vertical,
            children: vec![row, leaf(3)],
            sizes: vec![Some(px(700.)), Some(px(800.))],
        },
    );
    let measured = measure_node(&root, &|_| Some(expanded().collapsed(px(36.))), true).unwrap();
    assert_eq!(measured.extent.preferred(), size(px(1100.), px(72.)));
    assert_eq!(measured.extent.height_limit(), Some(px(72.)));
    assert!(measure_node(&root, &|_| None, true).is_none());
}
