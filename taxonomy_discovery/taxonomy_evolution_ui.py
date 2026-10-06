"""Governed local gap inspection and review; no research or publication on render."""
import json


def render_governed_research():
    import streamlit as st
    from taxonomy_discovery import governed_research as research
    from database.taxonomy_discovery_review_manager import (list_governed_research_results,
        save_governed_research_draft, save_governed_research_review)
    from taxonomy_discovery.taxonomy_evolution import DECISIONS
    st.subheader("Governed Gap Review and Research")
    st.caption("Research, draft creation, human approval and explicit production publication are separate.")
    flash = st.session_state.pop("tqd3_h1_flash",None)
    if flash:
        st.success(flash)
    from taxonomy_discovery.governed_publication_ui import render_governed_review_ledger
    render_governed_review_ledger()
    st.markdown("**Step 1 — Prepare Gap Review**")
    if st.button("Prepare / Refresh Gap Review", key="tqd3_h1_prepare"):
        try:
            st.session_state["tqd3_h1_prepared"] = research.prepare_gap_review()
            st.session_state.pop("tqd3_h1_plan", None)
            st.session_state.pop("tqd3_h1_executed_plan", None)
        except Exception as exc:
            st.error(f"Local preparation failed closed: {exc}")
    with st.expander("Advanced / reproducibility · frozen artifacts"):
        corpus = st.file_uploader("Historical frozen corpus JSON", type=["json"], key="tqd3_h1_corpus")
        gaps = st.file_uploader("Historical governed gap JSON", type=["json"], key="tqd3_h1_gaps")
        if st.button("Prepare uploaded artifacts", key="tqd3_h1_manual", disabled=corpus is None and gaps is None):
            try:
                st.session_state["tqd3_h1_prepared"] = research.prepare_gap_review(
                    corpus=json.loads(corpus.getvalue()) if corpus else None,
                    gaps=json.loads(gaps.getvalue()) if gaps else None)
                st.session_state.pop("tqd3_h1_plan", None)
                st.session_state.pop("tqd3_h1_executed_plan", None)
            except Exception as exc:
                st.error(f"Uploaded artifacts fail closed: {exc}")
        prepared = st.session_state.get("tqd3_h1_prepared")
        if prepared:
            st.json({k:prepared[k] for k in ("current_versions", "artifact_fingerprint")})
            for key, filename in (("corpus","tqd3_job_match_corpus.json"), ("gaps","tqd3_taxonomy_gap_inputs.json"), ("report","tqd3_taxonomy_candidates.json")):
                if prepared[key] is not None:
                    st.download_button("Download "+key, json.dumps(prepared[key],indent=2)+"\n", file_name=filename, mime="application/json", key="tqd3_h1_download_"+key)
            st.download_button("Download refined candidate CSV", prepared["csv"], file_name="tqd3_taxonomy_candidates.csv", mime="text/csv")
    with st.expander("TQ-D3 verification/publication canaries · diagnostics only"):
        st.json(research.canary_status())
    prepared = st.session_state.get("tqd3_h1_prepared")
    if not prepared:
        st.info("Prepare current saved snapshots or upload frozen artifacts to start. Preparation uses local deterministic functions only.")
        return
    candidates = prepared["candidates"]
    st.json({k:prepared["report"][k] for k in ("source_observations", "concept_count", "candidate_route_counts", "recurrence_counts")})
    from taxonomy_discovery.research_atomicity import candidate_atomicity
    atomicity = {c["candidate_id"]:candidate_atomicity(c) for c in candidates}
    normal = [c for c in candidates if c["candidate_route"] in research.ELIGIBLE_ROUTES and atomicity[c["candidate_id"]]["atomicity_status"] != "compound_requires_decomposition"]
    compounds = [c for c in candidates if atomicity[c["candidate_id"]]["atomicity_status"] == "compound_requires_decomposition"]
    st.markdown("**Step 2 — Select eligible atomic research candidates (maximum 3)**")
    st.dataframe([{"candidate_id":c["candidate_id"], "Concept":c["concept_key"],
        "Initial Phase-G research route":c["recommended_research_route"], "Refined candidate route":c["candidate_route"],
        "Jobs":c["job_count"], "Occurrences":c["occurrence_count"], "Reason":c["routing_reason"]} for c in normal], hide_index=True, width="stretch")
    with st.expander("Needs decomposition before research · preview only"):
        st.dataframe([{"Concept":"[Needs decomposition] "+c["concept_key"], "Relation":atomicity[c["candidate_id"]]["logical_relation"],
            "Detected children":", ".join(atomicity[c["candidate_id"]]["detected_entities"])} for c in compounds],hide_index=True,width="stretch")
        st.json([atomicity[c["candidate_id"]] for c in compounds])
        st.caption("Parent requirements/provenance are preserved. No child requirements or Job Match changes are created.")
    with st.expander("Advanced / quarantined administrative, noise and insufficient inputs"):
        st.json([c for c in candidates if c["candidate_route"] not in research.ELIGIBLE_ROUTES])
    eligible = sorted(normal,
                      key=lambda c:(research.ELIGIBLE_ROUTES.index(c["candidate_route"]),c["concept_key"],c["candidate_id"]))
    by_id = {c["candidate_id"]:c for c in eligible}
    labels = {"existing_capability_resolver_issue":"Resolver","technology_relationship":"Relationship","technology_identity":"Identity","possible_new_capability":"Capability"}
    selected = []
    frozen = bool(st.session_state.get("tqd3_h1_plan") and st.session_state.get("tqd3_h1_executed_plan") == st.session_state["tqd3_h1_plan"]["plan_fingerprint"])
    if frozen:
        st.info("Selection frozen because this research plan has already been executed. Prepare / Refresh Gap Review to create another plan. Saved evidence remains available below.")
    for slot in range(research.MAX_BATCH):
        cid = st.selectbox("Research candidate "+str(slot+1),[None,*[cid for cid in by_id if cid not in selected]],
            format_func=lambda cid:"No selection" if cid is None else "["+labels[by_id[cid]["candidate_route"]]+"] "+by_id[cid]["concept_key"],key="tqd3_h1_selection_"+str(slot),disabled=frozen)
        if cid:
            selected.append(cid)
    external_resolver = st.checkbox("Also request external supporting evidence for resolver issues", value=False, key="tqd3_h1_external_resolver",disabled=frozen)
    research_round = st.number_input("Research round (0 reuses initial results; increase for explicit follow-up)",min_value=0,max_value=3,value=0,step=1,key="tqd3_h1_round",disabled=frozen) or 0
    st.markdown("**Step 3 — Preview research plan**")
    if st.button("Preview selected research plan", key="tqd3_h1_plan_preview", disabled=not selected or frozen):
        try:
            st.session_state["tqd3_h1_plan"] = research.research_plan(candidates, selected_candidate_ids=selected, external_resolver=external_resolver, research_round=research_round)
        except Exception as exc:
            st.error(f"Planning rejected: {exc}")
    plan = st.session_state.get("tqd3_h1_plan")
    if plan:
        for target in plan["targets"]:
            st.write(target["subject"], "·", target["candidate"]["candidate_route"])
            st.write("Research questions",target["questions"])
            st.write("Why research is needed",target["reason"])
            st.write("Source examples",target["candidate"]["examples"])
            st.write("Preferred sources",target["preferred_source_classes"])
            st.caption("External query planned" if target["external_requested"] and not target["requires_decomposition"] else "Local deterministic review; no external query planned")
        with st.expander("Advanced / complete research plan and fingerprints"):
            st.json(plan)
        same_selection = sorted(selected) == sorted(t["candidate"]["candidate_id"] for t in plan["targets"])
        same_options = all(t["external_requested"] == (external_resolver or t["candidate"]["candidate_route"] != "existing_capability_resolver_issue") for t in plan["targets"])
        same_options = same_options and all(t["research_round"] == research_round for t in plan["targets"])
        st.markdown("**Step 4 — Explicitly run bounded research**")
        st.warning("This action may call Tavily Search: at most 3 candidates, one query each, at most two attempts each. Resolver issues use local knowledge first. Saved matching results are reused.")
        if st.button("Run selected bounded research", key="tqd3_h1_execute", disabled=frozen or not same_selection or not same_options):
            try:
                if frozen or not same_selection or not same_options:
                    raise ValueError("Selection/options changed; preview a new plan")
                receipt = research.execute_plan(plan, candidates, explicit_execution=True)
                st.session_state["tqd3_h1_receipt"] = receipt
                if receipt["failures"]:
                    st.error("Some candidates failed; completed research remains saved.")
                    st.json(receipt["failures"])
                else:
                    st.success(f"Completed or reused {len(receipt['results'])} research result(s).")
                    st.session_state["tqd3_h1_executed_plan"]=plan["plan_fingerprint"]
                    st.session_state["tqd3_h1_flash"]="Research evidence saved. Saved matching results are reused; rerender performs no research."
                    st.rerun()
            except Exception as exc:
                st.error(f"Research stopped: {exc}. Completed results remain saved.")
    st.markdown("**Step 5 — Review research evidence**")
    st.caption("Step 4 alternative: Re-evaluate saved evidence below uses only persisted raw evidence, with zero Tavily/model/network calls.")
    try:
        saved = list_governed_research_results()
    except Exception as exc:
        st.error(f"Saved research unavailable: {exc}")
        return
    superseded = {row["result"].get("interpretation_lineage",{}).get("previous_research_result_id") for row in saved}
    from taxonomy_discovery.governed_publication import list_publications, latest_impact
    published = {r["research_result_id"]:r for r in list_publications() if r["status"] == "published"}
    for row in saved:
        result, draft = row["result"], row["draft"]
        rid = result["research_result_id"]
        if rid in superseded:
            with st.expander("Advanced / earlier research interpretation · "+result["candidate"]["concept_key"]):
                st.json(result)
            continue
        with st.expander(result["candidate"]["concept_key"]+" · "+result["candidate_route"]):
            if rid in published:
                st.success("Published to production knowledge version "+published[rid]["version_after"]+". Review/publication history is retained in Governed Review Ledger.")
                with st.expander("Advanced / published research and draft history"):
                    st.json(row)
                continue
            persisted_report = latest_impact(rid)
            state = row["review"].get("decision","undecided")
            if state == "approve_for_publication":
                st.info("Approved — pending explicit publication in Governed Review Ledger.")
            elif state == "reject":
                st.info("Rejected — historical draft retained.")
            elif draft and persisted_report:
                st.info("Temporary regression saved — human review required; publication blockers must be checked.")
            elif draft:
                st.info("Draft created — awaiting temporary regression.")
            else:
                st.info("Research evidence saved — draft creation is a separate explicit action.")
            if st.button("Re-evaluate saved evidence",key=rid+"_reevaluate"):
                try:
                    updated = research.re_evaluate_saved_evidence(result,explicit_execution=True,persist=True)
                    st.success("Saved evidence re-evaluated without a new search. Original evidence/history preserved: "+updated["research_result_id"])
                    st.rerun()
                except Exception as exc:
                    st.error(f"Saved-evidence re-evaluation rejected: {exc}")
            st.write("Examples",result["candidate"]["examples"])
            st.write("Recurrence",result["candidate"]["job_count"],"jobs;",result["candidate"]["occurrence_count"],"occurrences. Frequency is context, not proof.")
            st.write("Source jobs",sorted({p["job_id"] for p in result["source_gap_provenance"]}))
            st.write("Authoritative evidence",result["authoritative_evidence_summary"])
            st.dataframe([{"Source":s["evidence"].get("url"),"Source class":s["source_class"],
                           "Accepted definitions":"\n".join(s["accepted_definition_sentences"])} for s in result["sources"]],hide_index=True,width="stretch")
            st.write("Identity finding",result["identity_finding"])
            st.write("Relationship finding",result["relationship_finding"])
            st.write("Existing capability overlap",result["existing_capability_assessment"]["exact_matches"],result["existing_capability_assessment"]["high_overlap_candidates"])
            st.write("Possible new capability assessment",result["possible_new_capability_assessment"])
            st.write("Blockers",result["conflicts_blockers"])
            st.write("Recommended next action",result["recommended_next_action"])
            with st.expander("Advanced / raw provider evidence and research diagnostics"):
                st.json(result)
            st.markdown("**Step 6 — Create proposal if warranted**")
            fields = None
            if result["recommended_next_action"] == "new_capability_proposal":
                st.caption("Enter a definition, positive concepts, explicit boundaries and native evidence tiers for human review. No new scoring policy is created.")
                fields = {"capability_id":st.text_input("Capability ID",key=rid+"_cap"),
                    "label":st.text_input("Label",key=rid+"_label"),
                    "domain":st.selectbox("Existing domain",sorted({c["domain"] for c in research.get_default_taxonomy().capabilities}),key=rid+"_domain"),
                    "definition":st.text_area("Definition",key=rid+"_definition"),
                    "match_concepts":(st.text_area("Positive concepts (one per line)",key=rid+"_concepts") or "").splitlines(),
                    "does_not_prove":(st.text_area("Does not prove (one per line)",key=rid+"_boundaries") or "").splitlines()}
                evidence_terms = (st.text_area("Direct evidence application terms (one per line)", value="built\nimplemented", key=rid+"_evidence_terms") or "").splitlines()
                fields["evidence_expectations"] = {"policy_references":["existing deterministic evidence tiers"],
                    "evidence_tiers":[{"label":"direct", "all_groups":[fields["match_concepts"], evidence_terms],
                        "reason":"explicit_application", "concepts":fields["match_concepts"]}]}
            from taxonomy_discovery.resolver_improvement import RESOLVER_DRAFT_VERSION
            legacy_resolver = bool(draft and draft.get("kind") == "resolver_improvement" and draft.get("resolver_draft_version") != RESOLVER_DRAFT_VERSION)
            replace_rejected = legacy_resolver and row["review"].get("decision") == "reject"
            if legacy_resolver:
                st.caption("Legacy resolver draft cannot be approved. Record Reject first; then create a guarded replacement. Its rejection history is retained.")
            if st.button("Create guarded replacement draft" if replace_rejected else "Create draft proposal",key=rid+"_draft",disabled=draft is not None and not replace_rejected) and (draft is None or replace_rejected):
                try:
                    draft = research.create_draft(result, explicit_creation=True, capability_fields=fields)
                    save_governed_research_draft(result,draft)
                    st.session_state.pop(rid+"_impact_report", None)
                    st.session_state.pop(rid+"_decision", None)
                    st.success("Draft saved. Human decision remains undecided.")
                    st.session_state["tqd3_h1_flash"]="Draft created — awaiting temporary regression"
                    st.rerun()
                except Exception as exc:
                    st.error(f"Draft rejected: {exc}")
            st.markdown("**Step 7 — Preview temporary Job Match impact**")
            if draft:
                st.json(draft)
                if st.button("Preview temporary Job Match impact",key=rid+"_impact",disabled=prepared["corpus"] is None):
                    st.session_state.pop(rid+"_impact_report", None)
                    try:
                        st.session_state[rid+"_impact_report"] = research.temporary_impact(prepared["corpus"], draft)
                        from database.taxonomy_discovery_review_manager import save_governed_temporary_impact
                        save_governed_temporary_impact(rid, st.session_state[rid+"_impact_report"])
                        st.session_state["tqd3_h1_flash"]="Temporary regression saved — human review required"
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Temporary impact failed closed: {exc}")
            from taxonomy_discovery.governed_publication import latest_impact
            report = latest_impact(rid)
            if report and (prepared["corpus"] is None or report.get("corpus_fingerprint") != research.fingerprint(prepared["corpus"])):
                report = None
            if report:
                st.write("Affected jobs",report["affected_jobs"])
                if "unexpectedly_changed_requirements" in report:
                    st.write("Intended changed requirements",report.get("intended_changed_requirements",[]))
                    st.write("Newly resolved / unchanged",report["newly_resolved_count"],report["unchanged_count"])
                    st.write("Unexpectedly changed requirements requiring review",report["unexpectedly_changed_requirements"])
                    if report.get("publication_blockers"):
                        st.error("Publication blocked: " + ", ".join(report["publication_blockers"]) + ". Reject or revise this resolver draft.")
                    else:
                        st.caption("No unexpected requirement changes. Human review and current regression checks remain required before approval.")
                st.dataframe([{"Job":j["job_id"], "Requirement":c["requirement_id"],
                    "Before":(c.get("before") or {}).get("resolution_status"), "After":(c.get("after") or {}).get("resolution_status"),
                    "Before capability":(c.get("before") or {}).get("capability_id"), "After capability":(c.get("after") or {}).get("capability_id"),
                    "Changed fields":", ".join(c["changed_fields"])} for j in report["jobs"] for c in j.get("requirement_changes",[])],hide_index=True,width="stretch")
                st.write("Score differences",[{"job":j["job_id"],"deltas":j.get("job_score_deltas")} for j in report["jobs"]])
                st.write("Duplicate-credit / availability checks",[{"job":j["job_id"], "classification":j["classification"],
                    "violations":j.get("duplicate_credit_violations",[]),"blockers":j.get("blockers",[])} for j in report["jobs"]])
                with st.expander("Advanced / full temporary Job Match report"):
                    st.json(report)
                st.caption("Temporary resolution, evidence and score differences require review; a score increase does not establish correctness.")
            st.markdown("**Step 8 — Human decision**")
            st.json(row["review"])
            decision = st.selectbox("Human decision",DECISIONS,index=DECISIONS.index(row["review"].get("decision","undecided")),key=rid+"_decision")
            reviewer = st.text_input("Reviewer",key=rid+"_reviewer")
            notes = st.text_area("Decision rationale",key=rid+"_notes")
            if st.button("Record human decision",key=rid+"_review"):
                try:
                    save_governed_research_review(rid,result_fingerprint=result["result_fingerprint"],decision=decision,reviewer=reviewer,notes=notes,regression=report)
                    st.session_state["tqd3_h1_flash"]="Human decision saved: "+decision+". Approval is separate from publication."
                    st.rerun()
                except Exception as exc:
                    st.error(f"Review rejected: {exc}")


