from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

import database.job_match_manager as manager
from database.job_match_manager import (
    list_latest_compatible_job_match_snapshots,
    save_job_match_snapshot,
)
from job_discovery.matching import summarize_stable_match
from tailoring.capability_taxonomy import CapabilityTaxonomy
from taxonomy_discovery.observations import (
    aggregate_unresolved_observations,
    build_discovery_report,
    build_taxonomy_resolution_diagnostics,
    build_unresolved_observations,
)


def _taxonomy() -> CapabilityTaxonomy:
    return CapabilityTaxonomy(
        version="test-taxonomy-v1",
        capabilities=(
            {
                "capability_id": "platform.kubernetes",
                "label": "Kubernetes",
                "domain": "platform",
                "priority": 1,
                "requirement": {
                    "any_terms": ["kubernetes"],
                    "all_terms": [],
                    "all_groups": [],
                },
            },
        ),
    )


def _analysis(rows):
    return {"canonical_requirements": rows}


class TaxonomyDiscoveryObservationTests(unittest.TestCase):
    def test_resolved_match_none_is_not_discovery_observation(self) -> None:
        resolution = build_taxonomy_resolution_diagnostics(
            _analysis(
                [
                    {
                        "requirement_id": "req_k8s",
                        "text": "Experience with Kubernetes",
                        "importance": "required",
                        "match_label": "none",
                        "score_eligible": True,
                    }
                ]
            ),
            taxonomy=_taxonomy(),
        )
        self.assertEqual(resolution["resolved_count"], 1)
        self.assertEqual(resolution["unresolved_count"], 0)
        self.assertEqual(
            build_unresolved_observations(
                resolution,
                discovered_job_id=1,
                job_content_hash="job-a",
            ),
            [],
        )

    def test_unresolved_resolution_is_independent_of_match_label(self) -> None:
        for label in ("none", "weak", "direct"):
            with self.subTest(label=label):
                resolution = build_taxonomy_resolution_diagnostics(
                    _analysis(
                        [
                            {
                                "requirement_id": f"req_cuda_{label}",
                                "text": "Experience optimizing CUDA Graphs",
                                "importance": "required",
                                "match_label": label,
                                "score_eligible": True,
                            }
                        ]
                    ),
                    taxonomy=_taxonomy(),
                )
                self.assertEqual(resolution["resolved_count"], 0)
                self.assertEqual(resolution["unresolved_count"], 1)
                observations = build_unresolved_observations(
                    resolution,
                    discovered_job_id=2,
                    job_content_hash=f"job-{label}",
                )
                self.assertEqual(len(observations), 1)
                self.assertEqual(observations[0]["match_label"], label)

    def test_non_score_eligible_unresolved_row_is_excluded(self) -> None:
        resolution = build_taxonomy_resolution_diagnostics(
            _analysis(
                [
                    {
                        "requirement_id": "req_culture",
                        "text": "Our collaborative company culture",
                        "importance": "required",
                        "match_label": "none",
                        "score_eligible": False,
                    }
                ]
            ),
            taxonomy=_taxonomy(),
        )
        self.assertEqual(resolution["eligible_requirement_count"], 0)
        self.assertEqual(resolution["rows"], [])

    def test_observation_and_candidate_ids_are_stable(self) -> None:
        resolution = build_taxonomy_resolution_diagnostics(
            _analysis(
                [
                    {
                        "requirement_id": "req_cuda",
                        "text": "Experience optimizing CUDA Graphs",
                        "importance": "required",
                        "match_label": "none",
                        "score_eligible": True,
                    }
                ]
            ),
            taxonomy=_taxonomy(),
        )
        first = build_unresolved_observations(
            resolution,
            discovered_job_id=7,
            job_content_hash="same-hash",
        )
        second = build_unresolved_observations(
            resolution,
            discovered_job_id=7,
            job_content_hash="same-hash",
        )
        self.assertEqual(first, second)
        self.assertEqual(
            aggregate_unresolved_observations(first),
            aggregate_unresolved_observations(second),
        )

    def test_exact_normalized_duplicates_aggregate_but_different_phrases_do_not(self) -> None:
        observations = [
            {
                "observation_id": "taxobs_a",
                "discovered_job_id": 1,
                "job_content_hash": "a",
                "requirement_id": "r1",
                "requirement_text": "OpenTelemetry",
                "normalised_observed_text": "opentelemetry",
                "importance": "required",
                "match_label": "none",
                "taxonomy_version": "test-taxonomy-v1",
                "resolution_reason": "no_canonical_capability_resolved",
            },
            {
                "observation_id": "taxobs_b",
                "discovered_job_id": 2,
                "job_content_hash": "b",
                "requirement_id": "r2",
                "requirement_text": "opentelemetry",
                "normalised_observed_text": "opentelemetry",
                "importance": "required",
                "match_label": "none",
                "taxonomy_version": "test-taxonomy-v1",
                "resolution_reason": "no_canonical_capability_resolved",
            },
            {
                "observation_id": "taxobs_c",
                "discovered_job_id": 3,
                "job_content_hash": "c",
                "requirement_id": "r3",
                "requirement_text": "OTel",
                "normalised_observed_text": "otel",
                "importance": "required",
                "match_label": "none",
                "taxonomy_version": "test-taxonomy-v1",
                "resolution_reason": "no_canonical_capability_resolved",
            },
        ]
        candidates = aggregate_unresolved_observations(observations)
        self.assertEqual(len(candidates), 2)
        by_text = {
            item["normalised_observed_text"]: item for item in candidates
        }
        self.assertEqual(by_text["opentelemetry"]["observation_count"], 2)
        self.assertEqual(by_text["opentelemetry"]["job_count"], 2)
        self.assertEqual(by_text["otel"]["observation_count"], 1)

    def test_job_count_is_unique_by_discovered_job(self) -> None:
        base = {
            "job_content_hash": "same",
            "importance": "required",
            "match_label": "none",
            "taxonomy_version": "test-taxonomy-v1",
            "resolution_reason": "no_canonical_capability_resolved",
            "requirement_text": "CUDA Graphs",
            "normalised_observed_text": "cuda graphs",
        }
        candidates = aggregate_unresolved_observations(
            [
                {
                    **base,
                    "observation_id": "a",
                    "discovered_job_id": 9,
                    "requirement_id": "r1",
                },
                {
                    **base,
                    "observation_id": "b",
                    "discovered_job_id": 9,
                    "requirement_id": "r2",
                },
            ]
        )
        self.assertEqual(candidates[0]["observation_count"], 2)
        self.assertEqual(candidates[0]["job_count"], 1)

    def test_existing_all_gaps_semantics_remain_candidate_evidence_gaps(self) -> None:
        summary = summarize_stable_match(
            _analysis(
                [
                    {
                        "requirement_id": "req_k8s",
                        "text": "Experience with Kubernetes",
                        "importance": "required",
                        "match_label": "none",
                        "score_eligible": True,
                    },
                    {
                        "requirement_id": "req_cuda",
                        "text": "Experience optimizing CUDA Graphs",
                        "importance": "required",
                        "match_label": "none",
                        "score_eligible": True,
                    },
                ]
            )
        )
        self.assertEqual(len(summary["all_gaps"]), 2)
        self.assertEqual(
            summary["taxonomy_resolution"]["eligible_requirement_count"],
            2,
        )


class LatestCompatibleSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = manager.DB_PATH
        manager.DB_PATH = Path(self.tempdir.name) / "applications.db"
        manager.init_job_match_schema()

    def tearDown(self) -> None:
        manager.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def _save(
        self,
        *,
        job_id: int,
        evidence_fingerprint: str,
        match_version: str = "job-match-snapshot-v2.1.0",
    ) -> None:
        save_job_match_snapshot(
            discovered_job_id=job_id,
            job_content_hash=f"job-{job_id}",
            evidence_fingerprint=evidence_fingerprint,
            match_version=match_version,
            scoring_version="score-v1",
            taxonomy_version="tax-v1",
            jd_profile={},
            evidence_snapshot=[],
            stable_analysis={"canonical_requirements": []},
            summary={},
        )

    def test_latest_compatible_snapshot_per_job_prevents_double_counting(self) -> None:
        self._save(job_id=1, evidence_fingerprint="old")
        self._save(job_id=1, evidence_fingerprint="new")
        self._save(job_id=2, evidence_fingerprint="only")
        self._save(
            job_id=3,
            evidence_fingerprint="wrong-version",
            match_version="job-match-snapshot-v2.0.1",
        )

        snapshots = list_latest_compatible_job_match_snapshots(
            match_version="job-match-snapshot-v2.1.0",
            scoring_version="score-v1",
            taxonomy_version="tax-v1",
        )
        self.assertEqual(
            [item["discovered_job_id"] for item in snapshots],
            [1, 2],
        )
        by_job = {item["discovered_job_id"]: item for item in snapshots}
        self.assertEqual(by_job[1]["evidence_fingerprint"], "new")

    def test_report_is_deterministic_for_same_snapshots(self) -> None:
        taxonomy = _taxonomy()
        snapshot = {
            "id": 10,
            "discovered_job_id": 5,
            "job_content_hash": "job-5",
            "stable_analysis": _analysis(
                [
                    {
                        "requirement_id": "req_cuda",
                        "text": "CUDA Graphs",
                        "importance": "required",
                        "match_label": "none",
                        "score_eligible": True,
                    }
                ]
            ),
        }
        first = build_discovery_report(
            [snapshot],
            match_version="m",
            scoring_version="s",
            taxonomy_version=taxonomy.version,
            taxonomy=taxonomy,
        )
        second = build_discovery_report(
            [snapshot],
            match_version="m",
            scoring_version="s",
            taxonomy_version=taxonomy.version,
            taxonomy=taxonomy,
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
