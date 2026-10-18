"""Stage 2D deterministic offline policy comparison; never computes a Job Match score."""
import argparse
from collections import Counter,defaultdict
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from scripts import preview_coordinated_ownership_v1 as stage2c
from taxonomy_discovery import partial_action_credit_preview as policy
from taxonomy_discovery.offline_execution import offline_execution

n=stage2c.n
ROOT=stage2c.ROOT
FIXTURE=ROOT/'tests/fixtures/coordinated_partial_action_policy_v1.json'
POLICIES=('P1','P2','P3','P4')


def load_expectations():return json.loads(FIXTURE.read_text(encoding='utf-8'))


def evidence_index(texts):return n.build_resume_evidence_index(stage2c.profile_for(texts),'')


def filtered_native(requirement,texts,allowed,admissions,native_reference,*,missing_only=False):
    """One native ranker, a compatibility filter, and downward-only source caps.

    Complete candidate pool is evaluated first. Partial pools never change the
    reference native NONE into positive credit. No numeric aggregation is called.
    """
    ns=stage2c.clone_namespace();profile=stage2c.profile_for(texts);trusted=evidence_index(texts)
    original=ns['_evidence_source_is_requirement_compatible'];phase='keyword_selection';events=[]
    def compatible(req,record):
        valid=original(req,record)
        ok=valid and record.get('evidence_id') in allowed and any(record==r for r in trusted)
        events.append({'stage':phase,'source':record.get('source'),'evidence_id':record.get('evidence_id'),
                       'native_source_compatible':valid,'admitted':ok})
        return ok
    ns['_evidence_source_is_requirement_compatible']=compatible
    trace=[]
    def capture(name,rows):
        nonlocal phase
        phase=name
        for row in rows:
            selected=row.get('evidence') or [];raw=row['match_label'];label=raw
            rec=selected[0] if len(selected)==1 else {}
            identity=rec.get('evidence_id');admission=admissions.get(identity,'REVIEW_REQUIRED')
            exact=next((r for r in trusted if all(r.get(k)==rec.get(k) for k in ('source','text','evidence_id','section'))),None)
            if raw!='none' and (identity not in allowed or exact is None):label='none'
            elif admission=='ELIGIBLE_PARTIAL':
                label=policy.cap_label(raw,admission)
                if native_reference=='none':label='none'
            trace.append({'stage':name,'native_stage_label':raw,'proposed_capped_label':label,
                'admission':admission,'evidence':deepcopy(selected),
                'recovery':deepcopy(row.get('capability_none_recovery')),
                'reselection':deepcopy(row.get('capability_evidence_reselection')),
                'decision_receipt':{'source':rec.get('source'),'evidence_id':identity,
                    'native_reference_final_label':native_reference,'policy_version':policy.PARTIAL_VERSION}})
            row.update(match_label=label,match_value=n.MATCH_VALUES[label])
        return rows
    reqs=[deepcopy(requirement)];acronym={}
    kw=({'present':[],'missing':[{'keyword':requirement['atomic_focus']}]} if missing_only else
        ns['build_deterministic_keyword_match'](requirements=reqs,acronym_map=acronym,resume_profile=profile,raw_resume_text=''))
    phase='link_selection'
    rows,_=ns['link_requirement_matches'](reqs,kw,acronym,resume_profile=profile,raw_resume_text='');rows=capture('linked',rows)
    rows,_=ns['apply_structured_requirement_matches'](rows,resume_profile=profile,raw_resume_text='');rows=capture('structured',rows)
    rows,_=ns['validate_linked_matches'](rows);rows=capture('validated_lexical_cap',rows)
    phase='single_row_reselection'
    rows,_=ns['_apply_capability_single_row_reselection'](rows,evidence_index=trusted,acronym_map=acronym);rows=capture('reselected',rows)
    rows=ns['apply_taxonomy_caps_to_requirements'](rows,retrieval_mode_override='off');rows=capture('capability_capped',rows)
    phase='none_recovery'
    rows,_=ns['_apply_capability_none_recovery'](rows,evidence_index=trusted,acronym_map=acronym);rows=capture('recovered',rows)
    rows=capture('post_recovery_invariant',rows)
    return {'label':rows[0]['match_label'],'evidence':deepcopy(rows[0].get('evidence') or []),
            'deterministic_keyword_match':kw,
            'stages':trace,'compatibility_events':events,'native_selector_retained':True}


