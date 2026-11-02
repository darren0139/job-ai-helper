"""V1.2.2 display-unit labels: use points without changing native receipts."""
from __future__ import annotations

import csv
import io
import unittest

from tailoring.score_component_tables_ui import (
    build_component_tables, component_exports, render_component_tables,
)
from tests.test_score_component_tables_ui import _sample


class _CaptureUI:
    def __init__(self):
        self.tables = []
        self.captions = []
    def markdown(self, *args, **kwargs):
        pass
    def caption(self, message, **kwargs):
        self.captions.append(message)
    def dataframe(self, display, **kwargs):
        self.tables.append(display)
    def divider(self):
        pass
    def download_button(self, *args, **kwargs):
        pass
    def info(self, *args, **kwargs):
        pass
    def warning(self, message, **kwargs):
        raise AssertionError(message)


class PointUnitLabelsTests(unittest.TestCase):
    def test_four_tables_use_point_labels_without_rescaling(self):
        receipt, breakdown = _sample()
        ui = _CaptureUI()
        self.assertTrue(render_component_tables(ui, receipt, breakdown=breakdown,
                         key_prefix="label_v122", origin="regression"))
        self.assertEqual(len(ui.tables), 4)
        required, preferred, evidence, overall = ui.tables
        for display in ui.tables:
            self.assertTrue(display)
            self.assertFalse(any("/100" in key for key in display[0]), display[0])
        self.assertIn("Coverage earned (pts)", required[0])
        self.assertIn("Reference allocation (pts)", preferred[0])
        self.assertIn("Evidence contribution (pts)", evidence[0])
        self.assertIn("Weighted points earned", overall[0])
        self.assertIn("Category allocation (pts)", overall[0])
        self.assertAlmostEqual(required[-1]["Coverage earned (pts)"], 7.765, places=3)
        self.assertAlmostEqual(preferred[-1]["Coverage earned (pts)"], 2.2, places=3)
        self.assertEqual(evidence[-1]["Evidence contribution (pts)"], 6.0)
        self.assertAlmostEqual(overall[-2]["Weighted points earned"],
                               receipt["subtotal_before_rounding"], places=4)
        self.assertEqual(overall[-1]["Weighted points earned"],
                         receipt["stored_scorer_score"])
        self.assertIn("/100", overall[-1]["Component"])

    def test_csv_native_columns_and_values_are_unchanged(self):
        receipt, breakdown = _sample()
        tables = build_component_tables(receipt, breakdown=breakdown)
        exported = component_exports(tables)
        self.assertEqual(list(csv.DictReader(io.StringIO(exported["required_core.csv"].decode("utf-8-sig"))))[-1]["coverage_reference_points"],
                         str(tables["required_core"][-1]["coverage_reference_points"]))
        self.assertEqual(list(csv.DictReader(io.StringIO(exported["overall.csv"].decode("utf-8-sig"))))[-1]["component"],
                         "Saved rounded Job Match /100")
        self.assertEqual(tables["manifest"]["stored_score"], receipt["stored_scorer_score"])
        self.assertIn("raw_score_percent", exported["overall.csv"].decode("utf-8-sig"))
        self.assertIn("coverage_earned_points", exported["required_core.csv"].decode("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
