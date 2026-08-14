"""Phase 9F-Master immutable resume preparation and identity helpers.

All document parsing, optional preview conversion, and model work happens in
this module before the database manager opens its short write transaction.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from analysis_stability.resume_profile_stability import (
    RESUME_PROFILE_STABILITY_VERSION,
)
from llm import (
    drain_call_ledger,
    get_active_model,
    reset_call_ledger,
    summarise_call_usage,
)
from parse import read_resume_docx, read_resume_pdf
from prompts import RESUME_PROFILE_PROMPT


PHASE9F_MASTER_RESUME_VERSION = "phase9f-global-master-resume-v1"
PHASE9F_MASTER_CONTENT_POLICY_VERSION = (
    "phase9f-global-master-resume-content-identity-v1"
)
PHASE9F_MASTER_VERSION_POLICY_VERSION = (
    "phase9f-global-master-resume-version-identity-v1"
)
PHASE9F_MASTER_PREPARATION_VERSION = "phase9f-master-resume-preparation-v1"
PHASE9F_MASTER_EXTRACTION_POLICY_VERSION = (
    "phase9f-master-resume-profile-extraction-v1"
)
PHASE9F_MASTER_EVENT_VERSION = "phase9f-master-resume-event-v1"
DEFAULT_MASTER_RESUME_MAX_ARTIFACT_BYTES = 15 * 1024 * 1024


class Phase9FMasterResumeError(ValueError):
    """Raised when a master-resume snapshot cannot be reproduced safely."""


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


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def configured_artifact_size_limit() -> int:
    """Return the configured upload limit, falling back to a 15 MiB default."""
    raw = os.getenv("PHASE9F_MASTER_MAX_ARTIFACT_BYTES", "").strip()
    if not raw:
        return DEFAULT_MASTER_RESUME_MAX_ARTIFACT_BYTES
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_MASTER_RESUME_MAX_ARTIFACT_BYTES
    return max(1, parsed)


def _normalise_current_identity(
    current_master: dict[str, Any] | None,
) -> dict[str, Any]:
    selected = current_master if isinstance(current_master, dict) else {}
    return {
        "master_version_id": str(selected.get("master_version_id") or ""),
        "master_version_fingerprint": str(
            selected.get("master_version_fingerprint") or ""
        ),
    }


def validate_structured_resume_profile(
    structured_profile: dict[str, Any],
) -> dict[str, Any]:
    """Validate the complete existing resume-profile extraction contract."""
    if not isinstance(structured_profile, dict):
        raise Phase9FMasterResumeError(
            "The structured master-resume profile is missing."
        )
    required_types = {
        "name": str,
        "contact": dict,
        "summary": str,
        "education": list,
        "projects": list,
        "experience": list,
        "skills": dict,
    }
    invalid = [
        key
        for key, expected_type in required_types.items()
        if key not in structured_profile
        or not isinstance(structured_profile[key], expected_type)
    ]
    if invalid:
        raise Phase9FMasterResumeError(
            "The structured master-resume profile does not satisfy the "
            "existing complete profile contract: " + ", ".join(invalid)
        )
    contact = structured_profile["contact"]
    contact_keys = ("email", "phone", "linkedin", "github", "portfolio")
    if any(
        key not in contact or not isinstance(contact[key], str)
        for key in contact_keys
    ):
        raise Phase9FMasterResumeError(
            "The structured master-resume contact profile is incomplete."
        )
    skills = structured_profile["skills"]
    skill_keys = ("languages", "frameworks", "tools", "concepts", "platforms")
    if any(
        key not in skills or not isinstance(skills[key], list)
        for key in skill_keys
    ):
        raise Phase9FMasterResumeError(
            "The structured master-resume skills profile is incomplete."
        )
    row_contracts = {
        "education": {
            "school": str,
            "degree": str,
            "graduation_date": str,
            "courses": list,
        },
        "projects": {"title": str, "date": str, "bullets": list},
        "experience": {
            "title": str,
            "company": str,
            "date": str,
            "bullets": list,
        },
    }
    for section, contract in row_contracts.items():
        for index, row in enumerate(structured_profile[section]):
            if not isinstance(row, dict) or any(
                key not in row or not isinstance(row[key], expected_type)
                for key, expected_type in contract.items()
            ):
                raise Phase9FMasterResumeError(
                    "The structured master-resume profile contains an invalid "
                    f"{section} row at index {index}."
                )
    return deepcopy(structured_profile)


def inspect_master_resume_upload(
    *,
    filename: str,
    content: bytes,
    artifact_size_limit_bytes: int | None = None,
) -> dict[str, Any]:
    """Perform complete local extraction and hashing without a model or write.

    The existing parser defaults remain truncating for legacy callers. This
    opt-in path requests complete text and then verifies the resulting hash and
    character count. No model-context truncation is introduced here.
    """
    safe_name = Path(str(filename or "")).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise Phase9FMasterResumeError(
            "Only PDF and DOCX master resume files are supported."
        )
    if not isinstance(content, bytes) or not content:
        raise Phase9FMasterResumeError("The uploaded master resume is empty.")

    limit = int(
        artifact_size_limit_bytes
        if artifact_size_limit_bytes is not None
        else configured_artifact_size_limit()
    )
    if limit < 1:
        raise Phase9FMasterResumeError(
            "The configured master-resume artifact limit is invalid."
        )
    if len(content) > limit:
        raise Phase9FMasterResumeError(
            "The uploaded master resume is too large: "
            f"{len(content):,} bytes exceeds the configured {limit:,}-byte limit. "
            "No model call or persistence write was made."
        )

    with tempfile.TemporaryDirectory(prefix="phase9f_master_preflight_") as name:
        source_path = Path(name) / f"uploaded{suffix}"
        source_path.write_bytes(content)
        try:
            resume_text = (
                read_resume_pdf(
                    str(source_path),
                    preserve_complete_text=True,
                )
                if suffix == ".pdf"
                else read_resume_docx(
                    str(source_path),
                    preserve_complete_text=True,
                )
            )
        except ValueError as exc:
            raise Phase9FMasterResumeError(
                f"Could not extract complete master-resume text: {exc}"
            ) from exc

    if not resume_text:
        raise Phase9FMasterResumeError(
            "Complete master-resume extraction returned no text."
        )

    artifact_type = suffix.removeprefix(".")
    media_type = (
        "application/pdf"
        if artifact_type == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    identity = {
        "inspection_version": PHASE9F_MASTER_PREPARATION_VERSION,
        "artifact_sha256": sha256_bytes(content),
        "artifact_type": artifact_type,
        "artifact_size_bytes": len(content),
        "resume_text_sha256": sha256_text(resume_text),
        "resume_text_char_count": len(resume_text),
        "extraction_method": (
            "pypdf_complete_text"
            if artifact_type == "pdf"
            else "python_docx_complete_text"
        ),
    }
    return {
        **identity,
        "inspection_fingerprint": fingerprint_value(identity),
        "original_filename": safe_name,
        "media_type": media_type,
        "artifact_bytes": bytes(content),
        "resume_text": resume_text,
    }


def _allowlisted_usage(calls: list[dict[str, Any]]) -> dict[str, Any]:
    usage = summarise_call_usage(calls)
    return {
        "currency": str(usage.get("currency") or "USD"),
        "estimated_cost_usd": usage.get("estimated_cost_usd"),
        "call_count": int(usage.get("call_count") or 0),
        "costed_call_count": int(usage.get("costed_call_count") or 0),
        "uncosted_call_count": int(usage.get("uncosted_call_count") or 0),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "cached_prompt_tokens": int(usage.get("cached_prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "cost_source": str(usage.get("cost_source") or ""),
        "cost_is_estimate": bool(usage.get("cost_is_estimate")),
    }


def _safe_extraction_provenance(
    *,
    method: str,
    requested_model: str = "",
    response_model: str = "",
    calls: list[dict[str, Any]] | None = None,
    profile_source_master_version_id: str = "",
    profile_source_master_version_fingerprint: str = "",
    profile_source_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_calls = [
        dict(call)
        for call in (calls or [])
        if isinstance(call, dict)
    ]
    elapsed_seconds = round(
        sum(float(call.get("elapsed_seconds") or 0.0) for call in selected_calls),
        3,
    )
    source = (
        profile_source_provenance
        if isinstance(profile_source_provenance, dict)
        else {}
    )
    return {
        "method": str(method or ""),
        "requested_model": str(requested_model or ""),
        "response_model": str(response_model or ""),
        "extraction_policy_version": PHASE9F_MASTER_EXTRACTION_POLICY_VERSION,
        "resume_profile_prompt_sha256": sha256_text(RESUME_PROFILE_PROMPT),
        "resume_profile_stability_version": RESUME_PROFILE_STABILITY_VERSION,
        "call_count": len(selected_calls),
        "elapsed_seconds": elapsed_seconds,
        "api_usage": _allowlisted_usage(selected_calls),
        "profile_source_master_version_id": str(
            profile_source_master_version_id or ""
        ),
        "profile_source_master_version_fingerprint": str(
            profile_source_master_version_fingerprint or ""
        ),
        "profile_source_extraction": {
            "method": str(source.get("method") or ""),
            "requested_model": str(source.get("requested_model") or ""),
            "response_model": str(source.get("response_model") or ""),
            "extraction_policy_version": str(
                source.get("extraction_policy_version") or ""
            ),
            "resume_profile_prompt_sha256": str(
                source.get("resume_profile_prompt_sha256") or ""
            ),
            "resume_profile_stability_version": str(
                source.get("resume_profile_stability_version") or ""
            ),
        },
        "embedding_call_count": 0,
    }


def build_prepared_master_resume_snapshot(
    *,
    inspection: dict[str, Any],
    structured_profile: dict[str, Any],
    extraction_provenance: dict[str, Any],
    current_master: dict[str, Any] | None,
    preparation_mode: str,
) -> dict[str, Any]:
    """Freeze an immutable prepared snapshot without opening a transaction."""
    if not isinstance(inspection, dict):
        raise Phase9FMasterResumeError("Master-resume inspection is missing.")
    artifact_bytes = inspection.get("artifact_bytes")
    resume_text = str(inspection.get("resume_text") or "")
    if not isinstance(artifact_bytes, bytes) or not artifact_bytes:
        raise Phase9FMasterResumeError("Prepared artifact bytes are missing.")
    if sha256_bytes(artifact_bytes) != str(inspection.get("artifact_sha256") or ""):
        raise Phase9FMasterResumeError("Prepared artifact bytes failed SHA-256 validation.")
    if sha256_text(resume_text) != str(inspection.get("resume_text_sha256") or ""):
        raise Phase9FMasterResumeError("Prepared complete resume text failed SHA-256 validation.")
    frozen_profile = validate_structured_resume_profile(structured_profile)
    if not isinstance(extraction_provenance, dict) or not extraction_provenance:
        raise Phase9FMasterResumeError("Profile extraction provenance is missing.")

    profile_fingerprint = fingerprint_value(frozen_profile)
    semantic_identity = {
        "format_version": PHASE9F_MASTER_RESUME_VERSION,
        "content_policy_version": PHASE9F_MASTER_CONTENT_POLICY_VERSION,
        "artifact": {
            "artifact_sha256": str(inspection["artifact_sha256"]),
            "artifact_type": str(inspection["artifact_type"]),
            "artifact_size_bytes": int(inspection["artifact_size_bytes"]),
        },
        "resume_text": {
            "resume_text_sha256": str(inspection["resume_text_sha256"]),
            "resume_text_char_count": int(inspection["resume_text_char_count"]),
        },
        "structured_profile_fingerprint": profile_fingerprint,
        "profile_contract": {
            "extraction_policy_version": PHASE9F_MASTER_EXTRACTION_POLICY_VERSION,
            "resume_profile_prompt_sha256": sha256_text(RESUME_PROFILE_PROMPT),
            "resume_profile_stability_version": RESUME_PROFILE_STABILITY_VERSION,
        },
    }
    content_fingerprint = fingerprint_value(semantic_identity)
    expected_current = _normalise_current_identity(current_master)
    provenance_fingerprint = fingerprint_value(extraction_provenance)
    prepared_identity = {
        "preparation_version": PHASE9F_MASTER_PREPARATION_VERSION,
        "master_content_fingerprint": content_fingerprint,
        "expected_current": expected_current,
        "preparation_mode": str(preparation_mode or ""),
        "extraction_provenance_fingerprint": provenance_fingerprint,
    }
    return {
        "preparation_version": PHASE9F_MASTER_PREPARATION_VERSION,
        "preparation_mode": str(preparation_mode or ""),
        "prepared_snapshot_fingerprint": fingerprint_value(prepared_identity),
        "expected_current": expected_current,
        "artifact_sha256": str(inspection["artifact_sha256"]),
        "artifact_type": str(inspection["artifact_type"]),
        "artifact_size_bytes": int(inspection["artifact_size_bytes"]),
        "original_filename": str(inspection.get("original_filename") or ""),
        "media_type": str(inspection.get("media_type") or ""),
        "artifact_bytes": bytes(artifact_bytes),
        "resume_text": resume_text,
        "resume_text_sha256": str(inspection["resume_text_sha256"]),
        "resume_text_char_count": int(inspection["resume_text_char_count"]),
        "structured_profile": frozen_profile,
        "structured_profile_fingerprint": profile_fingerprint,
        "semantic_identity": semantic_identity,
        "semantic_identity_json": canonical_json(semantic_identity),
        "master_content_fingerprint": content_fingerprint,
        "extraction_provenance": deepcopy(extraction_provenance),
        "extraction_provenance_fingerprint": provenance_fingerprint,
        "preview_pdf_bytes": None,
        "preview_pdf_sha256": "",
    }


def analyse_and_prepare_master_resume(
    *,
    inspection: dict[str, Any],
    current_master: dict[str, Any] | None,
    extract_profile_fn: Callable[[str], dict[str, Any]],
    requested_model: str | None = None,
) -> dict[str, Any]:
    """Make the one explicit paid extraction call, then freeze preparation."""
    model_id = str(requested_model or get_active_model("analysis"))
    reset_call_ledger()
    try:
        profile = extract_profile_fn(str(inspection.get("resume_text") or ""))
        calls = drain_call_ledger()
    except Exception:
        drain_call_ledger()
        raise
    if len(calls) != 1:
        raise Phase9FMasterResumeError(
            "Master-resume profile extraction must record exactly one model call; "
            f"recorded {len(calls)}. Nothing was persisted."
        )
    response_model = str(calls[-1].get("response_model") or "")
    provenance = _safe_extraction_provenance(
        method="explicit_model_profile_extraction",
        requested_model=model_id,
        response_model=response_model,
        calls=calls,
    )
    return build_prepared_master_resume_snapshot(
        inspection=inspection,
        structured_profile=profile,
        extraction_provenance=provenance,
        current_master=current_master,
        preparation_mode="novel_text_model_extraction",
    )


def prepare_master_resume_from_reusable_profile(
    *,
    inspection: dict[str, Any],
    reusable_master: dict[str, Any],
    current_master: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reuse a frozen profile only after exact complete-text identity matches."""
    if not isinstance(reusable_master, dict) or not reusable_master:
        raise Phase9FMasterResumeError("A reusable frozen master version is required.")
    if str(reusable_master.get("resume_text_sha256") or "") != str(
        inspection.get("resume_text_sha256") or ""
    ):
        raise Phase9FMasterResumeError(
            "Frozen profile reuse requires an exact complete resume-text SHA-256 match."
        )
    profile = reusable_master.get("structured_profile")
    if not isinstance(profile, dict) or not profile:
        raise Phase9FMasterResumeError(
            "The reusable master version has no authoritative frozen profile."
        )
    expected_profile_fingerprint = str(
        reusable_master.get("structured_profile_fingerprint") or ""
    )
    if fingerprint_value(profile) != expected_profile_fingerprint:
        raise Phase9FMasterResumeError(
            "The reusable frozen profile failed fingerprint validation."
        )
    same_artifact = str(reusable_master.get("artifact_sha256") or "") == str(
        inspection.get("artifact_sha256") or ""
    )
    provenance = _safe_extraction_provenance(
        method=(
            "frozen_profile_exact_artifact_reuse"
            if same_artifact
            else "frozen_profile_exact_text_reuse"
        ),
        profile_source_master_version_id=str(
            reusable_master.get("master_version_id") or ""
        ),
        profile_source_master_version_fingerprint=str(
            reusable_master.get("master_version_fingerprint") or ""
        ),
        profile_source_provenance=(
            reusable_master.get("extraction_provenance")
            if isinstance(reusable_master.get("extraction_provenance"), dict)
            else {}
        ),
    )
    return build_prepared_master_resume_snapshot(
        inspection=inspection,
        structured_profile=profile,
        extraction_provenance=provenance,
        current_master=current_master,
        preparation_mode=(
            "exact_artifact_profile_reuse"
            if same_artifact
            else "exact_text_profile_reuse"
        ),
    )


