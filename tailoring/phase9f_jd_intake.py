"""Phase 9F-A transient exact-JD intake and identity helpers."""

from __future__ import annotations

import hashlib
import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from analysis_stability.stable_evidence_scoring import canonicalise_requirements
from llm import summarise_call_usage
from parse import _MIN_JD_CHARS, read_resume_docx, read_resume_pdf
from rag.jd_identity import build_job_identity, source_version_id
from tailoring.jd_user_input_overrides import (
    build_effective_application_local_requirement_scope,
    normalise_requirement_override_lines,
    preferred_requirement_override_cache_identity,
)
from tailoring.phase9b_role_family import suggest_role_family


PHASE9F_JD_INTAKE_VERSION = "phase9f-jd-intake-v1"
PHASE9F_JD_INTAKE_IDENTITY_POLICY_VERSION = (
    "phase9f-transient-exact-jd-identity-v1"
)
JD_EXTRACTION_POLICY_VERSION = "existing-jd-extraction-and-review-v1"
PHASE9F_JD_DIAGNOSTICS_VERSION = "phase9f-jd-intake-diagnostics-v3"


class Phase9FJDIntakeError(ValueError):
    """Raised when a transient JD cannot be reproduced safely."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def fingerprint_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def validate_jd_text(raw_text: Any) -> str:
    text = str(raw_text or "").strip()
    if len(text) < _MIN_JD_CHARS:
        raise Phase9FJDIntakeError(
            f"Job description text is too short ({len(text)} chars). "
            f"Expected at least {_MIN_JD_CHARS} characters."
        )
    return text


def extract_job_description_file(*, filename: str, content: bytes) -> str:
    """Extract PDF/DOCX text locally through the existing document parsers."""
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise Phase9FJDIntakeError(
            "Only PDF and DOCX job-description files are supported."
        )
    if not isinstance(content, bytes) or not content:
        raise Phase9FJDIntakeError("The uploaded job-description file is empty.")

    with tempfile.TemporaryDirectory(prefix="phase9f_jd_") as temp_name:
        path = Path(temp_name) / f"uploaded{suffix}"
        path.write_bytes(content)
        try:
            text = (
                read_resume_pdf(str(path))
                if suffix == ".pdf"
                else read_resume_docx(str(path))
            )
        except ValueError as exc:
            raise Phase9FJDIntakeError(
                f"Could not extract readable JD text: {exc}"
            ) from exc
    return validate_jd_text(text)


def phase9f_jd_input_fingerprint(
    *,
    source_type: str,
    raw_text: str = "",
    title: str = "",
    company: str = "",
    location: str = "",
    library_jd_id: int | None = None,
    source_version_id_value: str = "",
    source_artifact_sha256: str = "",
    extraction_model_id: str = "",
    preferred_requirements: str | list[str] | tuple[str, ...] | None = None,
) -> str:
    """Identify semantic intake input; display-only source URL is excluded."""
    payload = {
            "version": PHASE9F_JD_INTAKE_IDENTITY_POLICY_VERSION,
            "source_type": _clean(source_type),
            "raw_jd_sha256": hashlib.sha256(
                str(raw_text or "").strip().encode("utf-8")
            ).hexdigest(),
            "title_override": _clean(title),
            "company_override": _clean(company),
            "location_override": _clean(location),
            "library_jd_id": int(library_jd_id or 0),
            "source_version_id": _clean(source_version_id_value),
            "source_artifact_sha256": _clean(source_artifact_sha256),
            "extraction_policy_version": JD_EXTRACTION_POLICY_VERSION,
            "extraction_model_id": _clean(extraction_model_id),
    }
    override_identity = preferred_requirement_override_cache_identity(
        preferred_requirements
    )
    if override_identity["preferred_requirement_override_keys"]:
        payload["jd_user_override_identity"] = override_identity
    return fingerprint_value(payload)


def _canonical_scope(
    *,
    jd_profile: dict[str, Any],
    raw_text: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    canonical = canonicalise_requirements(
        jd_profile=deepcopy(jd_profile),
        raw_jd_text=raw_text,
    )
    rows = [
        dict(row)
        for row in canonical.get("requirements", []) or []
        if isinstance(row, dict)
    ]
    if not rows:
        raise Phase9FJDIntakeError(
            "The JD analysis produced no canonical requirements."
        )
    compact = [
        {
            "requirement_id": _clean(row.get("requirement_id")),
            "text": _clean(row.get("text")),
            "importance": _clean(row.get("importance")),
            "atomic_group_id": _clean(row.get("atomic_group_id")),
            "group_weight_fraction": row.get("group_weight_fraction"),
        }
        for row in rows
    ]
    return canonical, rows, fingerprint_value(compact)


def build_transient_exact_jd_snapshot(
    *,
    raw_text: str,
    jd_profile: dict[str, Any],
    source_type: str,
    title: str = "",
    company: str = "",
    location: str = "",
    source_url: str = "",
    source_filename: str = "",
    source_artifact_sha256: str = "",
    library_jd_id: int | None = None,
    saved_source_version_id: str = "",
    extraction_model_id: str = "",
    model_calls: list[dict[str, Any]] | None = None,
    extraction_method_override: str = "",
    preferred_requirements: str | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Build one deterministic transient snapshot without persistence."""
    text = validate_jd_text(raw_text)
    if source_type not in {"pasted", "uploaded", "saved"}:
        raise Phase9FJDIntakeError("Invalid Phase 9F JD source type.")
    if not isinstance(jd_profile, dict) or not jd_profile:
        raise Phase9FJDIntakeError(
            "The structured job-description profile is missing."
        )

    profile = deepcopy(jd_profile)
    overrides = {
        "job_title": _clean(title),
        "company": _clean(company),
        "location": _clean(location),
    }
    for field, value in overrides.items():
        if value:
            profile[field] = value

    final_title = _clean(profile.get("job_title") or profile.get("title"))
    final_company = _clean(
        profile.get("company") or profile.get("company_name")
    )
    final_location = _clean(profile.get("location"))
    if final_title:
        profile["job_title"] = final_title
    if final_company:
        profile["company"] = final_company
    if final_location:
        profile["location"] = final_location

    canonical, base_requirements, _base_requirement_fingerprint = _canonical_scope(
        jd_profile=profile,
        raw_text=text,
    )
    requirements, user_inputs = build_effective_application_local_requirement_scope(
        base_requirements,
        preferred_requirements,
    )
    canonical["requirements"] = deepcopy(requirements)
    compact = [
        {
            "requirement_id": _clean(row.get("requirement_id")),
            "text": _clean(row.get("text")),
            "importance": _clean(row.get("importance")),
            "atomic_group_id": _clean(row.get("atomic_group_id")),
            "group_weight_fraction": row.get("group_weight_fraction"),
        }
        for row in requirements
    ]
    requirement_fingerprint = fingerprint_value(compact)
    raw_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    calculated_source_version = source_version_id(text)
    if saved_source_version_id and (
        calculated_source_version != _clean(saved_source_version_id)
    ):
        raise Phase9FJDIntakeError(
            "The saved JD source-version identity does not match its raw text."
        )

    canonical_jd_id = ""
    if final_title and final_company:
        canonical_jd_id = build_job_identity(
            company=final_company,
            title=final_title,
            location=final_location,
            raw_jd_text=text,
        ).canonical_jd_id

    role_family = suggest_role_family({"jd_profile": deepcopy(profile)})
    calls = [dict(call) for call in model_calls or [] if isinstance(call, dict)]
    extraction_method = _clean(extraction_method_override) or (
        "stored_exact_version_profile"
        if source_type == "saved"
        else "existing_jd_extraction_and_review"
    )
    reused_exact_saved_version = extraction_method in {
        "stored_exact_version_profile",
        "stored_exact_version_profile_reuse",
    }
    semantic_identity = {
        "format_version": PHASE9F_JD_INTAKE_VERSION,
        "identity_policy_version": PHASE9F_JD_INTAKE_IDENTITY_POLICY_VERSION,
        "source": {
            "source_type": source_type,
            "library_jd_id": int(library_jd_id or 0),
            "source_version_id": calculated_source_version,
            "source_artifact_sha256": _clean(source_artifact_sha256),
        },
        "raw_jd_sha256": raw_hash,
        "structured_profile_fingerprint": fingerprint_value(profile),
        "canonical_jd_id": canonical_jd_id,
        "canonical_requirement_fingerprint": requirement_fingerprint,
        "canonical_requirement_ids": sorted(
            _clean(row.get("requirement_id"))
            for row in requirements
            if _clean(row.get("requirement_id"))
        ),
        "extraction": {
            "policy_version": JD_EXTRACTION_POLICY_VERSION,
            "method": extraction_method,
            "model_id": _clean(extraction_model_id),
        },
        "role_family": {
            "classifier_version": _clean(
                role_family.get("suggestion_method")
            ),
            "role_family_id": _clean(role_family.get("role_family_id")),
            "role_family_label": _clean(role_family.get("role_family")),
            "confidence": _clean(role_family.get("confidence")),
            "matched_terms": list(role_family.get("matched_terms") or []),
        },
    }
    if user_inputs["preferred_requirement_overrides"]:
        semantic_identity["application_local_jd_user_inputs"] = deepcopy(
            user_inputs
        )
    snapshot_fingerprint = fingerprint_value(semantic_identity)
    return {
        "format_version": PHASE9F_JD_INTAKE_VERSION,
        "identity_policy_version": PHASE9F_JD_INTAKE_IDENTITY_POLICY_VERSION,
        "snapshot_fingerprint": snapshot_fingerprint,
        "semantic_identity": semantic_identity,
        "source_type": source_type,
        "source_filename": _clean(source_filename),
        "source_artifact_sha256": _clean(source_artifact_sha256),
        "source_url": str(source_url or "").strip(),
        "library_jd_id": int(library_jd_id or 0),
        "raw_text": text,
        "raw_jd_sha256": raw_hash,
        "jd_profile": profile,
        "structured_profile_fingerprint": fingerprint_value(profile),
        "job_title": final_title,
        "company": final_company,
        "location": final_location,
        "experience_level": _clean(profile.get("experience_level")),
        "responsibilities": list(profile.get("responsibilities") or []),
        "required_skills": list(profile.get("required_skills") or []),
        "preferred_skills": list(profile.get("preferred_skills") or []),
        "tools_technologies": list(profile.get("tools_technologies") or []),
        "canonical_jd_id": canonical_jd_id,
        "source_version_id": calculated_source_version,
        "canonical_requirements": requirements,
        "canonical_requirement_ids": semantic_identity[
            "canonical_requirement_ids"
        ],
        "canonical_requirement_fingerprint": requirement_fingerprint,
        "canonicalisation": canonical,
        "application_local_jd_user_inputs": deepcopy(user_inputs),
        "role_family": role_family,
        "extraction_provenance": {
            "policy_version": JD_EXTRACTION_POLICY_VERSION,
            "method": extraction_method,
            "model_id": _clean(extraction_model_id),
            "model_call_count": len(calls),
            "embedding_call_count": 0,
            "model_calls": calls,
        },
        "model_call_count": len(calls),
        "embedding_call_count": 0,
        "reused_exact_saved_version": reused_exact_saved_version,
    }


