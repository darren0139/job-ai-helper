"""Streamlit presentation for durable Phase 9F-E Reuse execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from database.application_resume_result_manager import (
    get_application_resume_result,
    list_application_result_verifications,
    list_application_resume_result_events,
)
from database.phase9f_application_execution_manager import (
    execute_phase9f_reuse,
    get_phase9f_application_execution,
    list_phase9f_application_execution_events,
)
from llm import get_active_model
from resume_builder.docx_projects_skills_replacer import pdf_to_preview_html
from tailoring.application_output_integrations_ui import (
    render_application_output_cover_letter,
)
from tailoring.phase9f_application_execution import Phase9FEExecutionError
from tailoring.phase9f_starting_source_provenance import (
    Phase9FBProvenanceError,
    load_blueprint_provenance_read_only,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _json_download_payload(value: Any) -> bytes:
    # Serialize technical/audit data only after an explicit export request.
    return json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _source_label(context: dict[str, Any]) -> str:
    decision = context.get("decision") or {}
    starting = decision.get("starting_snapshot") or {}
    source = starting.get("source_identity") or {}
    source_type = _clean(starting.get("source_type"))
    display_name = _clean(source.get("source_display_name"))
    version = int(source.get("source_version") or 0)
    if source_type == "global_blueprint":
        return f"{display_name or 'Global Blueprint'} · version {version}"
    if source_type == "base_resume":
        return f"{display_name or 'Base Resume'} · version {version}"
    return "Unsupported starting source"


def _download_artifact(
    *,
    application_id: int,
    result_id: str,
    artifact: dict[str, Any],
) -> None:
    path = Path(str(artifact.get("materialized_path") or ""))
    if not path.is_file():
        st.error("This exact Reuse artifact is missing or corrupt.")
        return
    kind = _clean(artifact.get("artifact_kind")) or "file"
    st.download_button(
        f"Download résumé {kind.upper()}",
        data=path.read_bytes(),
        file_name=path.name,
        mime=_clean(artifact.get("mime_type"))
        or "application/octet-stream",
        width="stretch",
        key=(
            f"phase9f_e_download_{application_id}_{result_id}_{kind}"
        ),
    )


def _percent(value: Any) -> str:
    if value is None or value == "":
        return "Unavailable"
    try:
        return f"{int(value)}%"
    except (TypeError, ValueError):
        return str(value)


def _delta(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:+d}"


def _phase8_metric_snapshot(phase8: dict[str, Any]) -> dict[str, Any]:
    """Build a display-only view from the already-persisted Phase 8 result."""
    after = phase8.get("after_stable_analysis") or {}
    comparison = phase8.get("comparison") or {}
    seed = phase8.get("final_scoring_seed") or {}
    aggregate = seed.get("aggregate") or {}

    def resolved(name: str) -> Any:
        value = after.get(name)
        return aggregate.get(name) if value is None else value

    canonical_rows = (
        after.get("canonical_requirements")
        or seed.get("canonical_requirements")
        or []
    )
    claim_lineage = phase8.get("claim_lineage") or {}
    return {
        "alignment": resolved("deterministic_alignment_score"),
        "required_core": resolved("required_core_coverage_score"),
        "preferred": resolved("preferred_coverage_score"),
        "evidence_strength": resolved("evidence_strength_score"),
        "before_score": comparison.get("before_score"),
        "after_score": comparison.get(
            "after_score",
            resolved("deterministic_alignment_score"),
        ),
        "score_delta": comparison.get("score_delta"),
        "required_core_delta": comparison.get("required_core_coverage_delta"),
        "preferred_delta": comparison.get("preferred_coverage_delta"),
        "evidence_delta": comparison.get("evidence_strength_delta"),
        "canonical_requirement_count": len(canonical_rows),
        "unchanged_requirement_count": int(
            comparison.get("unchanged_requirement_count", 0) or 0
        ),
        "improved_requirement_count": len(
            comparison.get("improved_requirements", []) or []
        ),
        "regressed_requirement_count": len(
            comparison.get("regressed_requirements", []) or []
        ),
        "important_regression_count": len(
            comparison.get("important_regressions", []) or []
        ),
        "claim_review_count": int(
            claim_lineage.get("claim_review_required_count", 0) or 0
        ),
        "comparison_valid": phase8.get("comparison_valid") is True,
        "verification_integrity": phase8.get("blueprint_ready") is True,
        "fit_one_page": phase8.get("fit_one_page") is True,
        "page_count": phase8.get("page_count"),
    }


def _render_source_blueprint_lineage(
    *,
    phase9e_context: dict[str, Any],
    result: dict[str, Any],
    phase8: dict[str, Any],
) -> None:
    """Render source provenance without changing or manufacturing lineage."""
    decision = phase9e_context.get("decision") or {}
    selection = decision.get("selection") or {}
    if _clean(selection.get("selected_source")) != "global_blueprint":
        return

    blueprint = selection.get("selected_blueprint") or {}
    starting = decision.get("starting_snapshot") or {}
    source_identity = starting.get("source_identity") or {}

    with st.expander("Source Blueprint lineage", expanded=False):
        st.write(
            f"**{_clean(selection.get('selected_blueprint_display_name')) or _clean(blueprint.get('display_name')) or 'Global Blueprint'}** "
            f"· version {int(blueprint.get('version_number') or source_identity.get('source_version') or 0)}"
        )
        st.caption(
            "This is provenance for the frozen source résumé. Historical "
            "Blueprint scores do not alter the current-JD Phase 8 score."
        )

        current = _phase8_metric_snapshot(phase8)
        source_application_id = result.get("source_application_id")
        columns = st.columns(3)
        columns[0].metric(
            "Current JD alignment",
            _percent(current.get("alignment")),
        )
        columns[1].metric(
            "Source Application",
            f"#{int(source_application_id)}" if source_application_id else "Unavailable",
        )
        columns[2].metric(
            "Blueprint version",
            int(result.get("blueprint_version") or blueprint.get("version_number") or 0),
        )

        exact_identity = {
            "blueprint_id": result.get("blueprint_id") or blueprint.get("blueprint_id"),
            "blueprint_fingerprint": result.get("blueprint_fingerprint") or blueprint.get("blueprint_fingerprint"),
            "blueprint_version": result.get("blueprint_version") or blueprint.get("version_number"),
            "source_application_id": result.get("source_application_id"),
            "source_generation_id": result.get("source_generation_id"),
            "source_verification_id": result.get("source_verification_id"),
            "source_verification_fingerprint": result.get("source_verification_fingerprint"),
        }
        st.write("**Exact bound/result source identity**")
        st.json(exact_identity)

        if not isinstance(blueprint, dict) or not blueprint.get("blueprint_snapshot"):
            st.info(
                "The Phase 9F-D decision keeps the exact Blueprint identity, "
                "but this persisted selection does not contain the full Phase "
                "9D history snapshot. No historical score is invented here."
            )
            return

        try:
            provenance = load_blueprint_provenance_read_only(blueprint)
        except (Phase9FBProvenanceError, OSError, RuntimeError, ValueError) as exc:
            st.info(f"Historical Blueprint provenance is unavailable: {exc}")
            return

        historical_phase8 = provenance.get("phase8_verification") or {}
        historical_score = historical_phase8.get("historical_approved_score")
        if historical_score is None:
            historical_score = (
                (provenance.get("phase9b_candidate") or {}).get("score_summary")
                or {}
            ).get("approved_tailored_score")

        st.metric(
            "Historical Blueprint/source score",
            _percent(historical_score),
        )
        st.caption(
            "Historical Blueprint/source score belongs to the source "
            "application that created the Blueprint. It is shown only for "
            "provenance and is not used as the current application score."
        )

        source_resume = provenance.get("source_resume_result_or_generation") or {}
        source_generation = source_resume.get("source_generation") or {}
        artifact_records = source_resume.get("immutable_artifact_hash_records") or []
        st.write(
            "**Immutable source proof:** "
            f"approval {'resolved' if source_generation.get('approval_resolved') else 'unresolved'} · "
            f"one-page fit {'verified' if source_generation.get('fit_identity_match') else 'unverified'} · "
            f"{len(artifact_records)} authoritative artifact hash record(s)"
        )
        if artifact_records:
            st.dataframe(
                [
                    {
                        "Artifact": row.get("artifact_kind"),
                        "SHA-256": row.get("artifact_sha256"),
                        "Bytes": row.get("artifact_size"),
                        "Result": row.get("application_result_id"),
                    }
                    for row in artifact_records
                ],
                hide_index=True,
                width="stretch",
            )

        source_jd_tab, phase8_tab, phase9c_tab, technical_tab = st.tabs(
            [
                "Source JD",
                "Historical Phase 8",
                "Phase 9C",
                "Technical provenance",
            ]
        )
        with source_jd_tab:
            st.json(provenance.get("source_jd") or {})
        with phase8_tab:
            st.json(historical_phase8)
        with phase9c_tab:
            st.json(provenance.get("phase9c_evaluation") or {})
        with technical_tab:
            st.json(
                {
                    "blueprint_identity": provenance.get("blueprint_identity") or {},
                    "blueprint_role_family": provenance.get("blueprint_role_family") or {},
                    "phase9b_candidate": provenance.get("phase9b_candidate") or {},
                    "phase9d_approval": provenance.get("phase9d_approval") or {},
                    "frozen_resume_snapshot": provenance.get("frozen_resume_snapshot") or {},
                    "missing_provenance_links": provenance.get("missing_provenance_links") or [],
                    "zero_cost_diagnostics": provenance.get("zero_cost_diagnostics") or {},
                }
            )

def _render_result(
    *,
    application_id: int,
    execution: dict[str, Any],
    result: dict[str, Any],
    phase9e_context: dict[str, Any],
) -> None:
    source_type = _clean(execution.get("source_type"))
    source_label = (
        "Approved Global Blueprint"
        if source_type == "global_blueprint"
        else "Authoritative Base Resume"
    )
    st.success(
        "Reuse execution completed. The exact confirmed résumé was copied "
        "unchanged; no draft, regeneration, fitting, or second content "
        "approval was created."
    )
    summary = st.columns(4)
    summary[0].metric("Result", "Immutable Reuse")
    summary[1].metric("Source", source_label)
    summary[2].metric("Page invariant", "1 page")
    summary[3].metric("Content changed", "No")
    st.caption(
        f"Application result `{result['application_result_id']}` · "
        f"fingerprint `{result['result_fingerprint']}`"
    )
    st.caption(
        f"Execution `{execution['execution_id']}` · "
        f"Phase 8 mode `{execution.get('phase8_mode')}`"
    )

    artifacts = result.get("artifacts") or []
    st.subheader("Preview and download unchanged résumé")
    pdf = next(
        (
            Path(str(row.get("materialized_path") or ""))
            for row in artifacts
            if _clean(row.get("artifact_kind")) == "pdf"
            and Path(str(row.get("materialized_path") or "")).is_file()
        ),
        None,
    )
    if pdf is not None:
        try:
            st.markdown(
                pdf_to_preview_html(
                    pdf,
                    max_width=820,
                    max_pages=5,
                    zoom=1.35,
                    include_download=False,
                ),
                unsafe_allow_html=True,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            st.caption(
                "The shared visual preview could not be rendered "
                f"({exc}). Verified downloads remain available."
            )
    else:
        st.caption(
            "No immutable PDF artifact is present. The exact DOCX remains "
            "available when it was the confirmed authoritative source."
        )
    if not artifacts:
        st.error("No exact immutable Reuse artifact is available.")
    else:
        with st.container(horizontal=True):
            for artifact in artifacts:
                with st.container(width="stretch"):
                    st.caption(
                        f"{artifact.get('provenance_label')} · SHA-256 "
                        f"`{artifact.get('artifact_sha256')}` · "
                        f"{artifact.get('artifact_size')} bytes"
                    )
                    _download_artifact(
                        application_id=application_id,
                        result_id=result["application_result_id"],
                        artifact=artifact,
                    )

    verifications = list_application_result_verifications(
        result["application_result_id"]
    )
    phase8_for_lineage: dict[str, Any] = {}
    with st.expander("Authoritative Phase 8 verification", expanded=False):
        if verifications:
            current = verifications[-1]
            phase8 = current.get("phase8_result") or {}
            phase8_for_lineage = phase8
            snapshot = _phase8_metric_snapshot(phase8)
            st.write(
                "**Strict inherited source verification**"
                if current.get("mode") == "strict_inherited_source_phase8"
                else "**Executed against the exact current JD**"
            )

            metrics = st.columns(4)
            metrics[0].metric(
                "Final alignment",
                _percent(snapshot.get("alignment")),
                delta=_delta(snapshot.get("score_delta")),
            )
            metrics[1].metric(
                "Final Required/Core",
                _percent(snapshot.get("required_core")),
                delta=_delta(snapshot.get("required_core_delta")),
            )
            metrics[2].metric(
                "Final Preferred",
                _percent(snapshot.get("preferred")),
                delta=_delta(snapshot.get("preferred_delta")),
            )
            metrics[3].metric(
                "Final evidence strength",
                _percent(snapshot.get("evidence_strength")),
                delta=_delta(snapshot.get("evidence_delta")),
            )

            before_score = snapshot.get("before_score")
            after_score = snapshot.get("after_score")
            if before_score is not None and after_score is not None:
                st.caption(
                    "Before → final canonical alignment: "
                    f"{_percent(before_score)} → {_percent(after_score)}."
                )

            integrity = (
                "Passed" if snapshot.get("verification_integrity") else "Not passed"
            )
            canonical_scope = (
                "Valid" if snapshot.get("comparison_valid") else "Invalid"
            )
            page_label = (
                "1 page"
                if snapshot.get("fit_one_page")
                else (
                    f"{snapshot.get('page_count')} pages"
                    if snapshot.get("page_count") not in (None, "")
                    else "Unavailable"
                )
            )
            st.write(
                f"**Verification integrity:** {integrity} · "
                f"**Canonical scope:** {canonical_scope} · "
                f"**Final fit:** {page_label}"
            )
            st.caption(
                "Canonical requirements: "
                f"{snapshot.get('canonical_requirement_count', 0)} · "
                f"unchanged {snapshot.get('unchanged_requirement_count', 0)} · "
                f"improved {snapshot.get('improved_requirement_count', 0)} · "
                f"regressed {snapshot.get('regressed_requirement_count', 0)} · "
                f"important regressions {snapshot.get('important_regression_count', 0)} · "
                f"claim-review risks {snapshot.get('claim_review_count', 0)}"
            )

            phase8_export_key = (
                "phase9f_e_phase8_export_"
                f"{application_id}_{result['application_result_id']}"
            )
            if st.button(
                "Prepare Phase 8 JSON download",
                key=f"{phase8_export_key}_prepare",
            ):
                st.session_state[phase8_export_key] = (
                    _json_download_payload(current)
                )
            prepared_phase8 = st.session_state.get(phase8_export_key)
            if isinstance(prepared_phase8, bytes):
                st.caption(
                    "Phase 8 technical export prepared from the persisted "
                    "verification. It is not rendered inline."
                )
                st.download_button(
                    "Download Phase 8 verification JSON",
                    data=prepared_phase8,
                    file_name=(
                        "phase9f_e_phase8_"
                        f"{result['application_result_id'][:12]}.json"
                    ),
                    mime="application/json",
                    key=f"{phase8_export_key}_download",
                )
        else:
            st.warning("The result has no persisted Phase 8 binding.")

    if source_type == "global_blueprint" and phase8_for_lineage:
        _render_source_blueprint_lineage(
            phase9e_context=phase9e_context,
            result=result,
            phase8=phase8_for_lineage,
        )

    with st.expander("Phase 9F-E identity and audit", expanded=False):
        st.caption(
            f"Execution `{execution.get('execution_id')}` · "
            f"result `{result.get('application_result_id')}` · "
            f"status `{execution.get('status')}` · "
            f"source `{execution.get('source_type')}`"
        )
        st.caption(
            "Event history is queried only when you explicitly prepare the "
            "audit export."
        )
        audit_export_key = (
            "phase9f_e_audit_export_"
            f"{application_id}_{execution.get('execution_id')}_"
            f"{result.get('application_result_id')}"
        )
        if st.button(
            "Prepare Phase 9F-E audit JSON",
            key=f"{audit_export_key}_prepare",
        ):
            audit_payload = {
                "execution": execution,
                "application_result": result,
                "execution_events": list_phase9f_application_execution_events(
                    application_id
                ),
                "application_result_events": (
                    list_application_resume_result_events(application_id)
                ),
            }
            st.session_state[audit_export_key] = (
                _json_download_payload(audit_payload)
            )
        prepared_audit = st.session_state.get(audit_export_key)
        if isinstance(prepared_audit, bytes):
            st.caption(
                "Audit export prepared. Event history was loaded on demand "
                "and is not rendered inline."
            )
            st.download_button(
                "Download Phase 9F-E audit JSON",
                data=prepared_audit,
                file_name=(
                    "phase9f_e_audit_"
                    f"{str(execution.get('execution_id') or '')[:12]}.json"
                ),
                mime="application/json",
                key=f"{audit_export_key}_download",
            )

    st.subheader("Cover letter")
    st.caption(
        "Cover-letter generation uses this immutable application result and "
        "the exact linked JD. It does not create or edit a résumé draft."
    )
    render_application_output_cover_letter(
        application_id=application_id,
        model_id=get_active_model("analysis"),
        key_prefix="phase9f_e_reuse_result",
    )



def render_phase9f_reuse_execution(
    *,
    application_id: int,
    phase9e_context: dict[str, Any],
) -> dict[str, Any]:
    """Render one D-confirmed Reuse path; writes occur only after its button."""
    st.divider()
    st.header("Phase 9F-E — Reuse Execution")
    st.write(f"**Confirmed source:** {_source_label(phase9e_context)}")
    st.write("**Confirmed tailoring intensity:** Reuse")
    st.caption(
        "Reuse validates and copies the exact immutable source, proves the "
        "one-page invariant, and runs or strictly references the existing "
        "deterministic Phase 8 contract. It makes zero model, embedding, "
        "Chroma, generation, rewrite, or content-changing fit calls."
    )

    execution = get_phase9f_application_execution(application_id)
    if execution is None:
        st.info(
            "Tailoring execution has not started. No application résumé "
            "result or editable draft has been created."
        )
        if st.button(
            "Begin Reuse tailoring",
            type="primary",
            width="stretch",
            key=f"phase9f_e_begin_reuse_{application_id}",
        ):
            try:
                execute_phase9f_reuse(
                    application_id=application_id,
                    actor_label="Local user",
                )
                st.rerun()
            except (Phase9FEExecutionError, OSError, RuntimeError, ValueError) as exc:
                st.error(str(exc))
        return {"status": "not_started", "owns_workflow": True}

    status = _clean(execution.get("status"))
    stage = _clean(execution.get("current_stage"))
    if status in {"preparing", "running"}:
        st.info(
            f"Reuse execution is {status} at `{stage}`. Duplicate starts are "
            "disabled and resolve to this same execution identity."
        )
        st.button(
            "Reuse execution in progress",
            disabled=True,
            width="stretch",
            key=f"phase9f_e_running_{application_id}",
        )
        return {**execution, "owns_workflow": True}

    if status == "failed":
        st.error(
            f"Reuse failed safely at `{stage}`: "
            f"{execution.get('last_error_message') or 'Unknown failure'}"
        )
        if execution.get("application_result_id"):
            st.info(
                "The valid immutable result remains preserved. Retry resumes "
                "at Phase 8 and does not generate a duplicate result."
            )
        else:
            st.info(
                "The Phase 9F-D session and exact binding remain intact. "
                "Retry uses the same execution identity."
            )
        if st.button(
            "Retry Reuse",
            type="primary",
            width="stretch",
            key=f"phase9f_e_retry_reuse_{application_id}",
        ):
            try:
                execute_phase9f_reuse(
                    application_id=application_id,
                    actor_label="Local user",
                )
                st.rerun()
            except (Phase9FEExecutionError, OSError, RuntimeError, ValueError) as exc:
                st.error(str(exc))
        return {**execution, "owns_workflow": True}

    if status == "completed":
        result_id = _clean(execution.get("application_result_id"))
        result = get_application_resume_result(result_id)
        if result is None:
            st.error(
                "The completed execution's immutable application result is missing."
            )
            return {**execution, "owns_workflow": True}
        _render_result(
            application_id=application_id,
            execution=execution,
            result=result,
            phase9e_context=phase9e_context,
        )
        return {**execution, "owns_workflow": True}

    st.error("The persisted Phase 9F-E execution status is unsupported.")
    return {**execution, "owns_workflow": True}
