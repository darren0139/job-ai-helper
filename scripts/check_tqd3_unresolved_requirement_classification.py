from __future__ import annotations

from taxonomy_discovery.classification import (
    CLASS_B,
    CLASS_D,
    CLASS_E,
    CLASS_U,
    CLASSIFICATION_VERSION,
    classify_unresolved_candidate,
)


def _candidate(
    text: str,
    *,
    job_count: int = 1,
    observation_count: int = 1,
) -> dict:
    return {
        "candidate_id": "smoke",
        "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
        "normalised_observed_text": text.lower(),
        "observed_terms": [text],
        "observation_count": observation_count,
        "job_count": job_count,
        "observations": [
            {
                "observation_id": f"obs_{index}",
                "discovered_job_id": index + 1,
                "requirement_id": f"req_{index}",
                "requirement_text": text,
                "normalised_observed_text": text.lower(),
                "taxonomy_version": "phase6d-capability-taxonomy-v1.4",
                "match_label": "none",
            }
            for index in range(observation_count)
        ],
        "diagnostic_flags": [],
        "observation_contexts": [
            {
                "context_available": True,
                "explicit_only_requirement": False,
                "retrieval": {"candidates": []},
                "atomic_siblings": [],
            }
        ],
        "technology_registry_resolution": {
            "status": "unresolved",
            "registry_version": "technology-registry-v1.1",
            "technology_id": None,
            "capability_id": None,
        },
    }


def main() -> None:
    technology = classify_unresolved_candidate(
        _candidate("AngularJS, NodeJS and ReactJS")
    )
    assert technology["class_id"] == CLASS_B

    subjective = classify_unresolved_candidate(
        _candidate("Ability to learn new technologies quickly")
    )
    assert subjective["class_id"] == CLASS_D

    recurrent = classify_unresolved_candidate(
        _candidate(
            "Generate technical documentation and operational reports",
            job_count=2,
            observation_count=2,
        )
    )
    assert recurrent["class_id"] == CLASS_E

    unresolved = classify_unresolved_candidate(
        _candidate("Analyze and troubleshoot software issues")
    )
    assert unresolved["class_id"] == CLASS_U

    for result in (technology, subjective, recurrent, unresolved):
        assert result["classification_version"] == CLASSIFICATION_VERSION
        assert result["requires_human_review"] is True
        assert result["mutates_taxonomy"] is False
        assert result["mutates_registry"] is False
        assert result["influences_scoring"] is False

    print(
        "TQ-D3 deterministic classification smoke PASS: "
        f"version={CLASSIFICATION_VERSION} "
        "model=0 network=0 taxonomy_mutations=0 registry_mutations=0 "
        "scoring_influence=false"
    )


if __name__ == "__main__":
    main()
