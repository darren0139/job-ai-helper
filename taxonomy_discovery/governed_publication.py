"""Explicit H.1 publication adapter over native knowledge artifacts and stores.

SQLite is audit/review history only. Runtime authority remains the native JSON.
"""

from taxonomy_discovery.offline_execution import offline_execution
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from taxonomy_discovery.corpus_expansion import fingerprint
from database import taxonomy_discovery_review_manager as store

PUBLICATION_VERSION = "tqd3-governed-publication-v1"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def list_publications(*, db_path=None):
    path = store._resolved_path(db_path)
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='governed_publications'").fetchone():
            return []
        return [json.loads(r[0]) for r in conn.execute("SELECT receipt_json FROM governed_publications ORDER BY publication_id")]


def latest_impact(result_id, *, db_path=None):
    path = store._resolved_path(db_path)
    if not path.exists():
        return None
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='governed_temporary_impacts'").fetchone():
            return None
        row = conn.execute("SELECT report_json FROM governed_temporary_impacts WHERE result_id=?",(result_id,)).fetchone()
        return json.loads(row[0]) if row else None


def _approved(conn, result_id):
    from taxonomy_discovery.governed_research import validate_result, knowledge_fingerprint, validate_candidate, create_draft
    from job_discovery.matching import current_match_versions
    row = conn.execute("SELECT result_json,result_fingerprint,draft_json,review_json FROM governed_research_results WHERE result_id=?",(result_id,)).fetchone()
    if not row or not row[2] or not row[3]:
        raise ValueError("Saved research, draft and human approval required")
    result, draft, review = json.loads(row[0]),json.loads(row[2]),json.loads(row[3])
    if draft.get("status") not in {"proposal_only","draft"} or draft.get("requires_human_approval") is not True:
        raise ValueError("Publication-eligible governed draft required")
    validate_result(result)
    validate_candidate(result["candidate"])
    if result["research_result_id"] != result_id or result["result_fingerprint"] != row[1] or review.get("result_fingerprint") != row[1]:
        raise ValueError("Source research fingerprint changed")
    if review.get("decision") != "approve_for_publication" or not str(review.get("reviewer","")).strip() or not review.get("updated_at"):
        raise ValueError("Latest explicit human approval and reviewer required")
    if not result.get("source_gap_provenance") or result.get("conflicts_blockers"):
        raise ValueError("Source provenance/evidence absent or conflicted")
    report = review.get("regression")
    if not report or report.get("draft_fingerprint") != fingerprint(draft):
        raise ValueError("Approval belongs to a different draft")
    if report.get("regression_fingerprint") != fingerprint({k:v for k,v in report.items() if k != "regression_fingerprint"}):
        raise ValueError("Regression fingerprint changed")
    table = conn.execute("SELECT 1 FROM sqlite_master WHERE name='governed_temporary_impacts'").fetchone()
    latest = conn.execute("SELECT report_json FROM governed_temporary_impacts WHERE result_id=?",(result_id,)).fetchone() if table else None
    if not latest or json.loads(latest[0]) != report:
        raise ValueError("Latest regression differs from the approved regression")
    if report.get("current_versions") != current_match_versions() or report.get("knowledge_fingerprint") != knowledge_fingerprint():
        raise ValueError("Approved production knowledge/scoring identity changed")
    if report.get("publication_blockers") or report.get("unexpectedly_changed_requirements"):
        raise ValueError("Unexpected requirement changes or publication blockers")
    if (report.get("review_only") is not True or not report.get("corpus_fingerprint") or not report.get("jobs")
        or any(j.get("available") is not True or j.get("duplicate_credit_violations") != []
            or j.get("classification") == "hard_regression/invariant_violation"
            or not isinstance(j.get("requirement_changes"),list) for j in report["jobs"])):
        raise ValueError("Missing/invalid regression or duplicate credit")
    provenance = draft.get("governed_research") if draft.get("kind") == "resolver_improvement" else draft.get("proposal",{}).get("governed_research") if draft.get("kind") == "capability" else draft.get("proposal_bundle",{}).get("proposals",[{}])[0].get("governed_research")
    if not provenance or provenance.get("research_result_id") != result_id or provenance.get("result_fingerprint") != row[1]:
        raise ValueError("Draft source evidence linkage changed")
    if draft.get("kind") != "capability" and create_draft(result,explicit_creation=True) != draft:
        raise ValueError("Draft differs from deterministic source research")
    return result,draft,review,report


