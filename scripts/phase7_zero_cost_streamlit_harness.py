from __future__ import annotations

import streamlit as st

from analysis_stability.resume_profile_stability import (
    stabilise_resume_profile_project_titles,
)
from tailoring.tailoring_generation_fingerprint import (
    build_generation_action_plan,
    resolve_locked_sections,
)


st.set_page_config(page_title="Phase 7 Zero-Cost Harness", layout="wide")
st.title("Phase 7 Zero-Cost UI Harness")
st.caption("No API calls, embeddings, or DOCX rendering are used.")

approved = {
    "generation_id": "approved-demo",
    "projects": {
        "recommended_projects": [
            {
                "title": "CyberSphere",
                "draft_bullets": [
                    "Final visible bullet.",
                    "Hidden pre-fit bullet.",
                ],
            }
        ]
    },
    "skills": {
        "skill_lines": [
            {"category": "Programming", "items": ["C++", "C#"]}
        ]
    },
    "fit_result": {
        "page_count": 1,
        "fit_one_page": True,
        "tailored_projects_used": {
            "recommended_projects": [
                {
                    "title": "CyberSphere",
                    "draft_bullets": ["Final visible bullet."],
                }
            ]
        },
        "tailored_skills_used": {
            "skill_lines": [
                {"category": "Programming", "items": ["C++"]}
            ]
        },
    },
}

lock_projects = st.checkbox("Lock approved Projects", value=True)
lock_skills = st.checkbox("Lock approved Skills", value=True)
plan = build_generation_action_plan(
    lock_projects=lock_projects,
    lock_skills=lock_skills,
    approved_generation=approved,
)
st.write("### Expected main action")
st.json(plan)

projects, skills = resolve_locked_sections(
    proposed_projects={
        "recommended_projects": [
            {"title": "New Project", "draft_bullets": ["Generated."]}
        ]
    },
    proposed_skills={
        "skill_lines": [
            {"category": "Programming", "items": ["Python"]}
        ]
    },
    approved_generation=approved,
    lock_projects=lock_projects,
    lock_skills=lock_skills,
)
st.write("### Effective content")
left, right = st.columns(2)
left.json(projects)
right.json(skills)

raw = """
PROJECTS
QueryAI (React, Team of 4) Mar 2025 - Apr 2025
• Built a help desk.
SKILLS
Python
"""
stable = stabilise_resume_profile_project_titles(
    {"projects": [{"title": "QueryAI", "date": "", "bullets": []}]},
    raw,
)
st.write("### Project-title stability")
st.json(stable)

if plan["mode"] == "load_approved":
    st.success(
        "PASS: both locks load the approved final content without AI "
        "and without a new draft."
    )
else:
    st.info(
        "The unlocked section would be generated; the locked section "
        "would reuse the approved final output."
    )
