"""Streamlit confirmation bridge from transient Phase 9F-A/B/C to a session."""

from __future__ import annotations

import uuid
from typing import Any, Callable

import streamlit as st

from database.db_manager import get_application_by_id
from database.jd_library_manager import (
    get_exact_job_description_version,
    save_job_description_to_library,
)
from database.phase9f_application_confirmation_manager import (
    confirm_phase9f_application_session,
)
from rag.jd_chroma_rag import index_job_description_to_chroma
from tailoring.phase9f_application_confirmation import (
    Phase9FDConfirmationError,
)
from tailoring.phase9f_jd_intake import build_saved_exact_jd_snapshot


INTENSITY_LABELS = {
    "reuse": "Reuse",
    "minor": "Minor",
    "full": "Full",
}
LABEL_TO_INTENSITY = {value: key for key, value in INTENSITY_LABELS.items()}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def prepare_persisted_exact_jd_for_confirmation(
    phase9f_a_snapshot: dict[str, Any],
    *,
    save_fn: Callable[..., dict[str, Any]] = save_job_description_to_library,
    index_fn: Callable[[int], int] = index_job_description_to_chroma,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """PRE-D: save/reuse the exact JD only after explicit confirmation."""
    library_jd_id = int(phase9f_a_snapshot.get("library_jd_id") or 0)
    version_id = _clean(phase9f_a_snapshot.get("source_version_id"))
    receipt: dict[str, Any] = {
        "created_new_job": False,
        "created_new_version": False,
        "needs_chroma_index": False,
        "chroma_indexing_occurred": False,
        "chroma_indexed_chunk_count": 0,
        "chroma_indexing_error": "",
    }
    exact = None
    if library_jd_id > 0 and version_id:
        exact = get_exact_job_description_version(library_jd_id, version_id)
        if exact is not None and str(exact.get("raw_text") or "") != str(
            phase9f_a_snapshot.get("raw_text") or ""
        ):
            exact = None

    if exact is None:
        receipt.update(
            save_fn(
                raw_text=str(phase9f_a_snapshot.get("raw_text") or ""),
                jd_profile=dict(phase9f_a_snapshot.get("jd_profile") or {}),
                title=str(phase9f_a_snapshot.get("job_title") or ""),
                company=str(phase9f_a_snapshot.get("company") or ""),
                location=str(phase9f_a_snapshot.get("location") or ""),
                source_url=str(phase9f_a_snapshot.get("source_url") or ""),
            )
        )
        library_jd_id = int(receipt.get("job_description_id") or 0)
        version_id = _clean(receipt.get("source_version_id"))
        if receipt.get("needs_chroma_index"):
            try:
                receipt["chroma_indexed_chunk_count"] = int(
                    index_fn(library_jd_id)
                )
                receipt["chroma_indexing_occurred"] = True
            except Exception as exc:  # JD persistence remains authoritative
                receipt["chroma_indexing_error"] = str(exc)
        exact = get_exact_job_description_version(library_jd_id, version_id)

    if exact is None:
        raise Phase9FDConfirmationError(
            "PRE-D could not resolve the exact persisted JD version.",
            code="pre_d_exact_jd_unavailable",
        )
    persisted = build_saved_exact_jd_snapshot(exact)
    if (
        _clean(persisted.get("raw_jd_sha256"))
        != _clean(phase9f_a_snapshot.get("raw_jd_sha256"))
        or _clean(persisted.get("canonical_requirement_fingerprint"))
        != _clean(
            phase9f_a_snapshot.get("canonical_requirement_fingerprint")
        )
        or persisted.get("jd_profile")
        != phase9f_a_snapshot.get("jd_profile")
    ):
        raise Phase9FDConfirmationError(
            "PRE-D persisted a JD that differs from the analyzed Phase 9F-A snapshot.",
            code="pre_d_exact_jd_mismatch",
        )
    receipt["job_description_id"] = int(persisted["library_jd_id"])
    receipt["source_version_id"] = persisted["source_version_id"]
    receipt["exact_existing_version_reused"] = not bool(
        receipt.get("created_new_job") or receipt.get("created_new_version")
    )
    return persisted, receipt


def _candidate_label(candidate: dict[str, Any]) -> str:
    return (
        f"#{int(candidate.get('rank') or 0)} · "
        f"{_clean(candidate.get('source_display_name')) or 'Immutable source'} "
        f"· {_clean(candidate.get('source_type')).replace('_', ' ').title()}"
    )


def _render_selected_metrics(candidate: dict[str, Any]) -> None:
    with st.container(horizontal=True):
        st.metric(
            "Current JD alignment",
            f"{int(candidate.get('deterministic_alignment_score') or 0)}%",
            border=True,
        )
        st.metric(
            "Required/Core",
            f"{int(candidate.get('required_core_coverage_score') or 0)}%",
            border=True,
        )
        st.metric(
            "Evidence strength",
            f"{int(candidate.get('evidence_strength_score') or 0)}%",
            border=True,
        )
        st.metric(
            "Important gaps",
            int(candidate.get("important_gap_count") or 0),
            border=True,
        )


def render_phase9f_application_confirmation(
    *,
    phase9f_a_snapshot: dict[str, Any],
    ranking_result: dict[str, Any],
    phase9f_c_recommendation: dict[str, Any],
) -> None:
    """Render a passive confirmation form; write only on the primary action."""
    if phase9f_c_recommendation.get("status") != "recommended":
        return
    candidates = list(ranking_result.get("ranked_candidates") or [])
    if not candidates:
        return
    ranking_fingerprint = _clean(ranking_result.get("ranking_fingerprint"))
    recommended = candidates[0]
    recommended_intensity = _clean(
        phase9f_c_recommendation.get("recommended_intensity")
    )

    st.divider()
    st.subheader("Create Application Session")
    st.caption(
        "Confirm the exact JD, immutable starting source, and tailoring "
        "intensity. This configures the existing Application Session only; "
        "it does not start tailoring, fitting, approval, or verification."
    )
    with st.container(border=True):
        st.write("**Recommended starting source**")
        st.write(_candidate_label(recommended))
        st.caption(
            "Recommended tailoring for this source: "
            f"{INTENSITY_LABELS.get(recommended_intensity, recommended_intensity)}"
        )
        candidate_by_fingerprint = {
            _clean(row.get("normalized_source_fingerprint")): row
            for row in candidates
        }
        selected_fingerprint = st.selectbox(
            "Starting source",
            list(candidate_by_fingerprint),
            index=0,
            format_func=lambda value: _candidate_label(
                candidate_by_fingerprint[value]
            ),
            key=f"phase9f_d_source_{ranking_fingerprint[:16]}",
        )
        selected = candidate_by_fingerprint[selected_fingerprint]
        selected_is_winner = (
            _clean(selected.get("normalized_source_fingerprint"))
            == _clean(recommended.get("normalized_source_fingerprint"))
        )
        if not selected_is_winner:
            st.warning(
                "You selected a different ranked source. The Phase 9F-C "
                "recommendation above remains tied to the original rank-one "
                "source; choose an intensity explicitly for this source."
            )
        if _clean(selected.get("role_family_relationship")) == "cross_family":
            st.warning(
                "This Global Blueprint belongs to a different role family. "
                "Its actual current-JD evidence is shown below; no source "
                "substitution will occur."
            )
        _render_selected_metrics(selected)

        intensity_key = (
            "phase9f_d_intensity_"
            f"{ranking_fingerprint[:12]}_"
            f"{_clean(selected.get('normalized_source_fingerprint'))[:12]}"
        )
        options = list(INTENSITY_LABELS.values())
        default_index = (
            options.index(INTENSITY_LABELS[recommended_intensity])
            if selected_is_winner and recommended_intensity in INTENSITY_LABELS
            else None
        )
        selected_label = st.selectbox(
            "Tailoring intensity",
            options,
            index=default_index,
            placeholder="Choose Reuse, Minor, or Full",
            key=intensity_key,
        )
        confirmed_intensity = LABEL_TO_INTENSITY.get(selected_label or "", "")

        intent_key = f"phase9f_d_intent_{ranking_fingerprint}"
        st.session_state.setdefault(intent_key, uuid.uuid4().hex)
        if st.button(
            "Confirm and create Application Session",
            type="primary",
            width="stretch",
            disabled=not bool(confirmed_intensity),
            key=f"phase9f_d_confirm_{ranking_fingerprint[:16]}",
        ):
            try:
                persisted_jd, preparation = (
                    prepare_persisted_exact_jd_for_confirmation(
                        phase9f_a_snapshot
                    )
                )
                result = confirm_phase9f_application_session(
                    phase9f_a_snapshot=phase9f_a_snapshot,
                    persisted_exact_jd_snapshot=persisted_jd,
                    ranking_result=ranking_result,
                    phase9f_c_recommendation=phase9f_c_recommendation,
                    confirmed_normalized_source_fingerprint=_clean(
                        selected.get("normalized_source_fingerprint")
                    ),
                    confirmed_intensity=confirmed_intensity,
                    application_intent_id=st.session_state[intent_key],
                )
                application_id = int(
                    result["confirmation"]["application_id"]
                )
                application = get_application_by_id(application_id)
                if application is None or not isinstance(
                    application.get("report"), dict
                ):
                    raise RuntimeError(
                        "The committed Application Session could not be loaded."
                    )
                st.session_state["current_application_id"] = application_id
                st.session_state["latest_report"] = application["report"]
                st.session_state["resume_filename"] = application.get(
                    "resume_filename", ""
                )
                st.session_state["cover_letter"] = application.get(
                    "cover_letter", ""
                )
                st.session_state["phase9f_d_confirmation_receipt"] = {
                    "application_id": application_id,
                    "cache_status": result["cache_status"],
                    "preparation": preparation,
                }
                st.session_state["flash_message"] = (
                    f"Application Session #{application_id} is configured "
                    "with the exact confirmed JD and starting source."
                )
                st.session_state["_pending_navigation_page"] = (
                    "Application Sessions"
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Could not create the Application Session: {exc}")
