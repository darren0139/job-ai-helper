from __future__ import annotations

import json
import os

from analysis_stability.stable_evidence_scoring import build_stable_analysis


def main() -> int:
    os.environ["CAPABILITY_RAG_MODE"] = "off"

    jd = (
        "Job Requirements\n"
        "- Experience programming in Python, TypeScript, C++, or C#"
    )
    resume_profile = {
        "education": [],
        "skills": {
            "languages": ["C++", "C#", "Python", "TypeScript"],
            "tools": [],
            "frameworks": [],
            "concepts": [],
            "platforms": [],
        },
    }
    deliberately_wrong_ai_result = {
        "present": [],
        "missing": [
            {
                "keyword": (
                    "Experience programming in Python, TypeScript, C++, or C#"
                ),
                "match_type": "missing",
                "evidence_type": "none",
                "match_reason": "Synthetic unstable AI miss.",
            }
        ],
    }

    result = build_stable_analysis(
        jd_profile={
            "required_skills": [
                "Experience programming in Python, TypeScript, C++, or C#"
            ],
            "responsibilities": [],
            "soft_skills": [],
            "preferred_skills": [],
            "deal_breakers": [],
            "tools_technologies": [],
        },
        keyword_match=deliberately_wrong_ai_result,
        raw_jd_text=jd,
        resume_profile=resume_profile,
    )

    row = result["canonical_requirements"][0]
    print(
        json.dumps(
            {
                "scoring_version": result["scoring_version"],
                "text": row["text"],
                "match_label": row["match_label"],
                "match_source": row["match_source"],
                "structured_match_status": row["structured_match_status"],
                "structured_match_kind": row.get("structured_match_kind"),
                "rag_influences_scoring": row["capability_retrieval"][
                    "influences_scoring"
                ],
            },
            indent=2,
        )
    )

    passed = (
        row["match_label"] == "direct"
        and row["match_source"] == "structured_resume_profile"
        and row["structured_match_status"] == "applied"
        and row["capability_retrieval"]["influences_scoring"] is False
    )
    print(
        "\nPHASE 6D.6 STRUCTURED MATCH SMOKE TEST:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
