"""Zero-cost smoke check for the Phase 9F-A transient JD contract."""

from tailoring.phase9f_jd_intake import build_transient_exact_jd_snapshot


RAW_JD = """
AI Full-Stack Software Engineer
Build secure user-facing applications with Python, React, TypeScript,
PostgreSQL, API authentication, automated tests, and cloud deployment.
Collaborate across engineering and product teams to deliver reliable services.
Python and React are required. Database design and secure access are core.
Container deployment experience is preferred.
""".strip()

PROFILE = {
    "job_title": "AI Full-Stack Software Engineer",
    "company": "Smoke Check Company",
    "location": "Singapore",
    "experience_level": "Junior",
    "responsibilities": ["Build secure full-stack applications."],
    "required_skills": ["Python", "React", "PostgreSQL"],
    "preferred_skills": ["Cloud deployment"],
    "tools_technologies": ["Python", "React", "TypeScript", "PostgreSQL"],
    "soft_skills": ["Collaboration"],
    "buzzwords": [],
    "deal_breakers": [],
}


def main() -> None:
    first = build_transient_exact_jd_snapshot(
        raw_text=RAW_JD,
        jd_profile=PROFILE,
        source_type="pasted",
    )
    second = build_transient_exact_jd_snapshot(
        raw_text=RAW_JD,
        jd_profile=PROFILE,
        source_type="pasted",
    )
    assert first["snapshot_fingerprint"] == second["snapshot_fingerprint"]
    assert first["canonical_requirements"]
    assert first["role_family"]["role_family_id"] == (
        "ai_fullstack_software_engineering"
    )
    assert first["model_call_count"] == 0
    assert first["embedding_call_count"] == 0
    assert "final_scoring_seed" not in first
    print(
        "Phase 9F-A smoke passed: "
        f"requirements={len(first['canonical_requirements'])} "
        "family=ai_fullstack_software_engineering "
        "model_calls=0 embedding_calls=0"
    )


if __name__ == "__main__":
    main()