def attach_preview_pdf(
    prepared: dict[str, Any],
    preview_pdf_bytes: bytes,
) -> dict[str, Any]:
    """Attach an optional derived preview without changing semantic identity."""
    if not isinstance(preview_pdf_bytes, bytes) or not preview_pdf_bytes.startswith(b"%PDF"):
        raise Phase9FMasterResumeError("The derived preview is not a valid PDF artifact.")
    result = deepcopy(prepared)
    result["preview_pdf_bytes"] = bytes(preview_pdf_bytes)
    result["preview_pdf_sha256"] = sha256_bytes(preview_pdf_bytes)
    return result


def build_master_version_identity(
    *,
    master_content_fingerprint: str,
    version_number: int,
    predecessor_master_version_id: str,
    predecessor_master_version_fingerprint: str,
) -> dict[str, Any]:
    """Return the canonical payload for one chronological master version."""
    return {
        "format_version": PHASE9F_MASTER_RESUME_VERSION,
        "version_policy_version": PHASE9F_MASTER_VERSION_POLICY_VERSION,
        "master_content_fingerprint": str(master_content_fingerprint or ""),
        "version_number": int(version_number),
        "predecessor": {
            "master_version_id": str(predecessor_master_version_id or ""),
            "master_version_fingerprint": str(
                predecessor_master_version_fingerprint or ""
            ),
        },
    }
