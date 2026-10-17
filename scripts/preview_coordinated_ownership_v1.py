"""Stage 2C isolated detector + native selection integration preview. No release edits."""
import argparse
from collections import Counter,defaultdict
from copy import deepcopy
import json
from pathlib import Path
import types

from scripts import preview_coordinated_evidence_v1 as stage2b
from taxonomy_discovery.coordinated_ownership_preview import (
    POLICY,extract_obligation,detect_ownership,action_kind,ground_to_raw_jd,
)
from taxonomy_discovery.offline_execution import offline_execution

n=stage2b.n
ROOT=stage2b.ROOT


def clone_namespace():
    ns=dict(n.__dict__)
    for key,value in n.__dict__.items():
        if isinstance(value,types.FunctionType) and value.__globals__ is n.__dict__:
            copy=types.FunctionType(value.__code__,ns,key,value.__defaults__,value.__closure__)
            copy.__kwdefaults__=value.__kwdefaults__
            ns[key]=copy
    return ns


def profile_for(evidence):
    return {'projects':[{'title':'Stage 2C hypothetical project','bullets':evidence}],
            'experience':[],'education':[],'skills':{}}


def pipeline(requirement,evidence,*,filtered=False,missing_only=False,source_mode='verified',
             _bypass_recovery_for_test=False):
    """Use native ranking/selectors with one additional compatibility predicate.

    Provisional NONE is quarantine plumbing ONLY, never an approved effective label.
    Neither overall alignment nor persistence is called.
    """
    ns=clone_namespace(); profile=profile_for(evidence)
    trusted=n.build_resume_evidence_index(profile,'')
    injected=deepcopy(trusted)
    if source_mode!='verified':
        for row in injected:
            if '.bullets[' in row['source']:
                if source_mode=='missing_source':row['source']=''
                elif source_mode=='forged_id':row['evidence_id']='ev_NOT_CURRENT'
                elif source_mode=='tampered_text':row['text']='I designed, developed and maintained invented content.'
                else:raise ValueError(source_mode)
    ns['build_resume_evidence_index']=lambda *args,**kwargs:deepcopy(injected)
    obligation=extract_obligation(requirement)
    applicable=obligation['status']=='SUPPORTED'
    events=[]; phase='start'
    original_compatible=ns['_evidence_source_is_requirement_compatible']
    def compatible(req,record):
        allowed=original_compatible(req,record)
        if not allowed or not filtered or not applicable:return allowed
        if _bypass_recovery_for_test and phase=='none_recovery':return allowed
        decision=detect_ownership(obligation,record,trusted)
        events.append({'stage':phase,'evidence_id':record.get('evidence_id'),
                       'source':record.get('source'),'detector_status':decision['status'],
                       'allowed':decision['complete']})
        return decision['complete']
    ns['_evidence_source_is_requirement_compatible']=compatible
    stages=[]
    def capture(name,rows,quarantine=True):
        nonlocal phase
        phase=name
        for row in rows:
            selected=row.get('evidence') or []
            detection=(detect_ownership(obligation,selected[0],trusted) if len(selected)==1 else
                       {'status':'MISSING_SINGLE_SOURCE','complete':False,'supported_actions':[],
                        'missing_actions':[a['action'] for a in obligation['actions']]})
            original_label=row['match_label']
            quarantined=bool(quarantine and filtered and applicable and original_label!='none' and not detection['complete'])
            stages.append({'stage':name,'native_stage_label':original_label,
                'selected_evidence':deepcopy(selected),'detector':detection,
                'quarantined_pending_policy_review':quarantined,
                'provisional_label':'none' if quarantined else original_label,
                'recovery':deepcopy(row.get('capability_none_recovery')),
                'reselection':deepcopy(row.get('capability_evidence_reselection'))})
            if quarantined:
                row.update(match_label='none',match_value=n.MATCH_VALUES['none'],evidence=[])
        return rows
    reqs=[deepcopy(requirement)]; acronym={}
    phase='keyword_selection'
    kw=({'present':[],'missing':[{'keyword':requirement['atomic_focus']}]}
        if missing_only else ns['build_deterministic_keyword_match'](
            requirements=reqs,acronym_map=acronym,resume_profile=profile,raw_resume_text=''))
    phase='link_selection'
    rows,_=ns['link_requirement_matches'](reqs,kw,acronym,resume_profile=profile,raw_resume_text='')
    rows=capture('linked',rows)
    phase='structured_selection'
    rows,_=ns['apply_structured_requirement_matches'](rows,resume_profile=profile,raw_resume_text='')
    rows=capture('structured',rows)
    rows,_=ns['validate_linked_matches'](rows); rows=capture('validated_lexical_cap',rows)
    phase='single_source_reselection'
    rows,_=ns['_apply_capability_single_row_reselection'](rows,evidence_index=injected,acronym_map=acronym)
    rows=capture('reselected',rows)
    rows=ns['apply_taxonomy_caps_to_requirements'](rows,retrieval_mode_override='off')
    rows=capture('taxonomy_capped',rows)
    phase='none_recovery'
    rows,_=ns['_apply_capability_none_recovery'](rows,evidence_index=injected,acronym_map=acronym)
    rows=capture('recovered',rows,quarantine=False)
    rows=capture('final_invariant',rows)
    admissible=[r for r in injected if original_compatible(requirement,r)
                and detect_ownership(obligation,r,trusted)['complete']] if applicable else []
    return {'filtered':filtered,'source_mode':source_mode,'missing_keyword_input':missing_only,
        'obligation':obligation,'stages':stages,'compatibility_events':events,
        'provisional_final_label':rows[0]['match_label'],
        'admissible_evidence_ids':[r['evidence_id'] for r in admissible],
        'final_evidence':deepcopy(rows[0].get('evidence') or []),
        'all_native_ranking_and_source_constraints_retained':True}


