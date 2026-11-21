"""Read-only Phase 9F project bullet-source comparison.

Historical generation used Library-only bullet selection. V2.7 generations
include selected Base and Evidence Library bullets, with source ownership and
saved decisions. Neither policy proves that a global best résumé was found.
"""
from __future__ import annotations

from typing import Any


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _key(value: Any) -> str:
    return _clean(value).casefold()


def _project_key(row: dict[str, Any]) -> str:
    return _key(row.get("title") or row.get("name") or row.get("display_title"))


def _bullets(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
        return None
    return [s.strip() for s in value if s.strip()]


def _pool_index(rows: Any) -> tuple[dict[str, dict[str, Any]], str]:
    if not isinstance(rows, list) or not rows:
        return {}, "Saved project candidate sources are unavailable."
    pool = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            return {}, "Candidate source contains an invalid project row."
        key = _project_key(candidate)
        if not key or key in pool:
            return {}, "Candidate source has missing or duplicate project identities."
        pool[key] = candidate
    return pool, ""



def explain_saved_bullet_decision(decision: dict[str, Any]) -> dict[str, Any]:
    """Read-only explanation from an allocator-time snapshot; never infer a winner.

    Older receipts do not contain the decision tuple. Their original reason is
    retained, but relative ranking and efficiency claims are explicitly withheld.
    """
    generic = {"status": "partial", "reason": _clean(decision.get("reason")),
               "message": "No verified per-step rank comparison in this saved generation.",
               "step": "", "peer": None, "metric": "", "chosen_value": None,
               "peer_value": None, "word_count_is_decision_factor": False}
    context = decision.get("decision_context")
    if not isinstance(context, dict) or context.get("version") != "phase9f-v27-bullet-selection-explanation-v1":
        return generic
    chosen = context.get("selected")
    if not isinstance(chosen, dict) or str(chosen.get("bullet_id")) != str(decision.get("bullet_id")):
        return {**generic, "status": "withheld", "message": "Decision snapshot identity mismatch; comparative explanation withheld."}
    if not decision.get("selected"):
        return generic
    if context.get("word_count_used_for_selection") is not False:
        return {**generic, "status": "withheld", "message": "Unexpected word-budget decision metadata; comparative explanation withheld."}
    mode = _clean(context.get("mode"))
    if mode == "all_canonical_before_fitting":
        return {**generic, "status": "all_admitted",
                "message": "Both Base and Library bullets were admitted before fitting. No quality winner at this stage.",
                "step": _clean(context.get("phase")),
                "word_count": chosen.get("word_count")}
    peer = context.get("best_opposite_source_peer_at_step")
    factor = _clean(context.get("first_differing_rank_factor"))
    factors = context.get("factor_order") or []
    chosen_rank = chosen.get("rank_tuple") or []
    peer_rank = peer.get("rank_tuple") if isinstance(peer, dict) else None
    if isinstance(peer, dict) and (factor not in factors and factor != "rank_tie"):
        return {**generic, "status": "withheld", "message": "Rank comparison fields are inconsistent; explanation withheld."}
    if isinstance(peer, dict) and (not isinstance(peer_rank, list)
                                    or len(factors) != len(chosen_rank)
                                    or len(factors) != len(peer_rank)):
        return {**generic, "status": "withheld", "message": "Incomplete ranking tuple; explanation withheld."}
    if isinstance(peer, dict) and factor in factors:
        idx = factors.index(factor)
        metric, value, peer_value = factor, chosen_rank[idx], peer_rank[idx]
        message = ("At this allocation step, the chosen bullet ranked ahead of the "
                   "best available opposite-source bullet within this project. "
                   "The first differing ranking factor is shown below; this is not a global quality score.")
    elif isinstance(peer, dict):
        metric, value, peer_value = "rank_tie", None, None
        message = "The local opposite-source alternative tied on recorded ranking factors; stable ordering decided."
    else:
        metric, value, peer_value = "", None, None
        message = "No opposite-source bullet was available as a local alternative at this step."
    return {"status": "step_recorded", "reason": generic["reason"],
            "message": message, "step": _clean(context.get("phase")),
            "ranking_scope": _clean(context.get("ranking_scope")),
            "metric": metric, "chosen_value": value, "peer_value": peer_value,
            "peer": peer, "word_count": chosen.get("word_count"),
            "named_technical_terms": chosen.get("named_technical_terms"),
            "ownership_score": chosen.get("ownership_score"),
            "new_strong": chosen.get("new_strong"),
            "new_required_core": chosen.get("new_required_core"),
            "strong_requirement_ids": chosen.get("strong_requirement_ids") or [],
            "word_count_is_decision_factor": False}

def build_project_bullet_source_view(projects: dict[str, Any] | None, candidate_pool: Any) -> dict[str, Any]:
    """Ground exact bullet-source displays in saved source and generation rows.

    `selected_blueprint_bullets` is named by the existing generation contract,
    not by this view. It is the filtered, *library-owned* canonical subset.
    Exact text equality is never described as a causal selection/quality score.
    """
    if not isinstance(projects, dict):
        return {"projects": [], "notice": "Saved generated Projects result is unavailable."}
    generated = projects.get("recommended_projects")
    ranked = projects.get("candidate_project_ranking")
    index, reason = _pool_index(candidate_pool)
    if reason:
        return {"projects": [], "notice": reason}
    if (not isinstance(generated, list) or not isinstance(ranked, list)
        or not all(isinstance(r, dict) for r in generated + ranked)):
        return {"projects": [], "notice": "Generated project/ranking receipt is unavailable."}
    ranked_map = {}
    for row in ranked:
        k = _project_key(row)
        if not k or k in ranked_map:
            return {"projects": [], "notice": "Saved ranked project identities are ambiguous."}
        ranked_map[k] = row
    selected_keys = set()
    output = []
    for project in generated:
        key = _project_key(project)
        if not key or key in selected_keys:
            return {"projects": [], "notice": "Generated project identities are ambiguous."}
        selected_keys.add(key)
        source = index.get(key)
        rank = ranked_map.get(key)
        if source is None or rank is None:
            return {"projects": [], "notice": "A selected project's saved source/ranking identity cannot be resolved."}
        saved_project_id = _clean(project.get("project_id"))
        saved_rank_id = _clean(rank.get("project_id"))
        if saved_project_id and saved_rank_id and saved_project_id != saved_rank_id:
            return {"projects": [], "notice": "Generated project ID differs from the saved ranking ID."}
        flags = (bool(source.get("currently_in_resume")), bool(source.get("in_evidence_library")))
        sources = {"resume" if flags[0] else "", "evidence_library" if flags[1] else ""} - {""}
        recorded_sources = [_clean(v) for v in (project.get("source"), rank.get("source")) if _clean(v)]
        expected_source = "both" if len(sources) == 2 else "resume" if flags[0] else "evidence_library" if flags[1] else ""
        if not expected_source or any(v != expected_source for v in recorded_sources):
            return {"projects": [], "notice": "Saved candidate source ownership conflicts with the generated project."}
        base_row = source.get("resume_evidence") or {}
        library_row = source.get("evidence_library_evidence") or {}
        if not isinstance(base_row, dict) or not isinstance(library_row, dict):
            return {"projects": [], "notice": "Project evidence source structure is malformed."}
        base = _bullets(base_row.get("bullets", [] if not flags[0] else None))
        library = _bullets(library_row.get("bullets", [] if not flags[1] else None))
        selected = _bullets(project.get("selected_blueprint_bullets"))
        draft = _bullets(project.get("draft_bullets"))
        if any(v is None for v in [base, library, selected, draft]):
            return {"projects": [], "notice": "Exact saved bullet lists are missing or malformed."}
        assert base is not None and library is not None and selected is not None and draft is not None
        lib_text = {_key(s) for s in library}
        selected_text = {_key(s) for s in selected}
        draft_text = {_key(s) for s in draft}
        new_policy = (project.get("bullet_source_policy_version")
                      == "phase9f-combined-project-bullet-sources-v2.7")
        base_text = {_key(s) for s in base}
        if new_policy:
            if any(s not in (lib_text | base_text) for s in selected_text):
                return {"projects": [], "notice": "Selected V2.7 bullets are not in either frozen source."}
            from tailoring.combined_project_bullet_sources_v2_7 import bullet_sources
            recorded_owners = project.get("selected_bullet_sources")
            if (not isinstance(recorded_owners, list)
                or recorded_owners != [bullet_sources(source, text) for text in selected]):
                return {"projects": [], "notice": "Saved V2.7 bullet ownership receipt does not match frozen sources."}
        elif any(s not in lib_text for s in selected_text):
            return {"projects": [], "notice": "Selected canonical bullets are not in the saved Evidence Library source."}
        priority = project.get("bullet_evidence_priorities") or []
        priority_by_index = {}
        if isinstance(priority, list):
            for item in priority:
                if isinstance(item, dict) and isinstance(item.get("bullet_index"), int):
                    priority_by_index[item["bullet_index"]] = item
        base_rows = [{
            "#": i, "Base Resume bullet": text,
            "Canonical Library text?": "Exact match" if _key(text) in lib_text else "No",
            "Selected for generation?": "Yes" if _key(text) in selected_text else "No",
            "Exact draft wording?": "Yes" if _key(text) in draft_text else "No",
        } for i, text in enumerate(base, 1)]
        library_rows = [{
            "#": i, "Evidence Library bullet": text,
            "Canonical selection": "Selected" if _key(text) in selected_text else "Available, not selected",
            "Exact draft wording?": "Yes" if _key(text) in draft_text else "No",
        } for i, text in enumerate(library, 1)]
        drafted = []
        for i, text in enumerate(draft):
            point = priority_by_index.get(i) or {}
            if point and _key(point.get("bullet_text")) != _key(text):
                # Do not attach potentially misindexed JD evidence to a draft bullet.
                point = {}
            canonical_match = _key(text) in selected_text
            drafted.append({
                "#": i+1,
                "Generated draft bullet": text,
                "Wording lineage": "Exact selected canonical bullet" if canonical_match else "Rephrased/generated; no exact-text lineage",
                "Saved JD requirement IDs": ", ".join(str(s) for s in (point.get("supported_requirement_ids") or []) if s),
                "Saved evidence priority": point.get("evidence_value") if point else None,
                "Protected for fitting?": "Yes" if point.get("protect_during_fitting") is True else "No" if point else "Not recorded",
            })
        matches = [r for r in rank.get("requirement_matches") or []
                   if isinstance(r, dict) and _clean(r.get("match_label")) in {"direct", "transferable", "weak"}]
        provenance = [{
            "JD requirement": _clean(m.get("requirement_text")),
            "Match": _clean(m.get("match_label")),
            "Saved evidence excerpt": " | ".join(_clean(s) for s in (m.get("evidence_snippets") or []) if isinstance(s, str)),
            "Evidence record IDs": ", ".join(_clean(s) for s in (m.get("evidence_ids") or [])),
        } for m in matches]
        output.append({
            "project": _clean(project.get("display_title") or project.get("title")),
            "source": expected_source,
            "base_count": len(base), "library_count": len(library),
            "canonical_count": len(selected), "draft_count": len(draft),
            "base_bullets": base_rows, "library_bullets": library_rows,
            "draft_bullets": drafted, "evidence_links": provenance,
            "exact_shared_count": sum(1 for s in base if _key(s) in lib_text),
            "base_only_count": sum(1 for s in base if _key(s) not in lib_text),
            "library_only_count": sum(1 for s in library if _key(s) not in {_key(x) for x in base}),
            "rank": rank.get("selection_rank"),
            "project_rank_score": rank.get("selection_score"),
            "rewrite_reason": _clean(project.get("rewrite_reason")),
            "bullet_decision_receipts": (
                project.get("bullet_decision_receipts") or []
            ),
            "saved_requirement_labels": {
                _clean(m.get("requirement_id")): {
                    "text": _clean(m.get("requirement_text")),
                    "match": _clean(m.get("match_label")),
                }
                for m in (rank.get("requirement_matches") or [])
                if isinstance(m, dict) and _clean(m.get("requirement_id"))
            },
            "bullet_source_policy_version": _clean(project.get("bullet_source_policy_version")),
        })
    policy_set = {r.get("bullet_source_policy_version", "") for r in output}
    notice = ("V2.7 allowed both the confirmed Base and frozen Library bullets. Saved source ownership and allocation decisions are shown; this is not a validated global quality optimum."
              if policy_set == {"phase9f-combined-project-bullet-sources-v2.7"}
              else "Legacy generation: the Evidence Library was canonical by bullet-source policy, not because a Base-versus-Library quality contest was won.")
    return {"projects": output, "notice": notice}


def _bound_candidate_sources(
    execution: dict[str, Any] | None,
    decision: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]] | None, str]:
    """Rebuild from already-loaded frozen Phase 9F data, with zero DB reads/writes.

    The caller's existing source binding is the only authority. Never resolve
    current/latest library items or another application/session here.
    """
    if not isinstance(execution, dict) or not execution:
        return None, "No saved Phase 9F-F source/evidence snapshot was loaded."
    if not isinstance(decision, dict):
        return None, "Current selected-source binding is unavailable."
    starting = decision.get("starting_snapshot") or {}
    snapshot = execution.get("evidence_snapshot") or {}
    source_id = (starting.get("source_identity") or {}).get("source_id")
    if (str(execution.get("phase9e_decision_fingerprint") or "") != str(decision.get("decision_fingerprint") or "")
        or str(execution.get("starting_snapshot_fingerprint") or "") != str(starting.get("starting_snapshot_fingerprint") or "")
        or str(execution.get("source_id") or "") != str(source_id or "")
        or str(execution.get("evidence_snapshot_fingerprint") or "") != str(snapshot.get("snapshot_fingerprint") or "")):
        return None, "The selected source or Evidence Library snapshot does not match this Phase 9F execution."
    resume_profile = starting.get("resume_profile_snapshot")
    rows = snapshot.get("rows")
    if (not isinstance(resume_profile, dict) or not isinstance(rows, list)
        or not rows or not snapshot.get("snapshot_fingerprint")):
        return None, "Immutable starting résumé or Evidence Library rows are missing."
    try:
        from tailoring.project_section_tailor import build_project_candidate_pool
        candidate_pool = build_project_candidate_pool(resume_profile=resume_profile, evidence_items=rows)
    except (ValueError, TypeError, KeyError) as exc:
        return None, "Saved evidence candidates could not be rebuilt: " + str(exc)
    return candidate_pool, "Frozen selected-source résumé + immutable Phase 9F Evidence Library snapshot"


