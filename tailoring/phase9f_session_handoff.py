"""Read-only presentation and guarded normal-fit policy for Phase 9F handoff.

Phase 9F-B analysed immutable resume sources for the exact JD. That is not an
explicit uploaded-document Initial Resume Analysis. Never infer the latter.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def confirmed_source_view(confirmation: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate a persisted Phase 9F-D source/analysis receipt without rescoring.

    Raises ValueError on missing or contradictory saved provenance. Never repairs,
    persists, or recomputes canonical requirements or match labels.
    """
    if not isinstance(confirmation, dict):
        return None
    snap = confirmation.get("confirmation_snapshot") or {}
    if not isinstance(snap, dict) or not snap:
        return None
    ranking = snap.get("phase9f_b_ranking_result") or {}
    selected = snap.get("selected_candidate") or {}
    decision = snap.get("phase9e_exact_decision") or {}
    if not all(isinstance(value, dict) and value for value in (ranking, selected, decision)):
        raise ValueError("Saved Phase 9F-D handoff has missing source receipts")
    if snap.get("semantic_identity") != confirmation.get("semantic_identity"):
        raise ValueError("Saved Phase 9F-D confirmation identity mismatch")
    if decision.get("decision_fingerprint") != confirmation.get("phase9e_decision_fingerprint"):
        raise ValueError("Saved Phase 9F-D decision identity mismatch")
    starting = decision.get("starting_snapshot") or {}
    if (starting.get("starting_snapshot_fingerprint")
            != confirmation.get("starting_snapshot_fingerprint")):
        raise ValueError("Saved Phase 9F-D starting source identity mismatch")
    source_identity = starting.get("source_identity") or {}
    if source_identity.get("normalized_source_fingerprint") != selected.get("normalized_source_fingerprint"):
        raise ValueError("Saved Phase 9F-D selected source mismatch")

    from tailoring.phase9f_starting_source_ranking import (
        Phase9FBRankingError,
        validate_ranked_candidate_analysis_snapshot,
        validate_ranked_result_contract,
    )
    try:
        validate_ranked_result_contract(
            ranking,
            expected_ranking_input_fingerprint=str(ranking.get("ranking_input_fingerprint") or ""),
        )
        validated = validate_ranked_candidate_analysis_snapshot(selected)
    except (Phase9FBRankingError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Saved Phase 9F source evidence failed verification") from exc
    rows = ranking.get("ranked_candidates") or []
    fingerprint = str(selected.get("normalized_source_fingerprint") or "")
    matches = [row for row in rows if row.get("normalized_source_fingerprint") == fingerprint]
    if len(matches) != 1 or matches[0].get("candidate_analysis_snapshot_fingerprint") != selected.get("candidate_analysis_snapshot_fingerprint"):
        raise ValueError("Selected source not uniquely present in frozen comparison")

    analysis = validated["candidate_analysis_snapshot"]
    if (analysis.get("resume_text_snapshot") != starting.get("resume_text_snapshot")
            or analysis.get("resume_profile_snapshot") != starting.get("resume_profile_snapshot")):
        raise ValueError("Frozen analysed source differs from bound starting source")
    comparison = []
    for row in rows:
        comparison.append({
            "Rank": int(row.get("rank") or 0),
            "Starting source": str(row.get("source_display_name") or "Immutable resume"),
            "Type": str(row.get("source_type") or ""),
            "Version": int(row.get("source_version") or 0),
            "Job Match": int(row.get("deterministic_alignment_score") or 0),
            "Required/Core": int(row.get("required_core_coverage_score") or 0),
            "Preferred": int(row.get("preferred_coverage_score") or 0),
            "Evidence strength": int(row.get("evidence_strength_score") or 0),
            "Important gaps": int(row.get("important_gap_count") or 0),
            "Selected": "Yes" if row.get("normalized_source_fingerprint") == fingerprint else "",
        })
    return {
        "selected": deepcopy(selected),
        "analysis": deepcopy(analysis["stable_analysis_snapshot"]),
        "raw_jd_text": str(analysis["raw_jd_text_snapshot"]),
        "comparison": comparison,
        "confirmation_id": str(confirmation.get("confirmation_id") or ""),
        "ranking_fingerprint": str(ranking.get("ranking_fingerprint") or ""),
    }


def load_confirmed_source_view(application_id: int) -> dict[str, Any] | None:
    from database.phase9f_application_confirmation_manager import get_phase9f_application_confirmation
    return confirmed_source_view(get_phase9f_application_confirmation(int(application_id)))


def render_phase9f_selected_source_analysis(st: Any, application_id: int) -> bool:
    """Display existing JD-to-starting-source analysis, without calling Analyze Resume."""
    try:
        view = load_confirmed_source_view(application_id)
    except (ValueError, KeyError, TypeError) as exc:
        st.warning("Saved Phase 9F starting-source analysis is unavailable: " + str(exc))
        return False
    if view is None:
        return False
    with st.expander("Phase 9F selected starting-source analysis", expanded=False):
        source = view["selected"]
        st.write("**Selected source:** " + str(source.get("source_display_name") or "Immutable resume"))
        st.caption("Frozen exact-JD starting-source analysis reused from Tailor Resume. No AI, scoring or persistence calls. This is not an independently uploaded Application résumé document receipt.")
        # This pane is intentionally simple: do not nest the full Initial
        # Analysis presenter (which itself opens an expander) inside a second
        # Streamlit expander. The saved B metrics are not recomputed.
        from analysis_stability.requirement_presentation import score_value, score_text
        analysis = view["analysis"]
        metrics = st.columns(4)
        for column, label, field in zip(metrics,
            ("Job Match", "Required/Core", "Preferred", "Evidence strength"),
            ("deterministic_alignment_score", "required_core_coverage_score",
             "preferred_coverage_score", "evidence_strength_score")):
            column.metric(label, score_text(score_value(analysis, field)))
        rows = analysis.get("canonical_requirements") or []
        st.dataframe([{
            "Requirement": str(row.get("text") or ""),
            "Importance": str(row.get("importance") or ""),
            "Match": str(row.get("match_label") or "none"),
            "Requirement ID": str(row.get("requirement_id") or ""),
        } for row in rows if isinstance(row, dict)],
            hide_index=True, width="stretch")
        st.caption("Frozen Phase 9F-D confirmation " + view["confirmation_id"] + ". The exact selected source, canonical rows and scores are inspected without rescoring.")
    return True


def render_phase9f_source_comparison(st: Any, application_id: int) -> bool:
    """Persisted, read-only ranking from the exact confirmed Phase 9F-D decision."""
    try:
        view = load_confirmed_source_view(application_id)
    except (ValueError, KeyError, TypeError) as exc:
        st.warning("Saved Phase 9F source comparison is unavailable: " + str(exc))
        return False
    if view is None:
        return False
    with st.expander("Confirmed Phase 9F starting-source comparison (read-only)", expanded=False):
        st.caption("Exact comparison saved when the tailoring base was confirmed. No recomputation, source change, or new analysis. Other sources shown here are historical candidates, not the current binding.")
        st.dataframe(view["comparison"], hide_index=True, width="stretch")
    return True


def normal_fit_selection_lock_reason(
    *,
    execution_active: bool,
    normal_lifecycle: bool,
    addressable: bool,
    fit_frozen: bool,
    workspace_edit_required: bool,
    legacy_section_locked: bool,
) -> str:
    """The fitting path, not the D binding's initial section lock, owns policy."""
    if workspace_edit_required:
        return "Approved or historical workspace requires an explicit editable draft"
    if execution_active:
        if not normal_lifecycle:
            return "Historical private Phase 9F execution cannot be rewritten as a normal fit"
        if not addressable:
            return "Section is not addressable in the frozen Phase 9F evidence scope"
        if fit_frozen:
            return "The fitted output is frozen; revise via a new normal draft"
        return ""
    if legacy_section_locked:
        return "The legacy Application Session section is locked"
    return ""
