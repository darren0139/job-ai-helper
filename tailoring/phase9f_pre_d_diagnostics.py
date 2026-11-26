"""Diagnostic-only comparison of PRE-D inputs; no persistence or model calls."""
from __future__ import annotations
from copy import deepcopy
from tailoring.phase9e_blueprint_selection import fingerprint_value


def _compare(left, right, fields):
    return {key: {"analyzed": deepcopy(left.get(key)),
                  "persisted": deepcopy(right.get(key)),
                  "equal": left.get(key) == right.get(key)}
            for key in fields}


def _profile_diff(left, right):
    left = left if isinstance(left, dict) else {}
    right = right if isinstance(right, dict) else {}
    return {key: {"left_present": key in left, "right_present": key in right,
                  "left": deepcopy(left.get(key)), "right": deepcopy(right.get(key))}
            for key in sorted(set(left) | set(right))
            if key not in left or key not in right or left[key] != right[key]}


def build_pre_d_mismatch_diagnostics(analyzed, exact, persisted, receipt):
    """Compare JD-only data. No resume, credentials, URLs or call ledgers."""
    a = analyzed.get("jd_profile") or {}
    e = exact.get("jd_profile") or {}
    p = persisted.get("jd_profile") or {}
    fields = ("raw_jd_sha256", "canonical_requirement_fingerprint",
              "structured_profile_fingerprint", "canonical_jd_id",
              "source_version_id", "job_title", "company", "location")
    comparisons = _compare(analyzed, persisted, fields)
    # These three predicates mirror the existing guard, including its whitespace
    # normalization for the two fingerprints. Do not use this report to authorize D.
    def clean(value):
        return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()
    failed = [key for key in ("raw_jd_sha256", "canonical_requirement_fingerprint")
              if clean(analyzed.get(key)) != clean(persisted.get(key))]
    if analyzed.get("jd_profile") != persisted.get("jd_profile"):
        failed.append("jd_profile")
    ai = set(analyzed.get("canonical_requirement_ids") or [])
    pi = set(persisted.get("canonical_requirement_ids") or [])
    return {
        "format_version": "phase9f-pre-d-mismatch-diagnostics-v1",
        "error_code": "pre_d_exact_jd_mismatch",
        "confirmation_blocked": True,
        "failed_guard_fields": failed,
        "analyzed_snapshot_fingerprint": analyzed.get("snapshot_fingerprint"),
        "analyzed_source_type": analyzed.get("source_type"),
        "analyzed_reused_exact_saved_version": bool(analyzed.get("reused_exact_saved_version")),
        "library": {
            "analyzed_library_jd_id": analyzed.get("library_jd_id"),
            "persisted_library_jd_id": persisted.get("library_jd_id"),
            "source_version_id": exact.get("source_version_id"),
            "created_new_job": bool(receipt.get("created_new_job")),
            "created_new_version": bool(receipt.get("created_new_version")),
            "existing_version_reused": not bool(receipt.get("created_new_job") or receipt.get("created_new_version")),
            "chroma_indexing_occurred": bool(receipt.get("chroma_indexing_occurred")),
        },
        "analyzed_vs_rebuilt": comparisons,
        "stored_exact": {"raw_jd_sha256": exact.get("raw_jd_sha256"),
                         "canonical_requirement_fingerprint": exact.get("canonical_requirement_fingerprint"),
                         "structured_profile_fingerprint": fingerprint_value(e),
                         "canonical_jd_id": exact.get("canonical_jd_id"),
                         "title": exact.get("title"), "company": exact.get("company"),
                         "location": exact.get("location")},
        "profile_differences": {
            "analyzed_vs_stored": _profile_diff(a, e),
            "stored_vs_rebuilt": _profile_diff(e, p),
            "analyzed_vs_rebuilt": _profile_diff(a, p),
        },
        "requirement_ids": {"analyzed_count": len(ai), "rebuilt_count": len(pi),
                            "only_analyzed": sorted(ai-pi), "only_rebuilt": sorted(pi-ai)},
    }
