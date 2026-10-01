from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

import database.job_match_manager as job_match_manager
from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION,
    build_deterministic_keyword_match,
    build_stable_analysis,
    canonicalise_requirements,
)
from job_discovery.matching import (
    MATCH_VERSION,
    analyze_job_match,
    build_profile_evidence_context,
    current_match_versions,
)
from tailoring.phase6d_stable_scoring_adapter import cap_requirement_with_taxonomy
from taxonomy_discovery.observations import build_taxonomy_resolution_diagnostics
from taxonomy_discovery.technology_registry import get_default_registry


class TechnologyRegistryStableAnalysisIntegrationTests(unittest.TestCase):
    def test_registry_fallback_resolves_rabbitmq_without_upgrading_none(self):
        row = {
            "requirement_id": "req_rabbitmq",
            "text": "Experience with RabbitMQ",
            "atomic_focus": "Experience with RabbitMQ",
            "importance": "required",
            "score_eligible": True,
            "match_label": "none",
            "match_value": 0.0,
            "evidence_strength": 0,
            "evidence": [],
        }
        result = cap_requirement_with_taxonomy(row)
        self.assertEqual(result["capability_id"], "realtime.messaging_streaming")
        self.assertEqual(result["capability_resolution_source"], "technology_registry")
        self.assertEqual(result["technology_registry_resolution"]["status"], "resolved")
        self.assertEqual(result["match_label"], "none")
        self.assertEqual(result["match_value"], 0.0)

    def test_registry_mapping_never_promotes_existing_none_label(self):
        row = {
            "requirement_id": "req_rabbitmq",
            "text": "Experience with RabbitMQ",
            "atomic_focus": "Experience with RabbitMQ",
            "importance": "required",
            "score_eligible": True,
            "match_label": "none",
            "match_value": 0.0,
            "evidence_strength": 0,
            "evidence": [{"text": "Implemented Kafka event-driven messaging and streaming services."}],
        }
        result = cap_requirement_with_taxonomy(row)
        self.assertEqual(result["capability_resolution_source"], "technology_registry")
        self.assertEqual(result["match_label"], "none")
        self.assertEqual(result["evidence_strength"], 0)

    def test_recognized_unmapped_mongodb_stays_unresolved(self):
        row = {
            "requirement_id": "req_mongodb",
            "text": "Experience with MongoDB",
            "atomic_focus": "Experience with MongoDB",
            "importance": "required",
            "score_eligible": True,
            "match_label": "none",
            "match_value": 0.0,
            "evidence_strength": 0,
            "evidence": [],
        }
        result = cap_requirement_with_taxonomy(row)
        self.assertNotIn("capability_id", result)
        self.assertEqual(result["technology_registry_resolution"]["status"], "recognized_unmapped")
        self.assertEqual(result["capability_resolution_source"], "unresolved")

    def test_canonical_taxonomy_wins_before_registry_fallback(self):
        row = {
            "requirement_id": "req_docker",
            "text": "Experience with Docker",
            "atomic_focus": "Experience with Docker",
            "importance": "required",
            "score_eligible": True,
            "match_label": "none",
            "match_value": 0.0,
            "evidence_strength": 0,
            "evidence": [],
        }
        result = cap_requirement_with_taxonomy(row)
        self.assertEqual(result["capability_id"], "devops.containerisation")
        self.assertEqual(result["capability_resolution_source"], "canonical_taxonomy")
        self.assertNotIn("technology_registry_resolution", result)

    def test_stable_analysis_pins_registry_and_resolves_rabbitmq(self):
        jd_profile = {
            "required_skills": ["Experience with RabbitMQ"],
            "preferred_skills": [],
            "responsibilities": [],
            "soft_skills": [],
            "tools_technologies": [],
            "deal_breakers": [],
        }
        raw_jd_text = "Requirements\nExperience with RabbitMQ"
        canonical = canonicalise_requirements(jd_profile=jd_profile, raw_jd_text=raw_jd_text)
        keyword_match = build_deterministic_keyword_match(
            requirements=canonical.get("requirements", []) or [],
            acronym_map=canonical.get("acronym_map", {}) or {},
            resume_profile={}, raw_resume_text="",
        )
        result = build_stable_analysis(
            jd_profile=jd_profile, keyword_match=keyword_match,
            raw_jd_text=raw_jd_text, raw_resume_text="", resume_profile={},
        )
        self.assertEqual(result["scoring_version"], SCORING_VERSION)
        self.assertEqual(result["technology_registry_version"], get_default_registry().version)
        rows = [
            row for row in result["canonical_requirements"]
            if "RabbitMQ" in str(row.get("atomic_focus") or row.get("text") or "")
        ]
        self.assertTrue(rows)
        self.assertEqual(rows[0]["capability_id"], "realtime.messaging_streaming")
        self.assertEqual(rows[0]["capability_resolution_source"], "technology_registry")
        self.assertEqual(rows[0]["match_label"], "none")

    def test_discovery_uses_snapshot_pinned_registry_resolution(self):
        stable = {
            "technology_registry_version": "technology-registry-v1.1",
            "canonical_requirements": [{
                "requirement_id": "req_rabbitmq",
                "text": "Experience with RabbitMQ",
                "atomic_focus": "Experience with RabbitMQ",
                "importance": "required",
                "score_eligible": True,
                "match_label": "none",
                "capability_id": "realtime.messaging_streaming",
                "capability_resolution_source": "technology_registry",
                "technology_registry_resolution": {
                    "status": "resolved",
                    "registry_version": "technology-registry-v1.1",
                    "technology_id": "rabbitmq",
                    "capability_id": "realtime.messaging_streaming",
                },
            }],
        }
        diagnostics = build_taxonomy_resolution_diagnostics(stable)
        self.assertEqual(diagnostics["resolved_count"], 1)
        self.assertEqual(diagnostics["unresolved_count"], 0)
        self.assertEqual(diagnostics["rows"][0]["resolution_source"], "technology_registry")
        self.assertEqual(diagnostics["rows"][0]["reason"], "technology_registry_resolved")

    def test_job_match_version_refresh_reuses_saved_jd_profile_without_extractor(self):
        original_db_path = job_match_manager.DB_PATH
        with tempfile.TemporaryDirectory() as tempdir:
            try:
                job_match_manager.DB_PATH = Path(tempdir) / "applications.db"
                job_match_manager.init_job_match_schema()
                context = build_profile_evidence_context([
                    {
                        "id": 1,
                        "category": "Skill",
                        "title": "Python",
                        "description": "Built backend services with Python.",
                        "skills": ["Python"],
                        "tools": [],
                    }
                ])
                job = {
                    "id": 77,
                    "content_hash": "same-job-hash",
                    "description": (
                        "We are hiring a software engineer with Python backend "
                        "experience and RabbitMQ messaging knowledge. The role "
                        "builds production services and collaborates with engineers."
                    ),
                }
                old_versions = {
                    "match_version": "job-match-snapshot-v2.1.0",
                    "scoring_version": "old-scoring",
                    "taxonomy_version": "old-taxonomy",
                }
                analyze_job_match(
                    job,
                    context=context,
                    versions=old_versions,
                    jd_profile_extractor=lambda _text: {
                        "required_skills": ["Python", "RabbitMQ"]
                    },
                    stable_builder=lambda **_kwargs: {
                        "deterministic_alignment_score": 50,
                        "canonical_requirements": [],
                    },
                )

                def fail_extractor(_text):
                    raise AssertionError("JD extractor should have been reused")

                refreshed = analyze_job_match(
                    job,
                    context=context,
                    versions=current_match_versions(),
                    jd_profile_extractor=fail_extractor,
                    stable_builder=lambda **_kwargs: {
                        "deterministic_alignment_score": 50,
                        "technology_registry_version": get_default_registry().version,
                        "canonical_requirements": [],
                    },
                )
                self.assertFalse(refreshed["cache_hit"])
                self.assertEqual(
                    refreshed["snapshot"]["jd_profile"]["required_skills"],
                    ["Python", "RabbitMQ"],
                )
            finally:
                job_match_manager.DB_PATH = original_db_path

    def test_job_match_identity_versions_include_registry_version(self):
        versions = current_match_versions()
        registry_version = get_default_registry().version
        self.assertEqual(versions["technology_registry_version"], registry_version)
        self.assertTrue(versions["match_version"].startswith(MATCH_VERSION))
        self.assertIn(f"|registry={registry_version}", versions["match_version"])


if __name__ == "__main__":
    unittest.main()
