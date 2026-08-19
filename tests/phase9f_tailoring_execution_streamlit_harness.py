from __future__ import annotations

import copy
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path

import streamlit as st

from database import (
    db_manager,
    jd_library_manager,
    tailoring_version_manager,
    user_profile_manager,
)
import database.phase9f_tailoring_execution_manager as execution_manager
from database.phase9f_tailoring_execution_manager import (
    get_phase9f_tailoring_execution,
    run_phase9f_normal_fit,
    run_phase9f_normal_generation,
)
from tailoring.phase9f_tailoring_execution import (
    PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
)
from tailoring.phase9f_tailoring_execution_ui import (
    render_phase9f_tailoring_execution,
)


database_path = Path(os.environ["PHASE9F_F_TEST_DATABASE"])
application_id = int(os.environ["PHASE9F_F_TEST_APPLICATION_ID"])
surface = os.environ.get("PHASE9F_F_TEST_SURFACE", "initialization")

db_manager.DB_PATH = database_path
jd_library_manager.DB_PATH = database_path
tailoring_version_manager.DB_PATH = database_path
user_profile_manager.DB_PATH = database_path


def _addressable_scope(**kwargs) -> dict:
    rows = copy.deepcopy(kwargs["evidence_snapshot"]["rows"])
    selected = rows[:1]
    return {
        "policy_version": PHASE9F_F_SECTION_SCOPE_POLICY_VERSION,
        "phase9a_version": "phase9a-evidence-opportunity-v1",
        "confirmed_intensity": kwargs["confirmed_intensity"],
        "opportunity_fingerprint": "phase9f-f-settings-ui-opportunity",
        "selected_evidence_ids": [row["id"] for row in selected],
        "selected_evidence_fingerprint": "phase9f-f-settings-ui-evidence",
        "projects_addressable": True,
        "skills_addressable": True,
        "enabled_sections": ["projects", "skills"],
        "selected_evidence": selected,
        "opportunity": {},
        "scope_fingerprint": "phase9f-f-settings-ui-scope",
    }


def _source_bundle() -> dict:
    source_path = Path(os.environ["PHASE9F_F_TEST_SOURCE_DOCX"])
    source_bytes = source_path.read_bytes()
    return {
        "artifacts": [
            {
                "artifact_type": "docx",
                "source_path": str(source_path),
                "artifact_bytes": source_bytes,
                "sha256": hashlib.sha256(source_bytes).hexdigest(),
                "byte_size": len(source_bytes),
            }
        ]
    }


@contextmanager
def _forced_test_f_scope():
    """Use synthetic addressable evidence only for one explicit test action."""
    original_scope = execution_manager.build_section_scope
    original_source = execution_manager.resolve_exact_phase9f_d_source
    execution_manager.build_section_scope = _addressable_scope
    execution_manager.resolve_exact_phase9f_d_source = lambda **_kwargs: _source_bundle()
    try:
        yield
    finally:
        execution_manager.build_section_scope = original_scope
        execution_manager.resolve_exact_phase9f_d_source = original_source


def _projects_writer(**kwargs) -> dict:
    st.session_state["phase9f_f_test_projects_writer_calls"] = int(
        st.session_state.get("phase9f_f_test_projects_writer_calls", 0)
    ) + 1
    return {
        "recommended_projects": [
            {
                "title": "Settings test project",
                "display_title": "Settings test project",
                "period": "2026",
                "draft_bullets": [
                    "Built a truthful frozen-evidence integration for the target JD."
                ],
            }
        ],
        "candidate_project_ranking": [],
    }


def _skills_writer(**kwargs) -> dict:
    st.session_state["phase9f_f_test_skills_writer_calls"] = int(
        st.session_state.get("phase9f_f_test_skills_writer_calls", 0)
    ) + 1
    return {
        "skill_lines": [
            {"category": "Evidence-backed", "items": ["PostgreSQL"]}
        ]
    }


def _fit_writer(**kwargs) -> dict:
    st.session_state["phase9f_f_test_fit_writer_calls"] = int(
        st.session_state.get("phase9f_f_test_fit_writer_calls", 0)
    ) + 1
    return {
        "generation_id": kwargs["generation_id"],
        "fit_one_page": True,
        "page_count": 1,
        "docx_path": os.environ["PHASE9F_F_TEST_OUTPUT_DOCX"],
        "pdf_path": os.environ["PHASE9F_F_TEST_OUTPUT_PDF"],
        "tailored_projects_used": copy.deepcopy(kwargs["tailored_projects"]),
        "tailored_skills_used": copy.deepcopy(kwargs["tailored_skills"]),
    }


