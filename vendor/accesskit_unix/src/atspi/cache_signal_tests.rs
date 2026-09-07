use super::{cache_path, cache_signal_body};
use atspi::{CacheItem, ObjectRefOwned};

// The parsed zvariant signature normalizes a sequence and a structure alike.
// Inspect the actual D-Bus signature field to detect a flattened argument.
fn wire_signature(message: &zbus::Message) -> &str {
    let bytes = message.data().bytes();
    let header_end = 16 + u32::from_le_bytes(bytes[12..16].try_into().unwrap()) as usize;
    let positions: Vec<_> = (16..header_end - 4)
        .step_by(8)
        .filter(|&i| bytes[i..i + 4] == [8, 1, b'g', 0])
        .collect();
    assert_eq!(positions.len(), 1, "one D-Bus signature field required");
    let start = positions[0] + 5;
    let end = start + bytes[start - 1] as usize;
    assert!(end < header_end);
    assert_eq!(bytes[end], 0);
    std::str::from_utf8(&bytes[start..end]).unwrap()
}

#[test]
fn add_accessible_preserves_one_structured_argument_on_the_wire() {
    let reference =
        ObjectRefOwned::from_static_str_unchecked(":1.42", "/org/a11y/atspi/accessible/root");
    let item = CacheItem {
        object: reference.clone(),
        app: reference.clone(),
        parent: reference,
        index: 3,
        children: 2,
        ifaces: atspi::Interface::Accessible.into(),
        short_name: "Process row".into(),
        role: atspi::Role::TableRow,
        name: "Selected process".into(),
        states: atspi::State::Selected.into(),
    };
    let message = zbus::Message::signal(cache_path(), "org.a11y.atspi.Cache", "AddAccessible")
        .unwrap()
        .endian(zbus::zvariant::Endian::Little)
        .build(&cache_signal_body(&item))
        .unwrap();
    assert_eq!(wire_signature(&message), "((so)(so)(so)iiassusau)");
    let (decoded,): (CacheItem,) = message.body().deserialize().unwrap();
    assert_eq!(decoded, item);
}

#[test]
fn remove_accessible_preserves_one_structured_argument_on_the_wire() {
    let reference =
        ObjectRefOwned::from_static_str_unchecked(":1.42", "/org/a11y/atspi/accessible/root");
    let message = zbus::Message::signal(cache_path(), "org.a11y.atspi.Cache", "RemoveAccessible")
        .unwrap()
        .endian(zbus::zvariant::Endian::Little)
        .build(&cache_signal_body(&reference))
        .unwrap();
    assert_eq!(wire_signature(&message), "(so)");
    let (decoded,): (ObjectRefOwned,) = message.body().deserialize().unwrap();
    assert_eq!(decoded, reference);
}
