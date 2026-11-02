"""Read-only, fail-closed identity diagnostics for document receipts.

No authority re-sealing, database writes or scoring.
"""
from __future__ import annotations


def compare_receipt_identity(saved: dict, current: dict) -> dict:
    """Expose differing identity FIELD NAMES only (no hashes or input text)."""
    if not isinstance(saved, dict) or not isinstance(current, dict) or not saved or not current:
        return {"status": "unavailable", "mismatched_fields": [], "missing_fields": []}
    missing = sorted(k for k in set(saved) | set(current)
                     if k not in saved or k not in current or not saved.get(k) or not current.get(k))
    mismatched = sorted(k for k in set(saved) & set(current)
                        if k not in missing and saved[k] != current[k])
    status = "incomplete" if missing else "current" if not mismatched else (
        "taxonomy_changed" if mismatched == ["taxonomy_fingerprint"] else "identity_changed"
    )
    return {"status": status, "mismatched_fields": mismatched, "missing_fields": missing}


def receipt_refresh_guidance(comparison: dict) -> str:
    """Actionable message; never says that stale receipts are current."""
    if comparison.get("status") == "taxonomy_changed":
        return (
            "The saved résumé/JD analysis is internally valid, but the taxonomy knowledge "
            "fingerprint has changed since it was created. Re-open this application's "
            "'Replace résumé or job description' panel, supply the same source résumé "
            "and exact JD, select Force fresh AI analysis, then run Analyze Resume to create a current "
            "analysis before continuing. Historical receipts are retained. "
            "Do not reset or manually alter the frozen receipt."
        )
    return (
        "The saved document analysis does not match the current JD, requirement scope, "
        "or analysis identity. Review the diagnostic field names, restore the intended "
        "source résumé and exact JD, select Force fresh AI analysis, and run Analyze Resume explicitly before binding. "
        "Historical receipts must not be relabeled as current."
    )
