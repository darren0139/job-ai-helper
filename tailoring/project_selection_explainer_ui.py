"""Read-only, human-facing explanation of saved deterministic Project selection.

Only saved project-ranking receipts are displayed. JD wording and matched
capabilities are not interchangeable with lexical trigger/keyword claims.
"""
from __future__ import annotations

from typing import Any


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _title(row: dict[str, Any]) -> str:
    return _clean(row.get("display_title") or row.get("title"))


def _matches(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [v for v in (row.get("requirement_matches") or []) if isinstance(v, dict)
            and _clean(v.get("match_label")).lower() in {"direct", "transferable", "weak"}]


def _unique(values: list[str]) -> str:
    return " | ".join(dict.fromkeys(value for value in values if value))


def _project_identity(row: dict[str, Any]) -> str:
    return _clean(row.get("project_id")) or "title:" + _title(row).casefold()


def project_explanation_tables(projects: dict[str, Any]) -> dict[str, Any]:
    """Make deterministic rank/selection and evidence tables, without re-ranking."""
    if not isinstance(projects, dict):
        return {"summary": [], "details": [], "notices": ["No saved Projects output available"]}
    ranked = projects.get("candidate_project_ranking")
    generated = projects.get("recommended_projects") or []
    if not isinstance(generated, list) or not all(isinstance(p, dict) for p in generated):
        return {"summary": [], "details": [], "notices": ["Saved Project selection is malformed"]}
    generated_keys = {_project_identity(p) for p in generated}
    # Never guess a ranking order from a list sorted for display by date.
    saved_rank_available = isinstance(ranked, list) and bool(ranked)
    if saved_rank_available and not all(isinstance(p, dict) for p in ranked):
        return {"summary": [], "details": [], "notices": ["Saved Project ranking is malformed"]}
    candidates = ranked if saved_rank_available else generated
    summary = []
    details = []
    for index, row in enumerate(candidates, start=1):
        pid = _project_identity(row)
        name = _title(row)
        if not name:
            continue
        selected = pid in generated_keys
        matches = _matches(row)
        jd_requirements = _unique([_clean(m.get("requirement_text")) for m in matches])
        capabilities = _unique([_clean(m.get("capability_id")) for m in matches])
        snippets = _unique([
            _clean(raw)
            for m in matches
            for raw in (m.get("evidence_snippets") or [])
            if isinstance(raw, str)
        ])
        selection_order = row.get("selection_rank")
        recorded_score = row.get("final_score", row.get("project_fit_score"))
        reason = _clean(row.get("reason") or row.get("why_relevant"))
        if not reason:
            reason = "Saved ranking explanation unavailable"
        rec = _clean(row.get("recommendation"))
        if rec not in {"include", "deprioritize", "exclude"}:
            rec = "selected" if selected else "not generated"
        # A saved candidate rank is not necessarily the final fit-time choice.
        summary.append({
            "Candidate order": index if saved_rank_available else None,
            "Selection rank": selection_order,
            "Project": name,
            "Generated": "Yes" if selected else "No",
            "Decision": rec,
            "Deterministic project score": recorded_score,
            "Canonical coverage points": row.get("deterministic_coverage_score"),
            "Unique coverage bonus": row.get("unique_coverage_bonus"),
            "Overlap penalty": row.get("overlap_penalty"),
            "Matched JD requirements": jd_requirements,
            "Recognized capabilities": capabilities,
            "Reason (saved evidence map)": reason,
        })
        for match in matches:
            evidence_ids = match.get("evidence_ids") or []
            details.append({
                "Project": name,
                "Generated": "Yes" if selected else "No",
                "Requirement": _clean(match.get("requirement_text")),
                "Requirement ID": _clean(match.get("requirement_id")),
                "Importance": _clean(match.get("importance")),
                "Evidence match": _clean(match.get("match_label")),
                "Coverage points": match.get("coverage_points"),
                "Capability ID": _clean(match.get("capability_id")),
                "Evidence excerpts": _unique([_clean(s) for s in (match.get("evidence_snippets") or []) if isinstance(s, str)]),
                "Evidence record IDs": _unique([_clean(s) for s in evidence_ids]),
                "Resolver source": _clean(match.get("source")),
            })
    notices = []
    if not saved_rank_available:
        notices.append("Complete candidate ranking was not saved; showing generated projects only, with no inferred rank or exclusions.")
    if not details:
        notices.append("No direct/transferable/weak canonical JD evidence links were stored for these projects. Do not infer matched keywords from titles.")
    return {"summary": summary, "details": details, "notices": notices,
            "ranking_available": saved_rank_available,
            "generated_count": len(generated),
            "candidate_count": len(candidates)}


def render_project_selection_explainer(
    st: Any, projects: dict[str, Any], *, application_id: int,
    phase9f_execution: dict[str, Any] | None = None,
    current_phase9e_decision: dict[str, Any] | None = None,
) -> bool:
    tables = project_explanation_tables(projects)
    if not tables["summary"]:
        return False
    with st.expander("Before fitting — Why these Projects were generated (ranking and JD evidence)", expanded=True):
        st.caption(
            "The saved Python ranking uses canonical JD requirement matches, evidence strength, "
            "unique-coverage bonuses, overlap penalties and stable near-tie rules. "
            "The terms shown below are *matched JD requirements and approved capabilities*, "
            "not a new keyword scan or proof that a word alone caused selection."
        )
        st.caption(f"{tables['generated_count']} project(s) generated from "
                   f"{tables['candidate_count']} saved candidate(s). "
                   "Generated selection, manual fit selection and one-page retention are different stages.")
        from tailoring.phase9f_explainer_clarity_v2_2 import project_selection_summary
        choice = project_selection_summary(projects)
        if choice["rows"]:
            st.write("**Why each project was chosen**")
            st.caption(choice["notice"] + " · Selection source: " + choice["selection_source"])
            st.dataframe(choice["rows"], hide_index=True, width="stretch")
        else:
            st.caption("Selection-basis table withheld: " + choice["notice"])
        from tailoring.phase9f_project_bullet_sources_v2_3 import (
            render_project_bullet_source_comparison,
        )
        render_project_bullet_source_comparison(
            st, projects, application_id=application_id,
            phase9f_execution=phase9f_execution,
            current_phase9e_decision=current_phase9e_decision,
        )
        st.divider()
        show_advanced = st.checkbox(
            "Show full ranking, coverage and requirement evidence",
            value=False, key=f"phase9f_project_explainer_advanced_{int(application_id)}",
        )
        if show_advanced:
            st.dataframe(tables["summary"], hide_index=True, width="stretch")
        for notice in tables["notices"]:
            st.caption(notice)
        if tables["details"] and show_advanced:
            st.write("**Full requirement-to-project evidence records**")
            st.dataframe(tables["details"], hide_index=True, width="stretch")
        debug = projects.get("selection_debug") or {}
        if isinstance(debug, dict) and debug:
            st.caption("Saved selection owner: " + _clean(debug.get("selection_owner") or "unavailable")
                       + " · Ranking version: " + _clean(debug.get("ranking_version") or "unavailable"))
        st.caption("An unrecognized requirement, weak match, or fallback selection must not be presented as a direct capability match.")
    return True
