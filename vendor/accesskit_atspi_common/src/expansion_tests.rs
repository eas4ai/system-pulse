// Local regression tests for the patch described in ../PATCH.md.
// Licensed under Apache-2.0 OR MIT, like the vendored crate.

use std::sync::{Arc, Mutex};

use accesskit::{
    Action, ActionHandler, ActionRequest, Node, NodeId, Role, Tree, TreeId, TreeUpdate,
};

use crate::{
    Adapter, AdapterCallback, AppContext, Event, InterfaceSet, NodeIdOrRoot, ObjectEvent, State,
    WindowBounds,
};

const WINDOW: NodeId = NodeId(0);
const BUTTON: NodeId = NodeId(1);

#[derive(Clone, Default)]
struct RecordingCallback(Arc<Mutex<Vec<Event>>>);

impl AdapterCallback for RecordingCallback {
    fn register_interfaces(&self, _: &Adapter, _: crate::NodeId, _: InterfaceSet) {}

    fn unregister_interfaces(&self, _: &Adapter, _: crate::NodeId, _: InterfaceSet) {}

    fn emit_event(&self, _: &Adapter, event: Event) {
        self.0.lock().unwrap().push(event);
    }
}

impl RecordingCallback {
    fn take_expansion_events(&self) -> Vec<(crate::NodeId, State, bool)> {
        std::mem::take(&mut *self.0.lock().unwrap())
            .into_iter()
            .filter_map(|event| match event {
                Event::Object {
                    target: NodeIdOrRoot::Node(id),
                    event: ObjectEvent::StateChanged(state @ (State::Expandable | State::Expanded), value),
                } => Some((id, state, value)),
                _ => None,
            })
            .collect()
    }
}

struct NoActions;

impl ActionHandler for NoActions {
    fn do_action(&mut self, _: ActionRequest) {
        panic!("state queries and updates must not invoke actions");
    }
}

fn button(expanded: Option<bool>) -> Node {
    let mut node = Node::new(Role::Button);
    node.set_label("Processes");
    node.add_action(Action::Click);
    if let Some(expanded) = expanded {
        node.set_expanded(expanded);
    }
    node
}

fn adapter(expanded: Option<bool>) -> (Adapter, RecordingCallback) {
    let mut window = Node::new(Role::Window);
    window.set_children([BUTTON]);
    let callback = RecordingCallback::default();
    let adapter = Adapter::new(
        &AppContext::new(None),
        callback.clone(),
        TreeUpdate {
            nodes: vec![(WINDOW, window), (BUTTON, button(expanded))],
            tree: Some(Tree::new(WINDOW)),
            tree_id: TreeId::ROOT,
            focus: WINDOW,
        },
        true,
        WindowBounds::default(),
        NoActions,
    );
    callback.take_expansion_events();
    (adapter, callback)
}

fn button_id(adapter: &Adapter) -> crate::NodeId {
    adapter
        .platform_node(adapter.root_id())
        .child_at_index(0)
        .unwrap()
        .unwrap()
}

#[test]
fn button_expansion_state_distinguishes_absent_collapsed_and_expanded() {
    for (expanded, expandable, is_expanded) in [
        (None, false, false),
        (Some(false), true, false),
        (Some(true), true, true),
    ] {
        let (adapter, _) = adapter(expanded);
        let node = adapter.platform_node(button_id(&adapter));
        assert_eq!(node.role().unwrap(), crate::Role::Button);
        let states = node.state();
        assert_eq!(
            states.contains(State::Expandable),
            expandable,
            "{expanded:?}"
        );
        assert_eq!(
            states.contains(State::Expanded),
            is_expanded,
            "{expanded:?}"
        );
    }
}

#[test]
fn button_expansion_updates_emit_only_changed_states() {
    let (mut adapter, callback) = adapter(None);
    let id = button_id(&adapter);
    for (expanded, expected) in [
        (None, vec![]),
        (Some(false), vec![(id, State::Expandable, true)]),
        (Some(false), vec![]),
        (Some(true), vec![(id, State::Expanded, true)]),
        (Some(true), vec![]),
        (Some(false), vec![(id, State::Expanded, false)]),
        (None, vec![(id, State::Expandable, false)]),
        (None, vec![]),
    ] {
        adapter.update(TreeUpdate {
            nodes: vec![(BUTTON, button(expanded))],
            tree: None,
            tree_id: TreeId::ROOT,
            focus: WINDOW,
        });
        assert_eq!(callback.take_expansion_events(), expected, "{expanded:?}");
        let states = adapter.platform_node(button_id(&adapter)).state();
        assert_eq!(states.contains(State::Expandable), expanded.is_some());
        assert_eq!(states.contains(State::Expanded), expanded == Some(true));
    }
}
