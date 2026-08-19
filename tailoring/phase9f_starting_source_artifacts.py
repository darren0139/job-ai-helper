"""Read-only artifact resolution for Phase 9F-B candidate inspection."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from parse import read_resume_docx, read_resume_pdf
from database.phase9f_exact_verified_reuse_manager import (
    resolve_blueprint_owned_artifacts,
)
from tailoring.phase9f_exact_verified_reuse import Phase9FExactVerifiedReuseError


class Phase9FBArtifactError(ValueError):
    """An immutable starting-source artifact could not be resolved safely."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_tokens(value: Any) -> list[str]:
    normalized = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.findall(r"[a-z0-9]+", normalized)


def _counter_fingerprint(counter: Counter[str]) -> str:
    payload = json.dumps(
        sorted(counter.items()),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _renderer_allowance(profile: dict[str, Any]) -> Counter[str]:
    """Return known visible template text excluded from evidence text.

    The frozen Phase 9D evidence text deliberately omits contact details and
    section headings. Existing fitted templates render those values, and some
    templates repeat an education date beside both the school and degree.
    """
    values: list[Any] = [
        profile.get("name"),
        "Education Work Experience Projects Skills Professional Summary Technical",
    ]
    values.extend((profile.get("contact") or {}).values())
    values.extend(
        row.get("graduation_date") or row.get("date")
        for row in profile.get("education", []) or []
        if isinstance(row, dict)
    )
    allowance: Counter[str] = Counter()
    for value in values:
        allowance.update(_canonical_tokens(value))
    return allowance


def _verify_frozen_snapshot_text(
    *,
    artifact_type: str,
    path: Path,
    frozen_snapshot: dict[str, Any],
) -> str:
    profile = frozen_snapshot.get("resume_profile_snapshot")
    resume_text = frozen_snapshot.get("resume_text_snapshot")
    if not isinstance(profile, dict) or not _clean(resume_text):
        raise Phase9FBArtifactError(
            "The Blueprint's complete frozen resume snapshot is unavailable."
        )
    try:
        extracted = (
            read_resume_pdf(str(path), preserve_complete_text=True)
            if artifact_type == "pdf"
            else read_resume_docx(str(path), preserve_complete_text=True)
        )
    except ValueError as exc:
        raise Phase9FBArtifactError(
            "The exact Blueprint artifact could not be safely verified."
        ) from exc
    expected = Counter(_canonical_tokens(resume_text))
    actual = Counter(_canonical_tokens(extracted))
    missing = expected - actual
    unexpected = actual - expected - _renderer_allowance(profile)
    if not expected or missing or unexpected:
        raise Phase9FBArtifactError(
            "The exact Blueprint artifact could not be safely verified."
        )
    return _counter_fingerprint(actual)


def _artifact_type(filename: str, media_type: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" or media_type == "application/pdf":
        return "pdf"
    if suffix == ".docx" or "wordprocessingml" in media_type:
        return "docx"
    return suffix.lstrip(".") or "file"


def _stored_artifact(
    value: dict[str, Any],
    *,
    expected_source_id: str,
    expected_kind: str,
    provenance_label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Phase9FBArtifactError(
            f"The {expected_kind} artifact record is missing."
        )
    content = value.get("artifact_bytes")
    if not isinstance(content, bytes) or not content:
        raise Phase9FBArtifactError(
            f"The {expected_kind} artifact bytes are missing."
        )
    if _clean(value.get("master_version_id")) != expected_source_id:
        raise Phase9FBArtifactError(
            f"The {expected_kind} artifact belongs to another Base Resume."
        )
    if _clean(value.get("artifact_kind")) != expected_kind:
        raise Phase9FBArtifactError(
            f"The {expected_kind} artifact kind is inconsistent."
        )
    digest = _sha256_bytes(content)
    if (
        digest != _clean(value.get("sha256"))
        or len(content) != int(value.get("byte_size") or -1)
    ):
        raise Phase9FBArtifactError(
            f"The {expected_kind} artifact failed hash or size validation."
        )
    filename = _clean(value.get("filename")) or f"resume.{expected_kind}"
    media_type = _clean(value.get("media_type")) or (
        "application/pdf"
        if expected_kind == "preview_pdf"
        else "application/octet-stream"
    )
    return {
        "artifact_type": _artifact_type(filename, media_type),
        "artifact_kind": expected_kind,
        "filename": filename,
        "media_type": media_type,
        "sha256": digest,
        "byte_size": len(content),
        "artifact_bytes": content,
        "provenance_label": provenance_label,
    }


def _path_artifact(
    raw_path: Any,
    *,
    artifact_type: str,
    provenance_label: str,
    frozen_snapshot: dict[str, Any],
    authoritative_hash: dict[str, Any] | None,
) -> dict[str, Any] | None:
    path_text = str(raw_path or "").strip()
    if not path_text:
        return None
    path = Path(path_text)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.is_file():
        return None
    content = path.read_bytes()
    if not content:
        raise Phase9FBArtifactError(
            f"The fitted {artifact_type.upper()} artifact is empty."
        )
    if artifact_type == "pdf" and not content.startswith(b"%PDF"):
        raise Phase9FBArtifactError(
            "The fitted PDF artifact does not contain a PDF header."
        )
    digest = _sha256_bytes(content)
    verification_method = "frozen_snapshot_token_multiset_v1"
    content_fingerprint = ""
    if authoritative_hash is not None:
        if (
            digest != _clean(authoritative_hash.get("artifact_sha256"))
            or len(content)
            != int(authoritative_hash.get("artifact_size") or -1)
        ):
            raise Phase9FBArtifactError(
                "The exact Blueprint artifact could not be safely verified."
            )
        verification_method = (
            "authoritative_immutable_application_result_sha256"
        )
    else:
        content_fingerprint = _verify_frozen_snapshot_text(
            artifact_type=artifact_type,
            path=path,
            frozen_snapshot=frozen_snapshot,
        )
    return {
        "artifact_type": artifact_type,
        "artifact_kind": "approved_fitted_source",
        "filename": path.name,
        "media_type": (
            "application/pdf"
            if artifact_type == "pdf"
            else "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        "sha256": digest,
        "byte_size": len(content),
        "artifact_bytes": content,
        "provenance_label": provenance_label,
        "verification_method": verification_method,
        "artifact_content_fingerprint": content_fingerprint,
        "source_path": str(path),
    }


def _authoritative_hashes(
    provenance: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    records = (
        (
            (provenance or {}).get("source_resume_result_or_generation")
            or {}
        ).get("immutable_artifact_hash_records")
        or []
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        if not isinstance(row, dict):
            continue
        kind = _clean(row.get("artifact_kind"))
        if kind in {"docx", "pdf"}:
            grouped.setdefault(kind, []).append(row)
    result: dict[str, dict[str, Any]] = {}
    for kind, rows in grouped.items():
        identities = {
            (
                _clean(row.get("artifact_sha256")),
                int(row.get("artifact_size") or -1),
            )
            for row in rows
        }
        if len(identities) != 1:
            raise Phase9FBArtifactError(
                "The Blueprint's authoritative artifact hashes are ambiguous."
            )
        result[kind] = rows[0]
    return result


def resolve_starting_source_artifacts(
    *,
    ranked_candidate: dict[str, Any],
    normalized_source: dict[str, Any],
    current_base_artifact: dict[str, Any] | None,
    current_base_preview_artifact: dict[str, Any] | None,
    global_blueprints: Iterable[dict[str, Any]],
    blueprint_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve downloads and an existing PDF preview without mutating state."""
    source_type = _clean(ranked_candidate.get("source_type"))
    source_id = _clean(ranked_candidate.get("source_id"))
    if (
        source_type != _clean(normalized_source.get("source_type"))
        or source_id != _clean(normalized_source.get("source_id"))
        or _clean(ranked_candidate.get("normalized_source_fingerprint"))
        != _clean(normalized_source.get("normalized_source_fingerprint"))
    ):
        raise Phase9FBArtifactError(
            "The ranked candidate does not match the current normalized source."
        )

    artifacts: list[dict[str, Any]] = []
    if source_type == "base_resume":
        original = _stored_artifact(
            current_base_artifact or {},
            expected_source_id=source_id,
            expected_kind="original",
            provenance_label="Authoritative immutable Base Resume artifact",
        )
        artifacts.append(original)
        preview_pdf = None
        if original["artifact_type"] == "pdf":
            preview_pdf = original
        elif current_base_preview_artifact is not None:
            preview_pdf = _stored_artifact(
                current_base_preview_artifact,
                expected_source_id=source_id,
                expected_kind="preview_pdf",
                provenance_label=(
                    "Stored derived PDF preview of the immutable Base Resume"
                ),
            )
            artifacts.append(preview_pdf)
        return {
            "source_type": source_type,
            "source_id": source_id,
            "source_content_fingerprint": _clean(
                normalized_source.get("source_content_fingerprint")
            ),
            "preview_pdf": preview_pdf,
            "artifacts": artifacts,
        }

    if source_type != "global_blueprint":
        raise Phase9FBArtifactError(
            f"Unsupported Phase 9F-B source type: {source_type or 'missing'}."
        )
    matches = [
        row
        for row in global_blueprints
        if isinstance(row, dict)
        and _clean(row.get("status")) == "active"
        and _clean(row.get("blueprint_id")) == source_id
        and _clean(row.get("blueprint_fingerprint"))
        == _clean(ranked_candidate.get("source_fingerprint"))
    ]
    if len(matches) != 1:
        raise Phase9FBArtifactError(
            "The ranked ACTIVE Blueprint artifact provenance is missing or ambiguous."
        )
    snapshot = matches[0].get("blueprint_snapshot") or {}
    declared_owned_manifest = isinstance(
        (matches[0].get("semantic_identity") or {}).get(
            "artifact_provenance"
        ),
        dict,
    )
    try:
        owned_artifacts = resolve_blueprint_owned_artifacts(matches[0])
    except Phase9FExactVerifiedReuseError as exc:
        if declared_owned_manifest:
            raise Phase9FBArtifactError(
                "The Blueprint-owned immutable artifact failed verification."
            ) from exc
        owned_artifacts = []
    if owned_artifacts:
        preview_pdf = next(
            (row for row in owned_artifacts if row["artifact_type"] == "pdf"),
            None,
        )
        return {
            "source_type": source_type,
            "source_id": source_id,
            "source_content_fingerprint": _clean(
                normalized_source.get("source_content_fingerprint")
            ),
            "preview_pdf": preview_pdf,
            "artifacts": owned_artifacts,
        }
    candidate = snapshot.get("phase9b_candidate_semantic_snapshot") or {}
    frozen_snapshot = snapshot.get("frozen_resume_snapshot") or {}
    fit_result = candidate.get("fit_result") or {}
    source_generation_id = _clean(candidate.get("source_generation_id"))
    # The fit-result generation ID can identify the final fitting render while
    # source_generation_id identifies the approved application generation.
    # Phase 9D immutably binds both values inside the candidate snapshot.
    if (
        not source_generation_id
        or fit_result.get("fit_one_page") is not True
        or int(fit_result.get("page_count") or 0) != 1
    ):
        raise Phase9FBArtifactError(
            "The Blueprint's approved one-page fitted artifact provenance is incomplete."
        )
    if not isinstance(blueprint_provenance, dict) or (
        blueprint_provenance.get("chain_status") != "resolved"
    ):
        raise Phase9FBArtifactError(
            "The exact Blueprint artifact could not be safely verified."
        )
    source_generation = (
        (
            blueprint_provenance.get("source_resume_result_or_generation")
            or {}
        ).get("source_generation")
        or {}
    )
    if (
        source_generation.get("resolved") is not True
        or source_generation.get("approval_resolved") is not True
        or source_generation.get("fit_identity_match") is not True
        or _clean(source_generation.get("generation_id"))
        != source_generation_id
        or (blueprint_provenance.get("phase8_verification") or {}).get(
            "resolved"
        )
        is not True
        or (blueprint_provenance.get("phase8_verification") or {}).get(
            "blueprint_ready"
        )
        is not True
    ):
        raise Phase9FBArtifactError(
            "The exact Blueprint artifact could not be safely verified."
        )
    hashes = _authoritative_hashes(blueprint_provenance)
    provenance_label = (
        "Approved one-page fitted source artifact from Phase 9B/Phase 9D provenance"
    )
    for artifact_type, field in (("docx", "docx_path"), ("pdf", "pdf_path")):
        artifact = _path_artifact(
            fit_result.get(field),
            artifact_type=artifact_type,
            provenance_label=provenance_label,
            frozen_snapshot=frozen_snapshot,
            authoritative_hash=hashes.get(artifact_type),
        )
        if artifact is not None:
            artifacts.append(artifact)
    if not artifacts:
        raise Phase9FBArtifactError(
            "No approved fitted Blueprint artifact is currently available."
        )
    preview_pdf = next(
        (row for row in artifacts if row["artifact_type"] == "pdf"),
        None,
    )
    return {
        "source_type": source_type,
        "source_id": source_id,
        "source_generation_id": source_generation_id,
        "source_verification_fingerprint": _clean(
            candidate.get("source_verification_fingerprint")
        ),
        "source_content_fingerprint": _clean(
            normalized_source.get("source_content_fingerprint")
        ),
        "preview_pdf": preview_pdf,
        "artifacts": artifacts,
    }
