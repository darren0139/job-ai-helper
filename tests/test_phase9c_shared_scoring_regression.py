from __future__ import annotations

import unittest

from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION,
    build_stable_analysis,
)
from tailoring.phase8_requirement_reconciliation import (
    RECONCILIATION_VERSION,
    reconcile_final_requirement_matches,
)
from tests.test_phase8_requirement_reconciliation import (
    analysis,
    generation,
    lineage,
    requirement,
)


class SharedStableScoringRegressionTests(unittest.TestCase):
    def test_phase6d_representative_output_is_byte_semantically_unchanged(self):
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
        rows = result["canonical_requirements"]
        self.assertEqual(SCORING_VERSION, "stable-evidence-v1.3-phase6d7")
        self.assertEqual(
            [row["requirement_id"] for row in rows],
            ["req_fa2df5ec2bec", "req_e234b59a39a9", "req_d548c5b83fa6"],
        )
        self.assertEqual(
            [row["match_label"] for row in rows], ["direct", "direct", "none"]
        )
        self.assertEqual([row["evidence_strength"] for row in rows], [5, 5, 0])
        self.assertEqual(result["deterministic_alignment_score"], 90)
        self.assertEqual(result["required_core_coverage_score"], 100)
        self.assertEqual(result["preferred_coverage_score"], 0)
        self.assertEqual(result["evidence_strength_score"], 100)
        self.assertEqual(
            result["input_fingerprint"],
            "1f67a2e959641d5d61f7162bff6ac20d652bdfa66d51b3b87856b8a76954b96b",
        )

    def test_phase8_representative_output_and_fingerprint_are_unchanged(self):
        requirement_id = "req-access"
        text = (
            "Implement authentication workflows, Row-Level Security policies, "
            "and secure database access"
        )
        bullet = (
            "Implemented backend data access through PostgREST and applied "
            "Row-Level Security policies to secure database operations."
        )
        project = {
            "project_id": "project-query",
            "title": "QueryAI",
            "display_title": "QueryAI (React, Team of 4)",
            "draft_bullets": [bullet],
            "requirement_matches": [
                {
                    "requirement_id": requirement_id,
                    "requirement_text": text,
                    "match_label": "direct",
                    "evidence_snippets": [bullet],
                }
            ],
        }
        state = generation(
            [project],
            skills=["authentication workflows", "access control"],
            rankings=[
                {
                    "skill": "authentication workflows",
                    "matched_requirement_ids": [requirement_id],
                },
                {
                    "skill": "access control",
                    "matched_requirement_ids": [requirement_id],
                },
            ],
        )
        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=analysis(
                [requirement(requirement_id, text, "weak")], score=20
            ),
            after_analysis=analysis(
                [requirement(requirement_id, text, "none")], score=0
            ),
            generation_state=state,
            claim_lineage=lineage(
                project_bullets=[
                    ("project-query", "QueryAI (React, Team of 4)", bullet)
                ],
                skills=["authentication workflows", "access control"],
            ),
        )
        row = reconciled["canonical_requirements"][0]
        self.assertEqual(RECONCILIATION_VERSION, "phase8-final-evidence-reconciliation-v2")
        self.assertEqual(row["requirement_id"], "req-access")
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(row["evidence_strength"], 5)
        self.assertEqual(reconciled["deterministic_alignment_score"], 100)
        self.assertEqual(reconciled["required_core_coverage_score"], 100)
        self.assertEqual(reconciled["preferred_coverage_score"], 0)
        self.assertEqual(reconciled["evidence_strength_score"], 100)
        self.assertEqual(
            report["reconciliation_fingerprint"],
            "5a151c3e9b47ed4b6eeb5b4adef516012c2a201968c5a4fbe985468f47acd6c1",
        )


if __name__ == "__main__":
    unittest.main()
