"""Refresh progress display: nullable counts and Arrow serialization."""
import ast
from pathlib import Path
import unittest
from typing import Any

import pandas as pd


class _Slot:
    def __init__(self):
        self.frames = []

    def dataframe(self, frame, **kwargs):
        self.frames.append(frame.copy())
        assert kwargs == {"width": "stretch", "hide_index": True}


class RefreshProgressArrowTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / "job_discovery" / "ui.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        callbacks = [node for node in ast.walk(tree)
                     if isinstance(node, ast.FunctionDef) and node.name == "_refresh_progress"]
        self.assertEqual(len(callbacks), 1)
        self.slot = _Slot()
        self.rows = {}
        namespace = {"pd": pd, "Any": Any, "progress_slot": self.slot,
                     "progress_rows": self.rows}
        exec(compile(ast.Module(body=callbacks, type_ignores=[]), str(source), "exec"), namespace)
        self.callback = namespace["_refresh_progress"]

    def event(self, key, phase, **summary):
        self.callback({"source_key": key, "phase": phase, "summary": summary})
        frame = self.slot.frames[-1]
        self.assertEqual(str(frame["Jobs"].dtype), "Int64")
        self.assertEqual(list(frame.columns), ["Source/company", "State", "Jobs", "Details"])
        try:
            import pyarrow as pa
        except ImportError:
            pass  # Numeric dtype checks still run without optional Arrow.
        else:
            table = pa.Table.from_pandas(frame, preserve_index=False)
            self.assertTrue(pa.types.is_int64(table.schema.field("Jobs").type))
        return frame

    def test_all_queued_is_nullable_numeric_not_zero(self):
        self.event("a", "queued")
        frame = self.event("b", "queued")
        self.assertTrue(frame["Jobs"].isna().all())
        self.assertEqual(list(frame["State"]), ["Queued", "Queued"])
        self.assertIsNone(self.rows["a"]["Jobs"])

    def test_mixed_states_preserve_counts_details_and_order(self):
        self.event("a", "queued")
        self.event("b", "queued")
        self.event("c", "completed", fetched_count=12, detail_fetched=3, detail_reused=9)
        self.event("d", "skipped", error="recent")
        frame = self.event("e", "error", error="timeout")
        self.assertEqual(list(frame["Source/company"]), ["a", "b", "c", "d", "e"])
        self.assertEqual(list(frame["State"]), ["Queued", "Queued", "Done", "Skipped", "Error"])
        self.assertTrue(frame["Jobs"].iloc[:2].isna().all())
        self.assertEqual(list(frame["Jobs"].iloc[2:]), [12, 0, 0])
        self.assertEqual(list(frame["Details"]), ["", "", "detail fetched 3, reused 9", "recent", "timeout"])
        frame = self.event("a", "completed", fetched_count=0)
        self.assertEqual(frame["Jobs"].iloc[0], 0)
        self.assertTrue(pd.isna(frame["Jobs"].iloc[1]))
        frame = self.event("b", "completed", fetched_count=7)
        self.assertEqual(list(frame["Jobs"]), [0, 7, 12, 0, 0])
        self.assertEqual(len(self.rows), 5)

    def test_completed_first_then_queued_keeps_integer_precision(self):
        count = 9007199254740993
        self.event("a", "completed", fetched_count=count)
        frame = self.event("b", "queued")
        self.assertEqual(int(frame["Jobs"].iloc[0]), count)
        self.assertTrue(pd.isna(frame["Jobs"].iloc[1]))


if __name__ == "__main__":
    unittest.main()
