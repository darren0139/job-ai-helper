"""Convenient, user-authored Profile & Evidence records for Job Finder.

These records are references for candidate-evidence matching, not edits to a
saved résumé or proof of unclaimed work. The existing evidence manager persists
all fields, keeping migration and new scorer logic unnecessary.
"""
from __future__ import annotations


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _comma_items(value: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for chunk in str(value or "").split(","):
        item = _clean(chunk)
        if item and item.casefold() not in seen:
            result.append(item)
            seen.add(item.casefold())
    return result


def _require(value: str, name: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{name} is required; add only facts you can substantiate.")
    return cleaned


def make_skill_evidence(*, name: str, used_for: str, work_reference: dict | None = None) -> dict:
    """Create a standalone skill record; never imply a new job or credential."""
    title = _require(name, "Skill name")
    detail = _require(used_for, "How you actually used this skill")
    subtitle = ""
    if work_reference is not None:
        if str(work_reference.get("category") or "").casefold() not in {"internship", "work experience"}:
            raise ValueError("The optional reference must be an existing work-experience item.")
        item_id = work_reference.get("id")
        if not isinstance(item_id, int) or item_id <= 0:
            raise ValueError("Work reference ID must be an existing positive evidence ID.")
        role = _require(work_reference.get("title") or "", "Work reference role")
        employer = _clean(work_reference.get("subtitle"))
        subtitle = f"Work evidence #{item_id}: {role}" + (f" — {employer}" if employer else "")
    return {
        "category": "Skill",
        "title": title,
        "description": detail,
        "subtitle": subtitle,
        "period": "",
        # The existing Job Finder matcher already projects Skill.title into
        # a structured skills claim; do not duplicate it as a second skills row.
        "skills": [],
        "tools": [],
        "impact": "",
        "source_type": "manual",
    }


def make_work_evidence(*, role: str, employer: str, period: str, description: str,
                       skills: str = "", tools: str = "") -> dict:
    """Create reference-only work history, not mutable résumé content."""
    return {
        "category": "Work Experience",
        "title": _require(role, "Position or role"),
        "subtitle": _require(employer, "Employer or organization"),
        "period": _clean(period),
        "description": _require(description, "Factual responsibilities or accomplishments"),
        "skills": _comma_items(skills),
        "tools": _comma_items(tools),
        "impact": "",
        "source_type": "manual",
    }


def render_job_finder_evidence_quick_add() -> None:
    import streamlit as st
    from database.user_profile_manager import (
        create_evidence_item,
        get_all_evidence_items_for_snapshot,
    )

    st.subheader("Standalone skills & work references for Job Finder")
    st.caption(
        "Job Finder matches saved Profile & Evidence facts, including independent "
        "skills and employment. These are reference records—not automatic edits "
        "to your original work experience or the actual résumé assessed in Phase 8. "
        "Adding evidence invalidates older Job Finder match snapshots until reanalysis."
    )

    with st.expander("Add a standalone skill (no project required)", expanded=False):
        work_items = [
            row for row in get_all_evidence_items_for_snapshot()
            if str(row.get("category") or "").casefold() in {"internship", "work experience"}
            and isinstance(row.get("id"), int)
        ]
        refs = {int(row["id"]): row for row in work_items}
        with st.form("jobfinder_standalone_skill_v1"):
            name = st.text_input("Skill or technology", key="jobfinder_skill_name_v1",
                                 placeholder="e.g. NVIDIA cuDF")
            used_for = st.text_area(
                "How did you actually use it?", key="jobfinder_skill_basis_v1",
                placeholder="Describe an actual task or experience. Do not claim broader CUDA programming if you only used cuDF.",
            )
            choices = [0, *sorted(refs)]
            reference_id = st.selectbox(
                "Related work-experience reference (optional)", choices,
                format_func=lambda val: (
                    "None — independent skill" if val == 0 else
                    f"#{val}: {refs[val].get('title', '')} — {refs[val].get('subtitle', '')}"
                ),
                key="jobfinder_skill_reference_v1",
                help="The selected source is a descriptive reference, not an automatic claim or a foreign-key link.",
            )
            save_skill = st.form_submit_button("Save standalone skill")
        if save_skill:
            try:
                payload = make_skill_evidence(
                    name=name, used_for=used_for, work_reference=refs.get(reference_id)
                )
                create_evidence_item(**payload)
            except ValueError as exc:
                st.warning(str(exc))
            else:
                st.success("Standalone skill saved. Re-analyze the job in Job Finder to refresh its match.")
                st.rerun()

    with st.expander("Add work experience as reference evidence", expanded=False):
        st.caption(
            "Enter your real experience here. Tailoring does not edit these source "
            "records. Edit them deliberately in Profile & Evidence if a correction is needed."
        )
        with st.form("jobfinder_work_reference_v1"):
            role = st.text_input("Position / role", key="jobfinder_work_role_v1")
            employer = st.text_input("Employer / organization", key="jobfinder_work_org_v1")
            period = st.text_input("Dates / period (optional)", key="jobfinder_work_period_v1")
            details = st.text_area(
                "Actual responsibilities and accomplishments", key="jobfinder_work_details_v1",
                placeholder="Use factual, independently verifiable statements, one per line.",
            )
            skills = st.text_input("Skills used (comma-separated, optional)", key="jobfinder_work_skills_v1")
            tools = st.text_input("Tools and technologies (comma-separated, optional)", key="jobfinder_work_tools_v1")
            save_work = st.form_submit_button("Save work reference")
        if save_work:
            try:
                payload = make_work_evidence(
                    role=role, employer=employer, period=period,
                    description=details, skills=skills, tools=tools,
                )
                create_evidence_item(**payload)
            except ValueError as exc:
                st.warning(str(exc))
            else:
                st.success("Work reference saved. Job Finder can use it after Analyze Match.")
                st.rerun()
