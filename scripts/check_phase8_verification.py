from __future__ import annotations

from tailoring.phase8_verification import compare_stable_analyses


def main() -> int:
    before = {
        "deterministic_alignment_score": 50,
        "alignment_band": "partial alignment",
        "required_core_coverage_score": 50,
        "preferred_coverage_score": 0,
        "evidence_strength_score": 60,
        "canonical_requirements": [
            {
                "requirement_id": "req_a",
                "text": "Python",
                "importance": "required",
                "match_label": "weak",
                "evidence_strength": 2,
            }
        ],
    }
    after = {
        **before,
        "deterministic_alignment_score": 60,
        "required_core_coverage_score": 60,
        "canonical_requirements": [
            {
                "requirement_id": "req_a",
                "text": "Python",
                "importance": "required",
                "match_label": "direct",
                "evidence_strength": 5,
            }
        ],
    }

    result = compare_stable_analyses(before, after)
    passed = (
        result["score_delta"] == 10
        and len(result["improved_requirements"]) == 1
        and not result["important_regressions"]
    )
    print("Score delta:", result["score_delta"])
    print("Improved:", len(result["improved_requirements"]))
    print("Important regressions:", len(result["important_regressions"]))
    print(
        "PHASE 8 BEFORE/AFTER VERIFICATION SMOKE TEST:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
