from __future__ import annotations

import unittest
from unittest.mock import patch

from tailoring.project_section_tailor import _score_project_candidates


class AllCanonicalProjectScoringScalingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidates = [
            {
                "title": f"Project {index}",
                "display_title": f"Project {index}",
                "evidence_library_evidence": {
                    "bullets": [
                        f"Built canonical evidence for project {index}."
                    ],
                },
            }
            for index in range(1, 5)
        ]
        self.jd_profile = {
            "required_skills": ["Python"],
            "responsibilities": ["Build systems"],
        }
        self.stable_analysis = {
            "canonical_requirements": [
                {
                    "requirement_id": "req_python",
                    "text": "Python",
                }
            ]
        }

    def _fake_ask_json(
        self,
        _system_prompt: str,
        user_prompt: str,
        **_kwargs,
    ) -> dict:
        supplied = [
            candidate
            for candidate in self.candidates
            if f'"title": "{candidate["title"]}"' in user_prompt
        ]
        return {
            "candidate_project_scores": [
                {
                    "title": candidate["title"],
                    "requirement_matches": [],
                    "matched_jd_requirements": [],
                    "transferable_jd_requirements": [],
                    "must_have_match_score": 1,
                    "responsibility_match_score": 1,
                    "tool_domain_match_score": 1,
                    "evidence_strength_score": 1,
                    "impact_scope_score": 1,
                    "reason": f"Scored {candidate['title']}",
                }
                for candidate in supplied
            ],
            "recommended_project_count": len(supplied),
            "project_count_reason": "test",
            "unsupported_jd_skills": [
                {
                    "skill": "Python",
                    "reason": "Per-project fake negative.",
                }
            ],
            "notes_for_user": [
                f"note:{candidate['title']}"
                for candidate in supplied
            ],
        }

    def test_all_canonical_scores_one_candidate_per_call(self) -> None:
        with patch(
            "tailoring.project_section_tailor.ask_json",
            side_effect=self._fake_ask_json,
        ) as mocked:
            result = _score_project_candidates(
                project_candidates=self.candidates,
                max_projects=4,
                raw_jd_text="Python systems role",
                jd_profile=self.jd_profile,
                stable_analysis=self.stable_analysis,
                keyword_match={},
                bullet_allocation_mode="all_canonical_before_fitting",
                model="openai/gpt-5.6-luna",
            )

        self.assertEqual(mocked.call_count, 4)
        self.assertEqual(
            [row["title"] for row in result["candidate_project_scores"]],
            [candidate["title"] for candidate in self.candidates],
        )
        self.assertEqual(result["recommended_project_count"], 4)
        self.assertEqual(result["unsupported_jd_skills"], [])
        self.assertEqual(
            result["notes_for_user"],
            [f"note:{candidate['title']}" for candidate in self.candidates],
        )

        for index, call in enumerate(mocked.call_args_list):
            user_prompt = call.args[1]
            self.assertEqual(call.kwargs["max_tokens"], 2200)
            self.assertIn(
                f'"title": "{self.candidates[index]["title"]}"',
                user_prompt,
            )
            for other_index, candidate in enumerate(self.candidates):
                if other_index != index:
                    self.assertNotIn(
                        f'"title": "{candidate["title"]}"',
                        user_prompt,
                    )

    def test_adaptive_mode_keeps_existing_single_scoring_call(self) -> None:
        with patch(
            "tailoring.project_section_tailor.ask_json",
            side_effect=self._fake_ask_json,
        ) as mocked:
            result = _score_project_candidates(
                project_candidates=self.candidates,
                max_projects=4,
                raw_jd_text="Python systems role",
                jd_profile=self.jd_profile,
                stable_analysis=self.stable_analysis,
                keyword_match={},
                bullet_allocation_mode="adaptive",
                model="openai/gpt-5.6-luna",
            )

        self.assertEqual(mocked.call_count, 1)
        call = mocked.call_args_list[0]
        self.assertEqual(call.kwargs["max_tokens"], 4200)
        user_prompt = call.args[1]
        for candidate in self.candidates:
            self.assertIn(
                f'"title": "{candidate["title"]}"',
                user_prompt,
            )

        self.assertEqual(
            [row["title"] for row in result["candidate_project_scores"]],
            [candidate["title"] for candidate in self.candidates],
        )
        self.assertEqual(
            result["unsupported_jd_skills"],
            [
                {
                    "skill": "Python",
                    "reason": "Per-project fake negative.",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
