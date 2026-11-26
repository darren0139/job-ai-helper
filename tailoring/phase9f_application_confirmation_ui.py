"""Streamlit confirmation bridge from transient Phase 9F-A/B/C to a session."""

from __future__ import annotations

import uuid
import json
from typing import Any, Callable

import streamlit as st

from tailoring.phase9f_navigation_state import navigation_selectbox

from database.db_manager import get_application_by_id, list_job_finder_application_bindings
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
from tailoring.phase9f_pre_d_diagnostics import build_pre_d_mismatch_diagnostics


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
        exact = get_exact_job_description_version(library_jd_id, version_id)

    if exact is None:
        raise Phase9FDConfirmationError(
            "PRE-D could not resolve the exact persisted JD version.",
            code="pre_d_exact_jd_unavailable",
        )
    persisted = build_saved_exact_jd_snapshot(
        exact,
        preferred_requirements=(
            phase9f_a_snapshot.get("application_local_jd_user_inputs") or {}
        ).get("preferred_requirement_overrides"),
    )
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
        error = Phase9FDConfirmationError(
            "PRE-D persisted a JD that differs from the analyzed Phase 9F-A snapshot.",
            code="pre_d_exact_jd_mismatch",
        )
        try:
            error.pre_d_diagnostics = build_pre_d_mismatch_diagnostics(
                phase9f_a_snapshot, exact, persisted, receipt
            )
        except Exception as diagnostic_error:
            error.pre_d_diagnostics = {
                "error_code": "pre_d_exact_jd_mismatch",
                "confirmation_blocked": True,
                "diagnostic_error_type": type(diagnostic_error).__name__,
            }
        raise error
    if receipt.get("needs_chroma_index"):
        try:
            receipt["chroma_indexed_chunk_count"] = int(
                index_fn(library_jd_id)
            )
            receipt["chroma_indexing_occurred"] = True
        except Exception as exc:  # JD persistence remains authoritative
            receipt["chroma_indexing_error"] = str(exc)
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
    st.subheader("Configure Application Session")
    st.caption(
        "Confirm the exact JD, immutable starting source, and tailoring "
        "intensity. Choose an existing Job Finder session or create a new one; "
        "it does not start tailoring, fitting, approval, or verification."
    )
    with st.container(border=True):
        st.write("**Recommended starting source**")
        st.write(_candidate_label(recommended))
        st.caption(
            "Recommended tailoring for this source: "
            f"{INTENSITY_LABELS.get(recommended_intensity, recommended_intensity)}"
        )
        exact_reuse = recommended.get("exact_verified_reuse") or {}
        if exact_reuse.get("eligible") is True:
            st.success(
                "Exact verified reuse available — this Blueprint is the "
                "approved one-page résumé verified against this exact JD."
            )
            st.caption(
                "Verified exact-JD score: "
                f"{int(exact_reuse.get('verified_score') or 0)}. Fresh "
                "comparison metrics remain diagnostic."
            )
        candidate_by_fingerprint = {
            _clean(row.get("normalized_source_fingerprint")): row
            for row in candidates
        }
        selected_fingerprint = navigation_selectbox(st,
            "Starting source",
            list(candidate_by_fingerprint),
            index=0,
            format_func=lambda value: _candidate_label(
                candidate_by_fingerprint[value]
            ),
            key=f"phase9f_d_source_{ranking_fingerprint[:16]}",
            scope=ranking_fingerprint,
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
        selected_label = navigation_selectbox(st,
            "Tailoring intensity",
            options,
            index=default_index,
            placeholder="Choose Reuse, Minor, or Full",
            key=intensity_key,
            scope=ranking_fingerprint,
        )
        confirmed_intensity = LABEL_TO_INTENSITY.get(selected_label or "", "")
        if selected_is_winner and exact_reuse.get("eligible") is True and (
            confirmed_intensity and confirmed_intensity != "reuse"
        ):
            st.warning(
                "You are overriding the exact verified Reuse recommendation. "
                "This explicit intensity override is retained in confirmation provenance."
            )

        intent_key = f"phase9f_d_intent_{ranking_fingerprint}"
        st.session_state.setdefault(intent_key, uuid.uuid4().hex)
        from database.phase9f_application_confirmation_manager import _jd_hash
        handoffs = [row for row in list_job_finder_application_bindings()
                    if row["binding"].get("raw_jd_sha256") == _jd_hash(phase9f_a_snapshot["raw_text"])]
        options = [None, *[row["application_id"] for row in handoffs]]
        labels = {row["application_id"]: f"Application #{row['application_id']} · {row['session_name']}" for row in handoffs}
        current_id = st.session_state.get("current_application_id")
        target_id = navigation_selectbox(st,
            "Application Session to configure", options,
            index=options.index(current_id) if current_id in options else 0,
            format_func=lambda value: labels.get(value, "Create a new Application Session"),
            key=f"phase9f_d_target_{ranking_fingerprint}",
            scope=ranking_fingerprint,
        )
        target_binding = next((row["binding"] for row in handoffs if row["application_id"] == target_id), None)
        if st.button(
            "Confirm and configure Application Session" if target_id else "Confirm and create Application Session",
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
                    existing_application_id=target_id,
                    discovered_job_id=target_binding["discovered_job_id"] if target_binding else None,
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
                diagnostics = getattr(exc, "pre_d_diagnostics", None)
                if isinstance(diagnostics, dict):
                    with st.expander("PRE-D exact JD mismatch diagnostics", expanded=True):
                        st.caption("JD-only comparison. Confirmation is still blocked. "
                                   "Review the report before sharing; it contains differing JD profile values.")
                        st.json(diagnostics)
                        st.download_button(
                            "Download PRE-D mismatch diagnostics JSON",
                            data=json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str),
                            file_name="phase9f_pre_d_mismatch_" + ranking_fingerprint[:16] + ".json",
                            mime="application/json",
                            key="phase9f_pre_d_diagnostics_" + ranking_fingerprint[:16],
                            on_click="ignore",
                        )


def render_phase9f_source_revision(*, application_id: int) -> None:
    """Explicit fresh source confirmation; never invokes legacy Phase 9E bind."""
    from database.phase9f_application_confirmation_manager import get_phase9f_application_confirmation
    from database.global_master_resume_manager import get_current_global_master_resume, get_global_master_resume_artifact
    from database.global_blueprint_manager import list_active_global_blueprints_read_only
    from tailoring.phase9f_starting_source_ranking import rank_starting_resume_sources
    from tailoring.phase9f_tailoring_intensity import recommend_tailoring_intensity
    from database.phase9f_tailoring_execution_manager import prepare_or_reuse_phase9f_tailoring_execution
    current = get_phase9f_application_confirmation(application_id)
    if not current:
        st.error('A guarded Phase 9F confirmation is required.')
        return
    prefix = f"phase9f_reconfirm_{application_id}_{current['confirmation_id']}"
    if st.button('Change tailoring base', key=prefix+'_open'):
        st.session_state[prefix+'_editing'] = True
    if st.session_state.get(prefix+'_editing'):
        st.subheader('New generation — confirm a different Tailor Base')
        st.caption(f'Application #{application_id} stays the same. Earlier frozen generations, documents and verification remain historical. No approval occurs here.')
        if st.button('Analyze available immutable bases', key=prefix+'_analyze'):
            try:
                exact=current['confirmation_snapshot']['phase9f_a_snapshot']
                master=get_current_global_master_resume()
                ranking=rank_starting_resume_sources(exact_jd=exact,current_base_resume=master,
                    current_base_artifact=get_global_master_resume_artifact(master['master_version_id']) if master else None,
                    global_blueprints=list_active_global_blueprints_read_only())
                recommendation=recommend_tailoring_intensity(ranking,expected_ranking_input_fingerprint=ranking['ranking_input_fingerprint'])
                st.session_state[prefix+'_scope']=(ranking,recommendation)
            except (ValueError,RuntimeError) as exc:
                st.error('Current source analysis unavailable: '+str(exc))
        scope=st.session_state.get(prefix+'_scope')
        if scope:
            ranking,recommendation=scope
            old=current['confirmation_snapshot']['selected_candidate']['normalized_source_fingerprint']
            candidates=[r for r in ranking.get('ranked_candidates',[]) if r['normalized_source_fingerprint']!=old]
            if not candidates:
                st.info('No different eligible immutable base is currently available. Register a verified source before retrying.')
            else:
                selected=st.selectbox('Tailor Base for the NEW generation',candidates,format_func=_candidate_label,key=prefix+'_choice')
                _render_selected_metrics(selected)
                identity=selected['normalized_source_fingerprint']
                intensity=st.radio('New generation tailoring intensity',['full','minor'],format_func=str.title,key=prefix+'_'+identity+'_intensity')
                ack=st.checkbox('I confirm this exact Tailor Base for a NEW guarded Phase 9F generation; earlier generations remain unchanged.',key=prefix+'_'+identity+'_'+intensity+'_ack')
                if st.button('Confirm new Phase 9F Tailor Base',disabled=not ack,key=prefix+'_confirm',type='primary'):
                    try:
                        result=confirm_phase9f_application_session(
                            phase9f_a_snapshot=current['confirmation_snapshot']['phase9f_a_snapshot'],
                            persisted_exact_jd_snapshot=current['confirmation_snapshot']['persisted_exact_jd_snapshot'],
                            ranking_result=ranking,phase9f_c_recommendation=recommendation,
                            confirmed_normalized_source_fingerprint=identity,confirmed_intensity=intensity,
                            application_intent_id=prefix,existing_application_id=application_id,
                            reconfirm_confirmation_id=current['confirmation_id'])
                        prepare_or_reuse_phase9f_tailoring_execution(application_id=application_id)
                        application=get_application_by_id(application_id)
                        st.session_state['latest_report']=application['report']
                        st.session_state['resume_filename']=application['resume_filename']
                        st.session_state['flash_message']='Fresh Phase 9F source confirmed for this same application. Generate a new draft below; fit, verification and explicit approval are still required.'
                        st.rerun()
                    except Exception as exc:
                        st.error('Guarded source reconfirmation stopped: '+str(exc))
    _render_phase9f_generation_sources(application_id)


def _render_phase9f_generation_sources(application_id: int) -> None:
    """Read-only generation/source history; selecting history never changes scope."""
    from database.tailoring_generation_control import list_tailoring_generations
    from database.phase9f_tailoring_execution_manager import get_phase9f_tailoring_execution
    from database.phase9f_application_confirmation_manager import get_phase9f_application_confirmation
    generations=list_tailoring_generations(application_id)
    if not generations:
        return
    panel=st.expander('Frozen generation sources (read-only)',key=f'phase9f_frozen_sources_{application_id}')
    with panel:
        chosen=panel.selectbox('Inspect frozen generation',generations,
            format_func=lambda r:r['generation_id'][:8]+' · '+r['status'],key=f'phase9f_frozen_generation_{application_id}')
        # phase9f-v39-history-inspection-crash-guard-v1
        try:
            execution=get_phase9f_tailoring_execution(application_id,generation_id=chosen['generation_id'])
        except ValueError as exc:
            panel.warning("Historical generation unavailable: " + str(exc))
            panel.caption("The saved generation/execution binding needs review. This read-only history panel cannot repair or approve it.")
            return
        if not execution:
            panel.caption('This historical generation has no matching Phase 9F execution identity.')
            return
        confirmation=get_phase9f_application_confirmation(application_id,confirmation_id=execution['confirmation_id'])
        source=confirmation['confirmation_snapshot']['selected_candidate']
        panel.write('**Frozen source:** '+source['source_display_name'])
        panel.caption('Generation '+chosen['generation_id']+' · confirmation '+confirmation['confirmation_id']+' · execution '+execution['execution_id'])
        panel.write('Frozen source Job Match: '+str(source['deterministic_alignment_score']))
        panel.caption('Source DOCX SHA-256: '+str(execution['source_artifact'].get('sha256') or 'Unavailable'))
        panel.caption('Historical view only. The active Tailor Base and approval evidence are not changed.')
