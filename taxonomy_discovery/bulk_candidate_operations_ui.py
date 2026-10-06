"""Thin Streamlit workflow for bounded TQ-D3 bulk operations."""
from __future__ import annotations

import json


ACTIVE_STAGE_KEY = "tqd3_bulk_active_stage"
_STAGE_NAV_KEY = "tqd3_bulk_stage_navigation"
_PENDING_STAGE_KEY = "tqd3_bulk_pending_stage"
WORKFLOW_SECTIONS = (
    "A. Corpus Coverage", "B. Unresolved Gaps", "C. Resolve Batch",
    "D. Needs Research", "E. Proposals / regression", "F. Review / Publish",
)
STAGES = ("select", "plan", "research", "proposals", "review", "publish")
STAGE_LABELS = {
    "select": "A–C. Coverage, gaps & resolve batch",
    "plan": "D. Needs research · plan",
    "research": "D. Needs research · run",
    "proposals": "E. Proposals / regression",
    "review": "F. Review",
    "publish": "F. Publish",
}

READINESS_LABELS = {
    "relationship_research_ready": "Relationship research ready",
    "identity_research_ready": "Identity research ready",
    "capability_research_ready": "Capability research ready",
    "local_review_required": "Local review",
    "needs_decomposition": "Needs decomposition",
    "blocked_noise_or_insufficient": "Blocked",
    "cached_current": "Cached / current",
    "stale_research": "Stale research",
    "manual_review": "Manual review",
}

AUTHORITY_LABELS = {
    "governed_official_scope": "Governed official source scope",
    "candidate_evidence_only_not_governed": "Not yet governed; discovery evidence only",
    "authoritative_definition_discovery": "Authoritative definition discovery required",
    "missing_governed_official_scope": "Governed official source scope missing",
    "not_applicable": "Not applicable",
}


def _readiness_label(value):
    return READINESS_LABELS.get(value, value or "Unknown")


def _authority_label(value):
    return AUTHORITY_LABELS.get(value, value or "Unknown")


def _table_rows(rows):
    return [{
        "rank": row.get("work_queue_rank", row["priority_rank"]),
        "candidate_id": row["candidate_id"],
        "concept": row["concept"],
        "route": row["route"],
        "jobs": row["distinct_job_count"],
        "occurrences": row["occurrence_count"],
        "importance": row["importance_distribution"],
        "current_knowledge": row["local_evidence_status"],
        "research": row["research_status"],
        "external_research": row["external_research_required"],
        "prior_action": row["prior_recommended_action"],
        "draft": row["draft_status"],
        "review": row["review_status"],
        "publication": row["publication_status"],
        "research_readiness": _readiness_label(
            (row.get("research_readiness") or {}).get("research_readiness")
        ),
        "priority": row["priority_score"],
        "blockers": ", ".join(row["blockers"]),
    } for row in rows]


def _active_stage(state):
    stage = state.get(ACTIVE_STAGE_KEY, "select")
    if stage not in STAGES:
        stage = "select"
    state[ACTIVE_STAGE_KEY] = stage
    return stage


def _request_stage(state, stage):
    """Queue a UI-only stage transition for the next Streamlit rerun."""
    if stage not in STAGES:
        raise ValueError(f"Unknown bulk workflow stage: {stage}")
    state[ACTIVE_STAGE_KEY] = stage
    state[_PENDING_STAGE_KEY] = stage


def _stage_complete(state, stage):
    if stage == "select":
        return bool(state.get("tqd3_bulk_selected"))
    if stage == "plan":
        return bool(state.get("tqd3_bulk_plan_receipt"))
    if stage == "research":
        plan = state.get("tqd3_bulk_plan_receipt") or {}
        return bool(state.get("tqd3_bulk_run_receipt")) or (bool(plan) and not plan.get("execution_targets"))
    if stage == "proposals":
        outcome = state.get("tqd3_bulk_draft_outcome") or {}
        return bool((outcome.get("created") or []) and state.get("tqd3_bulk_regression"))
    if stage == "review":
        return any((row.get("review") or {}).get("decision", "undecided") != "undecided"
                   for row in state.get("tqd3_bulk_saved", []))
    return bool(state.get("tqd3_bulk_preflight"))


