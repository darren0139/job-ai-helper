"""Real zero-cost Phase 9F-B deterministic ranking smoke check."""

from __future__ import annotations

from tailoring.phase9f_starting_source_ranking import (
    rank_starting_resume_sources,
)
from tests.test_phase9f_starting_source_ranking import (
    make_base,
    make_blueprint,
    make_exact_jd,
)


def main() -> None:
    jd = make_exact_jd()
    base, artifact = make_base(strong=False)
    blueprint = make_blueprint(
        strong=True,
        role_family_id="ai_fullstack_software_engineering",
        role_family_label="AI & Full-Stack Software Engineering",
        marker="smoke",
    )
    first = rank_starting_resume_sources(
        exact_jd=jd,
        current_base_resume=base,
        current_base_artifact=artifact,
        global_blueprints=[blueprint],
    )
    second = rank_starting_resume_sources(
        exact_jd=jd,
        current_base_resume=base,
        current_base_artifact=artifact,
        global_blueprints=[blueprint],
    )
    assert first["status"] == "ranked"
    assert first["recommended_source"]["source_id"] == blueprint["blueprint_id"]
    assert first["recommended_source"]["deterministic_alignment_score"] > 0
    assert first["recommended_source"]["required_core_coverage_score"] > 0
    assert first["ranked_candidates"][0][
        "deterministic_alignment_score"
    ] > first["ranked_candidates"][1]["deterministic_alignment_score"]
    assert first["ranking_fingerprint"] == second["ranking_fingerprint"]
    assert first["zero_cost_diagnostics"] == {
        "model_call_count": 0,
        "embedding_call_count": 0,
        "chroma_read_count": 0,
        "chroma_write_count": 0,
        "persistence_write_count": 0,
    }
    winner = first["recommended_source"]
    print(
        "Phase 9F-B smoke PASS: "
        f"winner={winner['source_type']} "
        f"alignment={winner['deterministic_alignment_score']} "
        f"required_core={winner['required_core_coverage_score']} "
        f"candidates={len(first['ranked_candidates'])} "
        "model_calls=0 embedding_calls=0 chroma_reads=0 "
        "chroma_writes=0 persistence_writes=0 exact_reuse=yes"
    )


if __name__ == "__main__":
    main()
