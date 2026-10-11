"""Read-only presentation of existing audit and reviewed Addressability receipts.

This adapter does not classify, replay, research, approve or persist knowledge.
"""
from collections import Counter
from copy import deepcopy
import json
import math

from taxonomy_discovery import maintenance_service as maintenance
from taxonomy_discovery import bulk_capability_campaign as campaign
from taxonomy_discovery import taxonomy_addressability as address


DESTINATIONS = {
    campaign.GAP: "Governed capability discovery / research",
    campaign.IDENTITY: "Technology identity workflow",
    campaign.RELATIONSHIP: "Contextual relationship review",
    campaign.PARSER: "Structural backlog",
    campaign.MIXED: "Structural backlog",
    campaign.NOT: "No capability-discovery action",
    campaign.SCOPE: "Deferred / needs review",
    campaign.EXISTING: "Existing capability resolution review",
}


def confirmed_coverage(snapshot, plan):
    """Consume sealed native proofs; raw unresolved is never the denominator."""
    maintenance._intact(snapshot, "audit_fingerprint")
    reviewed = plan["taxonomy_addressability"]
    maintenance._intact(reviewed, "addressability_fingerprint")
    if reviewed["audit_fingerprint"] != snapshot["audit_fingerprint"]:
        raise ValueError("Reviewed accounting belongs to another audit")
    summary = snapshot["audit"]["summary"]
    requirements = {(r["job_id"], r["requirement_id"]): r
                    for r in snapshot["audit"]["requirements"]}
    raw = campaign._records(snapshot["audit"]["corpus"])
    represented = summary["capability_resolved_requirements"]
    if represented != sum(r["current_resolution"].get("knowledge_status") == "CAPABILITY_RESOLVED"
                          for r in requirements.values()):
        raise ValueError("Capability count does not match the native audit rows")
    rows = reviewed["rows"]
    keys = {(r["job_id"], r["requirement_id"]) for r in rows}
    if len(keys) != len(rows) or len(keys) != summary["taxonomy_unresolved_requirements"]:
        raise ValueError("Reviewed accounting must cover every unique unresolved requirement")
    for row in rows:
        key = row["job_id"], row["requirement_id"]
        source = requirements[key]
        if (source["current_resolution"]["status"] == "resolved"
                or row["canonical_text"] != raw[key]["text"]
                or row["weight"] != maintenance.gaps._weight(source)):
            raise ValueError("Reviewed accounting source changed")
        if row["semantic_addressability"] == address.GAP and not all(
                row.get("proof", {}).get("gap_contract", {}).get(field)
                for field in campaign.GAP_PROOF_FIELDS):
            raise ValueError("Capability gap lacks its native proof contract")
    operational = campaign.inventory(snapshot, plan)
    proven = [deepcopy(r) for r in rows if r["semantic_addressability"] == address.GAP]
    denominator = represented + len(proven)
    weighted = {}
    for scope, field in (("overall", "capability_overall_weighted_coverage"),
                         ("required_core", "capability_required_core_weighted_coverage")):
        native = summary.get(field)
        if not native or "resolved_weight" not in native:
            weighted[scope] = None
            continue
        numerator = native["resolved_weight"]
        gap_weight = sum(r["weight"] for r in proven
                         if scope == "overall" or r["importance"] in campaign.CORE)
        total = numerator + gap_weight
        if not math.isfinite(total) or numerator < 0 or gap_weight < 0:
            raise ValueError("Invalid authoritative weight")
        weighted[scope] = {"numerator": numerator, "denominator": total,
                           "percentage": 100 * numerator / total if total else None}
    routes = [{"job_id": r["job_id"], "requirement_id": r["requirement_id"],
               "requirement": r["canonical_text"], "lane": r["lane"],
               "destination": DESTINATIONS[r["lane"]],
               "capability_discovery_eligible": r["semantic_addressability"] == address.GAP
                   and r["lane"] == campaign.GAP} for r in operational]
    return {"numerator": represented, "denominator": denominator,
            "percentage": 100 * represented / denominator if denominator else None,
            "weighted": weighted, "proven_gaps": proven, "routes": routes,
            "breakdown": dict(Counter(r["destination"] for r in routes)),
            "raw_summary": deepcopy(summary), "job_ids": snapshot["manifest"]["job_ids"]}


