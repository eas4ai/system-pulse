"""Reject incomplete or contradictory native resize receipts."""

import copy
import unittest

from performance_compare import InvalidMeasurement
from process_table_verify import validate_geometry, validate_search


def receipt():
    def frame(width, scroll=0):
        widths = [88, max(220, width - 894), 152, 112, 128, 128, 112, 140]
        left = 17 - scroll
        headings, cells = [], []
        for column_width in widths:
            headings.append([left, 176, column_width, 28])
            cells.append([left, 204, column_width, 28])
            left += column_width
        return {"window_width": width, "viewport": [16, 175, width - 32, 374],
                "headings": headings, "cells": cells}
    return {"status": "PASS", "platform": "linux",
            "frames": [frame(width) for width in (1280, 1800, 960, 1280)],
            "narrow_scrolled": frame(960, 154)}


class GeometryTests(unittest.TestCase):
    def test_complete_geometry(self):
        validate_geometry(receipt(), "linux")

    def test_rejects_wrong_platform_and_missing_resize(self):
        for change in (lambda r: r.update(platform="macos"), lambda r: r["frames"].pop()):
            record = receipt()
            change(record)
            with self.assertRaises(InvalidMeasurement):
                validate_geometry(record, "linux")

    def test_rejects_unfilled_table_even_with_aligned_cells(self):
        record = receipt()
        for key in ("headings", "cells"):
            record["frames"][1][key][-1][2] -= 20
        with self.assertRaises(InvalidMeasurement):
            validate_geometry(record, "linux")

    def test_rejects_misaligned_or_missing_cells(self):
        for change in (lambda r: r["frames"][0]["cells"][3].__setitem__(0, 10),
                       lambda r: r["frames"][0]["cells"].pop()):
            record = receipt()
            change(record)
            with self.assertRaises(InvalidMeasurement):
                validate_geometry(record, "linux")

    def test_rejects_inaccessible_last_column(self):
        record = receipt()
        record["narrow_scrolled"] = copy.deepcopy(record["frames"][2])
        with self.assertRaises(InvalidMeasurement):
            validate_geometry(record, "linux")


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.record = receipt()
        for frame in self.record["frames"]:
            frame.update(search=[16, 140, 280, 24],
                         actions=[[300, 140, 85, 24], [389, 140, 95, 24]])
        self.record.update(search_filter={"pid": 123, "identities": ["process:123:400"]},
                           search_clear_rows=15)

    def test_compact_search_and_native_filter_clear(self):
        validate_search(self.record)

    def test_rejects_stretched_input(self):
        self.record["frames"][1]["search"][2] = 900
        with self.assertRaises(InvalidMeasurement):
            validate_search(self.record)

    def test_rejects_clipped_toolbar(self):
        self.record["frames"][2]["actions"][1][0] = 940
        with self.assertRaises(InvalidMeasurement):
            validate_search(self.record)

    def test_rejects_wrong_filtered_process(self):
        self.record["search_filter"]["identities"] = ["process:124:400"]
        with self.assertRaises(InvalidMeasurement):
            validate_search(self.record)

    def test_rejects_clear_without_restored_rows(self):
        self.record["search_clear_rows"] = 1
        with self.assertRaises(InvalidMeasurement):
            validate_search(self.record)



if __name__ == "__main__":
    unittest.main()
