"""One requirement / one bullet adapter over relevance, rephrase and Phase 8."""
from __future__ import annotations

from copy import deepcopy

from ai_providers import (
    CONFIGURED_LLM_PROVIDER,
    RewriteContract,
    create_rewrite_provider,
)
from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION, build_deterministic_keyword_match,
)
from llm import ask_json
from tailoring.candidate_context import build_generation_candidate_context, context_fingerprint
from tailoring.capability_taxonomy import get_default_taxonomy
from tailoring.fresh_target_evidence_scoring import build_fresh_target_analysis
from tailoring.jd_specific_rephrase_preview import (
    build_rephrase_preview_context, build_rephrased_generation_candidate,
    validate_rephrase_suggestion,
)
from tailoring.phase8_claim_lineage import audit_claim_lineage_v2
from tailoring.phase8_score_explainability import build_score_breakdown
from tailoring.phase8_verification import (
    build_final_resume_profile, build_resume_text_from_profile, compare_stable_analyses,
)
from tailoring.stable_tailoring_ranking import (
    PROJECT_RELEVANCE_METADATA_VERSION, build_candidate_evidence_profile,
    rank_projects_deterministically,
)

BULLET_TAILORING_VERSION = "evidence-grounded-bullet-tailoring-v1.6-providers"
_LABEL_ORDER = {"none": 0, "weak": 1, "transferable": 2, "direct": 3}
_IMPORTANCE_ORDER = {"required": 0, "core": 1, "preferred": 2}


def _normalise_evidence_text(value: object) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip().lower()


def _report_authority_identity(report: dict) -> dict:
    """Fingerprint only report facts that can change tailoring authority.

    Volatile bookkeeping such as API-cost summaries, timestamps, summaries, and
    other UI/debug fields must not invalidate a generated preview between the
    Generate and explicit Apply clicks.
    """
    stable = report.get("stable_analysis") or {}
    return {
        "raw_jd_text": str(report.get("raw_jd_text") or ""),
        "jd_profile": deepcopy(report.get("jd_profile") or {}),
        "resume_profile": deepcopy(report.get("resume_profile") or {}),
        "stable_analysis": {
            "scoring_version": stable.get("scoring_version"),
            "capability_taxonomy_version": stable.get("capability_taxonomy_version"),
            "input_fingerprint": stable.get("input_fingerprint", ""),
            "canonical_requirements": deepcopy(stable.get("canonical_requirements") or []),
        },
    }
def _rank(pool: list[dict], requirements: list[dict]) -> list[dict]:
    rows, _ = rank_projects_deterministically(
        ranked_rows=[{"title": p["title"], "display_title": p.get("display_title", p["title"])} for p in pool],
        project_candidates=pool,
        stable_analysis={"canonical_requirements": requirements},
    )
    return rows


def _single_record_project(_project: dict, text: str) -> dict:
    # The probe must represent exactly one evidence row. An opaque title keeps
    # the real project title from becoming a second evidence source during the
    # deterministic support check.
    return {
        "title": "Selected Evidence Record",
        "display_title": "Selected Evidence Record",
        "resume_evidence": {"bullets": [text]},
        "currently_in_resume": True,
    }


def _relationship(row: dict, requirement_id: str) -> dict:
    return next(r for r in row["project_relevance"]["requirement_relationships"]
                if r["requirement_id"] == requirement_id)


def _grounded_records(project: dict, requirement: dict, relationship: dict) -> list[dict]:
    """Return only single evidence rows that independently support a requirement."""
    records: list[dict] = []
    if relationship["match_label"] not in {"direct", "transferable"}:
        return records
    for record in project["project_relevance"]["supporting_evidence_records"]:
        if (record["evidence_id"] not in relationship["supporting_evidence_ids"]
                or record.get("kind") not in {"bullet", "description", "impact"}
                or len(record.get("text", "")) > 1600):
            continue
        single = _rank([_single_record_project(project, record["text"])], [requirement])[0]
        single_relationship = _relationship(single, requirement["requirement_id"])
        if single_relationship["match_label"] in {"direct", "transferable"}:
            records.append({**deepcopy(record), "support_label": single_relationship["match_label"]})
    records.sort(key=lambda row: row["evidence_id"])
    return records


