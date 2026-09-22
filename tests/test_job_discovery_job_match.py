from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

import database.job_match_manager as manager
from job_discovery.matching import (
    MATCH_VERSION,
    analyze_job_match,
    build_profile_evidence_context,
    fingerprint_evidence_items,
    inspect_job_match,
)


class JobMatchSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = manager.DB_PATH
        manager.DB_PATH = Path(self.tempdir.name) / "applications.db"
        manager.init_job_match_schema()

        self.items = [
            {
                "id": 1,
                "category": "Project",
                "title": "RequestFlow",
                "subtitle": "",
                "description": "Built REST APIs with FastAPI.\nContainerized services with Docker.",
                "period": "2026",
                "skills": ["Python", "REST APIs"],
                "tools": ["FastAPI", "Docker"],
                "impact": "Implemented CI/CD workflows.",
                "source_type": "manual",
                "updated_at": "2026-09-01T00:00:00",
            },
            {
                "id": 2,
                "category": "Skill",
                "title": "PostgreSQL",
                "subtitle": "",
                "description": "Used PostgreSQL in application projects.",
                "period": "",
                "skills": ["PostgreSQL"],
                "tools": [],
                "impact": "",
                "source_type": "manual",
                "updated_at": "2026-09-02T00:00:00",
            },
        ]
        self.job = {
            "id": 42,
            "content_hash": "job-hash-a",
            "description": (
                "We are hiring a Software Engineer. The candidate must build REST APIs "
                "using Python and should have experience with Docker and PostgreSQL. "
                "You will design backend services, test software, and collaborate with engineers."
            ),
        }
        self.versions = {
            "match_version": MATCH_VERSION,
            "scoring_version": "test-scoring-v1",
            "taxonomy_version": "test-taxonomy-v1",
        }

    def tearDown(self) -> None:
        manager.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def test_evidence_fingerprint_ignores_updated_at(self) -> None:
        first = fingerprint_evidence_items(self.items)
        changed = [dict(item) for item in self.items]
        changed[0]["updated_at"] = "2099-01-01T00:00:00"
        self.assertEqual(first, fingerprint_evidence_items(changed))

    def test_evidence_fingerprint_changes_on_semantic_change(self) -> None:
        first = fingerprint_evidence_items(self.items)
        changed = [dict(item) for item in self.items]
        changed[0]["description"] += " Added Kubernetes."
        self.assertNotEqual(first, fingerprint_evidence_items(changed))

    def test_profile_context_uses_full_evidence_semantics(self) -> None:
        context = build_profile_evidence_context(self.items)
        self.assertEqual(context["evidence_item_count"], 2)
        self.assertEqual(context["resume_profile"]["projects"][0]["title"], "RequestFlow")
        skill_values = [
            value
            for values in context["resume_profile"]["skills"].values()
            for value in values
        ]
        self.assertIn("Python", skill_values)
        self.assertIn("PostgreSQL", skill_values)
        self.assertIn("Built REST APIs with FastAPI.", context["raw_resume_text"])

    def test_analyze_match_caches_by_job_and_evidence_identity(self) -> None:
        calls = {"extract": 0, "build": 0}

        def extractor(_text):
            calls["extract"] += 1
            return {"required_skills": ["Python", "REST APIs"]}

        def builder(**_kwargs):
            calls["build"] += 1
            return {
                "deterministic_alignment_score": 82,
                "alignment_band": "strong alignment",
                "required_core_coverage_score": 88,
                "preferred_coverage_score": 60,
                "evidence_strength_score": 80,
                "canonical_requirements": [
                    {
                        "requirement_id": "req_python",
                        "text": "Python",
                        "importance": "required",
                        "match_label": "direct",
                    },
                    {
                        "requirement_id": "req_aws",
                        "text": "AWS",
                        "importance": "required",
                        "match_label": "none",
                    },
                ],
            }

        context = build_profile_evidence_context(self.items)
        first = analyze_job_match(
            self.job,
            context=context,
            versions=self.versions,
            jd_profile_extractor=extractor,
            stable_builder=builder,
        )
        second = analyze_job_match(
            self.job,
            context=context,
            versions=self.versions,
            jd_profile_extractor=extractor,
            stable_builder=builder,
        )

        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(calls, {"extract": 1, "build": 1})
        self.assertEqual(first["snapshot"]["summary"]["deterministic_alignment_score"], 82)
        self.assertEqual(first["snapshot"]["summary"]["important_gap_count"], 1)

    def test_evidence_change_marks_previous_snapshot_stale(self) -> None:
        context = build_profile_evidence_context(self.items)

        analyze_job_match(
            self.job,
            context=context,
            versions=self.versions,
            jd_profile_extractor=lambda _text: {"required_skills": ["Python"]},
            stable_builder=lambda **_kwargs: {
                "deterministic_alignment_score": 70,
                "canonical_requirements": [],
            },
        )

        changed_items = [dict(item) for item in self.items]
        changed_items[0]["description"] += "\nAdded Kubernetes deployment."
        changed_context = build_profile_evidence_context(changed_items)

        state = inspect_job_match(
            self.job,
            context=changed_context,
            versions=self.versions,
        )
        self.assertEqual(state["status"], "stale")
        self.assertIn("Profile & Evidence changed", state["stale_reasons"])

    def test_job_hash_change_marks_previous_snapshot_stale(self) -> None:
        context = build_profile_evidence_context(self.items)
        analyze_job_match(
            self.job,
            context=context,
            versions=self.versions,
            jd_profile_extractor=lambda _text: {"required_skills": ["Python"]},
            stable_builder=lambda **_kwargs: {
                "deterministic_alignment_score": 70,
                "canonical_requirements": [],
            },
        )
        changed_job = dict(self.job)
        changed_job["content_hash"] = "job-hash-b"
        state = inspect_job_match(
            changed_job,
            context=context,
            versions=self.versions,
        )
        self.assertEqual(state["status"], "stale")
        self.assertIn("job description changed", state["stale_reasons"])


if __name__ == "__main__":
    unittest.main()
