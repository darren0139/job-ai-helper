"""Step 3 controls. Provider execution occurs only inside explicit button branches."""
from __future__ import annotations

import streamlit as st

from database.taxonomy_discovery_review_manager import (
    list_focused_verification_results, save_focused_verification_decision,
)
from database.technology_registry_proposal_manager import import_proposal_bundle
from taxonomy_discovery.focused_verification import (
    MAX_FOCUSED_BATCH, build_focused_draft, execute_focused_verification, interpret_focused_verification,
    focused_target_signature,
)
from taxonomy_discovery.focused_verification_preview import (
    build_focused_impact_preview, load_focused_preview_snapshots,
)


def render_focused_verification(target_report):
    targets = target_report["targets"]
    by_id = {t["target_id"]: t for t in targets}
    selected = st.multiselect("Select ready targets", list(by_id),
                              format_func=lambda tid: by_id[tid]["canonical_name"],
                              max_selections=MAX_FOCUSED_BATCH, key="tqd3_focused_selection")
    st.caption("Up to three targets per batch. Saved results reload without a Tavily request.")
    if st.button("Run focused verification", disabled=not selected, key="tqd3_run_focused_verification"):
        try:
            with st.spinner("Running focused verification..."):
                execute_focused_verification(targets, selected_target_ids=selected, explicit_execution=True)
        except Exception as exc:
            st.error(f"Focused verification failed: {exc}. Completed requests remain saved.")
    try:
        saved = list_focused_verification_results()
    except Exception as exc:
        st.error(f"Saved verification evidence could not be loaded: {exc}")
        return
    active = [r for r in saved if r["result"].get("target_id") in by_id and
              focused_target_signature(r["result"].get("target", {})) ==
              focused_target_signature(by_id[r["result"]["target_id"]])]
    latest = {}
    for row in active:
        latest.setdefault(row["result"]["target_id"], row)
    if not latest:
        return
    try:
        snapshots = load_focused_preview_snapshots()
        snapshot_error = ""
    except Exception as exc:
        snapshots = []
        snapshot_error = str(exc)
    for row in latest.values():
        result = row["result"]
        try:
            interpretation = interpret_focused_verification(result)
            draft = build_focused_draft(result, interpretation)
            preview = build_focused_impact_preview(draft, snapshots)
        except Exception as exc:
            st.error(f"Verification interpretation failed closed: {exc}")
            continue
        st.markdown(f"#### {interpretation['canonical_name']}")
        st.write("Verification result:", interpretation["outcome"].replace("_", " "))
        st.write("Authoritative evidence summary:")
        for source in interpretation["authoritative_sources"]:
            st.write(source["url"], " · ".join(source["evidence_sentences"]))
        if not interpretation["authoritative_sources"]:
            st.info("No candidate-specific first-party definition was verified.")
        st.write("Existing registry/taxonomy knowledge:", {
            "registry": interpretation["existing_registry_knowledge"]["status"],
            "capability": (interpretation["existing_taxonomy_knowledge"] or {}).get("capability_id"),
            "maintainer": interpretation["maintainer"],
            "recognized_first_party_organizations": interpretation["recognized_first_party_organizations"],
            "safe_aliases": interpretation["safe_aliases"],
        })
        st.write("Proposed draft action:", draft["action"].replace("_", " "))
        st.caption("Draft is not approval. Human approval and a separate production change are required.")
        st.markdown("**Job Match impact preview**")
        if preview["available"]:
            st.caption(preview["comparison"] + ". Requirement resolution only; no score changes are claimed.")
            st.write({key: preview[key] for key in ("requirements_evaluated", "unresolved_before",
                                                  "would_resolve_after", "unchanged_requirements")})
            st.dataframe([{
                "Requirement": item["requirement_text"], "Requirement ID": item["requirement_id"],
                "Before": item["before"].get("capability_id") or item["before"]["status"],
                "After": item["after"].get("capability_id") or item["after"]["status"],
                "Registry mapping": item["after"].get("technology_id"), "Changed": item["changed"],
            } for item in preview["rows"]], hide_index=True, width="stretch")
        else:
            st.info(preview["reason"])
        if row["decision"]:
            st.caption("Saved review action: " + row["decision"].replace("_", " "))
        c1, c2, c3 = st.columns(3)
        aid = row["artifact_id"]
        if c1.button("Send draft to review", key="focused_review_" + aid):
            try:
                # Existing proposal queue: import only, never save an approval.
                if draft["proposal_bundle"]["proposals"]:
                    import_proposal_bundle(draft["proposal_bundle"])
                save_focused_verification_decision(artifact_id=aid, decision="send_to_review", draft=draft)
                st.success("Draft sent to human review; no production change.")
            except Exception as exc:
                st.error(f"Could not send draft to review: {exc}")
        if c2.button("Research more", key="focused_more_" + aid):
            try:
                save_focused_verification_decision(artifact_id=aid, decision="research_more", draft=draft)
                execute_focused_verification(targets, selected_target_ids=[result["target_id"]],
                                             explicit_execution=True, research_more=True)
                st.rerun()
            except Exception as exc:
                st.error(f"Further focused research failed: {exc}")
        if c3.button("No change", key="focused_no_change_" + aid):
            try:
                save_focused_verification_decision(artifact_id=aid, decision="no_change", draft=draft)
                st.success("No change recorded; production knowledge remains unchanged.")
            except Exception as exc:
                st.error(f"Could not save review decision: {exc}")
        with st.expander("Advanced / Diagnostics · " + interpretation["canonical_name"]):
            st.json({"saved_evidence": row, "interpretation": interpretation, "draft": draft,
                     "impact_preview": preview, "snapshot_load_error": snapshot_error})
