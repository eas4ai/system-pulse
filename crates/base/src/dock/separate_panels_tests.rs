use super::*;
use crate::dock::PanelPolicy;
use crate::dock::test_support::{TestPanel, drain, log_of};
use gpui::{TestAppContext, VisualTestContext};

fn setup(cx: &mut TestAppContext) -> (Entity<DockArea>, &mut VisualTestContext) {
    cx.update(|cx| {
        let _ = crate::Theme::global_mut(cx);
    });
    cx.add_window_view(|window, cx| DockArea::new("separate-test", Some(1), window, cx))
}

fn assert_singletons(area: &DockArea) {
    PanelPolicy::Separate.validate_tree(&area.center).unwrap();
    for pane in area.docks.values() {
        PanelPolicy::Separate.validate_tree(&pane.tree).unwrap();
    }
}

#[gpui::test]
fn separate_default_preserves_tabs_and_policy_change_is_transactional(cx: &mut TestAppContext) {
    let (area, cx) = setup(cx);
    cx.update(|window, cx| {
        let alpha = TestPanel::new("Alpha", cx);
        let beta = TestPanel::new("Beta", cx);
        area.update(cx, |area, cx| {
            area.set_center(DockLayout::tabs().panel(alpha).panel(beta), window, cx);
            let before = area.dump(cx);
            assert!(
                area.set_panel_policy(PanelPolicy::Separate, window, cx)
                    .is_err()
            );
            assert_eq!(area.panel_policy(), PanelPolicy::Tabbed);
            assert_eq!(area.dump(cx), before);
        });
    });
}

#[gpui::test]
fn separate_install_and_load_reject_before_live_state_changes(cx: &mut TestAppContext) {
    let (area, cx) = setup(cx);
    let log = log_of();
    cx.update(|window, cx| {
        let alpha = TestPanel::logging("Alpha", &log, cx);
        let beta = TestPanel::logging("Beta", &log, cx);
        area.update(cx, |area, cx| {
            area.set_panel_policy(PanelPolicy::Separate, window, cx)
                .unwrap();
            area.try_set_center(DockLayout::tabs().panel(alpha.clone()), window, cx)
                .unwrap();
            let before = area.dump(cx);
            let entities = area.container_entity_ids();
            drain(&log);
            assert!(
                area.try_set_center(
                    DockLayout::tabs().panel(alpha.clone()).panel(beta.clone()),
                    window,
                    cx,
                )
                .is_err()
            );
            assert!(
                area.try_set_dock(
                    DockPlacement::Left,
                    DockLayout::tabs().panel(alpha).panel(beta),
                    window,
                    cx,
                )
                .is_err()
            );
            let invalid = DockAreaState {
                version: Some(999),
                center: PanelState {
                    panel_name: "TabPanel".into(),
                    children: vec![PanelState::new("CPU"), PanelState::new("GPU")],
                    info: PanelInfo::tabs(0),
                },
                ..Default::default()
            };
            let original = invalid.clone();
            assert!(area.load(invalid.clone(), window, cx).is_err());
            assert_eq!(invalid, original);
            assert_eq!(area.dump(cx), before);
            assert_eq!(area.container_entity_ids(), entities);
            assert!(drain(&log).is_empty());
            assert_singletons(area);
        });
    });
}

#[gpui::test]
fn separate_merge_rejection_preserves_both_regions_and_source_handle(cx: &mut TestAppContext) {
    let (area, cx) = setup(cx);
    cx.update(|window, cx| {
        let alpha = TestPanel::new("Alpha", cx);
        let beta = TestPanel::new("Beta", cx);
        let alpha_id = PanelId::from(alpha.entity_id());
        let beta_id = PanelId::from(beta.entity_id());
        area.update(cx, |area, cx| {
            area.set_panel_policy(PanelPolicy::Separate, window, cx)
                .unwrap();
            area.try_set_center(DockLayout::tabs().panel(alpha.clone()), window, cx)
                .unwrap();
            area.try_set_dock(
                DockPlacement::Left,
                DockLayout::tabs().panel(beta),
                window,
                cx,
            )
            .unwrap();
            let target = area
                .layout(DockPlacement::Left)
                .unwrap()
                .find_panel_node(beta_id)
                .unwrap();
            let before = area.dump(cx);
            let entities = area.container_entity_ids();
            assert!(
                area.try_move_panel(
                    alpha_id,
                    InsertTarget::Tabs {
                        node: target,
                        ix: None,
                        activate: true,
                    },
                    window,
                    cx
                )
                .is_err()
            );
            assert!(
                area.try_move_panel(
                    alpha_id,
                    InsertTarget::Split {
                        node: NodeId::from_u64(u64::MAX),
                        placement: Placement::Top,
                        size: None,
                    },
                    window,
                    cx
                )
                .is_err()
            );
            assert_eq!(area.dump(cx), before);
            assert_eq!(area.container_entity_ids(), entities);
            assert_eq!(
                area.panel(alpha_id)
                    .unwrap()
                    .as_any()
                    .downcast_ref::<Entity<TestPanel>>()
                    .unwrap()
                    .entity_id(),
                alpha.entity_id()
            );
            assert_singletons(area);
        });
    });
}

