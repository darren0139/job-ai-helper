"""V2.7 read-only pre-generation view of the production combined-source allocator.

Clicking to inspect never invokes a paid model or changes saved generation state.
"""
from __future__ import annotations
from typing import Any


def preview_mixed_allocation(
    *, candidates: list[dict[str, Any]], stable_analysis: dict[str, Any],
    selected_count: int, allocation_mode: str, max_bullets_per_project: int,
) -> dict[str, Any]:
    from tailoring.stable_tailoring_ranking import (
        rank_projects_deterministically, select_complementary_projects,
        build_low_confidence_project_selection,
    )
    from tailoring.project_section_tailor import _select_candidates_from_ranking
    from tailoring.deterministic_bullet_allocation import (
        build_deterministic_bullet_allocation,
    )
    from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
    from tailoring.combined_project_bullet_sources_v2_7 import (
        source_bullet_records, bullet_sources,
    )
    neutral = [{"title": c.get("title") or c.get("display_title"),
                "display_title": c.get("display_title") or c.get("title"),
                "final_score": 0, "requirement_matches": [],
                "matched_jd_requirements": [], "transferable_jd_requirements": []}
               for c in candidates]
    ranked, _ = rank_projects_deterministically(
        ranked_rows=neutral, project_candidates=candidates, stable_analysis=stable_analysis)
    ranked, _ = select_complementary_projects(
        ranked_rows=ranked, selected_count=selected_count)
    low = build_low_confidence_project_selection(ranked_rows=ranked, selected_count=selected_count)
    count = int(low.get("selected_project_count", 0) or 0)
    pairs = _select_candidates_from_ranking(
        ranked_rows=ranked, project_candidates=candidates, selected_count=count)
    plan = build_deterministic_bullet_allocation(
        selected_pairs=pairs, max_bullets_per_project=max_bullets_per_project,
        allocation_mode=allocation_mode)
    project_plans = plan.get("projects", [])
    if len(pairs) != len(project_plans):
        raise ValueError("Selection preview allocation identity mismatch")
    trace = plan.get("selection_trace") or []
    result = []
    for (candidate, ranking), choice in zip(pairs, project_plans, strict=True):
        bullet_pool = source_bullet_records(candidate)
        selected = choice.get("allocated_blueprint_bullets", [])
        from_base = sum(bullet_sources(candidate, text) == ["base"] for text in selected)
        from_library = sum(bullet_sources(candidate, text) == ["library"] for text in selected)
        shared = sum(set(bullet_sources(candidate, text)) == {"base", "library"} for text in selected)
        reason_by_text = {row.get("bullet_text"): row.get("reason") for row in trace
                          if row.get("project_id") == choice.get("project_id")}
        priorities = build_bullet_evidence_priorities(
            bullets=[row["text"] for row in bullet_pool], ranking_row=ranking)
        priority_by_text = {row.get("bullet_text", "").casefold(): row for row in priorities}
        matches = {str(m.get("requirement_id")): m for m in ranking.get("requirement_matches", [])
                   if isinstance(m, dict) and m.get("requirement_id")}
        def why(text: str) -> dict[str, Any]:
            point = priority_by_text.get(text.casefold()) or {}
            support = []
            for reqid in point.get("supported_requirement_ids", []) or []:
                m = matches.get(str(reqid))
                if m:
                    support.append({"id":str(reqid), "label":str(m.get("match_label") or "none"),
                                    "requirement":str(m.get("requirement_text") or "")})
            return {"jd_support": support, "priority": point.get("evidence_value", 0)}
        result.append({
            "title": candidate.get("display_title") or candidate.get("title"),
            "score": ranking.get("final_score", 0),
            "base_count": len((candidate.get("resume_evidence") or {}).get("bullets") or []),
            "library_count": len((candidate.get("evidence_library_evidence") or {}).get("bullets") or []),
            "selected_base": from_base, "selected_library": from_library,
            "selected_shared": shared,
            "eligible": bullet_pool,
            "selected": [{"text": text, "sources": bullet_sources(candidate, text),
                           "reason": reason_by_text.get(text, "Allocated by deterministic bullet policy"),
                           **why(text)} for text in selected],
        })
    return {"projects": result, "provisional": bool(low.get("active")),
            "source_policy_version": plan.get("source_policy_version"),
            "allocation_version": plan.get("allocation_version")}


