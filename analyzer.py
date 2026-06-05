"""
analyzer.py — 

Each of the 8 analysis functions calls ask_json() or ask_text() exactly once.
compute_overall_score() makes NO LLM call — it is pure Python arithmetic.

"""

import json

from llm import ask_json, ask_text
from prompts import (
    RESUME_PROFILE_PROMPT,
    JD_PROFILE_PROMPT,
    KEYWORD_MATCH_PROMPT,
    BULLET_QUALITY_PROMPT,
    JARGON_AUDIT_PROMPT,
    STRUCTURE_AUDIT_PROMPT,
    DEGREE_ALIGNMENT_PROMPT,
    OVERALL_SUMMARY_PROMPT,
)


# ---------------------------------------------------------------------------
# Extraction functions 
# ---------------------------------------------------------------------------

def extract_resume_profile(resume_text: str) -> dict:
    """
    Convert plain résumé text to a structured candidate profile dict.

    Calls: ask_json(RESUME_PROFILE_PROMPT, user, max_tokens=2000)
    User message format: "RÉSUMÉ TEXT:\\n\\n{resume_text}"

    Returns:
        Candidate profile dict matching the schema in RESUME_PROFILE_PROMPT.
    """
    user = f"RÉSUMÉ TEXT:\n\n{resume_text}"
    return ask_json(
        RESUME_PROFILE_PROMPT,
        user,
        temperature=0.0,
        max_tokens=2000,
    )



def extract_jd_profile(jd_text: str) -> dict:
    """
    Convert plain job-description text to a structured JD profile dict.

    Calls: ask_json(JD_PROFILE_PROMPT, user, max_tokens=1500)
    User message format: "JOB DESCRIPTION TEXT:\\n\\n{jd_text}"

    Returns:
        JD profile dict matching the schema in JD_PROFILE_PROMPT.
    """
    user = f"JOB DESCRIPTION TEXT:\n\n{jd_text}"
    return ask_json(
        JD_PROFILE_PROMPT,
        user,
        temperature=0.0,
        max_tokens=1500,
    )


# ---------------------------------------------------------------------------
# Evaluation functions 
# ---------------------------------------------------------------------------

def analyse_keyword_match(
    resume_profile: dict,
    jd_profile: dict,
    resume_text: str = "",
) -> dict:
    """
    Compare résumé keywords against JD requirements.

    Uses both the structured résumé profile and the raw résumé text.
    The raw text is useful because the extraction step may omit some keywords.
    """
    user = (
        f"RÉSUMÉ RAW TEXT:\n{resume_text}\n\n"
        f"RÉSUMÉ PROFILE:\n{_dump(resume_profile)}"
        f"\n\nJD PROFILE:\n{_dump(jd_profile)}"
    )

    return ask_json(
        KEYWORD_MATCH_PROMPT,
        user,
        temperature=0.2,
        max_tokens=3000,
    )



def analyse_bullets(resume_profile: dict) -> dict:
    """
    Score every bullet in the résumé against the Action→Technology→Impact rubric.

    Calls: ask_json(BULLET_QUALITY_PROMPT, user, max_tokens=3000)
    User message format: "RÉSUMÉ PROFILE:\\n{json_dump}"

    Returns:
        Bullet quality dict with keys: bullets, bullet_quality_avg.
    """
    user = f"RÉSUMÉ PROFILE:\n{_dump(resume_profile)}"
    return ask_json(
        BULLET_QUALITY_PROMPT,
        user,
        temperature=0.2,
        max_tokens=3000,
    )


def analyse_jargon(
    resume_profile: dict,
    degree_program: str,
    jd_profile: dict,
) -> dict:
    """
    Detect game-dev jargon in résumé bullets and flag suggested translations.

    Calls: ask_json(JARGON_AUDIT_PROMPT, user, max_tokens=1500)
    User message format:
        "DEGREE PROGRAM: {degree_program}\\n\\n"
        "RÉSUMÉ PROFILE:\\n{json_dump}\\n\\n"
        "JD PROFILE:\\n{json_dump}"

    Args:
        resume_profile: Output of extract_resume_profile().
        degree_program: One of "RTIS", "IMGD", "UXGD", "BFA".
        jd_profile: Output of extract_jd_profile().

    Returns:
        Jargon audit dict with keys: flags, jargon_score.
    """
    user = (
        f"DEGREE PROGRAM: {degree_program}\n\n"
        f"RÉSUMÉ PROFILE:\n{_dump(resume_profile)}\n\n"
        f"JD PROFILE:\n{_dump(jd_profile)}"
    )
    return ask_json(
        JARGON_AUDIT_PROMPT,
        user,
        temperature=0.2,
        max_tokens=1500,
    )


