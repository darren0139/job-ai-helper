"""Presentation-only Phase 9F baseline labels and fitted project-retention audit.

Never recompute scores, infer lexical triggers, mutate a saved generation, or
confuse pre-generation rank with post-fit visible content.
"""
from __future__ import annotations

from typing import Any


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def phase8_baseline_mode(result: dict[str, Any] | None) -> str:
    """Return selected_base only on exact saved Phase 9F and Phase 8 equality.

    True document-based Initial Analysis always keeps its original name, even
    when a different selected base also exists.
    """
    if not isinstance(result, dict):
        return "baseline"
    if isinstance(result.get("document_analysis"), dict):
        return "initial"
    try:
        app = int(result.get("application_id") or 0)
        if app <= 0:
            return "baseline"
        from tailoring.phase9f_session_handoff import load_confirmed_source_view
        base = load_confirmed_source_view(app)
        if not isinstance(base, dict):
            return "baseline"
        from tailoring.phase9f_base_vs_tailored_explainer import verify_selected_base_phase8_pair
        pair = verify_selected_base_phase8_pair(base, result, application_id=app)
        return "selected_base" if pair.get("comparison_valid") is True else "baseline"
    except (ValueError, KeyError, TypeError, RuntimeError, OSError):
        return "baseline"




def document_phase8_comparison_sections(result: dict[str, Any] | None) -> list[tuple[str, dict[str, Any] | None]]:
    """Read-only display order determined by saved identities, not entry page.

    An actual-document Initial receipt stays frozen. If a *different* selected
    Base is verified in Phase 8, show its comparison first and the Initial
    history second. A same-document Base is not displayed twice.
    """
    if not isinstance(result, dict) or not isinstance(result.get("document_analysis"), dict):
        return []
    initial = result.get("job_match_ab")
    selected = result.get("selected_base_analysis")
    if not isinstance(selected, dict):
        return [("Initial vs Final", initial)]
    if selected.get("same_as_initial") is True:
        return [("Initial / Selected Base vs Final", initial)]
    return [
        ("Selected Base vs Final", result.get("selected_base_job_match_ab")),
        ("Initial vs Final", initial),
    ]


def confirmed_phase9f_session(application_id: int) -> bool:
    """Determine the Tailor Resume entry path from confirmed, validated source.

    An application ID alone or a cached UI flag never authorizes this label.
    """
    try:
        from tailoring.phase9f_session_handoff import load_confirmed_source_view
        view = load_confirmed_source_view(int(application_id))
        return bool(isinstance(view, dict) and view.get("confirmation_id") and view.get("selected"))
    except (ValueError, KeyError, TypeError, OSError):
        return False


def _project_key(row: dict[str, Any]) -> str:
    # Stable explicit project ID when available; fallback to normalized name.
    pid = _clean(row.get("project_id"))
    if pid:
        return "id:" + pid
    title = _clean(row.get("title") or row.get("display_title"))
    return "title:" + title.casefold() if title else ""


def _project_title(row: dict[str, Any]) -> str:
    return _clean(row.get("display_title") or row.get("title"))


def _bullets(row: dict[str, Any]) -> list[str]:
    values = row.get("draft_bullets") or []
    return [_clean(item) for item in values if isinstance(item, str) and _clean(item)] if isinstance(values, list) else []


