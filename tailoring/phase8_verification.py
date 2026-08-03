"""Phase 8 deterministic before/after verification for tailored résumés."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from analysis_stability import build_stable_analysis
from analysis_stability.stable_evidence_scoring import SCORING_VERSION
from tailoring.phase8_requirement_reconciliation import (
    reconcile_final_requirement_matches,
)
from tailoring.phase8_claim_lineage import (
    audit_claim_lineage_v2,
)
from tailoring.tailoring_generation_fingerprint import (
    get_effective_generation_sections,
)


PHASE8_VERIFICATION_VERSION = "phase8-before-after-verification-v7"
PHASE8_BASELINE_RESOLUTION_VERSION = "phase8-current-scorer-baseline-v1"
MATCH_RANK = {
    "none": 0,
    "weak": 1,
    "transferable": 2,
    "direct": 3,
}
IMPORTANT_REQUIREMENTS = {"deal_breaker", "required", "core"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def _normalise_multiline_text(value: Any) -> str:
    # Normalise line endings without collapsing JD section boundaries.
    text = (
        str(value or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u00a0", " ")
    )
    lines = [line.rstrip() for line in text.split("\n")]

    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)


def _normalise(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return " ".join(text.split())


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in _normalise(value).split()
        if len(token) >= 2
    }


def _similarity(left: Any, right: Any) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    return max(
        overlap / len(left_tokens | right_tokens),
        overlap / min(len(left_tokens), len(right_tokens)),
    )


def _project_title(project: dict[str, Any]) -> str:
    return _clean(
        project.get("display_title")
        or project.get("title")
        or "Untitled Project"
    )


def _project_bullets(project: dict[str, Any]) -> list[str]:
    for key in (
        "draft_bullets",
        "rewritten_bullets",
        "bullets",
        "allocated_blueprint_bullets",
    ):
        values = project.get(key)
        if isinstance(values, list):
            cleaned = [_clean(value) for value in values if _clean(value)]
            if cleaned:
                return cleaned
    return []


def _effective_projects(
    generation_state: dict[str, Any],
) -> list[dict[str, Any]]:
    effective = get_effective_generation_sections(generation_state)
    projects = effective.get("projects")
    if not isinstance(projects, dict):
        return []
    return [
        project
        for project in projects.get("recommended_projects", []) or []
        if isinstance(project, dict)
    ]


def _effective_skill_lines(
    generation_state: dict[str, Any],
) -> list[dict[str, Any]]:
    effective = get_effective_generation_sections(generation_state)
    skills = effective.get("skills")
    if not isinstance(skills, dict):
        return []
    return [
        line
        for line in skills.get("skill_lines", []) or []
        if isinstance(line, dict)
    ]


def build_final_resume_profile(
    baseline_resume_profile: dict[str, Any] | None,
    generation_state: dict[str, Any],
) -> dict[str, Any]:
    """Overlay the generation's final fitted Projects and Skills."""
    profile = deepcopy(baseline_resume_profile or {})

    profile["projects"] = [
        {
            "title": _project_title(project),
            "date": _clean(
                project.get("period")
                or project.get("date")
            ),
            "bullets": _project_bullets(project),
        }
        for project in _effective_projects(generation_state)
    ]

    skills: dict[str, list[str]] = {}
    for line in _effective_skill_lines(generation_state):
        category = _clean(line.get("category")) or "Uncategorised"
        values = [
            _clean(value)
            for value in line.get("items", []) or []
            if _clean(value)
        ]
        if values:
            skills[category] = values
    profile["skills"] = skills
    return profile


