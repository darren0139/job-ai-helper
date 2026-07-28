from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tailoring.phase6d5_retrieval import build_capability_retrieval_trace


def lexical_row(index: int) -> dict:
    capability_id = f"lexical.capability_{index}"
    return {
        "id": capability_id,
        "metadata": {"capability_id": capability_id},
        "score": 0.20 - index * 0.01,
    }


def vector_row(index: int) -> dict:
    capability_id = f"vector.capability_{index}"
    return {
        "id": capability_id,
        "metadata": {"capability_id": capability_id},
        "distance": 0.10 + index * 0.01,
    }


class Phase6D5FinalTopKTests(unittest.TestCase):
    def test_hybrid_merged_candidates_respect_final_top_k(self):
        with patch.dict(
            os.environ,
            {
                "CAPABILITY_RAG_MODE": "hybrid",
                "CAPABILITY_RAG_TOP_K": "5",
                "CAPABILITY_RAG_VECTOR_THRESHOLD": "0.30",
            },
            clear=False,
        ), patch(
            "tailoring.phase6d5_retrieval.lexical_retrieve",
            return_value=[lexical_row(index) for index in range(5)],
        ), patch(
            "tailoring.phase6d5_retrieval.retrieve_taxonomy_candidates",
            return_value=[vector_row(index) for index in range(5)],
        ):
            trace = build_capability_retrieval_trace(
                {"text": "low confidence test requirement"},
                exact_capability_id=None,
            )

        self.assertTrue(trace["vector_attempted"])
        self.assertLessEqual(len(trace["candidates"]), 5)
        self.assertEqual(trace["top_k"], 5)
        self.assertFalse(trace["influences_scoring"])


if __name__ == "__main__":
    unittest.main()
