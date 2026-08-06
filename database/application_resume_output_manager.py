"""Resolve persisted application résumé outputs without session-state authority."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any

from database.application_resume_result_manager import (
    get_application_resume_result,
    get_current_application_resume_result,
)
from database.application_blueprint_manager import (
    list_application_blueprint_decisions,
)
from database.db_manager import get_application_by_id
from database.jd_library_manager import (
    get_exact_job_description_for_application,
)
from database.tailoring_generation_control import (
    get_application_generation_control,
    get_tailoring_generation,
)
from tailoring.phase8_verification import (
    build_final_resume_profile,
    build_resume_text_from_profile,
)
from tailoring.phase9e_blueprint_selection import (
    fingerprint_value,
    validate_exact_jd_snapshot,
)
from tailoring.tailoring_generation_fingerprint import (
    get_effective_generation_sections,
    stable_content_fingerprint,
)


APPLICATION_OUTPUT_RESOLVER_VERSION = "application-resume-output-resolver-v1"


class ApplicationResumeOutputError(ValueError):
    """Raised when a persisted résumé output cannot be resolved safely."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_rows(generation: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, mime, active_key, stored_key in (
        (
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx_path",
            "stored_docx_path",
        ),
        ("pdf", "application/pdf", "pdf_path", "stored_pdf_path"),
    ):
        raw = generation.get(active_key) or generation.get(stored_key)
        path = Path(str(raw or ""))
        if not raw or not path.is_file():
            continue
        rows.append(
            {
                "artifact_kind": kind,
                "mime_type": mime,
                "materialized_path": str(path),
                "artifact_sha256": _sha256(path),
                "artifact_size": path.stat().st_size,
                "provenance_mode": "tailoring_generation_artifact",
                "provenance_label": "Persisted tailoring-generation artifact",
            }
        )
    return rows


