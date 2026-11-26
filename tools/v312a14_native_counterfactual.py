#!/usr/bin/env python3
"""V3.12-A1.4: scoped real native scorer replay; never saves a Phase 8 receipt.

Recomputes both cohorts from their exact saved DOCX files, using the app's
native deterministic document scorer. A candidate replay is never a verified
production improvement; baseline parity with saved Phase 8 is mandatory.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import v312a1_native_two_cohort as a1
from analysis_stability.stable_evidence_scoring import temporary_v312a14_candidate_scope

VERSION = 'v312a14-scoped-native-counterfactual-v1'
IMPORTANT = {'required','core','deal_breaker'}
RANK = {'none':0,'weak':1,'transferable':2,'direct':3}
SCORES = ('deterministic_alignment_score','required_core_coverage_score','preferred_coverage_score','evidence_strength_score')


def _rows(analysis: dict) -> dict:
    return a1._rows(analysis,'candidate replay')


def _doc_and_profile(debug: dict, document: Path, *, parsed_projects: dict):
    """Rebuild evidence-bearing project profile from literal verified Word bullets.

    Other sections come from the frozen saved analysis but are bounded against
    actual document text by the production document_grounded_analysis module.
    If that reconstruction differs from the saved native result, stop.
    """
    from parse import read_resume_docx
    text = read_resume_docx(str(document), preserve_complete_text=True)
    frozen = debug.get('analysis_report') or {}
    if not text or not frozen.get('raw_jd_text') or not isinstance(frozen.get('jd_profile'),dict):
        raise ValueError('Missing actual final document or frozen JD/profile inputs')
    profile = deepcopy(frozen.get('resume_profile') or {})
    profile['projects'] = [
        {'title': project, 'date': info.get('date',''), 'bullets': list(info['bullets'])}
        for project,info in parsed_projects.items()
    ]
    return text, profile, frozen


def _native_document_analysis(*, document_text: str, profile: dict, frozen: dict, candidate: bool) -> dict:
    from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
    from tailoring.jd_user_input_overrides import apply_application_session_jd_user_inputs
    from contextlib import nullcontext
    context = temporary_v312a14_candidate_scope() if candidate else nullcontext()
    with context:
        result = analyze_actual_resume_against_jd(
            resume_text=document_text,
            jd_text=frozen['raw_jd_text'],
            jd_profile=frozen['jd_profile'],
            resume_profile=profile,
        )
        preferred = (((frozen.get('meta') or {}).get('jd_user_inputs') or {})
                     .get('preferred_requirement_overrides') or [])
        result = apply_application_session_jd_user_inputs(
            result, raw_jd_text=frozen['raw_jd_text'],
            raw_resume_text=document_text, preferred_requirements=preferred,
        )
    return result['stable_analysis']


def compare_replay(control: dict, candidate: dict, saved: dict) -> dict:
    """Don't accept experimental score until baseline exactly replays saved rows."""
    old, new, expected = _rows(control), _rows(candidate), _rows(saved)
    missing = sorted(set(expected) ^ set(old))
    if missing:
        return {'status':'HOLD_REPLAY_REQUIREMENT_SCOPE','requirement_scope_difference':missing}
    mismatched = [rid for rid in sorted(expected) if any(
        old[rid].get(key) != expected[rid].get(key)
        for key in ('match_label','match_value','evidence_strength','importance','score_eligible'))]
    components_mismatched = [key for key in SCORES if control.get(key) != saved.get(key)]
    if mismatched or components_mismatched:
        return {'status':'HOLD_REPLAY_BASELINE_MISMATCH',
                'requirement_mismatches':mismatched,
                'component_mismatches':components_mismatched,
                'observed_replay_score':control.get('deterministic_alignment_score'),
                'saved_native_score':saved.get('deterministic_alignment_score')}
    if set(old) != set(new):
        return {'status':'HOLD_CANDIDATE_SCOPE_CHANGED'}
    losses=[]; upgrades=[]
    for rid in sorted(old):
        a,b=old[rid],new[rid]
        if any(a.get(key)!=b.get(key) for key in ('importance','score_eligible','capability_id')):
            return {'status':'HOLD_CANDIDATE_REQUIREMENT_IDENTITY_CHANGED', 'requirement_id':rid}
        if RANK.get(b.get('match_label'),-1)<RANK.get(a.get('match_label'),-1) or b.get('evidence_strength',0)<a.get('evidence_strength',0):
            losses.append(rid)
        if b.get('match_label')!=a.get('match_label') or b.get('evidence_strength')!=a.get('evidence_strength'):
            upgrades.append({'requirement_id':rid, 'importance':a.get('importance'),
                             'from':a.get('match_label'),'to':b.get('match_label'),
                             'old_strength':a.get('evidence_strength'),'new_strength':b.get('evidence_strength'),
                             'experimental_audit':b.get('v312a14_candidate_audit')})
    score_before=control['deterministic_alignment_score']
    score_after=candidate['deterministic_alignment_score']
    if losses or score_after<score_before or candidate['required_core_coverage_score']<control['required_core_coverage_score']:
        status='HOLD_CANDIDATE_REGRESSION'
    elif any(not (x['importance']=='preferred' and x['from']=='transferable' and x['to']=='direct' and x['experimental_audit']) for x in upgrades):
        status='HOLD_UNEXPECTED_NATIVE_CHANGE'
    else:
        status='CANDIDATE_NATIVE_REPLAY_NO_REGRESSION'
    return {'status':status,'saved_native_parity_verified':True,
            'control_native_score':score_before,'candidate_native_score_EXPERIMENTAL':score_after,
            'experimental_score_delta':score_after-score_before,
            'required_core_score_before':control['required_core_coverage_score'],
            'required_core_score_after':candidate['required_core_coverage_score'],
            'losses':losses,'changed_requirements':upgrades}


