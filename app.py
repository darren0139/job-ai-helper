"""
app.py — Streamlit web version of the Job AI Helper capstone app.

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


from parse import read_resume_pdf, read_resume_docx, _MIN_JD_CHARS
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
    get_recent_applications,
    get_application_by_id,
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


# ---------------------------------------------------------------------------
# Streamlit app
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Job AI Helper",
    page_icon="📄",
    layout="wide",
)

init_db()
init_session_state()

st.title("📄 Job AI Helper")
st.caption("Analyze resume-job fit, save application sessions, and generate tailored cover letters.")

flash_message = st.session_state.pop("flash_message", "")
if flash_message:
    st.success(flash_message)


with st.sidebar:
    st.header("Settings")

    degree = st.selectbox(
        "Degree programme",
        VALID_DEGREES,
        index=VALID_DEGREES.index("IMGD"),
        help="Used for the degree-alignment score.",
    )

    model_name = os.getenv("MODEL", "openai/gpt-4o-mini")
    st.write("**Model route:**")
    st.code(model_name)

    show_debug_text = st.checkbox(
        "Show debug resume text",
        value=False,
        help="Shows extracted resume text after upload. Useful for checking PDF/DOCX parsing.",
    )

    st.divider()

    if st.button("➕ New Application Session", use_container_width=True):
        application_id = create_empty_application_session(degree=degree)

        reset_current_application()
        st.session_state["current_application_id"] = application_id
        st.session_state["flash_message"] = (
            f"Started new application session #{application_id}. "
            "Upload a resume and paste a job description."
        )

        st.rerun()

    st.write("**How to use**")
    st.write("1. Click **New Application Session** to start a blank session.")
    st.write("2. Upload a PDF or DOCX resume.")
    st.write("3. Paste the target job description.")
    st.write("4. Click **Analyze Resume**.")
    st.write("5. Optionally generate or revise a cover letter.")

    st.divider()
    st.subheader("Application Sessions")

    recent_applications = get_recent_applications(limit=15)
    current_application_id = st.session_state.get("current_application_id")

    if not recent_applications:
        st.caption("No application sessions yet.")
    else:
        for app_id, session_name, job_title, company, score, has_report, updated_at in recent_applications:
            is_current = current_application_id == app_id

            if has_report:
                clean_title = job_title or session_name or f"Application #{app_id}"
                clean_company = company or "Unknown Company"

                if score is None:
                    base_label = f"{clean_title} @ {clean_company}"
                else:
                    base_label = f"{clean_title} @ {clean_company} — {score}/100"

                label = f"✅ {base_label}" if is_current else f"📄 {base_label}"
            else:
                draft_name = session_name or f"Application #{app_id}"
                label = f"✅ {draft_name} (Draft)" if is_current else f"📝 {draft_name} (Draft)"

            if st.button(label, key=f"load_app_{app_id}", use_container_width=True):
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
                    st.session_state["flash_message"] = f"Loaded application session #{app_id}."
                    st.rerun()


input_suffix = st.session_state["input_reset_counter"]

uploaded_resume = st.file_uploader(
    "Upload resume",
    type=["pdf", "docx"],
    key=f"resume_upload_{input_suffix}",
    help="Upload a text-based PDF or DOCX resume. Scanned PDFs may not parse correctly.",
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

analyze_clicked = st.button("Analyze Resume", type="primary", use_container_width=True)


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
            # If the user started or loaded a session, update that session with the analysis result.
            update_application_report(
                application_id=application_id,
                resume_filename=uploaded_resume.name,
                report=report,
            )

        st.session_state["latest_report"] = report
        st.session_state["resume_filename"] = uploaded_resume.name
        st.session_state["current_application_id"] = application_id

        # Clear old generated content when a new resume/job is analysed.
        st.session_state.pop("cover_letter", None)
        st.session_state["revision_history"] = []
        st.session_state["analysis_chat"] = []

        st.session_state["flash_message"] = f"Saved application session #{application_id}."
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
        if present:
            st.dataframe(present, use_container_width=True)
        else:
            st.info("No present keywords returned.")

        st.write("### Missing Keywords")
        missing = report.get("keyword_match", {}).get("missing", [])
        if missing:
            st.dataframe(missing, use_container_width=True)
        else:
            st.success("No missing keywords returned.")

    with tab_bullets:
        st.write("### Bullet Quality Audit")
        bullet_rows = report.get("bullets", {}).get("bullets", [])
        if bullet_rows:
            st.dataframe(bullet_rows, use_container_width=True)
        else:
            st.info("No bullet audit rows returned.")

    with tab_structure:
        st.write("### Three-Thirds / ATS Structure")
        st.json(report.get("structure", {}))

    with tab_jargon:
        st.write("### Jargon Flags")
        flags = report.get("jargon", {}).get("flags", [])
        if flags:
            st.dataframe(flags, use_container_width=True)
        else:
            st.success("No jargon flags returned.")

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
            use_container_width=True,
        )

    with download_col2:
        st.download_button(
            "Download Markdown Report",
            data=markdown_text,
            file_name=markdown_filename,
            mime="text/markdown",
            use_container_width=True,
        )

    st.divider()
    st.header("Tailored Cover Letter")

    if st.button("Generate Cover Letter", type="primary", use_container_width=True):
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
            use_container_width=True,
        )

        st.subheader("Ask for a revision")

        revision_request = st.text_input(
            "Revision request",
            placeholder="Example: Make it shorter and more confident.",
        )

        if st.button("Revise Cover Letter", use_container_width=True):
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

    analysis_question = st.text_input(
        "Ask a question about the analysis",
        placeholder="Example: What should I improve first?",
    )

    if st.button("Ask AI About Analysis", use_container_width=True):
        try:
            with st.spinner("Answering question..."):
                answer = answer_analysis_question(report, analysis_question)

            st.session_state.setdefault("analysis_chat", []).append(
                {"question": analysis_question, "answer": answer}
            )

        except ValueError as exc:
            st.warning(str(exc))

        except RuntimeError as exc:
            st.error(f"LLM/API error: {exc}")

        except Exception as exc:
            st.error(f"Unexpected error while answering question: {exc}")

    for item in st.session_state.get("analysis_chat", []):
        st.markdown(f"**You:** {item['question']}")
        st.markdown(f"**AI:** {item['answer']}")

elif current_application_id is not None:
    st.info(
        f"Application session #{current_application_id} is open. "
        "Upload a resume, paste a job description, then click **Analyze Resume**."
    )
else:
    st.info("Click **New Application Session**, or upload a resume and paste a job description to begin.")
