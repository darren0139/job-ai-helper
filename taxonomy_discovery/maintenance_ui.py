"""Secondary maintenance surface; all domain behavior stays in native services."""
from __future__ import annotations

import json
from threading import RLock

from taxonomy_discovery import maintenance_service as service

_action_lock = RLock()


def _lines(text):
    return [value.strip() for value in text.splitlines() if value.strip()]


def _perform(st, operation, label="Running maintenance operation…"):
    busy_key = "tm_running_" + label
    with _action_lock:
        if st.session_state.get(busy_key):
            st.info("This operation is already running.")
            return None
        st.session_state[busy_key] = True
    try:
        with st.status(label, expanded=True) as progress:
            try:
                result = operation()
            except Exception:
                progress.update(label="Failed — see diagnostic below", state="error")
                raise
            failed = isinstance(result, dict) and result.get("candidates_failed", 0) > 0
            progress.update(label=label + (" Failed" if failed else " Complete"),
                            state="error" if failed else "complete", expanded=failed)
            return result
    except Exception as exc:
        st.error(f"Operation failed closed: {exc}")
        return None
    finally:
        with _action_lock:
            st.session_state[busy_key] = False


def render_taxonomy_maintenance():
    import streamlit as st
    st.header("Taxonomy Maintenance")
    st.caption("Maintenance / diagnostics · deterministic corpus audit, governed research, and explicit publication.")
    st.info("Unresolved requirements are not automatically taxonomy gaps. Taxonomy Knowledge and Job Match Health measure different things.")

    st.subheader("A. Corpus Audit")
    source = st.selectbox("Corpus source", ["Stored JD corpus", "Frozen regression corpus"], key="tm_source")
    upload = st.file_uploader("Frozen regression corpus JSON", type="json", key="tm_corpus_upload") if source == "Frozen regression corpus" else None
    selected_jobs = st.text_input("Selected job IDs (optional, comma separated)", key="tm_jobs")
    _render_gap_assistant(st, source, upload, selected_jobs)
    audit_label = "Running deterministic corpus audit… No model or external research calls are being made."
    if st.button("Run Corpus Audit", key="tm_audit", disabled=st.session_state.get("tm_running_" + audit_label, False)):
        def audit():
            if source == "Frozen regression corpus" and upload is None:
                raise ValueError("Select a frozen corpus file")
            payload = json.loads(upload.getvalue()) if upload is not None else None
            jobs = [int(value.strip()) for value in selected_jobs.split(",") if value.strip()] or None
            existing = st.session_state.get("tm_snapshot")
            request_key = service.fingerprint({"source": source, "payload": payload, "jobs": jobs})
            if (existing and st.session_state.get("tm_audit_request") == request_key
                    and service.currentness(existing)["current"]):
                st.write("Reusing the current audit; duplicate execution skipped.")
                return existing
            st.write("Load corpus → replay / resolve requirements → consolidate and route gaps → build snapshot")
            st.session_state["tm_audit_request"] = request_key
            return service.run_corpus_audit(explicit_execution=True, corpus=payload, job_ids=jobs)
        snapshot = _perform(st, audit, audit_label)
        if snapshot:
            st.session_state["tm_snapshot"] = snapshot
            st.success(f"Audit complete — {len(snapshot['manifest']['job_ids'])} jobs processed")
            for key in ("tm_tranche", "tm_validation", "tm_export", "tm_review_preview", "tm_plan_receipt", "tm_routing"):
                st.session_state.pop(key, None)
    snapshot = st.session_state.get("tm_snapshot")
    if not snapshot:
        st.caption("No audit runs on page load or rerender. Research requires a separate explicit action.")
        return
    status = service.currentness(snapshot)
    if not status["current"]:
        st.warning("STALE / unavailable — " + "; ".join(status["blockers"]))
    disabled = not status["current"]

    st.subheader("B. Summary")
    summary = snapshot["audit"]["summary"]
    labels = {
        "meaningful_technical_requirements": "Meaningful technical requirements",
        "taxonomy_resolved_requirements": "Taxonomy resolved",
        "taxonomy_unresolved_requirements": "Unresolved",
    }
    columns = st.columns(3)
    for column, (key, label) in zip(columns, labels.items()):
        column.metric(label, summary[key])
    coverage_columns = st.columns(2)
    coverage_columns[0].metric("Required/core weighted taxonomy coverage", f"{summary['required_core_weighted_coverage']['percent']:.2f}%")
    coverage_columns[1].metric("Overall weighted taxonomy coverage", f"{summary['overall_weighted_coverage']['percent']:.2f}%")
    st.caption("Audited job IDs: " + ", ".join(map(str, snapshot["manifest"]["job_ids"])))
    st.write("Fix-layer concept counts", snapshot["fix_layer_counts"])
    st.write("Parsing/noise source exclusions", len(snapshot["parsing_noise_diagnostics"]))
    with st.expander("Excluded source prose / parsing diagnostics"):
        st.json(snapshot["parsing_noise_diagnostics"])
    st.write("Existing research backlog", snapshot["existing_research_backlog_count"])
    with st.expander("Job Match Health (separate from Taxonomy Knowledge)"):
        st.json(snapshot["audit"]["job_match_health"])

    st.subheader("C. Consolidated Gap Queue")
    layer = st.selectbox("Fix layer", ["All", *service.FIX_LAYERS], key="tm_layer")
    frequency = st.number_input("Minimum frequency", min_value=0, value=0, key="tm_frequency")
    impact = st.number_input("Minimum required/core impact", min_value=0.0, value=0.0, key="tm_impact")
    has_research = st.selectbox("Existing research", ["All", "Has research", "No research"], key="tm_existing")
    rows = snapshot["gap_rows"]
    research_status = st.selectbox("Research status", ["All", *sorted({r["research_status"] for r in rows})], key="tm_research_filter")
    review_status = st.selectbox("Review status", ["All", *sorted({r["review_status"] for r in rows})], key="tm_review_filter")
    published = st.selectbox("Publication status", ["All", "published", "not_published"], key="tm_publication_filter")
    visible = [r for r in rows if (layer == "All" or r["fix_layer"] == layer)
        and r["frequency"] >= frequency and r["required_core_impact"] >= impact
        and (has_research == "All" or bool(r["research_targets"]) == (has_research == "Has research"))
        and (research_status == "All" or r["research_status"] == research_status)
        and (review_status == "All" or r["review_status"] == review_status)
        and (published == "All" or r["publication_status"] == published)]
    st.dataframe([{k: v for k, v in r.items() if k not in {"requirements", "candidate", "readiness"}}
                  for r in visible], hide_index=True, width="stretch")
    st.caption("Priority is diagnostic only; it is not approval or a predicted score increase.")
    route_ids = st.multiselect("Bulk maintenance selection", [r["candidate_id"] for r in visible],
        format_func=lambda cid, rows={r["candidate_id"]: r for r in visible}: rows[cid]["concept"], key="tm_route_ids")
    for destination, label in ((service.NEEDS_DECOMPOSITION, "Send Selected to Decomposition Review"),
                               (service.REVIEW_FIX_LAYER, "Send Selected to Manual/Fix-Layer Review")):
        if st.button(label, key="tm_route_" + destination, disabled=disabled or not route_ids):
            receipt = _perform(st, lambda destination=destination: service.route_for_review(snapshot, route_ids, destination), label)
            if receipt:
                st.session_state.setdefault("tm_routing", []).append(receipt)
                st.session_state.pop("tm_tranche", None)
                st.session_state.pop("tm_plan_receipt", None)
                st.success("Session-only review routing saved; no candidate or knowledge changed.")
    if st.session_state.get("tm_routing"):
        st.write("Session review routing", st.session_state["tm_routing"])

    st.subheader("D. Concept Detail")
    if visible:
        by_id = {r["candidate_id"]: r for r in visible}
        cid = st.selectbox("Concept to inspect", list(by_id), format_func=lambda cid, rows=by_id: rows[cid]["concept"], key="tm_detail")
        detail = service.get_concept_detail(snapshot, cid)
        st.write("Fix layer", detail["fix_layer"])
        st.write("Why this fix layer", detail["reason"])
        st.write("Current capability resolution", detail["capability_resolution"])
        st.write("Technology identity", detail["technology_identity"])
        st.write("Contextual relationships", detail["contextual_relationships"])
        st.dataframe([{k: r.get(k) for k in ("job_id", "snapshot_id", "requirement_id", "requirement_text",
                      "importance", "score_eligible", "match_label", "taxonomy_cap_status", "sources", "source_provenance", "provenance")}
                      for r in detail["requirements"]], hide_index=True, width="stretch")
        for row in detail["persisted_research"]:
            st.write("Persisted finding", row["result"]["recommended_next_action"], row["review"])
        with st.expander("Advanced / exact provenance, evidence, and persisted research"):
            st.json(detail)

    st.subheader("E. Build Next Research Tranche")
    size = st.number_input("Tranche size", min_value=1, max_value=20, value=5, key="tm_size")
    if st.button("Build Next Research Tranche", key="tm_build_tranche", disabled=disabled):
        tranche = _perform(st, lambda: service.build_research_tranche(snapshot, size=int(size), explicit_creation=True,
            routing=st.session_state.get("tm_routing")), "Building next research tranche…")
        if tranche:
            st.session_state["tm_tranche"] = tranche
            st.session_state.pop("tm_export", None)
            st.session_state.pop("tm_plan_receipt", None)
    tranche = st.session_state.get("tm_tranche")
    if tranche:
        st.write("READY FOR RESEARCH")
        st.dataframe([{k: r[k] for k in ("concept", "fix_layer", "reason", "job_ids", "frequency",
            "required_core_impact", "research_targets", "latest_research_actions", "review_status")}
            for r in tranche["targets"]], hide_index=True, width="stretch")
        st.caption("Existing backlog targets are references. No provider calls or duplicate candidates are created.")
        with st.expander("Excluded candidates — decomposition / fix-layer review", expanded=bool(tranche["excluded_targets"])):
            st.dataframe([{k: row.get(k) for k in ("concept", "boundary_state", "boundary_reason", "next_action", "job_ids")}
                          for row in tranche["excluded_targets"]], hide_index=True, width="stretch")

    st.subheader("F. Explicit Research")
    if tranche and tranche["targets"]:
        by_id = {r["candidate_id"]: r for r in tranche["targets"]}
        selected = st.multiselect("Research targets", list(by_id), format_func=lambda cid, rows=by_id: rows[cid]["concept"], key="tm_research_ids")
        if st.button("Preview exact research plan", key="tm_plan", disabled=disabled or not selected):
            plan = _perform(st, lambda: service.plan_research(snapshot, tranche, selected), "Preparing exact governed research plan…")
            if plan:
                st.session_state["tm_plan_receipt"] = plan
        plan = st.session_state.get("tm_plan_receipt")
        if plan:
            st.dataframe(plan["execution_preview"], hide_index=True, width="stretch")
            if plan["provider_blocker"]:
                st.warning(plan["provider_blocker"])
            if plan["execution_targets"]:
                st.dataframe([{k: item.get(k) for k in ("candidate_id", "research_route", "research_purpose",
                    "planned_tavily_calls", "planned_query", "planned_questions", "authority_state")}
                    for item in plan["execution_targets"]], hide_index=True, width="stretch")
            else:
                if any(item["execution_status"] == "EXISTING RESEARCH / REFRESH REQUIRED" for item in plan["execution_preview"]):
                    st.info("No provider execution is planned. Refresh existing saved evidence in Human Review.")
                else:
                    st.info("No provider execution is planned. Inspect existing research in Human Review.")
            with st.expander("Advanced / exact bounded research plan and cache diagnostics"):
                st.json(plan)
        plan_matches = bool(plan and set(plan["selected_candidate_ids"]) == set(selected))
        confirm = st.checkbox("I confirm research of these selected targets using the configured provider",
            key="tm_confirm_research_" + (plan["plan_fingerprint"] if plan_matches else "unplanned"))
        can_execute = bool(plan_matches and plan["execution_targets"] and not plan["provider_blocker"])
        if st.button("Research / Refresh Selected", key="tm_research", disabled=disabled or not selected or not confirm or not can_execute):
            receipt = _perform(st, lambda: service.execute_research(snapshot, tranche, selected, explicit_execution=True,
                confirmed_plan_fingerprint=plan["plan_fingerprint"]),
                "Executing governed research — provider, interpretation, and receipt persistence…")
            if receipt:
                st.session_state["tm_research_receipt"] = receipt
                if receipt["candidates_failed"]:
                    st.error(f"Research failed for {receipt['candidates_failed']} candidate(s). See saved receipt diagnostics.")
                else:
                    st.success("Research complete; receipt saved. Research is not approval; approval is not publication.")
                new_ids = [item["research_result_id"] for item in receipt["outcomes"].values() if item.get("research_result_id")]
                st.session_state["tm_new_results"] = new_ids
                if new_ids:
                    st.session_state["tm_result"] = new_ids[0]
                st.session_state.pop("tm_plan_receipt", None)
        with st.expander("Research execution receipt / diagnostics"):
            st.json(st.session_state.get("tm_research_receipt", {}))

    _render_review(st, snapshot, disabled)
    st.subheader("J. Export / Debug")
    if st.button("Export Audit Bundle", key="tm_export_button"):
        st.session_state["tm_export"] = service.export_audit_bundle(snapshot,
            tranche=st.session_state.get("tm_tranche"), validation=st.session_state.get("tm_validation"))
    exported = st.session_state.get("tm_export")
    if exported:
        st.download_button("Download Audit Bundle", exported["zip"], "taxonomy_maintenance_audit.zip", "application/zip")
        st.download_button("Download Debug Summary", exported["debug_summary"], "taxonomy_maintenance_debug.md", "text/markdown")
        st.code(exported["debug_summary"], language="markdown")
    with st.expander("Advanced / reproducibility manifest"):
        st.json(snapshot["manifest"])