def _render_navigation(st):
    active = _active_stage(st.session_state)
    pending = st.session_state.pop(_PENDING_STAGE_KEY, None)
    if pending in STAGES:
        st.session_state[_STAGE_NAV_KEY] = pending
        active = pending
    elif st.session_state.get(_STAGE_NAV_KEY) not in STAGES:
        st.session_state[_STAGE_NAV_KEY] = active

    chosen = st.radio(
        "Bulk workflow stage",
        STAGES,
        key=_STAGE_NAV_KEY,
        horizontal=True,
        format_func=lambda stage: STAGE_LABELS[stage],
        label_visibility="collapsed",
    )
    if chosen in STAGES:
        active = chosen
        st.session_state[ACTIVE_STAGE_KEY] = active

    indicators = []
    for index, stage in enumerate(STAGES, 1):
        marker = "●" if stage == active else ("✓" if _stage_complete(st.session_state, stage) else "○")
        short = STAGE_LABELS[stage].split(". ", 1)[1]
        indicators.append(f"{marker} {index} {short}")
    st.caption("  ·  ".join(indicators))
    return active


def _go(st, stage):
    _request_stage(st.session_state, stage)
    st.rerun()


def _execute_plan(st, bulk, *, next_stage="research"):
    plan = st.session_state.get("tqd3_bulk_plan_receipt")
    prepared = st.session_state.get("tqd3_bulk_prepared")
    try:
        receipt = bulk.execute_bulk_plan(plan, prepared["candidates"], explicit_execution=True)
    except Exception as exc:
        st.error(f"Bounded research stopped safely: {exc}")
        return False
    st.session_state["tqd3_bulk_run_receipt"] = receipt
    _go(st, next_stage)
    return True


def _plan_blocked_count(plan):
    counts = plan.get("precheck_counts") or {}
    blocked_states = {
        "blocked", "deferred", "already_rejected", "already_published",
        "partial_resolution_decomposition_required", "stale_requires_refresh",
    }
    return sum(int(counts.get(state, 0)) for state in blocked_states)