def _resolve_bullet_source_records(*, source_records: list[dict],
                                   current_bullet: str, canonical_bullet: str) -> tuple[list[dict], dict]:
    """Resolve one draft bullet to exactly one frozen bullet evidence row.

    The immutable selected/canonical bullet is the primary source identity. The
    current wording is only a fallback for legacy drafts where canonical source
    text is unavailable. Resolution is exact-text only and restricted to frozen
    bullet records. It never pairs evidence-library and resume rows by list
    position, because those lists are not guaranteed to be parallel.
    """
    canonical_text = _normalise_evidence_text(canonical_bullet)
    current_text = _normalise_evidence_text(current_bullet)
    lookup_text = canonical_text or current_text
    if not lookup_text:
        return [], {
            "method": "unresolved",
            "source_bullet_index": None,
            "source_evidence_ids": [],
        }

    exact = [
        deepcopy(record)
        for record in source_records
        if str(record.get("kind") or "").lower() == "bullet"
        and _normalise_evidence_text(record.get("text")) == lookup_text
    ]
    if not exact and canonical_text and current_text and current_text != canonical_text:
        exact = [
            deepcopy(record)
            for record in source_records
            if str(record.get("kind") or "").lower() == "bullet"
            and _normalise_evidence_text(record.get("text")) == current_text
        ]

    if not exact:
        return [], {
            "method": "unresolved",
            "source_bullet_index": None,
            "source_evidence_ids": [],
        }

    source_priority = {"resume": 0, "evidence_library": 1, "combined": 2}
    exact.sort(key=lambda row: (
        source_priority.get(str(row.get("source") or "").lower(), 9),
        str(row.get("evidence_id") or ""),
    ))
    selected = exact[0]
    return [selected], {
        "method": "exact_frozen_bullet_evidence",
        "source_bullet_index": None,
        "source_evidence_ids": [selected.get("evidence_id")],
    }


def _source_records_supporting_requirement(*, source_records: list[dict],
                                           source_project: dict, requirement: dict,
                                           relationship: dict, current_bullet: str,
                                           canonical_bullet: str) -> tuple[list[dict], dict]:
    """Resolve the bullet source first, then score only that same frozen row."""
    resolved, mapping = _resolve_bullet_source_records(
        source_records=source_records,
        current_bullet=current_bullet,
        canonical_bullet=canonical_bullet,
    )
    if not resolved:
        return [], mapping

    relationship_label = str(relationship.get("match_label") or "none").lower()
    supported: list[dict] = []
    for record in resolved:
        label = _probe_bullet_support(
            source_project=source_project,
            requirement=requirement,
            bullet_text=record.get("text", ""),
        )
        if label not in {"direct", "transferable"}:
            continue
        # Never let a same-row probe exceed the already-authoritative project
        # relationship ceiling for this requirement.
        if _LABEL_ORDER.get(label, 0) > _LABEL_ORDER.get(relationship_label, 0):
            label = relationship_label
        if label in {"direct", "transferable"}:
            supported.append({**deepcopy(record), "support_label": label})
    return supported, mapping


def _probe_bullet_support(*, source_project: dict, requirement: dict, bullet_text: str) -> str:
    """Return deterministic support for exactly one current bullet wording."""
    probe_text = str(bullet_text or "")
    if not probe_text:
        return "none"
    probe = _rank([_single_record_project(source_project, probe_text)], [requirement])[0]
    return str(_relationship(probe, requirement["requirement_id"]).get("match_label") or "none")


def _support_ceiling(records: list[dict]) -> str:
    """Return the strongest label independently supported by one frozen source row."""
    labels = [str(row.get("support_label") or "none").lower() for row in records]
    return max(labels or ["none"], key=lambda label: _LABEL_ORDER.get(label, -1))


def _promotion_available(current_label: str, ceiling_label: str) -> bool:
    """True only when a rewrite can deterministically improve the target match label."""
    return _LABEL_ORDER.get(str(ceiling_label or "none").lower(), 0) > _LABEL_ORDER.get(
        str(current_label or "none").lower(), 0
    )


def _resolve_frozen_source_candidate(*, pool: list[dict], ranked_project: dict) -> dict | None:
    """Recover the raw frozen candidate behind one ranked project row.

    Ranked rows own relevance metadata, but may omit the nested source payloads
    needed for exact provenance bridging. Recover those facts from the original
    frozen candidate pool using exact title/display-title identity only.
    """
    ranked_keys = {
        _normalise_evidence_text(ranked_project.get("title")),
        _normalise_evidence_text(ranked_project.get("display_title")),
    }
    ranked_keys.discard("")
    if not ranked_keys:
        return None

    matches: list[dict] = []
    for candidate in pool:
        candidate_keys = {
            _normalise_evidence_text(candidate.get("title")),
            _normalise_evidence_text(candidate.get("display_title")),
        }
        candidate_keys.discard("")
        if ranked_keys.intersection(candidate_keys):
            matches.append(candidate)

    return matches[0] if len(matches) == 1 else None


