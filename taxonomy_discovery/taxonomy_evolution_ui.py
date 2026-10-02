"""Governed local gap inspection and review; no research or publication on render."""
import json


def render_taxonomy_evolution():
    import streamlit as st
    from database.taxonomy_discovery_review_manager import (list_taxonomy_evolution_proposals,
        save_taxonomy_evolution_proposal, save_taxonomy_evolution_review)
    from taxonomy_discovery.taxonomy_evolution import gap_candidates, temporary_regression, DECISIONS
    from taxonomy_discovery.candidate_refinement import candidate_report
    with st.expander("Governed Taxonomy Evolution / Gap Review"):
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
