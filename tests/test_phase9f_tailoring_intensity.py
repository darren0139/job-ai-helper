from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tailoring.phase9f_starting_source_ranking import (
    PHASE9F_B_VERSION,
    PHASE9F_B_RANKING_POLICY_VERSION,
    build_comparison_result_identity,
    build_ranking_result_identity,
    fingerprint_value,
    rank_starting_resume_sources,
)
from tailoring.phase9f_exact_verified_reuse import (
    PHASE9F_BLUEPRINT_ARTIFACT_POLICY_VERSION,
    build_exact_verified_reuse_proof,
)
from tailoring.phase9f_tailoring_intensity import (
    PHASE9F_C_POLICY_VERSION,
    PHASE9F_C_VERSION,
    recommend_tailoring_intensity,
    tailoring_intensity_policy_identity,
)
from tests.test_phase9f_starting_source_ranking import (
    make_base,
    make_blueprint,
    make_exact_jd,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN = REPO_ROOT / "ci_fixtures" / (
    "phase9f_tailoring_intensity_golden.json"
)


def make_phase9f_b_result(
    *,
    name: str,
    overall: int,
    required_core: int,
    preferred: int,
    evidence: int,
    important_requirement_count: int,
    important_gap_count: int,
    deal_breaker_gap_count: int,
    preferred_requirement_count: int = 0,
    source_type: str = "global_blueprint",
    role_family_relationship: str = "same_family",
    role_family_confidence: str = "high",
    display_name: str = "Synthetic Winner",
) -> dict:
    outcomes = []
    core_required_gap_count = (
        important_gap_count - deal_breaker_gap_count
    )
    for index in range(important_requirement_count):
        is_gap = index < core_required_gap_count
        outcomes.append(
            {
                "requirement_id": f"req_{name}_important_{index:02d}",
                "importance": "required" if index % 2 == 0 else "core",
                "match_label": "none" if is_gap else "direct",
                "evidence_strength": 0 if is_gap else 5,
            }
        )
    for index in range(deal_breaker_gap_count):
        outcomes.append(
            {
                "requirement_id": f"req_{name}_deal_breaker_{index:02d}",
                "importance": "deal_breaker",
                "match_label": "none",
                "evidence_strength": 0,
            }
        )
    for index in range(preferred_requirement_count):
        outcomes.append(
            {
                "requirement_id": f"req_{name}_preferred_{index:02d}",
                "importance": "preferred",
                "match_label": "direct",
                "evidence_strength": 5,
            }
        )
    important_gaps = [
        {
            "requirement_id": row["requirement_id"],
            "text": f"Requirement {row['requirement_id']}",
            "importance": row["importance"],
        }
        for row in outcomes
        if row["importance"] in {"deal_breaker", "required", "core"}
        and row["match_label"] == "none"
    ]
    scope_fingerprint = fingerprint_value(
        {"scope": name, "ids": sorted(row["requirement_id"] for row in outcomes)}
    )
    comparison_identity = build_comparison_result_identity(
        canonical_requirement_results=outcomes,
        deterministic_alignment_score=overall,
        required_core_coverage_score=required_core,
        preferred_coverage_score=preferred,
        evidence_strength_score=evidence,
        important_gaps=important_gaps,
    )
    normalized_source_fingerprint = fingerprint_value(
        {"source": name, "source_type": source_type}
    )
    candidate = {
        "rank": 1,
        "source_type": source_type,
        "source_id": f"source-{name}",
        "source_version": 1,
        "source_fingerprint": f"source-fingerprint-{name}",
        "source_content_fingerprint": f"content-fingerprint-{name}",
        "normalized_source_fingerprint": normalized_source_fingerprint,
        "source_display_name": display_name,
        "source_role_family_id": "synthetic_family",
        "source_role_family_label": "Synthetic Family",
        "role_family_relationship": role_family_relationship,
        "role_family_prior_eligible": bool(
            role_family_relationship == "same_family"
            and role_family_confidence in {"medium", "high"}
        ),
        "role_family_prior_applied": False,
        "ranking_reason": "best_canonical_metrics",
        "current_jd_alignment": overall,
        "deterministic_alignment_score": overall,
        "required_core_coverage_score": required_core,
        "preferred_coverage_score": preferred,
        "evidence_strength_score": evidence,
        "important_gap_count": important_gap_count,
        "deal_breaker_gap_count": deal_breaker_gap_count,
        "important_gaps": important_gaps,
        "canonical_requirement_results": outcomes,
        "canonical_requirement_scope_fingerprint": scope_fingerprint,
        "stable_input_fingerprint": fingerprint_value(
            {"stable_input": name}
        ),
        "comparison_result_fingerprint": fingerprint_value(
            comparison_identity
        ),
        "scoring_version": "stable-evidence-v1.3-phase6d7",
        "capability_taxonomy_version": "capability-taxonomy-v1",
        "evidence_policy_version": "phase9f-phase9c-fresh-target-evidence-v1",
        "exact_verified_reuse_eligible": False,
        "exact_verified_reuse_reason_code": "exact_verified_reuse_proof_missing",
        "exact_verified_reuse_proof_fingerprint": "",
        "exact_verified_reuse": {
            "proof_version": "phase9f-exact-verified-reuse-proof-v1",
            "eligible": False,
            "reason_code": "exact_verified_reuse_proof_missing",
            "blueprint_id": "",
            "blueprint_fingerprint": "",
            "proof_fingerprint": "",
        },
    }
    exact_jd = {
        "raw_jd_sha256": fingerprint_value({"raw_jd": name}),
        "structured_profile_fingerprint": fingerprint_value(
            {"jd_profile": name}
        ),
        "canonical_requirement_fingerprint": scope_fingerprint,
        "canonical_requirement_ids": sorted(
            row["requirement_id"] for row in outcomes
        ),
        "role_family": {
            "role_family_id": "synthetic_family",
            "confidence": role_family_confidence,
            "classifier_version": "phase9b-role-family-v1",
        },
    }
    semantic_identity = {
        "format_version": PHASE9F_B_VERSION,
        "source_normalization_policy_version": (
            "phase9f-immutable-starting-source-v1"
        ),
        "exact_jd": exact_jd,
        "scoring": {
            "scoring_policy_version": (
                "phase9f-phase9c-fresh-target-scoring-v1"
            ),
            "scoring_version": "stable-evidence-v1.3-phase6d7",
            "capability_taxonomy_version": "capability-taxonomy-v1",
            "evidence_policy_version": (
                "phase9f-phase9c-fresh-target-evidence-v1"
            ),
            "retrieval_mode": "lexical",
            "fresh_target_only": True,
        },
        "source_scope": [
            {
                "source_type": source_type,
                "source_id": candidate["source_id"],
                "source_version": 1,
                "source_version_fingerprint": candidate[
                    "source_fingerprint"
                ],
                "source_content_fingerprint": candidate[
                    "source_content_fingerprint"
                ],
                "resume_profile_fingerprint": fingerprint_value(
                    {"profile": name}
                ),
                "resume_text_sha256": fingerprint_value({"text": name}),
                "role_family_id": "synthetic_family",
            }
        ],
        "exact_verified_reuse_scope": [
            {
                "normalized_source_fingerprint": normalized_source_fingerprint,
                "proof": copy.deepcopy(candidate["exact_verified_reuse"]),
            }
        ],
        "ranking_policy": {
            "policy_version": PHASE9F_B_RANKING_POLICY_VERSION
        },
    }
    ranking_input_fingerprint = fingerprint_value(semantic_identity)
    ranking_identity = build_ranking_result_identity(
        ranking_input_fingerprint=ranking_input_fingerprint,
        ranked_candidates=[candidate],
    )
    return {
        "phase9f_b_version": PHASE9F_B_VERSION,
        "status": "ranked",
        "ranking_input_fingerprint": ranking_input_fingerprint,
        "ranking_fingerprint": fingerprint_value(ranking_identity),
        "semantic_identity": semantic_identity,
        "jd_provenance": {
            "phase9f_a_snapshot_fingerprint": fingerprint_value(
                {"phase9f_a": name}
            ),
            "canonical_jd_id": f"canonical-jd-{name}",
            "source_version_id": fingerprint_value({"source_version": name}),
        },
        "recommended_source": copy.deepcopy(candidate),
        "ranked_candidates": [candidate],
        "zero_cost_diagnostics": {
            "model_call_count": 0,
            "embedding_call_count": 0,
            "chroma_read_count": 0,
            "chroma_write_count": 0,
            "persistence_write_count": 0,
        },
    }


def result_for_case(case: dict) -> dict:
    metrics = case["metrics"]
    return make_phase9f_b_result(
        name=case["name"],
        overall=metrics["overall"],
        required_core=metrics["required_core"],
        preferred=metrics["preferred"],
        evidence=metrics["evidence"],
        important_requirement_count=case["important_requirement_count"],
        important_gap_count=case["important_gap_count"],
        deal_breaker_gap_count=case["deal_breaker_gap_count"],
        preferred_requirement_count=case.get(
            "preferred_requirement_count", 0
        ),
    )


def attach_exact_verified_reuse_to_ranking(ranking: dict) -> dict:
    """Create a structurally valid B result carrying an authoritative proof."""
    result = copy.deepcopy(ranking)
    candidate = result["ranked_candidates"][0]
    proof = build_exact_verified_reuse_proof(
        {
            "blueprint": {
                "id": candidate["source_id"],
                "fingerprint": candidate["source_fingerprint"],
                "version": candidate["source_version"],
            },
            "current_jd": {
                "canonical_jd_id": result["jd_provenance"]["canonical_jd_id"],
                "source_version_id": result["jd_provenance"]["source_version_id"],
                "raw_jd_sha256": result["semantic_identity"]["exact_jd"]["raw_jd_sha256"],
                "canonical_requirement_fingerprint": candidate[
                    "canonical_requirement_scope_fingerprint"
                ],
                "canonical_requirement_ids": result["semantic_identity"]["exact_jd"][
                    "canonical_requirement_ids"
                ],
            },
            "source_jd": {"source": "same exact immutable JD"},
            "source_generation": {
                "application_id": 106,
                "generation_id": "approved-generation",
            },
            "phase8_verification": {
                "verification_id": "phase8-verification",
                "verification_fingerprint": "phase8-fingerprint",
                "score": 19,
            },
            "phase9c_source_parity": {"accepted": True},
            "artifact_identity": {
                "policy_version": PHASE9F_BLUEPRINT_ARTIFACT_POLICY_VERSION,
                "artifacts": [{"artifact_kind": "docx", "sha256": "docx"}],
            },
        }
    )
    candidate.update(
        {
            "exact_verified_reuse_eligible": True,
            "exact_verified_reuse_reason_code": "exact_verified_reuse",
            "exact_verified_reuse_proof_fingerprint": proof["proof_fingerprint"],
            "exact_verified_reuse": proof,
            "ranking_reason": "exact_verified_reuse_precedence",
        }
    )
    result["recommended_source"] = copy.deepcopy(candidate)
    result["semantic_identity"]["exact_verified_reuse_scope"][0]["proof"] = (
        copy.deepcopy(proof)
    )
    result["ranking_input_fingerprint"] = fingerprint_value(
        result["semantic_identity"]
    )
    identity = build_ranking_result_identity(
        ranking_input_fingerprint=result["ranking_input_fingerprint"],
        ranked_candidates=result["ranked_candidates"],
    )
    result["ranking_fingerprint"] = fingerprint_value(identity)
    return result


class Phase9FTailoringIntensityTests(unittest.TestCase):
    def test_exact_verified_reuse_short_circuits_weak_fresh_diagnostics(self):
        ranking = attach_exact_verified_reuse_to_ranking(
            make_phase9f_b_result(
                name="exact-weak-diagnostic",
                overall=7,
                required_core=2,
                preferred=10,
                evidence=40,
                important_requirement_count=10,
                important_gap_count=8,
                deal_breaker_gap_count=0,
            )
        )
        result = recommend_tailoring_intensity(
            ranking,
            expected_ranking_input_fingerprint=ranking[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(result["status"], "recommended")
        self.assertEqual(result["recommended_intensity"], "reuse")
        self.assertEqual(
            result["decisive_rule"]["code"], "reuse_exact_verified_source"
        )
        self.assertEqual(result["metrics"]["current_jd_alignment"], 7)
        self.assertEqual(
            result["selected_source_context"]["exact_verified_reuse"][
                "verified_score"
            ],
            19,
        )

    def test_golden_policy_and_boundaries(self):
        fixture = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(fixture["policy_version"], PHASE9F_C_POLICY_VERSION)
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                ranking = result_for_case(case)
                result = recommend_tailoring_intensity(
                    ranking,
                    expected_ranking_input_fingerprint=ranking[
                        "ranking_input_fingerprint"
                    ],
                )
                self.assertEqual(result["status"], case["expected_status"])
                self.assertEqual(
                    result["recommended_intensity"],
                    case["expected_intensity"],
                )
                self.assertEqual(
                    result["decisive_rule"]["code"],
                    case["expected_rule"],
                )

    def test_zero_important_scope_fails_closed_before_required_score(self):
        fixture = json.loads(GOLDEN.read_text(encoding="utf-8"))
        for name in ("preferred_only_scope", "empty_requirement_scope"):
            case = next(row for row in fixture["cases"] if row["name"] == name)
            ranking = result_for_case(case)
            result = recommend_tailoring_intensity(
                ranking,
                expected_ranking_input_fingerprint=ranking[
                    "ranking_input_fingerprint"
                ],
            )
            self.assertEqual(result["status"], "fail_closed")
            self.assertIsNone(result["recommended_intensity"])
            self.assertEqual(
                result["failure_code"],
                "insufficient_important_requirement_scope",
            )
            self.assertEqual(
                result["semantic_identity"]["diagnostics"][
                    "important_requirement_count"
                ],
                0,
            )

    def test_invalid_stale_unsupported_and_ambiguous_results_fail_closed(self):
        ranking = make_phase9f_b_result(
            name="invalid",
            overall=90,
            required_core=90,
            preferred=90,
            evidence=90,
            important_requirement_count=10,
            important_gap_count=0,
            deal_breaker_gap_count=0,
        )
        stale = recommend_tailoring_intensity(
            ranking,
            expected_ranking_input_fingerprint="different",
        )
        self.assertEqual(stale["failure_code"], "ranking_result_stale")

        unsupported = copy.deepcopy(ranking)
        unsupported["phase9f_b_version"] = "future"
        result = recommend_tailoring_intensity(
            unsupported,
            expected_ranking_input_fingerprint=ranking[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(
            result["failure_code"], "ranking_result_version_unsupported"
        )

        ambiguous = copy.deepcopy(ranking)
        ambiguous["ranked_candidates"].append(
            copy.deepcopy(ambiguous["ranked_candidates"][0])
        )
        result = recommend_tailoring_intensity(
            ambiguous,
            expected_ranking_input_fingerprint=ranking[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(result["status"], "fail_closed")

    def test_tampered_canonical_outcome_fails_closed(self):
        ranking = make_phase9f_b_result(
            name="tampered-outcome",
            overall=90,
            required_core=90,
            preferred=90,
            evidence=90,
            important_requirement_count=10,
            important_gap_count=0,
            deal_breaker_gap_count=0,
        )
        ranking["recommended_source"]["canonical_requirement_results"][0][
            "match_label"
        ] = "none"
        ranking["recommended_source"]["canonical_requirement_results"][0][
            "evidence_strength"
        ] = 0
        ranking["ranked_candidates"][0] = copy.deepcopy(
            ranking["recommended_source"]
        )
        result = recommend_tailoring_intensity(
            ranking,
            expected_ranking_input_fingerprint=ranking[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(result["status"], "fail_closed")
        self.assertEqual(
            result["failure_code"],
            "ranked_candidate_comparison_fingerprint_mismatch",
        )

    def test_preferred_is_explanatory_only(self):
        common = dict(
            overall=90,
            required_core=90,
            evidence=80,
            important_requirement_count=10,
            important_gap_count=0,
            deal_breaker_gap_count=0,
            preferred_requirement_count=2,
        )
        low = make_phase9f_b_result(name="preferred-low", preferred=0, **common)
        high = make_phase9f_b_result(
            name="preferred-high", preferred=100, **common
        )
        low_result = recommend_tailoring_intensity(
            low,
            expected_ranking_input_fingerprint=low[
                "ranking_input_fingerprint"
            ],
        )
        high_result = recommend_tailoring_intensity(
            high,
            expected_ranking_input_fingerprint=high[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(low_result["recommended_intensity"], "reuse")
        self.assertEqual(high_result["recommended_intensity"], "reuse")
        self.assertEqual(
            low_result["decisive_rule"]["code"],
            high_result["decisive_rule"]["code"],
        )

    def test_role_family_and_source_type_do_not_choose_intensity(self):
        common = dict(
            overall=75,
            required_core=75,
            preferred=50,
            evidence=70,
            important_requirement_count=10,
            important_gap_count=1,
            deal_breaker_gap_count=0,
        )
        same = make_phase9f_b_result(
            name="same-family",
            source_type="global_blueprint",
            role_family_relationship="same_family",
            role_family_confidence="high",
            **common,
        )
        cross = make_phase9f_b_result(
            name="cross-family",
            source_type="base_resume",
            role_family_relationship="cross_family",
            role_family_confidence="low",
            **common,
        )
        same_result = recommend_tailoring_intensity(
            same,
            expected_ranking_input_fingerprint=same[
                "ranking_input_fingerprint"
            ],
        )
        cross_result = recommend_tailoring_intensity(
            cross,
            expected_ranking_input_fingerprint=cross[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(same_result["recommended_intensity"], "minor")
        self.assertEqual(
            same_result["recommended_intensity"],
            cross_result["recommended_intensity"],
        )
        self.assertEqual(
            same_result["decisive_rule"]["code"],
            cross_result["decisive_rule"]["code"],
        )
        self.assertNotEqual(
            same_result["recommendation_fingerprint"],
            cross_result["recommendation_fingerprint"],
        )

    def test_history_date_and_display_name_do_not_change_identity(self):
        ranking = make_phase9f_b_result(
            name="display-only",
            overall=90,
            required_core=90,
            preferred=10,
            evidence=90,
            important_requirement_count=10,
            important_gap_count=0,
            deal_breaker_gap_count=0,
        )
        changed = copy.deepcopy(ranking)
        changed["recommended_source"]["source_display_name"] = "Renamed"
        changed["recommended_source"]["historical_score"] = 100
        changed["recommended_source"]["created_at"] = "2099-01-01"
        changed["ranked_candidates"][0] = copy.deepcopy(
            changed["recommended_source"]
        )
        first = recommend_tailoring_intensity(
            ranking,
            expected_ranking_input_fingerprint=ranking[
                "ranking_input_fingerprint"
            ],
        )
        second = recommend_tailoring_intensity(
            changed,
            expected_ranking_input_fingerprint=changed[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(first["recommended_intensity"], "reuse")
        self.assertEqual(
            first["recommendation_fingerprint"],
            second["recommendation_fingerprint"],
        )

    def test_exact_semantic_input_reuses_recommendation_fingerprint(self):
        ranking = make_phase9f_b_result(
            name="exact-reuse",
            overall=85,
            required_core=85,
            preferred=0,
            evidence=70,
            important_requirement_count=8,
            important_gap_count=0,
            deal_breaker_gap_count=0,
        )
        before = copy.deepcopy(ranking)
        first = recommend_tailoring_intensity(
            ranking,
            expected_ranking_input_fingerprint=ranking[
                "ranking_input_fingerprint"
            ],
        )
        second = recommend_tailoring_intensity(
            copy.deepcopy(ranking),
            expected_ranking_input_fingerprint=ranking[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(
            first["recommendation_fingerprint"],
            second["recommendation_fingerprint"],
        )
        self.assertEqual(ranking, before)

    def test_changed_winner_semantics_stale_previous_recommendation(self):
        first_ranking = make_phase9f_b_result(
            name="scope-one",
            overall=90,
            required_core=90,
            preferred=90,
            evidence=90,
            important_requirement_count=10,
            important_gap_count=0,
            deal_breaker_gap_count=0,
        )
        second_ranking = make_phase9f_b_result(
            name="scope-two",
            overall=90,
            required_core=90,
            preferred=90,
            evidence=90,
            important_requirement_count=10,
            important_gap_count=0,
            deal_breaker_gap_count=0,
        )
        first = recommend_tailoring_intensity(
            first_ranking,
            expected_ranking_input_fingerprint=first_ranking[
                "ranking_input_fingerprint"
            ],
        )
        second = recommend_tailoring_intensity(
            second_ranking,
            expected_ranking_input_fingerprint=second_ranking[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(first["recommended_intensity"], "reuse")
        self.assertEqual(second["recommended_intensity"], "reuse")
        self.assertNotEqual(
            first["recommendation_fingerprint"],
            second["recommendation_fingerprint"],
        )

    def test_reverse_phase9f_b_enumeration_is_intensity_invariant(self):
        jd = make_exact_jd()
        base, artifact = make_base(strong=False)
        blueprints = [
            make_blueprint(
                strong=True,
                role_family_id="ai_fullstack_software_engineering",
                role_family_label="AI & Full-Stack Software Engineering",
                marker="reverse-a",
            ),
            make_blueprint(
                strong=False,
                role_family_id="backend_cloud_software_engineering",
                role_family_label="Backend & Cloud Software Engineering",
                marker="reverse-b",
            ),
        ]
        first_ranking = rank_starting_resume_sources(
            exact_jd=jd,
            current_base_resume=base,
            current_base_artifact=artifact,
            global_blueprints=blueprints,
        )
        second_ranking = rank_starting_resume_sources(
            exact_jd=jd,
            current_base_resume=base,
            current_base_artifact=artifact,
            global_blueprints=list(reversed(blueprints)),
        )
        first = recommend_tailoring_intensity(
            first_ranking,
            expected_ranking_input_fingerprint=first_ranking[
                "ranking_input_fingerprint"
            ],
        )
        second = recommend_tailoring_intensity(
            second_ranking,
            expected_ranking_input_fingerprint=second_ranking[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(
            first_ranking["ranking_fingerprint"],
            second_ranking["ranking_fingerprint"],
        )
        self.assertEqual(
            first["recommendation_fingerprint"],
            second["recommendation_fingerprint"],
        )

    def test_contract_versions_policy_and_zero_cost_are_explicit(self):
        ranking = make_phase9f_b_result(
            name="contract",
            overall=90,
            required_core=90,
            preferred=0,
            evidence=90,
            important_requirement_count=10,
            important_gap_count=0,
            deal_breaker_gap_count=0,
        )
        result = recommend_tailoring_intensity(
            ranking,
            expected_ranking_input_fingerprint=ranking[
                "ranking_input_fingerprint"
            ],
        )
        self.assertEqual(result["phase9f_c_version"], PHASE9F_C_VERSION)
        self.assertEqual(result["policy_version"], PHASE9F_C_POLICY_VERSION)
        self.assertEqual(
            result["semantic_identity"]["phase9f_b"][
                "ranking_fingerprint"
            ],
            ranking["ranking_fingerprint"],
        )
        self.assertEqual(
            result["zero_cost_diagnostics"],
            {
                "model_call_count": 0,
                "embedding_call_count": 0,
                "chroma_read_count": 0,
                "chroma_write_count": 0,
                "persistence_write_count": 0,
            },
        )
        policy = tailoring_intensity_policy_identity()
        self.assertEqual(policy["preferred_coverage"], "explanatory_only")
        source = (
            REPO_ROOT / "tailoring" / "phase9f_tailoring_intensity.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "build_stable_analysis",
            "order_scored_candidates",
            "rank_prepared_context",
            "database.",
            "chromadb",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
