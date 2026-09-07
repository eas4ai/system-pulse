"""Connection verification uses interface identity, independently of UI labels."""

import copy
import sys
import unittest

from host_capture import connections


def snapshot(prefix="network:mac:aa:bb:cc:dd:ee:ff"):
    mid = prefix + ":name:eth0"
    query = dict(read_started_ns=1, captured_ns=2, availability="Available")
    word_order = "LittleEndian" if sys.byteorder == "little" else "BigEndian"
    address = int.from_bytes(bytes([192, 0, 2, 1]), sys.byteorder)
    return dict(
        capture_started_ns=0,
        capture_finished_ns=3,
        monitors=[dict(id=mid, kind="Network", title="Office connection (eth0)")],
        readings=[dict(sensor_id=mid + "/connections", availability="Available", value=1)],
        network_attribution=dict(
            interface_addresses=dict(query=copy.deepcopy(query), interfaces={"eth0": ["192.0.2.1"]}),
            tcp_v4=dict(
                query=copy.deepcopy(query),
                address_family="Ipv4",
                word_byte_order=word_order,
                rows=[dict(line_number=2, local_address_hex=f"{address:08X}", state_hex="01")],
            ),
            tcp_v6=dict(query=copy.deepcopy(query), address_family="Ipv6", word_byte_order=word_order, rows=[]),
        ),
    )


class ConnectionIdentityTests(unittest.TestCase):
    def test_display_labels_do_not_change_attribution_for_any_identity_form(self):
        for prefix in ("network", "network:mac:aa:bb:cc:dd:ee:ff", "network:path:/sys/devices/pci/net"):
            for title in ("eth0", "Office connection (eth0)", "Custom interface alias"):
                with self.subTest(prefix=prefix, title=title):
                    frame = snapshot(prefix)
                    frame["monitors"][0]["title"] = title
                    self.assertEqual(connections(frame), 1)

    def test_zero_unavailable_and_failed_states_keep_their_meaning(self):
        frame = snapshot()
        frame["network_attribution"]["tcp_v4"]["rows"] = []
        frame["readings"][0]["value"] = 0
        self.assertEqual(connections(frame), 1)
        frame["network_attribution"]["tcp_v4"]["query"]["availability"] = "Failed"
        frame["readings"][0].update(availability="Failed", value=None)
        self.assertEqual(connections(frame), 1)
        frame["network_attribution"]["interface_addresses"]["interfaces"]["eth0"] = []
        frame["readings"][0]["availability"] = "Unavailable"
        self.assertEqual(connections(frame), 1)

    def test_wrong_count_and_status_are_still_rejected(self):
        for change in (dict(value=0), dict(availability="Unavailable", value=None)):
            frame = snapshot()
            frame["readings"][0].update(change)
            with self.subTest(change=change), self.assertRaises(AssertionError):
                connections(frame)

    def test_malformed_identity_is_rejected_even_when_the_label_matches(self):
        frame = snapshot()
        frame["monitors"][0].update(id="network:eth0", title="eth0")
        frame["readings"][0]["sensor_id"] = "network:eth0/connections"
        with self.assertRaisesRegex(AssertionError, "interface identity"):
            connections(frame)