def analyse_structure(resume_text: str) -> dict:
    """
    Audit Three-Thirds layout compliance and ATS formatting.

    Calls: ask_json(STRUCTURE_AUDIT_PROMPT, user, temperature=0.0, max_tokens=1500)
    User message format: "RÉSUMÉ TEXT:\\n\\n{resume_text}"

    Returns:
        Structure audit dict with keys: three_thirds, ats_red_flags, structure_score, etc.
    """
    user = f"RÉSUMÉ TEXT:\n\n{resume_text}"
    return ask_json(
        STRUCTURE_AUDIT_PROMPT,
        user,
        temperature=0.0,
        max_tokens=1500,
    )


def _dump(data: dict) -> str:
    """Convert a Python dict to nicely formatted JSON text for the LLM user message."""
    return json.dumps(data, indent=2, ensure_ascii=False)

def analyse_degree_alignment(jd_profile: dict, degree_program: str) -> dict:
    """
    Assess how well the JD's job title fits the student's degree programme.

    Calls: ask_json(DEGREE_ALIGNMENT_PROMPT, user, max_tokens=600)
    User message format:
        "DEGREE PROGRAM: {degree_program}\\n\\nJD PROFILE:\\n{json_dump}"

    Args:
        jd_profile: Output of extract_jd_profile().
        degree_program: One of "RTIS", "IMGD", "UXGD", "BFA".

    Returns:
        Degree alignment dict with keys: degree_alignment_score, fit_commentary, etc.
    """
    user = (
        f"DEGREE PROGRAM: {degree_program}\n\n"
        f"JD PROFILE:\n{_dump(jd_profile)}"
    )
    return ask_json(
        DEGREE_ALIGNMENT_PROMPT,
        user,
        temperature=0.2,
        max_tokens=600,
    )


def summarise_overall(report: dict) -> str:
    """
    Generate a 3-bullet plain Markdown executive summary of the full report.

    NOTE: uses ask_text(), not ask_json() — returns a plain string, not a dict.

    Calls: ask_text(OVERALL_SUMMARY_PROMPT, user, max_tokens=400)
    User message format: "ANALYSIS REPORT:\\n{json_dump}"

    Only send the fields the summary needs — omit the raw résumé text to save tokens.
    Keys to include: overall_score, passes_ats_threshold, keyword_match, bullets,
    jargon, structure, degree_alignment.

    Returns:
        Plain Markdown string (3 bullet points).
    """
    # Hint: build a summary_input dict with only the fields listed above,
    # then call ask_text(OVERALL_SUMMARY_PROMPT, f"ANALYSIS REPORT:\n{json.dumps(summary_input, indent=2)}", max_tokens=400)
    summary_input = {
        "overall_score": report.get("overall_score", 0),
        "passes_ats_threshold": report.get("passes_ats_threshold", False),
        "keyword_match": report.get("keyword_match", {}),
        "bullets": report.get("bullets", {}),
        "jargon": report.get("jargon", {}),
        "structure": report.get("structure", {}),
        "degree_alignment": report.get("degree_alignment", {}),
    }

    user = f"ANALYSIS REPORT:\n{json.dumps(summary_input, indent=2, ensure_ascii=False)}"

    return ask_text(
        OVERALL_SUMMARY_PROMPT,
        user,
        temperature=0.3,
        max_tokens=400,
    )


# ---------------------------------------------------------------------------
# Score aggregation 
# ---------------------------------------------------------------------------

def _safe_number(value: object) -> float:
    """Convert a score-like value to float; return 0 if missing or invalid."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp_score(score: float) -> float:
    """Keep sub-scores within the 0-100 range."""
    return max(0.0, min(100.0, score))



def compute_overall_score(report: dict) -> int:
    """
    Compute the weighted composite score from sub-scores already in report.

    This function makes NO LLM call. It is pure Python arithmetic.

    Weights:
        keyword_match_score    40%  (report["keyword_match"]["keyword_match_score"])
        bullet_quality_avg     25%  (report["bullets"]["bullet_quality_avg"])
        structure_score        15%  (report["structure"]["structure_score"])
        jargon_score           10%  (report["jargon"]["jargon_score"])
        degree_alignment_score 10%  (report["degree_alignment"]["degree_alignment_score"])

    Returns:
        int — weighted average, rounded to the nearest whole number.
    """

    # Hint: read each sub-score with .get("field", 0) to handle missing data safely.
    keyword_score = _clamp_score(
        _safe_number(report.get("keyword_match", {}).get("keyword_match_score", 0))
    )
    bullet_score = _clamp_score(
        _safe_number(report.get("bullets", {}).get("bullet_quality_avg", 0))
    )
    structure_score = _clamp_score(
        _safe_number(report.get("structure", {}).get("structure_score", 0))
    )
    jargon_score = _clamp_score(
        _safe_number(report.get("jargon", {}).get("jargon_score", 0))
    )
    degree_score = _clamp_score(
        _safe_number(report.get("degree_alignment", {}).get("degree_alignment_score", 0))
    )

    total = (
        keyword_score * 0.40
        + bullet_score * 0.25
        + structure_score * 0.15
        + jargon_score * 0.10
        + degree_score * 0.10
    )

    return int(round(total))
