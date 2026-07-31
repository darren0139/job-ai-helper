"""Zero-cost smoke check for Phase 8 live readiness refresh."""

from __future__ import annotations

from tailoring.phase8_verification import refresh_phase8_readiness


def main() -> None:
    cached = {
        "generation_status": "draft",
        "fit_one_page": True,
        "page_count": 1,
        "comparison_valid": True,
        "comparison": {
            "score_delta": 38,
            "important_regressions": [],
            "canonical_requirement_ids_stable": True,
        },
        "claim_lineage": {
            "claim_review_required_count": 0,
        },
        "blueprint_ready": False,
        "blueprint_readiness_reasons": {
            "is_approved": False,
            "fits_one_page": True,
            "canonical_requirement_ids_stable": True,
            "no_required_core_regression": True,
            "no_claim_review_risks": True,
            "score_not_lower": True,
        },
    }
    generation = {
        "generation_id": "ac8191407bea4aecac63b1330729e5ec",
        "status": "approved",
        "fit_result": {
            "fit_one_page": True,
            "page_count": 1,
        },
    }

    refreshed = refresh_phase8_readiness(
        cached,
        generation,
    )

    assert cached["generation_status"] == "draft"
    assert cached["blueprint_ready"] is False
    assert refreshed["generation_status"] == "approved"
    assert refreshed["blueprint_readiness_reasons"]["is_approved"] is True
    assert refreshed["blueprint_ready"] is True

    print("Generation status:", refreshed["generation_status"])
    print("Blueprint ready:", refreshed["blueprint_ready"])
    print("PHASE 8 READINESS CACHE REFRESH: PASS")


if __name__ == "__main__":
    main()