def _render_corpus_resolution(st, bulk):
    """Normal local-first entry point; every expensive/write action stays explicit."""
    from taxonomy_discovery.corpus_gap_resolution import (
        audit_corpus_resolution,
        build_gap_resolution_queue,
        build_native_regression_handoff,
        create_local_proposals,
        preview_local_resolution,
    )

    def research_candidates(candidates):
        eligible_routes = {
            "existing_capability_resolver_issue", "technology_relationship",
            "technology_identity", "possible_new_capability",
        }
        return [candidate for candidate in candidates
                if candidate.get("operational_route") not in {
                    "needs_decomposition", "noise_or_non_capability", "manual_review"
                } and candidate.get("candidate_route") in eligible_routes]

    st.markdown("##### A. Corpus Coverage")
    st.caption(
        "Re-evaluate every saved canonical Job Match requirement with the current "
        "production taxonomy, registry, and resolver. The audit is read-only and offline."
    )
    if st.button("Run whole-corpus coverage audit", key="tqd3_corpus_gap_audit"):
        try:
            with st.spinner("Auditing saved requirements with current production knowledge..."):
                audit = audit_corpus_resolution()
                resolution_queue = build_gap_resolution_queue(audit)
                candidates = research_candidates(audit["candidates"])
                research_queue = bulk.build_candidate_queue(
                    candidates, include_hidden=True
                )
            st.session_state["tqd3_corpus_gap_audit"] = audit
            st.session_state["tqd3_gap_resolution_queue"] = resolution_queue
            st.session_state["tqd3_bulk_prepared"] = {
                "corpus": audit["corpus"],
                "candidates": candidates,
                "coverage_audit": audit,
            }
            st.session_state["tqd3_bulk_queue"] = research_queue
            st.success("Current corpus audit and one shared resolution queue are ready.")
        except Exception as exc:
            st.error(f"Corpus resolution audit failed closed: {exc}")

    audit = st.session_state.get("tqd3_corpus_gap_audit")
    resolution_queue = st.session_state.get("tqd3_gap_resolution_queue")
    if not audit or not resolution_queue:
        st.info("Run the audit explicitly to load corpus coverage and unresolved gaps. Passive rendering performs no work.")
        return

    summary = audit["summary"]
    st.write("Coverage summary", {
        "total requirements": summary["total_requirements"],
        "meaningful technical requirements": summary["meaningful_technical_requirements"],
        "resolved/scorable": summary["resolved_scorable_requirements"],
        "unresolved technical": summary["unresolved_technical_requirements"],
        "required/core weighted coverage": f"{summary['required_core_weighted_coverage']['percent']:.2f}%",
        "supporting/preferred weighted coverage": f"{summary['supporting_preferred_weighted_coverage']['percent']:.2f}%",
        "overall weighted coverage": f"{summary['overall_weighted_coverage']['percent']:.2f}%",
    })
    st.download_button(
        "Download corpus coverage and queue JSON",
        data=json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        file_name="tqd3_corpus_gap_resolution_audit.json",
        mime="application/json",
    )

    st.markdown("##### B. Unresolved Gaps")
    st.write("Operational route counts", audit["route_counts"])
    st.dataframe(audit["top_unresolved_concepts"], hide_index=True, width="stretch")

    uploaded = st.file_uploader(
        "Optional proposed technology seed list · dry-run only",
        type=["json"],
        key="tqd3_bulk_seed_upload",
    )
    if st.button("Validate seed into the same queue", key="tqd3_bulk_seed_validate", disabled=uploaded is None):
        try:
            payload = json.loads(uploaded.getvalue())
            resolution_queue = build_gap_resolution_queue(audit, bulk_seed=payload)
            st.session_state["tqd3_gap_resolution_queue"] = resolution_queue
            candidates = research_candidates(resolution_queue["candidates"])
            st.session_state["tqd3_bulk_prepared"] = {
                "corpus": audit["corpus"], "candidates": candidates, "coverage_audit": audit,
            }
            st.session_state["tqd3_bulk_queue"] = bulk.build_candidate_queue(candidates, include_hidden=True)
            st.success("Seed validated and added to the review queue. Production knowledge is unchanged.")
        except Exception as exc:
            st.error(f"Bulk seed rejected: {exc}")

    st.markdown("##### C. Resolve Batch")
    local_rows = [row for row in resolution_queue["rows"] if row["local_safe"]]
    st.dataframe([{
        "candidate": row["concept"],
        "example JD text": row["example_jd_text"],
        "jobs": row["job_count"],
        "occurrences": row["occurrences"],
        "importance": row["importance"],
        "current taxonomy": (row["current_taxonomy_result"].get("canonical_match")
                             or [item.get("capability_id") for item in row["current_taxonomy_result"].get("high_overlap_candidates", [])]),
        "current registry": row["current_registry_result"].get("status"),
        "recommended resolution": row["recommended_resolution_type"],
        "external research": row["external_research_required"],
        "reason": row["blocker_reason"],
    } for row in local_rows], hide_index=True, width="stretch")
    selected = st.multiselect(
        "Locally resolvable gaps for proposal preview",
        [row["candidate_id"] for row in local_rows],
        key="tqd3_local_gap_selected",
        format_func=lambda candidate_id: next(row["concept"] for row in local_rows if row["candidate_id"] == candidate_id),
    ) or []
    if st.button("Preview selected local proposals", key="tqd3_local_gap_preview", disabled=not selected):
        try:
            outcome = create_local_proposals(
                resolution_queue,
                selected_candidate_ids=selected,
                explicit_creation=True,
            )
            preview = preview_local_resolution(audit, outcome["proposals"])
            st.session_state["tqd3_local_gap_proposals"] = outcome
            st.session_state["tqd3_local_gap_impact"] = preview
            st.session_state["tqd3_local_regression_handoff"] = build_native_regression_handoff(outcome["proposals"])
        except Exception as exc:
            st.error(f"Local proposal preview failed closed: {exc}")
    preview = st.session_state.get("tqd3_local_gap_impact")
    if preview:
        st.write("Read-only Job Match requirement-resolution impact", {
            "requirements evaluated": preview["requirements_evaluated"],
            "unresolved before": preview["unresolved_before"],
            "would resolve after": preview["would_resolve_after"],
            "affected jobs": len(preview["affected_jobs"]),
            "conflicts/ambiguity": len(preview["conflicts_ambiguity"]),
            "coverage before": f"{preview['coverage_before_percent']:.2f}%",
            "projected after": f"{preview['projected_coverage_after_percent']:.2f}%",
        })
        st.caption("Draft-only preview. Human review is required; no score, approval, publication, taxonomy, or registry state changed.")
        with st.expander("Local proposal details and complete impact diagnostics"):
            st.json({"proposals": st.session_state.get("tqd3_local_gap_proposals"), "preview": preview})


