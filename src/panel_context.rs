//! The same actions back pointer context menus and keyboard-accessible buttons.
use crate::workspace::{Command, Shared};
use gpui::*;
use gpui_component::{
    Sizable,
    button::{Button, ButtonVariants},
    menu::{DropdownMenu, PopupMenu, PopupMenuItem},
};
use system_pulse_model::SensorMove;

fn item(label: String, command: Command, shared: &Shared) -> PopupMenuItem {
    let shared = shared.clone();
    PopupMenuItem::new(label).on_click(move |_, window, cx| {
        let owner = shared.borrow().owner.clone();
        if let Some(owner) = owner {
            let _ = owner.update(cx, |owner, cx| owner.command(command.clone(), window, cx));
        }
    })
}

pub(crate) fn sensors(
    mut menu: PopupMenu,
    monitor: &str,
    sensor: &str,
    shared: &Shared,
) -> PopupMenu {
    let data = shared.borrow();
    let Some(descriptor) = data
        .catalog
        .iter()
        .find(|m| m.id == monitor)
        .and_then(|m| m.sensors.iter().find(|s| s.id == sensor))
    else {
        return menu;
    };
    let Some(panel) = data.session.workspace.panels.get(monitor) else {
        return menu;
    };
    let Some(state) = panel.sensors.get(sensor) else {
        return menu;
    };
    menu = menu
        .item(item(
            format!("{} sensor", if state.visible { "Hide" } else { "Show" }),
            Command::SensorVisible(monitor.into(), sensor.into()),
            shared,
        ))
        .item(item(
            format!(
                "{} meter",
                if state.collapsed {
                    "Expand"
                } else {
                    "Collapse"
                }
            ),
            Command::RowCollapse(monitor.into(), sensor.into()),
            shared,
        ))
        .separator()
        .item(item(
            "Move up".into(),
            Command::SensorMove(monitor.into(), sensor.into(), SensorMove::Up),
            shared,
        ))
        .item(item(
            "Move down".into(),
            Command::SensorMove(monitor.into(), sensor.into(), SensorMove::Down),
            shared,
        ))
        .separator();
    for meter in descriptor.quantity.meters() {
        menu = menu.item(
            item(
                format!("{meter:?}"),
                Command::SensorMeter(monitor.into(), sensor.into(), *meter),
                shared,
            )
            .checked(state.meter == *meter),
        );
    }
    menu
}

pub(crate) fn monitor(mut menu: PopupMenu, id: &str, shared: &Shared) -> PopupMenu {
    let data = shared.borrow();
    let Some(panel) = data.session.workspace.panels.get(id) else {
        return menu;
    };
    menu = menu
        .item(item(
            format!("{} monitor", if panel.visible { "Hide" } else { "Show" }),
            Command::PanelVisible(id.into()),
            shared,
        ))
        .item(item(
            format!(
                "{} monitor",
                if panel.collapsed {
                    "Expand"
                } else {
                    "Collapse"
                }
            ),
            Command::PanelCollapse(id.into()),
            shared,
        ))
        .separator();
    if let Some(monitor) = data.catalog.iter().find(|m| m.id == id) {
        for sensor in &monitor.sensors {
            let visible = panel.sensors.get(&sensor.id).is_some_and(|s| s.visible);
            menu = menu.item(
                item(
                    format!("{} {}", if visible { "Hide" } else { "Show" }, sensor.title),
                    Command::SensorVisible(id.into(), sensor.id.clone()),
                    shared,
                )
                .checked(visible),
            );
        }
    }
    menu
}

pub(crate) fn workspace(mut menu: PopupMenu, shared: &Shared) -> PopupMenu {
    let data = shared.borrow();
    for monitor in &data.catalog {
        let visible = data
            .session
            .workspace
            .panels
            .get(&monitor.id)
            .is_some_and(|p| p.visible);
        menu = menu.item(
            item(
                format!(
                    "{} {}",
                    if visible { "Hide" } else { "Show" },
                    monitor.title
                ),
                Command::PanelVisible(monitor.id.clone()),
                shared,
            )
            .checked(visible),
        );
    }
    menu
}

pub(crate) fn sensor_button(monitor: String, sensor: String, shared: Shared) -> AnyElement {
    let title = shared
        .borrow()
        .catalog
        .iter()
        .find(|m| m.id == monitor)
        .and_then(|m| m.sensors.iter().find(|s| s.id == sensor))
        .map(|s| s.title.clone())
        .unwrap_or_else(|| sensor.clone());
    let id = format!("{monitor}:options:{sensor}");
    Button::new(SharedString::from(id.clone()))
        .accessibility_label(format!("Options for {title}"))
        .small()
        .ghost()
        .child(div().debug_selector(move || id.clone().into()).child("⋯"))
        .dropdown_menu(move |menu, _, _| sensors(menu, &monitor, &sensor, &shared))
        .into_any_element()
}
pub(crate) fn monitor_button(monitor_id: String, shared: Shared) -> AnyElement {
    let title = shared
        .borrow()
        .catalog
        .iter()
        .find(|m| m.id == monitor_id)
        .map(|m| m.title.clone())
        .unwrap_or_else(|| monitor_id.clone());
    let id = format!("{monitor_id}:options");
    Button::new(SharedString::from(id.clone()))
        .accessibility_label(format!("Options for {title}"))
        .small()
        .ghost()
        .child(div().debug_selector(move || id.clone().into()).child("⋯"))
        .dropdown_menu(move |menu, _, _| monitor(menu, &monitor_id, &shared))
        .into_any_element()
}
