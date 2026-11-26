#!/usr/bin/env python3
"""Read-only, artifact-based comparison of two existing Phase 9F fitted generations.

This deliberately does NOT generate new candidates or rerun the native scorer.
It reports score evidence as unavailable unless separately verified elsewhere.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

STOP = set("the and are for that this with from into through across under using via over your our their within which when where have has had does did who what which between while should more less they you your them its itself not can without after before then".split())
CONCEPTS = {
    "automated_testing": re.compile(r"\b(?:test(?:s|ing|ed)?|automated checks|verification checks)\b", re.I),
    "build_ci": re.compile(r"\b(?:github actions|ci/cd|builds?|build automation|pipeline)\b", re.I),
    "security_scanning": re.compile(r"\b(?:trivy|vulnerab\w*|security scans?)\b", re.I),
    "frontend_backend": re.compile(r"\bfrontend\b.*\bbackend\b|\bbackend\b.*\bfrontend\b", re.I),
    "deployment": re.compile(r"\b(?:deploy(?:ment|ed)?|kubernetes|docker)\b", re.I),
    "observability": re.compile(r"\b(?:prometheus|grafana|monitoring|metrics)\b", re.I),
    "authorization": re.compile(r"\b(?:jwt|rbac|role-based access|authorization)\b", re.I),
}


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    return " ".join(str(text or "").split())


def is_bullet(paragraph) -> bool:
    style = (paragraph.style.name or "").lower()
    if "bullet" in style:
        return True
    ppr = paragraph._p.pPr
    if ppr is not None and ppr.numPr is not None:
        return True
    return bool(re.match(r"^[•●▪◦‣]\s*", paragraph.text.strip()))


def extract_docx(path: Path, expected_titles: set[str] | None = None) -> dict:
    from docx import Document
    doc = Document(str(path))
    in_projects = False
    current = None
    projects = {}
    unclassified = []
    saw_projects = False
    saw_skills = False
    for p in doc.paragraphs:
        text = normalize(p.text)
        if text.upper() == "PROJECTS":
            in_projects = True
            saw_projects = True
            continue
        if in_projects and text.upper() == "SKILLS":
            saw_skills = True
            break
        if not in_projects or not text:
            continue
        style = (p.style.name or "").lower()
        candidate_title = normalize(p.text.split("\t", 1)[0])
        if ("entry" in style and "subentry" not in style) or ("\t" in p.text and expected_titles is not None and candidate_title in expected_titles):
            chunks = p.text.split("\t")
            current = normalize(chunks[0])
            if current in projects:
                raise ValueError(f"Repeated DOCX project heading: {current}")
            projects[current] = {"date": normalize(chunks[-1]) if len(chunks)>1 else "", "bullets": []}
            continue
        if is_bullet(p):
            if not current:
                unclassified.append(text)
            else:
                projects[current]["bullets"].append(re.sub(r"^[•●▪◦‣]\s*", "", text))
    if not saw_projects or not saw_skills or not projects or unclassified:
        raise ValueError("DOCX project section is ambiguous, incomplete, or has unclassified bullets")
    if not any(v["bullets"] for v in projects.values()):
        raise ValueError("No DOCX bullet paragraphs were recognized; refusing to treat zero as evidence")
    return projects


def expected_from_reductions(fitting: dict) -> dict:
    snap = fitting.get("fitting_input_snapshot", {})
    prepared = snap.get("prepared_initial_state", {}).get("projects", {}).get("recommended_projects", [])
    if not prepared:
        raise ValueError("No fitting-input snapshot; cannot verify reduction accounting")
    counts = {normalize(p.get("display_title") or p.get("title")): len(p.get("draft_bullets", [])) for p in prepared}
    for event in fitting.get("remaining_active_reductions", []):
        if event.get("section") != "projects":
            continue
        typ = event.get("change_type")
        if typ not in {"remove_bullet", "bullet_fusion", "shorten_bullet", "shorten_project_bullet", "compact_bullet", "shorten"}:
            raise ValueError(f"Unknown project-fitting event: {typ!r}")
        if typ in {"remove_bullet", "bullet_fusion"}:
            name = normalize(event.get("project"))
            if name not in counts:
                raise ValueError(f"Reduction event references unknown project: {name!r}")
            counts[name] -= 1
    if any(n<0 for n in counts.values()):
        raise ValueError("Reduction events imply negative bullet counts")
    return counts


def normalize_date(text: str) -> str:
    return re.sub(r"\s+", " ", normalize(text).replace("–", "-").replace("—", "-")).casefold()

def source_date_conflicts(profile: dict, projects: dict) -> list:
    rows = profile.get("projects", []) if isinstance(profile, dict) else []
    out=[]
    for r in rows:
        name=normalize(r.get("title", ""))
        if not name:
            continue
        for final_name, final in projects.items():
            if final_name == name or final_name.startswith(name + " —") or name.startswith(final_name + " ("):
                source_date=normalize(r.get("date", ""))
                dest_date=final.get("date", "")
                if source_date and dest_date and normalize_date(source_date) != normalize_date(dest_date):
                    out.append({"project":final_name,"base_resume_date":source_date,"docx_date":dest_date,"kind":"date_conflict_needs_provenance_review"})
    return out


def concepts(text: str) -> set:
    return {name for name,pat in CONCEPTS.items() if pat.search(text)}


def redundancy_review(projects:dict) -> list:
    out=[]
    for name, value in projects.items():
        for (i,a),(j,b) in itertools.combinations(enumerate(value["bullets"],1),2):
            common=sorted(concepts(a) & concepts(b))
            if len(common) >= 2:
                out.append({"project": name, "bullet_indices": [i,j], "shared_concepts":common,
                            "status":"review_only_not_a_dedupe_decision"})
    return out


def load_generation(debug_path:Path, docx_path:Path) ->dict:
    raw=json.loads(debug_path.read_text(encoding="utf-8"))
    meta=raw.get("debug_meta", {})
    analysis=raw.get("analysis_report", {})
    fit=raw.get("one_page_fitting_result", {})
    tp=raw.get("tailored_projects_result", {})
    selection=tp.get("adaptive_fit_selection", {})
    selected=raw.get("final_projects_used_in_docx", [])
    saved={normalize(p.get("display_title") or p.get("title")): [normalize(x) for x in p.get("draft_bullets",[])] for p in selected}
    final=extract_docx(docx_path, expected_titles=set(saved))
    expected=expected_from_reductions(fit)
    issues=[]
    if not fit.get("fit_one_page") or fit.get("page_count") != 1 or fit.get("fit_status") != "verified_one_page":
        issues.append("Saved fit is not verified one page")
    if set(final) != set(expected) or set(final) != set(saved):
        issues.append("Saved/DOCX project identities disagree")
    for title, info in final.items():
        actual=info["bullets"]
        if len(actual) != expected.get(title):
            issues.append(f"Reduction accounting mismatch for {title}: expected={expected.get(title)} actual={len(actual)}")
        if actual != saved.get(title):
            issues.append(f"Fitted DOCX wording disagrees with saved final bullets for {title}")
    v39=tp.get("_v39_auto_dedupe", {})
    v310=tp.get("_v310_lead_intro", {})
    portfolio=tp.get("portfolio_quality_selection", {})
    source=snap=fit.get("fitting_input_snapshot", {}).get("source_artifact", {})
    return {
       "application_id":meta.get("application_id"),
       "generation_id":fit.get("generation_id"),
       "input_fingerprint":fit.get("fitting_input_fingerprint"),
       "source_resume_sha256":source.get("sha256"),
       "jd_sha256":sha_text(analysis.get("raw_jd_text", "")),
       "base_resume_text_sha256":sha_text(analysis.get("raw_resume_text", "")),
       "debug_path":str(debug_path),"docx_path":str(docx_path),
       "mode":selection.get("mode", "unknown"),
       "original_generated_projects":selection.get("original_generated_count"),
       "selected_project_count":selection.get("selected_count"),
       "project_count_docx":len(final),
       "project_bullets_docx":sum(len(x["bullets"]) for x in final.values()),
       "project_bullet_counts":{name:len(info["bullets"]) for name,info in final.items()},
       "projects":final,
       "fitter_initial_bullet_count":sum(len(p.get("draft_bullets",[])) for p in snap.get("prepared_initial_state",{}).get("projects",{}).get("recommended_projects",[])),
       "active_reduction_events":len(fit.get("remaining_active_reductions",[])),
       "fitting_page_count":fit.get("page_count"),
       "page_fill_ratio":fit.get("page_fill_ratio"),
       "analysis_score_not_phase8":analysis.get("overall_score"),
       "v39_removed":len(v39.get("removals",[])),
       "v310_removed":len(v310.get("removals",[])),
       "portfolio_proxy_utility_not_native":portfolio.get("provisional_utility"),
       "portfolio_candidate_count":portfolio.get("candidate_count"),
       "date_conflicts":source_date_conflicts(analysis.get("resume_profile",{}),final),
       "possible_redundancy_review":redundancy_review(final),
       "issues":issues,
    }


def compare(a:dict, b:dict) ->dict:
    holds=[]
    for field in ("application_id", "jd_sha256", "base_resume_text_sha256", "source_resume_sha256"):
        if not a.get(field) or not b.get(field) or a[field]!=b[field]:
            holds.append(f"Different or missing frozen comparison identity: {field}")
    if a["issues"] or b["issues"]:
        holds.append("At least one fitted DOCX readback/reduction verification failed")
    return {
        "tool_version":"phase9f-fitted-artifact-comparator-v1-read-only",
        "verdict":"HOLD" if holds else "ARTIFACT_COMPARABLE_NATIVE_SCORE_UNVERIFIED",
        "comparison_holds":holds,
        "baseline":a,
        "candidate":b,
        "difference":{
          "projects_added":sorted(set(b['projects'])-set(a['projects'])),
          "projects_removed":sorted(set(a['projects'])-set(b['projects'])),
          "project_count_delta":b['project_count_docx']-a['project_count_docx'],
          "final_project_bullets_delta":b['project_bullets_docx']-a['project_bullets_docx'],
          "page_fill_delta":round((b['page_fill_ratio'] or 0)-(a['page_fill_ratio'] or 0),4),
          "new_bullets_by_project":{k:[v for v in dat['bullets'] if v not in a['projects'].get(k,{}).get('bullets',[])] for k,dat in b['projects'].items() if any(v not in a['projects'].get(k,{}).get('bullets',[]) for v in dat['bullets'])},
        },
        "native_phase8_comparison":{"status":"NOT_VERIFIED_FROM_THESE_DEBUG_BUNDLES",
                                    "reason":"The bundles carry an analysis score, not a pair of independently verifiable, same-baseline native Phase 8 comparison receipts"},
        "no_database_writes":True,
        "no_native_fitting_executed":True,
        "no_model_calls":True,
    }


def self_test():
    assert sha_text('same')==sha_text('same')
    class Style:
        name='Resume Bullet'
    class Numbering:
        numPr=object()
    class P:
        style=Style();_p=type('X',(),{'pPr':Numbering()})();text='A bullet'
    assert is_bullet(P())
    assert concepts('GitHub Actions builds and frontend tests') >= {'build_ci','automated_testing'}
    sample={'RequestFlow':{'bullets':['Automated tests and GitHub Actions builds','Performed GitHub Actions builds and tests']}}
    assert len(redundancy_review(sample))==1
    assert not redundancy_review({'X':{'bullets':['Created a React UI','Developed a database schema']}})
    print('[PASS] Read-only contract, Word bullet styles, shared-concept review, no speculative native score')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-debug',type=Path)
    parser.add_argument('--baseline-docx',type=Path)
    parser.add_argument('--candidate-debug',type=Path)
    parser.add_argument('--candidate-docx',type=Path)
    parser.add_argument('--report',type=Path)
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if args.self_test:
        self_test();return 0
    required=[args.baseline_debug,args.baseline_docx,args.candidate_debug,args.candidate_docx]
    if any(x is None for x in required):
        parser.error('Four input files required: --baseline-debug, --baseline-docx, --candidate-debug, --candidate-docx')
    try:
        a=load_generation(args.baseline_debug,args.baseline_docx)
        b=load_generation(args.candidate_debug,args.candidate_docx)
        report=compare(a,b)
    except (ValueError,KeyError,FileNotFoundError,ImportError,json.JSONDecodeError) as exc:
        print('[HOLD] '+str(exc));return 2
    print('[VERDICT]',report['verdict'])
    for label,z in [('BASELINE',a),('CANDIDATE',b)]:
        print(f'[{label}] generation={z["generation_id"]} mode={z["mode"]} projects={z["project_count_docx"]} bullets={z["project_bullets_docx"]} pages={z["fitting_page_count"]} fill={z["page_fill_ratio"]} analysis_score_NOT_Phase8={z["analysis_score_not_phase8"]}')
        for name,n in z['project_bullet_counts'].items():print(f'  {name}: {n}')
        for issue in z['issues']:print('  [AUDIT HOLD]',issue)
        for conflict in z['date_conflicts']:print('  [DATE REVIEW]',conflict['project'],repr(conflict['base_resume_date']),'->',repr(conflict['docx_date']))
        for overlap in z['possible_redundancy_review']:print('  [REDUNDANCY REVIEW]',overlap['project'],overlap['bullet_indices'],','.join(overlap['shared_concepts']))
    d=report['difference']
    print('[DIFF] project_count=',d['project_count_delta'],'bullet_count=',d['final_project_bullets_delta'],'removed=',d['projects_removed'],'added=',d['projects_added'])
    print('[NATIVE PHASE 8] NOT_VERIFIED_FROM_THESE_DEBUG_BUNDLES')
    if report['comparison_holds']:
        for msg in report['comparison_holds']:print('[HOLD]',msg)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
        print('[REPORT]',args.report)
    print('[READ_ONLY] No repository, application DB, DOCX or source-file modifications. No LLM or native fitter calls.')
    return 2 if report['comparison_holds'] else 0

if __name__=='__main__':
    sys.exit(main())
