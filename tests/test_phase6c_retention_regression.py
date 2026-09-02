from __future__ import annotations

import unittest

from resume_builder.docx_projects_skills_replacer import (
    _restore_fitting_change,
    apply_compact_bullets_once,
)
from resume_builder.evidence_aware_fitting import (
    build_evidence_aware_project_reductions,
    remove_project_bullet,
    sync_project_bullet_metadata,
)


def _row(index, *, supported=None, protected=None, unique_core=0, evidence_value=0.0):
    return {
        "bullet_index": index,
        "supported_requirement_ids": list(supported or []),
        "protected_requirement_ids": list(protected or []),
        "unique_required_core_count": unique_core,
        "evidence_value": evidence_value,
        "protect_during_fitting": bool(protected or unique_core),
        "evidence_priority": index + 1,
    }


def _project(title, bullets, rows, *, compact_bullets=None, requirement_matches=None):
    project = {
        "title": title,
        "display_title": title,
        "period": "2026",
        "priority": "medium",
        "project_fit_score": 50,
        "matched_jd_requirements": [],
        "transferable_jd_requirements": [],
        "draft_bullets": list(bullets),
        "compact_bullets": list(compact_bullets or []),
        "space_action": "keep_full",
        "bullet_evidence_priorities": rows,
        "requirement_matches": list(requirement_matches or []),
    }
    sync_project_bullet_metadata(project)
    return project


class Phase6CRetentionRegressionTests(unittest.TestCase):
    def test_mixed_compaction_preserves_protected_bullet_text_exactly(self):
        protected_full = (
            "Implemented role based access controls using Supabase policies "
            "to preserve authenticated project data safely."
        )
        unprotected_full = (
            "Developed a responsive React ticket interface with reusable "
            "components for the internal request workflow."
        )
        protected_compact = (
            "Implemented Supabase access controls with authenticated policies "
            "for safe project data handling."
        )
        unprotected_compact = (
            "Developed a responsive React ticket interface with reusable "
            "components for request workflows."
        )
        project = _project(
            "QueryAI",
            [protected_full, unprotected_full],
            [
                _row(
                    0,
                    supported=["req_access"],
                    protected=["req_access"],
                    unique_core=1,
                    evidence_value=10.0,
                ),
                _row(1),
            ],
            compact_bullets=[protected_compact, unprotected_compact],
        )

        compacted, changed, change = apply_compact_bullets_once(
            {"recommended_projects": [project]}
        )

        self.assertTrue(changed)
        bullets = compacted["recommended_projects"][0]["draft_bullets"]
        self.assertEqual(bullets[0], protected_full)
        self.assertEqual(bullets[1], unprotected_compact)
        self.assertEqual(change["protected_bullet_indexes_preserved"], [0])
        self.assertEqual(change["compacted_bullet_indexes"], [1])
        self.assertTrue(change["protected_bullet_text_preserved"])
        self.assertEqual(change["source_compact_bullet_count"], 2)
        self.assertEqual(change["applied_compact_bullet_count"], 1)
        self.assertEqual(change["compact_bullet_count"], 1)

    def test_all_protected_project_is_not_compacted(self):
        full = [
            "Implemented role based access controls using Supabase policies to preserve authenticated project data safely.",
            "Validated deployment security rules across the application workflow before releasing the project build.",
        ]
        compact = [
            "Implemented Supabase access controls with authenticated policies for safe project data handling.",
            "Validated deployment security rules across the application workflow before project release.",
        ]
        project = _project(
            "Protected",
            full,
            [
                _row(0, supported=["req_access"], protected=["req_access"], unique_core=1),
                _row(1, supported=["req_security"], protected=["req_security"], unique_core=1),
            ],
            compact_bullets=compact,
        )

        compacted, changed, change = apply_compact_bullets_once(
            {"recommended_projects": [project]}
        )
        self.assertFalse(changed)
        self.assertEqual(compacted["recommended_projects"][0]["draft_bullets"], full)
        self.assertEqual(change["change_type"], "compact_rewrite_unavailable")

    def test_required_core_becomes_tier_two_after_other_support_is_removed(self):
        req_match = {
            "requirement_id": "req_cpp",
            "importance": "required",
            "match_label": "direct",
            "coverage_points": 30.0,
        }
        project_a = _project(
            "Great Migration",
            [
                "Implemented the gameplay migration layer in C++ for engine integration.",
                "Documented the migration workflow for the project team.",
            ],
            [_row(0, supported=["req_cpp"], evidence_value=30.0), _row(1)],
            requirement_matches=[req_match],
        )
        project_b = _project(
            "Other C++",
            [
                "Built a C++ utility for asset processing and validation.",
                "Added documentation for the asset workflow.",
            ],
            [_row(0, supported=["req_cpp"], evidence_value=30.0), _row(1)],
            requirement_matches=[req_match],
        )

        before = build_evidence_aware_project_reductions(
            {"recommended_projects": [project_a, project_b]}
        )
        before_change = next(
            change
            for _, change in before
            if change["project"] == "Great Migration"
            and change["removed_bullet_index"] == 0
        )
        self.assertEqual(before_change["protection_tier"], 0)

        remove_project_bullet(project_b, bullet_index=0)
        after = build_evidence_aware_project_reductions(
            {"recommended_projects": [project_a, project_b]}
        )
        after_change = next(
            change
            for _, change in after
            if change["project"] == "Great Migration"
            and change["removed_bullet_index"] == 0
        )
        self.assertEqual(after_change["protection_tier"], 2)
        self.assertEqual(
            after_change["dynamic_unique_required_core_requirement_ids"],
            ["req_cpp"],
        )
        self.assertIn("became the only retained", after_change["evidence_loss_reason"])

    def test_compact_restore_resynchronises_metadata_text(self):
        full = [
            "Implemented role based access controls using Supabase policies to preserve authenticated project data safely.",
            "Developed a responsive React ticket interface with reusable components for the internal request workflow.",
        ]
        compact = [
            "Implemented Supabase access controls with authenticated policies for safe project data handling.",
            "Developed a responsive React ticket interface with reusable components for request workflows.",
        ]
        project = _project(
            "QueryAI",
            full,
            [
                _row(0, supported=["req_access"], protected=["req_access"], unique_core=1),
                _row(1),
            ],
            compact_bullets=compact,
        )
        compacted, changed, change = apply_compact_bullets_once(
            {"recommended_projects": [project]}
        )
        self.assertTrue(changed)

        restored, restored_ok, _ = _restore_fitting_change(compacted, change)
        self.assertTrue(restored_ok)
        restored_project = restored["recommended_projects"][0]
        self.assertEqual(restored_project["draft_bullets"], full)
        self.assertEqual(
            [row["bullet_text"] for row in restored_project["bullet_evidence_priorities"]],
            full,
        )
        self.assertEqual(restored_project["protected_bullet_indexes"], [0])


if __name__ == "__main__":
    unittest.main()
