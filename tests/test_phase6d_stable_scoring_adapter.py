from __future__ import annotations

import unittest

from tailoring.phase6d_stable_scoring_adapter import (
    cap_requirement_with_taxonomy,
)


class Phase6DStableScoringAdapterTests(unittest.TestCase):
    def test_direct_cross_functional_overclaim_is_capped_to_weak(self):
        requirement = {
            "text": "Ability to collaborate with cross-functional teams",
            "atomic_focus": "Ability to collaborate with cross-functional teams",
            "match_label": "direct",
            "match_value": 1.0,
            "evidence": [
                {
                    "text": "Collaborated with a team of interns in SCRUM."
                }
            ],
        }
        result = cap_requirement_with_taxonomy(requirement)
        self.assertEqual(result["match_label"], "weak")
        self.assertEqual(result["match_value"], 0.20)
        self.assertEqual(
            result["capability_id"],
            "collaboration.cross_functional",
        )

    def test_adapter_never_upgrades_an_existing_label(self):
        requirement = {
            "text": "Kubernetes orchestration",
            "atomic_focus": "Kubernetes orchestration",
            "match_label": "none",
            "match_value": 0.0,
            "evidence": [{"text": "Created Kubernetes Deployment manifests."}],
        }
        result = cap_requirement_with_taxonomy(requirement)
        self.assertEqual(result["match_label"], "none")


if __name__ == "__main__":
    unittest.main()
