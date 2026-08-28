from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from database import tailoring_version_manager as base_manager
from database.tailoring_generation_control import (
    clear_low_confidence_project_selection_override,
    get_low_confidence_project_selection_override,
    set_low_confidence_project_selection_override,
)
from tailoring.stable_tailoring_ranking import (
    apply_low_confidence_project_override,
)


def _row(
    title: str,
    *,
    project_id: str,
    score: int,
    coverage: float,
    support: int,
    selection_rank: int | None = None,
    match_label: str | None = None,
) -> dict:
    matches = []
    if match_label:
        matches = [
            {
                "requirement_id": f"req_{project_id}",
                "match_label": match_label,
                "coverage_points": coverage,
            }
        ]
    return {
        "title": title,
        "display_title": title,
        "project_id": project_id,
        "final_score": score,
        "deterministic_coverage_score": coverage,
        "support_score": support,
        "support_components": {
            "evidence_completeness": min(15, support),
            "impact_scope": min(8, max(0, support - 15)),
        },
        "currently_in_resume": True,
        "in_evidence_library": True,
        "requirement_matches": matches,
        "selection_rank": selection_rank,
    }


class LowConfidenceOverridePolicyTests(unittest.TestCase):
    def _rows(self) -> list[dict]:
        return [
            _row(
                "Workout Buddy",
                project_id="workout",
                score=57,
                coverage=19.5,
                support=18,
                selection_rank=1,
                match_label="direct",
            ),
            _row(
                "The Great Migration",
                project_id="migration",
                score=53,
                coverage=16.5,
                support=20,
                selection_rank=2,
                match_label="transferable",
            ),
            _row(
                "QueryAI",
                project_id="query",
                score=0,
                coverage=0.0,
                support=20,
                selection_rank=3,
            ),
            _row(
                "CyberSphere",
                project_id="cyber",
                score=0,
                coverage=0.0,
                support=18,
                selection_rank=4,
            ),
            _row(
                "Job AI Helper",
                project_id="job_ai",
                score=0,
                coverage=0.0,
                support=18,
            ),
        ]

    def test_user_override_replaces_only_low_confidence_slot(self):
        rows = self._rows()
        before = deepcopy(rows)

        final_rows, debug = apply_low_confidence_project_override(
            ranked_rows=rows,
            selected_count=4,
            override_project_ids=["query", "job_ai"],
        )

        self.assertEqual(
            [
                "Workout Buddy",
                "The Great Migration",
                "QueryAI",
                "Job AI Helper",
            ],
            [row["title"] for row in final_rows[:4]],
        )
        self.assertEqual("user_override", debug["selection_source"])
        self.assertEqual("applied", debug["override_status"])
        self.assertEqual(
            "pre_generation",
            debug["selection_timing"],
        )
        self.assertEqual(
            ["query", "job_ai"],
            debug["final_selection"][
                "low_confidence_project_ids"
            ],
        )
        self.assertEqual(
            [
                {
                    "removed_project_id": "cyber",
                    "removed_title": "CyberSphere",
                    "added_project_id": "job_ai",
                    "added_title": "Job AI Helper",
                }
            ],
            debug["overrides"],
        )

        # No relevance, coverage, or evidence score is manufactured.
        original_by_id = {
            row["project_id"]: row
            for row in before
        }
        for row in final_rows:
            original = original_by_id[row["project_id"]]
            self.assertEqual(
                original["final_score"],
                row["final_score"],
            )
            self.assertEqual(
                original["deterministic_coverage_score"],
                row["deterministic_coverage_score"],
            )
            self.assertEqual(
                original["support_score"],
                row["support_score"],
            )
        self.assertEqual(rows, before)

    def test_override_cannot_replace_proven_jd_project(self):
        rows = self._rows()

        final_rows, debug = apply_low_confidence_project_override(
            ranked_rows=rows,
            selected_count=4,
            override_project_ids=["workout", "job_ai"],
        )

        self.assertEqual(
            ["workout", "migration", "query", "cyber"],
            [row["project_id"] for row in final_rows[:4]],
        )
        self.assertEqual(
            "deterministic_default",
            debug["selection_source"],
        )
        self.assertEqual(
            "ignored_invalid",
            debug["override_status"],
        )

    def test_matching_default_does_not_claim_user_changed_ranking(self):
        rows = self._rows()

        final_rows, debug = apply_low_confidence_project_override(
            ranked_rows=rows,
            selected_count=4,
            override_project_ids=["query", "cyber"],
        )

        self.assertEqual(
            ["workout", "migration", "query", "cyber"],
            [row["project_id"] for row in final_rows[:4]],
        )
        self.assertEqual(
            "deterministic_default",
            debug["selection_source"],
        )
        self.assertEqual(
            "matches_default",
            debug["override_status"],
        )
        self.assertEqual([], debug["overrides"])


class LowConfidenceOverridePersistenceTests(unittest.TestCase):
    def test_application_local_override_round_trips_and_clears(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "applications.db"
            with patch.object(
                base_manager,
                "DB_PATH",
                db_path,
            ):
                empty = (
                    get_low_confidence_project_selection_override(
                        42
                    )
                )
                self.assertEqual([], empty["project_ids"])

                saved = (
                    set_low_confidence_project_selection_override(
                        application_id=42,
                        project_ids=["query", "job_ai", "query"],
                    )
                )
                self.assertEqual(
                    ["query", "job_ai"],
                    saved["project_ids"],
                )
                self.assertEqual(
                    "user_override",
                    saved["selection_source"],
                )

                other = (
                    get_low_confidence_project_selection_override(
                        43
                    )
                )
                self.assertEqual([], other["project_ids"])

                cleared = (
                    clear_low_confidence_project_selection_override(
                        42
                    )
                )
                self.assertEqual([], cleared["project_ids"])
                self.assertEqual(
                    "deterministic_default",
                    cleared["selection_source"],
                )


class LowConfidenceOverrideIntegrationSourceTests(unittest.TestCase):
    def test_app_wires_override_into_generation_and_debug_bundle(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn(
            '"low_confidence_project_selection_debug": (',
            source,
        )
        self.assertIn(
            '"low_confidence_project_override_ids": list(',
            source,
        )
        self.assertIn(
            "low_confidence_project_override_ids=(",
            source,
        )
        self.assertIn(
            "Save project selection",
            source,
        )
        self.assertIn(
            "Use recommended fallback",
            source,
        )
        self.assertNotIn(
            "Use selected projects on next Generate",
            source,
        )
        self.assertIn(
            'action="project_selection_override",',
            source,
        )
        self.assertIn(
            "record_zero_cost_action_event(",
            source,
        )

    def test_project_tailor_applies_override_before_selected_pairs(self):
        source = Path(
            "tailoring/project_section_tailor.py"
        ).read_text(encoding="utf-8")
        apply_at = source.index(
            "apply_low_confidence_project_override("
        )
        selected_at = source.index(
            "selected_pairs = _select_candidates_from_ranking(",
            apply_at,
        )
        self.assertLess(apply_at, selected_at)
        self.assertIn(
            "low_confidence_project_override_ids: "
            "list[str] | None = None",
            source,
        )


if __name__ == "__main__":
    unittest.main()
