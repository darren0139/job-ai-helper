from __future__ import annotations

from tailoring.phase9b_blueprint_candidate import (
    blueprint_candidate_eligibility,
)


def main() -> int:
    result = blueprint_candidate_eligibility(
        generation_state={
            "generation_id": "generation-a",
            "status": "approved",
            "fit_result": {
                "fit_one_page": True,
                "page_count": 1,
            },
        },
        verification={
            "generation_id": "generation-a",
            "comparison_valid": True,
            "blueprint_ready": True,
            "claim_lineage": {
                "claim_review_required_count": 0,
            },
        },
    )
    passed = result["eligible"] is True
    print("Eligibility gates:", result["reasons"])
    print(
        "PHASE 9B BLUEPRINT CANDIDATE ELIGIBILITY:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
