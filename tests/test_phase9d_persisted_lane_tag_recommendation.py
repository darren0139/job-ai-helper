from __future__ import annotations

import unittest

from tailoring.phase9d_variant_tags import suggest_blueprint_variant_lane


class PersistedBlueprintLaneTagRecommendationTests(unittest.TestCase):
    def test_persisted_lane_tags_drive_strong_overlap_update(self):
        candidate = {
            "evaluation_metadata": {
                "source_jd_requirement_summary": [
                    {
                        "text": "Build REST APIs",
                        "importance": "core",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "backend.api_development",
                    },
                    {
                        "text": "Build LLM RAG workflows",
                        "importance": "core",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "ai.rag_application",
                    },
                    {
                        "text": "Use Docker and CI/CD",
                        "importance": "required",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "devops.containerisation",
                    },
                ]
            }
        }
        suggestion = suggest_blueprint_variant_lane(
            candidate=candidate,
            active_family_lanes=[
                {
                    "variant_id": "primary",
                    "variant_label": "Primary",
                    "persisted_tags": ["Generalist"],
                },
                {
                    "variant_id": "backend_ai",
                    "variant_label": "Backend / AI",
                    "persisted_tags": ["Backend", "AI", "Data"],
                },
            ],
            selected_tags=["Backend", "AI", "DevOps"],
        )
        self.assertEqual(
            suggestion["recommendation"]["intent"],
            "update_existing_variant",
        )
        self.assertEqual(
            suggestion["recommendation"]["variant_id"],
            "backend_ai",
        )
        self.assertIn(
            "strongly overlaps",
            suggestion["recommendation"]["reason"],
        )

    def test_custom_confirmed_tags_can_match_persisted_lane_metadata(self):
        candidate = {"evaluation_metadata": {"source_jd_requirement_summary": []}}
        suggestion = suggest_blueprint_variant_lane(
            candidate=candidate,
            active_family_lanes=[
                {
                    "variant_id": "platform_security",
                    "variant_label": "Platform Security",
                    "persisted_tags": ["Platform Security", "Backend"],
                }
            ],
            selected_tags=["Platform Security", "Backend"],
        )
        self.assertEqual(
            suggestion["recommendation"]["variant_id"],
            "platform_security",
        )
        self.assertEqual(
            suggestion["recommendation"]["intent"],
            "update_existing_variant",
        )


if __name__ == "__main__":
    unittest.main()
