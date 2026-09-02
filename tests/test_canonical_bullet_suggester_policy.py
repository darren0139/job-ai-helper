from __future__ import annotations

import unittest
from unittest.mock import patch

from tailoring.canonical_bullet_suggester import (
    CANONICAL_BULLET_SUGGESTION_PROMPT,
    extract_canonical_source_contributions,
    suggest_canonical_project_bullets,
)


class CanonicalBulletSuggesterPolicyTests(unittest.TestCase):
    def test_extract_source_contributions_preserves_unbulleted_line_boundaries(self):
        description = (
            "Built one implementation and improved its workflow.\n"
            "Integrated a second system with a supported result.\n"
            "Collaborated across a separate integration workflow."
        )

        self.assertEqual(
            extract_canonical_source_contributions(description),
            [
                "Built one implementation and improved its workflow.",
                "Integrated a second system with a supported result.",
                "Collaborated across a separate integration workflow.",
            ],
        )

    def test_extract_source_contributions_handles_wrapped_bullets_generically(self):
        description = (
            "- Built one implementation and improved its workflow.\n"
            "  Continued context for the same contribution.\n"
            "* Integrated a second system with a supported result."
        )
        self.assertEqual(
            extract_canonical_source_contributions(description),
            [
                (
                    "Built one implementation and improved its workflow. "
                    "Continued context for the same contribution."
                ),
                "Integrated a second system with a supported result.",
            ],
        )

    def test_structured_source_coverage_rejects_silent_source_loss(self):
        def fake_ask_json(system_prompt, user_prompt, **kwargs):
            return {
                "canonical_bullets": [
                    "Built one implementation and improved its workflow."
                ],
                "source_coverage": [
                    {
                        "source_index": 1,
                        "decision": "preserved",
                        "canonical_bullet_indexes": [1],
                        "reason": "",
                    }
                ],
                "notes": [],
            }

        with patch(
            "tailoring.canonical_bullet_suggester.ask_json",
            side_effect=fake_ask_json,
        ):
            with self.assertRaisesRegex(
                ValueError,
                r"source contribution\(s\) 2 were not accounted for",
            ):
                suggest_canonical_project_bullets(
                    title="Example",
                    description=(
                        "- Built one implementation and improved its workflow.\n"
                        "- Collaborated across a separate integration workflow."
                    ),
                )

    def test_structured_source_coverage_requires_merge_reason(self):
        def fake_ask_json(system_prompt, user_prompt, **kwargs):
            return {
                "canonical_bullets": [
                    "Combined two substantially overlapping implementation details."
                ],
                "source_coverage": [
                    {
                        "source_index": 1,
                        "decision": "preserved",
                        "canonical_bullet_indexes": [1],
                        "reason": "",
                    },
                    {
                        "source_index": 2,
                        "decision": "merged",
                        "canonical_bullet_indexes": [1],
                        "reason": "",
                    },
                ],
                "notes": [],
            }

        with patch(
            "tailoring.canonical_bullet_suggester.ask_json",
            side_effect=fake_ask_json,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "merged source 2 requires a concrete reason",
            ):
                suggest_canonical_project_bullets(
                    title="Example",
                    description=(
                        "- Built one implementation.\n"
                        "- Added a dependent detail for the same implementation."
                    ),
                )

    def test_structured_source_coverage_surfaces_merge_reason_in_notes(self):
        def fake_ask_json(system_prompt, user_prompt, **kwargs):
            return {
                "canonical_bullets": [
                    "Combined two substantially overlapping implementation details."
                ],
                "source_coverage": [
                    {
                        "source_index": 1,
                        "decision": "preserved",
                        "canonical_bullet_indexes": [1],
                        "reason": "",
                    },
                    {
                        "source_index": 2,
                        "decision": "merged",
                        "canonical_bullet_indexes": [1],
                        "merged_with_source_indexes": [1],
                        "merge_relation": "dependent_detail",
                        "reason": "It is a dependent detail of the same work.",
                    },
                ],
                "notes": [],
            }

        with patch(
            "tailoring.canonical_bullet_suggester.ask_json",
            side_effect=fake_ask_json,
        ):
            result = suggest_canonical_project_bullets(
                title="Example",
                description=(
                    "- Built one implementation.\n"
                    "- Added a dependent detail for the same implementation."
                ),
            )

        self.assertIn(
            "Source 1 → Preserved as bullet 1.",
            result["notes"],
        )
        self.assertTrue(
            any(
                note.startswith(
                    "Source 2 → Merged with source(s) 1 into bullet(s) 1 "
                )
                and "[dependent_detail]" in note
                and "It is a dependent detail of the same work." in note
                for note in result["notes"]
            )
        )

    def test_prompt_preserves_linked_implementation_and_result(self):
        self.assertIn("Preserve SOURCE LINKAGE", CANONICAL_BULLET_SUGGESTION_PROMPT)
        self.assertIn(
            '"Integrated X ..., supporting Y ..." is normally one canonical contribution',
            CANONICAL_BULLET_SUGGESTION_PROMPT,
        )
        self.assertIn(
            "Do not promote a result clause, implementation detail, or feature "
            "consequence into a separate accomplishment",
            CANONICAL_BULLET_SUGGESTION_PROMPT,
        )

    def test_prompt_prefers_concrete_supported_results(self):
        self.assertIn(
            "Prefer the most concrete supported result/scope wording",
            CANONICAL_BULLET_SUGGESTION_PROMPT,
        )
        self.assertIn(
            'such as "extended capabilities", "improved functionality", or '
            '"enhanced experience"',
            CANONICAL_BULLET_SUGGESTION_PROMPT,
        )

    def test_user_prompt_requires_contribution_clustering_and_split_notes(self):
        captured: dict[str, object] = {}

        def fake_ask_json(system_prompt, user_prompt, **kwargs):
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            captured["kwargs"] = kwargs
            return {
                "canonical_bullets": [
                    (
                        "Integrated FMOD audio systems into gameplay features, "
                        "supporting audio proximity logic in the custom engine."
                    )
                ],
                "source_coverage": [
                    {
                        "source_index": 1,
                        "decision": "preserved",
                        "canonical_bullet_indexes": [1],
                        "reason": "",
                    }
                ],
                "notes": [],
            }

        with patch(
            "tailoring.canonical_bullet_suggester.ask_json",
            side_effect=fake_ask_json,
        ):
            result = suggest_canonical_project_bullets(
                title="The Great Migration",
                period="Sep 2023 - Apr 2024",
                description=(
                    "Integrated FMOD audio systems into gameplay features, "
                    "supporting audio proximity logic in the custom engine."
                ),
                skills=["audio systems"],
                tools=["FMOD", "Custom Game Engine"],
                impact=(
                    "Supported audio proximity logic in an 8-person custom "
                    "game engine project."
                ),
            )

        user_prompt = str(captured["user_prompt"])
        # Assert policy invariants rather than one historical wording.
        self.assertIn(
            "identify the explicit source contributions",
            user_prompt,
        )
        self.assertIn(
            "underlying contribution\nclusters",
            user_prompt,
        )
        self.assertIn(
            "do not manufacture extra\ncontributions by splitting one "
            "implementation-result chain",
            user_prompt,
        )
        self.assertIn(
            "Every MERGED or OMITTED source contribution must be explained",
            user_prompt,
        )
        self.assertIn(
            "the suggestion is incomplete",
            user_prompt,
        )
        self.assertEqual(len(result["canonical_bullets"]), 1)

    def test_prompt_requires_source_coverage_without_fixed_bullet_count(self):
        prompt = CANONICAL_BULLET_SUGGESTION_PROMPT
        self.assertIn("Preserve SOURCE COVERAGE", prompt)
        self.assertIn(
            "every explicit source contribution must end up as PRESERVED",
            prompt,
        )
        self.assertIn(
            "A merge requires substantial semantic overlap in the underlying work",
            prompt,
        )
        self.assertIn(
            "Skills, tools, header metadata, and project-level impact/scope may "
            "enrich a canonical bullet",
            prompt,
        )
        self.assertNotIn("always produce four canonical bullets", prompt.lower())

    def test_user_prompt_requires_coverage_ledger_and_merge_omission_notes(self):
        captured: dict[str, object] = {}

        def fake_ask_json(system_prompt, user_prompt, **kwargs):
            captured["user_prompt"] = user_prompt
            return {
                "canonical_bullets": [
                    "Built one implementation and improved its workflow.",
                    "Added a dependent detail for the same implementation.",
                    "Collaborated across a separate integration workflow.",
                ],
                "source_coverage": [
                    {
                        "source_index": 1,
                        "decision": "preserved",
                        "canonical_bullet_indexes": [1],
                        "reason": "",
                    },
                    {
                        "source_index": 2,
                        "decision": "preserved",
                        "canonical_bullet_indexes": [2],
                        "reason": "",
                    },
                    {
                        "source_index": 3,
                        "decision": "preserved",
                        "canonical_bullet_indexes": [3],
                        "reason": "",
                    },
                ],
                "notes": [],
            }

        with patch(
            "tailoring.canonical_bullet_suggester.ask_json",
            side_effect=fake_ask_json,
        ):
            suggest_canonical_project_bullets(
                title="Example Project",
                description=(
                    "- Built one implementation and improved its workflow.\n"
                    "- Added a dependent detail for the same implementation.\n"
                    "- Collaborated across a separate integration workflow."
                ),
                skills=["systems programming", "team collaboration"],
                tools=["Tool A", "Tool B"],
                impact="Improved the overall project workflow.",
            )

        user_prompt = str(captured["user_prompt"])
        self.assertIn("Run a source-coverage ledger before finalising the JSON", user_prompt)
        self.assertIn("PRESERVED:", user_prompt)
        self.assertIn("MERGED:", user_prompt)
        self.assertIn("OMITTED:", user_prompt)
        self.assertIn(
            "Every MERGED or OMITTED source contribution must be explained",
            user_prompt,
        )
        self.assertIn("the suggestion is incomplete", user_prompt)

    def test_strict_merge_policy_is_generic_and_defaults_to_preserve(self):
        prompt = CANONICAL_BULLET_SUGGESTION_PROMPT
        self.assertIn(
            "duplicate, dependent_detail, same_accomplishment_restated",
            prompt,
        )
        self.assertIn(
            "Shared project, technology, subsystem, team, workflow, or",
            prompt,
        )
        self.assertIn(
            "When uncertain whether a merge is justified, preserve",
            prompt,
        )
        self.assertNotIn("Great Migration", prompt)
        self.assertNotIn("FMOD", prompt)

    def test_structured_source_coverage_rejects_merge_without_relation(self):
        def fake_ask_json(system_prompt, user_prompt, **kwargs):
            return {
                "canonical_bullets": [
                    "Built one implementation with a dependent detail."
                ],
                "source_coverage": [
                    {
                        "source_index": 1,
                        "decision": "preserved",
                        "canonical_bullet_indexes": [1],
                        "reason": "",
                    },
                    {
                        "source_index": 2,
                        "decision": "merged",
                        "canonical_bullet_indexes": [1],
                        "merged_with_source_indexes": [1],
                        "reason": "It is part of the same underlying work.",
                    },
                ],
                "notes": [],
            }

        with patch(
            "tailoring.canonical_bullet_suggester.ask_json",
            side_effect=fake_ask_json,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "must use merge_relation from",
            ):
                suggest_canonical_project_bullets(
                    title="Example",
                    description=(
                        "- Built one implementation.\n"
                        "- Added a dependent detail for the same implementation."
                    ),
                )

    def test_structured_source_coverage_rejects_unanchored_merge_cycle(self):
        def fake_ask_json(system_prompt, user_prompt, **kwargs):
            return {
                "canonical_bullets": ["Combined overlapping source evidence."],
                "source_coverage": [
                    {
                        "source_index": 1,
                        "decision": "merged",
                        "canonical_bullet_indexes": [1],
                        "merged_with_source_indexes": [2],
                        "merge_relation": "duplicate",
                        "reason": "The two source items are duplicate evidence.",
                    },
                    {
                        "source_index": 2,
                        "decision": "merged",
                        "canonical_bullet_indexes": [1],
                        "merged_with_source_indexes": [1],
                        "merge_relation": "duplicate",
                        "reason": "The two source items are duplicate evidence.",
                    },
                ],
                "notes": [],
            }

        with patch(
            "tailoring.canonical_bullet_suggester.ask_json",
            side_effect=fake_ask_json,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "must merge into at least one preserved source contribution",
            ):
                suggest_canonical_project_bullets(
                    title="Example",
                    description=(
                        "- Built one implementation.\n"
                        "- Restated the same implementation."
                    ),
                )

    def test_coverage_notes_are_generated_deterministically(self):
        def fake_ask_json(system_prompt, user_prompt, **kwargs):
            return {
                "canonical_bullets": [
                    "Built one implementation with a dependent detail."
                ],
                "source_coverage": [
                    {
                        "source_index": 1,
                        "decision": "preserved",
                        "canonical_bullet_indexes": [1],
                        "reason": "",
                    },
                    {
                        "source_index": 2,
                        "decision": "merged",
                        "canonical_bullet_indexes": [1],
                        "merged_with_source_indexes": [1],
                        "merge_relation": "dependent_detail",
                        "reason": "It is a dependent detail of the same work.",
                    },
                ],
                "notes": [
                    "An unreliable free-form note that should not drive display."
                ],
            }

        with patch(
            "tailoring.canonical_bullet_suggester.ask_json",
            side_effect=fake_ask_json,
        ):
            result = suggest_canonical_project_bullets(
                title="Example",
                description=(
                    "- Built one implementation.\n"
                    "- Added a dependent detail for the same implementation."
                ),
            )

        self.assertEqual(
            result["notes"][0],
            "Source 1 → Preserved as bullet 1.",
        )
        self.assertIn(
            "Source 2 → Merged with source(s) 1 into bullet(s) 1 "
            "[dependent_detail]",
            result["notes"][1],
        )
        self.assertEqual(
            result["model_notes"],
            ["An unreliable free-form note that should not drive display."],
        )

    def test_generation_parameters_stay_deterministic(self):
        captured: dict[str, object] = {}

        def fake_ask_json(system_prompt, user_prompt, **kwargs):
            captured["kwargs"] = kwargs
            return {
                "canonical_bullets": [
                    "Built a concrete feature and supported its workflow."
                ],
                "source_coverage": [
                    {
                        "source_index": 1,
                        "decision": "preserved",
                        "canonical_bullet_indexes": [1],
                        "reason": "",
                    }
                ],
                "notes": [],
            }

        with patch(
            "tailoring.canonical_bullet_suggester.ask_json",
            side_effect=fake_ask_json,
        ):
            suggest_canonical_project_bullets(
                title="Example",
                description="Built a concrete feature and supported its workflow.",
            )

        self.assertEqual(captured["kwargs"]["temperature"], 0.0)
        self.assertEqual(captured["kwargs"]["max_tokens"], 2000)


if __name__ == "__main__":
    unittest.main()
