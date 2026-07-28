from __future__ import annotations

import unittest

from tailoring.capability_taxonomy import classify_requirement


class Phase6DExactMatchRefinementTests(unittest.TestCase):
    def test_llm_benchmark_metrics_maps_to_model_evaluation(self):
        capability_id = classify_requirement(
            {
                "text": (
                    "Assess language-model responses using repeatable "
                    "benchmark sets, pass-rate metrics, and regression checks"
                )
            }
        )
        self.assertEqual(capability_id, "ai.model_evaluation")

    def test_service_metrics_maps_to_observability(self):
        capability_id = classify_requirement(
            {
                "text": (
                    "Monitor application metrics and operational alerts "
                    "using Prometheus and Grafana"
                )
            }
        )
        self.assertEqual(capability_id, "devops.observability")

    def test_model_metrics_do_not_map_to_observability(self):
        capability_id = classify_requirement(
            {
                "text": (
                    "Evaluate LLM answers with a benchmark set "
                    "and pass-rate metrics"
                )
            }
        )
        self.assertNotEqual(capability_id, "devops.observability")
        self.assertEqual(capability_id, "ai.model_evaluation")


if __name__ == "__main__":
    unittest.main()
