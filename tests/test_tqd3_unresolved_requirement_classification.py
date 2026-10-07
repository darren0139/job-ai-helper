from __future__ import annotations

import copy
import unittest

from taxonomy_discovery.classification import (
    CLASS_A,
    CLASS_B,
    CLASS_D,
    CLASS_E,
    CLASS_U,
    CLASSIFICATION_VERSION,
    build_classification_report,
    classify_unresolved_candidate,
)


def _context(
    *,
    explicit_only: bool = False,
    candidates: list[tuple[str, float]] | None = None,
) -> dict:
    rows = [
        {
            "capability_id": capability_id,
            "lexical_score": score,
            "vector_distance": None,
            "retrieval_sources": ["lexical"],
        }
        for capability_id, score in (candidates or [])
    ]
    return {
        "context_available": True,
        "parent_text": "",
        "is_atomic": False,
        "atomic_group_id": "",
        "group_weight_fraction": 1.0,
        "semantic_type": "candidate_requirement",
        "eligibility_rule": "eligible_candidate_requirement",
        "explicit_only_requirement": explicit_only,
        "scoring_parent_occurrence_id": "srcgrp_1",
        "taxonomy_cap_status": "unrecognised",
        "capability_id": None,
        "retrieval": {
            "status": "candidates_retrieved" if rows else "no_candidates",
            "requested_mode": "lexical",
            "effective_mode": "lexical",
            "exact_capability_id": None,
            "lexical_top_score": rows[0]["lexical_score"] if rows else 0.0,
            "shadow_only": True,
            "influences_scoring": False,
            "top_candidate": rows[0] if rows else None,
            "candidates": rows,
        },
        "atomic_siblings": [],
    }


def _candidate(
    text: str,
    *,
    candidate_id: str = "taxcand_1",
    job_count: int = 1,
    observation_count: int = 1,
    context: dict | None = None,
    registry_status: str = "unresolved",
    technology_id: str | None = None,
    capability_id: str | None = None,
    flags: list[str] | None = None,
) -> dict:
    return {
        "candidate_id": candidate_id,
        "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
        "normalised_observed_text": text.lower(),
        "observed_terms": [text],
        "observation_count": observation_count,
        "job_count": job_count,
        "discovered_job_ids": list(range(1, job_count + 1)),
        "observations": [
            {
                "observation_id": f"obs_{index}",
                "discovered_job_id": index + 1,
                "requirement_id": f"req_{index}",
                "requirement_text": text,
                "normalised_observed_text": text.lower(),
                "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
                "match_label": "none",
            }
            for index in range(observation_count)
        ],
        "diagnostic_flags": list(flags or []),
        "observation_contexts": [context or _context()],
        "technology_registry_resolution": {
            "status": registry_status,
            "registry_version": "technology-registry-v1.1",
            "technology_id": technology_id,
            "capability_id": capability_id,
        },
    }


class TQD3ClassificationTests(unittest.TestCase):
    def test_version_is_explicit(self) -> None:
        self.assertEqual(
            CLASSIFICATION_VERSION,
            "tqd3-unresolved-requirement-classification-v1.0.0",
        )

    def test_known_registry_aliases_route_to_b(self) -> None:
        result = classify_unresolved_candidate(
            _candidate("comfortable using AngularJS, NodeJS, ReactJS")
        )
        self.assertEqual(result["class_id"], CLASS_B)
        technology_ids = {
            row["technology_id"]
            for row in result["signals"]["registry_alias_mentions"]
        }
        self.assertTrue({"angular", "node.js", "react"} <= technology_ids)
        self.assertFalse(result["influences_scoring"])

    def test_recognized_unmapped_routes_to_b_and_research(self) -> None:
        result = classify_unresolved_candidate(
            _candidate(
                "Experience with Keycloak",
                registry_status="recognized_unmapped",
                technology_id="keycloak",
            )
        )
        self.assertEqual(result["class_id"], CLASS_B)
        self.assertTrue(result["research_eligible"])

    def test_explicit_only_routes_to_d(self) -> None:
        result = classify_unresolved_candidate(
            _candidate(
                "Candidates with critical thinking skills",
                context=_context(explicit_only=True),
            )
        )
        self.assertEqual(result["class_id"], CLASS_D)
        self.assertEqual(result["rule_id"], "explicit_only_requirement")

    def test_general_learning_wording_routes_to_d(self) -> None:
        result = classify_unresolved_candidate(
            _candidate("Ability to learn new software and technologies quickly")
        )
        self.assertEqual(result["class_id"], CLASS_D)

    def test_strong_unambiguous_shadow_retrieval_routes_to_a(self) -> None:
        result = classify_unresolved_candidate(
            _candidate(
                "Coordinate delivery with engineering stakeholders",
                context=_context(
                    candidates=[
                        ("collaboration.cross_functional", 0.55),
                        ("delivery.end_to_end_application", 0.30),
                    ]
                ),
            )
        )
        self.assertEqual(result["class_id"], CLASS_A)
        self.assertEqual(
            result["signals"]["near_miss"]["capability_id"],
            "collaboration.cross_functional",
        )

    def test_strong_tie_fails_closed_to_u(self) -> None:
        result = classify_unresolved_candidate(
            _candidate(
                "Analyze and troubleshoot software issues",
                context=_context(
                    candidates=[
                        ("delivery.end_to_end_application", 0.40),
                        ("quality.qa_testing", 0.40),
                    ]
                ),
            )
        )
        self.assertEqual(result["class_id"], CLASS_U)
        self.assertIsNone(result["signals"]["near_miss"])

    def test_recurrent_persistent_unresolved_routes_to_e(self) -> None:
        result = classify_unresolved_candidate(
            _candidate(
                "Generate technical documentation and operational reports",
                job_count=3,
                observation_count=3,
            )
        )
        self.assertEqual(result["class_id"], CLASS_E)
        self.assertTrue(result["research_eligible"])
        self.assertTrue(result["requires_human_review"])
        self.assertFalse(result["mutates_taxonomy"])
        self.assertFalse(result["mutates_registry"])

    def test_report_skips_registry_resolved_and_is_order_stable(self) -> None:
        resolved = _candidate(
            "RabbitMQ",
            candidate_id="taxcand_resolved",
            registry_status="resolved",
            technology_id="rabbitmq",
            capability_id="realtime.messaging_streaming",
        )
        unresolved = _candidate(
            "Generate technical documentation and operational reports",
            candidate_id="taxcand_unresolved",
        )
        source = {
            "discovery_version": "capability-taxonomy-discovery-v1",
            "triage_version": "capability-taxonomy-discovery-triage-v1",
            "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
            "candidates": [resolved, unresolved],
        }
        original = copy.deepcopy(source)
        first = build_classification_report(source)
        second = build_classification_report(
            {**source, "candidates": list(reversed(source["candidates"]))}
        )
        self.assertEqual(source, original)
        self.assertEqual(first, second)
        self.assertEqual(first["input_candidate_count"], 2)
        self.assertEqual(first["persistent_unresolved_candidate_count"], 1)
        self.assertEqual(first["skipped_registry_resolved_count"], 1)
        self.assertEqual(
            first["governance"],
            {
                "model_calls": 0,
                "network_calls": 0,
                "taxonomy_mutations": 0,
                "registry_mutations": 0,
                "scoring_influence": False,
                "human_approval_required": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
