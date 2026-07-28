from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tailoring.phase6d5_retrieval import (
    build_capability_retrieval_trace,
)
from tailoring.phase6d_stable_scoring_adapter import (
    cap_requirement_with_taxonomy,
)


class Phase6D5RetrievalIntegrationTests(unittest.TestCase):
    def test_exact_match_skips_retrieval(self):
        with patch.dict(
            os.environ,
            {"CAPABILITY_RAG_MODE": "hybrid"},
            clear=False,
        ):
            trace = build_capability_retrieval_trace(
                {
                    "text": "Kubernetes orchestration",
                    "atomic_focus": "Kubernetes orchestration",
                },
                exact_capability_id="devops.kubernetes",
            )

        self.assertEqual(
            trace["status"],
            "not_needed_exact_match",
        )
        self.assertEqual(trace["used_modes"], [])
        self.assertEqual(trace["candidates"], [])
        self.assertFalse(trace["influences_scoring"])

    def test_lexical_shadow_candidates_do_not_change_score(self):
        row = {
            "text": "container cluster orchestration",
            "atomic_focus": "container cluster orchestration",
            "match_label": "transferable",
            "match_value": 0.55,
            "evidence_strength": 3,
            "evidence": [
                {
                    "text": (
                        "Worked with Docker containers "
                        "in a local development workflow."
                    )
                }
            ],
        }

        with patch.dict(
            os.environ,
            {"CAPABILITY_RAG_MODE": "lexical"},
            clear=False,
        ):
            result = cap_requirement_with_taxonomy(row)

        self.assertEqual(
            result["capability_taxonomy_cap_status"],
            "unrecognised",
        )
        self.assertEqual(
            result["match_label"],
            "transferable",
        )
        trace = result["capability_retrieval"]
        self.assertTrue(trace["shadow_only"])
        self.assertFalse(trace["influences_scoring"])
        self.assertIn("lexical", trace["used_modes"])
        ids = [
            item["capability_id"]
            for item in trace["candidates"]
        ]
        self.assertIn("devops.kubernetes", ids)

    def test_hybrid_avoids_vector_when_lexical_has_candidates(self):
        with patch.dict(
            os.environ,
            {"CAPABILITY_RAG_MODE": "hybrid"},
            clear=False,
        ), patch(
            "tailoring.phase6d5_retrieval."
            "retrieve_taxonomy_candidates"
        ) as vector:
            trace = build_capability_retrieval_trace(
                {
                    "text": "container cluster orchestration",
                    "atomic_focus": (
                        "container cluster orchestration"
                    ),
                },
                exact_capability_id=None,
            )

        vector.assert_not_called()
        self.assertIn("lexical", trace["used_modes"])

    def test_vector_failure_falls_back_without_breaking_analysis(self):
        with patch.dict(
            os.environ,
            {"CAPABILITY_RAG_MODE": "vector"},
            clear=False,
        ), patch(
            "tailoring.phase6d5_retrieval."
            "retrieve_taxonomy_candidates",
            side_effect=RuntimeError("offline"),
        ):
            trace = build_capability_retrieval_trace(
                {
                    "text": "container cluster orchestration",
                    "atomic_focus": (
                        "container cluster orchestration"
                    ),
                },
                exact_capability_id=None,
            )

        self.assertIn(
            "lexical_fallback",
            trace["used_modes"],
        )
        self.assertIn(
            "RuntimeError",
            trace["vector_fallback_reason"],
        )
        self.assertFalse(trace["influences_scoring"])


if __name__ == "__main__":
    unittest.main()