def _render_review(st, snapshot, disabled):
    from database import taxonomy_discovery_review_manager as store
    from taxonomy_discovery import governed_publication as publication
    from taxonomy_discovery.taxonomy_evolution import DECISIONS
    st.subheader("G. Human Review")
    saved = store.list_governed_research_results()
    if not saved:
        st.info("No persisted governed research. The audit and tranche do not write research or drafts.")
        return
    new_ids = st.session_state.get("tm_new_results", [])
    targets = service.build_review_targets(snapshot, saved_rows=saved, new_ids=new_ids)
    target_by_id = {target["primary"]["result"]["research_result_id"]: target for target in targets}
    by_id = {rid: target["primary"] for rid, target in target_by_id.items()}
    pending = st.session_state.pop("tm_pending_result", None)
    if pending in by_id:
        st.session_state["tm_result"] = pending
    if st.session_state.get("tm_result") not in by_id:
        st.session_state.pop("tm_result", None)
    subjects = [target["concept"] for target in targets]
    def label(rid, targets=target_by_id, subjects=subjects):
        target = targets[rid]
        value = target["status"] + " · " + target["concept"]
        if subjects.count(target["concept"]) > 1:
            value += " · scope " + target["group_id"][:8]
        if target["historical_attempts"]:
            value += f" · {len(target['historical_attempts'])} historical attempts"
        return value
    result_id = st.selectbox("Persisted research to review", list(by_id),
        format_func=label, key="tm_result")
    row = by_id[result_id]
    result = row["result"]
    target = target_by_id[result_id]
    st.write("CURRENT / MOST RELEVANT RESEARCH", result_id)
    with st.expander(f"Historical attempts ({len(target['historical_attempts'])}) — read-only diagnostics"):
        for attempt in target["historical_attempts"]:
            record = attempt["result"]
            with st.expander(record["research_result_id"] + " · " + (record.get("re_evaluated_at") or record.get("executed_at", ""))):
                st.json(attempt)
    with st.expander("Advanced / current candidate binding"):
        st.json({"current_candidate": target["current_candidate"], "binding_blocker": target["binding_blocker"]})
    if target["status"] == "STALE / REFRESH REQUIRED":
        st.info("Existing evidence is stale. Refresh interpretation locally before considering another provider request.")
        if target["binding_blocker"]:
            st.warning(target["binding_blocker"])
        if st.button("Refresh saved evidence (no provider calls)", key="tm_refresh_saved", disabled=disabled or bool(target["binding_blocker"])):
            refreshed = _perform(st, lambda: service.refresh_saved_research(snapshot,
                target["current_candidate"]["candidate_id"], explicit_execution=True), "Refreshing saved evidence with current governed rules…")
            if refreshed:
                st.session_state["tm_new_results"] = [refreshed["research_result_id"]]
                # The selectbox is already rendered; update its choice next run.
                st.session_state["tm_pending_result"] = refreshed["research_result_id"]
                st.session_state.pop("tm_plan_receipt", None)
                st.rerun()
    disabled = disabled or bool(target["binding_blocker"]) or target["status"] == "STALE / REFRESH REQUIRED"
    st.write("Research outcome", result["recommended_next_action"])
    st.write("Research blockers", result["conflicts_blockers"])
    bundle = result.get("support_bundle")
    if bundle:
        st.dataframe([{"Support required": name.replace("_", " ").capitalize(),
                       "Status": item["status"]} for name, item in bundle["fields"].items()],
                     hide_index=True, width="stretch")
        st.write("Source convergence — independent governed origins", bundle["independent_governed_origins"])
        st.caption("Search snippets are provisional. Convergence counts retrieved document text from governed origins.")
        st.write("Conflicts", bundle["conflicts"] or "none detected within deterministic checks")
        st.write("Sufficiency outcome", bundle["outcome"])
        if not bundle["eligible_for_human_review"]:
            st.write("Missing evidence", bundle["missing_evidence"])
            st.write("Recommended next research action", result.get("next_research_plan"))
        with st.expander("Advanced / exact support text, source scopes and origin provenance"):
            st.json(bundle)
    st.dataframe([{"title": s["evidence"].get("title"), "url": s["evidence"].get("url"),
                   "source_class": s.get("source_class"),
                   "accepted_definition_sentences": s.get("accepted_definition_sentences", [])}
                  for s in result.get("sources", [])], hide_index=True, width="stretch")
    fields = None
    if result["recommended_next_action"] == "new_capability_proposal" and not row["draft"]:
        with st.expander("Define bounded capability draft"):
            capability_id = st.text_input("Capability ID", key="tm_cap_id")
            label = st.text_input("Capability label", key="tm_cap_label")
            domain = st.text_input("Domain", key="tm_cap_domain")
            definition = st.text_area("Bounded definition", key="tm_cap_definition")
            concepts = _lines(st.text_area("Requirement match concepts (one per line)", key="tm_cap_concepts"))
            exclusions = _lines(st.text_area("Does not prove / exclusions (one per line)", key="tm_cap_exclusions"))
            evidence = _lines(st.text_area("Direct evidence concept terms (one per line)", key="tm_cap_evidence"))
            actions = _lines(st.text_area("Direct evidence implementation terms (one per line)", key="tm_cap_actions"))
            policy = _lines(st.text_area("Evidence policy references (one per line)", key="tm_cap_policy"))
            fields = {result_id: {"capability_id": capability_id, "label": label, "domain": domain,
                "definition": definition, "match_concepts": concepts, "does_not_prove": exclusions,
                "evidence_expectations": {"policy_references": policy, "evidence_tiers": [{"label": "direct",
                    "all_groups": [evidence, actions], "concepts": evidence, "reason": "explicit_application"}]}}}
    if st.button("Prepare governed draft", key="tm_draft", disabled=disabled or bool(result["conflicts_blockers"]) or bool(row["draft"])):
        outcome = _perform(st, lambda: service.bulk.create_bulk_drafts([result], selected_result_ids=[result_id],
            explicit_creation=True, capability_fields=fields))
        if outcome:
            st.write(outcome)
            st.rerun()
    if not row["draft"]:
        st.caption("No eligible saved draft. More authoritative research or manual review is required.")
        return
    draft = row["draft"]
    if draft["kind"] == "capability":
        proposal = draft["proposal"]
        st.write("Proposed capability", proposal["proposed_capability_id"], proposal["proposed_label"])
        st.write("Bounded definition", proposal["definition"])
        st.write("Requirement concepts / aliases", proposal["positive_match_concepts"], proposal["aliases"])
        st.write("Exclusions / non-implications", proposal["does_not_prove"])
    elif draft["kind"] == "technology":
        proposal = draft["proposal_bundle"]["proposals"][0]
        st.write("Proposed technology", proposal["label"], proposal["technology_id"])
        st.write("Aliases / capability relationship", proposal["aliases"], proposal["proposed_capability_id"])
    else:
        st.write("Draft kind", draft["kind"])
    with st.expander("Advanced / native draft and evidence predicates"):
        st.json(draft)
    if st.button("Preview Draft for Human Review", key="tm_review_preview_button", disabled=disabled):
        preview = _perform(st, lambda: service.run_candidate_validation(snapshot, [result_id], explicit_execution=True, approved=False), "Validating draft for human review…")
        if preview:
            _perform(st, lambda: store.save_governed_temporary_impact(result_id, preview["native"]["per_item"][0]["report"]))
            st.session_state["tm_review_preview"] = preview
    regression = publication.latest_impact(result_id)
    decision = st.selectbox("Human decision", DECISIONS, key="tm_decision")
    reviewer = st.text_input("Reviewer", key="tm_reviewer")
    notes = st.text_area("Review rationale", key="tm_review_notes")
    if st.button("Save Human Decision", key="tm_save_review", disabled=disabled):
        reviewed = _perform(st, lambda: store.save_governed_research_review(result_id,
            result_fingerprint=result["result_fingerprint"], decision=decision, reviewer=reviewer,
            notes=notes, draft=row["draft"], regression=regression))
        if reviewed:
            st.success("Human decision saved. No publication occurred.")
            st.rerun()
    st.subheader("H. Controlled Validation")
    published_ids = {receipt["research_result_id"] for receipt in publication.list_publications()
                     if receipt["status"] == "published"}
    approved_ids = [rid for rid, saved_row in by_id.items() if saved_row["draft"]
        and saved_row["review"].get("decision") == "approve_for_publication" and rid not in published_ids]
    selected_drafts = st.multiselect("Approved unpublished drafts to validate", approved_ids,
        default=[result_id] if result_id in approved_ids else [],
        format_func=lambda rid: by_id[rid]["result"]["candidate"]["concept_key"], key="tm_validate_results")
    if st.button("Validate Candidate Knowledge", key="tm_validate", disabled=disabled or not selected_drafts):
        validation = _perform(st, lambda: service.run_candidate_validation(snapshot, selected_drafts, explicit_execution=True), "Validating candidate knowledge against frozen corpus…")
        if validation:
            for item in validation["native"]["per_item"]:
                _perform(st, lambda item=item: store.save_governed_temporary_impact(item["result_id"], item["report"]))
            st.session_state["tm_validation"] = validation
            st.session_state.pop("tm_export", None)
    validation = st.session_state.get("tm_validation")
    report = validation or st.session_state.get("tm_review_preview")
    if report:
        st.write("Newly resolved / newly unresolved", report["newly_resolved"], report["newly_unresolved"])
        st.write("Newly DIRECT / NONE-to-positive", report["newly_direct"], report["none_to_positive"])
        st.dataframe(report["requirement_receipts"], hide_index=True, width="stretch")
        st.write("Score and rank changes", report["ranking_changes"])
        st.write("Warnings requiring evidence review", report["warnings"])
        with st.expander("Exact before/after reports, caps, rejections, and fingerprints"):
            st.json(report)
    st.subheader("I. Explicit Publication")
    if validation:
        preflight = service.publication_preflight(snapshot, validation, result_id)
        st.write("Publication fingerprint", validation["validation_fingerprint"])
        st.write("Publication preflight", preflight)
        confirmation = st.checkbox("I confirm publishing this exact human-approved, validated draft",
            key="tm_confirm_publish_" + validation["validation_fingerprint"])
        if st.button("Publish Validated Draft", key="tm_publish", disabled=disabled or not preflight["ready"] or not confirmation):
            receipt = _perform(st, lambda: service.publish_validated(snapshot, validation, result_id, explicit_publish=True), "Publishing exact human-approved validated draft…")
            if receipt:
                st.success("Published through the existing governance contract. Rerun the audit to refresh currentness.")


