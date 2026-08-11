"""Zero-cost Phase 8 -> Phase 9C canonical parity smoke."""

from __future__ import annotations

from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION,
    compute_deterministic_alignment,
)
from tailoring.final_scoring_seed import (
    build_final_scoring_seed,
    fingerprint_final_scoring_seed,
    verify_final_scoring_seed,
)


def rows(label: str, strength: int) -> list[dict]:
    values = {"none": 0.0, "weak": 0.2, "transferable": 0.55}
    return [
        {
            "requirement_id": f"req_{index}",
            "text": f"Requirement {index}",
            "importance": "core",
            "atomic_group_id": "shared",
            "group_weight_fraction": 1 / 6,
            "match_label": label if index == 0 else "none",
            "match_value": values[label] if index == 0 else 0.0,
            "evidence_strength": strength if index == 0 else 0,
            "capability_id": "",
        }
        for index in range(6)
    ]


def main() -> int:
    before = compute_deterministic_alignment(rows("weak", 2))
    after_rows = rows("transferable", 3)
    after = compute_deterministic_alignment(after_rows)
    assert before["deterministic_alignment_score"] == 7
    assert after["deterministic_alignment_score"] == 14
    seed = build_final_scoring_seed(
        {
            "scoring_version": SCORING_VERSION,
            "capability_taxonomy_version": "smoke",
            "canonical_requirements": after_rows,
        }
    )
    fingerprint = fingerprint_final_scoring_seed(seed)
    reproduced = verify_final_scoring_seed(seed, fingerprint)
    assert reproduced["aggregate"]["deterministic_alignment_score"] == 14
    print("PHASE 8 -> PHASE 9C CANONICAL AGGREGATION PARITY: PASS")
    print("Synthetic regression: 7 -> 14")
    print("Seed:", fingerprint[:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
