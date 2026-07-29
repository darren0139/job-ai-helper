from __future__ import annotations

from unittest.mock import patch

from tailoring.phase8_verification import build_phase8_verification


def _stable(requirement_id: str):
    return {
        "deterministic_alignment_score": 50,
        "alignment_band": "partial alignment",
        "required_core_coverage_score": 50,
        "preferred_coverage_score": 0,
        "evidence_strength_score": 60,
        "canonical_requirements": [
            {
                "requirement_id": requirement_id,
                "text": "Python",
                "importance": "required",
                "match_label": "direct",
                "evidence_strength": 5,
            }
        ],
        "input_fingerprint": "baseline",
    }


def main() -> int:
    baseline = {
        "stable_analysis": _stable("req_a"),
        "resume_profile": {
            "projects": [],
            "skills": {},
            "experience": [],
            "education": [],
        },
        "jd_profile": {},
        "keyword_match": {"present": [], "missing": []},
        "bullets": {"bullet_quality_avg": 80},
        "structure": {"structure_score": 100},
    }
    generation = {
        "application_id": 1,
        "generation_id": "generation-a",
        "status": "approved",
        "updated_at": "2026-07-29T10:00:00",
        "projects": {"recommended_projects": []},
        "skills": {"skill_lines": []},
        "fit_result": {"fit_one_page": True, "page_count": 1},
    }

    with patch(
        "tailoring.phase8_verification.build_stable_analysis",
        return_value=_stable("req_changed"),
    ):
        result = build_phase8_verification(
            baseline_report=baseline,
            generation_state=generation,
            raw_jd_text="Python is required.",
        )

    passed = (
        result["comparison_valid"] is False
        and result["verdict"] == "invalid_canonical_mismatch"
        and result["blueprint_ready"] is False
    )
    print("Comparison valid:", result["comparison_valid"])
    print("Verdict:", result["verdict"])
    print("Blueprint ready:", result["blueprint_ready"])
    print(
        "PHASE 8 CANONICAL REQUIREMENT GUARD:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
