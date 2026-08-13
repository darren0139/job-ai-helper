"""Deterministic fingerprints, fitted lock sources, and version comparison."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


TAILORING_FINGERPRINT_VERSION = "tailoring-input-fingerprint-v3"
TAILORING_LOCK_POLICY_VERSION = "tailoring-section-locks-v2"


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonical(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, str):
        return " ".join(value.split())
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def stable_content_fingerprint(value: Any) -> str:
    payload = json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generation_matches_phase9e_binding(
    generation: dict[str, Any] | None,
    phase9e_binding: dict[str, Any] | None,
) -> bool:
    """Return whether a persisted generation belongs to the current binding."""
    expected = phase9e_binding or {}
    if not expected:
        return False
    state = generation or {}
    settings = state.get("generation_settings") or {}
    stored = settings.get("phase9e_binding") or {}
    return bool(
        stored
        and stored.get("decision_fingerprint")
        == expected.get("decision_fingerprint")
        and stored.get("starting_snapshot_fingerprint")
        == expected.get("starting_snapshot_fingerprint")
        and stored.get("workflow_action_fingerprint")
        == expected.get("workflow_action_fingerprint")
    )


def constrain_generation_control_to_phase9e(
    control: dict[str, Any],
    phase9e_binding: dict[str, Any],
) -> dict[str, Any]:
    """Ignore approved locks from a different immutable starting source."""
    result = deepcopy(control)
    approved = result.get("approved_generation")
    if generation_matches_phase9e_binding(approved, phase9e_binding):
        return result
    result["approved_generation"] = None
    result["approved_generation_id"] = ""
    result["lock_projects"] = False
    result["lock_skills"] = False
    result["phase9e_incompatible_approval_ignored"] = bool(approved)
    return result


def get_effective_generation_sections(
    generation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return exactly what the final fitted document used when available."""
    state = generation or {}
    fit_result = state.get("fit_result") or {}
    final_projects = (
        fit_result.get("tailored_projects_used")
        if isinstance(fit_result, dict)
        else None
    )
    final_skills = (
        fit_result.get("tailored_skills_used")
        if isinstance(fit_result, dict)
        else None
    )

    projects_from_fit = isinstance(final_projects, dict)
    skills_from_fit = isinstance(final_skills, dict)

    return {
        "projects": deepcopy(
            final_projects if projects_from_fit else state.get("projects")
        ),
        "skills": deepcopy(
            final_skills if skills_from_fit else state.get("skills")
        ),
        "projects_source": (
            "final_fitted_output" if projects_from_fit else "generated_snapshot"
        ),
        "skills_source": (
            "final_fitted_output" if skills_from_fit else "generated_snapshot"
        ),
    }


def materialise_generation_for_display(
    generation: dict[str, Any],
) -> dict[str, Any]:
    """Copy a generation with Projects/Skills aligned to its final output."""
    result = deepcopy(generation)
    effective = get_effective_generation_sections(generation)
    result["projects"] = effective["projects"]
    result["skills"] = effective["skills"]
    result["display_section_sources"] = {
        "projects": effective["projects_source"],
        "skills": effective["skills_source"],
    }
    return result


def build_generation_action_plan(
    *,
    lock_projects: bool,
    lock_skills: bool,
    approved_generation: dict[str, Any] | None,
) -> dict[str, Any]:
    approved_exists = isinstance(approved_generation, dict)
    if lock_projects and lock_skills and approved_exists:
        return {
            "mode": "load_approved",
            "button_label": "Load Approved Final Projects + Skills",
            "requires_project_ai": False,
            "requires_skills_ai": False,
            "creates_draft": False,
            "note": (
                "Both sections are locked. The approved final fitted content "
                "will be loaded without AI or a redundant draft."
            ),
        }
    if lock_projects and approved_exists:
        return {
            "mode": "generate_skills_only",
            "button_label": "Generate Skills; Reuse Approved Projects",
            "requires_project_ai": False,
            "requires_skills_ai": True,
            "creates_draft": True,
            "note": "Approved final Projects will be reused.",
        }
    if lock_skills and approved_exists:
        return {
            "mode": "generate_projects_only",
            "button_label": "Generate Projects; Reuse Approved Skills",
            "requires_project_ai": True,
            "requires_skills_ai": False,
            "creates_draft": True,
            "note": "Approved final Skills will be reused.",
        }
    return {
        "mode": "generate_both",
        "button_label": "Generate Projects + Skills",
        "requires_project_ai": True,
        "requires_skills_ai": True,
        "creates_draft": True,
        "note": "Both sections will be generated.",
    }


