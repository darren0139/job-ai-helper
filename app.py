"""
app.py — Streamlit of the Job AI Helper capstone app.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load local .env before project modules read configuration.
load_dotenv()

import pandas as pd
import streamlit as st
from analysis_stability.analysis_cache_mode import (
    ANALYSIS_CACHE_MODE_OPTIONS,
    resolve_analysis_cache_mode,
)
from pypdf import PdfReader
# ---------------------------------------------------------------------------
# Streamlit Cloud secrets -> environment variables
# ---------------------------------------------------------------------------
# llm.py reads environment variables when it is imported.
# Therefore, copy st.secrets into os.environ BEFORE importing analyzer.py / llm.py.
try:
    for key in (
        "MODEL",
        "ANALYSIS_MODEL",
        "CHAT_MODEL",
        "REASONING_EFFORT",
        "ANALYSIS_REASONING_EFFORT",
        "CHAT_REASONING_EFFORT",
        "LLM_SEED",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OLLAMA_API_BASE",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "CAPABILITY_RAG_MODE",
        "CAPABILITY_RAG_TOP_K",
        "CAPABILITY_RAG_VECTOR_THRESHOLD",
    ):
        if key in st.secrets and key not in os.environ:
            os.environ[key] = str(st.secrets[key])
except Exception:
    # Local development without Streamlit secrets is fine.
    # llm.py can still read your local .env through python-dotenv.
    pass


from tailoring.skills_section_tailor import tailor_skills_section, skill_lines_to_plain_text

from resume_builder.docx_projects_skills_replacer import (
    save_uploaded_docx_for_editing,
    get_latest_saved_docx_for_application,
    generate_tailored_resume_copy_fit_one_page,
    resolve_effective_fitting_bullet_ceiling,
    resolve_fitting_bullet_allocation_mode,
    generate_tailored_resume_copy,
    extract_docx_preview_text,
    convert_docx_to_pdf_if_possible,
    pdf_to_preview_html,
    cleanup_old_tailored_outputs_for_application,
    cleanup_application_resume_files,
)

from parse import read_resume_pdf, read_resume_docx, _MIN_JD_CHARS


from database.user_profile_manager import (
    init_user_profile_library,
    create_evidence_item,
    get_evidence_items,
    delete_evidence_item,
    update_evidence_item,
    clear_evidence_library,
)

from tailoring.project_section_tailor import (
    tailor_projects_section,
    estimate_project_section_length,
    build_project_candidate_pool,
)





from analyzer import (
    extract_resume_profile,
    extract_jd_profile,
    analyse_keyword_match,
    analyse_bullets,
    analyse_jargon,
    analyse_structure,
    analyse_degree_alignment,
    summarise_overall,
    compute_overall_score,
)
from analysis_stability import build_stable_analysis
from database.db_manager import (
    init_db,
    create_empty_application_session,
    save_application,
    update_application_report,
    update_application_cover_letter,
    rename_application_session,
    delete_application_session,
    get_recent_applications,
    get_application_by_id,
)
from database.analysis_cache_manager import (
    ANALYSIS_CACHE_VERSION,
    activate_analysis_snapshot,
    build_analysis_input_fingerprint,
    delete_application_analysis_versions,
    find_cached_analysis,
    init_analysis_cache,
    save_analysis_snapshot,
)
from database.application_blueprint_manager import (
    delete_application_blueprint_decisions,
    init_application_blueprint_decisions,
)
from database.application_resume_result_manager import (
    delete_application_resume_results,
    get_current_application_resume_result,
    init_application_resume_results,
)
from database.application_cover_letter_manager import (
    delete_application_cover_letters,
    init_application_cover_letters,
)
from database.tailoring_version_manager import (
    TAILORING_PERSISTENCE_VERSION,
    delete_application_tailoring_generations,
    get_restorable_application_tailoring,
    init_application_tailoring_versions,
    save_application_tailoring_generation,
)
from database.tailoring_verification_manager import (
    delete_application_tailoring_verifications,
    init_tailoring_verifications,
)
from database.evidence_opportunity_manager import (
    delete_application_evidence_opportunities,
)
from database.tailoring_generation_control import (
    delete_application_generation_control,
    ensure_mutable_tailoring_generation,
    find_cached_tailoring_generation,
    get_application_generation_control,
    get_tailoring_generation,
    list_tailoring_generations,
    init_tailoring_generation_control,
    record_generation_metadata,
)
from tailoring.tailoring_generation_fingerprint import (
    build_generation_action_plan,
    build_tailoring_input_fingerprint,
    constrain_generation_control_to_phase9e,
    get_effective_generation_sections,
    resolve_locked_sections,
    stable_content_fingerprint,
)
from tailoring.phase9b_blueprint_ui import (
    render_blueprint_candidate_promotion,
)
from tailoring.phase9c_blueprint_evaluation_ui import (
    render_phase9c_blueprint_evaluation,
)
from tailoring.phase9d_global_blueprint_ui import (
    render_phase9d_global_blueprints,
)
from tailoring.phase9e_blueprint_selection_ui import (
    render_phase9e_blueprint_selection,
)
from tailoring.phase9f_orchestrator_ui import render_phase9f_jd_intake
from tailoring.phase9e_application_result_ui import (
    render_phase9e_application_result,
)
from tailoring.phase9e1_resume_workspace_ui import (
    get_resume_workspace_context,
    should_clear_phase9e_session_state,
    workspace_requires_edit_draft,
)
from tailoring.phase9e1_workflow_ui import (
    render_application_workflow_overview,
    render_current_legacy_resume_result,
)
from tailoring.phase9e1_blueprint_lifecycle_ui import (
    load_blueprint_lifecycle_state,
    render_state_aware_blueprint_lifecycle,
)
from tailoring.application_output_integrations_ui import (
    render_application_output_cover_letter,
)
from tailoring.phase9a_evidence_opportunity_ui import (
    render_evidence_opportunity_analysis,
)
from tailoring.phase8_verification_ui import (
    render_phase8_verification,
)
from tailoring.generation_controls_ui import (
    render_tailoring_generation_controls,
    render_tailoring_section_update_scope,
    restore_generation_to_session,
)

from database.jd_library_manager import (
    init_jd_library,
    save_or_link_job_description_for_application,
    save_or_update_job_description_for_application,
    get_recent_job_descriptions,
    get_job_description_by_id,
    get_job_description_by_application_id,
    get_exact_job_description_for_application,
    delete_job_description,
    delete_job_description_by_application_id,
    unlink_job_description_from_application,
)

from database.chat_history_manager import (
    init_chat_history,
    add_application_chat_message,
    get_application_chat_messages,
    clear_application_chat_history,
    add_rag_chat_message,
    get_rag_chat_messages,
    clear_rag_chat_history,
)

from rag.jd_chroma_rag import (
    index_job_description_to_chroma,
    delete_job_description_from_chroma,
    rebuild_chroma_index,
    get_chroma_index_count,
    get_common_jd_terms,
    compare_resume_to_common_market_skills,
    answer_jd_library_question_chroma,
)


from tailoring.canonical_bullet_suggester import (
    suggest_canonical_project_bullets,
    canonical_bullets_to_description,
)


from report import render_markdown
from api_cost import (
    summarise_api_calls,
    summarise_api_calls_by_action,
)
from llm import (
    ask_text,
    drain_call_ledger,
    get_active_model,
    get_model_options,
    reset_call_ledger,
    set_runtime_model,
)

from prompts import COVER_LETTER_PROMPT, COVER_LETTER_REVISION_PROMPT


VALID_DEGREES = ["RTIS", "IMGD", "UXGD", "BFA"]
ATS_PASS_THRESHOLD = 60


ANALYSIS_QA_PROMPT = """
Instruction:
Answer the user's question about the resume-job analysis report.

Context:
You are an AI job application assistant. The user has already analysed a resume
against a job description. Use the analysis report to explain the result and give
practical improvement advice.

Constraints:
- Use only the provided analysis report.
- Do not invent resume experience, companies, skills, or achievements.
- If the report does not contain enough information, say so clearly.
- Give practical advice that is honest and suitable for a student or junior applicant.
- Do not rewrite the full resume.
- Keep the answer concise and easy to understand.

Output:
Return a clear plain-text answer.
"""


# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------

def init_session_state() -> None:
    """Initialize Streamlit session-state keys used by the app."""
    st.session_state.setdefault("input_reset_counter", 0)
    st.session_state.setdefault("revision_history", [])
    st.session_state.setdefault("analysis_chat", [])
    st.session_state.setdefault("rag_resume_profile", None)
    st.session_state.setdefault("rag_resume_source", "")


def _api_usage_key(application_id: int | None) -> str:
    suffix = (
        str(application_id)
        if application_id is not None
        else "unsaved"
    )
    return f"api_usage_calls_{suffix}"


def _seed_api_calls_from_report(
    report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    summary = report.get("api_cost_summary", {}) or {}
    return [
        dict(call)
        for call in summary.get("calls", []) or []
        if isinstance(call, dict)
    ]


def _last_action_event_key(
    application_id: int | None,
    action: str,
) -> str:
    suffix = (
        str(application_id)
        if application_id is not None
        else "unsaved"
    )
    return f"last_api_action_event_{suffix}_{action}"


def record_zero_cost_action_event(
    *,
    application_id: int | None,
    action: str,
    note: str,
) -> None:
    st.session_state[
        _last_action_event_key(application_id, action)
    ] = {
        "action": action,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "call_count": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "elapsed_seconds": 0.0,
        "estimated_total_cost_usd": 0.0,
        "unknown_cost_call_count": 0,
        "cost_estimate_complete": True,
        "note": str(note or ""),
        "source": "cache_or_local",
    }


def append_api_usage(
    *,
    application_id: int | None,
    action: str,
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    calls = drain_call_ledger()
    captured_at = datetime.now().isoformat(timespec="seconds")
    for index, call in enumerate(calls, start=1):
        call["action"] = action
        call["action_call_index"] = index
        call["captured_at"] = captured_at

    key = _api_usage_key(application_id)
    existing = st.session_state.get(key)
    if not isinstance(existing, list):
        existing = _seed_api_calls_from_report(report)

    existing.extend(calls)
    st.session_state[key] = existing

    action_summary = summarise_api_calls(calls)
    st.session_state[
        _last_action_event_key(application_id, action)
    ] = {
        **action_summary,
        "action": action,
        "captured_at": captured_at,
        "note": "",
        "source": "api",
    }

    summary = summarise_api_calls(existing)
    if isinstance(report, dict):
        report["api_cost_summary"] = summary
    return summary


def render_ai_action_subtotal(
    *,
    application_id: int | None,
    actions: list[str],
    label: str = "Last use subtotal",
) -> None:
    events = [
        st.session_state.get(
            _last_action_event_key(application_id, action)
        )
        for action in actions
    ]
    events = [
        event
        for event in events
        if isinstance(event, dict)
    ]
    if not events:
        return

    call_count = sum(
        int(event.get("call_count", 0) or 0)
        for event in events
    )
    total_tokens = sum(
        int(event.get("total_tokens", 0) or 0)
        for event in events
    )
    cost = sum(
        float(event.get("estimated_total_cost_usd", 0.0) or 0.0)
        for event in events
    )
    notes = [
        str(event.get("note") or "").strip()
        for event in events
        if str(event.get("note") or "").strip()
    ]

    st.caption(
        f"**{label}:** ${cost:.6f} USD · "
        f"{call_count} model call(s) · {total_tokens:,} tokens"
    )
    for note in dict.fromkeys(notes):
        st.caption(note)


def get_api_usage_summary(
    application_id: int | None,
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key = _api_usage_key(application_id)
    calls = st.session_state.get(key)
    if not isinstance(calls, list):
        calls = _seed_api_calls_from_report(report)
        if calls:
            st.session_state[key] = calls
    return summarise_api_calls(
        calls if isinstance(calls, list) else []
    )


def reset_current_application() -> None:
    """Clear the current in-memory application and reset input widgets."""
    st.session_state.pop("latest_report", None)
    st.session_state.pop("cover_letter", None)
    st.session_state.pop("resume_filename", None)
    st.session_state.pop("current_application_id", None)
    st.session_state["revision_history"] = []
    st.session_state["analysis_chat"] = []

    # Changing widget keys forces Streamlit to show fresh upload/text inputs.
    st.session_state["input_reset_counter"] += 1


# ---------------------------------------------------------------------------
# LLM feature functions
# ---------------------------------------------------------------------------

def generate_cover_letter(report: dict) -> str:
    """Generate a tailored cover letter using the completed resume analysis report."""
    resume_profile = report.get("resume_profile", {})
    jd_profile = report.get("jd_profile", {})
    keyword_match = report.get("keyword_match", {})
    degree_alignment = report.get("degree_alignment", {})
    summary = report.get("summary", "")

    user_prompt = f"""
RÉSUMÉ PROFILE:
{json.dumps(resume_profile, indent=2, ensure_ascii=False)}

JOB DESCRIPTION PROFILE:
{json.dumps(jd_profile, indent=2, ensure_ascii=False)}

KEYWORD MATCH ANALYSIS:
{json.dumps(keyword_match, indent=2, ensure_ascii=False)}

DEGREE ALIGNMENT:
{json.dumps(degree_alignment, indent=2, ensure_ascii=False)}

ANALYSIS SUMMARY:
{summary}

TASK:
Write a tailored cover letter for this job application.
"""

    cover_letter = ask_text(
        COVER_LETTER_PROMPT,
        user_prompt,
        temperature=0.4,
        max_tokens=900,
    ).strip()

    if not cover_letter:
        raise RuntimeError("The AI returned an empty cover letter.")

    return cover_letter


def revise_cover_letter(
    report: dict,
    current_letter: str,
    revision_request: str,
) -> str:
    """Revise the current cover letter based on the user's follow-up request."""
    if not current_letter.strip():
        raise ValueError("There is no existing cover letter to revise.")

    if not revision_request.strip():
        raise ValueError("Please enter a revision request first.")

    resume_profile = report.get("resume_profile", {})
    jd_profile = report.get("jd_profile", {})

    user_prompt = f"""
RÉSUMÉ PROFILE:
{json.dumps(resume_profile, indent=2, ensure_ascii=False)}

JOB DESCRIPTION PROFILE:
{json.dumps(jd_profile, indent=2, ensure_ascii=False)}

CURRENT COVER LETTER:
{current_letter}

USER REVISION REQUEST:
{revision_request}

TASK:
Revise the cover letter according to the user's request.
"""

    revised_letter = ask_text(
        COVER_LETTER_REVISION_PROMPT,
        user_prompt,
        temperature=0.4,
        max_tokens=900,
    ).strip()

    if not revised_letter:
        raise RuntimeError("The AI returned an empty revised cover letter.")

    return revised_letter


def answer_analysis_question(report: dict, question: str) -> str:
    """Answer a follow-up question about the current analysis report."""
    if not question.strip():
        raise ValueError("Please enter a question first.")

    user_prompt = f"""
ANALYSIS REPORT:
{json.dumps(report, indent=2, ensure_ascii=False)}

USER QUESTION:
{question}
"""

    answer = ask_text(
        ANALYSIS_QA_PROMPT,
        user_prompt,
        temperature=0.3,
        max_tokens=1000,
        route="chat",
    ).strip()

    if not answer:
        raise RuntimeError("The AI returned an empty answer.")

    return answer


def render_application_analysis_chat(
    *,
    application_id: int | None,
    analysis_report: dict[str, Any],
    persisted_report: dict[str, Any],
) -> None:
    """Render the existing persistent application-analysis chat.

    Immutable Phase 9E application results short-circuit the legacy tailoring
    workflow with ``st.stop()``. Rendering this shared component before that
    stop keeps the existing application-scoped chat available without creating
    or mutating a résumé draft.
    """
    st.divider()
    st.header("Ask About This Analysis")

    if application_id is None:
        st.info(
            "Save or load an application session before using saved chat."
        )
        return

    st.caption("Chat history is saved for this application session.")

    saved_analysis_messages = get_application_chat_messages(application_id)

    if saved_analysis_messages:
        for message in saved_analysis_messages:
            if message["role"] == "user":
                st.markdown(f"**You:** {message['content']}")
            else:
                st.markdown(f"**AI:** {message['content']}")
    else:
        st.caption("No questions asked for this session yet.")

    analysis_question = st.text_input(
        "Ask a question about the analysis",
        placeholder="Example: What should I improve first?",
        key=f"analysis_question_{application_id}",
    )

    chat_col, clear_col = st.columns([0.75, 0.25])

    with chat_col:
        if st.button(
            "Ask AI About Analysis",
            width="stretch",
            key=f"ask_analysis_ai_{application_id}",
        ):
            try:
                reset_call_ledger()
                with st.spinner("Answering question..."):
                    answer = answer_analysis_question(
                        analysis_report,
                        analysis_question,
                    )

                add_application_chat_message(
                    application_id,
                    "user",
                    analysis_question,
                )
                add_application_chat_message(
                    application_id,
                    "assistant",
                    answer,
                )

                append_api_usage(
                    application_id=application_id,
                    action="ask_analysis_ai",
                    report=persisted_report,
                )
                st.session_state["latest_report"] = persisted_report
                update_application_report(
                    application_id=application_id,
                    resume_filename=st.session_state.get(
                        "resume_filename",
                        "",
                    ),
                    report=persisted_report,
                )
                st.rerun()

            except ValueError as exc:
                st.warning(str(exc))
            except RuntimeError as exc:
                st.error(f"LLM/API error: {exc}")
            except Exception as exc:
                st.error(
                    "Unexpected error while answering question: "
                    f"{exc}"
                )

        render_ai_action_subtotal(
            application_id=application_id,
            actions=["ask_analysis_ai"],
            label="Ask AI About Analysis subtotal",
        )

    with clear_col:
        if st.button(
            "Clear Chat",
            width="stretch",
            key=f"clear_analysis_chat_{application_id}",
        ):
            clear_application_chat_history(application_id)
            st.rerun()