def build_saved_exact_jd_snapshot(
    saved: dict[str, Any],
    *,
    preferred_requirements: str | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Rebuild a transient snapshot from one verified authoritative version."""
    snapshot = build_transient_exact_jd_snapshot(
        raw_text=str(saved.get("raw_text") or ""),
        jd_profile=deepcopy(saved.get("jd_profile") or {}),
        source_type="saved",
        source_url=str(saved.get("source_url") or ""),
        library_jd_id=int(saved.get("library_jd_id") or 0),
        saved_source_version_id=str(saved.get("source_version_id") or ""),
        model_calls=[],
        preferred_requirements=preferred_requirements,
    )
    for field in (
        "canonical_jd_id",
        "raw_jd_sha256",
    ):
        if _clean(snapshot.get(field)) != _clean(saved.get(field)):
            raise Phase9FJDIntakeError(
                f"The saved JD exact-version {field} is internally inconsistent."
            )
    if not normalise_requirement_override_lines(preferred_requirements):
        if _clean(snapshot.get("canonical_requirement_fingerprint")) != _clean(
            saved.get("canonical_requirement_fingerprint")
        ):
            raise Phase9FJDIntakeError(
                "The saved JD canonical requirements are internally inconsistent."
            )
        if snapshot["canonical_requirement_ids"] != sorted(
            str(value) for value in saved.get("canonical_requirement_ids") or []
        ):
            raise Phase9FJDIntakeError(
                "The saved JD canonical requirement IDs are internally inconsistent."
            )
    return snapshot


def build_reused_exact_jd_snapshot(
    saved: dict[str, Any],
    *,
    source_type: str,
    title: str = "",
    company: str = "",
    location: str = "",
    source_url: str = "",
    source_filename: str = "",
    source_artifact_sha256: str = "",
    preferred_requirements: str | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Reuse one exact saved JD profile for pasted/uploaded intake at zero LLM cost."""
    if source_type not in {"pasted", "uploaded"}:
        raise Phase9FJDIntakeError(
            "Exact saved-analysis reuse is only valid for pasted/uploaded intake."
        )
    if not isinstance(saved, dict) or not saved:
        raise Phase9FJDIntakeError(
            "An exact saved JD version is required for analysis reuse."
        )

    snapshot = build_transient_exact_jd_snapshot(
        raw_text=str(saved.get("raw_text") or ""),
        jd_profile=deepcopy(saved.get("jd_profile") or {}),
        source_type=source_type,
        title=title,
        company=company,
        location=location,
        source_url=source_url,
        source_filename=source_filename,
        source_artifact_sha256=source_artifact_sha256,
        library_jd_id=int(saved.get("library_jd_id") or 0),
        saved_source_version_id=str(saved.get("source_version_id") or ""),
        extraction_model_id="",
        model_calls=[],
        extraction_method_override="stored_exact_version_profile_reuse",
        preferred_requirements=preferred_requirements,
    )

    for field in ("source_version_id", "raw_jd_sha256"):
        if _clean(snapshot.get(field)) != _clean(saved.get(field)):
            raise Phase9FJDIntakeError(
                f"The exact saved JD {field} is internally inconsistent."
            )

    return snapshot


def _save_outcome(receipt: dict[str, Any] | None) -> str:
    if not receipt:
        return "not_saved"
    if bool(receipt.get("created_new_job")):
        return "new_jd_created"
    if bool(receipt.get("created_new_version")):
        return "new_version_created"
    return "exact_existing_jd_version_reused"


def build_phase9f_analysis_diagnostics(
    snapshot: dict[str, Any],
    *,
    save_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an allowlisted, read-only diagnostic view of an intake result."""
    if not isinstance(snapshot, dict) or not snapshot:
        raise Phase9FJDIntakeError("A Phase 9F JD snapshot is required.")

    snapshot_fingerprint = _clean(snapshot.get("snapshot_fingerprint"))
    receipt = save_receipt if isinstance(save_receipt, dict) else None
    if receipt and _clean(receipt.get("analysis_snapshot_fingerprint")) != (
        snapshot_fingerprint
    ):
        receipt = None

    rows = [
        row
        for row in snapshot.get("canonical_requirements", []) or []
        if isinstance(row, dict)
    ]
    core_count = sum(_clean(row.get("importance")) == "core" for row in rows)
    required_count = sum(
        _clean(row.get("importance")) == "required" for row in rows
    )
    preferred_count = sum(
        _clean(row.get("importance")) == "preferred" for row in rows
    )
    family = snapshot.get("role_family") or {}
    extraction = snapshot.get("extraction_provenance") or {}
    model_calls = [
        dict(call)
        for call in extraction.get("model_calls", []) or []
        if isinstance(call, dict)
    ]
    api_usage = summarise_call_usage(model_calls)

    saved_jd_id = int(
        (receipt or {}).get("job_description_id")
        or snapshot.get("library_jd_id")
        or 0
    )
    save_outcome = _save_outcome(receipt)
    if snapshot.get("source_type") == "saved" and not receipt:
        save_outcome = "loaded_saved_exact_version"

    # This structure is deliberately assembled field-by-field. Never include
    # raw text, source URLs, model-call ledgers, or arbitrary receipt fields.
    return {
        "format_version": PHASE9F_JD_DIAGNOSTICS_VERSION,
        "source": {
            "mode": _clean(snapshot.get("source_type")),
            "raw_jd_sha256": _clean(snapshot.get("raw_jd_sha256")),
            "uploaded_artifact_sha256": _clean(
                snapshot.get("source_artifact_sha256")
            ),
            "saved_jd_id": saved_jd_id or None,
            "exact_source_version_id": _clean(
                (receipt or {}).get("source_version_id")
                or snapshot.get("source_version_id")
            ),
        },
        "resolved_metadata": {
            "company": _clean(snapshot.get("company")),
            "title": _clean(snapshot.get("job_title")),
            "location": _clean(snapshot.get("location")),
        },
        "fingerprints": {
            "structured_profile": _clean(
                snapshot.get("structured_profile_fingerprint")
            ),
            "canonical_requirements": _clean(
                snapshot.get("canonical_requirement_fingerprint")
            ),
            "transient_snapshot": snapshot_fingerprint,
        },
        "requirements": {
            "total": len(rows),
            "required_core": core_count + required_count,
            "core": core_count,
            "required": required_count,
            "preferred": preferred_count,
        },
        "extraction": {
            "method": _clean(extraction.get("method")),
            "reused_exact_saved_version": bool(
                snapshot.get("reused_exact_saved_version")
            ),
            "model": _clean(extraction.get("model_id")),
            "model_call_count": int(snapshot.get("model_call_count") or 0),
            "embedding_call_count": int(
                snapshot.get("embedding_call_count") or 0
            ),
            "api_usage": api_usage,
        },
        "role_family": {
            "id": _clean(family.get("role_family_id")),
            "label": _clean(family.get("role_family")),
            "confidence": _clean(family.get("confidence")),
            "classifier_version": _clean(family.get("suggestion_method")),
        },
        "most_recent_save": {
            "outcome": save_outcome,
            "new_jd_created": bool(
                receipt and receipt.get("created_new_job")
            ),
            "new_version_created": bool(
                receipt and receipt.get("created_new_version")
            ),
            "exact_existing_jd_version_reused": (
                save_outcome == "exact_existing_jd_version_reused"
            ),
            "chroma_indexing_attempted": bool(
                receipt and receipt.get("chroma_indexing_attempted")
            ),
            "chroma_indexing_occurred": bool(
                receipt and receipt.get("chroma_indexing_occurred")
            ),
            "chroma_indexed_chunk_count": int(
                (receipt or {}).get("chroma_indexed_chunk_count") or 0
            ),
        },
    }


def phase9f_analysis_diagnostics_json(
    snapshot: dict[str, Any],
    *,
    save_receipt: dict[str, Any] | None = None,
) -> str:
    """Serialize safe diagnostics without calling models or persistence."""
    return json.dumps(
        build_phase9f_analysis_diagnostics(
            snapshot,
            save_receipt=save_receipt,
        ),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
