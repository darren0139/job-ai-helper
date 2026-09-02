from __future__ import annotations

import unittest

from resume_builder.docx_projects_skills_replacer import (
    _build_safe_bullet_fusion_candidates,
    _build_safe_fused_bullet_text,
    _project_reduction_quality_loss,
    _restore_fitting_change,
)
from resume_builder.evidence_aware_fitting import (
    sync_project_bullet_metadata,
)


def _row(
    index: int,
    *,
    supported=None,
    protected=None,
    unique_core: int = 0,
    evidence_value: float = 0.0,
):
    return {
        "bullet_index": index,
        "supported_requirement_ids": list(supported or []),
        "protected_requirement_ids": list(protected or []),
        "unique_required_core_count": unique_core,
        "evidence_value": evidence_value,
        "protect_during_fitting": bool(protected or unique_core),
        "evidence_priority": index + 1,
    }


def _project(
    bullets,
    rows,
    *,
    title: str = "The Great Migration",
):
    project = {
        "title": title,
        "display_title": f"{title} — Survival Game",
        "period": "Sep 2023 - Apr 2024",
        "priority": "high",
        "project_fit_score": 100,
        "matched_jd_requirements": [
            "Experience developing asset-loading systems in C++",
            "Experience integrating gameplay systems",
        ],
        "transferable_jd_requirements": [],
        "draft_bullets": list(bullets),
        "compact_bullets": [],
        "space_action": "keep_full",
        "bullet_evidence_priorities": list(rows),
        "requirement_matches": [],
    }
    sync_project_bullet_metadata(project)
    return project