def build_tailoring_input_fingerprint(
    *,
    report: dict[str, Any],
    evidence_items: list[dict[str, Any]],
    generation_settings: dict[str, Any],
    generation_kind: str,
    model_id: str,
    approved_generation: dict[str, Any] | None = None,
    lock_projects: bool = False,
    lock_skills: bool = False,
    phase9e_binding: dict[str, Any] | None = None,
) -> str:
    """Fingerprint every input that can alter Projects or Skills generation."""
    stable_analysis = report.get("stable_analysis", {}) or {}
    approved = approved_generation or {}
    effective = get_effective_generation_sections(approved)
    payload = {
        "fingerprint_version": TAILORING_FINGERPRINT_VERSION,
        "generator_contract_version": "phase7-projects-skills-cache-v3",
        "generation_kind": generation_kind,
        "model_id": model_id,
        "analysis_cache_fingerprint": (
            report.get("meta", {})
            .get("analysis_cache", {})
            .get("input_fingerprint", "")
        ),
        "stable_analysis_input_fingerprint": stable_analysis.get(
            "input_fingerprint",
            "",
        ),
        "scoring_version": stable_analysis.get("scoring_version", ""),
        "taxonomy_version": stable_analysis.get(
            "capability_taxonomy_version",
            "",
        ),
        "resume_profile": report.get("resume_profile", {}),
        "phase9e_binding": deepcopy(phase9e_binding or {}),
        "jd_profile": report.get("jd_profile", {}),
        "raw_jd_text": report.get("raw_jd_text", ""),
        "evidence_items": evidence_items,
        "generation_settings": generation_settings,
        "locks": {
            "lock_projects": bool(lock_projects),
            "lock_skills": bool(lock_skills),
            "approved_generation_id": approved.get("generation_id", ""),
            "approved_projects_source": effective["projects_source"],
            "approved_skills_source": effective["skills_source"],
            "approved_projects_fingerprint": (
                stable_content_fingerprint(effective["projects"])
                if lock_projects
                else ""
            ),
            "approved_skills_fingerprint": (
                stable_content_fingerprint(effective["skills"])
                if lock_skills
                else ""
            ),
        },
    }
    return stable_content_fingerprint(payload)


def resolve_locked_sections(
    *,
    proposed_projects: dict[str, Any] | None,
    proposed_skills: dict[str, Any] | None,
    approved_generation: dict[str, Any] | None,
    lock_projects: bool,
    lock_skills: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    effective = get_effective_generation_sections(approved_generation)
    projects = (
        deepcopy(effective["projects"])
        if lock_projects and effective["projects"] is not None
        else deepcopy(proposed_projects)
    )
    skills = (
        deepcopy(effective["skills"])
        if lock_skills and effective["skills"] is not None
        else deepcopy(proposed_skills)
    )
    return projects, skills


def build_fitting_lock_policy(
    *,
    lock_projects: bool,
    lock_skills: bool,
) -> dict[str, Any]:
    return {
        "lock_policy_version": TAILORING_LOCK_POLICY_VERSION,
        "lock_projects": bool(lock_projects),
        "lock_skills": bool(lock_skills),
        "allow_project_compaction": not bool(lock_projects),
        "allow_project_bullet_removal": not bool(lock_projects),
        "allow_project_removal": not bool(lock_projects),
        "allow_skills_compaction": not bool(lock_skills),
    }


def _project_map(value: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(value, dict):
        return result
    for project in value.get("recommended_projects", []) or []:
        if not isinstance(project, dict):
            continue
        title = str(
            project.get("display_title")
            or project.get("title")
            or "Untitled Project"
        )
        result[title] = project
    return result


def _skill_map(value: Any) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if not isinstance(value, dict):
        return result
    for line in value.get("skill_lines", []) or []:
        if not isinstance(line, dict):
            continue
        category = str(line.get("category") or "Uncategorised")
        result[category] = [
            str(item)
            for item in line.get("items", []) or []
            if str(item).strip()
        ]
    return result


def compare_tailoring_generations(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    left_effective = get_effective_generation_sections(left)
    right_effective = get_effective_generation_sections(right)
    left_projects = _project_map(left_effective["projects"])
    right_projects = _project_map(right_effective["projects"])
    left_skills = _skill_map(left_effective["skills"])
    right_skills = _skill_map(right_effective["skills"])

    common_projects = sorted(set(left_projects) & set(right_projects))
    changed_projects = [
        title
        for title in common_projects
        if stable_content_fingerprint(left_projects[title])
        != stable_content_fingerprint(right_projects[title])
    ]
    common_skill_categories = sorted(set(left_skills) & set(right_skills))
    changed_skill_categories = [
        category
        for category in common_skill_categories
        if left_skills[category] != right_skills[category]
    ]

    return {
        "left_generation_id": left.get("generation_id", ""),
        "right_generation_id": right.get("generation_id", ""),
        "comparison_basis": "final_fitted_output_when_available",
        "left_section_sources": {
            "projects": left_effective["projects_source"],
            "skills": left_effective["skills_source"],
        },
        "right_section_sources": {
            "projects": right_effective["projects_source"],
            "skills": right_effective["skills_source"],
        },
        "project_changes": {
            "added": sorted(set(right_projects) - set(left_projects)),
            "removed": sorted(set(left_projects) - set(right_projects)),
            "changed": changed_projects,
        },
        "skill_changes": {
            "added_categories": sorted(set(right_skills) - set(left_skills)),
            "removed_categories": sorted(set(left_skills) - set(right_skills)),
            "changed_categories": changed_skill_categories,
        },
        "fit_changes": {
            "left_page_count": (left.get("fit_result") or {}).get("page_count"),
            "right_page_count": (right.get("fit_result") or {}).get("page_count"),
            "left_fit_one_page": (left.get("fit_result") or {}).get(
                "fit_one_page"
            ),
            "right_fit_one_page": (right.get("fit_result") or {}).get(
                "fit_one_page"
            ),
        },
        "identical_projects": (
            stable_content_fingerprint(left_effective["projects"])
            == stable_content_fingerprint(right_effective["projects"])
        ),
        "identical_skills": (
            stable_content_fingerprint(left_effective["skills"])
            == stable_content_fingerprint(right_effective["skills"])
        ),
    }