def prepare_bullet_target(*, generation: dict, report: dict, project_index: int,
                          bullet_index: int, requirement_id: str) -> dict:
    """Rebuild authority from frozen facts; never trust model or saved debug labels."""
    if generation.get("status") != "draft":
        raise ValueError("Create an editable draft before tailoring a bullet.")
    analysis = report.get("stable_analysis") or {}
    if (analysis.get("scoring_version") != SCORING_VERSION or
            analysis.get("capability_taxonomy_version") != get_default_taxonomy().version):
        raise ValueError("Current scoring/taxonomy analysis is required.")
    requirements = analysis.get("canonical_requirements") or []
    matches = [r for r in requirements if r.get("requirement_id") == requirement_id]
    if len(matches) != 1:
        raise ValueError("Select exactly one current canonical requirement.")
    context = build_rephrase_preview_context(
        generation=generation, baseline_report=report,
        project_index=project_index, bullet_index=bullet_index,
    )
    pool = generation.get("candidate_pool") or []
    if not isinstance(pool, list) or not pool:
        raise ValueError("Frozen candidate evidence is unavailable; regenerate a draft with source evidence.")
    evidence_profile = build_candidate_evidence_profile(pool)
    evidence_projects = {
        str(row.get("project_id") or ""): row
        for row in evidence_profile.get("projects", []) or []
    }
    ranked = _rank(pool, requirements)
    candidates = [r for r in ranked if r.get("project_id") == context["project_id"]]
    if len(candidates) != 1:
        raise ValueError("The selected project cannot be resolved to one frozen source identity.")
    project = candidates[0]
    source_evidence_project = evidence_projects.get(str(context["project_id"]))
    if source_evidence_project is None:
        raise ValueError("Frozen source evidence records are unavailable for the selected project.")
    relationship = _relationship(project, requirement_id)
    current_match_label = _probe_bullet_support(
        source_project=project,
        requirement=matches[0],
        bullet_text=context.get("current_bullet", ""),
    )
    records, source_mapping = _source_records_supporting_requirement(
        source_records=source_evidence_project.get("evidence_records", []) or [],
        source_project=project,
        requirement=matches[0],
        relationship=relationship,
        current_bullet=context.get("current_bullet", ""),
        canonical_bullet=context.get("canonical_bullet", ""),
    )
    safe_evidence_ceiling = _support_ceiling(records)
    promotion_records = [
        record for record in records
        if _promotion_available(current_match_label, record.get("support_label", "none"))
    ]
    deterministic_promotion_available = bool(promotion_records)
    # Only frozen source facts, never the current analysis or model claims,
    # form the source-context identity. Existing evidence IDs are preserved.
    source_context = build_generation_candidate_context(generation)
    identity = {
        "policy_version": BULLET_TAILORING_VERSION,
        "relevance_metadata_version": PROJECT_RELEVANCE_METADATA_VERSION,
        "scoring_version": SCORING_VERSION,
        "taxonomy_version": get_default_taxonomy().version,
        "generation_fingerprint": context_fingerprint(generation),
        "report_fingerprint": context_fingerprint(_report_authority_identity(report)),
        "source_context_fingerprint": source_context["context_fingerprint"],
        "requirement_id": requirement_id,
        "project_index": project_index, "bullet_index": bullet_index,
    }
    if deterministic_promotion_available:
        status = "ready"
        reason = "Grounded single-row evidence can improve the deterministic target match"
        gap_actions = []
    elif records:
        status = "already_at_ceiling"
        reason = "Current bullet is already at the strongest match supported by its frozen source evidence"
        gap_actions = []
    else:
        status = "unsupported"
        reason = "No sufficient evidence found"
        gap_actions = ["Add evidence", "Review Candidate Context", "Treat as evidence/learning gap"]
    return {
        "status": status,
        "reason": reason,
        "gap_actions": gap_actions,
        "identity": identity, "target_fingerprint": context_fingerprint(identity),
        "requirement": deepcopy(matches[0]), "relationship": deepcopy(relationship),
        "project_id": context["project_id"], "project_title": context["project_title"],
        "current_bullet": context["current_bullet"],
        "canonical_bullet": context.get("canonical_bullet", ""),
        "source_mapping": source_mapping,
        "current_match_label": current_match_label,
        "safe_evidence_ceiling": safe_evidence_ceiling,
        "deterministic_promotion_available": deterministic_promotion_available,
        "candidate_context": source_context,
        "evidence_records": promotion_records if deterministic_promotion_available else records,
        "model_call_count": 0,
    }


