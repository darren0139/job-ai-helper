from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database.taxonomy_discovery_review_manager import (
    delete_review,
    get_review,
    list_reviews,
    save_review,
)
from taxonomy_discovery.triage import (
    TRIAGE_VERSION,
    enrich_discovery_report,
)


class TaxonomyDiscoveryTriageTests(unittest.TestCase):
    def _report(self) -> dict:
        return {
            "discovery_version": "capability-taxonomy-discovery-v1",
            "match_version": "job-match-snapshot-v2.1.0",
            "scoring_version": "stable-evidence-v1.7-phase6d12",
            "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
            "candidate_count": 2,
            "candidates": [
                {
                    "candidate_id": "taxcand_fragment",
                    "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
                    "observed_terms": ["Identify, analyze"],
                    "observations": [
                        {
                            "discovered_job_id": 632,
                            "requirement_id": "req_fragment",
                            "requirement_text": "Identify, analyze",
                            "match_label": "none",
                        }
                    ],
                },
                {
                    "candidate_id": "taxcand_react",
                    "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
                    "observed_terms": ["Experience with React"],
                    "observations": [
                        {
                            "discovered_job_id": 632,
                            "requirement_id": "req_react",
                            "requirement_text": "Experience with React",
                            "match_label": "direct",
                        }
                    ],
                },
            ],
        }

    def _snapshots(self) -> list[dict]:
        return [
            {
                "discovered_job_id": 632,
                "stable_analysis": {
                    "canonical_requirements": [
                        {
                            "requirement_id": "req_fragment",
                            "text": "Identify, analyze",
                            "parent_text": (
                                "Identify, analyze, and resolve coding bugs "
                                "in a timely manner"
                            ),
                            "is_atomic": True,
                            "atomic_group_id": "grp_bug",
                            "group_weight_fraction": 0.5,
                            "semantic_type": "role_responsibility",
                            "eligibility_rule": "eligible_role_responsibility",
                            "match_label": "none",
                            "capability_taxonomy_cap_status": "unrecognised",
                            "capability_retrieval": {
                                "status": "no_candidates",
                                "shadow_only": True,
                                "influences_scoring": False,
                                "candidates": [],
                            },
                        },
                        {
                            "requirement_id": "req_fragment_sibling",
                            "text": "resolve coding bugs in a timely manner",
                            "parent_text": (
                                "Identify, analyze, and resolve coding bugs "
                                "in a timely manner"
                            ),
                            "is_atomic": True,
                            "atomic_group_id": "grp_bug",
                            "group_weight_fraction": 0.5,
                            "semantic_type": "role_responsibility",
                            "eligibility_rule": "eligible_role_responsibility",
                            "match_label": "none",
                        },
                        {
                            "requirement_id": "req_react",
                            "text": "Experience with React",
                            "parent_text": "Experience with React",
                            "is_atomic": False,
                            "semantic_type": "candidate_requirement",
                            "eligibility_rule": "eligible_candidate_requirement",
                            "match_label": "direct",
                            "capability_taxonomy_cap_status": "unrecognised",
                            "capability_retrieval": {
                                "status": "candidates_retrieved",
                                "shadow_only": True,
                                "influences_scoring": False,
                                "candidates": [
                                    {
                                        "capability_id": "frontend.ui_development",
                                        "lexical_score": 0.75,
                                        "retrieval_sources": ["lexical"],
                                    }
                                ],
                            },
                        },
                    ]
                },
            }
        ]

    def test_enrichment_preserves_human_decision_boundary(self) -> None:
        enriched = enrich_discovery_report(
            self._report(),
            self._snapshots(),
            reviews=[],
        )
        self.assertEqual(enriched["triage_version"], TRIAGE_VERSION)
        self.assertEqual(enriched["unreviewed_candidate_count"], 2)

        fragment = enriched["candidates"][0]
        self.assertEqual(fragment["triage"]["status"], "unreviewed")
        self.assertIn("atomic_child", fragment["diagnostic_flags"])
        self.assertIn(
            "atomic_parent_context_available",
            fragment["diagnostic_flags"],
        )
        self.assertIn(
            "atomic_siblings_present",
            fragment["diagnostic_flags"],
        )
        self.assertNotIn(
            "research_candidate",
            fragment["diagnostic_flags"],
        )

        react = enriched["candidates"][1]
        self.assertIn(
            "candidate_match_direct",
            react["diagnostic_flags"],
        )
        self.assertIn(
            "retrieval_candidates_present",
            react["diagnostic_flags"],
        )
        top = react["observation_contexts"][0]["retrieval"][
            "top_candidate"
        ]
        self.assertEqual(
            top["capability_id"],
            "frontend.ui_development",
        )

    def test_review_persistence_is_keyed_by_candidate_and_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "reviews.sqlite3"
            saved = save_review(
                candidate_id="taxcand_react",
                taxonomy_version="phase6d-capability-taxonomy-v1.4",
                triage_status="existing_taxonomy_near_miss",
                target_capability_id="frontend.ui_development",
                notes="React maps to the existing frontend concept.",
                db_path=db_path,
            )
            self.assertEqual(
                saved["triage_status"],
                "existing_taxonomy_near_miss",
            )
            self.assertEqual(
                saved["target_capability_id"],
                "frontend.ui_development",
            )

            self.assertIsNone(
                get_review(
                    "taxcand_react",
                    "phase6d-capability-taxonomy-v1.5",
                    db_path=db_path,
                )
            )
            self.assertEqual(
                len(
                    list_reviews(
                        taxonomy_version=(
                            "phase6d-capability-taxonomy-v1.4"
                        ),
                        db_path=db_path,
                    )
                ),
                1,
            )

            self.assertTrue(
                delete_review(
                    "taxcand_react",
                    "phase6d-capability-taxonomy-v1.4",
                    db_path=db_path,
                )
            )
            self.assertEqual(list_reviews(db_path=db_path), [])

    def test_existing_taxonomy_near_miss_requires_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save_review(
                    candidate_id="taxcand_react",
                    taxonomy_version="phase6d-capability-taxonomy-v1.4",
                    triage_status="existing_taxonomy_near_miss",
                    db_path=Path(tmp) / "reviews.sqlite3",
                )


if __name__ == "__main__":
    unittest.main()