def _render_gap_assistant(st, source, upload, selected_jobs):
    from taxonomy_discovery import gap_reduction_assistant as assistant
    st.subheader("Taxonomy Gap Reduction Assistant")
    st.caption("Impact-first dry-run. Research may stop at scope refinement or deferral; publication is not the objective.")
    cols = st.columns(2)
    maximum = cols[0].number_input("Maximum actions", min_value=1, max_value=25, value=10, key="tm_gap_max")
    budget = cols[1].number_input("External research budget", min_value=0, max_value=20, value=3, key="tm_gap_budget")
    reuse = st.checkbox("Reuse exact current audit", value=True, key="tm_gap_reuse")
    options = {"include_local": st.checkbox("Include local/no-provider fixes", value=True, key="tm_gap_local"),
        "include_research": st.checkbox("Include research recommendations", value=True, key="tm_gap_research"),
        "include_scope": st.checkbox("Include scope/decomposition recommendations", value=True, key="tm_gap_scope"),
        "calculate_impact": st.checkbox("Calculate impact ranking", value=True, key="tm_gap_impact")}
    if st.button("Run Gap Reduction Assistant", key="tm_gap_run"):
        def run():
            payload = json.loads(upload.getvalue()) if upload is not None else None
            if source == "Frozen regression corpus" and payload is None:
                raise ValueError("Select a frozen corpus file")
            jobs = [int(value.strip()) for value in selected_jobs.split(",") if value.strip()] or None
            request_key = service.fingerprint({"source": source, "payload": payload, "jobs": jobs})
            snapshot = st.session_state.get("tm_snapshot")
            if not (reuse and snapshot and st.session_state.get("tm_audit_request") == request_key
                    and service.currentness(snapshot)["current"]):
                snapshot = service.run_corpus_audit(explicit_execution=True, corpus=payload, job_ids=jobs)
                st.session_state["tm_snapshot"] = snapshot
                st.session_state["tm_audit_request"] = request_key
            return assistant.build_plan(snapshot, max_actions=int(maximum), research_budget=int(budget), options=options)
        plan = _perform(st, run, "Planning safe gap-reduction actions… No external calls.")
        if plan:
            st.session_state["tm_gap_plan"] = plan
    plan = st.session_state.get("tm_gap_plan")
    if not plan:
        return
    snapshot = st.session_state.get("tm_snapshot")
    valid = bool(snapshot and service.currentness(snapshot)["current"]
                 and plan["audit_fingerprint"] == snapshot["audit_fingerprint"]
                 and plan["max_actions"] == maximum and plan["research_budget"] == budget and plan["options"] == options)
    if not valid:
        st.warning("Assistant plan stale or inputs changed. Run the dry-run again before any action.")
    st.write("CURRENT BASELINE — Taxonomy Knowledge")
    st.json(plan["baseline"])
    st.caption("Job Match Health remains separate. Estimated affected counts are not validated resolutions or score gains.")
    addressability = plan.get("taxonomy_addressability")
    if addressability:
        st.write("TAXONOMY ADDRESSABILITY")
        st.caption("Semantic knowledge status and remediation blockers are separate. All unresolved requirements remain accounted for; raw coverage and scoring are unchanged.")
        st.dataframe([{"Semantic status": status, "Requirements": values["count"], "Weight": values["weight"],
            "Required/core weight": values["required_core_weight"]} for status, values in addressability["summary"].items()],
            hide_index=True, width="stretch")
        triage = addressability.get("manual_review_triage")
        if triage:
            st.json(triage)
            for title, chosen in (
                ("HIGH-CONFIDENCE NON-ADDRESSABLE", [r for r in addressability["rows"]
                    if r.get("manual_review_triage", {}).get("decision") == "NOT_TAXONOMY_ADDRESSABLE" and r["semantic_addressability"] == "NOT_TAXONOMY_ADDRESSABLE"]),
                ("REMAINING UNDETERMINED MANUAL REVIEW", [r for r in addressability["rows"]
                    if r["primary_blocker"] == service.MANUAL and r["semantic_addressability"] == "UNDETERMINED_NEEDS_SCOPE_REVIEW"])):
                with st.expander(title):
                    st.dataframe([{"job_id": r["job_id"], "requirement_id": r["requirement_id"], "requirement": r["canonical_text"],
                        "reason_code": r["manual_review_triage"]["reason_code"], "subfamily": r["manual_review_triage"]["subfamily"],
                        "why": r["manual_review_triage"]["why"]} for r in chosen], hide_index=True, width="stretch")
                    if chosen:
                        n = st.selectbox("Inspect triage reason and original provenance", range(len(chosen)),
                            key="tm_manual_triage_" + title, format_func=lambda n, chosen=chosen: f"Job {chosen[n]['job_id']} · {chosen[n]['canonical_text']}")
                        st.json(chosen[n])
        sections = [("TRUE CAPABILITY GAPS", "TRUE_CAPABILITY_TAXONOMY_GAP"),
            ("NOT TAXONOMY-ADDRESSABLE", "NOT_TAXONOMY_ADDRESSABLE"),
            ("UNDETERMINED", "UNDETERMINED_NEEDS_SCOPE_REVIEW"),
            ("EXISTING TAXONOMY / OTHER BLOCKERS", "EXISTING_TAXONOMY_SUPPORTED")]
        for title, status in sections:
            with st.expander(title):
                rows = [r for r in addressability["rows"] if r["semantic_addressability"] == status]
                st.dataframe([{k: r[k] for k in ("job_id", "requirement_id", "canonical_text", "importance", "weight",
                    "addressability_reason", "primary_blocker", "secondary_blockers", "review_state")} for r in rows],
                    hide_index=True, width="stretch")
                if rows:
                    index = st.selectbox("Inspect requirement", range(len(rows)), key="tm_addressability_" + status,
                        format_func=lambda n, rows=rows: f"Job {rows[n]['job_id']} · {rows[n]['requirement_id']} · {rows[n]['canonical_text']}")
                    st.json(rows[index])
        with st.expander("True gap priorities / addressability accounting diagnostics"):
            st.json({k: addressability[k] for k in ("top_true_capability_gaps", "unique_unresolved_requirements", "semantic_count_total",
                "primary_blocker_counts", "blocker_association_counts", "raw_denominator_unchanged")})
    columns = ["rank", "concept", "fix_layer", "requirements_affected", "jobs_affected", "required_core_weight",
               "mentioned_requirements", "atomically_addressable_requirements", "estimated_directly_resolvable", "validated_resolved",
               "research_state", "provider_calls_required", "proposed_action", "priority_reason"]
    columns += ["foundational_rank", "impact_role", "unique_requirements", "dependent_requirement_count", "dependency_ids", "marginal_mentioned_requirements"]
    st.caption("Foundational ≠ directly resolving. Shared dependencies are review opportunities; temporary validation alone proves resolution.")
    st.write("FOUNDATIONAL ACTIONS")
    st.dataframe([{k: a.get(k) for k in columns} for a in plan["foundational_priority"][:int(maximum)]], hide_index=True, width="stretch")
    st.write("DIRECT GAP-REDUCTION ACTIONS")
    if plan["directly_resolving_actions"]:
        st.dataframe(plan["directly_resolving_actions"], hide_index=True, width="stretch")
    else:
        st.info("No directly resolving action is established by this dry-run. Bundle priorities below require review and temporary validation.")
    st.write("DIRECT / BUNDLE PRIORITY — blocked opportunities, not predicted resolutions")
    st.dataframe(plan["direct_gap_reduction_priority"][:int(maximum)], hide_index=True, width="stretch")
    with st.expander("DEPENDENCY BUNDLES"):
        st.dataframe(plan["dependency_bundles"], hide_index=True, width="stretch")
    from taxonomy_discovery import contextual_relationship_validation as relationships
    inventory = plan["contextual_relationship_inventory"]
    with st.expander("CONTEXTUAL RELATIONSHIP CANDIDATES"):
        st.caption("Requirement-context hypotheses; technology identity alone is not capability proof. No publication controls.")
        if st.button("Validate Contextual Relationships Offline", key="tm_relationship_validate", disabled=not valid):
            receipt = _perform(st, lambda: relationships.validate(snapshot, inventory, explicit_execution=True),
                "Validating contextual relationships… Frozen native replay; no external calls.")
            if receipt:
                st.session_state["tm_relationship_validation"] = receipt
        receipt = st.session_state.get("tm_relationship_validation")
        current_receipt = receipt and relationships.report_current(snapshot, inventory, receipt)
        decisions = {r["relationship_id"]: r for r in receipt["candidate_decisions"]} if current_receipt else {}
        st.dataframe([{**{k: c[k] for k in ("technology", "context", "existing_capability_id", "unique_unresolved_requirements",
            "jobs_affected", "required_core_weight", "estimated_impact", "validated_impact", "decision")},
            **{k: decisions[c["relationship_id"]][k] for k in ("validated_impact", "decision") if c["relationship_id"] in decisions}}
            for c in inventory["candidates"]], hide_index=True, width="stretch")
        if receipt:
            if current_receipt:
                st.json(receipt)
            else:
                st.warning("Relationship validation is stale; explicitly validate the current inventory.")
        with st.expander("Requirement contexts / capability boundaries / negative fixtures / research state"):
            st.json(inventory)
    with st.expander("DECOMPOSITION / PARSER BOTTLENECKS"):
        st.dataframe(plan["decomposition_parser_bottlenecks"], hide_index=True, width="stretch")
        triage = plan.get("structure_unavailable_triage")
        if triage:
            with st.expander(f"native_structure_unavailable ({triage['total']})"):
                st.caption(f"{triage['total']} blocked-review opportunities; no predicted resolutions.")
                st.dataframe([{
                    "Root cause": r["root_cause"], "Requirements": r["unique_unresolved_requirements"],
                    "Jobs": r["jobs_affected"], "Core weight": r["required_core_weight"],
                    "Native behavior correct": {True: "yes", False: "no", None: "unknown"}[r["native_behavior_correct"]],
                    "Code change needed": {True: "yes", False: "no", None: "unknown"}[r["code_change_required"]],
                    "Next action": r["recommended_next_action"],
                } for r in triage["subfamilies"]], hide_index=True, width="stretch")
                st.info(triage["recommendation"] + ": " + triage["recommendation_reason"])
                with st.expander("Requirement provenance / native probes / downstream review actions"):
                    st.json(triage)
    with st.expander("Requirement dependency graphs / unique unions / marginal impact"):
        st.json(plan["dependency_impact_summary"])
        st.json(plan["requirement_dependency_graphs"])
    groups = {"LOCAL / NO PROVIDER WORK": lambda a: not a["provider_calls_required"],
        "RESEARCH CANDIDATES": lambda a: a["provider_calls_required"] > 0,
        "NEEDS DECOMPOSITION": lambda a: a["research_state"] == service.NEEDS_DECOMPOSITION,
        "RELATIONSHIP WORK": lambda a: a["fix_layer"] == service.RELATIONSHIP_GAP,
        "PARSER / CANONICALISATION": lambda a: a["fix_layer"] == service.PARSING_PROBLEM,
        "EVIDENCE POLICY": lambda a: a["fix_layer"] == service.EVIDENCE_PROBLEM,
        "MANUAL REVIEW": lambda a: a["fix_layer"] == service.MANUAL,
        "DEFERRED": lambda a: a["research_state"] in assistant.TERMINAL}
    for label, predicate in groups.items():
        rows = [a for a in plan["all_actions"] if predicate(a)]
        with st.expander(f"{label} ({len(rows)})"):
            st.dataframe([{k: a.get(k) for k in columns} for a in rows], hide_index=True, width="stretch")
    if plan["all_actions"]:
        action = st.selectbox("Assistant action to inspect", plan["all_actions"],
            format_func=lambda a: f"{a['rank']}. {a['concept']} — {a['research_state']}", key="tm_gap_detail")
        st.json(action)
        if action["fix_layer"] == service.IDENTITY_GAP:
            _render_identity_remediation(st, snapshot, action, valid)
    with st.expander("Exact assistant plan / currentness / bounded research preview"):
        st.json(plan)
    st.download_button("Download assistant JSON", json.dumps(plan, indent=2), "taxonomy_gap_reduction_plan.json", key="tm_gap_json")
    st.download_button("Download assistant Markdown", assistant.markdown_report(plan), "taxonomy_gap_reduction_plan.md", key="tm_gap_md")
    confirm = st.checkbox("I confirm this exact assistant plan (including any external calls shown)", key="tm_gap_confirm")
    fingerprint = st.text_input("Exact assistant plan fingerprint", key="tm_gap_fingerprint")
    external = st.checkbox("Authorize the bounded external research shown in this plan", key="tm_gap_external")
    if st.button("Execute Exact Assistant Plan", key="tm_gap_execute", disabled=not valid or not confirm
        or fingerprint != plan["assistant_plan_fingerprint"] or (plan["planned_external_calls"] > 0 and not external)):
        receipt = _perform(st, lambda: assistant.execute_plan(snapshot, plan, explicit_execution=True,
            confirmed_fingerprint=fingerprint, allow_external_research=external), "Executing exact assistant plan…")
        if receipt:
            st.session_state["tm_gap_receipt"] = receipt
            st.info("Re-preview after execution. Research outcomes may require scope refinement or deferral; nothing was approved or published.")
    if st.session_state.get("tm_gap_receipt"):
        with st.expander("Assistant execution receipt"):
            st.json(st.session_state["tm_gap_receipt"])

    eligible = [a["selected_result_id"] for a in plan["all_actions"] if a["research_state"] == "ELIGIBLE_FOR_HUMAN_REVIEW"]
    if eligible:
        result_ids = st.multiselect("Eligible saved drafts for temporary impact preview", eligible, key="tm_gap_validate_ids")
        if st.button("Preview temporary draft impact", key="tm_gap_validate", disabled=not valid or not confirm
            or fingerprint != plan["assistant_plan_fingerprint"] or not result_ids):
            validation = _perform(st, lambda: assistant.validate_drafts(snapshot, plan, result_ids,
                explicit_execution=True, confirmed_fingerprint=fingerprint), "Validating temporary candidate overlay…")
            if validation:
                st.session_state["tm_gap_validation"] = validation
        validation = st.session_state.get("tm_gap_validation")
        if validation:
            st.write("VALIDATED IMPACT — temporary overlay; no approval or publication")
            with st.expander("Baseline/overlay changes, ranking, duplicate credit, canaries, caps and rejections"):
                st.json(validation)