def _jd_snapshot(application_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = get_exact_job_description_for_application(application_id)
    if not isinstance(raw, dict) or not raw:
        raise ApplicationResumeOutputError(
            "The application's exact linked JD snapshot is unavailable."
        )
    try:
        jd = validate_exact_jd_snapshot(deepcopy(raw))
    except ValueError as exc:
        raise ApplicationResumeOutputError(str(exc)) from exc
    identity = {
        "library_jd_id": int(jd.get("library_jd_id", 0) or 0),
        "canonical_jd_id": _clean(jd.get("canonical_jd_id")),
        "source_version_id": _clean(jd.get("source_version_id")),
        "raw_jd_sha256": _clean(jd.get("raw_jd_sha256")),
        "stable_input_fingerprint": _clean(
            jd.get("stable_input_fingerprint")
        ),
        "canonical_requirement_ids": list(
            jd.get("canonical_requirement_ids") or []
        ),
        "canonical_requirement_fingerprint": _clean(
            jd.get("canonical_requirement_fingerprint")
        ),
        "source_application_link": deepcopy(
            jd.get("source_application_link") or {}
        ),
    }
    identity["jd_identity_fingerprint"] = fingerprint_value(identity)
    return jd, identity


def _immutable_output(
    *,
    application_id: int,
    application_result_id: str,
    allow_historical: bool,
) -> dict[str, Any]:
    result = get_application_resume_result(application_result_id)
    if result is None or int(result.get("application_id", 0)) != int(
        application_id
    ):
        raise ApplicationResumeOutputError(
            "The requested immutable application result was not found."
        )
    current = get_current_application_resume_result(application_id)
    is_current = bool(
        current
        and current.get("application_result_id") == application_result_id
        and (current.get("state") or {}).get("active_output_mode")
        == "immutable_result"
    )
    if not is_current and not allow_historical:
        raise ApplicationResumeOutputError(
            "A historical immutable result requires explicit historical selection."
        )
    snapshot = result.get("result_snapshot") or {}
    starting = snapshot.get("starting_snapshot") or {}
    profile = starting.get("resume_profile_snapshot")
    text = starting.get("resume_text_snapshot")
    if not isinstance(profile, dict) or not profile or not _clean(text):
        raise ApplicationResumeOutputError(
            "The immutable result's frozen résumé snapshot is incomplete."
        )
    return {
        "output_kind": "immutable_application_result",
        "output_id": result["application_result_id"],
        "source_id": result["application_result_id"],
        "source_fingerprint": result["result_fingerprint"],
        "status": result["initial_status"],
        "is_current": is_current,
        "is_historical": not is_current,
        "editable": False,
        "content_changed": False,
        "resume_profile_snapshot": deepcopy(profile),
        "resume_text_snapshot": str(text),
        "artifacts": deepcopy(result.get("artifacts") or []),
        "source_provenance": {
            "application_result_id": result["application_result_id"],
            "result_fingerprint": result["result_fingerprint"],
            "phase9e_decision_id": result["phase9e_decision_id"],
            "phase9e_decision_fingerprint": result[
                "phase9e_decision_fingerprint"
            ],
            "blueprint_id": result["blueprint_id"],
            "blueprint_fingerprint": result["blueprint_fingerprint"],
            "blueprint_version": result["blueprint_version"],
        },
    }


def _generation_output(
    *,
    application_id: int,
    generation_id: str,
    allow_historical: bool,
) -> dict[str, Any]:
    generation = get_tailoring_generation(application_id, generation_id)
    if generation is None:
        raise ApplicationResumeOutputError(
            "The requested tailoring generation was not found."
        )
    current_result = get_current_application_resume_result(
        application_id, validate_artifacts=False
    )
    current_editable_id = ""
    if current_result is not None and (
        current_result.get("state") or {}
    ).get("active_output_mode") == "editable":
        current_editable_id = _clean(
            (current_result.get("state") or {}).get("current_generation_id")
        )
    control = get_application_generation_control(application_id)
    approved_id = _clean(control.get("approved_generation_id"))
    is_current = generation_id in {current_editable_id, approved_id}
    if not is_current and not allow_historical:
        raise ApplicationResumeOutputError(
            "A historical tailoring generation requires explicit historical selection."
        )
    phase9e_fingerprint = _clean(
        generation.get("phase9e_decision_fingerprint")
    )
    source_result_id = _clean(generation.get("source_application_result_id"))
    baseline_profile: dict[str, Any] = {}
    baseline_provenance: dict[str, Any] = {}
    if source_result_id:
        source_result = get_application_resume_result(source_result_id)
        if source_result is None or int(source_result.get("application_id", 0)) != int(
            application_id
        ):
            raise ApplicationResumeOutputError(
                "The editable generation's immutable source result is unavailable."
            )
        source_starting = (
            (source_result.get("result_snapshot") or {}).get("starting_snapshot")
            or {}
        )
        baseline_profile = deepcopy(
            source_starting.get("resume_profile_snapshot") or {}
        )
        baseline_provenance = {
            "source_type": "immutable_application_result",
            "application_result_id": source_result_id,
            "result_fingerprint": source_result.get("result_fingerprint"),
        }
    elif phase9e_fingerprint:
        matches = [
            row
            for row in list_application_blueprint_decisions(application_id)
            if _clean(row.get("decision_fingerprint")) == phase9e_fingerprint
        ]
        if len(matches) != 1:
            raise ApplicationResumeOutputError(
                "The generation's exact Phase 9E starting snapshot cannot be resolved uniquely."
            )
        starting = matches[0].get("starting_snapshot") or {}
        baseline_profile = deepcopy(
            starting.get("resume_profile_snapshot") or {}
        )
        baseline_provenance = {
            "source_type": "phase9e_starting_snapshot",
            "decision_id": matches[0].get("decision_id"),
            "decision_fingerprint": phase9e_fingerprint,
            "starting_snapshot_fingerprint": starting.get(
                "starting_snapshot_fingerprint"
            ),
        }
    else:
        application = get_application_by_id(application_id)
        report = (application or {}).get("report") or {}
        baseline_profile = deepcopy(report.get("resume_profile") or {})
        baseline_provenance = {
            "source_type": "persisted_application_report",
        }
    if not isinstance(baseline_profile, dict) or not baseline_profile:
        raise ApplicationResumeOutputError(
            "The persisted application résumé profile is unavailable."
        )
    effective = get_effective_generation_sections(generation)
    if not isinstance(effective.get("projects"), dict) or not isinstance(
        effective.get("skills"), dict
    ):
        raise ApplicationResumeOutputError(
            "The tailoring generation lacks complete Projects and Skills output."
        )
    profile = build_final_resume_profile(baseline_profile, generation)
    text = build_resume_text_from_profile(profile)
    if not _clean(text):
        raise ApplicationResumeOutputError(
            "The persisted generation could not produce résumé text."
        )
    status = _clean(generation.get("status")) or "draft"
    was_approved = status == "approved" or bool(
        _clean(generation.get("approved_at"))
    )
    return {
        "output_kind": (
            "approved_tailored_generation"
            if was_approved
            else "editable_tailoring_draft"
        ),
        "output_id": generation_id,
        "source_id": generation_id,
        "source_fingerprint": stable_content_fingerprint(
            {
                "generation_id": generation_id,
                "status": status,
                "resume_profile_snapshot": profile,
                "resume_text_snapshot": text,
                "fit_result": generation.get("fit_result") or {},
                "phase9e_decision_fingerprint": generation.get(
                    "phase9e_decision_fingerprint"
                ),
            }
        ),
        "status": status,
        "is_current": is_current,
        "is_historical": not is_current,
        "editable": status == "draft",
        "content_changed": generation.get("content_changed"),
        "resume_profile_snapshot": profile,
        "resume_text_snapshot": text,
        "artifacts": _artifact_rows(generation),
        "source_provenance": {
            "generation_id": generation_id,
            "generation_kind": generation.get("generation_kind"),
            "input_fingerprint": generation.get("input_fingerprint"),
            "phase9e_decision_fingerprint": generation.get(
                "phase9e_decision_fingerprint"
            ),
            "fit_result": deepcopy(generation.get("fit_result") or {}),
            "baseline": baseline_provenance,
        },
    }


def resolve_application_resume_output(
    application_id: int,
    *,
    application_result_id: str = "",
    generation_id: str = "",
    allow_historical: bool = False,
) -> dict[str, Any]:
    """Resolve the current output, or an explicitly selected historical output."""
    if int(application_id) <= 0:
        raise ApplicationResumeOutputError("application_id must be positive.")
    explicit_result = _clean(application_result_id)
    explicit_generation = _clean(generation_id)
    if explicit_result and explicit_generation:
        raise ApplicationResumeOutputError(
            "Select either an application result or a tailoring generation, not both."
        )
    if explicit_result:
        output = _immutable_output(
            application_id=application_id,
            application_result_id=explicit_result,
            allow_historical=allow_historical,
        )
    elif explicit_generation:
        output = _generation_output(
            application_id=application_id,
            generation_id=explicit_generation,
            allow_historical=allow_historical,
        )
    else:
        current_result = get_current_application_resume_result(application_id)
        if current_result is not None:
            state = current_result.get("state") or {}
            if state.get("active_output_mode") == "immutable_result":
                output = _immutable_output(
                    application_id=application_id,
                    application_result_id=current_result[
                        "application_result_id"
                    ],
                    allow_historical=False,
                )
            elif state.get("active_output_mode") == "editable" and _clean(
                state.get("current_generation_id")
            ):
                output = _generation_output(
                    application_id=application_id,
                    generation_id=_clean(state.get("current_generation_id")),
                    allow_historical=False,
                )
            else:
                raise ApplicationResumeOutputError(
                    "The current application-output state is invalid."
                )
        else:
            control = get_application_generation_control(application_id)
            approved_id = _clean(control.get("approved_generation_id"))
            if not approved_id:
                raise ApplicationResumeOutputError(
                    "No current immutable result or approved tailoring generation is available."
                )
            output = _generation_output(
                application_id=application_id,
                generation_id=approved_id,
                allow_historical=False,
            )

    jd, jd_identity = _jd_snapshot(application_id)
    profile_fingerprint = fingerprint_value(
        output["resume_profile_snapshot"]
    )
    text_sha256 = hashlib.sha256(
        output["resume_text_snapshot"].encode("utf-8")
    ).hexdigest()
    resolver_identity = {
        "resolver_version": APPLICATION_OUTPUT_RESOLVER_VERSION,
        "application_id": int(application_id),
        "output_kind": output["output_kind"],
        "source_id": output["source_id"],
        "source_fingerprint": output["source_fingerprint"],
        "resume_profile_fingerprint": profile_fingerprint,
        "resume_text_sha256": text_sha256,
        "jd_identity": jd_identity,
    }
    return {
        **output,
        "application_id": int(application_id),
        "resolver_version": APPLICATION_OUTPUT_RESOLVER_VERSION,
        "resume_profile_fingerprint": profile_fingerprint,
        "resume_text_sha256": text_sha256,
        "exact_jd_snapshot": jd,
        "exact_jd_identity": jd_identity,
        "output_fingerprint": fingerprint_value(resolver_identity),
        "semantic_identity": resolver_identity,
    }
