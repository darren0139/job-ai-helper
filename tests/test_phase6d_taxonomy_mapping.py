from __future__ import annotations

import unittest

from tailoring.capability_taxonomy import evaluate_evidence


class Phase6DTaxonomyMappingTests(unittest.TestCase):
    def decision(self, requirement: str, evidence: str):
        return evaluate_evidence(
            {"text": requirement, "atomic_focus": requirement},
            evidence,
        )

    def test_generic_teamwork_is_only_weak_cross_functional_evidence(self):
        result = self.decision(
            "Ability to collaborate with cross-functional teams",
            "Collaborated with a team of interns in a SCRUM environment.",
        )
        self.assertEqual(result["capability_id"], "collaboration.cross_functional")
        self.assertEqual(result["label"], "weak")

    def test_explicit_cross_functional_context_is_transferable(self):
        result = self.decision(
            "Ability to collaborate with cross-functional teams",
            "Collaborated across engineering and design to resolve product issues.",
        )
        self.assertEqual(result["label"], "transferable")

    def test_game_project_without_testing_does_not_prove_qa(self):
        result = self.decision(
            "Gaming product quality assurance",
            "Built gameplay and UI features in Unity for a published game.",
        )
        self.assertEqual(result["label"], "none")

    def test_testing_evidence_is_weak_without_game_context(self):
        result = self.decision(
            "Gaming product quality assurance",
            "Created regression tests and verified defects in a backend service.",
        )
        self.assertEqual(result["label"], "weak")


if __name__ == "__main__":
    unittest.main()