#[gpui::test]
fn separate_edge_moves_and_reinsertion_keep_every_panel_in_its_own_region(cx: &mut TestAppContext) {
    let (area, cx) = setup(cx);
    cx.update(|window, cx| {
        let alpha = TestPanel::new("Alpha", cx);
        let beta = TestPanel::new("Beta", cx);
        let gamma = TestPanel::new("Gamma", cx);
        let alpha_id = PanelId::from(alpha.entity_id());
        let beta_id = PanelId::from(beta.entity_id());
        let gamma_id = PanelId::from(gamma.entity_id());
        area.update(cx, |area, cx| {
            area.set_panel_policy(PanelPolicy::Separate, window, cx)
                .unwrap();
            area.try_set_center(
                DockLayout::v_split()
                    .child(DockLayout::tabs().panel(alpha.clone()), Some(px(200.)))
                    .child(DockLayout::tabs().panel(beta), Some(px(200.))),
                window,
                cx,
            )
            .unwrap();
            for placement in [
                Placement::Left,
                Placement::Right,
                Placement::Top,
                Placement::Bottom,
            ] {
                let node = area.center.find_panel_node(beta_id).unwrap();
                area.try_move_panel(
                    alpha_id,
                    InsertTarget::Split {
                        node,
                        placement,
                        size: None,
                    },
                    window,
                    cx,
                )
                .unwrap();
                assert_ne!(
                    area.center.find_panel_node(alpha_id),
                    area.center.find_panel_node(beta_id)
                );
                assert_singletons(area);
            }
            let target = area.center.find_panel_node(beta_id).unwrap();
            area.add_panel_split_view(
                Arc::new(gamma),
                target,
                Placement::Bottom,
                Some(px(200.)),
                window,
                cx,
            )
            .unwrap();
            assert!(area.center.contains_panel(gamma_id));
            area.remove_panel(alpha.clone(), window, cx);
            area.add_panel(alpha, DockPlacement::Center, None, window, cx);
            assert_eq!(area.center.panels().count(), 3);
            assert_singletons(area);
            let dump = area.dump(cx);
            PanelPolicy::Separate.validate_state(&dump).unwrap();
        });
    });
}

#[gpui::test]
fn separate_failed_insert_does_not_register_a_panel_or_replace_a_live_handle(
    cx: &mut TestAppContext,
) {
    let (area, cx) = setup(cx);
    cx.update(|window, cx| {
        let alpha = TestPanel::new("Alpha", cx);
        let beta = TestPanel::new("Beta", cx);
        let beta_id = PanelId::from(beta.entity_id());
        let alpha_id = PanelId::from(alpha.entity_id());
        area.update(cx, |area, cx| {
            area.set_panel_policy(PanelPolicy::Separate, window, cx)
                .unwrap();
            area.try_set_center(DockLayout::tabs().panel(alpha.clone()), window, cx)
                .unwrap();
            let before = area.dump(cx);
            assert!(
                area.add_panel_split_view(
                    Arc::new(beta),
                    NodeId::from_u64(u64::MAX),
                    Placement::Top,
                    None,
                    window,
                    cx
                )
                .is_err()
            );
            assert!(area.panel(beta_id).is_none());
            let node = area.center.find_panel_node(alpha_id).unwrap();
            assert!(
                area.add_panel_split_view(Arc::new(alpha), node, Placement::Top, None, window, cx)
                    .is_err()
            );
            assert_eq!(area.dump(cx), before);
        });
    });
}

#[gpui::test]
fn separate_checked_move_rejects_wrong_node_kind_even_in_default_mode(cx: &mut TestAppContext) {
    let (area, cx) = setup(cx);
    cx.update(|window, cx| {
        let alpha = TestPanel::new("Alpha", cx);
        let beta = TestPanel::new("Beta", cx);
        let gamma = TestPanel::new("Gamma", cx);
        let alpha_id = PanelId::from(alpha.entity_id());
        area.update(cx, |area, cx| {
            area.set_center(DockLayout::tabs().panel(alpha), window, cx);
            area.set_dock(
                DockPlacement::Left,
                DockLayout::h_split()
                    .child(DockLayout::tabs().panel(beta), None)
                    .child(DockLayout::tabs().panel(gamma), None),
                window,
                cx,
            );
            let node = area.layout(DockPlacement::Left).unwrap().root().id();
            let before = area.dump(cx);
            assert!(
                area.try_move_panel(
                    alpha_id,
                    InsertTarget::Tabs {
                        node,
                        ix: None,
                        activate: true
                    },
                    window,
                    cx
                )
                .is_err()
            );
            assert_eq!(area.dump(cx), before);
            assert!(area.panel(alpha_id).is_some());
        });
    });
}
