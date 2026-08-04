"""Real zero-cost Phase 9C smoke check using the Application 94 fixture."""

from __future__ import annotations

import json
from pathlib import Path

from tailoring.phase9c_blueprint_evaluation import evaluate_blueprint_candidate


def main() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "ci_fixtures" / (
        "phase9c_application94_acceptance.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    result = evaluate_blueprint_candidate(
        candidate=fixture["candidate"],
        selected_jds=fixture["saved_jds"][:2],
        saved_jds_for_source_resolution=fixture["saved_jds"],
    )
    per_jd = result["per_jd_results"]
    source = next(row for row in per_jd if row["is_source_jd"])
    aggregate = result["aggregate_result"]
    assert source["deterministic_alignment_score"] == 92
    assert source["source_jd_parity"]["accepted"] is True
    assert len(per_jd) == 2
    assert aggregate["provisional"] is False
    assert aggregate["mean_score"] >= 75
    assert aggregate["minimum_score"] >= 65
    assert aggregate["pass_rate"] == 100.0
    target = next(row for row in per_jd if not row["is_source_jd"])
    for section in ("education", "experience", "projects", "skills"):
        assert target["evidence_sections_considered"][section] > 0
    assert result["mutation_policy"] == {
        "candidate_mutated": False,
        "saved_jds_mutated": False,
    }
    print(
        "Phase 9C smoke PASS:",
        f"source={source['deterministic_alignment_score']}",
        f"mean={aggregate['mean_score']}",
        f"minimum={aggregate['minimum_score']}",
        f"fingerprint={result['evaluation_fingerprint'][:12]}",
    )


if __name__ == "__main__":
    main()