def list_grounded_bullet_opportunities(*, generation: dict, report: dict) -> dict:
    """Build a deterministic project-first view of valid one-bullet targets.

    Only combinations that can pass the existing evidence gate are returned.
    Unsupported requirements are intentionally kept out of the primary UI so
    users never have to guess which project/requirement combinations are valid.

    Diagnostic metadata is descriptive only. It explains why a selected project
    or current bullet was not offered without weakening the evidence gate.
    """
    if generation.get("status") != "draft":
        raise ValueError("Create an editable draft before tailoring a bullet.")
    analysis = report.get("stable_analysis") or {}
    if (analysis.get("scoring_version") != SCORING_VERSION or
            analysis.get("capability_taxonomy_version") != get_default_taxonomy().version):
        raise ValueError("Current scoring/taxonomy analysis is required.")
    requirements = analysis.get("canonical_requirements") or []
    projects = (generation.get("projects") or {}).get("recommended_projects") or []
    pool = generation.get("candidate_pool") or []
    if not isinstance(pool, list) or not pool:
        raise ValueError("Frozen candidate evidence is unavailable; regenerate a draft with source evidence.")
    ranked = _rank(pool, requirements)
    by_project_id = {str(row.get("project_id") or ""): row for row in ranked}
    evidence_profile = build_candidate_evidence_profile(pool)
    evidence_by_project_id = {
        str(row.get("project_id") or ""): row
        for row in evidence_profile.get("projects", []) or []
    }
    requirement_by_id = {str(row.get("requirement_id") or ""): row for row in requirements}
    supported_requirement_ids: set[str] = set()
    project_rows: list[dict] = []

    for project_index, selected_project in enumerate(projects):
        project_id = str(selected_project.get("project_id") or "")
        source_project = by_project_id.get(project_id)
        source_evidence_project = evidence_by_project_id.get(project_id)
        bullet_rows: list[dict] = []
        already_strong_bullet_rows: list[dict] = []
        bullet_checks: list[dict] = []
        project_supported: list[dict] = []
        project_relationships: dict[str, dict] = {}
        relevance_basis = ((source_project or {}).get("project_relevance") or {}).get("relevance_basis")

        if source_project is not None:
            project_relationships = {
                str(row.get("requirement_id") or ""): row
                for row in source_project["project_relevance"]["requirement_relationships"]
                if row.get("match_label") in {"direct", "transferable"}
            }
            project_supported = [
                {
                    "requirement_id": rid,
                    "text": requirement_by_id.get(rid, {}).get("text", ""),
                    "importance": requirement_by_id.get(rid, {}).get("importance", ""),
                    "match_label": relationship.get("match_label", ""),
                    "supporting_evidence_ids": list(relationship.get("supporting_evidence_ids") or []),
                }
                for rid, relationship in project_relationships.items()
                if rid in requirement_by_id
            ]
            project_supported.sort(key=lambda row: (
                _IMPORTANCE_ORDER.get(str(row.get("importance") or "").lower(), 9),
                str(row.get("text") or "").lower(),
                str(row.get("requirement_id") or ""),
            ))
            relevant_requirements = [
                requirement_by_id[rid]
                for rid in project_relationships
                if rid in requirement_by_id
            ]
            for bullet_index, _ in enumerate(selected_project.get("draft_bullets") or []):
                context = build_rephrase_preview_context(
                    generation=generation, baseline_report=report,
                    project_index=project_index, bullet_index=bullet_index,
                )
                canonical = str(context.get("canonical_bullet") or "")
                requirement_rows: list[dict] = []
                already_strong_rows: list[dict] = []
                probe_checks: list[dict] = []
                if canonical and relevant_requirements:
                    for requirement in relevant_requirements:
                        rid = str(requirement["requirement_id"])
                        current_match_label = _probe_bullet_support(
                            source_project=source_project,
                            requirement=requirement,
                            bullet_text=context.get("current_bullet", ""),
                        )
                        records, source_mapping = _source_records_supporting_requirement(
                            source_records=(source_evidence_project or {}).get("evidence_records", []) or [],
                            source_project=source_project,
                            requirement=requirement,
                            relationship=project_relationships[rid],
                            current_bullet=context.get("current_bullet", ""),
                            canonical_bullet=canonical,
                        )
                        safe_evidence_ceiling = _support_ceiling(records)
                        promotion_records = [
                            record for record in records
                            if _promotion_available(
                                current_match_label, record.get("support_label", "none")
                            )
                        ]
                        promotion_available = bool(promotion_records)
                        grounded = bool(records)
                        if not records:
                            reason = "current_bullet_not_exactly_mapped_to_frozen_supporting_evidence"
                        elif promotion_available:
                            reason = "score_improvement_available"
                        else:
                            reason = "already_at_evidence_supported_ceiling"
                        probe_checks.append({
                            "requirement_id": rid,
                            "text": requirement.get("text", ""),
                            "project_match_label": project_relationships[rid].get("match_label", ""),
                            "bullet_probe_match_label": current_match_label,
                            "current_match_label": current_match_label,
                            "safe_evidence_ceiling": safe_evidence_ceiling,
                            "deterministic_promotion_available": promotion_available,
                            "exact_evidence_ids": [record.get("evidence_id") for record in records],
                            "promotion_evidence_ids": [
                                record.get("evidence_id") for record in promotion_records
                            ],
                            "source_mapping_method": source_mapping.get("method"),
                            "source_bullet_index": source_mapping.get("source_bullet_index"),
                            "source_evidence_ids": list(source_mapping.get("source_evidence_ids") or []),
                            "grounded_source_mapping": grounded,
                            "eligible": promotion_available,
                            "reason": reason,
                        })
                        if not grounded:
                            continue
                        supported_requirement_ids.add(rid)
                        row = {
                            "requirement_id": rid,
                            "text": requirement.get("text", ""),
                            "importance": requirement.get("importance", ""),
                            "capability_id": requirement.get("capability_id"),
                            "match_label": current_match_label,
                            "current_match_label": current_match_label,
                            "safe_evidence_ceiling": safe_evidence_ceiling,
                            "deterministic_promotion_available": promotion_available,
                            "evidence_records": promotion_records if promotion_available else records,
                        }
                        if promotion_available:
                            requirement_rows.append(row)
                        else:
                            already_strong_rows.append(row)
                requirement_rows.sort(key=lambda row: (
                    _IMPORTANCE_ORDER.get(str(row.get("importance") or "").lower(), 9),
                    str(row.get("text") or "").lower(),
                    str(row.get("requirement_id") or ""),
                ))
                already_strong_rows.sort(key=lambda row: (
                    _IMPORTANCE_ORDER.get(str(row.get("importance") or "").lower(), 9),
                    str(row.get("text") or "").lower(),
                    str(row.get("requirement_id") or ""),
                ))
                bullet_checks.append({
                    "bullet_index": bullet_index,
                    "current_bullet": context.get("current_bullet", ""),
                    "canonical_bullet": canonical,
                    "canonical_bullet_available": bool(canonical),
                    "requirement_checks": probe_checks,
                    "grounded_requirement_ids": [
                        row["requirement_id"] for row in requirement_rows + already_strong_rows
                    ],
                    "eligible_requirement_ids": [
                        row["requirement_id"] for row in requirement_rows
                    ],
                    "score_improving_requirement_ids": [
                        row["requirement_id"] for row in requirement_rows
                    ],
                    "already_strong_requirement_ids": [
                        row["requirement_id"] for row in already_strong_rows
                    ],
                })
                if requirement_rows:
                    bullet_rows.append({
                        "bullet_index": bullet_index,
                        "current_bullet": context["current_bullet"],
                        "canonical_bullet": context["canonical_bullet"],
                        "requirements": requirement_rows,
                    })
                if already_strong_rows:
                    already_strong_bullet_rows.append({
                        "bullet_index": bullet_index,
                        "current_bullet": context["current_bullet"],
                        "canonical_bullet": context["canonical_bullet"],
                        "requirements": already_strong_rows,
                    })

        draft_bullets = selected_project.get("draft_bullets") or []
        has_exact_mapping_mismatch = any(
            check.get("reason") == "current_bullet_not_exactly_mapped_to_frozen_supporting_evidence"
            for bullet in bullet_checks
            for check in bullet.get("requirement_checks") or []
        )
        if source_project is None:
            diagnostic_code = "frozen_source_project_missing"
            diagnostic_message = (
                "The selected project could not be resolved to one frozen source project, "
                "so tailoring is disabled rather than guessing."
            )
        elif relevance_basis == "deterministic_fallback_suitability_only":
            diagnostic_code = "fallback_only"
            diagnostic_message = (
                "This project was selected as a fallback and has no proven JD coverage. "
                "Rewriting cannot manufacture missing evidence."
            )
        elif bullet_rows:
            diagnostic_code = "ready"
            diagnostic_message = "At least one current bullet has a deterministic score-improving rewrite opportunity."
        elif already_strong_bullet_rows:
            diagnostic_code = "already_at_ceiling"
            diagnostic_message = (
                "This project has grounded JD coverage, but its mapped bullets are already at the "
                "strongest deterministic match supported by their frozen evidence."
            )
        elif not project_relationships:
            diagnostic_code = "no_grounded_project_relationship"
            diagnostic_message = (
                "No direct or transferable JD relationship is grounded for this project."
            )
        elif not draft_bullets:
            diagnostic_code = "no_current_draft_bullets"
            diagnostic_message = (
                "The project has grounded JD coverage, but there are no current draft bullets to improve."
            )
        elif has_exact_mapping_mismatch:
            diagnostic_code = "supported_project_but_no_exact_bullet_evidence"
            diagnostic_message = (
                "This project has grounded JD coverage, but its current draft bullets do not map "
                "exactly to the frozen supporting evidence. Tailoring stays disabled rather than "
                "borrowing evidence from a different source row."
            )
        else:
            diagnostic_code = "supported_project_but_no_eligible_current_bullet"
            diagnostic_message = (
                "This project has grounded JD coverage, but no current bullet independently supports "
                "one of those requirements strongly enough for a safe rewrite."
            )

        project_rows.append({
            "project_index": project_index,
            "project_id": project_id,
            "title": selected_project.get("display_title") or selected_project.get("title") or "Untitled project",
            "relevance_basis": relevance_basis,
            "bullets": bullet_rows,
            "already_strong_bullets": already_strong_bullet_rows,
            "diagnostic": {
                "code": diagnostic_code,
                "message": diagnostic_message,
                "project_supported_requirements": project_supported,
                "bullet_checks": bullet_checks,
            },
        })

    unavailable = [
        {
            "requirement_id": row.get("requirement_id"),
            "text": row.get("text", ""),
            "importance": row.get("importance", ""),
        }
        for row in requirements
        if str(row.get("requirement_id") or "") not in supported_requirement_ids
    ]
    unavailable.sort(key=lambda row: (
        _IMPORTANCE_ORDER.get(str(row.get("importance") or "").lower(), 9),
        str(row.get("text") or "").lower(),
    ))
    return {
        "projects": project_rows,
        "unavailable_requirements": unavailable,
        "opportunity_count": sum(
            len(bullet["requirements"])
            for project in project_rows for bullet in project["bullets"]
        ),
        "already_strong_count": sum(
            len(bullet["requirements"])
            for project in project_rows for bullet in project.get("already_strong_bullets") or []
        ),
    }