def render_application_analysis_details(
    *,
    report: dict[str, Any],
    current_application_id: int | None,
) -> None:
    """Render diagnostic analysis, reports, and usage as secondary details."""
    stable_analysis = report.get("stable_analysis", {}) or {}

    if stable_analysis:
        stable_score = int(
            stable_analysis.get(
                "deterministic_alignment_score",
                0,
            )
        )
        stable_band = stable_analysis.get(
            "alignment_band",
            "not classified",
        )
        st.info(
            f"Role alignment: {stable_score}/100 "
            f"— {stable_band.title()}"
        )
        st.caption(
            "This evidence-linked score uses fixed Python weights and "
            "constrained match labels. It is an alignment estimate, "
            "not an ATS acceptance probability."
        )

        boundary_status = (
            stable_analysis.get("boundary_status", {}) or {}
        )
        if boundary_status.get("is_borderline"):
            st.warning(
                "This result is close to an alignment-band boundary. "
                "Review the requirement evidence instead of treating a "
                "small point difference as pass/fail."
            )

        stable_col1, stable_col2, stable_col3, stable_col4 = st.columns(4)
        stable_col1.metric(
            "Required/Core Coverage",
            f"{stable_analysis.get('required_core_coverage_score', 0)}%",
        )
        stable_col2.metric(
            "Preferred Coverage",
            f"{stable_analysis.get('preferred_coverage_score', 0)}%",
        )
        stable_col3.metric(
            "Credited Requirements",
            (
                f"{stable_analysis.get('credited_requirement_count', 0)}"
                f"/{stable_analysis.get('requirement_count', 0)}"
            ),
        )
        stable_col4.metric(
            "Strength of Credited Evidence",
            f"{stable_analysis.get('evidence_strength_score', 0)}%",
        )

        with st.expander(
            "Evidence-linked requirement breakdown",
            expanded=False,
        ):
            show_result_table(
                stable_analysis.get(
                    "canonical_requirements",
                    [],
                ),
                "No canonical requirements were created.",
            )

            warnings = stable_analysis.get(
                "validation_warnings",
                [],
            )
            if warnings:
                st.write("### Validation warnings")
                show_result_table(
                    warnings,
                    "No validation warnings.",
                )

        st.subheader("Role Alignment Summary")
        st.markdown(build_stable_alignment_summary(report))

        st.subheader("Résumé Quality")
        quality_col1, quality_col2, quality_col3, quality_col4 = st.columns(4)
        quality_col1.metric(
            "Bullet Quality",
            report.get("bullets", {}).get("bullet_quality_avg", 0),
        )
        quality_col2.metric(
            "Structure",
            report.get("structure", {}).get("structure_score", 0),
        )
        quality_col3.metric(
            "Jargon Clarity",
            report.get("jargon", {}).get("jargon_score", 0),
        )
        quality_col4.metric(
            "Degree Relevance",
            report.get("degree_alignment", {}).get(
                "degree_alignment_score",
                0,
            ),
        )

        with st.expander(
            "Legacy AI-assisted comparison (development only)",
            expanded=False,
        ):
            legacy_col1, legacy_col2 = st.columns(2)
            legacy_col1.metric(
                "Legacy Composite",
                f"{overall_score}/100",
            )
            legacy_col2.metric(
                "AI Keyword Diagnostic",
                report.get("keyword_match", {}).get(
                    "keyword_match_score",
                    0,
                ),
            )
            st.caption(
                "This older composite is retained only for development "
                "comparison. It is not an ATS pass/fail result."
            )
            st.markdown(
                report.get(
                    "summary",
                    "_No legacy summary returned._",
                )
            )
    else:
        if passed:
            st.success(
                f"Score: {overall_score}/100 "
                f"({score_label(overall_score)})"
            )
        else:
            st.error(
                f"Score: {overall_score}/100 "
                f"({score_label(overall_score)})"
            )

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Keyword Match", report.get("keyword_match", {}).get("keyword_match_score", 0))
        col2.metric("Bullet Quality", report.get("bullets", {}).get("bullet_quality_avg", 0))
        col3.metric("Structure", report.get("structure", {}).get("structure_score", 0))
        col4.metric("Jargon", report.get("jargon", {}).get("jargon_score", 0))
        col5.metric("Degree Fit", report.get("degree_alignment", {}).get("degree_alignment_score", 0))

        st.subheader("Executive Summary")
        st.markdown(report.get("summary", "_No summary returned._"))

    tab_keywords, tab_bullets, tab_structure, tab_jargon, tab_degree, tab_raw = st.tabs(
        ["Keywords", "Bullets", "Structure", "Jargon", "Degree Fit", "Raw JSON"]
    )

    with tab_keywords:
        st.write("### Present Keywords")
        present = report.get("keyword_match", {}).get("present", [])
        show_result_table(present, "No present keywords returned.")
        # if present:
        #     st.dataframe(present, width="stretch")
        # else:
        #     st.info("No present keywords returned.")

        st.write("### Missing Keywords")
        missing = report.get("keyword_match", {}).get("missing", [])
        # if missing:
        #     st.dataframe(missing, width="stretch")
        # else:
        #     st.success("No missing keywords returned.")
        show_result_table(missing, "No missing keywords returned.")

    with tab_bullets:
        st.write("### Bullet Quality Audit")
        bullet_rows = report.get("bullets", {}).get("bullets", [])
        # if bullet_rows:
        #     st.dataframe(bullet_rows, width="stretch")
        # else:
        #     st.info("No bullet audit rows returned.")
        show_result_table(bullet_rows, "No missing keywords returned.")

    with tab_structure:
        st.write("### Three-Thirds / ATS Structure")
        st.json(report.get("structure", {}))

    with tab_jargon:
        st.write("### Jargon Flags")
        flags = report.get("jargon", {}).get("flags", [])
        # if flags:
        #     st.dataframe(flags, width="stretch")
        # else:
        #     st.success("No jargon flags returned.")
        show_result_table(flags, "No jargon flags returned.")

    with tab_degree:
        st.write("### Degree Alignment")
        st.json(report.get("degree_alignment", {}))

    with tab_raw:
        st.write("### Full Report JSON")
        st.json(report)

    usage_summary = get_api_usage_summary(
        current_application_id,
        report,
    )
    if usage_summary.get("call_count", 0):
        st.subheader("Application API Total and Breakdown")
        st.caption(
            "Each AI button shows its latest-use subtotal nearby. "
            "This section is the cumulative application total."
        )

        fitting_result_exists = bool(
            current_application_id is not None
            and st.session_state.get(
                "tailored_resume_fit_result_"
                f"{current_application_id}"
            )
        )

        zero_actions = []
        if fitting_result_exists:
            zero_actions.append(
                {
                    "action": (
                        "generate_and_fit_tailored_resume"
                    ),
                    "label": (
                        "Generate and Fit Tailored Resume"
                    ),
                    "note": (
                        "Local deterministic DOCX/PDF fitting; "
                        "no model API call."
                    ),
                }
            )

        stage_rows = summarise_api_calls_by_action(
            usage_summary.get("calls", []) or [],
            action_order=[
                "analyse_resume",
                "generate_projects",
                "generate_skills",
                "generate_projects_and_skills",
                "generate_and_fit_tailored_resume",
            ],
            action_labels={
                "analyse_resume": "Analyse Resume",
                "generate_projects": "Generate Projects",
                "generate_skills": "Generate Skills",
                "generate_projects_and_skills": (
                    "Generate Projects + Skills (legacy)"
                ),
                "generate_and_fit_tailored_resume": (
                    "Generate and Fit Tailored Resume"
                ),
            },
            zero_actions=zero_actions,
        )

        st.write("#### Total breakdown by AI action")
        st.dataframe(
            [
                {
                    "Stage": row.get("label", ""),
                    "Calls": row.get("call_count", 0),
                    "Input tokens": row.get(
                        "input_tokens",
                        0,
                    ),
                    "Output tokens": row.get(
                        "output_tokens",
                        0,
                    ),
                    "Total tokens": row.get(
                        "total_tokens",
                        0,
                    ),
                    "Estimated cost (USD)": (
                        "${:.6f}".format(
                            float(
                                row.get(
                                    "estimated_total_cost_usd",
                                    0.0,
                                )
                                or 0.0
                            )
                        )
                    ),
                    "Notes": row.get("note", ""),
                }
                for row in stage_rows
            ],
            hide_index=True,
            width="stretch",
        )

        st.write("#### Application total")
        usage_col1, usage_col2, usage_col3 = st.columns(3)
        usage_col1.metric(
            "Estimated API Cost",
            "${:.6f}".format(
                float(
                    usage_summary.get(
                        "estimated_total_cost_usd",
                        0.0,
                    )
                    or 0.0
                )
            ),
        )
        usage_col2.metric(
            "Tracked API Calls",
            usage_summary.get("call_count", 0),
        )
        usage_col3.metric(
            "Total Tokens",
            f"{usage_summary.get('total_tokens', 0):,}",
        )

        st.caption(
            "Estimated from provider-reported usage and the local "
            "price catalogue. DOCX/PDF fitting is deterministic "
            "local processing and has no model-token charge."
        )

        if not usage_summary.get(
            "cost_estimate_complete",
            True,
        ):
            st.warning(
                "Some tracked models are missing from the local "
                "price catalogue, so the cost is partial."
            )

        with st.expander(
            "API usage details",
            expanded=False,
        ):
            st.json(usage_summary)

    st.subheader("Download Reports")

    json_bytes = json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")
    markdown_text, markdown_filename = create_markdown_report(report)

    download_col1, download_col2 = st.columns(2)

    with download_col1:
        st.download_button(
            "Download JSON Report",
            data=json_bytes,
            file_name=f"match_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            width="stretch",
        )

    with download_col2:
        st.download_button(
            "Download Markdown Report",
            data=markdown_text,
            file_name=markdown_filename,
            mime="text/markdown",
            width="stretch",
        )

    if current_application_id is not None:
        tailored_projects_key = f"tailored_projects_result_{current_application_id}"
        tailored_fit_key = f"tailored_projects_fit_{current_application_id}"
        tailored_skills_key = f"tailored_skills_result_{current_application_id}"
        tailored_docx_key = f"tailored_resume_copy_path_{current_application_id}"
        tailored_fit_result_key = f"tailored_resume_fit_result_{current_application_id}"
        saved_docx_key = f"saved_resume_docx_path_{current_application_id}"
        tailored_generation_id_key = (
            f"tailored_generation_id_{current_application_id}"
        )


# ---------------------------------------------------------------------------
# File and report helpers
# ---------------------------------------------------------------------------

