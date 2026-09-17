from __future__ import annotations

import unittest

from analysis_stability.stable_evidence_scoring import (
    build_deterministic_keyword_match,
    build_resume_evidence_index,
    link_requirement_matches,
)


def _requirement(text: str, *, requirement_id: str = "req_test") -> dict:
    return {
        "requirement_id": requirement_id,
        "text": text,
        "parent_text": text,
        "atomic_focus": text,
        "importance": "required",
        "is_atomic": False,
    }


class CrossUserEvidenceContextPrecisionTests(unittest.TestCase):
    def test_degree_heading_does_not_prove_infrastructure_design(self) -> None:
        requirement = _requirement("Design infrastructure")
        profile = {
            "education": [
                {
                    "degree": "Diploma in Game Design & Development",
                    "school": "Example Polytechnic",
                    "graduation_date": "2024",
                }
            ]
        }
        keyword_match = {
            "present": [
                {
                    "keyword": "Design infrastructure",
                    "matched_resume_term": "Diploma in Game Design & Development",
                    "match_type": "transferable",
                    "evidence_type": "transferable",
                    "found_in": "education",
                    "match_reason": "Related design background.",
                }
            ],
            "missing": [],
        }

        linked, _ = link_requirement_matches(
            [requirement],
            keyword_match,
            {},
            resume_profile=profile,
            raw_resume_text="Diploma in Game Design & Development",
        )

        self.assertEqual(linked[0]["match_label"], "none")
        self.assertEqual(linked[0]["evidence"], [])

    def test_structured_education_shadows_duplicate_raw_text_line(self) -> None:
        profile = {
            "education": [
                {
                    "degree": "Diploma in Game Design & Development",
                    "school": "Example Polytechnic",
                    "graduation_date": "2024",
                }
            ]
        }

        rows = build_resume_evidence_index(
            profile,
            "Diploma in Game Design & Development",
        )

        self.assertTrue(any(row["section"] == "education" for row in rows))
        self.assertFalse(
            any(
                row["section"] == "raw_text"
                and row["text"] == "Diploma in Game Design & Development"
                for row in rows
            )
        )

    def test_one_word_dynamic_overlap_does_not_prove_fast_paced_environment(self) -> None:
        requirement = _requirement(
            "Ability to work in a fast-paced, dynamic environment"
        )
        bullet = (
            "Integrated A* pathfinding into a custom C++ engine to support "
            "efficient, dynamic navigation for enemy AI."
        )
        profile = {
            "projects": [
                {"title": "Navigation Project", "bullets": [bullet]}
            ]
        }
        keyword_match = {
            "present": [
                {
                    "keyword": requirement["text"],
                    "matched_resume_term": bullet,
                    "match_type": "weak",
                    "evidence_type": "weak",
                    "found_in": "projects",
                    "match_reason": "Related experience.",
                }
            ],
            "missing": [],
        }

        linked, warnings = link_requirement_matches(
            [requirement],
            keyword_match,
            {},
            resume_profile=profile,
        )

        self.assertEqual(linked[0]["match_label"], "none")
        self.assertEqual(linked[0]["evidence"], [])
        self.assertTrue(
            any(
                item.get("code") == "insufficient_weak_evidence_context"
                for item in warnings
            )
        )

    def test_explicit_fast_paced_environment_evidence_can_keep_weak_credit(self) -> None:
        requirement = _requirement(
            "Ability to work in a fast-paced, dynamic environment"
        )
        bullet = (
            "Worked in a fast-paced, dynamic production environment while "
            "resolving time-sensitive incidents."
        )
        profile = {
            "experience": [
                {"title": "Support Engineer", "bullets": [bullet]}
            ]
        }
        keyword_match = {
            "present": [
                {
                    "keyword": requirement["text"],
                    "matched_resume_term": bullet,
                    "match_type": "weak",
                    "evidence_type": "weak",
                    "found_in": "experience",
                    "match_reason": "Explicit work-environment evidence.",
                }
            ],
            "missing": [],
        }

        linked, _ = link_requirement_matches(
            [requirement],
            keyword_match,
            {},
            resume_profile=profile,
        )

        self.assertEqual(linked[0]["match_label"], "weak")
        self.assertEqual(linked[0]["evidence"][0]["text"], bullet)

    def test_docker_kubernetes_project_evidence_remains_available(self) -> None:
        requirement = _requirement(
            "Experience deploying applications using Docker and Kubernetes"
        )
        bullet = (
            "Containerized and deployed the application using Docker and "
            "Kubernetes with health and readiness probes."
        )
        profile = {
            "projects": [
                {"title": "Service Platform", "bullets": [bullet]}
            ],
            "skills": {"tools": ["Docker", "Kubernetes"]},
        }

        result = build_deterministic_keyword_match(
            requirements=[requirement],
            acronym_map={},
            resume_profile=profile,
        )

        self.assertEqual(len(result["present"]), 1)
        self.assertEqual(result["missing"], [])


if __name__ == "__main__":
    unittest.main()