def _bounded_context(target: dict, record: dict) -> dict:
    # Existing preview guards must see only the selected evidence as authority.
    return {"canonical_bullet": record["text"], "current_bullet": record["text"],
            "frozen_project_evidence": [record["text"]],
            "raw_jd_text": target["requirement"]["text"]}


def build_grounded_baseline_suggestion(
    *, generation: dict, report: dict, project_index: int, bullet_index: int,
    requirement_id: str, evidence_id: str,
) -> dict:
    """Build the zero-model safe baseline from one exact frozen evidence row.

    The selected frozen evidence text itself is the candidate wording. The
    existing deterministic verifier and explicit Apply lifecycle remain the
    final authority for both deterministic and AI-polished candidates.
    """
    target = prepare_bullet_target(
        generation=generation,
        report=report,
        project_index=project_index,
        bullet_index=bullet_index,
        requirement_id=requirement_id,
    )
    if target["status"] != "ready":
        return {**target, "model_call_count": 0}

    record = next(
        (r for r in target["evidence_records"] if r["evidence_id"] == evidence_id),
        None,
    )
    if record is None:
        raise ValueError(
            "Select one evidence ID from this requirement's frozen context."
        )

    return {
        "status": "grounded_baseline",
        "suggestion_kind": "deterministic_grounded_source",
        "target_fingerprint": target["target_fingerprint"],
        "project_index": project_index,
        "bullet_index": bullet_index,
        "requirement_id": requirement_id,
        "selected_evidence_id": evidence_id,
        "response": {
            "target_requirement_id": requirement_id,
            "project_id": target["project_id"],
            "bullet_index": bullet_index,
            "candidate_bullet": record["text"],
            "evidence_ids": [evidence_id],
        },
        "model": "deterministic-grounded-source",
        "model_call_count": 0,
    }


