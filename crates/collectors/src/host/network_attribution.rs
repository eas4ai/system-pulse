//! Capture once, then derive all interface counts from the retained, shareable inputs.
use super::*;
use std::collections::{BTreeMap, BTreeSet};
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};
const ADDRESS_SOURCE: &str = "sysinfo::Networks::refresh / NetworkData::ip_networks";
impl HostCollector {
    pub(super) fn capture_network_attribution(&mut self) -> NetworkAttribution {
        let origin = self.origin;
        let fixed_ns = self.fixed_ns;
        let clock =
            || fixed_ns.unwrap_or_else(|| origin.elapsed().as_nanos().min(u64::MAX as u128) as u64);
        let interface_addresses = capture_addresses(clock, || {
            // sysinfo has no error return here: retain exactly the addresses it exposes.
            if self.root == Path::new("/") {
                self.networks.refresh(true);
            }
            self.networks
                .iter()
                .map(|(name, data)| {
                    (
                        name.clone(),
                        data.ip_networks()
                            .iter()
                            .map(|network| network.addr.to_string())
                            .collect(),
                    )
                })
                .collect()
        });
        let order = if cfg!(target_endian = "little") {
            WordByteOrder::LittleEndian
        } else {
            WordByteOrder::BigEndian
        };
        // Each table is attempted independently, including when the other query fails.
        let tcp_v4 = capture_table("/proc/net/tcp", IpVersion::Ipv4, order, clock, || {
            self.read("/proc/net/tcp")
        });
        let tcp_v6 = capture_table("/proc/net/tcp6", IpVersion::Ipv6, order, clock, || {
            self.read("/proc/net/tcp6")
        });
        NetworkAttribution {
            interface_addresses,
            tcp_v4,
            tcp_v6,
        }
    }
}
fn capture_addresses(
    clock: impl Fn() -> u64,
    query: impl FnOnce() -> BTreeMap<String, Vec<String>>,
) -> InterfaceAddressObservation {
    let started = clock();
    let interfaces = query();
    InterfaceAddressObservation {
        query: SourceQuery {
            source: ADDRESS_SOURCE.into(),
            read_started_ns: started,
            captured_ns: clock(),
            availability: Availability::Available,
            errors: vec![],
        },
        interfaces,
    }
}
fn capture_table(
    source: &str,
    family: IpVersion,
    order: WordByteOrder,
    clock: impl Fn() -> u64,
    read: impl FnOnce() -> Result<String, String>,
) -> TcpTableObservation {
    let started = clock();
    let mut rows = Vec::new();
    let mut errors = Vec::new();
    match read() {
        Err(error) => errors.push(error),
        Ok(text) => {
            let mut lines = text.lines();
            let header = lines
                .next()
                .map(|line| line.split_whitespace().collect::<Vec<_>>());
            let trusted_header = header.as_ref().is_some_and(|h| {
                h.first() == Some(&"sl")
                    && h.get(1) == Some(&"local_address")
                    && matches!(h.get(2), Some(&"rem_address" | &"remote_address"))
                    && h.get(3) == Some(&"st")
            });
            if !trusted_header {
                errors.push(format!(
                    "{source}: line 1: missing local_address/state header"
                ));
            }
            for (index, line) in lines.enumerate() {
                if line.trim().is_empty() {
                    continue;
                }
                let line_number = index as u64 + 2;
                let fields = line.split_whitespace().collect::<Vec<_>>();
                // Establish column ownership before copying any source contents. Otherwise a
                // missing column could cause a remote address or owner to masquerade as local.
                let hex = |token: &str, length| {
                    token.len() == length && token.bytes().all(|b| b.is_ascii_hexdigit())
                };
                let endpoint = |token: &&str| {
                    token.split_once(':').is_some_and(|(address, port)| {
                        hex(address, if family == IpVersion::Ipv4 { 8 } else { 32 }) && hex(port, 4)
                    })
                };
                let valid_slot = fields.first().is_some_and(|token| {
                    token.strip_suffix(':').is_some_and(|slot| {
                        !slot.is_empty() && slot.bytes().all(|b| b.is_ascii_digit())
                    })
                });
                let trusted_row = trusted_header
                    && valid_slot
                    && fields.get(1).is_some_and(endpoint)
                    && fields.get(2).is_some_and(endpoint)
                    && fields.get(3).is_some_and(|token| hex(token, 2));
                let (local_address_hex, state_hex) = if trusted_row {
                    (
                        fields[1].split_once(':').map(|(address, _)| address.into()),
                        Some(fields[3].to_string()),
                    )
                } else {
                    errors.push(format!(
                        "{source}: line {line_number}: uncertain slot/local endpoint/remote endpoint/state column structure"
                    ));
                    (None, None)
                };
                let row = TcpLocalRow {
                    line_number,
                    local_address_hex,
                    state_hex,
                };
                rows.push(row);
            }
        }
    }
    TcpTableObservation {
        query: SourceQuery {
            source: source.into(),
            read_started_ns: started,
            captured_ns: clock(),
            availability: if errors.is_empty() {
                Availability::Available
            } else {
                Availability::Failed
            },
            errors,
        },
        address_family: family,
        word_byte_order: order,
        rows,
    }
}
/// The returned readings are keyed by interface name. The caller assigns the stable sensor ID.
pub(super) fn connection_readings(capture: &NetworkAttribution) -> BTreeMap<String, Reading> {
    let interfaces = &capture.interface_addresses.interfaces;
    let mut owners: BTreeMap<IpAddr, BTreeSet<&str>> = BTreeMap::new();
    let mut input_errors = Vec::new();
    for (name, addresses) in interfaces {
        for value in addresses {
            match value.parse::<IpAddr>() {
                Ok(ip) => {
                    let ip = normalize(ip);
                    if !ip.is_unspecified() {
                        owners.entry(ip).or_default().insert(name);
                    }
                }
                Err(_) => input_errors.push(format!(
                    "{}: interface {name}: invalid local address",
                    capture.interface_addresses.query.source
                )),
            }
        }
    }
    let unique_owners = owners
        .into_iter()
        .filter_map(|(address, owners)| {
            if owners.len() == 1 {
                Some((address, *owners.first()?))
            } else {
                None
            }
        })
        .collect::<BTreeMap<_, _>>();
    let attributable = unique_owners.values().copied().collect::<BTreeSet<_>>();
    for query in [
        &capture.interface_addresses.query,
        &capture.tcp_v4.query,
        &capture.tcp_v6.query,
    ] {
        if query.availability != Availability::Available {
            if query.errors.is_empty() {
                input_errors.push(format!(
                    "{}: query is {:?}",
                    query.source, query.availability
                ));
            } else {
                input_errors.extend(query.errors.iter().cloned());
            }
        }
    }
    let mut counts: BTreeMap<&str, u64> = BTreeMap::new();
    if input_errors.is_empty() {
        for table in [&capture.tcp_v4, &capture.tcp_v6] {
            for row in &table.rows {
                let decoded = state(row).and_then(|state| {
                    address(row, table.address_family, table.word_byte_order)
                        .map(|address| (state, address))
                });
                match decoded {
                    Ok((1, address)) if !address.is_unspecified() => {
                        if let Some(owner) = unique_owners.get(&address) {
                            *counts.entry(owner).or_default() += 1;
                        }
                    }
                    Ok(_) => {}
                    Err(error) => input_errors.push(format!(
                        "{}: line {}: {error}",
                        table.query.source, row.line_number
                    )),
                }
            }
        }
    }
    let start = [
        capture.interface_addresses.query.read_started_ns,
        capture.tcp_v4.query.read_started_ns,
        capture.tcp_v6.query.read_started_ns,
    ]
    .into_iter()
    .min()
    .unwrap_or(0);
    let end = [
        capture.interface_addresses.query.captured_ns,
        capture.tcp_v4.query.captured_ns,
        capture.tcp_v6.query.captured_ns,
    ]
    .into_iter()
    .max()
    .unwrap_or(0);
    interfaces
        .keys()
        .map(|name| {
            let reading = if !attributable.contains(name.as_str()) {
                missing(
                    "",
                    Availability::Unavailable,
                    "No uniquely attributable local interface address; wildcard and distinct-interface shared addresses are excluded".into(),
                )
            } else if !input_errors.is_empty() {
                missing("", Availability::Failed, input_errors.join("; "))
            } else {
                let count = counts.get(name.as_str()).copied().unwrap_or(0);
                let mut reading = measured("", count as f64, None);
                reading.observations.push(raw_window(
                    "Snapshot.network_attribution",
                    start,
                    end,
                    [("value", count)],
                ));
                reading
            };
            (name.clone(), reading)
        })
        .collect()
}
fn state(row: &TcpLocalRow) -> Result<u8, String> {
    let token = row.state_hex.as_deref().ok_or("state field is missing")?;
    if token.len() != 2 || !token.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("state field must contain two hexadecimal digits".into());
    }
    u8::from_str_radix(token, 16).map_err(|_| "state field is invalid".into())
}
fn normalize(ip: IpAddr) -> IpAddr {
    match ip {
        IpAddr::V6(v6) => v6.to_ipv4_mapped().map(IpAddr::V4).unwrap_or(ip),
        _ => ip,
    }
}
fn address(row: &TcpLocalRow, family: IpVersion, order: WordByteOrder) -> Result<IpAddr, String> {
    let token = row
        .local_address_hex
        .as_deref()
        .ok_or("local_address field is missing")?;
    let expected = if family == IpVersion::Ipv4 { 8 } else { 32 };
    if token.len() != expected || !token.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(format!(
            "local_address field must contain {expected} hexadecimal digits"
        ));
    }
    let word = |hex: &str| -> Result<[u8; 4], String> {
        let value = u32::from_str_radix(hex, 16).map_err(|_| "local_address word is invalid")?;
        Ok(match order {
            WordByteOrder::LittleEndian => value.to_le_bytes(),
            WordByteOrder::BigEndian => value.to_be_bytes(),
        })
    };
    if family == IpVersion::Ipv4 {
        Ok(IpAddr::V4(Ipv4Addr::from(word(token)?)))
    } else {
        let mut bytes = [0; 16];
        for (index, chunk) in bytes.chunks_exact_mut(4).enumerate() {
            chunk.copy_from_slice(&word(&token[index * 8..index * 8 + 8])?);
        }
        Ok(normalize(IpAddr::V6(Ipv6Addr::from(bytes))))
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;
    fn header() -> &'static str {
        "  sl  local_address rem_address   st tx_queue rx_queue\n"
    }
    fn row(local: &str, state: &str) -> String {
        let remote = if local.len() == 32 {
            "00000000000000000000000001020304"
        } else {
            "01020304"
        };
        format!("0: {local}:1234 {remote}:ABCD {state} 00000000:00000000 0 0 12345 99\n")
    }
    fn table(family: IpVersion, text: &str) -> TcpTableObservation {
        capture_table(
            if family == IpVersion::Ipv4 {
                "/proc/net/tcp"
            } else {
                "/proc/net/tcp6"
            },
            family,
            WordByteOrder::LittleEndian,
            || 10,
            || Ok(text.into()),
        )
    }
    fn capture(interfaces: &[(&str, &[&str])], v4: &str, v6: &str) -> NetworkAttribution {
        NetworkAttribution {
            interface_addresses: capture_addresses(
                || 5,
                || {
                    interfaces
                        .iter()
                        .map(|(n, a)| (n.to_string(), a.iter().map(|a| a.to_string()).collect()))
                        .collect()
                },
            ),
            tcp_v4: table(IpVersion::Ipv4, v4),
            tcp_v6: table(IpVersion::Ipv6, v6),
        }
    }
    #[test]
    fn shared_evidence_keeps_raw_rows_without_excluded_socket_metadata() {
        let text = format!(
            "{}{}{}{}",
            header(),
            row("0100007F", "01"),
            row("00000000", "01"),
            row("0100007F", "0A")
        );
        let c = capture(&[("lo", &["127.0.0.1"])], &text, header());
        assert_eq!(c.tcp_v4.rows.len(), 3);
        assert_eq!(
            c.tcp_v4.rows[1].local_address_hex.as_deref(),
            Some("00000000")
        );
        assert_eq!(c.tcp_v4.rows[2].state_hex.as_deref(), Some("0A"));
        let snapshot = Snapshot {
            network_attribution: Some(c),
            ..Snapshot::default()
        };
        let value = serde_json::to_value(&snapshot).unwrap();
        let row = value["network_attribution"]["tcp_v4"]["rows"][0]
            .as_object()
            .unwrap();
        assert_eq!(
            row.keys().map(String::as_str).collect::<Vec<_>>(),
            ["line_number", "local_address_hex", "state_hex"]
        );
        let serialized = serde_json::to_string(&snapshot).unwrap();
        assert!(!serialized.contains("ABCD"));
        assert!(!serialized.contains("12345"));
        let restored: Snapshot = serde_json::from_str(&serialized).unwrap();
        assert_eq!(restored.network_attribution.unwrap().tcp_v4.rows.len(), 3);
    }
    #[test]
    fn address_and_each_table_keep_separate_query_windows_even_after_read_failure() {
        let clock = Cell::new(100u64);
        let now = || clock.get();
        let addresses = capture_addresses(now, || {
            clock.set(200);
            BTreeMap::new()
        });
        let v4 = capture_table(
            "/proc/net/tcp",
            IpVersion::Ipv4,
            WordByteOrder::LittleEndian,
            now,
            || {
                clock.set(400);
                Err("/proc/net/tcp: permission denied".into())
            },
        );
        let v6 = capture_table(
            "/proc/net/tcp6",
            IpVersion::Ipv6,
            WordByteOrder::LittleEndian,
            now,
            || {
                clock.set(900);
                Ok(header().into())
            },
        );
        assert_eq!(
            (addresses.query.read_started_ns, addresses.query.captured_ns),
            (100, 200)
        );
        assert_eq!((v4.query.read_started_ns, v4.query.captured_ns), (200, 400));
        assert_eq!((v6.query.read_started_ns, v6.query.captured_ns), (400, 900));
        assert_eq!(v4.query.availability, Availability::Failed);
        assert!(v4.query.errors[0].contains("permission denied"));
        assert_eq!(v6.query.availability, Availability::Available);
        assert!(addresses.interfaces.is_empty());
        assert_eq!(addresses.query.availability, Availability::Available);
        assert!(addresses.query.errors.is_empty());
    }
    #[test]
    fn attribution_uses_distinct_interface_owners_and_preserved_tokens() {
        let v4 = format!(
            "{}{}{}{}{}{}",
            header(),
            row("0100000A", "01"),
            row("0100000A", "0A"),
            row("00000000", "01"),
            row("0200000A", "01"),
            row("0300000A", "01")
        );
        let v6 = format!(
            "{}{}{}{}",
            header(),
            row("0000000000000000FFFF00000100000A", "01"),
            row("B80D0120000000000000000001000000", "01"),
            row("00000000000000000000000000000000", "01")
        );
        let c = capture(
            &[
                ("first", &["10.0.0.1", "10.0.0.1", "2001:db8::1"]),
                ("shared-a", &["10.0.0.2"]),
                ("shared-b", &["10.0.0.2"]),
                ("second", &["10.0.0.3"]),
                ("empty", &[]),
            ],
            &v4,
            &v6,
        );
        let readings = connection_readings(&c);
        assert_eq!(readings["first"].value, Some(3.0));
        assert_eq!(readings["second"].value, Some(1.0));
        assert_eq!(readings["shared-a"].availability, Availability::Unavailable);
        assert_eq!(readings["shared-b"].value, None);
        assert_eq!(readings["empty"].value, None);
        // Independent little-endian expansion of the retained words, not the collector decoder.
        let owned = [
            "10.0.0.1".parse::<IpAddr>().unwrap(),
            "2001:db8::1".parse().unwrap(),
        ];
        let independent = c
            .tcp_v4
            .rows
            .iter()
            .map(|r| (r, 4))
            .chain(c.tcp_v6.rows.iter().map(|r| (r, 16)))
            .filter(|(r, _)| r.state_hex.as_deref() == Some("01"))
            .filter(|(r, len)| {
                let raw = r.local_address_hex.as_ref().unwrap();
                let mut bytes = Vec::new();
                for offset in (0..raw.len()).step_by(8) {
                    let word = u32::from_str_radix(&raw[offset..offset + 8], 16).unwrap();
                    bytes.extend_from_slice(&word.to_le_bytes());
                }
                let addr = if *len == 4 {
                    IpAddr::from(<[u8; 4]>::try_from(bytes.as_slice()).unwrap())
                } else {
                    let ipv6 =
                        std::net::Ipv6Addr::from(<[u8; 16]>::try_from(bytes.as_slice()).unwrap());
                    ipv6.to_ipv4_mapped()
                        .map(IpAddr::V4)
                        .unwrap_or(IpAddr::V6(ipv6))
                };
                owned.contains(&addr)
            })
            .count();
        assert_eq!(independent, 3);
        assert_eq!(readings["first"].value, Some(independent as f64));
        assert_eq!(readings["first"].observations.len(), 1);
    }
    #[test]
    fn ipv4_ipv6_and_word_order_are_decoded_from_raw_tokens() {
        for (hex, family, order, expected) in [
            (
                "0100007F",
                IpVersion::Ipv4,
                WordByteOrder::LittleEndian,
                "127.0.0.1",
            ),
            (
                "7F000001",
                IpVersion::Ipv4,
                WordByteOrder::BigEndian,
                "127.0.0.1",
            ),
            (
                "00000000000000000000000001000000",
                IpVersion::Ipv6,
                WordByteOrder::LittleEndian,
                "::1",
            ),
            (
                "20010DB8000000000000000000000001",
                IpVersion::Ipv6,
                WordByteOrder::BigEndian,
                "2001:db8::1",
            ),
            (
                "0000000000000000FFFF00000100007F",
                IpVersion::Ipv6,
                WordByteOrder::LittleEndian,
                "127.0.0.1",
            ),
        ] {
            let r = TcpLocalRow {
                line_number: 2,
                local_address_hex: Some(hex.into()),
                state_hex: Some("01".into()),
            };
            assert_eq!(address(&r, family, order).unwrap().to_string(), expected);
        }
    }
    #[test]
    fn uncertain_column_ownership_redacts_both_fields_and_propagated_errors() {
        for line in [
            "0100007F:1234 DEADBEEF:CAFE 01 00000000:00000000",
            "0: DEADBEEF:CAFE 01 00000000:00000000",
            "0: 0100007F:1234 01 00000000:00000000",
            "0: 0100007F:1234 DEADBEEF:CAFE 00000000:00000000",
            "0: inserted 0100007F:1234 DEADBEEF:CAFE 01",
            "0: 0100007F:1234 inserted DEADBEEF:CAFE 01",
            "0: 0100007F:1234 DEADBEEF:CAFE inserted 01",
            "0: 0100007F:1234 DEADBEEF:CAFE 01:CAFE",
        ] {
            let text = format!("{}{line}\n", header());
            let captured = capture(&[("lo", &["127.0.0.1"])], &text, header());
            assert_eq!(captured.tcp_v4.query.availability, Availability::Failed);
            let raw = &captured.tcp_v4.rows[0];
            assert_eq!(raw.local_address_hex, None, "uncertain row: {line}");
            assert_eq!(raw.state_hex, None, "uncertain row: {line}");
            let readings = connection_readings(&captured);
            assert_eq!(readings["lo"].availability, Availability::Failed);
            for serialized in [
                serde_json::to_string(&captured).unwrap(),
                serde_json::to_string(&readings).unwrap(),
            ] {
                for excluded in ["DEADBEEF", "CAFE", "0100007F", "inserted"] {
                    assert!(!serialized.contains(excluded), "leaked row: {serialized}");
                }
            }
        }
        let invalid_header = table(
            IpVersion::Ipv4,
            "sl remote_address local_address st\n0: DEADBEEF:CAFE 0100007F:1234 01\n",
        );
        assert_eq!(invalid_header.query.availability, Availability::Failed);
        assert_eq!(invalid_header.rows[0].local_address_hex, None);
        assert_eq!(invalid_header.rows[0].state_hex, None);
        assert!(
            !serde_json::to_string(&invalid_header)
                .unwrap()
                .contains("DEADBEEF")
        );
        let valid = table(
            IpVersion::Ipv4,
            &format!("{}{}", header(), row("0100007f", "0a")),
        );
        assert_eq!(valid.query.availability, Availability::Available);
        assert_eq!(valid.rows[0].local_address_hex.as_deref(), Some("0100007f"));
        assert_eq!(valid.rows[0].state_hex.as_deref(), Some("0a"));
    }
    #[test]
    fn malformed_shifted_fields_cannot_serialize_excluded_socket_metadata() {
        for (local, state, excluded) in [
            ("0100007F", "DEADBEEF:CAFE", "DEADBEEF"),
            ("0100007F", "12345", "12345"),
            ("0100007F", "00000000:CAFEBABE", "CAFEBABE"),
            ("private-owner", "01", "private-owner"),
            ("12345", "01", "12345"),
        ] {
            let text = format!("{}{}", header(), row(local, state));
            let captured = capture(&[("lo", &["127.0.0.1"])], &text, header());
            assert_eq!(captured.tcp_v4.query.availability, Availability::Failed);
            let serialized = serde_json::to_string(&captured).unwrap();
            assert!(!serialized.contains(excluded), "leaked token: {serialized}");
            assert!(!serialized.contains("CAFE"));
            let readings = connection_readings(&captured);
            assert_eq!(readings["lo"].availability, Availability::Failed);
            assert!(!serde_json::to_string(&readings).unwrap().contains(excluded));
            let raw = &captured.tcp_v4.rows[0];
            assert_eq!(raw.local_address_hex, None);
            assert_eq!(raw.state_hex, None);
        }
        let shifted = table(
            IpVersion::Ipv4,
            &format!("{}0: DEADBEEF 01020304:CAFE 01\n", header()),
        );
        assert_eq!(shifted.query.availability, Availability::Failed);
        assert_eq!(shifted.rows[0].local_address_hex, None);
        let serialized = serde_json::to_string(&shifted).unwrap();
        assert!(!serialized.contains("DEADBEEF"));
        assert!(!serialized.contains("CAFE"));
    }
    #[test]
    fn malformed_tables_retain_allowed_tokens_and_context_without_faking_zero() {
        for text in [
            "".to_string(),
            format!("{}{}", header(), row("0100007F", "GG")),
            format!("{}{}", header(), row("XYZ", "0A")),
            format!("{}broken\n", header()),
        ] {
            let c = capture(&[("lo", &["127.0.0.1"])], &text, header());
            assert_eq!(c.tcp_v4.query.availability, Availability::Failed);
            assert!(!c.tcp_v4.query.errors.is_empty());
            assert!(
                c.tcp_v4
                    .query
                    .errors
                    .iter()
                    .all(|e| e.contains("/proc/net/tcp")
                        && !e.contains("ABCD")
                        && !e.contains("12345"))
            );
            let readings = connection_readings(&c);
            assert_eq!(readings["lo"].value, None);
            assert_eq!(readings["lo"].availability, Availability::Failed);
        }
        let mut c = capture(&[("lo", &["127.0.0.1"])], header(), header());
        c.tcp_v6 = capture_table(
            "/proc/net/tcp6",
            IpVersion::Ipv6,
            WordByteOrder::LittleEndian,
            || 1,
            || Err("/proc/net/tcp6: read failed".into()),
        );
        assert_eq!(
            connection_readings(&c)["lo"].availability,
            Availability::Failed
        );
    }
}
