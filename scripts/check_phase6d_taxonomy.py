"""Run a compact Phase 6D smoke test without making model API calls."""

from __future__ import annotations

import json

from tailoring.capability_taxonomy import (
    evaluate_evidence,
    get_default_taxonomy,
)
from rag.capability_taxonomy_rag import lexical_retrieve


CASES = [
    (
        "Kubernetes orchestration",
        "Containerised the application with Docker Compose.",
        "none",
    ),
    (
        "Kubernetes orchestration",
        "Created Kubernetes Deployment, Service and Ingress manifests.",
        "direct",
    ),
    (
        "Ability to collaborate with cross-functional teams",
        "Collaborated with a team of interns in SCRUM.",
        "weak",
    ),
    (
        "LLM model evaluation",
        "Manually reviewed generated answers.",
        "none",
    ),
    (
        "LLM model evaluation",
        "Built an evaluation harness with a test set and pass-rate metric.",
        "direct",
    ),
]


def main() -> int:
    taxonomy = get_default_taxonomy()
    print(f"Taxonomy version: {taxonomy.version}")
    print(f"Capability count: {len(taxonomy.capabilities)}")

    failures = []
    for requirement, evidence, expected in CASES:
        result = evaluate_evidence(
            {"text": requirement, "atomic_focus": requirement},
            evidence,
        )
        actual = result["label"]
        print(
            json.dumps(
                {
                    "requirement": requirement,
                    "evidence": evidence,
                    "capability_id": result["capability_id"],
                    "expected": expected,
                    "actual": actual,
                    "reason": result["reason"],
                },
                indent=2,
            )
        )
        if actual != expected:
            failures.append(
                f"{requirement}: expected {expected}, got {actual}"
            )

    rag_results = lexical_retrieve(
        "ChromaDB vector retrieval for a grounded LLM",
        top_k=3,
    )
    print("\nOffline taxonomy retrieval:")
    for row in rag_results:
        print(
            f"- {row['metadata']['capability_id']} "
            f"(score={row['score']})"
        )

    if failures:
        print("\nPHASE 6D SMOKE TEST: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nPHASE 6D SMOKE TEST: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