def build_resume_text_from_profile(
    profile: dict[str, Any],
) -> str:
    """Create deterministic evidence text from the final structured profile."""
    lines: list[str] = []

    summary = _clean(profile.get("summary"))
    if summary:
        lines.append(summary)

    for education in profile.get("education", []) or []:
        if not isinstance(education, dict):
            continue
        lines.append(
            " — ".join(
                value
                for value in (
                    _clean(education.get("degree")),
                    _clean(education.get("school")),
                    _clean(education.get("graduation_date")),
                )
                if value
            )
        )
        lines.extend(
            _clean(value)
            for value in education.get("courses", []) or []
            if _clean(value)
        )

    for field_name in ("experience", "projects"):
        for item in profile.get(field_name, []) or []:
            if not isinstance(item, dict):
                continue
            lines.append(
                " — ".join(
                    value
                    for value in (
                        _clean(item.get("title")),
                        _clean(item.get("company")),
                        _clean(item.get("date")),
                    )
                    if value
                )
            )
            lines.extend(
                _clean(value)
                for value in item.get("bullets", []) or []
                if _clean(value)
            )

    skills = profile.get("skills", {}) or {}
    if isinstance(skills, dict):
        for category, values in skills.items():
            cleaned = [
                _clean(value)
                for value in values or []
                if _clean(value)
            ]
            if cleaned:
                lines.append(f"{_clean(category)}: {', '.join(cleaned)}")

    return "\n".join(line for line in lines if line)


