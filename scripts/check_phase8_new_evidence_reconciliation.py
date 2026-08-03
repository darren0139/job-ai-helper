from __future__ import annotations

from tests.test_phase8_requirement_reconciliation import (
    analysis,
    generation,
    lineage,
    requirement,
)
from tailoring.phase8_requirement_reconciliation import (
    reconcile_final_requirement_matches,
)


def main() -> None:
    requirement_id = "req-access-new"
    requirement_text = (
        "Experience implementing authentication workflows or "
        "database access control"
    )
    bullet = (
        "Implemented backend data access through PostgREST and applied "
        "Row-Level Security policies to secure database operations."
    )
    project = {
        "project_id": "project-query",
        "title": "QueryAI",
        "display_title": "QueryAI (React, Team of 4)",
        "draft_bullets": [bullet],
        "requirement_matches": [
            {
                "requirement_id": requirement_id,
                "requirement_text": requirement_text,
                "match_label": "direct",
                "evidence_snippets": [bullet],
            }
        ],
    }
    state = generation(
        [project],
        skills=["authentication workflows", "access control"],
        rankings=[
            {
                "skill": "authentication workflows",
                "matched_requirement_ids": [requirement_id],
            },
            {
                "skill": "access control",
                "matched_requirement_ids": [requirement_id],
            },
        ],
    )
    reconciled, report = reconcile_final_requirement_matches(
        before_analysis=analysis(
            [requirement(requirement_id, requirement_text, "none")]
        ),
        after_analysis=analysis(
            [requirement(requirement_id, requirement_text, "none")]
        ),
        generation_state=state,
        claim_lineage=lineage(
            project_bullets=[
                (
                    "project-query",
                    "QueryAI (React, Team of 4)",
                    bullet,
                )
            ],
            skills=["authentication workflows", "access control"],
        ),
    )
    label = reconciled["canonical_requirements"][0]["match_label"]
    assert label == "direct", label
    assert report["newly_supported_requirement_count"] == 1
    print("New final-evidence label:", label)
    print(
        "Newly supported requirements:",
        report["newly_supported_requirement_count"],
    )
    print("PHASE 8 NEW EVIDENCE RECONCILIATION: PASS")


if __name__ == "__main__":
    main()
