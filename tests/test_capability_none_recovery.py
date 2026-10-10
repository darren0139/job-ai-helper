from __future__ import annotations

import unittest

from analysis_stability.stable_evidence_scoring import (
    CAPABILITY_NONE_RECOVERY_POLICY_VERSION,
    SCORING_VERSION,
    build_stable_analysis,
)


class CapabilityNoneRecoveryTests(unittest.TestCase):
    def test_named_api_protocol_completeness_uses_one_atomic_evidence_row(self):
        from tailoring.capability_taxonomy import evaluate_capability_evidence
        cases = (
            ("API development", "Implemented PostgREST API endpoints.", "direct"),
            ("API and REST", "Implemented PostgREST API endpoints.", "direct"),
            ("API, REST and gRPC", "Implemented PostgREST API endpoints.", "none"),
            ("gRPC API development", "Implemented gRPC API endpoints.", "direct"),
            ("REST or gRPC API development", "Implemented REST API endpoints.", "direct"),
            ("gRPC or REST API development", "Implemented gRPC API endpoints.", "direct"),
            ("gRPC API development", "Implemented API endpoints without gRPC.", "none"),
            ("gRPC API development", "Implemented API endpoints, not gRPC.", "none"),
            ("gRPC API development", "Implemented API endpoints; gRPC was not implemented.", "none"),
            ("gRPC API development", "Implemented API endpoints; gRPC is not yet supported.", "none"),
            ("REST API development", "Implemented API endpoints with no REST.", "none"),
            ("API, REST and gRPC", "Implemented REST API endpoints.\nImplemented gRPC API endpoints.", "none"),
            ("API, REST and gRPC", "Implemented REST and gRPC API endpoints.", "direct"),
        )
        for focus, evidence, expected in cases:
            with self.subTest(focus=focus, evidence=evidence):
                result = evaluate_capability_evidence(
                    "backend.api_development", {"atomic_focus": focus}, evidence,
                )
                self.assertEqual(result["label"], expected)
                if expected == "none":
                    self.assertEqual(result["reason"], "requested_api_protocol_evidence_missing")
        child = evaluate_capability_evidence(
            "backend.api_development",
            {"text": "API, REST and gRPC", "parent_text": "API, REST and gRPC", "atomic_focus": "API development"},
            "Implemented PostgREST API endpoints.",
        )
        self.assertEqual(child["label"], "direct")

    def test_job566_compound_does_not_recover_from_postgrest(self):
        text = "· Knowledge of web services, API, REST, and gRPC"
        evidence = "Implemented PostgREST API endpoints with Row-Level Security."
        result = build_stable_analysis(
            jd_profile={"required_skills": [text]},
            keyword_match={"present": [], "missing": [{"keyword": text}]},
            resume_profile={"projects": [{"title": "QueryAI", "bullets": [evidence]}], "skills": {}},
            raw_resume_text=evidence,
        )
        row = next(r for r in result["canonical_requirements"] if r["requirement_id"] == "req_86d57d2e033d")
        self.assertEqual(row["capability_id"], "backend.api_development")
        self.assertEqual(row["match_label"], "none")
        self.assertEqual(row["evidence"], [])
        self.assertEqual(result["capability_none_recovery"]["selection_count"], 0)

    def test_qa_requirement_recovers_real_single_row_from_none(self):
        requirement = (
            "Write automated tests and work with our QA team to ensure "
            "the correctness of new product features"
        )
        evidence = (
            "Added automated unit tests and GitHub Actions CI across Ubuntu "
            "and Windows, running dependency checks, compilation, the full "
            "test suite, and a Streamlit startup health check."
        )
        result = build_stable_analysis(
            jd_profile={
                "required_skills": [requirement],
                "responsibilities": [],
                "preferred_skills": [],
            },
            keyword_match={
                "present": [],
                "missing": [{"keyword": requirement}],
            },
            resume_profile={
                "education": [],
                "experience": [],
                "projects": [
                    {
                        "title": "Job AI Helper",
                        "company": "",
                        "date": "2026",
                        "bullets": [evidence],
                    }
                ],
                "skills": {},
            },
            raw_resume_text=evidence,
        )

        rows = [
            row
            for row in result["canonical_requirements"]
            if row.get("capability_id") == "quality.qa_testing"
        ]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["match_label"], "weak")
        self.assertEqual(row["match_source"], "capability_none_recovery")
        self.assertEqual(
            row["capability_none_recovery"]["status"],
            "recovered_from_none",
        )
        self.assertFalse(
            row["capability_none_recovery"]["combined_evidence_rows"]
        )
        self.assertEqual(len(row["evidence"]), 1)
        self.assertIn("automated unit tests", row["evidence"][0]["text"])
        self.assertGreater(result["deterministic_alignment_score"], 0)

    def test_cpp_requirement_recovers_real_implementation_from_none(self):
        requirement = "Experience developing systems software in C++"
        evidence = (
            "Built a C++ asset manager for a custom game engine, "
            "centralising asset loading and improving pipeline consistency."
        )
        result = build_stable_analysis(
            jd_profile={
                "required_skills": [requirement],
                "responsibilities": [],
                "preferred_skills": [],
            },
            keyword_match={
                "present": [],
                "missing": [{"keyword": requirement}],
            },
            resume_profile={
                "education": [],
                "experience": [],
                "projects": [
                    {
                        "title": "The Great Migration",
                        "company": "",
                        "date": "2024",
                        "bullets": [evidence],
                    }
                ],
                "skills": {"Languages": ["C++"]},
            },
            raw_resume_text=evidence + "\nC++",
        )

        rows = [
            row
            for row in result["canonical_requirements"]
            if row.get("capability_id") == "language.modern_cpp"
        ]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(row["match_source"], "capability_none_recovery")
        self.assertEqual(len(row["evidence"]), 1)
        self.assertIn("C++ asset manager", row["evidence"][0]["text"])

    def test_unrelated_evidence_does_not_recover_qa(self):
        requirement = (
            "Write automated tests and work with our QA team to ensure "
            "the correctness of new product features"
        )
        evidence = "Built React frontend workflows backed by PostgreSQL."
        result = build_stable_analysis(
            jd_profile={
                "required_skills": [requirement],
                "responsibilities": [],
                "preferred_skills": [],
            },
            keyword_match={
                "present": [],
                "missing": [{"keyword": requirement}],
            },
            resume_profile={
                "education": [],
                "experience": [],
                "projects": [
                    {
                        "title": "QueryAI",
                        "company": "",
                        "date": "2025",
                        "bullets": [evidence],
                    }
                ],
                "skills": {},
            },
            raw_resume_text=evidence,
        )

        rows = [
            row
            for row in result["canonical_requirements"]
            if row.get("capability_id") == "quality.qa_testing"
        ]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["match_label"], "none")
        self.assertNotIn("capability_none_recovery", row)
        self.assertEqual(result["capability_none_recovery"]["selection_count"], 0)

    def test_registry_resolved_requirement_is_not_recovered_from_other_technology(self):
        requirement = "Experience with RabbitMQ"
        evidence = "Implemented Kafka event-driven messaging and streaming services."
        result = build_stable_analysis(
            jd_profile={
                "required_skills": [requirement],
                "responsibilities": [],
                "preferred_skills": [],
            },
            keyword_match={
                "present": [],
                "missing": [{"keyword": requirement}],
            },
            resume_profile={
                "education": [],
                "experience": [],
                "projects": [
                    {
                        "title": "Messaging Project",
                        "company": "",
                        "date": "2026",
                        "bullets": [evidence],
                    }
                ],
                "skills": {},
            },
            raw_resume_text=evidence,
        )

        rows = [
            row
            for row in result["canonical_requirements"]
            if row.get("capability_id") == "realtime.messaging_streaming"
        ]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["capability_resolution_source"], "technology_registry")
        self.assertEqual(row["match_label"], "none")
        self.assertNotIn("capability_none_recovery", row)

    def test_explicit_only_subjective_cross_domain_is_not_recovered(self):
        requirement = "Passionate about games"
        evidence = "Passionate about cloud computing."
        result = build_stable_analysis(
            jd_profile={
                "required_skills": [requirement],
                "responsibilities": [],
                "preferred_skills": [],
            },
            keyword_match={
                "present": [],
                "missing": [{"keyword": requirement}],
            },
            resume_profile={
                "summary": evidence,
                "education": [],
                "experience": [],
                "projects": [],
                "skills": {},
            },
            raw_resume_text=evidence,
        )

        rows = [
            row
            for row in result["canonical_requirements"]
            if row.get("capability_id") == "motivation.subjective"
        ]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["match_label"], "none")
        self.assertNotIn("capability_none_recovery", row)

    def test_weak_zero_overlap_configuration_proxy_is_not_recovered(self):
        requirement = (
            "Perform comprehensive troubleshooting to diagnose and fix issues "
            "related to software configuration, performance, and integration"
        )
        evidence = (
            "Implemented backend data access through PostgREST and applied "
            "Row-Level Security policies to secure database operations."
        )
        result = build_stable_analysis(
            jd_profile={
                "required_skills": [requirement],
                "responsibilities": [],
                "preferred_skills": [],
            },
            keyword_match={
                "present": [],
                "missing": [{"keyword": requirement}],
            },
            resume_profile={
                "education": [],
                "experience": [],
                "projects": [
                    {
                        "title": "QueryAI",
                        "company": "",
                        "date": "2025",
                        "bullets": [evidence],
                    }
                ],
                "skills": {},
            },
            raw_resume_text=evidence,
        )

        rows = [
            row
            for row in result["canonical_requirements"]
            if row.get("capability_id") == "operations.configuration"
        ]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["match_label"], "none")
        self.assertNotIn("capability_none_recovery", row)

    def test_policy_and_scoring_versions_are_pinned(self):
        requirement = "Experience developing systems software in C++"
        evidence = "Built a C++ asset manager for a custom game engine."
        result = build_stable_analysis(
            jd_profile={
                "required_skills": [requirement],
                "responsibilities": [],
                "preferred_skills": [],
            },
            keyword_match={
                "present": [],
                "missing": [{"keyword": requirement}],
            },
            resume_profile={
                "education": [],
                "experience": [],
                "projects": [
                    {
                        "title": "Engine",
                        "company": "",
                        "date": "2024",
                        "bullets": [evidence],
                    }
                ],
                "skills": {},
            },
            raw_resume_text=evidence,
        )

        self.assertEqual(SCORING_VERSION, "stable-evidence-v1.15-phase6d20")
        self.assertEqual(
            CAPABILITY_NONE_RECOVERY_POLICY_VERSION,
            "capability-single-row-none-recovery-v1.1",
        )
        self.assertEqual(
            result["capability_none_recovery_policy_version"],
            CAPABILITY_NONE_RECOVERY_POLICY_VERSION,
        )
        self.assertEqual(
            result["capability_none_recovery"]["policy_version"],
            CAPABILITY_NONE_RECOVERY_POLICY_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
