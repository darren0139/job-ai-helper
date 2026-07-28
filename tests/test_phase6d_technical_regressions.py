from __future__ import annotations

import unittest

from tailoring.capability_taxonomy import evaluate_evidence


class Phase6DTechnicalRegressionTests(unittest.TestCase):
    def decision(self, requirement: str, evidence: str):
        return evaluate_evidence(
            {"text": requirement, "atomic_focus": requirement},
            evidence,
        )

    def test_docker_does_not_prove_kubernetes(self):
        result = self.decision(
            "Kubernetes orchestration",
            "Containerised the Python application using Docker and Docker Compose.",
        )
        self.assertEqual(result["capability_id"], "devops.kubernetes")
        self.assertEqual(result["label"], "none")

    def test_explicit_kubernetes_evidence_is_direct(self):
        result = self.decision(
            "Kubernetes orchestration",
            "Created Kubernetes Deployment, Service and Ingress manifests.",
        )
        self.assertEqual(result["label"], "direct")

    def test_manual_ai_review_does_not_prove_model_evaluation(self):
        result = self.decision(
            "LLM model evaluation",
            "Manually reviewed AI-generated resume suggestions.",
        )
        self.assertEqual(result["capability_id"], "ai.model_evaluation")
        self.assertEqual(result["label"], "none")

    def test_metric_based_model_evaluation_is_direct(self):
        result = self.decision(
            "LLM model evaluation",
            "Built an evaluation harness with a labelled test set and pass-rate metric.",
        )
        self.assertEqual(result["label"], "direct")

    def test_rest_api_does_not_prove_distributed_architecture(self):
        result = self.decision(
            "Backend API development",
            "Implemented REST API endpoints using FastAPI.",
        )
        self.assertEqual(result["label"], "direct")
        self.assertIn(
            "distributed systems architecture",
            result["does_not_prove"],
        )

    def test_rls_directly_supports_database_access_control(self):
        result = self.decision(
            "Database access control using Row-Level Security",
            "Applied PostgreSQL Row-Level Security policies in Supabase.",
        )
        self.assertEqual(result["capability_id"], "database.access_control")
        self.assertEqual(result["label"], "direct")

    def test_rag_does_not_prove_model_training(self):
        result = self.decision(
            "RAG and vector retrieval",
            "Integrated ChromaDB vector search to retrieve context for an LLM.",
        )
        self.assertEqual(result["label"], "direct")
        self.assertIn("model training", result["does_not_prove"])


if __name__ == "__main__":
    unittest.main()