def render_taxonomy_evolution():
    import streamlit as st
    from taxonomy_discovery.production_resolver_inspector_ui import (
        render_production_resolver_inspector,
    )

    render_production_resolver_inspector()
    st.divider()
    from taxonomy_discovery.bulk_candidate_operations_ui import render_bulk_candidate_operations
    render_bulk_candidate_operations()
    st.divider()
    render_governed_research()
    from database.taxonomy_discovery_review_manager import (list_taxonomy_evolution_proposals,
        save_taxonomy_evolution_proposal, save_taxonomy_evolution_review)
    from taxonomy_discovery.taxonomy_evolution import gap_candidates, temporary_regression, DECISIONS
    from taxonomy_discovery.candidate_refinement import candidate_report
    with st.expander("Advanced / reproducibility · historical H.0 gap and draft review"):
        st.caption("Research inputs, drafts and approval are separate. Temporary regression is read-only. H.0 provides no production publication action.")
        gaps = st.file_uploader("Governed gap inputs JSON", type=["json"],key="tqd3_taxonomy_gaps")
        if gaps is not None:
            try:
                candidates=gap_candidates(json.loads(gaps.getvalue()))
                refined=candidate_report(candidates)
                st.json({k:refined[k] for k in ("source_observations","concept_count","candidate_route_counts","recurrence_counts")})
                routes=st.multiselect("Candidate route filters",sorted(refined["candidate_route_counts"]),key="tqd3_taxonomy_route_filters")
                visible=[c for c in candidates if not routes or c["candidate_route"] in routes]
                st.dataframe([{"candidate_id":c["candidate_id"],"cluster":c["normalized_cluster"],"route":c["candidate_route"],
                    "concept":c["concept_key"],"recurrence":c["recurrence_priority"],
                    "jobs":c["job_count"],"requirements":c["occurrence_count"]} for c in visible],hide_index=True,width="stretch")
                with st.expander("Concept groups, source examples and route conflicts"):
                    st.json([c for c in refined["concepts"] if not routes or any(r in routes for r in c["candidate_routes"])])
                with st.expander("Candidate overlap and complete provenance"):
                    st.json(candidates)
                st.download_button("Download governed candidates",data=json.dumps(refined,indent=2)+"\n",file_name="tqd3_taxonomy_candidates.json",mime="application/json")
            except Exception as exc:
                st.error(f"Gap inputs fail closed: {exc}")
        draft_file=st.file_uploader("Proposal-only taxonomy draft JSON",type=["json"],key="tqd3_taxonomy_draft_import")
        if draft_file is not None and st.button("Save selected proposal-only draft",key="tqd3_taxonomy_import"):
            try:
                save_taxonomy_evolution_proposal(json.loads(draft_file.getvalue()))
            except Exception as exc:
                st.error(f"Draft import rejected: {exc}")
        try:
            saved=list_taxonomy_evolution_proposals()
        except Exception as exc:
            st.error(f"Local draft review unavailable: {exc}")
            return
        if not saved:
            st.info("No local taxonomy drafts. Gap selection does not create or approve a proposal.")
            return
        ids=[row["proposal"]["proposal_id"] for row in saved]
        selected=st.multiselect("Temporary review tranche",ids,key="tqd3_taxonomy_tranche")
        proposals=[row["proposal"] for row in saved if row["proposal"]["proposal_id"] in selected]
        corpus_file=st.file_uploader("Frozen corpus for temporary taxonomy regression",type=["json"],key="tqd3_taxonomy_regression_corpus")
        if st.button("Evaluate selected temporary taxonomy",key="tqd3_taxonomy_regression",disabled=not proposals or corpus_file is None):
            try:
                st.session_state["tqd3_taxonomy_regression"]=temporary_regression(json.loads(corpus_file.getvalue()),proposals)
            except Exception as exc:
                st.error(f"Temporary regression unavailable: {exc}")
        report=st.session_state.get("tqd3_taxonomy_regression")
        if report:
            st.json(report)
        for row in saved:
            proposal=row["proposal"]
            pid=proposal["proposal_id"]
            if pid not in selected:
                continue
            with st.expander(proposal["proposed_label"]+" · "+pid):
                st.json(proposal)  # Definition, boundaries, evidence, overlap, frequency and full provenance.
                st.json(row["review"])
                decision=st.selectbox("Human decision",DECISIONS,key="tqd3_taxdecision_"+pid,
                    index=DECISIONS.index(row["review"].get("decision","undecided")))
                reviewer=st.text_input("Reviewer",key="tqd3_taxreviewer_"+pid)
                notes=st.text_area("Review rationale / conflicts",key="tqd3_taxnotes_"+pid)
                if st.button("Record human decision",key="tqd3_taxsave_"+pid):
                    try:
                        save_taxonomy_evolution_review(pid,proposal_fingerprint=proposal["proposal_fingerprint"],
                            decision=decision,reviewer=reviewer,notes=notes,regression=report)
                        st.success("Local decision recorded. Publication remains unavailable in H.0.")
                    except Exception as exc:
                        st.error(f"Review rejected: {exc}")
