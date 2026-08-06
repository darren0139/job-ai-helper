"""Streamlit UI for Phase 9B Blueprint Candidate Promotion."""

from __future__ import annotations

from typing import Any

import streamlit as st

from database.blueprint_candidate_manager import (
    archive_blueprint_candidate,
    list_blueprint_candidates,
    save_blueprint_candidate,
)
from database.evidence_opportunity_manager import (
    get_latest_evidence_opportunity,
)
from database.tailoring_generation_control import (
    get_application_generation_control,
)
from database.tailoring_verification_manager import (
    get_latest_tailoring_verification,
)
from tailoring.phase9b_blueprint_candidate import (
    blueprint_candidate_eligibility,
    build_blueprint_candidate,
)
from tailoring.phase9b_role_family import (
    CUSTOM_ROLE_FAMILY_LABEL,
    build_default_candidate_name,
    build_default_candidate_notes,
    canonical_role_family_id,
    role_family_labels,
    suggest_role_family,
)


def _sync_generated_value(
    *,
    value_key: str,
    generated_key: str,
    generated_value: str,
) -> None:
    previous_generated = st.session_state.get(generated_key)
    current_value = st.session_state.get(value_key)
    if current_value is None or current_value == previous_generated:
        st.session_state[value_key] = generated_value
    st.session_state[generated_key] = generated_value


