from __future__ import annotations

import unittest

from tailoring.capability_taxonomy import evaluate_evidence, get_default_taxonomy


class CapabilityTaxonomyV14CppBoundaryTests(unittest.TestCase):
    def _decision(self, requirement: str, evidence: str) -> dict:
        return evaluate_evidence(
            {
                "text": requirement,
                "atomic_focus": requirement,
            },
            evidence,
            get_default_taxonomy(),
        )

    def test_bare_cpp_skill_directly_supports_narrow_knowledge_requirement(self):
        decision = self._decision("Knowledge of C++", "C++")
        self.assertEqual(decision["capability_id"], "language.modern_cpp")
        self.assertEqual(decision["label"], "direct")
        self.assertEqual(decision["reason"], "explicit_language_knowledge")

    def test_bare_cpp_skill_does_not_directly_prove_experience(self):
        decision = self._decision("Experience with C++", "C++")
        self.assertEqual(decision["capability_id"], "language.modern_cpp")
        self.assertEqual(decision["label"], "transferable")
        self.assertEqual(decision["reason"], "language_skill_only")

    def test_cpp_custom_engine_project_title_is_concrete_implementation_evidence(self):
        decision = self._decision(
            "Experience with C++ custom game engines",
            "The Great Migration (C++ Custom Engine, Team of 8) — Sep 2023 - Apr 2024",
        )
        self.assertEqual(decision["capability_id"], "language.modern_cpp")
        self.assertEqual(decision["label"], "direct")
        self.assertEqual(
            decision["reason"],
            "explicit_requested_language_implementation",
        )

    def test_non_modern_cpp_artifact_does_not_prove_modern_cpp(self):
        decision = self._decision(
            "Strong modern C++ programming experience",
            "The Great Migration (C++ Custom Engine, Team of 8)",
        )
        self.assertEqual(decision["capability_id"], "language.modern_cpp")
        self.assertEqual(decision["label"], "transferable")
        self.assertEqual(
            decision["reason"],
            "language_present_modern_proficiency_not_established",
        )

    def test_explicit_cpp_implementation_remains_direct(self):
        decision = self._decision(
            "Experience developing asset-loading systems in C++",
            "Built a C++ asset manager that centralised engine asset loading.",
        )
        self.assertEqual(decision["label"], "direct")

    def test_cpp_implementation_does_not_prove_unevidenced_performance_native_context(self):
        decision = self._decision(
            "C++ high-performance native code for systems-oriented work",
            "Built a C++ asset manager for a custom game engine and integrated FMOD.",
        )
        self.assertEqual(decision["capability_id"], "language.modern_cpp")
        self.assertEqual(decision["label"], "transferable")
        self.assertEqual(
            decision["reason"],
            "language_implementation_without_required_context",
        )

    def test_cpp_explicit_performance_native_context_can_remain_direct(self):
        decision = self._decision(
            "C++ high-performance native code for systems-oriented work",
            (
                "Built and profiled native C++ engine systems for "
                "high-performance asset loading."
            ),
        )
        self.assertEqual(decision["capability_id"], "language.modern_cpp")
        self.assertEqual(decision["label"], "direct")
        self.assertEqual(
            decision["reason"],
            "explicit_requested_language_implementation",
        )

    def test_cpp_course_without_action_remains_none(self):
        decision = self._decision(
            "Experience with C++",
            "Completed a C++ course",
        )
        self.assertEqual(decision["label"], "none")
        self.assertEqual(decision["reason"], "tool_or_learning_only")

    def test_csharp_does_not_prove_cpp(self):
        decision = self._decision(
            "Knowledge of C++",
            "C#",
        )
        self.assertEqual(decision["label"], "none")
        self.assertEqual(decision["reason"], "requested_language_not_evidenced")


if __name__ == "__main__":
    unittest.main()
