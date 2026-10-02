"""Explicit publication controls in the existing Research Proposals workflow."""
from __future__ import annotations

from database.technology_registry_proposal_manager import (
    proposal_publication_state, publish_approved_proposal,
)

DISCOVERY_TABS_KEY = "taxonomy_discovery_tabs"
REQUESTED_PROPOSAL_KEY = "taxonomy_discovery_requested_proposal"
PROPOSAL_INSPECTOR_KEY = "technology_registry_proposal_inspector"
PINNED_PROPOSAL_KEY = "taxonomy_discovery_pinned_proposal"


FRIENDLY_DECISION_LABELS = {
    "unreviewed": "Not reviewed yet",
    "approve_mapping": "Approve mapping",
    "approve_identity": "Approve identity / aliases",
    "keep_unmapped": "Keep recognised but unmapped",
    "new_capability_needed": "Needs a new capability",
    "reject_proposal": "Reject proposal",
}

FRIENDLY_VERIFICATION_LABELS = {
    "verified_registry_relationship": "Verified relationship",
    "verified_identity": "Verified identity",
    "insufficient_evidence": "More evidence needed",
    "no_change": "No change recommended",
}

FRIENDLY_CLASSIFICATION_LABELS = {
    "safe_mapping_candidate": "Safe mapping candidate",
    "recognized_unmapped": "Recognised technology / identity",
    "new_capability_candidate": "New capability candidate",
}


def friendly_decision_label(value):
    raw = str(value or "unreviewed")
    return FRIENDLY_DECISION_LABELS.get(raw, raw.replace("_", " ").strip().title())


def friendly_verification_label(value):
    raw = str(value or "")
    return FRIENDLY_VERIFICATION_LABELS.get(raw, raw.replace("_", " ").strip().title() or "Not verified")


def friendly_classification_label(value):
    raw = str(value or "")
    return FRIENDLY_CLASSIFICATION_LABELS.get(raw, raw.replace("_", " ").strip().title() or "Unknown")


def _has_reviewable_source_evidence(proposal, context):
    return bool((context or {}).get("authoritative_evidence") or proposal.get("sources"))


def decision_guidance(proposal, review=None, *, context=None):
    """Return plain-language approval guidance without changing proposal semantics."""
    review = review or {}
    classification = str(proposal.get("proposal_classification") or "")
    target = str(proposal.get("proposed_capability_id") or "")
    aliases = [str(value) for value in proposal.get("aliases", []) or [] if str(value).strip()]
    verification = str((context or {}).get("outcome") or "")
    verified = verification.startswith("verified_")
    source_ready = _has_reviewable_source_evidence(proposal, context)

    if classification == "safe_mapping_candidate":
        system_checks = [
            (verified, "Focused verification supports this technology-to-capability relationship."),
            (source_ready, "Reviewable source evidence is attached to the proposal."),
            (bool(target), f"The proposal names a capability target: {target or 'none'}."),
        ]
        human_questions = [
            f"Does {target or 'the proposed capability'} accurately describe the reusable capability represented by {proposal.get('label') or 'this technology'}?",
            "Are the proposed aliases genuinely names for the same technology, without broadening the meaning?",
            "Is this relationship direct enough that approving it will not overgeneralise unrelated skills or tools?",
        ]
        approval_rule = (
            "Choose **Approve mapping** when the system evidence checks are satisfied and you can answer "
            "yes to the human-judgment questions. If the technology is valid but this capability is not an "
            "accurate fit, keep it recognised but unmapped. If the missing concept is genuinely reusable and "
            "not represented by an existing capability, route it to the new-capability workflow."
        )
    elif classification == "recognized_unmapped":
        system_checks = [
            (verified, "Focused verification supports the technology identity."),
            (source_ready, "Reviewable source evidence is attached to the proposal."),
            (bool(aliases), "The proposal contains one or more aliases to review."),
        ]
        human_questions = [
            "Do the canonical name and aliases all refer to the same technology?",
            "Is it appropriate to recognise this technology without claiming a capability relationship yet?",
        ]
        approval_rule = (
            "Choose **Approve identity / aliases** when the identity is well supported and the aliases are safe, "
            "but no capability relationship should be activated yet."
        )
    elif classification == "new_capability_candidate":
        system_checks = [
            (verified, "Focused verification supports the underlying concept or technology identity."),
            (source_ready, "Reviewable source evidence is attached to the proposal."),
        ]
        human_questions = [
            "Is the missing concept broad and reusable enough to belong in the capability taxonomy?",
            "Is it genuinely absent rather than a synonym or narrower example of an existing capability?",
        ]
        approval_rule = (
            "Use **Needs a new capability** only when the concept is genuinely missing and reusable. "
            "Capability creation remains a separate governed workflow and cannot be published from this screen."
        )
    else:
        system_checks = [
            (verified, "Focused verification evidence is available."),
            (source_ready, "Reviewable source evidence is attached to the proposal."),
        ]
        human_questions = ["Does the proposed decision accurately reflect the evidence and intended taxonomy behaviour?"]
        approval_rule = "Save a decision only after the evidence and intended effect are clear."

    return {
        "classification": classification,
        "system_checks": system_checks,
        "human_questions": human_questions,
        "approval_rule": approval_rule,
        "aliases": aliases,
        "saved_decision": str(review.get("decision") or "unreviewed"),
    }


