from __future__ import annotations

import tempfile
from pathlib import Path

from analysis_stability.resume_profile_stability import (
    stabilise_resume_profile_project_titles,
)
from database import db_manager
from database.analysis_cache_manager import (
    build_analysis_input_fingerprint,
    find_cached_analysis,
    save_analysis_snapshot,
)
from tailoring.tailoring_generation_fingerprint import (
    build_generation_action_plan,
    resolve_locked_sections,
)


def main() -> int:
    raw = """
PROJECTS
QueryAI (React, Team of 4) Mar 2025 - Apr 2025
• Built a help desk.
SKILLS
Python
"""
    profile = stabilise_resume_profile_project_titles(
        {"projects": [{"title": "QueryAI", "date": "", "bullets": []}]},
        raw,
    )

    approved = {
        "generation_id": "approved",
        "projects": {
            "recommended_projects": [
                {"title": "CyberSphere", "draft_bullets": ["raw", "extra"]}
            ]
        },
        "skills": {"skill_lines": [{"category": "Programming", "items": ["C++"]}]},
        "fit_result": {
            "tailored_projects_used": {
                "recommended_projects": [
                    {"title": "CyberSphere", "draft_bullets": ["raw"]}
                ]
            },
            "tailored_skills_used": {
                "skill_lines": [{"category": "Programming", "items": ["C++"]}]
            },
        },
    }
    projects, _ = resolve_locked_sections(
        proposed_projects=None,
        proposed_skills=None,
        approved_generation=approved,
        lock_projects=True,
        lock_skills=True,
    )
    plan = build_generation_action_plan(
        lock_projects=True,
        lock_skills=True,
        approved_generation=approved,
    )

    old_path = db_manager.DB_PATH
    cache_ok = False
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_manager.DB_PATH = Path(temp_dir) / "applications.db"
            fingerprint = build_analysis_input_fingerprint(
                resume_text=raw,
                jd_text="Backend engineer",
                degree="IMGD",
                actual_page_count=1,
                model_id="model-a",
            )
            save_analysis_snapshot(
                application_id=1,
                input_fingerprint=fingerprint,
                report={"overall_score": 50},
                analysis_model="model-a",
            )
            cached = find_cached_analysis(
                application_id=1,
                input_fingerprint=fingerprint,
            )
            cache_ok = (
                cached is not None
                and cached["report"]["overall_score"] == 50
            )
    finally:
        db_manager.DB_PATH = old_path

    passed = all(
        [
            profile["projects"][0]["title"]
            == "QueryAI (React, Team of 4)",
            projects["recommended_projects"][0]["draft_bullets"]
            == ["raw"],
            plan["mode"] == "load_approved",
            plan["creates_draft"] is False,
            cache_ok,
        ]
    )

    print("Title restored:", profile["projects"][0]["title"])
    print(
        "Locked fitted bullets:",
        projects["recommended_projects"][0]["draft_bullets"],
    )
    print("Both-lock action:", plan["mode"])
    print("Analysis cache:", "HIT" if cache_ok else "MISS")
    print(
        "PHASE 7 CONSISTENCY/CACHE SMOKE TEST:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
