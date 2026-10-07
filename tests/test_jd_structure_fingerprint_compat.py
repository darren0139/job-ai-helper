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

        # Capability discovery intentionally advances scorer/registry
        # currentness. Pin the merged structure-and-scoring contract instead
        # of treating the older Phase 6D fingerprint as current.
        self.assertEqual(SCORING_VERSION, "stable-evidence-v1.12-phase6d18")
        self.assertEqual(
            result["input_fingerprint"],
            "24561642a839a4ba74bab4de412b696de2cb7dd24f0960a37c5c8c342aad467d",
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
