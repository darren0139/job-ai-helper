"""Bounded offline benchmark execution; no production database or document writes."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/bullet_choice_benchmark'
FROZEN_SHA256='f102c21822553ef401f55ca0cf9454a9ef92c691ab2b56202f057a10053975b8'
PUBLIC_SHA256='c560aeb3e05e8ac057d51d0619f32a3e92c63b6ec7b1935c03a39d690f796ade'
VALIDATION_SHA256='af88be7daeb68a56b6668028cd0fcc5d9aa7aeb6a877256d980630feb78f42d6'
MAX_CASES=116
MAX_SECONDS=65
SELECTOR_CASES=('required_gain','complementary','preferred_gain','duplicate_provenance','word_budget','required_preservation','invalid_links')


def load_dataset():
    raw=(DATA/'v1_public.json').read_bytes()
    if len(raw)>3_000_000 or sha256(raw).hexdigest()!=PUBLIC_SHA256:
        raise ValueError('Frozen dataset identity/size mismatch.')
    packet=json.loads(raw)
    private_path=DATA/'v1.json'
    private_available=private_path.is_file()
    if private_available:
        private_raw=private_path.read_bytes()
        if len(private_raw)>3_000_000 or sha256(private_raw).hexdigest()!=FROZEN_SHA256:
            raise ValueError('Optional private fixture integrity mismatch; no fallback.')
        private=json.loads(private_raw)
        if [c for c in private['cases'] if c['dataset']!='real']!=packet['cases']:
            raise ValueError('Public/private controlled expectations differ.')
        packet['cases'].extend(c for c in private['cases'] if c['dataset']=='real')
    packet['optional_data']={'real':{'status':'available' if private_available else 'unavailable',
        'expected_cases':20,'reason':'' if private_available else 'Optional private v1.json is not installed; real cases were not evaluated.'}}
    packet['dataset_sha256']=FROZEN_SHA256 if private_available else PUBLIC_SHA256
    validation=(DATA/'validation_v1.json').read_bytes()
    if sha256(validation).hexdigest()!=VALIDATION_SHA256:raise ValueError('Fresh validation identity mismatch.')
    packet['cases'].extend(json.loads(validation)['cases'])
    packet['validation_sha256']=VALIDATION_SHA256
    packet['split_policy']+=' Original held_out outcomes were inspected during fixes and are exposed controls. Only fresh_validation was frozen after fixes without subsequent tuning.'
    cases=packet['cases']
    if len(cases)>MAX_CASES or len({c['id'] for c in cases})!=len(cases):
        raise ValueError('Duplicate case IDs or case bound exceeded.')
    for c in cases:
        if (sha256(c['jd_text'].encode()).hexdigest()!=c['jd_sha256']
                or (c['dataset']!='real' and c['expected'] not in {'Base stronger','Library stronger','Equivalent','Complementary','Indeterminate'})
                or (c['dataset']=='real' and c['expected'] is not None)):
            raise ValueError('Invalid JD identity/expectation boundary.')
    return packet


def requirements_for(case):
    if case['dataset']!='real':return case['requirements'], 'Frozen requirement identities/classifications'
    # Wording estimation may parse raw JD through current deterministic parser;
    # these records are NOT upgrades to saved native evidence or historical links.
    from analysis_stability.stable_evidence_scoring import canonicalise_requirements
    reqs=canonicalise_requirements({},case['jd_text'])['requirements']
    return [{**q,'id':q['requirement_id']} for q in reqs], 'Current deterministic raw-JD parser for estimates only; saved native records remain separate'


def selector_case(name):
    """Exercise production generator's explicit evaluator seam with frozen-style input links.

    This tests the actual selection model, not semantic linking/native evaluation.
    No test-only optimization objective replaces the production implementation.
    """
    from tailoring.phase9f_certified_selection_v36 import build_certified_optimization
    core='Implemented Python API services.'
    lib='Implemented Python API services and PostgreSQL transaction validation.'
    reqs=[{'requirement_id':'r_core','importance':'core','coverage_points':9,'match_label':'direct','requirement_text':'Implement Python API services'},
          {'requirement_id':'r_second','importance':'core','coverage_points':9,'match_label':'direct','requirement_text':'PostgreSQL transaction validation'},
          {'requirement_id':'r_bonus','importance':'preferred','coverage_points':2,'match_label':'direct','requirement_text':'Build React dashboards'}]
    links={core:['r_core'],lib:['r_core','r_second']}
    if name=='complementary':lib='Implemented PostgreSQL transaction validation.';links={core:['r_core'],lib:['r_second']}
    if name=='preferred_gain':lib='Implemented Python API services and built React dashboards.';links={core:['r_core'],lib:['r_core','r_bonus']}
    if name=='duplicate_provenance':lib=core;links={core:['r_core']}
    if name=='word_budget':lib='Implemented PostgreSQL transaction validation '+('with reliable audited transaction handling '*15)+'.';links={core:['r_core'],lib:['r_core','r_second']}
    if name=='required_preservation':lib='Built React dashboards.';links={core:['r_core'],lib:['r_bonus']}
    if name=='invalid_links':links[lib]=['unknown_identity']
    audit={'verified':True,'generation_id':'controlled-selector','projects':[{'project':'Controlled API','base':[{'text':core}], 'library':[{'text':lib}], 'final':[{'text':core}]}]}
    projects={'candidate_project_ranking':[{'title':'Controlled API','requirement_matches':reqs}]}
    def evidence(*,bullets,ranking_row):
        return [{'bullet_index':i,'bullet_text':text,'supported_requirement_ids':links[text]} for i,text in enumerate(bullets)]
    result=build_certified_optimization(audit,projects,evaluator=evidence,max_trials=1)
    chosen=[text for p in result.get('projects',[]) for text in p.get('after',[])]
    if result.get('status')=='no_proxy_gain':chosen=[core]
    coverage={rid for text in chosen for rid in links.get(text,[])}
    if name=='invalid_links':passed=result.get('status')=='withheld'
    elif name in ('required_gain','complementary'):passed={'r_core','r_second'}<=coverage
    elif name=='preferred_gain':passed={'r_core','r_bonus'}<=coverage
    elif name=='word_budget':passed=core in chosen and lib not in chosen
    else:passed='r_core' in coverage and len(chosen)==len(set(chosen))
    return {'case_id':name,'pass':passed,'status':result.get('status'),'membership':chosen,
        'input_audit':audit,'input_requirements':reqs,'input_links':links,'trace':result,
        'expectation':'Retain Core and gain specified eligible coverage, respect word bound, deduplicate exact wording or reject unknown IDs according to case contract.',
        'scope':'Actual build_certified_optimization; controlled admitted saved-link seam. No native score or document fit measured.'}


def compare_runs(before,after):
    if before.get('dataset_sha256')!=after.get('dataset_sha256') or before.get('eligibility_version')!=after.get('eligibility_version'):
        return {'status':'incompatible','reason':'Dataset/eligibility identities differ; no aggregate improvement claimed.'}
    if (before.get('validation_sha256') and after.get('validation_sha256')
            and before['validation_sha256']!=after['validation_sha256']):
        return {'status':'incompatible','reason':'Fresh validation versions differ.'}
    old={r['case_id']:r for r in before['rows']};new={r['case_id']:r for r in after['rows']};common=old.keys() & new.keys()
    return {'status':'compatible','common_cases':len(common),
        'scope_note':'Only identical original case IDs compared; added fresh-validation cases are reported separately and not counted as improvements.',
        'added_cases':sorted(new.keys()-old.keys()),'removed_cases':sorted(old.keys()-new.keys()),
        'improvements':[k for k in sorted(common) if old[k]['pass'] is False and new[k]['pass'] is True],
        'regressions':[k for k in sorted(common) if old[k]['pass'] is True and new[k]['pass'] is False],
        'eligibility_changed':[k for k in sorted(common) if (old[k]['pass'] is None)!=(new[k]['pass'] is None)],
        'outcome_changes':[k for k in sorted(common) if old[k]['estimated']['outcome']!=new[k]['estimated']['outcome']]}


def run_benchmarks(*, datasets=('synthetic','corpus','real'), case_ids=(), split=None, limit=MAX_CASES, selectors=True, seconds=MAX_SECONDS):
    from tailoring.bullet_choice_estimated import estimate_pair, VERSION
    if (type(limit) is not int or not 1<=limit<=MAX_CASES or not 0<seconds<=MAX_SECONDS
            or not set(datasets)<={'synthetic','corpus','real'}):raise ValueError('Invalid execution bounds/dataset.')
    packet=load_dataset();selected=[c for c in packet['cases'] if c['dataset'] in datasets and (not case_ids or c['id'] in case_ids) and (not split or c['split']==split)][:limit]
    start=time.monotonic();rows=[]
    for c in selected:
        if time.monotonic()-start>=seconds:break
        req,origin=requirements_for(c)
        estimated=estimate_pair(c['base'],c['library'],req)
        expected=c['expected'];passed=None if expected is None else estimated['outcome']==expected
        actual_coverage={r['id'] for r in estimated['requirements'] if any(r[k]['supported_facets'] for k in ('base','library'))}
        missing=set(c['expected_coverage'])-actual_coverage if expected else set()
        if expected and missing:passed=False
        verified=None
        if c['dataset']=='real':
            from tailoring.phase9f_bullet_relevance_diagnostic import compare_ranked_bullets
            original=c['source_case']
            verified=compare_ranked_bullets(original['base'],original['library'],{q['id']:q for q in c['requirements']})
        rows.append({'case_id':c['id'],'dataset':c['dataset'],'split':c['split'],'expected':expected,'pass':passed,
            'failure_type':None if passed is not False else 'Estimated-relevance evaluator / controlled coverage',
            'missing_expected_coverage':sorted(missing),'estimated':estimated,'requirement_origin':origin,
            'verified':verified,'saved_verified':c.get('source_case',{}).get('diagnostic'),
            'saved_membership':c.get('source_case',{}).get('membership'),
            'native_impact':'unmeasured for this pair'})
    selection=[]
    if selectors:
        for name in SELECTOR_CASES:
            remaining=seconds-(time.monotonic()-start)
            if remaining<2:selection.append({'case_id':name,'pass':None,'status':'withheld_runtime_bound'});continue
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','LITELLM_LOCAL_MODEL_COST_MAP':'True','DOTENV_DONT_LOAD':'1'}
            try:
                proc=subprocess.run([sys.executable,'-B','-m','tailoring.bullet_choice_lab','--selector-case',name],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=min(8,remaining))
                if proc.returncode:raise ValueError(proc.stderr[-1000:])
                selection.append(json.loads(proc.stdout))
            except (subprocess.TimeoutExpired,ValueError) as exc:
                selection.append({'case_id':name,'pass':None,'status':'unavailable','reason':str(exc)})
    controlled=[r for r in rows if r['expected'] is not None];decisive=[r for r in controlled if r['estimated']['outcome']!='Indeterminate']
    unsupported=sum(any(value['supported_facets'] and value['action_status']!='performed_claim' for q in r['estimated']['requirements'] for value in (q['base'],q['library'])) for r in rows)
    core_fail=sum(bool(set(r['missing_expected_coverage']) & {q['id'] for q in next(c for c in selected if c['id']==r['case_id'])['requirements'] if q['importance'] in {'required','core','deal_breaker'}}) for r in controlled)
    return {'schema_version':1,'dataset_version':packet['dataset_version'],'dataset_sha256':packet['dataset_sha256'],'optional_data':packet['optional_data'],
        'execution_status':'unavailable' if not selected else 'complete' if len(rows)==len(selected) else 'partial',
        'validation_sha256':VALIDATION_SHA256,'evaluator_version':VERSION,'eligibility_version':'lab-control-v1',
        'available':Counter(c['dataset'] for c in packet['cases']), 'requested':len(selected),'executed':len(rows),'rows':rows,'selector_results':selection,
        'summary':{'controlled_denominator':len(controlled),'correct':sum(r['pass'] is True for r in controlled),'incorrect':sum(r['pass'] is False for r in controlled),
            'withheld':sum(r['estimated']['outcome']=='Indeterminate' for r in rows),'decisive_denominator':len(decisive),'decisive_correct':sum(r['pass'] is True for r in decisive),
            'real_unlabelled':sum(r['dataset']=='real' for r in rows),'independently_reviewed_real':0,'real_accuracy':None,
            'unsupported_capability_assertion_cases':unsupported,'required_core_expected_coverage_failures':core_fail,
            'negative_control_failures':sum(r['pass'] is False for r in controlled if any(t in next(c for c in selected if c['id']==r['case_id'])['rationale'].lower() for t in ('keyword','terminology','negat','plan'))),
            'verified_replay_cases':sum(r['verified'] is not None for r in rows),'verified_correctness':None,
            'selector_pass':sum(x['pass'] is True for x in selection),'selector_fail':sum(x['pass'] is False for x in selection),'selector_unavailable':sum(x['pass'] is None for x in selection)},
        'elapsed_seconds':round(time.monotonic()-start,3),'limits':{'max_cases':limit,'max_seconds':seconds,'selector_timeout_seconds':8},
        'native':'No new native experiment. Saved App156 whole-document receipt is separate from all pair-level metrics.',
        'source_hashes':{n:sha256((ROOT/n).read_bytes()).hexdigest() for n in ['tailoring/bullet_choice_estimated.py','tailoring/bullet_choice_lab.py','tailoring/phase9f_certified_selection_v36.py']}}


def save_run(result):
    folder=DATA/'runs';folder.mkdir(exist_ok=True)
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path=folder/(name+'.json');path.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');return path


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--selector-case':
        if sys.argv[2] not in SELECTOR_CASES:raise ValueError('Unknown selector case')
        print(json.dumps(selector_case(sys.argv[2]),ensure_ascii=True))
    else:print(save_run(run_benchmarks()))