def comparison(requirement,evidence,*,source_mode='verified',missing_only=False):
    unchecked=pipeline(requirement,evidence,source_mode=source_mode,missing_only=missing_only)
    checked=pipeline(requirement,evidence,filtered=True,source_mode=source_mode,missing_only=missing_only)
    original=unchecked['provisional_final_label']; proposed=checked['provisional_final_label']
    applicable=checked['obligation']['status']=='SUPPORTED'
    if not applicable:
        effective=None; disposition='REVIEW_REQUIRED_UNSUPPORTED_OBLIGATION'
    elif checked['admissible_evidence_ids']:
        effective=proposed; disposition='EXISTING_NATIVE_LABEL_ON_ADMISSIBLE_SOURCE'
    elif original!='none':
        effective=None; disposition='REVIEW_REQUIRED_NO_APPROVED_PARTIAL_RULE'
    else:
        effective='none'; disposition='EXISTING_NATIVE_NONE_RETAINED'
    return {'unchecked':unchecked,'text_filtered':checked,'effective_preview_label':effective,
            'policy_disposition':disposition,'no_job_match_score_computed':True}


def adversarial_cases(obligation):
    obj=obligation['object']; actions=[a['action'] for a in obligation['actions']]
    past={'design':'designed','develop':'developed','maintain':'maintained','deploy':'deployed'}
    whole=', '.join(past[a] for a in actions)+' '+obj+'.'
    allset=sorted(set(actions))
    return [
        {'id':'explicit_personal','evidence':['I '+whole],'expected':[allset]},
        {'id':'affirmative_clauses','evidence':['; '.join('I '+past[a]+' '+obj for a in actions)+'.'],'expected':[allset]},
        {'id':'present_personal','evidence':['I '+', '.join(actions)+' '+obj+'.'],'expected':[allset]},
        {'id':'ongoing_personal','evidence':['I am '+', '.join({'design':'designing','develop':'developing','maintain':'maintaining','deploy':'deploying'}[a] for a in actions)+' '+obj+'.'],'expected':[allset]},
        {'id':'team_only','evidence':['Our team '+whole],'expected':[[]]},
        {'id':'third_party','evidence':['The vendor '+whole],'expected':[[]]},
        {'id':'ambiguous_we','evidence':['We '+whole],'expected':[[]]},
        {'id':'future_intent','evidence':['I will '+', '.join(actions)+' '+obj+'.'],'expected':[[]]},
        {'id':'hypothetical','evidence':['If needed, I would '+', '.join(actions)+' '+obj+'.'],'expected':[[]]},
        {'id':'quoted_requirement','evidence':['The JD says: '+whole],'expected':[[]]},
        {'id':'question','evidence':['I '+whole.rstrip('.')+'?'],'expected':[[]]},
        {'id':'global_retraction','evidence':['I '+whole+' Correction: the vendor did this, not me.'],'expected':[[]]},
        {'id':'global_hypothetical','evidence':['I '+whole+' This is hypothetical.'],'expected':[[]]},
        {'id':'wrong_object_design','evidence':['I designed presentation slides; '+past['develop']+' '+obj+'; '+past[actions[2]]+' '+obj+'.'],'expected':[['develop',actions[2]]]},
        {'id':'contradiction','evidence':['I '+whole+' I did not design '+obj+'.'],'expected':[[a for a in allset if a!='design']]},
        {'id':'usage_only','evidence':['Used '+obj+'.'],'expected':[[]]},
        {'id':'collaboration_no_ownership','evidence':['I helped the vendor '+', '.join(actions)+' '+obj+'.'],'expected':[[]]},
        {'id':'shortened_object','evidence':['I '+', '.join(past[a] for a in actions)+' '+obj.split(' supporting ')[0].split(' using ')[0].split(' that ')[0].split(' with ')[0]+'.'],'expected':[allset]},
        {'id':'passive_attribution','evidence':[obj+' were '+', '.join(past[a] for a in actions)+' by me.'],'expected':[allset]},
        {'id':'owned_relative_clause','evidence':['Used '+obj+' which I '+', '.join(past[a] for a in actions)+'.'],'expected':[allset]},
        {'id':'complete_alternative_row','evidence':['Maintained '+obj+'.','I '+whole],'expected':[['maintain'] if 'maintain' in actions else [],allset]},
    ]


