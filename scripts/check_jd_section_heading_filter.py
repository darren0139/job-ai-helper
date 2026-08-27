# Zero-cost smoke check for JD section-heading filtering.

from __future__ import annotations

from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION,
    canonicalise_requirements,
)


def main() -> None:
    raw_jd = """
Company: Example
Role: Software Engineer

Key Responsibilities:
Build reliable Python services.

Job Requirements
Hands-on experience with Python.

Preferred Qualifications
Experience with Docker.

Benefits
Medical coverage and annual leave.
"""

    result = canonicalise_requirements({}, raw_jd)
    rows = result["requirements"]
    by_text = {row["text"]: row for row in rows}

    heading_texts = {
        "Key Responsibilities:",
        "Job Requirements",
        "Preferred Qualifications",
        "Benefits",
    }
    leaked = heading_texts & set(by_text)
    assert not leaked, f"Section headings leaked into requirements: {sorted(leaked)}"

    assert by_text["Build reliable Python services"]["importance"] == "core"
    assert by_text["Hands-on experience with Python"]["importance"] == "required"
    assert by_text["Experience with Docker"]["importance"] == "preferred"
    assert "Medical coverage and annual leave" not in by_text

    filtered = result.get("filtered_section_headings", [])
    assert len(filtered) >= 4
    assert SCORING_VERSION == "stable-evidence-v1.3-phase6d7"

    sentence_result = canonicalise_requirements(
        {},
        """
Job Description
Responsibilities include implementing production monitoring workflows.
""",
    )
    sentence_texts = {row["text"] for row in sentence_result["requirements"]}
    assert (
        "Responsibilities include implementing production monitoring workflows"
        in sentence_texts
    )

    phase_2_3b_result = canonicalise_requirements(
        {},
        """
Requirements and Skills
• C++
• Data Structures

Bonus Requirements and Skills
• Android/Kotlin
• CUDA
""",
    )
    phase_2_3b_rows = {
        row["text"]: row
        for row in phase_2_3b_result["requirements"]
    }
    assert set(phase_2_3b_rows) == {
        "C++",
        "Data Structures",
        "Android/Kotlin",
        "CUDA",
    }
    assert phase_2_3b_rows["C++"]["importance"] == "required"
    assert phase_2_3b_rows["Data Structures"]["importance"] == "required"
    assert phase_2_3b_rows["Android/Kotlin"]["importance"] == "preferred"
    assert phase_2_3b_rows["CUDA"]["importance"] == "preferred"

    print("JD section-heading filter smoke check passed.")
    print(f"Scoring version: {SCORING_VERSION}")
    print(f"Filtered section markers: {len(filtered)}")
    print(f"Scored requirements: {len(rows)}")


if __name__ == "__main__":
    main()
