from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


TAILOR_RESUME_PAGE = "Tailor Resume"
TAILOR_RESUME_SOURCE_LABEL = "Paste job description"

_TRANSIENT_PHASE9F_KEYS = (
    "phase9f_jd_analysis",
    "phase9f_jd_analysis_input_fingerprint",
    "phase9f_jd_save_receipt",
    "phase9f_b_ranking_result",
    "phase9f_d_confirmation_receipt",
    "phase9f_jd_preferred_requirements",
)


def apply_job_finder_tailor_resume_handoff(
    session_state: MutableMapping[str, Any],
    *,
    application_id: int,
    job: dict[str, Any],
) -> None:
    """Prefill the existing manual Phase 9F Tailor Resume intake from Job Finder."""
    resolved_id = int(application_id)
    if resolved_id <= 0:
        raise ValueError("Application ID must be positive.")
    if not isinstance(job, dict):
        raise ValueError("A Job Finder job is required.")

    raw_text = str(job.get("description") or "").strip()
    if not raw_text:
        raise ValueError("The Job Finder job has no normalized JD text.")

    for key in _TRANSIENT_PHASE9F_KEYS:
        session_state.pop(key, None)

    session_state["current_application_id"] = resolved_id
    session_state["phase9f_jd_source_mode"] = TAILOR_RESUME_SOURCE_LABEL
    session_state["phase9f_pasted_jd_text"] = raw_text
    session_state["phase9f_jd_company"] = str(job.get("company") or "").strip()
    session_state["phase9f_jd_title"] = str(job.get("title") or "").strip()
    session_state["phase9f_jd_location"] = str(job.get("location") or "").strip()
    session_state["phase9f_jd_source_url"] = str(
        job.get("source_url") or job.get("apply_url") or ""
    ).strip()
    session_state["phase9f_jd_intake_state"] = "jd_entered"
    session_state["_pending_navigation_page"] = TAILOR_RESUME_PAGE