def suggest_grounded_bullet(
    *, generation: dict, report: dict, project_index: int,
    bullet_index: int, requirement_id: str, evidence_id: str,
    model: str, provider: str = CONFIGURED_LLM_PROVIDER,
) -> dict:
    """Request one optional wording polish through an explicit rewrite provider.

    Provider output never controls target identity. Requirement/project/bullet
    identity is reconstructed deterministically from the frozen target before
    the existing verifier sees the suggestion.
    """
    target = prepare_bullet_target(
        generation=generation,
        report=report,
        project_index=project_index,
        bullet_index=bullet_index,
        requirement_id=requirement_id,
    )
    if target["status"] != "ready":
        return {**target, "model_call_count": 0}

    record = next(
        (r for r in target["evidence_records"] if r["evidence_id"] == evidence_id),
        None,
    )
    if record is None:
        raise ValueError(
            "Select one evidence ID from this requirement's frozen context."
        )

    contract = RewriteContract(
        target_requirement_id=requirement_id,
        project_id=target["project_id"],
        bullet_index=bullet_index,
        current_bullet=target["current_bullet"],
        grounded_baseline=record["text"],
        target_requirement=target["requirement"]["text"],
        evidence_id=evidence_id,
        evidence_record=deepcopy(record),
        required_ceiling=record["support_label"],
    )
    writer = create_rewrite_provider(
        provider,
        model=model,
        ask_json_fn=ask_json,
    )
    result = writer.polish(contract)

    # Do not trust a writer with target identity. Only candidate wording and the
    # selected evidence-ID echo cross the provider boundary.
    response = {
        "target_requirement_id": requirement_id,
        "project_id": target["project_id"],
        "bullet_index": bullet_index,
        "candidate_bullet": result.candidate_bullet,
        "evidence_ids": result.evidence_ids,
    }
    return {
        "status": "ai_polish",
        "suggestion_kind": "ai_polish",
        "target_fingerprint": target["target_fingerprint"],
        "project_index": project_index,
        "bullet_index": bullet_index,
        "requirement_id": requirement_id,
        "selected_evidence_id": evidence_id,
        "response": response,
        "model": result.model,
        "provider": result.provider_id,
        "provider_metadata": deepcopy(result.metadata),
        "model_call_count": int(result.call_count),
    }


