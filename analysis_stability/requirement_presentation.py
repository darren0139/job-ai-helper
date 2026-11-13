"""Shared Job Match publication and presentation helpers."""

from math import isfinite

JOB_MATCH_SCORE = "deterministic_alignment_score"


def _score_withheld(result):
    status = str(result.get("score_publication_status") or "").upper()
    return (result.get("score_publishable") is False
            or status.startswith(("WITHHELD", "UNAVAILABLE", "FAILED", "INCOMPLETE")))


def score_value(result, key=JOB_MATCH_SCORE):
    """Return a published numeric score, including genuine zero."""
    result = result or {}
    if _score_withheld(result):
        return None
    value = result.get(key)
    if type(value) not in (int, float) or not 0 <= value <= 100 or not isfinite(value):
        return None
    return value


def unavailable_score_reason(result):
    result = result or {}
    return (result.get("score_interpretation") or result.get("score_publication_status")
            or "Job Match score unavailable.")


def score_text(value, suffix=""):
    return "Unavailable" if value is None else f"{value}{suffix}"


def saved_overall_score(report):
    """Read the legacy display index without overriding a native score hold."""
    stable = report.get("stable_analysis")
    if isinstance(stable, dict) and score_value(stable) is None:
        return None
    return score_value(report, "overall_score")

def explicitly_unavailable(result):
    """Keep explicit unavailable receipts intact through optional recomputation."""
    return isinstance(result, dict) and (_score_withheld(result)
        or (JOB_MATCH_SCORE in result and score_value(result) is None))


def report_for_score_publication(report):
    """Publish a new receipt without an inconsistent legacy aggregate."""
    stable = report.get("stable_analysis")
    if not isinstance(stable, dict) or score_value(stable) is not None:
        return report
    return {**report, "overall_score": None, "passes_ats_threshold": None,
            "summary": unavailable_score_reason(stable)}
