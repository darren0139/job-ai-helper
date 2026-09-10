"""Pure helpers for handing browser JD captures into Phase 9F Tailor Resume."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


BROWSER_CAPTURE_SOURCE_LABEL = "Choose browser capture"
TAILOR_RESUME_PAGE = "Tailor Resume"

_TRANSIENT_PHASE9F_KEYS = (
    "phase9f_jd_analysis",
    "phase9f_jd_analysis_input_fingerprint",
    "phase9f_jd_save_receipt",
)


def browser_capture_to_phase9f_input(capture: dict[str, Any]) -> dict[str, str]:
    if not isinstance(capture, dict) or not capture:
        raise ValueError("A browser JD capture is required.")

    raw_text = str(capture.get("jd_text") or "").strip()
    if not raw_text:
        raise ValueError("The browser capture has no clean JD text.")

    return {
        "raw_text": raw_text,
        "title": str(capture.get("job_title") or "").strip(),
        "company": str(capture.get("company") or "").strip(),
        "location": str(capture.get("location") or "").strip(),
        "source_url": str(capture.get("source_url") or "").strip(),
        "source_artifact_sha256": str(capture.get("capture_hash") or "").strip(),
    }


def apply_browser_capture_tailor_resume_handoff(
    session_state: MutableMapping[str, Any],
    capture_id: int,
) -> None:
    """Select one capture and navigate to Tailor Resume on the next rerun."""
    resolved_id = int(capture_id)
    if resolved_id <= 0:
        raise ValueError("Browser capture ID must be positive.")

    for key in _TRANSIENT_PHASE9F_KEYS:
        session_state.pop(key, None)

    session_state["phase9f_jd_source_mode"] = BROWSER_CAPTURE_SOURCE_LABEL
    session_state["phase9f_browser_capture_id"] = resolved_id
    session_state["phase9f_jd_intake_state"] = "jd_entered"
    session_state["navigation_page"] = TAILOR_RESUME_PAGE