def _next_version(version, prefix):
    match = re.fullmatch(re.escape(prefix)+r"(\d+)\.(\d+)",version)
    if not match:
        raise ValueError("Unsupported native knowledge version")
    return prefix+match[1]+"."+str(int(match[2])+1)


def _prepare(conn, result_id, proposal_db_path=None):
    from tailoring import capability_taxonomy as taxonomy
    from taxonomy_discovery import technology_registry as registry
    result,draft,review,report = _approved(conn,result_id)
    kind = draft["kind"]
    if kind == "technology":
        kind = "technology_relationship" if draft["proposal_bundle"]["proposals"][0]["proposal_classification"] == "safe_mapping_candidate" else "technology_identity"
    if kind in {"resolver_improvement","capability"}:
        path = Path(taxonomy.TAXONOMY_PATH).resolve()
        original = path.read_bytes()
        raw = json.loads(original)
        if fingerprint(taxonomy.load_taxonomy(path).capabilities) != fingerprint(taxonomy.get_default_taxonomy().capabilities):
            raise ValueError("Native taxonomy cache/file identity differs")
        if kind == "resolver_improvement":
            from taxonomy_discovery.resolver_improvement import resolver_overlay
            shadow = resolver_overlay(draft)
            if report.get("temporary_resolver_identity") != shadow.version or report.get("unexpectedly_changed_requirements") != [] or report.get("publication_blockers") != []:
                raise ValueError("Guarded resolver requires a clean current regression")
            from taxonomy_discovery.candidate_refinement import product_context_names
            names = product_context_names()
            if (report.get("resolver_product_context_names") != names or report.get("resolver_product_context_fingerprint") != fingerprint(names)
                or report.get("resolver_guard_contract_version") != taxonomy.PRODUCT_CONTEXT_GUARD_VERSION):
                raise ValueError("Product-context vocabulary missing/changed: preview locally and explicitly approve again")
            cid = draft["target_capability_id"]
            target = next(e for e in raw["capabilities"] if e["capability_id"] == cid)
            if target["requirement"].get("contextual_phrase_variants"):
                raise ValueError("Conflicting/duplicate production resolver rule exists")
            applied = deepcopy(shadow.by_id()[cid]["requirement"]["contextual_phrase_variants"])
            for variant in applied:
                variant["excluded_product_names"] = names
                variant["guard_contract_version"] = taxonomy.PRODUCT_CONTEXT_GUARD_VERSION
            target["requirement"]["contextual_phrase_variants"] = applied
            change = {"capability_id":cid,"contextual_phrase_variants":applied}
        else:
            from taxonomy_discovery.taxonomy_evolution import temporary_overlay
            proposal = draft["proposal"]
            saved = conn.execute("SELECT proposal_json FROM taxonomy_evolution_proposals WHERE proposal_id=?",(proposal["proposal_id"],)).fetchone()
            if not saved or json.loads(saved[0]) != proposal:
                raise ValueError("Immutable native capability proposal differs/missing")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='taxonomy_evolution_reviews'").fetchone():
                native_review = conn.execute("SELECT review_json FROM taxonomy_evolution_reviews WHERE proposal_id=?",(proposal["proposal_id"],)).fetchone()
                if native_review and json.loads(native_review[0]).get("decision") not in {"undecided","approve_for_publication"}:
                    raise ValueError("Native capability proposal has a conflicting/rejected human decision")
            if proposal.get("gap_candidate") != result["candidate"] or proposal.get("research_evidence") != result["research"]:
                raise ValueError("Capability proposal source research changed")
            shadow = temporary_overlay([proposal])
            cid = proposal["proposed_capability_id"]
            entry = deepcopy(shadow.by_id()[cid])
            existing_phrases = {taxonomy.normalise(p) for c in taxonomy.get_default_taxonomy().capabilities
                for p in [c["label"],*c["requirement"].get("any_terms",[])]}
            if any(taxonomy.normalise(p) in existing_phrases for p in entry["requirement"]["any_terms"]):
                raise ValueError("Capability requirement phrase/alias conflicts with existing production knowledge")
            # A new capability requires native matcher/evidence predicates and
            # affirmative first-party source evidence; local lexical hints do not suffice.
            if not result.get("quality_diagnostics",{}).get("primary_definitions"):
                raise ValueError("Capability publication requires first-party definitions")
            raw["capabilities"].append(entry)
            change = {"capability_id":cid,"entry":entry}
        raw["taxonomy_version"] = _next_version(raw["taxonomy_version"],"phase6d-capability-taxonomy-v")
        before_version = taxonomy.load_taxonomy(path).version
        after_version = raw["taxonomy_version"]
    elif kind in {"technology_identity","technology_relationship"}:
        from database.technology_registry_proposal_manager import list_proposals, list_proposal_reviews
        from taxonomy_discovery.research_proposals import build_registry_vnext_preview
        path = Path(registry.REGISTRY_PATH).resolve()
        original = path.read_bytes()
        raw = json.loads(original)
        bundle = draft["proposal_bundle"]
        proposal = bundle["proposals"][0]
        saved = next((p for p in list_proposals(db_path=proposal_db_path) if p["proposal_id"] == proposal["proposal_id"]),None)
        expected = deepcopy(proposal)
        expected["knowledge_context"] = {"taxonomy_version":bundle["taxonomy_version"],"registry_version":bundle["registry_version"]}
        native_fingerprint = _sha(json.dumps(expected,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())
        if not saved or saved.get("source_fingerprint") != native_fingerprint:
            raise ValueError("Native imported proposal fingerprint differs/missing")
        decision = "approve_mapping" if kind == "technology_relationship" else "approve_identity"
        native_review = next((r for r in list_proposal_reviews(db_path=proposal_db_path) if r["proposal_id"] == proposal["proposal_id"] and r["proposal_bundle_version"] == bundle["proposal_bundle_version"]),None)
        if native_review and native_review["decision"] not in {"unreviewed",decision}:
            raise ValueError("Native proposal has a conflicting/rejected human decision")
        preview = build_registry_vnext_preview([saved],[{"proposal_id":saved["proposal_id"],"proposal_bundle_version":bundle["proposal_bundle_version"],"decision":decision}],registry_path=path)
        if preview["skipped"] or preview["applied_proposal_ids"] != [saved["proposal_id"]]:
            raise ValueError("Native registry preview conflict: "+str(preview["skipped"]))
        promoted = preview["registry_preview"]
        promoted["description"] = raw.get("description","")
        if sorted(raw["entries"],key=lambda e:e["technology_id"]) == promoted["entries"]:
            raise ValueError("Duplicate production registry knowledge")
        before_version = raw["registry_version"]
        promoted["registry_version"] = _next_version(before_version,"technology-registry-v")
        raw = promoted
        after_version = raw["registry_version"]
        registry._validate_registry(raw)
        change = {"technology_id":proposal["technology_id"],"proposal":proposal,"native_source_fingerprint":native_fingerprint}
    else:
        raise ValueError("Proposal family has no safe native publication contract")
    # Taxonomy entries are maintained in a stable, human-reviewed field order.
    # They are mutated in place above, so sorting every mapping here creates a
    # repository-wide formatting diff for a one-field publication.  Registry
    # previews retain their established canonical sorted representation.
    sort_keys = kind in {"technology_identity", "technology_relationship"}
    encoded = (json.dumps(raw,ensure_ascii=False,indent=2,sort_keys=sort_keys)+"\n").encode()
    return {"kind":kind,"result":result,"draft":draft,"review":review,"regression":report,"path":path,"original":original,
        "encoded":encoded,"version_before":before_version,"version_after":after_version,"change":change}


def prepare_publication(result_id, *, db_path=None, proposal_db_path=None):
    """Read-only fresh preflight; no schema creation, approval or publication."""
    path = store._resolved_path(db_path)
    try:
        with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)) as conn:
            p = _prepare(conn,result_id,proposal_db_path)
        return {"ready":True,"blockers":[],"kind":p["kind"],"change":p["change"],"artifact":str(p["path"]),
            "version_before":p["version_before"],"version_after":p["version_after"],"draft_fingerprint":fingerprint(p["draft"]),
            "regression_fingerprint":p["regression"]["regression_fingerprint"],"affected_jobs":p["regression"]["affected_jobs"],
            "reviewer":p["review"]["reviewer"],"approval_timestamp":p["review"]["updated_at"]}
    except (ValueError,KeyError,IndexError,TypeError,OSError,sqlite3.Error) as exc:
        return {"ready":False,"blockers":[str(exc)]}


