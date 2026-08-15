"""Zero-cost deterministic Phase 9F-C smoke check."""

from __future__ import annotations

from tailoring.phase9f_tailoring_intensity import (
    recommend_tailoring_intensity,
)
from tests.test_phase9f_tailoring_intensity import make_phase9f_b_result


def _recommend(**values):
    ranking = make_phase9f_b_result(**values)
    return recommend_tailoring_intensity(
        ranking,
        expected_ranking_input_fingerprint=ranking[
            "ranking_input_fingerprint"
        ],
    )


def main() -> None:
    common = {
        "preferred": 10,
        "deal_breaker_gap_count": 0,
    }
    reuse = _recommend(
        name="smoke-reuse",
        overall=90,
        required_core=90,
        evidence=80,
        important_requirement_count=10,
        important_gap_count=0,
        **common,
    )
    minor = _recommend(
        name="smoke-minor",
        overall=80,
        required_core=80,
        evidence=80,
        important_requirement_count=22,
        important_gap_count=3,
        **common,
    )
    full = _recommend(
        name="smoke-full",
        overall=80,
        required_core=80,
        evidence=80,
        important_requirement_count=15,
        important_gap_count=3,
        **common,
    )
    insufficient = _recommend(
        name="smoke-insufficient",
        overall=0,
        required_core=0,
        preferred=100,
        evidence=100,
        important_requirement_count=0,
        important_gap_count=0,
        deal_breaker_gap_count=0,
        preferred_requirement_count=2,
    )
    repeated = _recommend(
        name="smoke-reuse",
        overall=90,
        required_core=90,
        evidence=80,
        important_requirement_count=10,
        important_gap_count=0,
        **common,
    )

    assert reuse["recommended_intensity"] == "reuse"
    assert minor["recommended_intensity"] == "minor"
    assert full["recommended_intensity"] == "full"
    assert (
        full["decisive_rule"]["code"]
        == "full_broad_important_gap_deficiency"
    )
    assert insufficient["status"] == "fail_closed"
    assert insufficient["recommended_intensity"] is None
    assert (
        insufficient["failure_code"]
        == "insufficient_important_requirement_scope"
    )
    assert (
        reuse["recommendation_fingerprint"]
        == repeated["recommendation_fingerprint"]
    )
    assert reuse["zero_cost_diagnostics"] == {
        "model_call_count": 0,
        "embedding_call_count": 0,
        "chroma_read_count": 0,
        "chroma_write_count": 0,
        "persistence_write_count": 0,
    }
    print(
        "Phase 9F-C smoke PASS: reuse=Reuse minor=Minor full=Full "
        "gap_boundary=3/15 insufficient_scope=fail_closed "
        "model_calls=0 embedding_calls=0 chroma_reads=0 "
        "chroma_writes=0 persistence_writes=0 exact_reuse=yes"
    )


if __name__ == "__main__":
    main()