def _score_generation(report: dict, generation: dict) -> dict:
    profile = build_final_resume_profile(report.get("resume_profile") or {}, generation)
    text = build_resume_text_from_profile(profile)
    rows = report["stable_analysis"]["canonical_requirements"]
    keyword = build_deterministic_keyword_match(requirements=rows, acronym_map={},
        resume_profile=profile, raw_resume_text=text)
    analysis = build_fresh_target_analysis(jd_profile=deepcopy(report.get("jd_profile") or {}),
        raw_jd_text=report.get("raw_jd_text", ""), keyword_match=keyword,
        resume_profile=profile, raw_resume_text=text, retrieval_mode_override="lexical")
    if {r["requirement_id"] for r in analysis["canonical_requirements"]} != {r["requirement_id"] for r in rows}:
        raise ValueError("Fresh scoring could not reproduce the exact canonical requirement scope.")
    return analysis


def evaluate_grounded_bullet(*, generation: dict, report: dict, suggestion: dict) -> dict:
    target = prepare_bullet_target(generation=generation, report=report,
        project_index=suggestion["project_index"], bullet_index=suggestion["bullet_index"],
        requirement_id=suggestion["requirement_id"])
    errors = []
    if target["status"] != "ready" or target["target_fingerprint"] != suggestion.get("target_fingerprint"):
        errors.append("stale_or_unsupported_context")
    response = suggestion.get("response") or {}
    if not isinstance(response, dict) or not isinstance(response.get("candidate_bullet"), str):
        return {"safe_to_apply": False, "reasons": ["malformed_response"], "target": target}
    evidence_id = suggestion.get("selected_evidence_id")
    record = next((r for r in target["evidence_records"] if r["evidence_id"] == evidence_id), None)
    if (record is None or response.get("evidence_ids") != [evidence_id]
            or response.get("target_requirement_id") != suggestion["requirement_id"]
            or response.get("project_id") != target["project_id"]
            or response.get("bullet_index") != suggestion["bullet_index"]):
        errors.append("response_identity_outside_selected_context")
    if errors:
        return {"safe_to_apply": False, "reasons": errors, "target": target}
    bullet = response.get("candidate_bullet")
    guard = validate_rephrase_suggestion(context=_bounded_context(target, record), suggested_bullet=bullet)
    errors.extend(guard["guard_reasons"])
    # Reuse the rephrase novelty detector conservatively: even one unsupported
    # material term cannot gain authority from the JD or the current draft.
    if guard["unsupported_material_tokens"]:
        errors.append("unsupported_material_claim")
    bounded_project = {"project_id": target["project_id"], "title": target["project_title"],
                       "draft_bullets": [bullet]}
    bounded = {"projects": {"recommended_projects": [bounded_project]},
               "candidate_pool": [{"project_id": target["project_id"],
                   "title": target["project_title"], "evidence_records": [record]}]}
    lineage = audit_claim_lineage_v2({}, bounded)
    if lineage["claim_review_required_count"]:
        errors.append("claim_lineage_failed")
    projected = _rank([_single_record_project({"title": target["project_title"]}, str(bullet or ""))],
                      [target["requirement"]])[0]
    if _LABEL_ORDER[_relationship(projected, suggestion["requirement_id"])["match_label"]] > _LABEL_ORDER[record["support_label"]]:
        errors.append("support_ceiling_exceeded")
    if errors:
        return {"safe_to_apply": False, "reasons": sorted(set(errors)), "claim_lineage": lineage, "target": target}
    proposed = build_rephrased_generation_candidate(generation=generation,
        project_index=suggestion["project_index"], bullet_index=suggestion["bullet_index"], accepted_bullet=bullet)
    # Compare like-for-like unfitted structured output. Historical fit content
    # belongs to its original source version, not this wording preview.
    current = deepcopy(generation)
    current.update(fit_result=None, docx_path="", pdf_path="")
    before, after = _score_generation(report, current), _score_generation(report, proposed)
    comparison = compare_stable_analyses(before, after)
    if comparison["important_regressions"] or not comparison["canonical_requirement_ids_stable"]:
        errors.append("protected_requirement_regression")
    rid = suggestion["requirement_id"]
    left = next(r for r in before["canonical_requirements"] if r["requirement_id"] == rid)
    right = next(r for r in after["canonical_requirements"] if r["requirement_id"] == rid)
    before_points = next(r for r in build_score_breakdown(before)["requirements"] if r["requirement_id"] == rid)
    after_points = next(r for r in build_score_breakdown(after)["requirements"] if r["requirement_id"] == rid)
    return {"safe_to_apply": not errors, "reasons": errors, "target": target,
            "claim_lineage": lineage, "comparison": comparison,
            "target_before": left, "target_after": right,
            "target_points_before": before_points, "target_points_after": after_points,
            "target_improved": float(right.get("match_value", 0)) > float(left.get("match_value", 0)),
            "proposed_generation": proposed}