def compare(requirement,texts,*,missing_only=False,source_mode='verified'):
    obligation=policy.prior.extract_obligation(requirement)
    trusted=evidence_index(texts)
    proofs={}
    for row in trusted:
        if '.bullets[' not in row['source']:continue
        claim=deepcopy(row)
        if source_mode=='forged_id':claim['evidence_id']='ev_FORGED'
        elif source_mode=='missing_source':claim['source']=''
        proof=policy.detect(obligation,claim,trusted)
        proofs[row['evidence_id']]={'record':claim,'proof':proof}
    unchecked=stage2c.pipeline(requirement,texts,missing_only=missing_only,source_mode=source_mode)
    before=unchecked['provisional_final_label']
    old_filtered=stage2c.pipeline(requirement,texts,filtered=True,missing_only=missing_only,source_mode=source_mode)
    historical={'native_label':before,'text_filtered':old_filtered,
        'effective_preview_label':(old_filtered['provisional_final_label'] if old_filtered['admissible_evidence_ids']
                                  else ('none' if before=='none' else None))}
    variants={};cache={}
    for name in POLICIES:
        admissions={key:policy.eligibility(obligation,item['proof'],name) for key,item in proofs.items()}
        complete={key for key,value in admissions.items() if value=='COMPLETE'}
        eligible=complete or {key for key,value in admissions.items() if value=='ELIGIBLE_PARTIAL'}
        # Complete priority changes admissibility, not native score sorting/ceilings.
        key=tuple(sorted(eligible))
        if not eligible:
            variants[name]={'label':'none' if before=='none' else None,'disposition':'REVIEW_REQUIRED',
                'admissions':admissions,'selected_evidence':[],'pipeline':None,'parent_contribution':0.0 if before=='none' else None}
            continue
        if key not in cache:
            cache[key]=filtered_native(requirement,texts,eligible,admissions,before,missing_only=missing_only)
        run=deepcopy(cache[key]);label=run['label'];selected=run['evidence']
        selected_id=selected[0].get('evidence_id') if len(selected)==1 else None
        admission=admissions.get(selected_id)
        variants[name]={'label':label,'disposition':admission or 'NATIVE_NONE_NO_SELECTED_RECORD',
            'admissions':admissions,'selected_evidence':selected,'pipeline':run,
            'parent_contribution':n.MATCH_VALUES[label]*requirement['group_weight_fraction']}
    return {'native_unchecked':unchecked,'stage2c_result':historical,
        'obligation':obligation,'proofs':proofs,'policies':variants,
        'parent_allocation':requirement['group_weight_fraction'],
        'canonical_requirement_id_unchanged':requirement['requirement_id'],
        'no_job_match_score_computed':True}


def judge(records,obligation,texts,expected,which):
    required={a['action'] for a in obligation['actions']};index=evidence_index(texts);out=[]
    for i,truth in enumerate(expected):
        row=next(r for r in index if r['source']==f'resume_profile.projects[0].bullets[{i}]')
        result=(policy.detect(obligation,row,index) if which=='2d' else policy.prior.detect_ownership(obligation,row,index))
        gold={policy.prior.action_kind(a) or a for a in truth};actual=set(result['supported_actions'])
        action_outcomes={a:('TP' if a in actual else 'FN') if a in gold else ('FP' if a in actual else 'TN') for a in sorted(required)}
        complete_gold=required<=gold;complete=result['complete']
        full=('TP' if complete else 'FN') if complete_gold else ('FP' if complete else 'TN')
        out.append({'evidence_index':i,'expected_actions':sorted(gold),'computed':result,
                    'action_outcomes':action_outcomes,'full_obligation_outcome':full})
    return out