def _render_select(st, bulk):
    _render_corpus_resolution(st, bulk)
    st.markdown("##### D. Needs Research")
    st.caption("Hard cases continue through the existing route-aware governed TQ-D3 research path.")
    if st.button("Refresh candidate queue", key="tqd3_bulk_refresh"):
        try:
            from taxonomy_discovery.governed_research import prepare_gap_review
            prepared = prepare_gap_review()
            queue = bulk.build_candidate_queue(prepared["candidates"])
            st.session_state["tqd3_bulk_prepared"] = prepared
            st.session_state["tqd3_bulk_queue"] = queue
            st.success("Current gap candidates loaded with zero external/model calls.")
        except Exception as exc:
            st.error(f"Candidate queue unavailable: {exc}")
    queue = st.session_state.get("tqd3_bulk_queue")
    prepared = st.session_state.get("tqd3_bulk_prepared")
    selected = list(st.session_state.get("tqd3_bulk_selected") or [])
    if not queue:
        st.info("Refresh explicitly to load the current persisted corpus and governance state. Passive rendering performs no research or writes.")
    else:
        st.write("Current route counts", queue["route_counts"])
        st.write("Current operational states", queue["status_counts"])
        show_hidden = st.checkbox("Show diagnostic/non-actionable routes", key="tqd3_bulk_show_hidden")
        rows = queue["rows"] if show_hidden else queue["default_rows"]
        st.dataframe(_table_rows(rows), hide_index=True, width="stretch")
        selected = st.multiselect(
            "Working batch (maximum 25)",
            [row["candidate_id"] for row in rows],
            key="tqd3_bulk_selected",
            max_selections=bulk.MAX_WORKING_BATCH,
            format_func=lambda candidate_id: next(row["concept"] for row in rows if row["candidate_id"] == candidate_id),
        ) or []
        st.caption(
            f"Selected {len(selected)} / {bulk.MAX_WORKING_BATCH}.\n\n"
            "Selection performs: 0 research · 0 approval · 0 publication · 0 production writes."
        )
        with st.expander("Priority formula and candidate diagnostics"):
            st.json([row for row in rows if row["candidate_id"] in selected])

    if st.button("Prepare selected batch →", key="tqd3_bulk_plan", disabled=not prepared or not selected):
        try:
            plan = bulk.prepare_bulk_plan(prepared["candidates"], selected_candidate_ids=selected)
        except Exception as exc:
            st.error(f"Research planning rejected: {exc}")
        else:
            st.session_state["tqd3_bulk_plan_receipt"] = plan
            _go(st, "plan")
            return


