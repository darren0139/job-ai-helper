from __future__ import annotations

import unittest

from resume_builder.evidence_aware_fitting import (
    PHASE6C_FITTING_VERSION,
    build_evidence_aware_project_reductions,
    remove_project_bullet,
    restore_removed_bullet_metadata,
    sync_project_bullet_metadata,
)


def _project(
    title: str,
    bullets: list[str],
    metadata: list[dict],
    *,
    priority: str = "medium",
    fit_score: int = 50,
) -> dict:
    project = {
        "title": title,
        "display_title": title,
        "period": "2026",
        "priority": priority,
        "project_fit_score": fit_score,
        "matched_jd_requirements": [],
        "transferable_jd_requirements": [],
        "draft_bullets": bullets,
        "compact_bullets": [],
        "space_action": "keep_full",
        "bullet_evidence_priorities": metadata,
        "protected_bullet_indexes": [
            int(row["bullet_index"])
            for row in metadata
            if row.get("protect_during_fitting")
        ],
    }
    sync_project_bullet_metadata(project)
    return project


class EvidenceAwareFittingTests(unittest.TestCase):
    def test_unprotected_bullet_is_removed_before_protected_last_bullet(self):
        project = _project(
            "QueryAI",
            [
                "Developed the React interface for ticket creation.",
                "Configured Supabase Row Level Security policies for role-based access.",
            ],
            [
                {
                    "bullet_index": 0,
                    "bullet_text": "Developed the React interface for ticket creation.",
                    "supported_requirement_ids": [],
                    "protected_requirement_ids": [],
                    "unique_required_core_count": 0,
                    "evidence_value": 0.0,
                    "protect_during_fitting": False,
                    "evidence_priority": 2,
                },
                {
                    "bullet_index": 1,
                    "bullet_text": (
                        "Configured Supabase Row Level Security policies "
                        "for role-based access."
                    ),
                    "supported_requirement_ids": ["req_configuration"],
                    "protected_requirement_ids": ["req_configuration"],
                    "unique_required_core_count": 1,
                    "evidence_value": 12.0,
                    "protect_during_fitting": True,
                    "evidence_priority": 1,
                },
            ],
        )

        candidates = build_evidence_aware_project_reductions(
            {"recommended_projects": [project]}
        )

        self.assertEqual(len(candidates), 2)
        safest_state, safest_change = candidates[0]
        self.assertEqual(safest_change["removed_bullet_index"], 0)
        self.assertEqual(safest_change["protection_tier"], 0)
        self.assertIn(
            "Configured Supabase Row Level Security",
            safest_state["recommended_projects"][0]["draft_bullets"][0],
        )

    def test_globally_unique_requirement_is_protected_across_projects(self):
        project_a = _project(
            "Project A",
            ["Implemented a unique deployment workflow.", "Added UI filters."],
            [
                {
                    "bullet_index": 0,
                    "supported_requirement_ids": ["req_deployment"],
                    "protected_requirement_ids": [],
                    "unique_required_core_count": 0,
                    "evidence_value": 2.0,
                    "protect_during_fitting": False,
                },
                {
                    "bullet_index": 1,
                    "supported_requirement_ids": [],
                    "protected_requirement_ids": [],
                    "unique_required_core_count": 0,
                    "evidence_value": 0.0,
                    "protect_during_fitting": False,
                },
            ],
        )
        project_b = _project(
            "Project B",
            ["Built a dashboard.", "Added export controls."],
            [
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
                    "supported_requirement_ids": [],
                    "protected_requirement_ids": [],
                    "unique_required_core_count": 0,
                    "evidence_value": 0.0,
                    "protect_during_fitting": False,
                },
            ],
        )

        candidates = build_evidence_aware_project_reductions(
            {"recommended_projects": [project_a, project_b]}
        )
        deployment_candidate = next(
            change
            for _, change in candidates
            if change["project"] == "Project A"
            and change["removed_bullet_index"] == 0
        )

        self.assertEqual(
            deployment_candidate["globally_unique_requirement_ids"],
            ["req_deployment"],
        )
        self.assertEqual(deployment_candidate["protection_tier"], 1)

    def test_redundant_requirement_evidence_has_lower_loss_than_unique(self):
        project_a = _project(
            "Project A",
            ["Tested API endpoints.", "Configured access control."],
            [
                {
                    "bullet_index": 0,
                    "supported_requirement_ids": ["req_testing"],
                    "protected_requirement_ids": [],
                    "unique_required_core_count": 0,
                    "evidence_value": 1.0,
                    "protect_during_fitting": False,
                },
                {
                    "bullet_index": 1,
                    "supported_requirement_ids": ["req_access"],
                    "protected_requirement_ids": ["req_access"],
                    "unique_required_core_count": 1,
                    "evidence_value": 8.0,
                    "protect_during_fitting": True,
                },
            ],
        )
        project_b = _project(
            "Project B",
            ["Tested user workflows.", "Built the interface."],
            [
                {
                    "bullet_index": 0,
                    "supported_requirement_ids": ["req_testing"],
                    "protected_requirement_ids": [],
                    "unique_required_core_count": 0,
                    "evidence_value": 1.0,
                    "protect_during_fitting": False,
                },
                {
                    "bullet_index": 1,
                    "supported_requirement_ids": [],
                    "protected_requirement_ids": [],
                    "unique_required_core_count": 0,
                    "evidence_value": 0.0,
                    "protect_during_fitting": False,
                },
            ],
        )

        candidates = build_evidence_aware_project_reductions(
            {"recommended_projects": [project_a, project_b]}
        )
        testing = next(
            change
            for _, change in candidates
            if change["project"] == "Project A"
            and change["removed_bullet_index"] == 0
        )
        access = next(
            change
            for _, change in candidates
            if change["project"] == "Project A"
            and change["removed_bullet_index"] == 1
        )

        self.assertLess(
            testing["evidence_loss_score"],
            access["evidence_loss_score"],
        )

    def test_metadata_is_reindexed_after_deletion_and_restoration(self):
        project = _project(
            "Project",
            ["Bullet zero.", "Bullet one.", "Bullet two."],
            [
                {
                    "bullet_index": 0,
                    "supported_requirement_ids": ["req_0"],
                    "protected_requirement_ids": [],
                },
                {
                    "bullet_index": 1,
                    "supported_requirement_ids": ["req_1"],
                    "protected_requirement_ids": ["req_1"],
                    "protect_during_fitting": True,
                },
                {
                    "bullet_index": 2,
                    "supported_requirement_ids": ["req_2"],
                    "protected_requirement_ids": [],
                },
            ],
        )

        removed_text, removed_metadata = remove_project_bullet(
            project,
            bullet_index=1,
        )
        rows = project["bullet_evidence_priorities"]
        self.assertEqual([row["bullet_index"] for row in rows], [0, 1])
        self.assertEqual(
            rows[1]["supported_requirement_ids"],
            ["req_2"],
        )

        project["draft_bullets"].insert(1, removed_text)
        restore_removed_bullet_metadata(
            project,
            bullet_index=1,
            bullet_text=removed_text,
            removed_metadata=removed_metadata,
        )
        rows = project["bullet_evidence_priorities"]
        self.assertEqual([row["bullet_index"] for row in rows], [0, 1, 2])
        self.assertEqual(
            rows[1]["supported_requirement_ids"],
            ["req_1"],
        )
        self.assertEqual(
            project["protected_bullet_indexes"],
            [1],
        )

    def test_missing_phase6b_metadata_uses_safe_unprotected_defaults(self):
        project = {
            "title": "Legacy Project",
            "display_title": "Legacy Project",
            "period": "2026",
            "priority": "low",
            "project_fit_score": 10,
            "draft_bullets": [
                "Built a small API.",
                "Added a simple dashboard.",
            ],
            "compact_bullets": [],
            "space_action": "keep_full",
        }

        candidates = build_evidence_aware_project_reductions(
            {"recommended_projects": [project]}
        )

        self.assertEqual(len(candidates), 2)
        self.assertTrue(
            all(change["protection_tier"] == 0 for _, change in candidates)
        )
        self.assertTrue(
            all(change["supported_requirement_ids"] == []
                for _, change in candidates)
        )

    def test_compact_wording_sync_preserves_requirement_mapping_by_index(self):
        project = _project(
            "QueryAI",
            [
                "Configured Supabase Row Level Security policies for role-based access.",
                "Developed the React interface for ticket creation.",
            ],
            [
                {
                    "bullet_index": 0,
                    "supported_requirement_ids": ["req_configuration"],
                    "protected_requirement_ids": ["req_configuration"],
                    "unique_required_core_count": 1,
                    "evidence_value": 12.0,
                    "protect_during_fitting": True,
                },
                {
                    "bullet_index": 1,
                    "supported_requirement_ids": [],
                    "protected_requirement_ids": [],
                    "unique_required_core_count": 0,
                    "evidence_value": 0.0,
                    "protect_during_fitting": False,
                },
            ],
        )

        sync_project_bullet_metadata(
            project,
            bullet_texts=[
                "Configured Supabase RLS policies for role-based access.",
                "Developed a React ticket-creation interface.",
            ],
        )

        rows = project["bullet_evidence_priorities"]
        self.assertEqual(
            rows[0]["supported_requirement_ids"],
            ["req_configuration"],
        )
        self.assertEqual(project["protected_bullet_indexes"], [0])
        self.assertEqual(
            rows[0]["bullet_text"],
            "Configured Supabase RLS policies for role-based access.",
        )

    def test_all_protected_bullets_have_deterministic_fallback(self):
        project = _project(
            "Protected Project",
            ["Configured access controls.", "Validated security rules."],
            [
                {
                    "bullet_index": 0,
                    "supported_requirement_ids": ["req_access"],
                    "protected_requirement_ids": ["req_access"],
                    "unique_required_core_count": 1,
                    "evidence_value": 10.0,
                    "protect_during_fitting": True,
                },
                {
                    "bullet_index": 1,
                    "supported_requirement_ids": ["req_validation"],
                    "protected_requirement_ids": ["req_validation"],
                    "unique_required_core_count": 1,
                    "evidence_value": 5.0,
                    "protect_during_fitting": True,
                },
            ],
        )

        candidates = build_evidence_aware_project_reductions(
            {"recommended_projects": [project]}
        )

        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            candidates[0][1]["fitting_version"],
            PHASE6C_FITTING_VERSION,
        )
        self.assertEqual(
            candidates[0][1]["removed_bullet_index"],
            1,
        )

    def test_project_removal_is_only_generated_after_minimum_bullets(self):
        projects = [
            _project(
                f"Project {index}",
                [f"Only bullet {index}."],
                [
                    {
                        "bullet_index": 0,
                        "supported_requirement_ids": [],
                        "protected_requirement_ids": [],
                    }
                ],
            )
            for index in range(4)
        ]

        candidates = build_evidence_aware_project_reductions(
            {"recommended_projects": projects},
            minimum_projects_to_keep=3,
        )

        self.assertEqual(len(candidates), 4)
        self.assertTrue(
            all(change["change_type"] == "remove_project"
                for _, change in candidates)
        )


if __name__ == "__main__":
    unittest.main()
