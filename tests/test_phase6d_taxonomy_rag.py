from __future__ import annotations

import unittest

from rag.capability_taxonomy_rag import lexical_retrieve


class Phase6DTaxonomyRAGTests(unittest.TestCase):
    def test_lexical_retrieval_finds_kubernetes(self):
        results = lexical_retrieve(
            "orchestrated containers with Kubernetes ingress",
            top_k=5,
        )
        ids = [row["metadata"]["capability_id"] for row in results]
        self.assertIn("devops.kubernetes", ids)

    def test_lexical_retrieval_finds_rag(self):
        results = lexical_retrieve(
            "used ChromaDB vector search to retrieve context for an LLM",
            top_k=5,
        )
        ids = [row["metadata"]["capability_id"] for row in results]
        self.assertIn("ai.rag_application", ids)


if __name__ == "__main__":
    unittest.main()
