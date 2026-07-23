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
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd
import streamlit as st
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
    generate_tailored_resume_copy,
    extract_docx_preview_text,
    convert_docx_to_pdf_if_possible,
    pdf_to_iframe_html,
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
from database.jd_library_manager import (
    init_jd_library,
    save_or_link_job_description_for_application,
    save_or_update_job_description_for_application,
    get_recent_job_descriptions,
    get_job_description_by_id,
    get_job_description_by_application_id,
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
from llm import (
    ask_text,
    get_active_model,
    get_model_options,
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


# ---------------------------------------------------------------------------
# Streamlit app
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Job AI Helper",
    page_icon="📄",
    layout="wide",
)

init_db()
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

    page = st.radio(
        "Go to",
        ["Application Sessions", "Job Market Insights", "Profile & Evidence"],
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

    else:
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


if page == "Application Sessions":
    input_suffix = st.session_state["input_reset_counter"]

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
                    with st.expander("Debug: Extracted resume text", expanded=True):
                        st.text(resume_text[-3000:])

                st.write(f"Extracted {len(resume_text)} characters from resume.")

                actual_page_count = (
                    calculate_uploaded_resume_page_count(
                        uploaded_resume
                    )
                )

                if actual_page_count is None:
                    st.write(
                        "Rendered page count could not be "
                        "determined. Structure analysis will "
                        "treat the page count as unknown."
                    )
                else:
                    st.write(
                        f"Detected {actual_page_count} "
                        "rendered résumé page(s)."
                    )

                jd_text = validate_jd_text(jd_text_input)
                st.write(f"Read {len(jd_text)} characters from job description.")

                status.update(label="Running AI analysis...", state="running")
                report = run_resume_analysis(resume_text, jd_text, degree, actual_page_count=actual_page_count,)

                # Store the full pasted job description in the saved report.
                # This makes saved sessions self-contained for debugging/rebuilds.
                report["raw_jd_text"] = jd_text

                status.update(label="Analysis complete.", state="complete")

            application_id = st.session_state.get("current_application_id")

            if application_id is None:
                # If the user did not click "New Application Session", create one automatically.
                application_id = save_application(
                    resume_filename=uploaded_resume.name,
                    report=report,
                    cover_letter="",
                )
            else:
                update_application_report(
                    application_id=application_id,
                    resume_filename=uploaded_resume.name,
                    report=report,
                )

            # Clear old tailored resume state when this session is re-analysed.
            # This prevents old tailored projects/skills/DOCX preview from showing after a new analysis.
            for key in [
                f"tailored_projects_result_{application_id}",
                f"tailored_projects_fit_{application_id}",
                f"tailored_skills_result_{application_id}",
                f"tailored_resume_copy_path_{application_id}",
                f"tailored_resume_fit_result_{application_id}",
                f"saved_resume_docx_path_{application_id}",

                # Add these debug keys too
                f"debug_project_tailor_inputs_{application_id}",
                f"project_candidate_pool_{application_id}",
                f"project_tailor_debug_path_{application_id}",
                f"project_tailor_input_fingerprint_{application_id}",
            ]:
                st.session_state.pop(key, None)

            cleanup_old_tailored_outputs_for_application(application_id)
            st.session_state.pop("saved_resume_docx_path", None)

            if save_resume_docx_for_editing:
                if uploaded_resume.name.lower().endswith(".docx"):
                    saved_resume_docx_path = save_uploaded_docx_for_editing(
                        uploaded_resume,
                        application_id=application_id,
                    )
                    st.session_state["saved_resume_docx_path"] = str(saved_resume_docx_path)
                    st.session_state[f"saved_resume_docx_path_{application_id}"] = str(saved_resume_docx_path)

                else:
                    st.warning(
                        "Analysis was saved, but editable resume-copy generation requires a DOCX file. "
                        "PDF files are not saved for this feature."
                    )

            else:
                # If the user started or loaded a session, update that session with the analysis result.
                update_application_report(
                    application_id=application_id,
                    resume_filename=uploaded_resume.name,
                    report=report,
                )

            jd_library_message = ""

            try:
                # Save/update the analyzed job description into the JD Library.
                # This means the RAG feature only uses jobs that went through Analyze Resume.
                jd_profile_for_library = report.get("jd_profile", {})

                jd_save_result = save_or_link_job_description_for_application(
                    application_id=application_id,
                    raw_text=jd_text,
                    jd_profile=jd_profile_for_library,
                    title=jd_profile_for_library.get("job_title", ""),
                    company=jd_profile_for_library.get("company", ""),
                    location=jd_profile_for_library.get("location", ""),
                    source_type="application_session",
                    source_url="",
                )

                orphaned_canonical_id = jd_save_result.get(
                    "orphaned_canonical_jd_id"
                )
                if orphaned_canonical_id:
                    delete_job_description_from_chroma(
                        jd_save_result.get("orphaned_job_description_id"),
                        canonical_jd_id=orphaned_canonical_id,
                    )

                if jd_save_result.get("needs_chroma_index"):
                    chunk_count = index_job_description_to_chroma(
                        int(jd_save_result["job_description_id"])
                    )
                    jd_library_message = (
                        f" Indexed canonical JD into Chroma with {chunk_count} chunks."
                    )
                else:
                    jd_library_message = (
                        " Reused the existing canonical JD; no duplicate embeddings were created."
                    )

            except Exception as rag_exc:
                # The main resume analysis should still succeed even if RAG indexing fails.
                jd_library_message = f" RAG indexing skipped: {rag_exc}"

            st.session_state["latest_report"] = report
            st.session_state["resume_filename"] = uploaded_resume.name
            st.session_state["current_application_id"] = application_id

            # Clear old generated content when a new resume/job is analysed.
            st.session_state.pop("cover_letter", None)
            st.session_state["revision_history"] = []
            st.session_state["analysis_chat"] = []

            st.session_state["flash_message"] = f"Saved application session #{application_id}.{jd_library_message}"
            st.rerun()

        except ValueError as exc:
            st.error(f"Input error: {exc}")
            st.stop()

        except RuntimeError as exc:
            st.error(f"LLM/API error: {exc}")
            st.info("Check your .env file locally, or Streamlit Cloud secrets after deployment.")
            st.stop()

        except Exception as exc:
            st.error(f"Unexpected error: {exc}")
            st.stop()


    report = st.session_state.get("latest_report")
    current_application_id = st.session_state.get("current_application_id")

    if report:
        overall_score = int(report.get("overall_score", 0))
        passed = bool(report.get("passes_ats_threshold", False))

        st.divider()
        st.header("Results")

        if current_application_id is not None:
            st.caption(f"Current application session: #{current_application_id}")

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


        st.divider()
        st.header("Tailor Resume for This Job")
        st.caption(
            "Phase 6B uses canonical requirement IDs and fixed Python weights "
            "for Project selection and Skills priorities. AI numeric scores are "
            "diagnostic only."
        )

        if current_application_id is None:
            st.info("Save or load an application session before tailoring the resume.")
        else:
            tailored_projects_key = f"tailored_projects_result_{current_application_id}"
            tailored_fit_key = f"tailored_projects_fit_{current_application_id}"
            tailored_skills_key = f"tailored_skills_result_{current_application_id}"
            tailored_docx_key = f"tailored_resume_copy_path_{current_application_id}"
            tailored_fit_result_key = f"tailored_resume_fit_result_{current_application_id}"
            saved_docx_key = f"saved_resume_docx_path_{current_application_id}"
            tailored_generation_id_key = (
                f"tailored_generation_id_{current_application_id}"
            )

            max_projects = st.slider(
                "Maximum projects",
                1,
                4,
                3,
                key=f"max_projects_{current_application_id}",
            )

            max_bullets = st.slider(
                "Maximum bullets for strongest project",
                1,
                3,
                3,
                key=f"max_bullets_{current_application_id}",
            )

            if st.button(
                "Generate Projects + Skills",
                type="primary",
                width="stretch",
                key=f"generate_projects_skills_{current_application_id}",
            ):
                try:
                    evidence_items = get_evidence_items(limit=100)

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

                    with st.spinner(
                        "Generating tailored projects and skills..."
                    ):
                        project_result = tailor_projects_section(
                            resume_profile=report.get("resume_profile", {}),
                            jd_profile=report.get("jd_profile", {}),
                            evidence_items=evidence_items,
                            max_projects=max_projects,
                            max_bullets_per_project=max_bullets,
                            keyword_match=report.get("keyword_match", {}),
                            raw_jd_text=report.get("raw_jd_text", ""),
                            stable_analysis=report.get("stable_analysis", {}),
                        )

                        fit_estimate = estimate_project_section_length(
                            project_result,
                            max_projects=max_projects,
                            max_total_bullets=max_projects * max_bullets,
                        )

                        skills_result = tailor_skills_section(
                            resume_profile=report.get("resume_profile", {}),
                            jd_profile=report.get("jd_profile", {}),
                            evidence_items=evidence_items,
                            stable_analysis=report.get("stable_analysis", {}),
                            selected_projects_result=project_result,
                        )

                    st.session_state[tailored_projects_key] = project_result
                    st.session_state[tailored_fit_key] = fit_estimate
                    st.session_state[tailored_skills_key] = skills_result
                    st.session_state.pop(tailored_docx_key, None)
                    st.session_state.pop(tailored_fit_result_key, None)
                    st.session_state[tailored_generation_id_key] = uuid.uuid4().hex
                    st.rerun()

                except ValueError as exc:
                    st.warning(str(exc))
                except RuntimeError as exc:
                    st.error(f"LLM/API error: {exc}")
                except Exception as exc:
                    st.error(
                        "Unexpected error while tailoring projects and skills: "
                        f"{exc}"
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
                    ):
                        try:
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
                                    keyword_match=report.get("keyword_match", {}),
                                    raw_jd_text=report.get("raw_jd_text","",),
                                    stable_analysis=report.get("stable_analysis", {}),
                                )

                                fit_estimate = estimate_project_section_length(
                                    project_result,
                                    max_projects=max_projects,
                                    max_total_bullets=max_projects * max_bullets,
                                )

                            st.session_state[tailored_projects_key] = project_result
                            st.session_state[tailored_fit_key] = fit_estimate
                            st.session_state.pop(tailored_docx_key, None)
                            st.session_state.pop(tailored_fit_result_key, None)
                            st.session_state[tailored_generation_id_key] = uuid.uuid4().hex
                            st.rerun()

                        except ValueError as exc:
                            st.warning(str(exc))
                        except RuntimeError as exc:
                            st.error(f"LLM/API error: {exc}")
                        except Exception as exc:
                            st.error(f"Unexpected error while tailoring projects: {exc}")

                with col_skills:
                    if st.button(
                        "Generate Tailored Skills Section",
                        width="stretch",
                        key=f"generate_skills_{current_application_id}",
                    ):
                        try:
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

                            st.session_state[tailored_skills_key] = skills_result
                            st.session_state.pop(tailored_docx_key, None)
                            st.session_state.pop(tailored_fit_result_key, None)
                            st.session_state[tailored_generation_id_key] = uuid.uuid4().hex
                            st.rerun()

                        except ValueError as exc:
                            st.warning(str(exc))
                        except RuntimeError as exc:
                            st.error(f"LLM/API error: {exc}")
                        except Exception as exc:
                            st.error(f"Unexpected error while tailoring skills: {exc}")

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

                with st.expander("Unsupported JD skills"):
                    st.json(project_result.get("unsupported_jd_skills", []))

                with st.expander("Full tailored projects JSON"):
                    st.json(project_result)

            if skills_result:
                st.write("### Recommended Skills Section")

                st.text_area(
                    "Preview skills text",
                    value=skill_lines_to_plain_text(skills_result),
                    height=160,
                    key=f"skills_preview_{current_application_id}",
                )

                with st.expander("Evidence-supported additions"):
                    st.json(skills_result.get("evidence_supported_additions", []))

                with st.expander("Unsupported JD skills"):
                    st.json(skills_result.get("unsupported_jd_skills", []))

            st.divider()
            st.subheader("Generate Edited Resume Copy")

            st.caption(
            "This can change the Skills section, Projects section, or both in a copied DOCX. "
            "Work Experience is not changed."
            )

            saved_resume_docx_path = st.session_state.get(saved_docx_key)

            if not saved_resume_docx_path:
                latest_saved_docx = get_latest_saved_docx_for_application(current_application_id)
                
                if latest_saved_docx:
                    saved_resume_docx_path = str(latest_saved_docx)
                    st.session_state[saved_docx_key] = saved_resume_docx_path

            if not saved_resume_docx_path:
                st.info(
                    "No saved DOCX found for this session. Upload a DOCX resume, "
                    "tick the save checkbox, and run Analyze Resume again."
                )
            elif not project_result and not skills_result:
                st.info("Generate a Tailored Projects Section or Tailored Skills Section first.")
            else:
                selected_sections = []

                if project_result:
                    selected_sections.append("Projects")

                if skills_result:
                    selected_sections.append("Skills")

                st.success(f"Saved DOCX loaded for this session: {Path(saved_resume_docx_path).name}")
                st.caption(f"Will update: {', '.join(selected_sections)}")

                with st.expander("Fitting strategy", expanded=True):
                    use_compact_before_delete = st.checkbox(
                        "Compact project wording before deleting content",
                        value=True,
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
                        value=False,
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
                        value=False,
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

                    page_density_label = st.radio(
                        "Page density",
                        ["Balanced", "Maximize relevant content"],
                        horizontal=True,
                        key=f"page_density_mode_{current_application_id}",
                        help=(
                            "Balanced restores content up to about 92% page fill. "
                            "Maximize relevant content restores more truthful content "
                            "up to about 97%. This setting never removes content when "
                            "the full version already fits."
                        ),
                    )
                    page_density_mode = (
                        "maximize"
                        if page_density_label == "Maximize relevant content"
                        else "balanced"
                    )

                    st.caption(
                        "These options apply only when generating and fitting the "
                        "DOCX. Changing them does not regenerate Projects or Skills."
                    )

                with st.expander("Spacing options", expanded=False):
                    spacing_mode_label = st.radio(
                        "Spacing mode",
                        ["Paragraph spacing", "Blank line"],
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
                        value=False,
                        key=f"spacing_before_first_project_{current_application_id}",
                    )

                    if spacing_mode == "paragraph_spacing":
                        project_spacing_pt = st.slider(
                            "Spacing before each next project (pt)",
                            0,
                            20,
                            10,
                            key=f"project_spacing_pt_{current_application_id}",
                        )

                        after_projects_spacing_pt = st.slider(
                            "Spacing after final project / before Skills (pt)",
                            0,
                            20,
                            10,
                            key=f"after_projects_spacing_pt_{current_application_id}",
                        )

                        blank_lines_between_projects = 0
                        blank_lines_after_projects = 0

                    else:
                        blank_lines_between_projects = st.number_input(
                            "Blank lines before each project",
                            min_value=0,
                            max_value=3,
                            value=1,
                            step=1,
                            key=f"blank_lines_between_projects_{current_application_id}",
                        )

                        blank_lines_after_projects = st.number_input(
                            "Blank lines after final project / before Skills",
                            min_value=0,
                            max_value=3,
                            value=1,
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
                ):
                    try:
                        fit_result = generate_tailored_resume_copy_fit_one_page(
                            saved_resume_docx_path=saved_resume_docx_path,
                            tailored_projects=project_result,
                            tailored_skills=skills_result,
                            application_id=current_application_id,
                            max_projects=max_projects,
                            max_bullets_per_project=max_bullets,
                            spacing_mode=spacing_mode,
                            project_spacing_pt=project_spacing_pt,
                            after_projects_spacing_pt=after_projects_spacing_pt,
                            blank_lines_between_projects=blank_lines_between_projects,
                            blank_lines_after_projects=blank_lines_after_projects,
                            add_spacing_before_first_project=add_spacing_before_first_project,
                            use_compact_before_delete=use_compact_before_delete,
                            prefer_balanced_bullets=prefer_balanced_bullets,
                            allow_skills_compaction=allow_skills_compaction,
                            page_density_mode=page_density_mode,
                            generation_id=st.session_state.get(
                                tailored_generation_id_key
                            ),
                        )

                        tailored_resume_path = fit_result["docx_path"]

                        st.session_state[tailored_docx_key] = str(tailored_resume_path)
                        st.session_state[tailored_fit_result_key] = fit_result

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

            has_debug_content = any(
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



            if tailored_resume_copy_path and Path(tailored_resume_copy_path).exists():
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

                pdf_preview_path = convert_docx_to_pdf_if_possible(tailored_resume_copy_path)

                if pdf_preview_path:
                    st.markdown(
                        pdf_to_iframe_html(pdf_preview_path, height=800),
                        unsafe_allow_html=True,
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
        st.header("Tailored Cover Letter")

        if st.button("Generate Cover Letter", type="primary", width="stretch"):
            try:
                with st.spinner("Generating tailored cover letter..."):
                    cover_letter = generate_cover_letter(report)

                st.session_state["cover_letter"] = cover_letter
                st.session_state.setdefault("revision_history", [])

                application_id = st.session_state.get("current_application_id")

                if application_id is None:
                    application_id = save_application(
                        resume_filename=st.session_state.get("resume_filename", "uploaded_resume"),
                        report=report,
                        cover_letter=cover_letter,
                    )
                    st.session_state["current_application_id"] = application_id
                else:
                    update_application_cover_letter(application_id, cover_letter)

                st.success("Cover letter saved to the current application session.")

            except RuntimeError as exc:
                st.error(f"LLM/API error: {exc}")

            except Exception as exc:
                st.error(f"Unexpected error while generating cover letter: {exc}")

        cover_letter = st.session_state.get("cover_letter", "")

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

                    st.rerun()

                except ValueError as exc:
                    st.warning(str(exc))

                except RuntimeError as exc:
                    st.error(f"LLM/API error: {exc}")

                except Exception as exc:
                    st.error(f"Unexpected error while revising cover letter: {exc}")

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

                        st.rerun()

                    except ValueError as exc:
                        st.warning(str(exc))

                    except RuntimeError as exc:
                        st.error(f"LLM/API error: {exc}")

                    except Exception as exc:
                        st.error(f"Unexpected error while answering question: {exc}")

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

            st.success(f"Resume loaded for market comparison: {rag_resume_source}")
            st.rerun()

        except ValueError as exc:
            st.warning(str(exc))
        except RuntimeError as exc:
            st.error(f"LLM/API error: {exc}")
        except Exception as exc:
            st.error(f"Unexpected error while analyzing market resume: {exc}")

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
                answer = answer_jd_library_question_chroma(
                    rag_question,
                    resume_profile=st.session_state.get("rag_resume_profile"),
                    top_k=6,
                )

                add_rag_chat_message("user", rag_question)
                add_rag_chat_message("assistant", answer)

                st.rerun()

            except ValueError as exc:
                st.warning(str(exc))
            except RuntimeError as exc:
                st.error(f"LLM/API error: {exc}")
            except Exception as exc:
                st.error(f"Unexpected error while answering Chroma RAG question: {exc}")

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
                        for line in lines:
                            cleaned_line = line.lstrip("•-* ").strip()

                            if cleaned_line:
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
                                st.rerun()

                            except ValueError as exc:
                                st.warning(str(exc))
                            except RuntimeError as exc:
                                st.error(f"LLM/API error: {exc}")
                            except Exception as exc:
                                st.error(f"Unexpected error while suggesting bullets: {exc}")

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
                                "Tailoring should select or lightly rephrase from these, not rewrite from scratch."
                            ),
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