def render_human_decision_guidance(proposal, review=None):
    """Explain what 'good enough to approve' means before the decision form."""
    import streamlit as st
    try:
        context = focused_proposal_context(proposal)
    except Exception:
        context = proposal.get("focused_verification") if isinstance(proposal.get("focused_verification"), dict) else None
    guide = decision_guidance(proposal, review, context=context)

    st.markdown("##### Decision guidance · What is good enough to approve?")
    st.caption(
        "The system can verify evidence and proposal structure, but the final semantic fit remains a human judgment. "
        "You should not need to interpret research-confidence scores or internal state names to make this decision."
    )
    st.markdown("**System evidence already available**")
    for passed, label in guide["system_checks"]:
        st.markdown(f"- {'✅' if passed else '○'} {label}")
    if guide["aliases"]:
        st.caption("Aliases to review: " + ", ".join(guide["aliases"]))

    st.markdown("**Your judgment**")
    for question in guide["human_questions"]:
        st.markdown(f"- ○ {question}")
    st.info(guide["approval_rule"])

    saved = guide["saved_decision"]
    if saved != "unreviewed":
        st.caption(
            "Saved human decision: " + friendly_decision_label(saved) +
            ". Change it only if your judgment or the underlying proposal changes."
        )


def request_proposal_navigation(session_state, proposal_id):
    session_state[DISCOVERY_TABS_KEY] = "Research Proposals"
    session_state[REQUESTED_PROPOSAL_KEY] = proposal_id


def prepare_proposal_inspector(session_state, proposals, filtered_proposals):
    """Select a requested exact proposal even when historical filters exclude it."""
    all_ids = [p["proposal_id"] for p in proposals]
    ids = [p["proposal_id"] for p in filtered_proposals] or all_ids
    requested = session_state.pop(REQUESTED_PROPOSAL_KEY, None)
    if requested in all_ids:
        session_state[PINNED_PROPOSAL_KEY] = requested
        session_state[PROPOSAL_INSPECTOR_KEY] = requested
    pinned = session_state.get(PINNED_PROPOSAL_KEY)
    if pinned in all_ids and session_state.get(PROPOSAL_INSPECTOR_KEY) == pinned:
        ids = list(dict.fromkeys([pinned] + ids))
    else:
        session_state.pop(PINNED_PROPOSAL_KEY, None)
    if session_state.get(PROPOSAL_INSPECTOR_KEY) not in ids:
        session_state[PROPOSAL_INSPECTOR_KEY] = ids[0]
    return ids


def focused_proposal_context(proposal, *, review_db_path=None):
    """Restore the handoff context of existing v1.6.1 drafts without research."""
    if proposal.get("focused_verification"):
        return proposal["focused_verification"]
    from database.taxonomy_discovery_review_manager import list_focused_verification_results
    from taxonomy_discovery.focused_verification import interpret_focused_verification
    for row in list_focused_verification_results(db_path=review_db_path):
        draft = row.get("review_draft") or {}
        for original in draft.get("proposal_bundle", {}).get("proposals", []):
            if original.get("proposal_id") != proposal["proposal_id"]:
                continue
            if any(original.get(key) != proposal.get(key) for key in (
                "technology_id", "aliases", "proposed_capability_id", "relationship_type", "sources"
            )):
                continue
            interpretation = interpret_focused_verification(row["result"])
            return {"outcome": "verified_registry_relationship" if draft["action"] == "add_technology_capability_relationship"
                    else "verified_identity", "authoritative_evidence": interpretation["authoritative_sources"],
                    "action": draft["action"], "provider_request_id": row["result"]["provider_request_id"]}
    return None


def render_focused_review_handoff(draft, label):
    import streamlit as st
    proposals = draft.get("proposal_bundle", {}).get("proposals", [])
    if not proposals:
        st.info("This draft records a research/no-change decision; no publishable Research Proposal was created.")
        return
    proposal = proposals[0]
    st.success(f"{label} draft sent to Research Proposals.")
    st.write("Proposed mapping:", f"{label} → {proposal.get('proposed_capability_id') or 'technology identity / safe aliases'}")
    st.caption("Next: Review and approve this proposal. Approval does not publish it.")
    st.button(f"Open {label} proposal", key="open_focused_proposal_" + proposal["proposal_id"],
              on_click=request_proposal_navigation, args=(st.session_state, proposal["proposal_id"]))


