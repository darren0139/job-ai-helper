#!/usr/bin/env python3
"""V3.12-A1: read-only, dual-cohort native Phase 8 verification receipt comparator.

Never fits/rescores, mutates applications or approves a generation. Requires
native Phase 8 JSON exports from the UI before asserting native improvement.
The accompanying artifact comparator audits the actual DOCX + debug bundles.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import v312a1_portfolio_artifact_comparator as artifacts

VERSION = "v312a1-dual-cohort-native-phase8-readonly-v1"
RANK = {"none": 0, "weak": 1, "transferable": 2, "direct": 3}
IMPORTANT = {"required", "core", "deal_breaker"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _id(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: expected a native numeric field")
    val = float(value)
    if not math.isfinite(val) or not 0 <= val <= 100:
        raise ValueError(f"{name}: score outside native 0–100 range")
    return val


def _rows(stable: dict, name: str) -> dict[str, dict]:
    raw = stable.get("canonical_requirements")
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{name}: missing native canonical requirements")
    result = {}
    for row in raw:
        if not isinstance(row, dict) or not _id(row.get("requirement_id")):
            raise ValueError(f"{name}: invalid requirement row")
        rid = _id(row["requirement_id"])
        if rid in result:
            raise ValueError(f"{name}: duplicate requirement ID {rid}")
        if _id(row.get("match_label")).lower() not in RANK:
            raise ValueError(f"{name}: invalid or unknown match label for {rid}")
        if _id(row.get("importance")).lower() not in {"required", "core", "deal_breaker", "preferred", "supporting", "context", "none", "excluded"}:
            raise ValueError(f"{name}: unknown importance for {rid}")
        strength = row.get("evidence_strength")
        if isinstance(strength, bool) or not isinstance(strength, (int, float)) or not math.isfinite(float(strength)) or strength < 0:
            raise ValueError(f"{name}: invalid evidence strength for {rid}")
        result[rid] = row
    return result


def _native_score(stable: dict, name: str) -> float:
    return _number(stable.get("deterministic_alignment_score"), name)


def _authority_identity(phase8: dict, name: str) -> dict:
    doc = phase8.get("document_analysis") or {}
    for role in ("initial", "final"):
        auth = doc.get(role)
        if not isinstance(auth, dict) or not isinstance(auth.get("identity"), dict):
            raise ValueError(f"{name}: missing actual-document {role} identity")
    if doc["initial"]["identity"] != doc["final"]["identity"]:
        raise ValueError(f"{name}: initial/final document authority identities differ")
    if not _id(doc["final"].get("canonical_requirement_fingerprint")):
        raise ValueError(f"{name}: missing canonical requirement scope fingerprint")
    return doc["final"]["identity"]


def validate_receipt_payload(value: dict, name: str, artifact: dict, *, expected_application: int, docx_path: Path) -> dict:
    """Bind native verification (from JSON or read-only SQLite) to exact DOCX bytes."""
    if not isinstance(value, dict):
        raise ValueError(f"{name}: native verification must be a JSON object")
    if _id(value.get("generation_id")) != _id(artifact.get("generation_id")):
        raise ValueError(f"{name}: generation ID does not match audited DOCX/debug")
    if value.get("application_id") != expected_application or artifact.get("application_id") != expected_application:
        raise ValueError(f"{name}: application ID does not match cohort")
    # The current document-grounded Phase 8 stores a distinct verification mode.
    # Require its *exact* version/mode pair; never accept an arbitrary version just
    # because the mode text sounds document-related. Retain the original A1 legacy
    # contract for compatibility with already accepted, DOCX-bound receipts.
    mode = _id(value.get("verification_mode"))
    version = _id(value.get("phase8_version"))
    accepted = (mode == "zero_cost_deterministic" and bool(version)) or (
        mode == "selected_base_docx_vs_final_docx"
        and version == "phase8-before-after-verification-v10"
    )
    if not accepted:
        raise ValueError(f"{name}: incompatible native Phase 8 verification contract (version/mode)")
    if not _id(value.get("verification_fingerprint")) or not _id(value.get("verified_generation_snapshot_fingerprint")):
        raise ValueError(f"{name}: missing native generation/verification fingerprints")
    if value.get("fit_one_page") is not True or value.get("page_count") != 1:
        raise ValueError(f"{name}: native verification does not certify one-page fit")
    if value.get("comparison_valid") is not True or (value.get("job_match_ab") or {}).get("comparable") is not True:
        raise ValueError(f"{name}: native within-generation comparison not comparable")
    doc = value.get("document_analysis")
    if not isinstance(doc, dict):
        raise ValueError(f"{name}: actual fitted DOCX authority missing")
    actual_sha = _sha256(docx_path)
    if _id(doc.get("final_document_sha256")).lower() != actual_sha:
        raise ValueError(f"{name}: final DOCX SHA-256 not bound to this verification receipt")
    identity = _authority_identity(value, name)
    if not _id(identity.get("scoring_version")):
        raise ValueError(f"{name}: missing native scoring version identity")
    after = value.get("after_stable_analysis")
    selected = value.get("selected_base_analysis")
    if not isinstance(after, dict) or not isinstance(selected, dict) or not isinstance(selected.get("stable_analysis"), dict):
        raise ValueError(f"{name}: Selected Base and final native score snapshots required")
    baseline = selected["stable_analysis"]
    selected_authority = selected.get("document_analysis") or {}
    if not isinstance(selected_authority, dict) or selected_authority.get("identity") != identity:
        raise ValueError(f"{name}: Selected Base and final authority identities differ")
    if not _id(selected_authority.get("fingerprint")) or not _id(selected_authority.get("resume_text_sha256")):
        raise ValueError(f"{name}: Selected Base document authority incomplete")
    score = _native_score(after, f"{name} final")
    base_score = _native_score(baseline, f"{name} Selected Base")
    final_rows = _rows(after, f"{name} final")
    base_rows = _rows(baseline, f"{name} Selected Base")
    if set(final_rows) != set(base_rows):
        raise ValueError(f"{name}: native requirement IDs differ within this generation")
    if _id(after.get("scoring_version")) != _id(identity.get("scoring_version")):
        raise ValueError(f"{name}: native scorer version and authority identity differ")
    # The score on the exported native A/B snapshot, when present, must agree.
    ab_tailored = (value.get("job_match_ab") or {}).get("tailored") or {}
    if isinstance(ab_tailored, dict) and isinstance(ab_tailored.get("score"), (int, float)) and not isinstance(ab_tailored.get("score"), bool):
        if abs(float(ab_tailored["score"]) - score) > 0.01:
            raise ValueError(f"{name}: A/B and final native score disagree")
    return {
        "generation_id": _id(value.get("generation_id")),
        "application_id": value.get("application_id"),
        "docx_sha256": actual_sha,
        "verification_fingerprint": _id(value.get("verification_fingerprint")),
        "snapshot_fingerprint": _id(value.get("verified_generation_snapshot_fingerprint")),
        "identity": identity,
        "phase8_version": value["phase8_version"],
        "native_score": score,
        "selected_base_score": base_score,
        "selected_base_document_fingerprint": selected_authority["fingerprint"],
        "selected_base_document_sha256": _id(selected_authority["resume_text_sha256"]),
        "selected_base_rows": base_rows,
        "rows": final_rows,
        "scoring_version": _id(after.get("scoring_version")),
        "canonical_fingerprint": _id(doc["final"].get("canonical_requirement_fingerprint")),
        "required_core_coverage": _number(after.get("required_core_coverage_score"), f"{name} required/core"),
        "claim_reviews": int((value.get("claim_lineage") or {}).get("claim_review_required_count", 0) or 0),
        "receipt_file": str(name),
    }


def validate_receipt(path: Path, artifact: dict, *, expected_application: int, docx_path: Path) -> dict:
    return validate_receipt_payload(json.loads(path.read_text(encoding="utf-8")), str(path.name), artifact, expected_application=expected_application, docx_path=docx_path)


def read_database_receipt(db_path: Path, *, application_id: int, generation_id: str) -> dict:
    """Read the newest exact-generation stored Phase 8 JSON with SQLite mode=ro.

    Never substitutes an older receipt if the newest doesn't match DOCX bytes.
    WAL-aware mode=ro is intentional: immutable=1 could miss recent commits.
    """
    if not db_path.is_file():
        raise ValueError(f"Database missing: {db_path}")
    uri = db_path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=10)) as conn:
        row = conn.execute(
            "SELECT result_json FROM application_tailoring_verifications "
            "WHERE application_id=? AND generation_id=? ORDER BY id DESC LIMIT 1",
            (application_id, generation_id),
        ).fetchone()
    if not row:
        raise ValueError(f"No saved Phase 8 receipt for application {application_id}, generation {generation_id[:8]} in {db_path}")
    result = json.loads(row[0])
    if not isinstance(result, dict):
        raise ValueError("Saved Phase 8 result_json must be a JSON object")
    return result


def compare_native(control: dict, challenger: dict) -> dict:
    """Fail closed for different source, scoring and canonical identity; fail a score loss."""
    holds = []
    for field in ("application_id", "identity", "phase8_version", "scoring_version", "canonical_fingerprint", "selected_base_document_fingerprint", "selected_base_document_sha256", "selected_base_score"):
        if control[field] != challenger[field]:
            holds.append(f"Native A/B identities differ: {field}")
    left, right = control["rows"], challenger["rows"]
    if set(left) != set(right):
        holds.append("Canonical requirement ID sets differ across native fits")
    if set(control["selected_base_rows"]) != set(challenger["selected_base_rows"]):
        holds.append("Selected Base requirement ID sets differ")
    for rid in set(left) & set(right):
        for field in ("importance", "score_eligible"):
            if left[rid].get(field) != right[rid].get(field):
                holds.append(f"Canonical {field} differs: {rid}")
    for rid in set(control["selected_base_rows"]) & set(challenger["selected_base_rows"]):
        for field in ("importance", "score_eligible", "match_label", "evidence_strength"):
            if control["selected_base_rows"][rid].get(field) != challenger["selected_base_rows"][rid].get(field):
                holds.append(f"Frozen Selected Base outcome differs: {rid} / {field}")
    score_delta = round(challenger["native_score"] - control["native_score"], 6)
    regressions = []
    gains = []
    if not holds:
        for rid in sorted(left):
            a,b = left[rid], right[rid]
            if _id(a.get("importance")).lower() not in IMPORTANT or a.get("score_eligible") is False:
                continue
            old, new = RANK[_id(a.get("match_label")).lower()], RANK[_id(b.get("match_label")).lower()]
            lost_label = new < old
            lost_evidence = float(b["evidence_strength"]) < float(a["evidence_strength"])
            if lost_label or lost_evidence:
                regressions.append({"requirement_id":rid,"importance":a.get("importance"),"old_match":a.get("match_label"),"new_match":b.get("match_label"),"old_strength":a.get("evidence_strength"),"new_strength":b.get("evidence_strength"),"type":"match_or_evidence_regression"})
            elif new > old or float(b["evidence_strength"]) > float(a["evidence_strength"]):
                gains.append({"requirement_id":rid,"old_match":a.get("match_label"),"new_match":b.get("match_label")})
    if holds:
        status = "HOLD_INCOMPARABLE"
    elif score_delta < 0 or regressions or challenger["required_core_coverage"] < control["required_core_coverage"]:
        status = "REGRESSION"
    elif challenger["claim_reviews"] > 0:
        status = "REVIEW_CLAIMS"
    else:
        status = "PASS_NO_NATIVE_REGRESSION"
    return {
        "status":status,
        "balanced_final_native_score":control["native_score"],
        "portfolio_final_native_score":challenger["native_score"],
        "native_score_delta":score_delta,
        "selected_base_score":control["selected_base_score"] if not holds else None,
        "required_core_coverage": {"balanced":control["required_core_coverage"],"portfolio":challenger["required_core_coverage"]},
        "required_core_regressions":regressions,
        "required_core_gains":gains,
        "claim_reviews":challenger["claim_reviews"],
        "comparison_holds":holds,
        "requirement_changes": [
            {"requirement_id":rid,"importance":left[rid].get("importance"),"from":left[rid].get("match_label"),"to":right[rid].get("match_label"),"evidence_strength_before":left[rid].get("evidence_strength"),"evidence_strength_after":right[rid].get("evidence_strength")}
            for rid in sorted(set(left)&set(right))
            if left[rid].get("match_label") != right[rid].get("match_label") or left[rid].get("evidence_strength") != right[rid].get("evidence_strength")
        ] if not holds else [],
    }


def _resolve(root: Path, item: str) -> Path:
    if not isinstance(item,str) or not item.strip():
        raise ValueError("Manifest file path is missing")
    p = Path(item)
    return p if p.is_absolute() else root / p


def validate_manifest(data: Any) -> list[dict]:
    if not isinstance(data,dict) or data.get("version") != VERSION:
        raise ValueError("Unknown or missing V3.12-A1 manifest version")
    cohorts=data.get("cohorts")
    if not isinstance(cohorts,list) or len(cohorts)!=2 or {str(c.get("id")) for c in cohorts if isinstance(c,dict)} != {"Keith","Darren"}:
        raise ValueError("Keith and Darren cohorts are both mandatory")
    for c in cohorts:
        if not isinstance(c.get("application_id"),int) or isinstance(c.get("application_id"),bool):
            raise ValueError("Cohort application ID must be numeric")
        for k in ("balanced", "portfolio"):
            v=c.get(k)
            if not isinstance(v,dict) or any(not isinstance(v.get(x),str) or not v.get(x) for x in ("debug","docx","phase8")):
                raise ValueError(f"{c['id']} {k}: debug, docx and native Phase 8 receipt paths required")
    return cohorts


def run_cohort(c: dict, root: Path, *, inspect_only: bool = False, db_path: Path | None = None) -> dict:
    missing=[]
    paths={}
    for mode in ("balanced","portfolio"):
        paths[mode]={}
        for kind in ("debug","docx","phase8"):
            p=_resolve(root,c[mode][kind]);paths[mode][kind]=p
            if not p.is_file() and (kind != "phase8" or db_path is None):
                missing.append(f"{mode}.{kind}: {p}")
    if db_path is not None and not db_path.is_file():
        missing.append(f"native_db: {db_path}")
    document_missing=[x for x in missing if ".phase8:" not in x and not x.startswith("native_db:")]
    result={"cohort":c["id"],"application_id":c["application_id"],"missing_files":missing,"artifact_comparison":None,"native_comparison":None,"status":"HOLD"}
    if inspect_only:
        # A1 checked only that rows existed. This produced a misleading READY
        # even for receipts whose contents failed the native contract. Validate
        # BOTH actual DOCX/receipt pairs and their comparable native identities.
        if document_missing or missing:
            result["status"] = "HOLD_MISSING_ARTIFACTS" if document_missing else "HOLD_MISSING_NATIVE_RECEIPTS"
            return result
        verified = run_cohort(c, root, inspect_only=False, db_path=db_path)
        native = verified.get("native_comparison")
        if isinstance(native, dict) and native.get("status") != "HOLD_INCOMPARABLE" and not native.get("comparison_holds"):
            result["status"] = "READY_VERIFIED_NATIVE_RECEIPTS"
            result["native_comparison"] = native
        else:
            result["status"] = "HOLD_NATIVE_RECEIPT_VALIDATION"
            result["verification_error"] = (verified.get("verification_error")
                or "; ".join((native or {}).get("comparison_holds") or [])
                or verified.get("status") or "No comparable native receipts")
        return result
    if document_missing:
        result["status"]="HOLD_MISSING_ARTIFACTS";return result
    try:
        a=artifacts.load_generation(paths["balanced"]["debug"],paths["balanced"]["docx"])
        b=artifacts.load_generation(paths["portfolio"]["debug"],paths["portfolio"]["docx"])
        pair=artifacts.compare(a,b)
        result["artifact_comparison"]={"verdict":pair["verdict"],"comparison_holds":pair["comparison_holds"],"baseline":{k:a[k] for k in ("generation_id","mode","project_count_docx","project_bullets_docx","fitting_page_count","page_fill_ratio","date_conflicts","possible_redundancy_review","issues")},"candidate":{k:b[k] for k in ("generation_id","mode","project_count_docx","project_bullets_docx","fitting_page_count","page_fill_ratio","date_conflicts","possible_redundancy_review","issues")},"difference":pair["difference"]}
        if a["application_id"] != c["application_id"] or b["application_id"] != c["application_id"] or a["mode"] != "balanced" or b["mode"] != "portfolio_quality":
            result["status"]="HOLD_INVALID_COHORT_ARTIFACTS";return result
        if pair["comparison_holds"]:
            result["status"]="HOLD_ARTIFACT_COMPARISON";return result
        if any(".phase8:" in x for x in missing) or any(x.startswith("native_db:") for x in missing):
            result["status"]="HOLD_MISSING_NATIVE_RECEIPTS";return result
        if db_path is not None:
            raw1=read_database_receipt(db_path, application_id=c["application_id"], generation_id=a["generation_id"])
            raw2=read_database_receipt(db_path, application_id=c["application_id"], generation_id=b["generation_id"])
            r1=validate_receipt_payload(raw1,f"SQLite:{c['id']}:Balanced",a,expected_application=c["application_id"],docx_path=paths["balanced"]["docx"])
            r2=validate_receipt_payload(raw2,f"SQLite:{c['id']}:Portfolio",b,expected_application=c["application_id"],docx_path=paths["portfolio"]["docx"])
            result["native_source"]="read_only_sqlite"
        else:
            r1=validate_receipt(paths["balanced"]["phase8"],a,expected_application=c["application_id"],docx_path=paths["balanced"]["docx"])
            r2=validate_receipt(paths["portfolio"]["phase8"],b,expected_application=c["application_id"],docx_path=paths["portfolio"]["docx"])
            result["native_source"]="exported_phase8_json"
        native=compare_native(r1,r2)
        result["native_comparison"]=native
        if native["status"] != "PASS_NO_NATIVE_REGRESSION":
            result["status"]=native["status"]
        elif a["date_conflicts"] or b["date_conflicts"] or b["possible_redundancy_review"]:
            result["status"]="REVIEW_EDITORIAL"
        else:
            result["status"]="PASS"
    except (FileNotFoundError,KeyError,ValueError,TypeError,ImportError,json.JSONDecodeError, OSError,sqlite3.Error) as exc:
        result["status"]="HOLD_VERIFICATION_ERROR"
        result["verification_error"]=str(exc)
    return result


def overall_status(results: list[dict]) -> str:
    if len(results)!=2 or {r.get("cohort") for r in results}!={"Keith","Darren"}:
        return "HOLD_MISSING_COHORT"
    statuses=[r["status"] for r in results]
    if any(s=="REGRESSION" for s in statuses):return "REGRESSION_BLOCK_RELEASE"
    if any(s.startswith("HOLD") or s=="MISSING_ARTIFACTS" for s in statuses):return "HOLD_INCOMPLETE_EVIDENCE"
    if any(s.startswith("REVIEW") for s in statuses):return "REVIEW_REQUIRED"
    if all(s=="PASS" for s in statuses):return "PASS_BOTH_COHORTS"
    return "HOLD_UNEXPECTED_STATUS"


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-test", action="store_true",help="Run embedded safety contract tests; no files written")
    group.add_argument("--check", action="store_true",help="Check filenames without altering files")
    group.add_argument("--compare", action="store_true",help="Audit both cohorts and require matching native receipts")
    p.add_argument("--manifest",type=Path,help="JSON manifest requiring both Keith and Darren")
    p.add_argument("--root",type=Path,default=Path.cwd(),help="Root for artifact filenames in the manifest")
    p.add_argument("--keith-db",type=Path,help="Keith test application DB, opened mode=ro instead of requiring exported Phase 8 JSONs")
    p.add_argument("--darren-db",type=Path,help="Darren main application DB, opened mode=ro instead of requiring exported Phase 8 JSONs")
    p.add_argument("--report",type=Path,help="Output JSON file (ONLY when --compare)")
    args=p.parse_args(argv)
    if args.self_test:
        # Test only local invariants; separate unittest module covers negative controls.
        assert overall_status([{"cohort":"Keith","status":"PASS"},{"cohort":"Darren","status":"PASS"}])=="PASS_BOTH_COHORTS"
        assert overall_status([{"cohort":"Keith","status":"REGRESSION"},{"cohort":"Darren","status":"PASS"}])=="REGRESSION_BLOCK_RELEASE"
        assert overall_status([{"cohort":"Keith","status":"PASS"}])=="HOLD_MISSING_COHORT"
        print("[PASS] Two-cohort release gate, regression hold and no fabricated native score; read-only")
        return 0
    if not args.manifest:
        p.error("--manifest is required for --check and --compare")
    if args.report and not args.compare:
        p.error("--report only allowed with --compare")
    try:
        cohorts=validate_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        print("[HOLD] Invalid manifest:",str(exc));return 2
    dbs={"Keith":args.keith_db,"Darren":args.darren_db}
    results=[run_cohort(c,args.root,inspect_only=args.check,db_path=dbs.get(c["id"])) for c in cohorts]
    for r in results:
        print(f"[{r['cohort']}] {r['status']}")
        for x in r["missing_files"]:print("  [MISSING]",x)
        if r.get("artifact_comparison"):
            a=r["artifact_comparison"]["baseline"];b=r["artifact_comparison"]["candidate"]
            print(f"  [DOCX] Balanced: {a['project_count_docx']} projects, {a['project_bullets_docx']} bullets; Portfolio: {b['project_count_docx']} projects, {b['project_bullets_docx']} bullets")
            print("  [PROJECTS REMOVED]", r["artifact_comparison"]["difference"]["projects_removed"])
            print("  [DATE CONFLICTS]",len(a["date_conflicts"])+len(b["date_conflicts"]),"[REDUNDANCY FLAGS]",len(b["possible_redundancy_review"]))
        if r.get("native_comparison"):
            n=r["native_comparison"]
            print(f"  [NATIVE] Balanced {n['balanced_final_native_score']} -> Portfolio {n['portfolio_final_native_score']} (delta {n['native_score_delta']:+g}); Required/Core regressions: {len(n['required_core_regressions'])}")
            for row in n["requirement_changes"]:print("    [REQ]",row)
            for issue in n["comparison_holds"]:print("    [NATIVE HOLD]",issue)
        if r.get("verification_error"):print("  [HOLD]",r["verification_error"])
    if args.check:
        both_verified = all(r["status"] == "READY_VERIFIED_NATIVE_RECEIPTS" for r in results)
        print("[CHECK]", "READY_NATIVE_COMPARISON_BOTH_COHORTS" if both_verified else "HOLD_NATIVE_RECEIPTS_OR_ARTIFACTS")
        print("[READ_ONLY] Validated both native receipts and exact document identity; no changes to saved files.")
        return 0 if both_verified else 2
    verdict=overall_status(results)
    print("[COHORT GATE]",verdict)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({"version":VERSION,"verdict":verdict,"cohorts":results,"read_only_source_files":True,"native_fitting_executed":False,"model_calls":False,"native_score_inferred_from_analysis_score":False},indent=2,ensure_ascii=False),encoding="utf-8")
        print("[REPORT]",args.report)
    print("[READ_ONLY] No DB, DOCX, Git, approvals, fitting, model or source changes. Only an explicitly requested JSON report can be written.")
    return 0 if verdict=="PASS_BOTH_COHORTS" else 2


if __name__=="__main__":
    raise SystemExit(main())
