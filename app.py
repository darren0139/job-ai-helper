"""
app.py — Streamlit of the Job AI Helper capstone app.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Streamlit Cloud secrets -> environment variables
# ---------------------------------------------------------------------------
# llm.py reads environment variables when it is imported.
# Therefore, copy st.secrets into os.environ BEFORE importing analyzer.py / llm.py.
try:
    for key in (
        "MODEL",
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
    generate_tailored_resume_copy,
    extract_docx_preview_text,
    convert_docx_to_pdf_if_possible,
    pdf_to_iframe_html,
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
    save_or_update_job_description_for_application,
    get_recent_job_descriptions,
    get_job_description_by_id,
    get_job_description_by_application_id,
    delete_job_description,
    delete_job_description_by_application_id,
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

from report import render_markdown
from llm import ask_text
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
        max_tokens=700,
    ).strip()

    if not answer:
        raise RuntimeError("The AI returned an empty answer.")

    return answer


# ---------------------------------------------------------------------------
# File and report helpers
# ---------------------------------------------------------------------------

def create_markdown_report(report: dict) -> tuple[str, str]:
    """
    Create a Markdown report using the existing report.py renderer.

    Returns:
        markdown_text: The report content as text.
        filename: Suggested filename for download.
    """
    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"match_report_{timestamp}.md"
    md_path = output_dir / filename

    render_markdown(report, out_path=md_path)
    markdown_text = md_path.read_text(encoding="utf-8")

    return markdown_text, filename


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


def run_resume_analysis(resume_text: str, jd_text: str, degree: str) -> dict:
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
    keyword_match = analyse_keyword_match(resume_profile, jd_profile, resume_text)
    progress.progress(50)

    log.write("[5/8] Analysing bullet quality...")
    bullets = analyse_bullets(resume_profile)
    progress.progress(62)

    log.write("[6/8] Auditing jargon...")
    jargon = analyse_jargon(resume_profile, degree, jd_profile)
    progress.progress(75)

    log.write("[7/8] Auditing resume structure...")
    structure = analyse_structure(resume_text)
    progress.progress(87)

    log.write("[8/8] Analysing degree alignment...")
    degree_alignment = analyse_degree_alignment(jd_profile, degree)
    progress.progress(95)

    report = {
        "meta": {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "model": os.getenv("MODEL", "openai/gpt-4o-mini"),
            "degree": degree,
            "ats_pass_threshold": ATS_PASS_THRESHOLD,
        },
        "resume_profile": resume_profile,
        "jd_profile": jd_profile,
        "keyword_match": keyword_match,
        "bullets": bullets,
        "jargon": jargon,
        "structure": structure,
        "degree_alignment": degree_alignment,
    }

    log.write("[Final] Computing overall score and summary...")
    overall_score = compute_overall_score(report)
    report["overall_score"] = overall_score
    report["passes_ats_threshold"] = overall_score >= ATS_PASS_THRESHOLD
    report["summary"] = summarise_overall(report)

    progress.progress(100)

    return report


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

    model_name = os.getenv("MODEL", "openai/gpt-4o-mini")
    st.write("**Model route:**")
    st.code(model_name)

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

                    confirm_col, cancel_col = st.columns(2)

                    with confirm_col:
                        if st.button("Confirm", key=f"confirm_delete_{app_id}", width="stretch"):
                            # Also remove the linked job description from the RAG library.
                            try:
                                linked_jd = get_job_description_by_application_id(app_id)
                                if linked_jd:
                                    delete_job_description_from_chroma(int(linked_jd["id"]))
                                    delete_job_description_by_application_id(app_id)
                            except Exception:
                                # Deleting the application session should still work even if RAG cleanup fails.
                                pass

                            delete_application_session(app_id)

                            if current_application_id == app_id:
                                reset_current_application()

                            st.session_state.pop("pending_delete_application_id", None)
                            st.session_state["flash_message"] = "Session deleted."
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

    save_resume_docx_for_editing = st.checkbox(
        "Save uploaded DOCX so the app can generate an edited resume copy",
        value=False,
        help=(
            "Optional. Only DOCX files can be edited. The app saves a local copy "
            "only when this is ticked. The original saved copy is not overwritten."
        ),
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

                jd_text = validate_jd_text(jd_text_input)
                st.write(f"Read {len(jd_text)} characters from job description.")

                status.update(label="Running AI analysis...", state="running")
                report = run_resume_analysis(resume_text, jd_text, degree)

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

            if save_resume_docx_for_editing:
                if uploaded_resume.name.lower().endswith(".docx"):
                    saved_resume_docx_path = save_uploaded_docx_for_editing(
                        uploaded_resume,
                        application_id=application_id,
                    )
                    st.session_state["saved_resume_docx_path"] = str(saved_resume_docx_path)
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

                jd_library_id = save_or_update_job_description_for_application(
                    application_id=application_id,
                    raw_text=jd_text,
                    jd_profile=jd_profile_for_library,
                    title=jd_profile_for_library.get("job_title", ""),
                    company=jd_profile_for_library.get("company", ""),
                    source_type="application_session",
                    source_url="",
                )

                chunk_count = index_job_description_to_chroma(jd_library_id)
                jd_library_message = f" Indexed JD into Chroma with {chunk_count} chunks."

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

        if passed:
            st.success(f"Score: {overall_score}/100 ({score_label(overall_score)})")
        else:
            st.error(f"Score: {overall_score}/100 ({score_label(overall_score)})")

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
                st.write(item["description"])

                if item.get("period"):
                    st.write("**Period:** " + item["period"])

                if item.get("skills"):
                    st.write("**Skills:** " + ", ".join(item["skills"]))

                if item.get("tools"):
                    st.write("**Tools:** " + ", ".join(item["tools"]))

                if item.get("impact"):
                    st.write("**Impact/scope:** " + item["impact"])

                st.divider()

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
                            "What did you actually do?",
                            value=item.get("description", ""),
                            height=140,
                            key=f"edit_description_{item['id']}",
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

    st.divider()
    st.subheader("Tailor Projects Section")

    current_report = st.session_state.get("latest_report")

    if not current_report:
        st.info("Load or run an application analysis first before tailoring the Projects section.")
    else:
        max_projects = st.slider("Maximum projects", 1, 4, 3)
        max_bullets = st.slider("Maximum bullets per project", 1, 3, 2)

        if st.button("Generate Tailored Projects Section", type="primary", width="stretch"):
            try:
                result = tailor_projects_section(
                    resume_profile=current_report.get("resume_profile", {}),
                    jd_profile=current_report.get("jd_profile", {}),
                    evidence_items=get_evidence_items(limit=100),
                    max_projects=max_projects,
                    max_bullets_per_project=max_bullets,
                )

                fit_estimate = estimate_project_section_length(
                    result,
                    max_projects=max_projects,
                    max_total_bullets=max_projects * max_bullets,
                )

                st.session_state["tailored_projects_result"] = result
                st.session_state["tailored_projects_fit_estimate"] = fit_estimate
                st.rerun()

            except ValueError as exc:
                st.warning(str(exc))
            except RuntimeError as exc:
                st.error(f"LLM/API error: {exc}")
            except Exception as exc:
                st.error(f"Unexpected error while tailoring projects: {exc}")

        result = st.session_state.get("tailored_projects_result")
        fit_estimate = st.session_state.get("tailored_projects_fit_estimate")

        if result:
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

            for project in result.get("recommended_projects", []):
                st.write(f"#### {project.get('title', 'Untitled Project')}")
                st.write(f"**Action:** {project.get('action', '')}")
                st.write(f"**Source:** {project.get('source', '')}")
                st.write(f"**Why relevant:** {project.get('why_relevant', '')}")

                for bullet in project.get("draft_bullets", []):
                    st.markdown(f"- {bullet}")

            with st.expander("Projects to remove or deprioritize"):
                st.json(result.get("projects_to_remove_or_deprioritize", []))

            with st.expander("Unsupported JD skills"):
                st.json(result.get("unsupported_jd_skills", []))

            with st.expander("Full JSON"):
                st.json(result)

    st.divider()
    st.subheader("Tailor Skills Section")

    if not current_report:
        st.info("Load or run an application analysis first before tailoring the Skills section.")
    else:
        if st.button("Generate Tailored Skills Section", width="stretch"):
            try:
                with st.spinner("Generating tailored skills section..."):
                    tailored_skills_result = tailor_skills_section(
                        resume_profile=current_report.get("resume_profile", {}),
                        jd_profile=current_report.get("jd_profile", {}),
                        evidence_items=get_evidence_items(limit=100),
                    )

                st.session_state["tailored_skills_result"] = tailored_skills_result
                st.rerun()

            except ValueError as exc:
                st.warning(str(exc))
            except RuntimeError as exc:
                st.error(f"LLM/API error: {exc}")
            except Exception as exc:
                st.error(f"Unexpected error while tailoring skills: {exc}")

    tailored_skills_result = st.session_state.get("tailored_skills_result")

    if tailored_skills_result:
        st.write("### Recommended Skills Section")
        st.text_area(
            "Preview skills text",
            value=skill_lines_to_plain_text(tailored_skills_result),
            height=160,
        )

        with st.expander("Evidence-supported additions"):
            st.json(tailored_skills_result.get("evidence_supported_additions", []))

        with st.expander("Unsupported JD skills"):
            st.json(tailored_skills_result.get("unsupported_jd_skills", []))
    


    st.divider()
    st.subheader("Generate Edited Resume Copy")

st.caption(
    "This changes only the Skills and Projects sections in a copied DOCX. "
    "Work Experience is not changed."
)

saved_resume_docx_path = st.session_state.get("saved_resume_docx_path")
project_result = st.session_state.get("tailored_projects_result")
skills_result = st.session_state.get("tailored_skills_result")

if not saved_resume_docx_path:
    st.info(
        "No saved DOCX found. Go to Application Sessions, upload a DOCX resume, "
        "tick the save checkbox, and run Analyze Resume again."
    )
elif not project_result:
    st.info("Generate a Tailored Projects Section first.")
elif not skills_result:
    st.info("Generate a Tailored Skills Section first.")
else:
    if st.button("Generate Tailored Resume Copy DOCX", type="primary", width="stretch"):
        try:
            tailored_resume_path = generate_tailored_resume_copy(
                saved_resume_docx_path=saved_resume_docx_path,
                tailored_projects=project_result,
                tailored_skills=skills_result,
                application_id=st.session_state.get("current_application_id"),
                max_projects=max_projects,
                max_bullets_per_project=max_bullets,
            )

            st.session_state["tailored_resume_copy_path"] = str(tailored_resume_path)
            st.success("Tailored resume copy generated.")
            st.rerun()

        except ValueError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(f"Unexpected error while generating tailored resume copy: {exc}")

tailored_resume_copy_path = st.session_state.get("tailored_resume_copy_path")

if tailored_resume_copy_path and Path(tailored_resume_copy_path).exists():
    st.write("### Preview")

    preview_text = extract_docx_preview_text(tailored_resume_copy_path)
    st.text_area("Text preview", value=preview_text, height=360)

    pdf_preview_path = convert_docx_to_pdf_if_possible(tailored_resume_copy_path)

    if pdf_preview_path:
        st.markdown(
            pdf_to_iframe_html(pdf_preview_path, height=800),
            unsafe_allow_html=True,
        )
    else:
        st.caption(
            "PDF visual preview is unavailable because LibreOffice is not installed. "
            "Text preview and DOCX download are still available."
        )

    with open(tailored_resume_copy_path, "rb") as file:
        st.download_button(
            "Download Tailored Resume Copy",
            data=file,
            file_name=Path(tailored_resume_copy_path).name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
        )
