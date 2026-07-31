from __future__ import annotations

from unittest.mock import patch

from tailoring.phase9a_evidence_opportunity import (
    select_evidence_opportunities,
)


def main() -> int:
    stable = {
        "canonical_requirements": [
            {
                "requirement_id": "req_python",
                "text": "Python",
                "importance": "required",
                "match_label": "none",
            }
        ]
    }
    evidence = [
        {
            "id": 1,
            "title": "Job AI Helper",
            "description": "Built a Python application.",
            "skills": ["Python"],
            "tools": [],
        }
    ]

    with patch(
        "tailoring.phase9a_evidence_opportunity."
        "match_requirement_to_candidate",
        return_value={
            "label": "direct",
            "capability_id": "programming.python",
            "reason": "smoke",
            "taxonomy_version": "smoke",
        },
    ):
        selected = select_evidence_opportunities(
            stable_analysis=stable,
            evidence_items=evidence,
            max_projects=3,
        )

    passed = (
        len(selected) == 1
        and selected[0]["item"]["title"] == "Job AI Helper"
        and selected[0]["incremental_points"] > 0
    )
    print("Selected evidence:", len(selected))
    print(
        "PHASE 9A EVIDENCE OPPORTUNITY SMOKE:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
