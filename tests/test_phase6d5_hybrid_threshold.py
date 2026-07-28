from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tailoring.phase6d5_retrieval import (
    build_capability_retrieval_trace,
)


def lexical_row(capability_id: str, score: float) -> dict:
    return {
        "id": capability_id,
        "document": capability_id,
        "metadata": {"capability_id": capability_id},
        "score": score,
        "retrieval": "lexical",
    }


def vector_row(capability_id: str, distance: float) -> dict:
    return {
        "id": capability_id,
        "document": capability_id,
        "metadata": {"capability_id": capability_id},
        "distance": distance,
        "retrieval": "embedding",
    }


class Phase6D5HybridThresholdTests(unittest.TestCase):
    def test_hybrid_skips_vector_above_threshold(self):
        with patch.dict(
            os.environ,
            {
                "CAPABILITY_RAG_MODE": "hybrid",
                "CAPABILITY_RAG_VECTOR_THRESHOLD": "0.30",
            },
            clear=False,
        ), patch(
            "tailoring.phase6d5_retrieval.lexical_retrieve",
            return_value=[lexical_row("devops.kubernetes", 0.60)],
        ), patch(
            "tailoring.phase6d5_retrieval.retrieve_taxonomy_candidates"
        ) as vector:
            trace = build_capability_retrieval_trace(
                {"text": "clustered container workloads"},
                exact_capability_id=None,
            )

        vector.assert_not_called()
        self.assertFalse(trace["vector_attempted"])
        self.assertEqual(trace["lexical_top_score"], 0.60)

    def test_hybrid_calls_vector_below_threshold(self):
        with patch.dict(
            os.environ,
            {
                "CAPABILITY_RAG_MODE": "hybrid",
                "CAPABILITY_RAG_VECTOR_THRESHOLD": "0.30",
            },
            clear=False,
        ), patch(
            "tailoring.phase6d5_retrieval.lexical_retrieve",
            return_value=[lexical_row("operations.daily", 0.12)],
        ), patch(
            "tailoring.phase6d5_retrieval.retrieve_taxonomy_candidates",
            return_value=[vector_row("operations.live", 0.18)],
        ) as vector:
            trace = build_capability_retrieval_trace(
                {"text": "restore service after an outage"},
                exact_capability_id=None,
            )

        vector.assert_called_once()
        self.assertTrue(trace["vector_attempted"])
        self.assertEqual(
            trace["vector_trigger_reason"],
            "low_lexical_confidence",
        )
        self.assertIn("vector", trace["used_modes"])
        self.assertFalse(trace["influences_scoring"])

    def test_hybrid_calls_vector_for_ambiguous_tie(self):
        with patch.dict(
            os.environ,
            {
                "CAPABILITY_RAG_MODE": "hybrid",
                "CAPABILITY_RAG_VECTOR_THRESHOLD": "0.20",
            },
            clear=False,
        ), patch(
            "tailoring.phase6d5_retrieval.lexical_retrieve",
            return_value=[
                lexical_row("backend.api_development", 0.40),
                lexical_row("fullstack.integration", 0.39),
            ],
        ), patch(
            "tailoring.phase6d5_retrieval.retrieve_taxonomy_candidates",
            return_value=[],
        ) as vector:
            trace = build_capability_retrieval_trace(
                {"text": "backend service integration"},
                exact_capability_id=None,
            )

        vector.assert_called_once()
        self.assertEqual(
            trace["vector_trigger_reason"],
            "ambiguous_lexical_tie",
        )

    def test_vector_failure_keeps_lexical_candidates(self):
        with patch.dict(
            os.environ,
            {
                "CAPABILITY_RAG_MODE": "hybrid",
                "CAPABILITY_RAG_VECTOR_THRESHOLD": "0.30",
            },
            clear=False,
        ), patch(
            "tailoring.phase6d5_retrieval.lexical_retrieve",
            return_value=[lexical_row("operations.daily", 0.10)],
        ), patch(
            "tailoring.phase6d5_retrieval.retrieve_taxonomy_candidates",
            side_effect=RuntimeError("offline"),
        ):
            trace = build_capability_retrieval_trace(
                {"text": "restore service after an outage"},
                exact_capability_id=None,
            )

        self.assertEqual(
            trace["candidates"][0]["capability_id"],
            "operations.daily",
        )
        self.assertIn(
            "RuntimeError",
            trace["vector_fallback_reason"],
        )
        self.assertFalse(trace["influences_scoring"])


if __name__ == "__main__":
    unittest.main()