class Phase6CBulletFusionTests(unittest.TestCase):
    def test_great_migration_pair_fuses_and_preserves_protected_bullet(self):
        bullets = [
            "Built a C++ asset manager centralising asset loading in a custom game engine.",
            "Integrated FMOD audio systems supporting proximity logic in the custom engine.",
            "Contributed to engine systems and gameplay support in an 8-person team project.",
            "Collaborated with a custom-engine team to integrate systems across asset loading, audio, and gameplay workflows.",
        ]
        shared = [
            "req_asset",
            "req_engine",
            "req_cpp",
            "req_audio",
            "req_gameplay",
        ]
        project = _project(
            bullets,
            [
                _row(0, supported=shared, evidence_value=120.0),
                _row(1, supported=shared, evidence_value=120.0),
                _row(2),
                _row(
                    3,
                    supported=["req_gameplay_integration"],
                    protected=["req_gameplay_integration"],
                    unique_core=1,
                    evidence_value=71.0,
                ),
            ],
        )

        candidates = _build_safe_bullet_fusion_candidates(
            {"recommended_projects": [project]}
        )
        self.assertEqual(len(candidates), 1)

        fused, change = candidates[0]
        fused_project = fused["recommended_projects"][0]
        expected = (
            "Built a C++ asset manager centralising asset loading and integrated "
            "FMOD audio systems supporting proximity logic in a custom game engine."
        )
        self.assertEqual(change["source_bullet_indexes"], [0, 1])
        self.assertEqual(change["merged_bullet"], expected)
        self.assertEqual(
            fused_project["draft_bullets"],
            [expected, bullets[2], bullets[3]],
        )
        self.assertEqual(fused_project["protected_bullet_indexes"], [2])
        self.assertEqual(
            fused_project["bullet_evidence_priorities"][0][
                "supported_requirement_ids"
            ],
            shared,
        )
        self.assertEqual(
            fused_project["bullet_evidence_priorities"][0][
                "fusion_source_count"
            ],
            2,
        )

    def test_shared_engine_context_is_hoisted_once(self):
        merged = _build_safe_fused_bullet_text(
            "Built a C++ asset manager centralising asset loading in a custom game engine.",
            "Integrated FMOD audio systems supporting proximity logic in the custom engine.",
        )
        self.assertEqual(
            merged,
            (
                "Built a C++ asset manager centralising asset loading and integrated "
                "FMOD audio systems supporting proximity logic in a custom game engine."
            ),
        )

    def test_distinct_trailing_contexts_are_not_hoisted(self):
        merged = _build_safe_fused_bullet_text(
            "Built a C++ asset manager centralising asset loading in a custom game engine.",
            "Integrated FMOD audio systems supporting proximity logic in an eight-person engine project.",
        )
        self.assertEqual(
            merged,
            (
                "Built a C++ asset manager centralising asset loading in a custom "
                "game engine and integrated FMOD audio systems supporting proximity "
                "logic in an eight-person engine project."
            ),
        )

    def test_non_anaphoric_specificity_is_not_hoisted(self):
        merged = _build_safe_fused_bullet_text(
            "Built monitoring in a distributed cloud environment.",
            "Integrated alerts in a cloud environment.",
        )
        self.assertEqual(
            merged,
            (
                "Built monitoring in a distributed cloud environment and "
                "integrated alerts in a cloud environment."
            ),
        )

    def test_last_trailing_context_is_used_for_hoisting(self):
        merged = _build_safe_fused_bullet_text(
            "Built asset tooling in Python for workflows in a custom game engine.",
            "Integrated FMOD audio systems supporting proximity logic in the custom engine.",
        )
        self.assertEqual(
            merged,
            (
                "Built asset tooling in Python for workflows and integrated FMOD "
                "audio systems supporting proximity logic in a custom game engine."
            ),
        )

    def test_protected_or_distinct_competency_bullets_are_not_fused(self):
        shared = ["req_engine", "req_gameplay"]
        protected_project = _project(
            [
                "Built a C++ asset manager centralising asset loading in a custom game engine.",
                "Integrated FMOD audio systems supporting proximity logic in the custom engine.",
            ],
            [
                _row(
                    0,
                    supported=shared,
                    protected=["req_engine"],
                    unique_core=1,
                ),
                _row(1, supported=shared),
            ],
        )
        self.assertEqual(
            _build_safe_bullet_fusion_candidates(
                {"recommended_projects": [protected_project]}
            ),
            [],
        )

        collaboration_project = _project(
            [
                "Built a C++ asset manager centralising asset loading in a custom game engine.",
                "Collaborated with an eight-person team to integrate engine systems across gameplay workflows.",
            ],
            [
                _row(0, supported=shared),
                _row(1, supported=shared),
            ],
        )
        self.assertEqual(
            _build_safe_bullet_fusion_candidates(
                {"recommended_projects": [collaboration_project]}
            ),
            [],
        )

    def test_low_requirement_overlap_is_not_fused(self):
        project = _project(
            [
                "Built a C++ asset manager centralising asset loading in a custom game engine.",
                "Integrated FMOD audio systems supporting proximity logic in the custom engine.",
            ],
            [
                _row(0, supported=["req_asset", "req_cpp"]),
                _row(1, supported=["req_audio", "req_gameplay"]),
            ],
        )
        self.assertEqual(
            _build_safe_bullet_fusion_candidates(
                {"recommended_projects": [project]}
            ),
            [],
        )

    def test_fusion_restores_exact_source_bullets_and_metadata(self):
        bullets = [
            "Built a C++ asset manager centralising asset loading in a custom game engine.",
            "Integrated FMOD audio systems supporting proximity logic in the custom engine.",
            "Collaborated with a custom-engine team to integrate systems across asset loading, audio, and gameplay workflows.",
        ]
        shared = ["req_asset", "req_engine", "req_audio"]
        project = _project(
            bullets,
            [
                _row(0, supported=shared, evidence_value=120.0),
                _row(1, supported=shared, evidence_value=120.0),
                _row(
                    2,
                    supported=["req_gameplay"],
                    protected=["req_gameplay"],
                    unique_core=1,
                ),
            ],
        )
        original_rows = [
            dict(row)
            for row in project["bullet_evidence_priorities"]
        ]

        fused, change = _build_safe_bullet_fusion_candidates(
            {"recommended_projects": [project]}
        )[0]
        restored, restored_ok, info = _restore_fitting_change(
            fused,
            change,
        )

        self.assertTrue(restored_ok)
        restored_project = restored["recommended_projects"][0]
        self.assertEqual(restored_project["draft_bullets"], bullets)
        self.assertEqual(
            restored_project["protected_bullet_indexes"],
            [2],
        )
        self.assertEqual(
            [
                row["supported_requirement_ids"]
                for row in restored_project["bullet_evidence_priorities"]
            ],
            [
                row["supported_requirement_ids"]
                for row in original_rows
            ],
        )
        self.assertEqual(
            info["change_type"],
            "restore_bullet_fusion",
        )

    def test_fused_bullet_is_not_recursively_fused_again(self):
        shared = ["req_asset", "req_engine", "req_audio"]
        project = _project(
            [
                "Built a C++ asset manager centralising asset loading in a custom game engine.",
                "Integrated FMOD audio systems supporting proximity logic in the custom engine.",
                "Implemented engine validation tooling supporting asset and audio integration workflows.",
            ],
            [
                _row(0, supported=shared),
                _row(1, supported=shared),
                _row(2, supported=shared),
            ],
        )

        first_state, first_change = next(
            (state, change)
            for state, change in _build_safe_bullet_fusion_candidates(
                {"recommended_projects": [project]}
            )
            if change["source_bullet_indexes"] == [0, 1]
        )
        follow_up = _build_safe_bullet_fusion_candidates(first_state)

        self.assertTrue(
            all(
                0 not in (change.get("source_bullet_indexes") or [])
                for _, change in follow_up
            )
        )

    def test_fusion_cost_is_between_compaction_and_deletion(self):
        fusion_change = {
            "change_type": "bullet_fusion",
            "project_priority_score": 400,
            "source_word_count": 24,
            "merged_word_count": 25,
        }
        deletion_change = {
            "change_type": "remove_bullet",
            "project_priority_score": 400,
            "removed_bullet": (
                "Built a C++ asset manager centralising asset loading in a "
                "custom game engine."
            ),
        }
        self.assertLess(
            _project_reduction_quality_loss(fusion_change),
            _project_reduction_quality_loss(deletion_change),
        )


if __name__ == "__main__":
    unittest.main()