def render_combined_evidence_preview(
    st: Any, *, application_id: int, candidates: list[dict[str, Any]],
    stable_analysis: dict[str, Any], selected_count: int,
    allocation_mode: str, max_bullets_per_project: int,
    source_note: str = "",
) -> bool:
    with st.expander("Before generation — Base + Library project-bullet selection (V2.7)", expanded=False):
        st.caption("Both Base and Library bullets are now eligible. This read-only estimate uses the JD analysis, not paid project-scoring results; final selections can differ. It does not certify the best possible résumé.")
        if source_note:
            st.caption("Source: " + source_note)
        if not st.checkbox("Inspect mixed-source allocation for the selected projects", value=False,
                           key=f"phase9f_v27_preview_enable_{application_id}"):
            return False
        try:
            view = preview_mixed_allocation(
                candidates=candidates, stable_analysis=stable_analysis,
                selected_count=selected_count, allocation_mode=allocation_mode,
                max_bullets_per_project=max_bullets_per_project)
        except (ValueError, TypeError, KeyError) as exc:
            st.warning("Preview withheld: " + str(exc))
            return False
        rows = view["projects"]
        if not rows:
            st.info("No selected projects available in the saved JD preview.")
            return False
        if view["provisional"]:
            st.warning("Fallback project slots are provisional. Confirm any fallback selection separately before generation.")
        import pandas as pd
        names = []
        for row in rows:
            names.append({"Inspect": False, "Project": row["title"],
                          "Provisional rank": row["score"], "Base bullets": row["base_count"],
                          "Library bullets": row["library_count"],
                          "Base-only used": row["selected_base"],
                          "Library-only used": row["selected_library"],
                          "Shared used": row["selected_shared"],
                          "Chosen total": len(row["selected"])})
        frozen_columns = [name for name in names[0] if name != "Inspect"]
        chosen = st.data_editor(pd.DataFrame(names), hide_index=True, width="stretch",
                                disabled=frozen_columns, num_rows="fixed",
                                key=f"phase9f_v27_project_inspect_{application_id}")
        inspected = [rows[i] for i, flag in enumerate(chosen["Inspect"].tolist()) if flag]
        if not inspected:
            st.caption("Tick Inspect for one or more projects in the table to see complete bullet wording and selection reasons.")
        for row in inspected:
            st.markdown("**" + str(row["title"]) + "**")
            selected_text = {x["text"].casefold() for x in row["selected"]}
            for item in row["eligible"]:
                chosen_label = "Selected" if item["text"].casefold() in selected_text else "Not allocated"
                selected_detail = next((s for s in row["selected"]
                                       if s["text"].casefold() == item["text"].casefold()), None)
                reason_codes = {
                    "minimum_project_coverage": "Chosen as this project's highest-priority first bullet",
                    "baseline_budget": "Added within the balanced bullet budget using marginal JD support",
                    "all_canonical_before_fitting_fill": "Included for consideration before one-page fitting",
                    "prefer_available_evidence_fill": "Included using available evidence; fitting may still reduce it",
                }
                if selected_detail is None:
                    reason = "Not allocated within the current budget; no evidence-quality inferiority is proven"
                else:
                    raw_reason = str(selected_detail["reason"])
                    reason = reason_codes.get(raw_reason, raw_reason.replace("_", " ").capitalize())
                    support = selected_detail.get("jd_support") or []
                    if support:
                        reason += ". Saved JD signals: " + "; ".join(
                            f"{x['label']} ({x['id']}) {x['requirement']}" for x in support)
                    else:
                        reason += ". No bullet-level canonical JD support recorded; this is not a JD match claim"
                with st.container(border=True):
                    st.write("**" + chosen_label + "** · " + ", ".join(item["sources"]))
                    st.write(item["text"])
                    st.caption(str(reason))
                    if selected_detail is not None and item["sources"] == ["base"]:
                        st.caption("Base-only source: preserved exactly from the confirmed résumé, but factual claims are not independently revalidated by this preview.")
        st.caption("Selection is a bounded JD-coverage decision, not proof of globally best résumé wording. Fitting and Phase 8 must still verify the actual final document.")
    return True
