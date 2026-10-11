from __future__ import annotations

import unittest

from analysis_stability.stable_evidence_scoring import (
    JD_STRUCTURE_INFERENCE_VERSION,
    SCORING_VERSION,
    build_stable_analysis,
)


class JDStructureFingerprintCompatibilityTests(unittest.TestCase):
    def test_combined_structure_and_scoring_currentness_contract(self) -> None:
        jd = {
            "responsibilities": [
                "Build Python APIs and collaborate in a software team"
            ],
            "required_skills": ["Hands-on experience with Python"],
            "preferred_skills": ["Experience with Docker"],
        }
        resume = {
            "education": [
                {
                    "degree": "Bachelor of Computer Science",
                    "school": "Example University",
                    "courses": [],
                }
            ],
            "experience": [
                {
                    "title": "Software Engineer",
                    "company": "Example",
                    "date": "2025",
                    "bullets": [
                        "Built Python APIs and collaborated in a software team."
                    ],
                }
            ],
            "projects": [
                {
                    "title": "API Project",
                    "company": "",
                    "date": "2025",
                    "bullets": ["Developed Python API services."],
                }
            ],
            "skills": {"Languages": ["Python"], "Tools": ["Git"]},
        }
        keyword_match = {
            "present": [
                {
                    "keyword": "Build Python APIs and collaborate in a software team",
                    "matched_resume_term": (
                        "Built Python APIs and collaborated in a software team."
                    ),
                    "match_type": "direct",
                    "evidence_type": "direct",
                    "found_in": "experience",
                    "match_reason": "Direct verified work evidence.",
                },
                {
                    "keyword": "Hands-on experience with Python",
                    "matched_resume_term": "Python",
                    "match_type": "direct",
                    "evidence_type": "direct",
                    "found_in": "skills",
                    "match_reason": "Exact verified skill.",
                },
            ],
            "missing": [{"keyword": "Experience with Docker"}],
        }

        result = build_stable_analysis(
            jd_profile=jd,
            keyword_match=keyword_match,
            resume_profile=resume,
            raw_resume_text=(
                "Built Python APIs and collaborated in a software team.\nPython"
            ),
        )

        # The previous hash represented scorer v1.15 / registry v1.2.
        # Pin the existing v1.16 / v1.3 identity. Rejected parser
        # hypotheses must not silently alter production currentness.
        self.assertEqual(SCORING_VERSION, "stable-evidence-v1.16-phase6d20")
        self.assertEqual(
            result["input_fingerprint"],
            "3b9ce38aea8345b847b486c710fa8f0c1dda3cc51d8b70cd6657503a25e0379c",
        )
        self.assertEqual(
            JD_STRUCTURE_INFERENCE_VERSION,
            "jd-structure-inference-v1.0.3",
        )
        self.assertEqual(
            result.get("jd_structure_inference_version"),
            JD_STRUCTURE_INFERENCE_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