def _progress_text(*, verified, human_decided, approved, published):
    def mark(done):
        return "✅" if done else "○"
    return (
        f"{mark(verified)} Verified  →  {mark(human_decided)} Human decision  →  "
        f"{mark(approved)} Approved  →  {mark(published)} Published"
    )


def render_proposal_publication(proposal, review, *, publications=None, automation_suggestion=None):
    import streamlit as st
    try:
        context = focused_proposal_context(proposal)
    except Exception as exc:
        context = None
        st.warning(f"Saved focused evidence context could not be loaded: {exc}")

    try:
        status = proposal_publication_state(proposal, review, publications=publications)
    except Exception as exc:
        st.error(f"Publication status unavailable; publication stopped: {exc}")
        return

    decision = str(review.get("decision") or "unreviewed")
    verification_outcome = str((context or {}).get("outcome") or "")
    verified = verification_outcome.startswith("verified_")
    human_decided = decision != "unreviewed"
    approved = status.get("state") in {"human_approved", "production_active"} or bool(status.get("production_active"))
    published = bool(status.get("production_active"))
    mapping_target = proposal.get("proposed_capability_id") or "identity / safe aliases"

    st.markdown("#### Review and publication")
    st.markdown(f"**{proposal['label']} → {mapping_target}**")
    st.caption(_progress_text(verified=verified, human_decided=human_decided, approved=approved, published=published))

    if published:
        st.success("Production active. This approved change is already published and used by the deterministic resolver.")
    elif status.get("state") == "human_approved":
        st.info("Next action: Publish the approved change when you are ready. Production has not changed yet.")
    elif decision == "unreviewed":
        st.info("Next action: Review the evidence and save a human decision. Nothing is published automatically.")
    else:
        st.info("Next action: No publication action is available for this decision. Production remains unchanged.")

    if context:
        st.markdown("**Focused verification**")
        st.write("Verification:", friendly_verification_label(context.get("outcome")))
        if context.get("authoritative_evidence"):
            st.caption("Authoritative evidence")
            for source in context.get("authoritative_evidence", []):
                st.write(source.get("url"), " · ".join(source.get("evidence_sentences", [])))

    st.write("Human decision:", friendly_decision_label(decision))
    suggestion = str(automation_suggestion or "unreviewed")
    st.write("Automation suggestion (optional):", friendly_decision_label(suggestion))
    st.caption(
        "Python/Ollama suggestions are advisory only. A missing or low-confidence automation suggestion does not invalidate verified evidence; manual human review remains authoritative."
    )

    st.markdown("**Publication**")
    st.write("State:", status["display"])
    if published:
        st.success("Published · Production resolver active")
        st.write("Current registry version:", status["registry_version"])
        st.write("Taxonomy version:", status["taxonomy_version"])
        st.caption("Existing Job Match and Session Analysis currentness checks detect the registry version. Recognition grants no candidate evidence.")
    elif status.get("state") == "human_approved":
        st.markdown("##### Ready-to-publish checklist · What is good enough to publish?")
        st.markdown("- ✅ The exact proposal has an eligible saved human approval.")
        st.markdown("- ✅ Production has not changed because of this approval yet.")
        st.markdown("- ✅ Publish will revalidate the proposal fingerprint, registry/taxonomy versions, source evidence, aliases, and mapping conflicts before writing.")
        st.markdown("- ✅ Publication fails closed if the proposal, approval, or production knowledge changes during the operation.")
        st.markdown("- ✅ Publishing registry knowledge does not create candidate/resume evidence and does not create a new capability.")
        st.info(
            "Publish when you are satisfied that the approved semantic decision is correct **and** you are ready for it to become active production knowledge. "
            "The system will run the deterministic safety checks again on click; if any check fails, nothing is published."
        )
        st.caption("Publishing writes approved registry knowledge to production. It does not create candidate/resume evidence.")
        if st.button("Publish approved change", key="publish_registry_proposal_" + proposal["proposal_id"]):
            try:
                publish_approved_proposal(proposal_id=proposal["proposal_id"], explicit_publish=True,
                    expected_source_fingerprint=proposal["source_fingerprint"],
                    expected_registry_version=status["registry_version"],
                    proposal_bundle_version=proposal["proposal_bundle_version"])
                st.success("Published · Production resolver active")
                st.rerun()
            except Exception as exc:
                st.error(f"Publication failed: {exc}")

    if proposal["proposal_classification"] == "new_capability_candidate":
        st.info("Route to the existing capability proposal/design workflow. This publication action cannot create a capability.")

    with st.expander("Advanced / Debug details", expanded=False):
        st.json({
            "verification_outcome": verification_outcome or None,
            "human_decision": decision,
            "automation_suggestion": suggestion,
            "proposal_classification": proposal.get("proposal_classification"),
            "publication_state": status.get("state"),
            "publication_display": status.get("display"),
            "production_active": published,
        })