def render_project_bullet_source_comparison(
    st: Any, projects: dict[str, Any], *, application_id: int,
    phase9f_execution: dict[str, Any] | None = None,
    current_phase9e_decision: dict[str, Any] | None = None,
) -> bool:
    """Show per-project source bullets and generation decisions within the existing open panel."""
    try:
        candidates, provenance = _bound_candidate_sources(phase9f_execution, current_phase9e_decision)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        candidates, provenance = None, "Could not verify frozen source snapshots: " + str(exc)
    if candidates is None and not phase9f_execution:
        # Session-captured generation inputs are useful but not durable. Do not
        # silently rebuild using *current* Evidence Library contents.
        saved_candidates = st.session_state.get(f"project_candidate_pool_{int(application_id)}")
        if isinstance(saved_candidates, list):
            candidates = saved_candidates
            provenance = "Session-captured generation source pool (not an immutable execution receipt)"
    st.markdown("**Base Resume vs Evidence Library — bullet sources**")
    if candidates is None:
        st.caption("Source bullet comparison withheld: " + provenance)
        return False
    view = build_project_bullet_source_view(projects, candidates)
    if not view["projects"]:
        st.warning("Source bullet comparison withheld: " + view["notice"])
        return False
    st.caption(view["notice"])
    st.caption("Source authority: " + provenance + ". Each source list is independent; bullet numbers do not imply paired alternatives.")
    import pandas as pd
    summary = []
    for row in view["projects"]:
        receipts = row.get("bullet_decision_receipts") or []
        accepted = [r for r in receipts if r.get("selected") is True]
        ownership = [set(r.get("sources") or []) for r in accepted]
        is_new = row.get("bullet_source_policy_version") == "phase9f-combined-project-bullet-sources-v2.7"
        summary.append({
            "Inspect": False,
            "Project": row["project"],
            "Base available": row["base_count"],
            "Library available": row["library_count"],
            "Chosen Base-only": sum(x == {"base"} for x in ownership) if is_new else "Legacy",
            "Chosen Library-only": sum(x == {"library"} for x in ownership) if is_new else "Legacy",
            "Chosen shared": sum(x == {"base", "library"} for x in ownership) if is_new else "Legacy",
            "Draft count": row["draft_count"],
        })
    st.caption("Tick Inspect on one or more projects below. The checked boxes expand explanations only; they do not edit the saved generation.")
    inspection = st.data_editor(
        pd.DataFrame(summary), hide_index=True, width="stretch", num_rows="fixed",
        disabled=[col for col in summary[0] if col != "Inspect"],
        key=f"phase9f_v27_generated_project_inspection_{int(application_id)}",
    )
    picks = [i for i, checked in enumerate(inspection["Inspect"].tolist()) if checked]
    for i in picks:
        chosen = view["projects"][i]
        st.markdown("### " + chosen["project"])
        col_base, col_library, col_draft = st.columns(3)
        col_base.metric("Base bullets", chosen["base_count"])
        col_library.metric("Library bullets", chosen["library_count"])
        col_draft.metric("Generated draft", chosen["draft_count"])
        if chosen.get("bullet_source_policy_version") == "phase9f-combined-project-bullet-sources-v2.7":
            decisions = chosen.get("bullet_decision_receipts") or []
            st.markdown("**Actual bullet allocation and saved reasons**")
            if not decisions:
                st.warning("This generation has no saved per-bullet selection receipts.")
            for decision in decisions:
                label = "Chosen" if decision.get("selected") else "Not allocated"
                with st.container(border=True):
                    st.write("**" + label + "** · " + ", ".join(decision.get("sources") or []))
                    st.write(str(decision.get("bullet") or ""))
                    reason = str(decision.get("reason") or "No saved reason")
                    reqids = decision.get("supported_requirement_ids") or []
                    st.caption("Allocator: " + reason)
                    evidence = chosen.get("saved_requirement_labels") or {}
                    if reqids:
                        st.caption("Saved project-level JD signals used by this allocator bullet: " +
                                   "; ".join(
                                      (evidence.get(rid, {}).get("text") or rid) +
                                      (" [" + evidence.get(rid, {}).get("match", "") + "]"
                                       if evidence.get(rid, {}).get("match") else "")
                                      for rid in reqids
                                   ))
                    else:
                        st.caption("No strong JD requirement support recorded for this bullet.")
                    why = explain_saved_bullet_decision(decision)
                    if why["status"] == "step_recorded":
                        st.write("**Why at this allocation step?** " + why["message"])
                        st.caption("Phase: " + why["step"] + " · Scope: " + why.get("ranking_scope", ""))
                        if why.get("metric"):
                            st.write("First differing rank factor: **" + why["metric"] + "**")
                            if why["chosen_value"] is not None:
                                st.caption("Chosen: " + str(why["chosen_value"]) +
                                           " · Other-source alternative: " + str(why["peer_value"]))
                        peer = why.get("peer")
                        if peer:
                            st.write("**Best other-source bullet available then:** " + str(peer.get("bullet") or ""))
                            st.caption("Source: " + ", ".join(peer.get("sources") or []))
                        st.caption("Chosen words: " + str(why.get("word_count")) +
                                   " · Named technical-term hits: " + str(why.get("named_technical_terms")) +
                                   " · Ownership signal: " + str(why.get("ownership_score")) +
                                   ". Word count is informational: it is NOT an allocator ranking factor.")
                    elif why["status"] == "all_admitted":
                        st.caption(why["message"])
                    else:
                        st.caption(why["message"])
                    if decision.get("selected"):
                        with st.expander("Compare JD terms: selected bullet vs other-source alternative", expanded=False):
                            from tailoring.phase9f_bullet_comparison_detail_v1 import compare_saved_source_bullets
                            detail = compare_saved_source_bullets(decision, evidence)
                            if detail["status"] != "ok":
                                st.caption(detail["message"])
                            else:
                                st.caption(detail["selection_reason"])
                                st.caption(detail["caveat"])
                                cols = st.columns(2)
                                for column, key in zip(cols, ("chosen", "peer")):
                                    item = detail[key]
                                    with column:
                                        st.markdown("**" + ("Selected" if key == "chosen" else "Other-source alternative")
                                                    + " — " + ", ".join(item["sources"]) + "**")
                                        st.markdown(item["marked"])
                                        st.caption("Words: " + str(item["words"]) +
                                                   " · JD terms present: " + ", ".join(item["jd_terms"]))
                                st.write("**Shared JD terms:** " + ", ".join(detail["common_terms"]))
                                st.write("**Selected-only JD terms:** " + ", ".join(detail["chosen_only_terms"]))
                                st.write("**Alternative-only JD terms:** " + ", ".join(detail["peer_only_terms"]))
                                for requirement in detail["requirements"]:
                                    st.markdown("**JD: " + requirement["text"] + "**")
                                    st.caption("Saved project match: " + requirement["project_match"] +
                                               " · Selected support recorded: " + str(requirement["selected_support_recorded"]) +
                                               " · Alternative support recorded: " + str(requirement["alternative_support_recorded"]))
                                    st.caption("Exact terms — Selected: " + ", ".join(requirement["lexical_selected"]) +
                                               " | Alternative: " + ", ".join(requirement["lexical_alternative"]))
            st.caption("Older generations have broad saved reasons only. New selection-step explanations are not backfilled; word efficiency is a diagnostic, not an allocator rank factor.")
            st.caption("Source ownership is not a quality score. No alternative is proven globally optimal.")
        else:
            st.caption("Legacy Library-only generation. The Library source won by the historical policy, not by a Base-vs-Library quality comparison.")
        with st.expander("See full original Base, Library and generated bullets", expanded=False):
            st.markdown("**Selected Base Resume**")
            for bullet in chosen["base_bullets"]:
                with st.container(border=True):
                    st.write(f"**Base B{bullet['#']}**")
                    st.write(bullet["Base Resume bullet"])
            st.markdown("**Evidence Library**")
            for bullet in chosen["library_bullets"]:
                with st.container(border=True):
                    st.write(f"**Library L{bullet['#']} · {bullet['Canonical selection']}**")
                    st.write(bullet["Evidence Library bullet"])
            st.markdown("**Generated draft**")
            for bullet in chosen["draft_bullets"]:
                with st.container(border=True):
                    st.write(f"**Draft D{bullet['#']}**")
                    st.write(bullet["Generated draft bullet"])
                    st.caption(bullet["Wording lineage"])
            if chosen["rewrite_reason"]:
                st.caption("Saved writer note: " + chosen["rewrite_reason"])
        with st.expander("JD evidence links and requirement provenance", expanded=False):
            for item in chosen["evidence_links"]:
                with st.container(border=True):
                    st.write("**" + item["JD requirement"] + "** · " + item["Match"])
                    st.write(item["Saved evidence excerpt"] or "No excerpt recorded")
                    st.caption("Evidence IDs: " + item["Evidence record IDs"])
            st.caption("Project-level JD evidence does not prove that one alternative bullet text is superior.")
    return True
