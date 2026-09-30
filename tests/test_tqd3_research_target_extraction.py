from __future__ import annotations

import copy
import unittest

from taxonomy_discovery.classification import (
    CLASS_B,
    CLASS_D,
    CLASS_E,
)
from taxonomy_discovery.research_targets import (
    RESEARCH_TARGET_VERSION,
    TARGET_CAPABILITY_CONCEPT,
    TARGET_TECHNOLOGY_IDENTITY,
    TARGET_TECHNOLOGY_RELATIONSHIP,
    build_research_target_report,
    extract_research_targets_for_candidate,
)


def _candidate(
    text: str,
    *,
    class_id: str,
    candidate_id: str = "taxcand_1",
    alias_mentions: list[dict] | None = None,
    job_count: int = 1,
    observation_count: int = 1,
) -> dict:
    return {
        "candidate_id": candidate_id,
        "normalised_observed_text": text.lower(),
        "observed_terms": [text],
        "job_count": job_count,
        "observation_count": observation_count,
        "tqd3_classification": {
            "class_id": class_id,
            "signals": {
                "registry_alias_mentions": list(alias_mentions or []),
            },
        },
    }


class TQD3ResearchTargetExtractionTests(unittest.TestCase):
    def test_version_is_explicit(self) -> None:
        self.assertEqual(
            RESEARCH_TARGET_VERSION,
            "tqd3-research-target-extraction-v1.2.0",
        )

    def test_known_unmapped_csharp_becomes_relationship_target(self) -> None:
        candidate = _candidate(
            "Basic programming experience with knowledge of C#, Java, "
            "Javascript, HTML5 and Python is preferred",
            class_id=CLASS_B,
            alias_mentions=[
                {
                    "technology_id": "csharp",
                    "technology_label": "C#",
                    "alias": "C#",
                    "mapping_status": "recognized_unmapped",
                    "capability_id": None,
                }
            ],
        )
        rows = extract_research_targets_for_candidate(candidate)
        relationships = [
            row
            for row in rows
            if row["target_type"] == TARGET_TECHNOLOGY_RELATIONSHIP
        ]
        self.assertEqual(
            [row["target_key"] for row in relationships],
            ["csharp"],
        )

    def test_mapped_angular_and_react_are_excluded_but_node_is_targeted(self) -> None:
        candidate = _candidate(
            "comfortable using AngularJS, NodeJS, ReactJS and other common "
            "frameworks is an advantage",
            class_id=CLASS_B,
            alias_mentions=[
                {
                    "technology_id": "angular",
                    "technology_label": "Angular",
                    "alias": "AngularJS",
                    "mapping_status": "mapped",
                    "capability_id": "frontend.ui_development",
                },
                {
                    "technology_id": "node.js",
                    "technology_label": "Node.js",
                    "alias": "NodeJS",
                    "mapping_status": "recognized_unmapped",
                    "capability_id": None,
                },
                {
                    "technology_id": "react",
                    "technology_label": "React",
                    "alias": "ReactJS",
                    "mapping_status": "mapped",
                    "capability_id": "frontend.ui_development",
                },
            ],
        )
        rows = extract_research_targets_for_candidate(candidate)
        relationship_keys = [
            row["target_key"]
            for row in rows
            if row["target_type"] == TARGET_TECHNOLOGY_RELATIONSHIP
        ]
        self.assertEqual(relationship_keys, ["node.js"])
        self.assertNotIn("angular", relationship_keys)
        self.assertNotIn("react", relationship_keys)

    def test_sql_nosql_u_candidate_yields_identity_targets(self) -> None:
        candidate = _candidate(
            "Knowledge of databases (SQL / NoSQL) is an advantage",
            class_id="U_unclassified",
        )
        rows = extract_research_targets_for_candidate(candidate)
        identity_labels = {
            row["label"]
            for row in rows
            if row["target_type"] == TARGET_TECHNOLOGY_IDENTITY
        }
        self.assertEqual(identity_labels, {"SQL", "NoSQL"})

    def test_subjective_d_candidate_produces_no_targets(self) -> None:
        candidate = _candidate(
            "Ability to learn new software and technologies quickly",
            class_id=CLASS_D,
        )
        self.assertEqual(
            extract_research_targets_for_candidate(candidate),
            [],
        )

    def test_e_candidate_becomes_capability_concept_target(self) -> None:
        candidate = _candidate(
            "Generate technical documentation and operational reports",
            class_id=CLASS_E,
            job_count=3,
            observation_count=3,
        )
        rows = extract_research_targets_for_candidate(candidate)
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["target_type"],
            TARGET_CAPABILITY_CONCEPT,
        )

    def test_report_aggregates_same_target_stably(self) -> None:
        first = _candidate(
            "Experience with C#",
            class_id=CLASS_B,
            candidate_id="taxcand_b",
            alias_mentions=[
                {
                    "technology_id": "csharp",
                    "technology_label": "C#",
                    "alias": "C#",
                    "mapping_status": "recognized_unmapped",
                    "capability_id": None,
                }
            ],
        )
        second = _candidate(
            "Knowledge of C#",
            class_id=CLASS_B,
            candidate_id="taxcand_a",
            alias_mentions=[
                {
                    "technology_id": "csharp",
                    "technology_label": "C#",
                    "alias": "C#",
                    "mapping_status": "recognized_unmapped",
                    "capability_id": None,
                }
            ],
        )
        source = {
            "classification_version": (
                "tqd3-unresolved-requirement-classification-v1.0.0"
            ),
            "candidates": [first, second],
        }
        original = copy.deepcopy(source)
        a = build_research_target_report(source)
        b = build_research_target_report(
            {
                **source,
                "candidates": list(reversed(source["candidates"])),
            }
        )
        self.assertEqual(source, original)
        self.assertEqual(a, b)
        csharp = next(
            row
            for row in a["targets"]
            if row["target_key"] == "csharp"
            and row["target_type"] == TARGET_TECHNOLOGY_RELATIONSHIP
        )
        self.assertEqual(
            csharp["source_candidate_ids"],
            ["taxcand_a", "taxcand_b"],
        )

    def test_governance_is_zero_call_and_non_mutating(self) -> None:
        report = build_research_target_report(
            {
                "classification_version": (
                    "tqd3-unresolved-requirement-classification-v1.0.0"
                ),
                "candidates": [],
            }
        )
        self.assertEqual(
            report["governance"],
            {
                "tavily_calls": 0,
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
