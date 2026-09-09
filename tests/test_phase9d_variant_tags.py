from __future__ import annotations

import copy
import unittest

from tailoring.phase9d_variant_tags import (
    PHASE9D_VARIANT_TAG_POLICY_VERSION,
    derive_candidate_variant_tag_scores,
    derive_candidate_variant_tags,
    suggest_blueprint_variant_lane,
    variant_tags_from_label,
)
from tests.phase9d_test_support import load_phase9d_fixture


class Phase9DVariantTagTests(unittest.TestCase):
    def test_backend_ai_requirements_suggest_backend_ai(self):
        candidate = {
            "evaluation_metadata": {
                "source_jd_requirement_summary": [
                    {
                        "text": (
                            "Build backend services with Python, FastAPI, Flask, "
                            "and REST APIs"
                        ),
                        "importance": "core",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "backend.api_development",
                    },
                    {
                        "text": (
                            "Build LLM and RAG workflows with vector search "
                            "and pgvector"
                        ),
                        "importance": "core",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "ai.rag_application",
                    },
                    {
                        "text": "Use PostgreSQL for application data",
                        "importance": "required",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "database.relational",
                    },
                    {
                        "text": "Use Docker and AWS CI/CD",
                        "importance": "preferred",
                        "match_label": "transferable",
                        "evidence_strength": 3,
                        "capability_id": "devops.containerisation",
                    },
                ]
            }
        }
        suggestion = suggest_blueprint_variant_lane(
            candidate=candidate,
            active_family_lanes=[
                {"variant_id": "primary", "variant_label": "Primary"}
            ],
        )
        tags = [row["tag"] for row in suggestion["tags"]]
        self.assertIn("Backend", tags)
        self.assertIn("AI", tags)
        self.assertEqual(suggestion["suggested_label"], "Backend / AI")
        self.assertEqual(
            suggestion["recommendation"]["intent"],
            "create_new_variant",
        )

    def test_plural_rest_apis_is_a_backend_signal(self):
        candidate = {
            "evaluation_metadata": {
                "source_jd_requirement_summary": [
                    {
                        "text": "Design REST APIs for application services",
                        "importance": "core",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "",
                    }
                ]
            }
        }
        scores = {
            row["tag"]: row
            for row in derive_candidate_variant_tag_scores(candidate)
        }
        self.assertGreater(scores["Backend"]["score"], 0)
        self.assertIn("rest apis", scores["Backend"]["signals"])

    def test_user_confirmed_backend_ai_tags_recommend_existing_lane(self):
        candidate = load_phase9d_fixture()["candidate"]
        suggestion = suggest_blueprint_variant_lane(
            candidate=candidate,
            active_family_lanes=[
                {"variant_id": "primary", "variant_label": "Primary"},
                {
                    "variant_id": "backend_ai",
                    "variant_label": "Backend / AI",
                },
            ],
            selected_tags=["Backend", "AI"],
        )
        self.assertEqual(suggestion["tag_source"], "user_confirmed")
        self.assertEqual(
            {row["tag"] for row in suggestion["tags"]},
            {"Backend", "AI"},
        )
        self.assertEqual(suggestion["suggested_label"], "Backend / AI")
        self.assertEqual(
            suggestion["recommendation"]["intent"],
            "update_existing_variant",
        )
        self.assertEqual(
            suggestion["recommendation"]["variant_id"],
            "backend_ai",
        )

    def test_strong_backend_signal_survives_dominant_ai_and_devops_scores(self):
        candidate = {
            "evaluation_metadata": {
                "source_jd_requirement_summary": [
                    {
                        "text": (
                            "Build RAG LLM vector-search workflows with OpenAI "
                            "embeddings"
                        ),
                        "importance": "core",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "ai.rag_application",
                    },
                    {
                        "text": "Build LLM workflows with RAG",
                        "importance": "required",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "ai.rag_application",
                    },
                    {
                        "text": "Design REST APIs for application services",
                        "importance": "required",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "",
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
                {"variant_id": "primary", "variant_label": "Primary"},
                {
                    "variant_id": "backend_ai",
                    "variant_label": "Backend / AI",
                },
            ],
        )
        selected = {row["tag"] for row in suggestion["automatic_tags"]}
        self.assertIn("AI", selected)
        self.assertIn("DevOps", selected)
        self.assertIn("Backend", selected)
        self.assertEqual(suggestion["suggested_label"], "Backend / AI")
        self.assertEqual(
            suggestion["recommendation"]["intent"],
            "update_existing_variant",
        )
        self.assertEqual(
            suggestion["recommendation"]["variant_id"],
            "backend_ai",
        )

    def test_existing_backend_ai_lane_is_recommended_for_update(self):
        fixture = load_phase9d_fixture()
        candidate = copy.deepcopy(fixture["candidate"])
        first = suggest_blueprint_variant_lane(
            candidate=candidate,
            active_family_lanes=[
                {"variant_id": "primary", "variant_label": "Primary"}
            ],
        )
        self.assertTrue(first["suggested_label"])
        lane = {
            "variant_id": "suggested_lane",
            "variant_label": first["suggested_label"],
        }
        second = suggest_blueprint_variant_lane(
            candidate=candidate,
            active_family_lanes=[
                {"variant_id": "primary", "variant_label": "Primary"},
                lane,
            ],
        )
        self.assertEqual(
            second["recommendation"]["intent"],
            "update_existing_variant",
        )
        self.assertEqual(
            second["recommendation"]["variant_id"],
            "suggested_lane",
        )

    def test_generalist_falls_back_to_primary(self):
        candidate = {
            "evaluation_metadata": {
                "source_jd_requirement_summary": [
                    {
                        "text": "Build reliable software in a small team",
                        "importance": "required",
                        "match_label": "direct",
                        "evidence_strength": 5,
                        "capability_id": "software.engineering",
                    }
                ]
            }
        }
        suggestion = suggest_blueprint_variant_lane(
            candidate=candidate,
            active_family_lanes=[
                {"variant_id": "primary", "variant_label": "Primary"}
            ],
        )
        self.assertEqual(suggestion["tags"], [])
        self.assertEqual(suggestion["suggested_label"], "")
        self.assertEqual(
            suggestion["recommendation"]["variant_id"],
            "primary",
        )

    def test_requirement_order_does_not_change_tags_or_recommendation(self):
        fixture = load_phase9d_fixture()
        candidate = copy.deepcopy(fixture["candidate"])
        forward = suggest_blueprint_variant_lane(
            candidate=candidate,
            active_family_lanes=[
                {"variant_id": "primary", "variant_label": "Primary"}
            ],
        )
        reversed_candidate = copy.deepcopy(candidate)
        rows = reversed_candidate["evaluation_metadata"][
            "source_jd_requirement_summary"
        ]
        rows.reverse()
        reverse = suggest_blueprint_variant_lane(
            candidate=reversed_candidate,
            active_family_lanes=[
                {"variant_id": "primary", "variant_label": "Primary"}
            ],
        )
        self.assertEqual(forward, reverse)
        self.assertEqual(
            forward["policy_version"],
            PHASE9D_VARIANT_TAG_POLICY_VERSION,
        )

    def test_existing_lane_label_tags_are_stable(self):
        self.assertEqual(
            set(variant_tags_from_label("Backend / AI")),
            {"Backend", "AI"},
        )
        self.assertEqual(
            set(variant_tags_from_label("Backend / Cloud")),
            {"Backend", "DevOps"},
        )
        self.assertEqual(variant_tags_from_label("Primary"), [])

    def test_fixture_has_nonempty_deterministic_specialization(self):
        candidate = load_phase9d_fixture()["candidate"]
        tags = derive_candidate_variant_tags(candidate)
        suggestion = suggest_blueprint_variant_lane(
            candidate=candidate,
            active_family_lanes=[
                {"variant_id": "primary", "variant_label": "Primary"}
            ],
        )
        self.assertTrue(tags)
        self.assertTrue(suggestion["suggested_label"])
        self.assertEqual(
            suggestion["recommendation"]["intent"],
            "create_new_variant",
        )


if __name__ == "__main__":
    unittest.main()