def _render_plan(st, bulk):
    plan = st.session_state.get("tqd3_bulk_plan_receipt")
    prepared = st.session_state.get("tqd3_bulk_prepared")
    if not plan:
        st.info("Prepare a selected batch before reviewing a research plan.")
    else:
        from taxonomy_discovery.research_readiness import audit_technology_registry
        registry_readiness = audit_technology_registry()
        queue_readiness = (st.session_state.get("tqd3_bulk_queue") or {}).get("research_readiness") or {}
        st.markdown("##### Research Readiness")
        st.write("Registry readiness summary", {
            "technologies audited": registry_readiness["technology_count"],
            "authority covered": registry_readiness["authority_covered_count"],
            "missing authority coverage": registry_readiness["missing_authority_coverage_count"],
            "states": registry_readiness["state_counts"],
        })
        if queue_readiness:
            st.write("Current queue readiness summary", {
                "current external candidates": queue_readiness["current_external_candidates"],
                "safe paid research routes": queue_readiness["ready_for_paid_research"],
                "route-aware states": queue_readiness.get("route_readiness_counts", {}),
                "blocked by authority coverage": queue_readiness["blocked_by_authority_coverage"],
                "blocked by query planning": queue_readiness["blocked_by_query_planning"],
                "needs decomposition": queue_readiness["needs_decomposition"],
                "cached/current": queue_readiness["cached_current"],
            })
        st.dataframe([{
            "candidate": row["candidate"],
            "research route": row.get("candidate_route"),
            "purpose": row.get("research_purpose"),
            "technology identity": row["technology_identity"],
            "authority state": _authority_label(row.get("authority_state")),
            "official authority coverage": ", ".join(row["official_domains"]) or "not governed / discovery only",
            "planned query": (row.get("query_strategy") or {}).get("primary_query"),
            "planned calls": 1 if row.get("paid_research_eligible") else 0,
            "query readiness": row["query_ready"],
            "cache/currentness": row["cache_currentness"],
            "decomposition": row["decomposition_status"],
            "research readiness": _readiness_label(row["research_readiness"]),
            "blocker/reason": row["blocker_reason"],
        } for row in plan["selected_readiness"]], hide_index=True, width="stretch")
        if plan["readiness_blockers"]:
            st.warning("Some selected candidates are excluded from paid research by readiness preflight.")
            with st.expander("Readiness blockers"):
                st.json(plan["readiness_blockers"])
        counts = plan.get("precheck_counts") or {}
        st.write("Selected candidates", plan["selected_count"])
        st.write("Resolved locally", counts.get("resolved_locally", 0))
        st.write("Cache hits", counts.get("research_current_cached", 0))
        st.write("External research required", plan["external_candidates_required"])
        st.write("Safe paid research routes", plan["ready_external_candidates"])
        st.write("Blocked by readiness", plan["blocked_by_readiness"])
        st.write("Blocked/deferred", _plan_blocked_count(plan))
        st.write("Candidates in next external run", plan["external_candidates_next_run"])
        st.write("Planned Tavily calls", plan["planned_tavily_calls"])
        st.write("Hard call cap", plan["hard_tavily_call_cap"])
        st.write("Queries/candidate", plan["maximum_queries_per_candidate"])
        st.write("Parallelism", plan["maximum_parallelism"])
        st.info("No external calls have occurred. Planning uses zero network/model calls and makes no production writes.")
        st.dataframe([{
            "candidate_id": item["candidate_id"],
            "research_route": item.get("research_route"),
            "purpose": item.get("research_purpose"),
            "authority_state": _authority_label(item.get("authority_state")),
            "external": item["external"],
            "planned_calls": item["planned_tavily_calls"],
            "planned_query": item.get("planned_query"),
            "questions": item["planned_questions"],
        } for item in plan["execution_targets"]], hide_index=True, width="stretch")
        with st.expander("Advanced / complete plan and fingerprints"):
            st.json(plan)

    if st.button("← Back to selection", key="tqd3_bulk_plan_back"):
        _go(st, "select")
        return
    if not plan:
        return
    if plan["external_candidates_next_run"]:
        if st.button("Research next safe route-aware batch →", key="tqd3_bulk_execute_plan", disabled=not prepared):
            _execute_plan(st, bulk)
            return
    elif plan["execution_targets"]:
        if st.button("Run local checks →", key="tqd3_bulk_execute_local", disabled=not prepared):
            _execute_plan(st, bulk)
            return
    elif plan["external_candidates_required"]:
        st.info("No selected external candidate passed its route-specific readiness profile. Resolve the listed blockers before spending credits.")
    elif st.button("Continue to proposals →", key="tqd3_bulk_plan_continue"):
        _go(st, "proposals")
        return


