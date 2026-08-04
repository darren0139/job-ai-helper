from __future__ import annotations

import copy
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from tailoring.phase9c_blueprint_evaluation import (
    Phase9CEvaluationError,
    aggregate_portability_metrics,
    evaluate_blueprint_candidate,
    fingerprint_semantic_identity,
    source_requirement_summary_fingerprint,
)


FIXTURE = Path(__file__).resolve().parents[1] / "ci_fixtures" / (
    "phase9c_application94_acceptance.json"
)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class Phase9CBlueprintEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = load_fixture()
        self.candidate = self.fixture["candidate"]
        self.jds = self.fixture["saved_jds"]
        self.source = self.jds[0]
        self.target = self.jds[1]

    def evaluate(self, selected=None, **kwargs):
        return evaluate_blueprint_candidate(
            candidate=copy.deepcopy(self.candidate),
            selected_jds=copy.deepcopy(selected or [self.source, self.target]),
            saved_jds_for_source_resolution=copy.deepcopy(self.jds),
            **kwargs,
        )

    def test_application94_source_parity_and_full_snapshot_sections(self):
        result = self.evaluate()
        source = next(row for row in result["per_jd_results"] if row["is_source_jd"])
        self.assertEqual(source["deterministic_alignment_score"], 92)
        self.assertTrue(source["source_jd_parity"]["accepted"])
        target = next(row for row in result["per_jd_results"] if not row["is_source_jd"])
        counts = target["evidence_sections_considered"]
        for section in ("education", "experience", "projects", "skills"):
            self.assertGreater(counts[section], 0, section)
        self.assertEqual(target["evaluation_mode"], "full_frozen_snapshot")
        self.assertEqual(result["candidate_scope"]["scoring_version"], SCORING_VERSION)

    def test_candidate_fail_closed_gates(self):
        mutations = (
            lambda row: row.pop("resume_profile_snapshot"),
            lambda row: row.pop("resume_text_snapshot"),
            lambda row: row.update(status="archived"),
            lambda row: row.update(phase9b_version="phase9b-blueprint-candidate-v2"),
            lambda row: row["claim_lineage"].update(claim_review_required_count=1),
            lambda row: row["evaluation_metadata"].update(
                source_scoring_version="future-scorer"
            ),
            lambda row: row["evaluation_metadata"].update(
                capability_taxonomy_version="future-taxonomy"
            ),
        )
        for mutation in mutations:
            candidate = copy.deepcopy(self.candidate)
            mutation(candidate)
            with self.subTest(candidate=candidate):
                with self.assertRaises(Phase9CEvaluationError):
                    evaluate_blueprint_candidate(
                        candidate=candidate,
                        selected_jds=[copy.deepcopy(self.source)],
                        saved_jds_for_source_resolution=copy.deepcopy(self.jds),
                    )

    def test_different_family_is_recorded_and_excluded(self):
        result = self.evaluate([self.source, self.fixture["different_family_jd"]])
        self.assertEqual(len(result["per_jd_results"]), 1)
        excluded = result["excluded_jds"]
        self.assertEqual(excluded[0]["family_match_status"], "different")
        self.assertEqual(excluded[0]["selection_reason"], "different_role_family")

    def test_uncertain_family_requires_explicit_inclusion(self):
        uncertain = self.fixture["uncertain_family_jd"]
        without = self.evaluate([self.source, uncertain])
        self.assertEqual(len(without["per_jd_results"]), 1)
        uncertain_key = next(
            row["jd_key"]
            for row in without["selected_jd_scope"]
            if row["family_match_status"] == "uncertain"
        )
        included = self.evaluate(
            [self.source, uncertain],
            explicitly_allowed_uncertain=[uncertain_key],
        )
        self.assertEqual(len(included["per_jd_results"]), 2)

    def test_one_is_provisional_and_two_are_not(self):
        self.assertTrue(self.evaluate([self.source])["aggregate_result"]["provisional"])
        self.assertFalse(self.evaluate()["aggregate_result"]["provisional"])

    def test_selection_order_does_not_change_fingerprint_or_result_order(self):
        first = self.evaluate([self.source, self.target])
        second = self.evaluate([self.target, self.source])
        self.assertEqual(
            first["evaluation_fingerprint"], second["evaluation_fingerprint"]
        )
        self.assertEqual(first["per_jd_results"], second["per_jd_results"])

    def test_identical_stable_input_produces_identical_evaluation_fingerprint(self):
        first = self.evaluate()
        second = self.evaluate()
        self.assertEqual(
            first["evaluation_fingerprint"], second["evaluation_fingerprint"]
        )
        self.assertEqual(
            [
                row["stable_input_fingerprint"]
                for row in first["semantic_identity"]["selected_jd_scope"]
            ],
            [
                row["stable_input_fingerprint"]
                for row in second["semantic_identity"]["selected_jd_scope"]
            ],
        )

    def test_excluded_jd_changes_complete_scope_fingerprint(self):
        source_only = self.evaluate([self.source])
        with_excluded = self.evaluate(
            [self.source, self.fixture["different_family_jd"]]
        )
        self.assertNotEqual(
            source_only["evaluation_fingerprint"],
            with_excluded["evaluation_fingerprint"],
        )
        self.assertEqual(
            with_excluded["excluded_jds"][0]["selection_decision"],
            "excluded",
        )

    def test_semantic_scope_and_per_jd_share_stable_input_fingerprint(self):
        result = self.evaluate()
        semantic_by_jd = {
            row["jd_key"]: row["stable_input_fingerprint"]
            for row in result["semantic_identity"]["selected_jd_scope"]
        }
        self.assertTrue(semantic_by_jd)
        for row in result["per_jd_results"]:
            self.assertEqual(
                row["stable_input_fingerprint"],
                semantic_by_jd[row["jd_key"]],
            )

    def test_stable_input_fingerprint_change_invalidates_evaluation_fingerprint(self):
        target = (
            "tailoring.phase9c_blueprint_evaluation."
            "_stable_input_fingerprint"
        )
        with patch(target, return_value="stable-input-a"):
            first = self.evaluate([self.source])
        with patch(target, return_value="stable-input-b"):
            second = self.evaluate([self.source])

        first_identity = copy.deepcopy(first["semantic_identity"])
        second_identity = copy.deepcopy(second["semantic_identity"])
        self.assertEqual(
            first_identity["selected_jd_scope"][0][
                "stable_input_fingerprint"
            ],
            "stable-input-a",
        )
        self.assertEqual(
            second_identity["selected_jd_scope"][0][
                "stable_input_fingerprint"
            ],
            "stable-input-b",
        )
        for identity in (first_identity, second_identity):
            identity["selected_jd_scope"][0].pop(
                "stable_input_fingerprint"
            )
        self.assertEqual(first_identity, second_identity)
        self.assertNotEqual(
            first["evaluation_fingerprint"],
            second["evaluation_fingerprint"],
        )

    def test_fingerprint_includes_versions_candidate_and_source_seed(self):
        result = self.evaluate()
        identity = result["semantic_identity"]
        variants = []
        for path, value in (
            (("candidate", "scoring_version"), "future-scorer"),
            (("candidate", "candidate_fingerprint"), "different-candidate"),
            (
                ("candidate", "source_jd_requirement_summary_fingerprint"),
                "different-seed",
            ),
        ):
            variant = copy.deepcopy(identity)
            variant[path[0]][path[1]] = value
            variants.append(variant)
        base = fingerprint_semantic_identity(identity)
        self.assertTrue(
            all(fingerprint_semantic_identity(value) != base for value in variants)
        )
        self.assertEqual(
            identity["candidate"]["source_jd_requirement_summary_fingerprint"],
            source_requirement_summary_fingerprint(self.candidate),
        )

    def test_source_identity_mismatch_and_ambiguity_fail_closed(self):
        mutations = (
            lambda row: row.update(canonical_jd_id="different-canonical-jd"),
            lambda row: row.update(source_version_id="different-version"),
            lambda row: row.update(raw_text="different raw JD"),
            lambda row: row.update(application_id=999, application_ids=[999]),
        )
        for mutation in mutations:
            mismatch = copy.deepcopy(self.jds)
            mutation(mismatch[0])
            with self.subTest(source=mismatch[0]):
                with self.assertRaises(Phase9CEvaluationError):
                    evaluate_blueprint_candidate(
                        candidate=copy.deepcopy(self.candidate),
                        selected_jds=[copy.deepcopy(mismatch[0])],
                        saved_jds_for_source_resolution=mismatch,
                    )
        candidate_ids = copy.deepcopy(self.candidate)
        candidate_ids["canonical_requirement_ids"] = ["different-requirement"]
        with self.assertRaises(Phase9CEvaluationError):
            evaluate_blueprint_candidate(
                candidate=candidate_ids,
                selected_jds=[copy.deepcopy(self.source)],
                saved_jds_for_source_resolution=copy.deepcopy(self.jds),
            )
        duplicate = copy.deepcopy(self.source)
        duplicate["id"] = 9402
        with self.assertRaisesRegex(Phase9CEvaluationError, "ambiguous"):
            evaluate_blueprint_candidate(
                candidate=copy.deepcopy(self.candidate),
                selected_jds=[copy.deepcopy(self.source)],
                saved_jds_for_source_resolution=[self.source, duplicate, self.target],
            )

    def test_vector_and_hybrid_environment_cannot_trigger_embeddings(self):
        for mode in ("vector", "hybrid"):
            with self.subTest(mode=mode), patch.dict(
                os.environ, {"CAPABILITY_RAG_MODE": mode}
            ), patch(
                "tailoring.phase6d5_retrieval.retrieve_taxonomy_candidates",
                side_effect=AssertionError("embedding/vector retrieval attempted"),
            ) as retrieve:
                result = self.evaluate()
                self.assertGreater(result["aggregate_result"]["mean_score"], 60)
                retrieve.assert_not_called()

    def test_model_call_surfaces_are_never_used(self):
        sentinel = types.ModuleType("llm")
        sentinel.call_model = Mock(side_effect=AssertionError("model call attempted"))
        sentinel.generate = Mock(side_effect=AssertionError("model call attempted"))
        with patch.dict(sys.modules, {"llm": sentinel}):
            result = self.evaluate()
            self.assertEqual(
                result["semantic_identity"]["policy"]["model_calls"], 0
            )
            sentinel.call_model.assert_not_called()
            sentinel.generate.assert_not_called()

    def test_chroma_read_write_and_index_functions_are_never_called(self):
        sentinel = types.ModuleType("rag.jd_chroma_rag")
        sentinel._get_chroma_client = Mock(side_effect=AssertionError("Chroma read"))
        sentinel.index_job_description_to_chroma = Mock(
            side_effect=AssertionError("Chroma index")
        )
        sentinel.rebuild_chroma_index = Mock(
            side_effect=AssertionError("Chroma write")
        )
        with patch.dict(sys.modules, {"rag.jd_chroma_rag": sentinel}):
            result = self.evaluate()
            self.assertEqual(result["mutation_policy"]["saved_jds_mutated"], False)
            for mock in (
                sentinel._get_chroma_client,
                sentinel.index_job_description_to_chroma,
                sentinel.rebuild_chroma_index,
            ):
                mock.assert_not_called()

    def test_candidate_and_saved_jd_inputs_are_not_mutated(self):
        candidate = copy.deepcopy(self.candidate)
        jds = copy.deepcopy([self.source, self.target])
        before_candidate = copy.deepcopy(candidate)
        before_jds = copy.deepcopy(jds)
        evaluate_blueprint_candidate(
            candidate=candidate,
            selected_jds=jds,
            saved_jds_for_source_resolution=copy.deepcopy(self.jds),
        )
        self.assertEqual(candidate, before_candidate)
        self.assertEqual(jds, before_jds)

    def test_recurring_gaps_and_outliers_are_deterministic(self):
        rows = [
            {
                "jd_key": "a",
                "deterministic_alignment_score": 90,
                "required_core_coverage_score": 90,
                "preferred_coverage_score": 80,
                "evidence_strength_score": 90,
                "important_gaps": [{"requirement_id": "r1", "text": "Kubernetes"}],
            },
            {
                "jd_key": "b",
                "deterministic_alignment_score": 80,
                "required_core_coverage_score": 85,
                "preferred_coverage_score": 70,
                "evidence_strength_score": 80,
                "important_gaps": [{"requirement_id": "r2", "text": "Kubernetes"}],
            },
            {
                "jd_key": "c",
                "deterministic_alignment_score": 35,
                "required_core_coverage_score": 40,
                "preferred_coverage_score": 20,
                "evidence_strength_score": 50,
                "important_gaps": [{"requirement_id": "r3", "text": "Kubernetes"}],
            },
        ]
        first = aggregate_portability_metrics(rows, source_required_core_score=90)
        second = aggregate_portability_metrics(copy.deepcopy(rows), source_required_core_score=90)
        self.assertEqual(first, second)
        self.assertEqual(first["recurring_important_gaps"][0]["count"], 3)
        self.assertEqual(first["outlier_jds"][0]["jd_key"], "c")


if __name__ == "__main__":
    unittest.main()
