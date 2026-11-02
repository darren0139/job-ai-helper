"""UI-only Arrow compatibility regression for score-component overall table."""
from __future__ import annotations

import csv
from contextlib import nullcontext
import io
import unittest

from tailoring.score_component_tables_ui import (
    _overall_display_rows, build_component_tables, component_exports,
    render_component_tables,
)
from tests.test_score_component_tables_ui import _sample


class _FakeStreamlit:
    def __init__(self):
        self.dataframes = []
    def markdown(self, *_args, **_kwargs):
        pass
    def tabs(self, labels):
        return [nullcontext() for _ in labels]
    def caption(self, *_args, **_kwargs):
        pass
    def dataframe(self, data, **_kwargs):
        self.dataframes.append(data)
    def download_button(self, *_args, **_kwargs):
        pass
    def divider(self, *_args, **_kwargs):
        pass
    def info(self, *_args, **_kwargs):
        pass
    def warning(self, *_args, **_kwargs):
        raise AssertionError("Unexpected receipt validation warning")


class ArrowCompatibleComponentDisplayTests(unittest.TestCase):
    def test_overall_display_has_nullable_numeric_columns(self):
        receipt, breakdown = _sample()
        rows = build_component_tables(receipt, breakdown=breakdown)["overall"]
        display = _overall_display_rows(rows)
        self.assertEqual(len(display), 5)
        self.assertEqual(rows[3]["raw_score_percent"], "")  # Native/CSV kept untouched.
        self.assertIsNone(display[3]["Raw score (%)"])
        self.assertIsNone(display[4]["Weight (%)"])
        self.assertEqual(display[4]["Weighted points earned"], 16)
        for col in ("Raw score (%)", "Weight (%)", "Weighted points earned", "Category allocation (pts)"):
            self.assertTrue(all((value is None or isinstance(value, (int, float)))
                                for value in (row[col] for row in display)))

        import pandas as pd
        frame = pd.DataFrame(display)
        for col in ("Raw score (%)", "Weight (%)", "Weighted points earned", "Category allocation (pts)"):
            self.assertTrue(pd.api.types.is_numeric_dtype(frame[col].dtype), col)
        try:
            import pyarrow as pa
        except ImportError:
            pass  # Pandas numeric dtype assertion still runs in environments without Arrow.
        else:
            pa.Table.from_pandas(frame, preserve_index=False)

    def test_streamlit_render_and_csv_exports_keep_native_values(self):
        receipt, breakdown = _sample()
        fake = _FakeStreamlit()
        self.assertTrue(render_component_tables(fake, receipt, breakdown=breakdown,
                                                key_prefix="arrow_v1", origin="test"))
        self.assertEqual(len(fake.dataframes), 4)
        self.assertIsNone(fake.dataframes[-1][3]["Raw score (%)"])
        self.assertIsNone(fake.dataframes[-1][3]["Weight (%)"])
        # Existing exported receipt remains unchanged: blank subtotal columns are
        # allowed in CSV, but not in numeric UI display columns.
        files = component_exports(build_component_tables(receipt, breakdown=breakdown))
        records = list(csv.DictReader(io.StringIO(files["overall.csv"].decode("utf-8-sig"))))
        self.assertEqual(records[3]["raw_score_percent"], "")
        self.assertEqual(records[4]["component_weight_percent"], "")
        self.assertAlmostEqual(float(records[3]["earned_points"]), receipt["subtotal_before_rounding"])


if __name__ == "__main__":
    unittest.main()