def oracle_comparison(obligation,evidence,expected):
    # Expected actions are consumed only here, AFTER text detection. They are
    # never passed into detector, compatibility hook or scoring functions.
    index=n.build_resume_evidence_index(profile_for(evidence),'')
    records=[]
    for i,truth in enumerate(expected):
        row=next(r for r in index if r['source']==f'resume_profile.projects[0].bullets[{i}]')
        computed=detect_ownership(obligation,row,index)
        actual=set(computed['supported_actions']); target=set(action_kind(a) or a for a in truth)
        comparisons=[]
        for required in sorted(set(a['action'] for a in obligation['actions'])):
            yes=required in actual; gold=required in target
            comparisons.append({'action':required,'expected':gold,'computed':yes,
                'outcome':('TP' if yes else 'FN') if gold else ('FP' if yes else 'TN')})
        records.append({'evidence_index':i,'computed':computed,'independent_expected_actions':sorted(target),
                        'comparisons':comparisons})
    return records


def study():
    oracle={'parents':stage2b.independent_parent_rows()}
    results=[]; breakdown=defaultdict(Counter); full_breakdown=defaultdict(Counter)
    raw_jobs=json.loads((ROOT/stage2b.stage2.inventory.FIXTURES[0]).read_text(encoding='utf-8'))['snapshot']['audit']['corpus']['jobs']
    replay=[]; raw_parents={}; original_documents={}
    with offline_execution('Stage 2C forbids all external execution'):
        for job in raw_jobs:
            raw=job['frozen_inputs']['raw_jd_text']
            original_documents[job['job_id']]=raw
            baseline=stage2b.stage2.canonical(raw)
            full=stage2b.stage2.canonical(raw,proposed=True)
            replay.append({'job_id':job['job_id'],'baseline':len(baseline['requirements']),
                           'A_full':len(full['requirements'])})
            for pid,rows in stage2b.stage2.parent_rows(full).items():
                raw_parents[(job['job_id'],pid)]=rows
        for parent in oracle['parents']:
            requirement=deepcopy(parent['variants']['A_full'][0]); requirement.pop('recognition',None)
            actual=raw_parents[(parent['job_id'],parent['parent_occurrence_id'])]
            if len(actual)!=1 or any(actual[0][0].get(k)!=requirement.get(k) for k in
                ('text','requirement_id','source_provenance','atomic_group_id','group_weight_fraction')):
                raise ValueError('Stage 2B parent differs from current original raw-JD replay')
            obligation=ground_to_raw_jd(extract_obligation(requirement),original_documents[parent['job_id']])
            if obligation['status']!='SUPPORTED':raise ValueError('A real five-parent source failed admission')
            original_cases=[{'id':s['id'],'evidence':s['evidence'],'expected':s['declared_actions_by_evidence'],
                             'oracle_origin':'UNCHANGED_STAGE2B_FIXTURE_ORACLE'} for s in parent['scenarios']]
            new_cases=[{**s,'oracle_origin':'INDEPENDENT_STAGE2C_SYNTHETIC_EXPECTATION'} for s in adversarial_cases(obligation)]
            cases=[]
            for case in original_cases+new_cases:
                measured=oracle_comparison(obligation,case['evidence'],case['expected'])
                for record in measured:
                    required={a['action'] for a in obligation['actions']}
                    gold=required<=set(record['independent_expected_actions'])
                    yes=record['computed']['complete']
                    result=('TP' if yes else 'FN') if gold else ('FP' if yes else 'TN')
                    for group in ('overall','job:'+str(parent['job_id']),'category:'+case['id'],
                                  'oracle:'+case['oracle_origin']):full_breakdown[group][result]+=1
                    for decision in record['comparisons']:
                        for group in ('overall','job:'+str(parent['job_id']),
                                      'parent:'+parent['parent_occurrence_id'],
                                      'action:'+decision['action'],'category:'+case['id'],
                                      'oracle:'+case['oracle_origin']):
                            breakdown[group][decision['outcome']]+=1
                cases.append({**case,'detector_vs_oracle':measured,
                    'integration':comparison(requirement,case['evidence'])})
            for mode in ('missing_source','forged_id','tampered_text'):
                evidence=new_cases[0]['evidence']
                cases.append({'id':mode,'evidence':evidence,'oracle_origin':'SOURCE_VERIFICATION_CONTROL',
                              'integration':comparison(requirement,evidence,source_mode=mode)})
            zero=next(s for s in original_cases if s['id']=='zero_overlap_topic')
            cases.append({'id':'zero_overlap_missing_keyword_input','evidence':zero['evidence'],
                          'integration':comparison(requirement,zero['evidence'],missing_only=True)})
            results.append({'job_id':parent['job_id'],'parent_occurrence_id':parent['parent_occurrence_id'],
                'requirement':requirement,'obligation':obligation,
                'baseline_requirements':parent['variants']['baseline'],
                'parent_allocation_before':parent['allocation']['baseline'],
                'parent_allocation_after':parent['allocation']['A_full'], 'cases':cases})
        controls=[]
        for cid,text,evidence in stage2b.control_cases():
            canonical=stage2b.stage2.canonical('Responsibilities:\n'+text,proposed=True)
            controls.append({'id':cid,'requirement':text,'synthetic_evidence':evidence,
                'extractions':[extract_obligation(r) for r in canonical['requirements']],
                'native':stage2b.native_path(canonical['requirements'],evidence,canonical['acronym_map']),
                'native_missing_keywords':stage2b.native_path(canonical['requirements'],evidence,canonical['acronym_map'],missing_only=True),
                'forced_api_evaluator_only':([stage2b.evaluate_capability_evidence('backend.api_development',{'text':text},row)
                    for row in evidence] if cid.startswith(('api_','protocol_')) else []),
                'no_detector_override_of_existing_api_policy':True})
        extra_obligations=[]
        for cid,text,evidence in [
            ('optional_embedded','Design, develop and maintain embedded software modules, preferably using C++.',
             'I designed, developed and maintained embedded software modules.'),
            ('alternative_embedded','Design or develop embedded software modules.','I developed embedded software modules.'),
            ('negated','Do not design, develop and maintain embedded software modules.','I designed, developed and maintained embedded software modules.'),
            ('mixed_and_or','Design, develop or maintain embedded software modules.','I maintained embedded software modules.'),
            ('ambiguous_object_or','Design, develop and maintain embedded software modules or cloud applications.','I designed, developed and maintained embedded software modules.'),
        ]:
            # Keep original full raw parent for extraction, even when native baseline
            # would split it. This control does not change production canonicalization.
            source={'text':text,'atomic_focus':text,'requirement_id':'synthetic:'+cid,
                'source_provenance':[{'raw_parent_text':text,'parent_text':text,
                    'parent_occurrence_id':'synthetic:'+cid,'source':'synthetic_control',
                    'source_group_fraction':1.0,'grounding':{'kind':'SYNTHETIC_CONTROL','sentence_text':text}}]}
            obligation=extract_obligation(source)
            index=n.build_resume_evidence_index(profile_for([evidence]),'')
            record=next(r for r in index if '.bullets[' in r['source'])
            extra_obligations.append({'id':cid,'obligation':obligation,
                                      'detection':detect_ownership(obligation,record,index),
                'integration':(comparison(stage2b.stage2.canonical('Responsibilities:\n'+text,proposed=True)['requirements'][0],[evidence])
                               if cid in ('optional_embedded','alternative_embedded') else None)})
    return {'policy':POLICY,'scope':'OFFLINE_SYNTHETIC_ONLY_NOT_PRODUCTION',
        'current_versions_unchanged':stage2b.stage2.inventory.knowledge_identity(),
        'oracle_fixture_sha256':stage2b.stage2.inventory.file_sha(stage2b.ORACLE_FIXTURE),
        'confusion':{key:{label:counts[label] for label in ('TP','TN','FP','FN')} for key,counts in sorted(breakdown.items())},
        'full_obligation_confusion':{key:{label:counts[label] for label in ('TP','TN','FP','FN')} for key,counts in sorted(full_breakdown.items())},
        'raw_jd_corpus_replay':replay,
        'parents':results,'independent_api_and_scope_controls':controls,
        'additional_obligation_controls':extra_obligations,
        'real_candidate_inputs_used':False,'job_match_scores_computed':False,
        'production_versions_changed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'bulk_unresolved_stage2c_preview.json')
    parser.add_argument('--protected-baseline',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or not args.output.resolve().is_relative_to(ROOT):raise ValueError('Use a new worktree output')
    result=study(); ledger=json.loads(args.protected_baseline.read_text(encoding='utf-8-sig'))
    result['protected_sha256_before']=ledger['files']
    result['protected_sha256_after']={p:stage2b.stage2.inventory.file_sha(ROOT/p) for p in ledger['files']}
    if result['protected_sha256_before']!=result['protected_sha256_after']:raise ValueError('Protected input changed')
    args.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'overall':result['confusion']['overall'],
                      'stage2b_oracle':result['confusion']['oracle:UNCHANGED_STAGE2B_FIXTURE_ORACLE'],
                      'protected':len(ledger['files'])}))


if __name__=='__main__':main()