def _render_research(st, bulk):
    plan = st.session_state.get("tqd3_bulk_plan_receipt")
    prepared = st.session_state.get("tqd3_bulk_prepared")
    receipt = st.session_state.get("tqd3_bulk_run_receipt")
    if plan and not receipt and plan.get("execution_targets"):
        st.warning(
            f"Explicit action required: up to {plan['external_candidates_next_run']} external candidates, "
            f"{plan['planned_tavily_calls']} planned calls, hard cap {plan['hard_tavily_call_cap']}."
        )
        label = "Research next safe route-aware batch →" if plan["external_candidates_next_run"] else "Run local checks →"
        if st.button(label, key="tqd3_bulk_execute", disabled=not prepared):
            _execute_plan(st, bulk)
            return
    elif not plan:
        st.info("Prepare a selected batch before running research.")
    if receipt:
        st.success("Bounded run completed. Each completed candidate was persisted independently.")
        st.write({key: receipt[key] for key in (
            "calls_attempted", "calls_completed", "cache_hits",
            "candidates_completed", "candidates_failed", "candidates_pending",
        )})
        st.dataframe([{"candidate_id": candidate_id, **outcome}
                      for candidate_id, outcome in receipt["outcomes"].items()], hide_index=True, width="stretch")
        with st.expander("Advanced / run receipt"):
            st.json(receipt)
    if plan and (receipt or not plan.get("execution_targets")):
        if st.button("Continue to proposals & regression →", key="tqd3_bulk_research_continue"):
            _go(st, "proposals")
            return