def _render_settings_surface() -> None:
    # This is a real Streamlit surface backed by the production normal-F
    # manager.  Initialization freezes source/JD/evidence, not tuning.
    execution = get_phase9f_tailoring_execution(application_id)
    if execution is None:
        st.subheader("Tailoring Base")
        st.caption(
            "The exact Phase 9F-D source and JD are bound. Initialization "
            "freezes the truthful Full scope before the normal Application "
            "Session stages continue."
        )
        if st.button(
            "Begin Full tailoring",
            type="primary",
            width="stretch",
            key=f"phase9f_f_prepare_{application_id}",
        ):
            with _forced_test_f_scope():
                execution_manager.prepare_or_reuse_phase9f_tailoring_execution(
                    application_id=application_id
                )
            st.rerun()
        return

    scope = execution.get("section_scope") or {}
    projects_addressable = bool(scope.get("projects_addressable"))
    legacy_private = any(
        key in (execution.get("stage_outputs") or {})
        for key in (
            "generation_settings",
            "projects",
            "skills",
            "fitting",
            "fitting_attempts",
        )
    )
    controls_disabled = not projects_addressable or legacy_private
    defaults: dict = {}

    st.subheader("Tailor Résumé Content")
    st.caption("Frozen tailoring scope · Projects: Will tailor · Skills: Will tailor · Intensity: Full")
    max_projects = st.slider(
        "Maximum projects",
        min_value=1,
        max_value=8,
        value=int(defaults.get("max_projects", 3)),
        key=f"max_projects_{application_id}",
        disabled=controls_disabled,
    )
    allocation_options = [
        "Adaptive",
        "Prefer available evidence",
        "Fit from all canonical evidence",
    ]
    saved_mode = str(defaults.get("bullet_allocation_mode", "prefer_available_evidence"))
    allocation_index = {
        "adaptive": 0,
        "prefer_available_evidence": 1,
        "all_canonical_before_fitting": 2,
    }.get(saved_mode, 1)
    allocation_label = st.radio(
        "Bullet allocation",
        allocation_options,
        index=allocation_index,
        horizontal=True,
        key=f"bullet_allocation_mode_{application_id}",
        disabled=controls_disabled,
    )
    allocation_mode = {
        "Adaptive": "adaptive",
        "Prefer available evidence": "prefer_available_evidence",
        "Fit from all canonical evidence": "all_canonical_before_fitting",
    }[allocation_label]
    max_bullets = st.slider(
        "Bullet limit per project",
        min_value=1,
        max_value=4,
        value=int(defaults.get("max_bullets", 3)),
        key=f"max_bullets_{application_id}",
        disabled=(
            controls_disabled
            or allocation_mode == "all_canonical_before_fitting"
        ),
    )

    acknowledged = st.checkbox(
        "I understand this starts paid Projects/Skills generation for the enabled sections.",
        value=False,
        key=f"phase9f_f_paid_generation_acknowledgement_{application_id}",
    )
    if st.button(
        "Generate Projects + Skills",
        type="primary",
        width="stretch",
        key=f"generate_projects_skills_{application_id}",
        disabled=not acknowledged,
    ):
        with _forced_test_f_scope():
            result = run_phase9f_normal_generation(
                application_id=application_id,
                projects_writer=_projects_writer,
                skills_writer=_skills_writer,
                acknowledge_uncertain_model_retry=acknowledged,
                generation_settings={
                    "max_projects": max_projects,
                    "max_bullets": max_bullets,
                    "bullet_allocation_mode": allocation_mode,
                },
                generation_model="phase9f-f-settings-ui-model",
            )
        st.session_state["phase9f_f_test_generation_id"] = result["generation"]["generation_id"]
        st.rerun()

    generation_id = str(st.session_state.get("phase9f_f_test_generation_id") or "")
    if not generation_id:
        return
    fit_controls_locked = False
    st.subheader("Build and Fit Résumé Document")
    page_density = st.radio(
        "Page density",
        ["Fit only", "Balanced", "Maximize relevant content"],
        index=1,
        horizontal=True,
        key=f"page_density_mode_{application_id}",
        disabled=fit_controls_locked,
    )
    if st.button(
        "Build and Fit",
        type="primary",
        width="stretch",
        key=f"build_fit_{application_id}",
        disabled=fit_controls_locked,
    ):
        with _forced_test_f_scope():
            run_phase9f_normal_fit(
                application_id=application_id,
                generation_id=generation_id,
                fit_writer=_fit_writer,
                fit_settings={
                    "page_density_mode": {
                        "Fit only": "none",
                        "Balanced": "balanced",
                        "Maximize relevant content": "maximize",
                    }[page_density]
                },
            )
        st.rerun()


if surface == "settings":
    _render_settings_surface()
else:
    render_phase9f_tailoring_execution(
        application_id=application_id,
        phase9e_context={"confirmed_intensity": "minor"},
    )
    st.write("PHASE9F_F_RENDERED")
