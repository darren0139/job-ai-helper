from __future__ import annotations

import unittest

from resume_builder.docx_projects_skills_replacer import (
    _choose_layout_aware_reduction,
    _restore_fitting_change,
    compact_tailored_projects_one_step,
)
from resume_builder.evidence_aware_fitting import (
    PHASE6C_FITTING_VERSION,
    sync_project_bullet_metadata,
)


def _tailored_projects() -> dict:
    project = {
        "title": "QueryAI",
        "display_title": "QueryAI",
        "period": "2026",
        "priority": "medium",
        "project_fit_score": 50,
        "matched_jd_requirements": [],
        "transferable_jd_requirements": [],
        "draft_bullets": [
            "Developed the React interface for ticket creation.",
            "Configured Supabase Row Level Security policies for role-based access.",
        ],
        "compact_bullets": [],
        "space_action": "keep_full",
        "bullet_evidence_priorities": [
            {
                "bullet_index": 0,
                "supported_requirement_ids": [],
                "protected_requirement_ids": [],
                "unique_required_core_count": 0,
                "evidence_value": 0.0,
                "protect_during_fitting": False,
            },
            {
                "bullet_index": 1,
                "supported_requirement_ids": ["req_configuration"],
                "protected_requirement_ids": ["req_configuration"],
                "unique_required_core_count": 1,
                "evidence_value": 12.0,
                "protect_during_fitting": True,
            },
        ],
    }
    sync_project_bullet_metadata(project)
    return {"recommended_projects": [project]}


class EvidenceAwareFitterIntegrationTests(unittest.TestCase):
    def test_compatibility_wrapper_uses_phase6c_candidate(self):
        compacted, changed, change = compact_tailored_projects_one_step(
            _tailored_projects()
        )

        self.assertTrue(changed)
        self.assertEqual(
            change["fitting_version"],
            PHASE6C_FITTING_VERSION,
        )
        self.assertEqual(change["removed_bullet_index"], 0)
        self.assertEqual(
            len(
                compacted["recommended_projects"][0][
                    "bullet_evidence_priorities"
                ]
            ),
            1,
        )

    def test_layout_chooser_keeps_lower_protection_tier(self):
        unprotected = {
            "change": {"protection_tier": 0},
            "reaches_one_page": False,
            "space_saved_ratio": 0.01,
            "quality_loss": 100,
            "candidate_order": 2,
        }
        protected = {
            "change": {"protection_tier": 2},
            "reaches_one_page": True,
            "space_saved_ratio": 0.2,
            "quality_loss": 50,
            "candidate_order": 3,
        }

        chosen = _choose_layout_aware_reduction(
            [protected, unprotected]
        )
        self.assertIs(chosen, unprotected)

    def test_restoration_reinserts_removed_metadata(self):
        compacted, changed, change = compact_tailored_projects_one_step(
            _tailored_projects()
        )
        self.assertTrue(changed)

        restored, restored_ok, _ = _restore_fitting_change(
            compacted,
            change,
        )

        self.assertTrue(restored_ok)
        project = restored["recommended_projects"][0]
        self.assertEqual(len(project["draft_bullets"]), 2)
        self.assertEqual(
            len(project["bullet_evidence_priorities"]),
            2,
        )
        self.assertEqual(project["protected_bullet_indexes"], [1])


if __name__ == "__main__":
    unittest.main()