def evaluate(cohort: dict, root: Path, db: Path) -> dict:
    original = a1.run_cohort(cohort,root,db_path=db)
    if original.get('native_comparison') is None or original.get('native_comparison',{}).get('comparison_holds'):
        return {'cohort':cohort['id'],'status':'HOLD_NATIVE_RECEIPTS', 'original_status':original.get('status')}
    result={'cohort':cohort['id'], 'app_id':cohort['application_id'], 'saved_gate':original['status'],'modes':{}}
    for mode in ('balanced','portfolio'):
        paths=cohort[mode]
        doc_path=a1._resolve(root,paths['docx']); debug_path=a1._resolve(root,paths['debug'])
        debug=json.loads(debug_path.read_text(encoding='utf-8'))
        artifact=a1.artifacts.load_generation(debug_path,doc_path)
        raw=a1.read_database_receipt(db,application_id=cohort['application_id'],generation_id=artifact['generation_id'])
        validated=a1.validate_receipt_payload(raw,mode,artifact,expected_application=cohort['application_id'],docx_path=doc_path)
        document_text, profile, frozen=_doc_and_profile(debug,doc_path,parsed_projects=artifact['projects'])
        baseline=_native_document_analysis(document_text=document_text,profile=profile,frozen=frozen,candidate=False)
        candidate=_native_document_analysis(document_text=document_text,profile=profile,frozen=frozen,candidate=True)
        comparison=compare_replay(baseline,candidate,raw['after_stable_analysis'])
        result['modes'][mode]=comparison
    if any(x['status'].startswith('HOLD') for x in result['modes'].values()):
        result['status']='HOLD_REPLAY_NOT_PROMOTABLE'
    else:
        result['status']='CANDIDATE_BOTH_MODES_PARITY_CHECKED'
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--replay',action='store_true');p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--keith-db',type=Path,required=True)
    p.add_argument('--darren-db',type=Path,required=True);p.add_argument('--report',type=Path)
    args=p.parse_args()
    if not args.replay:
        p.error('--replay is required; this is an explicit candidate-only action')
    cohorts=a1.validate_manifest(json.loads(args.manifest.read_text(encoding='utf-8')))
    results=[]
    for c in cohorts:
        try:
            x=evaluate(c,args.root,args.keith_db if c['id']=='Keith' else args.darren_db)
        except Exception as exc:
            x={'cohort':c['id'],'status':'HOLD_REPLAY_ERROR','error':f'{type(exc).__name__}: {exc}'}
        results.append(x)
        print(f"[{c['id']}] {x['status']}")
        for mode,row in x.get('modes',{}).items():
            print(f"  [{mode.upper()}] {row['status']} control={row.get('control_native_score',row.get('observed_replay_score','unverified'))} experimental={row.get('candidate_native_score_EXPERIMENTAL','unverified')} changed={len(row.get('changed_requirements',[]))}")
    status = ('CANDIDATE_REPLAY_PASS_BOTH' if all(r['status']=='CANDIDATE_BOTH_MODES_PARITY_CHECKED' for r in results)
              and all(r['modes']['portfolio']['candidate_native_score_EXPERIMENTAL']>=r['modes']['balanced']['candidate_native_score_EXPERIMENTAL'] for r in results)
              else 'HOLD_CANDIDATE_NOT_VERIFIED')
    output={'version':VERSION,'status':status,'cohorts':results,'candidate_is_not_a_saved_phase8_receipt':True,
            'read_only_application_db_docx':True,'no_application_scoring_change_without_opt_in_scope':True,
            'no_fitting_or_model_calls':True}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding='utf-8')
        print('[REPORT]',args.report)
    print('[DUAL COHORT]',status)
    print('[NO_APP_WRITES] Experimental local scoring only. No DB, DOCX, fitter, Git, or approvals changed.')
    return 0 if status=='CANDIDATE_REPLAY_PASS_BOTH' else 2

if __name__=='__main__':
    raise SystemExit(main())
