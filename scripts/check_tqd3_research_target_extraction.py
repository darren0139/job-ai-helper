from __future__ import annotations

from taxonomy_discovery.classification import CLASS_B
from taxonomy_discovery.research_targets import (
    RESEARCH_TARGET_VERSION,
    TARGET_TECHNOLOGY_RELATIONSHIP,
    build_research_target_report,
)


def main() -> None:
    candidate = {
        "candidate_id": "smoke_node",
        "normalised_observed_text": "nodejs",
        "observed_terms": [
            "comfortable using AngularJS, NodeJS, ReactJS"
        ],
        "job_count": 1,
        "observation_count": 1,
        "tqd3_classification": {
            "class_id": CLASS_B,
            "signals": {
                "registry_alias_mentions": [
                    {
                        "technology_id": "angular",
                        "technology_label": "Angular",
                        "alias": "AngularJS",
                        "mapping_status": "mapped",
                        "capability_id": "frontend.ui_development",
                    },
                    {
                        "technology_id": "node.js",
                        "technology_label": "Node.js",
                        "alias": "NodeJS",
                        "mapping_status": "recognized_unmapped",
                        "capability_id": None,
                    },
                    {
                        "technology_id": "react",
                        "technology_label": "React",
                        "alias": "ReactJS",
                        "mapping_status": "mapped",
                        "capability_id": "frontend.ui_development",
                    },
                ]
            },
        },
    }
    report = build_research_target_report(
        {
            "classification_version": (
                "tqd3-unresolved-requirement-classification-v1.0.0"
            ),
            "candidates": [candidate],
        }
    )
    relation_targets = [
        row
        for row in report["targets"]
        if row["target_type"] == TARGET_TECHNOLOGY_RELATIONSHIP
    ]
    assert [row["target_key"] for row in relation_targets] == ["node.js"]
    assert report["governance"]["tavily_calls"] == 0
    assert report["governance"]["network_calls"] == 0
    assert report["governance"]["taxonomy_mutations"] == 0
    assert report["governance"]["registry_mutations"] == 0
    assert report["governance"]["scoring_influence"] is False

    print(
        "TQ-D3 research-target extraction smoke PASS: "
        f"version={RESEARCH_TARGET_VERSION} "
        "tavily=0 network=0 mutation=0 scoring_influence=false"
    )


if __name__ == "__main__":
    main()