def session_coverage(state):
    receipt = state.get("tm_coverage_receipt")
    snapshot = receipt["snapshot"] if receipt else state.get("tm_snapshot")
    plan = receipt["plan"] if receipt else state.get("tm_gap_plan")
    if not snapshot or not plan:
        return None, "Load a reviewed corpus audit and its Addressability accounting."
    try:
        status = maintenance.currentness(snapshot)
        if not status["current"]:
            return None, "Reviewed audit is stale: " + "; ".join(status["blockers"])
        return confirmed_coverage(snapshot, plan), None
    except (ValueError, KeyError, TypeError) as exc:
        return None, "Reviewed accounting unavailable: " + str(exc)


def render_confirmed_coverage(st, *, key, allow_import=False):
    """Render corpus health, separate from any selected job's match score."""
    if allow_import:
        with st.expander("Advanced / load existing reviewed taxonomy accounting"):
            uploaded = st.file_uploader("Reviewed audit + Addressability receipt JSON",
                                        type=["json"], key=key + "_receipt")
            if st.button("Load reviewed accounting", key=key + "_load", disabled=uploaded is None):
                try:
                    receipt = json.loads(uploaded.getvalue())
                    # Validate first; a failed load must not replace the current receipt.
                    status = maintenance.currentness(receipt["snapshot"])
                    if not status["current"]:
                        raise ValueError("; ".join(status["blockers"]))
                    confirmed_coverage(receipt["snapshot"], receipt["plan"])
                    st.session_state["tm_coverage_receipt"] = receipt
                except (ValueError, KeyError, TypeError) as exc:
                    st.error("Reviewed accounting not loaded: " + str(exc))
    view, blocker = session_coverage(st.session_state)
    columns = st.columns(2)
    percentage = view["percentage"] if view else None
    columns[0].metric("Global confirmed taxonomy coverage", f"{percentage:.0f}%" if percentage is not None else "Unavailable",
                      help="Among requirements confirmed to be capability-taxonomy-addressable.")
    columns[1].metric("Proven capability gaps", len(view["proven_gaps"]) if view else "Unavailable")
    if not view:
        st.caption(blocker)
        return None
    st.caption(f"Reviewed corpus: {len(view['job_ids'])} jobs · {view['numerator']} of "
               f"{view['denominator']} confirmed capability requirements represented. "
               "Among requirements confirmed to be capability-taxonomy-addressable. "
               "Deferred requirements have not been established as taxonomy gaps.")
    if view["proven_gaps"]:
        st.dataframe([{"Job": r["job_id"], "Requirement ID": r["requirement_id"],
                       "Proven capability gap": r["canonical_text"]} for r in view["proven_gaps"]],
                     hide_index=True, width="stretch")
    with st.expander("Advanced diagnostics — raw knowledge coverage", key=key + "_diagnostics"):
        raw = view["raw_summary"]
        for label, field in (("Required/core model-resolved requirement share", "required_core_weighted_coverage"),
                             ("Overall model-resolved requirement share", "overall_weighted_coverage")):
            st.metric(label, f"{raw[field]['percent']:.2f}%")
        for label, field in (("Capability resolved", "capability_resolved_requirements"),
                             ("Technology identity resolved", "technology_identity_resolved_requirements"),
                             ("Total knowledge resolved", "knowledge_resolved_requirements"),
                             ("Raw unresolved", "taxonomy_unresolved_requirements")):
            st.metric(label, raw[field])
        st.write("Unresolved accounting (one operational destination per requirement)", view["breakdown"])
        st.write("Confirmed weighted taxonomy coverage", view["weighted"])
        st.caption("This measures how much extracted technical requirement weight is currently "
                   "represented by the production knowledge model. The remainder includes deferred, "
                   "structural, relationship, registry and non-taxonomy-addressable cases and is not assumed to be fixable.")
    return view