def _present(receipt):
    path = Path(receipt["production_artifact"])
    raw = json.loads(path.read_bytes())
    change = receipt["change_applied"]
    if receipt["kind"] == "resolver_improvement":
        entry = next((c for c in raw["capabilities"] if c["capability_id"] == change["capability_id"]),{})
        return all(v in entry.get("requirement",{}).get("contextual_phrase_variants",[]) for v in change["contextual_phrase_variants"])
    if receipt["kind"] == "capability":
        return change["entry"] in raw["capabilities"]
    from database.technology_registry_proposal_manager import _published_knowledge_present
    from taxonomy_discovery.technology_registry import load_registry
    return _published_knowledge_present(change["proposal"],load_registry(path))


def _publish_approved_change(result_id, *, explicit_publish=False, db_path=None, proposal_db_path=None):
    if explicit_publish is not True:
        raise ValueError("Explicit confirmed publication required")
    with closing(store._connect(store._resolved_path(db_path),create_parent=False)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("CREATE TABLE IF NOT EXISTS governed_publications (publication_id TEXT PRIMARY KEY, result_id TEXT, idempotency_key TEXT UNIQUE, receipt_json TEXT NOT NULL)")
        row = conn.execute("SELECT draft_json FROM governed_research_results WHERE result_id=?",(result_id,)).fetchone()
        if not row or not row[0]:
            raise ValueError("Saved draft required")
        key = fingerprint(json.loads(row[0]))
        existing = conn.execute("SELECT receipt_json FROM governed_publications WHERE idempotency_key=?",(key,)).fetchone()
        if existing:
            receipt = json.loads(existing[0])
            if _present(receipt):
                if receipt["status"] != "published":
                    receipt["status"] = "published"
                    conn.execute("UPDATE governed_publications SET receipt_json=? WHERE publication_id=?",(json.dumps(receipt,sort_keys=True),receipt["publication_id"]))
                    conn.commit()
                return receipt
            if receipt["status"] == "published":
                raise ValueError("Published knowledge subsequently changed; new review required")
        p = _prepare(conn,result_id,proposal_db_path)
        review = p["review"]
        lineage = []
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='governed_resolver_draft_history'").fetchone():
            lineage = [{"draft":json.loads(r[0]),"review":json.loads(r[1])} for r in conn.execute(
                "SELECT draft_json,review_json FROM governed_resolver_draft_history WHERE result_id=?",(result_id,))]
        receipt = {"publication_contract_version":PUBLICATION_VERSION,"publication_id":"tqd3pub_"+key[:24],
            "kind":p["kind"],"candidate_id":p["result"]["candidate"]["candidate_id"],"research_result_id":result_id,
            "candidate_fingerprint":p["result"]["candidate"]["candidate_fingerprint"],"source_result_fingerprint":p["result"]["result_fingerprint"],
            "draft_id":p["draft"].get("resolver_draft_id") or p["draft"].get("proposal",{}).get("proposal_id") or p["draft"].get("proposal_bundle",{}).get("proposals",[{}])[0].get("proposal_id"),
            "draft_fingerprint":key,"regression_fingerprint":p["regression"]["regression_fingerprint"],
            "review_id":fingerprint(review),"reviewer":review["reviewer"],"approval_timestamp":review["updated_at"],
            "publication_timestamp":_now(),"production_artifact":str(p["path"]),"artifact_hash_before":_sha(p["original"]),
            "artifact_hash_after":_sha(p["encoded"]),"version_before":p["version_before"],"version_after":p["version_after"],
            "change_applied":p["change"],"previous_draft_lineage":lineage,"affected_jobs":p["regression"]["affected_jobs"],
            "status":"prepared","idempotency_key":key}
        if existing:
            previous = json.loads(existing[0])
            if any(previous[k] != receipt[k] for k in ("review_id","regression_fingerprint","artifact_hash_before","artifact_hash_after","version_before","version_after")):
                raise ValueError("Prepared publication approval/knowledge changed; a new governed draft is required")
            receipt = previous  # Preserve original intent/audit timestamp on retry.
        else:
            conn.execute("INSERT INTO governed_publications VALUES (?,?,?,?)",(receipt["publication_id"],result_id,key,json.dumps(receipt,sort_keys=True)))
        conn.commit()  # Journal explicit intent before replacing native knowledge.
        conn.execute("BEGIN IMMEDIATE")
        checked = _prepare(conn,result_id,proposal_db_path)
        if checked["original"] != p["original"] or checked["draft"] != p["draft"] or checked["review"] != review:
            raise ValueError("Approval/knowledge changed during publication staging")
        if p["draft"]["kind"] in {"resolver_improvement","capability"}:
            from database.technology_registry_proposal_manager import _replace_knowledge
            from tailoring.capability_taxonomy import load_taxonomy
            _replace_knowledge(p["path"],p["original"],p["encoded"],load_taxonomy)
        else:
            from database.technology_registry_proposal_manager import save_proposal_review, publish_approved_proposal
            proposal = p["draft"]["proposal_bundle"]["proposals"][0]
            # Translate this exact H.1 human approval to the native proposal
            # review contract only as part of the explicit publication action.
            save_proposal_review(proposal_id=proposal["proposal_id"],decision="approve_mapping" if p["kind"] == "technology_relationship" else "approve_identity",
                notes="Governed human approval "+receipt["review_id"]+" by "+review["reviewer"],
                db_path=proposal_db_path,proposal_bundle_version=p["draft"]["proposal_bundle"]["proposal_bundle_version"])
            native = publish_approved_proposal(proposal_id=proposal["proposal_id"],explicit_publish=True,
                expected_source_fingerprint=p["change"]["native_source_fingerprint"],expected_registry_version=p["version_before"],
                proposal_bundle_version=p["draft"]["proposal_bundle"]["proposal_bundle_version"],db_path=proposal_db_path,registry_path=p["path"])
            receipt["native_publication_receipt"] = native
            receipt["artifact_hash_after"] = _sha(p["path"].read_bytes())
        receipt["status"] = "published"
        conn.execute("UPDATE governed_publications SET receipt_json=? WHERE publication_id=?",(json.dumps(receipt,sort_keys=True),receipt["publication_id"]))
        conn.commit()
    return receipt


def list_linkage_receipts(*, db_path=None):
    path = store._resolved_path(db_path)
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='governed_publication_linkage'").fetchone():
            return []
        return [json.loads(r[0]) for r in conn.execute("SELECT report_json FROM governed_publication_linkage")]


def refresh_published_jobs(receipt, *, explicit_refresh=False, db_path=None):
    """Native zero-model rebuild; unavailable/changed inputs stay visibly stale."""
    if explicit_refresh is not True or receipt not in list_publications(db_path=db_path) or receipt.get("status") != "published" or not _present(receipt):
        raise ValueError("Explicit refresh of a durable active publication required")
    from database.job_match_manager import publication_rebuild_inputs
    from job_discovery.matching import analyze_job_match, current_evidence_context, current_match_versions
    # The approved regression is pinned in the human review, not a new corpus.
    with closing(sqlite3.connect(store._resolved_path(db_path).as_uri()+"?mode=ro",uri=True)) as conn:
        row = conn.execute("SELECT review_json FROM governed_research_results WHERE result_id=?",(receipt["research_result_id"],)).fetchone()
        review = json.loads(row[0]) if row and row[0] else {}
    regression = review.get("regression") or {}
    jobs = []
    def forbid_extraction(_):
        raise ValueError("Saved compatible JD extraction unavailable; explicit refresh required")
    with offline_execution('Offline publication refresh forbids network'):
        for job_id in receipt["affected_jobs"]:
            try:
                if regression.get("regression_fingerprint") != receipt["regression_fingerprint"]:
                    raise ValueError("Historical approved regression unavailable")
                approved = next(j for j in regression["jobs"] if j["job_id"] == job_id)
                job,snapshot = publication_rebuild_inputs(job_id,approved["snapshot_id"])
                context = current_evidence_context()
                if not context.get("evidence_item_count"):
                    raise ValueError("Current Profile & Evidence unavailable; explicit refresh required")
                output = analyze_job_match(job,context=context,jd_profile_extractor=forbid_extraction)
                jobs.append({"job_id":job_id,"status":"current","historical_snapshot_id":snapshot["id"],"current_snapshot_id":output["snapshot"]["id"],"current_versions":current_match_versions()})
            except (ValueError,RuntimeError,KeyError,StopIteration,OSError,sqlite3.Error) as exc:
                jobs.append({"job_id":job_id,"status":"stale_currentness_required","reason":str(exc)})
    linkage = {"publication_id":receipt["publication_id"],"jobs":jobs,"current_versions":current_match_versions(),"refreshed_at":_now(),"network_calls":0,"model_calls":0}
    with closing(store._connect(store._resolved_path(db_path),create_parent=False)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS governed_publication_linkage (linkage_id TEXT PRIMARY KEY, report_json TEXT NOT NULL)")
        conn.execute("INSERT INTO governed_publication_linkage VALUES (?,?)",(fingerprint(linkage),json.dumps(linkage,sort_keys=True)))
        conn.commit()
    return linkage


def publish_approved_change(result_id, *, explicit_publish=False, db_path=None, proposal_db_path=None):
    receipt = _publish_approved_change(result_id,explicit_publish=explicit_publish,db_path=db_path,proposal_db_path=proposal_db_path)
    if not any(r["publication_id"] == receipt["publication_id"] for r in list_linkage_receipts(db_path=db_path)):
        refresh_published_jobs(receipt,explicit_refresh=True,db_path=db_path)
    return receipt


def review_ledger(*, db_path=None):
    """H.1 lineage only; never conflate Broad Mining candidate reviews."""
    receipts = list_publications(db_path=db_path)
    output = []
    def append(result,draft,review,*,superseded_by=None):
        receipt = next((r for r in receipts if r["draft_fingerprint"] == fingerprint(draft)),None) if draft else None
        decision = review.get("decision","undecided")
        state = "published" if receipt and receipt["status"] == "published" else "superseded" if superseded_by else {
            "reject":"rejected","defer":"deferred","approve_for_publication":"approved_pending_publication","research_more":"research_more"}.get(decision,"pending_review")
        report = review.get("regression") or ({} if superseded_by else latest_impact(result["research_result_id"],db_path=db_path)) or {}
        blockers = list(report.get("publication_blockers",[]))
        if report.get("unexpectedly_changed_requirements") and "unexpected_requirement_changes" not in blockers:
            blockers.append("unexpected_requirement_changes")
        if any(j.get("duplicate_credit_violations") for j in report.get("jobs",[])):
            blockers.append("duplicate_credit_violations")
        if report.get("jobs") and any(j.get("available") is not True for j in report["jobs"]):
            blockers.append("regression_unavailable")
        output.append({"concept":result["candidate"]["concept_key"],"candidate_id":result["candidate"]["candidate_id"],
            "research_result_id":result["research_result_id"],"kind":(draft or {}).get("kind"),"route":result["candidate_route"],
            "draft_version":(draft or {}).get("resolver_draft_version") or (draft or {}).get("proposal",{}).get("proposal_schema_version"),
            "draft_id":(draft or {}).get("resolver_draft_id") or (draft or {}).get("draft_id") or (draft or {}).get("proposal",{}).get("proposal_id"),
            "status":state,"human_decision":decision,"reviewer":review.get("reviewer"),"decision_timestamp":review.get("updated_at"),
            "regression_status":"blocked" if blockers else "clean" if report.get("jobs") else "missing",
            "regression_blockers":blockers,"publication":receipt,"superseded_by":superseded_by})
    saved = store.list_governed_research_results(db_path=db_path)
    superseded_results = {r["result"].get("interpretation_lineage",{}).get("previous_research_result_id"):r["result"]["research_result_id"] for r in saved}
    for row in saved:
        append(row["result"],row["draft"],row["review"],superseded_by=superseded_results.get(row["result"]["research_result_id"]))
    path = store._resolved_path(db_path)
    if path.exists():
        with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)) as conn:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='governed_resolver_draft_history'").fetchone():
                for rid,draft,review in conn.execute("SELECT result_id,draft_json,review_json FROM governed_resolver_draft_history"):
                    current = next((r for r in saved if r["result"]["research_result_id"] == rid),None)
                    if current:
                        append(current["result"],json.loads(draft),json.loads(review),superseded_by=(current["draft"] or {}).get("resolver_draft_id"))
    return output
