from __future__ import annotations

import unittest

from analysis_stability.stable_evidence_scoring import (
    _split_requirement_clauses,
)


class Phase6DCompoundSplittingRefinementTests(unittest.TestCase):
    def test_interest_and_recent_shooter_are_split(self):
        rows = _split_requirement_clauses(
            (
                "Interest in online games and familiarity with "
                "recent tactical shooting titles"
            ),
            "required",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [row["atomic_focus"] for row in rows],
            [
                "Interest in online games",
                "familiarity with recent tactical shooting titles",
            ],
        )
        self.assertTrue(all(row["is_atomic"] for row in rows))
        self.assertEqual(
            len({row["atomic_group_id"] for row in rows}),
            1,
        )

    def test_documentation_and_communication_are_split(self):
        rows = _split_requirement_clauses(
            (
                "Maintain clear technical documentation and communicate "
                "findings to technical and non-technical stakeholders"
            ),
            "core",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [row["atomic_focus"] for row in rows],
            [
                "Maintain clear technical documentation",
                (
                    "communicate findings to technical and "
                    "non-technical stakeholders"
                ),
            ],
        )

    def test_shared_head_comma_list_is_split(self):
        rows = _split_requirement_clauses(
            "Experience using Git, relational databases, and REST APIs",
            "required",
        )
        self.assertEqual(
            [row["atomic_focus"] for row in rows],
            [
                "Experience using Git",
                "Experience using relational databases",
                "Experience using REST APIs",
            ],
        )
        self.assertTrue(all(row["is_atomic"] for row in rows))

    def test_or_alternatives_remain_single_requirement(self):
        rows = _split_requirement_clauses(
            (
                "Knowledge of cloud platforms, automated testing, "
                "or production support is preferred"
            ),
            "required",
        )
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["is_atomic"])

    def test_written_and_verbal_communication_is_not_over_split(self):
        rows = _split_requirement_clauses(
            "Good written and verbal communication skills",
            "required",
        )
        self.assertEqual(len(rows), 1)

    def test_repeat_runs_are_identical(self):
        value = (
            "Interest in online games and familiarity with "
            "recent tactical shooting titles"
        )
        self.assertEqual(
            _split_requirement_clauses(value, "required"),
            _split_requirement_clauses(value, "required"),
        )


if __name__ == "__main__":
    unittest.main()