def _registry_rows(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for candidate in candidates:
        scores = candidate.get("score_summary") or {}
        rows.append(
            {
                "Candidate": candidate.get(
                    "candidate_name",
                    "",
                ),
                "Role family": candidate.get("role_family", ""),
                "Status": candidate.get("status", ""),
                "Original score": scores.get(
                    "original_resume_score",
                    0,
                ),
                "Approved score": scores.get(
                    "approved_tailored_score",
                    0,
                ),
                "Potential score": scores.get(
                    "evidence_potential_score",
                    "—",
                ),
                "Source application": candidate.get(
                    "source_application_id",
                    "",
                ),
                "Source generation": str(
                    candidate.get(
                        "source_generation_id",
                        "",
                    )
                )[:8],
                "Candidate ID": str(
                    candidate.get("candidate_id", "")
                )[:8],
            }
        )
    return rows


def _role_family_input(
    *,
    application_id: int,
    suggestion: dict[str, Any],
) -> tuple[str, str]:
    labels = role_family_labels()
    suggested_label = str(
        suggestion.get("role_family")
        or "General Software Engineering"
    )
    legacy_key = f"phase9b_role_family_{application_id}"
    legacy_value = str(
        st.session_state.get(legacy_key) or ""
    ).strip()

    default_label = (
        legacy_value
        if legacy_value in labels
        else suggested_label
    )
    use_custom_default = bool(
        legacy_value and legacy_value not in labels
    )
    options = [*labels, CUSTOM_ROLE_FAMILY_LABEL]
    default_choice = (
        CUSTOM_ROLE_FAMILY_LABEL
        if use_custom_default
        else default_label
    )
    choice_key = f"phase9b_role_family_choice_{application_id}"
    if choice_key not in st.session_state:
        st.session_state[choice_key] = default_choice

    selected = st.selectbox(
        "Role family",
        options=options,
        key=choice_key,
        help=(
            "A reusable category used by Phase 9C to compare candidates "
            "across similar job descriptions. It is broader than one exact "
            "job title."
        ),
    )

    if selected == CUSTOM_ROLE_FAMILY_LABEL:
        custom_key = f"phase9b_custom_role_family_{application_id}"
        if custom_key not in st.session_state:
            st.session_state[custom_key] = legacy_value
        role_family = st.text_input(
            "Custom role family",
            placeholder="Example: Security Software Engineering",
            key=custom_key,
        ).strip()
    else:
        role_family = selected

    role_family_id = canonical_role_family_id(role_family)
    title = str(suggestion.get("source_job_title") or "").strip()
    confidence = str(suggestion.get("confidence") or "low").title()
    if title:
        st.caption(
            f"Suggested from source job title: {title} · "
            f"confidence: {confidence}. You may override it."
        )
    return role_family, role_family_id


def render_blueprint_candidate_promotion(
    *,
    application_id: int,
    baseline_report: dict[str, Any],
    current_phase9e_decision_fingerprint: str = "",
) -> None:
    st.divider()
    st.subheader("Phase 9B — Blueprint Candidate Promotion")
    st.caption(
        "Promotes an Approved, Phase-8-ready fitted résumé into a global "
        "candidate registry. A candidate is not yet the reusable global "
        "blueprint; Phase 9C evaluates it and Phase 9D approves/version it."
    )

    control = get_application_generation_control(application_id)
    approved = control.get("approved_generation")
    if (
        isinstance(approved, dict)
        and approved.get("source_application_result_id")
    ):
        approved = dict(approved)
        approved["phase9e_scope_matches"] = bool(
            current_phase9e_decision_fingerprint
            and str(approved.get("phase9e_decision_fingerprint") or "")
            == str(current_phase9e_decision_fingerprint)
        )
    approved_id = (
        str(approved.get("generation_id") or "")
        if isinstance(approved, dict)
        else ""
    )
    verification = (
        get_latest_tailoring_verification(
            application_id,
            approved_id,
        )
        if approved_id
        else None
    )
    eligibility = blueprint_candidate_eligibility(
        generation_state=approved,
        verification=verification,
    )

    gate_rows = [
        {
            "Gate": name.replace("_", " ").title(),
            "Passed": bool(passed),
        }
        for name, passed in eligibility["reasons"].items()
    ]
    st.dataframe(
        gate_rows,
        hide_index=True,
        width="stretch",
    )

    suggestion = suggest_role_family(baseline_report)
    role_family, role_family_id = _role_family_input(
        application_id=application_id,
        suggestion=suggestion,
    )
    opportunity = get_latest_evidence_opportunity(application_id)

    generated_name = build_default_candidate_name(
        application_id=application_id,
        generation_id=approved_id,
        role_family=role_family,
    )
    name_key = f"phase9b_candidate_name_{application_id}"
    name_generated_key = (
        f"phase9b_candidate_name_generated_{application_id}"
    )
    _sync_generated_value(
        value_key=name_key,
        generated_key=name_generated_key,
        generated_value=generated_name,
    )
    candidate_name = st.text_input(
        "Candidate name",
        key=name_key,
        help=(
            "Auto-generated for readability. Editing this metadata does not "
            "change the résumé content or Phase 9C scoring."
        ),
    )
    if st.button(
        "Reset candidate name",
        key=f"phase9b_reset_name_{application_id}",
    ):
        st.session_state[name_key] = generated_name
        st.rerun()

    generated_notes = build_default_candidate_notes(
        application_id=application_id,
        generation_state=approved or {},
        verification=verification or {},
        baseline_report=baseline_report,
        role_family=role_family,
    )
    notes_key = f"phase9b_notes_{application_id}"
    notes_generated_key = (
        f"phase9b_notes_generated_{application_id}"
    )
    _sync_generated_value(
        value_key=notes_key,
        generated_key=notes_generated_key,
        generated_value=generated_notes,
    )
    notes = st.text_area(
        "Candidate notes (optional)",
        height=120,
        key=notes_key,
        help=(
            "Human context only. Notes are not used for scoring, candidate "
            "deduplication, or résumé generation. The automatic draft may be "
            "edited or cleared."
        ),
    )
    if st.button(
        "Reset candidate notes",
        key=f"phase9b_reset_notes_{application_id}",
    ):
        st.session_state[notes_key] = generated_notes
        st.rerun()

    name_source = (
        "auto_generated"
        if candidate_name == generated_name
        else "user_edited"
    )
    notes_source = (
        "auto_generated"
        if notes == generated_notes
        else ("user_edited" if notes.strip() else "blank")
    )

    if st.button(
        "Promote Approved Version to Blueprint Candidate",
        type="primary",
        width="stretch",
        disabled=(
            not eligibility["eligible"]
            or not role_family.strip()
            or not candidate_name.strip()
        ),
        key=f"phase9b_promote_{application_id}",
    ):
        try:
            snapshot = build_blueprint_candidate(
                application_id=application_id,
                generation_state=approved,
                verification=verification,
                baseline_report=baseline_report,
                role_family=role_family,
                role_family_id=role_family_id,
                role_family_suggestion=suggestion,
                candidate_name=candidate_name,
                candidate_name_source=name_source,
                notes=notes,
                notes_source=notes_source,
                evidence_opportunity=opportunity,
            )
            saved = save_blueprint_candidate(snapshot)
            cache_status = str(saved.get("cache_status") or "")
            if cache_status == "hit_metadata_updated":
                flash = (
                    "Reused the exact global candidate and updated its "
                    "editable name/notes metadata."
                )
            elif cache_status == "hit":
                flash = "Reused the exact global blueprint candidate."
            else:
                flash = (
                    "Promoted the Approved version to a global blueprint "
                    "candidate."
                )
            st.session_state[
                f"phase9b_flash_{application_id}"
            ] = flash
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(
                f"Blueprint candidate promotion failed: {exc}"
            )

    flash = st.session_state.pop(
        f"phase9b_flash_{application_id}",
        "",
    )
    if flash:
        st.success(flash)

    candidates = list_blueprint_candidates(
        include_archived=True,
    )
    st.write("**Global candidate registry**")
    if not candidates:
        st.info("No global blueprint candidates have been created.")
        return

    st.dataframe(
        _registry_rows(candidates),
        hide_index=True,
        width="stretch",
    )

    by_id = {
        str(candidate["candidate_id"]): candidate
        for candidate in candidates
    }
    selected_id = st.selectbox(
        "Inspect candidate",
        options=list(by_id),
        format_func=lambda value: (
            f"{by_id[value].get('status', 'candidate').title()} · "
            f"{by_id[value].get('candidate_name', '')} · "
            f"{value[:8]}"
        ),
        key=f"phase9b_inspect_{application_id}",
    )
    selected = by_id[selected_id]

    with st.expander(
        "Phase 9C evaluation seed",
        expanded=False,
    ):
        st.json(
            {
                "role_family_id": selected.get("role_family_id"),
                "role_family": selected.get("role_family"),
                "source_job": selected.get("source_job"),
                "score_summary": selected.get("score_summary"),
                "quality_gates": selected.get("quality_gates"),
                "evaluation_metadata": selected.get(
                    "evaluation_metadata"
                ),
                "provenance": selected.get("provenance"),
            }
        )

    with st.expander(
        "Selected candidate snapshot",
        expanded=False,
    ):
        st.json(selected)

    if selected.get("status") != "archived":
        confirm = st.checkbox(
            "Confirm archive of selected candidate",
            value=False,
            key=f"phase9b_archive_confirm_{application_id}",
        )
        if st.button(
            "Archive Selected Candidate",
            disabled=not confirm,
            key=f"phase9b_archive_{application_id}",
        ):
            if archive_blueprint_candidate(selected_id):
                st.session_state[
                    f"phase9b_flash_{application_id}"
                ] = "Archived the selected blueprint candidate."
                st.rerun()
