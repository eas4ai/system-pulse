"""Reject incomplete or contradictory native resize receipts."""

import copy
import unittest

from performance_compare import InvalidMeasurement
from process_table_verify import validate_geometry


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


if __name__ == "__main__":
    unittest.main()
