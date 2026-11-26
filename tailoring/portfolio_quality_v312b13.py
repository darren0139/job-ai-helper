"""B1.3: depth-sensitive *real fitter* reduction ordering for Portfolio only.

Not a new scorer, not a shadow preview, and not a claim about individual
bullet scores. This selects one-step reduction candidates in the existing
one-page Word/PDF fitter. The fitter remains the layout authority and Phase 8
is the native requirement-level authority after generating the exact DOCX.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

VERSION = "portfolio-quality-v312b13-depth-sensitive-fitting-v1"
B1_PROVENANCE = "portfolio-quality-v312b1-fit-input-marginal-v1"


def _identity(project: dict[str, Any]) -> str:
    return str(project.get("project_id") or project.get("display_title") or project.get("title") or "").strip()


def _counts(payload: dict[str, Any] | None) -> dict[str, int] | None:
    if not isinstance(payload, dict):
        return None
    rows = payload.get("recommended_projects")
    if not isinstance(rows, list) or not rows:
        return None
    result: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            return None
        key = _identity(row)
        bullets = row.get("draft_bullets")
        if not key or key in result or not isinstance(bullets, list) or not bullets:
            return None
        if any(not isinstance(x, str) or not x.strip() for x in bullets):
            return None
        result[key] = len(bullets)
    return result


def _depth_cost(before: dict[str, int], after: dict[str, int]) -> tuple[int, dict[str, Any]] | None:
    """Bounded depth preference; never override the fitter's protection tiers."""
    if not set(after).issubset(before) or len(after) < 1:
        return None
    decrements = [(k,old,after.get(k,0)) for k,old in before.items() if old != after.get(k,0)]
    if len(decrements) != 1:
        return None  # Unexpected multi-project mutation: leave existing ordering.
    key,old,new = decrements[0]
    if new < 0 or old - new != 1:
        return None
    # Prefer a second substantive accomplishment across projects where the
    # original candidate tiers permit it. This preference is NOT a hard floor:
    # the one-page fitter can still remove a second bullet when necessary.
    loss = (
        2400 if new == 0 else
        1300 if old == 2 and new == 1 else
        350 if old == 3 and new == 2 else
        80 if old == 4 and new == 3 else
        0
    )
    return loss, {"project":key,"before":old,"after":new,
                  "would_leave_one_bullet":old==2 and new==1,
                  "would_drop_project":new==0}


def prioritize_portfolio_reductions(projects_state: dict[str, Any] | None,
                                    candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign depth-aware candidate order while preserving protection tiers.

    Called by the *actual one-page fitter* before its existing protection-tier
    group/sort and Word/PDF rendering. No new content, extra rendering budget,
    SQL updates or native score change. Fail closed if payload geometry shifts.
    """
    if (not isinstance(projects_state, dict)
            or projects_state.get("portfolio_quality_b1_active") != B1_PROVENANCE):
        return candidates
    before = _counts(projects_state)
    if before is None or not isinstance(candidates, list) or not candidates:
        return candidates
    # Any ambiguous candidate geometry holds the entire ordering unchanged;
    # we do not silently privilege one candidate using partial evidence.
    annotated = []
    for i,candidate in enumerate(candidates):
        if not isinstance(candidate,dict) or not isinstance(candidate.get("change"),dict):
            return candidates
        change=candidate["change"]
        section=str(change.get("section") or "projects")
        ctype=str(change.get("change_type") or "")
        base_loss=candidate.get("quality_loss")
        if not isinstance(base_loss,(int,float)) or isinstance(base_loss,bool) or base_loss < 0:
            return candidates
        cost=0;detail={"status":"UNCHANGED_NON_PROJECT"}
        if section=="projects" and ctype in ("remove_bullet","remove_project","bullet_fusion","compact_rewrite"):
            after=_counts(candidate.get("projects"))
            if after is None: return candidates
            if after==before:
                # Compaction can save space without deleting a bullet.
                detail={"status":"BULLET_DEPTH_UNCHANGED"}
            else:
                outcome=_depth_cost(before,after)
                if outcome is None:return candidates
                cost,details=outcome
                detail={"status":"BULLET_DEPTH_ADJUSTED",**details}
        elif section=="projects" and ctype:
            # Unknown future reduction type: retain native fitter order.
            return candidates
        annotated.append((i,candidate,int(base_loss)+cost,cost,detail))
    # Original groups are sorted by *candidate_order*, not quality_loss. For
    # B1.3, reorder using the depth-aware loss, then assign sequential order.
    # The existing group-by-protection-tier still happens *after* this, so no
    # strongly protected requirement can be bypassed by this preference.
    ranked=sorted(annotated,key=lambda r:(r[2],int(r[1].get("candidate_order",r[0]) or r[0]),r[0]))
    new=[]
    for rank,(index,row,adjusted,extra,detail) in enumerate(ranked,start=1):
        # B1.5: Phase 6C already constructed each candidate project state.
        # Reuse those immutable-for-ranking project/skill payloads; isolate
        # only the change receipt that this function actually annotates.
        updated=row.copy()
        updated["change"]=deepcopy(row["change"])
        updated["candidate_order"]=rank
        updated["quality_loss"]=adjusted
        updated["change"]["v312b13_depth_order"]={
            "version":VERSION,"original_candidate_index":index,
            "original_quality_loss":int(row["quality_loss"]),
            "depth_penalty":extra,"detail":detail,
            "no_native_score_claim":True,
        }
        new.append(updated)
    return new


def audit_portfolio_depth_after_fit(source_projects: dict[str, Any] | None,
                                    fit_result: dict[str, Any]) -> dict[str, Any]:
    """Compare actual DOCX B1 readback with fit-input depth, never proxies alone."""
    result={"version":VERSION,"status":"HOLD_NO_VERIFIED_FINAL_DOCX",
            "native_score_checked":False,"required_core_checked":False,
            "no_approval_or_scoring_claim":True}
    if not isinstance(fit_result,dict):return result
    audit=fit_result.get("portfolio_quality_b1_final_audit")
    if not isinstance(audit,dict) or not audit.get("is_actual_docx_readback") or not audit.get("exact_saved_fitted_bullets_match_docx"):
        return result
    if not fit_result.get("fit_one_page") or fit_result.get("page_count") != 1:
        return result
    source=_counts(source_projects)
    counts=audit.get("project_bullet_counts")
    if source is None or not isinstance(counts,dict) or not counts:
        return result
    source_rows=(source_projects or {}).get("recommended_projects") or []
    by_title={str(p.get("display_title") or p.get("title") or ""):len(p["draft_bullets"])
              for p in source_rows if isinstance(p,dict)}
    if len(by_title)!=len(source_rows):return result
    actual={str(k):int(v) for k,v in counts.items() if isinstance(v,int) and v>0}
    if actual!=counts or not set(actual).issubset(by_title):return result
    return {**result,"status":"OBSERVED_FINAL_DOCX_DEPTH", "project_count":len(actual),
            "pre_fit_project_bullet_counts":by_title,
            "final_docx_project_bullet_counts":actual,
            "one_bullet_projects":sorted(name for name,n in actual.items() if n==1),
            "one_bullet_project_count":sum(n==1 for n in actual.values()),
            "docx_sha256":audit.get("docx_sha256"),
            "measured_by":"actual_docx_b1_readback",
            "note":"Observed fitted depth; not an independent native score or alternative-DOCX comparison."}