def apply_grounded_bullet(*, application_id: int, source_generation_id: str, suggestion: dict) -> dict:
    """Explicit Apply only: reload, revalidate, then use the existing draft lifecycle."""
    from database import phase9f_tailoring_execution_manager as manager
    source = manager.get_tailoring_generation(application_id, source_generation_id)
    application = manager.db_manager.get_application_by_id(application_id)
    if source is None or not application:
        raise ValueError("The source application/draft is unavailable.")
    report = application["report"]
    if source.get("phase9e_decision_fingerprint"):
        from database.application_blueprint_manager import resolve_current_phase9e_generation_context
        scope = resolve_current_phase9e_generation_context(application_id)
        if (not scope.get("can_generate") or
                (scope.get("binding_identity") or {}).get("decision_fingerprint") != source["phase9e_decision_fingerprint"]):
            raise ValueError("The source draft is outside the current application scope.")
        report = scope["effective_report"]
    evaluation = evaluate_grounded_bullet(generation=source, report=report, suggestion=suggestion)
    if not evaluation["safe_to_apply"]:
        raise ValueError("Apply blocked: " + ", ".join(evaluation["reasons"]))
    return manager.create_application_jd_rephrase_generation(
        application_id=application_id, source_generation_id=source_generation_id,
        project_index=suggestion["project_index"], bullet_index=suggestion["bullet_index"],
        accepted_bullet=suggestion["response"]["candidate_bullet"],
        suggestion_model=suggestion.get("model", ""),
        suggestion_payload={"policy_version": BULLET_TAILORING_VERSION,
                            "request": suggestion, "evaluation": {k: v for k, v in evaluation.items() if k != "proposed_generation"}},
    )
