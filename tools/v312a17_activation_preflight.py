#!/usr/bin/env python3
"""A1.8 default-on rollout preflight for the validated A1.7 scorer policy.

Runs A1.4's original saved-score replay under an explicitly selected legacy
policy and a second fresh default-on process. Both people and BOTH modes must
match; no application database, document, Phase 8 receipt or approval writes.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from copy import deepcopy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import v312a1_native_two_cohort as a1

POLICY_ENV = 'JOB_AI_HELPER_V312A17_NATIVE_FULLSTACK_POLICY'
POLICY_TOKEN = 'v312a17_fullstack_single_row'
TARGET_ID = 'req_43a0f0d2aaf8'
VERSION = 'v312a18-default-on-rollout-preflight-v1'


def _args(p: argparse.Namespace) -> list[str]:
    return ['--manifest', str(p.manifest), '--root', str(p.root),
            '--keith-db', str(p.keith_db), '--darren-db', str(p.darren_db)]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def active_probe(p: argparse.Namespace) -> dict:
    from analysis_stability import stable_evidence_scoring as scoring
    from tailoring import phase8_verification as phase8
    import v312a14_native_counterfactual as replay
    if not scoring._V312A17_RUNTIME_ACTIVE or not scoring.SCORING_VERSION.endswith('-v312a17-fullstack-single-row'):
        return {'status': 'HOLD_POLICY_NOT_ACTIVE', 'reason': 'Exact startup setting is missing'}
    if scoring.SCORING_VERSION != phase8.SCORING_VERSION:
        return {'status': 'HOLD_PHASE8_SCORER_IDENTITY_MISMATCH'}
    cohorts = a1.validate_manifest(_read(p.manifest))
    result = {'status': 'HOLD_REPLAY_NOT_VERIFIED', 'scoring_version': scoring.SCORING_VERSION,
              'phase8_scoring_version': phase8.SCORING_VERSION, 'cohorts': []}
    for c in cohorts:
        db = p.keith_db if c['id'] == 'Keith' else p.darren_db
        entry = {'cohort': c['id'], 'modes': {}}
        try:
            old = a1.run_cohort(c, p.root, db_path=db)
            if old.get('native_comparison') is None or old.get('native_comparison',{}).get('comparison_holds'):
                raise ValueError('Saved native verification receipt cannot be validated')
            for mode in ('balanced','portfolio'):
                spec = c[mode]
                doc = a1._resolve(p.root, spec['docx'])
                debug_path = a1._resolve(p.root, spec['debug'])
                debug = _read(debug_path)
                artifact = a1.artifacts.load_generation(debug_path, doc)
                raw = a1.read_database_receipt(db,application_id=c['application_id'],generation_id=artifact['generation_id'])
                a1.validate_receipt_payload(raw,mode,artifact,expected_application=c['application_id'],docx_path=doc)
                text,profile,frozen = replay._doc_and_profile(debug,doc,parsed_projects=artifact['projects'])
                # No experimental scope. This is the actual activated runtime path.
                live = replay._native_document_analysis(document_text=text,profile=profile,frozen=frozen,candidate=False)
                saved = raw['after_stable_analysis']
                # Reuse the already tested A1.4 no-regression comparator without
                # changing the runtime row's distinct production audit identity.
                test_view = deepcopy(live)
                for native_row in test_view.get('canonical_requirements',[]):
                    if native_row.get('v312a17_policy_audit'):
                        native_row['v312a14_candidate_audit'] = deepcopy(native_row['v312a17_policy_audit'])
                diff = replay.compare_replay(saved,test_view,saved)
                audit = live.get('native_fullstack_policy_v312a17')
                if not isinstance(audit,dict) or audit.get('policy_version') != scoring._V312A17_POLICY_VERSION:
                    raise ValueError('Activated native policy receipt is missing')
                if not str(live.get('scoring_version') or '').startswith(scoring.SCORING_VERSION):
                    raise ValueError('Activated stable-analysis scoring identity is stale')
                changes = diff.get('changed_requirements', [])
                if c['id']=='Keith' and mode=='portfolio':
                    if len(changes)!=1 or changes[0].get('requirement_id')!=TARGET_ID or changes[0].get('from')!='transferable' or changes[0].get('to')!='direct' or len(audit.get('audit',[]))!=1:
                        raise ValueError('Keith promotion is not exactly the approved single preferred requirement')
                    if not any(row.get('v312a17_policy_audit') for row in live['canonical_requirements']):
                        raise ValueError('Missing production-policy evidence audit')
                elif changes or audit.get('selection_count')!=0:
                    raise ValueError('Unexpected native requirement change for '+c['id']+' '+mode)
                if diff.get('status')!='CANDIDATE_NATIVE_REPLAY_NO_REGRESSION':
                    raise ValueError('Native regression, mismatched requirements, or baseline hold: '+str(diff.get('status')))
                entry['modes'][mode]={'status':'ACTIVE_POLICY_NATIVE_PARITY_VERIFIED',
                   'previous_score':diff['control_native_score'], 'active_score':diff['candidate_native_score_EXPERIMENTAL'],
                   'required_core_before':diff['required_core_score_before'], 'required_core_after':diff['required_core_score_after'],
                   'changed_requirements':[{k:v for k,v in x.items() if k!='experimental_audit'} for x in changes],
                   'policy_selected_rows':audit['selection_count'],
                   'document_sha_verified':True}
        except Exception as exc:
            entry['status']='HOLD_ACTIVE_PROBE_ERROR'
            entry['error']=f'{type(exc).__name__}: {exc}'
        else:
            entry['status']='ACTIVE_POLICY_BOTH_MODES_VERIFIED'
        result['cohorts'].append(entry)
    if len(result['cohorts'])==2 and all(c['status']=='ACTIVE_POLICY_BOTH_MODES_VERIFIED' for c in result['cohorts']):
        result['status']='ACTIVE_REPLAY_PASS_BOTH'
    return result


def verify(p: argparse.Namespace) -> dict:
    # Force independent Python startup for both settings. This also prevents an
    # already imported Streamlit/scoring module from making the check ambiguous.
    with tempfile.TemporaryDirectory(prefix='v312a17_verify_') as tmp:
        off=Path(tmp)/'off.json'
        on=Path(tmp)/'on.json'
        env_off=os.environ.copy()
        env_off[POLICY_ENV]='legacy'
        proc_off=subprocess.run([sys.executable,str(TOOLS/'v312a14_native_counterfactual.py'),'--replay',*_args(p),'--report',str(off)],
            cwd=ROOT,env=env_off,text=True,capture_output=True)
        if proc_off.returncode or not off.is_file():
            return {'status':'HOLD_LEGACY_REPLAY','exit_code':proc_off.returncode,
                    'output_tail':(proc_off.stdout+'\n'+proc_off.stderr)[-1800:]}
        baseline=_read(off)
        if baseline.get('status')!='CANDIDATE_REPLAY_PASS_BOTH':
            return {'status':'HOLD_LEGACY_REPLAY','baseline_status':baseline.get('status')}
        env_on=env_off.copy()
        env_on.pop(POLICY_ENV,None)
        proc_on=subprocess.run([sys.executable,str(__file__),'--probe-active',*_args(p),'--report',str(on)],
            cwd=ROOT,env=env_on,text=True,capture_output=True)
        if proc_on.returncode or not on.is_file():
            return {'status':'HOLD_DEFAULT_ON_REPLAY','exit_code':proc_on.returncode,
                    'output_tail':(proc_on.stdout+'\n'+proc_on.stderr)[-1800:]}
        active=_read(on)
        if active.get('status')!='ACTIVE_REPLAY_PASS_BOTH':
            return {'status':'HOLD_DEFAULT_ON_REPLAY','active_probe':active}
        target={c['cohort']:c for c in baseline.get('cohorts',[])}
        for cohort in active['cohorts']:
            other=target.get(cohort['cohort'])
            if not other:
                return {'status':'HOLD_COHORT_MISSING_FROM_DEFAULT_REPLAY'}
            for mode, row in cohort['modes'].items():
                expect=other['modes'][mode]
                if (row['active_score'] != expect['candidate_native_score_EXPERIMENTAL'] or
                    row['previous_score'] != expect['control_native_score'] or
                    row['required_core_after'] != expect['required_core_score_after']):
                    return {'status':'HOLD_RUNTIME_DIFFERS_FROM_VERIFIED_EXPERIMENT',
                            'cohort':cohort['cohort'],'mode':mode}
        return {'version':VERSION,'status':'A18_DEFAULT_POLICY_VERIFIED_BOTH',
                'legacy_replay_status':baseline['status'],
                'default_on_scoring_version':active['scoring_version'],
                'cohorts':active['cohorts'],
                'saved_phase8_receipts_unchanged':True,
                'runtime_active_by_default':True, 'legacy_rollback_setting':'legacy',
                'no_app_db_docx_approval_or_git_writes':True}


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--verify',action='store_true')
    group.add_argument('--probe-active',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--keith-db',required=True,type=Path)
    parser.add_argument('--darren-db',required=True,type=Path)
    parser.add_argument('--report',type=Path)
    p=parser.parse_args()
    output=active_probe(p) if p.probe_active else verify(p)
    if p.report:
        p.report.parent.mkdir(parents=True,exist_ok=True)
        p.report.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding='utf-8')
        print('[REPORT]',p.report)
    print('[A1.8]',output.get('status'))
    for c in output.get('cohorts',[]):
        print(' ',c.get('cohort'),c.get('status'), 'balanced=',c.get('modes',{}).get('balanced',{}).get('active_score'),
              'portfolio=',c.get('modes',{}).get('portfolio',{}).get('active_score'))
    print('[READ_ONLY] No database, DOCX, approvals, fitted output, existing receipts or Git writes')
    return 0 if output['status'] in ('ACTIVE_REPLAY_PASS_BOTH','A18_DEFAULT_POLICY_VERIFIED_BOTH') else 2

if __name__=='__main__':
    raise SystemExit(main())
