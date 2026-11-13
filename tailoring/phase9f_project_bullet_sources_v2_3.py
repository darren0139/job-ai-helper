"""Read-only Phase 9F project bullet-source comparison.

Project ranking pools résumé and Evidence Library evidence. Project bullet
writing takes approved *canonical* bullets from Evidence Library by policy.
Neither fact proves an individual Evidence Library bullet scored better than a
résumé bullet; this UI deliberately makes no such claim.
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
        if any(s not in lib_text for s in selected_text):
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
        })
    return {"projects": output, "notice": "The Evidence Library is canonical by bullet-source policy, not because a saved Base-versus-Library bullet-quality contest was won."}


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
    options = list(range(len(view["projects"])))
    picked = st.selectbox("Inspect source bullets for project", options,
                          format_func=lambda i: view["projects"][i]["project"],
                          key=f"phase9f_project_bullet_sources_v23_{int(application_id)}")
    if picked is None:
        return True
    chosen = view["projects"][picked]
    col_base, col_library, col_draft = st.columns(3)
    col_base.metric("Base bullets", chosen["base_count"])
    col_library.metric("Canonical Library", chosen["library_count"])
    col_draft.metric("Generated draft", chosen["draft_count"])
    st.caption("Why Library wording is used: the writer's current eligibility rule accepts canonical Evidence Library bullets. This is a policy, NOT a measured verdict that a Base bullet is weaker.")
    st.markdown("**Selected Base Resume — full original wording**")
    if not chosen["base_bullets"]:
        st.caption("No saved Base bullets for this project.")
    for row in chosen["base_bullets"]:
        with st.container(border=True):
            st.write(f"**Base B{row['#']}**")
            st.write(row["Base Resume bullet"])
            st.caption("Verbatim in canonical Library: " + row["Canonical Library text?"] +
                       " · Exact wording in generated draft: " + row["Exact draft wording?"])
    st.markdown("**Canonical Evidence Library — approved alternatives**")
    if not chosen["library_bullets"]:
        st.caption("No canonical Library bullets recorded.")
    for row in chosen["library_bullets"]:
        with st.container(border=True):
            st.write(f"**Library L{row['#']} · {row['Canonical selection']}**")
            st.write(row["Evidence Library bullet"])
            st.caption("Exact generated draft wording: " + row["Exact draft wording?"] +
                       ". Inclusion is not a claim of relative bullet quality.")
    st.markdown("**Generated draft — complete readable bullet text**")
    for row in chosen["draft_bullets"]:
        with st.container(border=True):
            st.write(f"**Draft D{row['#']}**")
            st.write(row["Generated draft bullet"])
            note = row["Wording lineage"]
            if row["Saved JD requirement IDs"]:
                note += " · Saved JD IDs: " + row["Saved JD requirement IDs"]
            if row["Saved evidence priority"] is not None:
                note += " · Saved draft evidence value: " + str(row["Saved evidence priority"])
            st.caption(note)
    if chosen["rewrite_reason"]:
        st.caption("Saved writer explanation: " + chosen["rewrite_reason"])
    if chosen["evidence_links"]:
        if st.checkbox("Show saved JD evidence links for this project", value=False,
                       key=f"phase9f_bullet_source_jd_links_{int(application_id)}"):
            for row in chosen["evidence_links"]:
                with st.container(border=True):
                    st.write("**" + row["JD requirement"] + "** · " + row["Match"])
                    st.write(row["Saved evidence excerpt"] or "No specific excerpt recorded")
                    st.caption("Evidence record IDs: " + row["Evidence record IDs"])
            st.caption("JD matching applies to pooled project evidence; it did not compare Base versus Library wording.")
    return True
