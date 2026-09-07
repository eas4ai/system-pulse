//! Default interface preference from the main routing tables. IPv4 precedes IPv6;
//! metrics are comparable only within an address family. Policy routing is not inferred.
pub(super) fn default_routes(ipv4: &str, ipv6: &str) -> Vec<String> {
    let mut routes = Vec::new();
    for line in ipv4.lines() {
        let fields: Vec<_> = line.split_whitespace().collect();
        if fields.len() < 8 || fields[1] != "00000000" || fields[7] != "00000000" {
            continue;
        }
        if let (Ok(flags), Ok(metric)) =
            (u32::from_str_radix(fields[3], 16), fields[6].parse::<u32>())
            && flags & 1 != 0
            && flags & 0x200 == 0
        {
            routes.push((0, metric, fields[0].to_owned()));
        }
    }
    for line in ipv6.lines() {
        let fields: Vec<_> = line.split_whitespace().collect();
        if fields.len() != 10
            || fields[0] != "00000000000000000000000000000000"
            || fields[1] != "00"
            || fields[2] != "00000000000000000000000000000000"
            || fields[3] != "00"
        {
            continue;
        }
        if let (Ok(flags), Ok(metric)) = (
            u32::from_str_radix(fields[8], 16),
            u32::from_str_radix(fields[5], 16),
        ) && flags & 1 != 0
            && flags & 0x200 == 0
        {
            routes.push((1, metric, fields[9].to_owned()));
        }
    }
    routes.sort();
    routes.into_iter().map(|(_, _, name)| name).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_ignore_subnets_down_reject_and_malformed_routes_and_sort_metrics() {
        let v4 = "Iface Destination Gateway Flags RefCnt Use Metric Mask\n\
            docker0 000011AC 00000000 0001 0 0 0 0000FFFF\n\
            wlan0 00000000 0101A8C0 0003 0 0 600 00000000\n\
            down0 00000000 0101A8C0 0002 0 0 0 00000000\n\
            reject0 00000000 00000000 0201 0 0 0 00000000\n\
            enp10s0 00000000 0101A8C0 0003 0 0 100 00000000\n\
            malformed 00000000 0 nope 0 0 0 00000000";
        assert_eq!(default_routes(v4, ""), ["enp10s0", "wlan0"]);
    }

    #[test]
    fn ipv6_default_excludes_reject_and_source_specific_routes() {
        let zero = "00000000000000000000000000000000";
        let v6 = format!(
            "{zero} 00 {zero} 00 {zero} 00000400 0 0 00000003 wlan0\n\
            {zero} 00 {zero} 00 {zero} ffffffff 0 0 00200200 lo\n\
            {zero} 00 {zero} 40 {zero} 00000001 0 0 00000003 eth1"
        );
        assert_eq!(default_routes("", &v6), ["wlan0"]);
        assert!(default_routes("missing", "bad").is_empty());
    }
}
