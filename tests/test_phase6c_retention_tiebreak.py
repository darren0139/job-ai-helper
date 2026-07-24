from __future__ import annotations

import unittest

from resume_builder.docx_projects_skills_replacer import (
    _choose_layout_aware_reduction,
)
from resume_builder.evidence_aware_fitting import (
    PHASE6C_RETENTION_TIEBREAK_VERSION,
    build_evidence_aware_project_reductions,
)


class Phase6CRetentionTieBreakTests(unittest.TestCase):
    def test_layout_tie_removes_lower_priority_bullet(self):
        stronger = {
            "candidate_order": 0,
            "quality_loss": 1280,
            "reaches_one_page": True,
            "space_saved_ratio": 0.05,
            "change": {
                "change_type": "remove_bullet",
                "protection_tier": 0,
                "evidence_priority": 1,
                "removed_bullet": "Stronger gameplay bullet",
            },
        }
        weaker = {
            "candidate_order": 1,
            "quality_loss": 1280,
            "reaches_one_page": True,
            "space_saved_ratio": 0.05,
            "change": {
                "change_type": "remove_bullet",
                "protection_tier": 0,
                "evidence_priority": 2,
                "removed_bullet": "Weaker UI bullet",
            },
        }

        chosen = _choose_layout_aware_reduction(
            [stronger, weaker]
        )

        self.assertEqual(
            chosen["change"]["removed_bullet"],
            "Weaker UI bullet",
        )

    def test_generated_changes_preserve_evidence_priority_metadata(self):
        projects = {
            "recommended_projects": [
                {
                    "title": "CyberSphere",
                    "display_title": "CyberSphere",
                    "priority": "medium",
                    "project_fit_score": 45,
                    "draft_bullets": [
                        (
                            "Scripted Unity gameplay features for a "
                            "published mobile game."
                        ),
                        (
                            "Implemented user-facing UI features to "
                            "support player progression."
                        ),
                    ],
                    "bullet_evidence_priorities": [
                        {
                            "bullet_index": 0,
                            "bullet_text": (
                                "Scripted Unity gameplay features for "
                                "a published mobile game."
                            ),
                            "supported_requirement_ids": ["req_game"],
                            "protected_requirement_ids": [],
                            "unique_required_core_count": 0,
                            "evidence_value": 10.0,
                            "protect_during_fitting": False,
                            "evidence_priority": 1,
                        },
                        {
                            "bullet_index": 1,
                            "bullet_text": (
                                "Implemented user-facing UI features "
                                "to support player progression."
                            ),
                            "supported_requirement_ids": ["req_game"],
                            "protected_requirement_ids": [],
                            "unique_required_core_count": 0,
                            "evidence_value": 10.0,
                            "protect_during_fitting": False,
                            "evidence_priority": 2,
                        },
                    ],
                }
            ]
        }

        candidates = build_evidence_aware_project_reductions(
            projects,
            minimum_bullets_per_project=1,
        )

        self.assertEqual(len(candidates), 2)
        first_change = candidates[0][1]
        second_change = candidates[1][1]

        changes = [
            change
            for _, change in candidates
        ]

        gameplay_change = next(
            change
            for change in changes
            if "gameplay features" in change["removed_bullet"]
        )

        ui_change = next(
            change
            for change in changes
            if "UI features" in change["removed_bullet"]
        )

        self.assertEqual(
            gameplay_change["evidence_priority"],
            1,
        )
        self.assertEqual(
            ui_change["evidence_priority"],
            2,
        )

        for change in changes:
            self.assertEqual(
                change["retention_tiebreak_version"],
                PHASE6C_RETENTION_TIEBREAK_VERSION,
            )

    def test_protection_tier_still_wins_before_priority(self):
        protected = {
            "candidate_order": 0,
            "quality_loss": 100,
            "reaches_one_page": True,
            "space_saved_ratio": 0.05,
            "change": {
                "protection_tier": 1,
                "evidence_priority": 99,
            },
        }
        unprotected = {
            "candidate_order": 1,
            "quality_loss": 1000,
            "reaches_one_page": True,
            "space_saved_ratio": 0.05,
            "change": {
                "protection_tier": 0,
                "evidence_priority": 1,
            },
        }

        chosen = _choose_layout_aware_reduction(
            [protected, unprotected]
        )
        self.assertIs(chosen, unprotected)


if __name__ == "__main__":
    unittest.main()
