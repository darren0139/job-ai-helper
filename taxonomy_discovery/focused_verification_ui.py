"""Step 3 controls. Provider execution occurs only inside explicit button branches."""
from __future__ import annotations

import streamlit as st
from taxonomy_discovery.proposal_publication_ui import render_focused_review_handoff

from database.taxonomy_discovery_review_manager import (
    list_focused_verification_results, save_focused_verification_decision,
)
from database.technology_registry_proposal_manager import import_proposal_bundle, list_proposal_reviews
from taxonomy_discovery.focused_verification import (
    build_focused_draft, execute_focused_verification, interpret_focused_verification,
    focused_target_signature,
    verified_relationship_followup,
    execute_focused_bulk, focused_review_rows,
)
from taxonomy_discovery.focused_verification_preview import (
    build_focused_impact_preview, load_focused_preview_snapshots,
)
from taxonomy_discovery.focused_verification_targets import (
    TARGET_REGISTRY_RELATIONSHIP,
)
from tailoring.capability_taxonomy import get_default_taxonomy


def render_focused_verification(target_report):
    targets = target_report["targets"]
    by_id = {t["target_id"]: t for t in targets}
    selected = st.multiselect("Select ready targets", list(by_id),
                              format_func=lambda tid: by_id[tid]["canonical_name"],
                              key="tqd3_focused_selection")
    st.caption("Selections run in batches of three. Each completion is saved; reload does not request Tavily.")
    if st.button("Run focused verification", disabled=not selected, key="tqd3_run_focused_verification"):
        try:
            with st.spinner("Running focused verification..."):
                execute_focused_bulk(targets, selected_target_ids=selected, explicit_execution=True)
        except Exception as exc:
            st.error(f"Focused verification failed: {exc}. Completed requests remain saved.")
    try:
        saved = list_focused_verification_results()
    except Exception as exc:
        st.error(f"Saved verification evidence could not be loaded: {exc}")
        return
    root_target_ids = set(by_id)
    active = []
    for saved_row in saved:
        saved_result = saved_row.get("result", {}) or {}
        saved_target = saved_result.get("target", {}) or {}
        saved_target_id = str(
            saved_result.get("target_id") or ""
        )
        root_match = (
            saved_target_id in by_id
            and focused_target_signature(saved_target)
            == focused_target_signature(
                by_id[saved_target_id]
            )
        )
        followup_match = (
            str(
                saved_target.get(
                    "followup_of_target_id"
                )
                or ""
            )
            in root_target_ids
            and str(
                saved_target.get("route") or ""
            )
            == TARGET_REGISTRY_RELATIONSHIP
            and bool(
                saved_target.get(
                    "governance",
                    {},
                ).get(
                    "generated_from_verified_identity"
                )
            )
        )
        if root_match or followup_match:
            active.append(saved_row)
    latest = {}
    for row in active:
        latest.setdefault(row["result"]["target_id"], row)
    if not latest:
        return
    st.markdown("**Consolidated verification review**")
    try:
        st.dataframe(focused_review_rows(latest.values(), proposal_reviews=list_proposal_reviews()),
                     hide_index=True, width="stretch")
    except Exception as exc:
        st.error(f"Consolidated review unavailable: {exc}")
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
        if (
            interpretation["outcome"] == "verified_identity"
            and str(
                result.get("target", {}).get("route")
                or ""
            )
            != TARGET_REGISTRY_RELATIONSHIP
            and interpretation[
                "existing_registry_knowledge"
            ]["status"]
            in {"unresolved", "recognized_unmapped"}
        ):
            st.markdown("**Research an existing capability relationship**")
            st.caption(
                "Identity is verified, but no production mapping exists. "
                "Selecting a capability below creates a focused research target "
                "only; it does not approve or publish a mapping."
            )
            taxonomy = get_default_taxonomy()
            capability_index = taxonomy.by_id()
            capability_options = [
                ""
            ] + sorted(capability_index)
            selected_capability_id = st.selectbox(
                "Existing capability to research",
                capability_options,
                format_func=lambda cid: (
                    "Select a capability…"
                    if not cid
                    else (
                        f"{cid} — "
                        f"{capability_index[cid].get('label', cid)}"
                    )
                ),
                key=(
                    "focused_relationship_capability_"
                    + row["artifact_id"]
                ),
            )
            if st.button(
                "Research selected capability relationship",
                disabled=not selected_capability_id,
                key=(
                    "focused_relationship_research_"
                    + row["artifact_id"]
                ),
            ):
                try:
                    relationship_target = (
                        verified_relationship_followup(
                            result,
                            capability_id=selected_capability_id,
                        )
                    )
                    execute_focused_verification(
                        [relationship_target],
                        selected_target_ids=[
                            relationship_target[
                                "target_id"
                            ]
                        ],
                        explicit_execution=True,
                    )
                    st.success(
                        "Relationship research completed and saved. "
                        "No approval or production change was made."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(
                        "Relationship research failed closed: "
                        f"{exc}"
                    )

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
        sent_draft = row.get("review_draft") if row.get("decision") == "send_to_review" else None
        if c1.button("Send draft to review", key="focused_review_" + aid):
            try:
                # Existing proposal queue: import only, never save an approval.
                if draft["proposal_bundle"]["proposals"]:
                    import_proposal_bundle(draft["proposal_bundle"])
                save_focused_verification_decision(artifact_id=aid, decision="send_to_review", draft=draft)
                sent_draft = draft
            except Exception as exc:
                st.error(f"Could not send draft to review: {exc}")
        if c2.button("Research more", key="focused_more_" + aid):
            try:
                save_focused_verification_decision(artifact_id=aid, decision="research_more", draft=draft)
                execute_focused_verification([result["target"]], selected_target_ids=[result["target_id"]],
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
        if sent_draft:
            render_focused_review_handoff(sent_draft, interpretation["canonical_name"])
        with st.expander("Advanced / Diagnostics · " + interpretation["canonical_name"]):
            st.json({"saved_evidence": row, "interpretation": interpretation, "draft": draft,
                     "impact_preview": preview, "snapshot_load_error": snapshot_error})
