"""Evidence-grounded Job Finder matching using the existing stable scorer."""

from __future__ import annotations

from typing import Any, Callable

from tailoring.candidate_context import build_candidate_context, context_fingerprint

from database.job_match_manager import (
    get_job_match_snapshot,
    get_latest_job_match_snapshot,
    save_job_match_snapshot,
)


MATCH_VERSION = "job-match-snapshot-v2.0.1"
IMPORTANT_IMPORTANCE = {"deal_breaker", "required", "core"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def fingerprint_evidence_items(
    evidence_items: list[dict[str, Any]] | None,
) -> str:
    """Fingerprint only evidence fields that can affect matching/provenance.

    Presentation-only fields and updated_at are intentionally excluded so
    cosmetic edits do not invalidate a cached match.
    """
    # Keep the canonical supported-field boundary and provenance. Timestamp
    # edits alone must still leave Job Match snapshots current.
    rows = [
        {key: value for key, value in item.items()
         if key not in {"created_at", "updated_at", "display_title"}}
        for item in (evidence_items or []) if isinstance(item, dict)
    ]
    return context_fingerprint(build_candidate_context({}, rows))


def _description_lines(value: Any) -> list[str]:
    output: list[str] = []
    for raw in str(value or "").splitlines():
        cleaned = raw.strip().lstrip("•-* ").strip()
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output


def build_profile_evidence_context(
    evidence_items: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Convert the canonical Profile & Evidence library into scorer inputs.

    Projects and internships become structured resume-profile records. Skills
    and tools are also exposed as structured skill rows. Every evidence item is
    represented in raw_resume_text so coursework/certifications/other truthful
    evidence remains eligible without pretending it was employment.
    """
    candidate_context = build_candidate_context(
        {}, [row for row in (evidence_items or []) if isinstance(row, dict)]
    )
    # This is only a scorer input projection of canonical evidence, not a
    # separate source of candidate truth or an inferred employment history.
    items = candidate_context["evidence_library"]
    resume_profile: dict[str, Any] = {
        "education": [],
        "experience": [],
        "projects": [],
        "skills": {},
    }
    raw_lines: list[str] = []

    for item in items:
        item_id = int(item.get("id", 0) or 0)
        category = _clean(item.get("category"))
        title = _clean(item.get("title"))
        subtitle = _clean(item.get("subtitle"))
        period = _clean(item.get("period"))
        description_lines = _description_lines(item.get("description"))
        for field in ("canonical_bullets", "bullets"):
            for bullet in item.get(field, []) or []:
                for line in _description_lines(bullet):
                    if line not in description_lines:
                        description_lines.append(line)
        impact_lines = _description_lines(item.get("impact"))
        bullets = list(description_lines)
        for line in impact_lines:
            if line not in bullets:
                bullets.append(line)

        heading = " — ".join(part for part in (title, subtitle, period) if part)
        if heading:
            raw_lines.append(heading)
        raw_lines.extend(description_lines)
        raw_lines.extend(impact_lines)

        skills = [_clean(v) for v in item.get("skills", []) or [] if _clean(v)]
        tools = [_clean(v) for v in item.get("tools", []) or [] if _clean(v)]
        if skills:
            resume_profile["skills"][f"evidence_{item_id}_skills"] = skills
            raw_lines.extend(skills)
        if tools:
            resume_profile["skills"][f"evidence_{item_id}_tools"] = tools
            raw_lines.extend(tools)

        if category.casefold() == "project":
            resume_profile["projects"].append(
                {
                    "title": title,
                    "company": subtitle,
                    "date": period,
                    "bullets": bullets,
                }
            )
        elif category.casefold() == "internship":
            resume_profile["experience"].append(
                {
                    "title": title,
                    "company": subtitle,
                    "date": period,
                    "bullets": bullets,
                }
            )
        elif category.casefold() == "skill" and title:
            resume_profile["skills"].setdefault(
                f"evidence_{item_id}_claims",
                [],
            ).append(title)

    deduped_raw: list[str] = []
    seen: set[str] = set()
    for line in raw_lines:
        cleaned = _clean(line)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            deduped_raw.append(cleaned)

    return {
        "candidate_context": candidate_context,
        "evidence_items": items,
        "evidence_item_count": len(items),
        "evidence_fingerprint": fingerprint_evidence_items(items),
        "resume_profile": resume_profile,
        "raw_resume_text": "\n".join(deduped_raw),
    }


def current_evidence_context() -> dict[str, Any]:
    """Load the complete Profile & Evidence library, not the paginated UI list."""
    from database.user_profile_manager import get_all_evidence_items_for_snapshot

    return build_profile_evidence_context(
        get_all_evidence_items_for_snapshot()
    )


def current_match_versions() -> dict[str, str]:
    from analysis_stability.stable_evidence_scoring import SCORING_VERSION
    from tailoring.capability_taxonomy import get_default_taxonomy

    return {
        "match_version": MATCH_VERSION,
        "scoring_version": str(SCORING_VERSION),
        "taxonomy_version": str(get_default_taxonomy().version),
    }


def _default_extract_jd_profile(jd_text: str) -> dict[str, Any]:
    # Lazy import: merely browsing/searching Job Finder must never make a model call.
    from analyzer import extract_jd_profile

    return extract_jd_profile(jd_text)


def _default_stable_builder(
    *,
    raw_jd_text: str,
    jd_profile: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Run the shared deterministic matcher after the existing JD extractor."""
    from analysis_stability.stable_evidence_scoring import (
        build_deterministic_keyword_match,
        build_stable_analysis,
        canonicalise_requirements,
    )

    canonical = canonicalise_requirements(
        jd_profile=jd_profile,
        raw_jd_text=raw_jd_text,
    )
    keyword_match = build_deterministic_keyword_match(
        requirements=canonical.get("requirements", []) or [],
        acronym_map=canonical.get("acronym_map", {}) or {},
        resume_profile=context.get("resume_profile") or {},
        raw_resume_text=str(context.get("raw_resume_text") or ""),
    )
    return build_stable_analysis(
        jd_profile=jd_profile,
        keyword_match=keyword_match,
        raw_jd_text=raw_jd_text,
        raw_resume_text=str(context.get("raw_resume_text") or ""),
        resume_profile=context.get("resume_profile") or {},
        bullet_quality_score=0,
        structure_score=0,
    )


def summarize_stable_match(
    stable_analysis: dict[str, Any],
) -> dict[str, Any]:
    from analysis_stability.stable_evidence_scoring import requirement_is_score_eligible

    rows = [
        row
        for row in stable_analysis.get("canonical_requirements", []) or []
        if isinstance(row, dict) and requirement_is_score_eligible(row)
    ]
    important_gaps: list[dict[str, Any]] = []
    all_gaps: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("match_label") or "none").lower() != "none":
            continue
        gap = {
            "requirement_id": _clean(row.get("requirement_id")),
            "text": _clean(row.get("atomic_focus") or row.get("text")),
            "importance": _clean(row.get("importance")),
            "capability_id": _clean(
                row.get("capability_id")
                or row.get("taxonomy_capability_id")
                or row.get("canonical_capability_id")
            ),
        }
        all_gaps.append(gap)
        if gap["importance"].lower() in IMPORTANT_IMPORTANCE:
            important_gaps.append(gap)

    counts = {
        label: sum(
            1
            for row in rows
            if str(row.get("match_label") or "none").lower() == label
        )
        for label in ("direct", "transferable", "weak", "none")
    }

    return {
        "deterministic_alignment_score": int(
            stable_analysis.get("deterministic_alignment_score", 0) or 0
        ),
        "alignment_band": _clean(stable_analysis.get("alignment_band")),
        "required_core_coverage_score": int(
            stable_analysis.get("required_core_coverage_score", 0) or 0
        ),
        "preferred_coverage_score": int(
            stable_analysis.get("preferred_coverage_score", 0) or 0
        ),
        "evidence_strength_score": int(
            stable_analysis.get("evidence_strength_score", 0) or 0
        ),
        "requirement_count": len(rows),
        "direct_requirement_count": counts["direct"],
        "transferable_requirement_count": counts["transferable"],
        "weak_requirement_count": counts["weak"],
        "unmatched_requirement_count": counts["none"],
        "important_gap_count": len(important_gaps),
        "important_gaps": important_gaps[:12],
        "all_gaps": all_gaps[:30],
        "score_interpretation": _clean(
            stable_analysis.get("score_interpretation")
        ),
    }


def _identity(
    job: dict[str, Any],
    context: dict[str, Any],
    versions: dict[str, str],
) -> dict[str, Any]:
    return {
        "discovered_job_id": int(job.get("id", 0) or 0),
        "job_content_hash": _clean(job.get("content_hash")),
        "evidence_fingerprint": str(context.get("evidence_fingerprint") or ""),
        "match_version": str(versions.get("match_version") or MATCH_VERSION),
        "scoring_version": str(versions.get("scoring_version") or ""),
        "taxonomy_version": str(versions.get("taxonomy_version") or ""),
    }


def inspect_job_match(
    job: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    context = context or current_evidence_context()
    versions = versions or current_match_versions()
    identity = _identity(job, context, versions)

    current = get_job_match_snapshot(**identity)
    if current is not None:
        return {
            "status": "current",
            "snapshot": current,
            "stale_reasons": [],
            "identity": identity,
        }

    latest = get_latest_job_match_snapshot(identity["discovered_job_id"])
    if latest is None:
        return {
            "status": "none",
            "snapshot": None,
            "stale_reasons": [],
            "identity": identity,
        }

    stale_reasons: list[str] = []
    comparisons = (
        ("job_content_hash", "job description changed"),
        ("evidence_fingerprint", "Profile & Evidence changed"),
        ("match_version", "job-match pipeline changed"),
        ("scoring_version", "stable scoring version changed"),
        ("taxonomy_version", "capability taxonomy changed"),
    )
    for field, reason in comparisons:
        if str(latest.get(field) or "") != str(identity.get(field) or ""):
            stale_reasons.append(reason)

    return {
        "status": "stale",
        "snapshot": latest,
        "stale_reasons": stale_reasons or ["cache identity changed"],
        "identity": identity,
    }


def analyze_job_match(
    job: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    versions: dict[str, str] | None = None,
    jd_profile_extractor: Callable[[str], dict[str, Any]] | None = None,
    stable_builder: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Analyze one discovered job and persist/reuse its deterministic snapshot.

    The default JD extractor is the existing two-pass model-backed extractor.
    Everything after extraction uses the existing deterministic stable scorer.
    Tests can inject an extractor/builder, so unit tests never require a model.
    """
    context = context or current_evidence_context()
    versions = versions or current_match_versions()
    identity = _identity(job, context, versions)

    if identity["discovered_job_id"] <= 0:
        raise ValueError("A persisted discovered job ID is required.")
    if not identity["job_content_hash"]:
        raise ValueError("The discovered job has no content_hash.")
    if int(context.get("evidence_item_count", 0) or 0) <= 0:
        raise ValueError(
            "Profile & Evidence is empty. Add truthful evidence before analyzing job fit."
        )

    raw_jd_text = str(job.get("description") or "").strip()
    if len(raw_jd_text) < 100:
        raise ValueError("The normalized job description is too short to analyze reliably.")

    cached = get_job_match_snapshot(**identity)
    if cached is not None:
        return {
            "cache_hit": True,
            "snapshot": cached,
            "identity": identity,
        }

    extractor = jd_profile_extractor or _default_extract_jd_profile
    builder = stable_builder or _default_stable_builder

    jd_profile = extractor(raw_jd_text)
    if not isinstance(jd_profile, dict) or not jd_profile:
        raise RuntimeError("JD extraction returned an empty profile.")

    stable_analysis = builder(
        raw_jd_text=raw_jd_text,
        jd_profile=jd_profile,
        context=context,
    )
    if not isinstance(stable_analysis, dict) or not stable_analysis:
        raise RuntimeError("Stable job matching returned no analysis.")

    summary = summarize_stable_match(stable_analysis)
    snapshot = save_job_match_snapshot(
        **identity,
        jd_profile=jd_profile,
        evidence_snapshot=context.get("evidence_items", []) or [],
        stable_analysis=stable_analysis,
        summary=summary,
    )
    return {
        "cache_hit": False,
        "snapshot": snapshot,
        "identity": identity,
    }
