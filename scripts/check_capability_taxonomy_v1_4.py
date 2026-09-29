"""Offline rule smoke; no application/model/database imports."""
from tailoring.capability_taxonomy import evaluate_evidence, get_default_taxonomy


def main():
    assert get_default_taxonomy().version == "phase6d-capability-taxonomy-v1.4"
    cases = [
        ("Android application development using Kotlin", "Built an Android application using Kotlin", "direct"),
        ("Android application development", "Kotlin", "none"),
        ("Vulkan", "OpenGL", "none"),
        ("Modern C++ proficiency", "Built C++ software", "transferable"),
        ("Data structures and algorithms", "Built data pipelines", "none"),
    ]
    for requirement, evidence, expected in cases:
        assert evaluate_evidence({"text": requirement}, evidence)["label"] == expected
    print("Taxonomy v1.4 smoke PASS: 5 cases; model=0 embedding=0 Chroma=0 network=0 writes=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