def project_fit_retention_rows(
    projects: dict[str, Any] | None, fit_result: dict[str, Any] | None
) -> dict[str, Any]:
    """Compare generated project IDs and bullets with saved *final fit* payload.

    The generated order is not a deterministic relevance ranking; callers
    should use the separate candidate_project_ranking table for that.
    """
    generated = (projects or {}).get("recommended_projects") if isinstance(projects, dict) else None
    if not isinstance(generated, list) or not generated or not all(isinstance(r, dict) for r in generated):
        return {"rows": [], "notice": "No saved generated Projects output to compare."}
    if not isinstance(fit_result, dict):
        return {"rows": [], "notice": "No fitted result saved yet. Generated Projects are not proof of final retention."}
    used = fit_result.get("tailored_projects_used")
    if (fit_result.get("fit_one_page") is not True
            or int(fit_result.get("page_count") or 0) != 1
            or not _clean(fit_result.get("docx_path"))
            or not isinstance(used, dict)
            or not isinstance(used.get("recommended_projects"), list)):
        return {"rows": [], "notice": "A verified one-page fitted Projects payload is unavailable; final visible projects cannot be inferred."}
    fitted = used["recommended_projects"]
    if not all(isinstance(r, dict) for r in fitted):
        return {"rows": [], "notice": "Saved final fit Projects are malformed; nothing inferred."}
    # IDs may be absent from older outputs. Never let a missing / duplicate ID
    # silently turn a genuinely retained project into a reported removal.
    before_map = {}
    after_map = {}
    for row in generated:
        key = _project_key(row)
        if not key or key in before_map:
            return {"rows": [], "notice": "Generated project identities are missing or ambiguous."}
        before_map[key] = row
    for row in fitted:
        key = _project_key(row)
        if not key or key in after_map:
            return {"rows": [], "notice": "Fitted project identities are missing or ambiguous."}
        after_map[key] = row
    # Title-only fallback is acceptable only when unique across both collections;
    # project IDs take priority and a conflicting identity is not guessed.
    unmatched_fitted = set(after_map) - set(before_map)
    rows = []
    for generated_row in generated:
        key = _project_key(generated_row)
        fit_row = after_map.get(key)
        before_bullets = _bullets(generated_row)
        final_bullets = _bullets(fit_row) if fit_row is not None else []
        if fit_row is None:
            status = "Not retained in final fit"
        elif before_bullets == final_bullets:
            status = "Retained unchanged"
        elif len(final_bullets) < len(before_bullets):
            status = "Retained with fewer bullets"
        else:
            status = "Retained; wording/allocation differs"
        rows.append({
            "Project": _project_title(generated_row),
            "Generated": "Yes",
            "Final fitted": "Yes" if fit_row is not None else "No",
            "Project outcome": status,
            "Generated bullets": len(before_bullets),
            "Fitted bullets": len(final_bullets) if fit_row is not None else 0,
            "Exact preserved bullets": sum(1 for b in before_bullets if b in final_bullets),
            "Reason": ("Stage of removal not proven: manual selection or fitting"
                       if fit_row is None else
                       "Observed saved bullet difference; cause not inferred" if before_bullets != final_bullets else
                       "No content change in saved project bullets"),
        })
    if unmatched_fitted:
        return {"rows": [], "notice": "Final fitted Projects contain identities not found in the saved generated set; comparison withheld."}
    return {"rows": rows,
            "notice": "Generated order is not relevance rank. Final fitted contents are taken from the saved one-page fit payload; whether manual selection or fitting removed content is not inferred."}


def render_project_fit_retention(st: Any, projects: dict[str, Any] | None,
                                 fit_result: dict[str, Any] | None, *, application_id: int) -> bool:
    """Explain real saved fit-stage reductions; never mislabel fit input as output."""
    from tailoring.phase9f_explainer_clarity_v2_2 import fit_stage_summary
    snapshot = fit_stage_summary(projects, fit_result)
    with st.expander("After fitting — Project selection, reductions and fitted content", expanded=True):
        st.caption("The selector chooses projects first; the generated draft and fitter starting pool are separate stages. The last columns show final ACTIVE fit reductions, not an unverified manual-vs-fitter guess.")
        if snapshot["rows"]:
            st.dataframe(snapshot["rows"], hide_index=True, width="stretch")
        else:
            st.info("Exact fitted-project attribution unavailable for this saved receipt.")
        st.caption(snapshot["notice"])
    return bool(snapshot["rows"])