def create_full_debug_bundle(
    *,
    application_id: int | None,
    resume_filename: str,
    report: dict[str, Any] | None,
    candidate_pool: list[dict[str, Any]] | None,
    project_inputs: dict[str, Any] | None,
    project_result: dict[str, Any] | None,
    skills_result: dict[str, Any] | None,
    fit_estimate: dict[str, Any] | None,
    fit_result: dict[str, Any] | None,
) -> tuple[bytes, str]:
    """
    Combine all analysis and resume-tailoring debug data
    into one downloadable JSON file.

    API keys and Streamlit secrets are intentionally excluded.
    """
    final_projects_used: list[dict[str, Any]] = []

    if isinstance(fit_result, dict):
        tailored_projects_used = fit_result.get(
            "tailored_projects_used",
            {},
        )

        if isinstance(tailored_projects_used, dict):
            final_projects_used = (
                tailored_projects_used.get(
                    "recommended_projects",
                    [],
                )
                or []
            )

    # active_model = os.getenv(
    #     "MODEL",
    #     "openai/gpt-4o-mini",
    # )

    active_model = get_active_model("analysis")

    chat_model = get_active_model("chat")

    workspace_provenance_debug: dict[str, Any] = {}
    if application_id is not None:
        try:
            ws = get_resume_workspace_context(int(application_id))
            control = get_application_generation_control(int(application_id))
            binding = ws.get("phase9e_binding") or {}
            current_fp = str(binding.get("decision_fingerprint") or "")
            raw_approved = control.get("approved_generation")
            previous_approved = ws.get(
                "previous_scope_approved_generation"
            )
            generation_rows = []
            for row in list_tailoring_generations(int(application_id)):
                if not isinstance(row, dict):
                    continue
                row_fp = str(
                    row.get("phase9e_decision_fingerprint") or ""
                )
                generation_rows.append(
                    {
                        "generation_id": str(
                            row.get("generation_id") or ""
                        ),
                        "status": str(row.get("status") or ""),
                        "generation_kind": str(
                            row.get("generation_kind") or ""
                        ),
                        "phase9e_decision_fingerprint": row_fp,
                        "matches_current_phase9e": (
                            bool(
                                current_fp
                                and row_fp
                                and row_fp == current_fp
                            )
                            if row_fp
                            else None
                        ),
                    }
                )
            workspace_provenance_debug = {
                "current_phase9e": {
                    "decision_id": str(
                        binding.get("decision_id") or ""
                    ),
                    "decision_fingerprint": current_fp,
                    "selected_source": str(
                        (binding.get("selection") or {}).get(
                            "selected_source"
                        )
                        or binding.get("selected_source")
                        or ""
                    ),
                    "starting_snapshot_fingerprint": str(
                        binding.get("starting_snapshot_fingerprint")
                        or binding.get("source_snapshot_fingerprint")
                        or ""
                    ),
                },
                "workspace": {
                    "loaded_mode": str(ws.get("loaded_mode") or ""),
                    "current_approved_generation_id": str(
                        (ws.get("approved_generation") or {}).get(
                            "generation_id"
                        )
                        or ""
                    ),
                    "application_approved_generation_id": str(
                        (raw_approved or {}).get("generation_id") or ""
                    ),
                    "previous_scope_approved_generation_id": str(
                        (previous_approved or {}).get("generation_id")
                        or ""
                    ),
                },
                "generation_control": {
                    "approved_generation_id": str(
                        (raw_approved or {}).get("generation_id") or ""
                    ),
                    "approved_phase9e_decision_fingerprint": str(
                        (raw_approved or {}).get(
                            "phase9e_decision_fingerprint"
                        )
                        or ""
                    ),
                },
                "generations": generation_rows,
            }
        except Exception as exc:
            workspace_provenance_debug = {"error": str(exc)}

    debug_bundle = {
        "debug_meta": {
            "created_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "application_id": application_id,
            "resume_filename": resume_filename,
            "active_model": active_model,
            "chat_model": chat_model,
            # "reasoning_effort": os.getenv(

            #     "REASONING_EFFORT",
            #     "provider_default",
            # ),

            "reasoning_effort": os.getenv(
            "ANALYSIS_REASONING_EFFORT",
            os.getenv("REASONING_EFFORT",
                "provider_default",),
            ),
        },
        "analysis_report": report or {},
        "workspace_provenance_debug": workspace_provenance_debug,
        "api_cost_summary": get_api_usage_summary(
            application_id,
            report,
        ),
        "combined_project_candidate_pool": (
            candidate_pool or []
        ),
        "project_tailoring_inputs": (
            project_inputs or {}
        ),
        "project_length_estimate": (
            fit_estimate or {}
        ),
        "tailored_projects_result": (
            project_result or {}
        ),
        "tailored_skills_result": (
            skills_result or {}
        ),
        "one_page_fitting_result": (
            fit_result or {}
        ),
        "final_projects_used_in_docx": (
            final_projects_used
        ),
    }

    json_bytes = json.dumps(
        debug_bundle,
        indent=2,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    model_slug = (
        active_model
        .replace("/", "_")
        .replace(":", "_")
    )

    app_label = (
        str(application_id)
        if application_id is not None
        else "unsaved"
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"app_{app_label}_{model_slug}_"
        f"debug_bundle_{timestamp}.json"
    )

    return json_bytes, filename

def _markdown_escape(value: Any) -> str:
    """Escape table separators and line breaks for Markdown output."""
    return (
        str(value or "")
        .replace("|", "\\|")
        .replace("\n", " ")
        .strip()
    )


def build_stable_alignment_summary(report: dict[str, Any]) -> str:
    stable = report.get("stable_analysis", {}) or {}
    rows = stable.get("canonical_requirements", []) or []

    credited = [
        row
        for row in rows
        if row.get("match_label") != "none"
    ]
    gaps = [
        row
        for row in rows
        if row.get("match_label") == "none"
        and row.get("importance") in {"deal_breaker", "required", "core"}
    ]

    importance_order = {
        "deal_breaker": 4,
        "required": 3,
        "core": 2,
        "preferred": 1,
    }
    label_order = {
        "direct": 3,
        "transferable": 2,
        "weak": 1,
        "none": 0,
    }

    credited.sort(
        key=lambda row: (
            importance_order.get(str(row.get("importance")), 0),
            label_order.get(str(row.get("match_label")), 0),
            int(row.get("evidence_strength", 0)),
        ),
        reverse=True,
    )
    gaps.sort(
        key=lambda row: importance_order.get(
            str(row.get("importance")),
            0,
        ),
        reverse=True,
    )

    lines = [
        (
            f"- **Role alignment:** {stable.get('deterministic_alignment_score', 0)}/100 "
            f"— {str(stable.get('alignment_band', 'not classified')).title()}."
        )
    ]

    if credited:
        strongest = "; ".join(
            f"{row.get('text', '')} ({row.get('match_label', 'none')})"
            for row in credited[:3]
        )
        lines.append(f"- **Strongest credited matches:** {strongest}.")
    else:
        lines.append("- **Strongest credited matches:** No supported matches were credited.")

    if gaps:
        gap_text = "; ".join(
            str(row.get("text", ""))
            for row in gaps[:4]
        )
        lines.append(f"- **Most important evidence gaps:** {gap_text}.")

    lines.append(
        "- Review the evidence-linked requirement rows rather than treating "
        "the number as an ATS acceptance probability."
    )
    return "\n".join(lines)


def create_markdown_report(report: dict) -> tuple[str, str]:
    """Create a stable-first Markdown report without writing to outputs/."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"match_report_{timestamp}.md"

    stable = report.get("stable_analysis", {}) or {}
    resume_profile = report.get("resume_profile", {}) or {}
    jd_profile = report.get("jd_profile", {}) or {}
    bullets = report.get("bullets", {}) or {}
    structure = report.get("structure", {}) or {}
    jargon = report.get("jargon", {}) or {}
    degree = report.get("degree_alignment", {}) or {}
    keyword_match = report.get("keyword_match", {}) or {}

    lines: list[str] = [
        "# Résumé Analysis Report",
        "",
        f"**Candidate:** {_markdown_escape(resume_profile.get('name', ''))}",
        (
            f"**Target role:** {_markdown_escape(jd_profile.get('job_title', ''))}"
            f" @ {_markdown_escape(jd_profile.get('company', ''))}"
        ),
        f"**Generated:** {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    if stable:
        lines.extend(
            [
                "## Role Alignment",
                "",
                (
                    f"**Deterministic score:** "
                    f"{stable.get('deterministic_alignment_score', 0)}/100 "
                    f"— {str(stable.get('alignment_band', '')).title()}"
                ),
                "",
                (
                    "This is an evidence-linked résumé-to-JD alignment estimate, "
                    "not an ATS acceptance probability."
                ),
                "",
                f"- Required/Core coverage: **{stable.get('required_core_coverage_score', 0)}%**",
                f"- Preferred coverage: **{stable.get('preferred_coverage_score', 0)}%**",
                (
                    f"- Credited requirements: **{stable.get('credited_requirement_count', 0)}"
                    f" of {stable.get('requirement_count', 0)}**"
                ),
                (
                    f"- Strength of credited evidence: "
                    f"**{stable.get('evidence_strength_score', 0)}%**"
                ),
                "",
                "## Role Alignment Summary",
                "",
                build_stable_alignment_summary(report),
                "",
                "## Evidence-Linked Requirement Breakdown",
                "",
                "| Importance | Requirement | Label | Evidence |",
                "|---|---|---|---|",
            ]
        )

        for row in stable.get("canonical_requirements", []) or []:
            evidence_text = "; ".join(
                str(item.get("text", ""))
                for item in row.get("evidence", []) or []
                if isinstance(item, dict)
            ) or "—"
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_escape(row.get("importance", "")),
                        _markdown_escape(row.get("text", "")),
                        _markdown_escape(row.get("match_label", "none")),
                        _markdown_escape(evidence_text),
                    ]
                )
                + " |"
            )

        warnings = stable.get("validation_warnings", []) or []
        if warnings:
            lines.extend(["", "### Validation Warnings", ""])
            for warning in warnings:
                lines.append(
                    f"- `{_markdown_escape(warning.get('code', 'warning'))}`: "
                    f"{_markdown_escape(warning.get('message', ''))}"
                )

    lines.extend(
        [
            "",
            "## Résumé Quality",
            "",
            f"- Bullet quality: **{bullets.get('bullet_quality_avg', 0)}/100**",
            f"- Structure: **{structure.get('structure_score', 0)}/100**",
            f"- Jargon clarity: **{jargon.get('jargon_score', 0)}/100**",
            f"- Degree relevance: **{degree.get('degree_alignment_score', 0)}/100**",
            "",
            "## Legacy AI-Assisted Comparison",
            "",
            (
                "This development-only comparison is retained while the stable "
                "scoring system is validated. It is not a pass/fail ATS result."
            ),
            "",
            f"- Legacy composite: **{report.get('overall_score', 0)}/100**",
            f"- AI keyword diagnostic: **{keyword_match.get('keyword_match_score', 0)}/100**",
            "",
            "### Legacy AI Summary",
            "",
            report.get("summary", "_No legacy summary returned._"),
        ]
    )

    return "\n".join(lines).strip() + "\n", filename


def validate_jd_text(jd_text: str) -> str:
    """Validate job description text pasted into the Streamlit text area."""
    cleaned = jd_text.strip()

    if len(cleaned) < _MIN_JD_CHARS:
        raise ValueError(
            f"Job description text is too short ({len(cleaned)} chars). "
            f"Expected at least {_MIN_JD_CHARS} chars. "
            "Paste the full job description before analysing."
        )

    return cleaned


def read_uploaded_resume(uploaded_file: Any) -> str:
    """Read an uploaded resume file. Supports text-based PDF and DOCX files."""
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".pdf"):
        suffix = ".pdf"
    elif file_name.endswith(".docx"):
        suffix = ".docx"
    else:
        raise ValueError("Unsupported file type. Please upload a PDF or DOCX resume.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(uploaded_file.getbuffer())
        tmp_path = tmp_file.name

    try:
        if suffix == ".pdf":
            return read_resume_pdf(tmp_path)
        return read_resume_docx(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def calculate_uploaded_resume_page_count(
    uploaded_file: Any,
) -> int | None:
    """
    Calculate the rendered page count of an uploaded PDF or DOCX.

    PDF:
        Count its pages directly using pypdf.

    DOCX:
        Convert a temporary copy to PDF using LibreOffice,
        then count the PDF pages.

    Returns None when page counting is unavailable.
    """
    if uploaded_file is None:
        return None

    filename = str(
        getattr(uploaded_file, "name", "")
    ).lower()

    if filename.endswith(".pdf"):
        suffix = ".pdf"
    elif filename.endswith(".docx"):
        suffix = ".docx"
    else:
        return None

    temporary_path: Path | None = None
    generated_pdf_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temporary_file:
            temporary_file.write(
                uploaded_file.getbuffer()
            )
            temporary_path = Path(
                temporary_file.name
            )

        # A PDF already has an explicit page structure.
        if suffix == ".pdf":
            reader = PdfReader(
                str(temporary_path)
            )
            return len(reader.pages)

        # A DOCX must be rendered before its page count is known.
        generated_pdf_path = (
            convert_docx_to_pdf_if_possible(
                temporary_path
            )
        )

        if generated_pdf_path is None:
            return None

        reader = PdfReader(
            str(generated_pdf_path)
        )

        return len(reader.pages)

    except Exception:
        # Page counting should not prevent the main analysis
        # from running.
        return None

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

        if generated_pdf_path is not None:
            try:
                generated_pdf_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def run_resume_analysis(
    resume_text: str,
    jd_text: str,
    degree: str,
    *,
    actual_page_count: int | None = None,
) -> dict:
    """Run the full resume-job analysis pipeline and return the report dict."""
    progress = st.progress(0)
    log = st.container()

    log.write("[1/8] Reading resume and job description...")
    progress.progress(12)

    log.write("[2/8] Extracting resume profile...")
    resume_profile = extract_resume_profile(resume_text)
    progress.progress(25)

    log.write("[3/8] Extracting job description profile...")
    jd_profile = extract_jd_profile(jd_text)
    progress.progress(37)

    log.write("[4/8] Analysing keyword match...")
    keyword_match = analyse_keyword_match(resume_profile, jd_profile, resume_text, jd_text,)
    progress.progress(50)

    log.write("[5/8] Analysing bullet quality...")
    bullets = analyse_bullets(resume_profile)
    progress.progress(62)

    log.write("[6/8] Auditing jargon...")
    jargon = analyse_jargon(resume_profile, degree, jd_profile, jd_text)
    progress.progress(75)

    log.write("[7/8] Auditing resume structure...")
    # structure = analyse_structure(resume_text)
    structure = analyse_structure(
    resume_text,
    actual_page_count=actual_page_count,
    resume_profile=resume_profile,
    )
    progress.progress(87)

    log.write("[8/8] Analysing degree alignment...")
    degree_alignment = analyse_degree_alignment(jd_profile, degree)
    progress.progress(95)

    report = {
        "meta": {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            # "model": os.getenv("MODEL", "openai/gpt-4o-mini"),
            "model": get_active_model("analysis"),
            "degree": degree,
            "ats_pass_threshold": ATS_PASS_THRESHOLD,
            "actual_page_count": (actual_page_count),
        },
        "resume_profile": resume_profile,
        "jd_profile": jd_profile,
        "keyword_match": keyword_match,
        "bullets": bullets,
        "jargon": jargon,
        "structure": structure,
        "degree_alignment": degree_alignment,
    }

    log.write("[Final] Computing deterministic evidence-linked alignment...")
    report["stable_analysis"] = build_stable_analysis(
        jd_profile=jd_profile,
        keyword_match=keyword_match,
        raw_jd_text=jd_text,
        raw_resume_text=resume_text,
        resume_profile=resume_profile,
        bullet_quality_score=bullets.get("bullet_quality_avg", 0),
        structure_score=structure.get("structure_score", 0),
    )

    log.write("[Final] Computing legacy score and summary...")
    overall_score = compute_overall_score(report)
    report["overall_score"] = overall_score
    report["passes_ats_threshold"] = overall_score >= ATS_PASS_THRESHOLD
    report["summary"] = summarise_overall(report)

    progress.progress(100)

    return report


# def run_resume_analysis(resume_text: str, jd_text: str, degree: str) -> dict:
#     """Run the full resume-job analysis pipeline and return the report dict."""
#     progress = st.progress(0)
#     log = st.container()

#     log.write("[1/8] Reading resume and job description...")
#     progress.progress(12)

#     log.write("[2/8] Extracting resume profile...")
#     resume_profile = extract_resume_profile(resume_text)
#     progress.progress(25)

#     log.write("[3/8] Extracting job description profile...")
#     jd_profile = extract_jd_profile(jd_text)
#     progress.progress(37)

#     log.write("[4/8] Analysing keyword match...")
#     keyword_match = analyse_keyword_match(resume_profile, jd_profile, resume_text, jd_text,)
#     progress.progress(50)

#     log.write("[5/8] Analysing bullet quality...")
#     bullets = analyse_bullets(resume_profile)
#     progress.progress(62)

#     log.write("[6/8] Auditing jargon...")
#     jargon = analyse_jargon(resume_profile, degree, jd_profile)
#     progress.progress(75)

#     log.write("[7/8] Auditing resume structure...")
#     structure = analyse_structure(resume_text)
#     progress.progress(87)

#     log.write("[8/8] Analysing degree alignment...")
#     degree_alignment = analyse_degree_alignment(jd_profile, degree)
#     progress.progress(95)

#     report = {
#         "meta": {
#             "created_at": datetime.now().isoformat(timespec="seconds"),
#             "model": os.getenv("MODEL", "openai/gpt-4o-mini"),
#             "degree": degree,
#             "ats_pass_threshold": ATS_PASS_THRESHOLD,
#         },
#         "resume_profile": resume_profile,
#         "jd_profile": jd_profile,
#         "keyword_match": keyword_match,
#         "bullets": bullets,
#         "jargon": jargon,
#         "structure": structure,
#         "degree_alignment": degree_alignment,
#     }

#     log.write("[Final] Computing overall score and summary...")
#     overall_score = compute_overall_score(report)
#     report["overall_score"] = overall_score
#     report["passes_ats_threshold"] = overall_score >= ATS_PASS_THRESHOLD
#     report["summary"] = summarise_overall(report)

#     progress.progress(100)

#     return report


def score_label(score: int) -> str:
    """Return PASS/FAIL label for the ATS threshold."""
    if score >= ATS_PASS_THRESHOLD:
        return f"PASS — above {ATS_PASS_THRESHOLD}% ATS threshold"
    return f"FAIL — below {ATS_PASS_THRESHOLD}% ATS threshold"


def show_result_table(rows: Any, empty_message: str) -> None:
    """Display AI result rows safely without Streamlit dataframe rendering issues."""
    if not rows:
        st.info(empty_message)
        return

    try:
        if isinstance(rows, list):
            df = pd.json_normalize(rows)
        elif isinstance(rows, dict):
            df = pd.json_normalize([rows])
        else:
            df = pd.DataFrame(rows)

        if df.empty:
            st.info(empty_message)
            return

        # Convert nested/list values into readable strings.
        for column in df.columns:
            df[column] = df[column].apply(
                lambda value: json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list))
                else value
            )

        st.table(df.astype(str))

    except Exception:
        st.write(rows)


def _restore_application_tailoring_to_session(
    application_id: int,
) -> bool:
    """
    Restore the latest structured tailoring generation for an application.

    Sessions created before persistence was added can still recover their latest
    generated DOCX/PDF file when it remains on disk.
    """
    state = get_restorable_application_tailoring(
        application_id
    )
    if not isinstance(state, dict):
        return False

    prefix_values = {
        f"project_candidate_pool_{application_id}": state.get(
            "candidate_pool"
        ),
        f"debug_project_tailor_inputs_{application_id}": state.get(
            "project_inputs"
        ),
        f"tailored_projects_fit_{application_id}": state.get(
            "fit_estimate"
        ),
        f"tailored_projects_result_{application_id}": state.get(
            "projects"
        ),
        f"tailored_skills_result_{application_id}": state.get(
            "skills"
        ),
        f"tailored_resume_fit_result_{application_id}": state.get(
            "fit_result"
        ),
    }

    for key, value in prefix_values.items():
        if value is not None:
            st.session_state[key] = value

    generation_id = str(
        state.get("generation_id") or ""
    ).strip()
    if generation_id:
        st.session_state[
            f"tailored_generation_id_{application_id}"
        ] = generation_id

    docx_path = str(
        state.get("docx_path") or ""
    ).strip()
    if docx_path and Path(docx_path).exists():
        st.session_state[
            f"tailored_resume_copy_path_{application_id}"
        ] = docx_path

    settings = state.get(
        "generation_settings"
    )
    restored_settings_key = (
        f"restored_tailoring_settings_{application_id}"
    )

    if isinstance(settings, dict):
        # Keep persisted values separate from Streamlit widget keys. Writing a
        # restored value directly into a widget key and also supplying that
        # widget's `value`/`index` argument causes Streamlit's duplicate-default
        # warning on the next rerun.
        st.session_state[restored_settings_key] = dict(settings)
    else:
        st.session_state[restored_settings_key] = {}

    # Loading a session should recreate these widgets from the restored
    # defaults on the next rerun. Remove any values left by the previously
    # selected application so they cannot leak into this one.
    widget_keys = [
        f"max_projects_{application_id}",
        f"max_bullets_{application_id}",
        f"use_compact_before_delete_{application_id}",
        f"prefer_balanced_bullets_{application_id}",
        f"allow_skills_compaction_{application_id}",
        f"page_density_mode_{application_id}",
        f"allow_margin_compaction_{application_id}",
        f"spacing_mode_{application_id}",
        f"spacing_before_first_project_{application_id}",
        f"project_spacing_pt_{application_id}",
        f"after_projects_spacing_pt_{application_id}",
        f"blank_lines_between_projects_{application_id}",
        f"blank_lines_after_projects_{application_id}",
    ]

    for widget_key in widget_keys:
        st.session_state.pop(widget_key, None)

    return True


def _persist_current_tailoring_state(
    *,
    application_id: int,
    generation_id: str,
    generation_settings: dict[str, Any] | None = None,
    fit_result: dict[str, Any] | None = None,
    input_fingerprint: str = "",
    generation_kind: str = "",
) -> None:
    """Persist the current session-state tailoring payload."""
    save_application_tailoring_generation(
        application_id=application_id,
        generation_id=generation_id,
        candidate_pool=st.session_state.get(
            f"project_candidate_pool_{application_id}"
        ),
        project_inputs=st.session_state.get(
            f"debug_project_tailor_inputs_{application_id}"
        ),
        fit_estimate=st.session_state.get(
            f"tailored_projects_fit_{application_id}"
        ),
        projects=st.session_state.get(
            f"tailored_projects_result_{application_id}"
        ),
        skills=st.session_state.get(
            f"tailored_skills_result_{application_id}"
        ),
        fit_result=fit_result,
        generation_settings=generation_settings,
        docx_path=(
            fit_result.get("docx_path")
            if isinstance(fit_result, dict)
            else None
        ),
        pdf_path=(
            fit_result.get("pdf_path")
            if isinstance(fit_result, dict)
            else None
        ),
    )
    stored_generation = get_tailoring_generation(application_id, generation_id)
    effective_settings = (
        generation_settings
        if isinstance(generation_settings, dict)
        else (stored_generation or {}).get("generation_settings") or {}
    )
    phase9e_generation_binding = (
        effective_settings.get("phase9e_binding")
        if isinstance(effective_settings, dict)
        else {}
    ) or {}
    base_content_fingerprint = str(
        (stored_generation or {}).get("base_content_fingerprint") or ""
        or effective_settings.get("phase9e_base_content_fingerprint")
        or ""
    )
    current_content_fingerprint = ""
    content_changed = None
    if base_content_fingerprint:
        current_content_fingerprint = stable_content_fingerprint(
            {
                "projects": st.session_state.get(
                    f"tailored_projects_result_{application_id}"
                ),
                "skills": st.session_state.get(
                    f"tailored_skills_result_{application_id}"
                ),
            }
        )
        content_changed = current_content_fingerprint != base_content_fingerprint
    record_generation_metadata(
        application_id=application_id,
        generation_id=generation_id,
        input_fingerprint=input_fingerprint,
        generation_kind=generation_kind,
        base_content_fingerprint=base_content_fingerprint,
        content_fingerprint=current_content_fingerprint,
        content_changed=content_changed,
        phase9e_decision_fingerprint=str(
            phase9e_generation_binding.get("decision_fingerprint") or ""
        ),
    )


# ---------------------------------------------------------------------------
# Streamlit app
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Job AI Helper",
    page_icon="📄",
    layout="wide",
)

init_db()
init_application_tailoring_versions()
init_tailoring_generation_control()
init_analysis_cache()
init_tailoring_verifications()
init_application_blueprint_decisions()
init_application_resume_results()
init_application_cover_letters()

init_jd_library()
init_chat_history()
init_session_state()
init_user_profile_library()

st.title("📄 Job AI Helper")
st.caption("Analyze resume-job fit, save application sessions, and generate tailored cover letters.")

flash_message = st.session_state.pop("flash_message", "")
if flash_message:
    st.success(flash_message)


# Default values used by the Application Sessions page.
page = "Application Sessions"
degree = VALID_DEGREES[VALID_DEGREES.index("IMGD")]
show_debug_text = False

CATEGORY_OPTIONS = [
    "Project",
    "Internship",
    "Coursework",
    "Certification",
    "Skill",
    "Achievement",
    "Other",
]




with st.sidebar:
    st.header("Navigation")

    if st.session_state.get("navigation_page") == "Global Blueprints":
        st.session_state["navigation_page"] = "Blueprint Library"

    pending_navigation_page = st.session_state.pop(
        "_pending_navigation_page",
        "",
    )
    if pending_navigation_page == "Global Blueprints":
        pending_navigation_page = "Blueprint Library"
    if pending_navigation_page:
        st.session_state["navigation_page"] = pending_navigation_page

    page = st.radio(
        "Go to",
        [
            "Tailor Resume",
            "Application Sessions",
            "Blueprint Library",
            "Profile & Evidence",
            "Job Market Insights",
        ],
        key="navigation_page",
        label_visibility="collapsed",
    )

    st.divider()

    st.subheader("AI Models")

    model_options = get_model_options()
    model_labels = list(model_options.keys())

    current_analysis_model = get_active_model(
        "analysis"
    )

    current_chat_model = get_active_model(
        "chat"
    )

    analysis_default_index = next(
        (
            index
            for index, label in enumerate(
                model_labels
            )
            if model_options[label]
            == current_analysis_model
        ),
        0,
    )

    chat_default_index = next(
        (
            index
            for index, label in enumerate(
                model_labels
            )
            if model_options[label]
            == current_chat_model
        ),
        0,
    )

    analysis_model_label = st.selectbox(
        "Analysis model",
        model_labels,
        index=analysis_default_index,
        key="analysis_model_selector",
        help=(
            "Used for resume analysis, JD extraction, "
            "project scoring, bullet writing and "
            "cover-letter generation."
        ),
    )

    chat_model_label = st.selectbox(
        "Chatbot model",
        model_labels,
        index=chat_default_index,
        key="chat_model_selector",
        help=(
            "Used for analysis questions and the "
            "Job Market Insights RAG chatbot."
        ),
    )

    set_runtime_model(
        model_options[analysis_model_label],
        route="analysis",
    )

    set_runtime_model(
        model_options[chat_model_label],
        route="chat",
    )

    st.caption("Active analysis model")
    st.code(
        get_active_model("analysis")
    )

    st.caption("Active chatbot model")
    st.code(
        get_active_model("chat")
    )

    st.divider()

    if page == "Application Sessions":
        st.subheader("Settings")

        degree = st.selectbox(
            "Degree programme",
            VALID_DEGREES,
            index=VALID_DEGREES.index("IMGD"),
            help="Used for the degree-alignment score.",
        )

        show_debug_text = st.checkbox(
            "Show debug resume text",
            value=False,
            help="Shows extracted resume text after upload. Useful for checking PDF/DOCX parsing.",
        )

        st.divider()

        if st.button("➕ New Application Session", width="stretch"):
            application_id = create_empty_application_session(degree=degree)

            reset_current_application()
            st.session_state["current_application_id"] = application_id
            st.session_state["flash_message"] = (
                f"Started new application session #{application_id}. "
                "Upload a resume and paste a job description."
            )

            st.rerun()

        st.subheader("Application Sessions")

        recent_applications = get_recent_applications(limit=15)
        current_application_id = st.session_state.get("current_application_id")

        if not recent_applications:
            st.caption("No application sessions yet.")
        else:
            for app_id, session_name, job_title, company, score, has_report, updated_at in recent_applications:
                is_current = current_application_id == app_id

                if has_report:
                    display_name = session_name or job_title or f"Application {app_id}"

                    if score is not None:
                        label = f"{display_name} — {score}/100"
                    else:
                        label = display_name

                    if is_current:
                        label = f"✅ {label}"
                    else:
                        label = f"📄 {label}"
                else:
                    display_name = session_name or f"Application {app_id}"
                    label = f"✅ {display_name} (Draft)" if is_current else f"📝 {display_name} (Draft)"

                row_col, menu_col = st.columns([0.82, 0.18])

                with row_col:
                    if st.button(label, key=f"load_app_{app_id}", width="stretch"):
                        saved = get_application_by_id(app_id)

                        if saved:
                            if saved.get("report") is None:
                                st.session_state.pop("latest_report", None)
                            else:
                                st.session_state["latest_report"] = saved["report"]

                            st.session_state["cover_letter"] = saved.get("cover_letter", "")
                            st.session_state["resume_filename"] = saved.get("resume_filename", "")
                            st.session_state["current_application_id"] = app_id
                            st.session_state["revision_history"] = []
                            st.session_state["analysis_chat"] = []
                            _restore_application_tailoring_to_session(
                                app_id
                            )

                            # Clear upload/JD inputs when switching sessions.
                            # Saved sessions restore the report, not the original uploaded file.
                            st.session_state["input_reset_counter"] += 1

                            st.session_state["flash_message"] = f"Loaded application session #{app_id}."
                            st.rerun()

                with menu_col:
                    with st.popover("⋯", width="stretch"):
                        st.write(f"**{display_name}**")

                        new_name = st.text_input(
                            "Rename session",
                            value=display_name,
                            key=f"session_name_{app_id}",
                        )

                        if st.button("Rename", key=f"rename_app_{app_id}", width="stretch"):
                            cleaned_name = new_name.strip()

                            if cleaned_name:
                                rename_application_session(app_id, cleaned_name)
                                st.session_state["flash_message"] = "Session renamed."
                                st.rerun()
                            else:
                                st.warning("Session name cannot be empty.")

                        st.divider()

                        if st.button("Delete", key=f"delete_app_{app_id}", width="stretch"):
                            st.session_state["pending_delete_application_id"] = app_id
                            st.rerun()

                pending_delete_id = st.session_state.get("pending_delete_application_id")

                if pending_delete_id == app_id:
                    st.warning(f"Delete '{display_name}'? This cannot be undone.")

                    delete_local_files = st.checkbox(
                        "Also delete this session's saved résumé and generated DOCX/PDF files",
                        value=True,
                        key=f"delete_local_files_{app_id}",
                        help=(
                            "Deletes only app-owned files whose names begin with "
                            f"app_{app_id}_. Files you already downloaded elsewhere "
                            "are not affected."
                        ),
                    )

                    confirm_col, cancel_col = st.columns(2)

                    with confirm_col:
                        if st.button("Confirm", key=f"confirm_delete_{app_id}", width="stretch"):
                            # Remove only this session's link to the canonical JD.
                            # Delete shared SQLite/Chroma data only when no sessions remain.
                            try:
                                unlink_result = unlink_job_description_from_application(app_id)
                                if unlink_result.get("deleted_canonical_job"):
                                    delete_job_description_from_chroma(
                                        unlink_result.get("job_description_id"),
                                        canonical_jd_id=unlink_result.get("canonical_jd_id"),
                                    )
                            except Exception:
                                # Deleting the application session should still work even if RAG cleanup fails.
                                pass

                            delete_application_analysis_versions(
                                app_id
                            )
                            delete_application_tailoring_verifications(
                                app_id
                            )
                            delete_application_evidence_opportunities(
                                app_id
                            )
                            delete_application_generation_control(
                                app_id
                            )
                            delete_application_tailoring_generations(
                                app_id
                            )
                            delete_application_blueprint_decisions(
                                app_id
                            )
                            delete_application_resume_results(app_id)
                            delete_application_cover_letters(app_id)
                            delete_application_session(app_id)

                            cleanup_summary = {}
                            if delete_local_files:
                                cleanup_summary = cleanup_application_resume_files(
                                    app_id,
                                    delete_saved_resume=True,
                                    delete_generated_outputs=True,
                                    delete_libreoffice_profiles=True,
                                )

                            if current_application_id == app_id:
                                reset_current_application()

                            st.session_state.pop("pending_delete_application_id", None)

                            deleted_count = int(
                                cleanup_summary.get("deleted_file_count", 0)
                            )
                            if delete_local_files:
                                st.session_state["flash_message"] = (
                                    "Session deleted. "
                                    f"Removed {deleted_count} local résumé file(s)."
                                )
                            else:
                                st.session_state["flash_message"] = (
                                    "Session deleted. Local résumé files were kept."
                                )

                            st.rerun()

                    with cancel_col:
                        if st.button("Cancel", key=f"cancel_delete_{app_id}", width="stretch"):
                            st.session_state.pop("pending_delete_application_id", None)
                            st.rerun()

        st.divider()

        st.write("**How to use**")
        st.write("1. Click **New Application Session** to start a blank session.")
        st.write("2. Upload a PDF or DOCX resume.")
        st.write("3. Paste the target job description.")
        st.write("4. Click **Analyze Resume**.")
        st.write("5. Optionally generate or revise a cover letter.")

    elif page == "Tailor Resume":
        st.subheader("Tailor Resume")
        st.caption(
            "Analyse a job description without creating an Application Session."
        )
    elif page == "Job Market Insights":
        st.subheader("Job Market Insights")
        st.caption(
            "This page aggregates job descriptions from all previous Analyze Resume runs."
        )

        try:
            index_count = get_chroma_index_count()
            st.metric("Indexed Chunks", index_count)
        except Exception:
            st.metric("Indexed Chunks", 0)

        saved_jd_count = len(get_recent_job_descriptions(limit=200))
        st.metric("Analyzed JDs", saved_jd_count)

        st.info(
            "Run Analyze Resume on one or more jobs first. Then this page can answer questions across those analyzed job descriptions."
        )
    elif page == "Blueprint Library":
        st.subheader("Blueprint Library")
        st.caption(
            "Approve and inspect immutable reusable role-family blueprint versions."
        )
    else:
        st.subheader("Profile & Evidence")
        st.caption("Manage truthful reusable profile evidence.")


if page == "Tailor Resume":
    render_phase9f_jd_intake()

elif page == "Application Sessions":
    input_suffix = st.session_state["input_reset_counter"]

    has_loaded_application_report = bool(
        st.session_state.get("current_application_id") is not None
        and isinstance(st.session_state.get("latest_report"), dict)
    )
    input_panel = (
        st.expander(
            "Replace résumé or job description",
            expanded=False,
        )
        if has_loaded_application_report
        else st.container()
    )
    with input_panel:
        uploaded_resume = st.file_uploader(
            "Upload resume",
            type=["pdf", "docx"],
            key=f"resume_upload_{input_suffix}",
            help="Upload a text-based PDF or DOCX resume. Scanned PDFs may not parse correctly.",
        )

        uploaded_resume_is_docx = bool(
            uploaded_resume is not None
            and str(uploaded_resume.name).lower().endswith(".docx")
        )

        if uploaded_resume is None:
            save_resume_docx_for_editing = False
            st.caption(
                "Upload a DOCX when you want the app to generate an edited "
                "Word-document copy. PDFs can still be analysed."
            )
        elif uploaded_resume_is_docx:
            save_resume_docx_for_editing = st.checkbox(
                "Save this DOCX so the app can generate an edited resume copy",
                value=True,
                key=f"save_resume_docx_{input_suffix}",
                help=(
                    "The app saves a session-owned local copy. The uploaded "
                    "original is not overwritten."
                ),
            )
        else:
            save_resume_docx_for_editing = False
            st.info(
                "This PDF can be analysed, but tailored Word-document generation "
                "requires a DOCX source. Upload the DOCX version in a new or "
                "re-analysed session when you need an edited copy."
            )

        jd_text_input = st.text_area(
            "Paste job description",
            height=260,
            key=f"jd_text_{input_suffix}",
            placeholder=(
                "Paste the full job description here, including responsibilities, "
                "requirements, tools, technologies, and soft skills..."
            ),
        )

        analyze_clicked = st.button("Analyze Resume", type="primary", width="stretch")

        analysis_cache_mode = st.radio(
            "Analysis mode",
            options=ANALYSIS_CACHE_MODE_OPTIONS,
            index=0,
            horizontal=True,
            key=f"analysis_cache_mode_{input_suffix}",
            help=(
                "Choose exactly one mode. Reuse loads an exact saved analysis "
                "when available. Force fresh bypasses the cache and incurs normal "
                "model usage."
            ),
        )
        reuse_exact_analysis_cache, force_fresh_analysis = (
            resolve_analysis_cache_mode(analysis_cache_mode)
        )
        st.caption(
            "Reuse exact saved analysis avoids model calls on an exact cache hit. "
            "Force fresh AI analysis always runs the analysis pipeline again."
        )

    if analyze_clicked:
        if uploaded_resume is None:
            st.error("Please upload a resume first.")
            st.stop()

        if not jd_text_input.strip():
            st.error("Please paste a job description first.")
            st.stop()

        try:
            with st.status("Reading resume...", expanded=True) as status:
                resume_text = read_uploaded_resume(uploaded_resume)

                if show_debug_text:
                    with st.expander(
                        "Debug: Extracted resume text",
                        expanded=True,
                    ):
                        st.text(resume_text[-3000:])

                st.write(
                    f"Extracted {len(resume_text)} characters from resume."
                )
                actual_page_count = (
                    calculate_uploaded_resume_page_count(uploaded_resume)
                )
                if actual_page_count is None:
                    st.write(
                        "Rendered page count could not be determined. "
                        "Structure analysis will treat it as unknown."
                    )
                else:
                    st.write(
                        f"Detected {actual_page_count} rendered résumé page(s)."
                    )

                jd_text = validate_jd_text(jd_text_input)
                st.write(
                    f"Read {len(jd_text)} characters from job description."
                )

                application_id = st.session_state.get(
                    "current_application_id"
                )
                if application_id is None:
                    application_id = create_empty_application_session(
                        degree=degree
                    )
                    st.session_state[
                        "current_application_id"
                    ] = application_id

                analysis_fingerprint = build_analysis_input_fingerprint(
                    resume_text=resume_text,
                    jd_text=jd_text,
                    degree=degree,
                    actual_page_count=actual_page_count,
                    model_id=get_active_model("analysis"),
                    retrieval_config={
                        "capability_rag_mode": os.getenv(
                            "CAPABILITY_RAG_MODE",
                            "lexical",
                        ),
                        "capability_rag_top_k": os.getenv(
                            "CAPABILITY_RAG_TOP_K",
                            "5",
                        ),
                        "capability_rag_vector_threshold": os.getenv(
                            "CAPABILITY_RAG_VECTOR_THRESHOLD",
                            "0.30",
                        ),
                    },
                )

                cached_analysis = None
                if (
                    reuse_exact_analysis_cache
                    and not force_fresh_analysis
                ):
                    cached_analysis = find_cached_analysis(
                        application_id=application_id,
                        input_fingerprint=analysis_fingerprint,
                    )

                analysis_cache_hit = isinstance(
                    cached_analysis,
                    dict,
                )
                if analysis_cache_hit:
                    activated = activate_analysis_snapshot(
                        application_id=application_id,
                        analysis_id=str(
                            cached_analysis.get("analysis_id") or ""
                        ),
                    )
                    report = deepcopy(
                        activated.get("report") or {}
                    )
                    report["raw_jd_text"] = jd_text
                    report.setdefault("meta", {})[
                        "analysis_cache"
                    ] = {
                        "status": "hit",
                        "input_fingerprint": analysis_fingerprint,
                        "analysis_id": activated.get(
                            "analysis_id",
                            "",
                        ),
                        "cache_version": ANALYSIS_CACHE_VERSION,
                    }
                    record_zero_cost_action_event(
                        application_id=application_id,
                        action="analyse_resume",
                        note=(
                            "Exact persistent analysis cache hit; "
                            "the résumé/JD analysis AI was not called."
                        ),
                    )
                    status.update(
                        label="Loaded exact saved analysis.",
                        state="complete",
                    )
                else:
                    status.update(
                        label="Running AI analysis...",
                        state="running",
                    )
                    reset_call_ledger()
                    report = run_resume_analysis(
                        resume_text,
                        jd_text,
                        degree,
                        actual_page_count=actual_page_count,
                    )
                    report["raw_jd_text"] = jd_text
                    report.setdefault("meta", {})[
                        "analysis_cache"
                    ] = {
                        "status": (
                            "forced_refresh"
                            if force_fresh_analysis
                            else "miss"
                        ),
                        "input_fingerprint": analysis_fingerprint,
                        "analysis_id": "",
                        "cache_version": ANALYSIS_CACHE_VERSION,
                    }
                    status.update(
                        label="Analysis complete.",
                        state="complete",
                    )

            application_id = int(
                st.session_state["current_application_id"]
            )

            update_application_report(
                application_id=application_id,
                resume_filename=uploaded_resume.name,
                report=report,
            )

            # A genuine fresh analysis replaces what is currently displayed,
            # but historical approved/draft generations and their output files
            # remain persisted for comparison and restoration.
            if not analysis_cache_hit:
                for key in [
                    f"tailored_projects_result_{application_id}",
                    f"tailored_projects_fit_{application_id}",
                    f"tailored_skills_result_{application_id}",
                    f"tailored_resume_copy_path_{application_id}",
                    f"tailored_resume_fit_result_{application_id}",
                    f"debug_project_tailor_inputs_{application_id}",
                    f"project_candidate_pool_{application_id}",
                    f"project_tailor_debug_path_{application_id}",
                    f"project_tailor_input_fingerprint_{application_id}",
                ]:
                    st.session_state.pop(key, None)

            if save_resume_docx_for_editing:
                if uploaded_resume.name.lower().endswith(".docx"):
                    saved_resume_docx_path = (
                        save_uploaded_docx_for_editing(
                            uploaded_resume,
                            application_id=application_id,
                        )
                    )
                    st.session_state[
                        "saved_resume_docx_path"
                    ] = str(saved_resume_docx_path)
                    st.session_state[
                        f"saved_resume_docx_path_{application_id}"
                    ] = str(saved_resume_docx_path)
                else:
                    st.warning(
                        "Analysis was saved, but editable résumé-copy "
                        "generation requires a DOCX file."
                    )

            jd_library_message = ""
            try:
                jd_profile_for_library = report.get(
                    "jd_profile",
                    {},
                )
                jd_save_result = (
                    save_or_link_job_description_for_application(
                        application_id=application_id,
                        raw_text=jd_text,
                        jd_profile=jd_profile_for_library,
                        title=jd_profile_for_library.get(
                            "job_title",
                            "",
                        ),
                        company=jd_profile_for_library.get(
                            "company",
                            "",
                        ),
                        location=jd_profile_for_library.get(
                            "location",
                            "",
                        ),
                        source_type="application_session",
                        source_url="",
                    )
                )
                orphaned_canonical_id = jd_save_result.get(
                    "orphaned_canonical_jd_id"
                )
                if orphaned_canonical_id:
                    delete_job_description_from_chroma(
                        jd_save_result.get(
                            "orphaned_job_description_id"
                        ),
                        canonical_jd_id=orphaned_canonical_id,
                    )
                if jd_save_result.get("needs_chroma_index"):
                    chunk_count = index_job_description_to_chroma(
                        int(jd_save_result["job_description_id"])
                    )
                    jd_library_message = (
                        " Indexed canonical JD into Chroma with "
                        f"{chunk_count} chunks."
                    )
                else:
                    jd_library_message = (
                        " Reused the existing canonical JD; no duplicate "
                        "embeddings were created."
                    )
            except Exception as rag_exc:
                jd_library_message = (
                    f" RAG indexing skipped: {rag_exc}"
                )

            if not analysis_cache_hit:
                append_api_usage(
                    application_id=application_id,
                    action="analyse_resume",
                    report=report,
                )
                snapshot = save_analysis_snapshot(
                    application_id=application_id,
                    input_fingerprint=analysis_fingerprint,
                    report=report,
                    analysis_model=get_active_model("analysis"),
                    resume_filename=uploaded_resume.name,
                )
                report.setdefault("meta", {})[
                    "analysis_cache"
                ]["analysis_id"] = snapshot.get(
                    "analysis_id",
                    "",
                )

            update_application_report(
                application_id=application_id,
                resume_filename=uploaded_resume.name,
                report=report,
            )
            st.session_state["latest_report"] = report
            st.session_state["resume_filename"] = uploaded_resume.name
            st.session_state[
                "current_application_id"
            ] = application_id
            st.session_state.pop("cover_letter", None)
            st.session_state["revision_history"] = []
            st.session_state["analysis_chat"] = []
            st.session_state["flash_message"] = (
                f"Saved application session #{application_id}."
                f"{jd_library_message}"
            )
            st.rerun()

        except ValueError as exc:
            st.error(f"Input error: {exc}")
            st.stop()
        except RuntimeError as exc:
            st.error(f"LLM/API error: {exc}")
            st.info(
                "Check your .env file locally, or Streamlit Cloud "
                "secrets after deployment."
            )
            st.stop()
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")
            st.stop()

    render_ai_action_subtotal(
        application_id=st.session_state.get(
            "current_application_id"
        ),
        actions=["analyse_resume"],
        label="Analyse Resume subtotal",
    )


    report = st.session_state.get("latest_report")
    current_application_id = st.session_state.get("current_application_id")

    if report:
        overall_score = int(report.get("overall_score", 0))
        passed = bool(report.get("passes_ats_threshold", False))

        st.divider()
        st.header("Results")

        has_current_legacy_result = False
        if current_application_id is not None:
            st.caption(f"Current application session: #{current_application_id}")
            render_application_workflow_overview(
                application_id=int(current_application_id),
                baseline_report=report,
            )
            has_current_legacy_result = (
                render_current_legacy_resume_result(
                    application_id=int(current_application_id),
                )
            )

        phase9a_jd_record: dict[str, Any] = {}
        if current_application_id is not None:
            phase9a_jd_record = (
                get_exact_job_description_for_application(
                    int(current_application_id)
                )
                or {}
            )

        persisted_application_report = report
        phase9e_context: dict[str, Any] = {
            "status": "unbound",
            "can_generate": False,
            "reasons": [
                "Bind a current Phase 9E starting source before tailoring."
            ],
        }
        if current_application_id is not None:
            if has_current_legacy_result:
                with st.expander(
                    "Optional Phase 9E source migration",
                    expanded=False,
                ):
                    phase9e_context = (
                        render_phase9e_blueprint_selection(
                            application_id=int(current_application_id),
                            baseline_report=persisted_application_report,
                        )
                    )
            else:
                phase9e_context = render_phase9e_blueprint_selection(
                    application_id=int(current_application_id),
                    baseline_report=persisted_application_report,
                )
            try:
                current_application_result = (
                    get_current_application_resume_result(
                        int(current_application_id)
                    )
                )
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
                st.stop()
            if (
                current_application_result is not None
                and (
                    current_application_result.get("state") or {}
                ).get("active_output_mode") == "immutable_result"
                and current_application_result.get(
                    "phase9e_decision_fingerprint"
                )
                == (
                    phase9e_context.get("decision") or {}
                ).get("decision_fingerprint")
                and phase9e_context.get("status") == "current"
            ):
                render_phase9e_application_result(
                    application_id=int(current_application_id),
                    result=current_application_result,
                )
                phase9a_raw_jd_text = str(
                    phase9a_jd_record.get("raw_text")
                    or persisted_application_report.get("raw_jd_text")
                    or ""
                )
                render_evidence_opportunity_analysis(
                    application_id=int(current_application_id),
                    baseline_report=persisted_application_report,
                    raw_jd_text=phase9a_raw_jd_text,
                    evidence_items=get_evidence_items(limit=100),
                    collapsed=True,
                )
                with st.expander(
                    "Match, scores, reports, and API usage",
                    expanded=False,
                ):
                    render_application_analysis_details(
                        report=persisted_application_report,
                        current_application_id=current_application_id,
                    )
                render_application_analysis_chat(
                    application_id=int(current_application_id),
                    analysis_report=persisted_application_report,
                    persisted_report=persisted_application_report,
                )
                st.stop()

        if current_application_id is not None:
            phase9a_raw_jd_text = str(
                phase9a_jd_record.get("raw_text")
                or persisted_application_report.get("raw_jd_text")
                or ""
            )
            phase9a_decision = (
                phase9e_context.get("decision") or {}
            ).get("recommended_tailoring")
            phase9a_decision_fingerprint = str(
                (
                    phase9e_context.get("binding_identity") or {}
                ).get("decision_fingerprint")
                or (
                    phase9e_context.get("decision") or {}
                ).get("decision_fingerprint")
                or ""
            )
            phase9a_lifecycle_state = load_blueprint_lifecycle_state(
                application_id=int(current_application_id),
                current_phase9e_decision_fingerprint=(
                    phase9a_decision_fingerprint
                ),
            )
            phase9a_lifecycle_stage = str(
                (
                    phase9a_lifecycle_state.get("summary") or {}
                ).get("current_stage")
                or ""
            )
            phase9a_workspace_state = get_resume_workspace_context(
                int(current_application_id)
            )
            phase9a_has_working_draft = bool(
                phase9a_workspace_state.get("loaded_mode")
                == "working_draft"
                and isinstance(
                    phase9a_workspace_state.get("loaded_generation"),
                    dict,
                )
            )
            render_evidence_opportunity_analysis(
                application_id=int(current_application_id),
                baseline_report=persisted_application_report,
                raw_jd_text=phase9a_raw_jd_text,
                evidence_items=get_evidence_items(limit=100),
                collapsed=(
                    (phase9a_has_working_draft or (phase9a_decision in {
                        "reuse_approved_source",
                        "reuse_unchanged",
                    }
                    or phase9a_lifecycle_stage in {
                        "phase9b",
                        "phase9c",
                        "phase9d",
                        "phase9e",
                    }))
                ),
            )

        with st.expander(
            "Match, scores, reports, and API usage",
            expanded=False,
        ):
            render_application_analysis_details(
                report=persisted_application_report,
                current_application_id=current_application_id,
            )

        phase9e_ready = bool(phase9e_context.get("can_generate"))
        phase9e_enforced = bool(phase9e_context.get("phase9e_enforced"))
        phase9e_binding = deepcopy(
            phase9e_context.get("binding_identity") or {}
        )
        phase9e_base_content_fingerprint = (
            stable_content_fingerprint(
                phase9e_context.get("starting_sections") or {}
            )
            if phase9e_enforced and phase9e_ready
            else ""
        )
        phase9e_section_scope = deepcopy(
            phase9e_context.get("section_lock_scope")
            or (
                phase9e_context.get("decision") or {}
            ).get("section_lock_scope")
            or {}
        )
        phase9e_projects_locked = bool(
            phase9e_section_scope.get("projects_locked")
        )
        phase9e_skills_locked = bool(
            phase9e_section_scope.get("skills_locked")
        )
        if phase9e_ready:
            report = deepcopy(phase9e_context["effective_report"])
            if phase9e_enforced:
                binding_marker = str(
                    phase9e_binding.get("decision_fingerprint") or ""
                )
                binding_marker += ":" + str(
                    phase9e_binding.get("workflow_action_fingerprint") or ""
                )
            else:
                binding_marker = f"legacy:{current_application_id}"
        else:
            report = deepcopy(persisted_application_report)
            binding_marker = f"blocked:{phase9e_context.get('status', 'unknown')}"

        if current_application_id is not None:
            marker_key = f"phase9e_session_binding_{current_application_id}"
            previous_marker = st.session_state.get(marker_key)
            if should_clear_phase9e_session_state(
                previous_marker=previous_marker,
                binding_marker=binding_marker,
                phase9e_enforced=phase9e_enforced,
            ):
                for key in (
                    f"tailored_projects_result_{current_application_id}",
                    f"tailored_projects_fit_{current_application_id}",
                    f"tailored_skills_result_{current_application_id}",
                    f"tailored_resume_copy_path_{current_application_id}",
                    f"tailored_resume_fit_result_{current_application_id}",
                    f"tailored_generation_id_{current_application_id}",
                    f"debug_project_tailor_inputs_{current_application_id}",
                    f"project_candidate_pool_{current_application_id}",
                ):
                    st.session_state.pop(key, None)
            st.session_state[marker_key] = binding_marker

        st.divider()
        st.header("Tailor Résumé Content")
        st.caption(
            "Phase 6B uses canonical requirement IDs and fixed Python weights "
            "for Project selection and Skills priorities. AI numeric scores are "
            "diagnostic only."
        )

        workspace_edit_required = False
        workspace_message_context: dict[str, Any] = {}
        previous_scope_message_approved: dict[str, Any] | None = None
        if current_application_id is not None:
            workspace_edit_required = workspace_requires_edit_draft(
                int(current_application_id)
            )
            workspace_message_context = (
                get_resume_workspace_context(
                    int(current_application_id)
                )
                or {}
            )
            candidate_previous_scope = workspace_message_context.get(
                "previous_scope_approved_generation"
            )
            if isinstance(candidate_previous_scope, dict):
                previous_scope_message_approved = candidate_previous_scope

        if workspace_edit_required:
            if isinstance(previous_scope_message_approved, dict):
                previous_scope_id = str(
                    previous_scope_message_approved.get("generation_id")
                    or ""
                )[:8]
                st.info(
                    "Approved résumé "
                    f"{previous_scope_id or 'result'} belongs to a previous "
                    "Tailoring Base and is read-only. Use Start new résumé "
                    "from current Tailoring Base in the Résumé Workspace "
                    "before generating new Projects or Skills. The existing "
                    "approved result and its earlier lineage remain preserved."
                )
            else:
                st.info(
                    "The current approved résumé is read-only. Use "
                    "Revise approved résumé from the Résumé Workspace "
                    "to remove the approval and continue normal editing, "
                    "or Create alternative copy to experiment while "
                    "keeping the approved result active."
                )

        if current_application_id is None:
            st.info("Save or load an application session before tailoring the resume.")
        else:
            if not phase9e_ready:
                st.error(
                    "Résumé generation is blocked until the current Phase 9E "
                    "scope is explicitly evaluated and bound."
                )
                for reason in phase9e_context.get("reasons") or []:
                    st.write(f"- {reason}")
            elif phase9e_enforced:
                source = phase9e_context["decision"]["selection"].get(
                    "effective_starting_source"
                ) or phase9e_context["decision"]["selection"][
                    "selected_source"
                ]
                st.success(
                    "All downstream tailoring inputs are using a deep copy of "
                    f"the current immutable Phase 9E {source.replace('_', ' ')} snapshot."
                )
            else:
                st.info(
                    phase9e_context.get("legacy_notice")
                    or "The existing legacy generation scope remains current."
                )
            tailored_projects_key = f"tailored_projects_result_{current_application_id}"
            tailored_fit_key = f"tailored_projects_fit_{current_application_id}"
            tailored_skills_key = f"tailored_skills_result_{current_application_id}"
            tailored_docx_key = f"tailored_resume_copy_path_{current_application_id}"
            tailored_fit_result_key = f"tailored_resume_fit_result_{current_application_id}"
            saved_docx_key = f"saved_resume_docx_path_{current_application_id}"
            tailored_generation_id_key = (
                f"tailored_generation_id_{current_application_id}"
            )

            restored_settings = st.session_state.get(
                f"restored_tailoring_settings_{current_application_id}",
                {},
            )
            if not isinstance(restored_settings, dict):
                restored_settings = {}

            phase7_control = get_application_generation_control(
                current_application_id
            )
            if phase9e_enforced:
                phase7_control = constrain_generation_control_to_phase9e(
                    phase7_control,
                    phase9e_binding,
                )
            phase7_flash = st.session_state.pop(
                f"phase7_flash_{current_application_id}",
                "",
            )
            if phase7_flash:
                st.success(phase7_flash)

            (
                lock_projects,
                lock_skills,
                update_scope_dirty,
            ) = render_tailoring_section_update_scope(
                application_id=current_application_id,
                required_phase9e_binding=(
                    phase9e_binding
                    if phase9e_enforced
                    else None
                ),
                disabled=(
                    workspace_edit_required
                    or not phase9e_ready
                ),
            )
            project_controls_disabled = (
                workspace_edit_required
                or lock_projects
                or phase9e_projects_locked
                or update_scope_dirty
            )

            max_projects = st.slider(
                "Maximum projects",
                min_value=1,
                max_value=8,
                value=int(restored_settings.get("max_projects", 3)),
                key=f"max_projects_{current_application_id}",
                disabled=project_controls_disabled,
            )

            saved_bullet_allocation_mode = str(
                restored_settings.get(
                    "bullet_allocation_mode",
                    "prefer_available_evidence",
                )
            ).strip().lower()

            bullet_allocation_options = [
                "Adaptive",
                "Prefer available evidence",
                "Fit from all canonical evidence",
            ]
            if (
                saved_bullet_allocation_mode
                == "all_canonical_before_fitting"
            ):
                bullet_allocation_index = 2
            elif (
                saved_bullet_allocation_mode
                == "prefer_available_evidence"
            ):
                bullet_allocation_index = 1
            else:
                bullet_allocation_index = 0

            bullet_allocation_label = st.radio(
                "Bullet allocation",
                bullet_allocation_options,
                index=bullet_allocation_index,
                horizontal=True,
                key=f"bullet_allocation_mode_{current_application_id}",
                disabled=project_controls_disabled,
                help=(
                    "Adaptive starts compact and expands only when evidence gates "
                    "justify another bullet. Prefer available evidence includes "
                    "truthful canonical bullets up to the Bullet limit per project. "
                    "Fit from all canonical evidence sends every available truthful "
                    "canonical bullet from each selected project into fitting, where "
                    "lower-value content is removed only if needed for one page."
                ),
            )
            if (
                bullet_allocation_label
                == "Fit from all canonical evidence"
            ):
                bullet_allocation_mode = (
                    "all_canonical_before_fitting"
                )
            elif (
                bullet_allocation_label
                == "Prefer available evidence"
            ):
                bullet_allocation_mode = (
                    "prefer_available_evidence"
                )
            else:
                bullet_allocation_mode = "adaptive"

            max_bullets = st.slider(
                "Bullet limit per project",
                min_value=1,
                max_value=4,
                value=int(restored_settings.get("max_bullets", 3)),
                key=f"max_bullets_{current_application_id}",
                disabled=(
                    project_controls_disabled
                    or bullet_allocation_mode
                    == "all_canonical_before_fitting"
                ),
                help=(
                    "Adaptive and Prefer available evidence use this as a "
                    "pre-fit per-project ceiling. Fit from all canonical evidence "
                    "ignores this ceiling and lets the one-page fitter determine "
                    "the final retained bullet count."
                ),
            )
            if (
                bullet_allocation_mode
                == "all_canonical_before_fitting"
            ):
                st.caption(
                    "Bullet limit is disabled in this mode. All available "
                    "truthful canonical bullets enter fitting; the fitter then "
                    "compacts or removes lower-value evidence only when needed."
                )

            generation_plan = build_generation_action_plan(
                lock_projects=lock_projects,
                lock_skills=lock_skills,
                approved_generation=phase7_control.get(
                    "approved_generation"
                ),
            )
            if phase9e_projects_locked and phase9e_skills_locked:
                generation_plan = {
                    "mode": "load_phase9e_starting_snapshot",
                    "button_label": "Load Phase 9E Starting Projects + Skills",
                    "requires_project_ai": False,
                    "requires_skills_ai": False,
                    "creates_draft": True,
                    "note": (
                        "The deterministic decision is Reuse Unchanged. Load "
                        "Projects and Skills from the immutable starting "
                        "snapshot with zero model calls."
                    ),
                }
            st.caption(generation_plan["note"])

            if st.button(
                generation_plan["button_label"],
                type="primary",
                width="stretch",
                key=f"generate_projects_skills_{current_application_id}",
                disabled=(
                    not phase9e_ready
                    or workspace_edit_required
                    or update_scope_dirty
                ),
            ):
                try:
                    evidence_items = get_evidence_items(limit=100)
                    generation_settings = {
                        "max_projects": max_projects,
                        "max_bullets": max_bullets,
                        "bullet_allocation_mode": bullet_allocation_mode,
                        "phase9e_binding": deepcopy(phase9e_binding),
                        "phase9e_base_content_fingerprint": (
                            phase9e_base_content_fingerprint
                        ),
                    }
                    phase7_control = get_application_generation_control(
                        current_application_id
                    )
                    if phase9e_enforced:
                        phase7_control = constrain_generation_control_to_phase9e(
                            phase7_control,
                            phase9e_binding,
                        )
                    approved_generation = phase7_control.get(
                        "approved_generation"
                    )
                    lock_projects = bool(
                        phase7_control.get("lock_projects")
                    )
                    lock_skills = bool(
                        phase7_control.get("lock_skills")
                    )
                    generation_plan = build_generation_action_plan(
                        lock_projects=lock_projects,
                        lock_skills=lock_skills,
                        approved_generation=approved_generation,
                    )
                    if phase9e_projects_locked and phase9e_skills_locked:
                        generation_plan = {
                            "mode": "load_phase9e_starting_snapshot",
                            "button_label": (
                                "Load Phase 9E Starting Projects + Skills"
                            ),
                            "requires_project_ai": False,
                            "requires_skills_ai": False,
                            "creates_draft": True,
                            "note": "Reuse the immutable Phase 9E snapshot.",
                        }

                    if generation_plan["mode"] == "load_phase9e_starting_snapshot":
                        starting_sections = deepcopy(
                            phase9e_context["starting_sections"]
                        )
                        project_result = starting_sections["projects"]
                        skills_result = starting_sections["skills"]
                        fit_estimate = estimate_project_section_length(
                            project_result,
                            max_projects=max_projects,
                            max_total_bullets=(
                                max(
                                    max_projects * max_bullets,
                                    sum(
                                        len(
                                            project.get(
                                                "draft_bullets",
                                                [],
                                            )
                                            or []
                                        )
                                        for project in (
                                            project_result.get(
                                                "recommended_projects",
                                                [],
                                            )
                                            or []
                                        )
                                    ),
                                )
                                if bullet_allocation_mode
                                == "all_canonical_before_fitting"
                                else max_projects * max_bullets
                            ),
                        )
                        input_fingerprint = build_tailoring_input_fingerprint(
                            report=report,
                            evidence_items=[],
                            generation_settings=generation_settings,
                            generation_kind="phase9e_reuse_snapshot",
                            model_id="deterministic-local-reuse",
                            phase9e_binding=phase9e_binding,
                        )
                        st.session_state[tailored_projects_key] = project_result
                        st.session_state[tailored_fit_key] = fit_estimate
                        st.session_state[tailored_skills_key] = skills_result
                        st.session_state.pop(tailored_docx_key, None)
                        st.session_state.pop(tailored_fit_result_key, None)
                        generation_id = uuid.uuid4().hex
                        st.session_state[
                            tailored_generation_id_key
                        ] = generation_id
                        _persist_current_tailoring_state(
                            application_id=current_application_id,
                            generation_id=generation_id,
                            generation_settings=generation_settings,
                            input_fingerprint=input_fingerprint,
                            generation_kind="phase9e_reuse_snapshot",
                        )
                        record_zero_cost_action_event(
                            application_id=current_application_id,
                            action="generate_projects",
                            note=(
                                "Immutable Phase 9E starting Projects loaded; "
                                "no project model call."
                            ),
                        )
                        record_zero_cost_action_event(
                            application_id=current_application_id,
                            action="generate_skills",
                            note=(
                                "Immutable Phase 9E starting Skills loaded; "
                                "no skills model call."
                            ),
                        )
                        st.session_state[
                            f"phase7_flash_{current_application_id}"
                        ] = (
                            "Loaded immutable Phase 9E Projects and Skills. "
                            "No model call was made."
                        )
                        st.rerun()

                    if generation_plan["mode"] == "load_approved":
                        if not isinstance(approved_generation, dict):
                            raise ValueError(
                                "Approve a generation before locking both "
                                "Projects and Skills."
                            )
                        restore_generation_to_session(
                            current_application_id,
                            approved_generation,
                        )
                        record_zero_cost_action_event(
                            application_id=current_application_id,
                            action="generate_projects",
                            note=(
                                "Approved final Projects were loaded; "
                                "no project model call."
                            ),
                        )
                        record_zero_cost_action_event(
                            application_id=current_application_id,
                            action="generate_skills",
                            note=(
                                "Approved final Skills were loaded; "
                                "no skills model call."
                            ),
                        )
                        st.session_state[
                            f"phase7_flash_{current_application_id}"
                        ] = (
                            "Loaded the approved final Projects and Skills. "
                            "No duplicate Draft and no AI call were created."
                        )
                        st.rerun()

                    input_fingerprint = build_tailoring_input_fingerprint(
                        report=report,
                        evidence_items=evidence_items,
                        generation_settings=generation_settings,
                        generation_kind="projects_skills",
                        model_id=get_active_model("analysis"),
                        approved_generation=approved_generation,
                        lock_projects=lock_projects,
                        lock_skills=lock_skills,
                        phase9e_binding=phase9e_binding,
                    )
                    cached = find_cached_tailoring_generation(
                        application_id=current_application_id,
                        input_fingerprint=input_fingerprint,
                        generation_kind="projects_skills",
                    )
                    if isinstance(cached, dict):
                        restore_generation_to_session(
                            current_application_id,
                            cached,
                        )
                        record_zero_cost_action_event(
                            application_id=current_application_id,
                            action="generate_projects",
                            note=(
                                "Exact Projects/Skills generation cache hit; "
                                "no project model call."
                            ),
                        )
                        record_zero_cost_action_event(
                            application_id=current_application_id,
                            action="generate_skills",
                            note=(
                                "Exact Projects/Skills generation cache hit; "
                                "no skills model call."
                            ),
                        )
                        st.session_state[
                            f"phase7_flash_{current_application_id}"
                        ] = (
                            "Reused an exact persistent generation cache hit; "
                            "no Projects or Skills model call was made."
                        )
                        st.rerun()

                    st.session_state[
                        f"debug_project_tailor_inputs_{current_application_id}"
                    ] = {
                        "resume_projects": report.get(
                            "resume_profile",
                            {},
                        ).get("projects", []),
                        "evidence_items": evidence_items,
                    }
                    debug_candidate_pool = build_project_candidate_pool(
                        resume_profile=report.get("resume_profile", {}),
                        evidence_items=evidence_items,
                    )
                    st.session_state[
                        f"project_candidate_pool_{current_application_id}"
                    ] = debug_candidate_pool

                    effective_approved = (
                        get_effective_generation_sections(
                            approved_generation
                        )
                    )
                    reset_call_ledger()

                    with st.spinner(
                        "Generating unlocked sections and reusing "
                        "approved final locked sections..."
                    ):
                        if generation_plan["requires_project_ai"]:
                            project_result = tailor_projects_section(
                                resume_profile=report.get(
                                    "resume_profile",
                                    {},
                                ),
                                jd_profile=report.get("jd_profile", {}),
                                evidence_items=evidence_items,
                                max_projects=max_projects,
                                max_bullets_per_project=max_bullets,
                                bullet_allocation_mode=bullet_allocation_mode,
                                keyword_match=report.get(
                                    "keyword_match",
                                    {},
                                ),
                                raw_jd_text=report.get("raw_jd_text", ""),
                                stable_analysis=report.get(
                                    "stable_analysis",
                                    {},
                                ),
                            )
                            append_api_usage(
                                application_id=current_application_id,
                                action="generate_projects",
                                report=persisted_application_report,
                            )
                        else:
                            project_result = deepcopy(
                                effective_approved.get("projects")
                            )
                            record_zero_cost_action_event(
                                application_id=current_application_id,
                                action="generate_projects",
                                note=(
                                    "Approved final Projects were reused; "
                                    "no project model call."
                                ),
                            )

                        fit_estimate = estimate_project_section_length(
                            project_result,
                            max_projects=max_projects,
                            max_total_bullets=(
                                max(
                                    max_projects * max_bullets,
                                    sum(
                                        len(
                                            project.get(
                                                "draft_bullets",
                                                [],
                                            )
                                            or []
                                        )
                                        for project in (
                                            project_result.get(
                                                "recommended_projects",
                                                [],
                                            )
                                            or []
                                        )
                                    ),
                                )
                                if bullet_allocation_mode
                                == "all_canonical_before_fitting"
                                else max_projects * max_bullets
                            ),
                        )

                        reset_call_ledger()
                        if generation_plan["requires_skills_ai"]:
                            skills_result = tailor_skills_section(
                                resume_profile=report.get(
                                    "resume_profile",
                                    {},
                                ),
                                jd_profile=report.get("jd_profile", {}),
                                evidence_items=evidence_items,
                                stable_analysis=report.get(
                                    "stable_analysis",
                                    {},
                                ),
                                selected_projects_result=project_result,
                            )
                            append_api_usage(
                                application_id=current_application_id,
                                action="generate_skills",
                                report=persisted_application_report,
                            )
                        else:
                            skills_result = deepcopy(
                                effective_approved.get("skills")
                            )
                            record_zero_cost_action_event(
                                application_id=current_application_id,
                                action="generate_skills",
                                note=(
                                    "Approved final Skills were reused; "
                                    "no skills model call."
                                ),
                            )

                    st.session_state["latest_report"] = (
                        persisted_application_report
                    )
                    update_application_report(
                        application_id=current_application_id,
                        resume_filename=st.session_state.get(
                            "resume_filename",
                            "",
                        ),
                        report=persisted_application_report,
                    )
                    st.session_state[tailored_projects_key] = project_result
                    st.session_state[tailored_fit_key] = fit_estimate
                    st.session_state[tailored_skills_key] = skills_result
                    st.session_state.pop(tailored_docx_key, None)
                    st.session_state.pop(
                        tailored_fit_result_key,
                        None,
                    )

                    generation_id = uuid.uuid4().hex
                    st.session_state[
                        tailored_generation_id_key
                    ] = generation_id
                    _persist_current_tailoring_state(
                        application_id=current_application_id,
                        generation_id=generation_id,
                        generation_settings=generation_settings,
                        input_fingerprint=input_fingerprint,
                        generation_kind="projects_skills",
                    )
                    st.session_state[
                        f"phase7_flash_{current_application_id}"
                    ] = (
                        "Created a new Draft for the unlocked generated "
                        "section(s). Locked sections came from the approved "
                        "final fitted output."
                    )
                    st.rerun()

                except ValueError as exc:
                    st.warning(str(exc))
                except RuntimeError as exc:
                    st.error(f"LLM/API error: {exc}")
                except Exception as exc:
                    st.error(
                        "Unexpected error while tailoring Projects and Skills: "
                        f"{exc}"
                    )

            render_ai_action_subtotal(
                application_id=current_application_id,
                actions=["generate_projects", "generate_skills"],
                label="Projects + Skills subtotal",
            )

            with st.expander(
                "Advanced: Generate sections separately",
                expanded=False,
            ):
                col_project, col_skills = st.columns(2)

                with col_project:
                    if st.button(
                        "Generate Tailored Projects Section",
                        type="primary",
                        width="stretch",
                        key=f"generate_projects_{current_application_id}",
                        disabled=(
                            lock_projects
                            or phase9e_projects_locked
                            or not phase9e_ready
                            or workspace_edit_required
                            or update_scope_dirty
                        ),
                    ):
                        try:
                            reset_call_ledger()
                            evidence_items = get_evidence_items(limit=100)

                            st.session_state[f"debug_project_tailor_inputs_{current_application_id}"] = {
                                "resume_projects": report.get("resume_profile", {}).get("projects", []),
                                "evidence_items": evidence_items,
                            }

                            debug_candidate_pool = build_project_candidate_pool(
                            resume_profile=report.get("resume_profile", {}),
                            evidence_items=evidence_items,
                            )

                            st.session_state[f"project_candidate_pool_{current_application_id}"] = debug_candidate_pool

                            with st.spinner("Generating tailored projects..."):
                                project_result = tailor_projects_section(
                                    resume_profile=report.get("resume_profile", {}),
                                    jd_profile=report.get("jd_profile", {}),
                                    evidence_items=evidence_items,
                                    max_projects=max_projects,
                                    max_bullets_per_project=max_bullets,
                                    bullet_allocation_mode=bullet_allocation_mode,
                                    keyword_match=report.get("keyword_match", {}),
                                    raw_jd_text=report.get("raw_jd_text","",),
                                    stable_analysis=report.get("stable_analysis", {}),
                                )

                                fit_estimate = estimate_project_section_length(
                                    project_result,
                                    max_projects=max_projects,
                                    max_total_bullets=(
                                max(
                                    max_projects * max_bullets,
                                    sum(
                                        len(
                                            project.get(
                                                "draft_bullets",
                                                [],
                                            )
                                            or []
                                        )
                                        for project in (
                                            project_result.get(
                                                "recommended_projects",
                                                [],
                                            )
                                            or []
                                        )
                                    ),
                                )
                                if bullet_allocation_mode
                                == "all_canonical_before_fitting"
                                else max_projects * max_bullets
                            ),
                                )

                            append_api_usage(
                                application_id=current_application_id,
                                action="generate_projects",
                                report=persisted_application_report,
                            )
                            st.session_state["latest_report"] = (
                                persisted_application_report
                            )
                            update_application_report(
                                application_id=current_application_id,
                                resume_filename=st.session_state.get(
                                    "resume_filename",
                                    "",
                                ),
                                report=persisted_application_report,
                            )
                            st.session_state[tailored_projects_key] = project_result
                            st.session_state[tailored_fit_key] = fit_estimate
                            st.session_state.pop(tailored_docx_key, None)
                            st.session_state.pop(tailored_fit_result_key, None)
                            generation_id = uuid.uuid4().hex
                            st.session_state[
                                tailored_generation_id_key
                            ] = generation_id
                            _persist_current_tailoring_state(
                                application_id=current_application_id,
                                generation_id=generation_id,
                                generation_settings={
                                    "max_projects": max_projects,
                                    "max_bullets": max_bullets,
                                    "bullet_allocation_mode": bullet_allocation_mode,
                                    "phase9e_binding": deepcopy(
                                        phase9e_binding
                                    ),
                                    "phase9e_base_content_fingerprint": (
                                        phase9e_base_content_fingerprint
                                    ),
                                },
                                input_fingerprint=build_tailoring_input_fingerprint(
                                    report=report,
                                    evidence_items=evidence_items,
                                    generation_settings={
                                        "max_projects": max_projects,
                                        "max_bullets": max_bullets,
                                        "bullet_allocation_mode": bullet_allocation_mode,
                                    },
                                    generation_kind="projects",
                                    model_id=get_active_model("analysis"),
                                    phase9e_binding=phase9e_binding,
                                ),
                                generation_kind="projects",
                            )
                            st.rerun()

                        except ValueError as exc:
                            st.warning(str(exc))
                        except RuntimeError as exc:
                            st.error(f"LLM/API error: {exc}")
                        except Exception as exc:
                            st.error(f"Unexpected error while tailoring projects: {exc}")

                    render_ai_action_subtotal(
                        application_id=current_application_id,
                        actions=["generate_projects"],
                        label="Generate Projects subtotal",
                    )

                with col_skills:
                    if st.button(
                        "Generate Tailored Skills Section",
                        width="stretch",
                        key=f"generate_skills_{current_application_id}",
                        disabled=(
                            lock_skills
                            or phase9e_skills_locked
                            or not phase9e_ready
                            or workspace_edit_required
                            or update_scope_dirty
                        ),
                    ):
                        try:
                            reset_call_ledger()
                            with st.spinner("Generating tailored skills..."):
                                skills_result = tailor_skills_section(
                                    resume_profile=report.get("resume_profile", {}),
                                    jd_profile=report.get("jd_profile", {}),
                                    evidence_items=get_evidence_items(limit=100),
                                    stable_analysis=report.get("stable_analysis", {}),
                                    selected_projects_result=st.session_state.get(
                                        tailored_projects_key
                                    ),
                                )

                            append_api_usage(
                                application_id=current_application_id,
                                action="generate_skills",
                                report=persisted_application_report,
                            )
                            st.session_state["latest_report"] = (
                                persisted_application_report
                            )
                            update_application_report(
                                application_id=current_application_id,
                                resume_filename=st.session_state.get(
                                    "resume_filename",
                                    "",
                                ),
                                report=persisted_application_report,
                            )
                            st.session_state[tailored_skills_key] = skills_result
                            st.session_state.pop(tailored_docx_key, None)
                            st.session_state.pop(tailored_fit_result_key, None)
                            generation_id = uuid.uuid4().hex
                            st.session_state[
                                tailored_generation_id_key
                            ] = generation_id
                            _persist_current_tailoring_state(
                                application_id=current_application_id,
                                generation_id=generation_id,
                                generation_settings={
                                    "max_projects": max_projects,
                                    "max_bullets": max_bullets,
                                    "bullet_allocation_mode": bullet_allocation_mode,
                                    "phase9e_binding": deepcopy(
                                        phase9e_binding
                                    ),
                                    "phase9e_base_content_fingerprint": (
                                        phase9e_base_content_fingerprint
                                    ),
                                },
                                input_fingerprint=build_tailoring_input_fingerprint(
                                    report=report,
                                    evidence_items=get_evidence_items(limit=100),
                                    generation_settings={
                                        "max_projects": max_projects,
                                        "max_bullets": max_bullets,
                                        "bullet_allocation_mode": bullet_allocation_mode,
                                    },
                                    generation_kind="skills",
                                    model_id=get_active_model("analysis"),
                                    phase9e_binding=phase9e_binding,
                                ),
                                generation_kind="skills",
                            )
                            st.rerun()

                        except ValueError as exc:
                            st.warning(str(exc))
                        except RuntimeError as exc:
                            st.error(f"LLM/API error: {exc}")
                        except Exception as exc:
                            st.error(f"Unexpected error while tailoring skills: {exc}")

                    render_ai_action_subtotal(
                        application_id=current_application_id,
                        actions=["generate_skills"],
                        label="Generate Skills subtotal",
                    )

            project_result = st.session_state.get(tailored_projects_key)
            fit_estimate = st.session_state.get(tailored_fit_key)
            skills_result = st.session_state.get(tailored_skills_key)
            
            candidate_pool = st.session_state.get(
                f"project_candidate_pool_{current_application_id}"
            )

            if candidate_pool:
                with st.expander("Debug: Combined project candidate pool"):
                    st.json(candidate_pool)

            debug_inputs = st.session_state.get(f"debug_project_tailor_inputs_{current_application_id}")

            if debug_inputs:
                with st.expander("Debug: Project tailoring inputs"):
                    st.json(debug_inputs)

            if project_result:
                st.write("### Recommended Projects Section")

                if fit_estimate:
                    risk = fit_estimate.get("risk", "unknown")
                    if risk == "low":
                        st.success(f"One-page fit risk: {risk}")
                    elif risk == "medium":
                        st.warning(f"One-page fit risk: {risk}")
                    else:
                        st.error(f"One-page fit risk: {risk}")

                    st.caption(fit_estimate.get("reason", ""))

                for project in project_result.get("recommended_projects", []):
                    display_name = (
                        project.get("display_title")
                        or project.get("title")
                        or "Untitled Project"
                    )

                    st.write(f"#### {display_name}")

                    if project.get("period"):
                        st.write(f"**Period:** {project.get('period')}")

                    st.write(f"**Priority:** {project.get('priority', '')}")
                    st.write(f"**Space action:** {project.get('space_action', '')}")
                    st.write(f"**Action:** {project.get('action', '')}")
                    st.write(f"**Source:** {project.get('source', '')}")
                    st.write(f"**Why relevant:** {project.get('why_relevant', '')}")

                    for bullet in project.get("draft_bullets", []):
                        st.markdown(f"- {bullet}")

                bullet_warnings = project_result.get(
                    "bullet_validation_warnings",
                    [],
                )

                if bullet_warnings:
                    with st.expander(
                        (
                            "Bullet quality warnings "
                            f"({len(bullet_warnings)})"
                        ),
                        expanded=False,
                    ):
                        for warning in bullet_warnings:
                            project_name = warning.get(
                                "project",
                                "Project",
                            )

                            message = warning.get(
                                "message",
                                "Bullet warning detected.",
                            )

                            code = warning.get(
                                "code",
                                "warning",
                            )

                            st.warning(
                                f"**{project_name}** "
                                f"`{code}` — {message}"
                            )
                else:
                    st.success(
                        "Bullet quality validation found no warnings."
                    )

                with st.expander("Projects to remove or deprioritize"):
                    st.json(project_result.get("projects_to_remove_or_deprioritize", []))


                with st.expander("All candidate projects scored"):
                    st.json(project_result.get("candidate_project_ranking", []))

                allocation_debug = (
                    project_result.get(
                        "deterministic_rule_debug",
                        {},
                    ).get(
                        "bullet_allocation",
                        {},
                    )
                )
                if allocation_debug:
                    with st.expander(
                        "Phase 6B.2 bullet allocation"
                    ):
                        st.json(allocation_debug)

                with st.expander("Unsupported JD skills"):
                    st.json(project_result.get("unsupported_jd_skills", []))

                with st.expander("Full tailored projects JSON"):
                    st.json(project_result)

            if skills_result:
                st.write("### Recommended Skills Section")

                skills_preview_fingerprint = (
                    stable_content_fingerprint(
                        skills_result
                    )[:12]
                )
                st.text_area(
                    "Preview skills text",
                    value=skill_lines_to_plain_text(skills_result),
                    height=160,
                    key=(
                        f"skills_preview_{current_application_id}_"
                        f"{skills_preview_fingerprint}"
                    ),
                )

                with st.expander("Evidence-supported additions"):
                    st.json(skills_result.get("evidence_supported_additions", []))

                with st.expander("Unsupported JD skills"):
                    st.json(skills_result.get("unsupported_jd_skills", []))

            st.divider()
            st.subheader("Build and Fit Résumé Document")

            st.caption(
            "This can change the Skills section, Projects section, or both in a copied DOCX. "
            "Work Experience is not changed."
            )

            saved_resume_docx_path = st.session_state.get(saved_docx_key)

            if workspace_edit_required:
                if isinstance(previous_scope_message_approved, dict):
                    previous_scope_id = str(
                        previous_scope_message_approved.get("generation_id")
                        or ""
                    )[:8]
                    st.info(
                        "Approved résumé "
                        f"{previous_scope_id or 'result'} belongs to a previous "
                        "Tailoring Base and is read-only. Use Start new résumé "
                        "from current Tailoring Base in the Résumé Workspace "
                        "before generating or fitting a replacement document."
                    )
                else:
                    active_approved = get_application_generation_control(
                        current_application_id
                    ).get("approved_generation")
                    active_approved_id = str(
                        (active_approved or {}).get("generation_id") or ""
                    )[:8]
                    st.info(
                        "Approved résumé "
                        f"{active_approved_id or 'result'} is already fitted "
                        "and read-only. Revise it or create an alternative "
                        "copy in the Résumé Workspace before generating "
                        "another fitted document."
                    )
            elif not saved_resume_docx_path:
                latest_saved_docx = get_latest_saved_docx_for_application(current_application_id)
                
                if latest_saved_docx:
                    saved_resume_docx_path = str(latest_saved_docx)
                    st.session_state[saved_docx_key] = saved_resume_docx_path

            if (
                not saved_resume_docx_path
                and not isinstance(previous_scope_message_approved, dict)
            ):
                st.info(
                    "No saved DOCX found for this session. Upload a DOCX resume, "
                    "tick the save checkbox, and run Analyze Resume again."
                )
            elif not project_result and not skills_result:
                recovered_path = st.session_state.get(
                    tailored_docx_key
                )
                if recovered_path and Path(recovered_path).exists():
                    st.info(
                        "This older session did not save structured Projects/Skills, "
                        "but its latest generated tailored résumé is restored below."
                    )
                else:
                    st.info(
                        "Generate a Tailored Projects Section or "
                        "Tailored Skills Section first."
                    )
            else:
                selected_sections = []

                if project_result:
                    selected_sections.append("Projects")

                if skills_result:
                    selected_sections.append("Skills")

                if saved_resume_docx_path:
                    st.success(f"Saved DOCX loaded for this session: {Path(saved_resume_docx_path).name}")
                st.caption(f"Will update: {', '.join(selected_sections)}")

                with st.expander("Fitting strategy", expanded=True):
                    use_compact_before_delete = st.checkbox(
                        "Compact project wording before deleting content",
                        value=bool(
                            restored_settings.get(
                                "use_compact_before_delete",
                                True,
                            )
                        ),
                        key=(
                            "use_compact_before_delete_"
                            f"{current_application_id}"
                        ),
                        help=(
                            "Only used when the full résumé exceeds one page. "
                            "The fitter tests truthful compact project bullets "
                            "before deleting a complete bullet."
                        ),
                    )

                    prefer_balanced_bullets = st.checkbox(
                        "Balance project bullets during deletion",
                        value=bool(
                            restored_settings.get(
                                "prefer_balanced_bullets",
                                False,
                            )
                        ),
                        key=(
                            "prefer_balanced_bullets_"
                            f"{current_application_id}"
                        ),
                        help=(
                            "Only affects complete-bullet deletion. Projects with "
                            "more bullets are reduced first, then relevance is used "
                            "as a tie-breaker."
                        ),
                    )

                    allow_skills_compaction = st.checkbox(
                        "Allow removal of low-priority Skills",
                        value=bool(
                            restored_settings.get(
                                "allow_skills_compaction",
                                False,
                            )
                        ),
                        key=(
                            "allow_skills_compaction_"
                            f"{current_application_id}"
                        ),
                        help=(
                            "The fitter may temporarily remove supported but "
                            "low-priority Skills when their rendered space saving "
                            "is better than reducing project evidence."
                        ),
                    )

                    page_density_options = [
                        "Fit only",
                        "Balanced",
                        "Maximize relevant content",
                    ]
                    saved_page_density = str(
                        restored_settings.get(
                            "page_density_mode",
                            "balanced",
                        )
                    ).strip().lower()
                    if saved_page_density == "none":
                        default_page_density_label = "Fit only"
                    elif saved_page_density == "maximize":
                        default_page_density_label = "Maximize relevant content"
                    else:
                        default_page_density_label = "Balanced"

                    page_density_label = st.radio(
                        "Page density",
                        page_density_options,
                        index=page_density_options.index(
                            default_page_density_label
                        ),
                        horizontal=True,
                        key=f"page_density_mode_{current_application_id}",
                        help=(
                            "Fit only reaches one page and then stops; it does not restore "
                            "content just to fill spare space. Balanced restores the "
                            "strongest removed content up to about 92% page fill. "
                            "Maximize relevant content restores more truthful content "
                            "up to about 97%. If the full generated version already "
                            "fits on one page, all three modes keep it unchanged."
                        ),
                    )
                    page_density_mode = (
                        "none"
                        if page_density_label == "Fit only"
                        else "maximize"
                        if page_density_label == "Maximize relevant content"
                        else "balanced"
                    )

                    allow_margin_compaction = st.checkbox(
                        "Allow safe margin compaction before deleting content",
                        value=bool(
                            restored_settings.get(
                                "allow_margin_compaction",
                                False,
                            )
                        ),
                        key=(
                            "allow_margin_compaction_"
                            f"{current_application_id}"
                        ),
                        help=(
                            "If the full résumé exceeds one page, the fitter may "
                            "reduce larger source margins in conservative steps before "
                            "removing project bullets or Skills. It never expands a "
                            "margin and never reduces any margin below 0.50 in."
                        ),
                    )

                    st.caption(
                        "These options apply only when generating and fitting the "
                        "DOCX. Changing them does not regenerate Projects or Skills."
                    )

                with st.expander("Spacing options", expanded=False):
                    spacing_mode_options = [
                        "Paragraph spacing",
                        "Blank line",
                    ]
                    saved_spacing_mode = str(
                        restored_settings.get(
                            "spacing_mode",
                            "paragraph_spacing",
                        )
                    ).strip().lower()
                    default_spacing_mode_label = (
                        "Blank line"
                        if saved_spacing_mode == "blank_line"
                        else "Paragraph spacing"
                    )

                    spacing_mode_label = st.radio(
                        "Spacing mode",
                        spacing_mode_options,
                        index=spacing_mode_options.index(
                            default_spacing_mode_label
                        ),
                        horizontal=True,
                        key=f"spacing_mode_{current_application_id}",
                        help=(
                            "Paragraph spacing uses Word spacing values. "
                            "Blank line inserts real empty paragraphs, similar to pressing Enter."
                        ),
                    )

                    spacing_mode = (
                        "blank_line"
                        if spacing_mode_label == "Blank line"
                        else "paragraph_spacing"
                    )

                    add_spacing_before_first_project = st.checkbox(
                        "Add spacing before the first project too",
                        value=bool(
                            restored_settings.get(
                                "add_spacing_before_first_project",
                                False,
                            )
                        ),
                        key=f"spacing_before_first_project_{current_application_id}",
                    )

                    if spacing_mode == "paragraph_spacing":
                        project_spacing_pt = st.slider(
                            "Spacing before each next project (pt)",
                            min_value=0,
                            max_value=20,
                            value=int(
                                restored_settings.get(
                                    "project_spacing_pt",
                                    10,
                                )
                            ),
                            key=f"project_spacing_pt_{current_application_id}",
                        )

                        after_projects_spacing_pt = st.slider(
                            "Spacing after final project / before Skills (pt)",
                            min_value=0,
                            max_value=20,
                            value=int(
                                restored_settings.get(
                                    "after_projects_spacing_pt",
                                    10,
                                )
                            ),
                            key=f"after_projects_spacing_pt_{current_application_id}",
                        )

                        blank_lines_between_projects = 0
                        blank_lines_after_projects = 0

                    else:
                        blank_lines_between_projects = st.number_input(
                            "Blank lines before each project",
                            min_value=0,
                            max_value=3,
                            value=int(
                                restored_settings.get(
                                    "blank_lines_between_projects",
                                    1,
                                )
                            ),
                            step=1,
                            key=f"blank_lines_between_projects_{current_application_id}",
                        )

                        blank_lines_after_projects = st.number_input(
                            "Blank lines after final project / before Skills",
                            min_value=0,
                            max_value=3,
                            value=int(
                                restored_settings.get(
                                    "blank_lines_after_projects",
                                    1,
                                )
                            ),
                            step=1,
                            key=f"blank_lines_after_projects_{current_application_id}",
                        )

                        project_spacing_pt = 0
                        after_projects_spacing_pt = 0

                    st.caption(
                        "Changing spacing only affects DOCX formatting. "
                        "You can regenerate the DOCX without re-tailoring the projects or skills."
                    )

                if st.button(
                    "Generate and Fit Tailored Resume DOCX",
                    type="primary",
                    width="stretch",
                    key=f"generate_docx_{current_application_id}",
                    disabled=(
                        not phase9e_ready
                        or workspace_edit_required
                        or update_scope_dirty
                    ),
                ):
                    try:
                        phase7_control = get_application_generation_control(
                            current_application_id
                        )
                        if phase9e_enforced:
                            phase7_control = constrain_generation_control_to_phase9e(
                                phase7_control,
                                phase9e_binding,
                            )
                        fit_lock_projects = bool(
                            phase7_control.get("lock_projects")
                        ) or phase9e_projects_locked
                        fit_lock_skills = bool(
                            phase7_control.get("lock_skills")
                        ) or phase9e_skills_locked
                        projects_for_fit, skills_for_fit = resolve_locked_sections(
                            proposed_projects=project_result,
                            proposed_skills=skills_result,
                            approved_generation=phase7_control.get(
                                "approved_generation"
                            ),
                            lock_projects=fit_lock_projects,
                            lock_skills=fit_lock_skills,
                        )
                        fit_max_bullets_per_project = (
                            resolve_effective_fitting_bullet_ceiling(
                                projects_for_fit,
                                configured_max_bullets_per_project=(
                                    max_bullets
                                ),
                            )
                        )
                        fit_bullet_allocation_mode = (
                            resolve_fitting_bullet_allocation_mode(
                                projects_for_fit,
                                fallback_mode=bullet_allocation_mode,
                            )
                        )

                        # Keep the draft record consistent with the exact content
                        # sent to the fitter after approved-section lock resolution.
                        st.session_state[tailored_projects_key] = projects_for_fit
                        st.session_state[tailored_skills_key] = skills_for_fit
                        current_generation_id = str(
                            st.session_state.get(
                                tailored_generation_id_key
                            )
                            or ""
                        )
                        if not current_generation_id:
                            current_generation_id = uuid.uuid4().hex
                            st.session_state[
                                tailored_generation_id_key
                            ] = current_generation_id
                            _persist_current_tailoring_state(
                                application_id=current_application_id,
                                generation_id=current_generation_id,
                                generation_kind="fit_only",
                            )
                        mutable_generation = ensure_mutable_tailoring_generation(
                            application_id=current_application_id,
                            generation_id=current_generation_id,
                        )
                        mutable_generation_id = str(
                            mutable_generation["generation_id"]
                        )
                        st.session_state[
                            tailored_generation_id_key
                        ] = mutable_generation_id

                        fit_result = generate_tailored_resume_copy_fit_one_page(
                            saved_resume_docx_path=saved_resume_docx_path,
                            tailored_projects=projects_for_fit,
                            tailored_skills=skills_for_fit,
                            application_id=current_application_id,
                            max_projects=max_projects,
                            max_bullets_per_project=fit_max_bullets_per_project,
                            spacing_mode=spacing_mode,
                            project_spacing_pt=project_spacing_pt,
                            after_projects_spacing_pt=after_projects_spacing_pt,
                            blank_lines_between_projects=blank_lines_between_projects,
                            blank_lines_after_projects=blank_lines_after_projects,
                            add_spacing_before_first_project=add_spacing_before_first_project,
                            use_compact_before_delete=use_compact_before_delete,
                            prefer_balanced_bullets=prefer_balanced_bullets,
                            allow_skills_compaction=allow_skills_compaction,
                            lock_projects=fit_lock_projects,
                            lock_skills=fit_lock_skills,
                            page_density_mode=page_density_mode,
                            allow_margin_compaction=allow_margin_compaction,
                            generation_id=mutable_generation_id,
                        )

                        tailored_resume_path = fit_result["docx_path"]

                        st.session_state[tailored_docx_key] = str(tailored_resume_path)
                        st.session_state[tailored_fit_result_key] = fit_result

                        generation_id = str(
                            st.session_state.get(
                                tailored_generation_id_key
                            )
                            or uuid.uuid4().hex
                        )
                        st.session_state[
                            tailored_generation_id_key
                        ] = generation_id
                        fit_generation_settings = {
                            "max_projects": max_projects,
                            "max_bullets": max_bullets,
                            "fit_effective_max_bullets": fit_max_bullets_per_project,
                            "bullet_allocation_mode": (
                                fit_bullet_allocation_mode
                            ),
                            "use_compact_before_delete": (
                                use_compact_before_delete
                            ),
                            "prefer_balanced_bullets": (
                                prefer_balanced_bullets
                            ),
                            "allow_skills_compaction": (
                                allow_skills_compaction
                            ),
                            "lock_projects": fit_lock_projects,
                            "lock_skills": fit_lock_skills,
                            "page_density_mode": page_density_mode,
                            "allow_margin_compaction": (
                                allow_margin_compaction
                            ),
                            "spacing_mode": spacing_mode,
                            "project_spacing_pt": project_spacing_pt,
                            "after_projects_spacing_pt": (
                                after_projects_spacing_pt
                            ),
                            "blank_lines_between_projects": (
                                blank_lines_between_projects
                            ),
                            "blank_lines_after_projects": (
                                blank_lines_after_projects
                            ),
                            "add_spacing_before_first_project": (
                                add_spacing_before_first_project
                            ),
                            "projects_fingerprint": stable_content_fingerprint(
                                projects_for_fit
                            ),
                            "skills_fingerprint": stable_content_fingerprint(
                                skills_for_fit
                            ),
                            "phase9e_binding": deepcopy(phase9e_binding),
                            "phase9e_base_content_fingerprint": (
                                phase9e_base_content_fingerprint
                            ),
                        }
                        _persist_current_tailoring_state(
                            application_id=current_application_id,
                            generation_id=generation_id,
                            generation_settings=fit_generation_settings,
                            fit_result=fit_result,
                            input_fingerprint=build_tailoring_input_fingerprint(
                                report=report,
                                evidence_items=get_evidence_items(limit=100),
                                generation_settings=fit_generation_settings,
                                generation_kind="fit_only",
                                model_id="deterministic-local-fit",
                                approved_generation=phase7_control.get(
                                    "approved_generation"
                                ),
                                lock_projects=fit_lock_projects,
                                lock_skills=fit_lock_skills,
                                phase9e_binding=phase9e_binding,
                            ),
                            generation_kind="fit_only",
                        )

                        if fit_result["fit_one_page"] is True:
                            st.success("Tailored resume copy generated and fits within one page.")
                        elif fit_result["fit_one_page"] is False:
                            st.warning(fit_result["note"])
                        else:
                            st.warning(fit_result["note"])

                        st.rerun()

                    except ValueError as exc:
                        st.warning(str(exc))
                    except Exception as exc:
                        st.error(f"Unexpected error while generating tailored resume copy: {exc}")

            tailored_resume_copy_path = st.session_state.get(tailored_docx_key)
            fit_result = st.session_state.get(tailored_fit_result_key)

            has_debug_content = phase9e_ready and any(
            (
                report,
                candidate_pool,
                debug_inputs,
                project_result,
                skills_result,
                fit_estimate,
                fit_result,
            )
        )

            if has_debug_content:
                debug_bytes, debug_filename = (
                    create_full_debug_bundle(
                        application_id=current_application_id,
                        resume_filename=st.session_state.get(
                            "resume_filename",
                            "",
                        ),
                        report=report,
                        candidate_pool=candidate_pool,
                        project_inputs=debug_inputs,
                        project_result=project_result,
                        skills_result=skills_result,
                        fit_estimate=fit_estimate,
                        fit_result=fit_result,
                    )
                )

                st.download_button(
                    "Download Full Debug Bundle JSON",
                    data=debug_bytes,
                    file_name=debug_filename,
                    mime="application/json",
                    width="stretch",
                    key=(
                        "download_debug_bundle_"
                        f"{current_application_id}"
                    ),
                )
                
                if isinstance(fit_result, dict):
                    with st.expander("One-page fitting attempts"):
                        st.json(
                            fit_result.get(
                                "attempts",
                                [],
                            )
                            or []
                        )

                    with st.expander(
                        "Debug: Final projects used in DOCX"
                    ):
                        final_projects_used = fit_result.get(
                            "tailored_projects_used"
                        )

                        if not isinstance(
                            final_projects_used,
                            dict,
                        ):
                            final_projects_used = {}

                        recommended_projects = (
                            final_projects_used.get(
                                "recommended_projects",
                                [],
                            )
                            or []
                        )

                        st.json(recommended_projects)

                    with st.expander(
                        "Debug: Final skills used in DOCX"
                    ):
                        final_skills_used = fit_result.get(
                            "tailored_skills_used"
                        )

                        if not isinstance(final_skills_used, dict):
                            final_skills_used = {}

                        st.json(
                            final_skills_used.get(
                                "skill_lines",
                                [],
                            )
                            or []
                        )

                    page_count = fit_result.get(
                        "page_count"
                    )

                    if page_count is not None:
                        st.caption(
                            f"Detected PDF page count: {page_count}"
                        )



            if (
                phase9e_ready
                and tailored_resume_copy_path
                and Path(tailored_resume_copy_path).exists()
            ):
                st.write("### Preview")

                preview_text = extract_docx_preview_text(tailored_resume_copy_path)
                preview_key = f"docx_preview_{current_application_id}_{Path(tailored_resume_copy_path).stem}"
                st.text_area(
                    "Text preview",
                    value=preview_text,
                    height=360,
                    #key=f"docx_preview_{current_application_id}",
                    key=preview_key,
                )

                pdf_preview_path = None

                if isinstance(fit_result, dict):
                    fitted_pdf_path = fit_result.get(
                        "pdf_path"
                    )
                    if fitted_pdf_path:
                        fitted_pdf = Path(
                            fitted_pdf_path
                        )
                        if fitted_pdf.exists():
                            pdf_preview_path = (
                                fitted_pdf
                            )

                if pdf_preview_path is None:
                    pdf_preview_path = (
                        convert_docx_to_pdf_if_possible(
                            tailored_resume_copy_path
                        )
                    )

                if pdf_preview_path:
                    try:
                        st.markdown(
                            pdf_to_preview_html(
                                pdf_preview_path,
                                max_width=820,
                                max_pages=5,
                                zoom=1.35,
                                include_download=True,
                            ),
                            unsafe_allow_html=True,
                        )
                    except Exception as preview_exc:
                        st.caption(
                            "The visual PDF preview could not be rendered "
                            f"({preview_exc}). The text preview and DOCX "
                            "download remain available."
                        )
                else:
                    st.caption(
                        "PDF visual preview and page-count checking are unavailable because LibreOffice "
                        "is not installed or conversion failed. DOCX download still works."
                    )

                with open(tailored_resume_copy_path, "rb") as file:
                    st.download_button(
                        "Download Tailored Resume Copy",
                        data=file,
                        file_name=Path(tailored_resume_copy_path).name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        width="stretch",
                        key=f"download_tailored_docx_{current_application_id}",
                    )

            st.divider()
            st.subheader("Approve and Verify Résumé")
            st.caption(
                "Workflow order: build and fit the document, approve the "
                "chosen fitted generation, run Phase 8 verification, then "
                "continue through Phase 9B, Phase 9C, and Phase 9D."
            )

            post_fit_control = get_application_generation_control(
                current_application_id
            )
            post_fit_approved = post_fit_control.get(
                "approved_generation"
            )
            session_fit_result = (
                fit_result if isinstance(fit_result, dict) else {}
            )
            approved_fit_result = (
                (post_fit_approved or {}).get("fit_result") or {}
                if isinstance(post_fit_approved, dict)
                else {}
            )
            has_fitted_output = bool(
                session_fit_result.get("docx_path")
                or session_fit_result.get("pdf_path")
                or session_fit_result.get("fit_one_page") is not None
                or approved_fit_result.get("docx_path")
                or approved_fit_result.get("pdf_path")
                or approved_fit_result.get("fit_one_page") is not None
            )

            if not has_fitted_output:
                st.info(
                    "Generate and fit the résumé document before approving "
                    "or running Phase 8."
                )
            else:
                if phase9e_ready:
                    render_tailoring_generation_controls(
                        application_id=current_application_id,
                        required_phase9e_binding=(
                            phase9e_binding
                            if phase9e_enforced
                            else None
                        ),
                        workspace_managed=True,
                    )
                else:
                    st.info(
                        "Approval and generation restoration are blocked for "
                        "an unbound or stale Phase 9E scope."
                    )

                post_approval_control = (
                    get_application_generation_control(
                        current_application_id
                    )
                )
                approved_for_phase8 = post_approval_control.get(
                    "approved_generation"
                )

                active_workspace_context = get_resume_workspace_context(
                    int(current_application_id)
                )
                active_workspace_generation = (
                    active_workspace_context.get("loaded_generation")
                )
                active_workspace_is_draft = bool(
                    active_workspace_context.get("loaded_mode")
                    == "working_draft"
                    and isinstance(active_workspace_generation, dict)
                )

                active_previous_scope_approved = (
                    active_workspace_context.get(
                        "previous_scope_approved_generation"
                    )
                )
                approved_for_phase8_id = str(
                    (approved_for_phase8 or {}).get("generation_id")
                    or ""
                )
                previous_scope_phase8_id = str(
                    (active_previous_scope_approved or {}).get(
                        "generation_id"
                    )
                    or ""
                )
                approved_for_phase8_is_current_scope = not bool(
                    previous_scope_phase8_id
                    and approved_for_phase8_id
                    and previous_scope_phase8_id
                    == approved_for_phase8_id
                )

                phase8_jd_record = (
                    get_exact_job_description_for_application(
                        int(current_application_id)
                    )
                    if current_application_id is not None
                    else None
                ) or {}
                phase8_raw_jd_text = str(
                    phase8_jd_record.get("raw_text")
                    or report.get("raw_jd_text")
                    or ""
                )

                post_fit_lifecycle_state = (
                    load_blueprint_lifecycle_state(
                        application_id=int(current_application_id),
                        current_phase9e_decision_fingerprint=str(
                            phase9e_binding.get(
                                "decision_fingerprint"
                            )
                            or ""
                        ),
                    )
                )
                post_fit_lifecycle_stage = str(
                    (
                        post_fit_lifecycle_state.get("summary") or {}
                    ).get("current_stage")
                    or ""
                )

                if active_workspace_is_draft:
                    working_draft_short = str(
                        active_workspace_generation.get("generation_id")
                        or ""
                    )[:8]
                    st.info(
                        "Phase 8 — Waiting for working draft "
                        f"{working_draft_short or 'draft'}. Approve this fitted "
                        "draft first; then verify it before Phase 9B can begin."
                    )
                elif (
                    phase9e_ready
                    and isinstance(approved_for_phase8, dict)
                    and approved_for_phase8_is_current_scope
                ):
                    if post_fit_lifecycle_stage in {
                        "phase9c",
                        "phase9d",
                        "phase9e",
                    }:
                        phase8_force_open = bool(
                            st.session_state.pop(
                                f"phase8_force_open_{current_application_id}",
                                False,
                            )
                        )
                        approved_phase8_short = str(
                            approved_for_phase8.get("generation_id")
                            or ""
                        )[:8]
                        phase8_complete_label = (
                            "Phase 8 — Approved résumé "
                            f"{approved_phase8_short or 'result'} · Complete"
                        )
                        with st.expander(
                            phase8_complete_label,
                            expanded=phase8_force_open,
                        ):
                            render_phase8_verification(
                                application_id=current_application_id,
                                baseline_report=report,
                                raw_jd_text=phase8_raw_jd_text,
                            )
                    else:
                        render_phase8_verification(
                            application_id=current_application_id,
                            baseline_report=report,
                            raw_jd_text=phase8_raw_jd_text,
                        )
                elif isinstance(
                    active_previous_scope_approved,
                    dict,
                ):
                    previous_phase8_short = str(
                        active_previous_scope_approved.get(
                            "generation_id"
                        )
                        or ""
                    )[:8]
                    st.info(
                        "Phase 8 — Waiting for a résumé under the current "
                        "Tailoring Base. Previous approved résumé "
                        f"{previous_phase8_short or 'result'} keeps its old "
                        "verification as preserved lineage/history."
                    )
                elif phase9e_ready:
                    st.info(
                        "Approve one fitted generation to unlock Phase 8."
                    )

                render_state_aware_blueprint_lifecycle(
                    application_id=int(current_application_id),
                    baseline_report=report,
                    working_generation=(
                        active_workspace_generation
                        if active_workspace_is_draft
                        else None
                    ),
                    current_phase9e_decision_fingerprint=str(
                        phase9e_binding.get(
                            "decision_fingerprint"
                        )
                        or ""
                    ),
                )

        st.divider()
        st.header("Tailored Cover Letter")

        if current_application_id is not None:
            render_application_output_cover_letter(
                application_id=int(current_application_id),
                model_id=get_active_model("analysis"),
                key_prefix="application_session",
            )

        if current_application_id is None and st.button(
            "Generate Cover Letter", type="primary", width="stretch"
        ):
            try:
                reset_call_ledger()
                with st.spinner("Generating tailored cover letter..."):
                    cover_letter = generate_cover_letter(report)

                st.session_state["cover_letter"] = cover_letter
                st.session_state.setdefault("revision_history", [])

                application_id = st.session_state.get("current_application_id")

                if application_id is None:
                    application_id = save_application(
                        resume_filename=st.session_state.get("resume_filename", "uploaded_resume"),
                        report=persisted_application_report,
                        cover_letter=cover_letter,
                    )
                    st.session_state["current_application_id"] = application_id
                else:
                    update_application_cover_letter(application_id, cover_letter)

                append_api_usage(
                    application_id=application_id,
                    action="generate_cover_letter",
                    report=persisted_application_report,
                )
                st.session_state["latest_report"] = persisted_application_report
                update_application_report(
                    application_id=application_id,
                    resume_filename=st.session_state.get(
                        "resume_filename",
                        "",
                    ),
                    report=persisted_application_report,
                )
                st.success("Cover letter saved to the current application session.")

            except RuntimeError as exc:
                st.error(f"LLM/API error: {exc}")

            except Exception as exc:
                st.error(f"Unexpected error while generating cover letter: {exc}")

        if current_application_id is None:
            render_ai_action_subtotal(
                application_id=current_application_id,
                actions=["generate_cover_letter"],
                label="Generate Cover Letter subtotal",
            )

        cover_letter = (
            st.session_state.get("cover_letter", "")
            if current_application_id is None
            else ""
        )

        if cover_letter:
            st.text_area(
                "Generated cover letter",
                value=cover_letter,
                height=360,
            )

            st.download_button(
                "Download Cover Letter (.txt)",
                data=cover_letter,
                file_name=f"cover_letter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                width="stretch",
            )

            st.subheader("Ask for a revision")

            revision_request = st.text_input(
                "Revision request",
                placeholder="Example: Make it shorter and more confident.",
            )

            if st.button("Revise Cover Letter", width="stretch"):
                try:
                    reset_call_ledger()
                    with st.spinner("Revising cover letter..."):
                        revised_letter = revise_cover_letter(
                            report,
                            cover_letter,
                            revision_request,
                        )

                    st.session_state.setdefault("revision_history", []).append(
                        {
                            "request": revision_request,
                            "before": cover_letter,
                            "after": revised_letter,
                        }
                    )

                    st.session_state["cover_letter"] = revised_letter

                    application_id = st.session_state.get("current_application_id")
                    if application_id is not None:
                        update_application_cover_letter(application_id, revised_letter)
                    append_api_usage(
                        application_id=application_id,
                        action="revise_cover_letter",
                        report=persisted_application_report,
                    )
                    st.session_state["latest_report"] = (
                        persisted_application_report
                    )
                    if application_id is not None:
                        update_application_report(
                            application_id=application_id,
                            resume_filename=st.session_state.get(
                                "resume_filename",
                                "",
                            ),
                            report=persisted_application_report,
                        )

                    st.rerun()

                except ValueError as exc:
                    st.warning(str(exc))

                except RuntimeError as exc:
                    st.error(f"LLM/API error: {exc}")

                except Exception as exc:
                    st.error(f"Unexpected error while revising cover letter: {exc}")

            render_ai_action_subtotal(
                application_id=current_application_id,
                actions=["revise_cover_letter"],
                label="Revise Cover Letter subtotal",
            )

        st.divider()
        st.header("Ask About This Analysis")

        if current_application_id is None:
            st.info("Save or load an application session before using saved chat.")
        else:
            st.caption("Chat history is saved for this application session.")

            saved_analysis_messages = get_application_chat_messages(current_application_id)

            if saved_analysis_messages:
                for message in saved_analysis_messages:
                    if message["role"] == "user":
                        st.markdown(f"**You:** {message['content']}")
                    else:
                        st.markdown(f"**AI:** {message['content']}")
            else:
                st.caption("No questions asked for this session yet.")

            analysis_question = st.text_input(
                "Ask a question about the analysis",
                placeholder="Example: What should I improve first?",
                key=f"analysis_question_{current_application_id}",
            )

            chat_col, clear_col = st.columns([0.75, 0.25])

            with chat_col:
                if st.button("Ask AI About Analysis", width="stretch"):
                    try:
                        reset_call_ledger()
                        with st.spinner("Answering question..."):
                            answer = answer_analysis_question(report, analysis_question)

                        add_application_chat_message(
                            current_application_id,
                            "user",
                            analysis_question,
                        )
                        add_application_chat_message(
                            current_application_id,
                            "assistant",
                            answer,
                        )

                        append_api_usage(
                            application_id=current_application_id,
                            action="ask_analysis_ai",
                            report=persisted_application_report,
                        )
                        st.session_state["latest_report"] = (
                            persisted_application_report
                        )
                        update_application_report(
                            application_id=current_application_id,
                            resume_filename=st.session_state.get(
                                "resume_filename",
                                "",
                            ),
                            report=persisted_application_report,
                        )

                        st.rerun()

                    except ValueError as exc:
                        st.warning(str(exc))

                    except RuntimeError as exc:
                        st.error(f"LLM/API error: {exc}")

                    except Exception as exc:
                        st.error(f"Unexpected error while answering question: {exc}")

                render_ai_action_subtotal(
                    application_id=current_application_id,
                    actions=["ask_analysis_ai"],
                    label="Ask AI About Analysis subtotal",
                )

            with clear_col:
                if st.button("Clear Chat", width="stretch"):
                    clear_application_chat_history(current_application_id)
                    st.rerun()

    elif current_application_id is not None:
        st.info(
            f"Application session #{current_application_id} is open. "
            "Upload a resume, paste a job description, then click **Analyze Resume**."
        )
    else:
        st.info("Click **New Application Session**, or upload a resume and paste a job description to begin.")

elif page == "Blueprint Library":
    st.divider()
    global_blueprint_application_id = st.session_state.get(
        "current_application_id"
    )
    render_phase9d_global_blueprints(
        current_application_id=global_blueprint_application_id
    )

elif page == "Job Market Insights":
    # ---------------------------------------------------------------------------
    # Job Market Insights / Chroma RAG page
    # ---------------------------------------------------------------------------

    st.divider()
    st.header("Job Market Insights from Analyzed Jobs")

    st.caption(
        "This page uses job descriptions from previous **Analyze Resume** runs. "
        "Upload or paste a separate resume here to compare it against the aggregate job market data."
    )

    # -----------------------------------------------------------------------
    # Vector index status
    # -----------------------------------------------------------------------

    st.subheader("Vector Index")

    saved_jds = get_recent_job_descriptions(limit=200)
    saved_jd_count = len(saved_jds)

    try:
        index_count = get_chroma_index_count()
        st.write(f"Analyzed job descriptions: **{saved_jd_count}**")
        st.write(f"Indexed Chroma chunks: **{index_count}**")
    except Exception as exc:
        st.warning(f"Could not read Chroma index count: {exc}")

    if saved_jd_count == 0:
        st.info("No analyzed job descriptions yet. Go to **Application Sessions** and run **Analyze Resume** first.")

    if st.button("Rebuild Chroma Index from Analyzed Jobs", width="stretch"):
        try:
            total_chunks = rebuild_chroma_index(limit=200)
            st.success(f"Rebuilt Chroma index with {total_chunks} chunks.")
            st.rerun()
        except Exception as exc:
            st.error(f"Unexpected error while rebuilding Chroma index: {exc}")

    # -----------------------------------------------------------------------
    # RAG-specific resume input and market-fit score
    # -----------------------------------------------------------------------

    st.divider()
    st.subheader("Resume for Market Comparison")

    st.caption(
        "This resume is only used on the Job Market Insights page. "
        "It is separate from the currently loaded application session."
    )

    rag_resume_upload = st.file_uploader(
        "Upload resume for market comparison",
        type=["pdf", "docx"],
        key="rag_resume_upload",
        help="Upload a PDF or DOCX resume to compare against all analyzed job descriptions.",
    )

    rag_resume_text_input = st.text_area(
        "Or paste resume text for market comparison",
        height=180,
        key="rag_resume_text_input",
        placeholder="Optional: paste resume text here instead of uploading a file.",
    )

    if st.button("Analyze Resume for Market Fit", width="stretch"):
        try:
            reset_call_ledger()
            if rag_resume_upload is not None:
                rag_resume_text = read_uploaded_resume(rag_resume_upload)
                rag_resume_source = rag_resume_upload.name
            elif rag_resume_text_input.strip():
                rag_resume_text = rag_resume_text_input.strip()
                rag_resume_source = "pasted resume text"
            else:
                raise ValueError("Upload a resume or paste resume text first.")

            with st.spinner("Extracting resume profile for market comparison..."):
                rag_resume_profile = extract_resume_profile(rag_resume_text)

            st.session_state["rag_resume_profile"] = rag_resume_profile
            st.session_state["rag_resume_source"] = rag_resume_source
            append_api_usage(
                application_id=None,
                action="analyse_market_resume",
                report=None,
            )

            st.success(f"Resume loaded for market comparison: {rag_resume_source}")
            st.rerun()

        except ValueError as exc:
            st.warning(str(exc))
        except RuntimeError as exc:
            st.error(f"LLM/API error: {exc}")
        except Exception as exc:
            st.error(f"Unexpected error while analyzing market resume: {exc}")

    render_ai_action_subtotal(
        application_id=None,
        actions=["analyse_market_resume"],
        label="Market Resume Analysis subtotal",
    )

    rag_resume_profile = st.session_state.get("rag_resume_profile")

    if rag_resume_profile:
        st.success(f"Using market comparison resume: {st.session_state.get('rag_resume_source', 'resume')}")

        with st.expander("View extracted market resume profile"):
            st.json(rag_resume_profile)

        if saved_jd_count == 0:
            st.info("Analyze at least one job description first before calculating market fit.")
        else:
            try:
                market_fit = compare_resume_to_common_market_skills(
                    rag_resume_profile,
                    top_n=30,
                    min_count=1,
                )

                st.subheader("Overall Market Fit Score")
                st.metric(
                    "Market Fit Against Frequent JD Skills",
                    f"{market_fit.get('market_fit_score', 0)}/100",
                )

                st.caption(
                    "This score compares the uploaded/pasted resume against common skills "
                    "found across analyzed job descriptions. It is separate from the one-job ATS score."
                )

                st.write("### Common Skills Already Shown")
                matched_terms = market_fit.get("matched_common_terms", [])

                if matched_terms:
                    st.dataframe(matched_terms, width="stretch")
                else:
                    st.info("No common terms were strongly matched.")

                st.write("### Common Skills Missing or Weakly Evidenced")
                missing_terms = market_fit.get("missing_common_terms", [])

                if missing_terms:
                    st.dataframe(missing_terms, width="stretch")
                else:
                    st.success("No common missing terms detected.")

                with st.expander("Common JD terms used for scoring"):
                    common_terms = get_common_jd_terms(top_n=20)
                    st.write("Required skills")
                    st.dataframe(common_terms.get("required_skills", []), width="stretch")
                    st.write("Tools and technologies")
                    st.dataframe(common_terms.get("tools_technologies", []), width="stretch")
                    st.write("Preferred skills")
                    st.dataframe(common_terms.get("preferred_skills", []), width="stretch")
                    st.write("Soft skills")
                    st.dataframe(common_terms.get("soft_skills", []), width="stretch")

            except Exception as exc:
                st.warning(f"Could not calculate market fit score: {exc}")
    else:
        st.info("Upload or paste a resume above to calculate your market fit score.")

    # -----------------------------------------------------------------------
    # Analyzed JD records
    # -----------------------------------------------------------------------

    st.divider()
    st.subheader("Analyzed Job Descriptions")

    if not saved_jds:
        st.caption("No analyzed job descriptions saved yet.")
    else:
        for jd_id, application_id, title, company, source_type, created_at in saved_jds[:20]:
            label = f"{title or 'Untitled Job'} @ {company or 'Unknown Company'}"

            with st.expander(label):
                saved_jd = get_job_description_by_id(jd_id)

                if saved_jd:
                    st.write(f"**Linked application session:** {saved_jd.get('application_id', '')}")
                    st.write(f"**Source type:** {saved_jd.get('source_type', '')}")
                    st.write(f"**Created:** {saved_jd.get('created_at', '')}")

                    st.write("**JD Profile**")
                    st.json(saved_jd.get("jd_profile", {}))

                    col_a, col_b = st.columns(2)

                    with col_a:
                        if st.button("Re-index JD", key=f"reindex_jd_{jd_id}", width="stretch"):
                            chunk_count = index_job_description_to_chroma(jd_id)
                            st.success(f"Re-indexed {chunk_count} chunks.")
                            st.rerun()

                    with col_b:
                        if st.button("Remove from RAG Library", key=f"delete_jd_{jd_id}", width="stretch"):
                            delete_job_description_from_chroma(jd_id)
                            delete_job_description(jd_id)
                            st.success("Removed job description and vector chunks from RAG library.")
                            st.rerun()

    # -----------------------------------------------------------------------
    # Persistent RAG chatbot
    # -----------------------------------------------------------------------

    st.divider()
    st.subheader("RAG Chatbot Across Analyzed Jobs")

    st.caption(
        "This chat history is saved globally for the Job Market Insights page. "
        "The chatbot uses all indexed analyzed job descriptions and the market comparison resume if one is loaded."
    )

    rag_messages = get_rag_chat_messages(limit=80)

    if rag_messages:
        for message in rag_messages:
            if message["role"] == "user":
                st.markdown(f"**You:** {message['content']}")
            else:
                st.markdown(f"**AI:** {message['content']}")
    else:
        st.caption("No RAG questions asked yet.")

    rag_question = st.text_input(
        "Ask a market/RAG question",
        placeholder="Example: Based on my uploaded resume, what common skills should I strengthen?",
        key="rag_market_question",
    )

    rag_chat_col, rag_clear_col = st.columns([0.75, 0.25])

    with rag_chat_col:
        if st.button("Ask Chroma RAG", width="stretch"):
            try:
                reset_call_ledger()
                answer = answer_jd_library_question_chroma(
                    rag_question,
                    resume_profile=st.session_state.get("rag_resume_profile"),
                    top_k=6,
                )

                add_rag_chat_message("user", rag_question)
                add_rag_chat_message("assistant", answer)

                append_api_usage(
                    application_id=None,
                    action="ask_chroma_rag",
                    report=None,
                )

                st.rerun()

            except ValueError as exc:
                st.warning(str(exc))
            except RuntimeError as exc:
                st.error(f"LLM/API error: {exc}")
            except Exception as exc:
                st.error(f"Unexpected error while answering Chroma RAG question: {exc}")

        render_ai_action_subtotal(
            application_id=None,
            actions=["ask_chroma_rag"],
            label="Ask Chroma RAG subtotal",
        )

    with rag_clear_col:
        if st.button("Clear RAG Chat", width="stretch"):
            clear_rag_chat_history()
            st.rerun()
elif page == "Profile & Evidence":
    st.divider()
    st.header("Profile & Evidence Library")

    st.caption(
        "Add truthful evidence that may not fit into your current one-page resume. "
        "The app can use this later to recommend which projects or skills to include "
        "without inventing experience."
    )

    st.subheader("Add Evidence Item")
    st.caption(
        "For Project evidence, bullet order matters. "
        "The first canonical bullet is the project lead and is shown first "
        "in tailored résumés whenever that bullet is selected."
    )

    with st.form("add_evidence_form"):
        category = st.selectbox(
            "Category",
            ["Project", "Internship", "Coursework", "Certification", "Skill", "Achievement", "Other"],
        )

        title = st.text_input("Title", placeholder="Example: Job AI Helper")
        
        period = st.text_input(
            "Date / Period, optional",
            placeholder="Example: Jun 2024 – Jul 2024",
        )

        description = st.text_area(
            "What did you actually do?",
            height=160,
            placeholder="Describe real work done. Do not include fake experience.",
        )

        skills_text = st.text_input(
            "Supported skills, comma-separated",
            placeholder="Example: Python, Streamlit, RAG, prompt engineering",
        )

        tools_text = st.text_input(
            "Tools/technologies, comma-separated",
            placeholder="Example: OpenAI API, SQLite, ChromaDB",
        )

        impact = st.text_area(
            "Impact or scope",
            height=90,
            placeholder="Example: Supports resume-job analysis, cover letter generation, and saved sessions.",
        )

        submitted = st.form_submit_button("Save Evidence")

        if submitted:
            try:
                skills = [item.strip() for item in skills_text.split(",") if item.strip()]
                tools = [item.strip() for item in tools_text.split(",") if item.strip()]

                create_evidence_item(
                    category=category,
                    title=title,
                    description=description,
                    period=period,
                    skills=skills,
                    tools=tools,
                    impact=impact,
                    source_type="manual",
                )

                st.success("Evidence item saved.")
                st.rerun()

            except ValueError as exc:
                st.warning(str(exc))
            except Exception as exc:
                st.error(f"Unexpected error while saving evidence: {exc}")


    st.divider()
    st.subheader("Saved Evidence")

    evidence_sort_mode = st.selectbox(
    "Evidence display order",
    [
        "Earliest period first",
        "Newest period first",
        "Recently edited first",
    ],
)

    if evidence_sort_mode == "Earliest period first":
        evidence_items = get_evidence_items(
            limit=100,
            sort_by_period=True,
            period_order="earliest_first",
        )
    elif evidence_sort_mode == "Newest period first":
        evidence_items = get_evidence_items(
            limit=100,
            sort_by_period=True,
            period_order="newest_first",
        )
    else:
        evidence_items = get_evidence_items(limit=100)

   # evidence_items = get_evidence_items(limit=100)

    if not evidence_items:
        st.info("No evidence items saved yet.")
    else:
        for item in evidence_items:
            with st.expander(f"{item['category']}: {item['title']}"):

                description = str(item.get("description", "")).strip()

                if description:
                    lines = [line.strip() for line in description.splitlines() if line.strip()]

                    if lines:
                        for line_index, line in enumerate(lines):
                            cleaned_line = line.lstrip("•-* ").strip()

                            if cleaned_line:
                                if (
                                    item.get("category") == "Project"
                                    and line_index == 0
                                ):
                                    st.markdown(
                                        f"- **Lead:** {cleaned_line}"
                                    )
                                else:
                                    st.markdown(f"- {cleaned_line}")
                    else:
                        st.write(description)

                if item.get("period"):
                    st.write("**Period:** " + item["period"])

                if item.get("skills"):
                    st.write("**Skills:** " + ", ".join(item["skills"]))

                if item.get("tools"):
                    st.write("**Tools:** " + ", ".join(item["tools"]))

                if item.get("impact"):
                    st.write("**Impact/scope:** " + item["impact"])

                # with st.expander("Debug raw evidence value"):
                #     st.code(item.get("description", ""), language=None)

                st.divider()

                if item.get("category") == "Project":
                    with st.expander("Suggest canonical CAR bullets"):
                        st.caption(
                            "Uses the current Evidence Library description, skills, tools, and impact "
                            "to suggest stable master bullets. Review before saving."
                        )

                        suggestion_key = f"canonical_bullet_suggestion_{item['id']}"

                        if st.button(
                            "Suggest canonical bullets",
                            key=f"suggest_canonical_bullets_{item['id']}",
                            width="stretch",
                        ):
                            try:
                                reset_call_ledger()
                                with st.spinner("Suggesting canonical bullets..."):
                                    suggestion = suggest_canonical_project_bullets(
                                        title=item.get("title", ""),
                                        period=item.get("period", ""),
                                        description=item.get("description", ""),
                                        skills=item.get("skills", []),
                                        tools=item.get("tools", []),
                                        impact=item.get("impact", ""),
                                    )

                                st.session_state[suggestion_key] = suggestion
                                append_api_usage(
                                    application_id=None,
                                    action="suggest_canonical_bullets",
                                    report=None,
                                )
                                st.rerun()

                            except ValueError as exc:
                                st.warning(str(exc))
                            except RuntimeError as exc:
                                st.error(f"LLM/API error: {exc}")
                            except Exception as exc:
                                st.error(f"Unexpected error while suggesting bullets: {exc}")

                        render_ai_action_subtotal(
                            application_id=None,
                            actions=["suggest_canonical_bullets"],
                            label="Canonical Bullet Suggestion subtotal",
                        )

                        suggestion = st.session_state.get(suggestion_key)

                        if suggestion:
                            suggested_description = canonical_bullets_to_description(suggestion)

                            st.write("**Suggested canonical bullets:**")
                            for bullet in suggestion.get("canonical_bullets", []):
                                st.markdown(f"- {bullet}")

                            if suggestion.get("notes"):
                                with st.expander("Suggestion notes"):
                                    st.json(suggestion.get("notes", []))

                            st.text_area(
                                "Suggested Evidence Library description",
                                value=suggested_description,
                                height=180,
                                key=f"suggested_canonical_description_{item['id']}",
                            )

                            if st.button(
                                "Apply suggestion to edit form",
                                key=f"apply_canonical_suggestion_{item['id']}",
                                width="stretch",
                            ):
                                st.session_state[f"edit_evidence_mode_{item['id']}"] = True
                                st.session_state[f"edit_description_{item['id']}"] = suggested_description
                                st.success("Suggestion applied to the edit form. Review it, then click Save Changes.")
                                st.rerun()

                edit_mode = st.checkbox(
                    "Edit evidence",
                    key=f"edit_evidence_mode_{item['id']}",
                )

                if edit_mode:
                    current_category = item.get("category", "Project")

                    if current_category in CATEGORY_OPTIONS:
                        category_index = CATEGORY_OPTIONS.index(current_category)
                    else:
                        category_index = 0

                    with st.form(f"edit_evidence_form_{item['id']}"):
                        edited_category = st.selectbox(
                            "Category",
                            CATEGORY_OPTIONS,
                            index=category_index,
                            key=f"edit_category_{item['id']}",
                        )

                        edited_title = st.text_input(
                            "Title",
                            value=item.get("title", ""),
                            key=f"edit_title_{item['id']}",
                        )

                        edited_period = st.text_input(
                            "Date / Period, optional",
                            value=item.get("period", ""),
                            key=f"edit_period_{item['id']}",
                        )

                        edited_description = st.text_area(
                            "Canonical bullets / master evidence",
                            value=item.get("description", ""),
                            height=180,
                            key=f"edit_description_{item['id']}",
                            help=(
                                "These are the user-approved master bullets. "
                                "The first bullet is the project lead and is shown first "
                                "in tailored résumés when selected. Tailoring should "
                                "select or lightly rephrase from these, not rewrite from scratch."
                            ),
                        )
                        if edited_category == "Project":
                            st.caption(
                                "Lead bullet: put the bullet that best summarizes "
                                "the project or your main contribution first. "
                                "It is shown first whenever it is selected."
                            )

                        edited_skills = st.text_input(
                            "Supported skills, comma-separated",
                            value=", ".join(item.get("skills", [])),
                            key=f"edit_skills_{item['id']}",
                        )

                        edited_tools = st.text_input(
                            "Tools/technologies, comma-separated",
                            value=", ".join(item.get("tools", [])),
                            key=f"edit_tools_{item['id']}",
                        )

                        edited_impact = st.text_area(
                            "Impact or scope",
                            value=item.get("impact", ""),
                            height=90,
                            key=f"edit_impact_{item['id']}",
                        )

                        save_changes = st.form_submit_button("Save Changes")

                        if save_changes:
                            try:
                                update_evidence_item(
                                    item["id"],
                                    category=edited_category,
                                    title=edited_title,
                                    description=edited_description,
                                    period=edited_period,
                                    skills=[
                                        skill.strip()
                                        for skill in edited_skills.split(",")
                                        if skill.strip()
                                    ],
                                    tools=[
                                        tool.strip()
                                        for tool in edited_tools.split(",")
                                        if tool.strip()
                                    ],
                                    impact=edited_impact,
                                    source_type=item.get("source_type", "manual"),
                                )

                                st.success("Evidence updated.")
                                st.rerun()

                            except ValueError as exc:
                                st.warning(str(exc))

                            except Exception as exc:
                                st.error(f"Unexpected error while updating evidence: {exc}")

                st.divider()

                delete_col, spacer_col = st.columns([0.25, 0.75])

                with delete_col:
                    if st.button(
                        "Delete Evidence",
                        key=f"delete_evidence_{item['id']}",
                        width="stretch",
                    ):
                        delete_evidence_item(item["id"])
                        st.success("Evidence deleted.")
                        st.rerun()
        # for item in evidence_items:
        #     with st.expander(f"{item['category']}: {item['title']}"):
        #         st.write(item["description"])

        #         if item.get("skills"):
        #             st.write("**Skills:** " + ", ".join(item["skills"]))

        #         if item.get("tools"):
        #             st.write("**Tools:** " + ", ".join(item["tools"]))

        #         if item.get("impact"):
        #             st.write("**Impact/scope:** " + item["impact"])

        #         if st.button("Delete Evidence", key=f"delete_evidence_{item['id']}", width="stretch"):
        #             delete_evidence_item(item["id"])
        #             st.success("Evidence deleted.")
        #             st.rerun()