def _render_proposals(st, bulk):
    local_handoff = st.session_state.get("tqd3_local_regression_handoff") or {}
    native_items = local_handoff.get("result_drafts") or []
    if local_handoff:
        st.markdown("##### Local proposal regression handoff")
        st.write({"native-compatible drafts": len(native_items),
                  "unsupported local actions": len(local_handoff.get("unsupported") or [])})
        st.caption("Compatible identity drafts use the existing bulk regression engine. Unsupported action types remain blocked from that path.")
        if st.button("Run existing regression preview for local-compatible drafts",
                     key="tqd3_local_native_regression", disabled=not native_items):
            prepared = st.session_state.get("tqd3_bulk_prepared") or {}
            try:
                st.session_state["tqd3_local_native_regression"] = bulk.preview_bulk_regression(
                    prepared.get("corpus"), native_items
                )
            except Exception as exc:
                st.error(f"Existing regression preview failed closed: {exc}")
        if st.session_state.get("tqd3_local_native_regression"):
            st.json(st.session_state["tqd3_local_native_regression"])

    from database.taxonomy_discovery_review_manager import list_governed_research_results
    try:
        all_saved = list_governed_research_results()
    except Exception as exc:
        st.error(f"Saved research unavailable: {exc}")
        all_saved = []
    receipt = st.session_state.get("tqd3_bulk_run_receipt") or {}
    current_ids = {row.get("research_result_id") for row in receipt.get("outcomes", {}).values()
                   if row.get("research_result_id")}
    current_saved = [row for row in all_saved if row["result"].get("research_result_id") in current_ids]
    st.session_state["tqd3_bulk_all_saved"] = all_saved
    st.session_state["tqd3_bulk_saved"] = current_saved
    show_historical = st.checkbox("Show historical / other persisted research", key="tqd3_bulk_show_historical")
    saved = all_saved if show_historical else current_saved
    if not saved:
        st.info("No current batch research results are available. Loading persisted results performs 0 network, 0 model, and 0 writes.")
        return

    st.dataframe([{
        "candidate": row["result"]["candidate"]["concept_key"],
        "route": row["result"]["candidate_route"],
        "research_status": row["result"]["recommended_next_action"],
        "source_count": len(row["result"].get("sources", [])),
        "first_party_sources": sum(s.get("source_class", "").startswith("first_party")
                                   for s in row["result"].get("sources", [])),
        "blockers": ", ".join(row["result"].get("conflicts_blockers", [])),
        "draft": (row.get("draft") or {}).get("kind"),
        "review": row["review"].get("decision", "undecided"),
        "fingerprint": row["result"]["result_fingerprint"],
    } for row in saved], hide_index=True, width="stretch")
    eligible = [row for row in saved
                if row["result"].get("recommended_next_action") in {
                    "technology_identity_proposal", "relationship_proposal",
                    "resolver_improvement", "new_capability_proposal",
                }
                and not row["result"].get("conflicts_blockers")
                and (row.get("review") or {}).get("decision") not in {"defer", "reject"}]
    eligible_by_id = {row["result"]["research_result_id"]: row for row in eligible}
    if not eligible:
        st.info("No current research result is eligible for proposal creation.")
        result_ids = []
    else:
        result_ids = st.multiselect(
            "Research results for explicit draft creation",
            list(eligible_by_id),
            key="tqd3_bulk_draft_results",
            format_func=lambda result_id: (
                f"{eligible_by_id[result_id]['result']['candidate'].get('concept_key') or eligible_by_id[result_id]['result']['candidate'].get('normalized_cluster')}"
                f" — {eligible_by_id[result_id]['result']['recommended_next_action'].replace('_', ' ')}"
            ),
        ) or []
    if st.button("Create/refresh proposals", key="tqd3_bulk_create_drafts", disabled=not result_ids):
        try:
            outcome = bulk.create_bulk_drafts(
                [row["result"] for row in saved],
                selected_result_ids=result_ids,
                explicit_creation=True,
            )
            st.session_state["tqd3_bulk_draft_outcome"] = outcome
            st.write(outcome)
        except Exception as exc:
            st.error(f"Draft creation stopped safely: {exc}")
    prepared = st.session_state.get("tqd3_bulk_prepared")
    draft_items = [{"result_id": row["result"]["research_result_id"], "draft": row["draft"]}
                   for row in saved if row.get("draft")]
    if st.button(
        "Preview temporary Job Match impact",
        key="tqd3_bulk_regression",
        disabled=not prepared or not prepared.get("corpus") or not draft_items,
    ):
        try:
            preview = bulk.preview_bulk_regression(prepared["corpus"], draft_items)
            from database.taxonomy_discovery_review_manager import save_governed_temporary_impact
            for item in preview["per_item"]:
                save_governed_temporary_impact(item["result_id"], item["report"])
            st.session_state["tqd3_bulk_regression"] = preview
        except Exception as exc:
            st.error(f"Temporary regression failed closed: {exc}")
    if st.session_state.get("tqd3_bulk_regression"):
        st.json(st.session_state["tqd3_bulk_regression"])
    with st.expander("Advanced / raw evidence and diagnostics"):
        st.json(saved)

    outcome = st.session_state.get("tqd3_bulk_draft_outcome") or {}
    eligible_drafts = bool(draft_items or outcome.get("created"))
    if st.button(
        "Continue to review →",
        key="tqd3_bulk_proposals_continue",
        disabled=not eligible_drafts or not st.session_state.get("tqd3_bulk_regression"),
    ):
        _go(st, "review")
        return


