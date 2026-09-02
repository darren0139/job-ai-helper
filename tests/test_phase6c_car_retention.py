from __future__ import annotations

import unittest

from resume_builder.car_retention import (
    PHASE6C_CAR_RETENTION_VERSION,
    analyse_car_components,
    car_transform_preserves_minimum,
    evaluate_car_retention,
)
from resume_builder.docx_projects_skills_replacer import (
    _build_evidence_preserving_compact_bullets,
    _build_safe_fused_bullet_text,
)


class Phase6CCARRetentionTests(unittest.TestCase):
    def test_great_migration_compact_keeps_car_dimensions(self):
        source = (
            "Built a C++ asset manager for a custom game engine, centralising "
            "asset loading and improving pipeline consistency."
        )
        compact = (
            "Built a C++ asset manager centralising asset loading in a custom "
            "game engine."
        )
        evaluation = evaluate_car_retention([source], compact)
        self.assertTrue(evaluation["preserves_minimum"])
        self.assertEqual(
            set(evaluation["source_dimensions"]),
            {"context", "action", "result"},
        )
        self.assertIn("centralise", evaluation["candidate"]["result_cues"])

    def test_compaction_that_drops_result_is_rejected(self):
        source = (
            "Built a deployment workflow using Docker, improving execution "
            "consistency across environments."
        )
        compact = "Built a deployment workflow using Docker."
        self.assertFalse(car_transform_preserves_minimum(source, compact))
        evaluation = evaluate_car_retention([source], compact)
        self.assertIn(
            "candidate_lost_result_dimension",
            evaluation["reasons"],
        )

    def test_compaction_that_drops_explicit_context_is_rejected(self):
        source = (
            "Built an asset manager in a custom game engine, improving pipeline "
            "consistency."
        )
        compact = "Built an asset manager, improving pipeline consistency."
        self.assertFalse(car_transform_preserves_minimum(source, compact))
        evaluation = evaluate_car_retention([source], compact)
        self.assertIn(
            "candidate_lost_context_dimension",
            evaluation["reasons"],
        )

    def test_mixed_compaction_keeps_full_text_when_car_would_be_lost(self):
        full = [
            (
                "Built a deployment workflow using Docker, improving execution "
                "consistency across environments."
            ),
            (
                "Integrated FMOD audio systems into gameplay features, supporting "
                "proximity logic in a custom game engine."
            ),
        ]
        compact = [
            (
                "Built a deployment workflow using Docker across local "
                "development environments."
            ),
            (
                "Integrated FMOD audio systems supporting proximity logic in a "
                "custom game engine."
            ),
        ]
        project = {
            "draft_bullets": list(full),
            "protected_bullet_indexes": [],
            "bullet_evidence_priorities": [
                {
                    "bullet_index": 0,
                    "bullet_text": full[0],
                    "supported_requirement_ids": [],
                    "protected_requirement_ids": [],
                    "unique_required_core_count": 0,
                    "evidence_value": 0.0,
                    "protect_during_fitting": False,
                    "evidence_priority": 1,
                },
                {
                    "bullet_index": 1,
                    "bullet_text": full[1],
                    "supported_requirement_ids": [],
                    "protected_requirement_ids": [],
                    "unique_required_core_count": 0,
                    "evidence_value": 0.0,
                    "protect_during_fitting": False,
                    "evidence_priority": 2,
                },
            ],
        }
        result = _build_evidence_preserving_compact_bullets(
            project,
            full_bullets=full,
            compact_bullets=compact,
        )
        self.assertIsNotNone(result)
        mixed, protected, compacted = result
        self.assertEqual(protected, [])
        self.assertEqual(compacted, [1])
        self.assertEqual(mixed[0], full[0])
        self.assertEqual(mixed[1], compact[1])

    def test_great_migration_fusion_preserves_car(self):
        first = (
            "Built a C++ asset manager centralising asset loading in a custom "
            "game engine."
        )
        second = (
            "Integrated FMOD audio systems supporting proximity logic in the "
            "custom engine."
        )
        merged = _build_safe_fused_bullet_text(first, second)
        self.assertIsNotNone(merged)
        evaluation = evaluate_car_retention(
            [first, second],
            merged or "",
        )
        self.assertTrue(evaluation["preserves_minimum"])
        self.assertEqual(
            analyse_car_components(merged or "")["car_strength"],
            3,
        )

    def test_fusion_that_drops_source_result_is_rejected_by_car_gate(self):
        first = (
            "Built monitoring in a cloud environment, improving incident "
            "visibility."
        )
        second = (
            "Integrated alerts in the cloud environment, reducing response time."
        )
        bad_candidate = (
            "Built monitoring and integrated alerts in a cloud environment."
        )
        evaluation = evaluate_car_retention(
            [first, second],
            bad_candidate,
        )
        self.assertFalse(evaluation["preserves_minimum"])
        self.assertIn(
            "candidate_lost_result_dimension",
            evaluation["reasons"],
        )

    def test_result_retention_requires_source_result_signal_overlap(self):
        source = (
            "Built a deployment workflow using Docker, improving execution "
            "consistency across environments."
        )
        candidate = (
            "Built a deployment workflow using Docker, supporting local "
            "development environments."
        )
        evaluation = evaluate_car_retention([source], candidate)
        self.assertFalse(evaluation["preserves_minimum"])
        self.assertEqual(evaluation["retained_result_cues"], [])

    def test_policy_version_is_explicit(self):
        self.assertEqual(
            PHASE6C_CAR_RETENTION_VERSION,
            "phase6c4-car-retention-v2-selective-compaction",
        )


if __name__ == "__main__":
    unittest.main()