def jd_coverage(snapshot, plan, *, raw_jd_text, stable_analysis, job_id=None):
    """Native positive resolutions suffice; reviewed proofs only establish gaps.

    Entry surfaces supply the JD bound to their validated saved analysis. Review
    absence/staleness is independent of that analysis's own currentness.
    """
    from job_discovery.matching import current_match_versions
    from analysis_stability.stable_evidence_scoring import JD_STRUCTURE_INFERENCE_VERSION, TECHNOLOGY_REGISTRY_RESOLUTION_VERSION
    from tailoring.job_match_ab_analysis import current_ab_identity
    from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint

    if not raw_jd_text or not isinstance(stable_analysis, dict):
        raise ValueError("Saved analysis/JD unavailable")
    rows = stable_analysis.get("canonical_requirements")
    if not isinstance(rows, list) or not rows or any(not isinstance(r, dict)
            or not isinstance(r.get("requirement_id"), str) or not r["requirement_id"]
            or not isinstance(r.get("text"), str) or not r["text"]
            or not isinstance(r.get("knowledge_resolution") or {}, dict) for r in rows):
        raise ValueError("Canonical requirements unavailable or corrupt")
    if len({r["requirement_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate canonical requirement IDs")
    versions = current_match_versions()
    for field, key in (("scoring_version", "scoring_version"),
                       ("capability_taxonomy_version", "taxonomy_version"),
                       ("technology_registry_version", "technology_registry_version")):
        if stable_analysis.get(field) != versions[key]:
            raise ValueError("Stale/incompatible analysis: " + field)
    identity = current_ab_identity(raw_jd_text)
    scope = canonical_requirement_scope_fingerprint(rows)
    for field, expected in (("jd_fingerprint", identity["jd_fingerprint"]),
                            ("canonical_requirement_fingerprint", scope)):
        if stable_analysis.get(field) and stable_analysis[field] != expected:
            raise ValueError("Saved analysis " + field + " mismatch")
    for field, expected in (("jd_structure_inference_version", JD_STRUCTURE_INFERENCE_VERSION),
                            ("technology_registry_resolution_version", TECHNOLOGY_REGISTRY_RESOLUTION_VERSION)):
        if stable_analysis.get(field) != expected:
            raise ValueError("Stale/incompatible analysis: " + field)
    statuses = [r.get("knowledge_status") or (r.get("knowledge_resolution") or {}).get("knowledge_status") for r in rows]
    if any(status == "CAPABILITY_RESOLVED" and not r.get("capability_id") for r, status in zip(rows, statuses)):
        raise ValueError("Capability resolution lacks its native capability identity")
    capability = sum(status == "CAPABILITY_RESOLVED" for status in statuses)
    identities = sum(status == "TECHNOLOGY_IDENTITY_RESOLVED" for status in statuses)
    native = {"job_id": job_id, "jd_fingerprint": identity["jd_fingerprint"],
        "requirement_scope_fingerprint": scope, "capability_resolved": capability,
        "technology_identity_resolved": identities, "proven_gap_count": 0,
        "denominator": capability, "percentage": 100.0 if capability else None,
        "additional_analysis_items": len(rows) - capability,
        "breakdown": {}, "proven_gaps": [], "routes": [],
        "reviewed_accounting": False}
    if not snapshot or not plan:
        return native
    # Complete corpus review remains the global contract. A compatible partial
    # review can still contribute positive gap proofs for this JD alone.
    try:
        maintenance._intact(snapshot, "audit_fingerprint")
        reviewed = plan["taxonomy_addressability"]
        maintenance._intact(reviewed, "addressability_fingerprint")
        if reviewed["audit_fingerprint"] != snapshot["audit_fingerprint"]:
            raise ValueError("Reviewed accounting belongs to another audit")
        if not maintenance.currentness(snapshot)["current"]:
            raise ValueError("Reviewed accounting is stale")
    except (ValueError, KeyError, TypeError) as exc:
        native["review_blocker"] = str(exc)
        return native
    try:
        view = confirmed_coverage(snapshot, plan)
    except (ValueError, KeyError, TypeError, AttributeError):
        # Validate only positive proofs; unclassified rows cannot invent gaps.
        if not isinstance(reviewed.get("rows"), list) or any(not isinstance(r, dict) for r in reviewed["rows"]):
            native["review_blocker"] = "Corrupt reviewed rows"
            return native
        sources = {(r["job_id"], r["requirement_id"]): r for r in snapshot["audit"]["requirements"]}
        raw = campaign._records(snapshot["audit"]["corpus"])
        gaps, seen = [], set()
        for row in reviewed["rows"]:
            if row.get("semantic_addressability") != address.GAP:
                continue
            key = row.get("job_id"), row.get("requirement_id")
            source = sources.get(key)
            valid = (key not in seen and source and key in raw
                and source["current_resolution"]["status"] != "resolved"
                and row.get("canonical_text") == raw[key]["text"]
                and row.get("weight") == maintenance.gaps._weight(source)
                and isinstance(row.get("proof"), dict)
                and isinstance(row["proof"].get("gap_contract"), dict)
                and all(row["proof"]["gap_contract"].get(f)
                        for f in campaign.GAP_PROOF_FIELDS))
            if not valid:
                native["review_blocker"] = "Invalid positive gap proof"
                return native
            seen.add(key); gaps.append(deepcopy(row))
        view = {"proven_gaps": gaps, "routes": []}
    jobs = snapshot["audit"]["corpus"]["jobs"]
    if not any((job_id is not None and j["job_id"] == job_id)
            or (job_id is None and current_ab_identity(j.get("frozen_inputs", {}).get("raw_jd_text", ""))["jd_fingerprint"] == identity["jd_fingerprint"])
            for j in jobs):
        return native
    result = _jd_coverage_with_view(snapshot, view, raw_jd_text=raw_jd_text,
                                   stable_analysis=stable_analysis, job_id=job_id)
    result["capability_resolved"] = capability
    result["denominator"] = capability + result["proven_gap_count"]
    result["percentage"] = 100 * capability / result["denominator"] if result["denominator"] else None
    if not view["routes"]:
        result["additional_analysis_items"] = len(rows) - result["denominator"]
    result["reviewed_accounting"] = True
    return result


def _jd_coverage_with_view(snapshot, view, *, raw_jd_text, stable_analysis, job_id=None):
    """Join one JD after the shared native accounting has been validated."""
    from tailoring.job_match_ab_analysis import current_ab_identity
    from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint

    if not raw_jd_text or not stable_analysis.get("canonical_requirements"):
        raise ValueError("Analyzed JD requirements unavailable")
    identity = current_ab_identity(raw_jd_text)
    scope = canonical_requirement_scope_fingerprint(stable_analysis["canonical_requirements"])
    jobs = []
    for job in snapshot["audit"]["corpus"]["jobs"]:
        if job_id is not None and job["job_id"] != job_id:
            continue
        native = job["baseline_stable_analysis"]
        if (current_ab_identity(job.get("frozen_inputs", {}).get("raw_jd_text", ""))["jd_fingerprint"]
                != identity["jd_fingerprint"]):
            continue
        if scope != canonical_requirement_scope_fingerprint(native["canonical_requirements"]):
            continue
        fields = ("scoring_version", "capability_taxonomy_version", "technology_registry_version",
                  "technology_registry_resolution_version", "jd_structure_inference_version")
        if any(not native.get(k) or native.get(k) != stable_analysis.get(k) for k in fields):
            continue
        jobs.append(job)
    if len(jobs) != 1:
        raise ValueError("No unique reviewed accounting for this JD and requirement generation")
    jid = jobs[0]["job_id"]
    rows = [r for r in snapshot["audit"]["requirements"] if r["job_id"] == jid]
    routes = [r for r in view["routes"] if r["job_id"] == jid]
    gaps = [r for r in view["proven_gaps"] if r["job_id"] == jid]
    capability = sum(r["current_resolution"]["knowledge_status"] == "CAPABILITY_RESOLVED" for r in rows)
    identities = sum(r["current_resolution"]["knowledge_status"] == "TECHNOLOGY_IDENTITY_RESOLVED" for r in rows)
    denominator = capability + len(gaps)
    return {"job_id": jid, "jd_fingerprint": identity["jd_fingerprint"],
            "requirement_scope_fingerprint": scope, "capability_resolved": capability,
            "technology_identity_resolved": identities, "proven_gap_count": len(gaps),
            "denominator": denominator, "percentage": 100 * capability / denominator if denominator else None,
            "additional_analysis_items": len(routes) - len(gaps),
            "breakdown": dict(Counter(r["destination"] for r in routes)),
            "proven_gaps": gaps, "routes": routes}


def render_jd_taxonomy_status(st, *, raw_jd_text, stable_analysis=None, job_id=None,
                              analyzed=True, current=True):
    st.markdown("#### This JD's taxonomy status")
    if not analyzed:
        st.caption("Analyze job to view")
        return None
    receipt = st.session_state.get("tm_coverage_receipt") or {
        "snapshot": st.session_state.get("tm_snapshot"), "plan": st.session_state.get("tm_gap_plan")}
    try:
        if not current:
            raise ValueError("Stale/incompatible analysis")
        view = jd_coverage(receipt.get("snapshot"), receipt.get("plan"), raw_jd_text=raw_jd_text,
                           stable_analysis=stable_analysis or {}, job_id=job_id)
    except (ValueError, KeyError, TypeError) as exc:
        st.caption("Unavailable / review pending — " + str(exc))
        return None
    columns = st.columns(2)
    percentage = view["percentage"]
    columns[0].metric("This JD's confirmed taxonomy coverage",
                      f"{percentage:.2f}%" if percentage is not None else "Not enough classified capability requirements yet")
    columns[1].metric("This JD's proven capability gaps", f"{view['proven_gap_count']} currently established")
    st.caption(f"{view['capability_resolved']} / {view['denominator']} confirmed capability requirements represented. "
               f"Additional analysis items: {view['additional_analysis_items']}. "
               "Additional analysis items are excluded from confirmed taxonomy coverage until their taxonomy status is established. "
               "They are not assumed to be gaps. Confirmed coverage does not mean every JD requirement is understood.")
    with st.expander("Advanced / this JD's reviewed accounting"):
        st.write("Technology identity resolved", view["technology_identity_resolved"])
        st.write(view["breakdown"])
        st.dataframe(view["routes"], hide_index=True, width="stretch")
    return view


def analyzed_job_records(jobs, states, full_receipts):
    """Join lightweight currentness to explicitly loaded full receipts."""
    records = []
    for job in jobs:
        jid = int(job["id"])
        state, saved = states.get(jid, {}), full_receipts.get(jid, {})
        current_snapshot, saved_snapshot = state.get("snapshot") or {}, saved.get("snapshot") or {}
        compatible = (state.get("status") == saved.get("status") == "current"
            and bool(state.get("identity")) and state["identity"] == saved.get("identity")
            and current_snapshot.get("id") is not None
            and current_snapshot.get("id") == saved_snapshot.get("id"))
        records.append({"job_id": jid, "raw_jd_text": job.get("description") or "",
            "status": state.get("status", "none"),
            "stable_analysis": saved_snapshot.get("stable_analysis") if compatible else None})
    return records


def analyzed_jobs_coverage(snapshot, plan, analyses):
    """Sum confirmed occurrences, never percentages or lightweight summaries."""
    eligible, pending, unanalyzed = [], [], []
    seen = set()
    concepts = set()
    for item in analyses:
        jid = item["job_id"]
        if jid in seen:
            raise ValueError("Duplicate analyzed job identity")
        seen.add(jid)
        if item.get("status") == "none":
            unanalyzed.append(jid)
            continue
        try:
            if item.get("status") != "current" or not item.get("stable_analysis"):
                raise ValueError("Current full analysis receipt unavailable")
            view = jd_coverage(snapshot, plan, job_id=jid,
                raw_jd_text=item.get("raw_jd_text", ""), stable_analysis=item["stable_analysis"])
            identities = []
            for gap in view["proven_gaps"]:
                profile = gap.get("proof", {}).get("profile", {})
                identity = (profile.get("new_capability") or {}).get("capability_id") or profile.get("canonical_concept")
                if not identity:
                    raise ValueError("Governed gap concept identity unavailable")
                identities.append(str(identity).strip().casefold())
            concepts.update(identities)
            eligible.append(view)
        except (ValueError, KeyError, TypeError) as exc:
            pending.append({"job_id": jid, "reason": str(exc)})
    numerator = sum(v["capability_resolved"] for v in eligible)
    gaps = sum(v["proven_gap_count"] for v in eligible)
    denominator = numerator + gaps
    return {"eligible_analyzed_jobs": len(eligible), "pending_analyzed_jobs": len(pending),
        "unanalyzed_jobs": len(unanalyzed), "numerator": numerator, "denominator": denominator,
        "percentage": 100 * numerator / denominator if denominator else None,
        "proven_gap_occurrences": gaps, "unique_missing_capabilities": len(concepts),
        "additional_analysis_items": sum(v.get("additional_analysis_items", 0) for v in eligible),
        "jobs_affected": sum(v["proven_gap_count"] > 0 for v in eligible),
        "gap_concept_ids": sorted(concepts), "pending": pending, "jobs": eligible}


def render_analyzed_jobs_summary(st, analyses):
    st.subheader("Analyzed Jobs Taxonomy Summary")
    receipt = st.session_state.get("tm_coverage_receipt") or {
        "snapshot": st.session_state.get("tm_snapshot"), "plan": st.session_state.get("tm_gap_plan")}
    view = analyzed_jobs_coverage(receipt.get("snapshot"), receipt.get("plan"), analyses)
    columns = st.columns(3)
    columns[0].metric("Analyzed jobs confirmed taxonomy coverage",
        f"{view['percentage']:.2f}%" if view["percentage"] is not None else "Not enough classified capability requirements yet")
    columns[1].metric("Proven gap requirement occurrences", f"{view['proven_gap_occurrences']} currently established")
    columns[2].metric("Unique missing capabilities", view["unique_missing_capabilities"])
    st.caption(f"{view['numerator']} / {view['denominator']} confirmed capability requirements represented · "
        f"Current taxonomy status: {view['eligible_analyzed_jobs']} analyzed jobs · "
        f"Review pending: {view['pending_analyzed_jobs']} analyzed jobs · "
        f"Jobs affected by proven gaps: {view['jobs_affected']} · Unanalyzed: {view['unanalyzed_jobs']}. "
        f"Additional analysis items: {view['additional_analysis_items']}. "
        "Unresolved or unreviewed requirements are excluded from confirmed taxonomy coverage and are not assumed to be taxonomy gaps.")
    if view["pending"]:
        with st.expander("Analyzed jobs awaiting reviewed/current taxonomy status"):
            st.dataframe(view["pending"], hide_index=True, width="stretch")
    return view