def _baseline_keyword_rows(
    baseline_report: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    keyword_match = baseline_report.get("keyword_match", {}) or {}
    present = [
        deepcopy(row)
        for row in keyword_match.get("present", []) or []
        if isinstance(row, dict)
    ]
    missing = [
        deepcopy(row)
        for row in keyword_match.get("missing", []) or []
        if isinstance(row, dict)
    ]
    return present, missing


def _generation_requirement_rows(
    generation_state: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for project in _effective_projects(generation_state):
        bullets = _project_bullets(project)
        fallback_evidence = bullets[0] if bullets else _project_title(project)
        for match in project.get("requirement_matches", []) or []:
            if not isinstance(match, dict):
                continue
            label = _clean(match.get("match_label")).lower()
            if label not in {"direct", "transferable", "weak"}:
                continue
            snippets = [
                _clean(value)
                for value in match.get("evidence_snippets", []) or []
                if _clean(value)
            ]
            rows.append(
                {
                    "keyword": _clean(
                        match.get("requirement_text")
                        or match.get("keyword")
                    ),
                    "category": "phase8_generation_evidence",
                    "importance": _clean(
                        match.get("importance")
                    ) or "core",
                    "found_in": "projects",
                    "matched_resume_term": (
                        snippets[0]
                        if snippets
                        else fallback_evidence
                    ),
                    "match_type": label,
                    "evidence_type": label,
                    "match_reason": (
                        "Phase 8 reused the generation's deterministic "
                        "requirement-to-project evidence mapping."
                    ),
                }
            )
    return rows


def build_verification_keyword_match(
    baseline_report: dict[str, Any],
    generation_state: dict[str, Any],
) -> dict[str, Any]:
    """Build conservative match proposals without making a model call."""
    present, missing = _baseline_keyword_rows(baseline_report)
    present.extend(_generation_requirement_rows(generation_state))

    deduped_present: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in present:
        key = (
            _normalise(row.get("keyword")),
            _normalise(row.get("matched_resume_term")),
            _normalise(row.get("match_type")),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped_present.append(row)

    return {
        "present": deduped_present,
        "missing": missing,
        "verification_source": (
            "baseline_match_proposals_plus_generation_requirement_mappings"
        ),
    }


def compare_stable_analyses(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Compare canonical requirement labels using stable requirement IDs."""
    before_rows = {
        str(row.get("requirement_id") or ""): row
        for row in before.get("canonical_requirements", []) or []
        if isinstance(row, dict)
    }
    after_rows = {
        str(row.get("requirement_id") or ""): row
        for row in after.get("canonical_requirements", []) or []
        if isinstance(row, dict)
    }

    improved: list[dict[str, Any]] = []
    regressed: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []

    for requirement_id in sorted(set(before_rows) | set(after_rows)):
        left = before_rows.get(requirement_id)
        right = after_rows.get(requirement_id)
        if left is None and right is not None:
            added.append(right)
            continue
        if right is None and left is not None:
            removed.append(left)
            continue
        if left is None or right is None:
            continue

        before_label = _clean(left.get("match_label")).lower() or "none"
        after_label = _clean(right.get("match_label")).lower() or "none"
        row = {
            "requirement_id": requirement_id,
            "requirement": _clean(
                right.get("text")
                or left.get("text")
            ),
            "importance": _clean(
                right.get("importance")
                or left.get("importance")
            ),
            "before_label": before_label,
            "after_label": after_label,
            "before_evidence_strength": int(
                left.get("evidence_strength", 0) or 0
            ),
            "after_evidence_strength": int(
                right.get("evidence_strength", 0) or 0
            ),
        }
        before_rank = MATCH_RANK.get(before_label, 0)
        after_rank = MATCH_RANK.get(after_label, 0)
        if after_rank > before_rank:
            improved.append(row)
        elif after_rank < before_rank:
            regressed.append(row)
        else:
            unchanged.append(row)

    important_regressions = [
        row
        for row in regressed
        if row.get("importance") in IMPORTANT_REQUIREMENTS
    ]

    before_score = int(
        before.get("deterministic_alignment_score", 0) or 0
    )
    after_score = int(
        after.get("deterministic_alignment_score", 0) or 0
    )

    return {
        "before_score": before_score,
        "after_score": after_score,
        "score_delta": after_score - before_score,
        "before_band": before.get("alignment_band", ""),
        "after_band": after.get("alignment_band", ""),
        "required_core_coverage_delta": int(
            after.get("required_core_coverage_score", 0) or 0
        ) - int(
            before.get("required_core_coverage_score", 0) or 0
        ),
        "preferred_coverage_delta": int(
            after.get("preferred_coverage_score", 0) or 0
        ) - int(
            before.get("preferred_coverage_score", 0) or 0
        ),
        "evidence_strength_delta": int(
            after.get("evidence_strength_score", 0) or 0
        ) - int(
            before.get("evidence_strength_score", 0) or 0
        ),
        "improved_requirements": improved,
        "regressed_requirements": regressed,
        "important_regressions": important_regressions,
        "unchanged_requirement_count": len(unchanged),
        "added_requirements": added,
        "removed_requirements": removed,
        "canonical_requirement_ids_stable": not added and not removed,
    }


def audit_claim_lineage(
    baseline_resume_profile: dict[str, Any] | None,
    generation_state: dict[str, Any],
) -> dict[str, Any]:
    # Verify final claims through stable identity and lineage metadata.
    return audit_claim_lineage_v2(
        baseline_resume_profile,
        generation_state,
    )


def build_current_baseline_analysis(
    *,
    baseline_report: dict[str, Any],
    raw_jd_text: str,
) -> dict[str, Any]:
    """Re-score the original résumé with the currently installed scorer."""
    baseline_profile = deepcopy(
        baseline_report.get("resume_profile", {}) or {}
    )
    baseline_resume_text = build_resume_text_from_profile(
        baseline_profile
    )
    baseline_keyword_match = deepcopy(
        baseline_report.get("keyword_match", {}) or {}
    )

    return build_stable_analysis(
        jd_profile=baseline_report.get("jd_profile", {}) or {},
        keyword_match=baseline_keyword_match,
        raw_jd_text=raw_jd_text,
        raw_resume_text=baseline_resume_text,
        resume_profile=baseline_profile,
        bullet_quality_score=(
            baseline_report.get("bullets", {}) or {}
        ).get("bullet_quality_avg", 0),
        structure_score=(
            baseline_report.get("structure", {}) or {}
        ).get("structure_score", 0),
    )


def resolve_phase8_baseline_analysis(
    *,
    baseline_report: dict[str, Any],
    raw_jd_text: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a baseline compatible with the current stable scorer."""
    stored = baseline_report.get("stable_analysis")
    if not isinstance(stored, dict):
        raise ValueError(
            "The application does not contain a stable baseline analysis."
        )

    stored_version = _clean(stored.get("scoring_version"))
    can_reuse = bool(
        stored_version
        and stored_version == SCORING_VERSION
    )

    if can_reuse:
        resolved = deepcopy(stored)
        mode = "reused_current_stored_baseline"
        rebuilt = False
    else:
        resolved = build_current_baseline_analysis(
            baseline_report=baseline_report,
            raw_jd_text=raw_jd_text,
        )
        mode = "rebuilt_with_current_scorer"
        rebuilt = True

    stored_requirements = (
        stored.get("canonical_requirements", []) or []
    )
    resolved_requirements = (
        resolved.get("canonical_requirements", []) or []
    )

    metadata = {
        "baseline_resolution_version": (
            PHASE8_BASELINE_RESOLUTION_VERSION
        ),
        "mode": mode,
        "rebuilt": rebuilt,
        "stored_scoring_version": stored_version,
        "current_scoring_version": SCORING_VERSION,
        "resolved_scoring_version": _clean(
            resolved.get("scoring_version")
        ),
        "stored_input_fingerprint": _clean(
            stored.get("input_fingerprint")
        ),
        "resolved_input_fingerprint": _clean(
            resolved.get("input_fingerprint")
        ),
        "stored_requirement_count": len(stored_requirements),
        "resolved_requirement_count": len(
            resolved_requirements
        ),
    }
    return resolved, metadata

def _verification_fingerprint(
    baseline_report: dict[str, Any],
    generation_state: dict[str, Any],
    raw_jd_text: str,
) -> str:
    effective = get_effective_generation_sections(generation_state)
    baseline_requirements = (
        baseline_report.get("stable_analysis", {}) or {}
    ).get("canonical_requirements", []) or []
    baseline_requirement_ids = sorted(
        str(row.get("requirement_id") or "")
        for row in baseline_requirements
        if isinstance(row, dict) and row.get("requirement_id")
    )
    payload = {
        "phase8_version": PHASE8_VERIFICATION_VERSION,
        "baseline_resolution_version": (
            PHASE8_BASELINE_RESOLUTION_VERSION
        ),
        "current_stable_scoring_version": SCORING_VERSION,
        "baseline_stable_fingerprint": (
            baseline_report.get("stable_analysis", {}) or {}
        ).get("input_fingerprint", ""),
        "baseline_requirement_ids": baseline_requirement_ids,
        "raw_jd_sha256": hashlib.sha256(
            _normalise_multiline_text(raw_jd_text).encode("utf-8")
        ).hexdigest(),
        "generation_id": generation_state.get("generation_id", ""),
        "generation_updated_at": generation_state.get("updated_at", ""),
        "fit_result": generation_state.get("fit_result"),
        "projects": effective.get("projects"),
        "skills": effective.get("skills"),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()



def refresh_phase8_readiness(
    result: dict[str, Any],
    generation_state: dict[str, Any],
) -> dict[str, Any]:
    """Refresh mutable Phase 8 lifecycle gates without rerunning analysis.

    The deterministic comparison and evidence audit remain cached. Approval and
    blueprint readiness are derived from the current saved generation each time.
    """
    refreshed = deepcopy(result)

    status = (
        _clean(generation_state.get("status")).lower()
        or "draft"
    )
    fit_result = generation_state.get("fit_result")
    if not isinstance(fit_result, dict):
        fit_result = {}

    comparison = refreshed.get("comparison")
    if not isinstance(comparison, dict):
        comparison = {}

    lineage = refreshed.get("claim_lineage")
    if not isinstance(lineage, dict):
        lineage = {}

    comparison_valid = bool(
        refreshed.get(
            "comparison_valid",
            comparison.get(
                "canonical_requirement_ids_stable",
                False,
            ),
        )
    )
    important_regressions = (
        comparison.get("important_regressions", []) or []
    )
    claim_risks = int(
        lineage.get("claim_review_required_count", 0) or 0
    )
    score_delta = int(
        comparison.get("score_delta", 0) or 0
    )
    fit_one_page = fit_result.get("fit_one_page") is True
    approved = status == "approved"

    reasons = {
        "is_approved": approved,
        "fits_one_page": fit_one_page,
        "canonical_requirement_ids_stable": comparison_valid,
        "no_required_core_regression": (
            comparison_valid and not important_regressions
        ),
        "no_claim_review_risks": claim_risks == 0,
        "score_not_lower": score_delta >= 0,
    }

    refreshed["generation_status"] = status
    refreshed["fit_one_page"] = fit_one_page
    refreshed["page_count"] = fit_result.get(
        "page_count",
        refreshed.get("page_count"),
    )
    refreshed["blueprint_readiness_reasons"] = reasons
    refreshed["blueprint_ready"] = all(
        bool(value) for value in reasons.values()
    )
    return refreshed


def build_phase8_verification(
    *,
    baseline_report: dict[str, Any],
    generation_state: dict[str, Any],
    raw_jd_text: str,
) -> dict[str, Any]:
    """Verify one fitted generation without making any model/API call."""
    stored_before = baseline_report.get("stable_analysis")
    if not isinstance(stored_before, dict):
        raise ValueError(
            "The application does not contain a stable baseline analysis."
        )

    fit_result = generation_state.get("fit_result")
    if not isinstance(fit_result, dict):
        raise ValueError(
            "Generate and fit the selected version before Phase 8 verification."
        )

    canonical_jd_text = _normalise_multiline_text(raw_jd_text)
    if not canonical_jd_text:
        raise ValueError(
            "Phase 8 requires the application's original job-description text. "
            "The comparison was stopped instead of rebuilding a different "
            "canonical requirement set."
        )

    before, baseline_resolution = (
        resolve_phase8_baseline_analysis(
            baseline_report=baseline_report,
            raw_jd_text=canonical_jd_text,
        )
    )

    final_profile = build_final_resume_profile(
        baseline_report.get("resume_profile", {}),
        generation_state,
    )
    final_resume_text = build_resume_text_from_profile(final_profile)
    verification_keyword_match = build_verification_keyword_match(
        baseline_report,
        generation_state,
    )

    after = build_stable_analysis(
        jd_profile=baseline_report.get("jd_profile", {}) or {},
        keyword_match=verification_keyword_match,
        raw_jd_text=canonical_jd_text,
        raw_resume_text=final_resume_text,
        resume_profile=final_profile,
        bullet_quality_score=(
            baseline_report.get("bullets", {}) or {}
        ).get("bullet_quality_avg", 0),
        structure_score=(
            baseline_report.get("structure", {}) or {}
        ).get("structure_score", 0),
    )
    raw_comparison = compare_stable_analyses(before, after)
    lineage = audit_claim_lineage(
        baseline_report.get("resume_profile", {}),
        generation_state,
    )
    after, reconciliation = reconcile_final_requirement_matches(
        before_analysis=before,
        after_analysis=after,
        generation_state=generation_state,
        claim_lineage=lineage,
    )
    comparison = compare_stable_analyses(before, after)

    important_regressions = comparison["important_regressions"]
    claim_risks = int(
        lineage.get("claim_review_required_count", 0) or 0
    )
    score_delta = int(comparison.get("score_delta", 0) or 0)
    fit_one_page = fit_result.get("fit_one_page") is True
    approved = (
        _clean(generation_state.get("status")).lower()
        == "approved"
    )

    comparison_valid = bool(
        comparison.get("canonical_requirement_ids_stable")
    )

    if not comparison_valid:
        verdict = "invalid_canonical_mismatch"
        verdict_message = (
            "Verification stopped: the before and after analyses produced "
            "different canonical requirement IDs. The score delta is not a "
            "safe résumé-quality comparison."
        )
    elif important_regressions:
        verdict = "regression_detected"
        verdict_message = (
            "Required/core evidence regressed. Review the changed requirement "
            "rows before approving or promoting this version."
        )
    elif claim_risks:
        verdict = "review_required"
        verdict_message = (
            "No required/core regression was found, but some final claims need "
            "manual evidence-lineage review."
        )
    elif score_delta > 0:
        verdict = "improved"
        verdict_message = (
            "The deterministic role-alignment score improved without losing "
            "required/core evidence."
        )
    else:
        verdict = "maintained"
        verdict_message = (
            "The deterministic score was maintained without losing "
            "required/core evidence."
        )

    blueprint_ready = bool(
        approved
        and fit_one_page
        and comparison_valid
        and not important_regressions
        and claim_risks == 0
        and score_delta >= 0
    )

    return {
        "phase8_version": PHASE8_VERIFICATION_VERSION,
        "verification_mode": "zero_cost_deterministic",
        "verification_fingerprint": _verification_fingerprint(
            baseline_report,
            generation_state,
            canonical_jd_text,
        ),
        "comparison_valid": comparison_valid,
        "jd_text_source": "application_job_description",
        "baseline_resolution": baseline_resolution,
        "application_id": generation_state.get("application_id"),
        "generation_id": generation_state.get("generation_id", ""),
        "generation_status": generation_state.get("status", "draft"),
        "fit_one_page": fit_one_page,
        "page_count": fit_result.get("page_count"),
        "before_stable_analysis": before,
        "after_stable_analysis": after,
        "raw_comparison_before_reconciliation": raw_comparison,
        "comparison": comparison,
        "requirement_reconciliation": reconciliation,
        "claim_lineage": lineage,
        "verdict": verdict,
        "verdict_message": verdict_message,
        "blueprint_ready": blueprint_ready,
        "blueprint_readiness_reasons": {
            "is_approved": approved,
            "fits_one_page": fit_one_page,
            "canonical_requirement_ids_stable": comparison_valid,
            "no_required_core_regression": (
                comparison_valid and not important_regressions
            ),
            "no_claim_review_risks": claim_risks == 0,
            "score_not_lower": score_delta >= 0,
        },
        "canonical_requirement_guard": {
            "valid": comparison_valid,
            "added_requirement_count": len(
                comparison.get("added_requirements", []) or []
            ),
            "removed_requirement_count": len(
                comparison.get("removed_requirements", []) or []
            ),
            "action": (
                "compare_scores"
                if comparison_valid
                else "invalidate_score_delta"
            ),
        },
        "limitations": [
            (
                "When the saved baseline scoring version differs from the current "
                "stable scorer, Phase 8 deterministically rebuilds the original "
                "résumé baseline before comparing it with the final résumé."
            ),
            (
                "The comparison is valid only when the canonical requirement "
                "IDs are identical before and after. A mismatch invalidates the "
                "score delta and blocks blueprint readiness."
            ),
            (
                "This zero-cost verification reuses the original semantic "
                "match proposals and the generation's deterministic requirement "
                "mappings, then revalidates them against final evidence."
            ),
            (
                "When the raw final scorer reports a lower label, Phase 8 "
                "performs a conservative reconciliation pass. It restores "
                "credit only when unchanged source evidence or lineage-verified "
                "final project/skill evidence is still present."
            ),
            (
                "It is conservative and may miss a new non-technical semantic "
                "match that would require an optional AI recheck."
            ),
            (
                "Claim-lineage warnings require human review and are not proof "
                "that a statement is false."
            ),
        ],
    }