def _render_identity_remediation(st, snapshot, action, valid):
    from taxonomy_discovery import technology_identity_remediation as remediation
    cid = action["candidate_id"]
    if st.button("Inspect Identity Gap", key="tm_identity_inspect", disabled=not valid):
        detail = _perform(st, lambda: remediation.inspect_identity_gap(snapshot, cid), "Inspecting native identity gap…")
        if detail:
            st.session_state["tm_identity_detail"] = {"audit": snapshot["audit_fingerprint"], "detail": detail}
            st.session_state.pop("tm_identity_proposal", None)
            st.session_state.pop("tm_identity_validation", None)
    saved = st.session_state.get("tm_identity_detail")
    if not saved or saved["audit"] != snapshot["audit_fingerprint"] or saved["detail"]["candidate_id"] != cid:
        return
    detail = saved["detail"]
    st.write("Estimated assistant impact", {"requirements": action["requirements_affected"], "jobs": action["jobs_affected"]})
    st.dataframe(detail["requirements"], hide_index=True, width="stretch")
    st.caption("Identity establishes a name, not capability or candidate evidence. Compound requirements retain native semantics.")
    if st.button("Prepare Identity Proposal", key="tm_identity_prepare", disabled=not valid):
        proposal = _perform(st, lambda: remediation.prepare_identity_proposal(snapshot, cid, explicit_execution=True), "Preparing identity-only draft…")
        if proposal:
            st.session_state["tm_identity_proposal"] = proposal
            st.session_state.pop("tm_identity_validation", None)
    proposal = st.session_state.get("tm_identity_proposal")
    if not proposal or proposal["candidate_id"] != cid or proposal["audit_fingerprint"] != snapshot["audit_fingerprint"]:
        return
    st.write("Proposed identity", proposal["canonical_technology_id"], proposal["canonical_label"])
    st.write("Bounded aliases", proposal["aliases"])
    st.write("Alias collision checks", proposal["alias_collisions"])
    if st.button("Validate Temporary Registry Overlay", key="tm_identity_validate", disabled=not valid):
        report = _perform(st, lambda: remediation.validate_identity_proposal(snapshot, proposal, explicit_execution=True), "Validating identity through native corpus replay…")
        if report:
            st.session_state["tm_identity_validation"] = report
    report = st.session_state.get("tm_identity_validation")
    if report and report["proposal_fingerprint"] == proposal["proposal_fingerprint"]:
        st.write("Validated impact — temporary overlay", report["validated_impact"])
        st.write("Validation status", report["validation_status"])
        st.write("Baseline", report["baseline"])
        st.write("Temporary overlay", report["temporary_overlay"])
        st.caption("STOP for human review. No approval or production publication is available in this identity workflow.")
        with st.expander("Identity validation — exact rows, currentness, collisions and safety diagnostics"):
            st.json(report)
        st.download_button("Download identity validation", json.dumps(report, indent=2), "identity_validation.json", key="tm_identity_json")