def _render_review(st, bulk):
    saved = st.session_state.get("tqd3_bulk_saved", [])
    if not saved:
        st.info("Create and refresh eligible proposals before review.")
        return
    from taxonomy_discovery.taxonomy_evolution import DECISIONS
    from database.taxonomy_discovery_review_manager import save_governed_research_review
    ids = [row["result"]["research_result_id"] for row in saved]
    result_id = st.selectbox("Proposal/result to review", ids, key="tqd3_bulk_review_result") or ids[0]
    row = next((item for item in saved if item["result"]["research_result_id"] == result_id), None)
    if not row:
        return
    decision = st.selectbox("Independent human decision", DECISIONS, key="tqd3_bulk_review_decision")
    reviewer = st.text_input("Reviewer", key="tqd3_bulk_reviewer")
    notes = st.text_area("Decision rationale", key="tqd3_bulk_review_notes")
    regression = next((item["report"] for item in st.session_state.get("tqd3_bulk_regression", {}).get("per_item", [])
                       if item["result_id"] == result_id), None)
    if st.button("Save review decision", key="tqd3_bulk_review_save"):
        try:
            review = save_governed_research_review(
                result_id,
                result_fingerprint=row["result"]["result_fingerprint"],
                decision=decision,
                reviewer=reviewer,
                notes=notes,
                draft=row.get("draft"),
                regression=regression,
            )
            row["review"] = review
            st.success("Independent decision saved. Approval does not publish.")
        except Exception as exc:
            st.error(f"Review rejected: {exc}")

    if (row.get("review") or {}).get("decision") == "approve_for_publication":
        if st.button("Run publication preflight →", key="tqd3_bulk_review_preflight"):
            try:
                preflight = bulk.prepare_publication_tranche([result_id])
            except Exception as exc:
                st.error(f"Publication preflight failed closed: {exc}")
            else:
                st.session_state["tqd3_bulk_publish_ids"] = [result_id]
                st.session_state["tqd3_bulk_preflight"] = preflight
                _go(st, "publish")
                return


def _render_publish(st, bulk):
    saved = st.session_state.get("tqd3_bulk_saved", [])
    approved = [row["result"]["research_result_id"] for row in saved
                if row["review"].get("decision") == "approve_for_publication"]
    publish_ids = st.multiselect(
        "Approved results for publication tranche",
        approved,
        key="tqd3_bulk_publish_ids",
    ) or []
    if st.button("Run publication preflight", key="tqd3_bulk_preflight_action", disabled=not publish_ids):
        try:
            st.session_state["tqd3_bulk_preflight"] = bulk.prepare_publication_tranche(publish_ids)
        except Exception as exc:
            st.error(f"Publication preflight failed closed: {exc}")
    preflight = st.session_state.get("tqd3_bulk_preflight")
    if preflight:
        st.json(preflight)
        confirmed = st.checkbox("I confirm this explicit production publication", key="tqd3_bulk_publish_confirm")
        if st.button("Publish approved tranche", key="tqd3_bulk_publish",
                     disabled=not preflight["ready"] or not confirmed):
            try:
                receipt = bulk.publish_publication_tranche(preflight, explicit_publish=True)
                st.success("Published through the governed publication contract: " + receipt["publication_id"])
            except Exception as exc:
                st.error(f"Publication failed closed: {exc}")


def render_bulk_candidate_operations():
    import streamlit as st
    from taxonomy_discovery import bulk_candidate_operations as bulk

    st.subheader("Taxonomy Knowledge Maintenance")
    st.caption("Corpus coverage, one local-first resolution queue, bounded governed research, regression preview, independent review, and separate publication.")
    stage = _render_navigation(st)
    st.markdown(f"#### {STAGE_LABELS[stage]}")

    renderers = {
        "select": _render_select,
        "plan": _render_plan,
        "research": _render_research,
        "proposals": _render_proposals,
        "review": _render_review,
        "publish": _render_publish,
    }
    renderers[stage](st, bulk)