@lru_cache(maxsize=1)
def study():
    parents=stage2c.stage2b.independent_parent_rows();fixture=load_expectations()
    all_parents=[];stats=defaultdict(Counter);fullstats=defaultdict(Counter);disagreements=Counter()
    with offline_execution('Stage 2D is offline only'):
        for parent in parents:
            req=deepcopy(parent['variants']['A_full'][0]);req.pop('recognition',None)
            o=policy.prior.extract_obligation(req)
            existing=[{'id':c['id'],'evidence':c['evidence'],'expected':c['declared_actions_by_evidence'],
                       'origin':'INDEPENDENT_STAGE2B_ORACLE'} for c in parent['scenarios']]
            adversarial=[{**c,'origin':'REVIEWED_STAGE2C_ADVERSARIAL'} for c in stage2c.adversarial_cases(o)]
            new=[{'id':c['id'],'evidence':[c['text']],'expected':[c['owned']],
                  'origin':fixture['schema_version']} for c in fixture['cases']
                 if c.get('family','embedded')==o['object_family']]
            cases=[]
            for case in existing+adversarial+new:
                measurements={which:judge(None,o,case['evidence'],case['expected'],which) for which in ('2c','2d')}
                for which,measured in measurements.items():
                    for record in measured:
                        fullstats[which].update([record['full_obligation_outcome']])
                        for action,outcome in record['action_outcomes'].items():
                            for group in (which,which+':'+case['origin'],which+':job:'+str(parent['job_id']),which+':action:'+action,
                                          which+':category:'+case['id']):stats[group].update([outcome])
                result=compare(req,case['evidence'])
                for name in POLICIES:
                    if result['policies'][name]['label']!=result['policies']['P3']['label']:disagreements[name]+=1
                baseline_native=stage2c.stage2b.native_path(parent['variants']['baseline'],case['evidence'],{})
                cases.append({**case,'measurements':measurements,'comparison':result,
                    'original_split_native':baseline_native,
                    'original_split_parent_contribution':sum(n.MATCH_VALUES[r['native_label']]*s['group_weight_fraction']
                        for r,s in zip(baseline_native,parent['variants']['baseline']))})
            for mode in ('missing_source','forged_id'):
                cases.append({'id':mode,'evidence':[stage2c.adversarial_cases(o)[0]['evidence'][0]],
                              'comparison':compare(req,stage2c.adversarial_cases(o)[0]['evidence'],source_mode=mode)})
            for cid,text in [('missing_keywords_partial','Designed and developed '+o['object']+'.'),
                             ('missing_keywords_topic','Configured ESP32 GPIO interrupts.')]:
                cases.append({'id':cid,'evidence':[text],'comparison':compare(req,[text],missing_only=True)})
            past={'design':'designed','develop':'developed','maintain':'maintained','deploy':'deployed'}
            complete=o['object']+' were '+', '.join(past[a['action']] for a in o['actions'])+' by me.'
            overlap=['Maintained '+o['object']+'. Learned to design and develop '+o['object']+'.',complete]
            cases.append({'id':'higher_overlap_partial_before_passive_complete','evidence':overlap,
                          'expected_complete_source_index':1,'comparison':compare(req,overlap)})
            all_parents.append({'job_id':parent['job_id'],'parent_occurrence_id':parent['parent_occurrence_id'],
                'original_raw_jd':parent['original_raw_parent'],'recognition':stage2c.stage2b.stage2.recognition(req),
                'baseline_rows':parent['variants']['baseline'],'option_a_row':req,
                'allocation_before':parent['allocation']['baseline'],'allocation_after':parent['allocation']['A_full'],
                'cases':cases})
        scope_controls=[]
        for case in fixture['scope_controls']:
            req=stage2c.stage2b.stage2.canonical('Responsibilities:\n'+case['requirement'],proposed=True)['requirements'][0]
            o=policy.prior.extract_obligation(req);index=evidence_index([case['evidence']])
            row=next(r for r in index if '.bullets[' in r['source'])
            proof=policy.detect(o,row,index)
            scope_controls.append({**case,'obligation':o,'proof':proof,
                'computed_policies':[policy.eligibility(o,proof,name) for name in POLICIES]})
        controls=[]
        for cid,req,evidence in stage2c.stage2b.control_cases():
            can=stage2c.stage2b.stage2.canonical('Responsibilities:\n'+req,proposed=True)
            controls.append({'id':cid,'requirement':req,'synthetic_evidence':evidence,
                'native':stage2c.stage2b.native_path(can['requirements'],evidence,can['acronym_map'],missing_only=True),
                'forced_api_only':([stage2c.stage2b.evaluate_capability_evidence('backend.api_development',{'text':req},text)
                    for text in evidence] if cid.startswith(('api_','protocol_')) else []),
                'no_new_policy_override':True})
    return {'research_policy_version':policy.PARTIAL_VERSION,'language_version':policy.LANGUAGE_VERSION,
        'current_versions':stage2c.stage2b.stage2.inventory.knowledge_identity(),
        'expectation_fixture_sha256':stage2c.stage2b.stage2.inventory.file_sha(FIXTURE),
        'parents':all_parents,'independent_controls':controls,'independent_scope_controls':scope_controls,
        'action_confusion':{key:{x:c[x] for x in ('TP','TN','FP','FN')} for key,c in sorted(stats.items())},
        'full_confusion':{key:{x:c[x] for x in ('TP','TN','FP','FN')} for key,c in fullstats.items()},
        'proposed_label_disagreements_with_P3':dict(disagreements),
        'native_match_values_unchanged':dict(n.MATCH_VALUES),'job_match_scores_computed':False}


def write_preview(output,protected_baseline=None):
    out=Path(output).resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):raise ValueError('Use a new local reports/ path')
    result=deepcopy(study())
    if protected_baseline is not None:
        before=json.loads(Path(protected_baseline).read_text(encoding='utf-8-sig'))['files']
        after={path:stage2c.stage2b.stage2.inventory.file_sha(ROOT/path) for path in before}
        changed=[path for path in before if before[path]!=after[path]]
        if any(path!='scripts/run_coordinated_preview_checks.py' for path in changed):
            raise ValueError('Unexpected protected change: '+str(changed))
        result.update(protected_sha256_before=before,protected_sha256_after=after,
                      intentional_test_only_changes=changed)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/bulk_unresolved_stage2d_preview.json')
    args=parser.parse_args();result=write_preview(args.output)
    print(json.dumps({'actions':result['action_confusion']['2d'],'full':result['full_confusion']['2d']}))


if __name__=='__main__':main()
