"""Persisted H.1 ledger and explicit final publication, with no writes on render."""


def render_governed_review_ledger():
    import streamlit as st
    from taxonomy_discovery import governed_publication as publication
    st.subheader("Governed Review Ledger")
    rows = publication.review_ledger()
    status = st.selectbox("Ledger status",["all","pending_review","research_more","rejected","approved_pending_publication","published","superseded"],key="tqd3_ledger_status") or "all"
    visible = [r for r in rows if status == "all" or r["status"] == status or status == "rejected" and r["human_decision"] == "reject"]
    st.dataframe([{k:v for k,v in r.items() if k != "publication"} for r in visible],hide_index=True,width="stretch")
    for row in visible:
        with st.expander(row["concept"]+" · "+row["status"]+" · "+str(row["draft_id"] or "research evidence")):
            st.json(row)
            state = row["status"]
            banners = {"pending_review":"Research evidence saved — draft/regression/human review required",
                "rejected":"Rejected — historical draft retained","research_more":"More research requested — no approval",
                "superseded":"Rejected historical draft — superseded by "+str(row["superseded_by"]),
                "approved_pending_publication":"Approved — pending explicit publication"}
            if state == "published":
                st.success("Published to production knowledge version "+row["publication"]["version_after"])
                st.json([r for r in publication.list_linkage_receipts() if r["publication_id"] == row["publication"]["publication_id"]])
                if st.button("Return existing publication receipt",key=str(row["draft_id"])+"_publication_receipt"):
                    publication.publish_approved_change(row["research_result_id"],explicit_publish=True)
                    st.rerun()
                if st.button("Refresh affected current Job Match",key=str(row["draft_id"])+"_refresh_published_jobs"):
                    publication.refresh_published_jobs(row["publication"],explicit_refresh=True)
                    st.rerun()
                continue
            st.info(banners.get(state,state))
            if state != "approved_pending_publication":
                continue
            st.markdown("**Step 9 — Publish approved change**")
            preflight = publication.prepare_publication(row["research_result_id"])
            if preflight["ready"]:
                st.write("Concept / proposal kind",row["concept"],preflight["kind"])
                st.write("Production artifact",preflight["artifact"])
                st.write("Knowledge version",preflight["version_before"],"→",preflight["version_after"])
                st.write("Draft / regression fingerprints",preflight["draft_fingerprint"],preflight["regression_fingerprint"])
                st.write("Affected jobs",preflight["affected_jobs"])
                st.write("Human approval",preflight["reviewer"],preflight["approval_timestamp"])
                st.caption("Publication blockers = 0. Publication is separate from approval.")
            with st.expander("Advanced / exact publication preflight and guard metadata"):
                st.json(preflight)
            if not preflight["ready"]:
                st.error("Publication blocked: "+"; ".join(preflight["blockers"]))
            confirm = st.checkbox("I confirm publishing this exact approved change to production knowledge",value=False,key=str(row["draft_id"])+"_confirm_publication")
            if st.button("Publish approved change",key=str(row["draft_id"])+"_publish",disabled=not preflight["ready"] or confirm is not True):
                try:
                    if confirm is not True:
                        raise ValueError("Explicit confirmation required")
                    receipt = publication.publish_approved_change(row["research_result_id"],explicit_publish=True)
                    st.session_state["tqd3_h1_flash"]="Published to production knowledge version "+receipt["version_after"]
                    st.rerun()
                except Exception as exc:
                    st.error(f"Publication failed closed: {exc}")
