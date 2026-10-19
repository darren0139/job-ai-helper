"""Stage 2B investigation only: native credit path and fixture-declared action receipts.

No production matcher is patched. Action receipts below are synthetic test metadata,
not an implemented ownership detector or an approved partial-credit policy.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import argparse
import json
from pathlib import Path
import re
import subprocess

from scripts import preview_coordinated_actions_v1 as stage2
from taxonomy_discovery.offline_execution import offline_execution
from tailoring.capability_taxonomy import evaluate_capability_evidence

n = stage2.native
ROOT = stage2.inventory.ROOT
VERSION = 'INVESTIGATION-ONLY-coordinated-evidence-v1'
ORACLE_FIXTURE = ROOT/'tests/fixtures/coordinated_action_ownership_oracle_v1.json'


def load_independent_oracle():
    """Reviewed input/expected actions, never outputs of the detector under test."""
    fixture=json.loads(ORACLE_FIXTURE.read_text(encoding='utf-8'))
    if fixture['source_fixture_sha256']!=stage2.inventory.file_sha(ROOT/fixture['source_fixture']):
        raise ValueError('The independently reviewed JD fixture changed')
    for path,expected in fixture['production_source_lf_sha256'].items():
        if hashlib.sha256((ROOT/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=expected:
            # Stage 2E intentionally adds default-OFF hooks to this one source.
            # Preserve the exact historical source pin, and keep the complete
            # frozen semantic digests (plus 30-job OFF equivalence tests) binding.
            if path != 'analysis_stability/stable_evidence_scoring.py':
                raise ValueError('Reviewed production source changed: '+path)
            historical=subprocess.check_output(['git','show',
                '3e6ff34501b4d68cbe3e66b55ec8af5b0e288026:'+path],cwd=ROOT)
            if hashlib.sha256(historical.replace(b'\r\n',b'\n')).hexdigest()!=expected:
                raise ValueError('Historical reviewed production source changed: '+path)
    return fixture


@lru_cache(maxsize=1)
def _replayed_independent_parents():
    fixture=load_independent_oracle()
    jobs=json.loads((ROOT/fixture['source_fixture']).read_text(encoding='utf-8'))['snapshot']['audit']['corpus']['jobs']
    wanted={p['job_id'] for p in fixture['parents']}
    representations={j['job_id']:(stage2.canonical(j['frozen_inputs']['raw_jd_text']),
        stage2.canonical(j['frozen_inputs']['raw_jd_text'],proposed=True)) for j in jobs if j['job_id'] in wanted}
    parents=[]
    for expected in fixture['parents']:
        baseline,full=representations[expected['job_id']]
        pid=expected['parent_occurrence_id']
        old=stage2.parent_rows(baseline)[pid];new=stage2.parent_rows(full)[pid]
        if len(new)!=1 or new[0][1]['raw_parent_text']!=expected['original_raw_parent']:
            raise ValueError('Independent parent source identity changed')
        decorate=lambda rows:[{**deepcopy(row),'recognition':stage2.recognition(row)} for row,_ in rows]
        parents.append({**deepcopy(expected),'variants':{'baseline':decorate(old),'A_full':decorate(new)},
            'allocation':{'baseline':sum(r['group_weight_fraction'] for r,_ in old),
                          'A_full':sum(r['group_weight_fraction'] for r,_ in new)}})
    return parents


def independent_parent_rows():
    """Regenerate only JD geometry from tracked sources; retain independent oracle."""
    return deepcopy(_replayed_independent_parents())


def semantic_preview_digest(result):
    """Full frozen result contract, without local ledgers/oracle storage location."""
    portable=deepcopy(result)
    for key in ('protected_sha256_before','protected_sha256_after','oracle_artifact_sha256','oracle_fixture_sha256'):
        portable.pop(key,None)
    identity=portable.get('current_versions_unchanged')
    if identity is not None:
        # Raw checkout-byte hashes are verified independently with LF-normalized
        # frozen source hashes, rather than baking core.autocrlf into test credit.
        identity.pop('artifact_sha256',None)
    return stage2.inventory.digest(portable)


def grounded_children(parent, acronym_map):
    """Finite five-parent preview; every inherited character has a raw-JD receipt."""
    source = parent['source_provenance'][0]
    raw = source['raw_parent_text']
    m = re.fullmatch(r'\s*[\u00b7\u2022]?\s*(Design),\s*(develop|build),?\s+and\s+(maintain|deploy)\s+(.+?)\.?', raw, re.I)
    if not m:
        raise ValueError('Not one of the admitted source forms')
    rows = []
    for i in range(3):
        action = m.group(i+1)
        obj = m.group(4)
        text = action.capitalize()+' '+obj
        key = n._canonical_key(text, acronym_map)
        row = deepcopy(parent)
        row.update(requirement_id=n._stable_id('req', key), text=text,
                   canonical_key=key, atomic_focus=text, atomic_focus_key=key,
                   variants=[text], is_atomic=True,
                   group_weight_fraction=(1/3 if i < 2 else 1-2/3))
        for receipt in row['source_provenance']:
            receipt['source_group_fraction'] = row['group_weight_fraction']
        row['preview_derivation'] = {
            'kind':'INHERITED_OBJECT_FROM_EXACT_RAW_PARENT', 'action':action.lower(),
            'action_span':[m.start(i+1),m.end(i+1)],
            'object_span':[m.start(4),m.end(4)], 'object_text':obj,
            'parent_occurrence_id':source['parent_occurrence_id'],
            'offset_unit':'Python Unicode code points; half-open in raw_parent_text',
            'not_a_literal_contiguous_child_span':True,
        }
        rows.append(row)
    return rows


def scenarios(children):
    obj = children[0]['preview_derivation']['object_text']
    actions = [r['preview_derivation']['action'] for r in children]
    past = {'design':'Designed','develop':'Developed','build':'Built',
            'maintain':'Maintained','deploy':'Deployed'}
    def owned(indices):
        return ', '.join(past[actions[i]] for i in indices)+' '+obj+'.'
    cases = [
        ('maintenance_only', 'Maintained '+obj+'.', ['maintain']),
        ('development_only', 'Developed '+obj+'.', ['develop','build']),
        ('design_only', 'Designed '+obj+'.', ['design']),
        ('design_development_no_lifecycle', 'Designed and developed '+obj+'.', ['design','develop','build']),
        ('all_requested_actions', owned([0,1,2]), actions),
        ('generic_software', 'Worked on software projects.', []),
        ('technology_usage_no_ownership', 'Used '+obj+' as an end user without responsibility for their design, development or maintenance.', []),
        ('api_consumption', 'Consumed existing REST APIs using HTTP requests and JSON responses.', []),
        ('postgrest_supabase_integration', 'Integrated React with Supabase PostgREST for CRUD data access and authentication.', []),
        ('java_rest_authorship', 'Implemented Java REST API endpoints and request handlers in an existing backend.', []),
        ('incomplete_design', 'Designed user interface mockups; implemented '+obj+' without owning its design or maintenance.', ['develop','build']),
        ('negated_ownership', 'Never designed, developed, built, maintained or deployed '+obj+'.', []),
        ('zero_overlap_topic', 'Configured ESP32 GPIO interrupts.', []),
    ]
    cases.append(('lifecycle_action_only', owned([2]), [actions[2]]))
    if 'full-stack' in obj:
        cases.append(('all_actions_explicit_layers',owned([0,1,2])+
                      ' Owned the React frontend and Python backend.',actions))
    result = [dict(id=cid,evidence=[text],declared_owned_actions=owned_actions,
                 declared_actions_by_evidence=[owned_actions],
                 attribution='HYPOTHETICAL: resume_profile.projects[0].bullets[0]; not real candidate evidence')
            for cid,text,owned_actions in cases]
    result.append(dict(id='three_actions_separate_rows',evidence=[owned([i]) for i in range(3)],
        declared_owned_actions=actions,declared_actions_by_evidence=[[action] for action in actions],
        attribution='HYPOTHETICAL: three separate project bullets; no union of receipts permitted'))
    return result


def selected_actions(case, result):
    receipts=result['selected_evidence']
    if len(receipts)!=1:
        return []
    source=receipts[0]['source']
    for i, actions in enumerate(case['declared_actions_by_evidence']):
        if source==f'resume_profile.projects[0].bullets[{i}]':
            return actions
    return []


def native_path(requirements, evidence, acronym_map, *, missing_only=False):
    """Same stages as build_stable_analysis, stopping before overall alignment."""
    profile={'projects':[{'title':'Stage 2B disposable synthetic project','bullets':evidence}],
             'experience':[], 'education':[], 'skills':{}}
    raw='\n'.join(evidence)
    kw = ({'present':[], 'missing':[{'keyword':r['atomic_focus']} for r in requirements]}
          if missing_only else n.build_deterministic_keyword_match(
              requirements=requirements, acronym_map=acronym_map,
              resume_profile=profile, raw_resume_text=raw))
    linked,_=n.link_requirement_matches(deepcopy(requirements),kw,acronym_map,
                                      resume_profile=profile,raw_resume_text=raw)
    structured,_=n.apply_structured_requirement_matches(linked,resume_profile=profile,raw_resume_text=raw)
    validated,_=n.validate_linked_matches(structured)
    index=n.build_resume_evidence_index(profile,raw)
    selected,_=n._apply_capability_single_row_reselection(validated,evidence_index=index,acronym_map=acronym_map)
    capped=n.apply_taxonomy_caps_to_requirements(selected,retrieval_mode_override='off')
    recovered,_=n._apply_capability_none_recovery(capped,evidence_index=index,acronym_map=acronym_map)
    out=[]
    for i,r in enumerate(recovered):
        decision=stage2.resolve(requirements[i], evidence_text='\n'.join(evidence))['decision']
        out.append(dict(requirement_id=r['requirement_id'], native_label=r['match_label'],
            evaluator_label=decision.get('label'),evaluator_reason=decision.get('reason'),
            labels_by_stage={name:rows[i]['match_label'] for name,rows in
                [('linked',linked),('validated',validated),('reselected',selected),('capped',capped),('recovered',recovered)]},
            selected_evidence=[{k:e.get(k) for k in ('source','text','evidence_id')} for e in r.get('evidence',[])],
            recovery=deepcopy(r.get('capability_none_recovery')),
            recovery_changes_label=capped[i]['match_label']!=r['match_label']))
    return out


def gate(native_result, required_actions, declared_owned_actions):
    """Diagnostic oracle only. Never manufactures a weak/none credit rule."""
    missing=sorted(set(required_actions)-set(declared_owned_actions))
    blocked=native_result['native_label']=='direct' and bool(missing)
    return dict(missing_actions=missing, direct_blocked=blocked,
                disposition='REVIEW_REQUIRED_NO_APPROVED_PARTIAL_RULE' if blocked else 'NATIVE_LABEL_RETAINED',
                effective_label=None if blocked else native_result['native_label'],
                ownership_basis='fixture-declared semantic receipts; no inferred ownership algorithm')


def control_cases():
    return [
        ('api_consume','Develop REST APIs',['Consumed existing REST API endpoints.']),
        ('api_postgrest','Develop REST APIs',['Integrated Supabase PostgREST for CRUD data access.']),
        ('api_java','Develop REST APIs',['Implemented Java REST API endpoints.']),
        ('api_incomplete_design','Design and develop RESTful APIs',['Implemented REST API endpoints.']),
        ('api_complete_design','Design and develop RESTful APIs',['Designed REST API interfaces and implemented REST API endpoints.']),
        ('api_negated','Develop REST APIs',['Did not implement REST API endpoints.']),
        ('api_split_sources','Design and develop RESTful APIs',['Designed REST API interfaces.','Implemented REST API endpoints.']),
        ('protocol_and','Develop REST and gRPC APIs',['Implemented REST API endpoints.']),
        ('protocol_or','Develop REST or gRPC APIs',['Implemented REST API endpoints.']),
        ('protocol_mixed_consumption','Develop REST and gRPC APIs',['Implemented REST API endpoints; consumed gRPC APIs.']),
        ('protocol_both_authored','Develop REST and gRPC APIs',['Implemented REST API endpoints and implemented gRPC API endpoints.']),
        ('api_lifecycle_missing','Design, develop and maintain REST APIs',['Designed REST API interfaces and implemented REST API endpoints.']),
        ('dsa_generic_data','Knowledge of data structures and algorithms',['Processed generic data with SQL databases.']),
        ('optional','Design, develop and maintain applications, preferably using Python.',['Maintained Python applications.']),
        ('and_or_actions','Design or develop embedded software modules.',['Developed embedded software modules.']),
        ('negated_requirement','Do not design, develop and maintain embedded software modules.',['Maintained embedded software modules.']),
    ]


def study():
    jobs=json.loads((ROOT/stage2.inventory.FIXTURES[0]).read_text(encoding='utf-8'))['snapshot']['audit']['corpus']['jobs']
    counts=[]; parents=[]
    with offline_execution('Stage 2B forbids all network/model use'):
        for job in jobs:
            raw=job['frozen_inputs']['raw_jd_text']
            baseline=stage2.canonical(raw); a=stage2.canonical(raw,proposed=True)
            bparents=stage2.parent_rows(baseline); aparents=stage2.parent_rows(a)
            changed=[pid for pid in bparents if [(r['text'],s['source_group_fraction']) for r,s in bparents[pid]]
                     !=[(r['text'],s['source_group_fraction']) for r,s in aparents[pid]]]
            bcount=len(a['requirements'])
            for pid in changed:
                old=[deepcopy(r) for r,_ in bparents[pid]]
                full=[deepcopy(r) for r,_ in aparents[pid]]
                if len(full)!=1: raise ValueError('Expected a single retained parent')
                children=grounded_children(full[0],a['acronym_map']); bcount+=len(children)-1
                required=[r['preview_derivation']['action'] for r in children]
                variants={'baseline':old,'A_full':full,'B_atomic':children}
                scenario_results=[]
                for case in scenarios(children):
                    results={}
                    for name,rows in variants.items():
                        result=native_path(rows,case['evidence'],a['acronym_map'])
                        result_missing=native_path(rows,case['evidence'],a['acronym_map'],missing_only=True)
                        results[name]={'native':result,'native_missing_keyword_input':result_missing}
                        if name!='baseline':
                            obligations=[required] if name=='A_full' else [[action] for action in required]
                            results[name]['diagnostic_mandatory_action_gate']=[gate(r,req,selected_actions(case,r))
                                for r,req in zip(result,obligations)]
                    scenario_results.append({**case,'results':results})
                parents.append(dict(job_id=job['job_id'],parent_occurrence_id=pid,
                    original_raw_parent=full[0]['source_provenance'][0]['raw_parent_text'],
                    required_actions=required,
                    variants={name:[{**deepcopy(r),'recognition':stage2.recognition(r)} for r in rows] for name,rows in variants.items()},
                    allocation={name:sum(r['group_weight_fraction'] for r in rows) for name,rows in variants.items()},
                    source_allocation={name:sum(s['source_group_fraction'] for r in rows for s in r['source_provenance']
                        if s.get('contributes_scoring_allocation',True)) for name,rows in variants.items()},
                    canonical_ids_change={name:[r['requirement_id'] for r in rows] for name,rows in variants.items()},
                    scenarios=scenario_results))
            counts.append(dict(job_id=job['job_id'],baseline=len(baseline['requirements']),A_full=len(a['requirements']),B_atomic=bcount))
        controls=[]
        for cid,req,evidence in control_cases():
            base=stage2.canonical('Responsibilities:\n'+req)
            full=stage2.canonical('Responsibilities:\n'+req,proposed=True)
            controls.append(dict(id=cid,requirement=req,synthetic_evidence=evidence,
                baseline_rows=deepcopy(base['requirements']),A_rows=deepcopy(full['requirements']),
                baseline_native=native_path(base['requirements'],evidence,base['acronym_map']),
                A_native=native_path(full['requirements'],evidence,full['acronym_map']),
                A_native_missing_keyword_input=native_path(full['requirements'],evidence,full['acronym_map'],missing_only=True),
                forced_api_evaluator_only=([evaluate_capability_evidence('backend.api_development',{'text':req},text)
                    for text in evidence] if cid.startswith(('api_','protocol_')) else []),
                B_disposition='NOT_DECOMPOSED: boolean/optional/negation/protocol control; finite B preview applies only to the five admitted parents'))
    return dict(preview_version=VERSION,current_versions_unchanged=stage2.inventory.knowledge_identity(),
        scope='CURRENT_RAW_JD_ONLY_PLUS_HYPOTHETICAL_PROJECT_ROWS; NOT_HISTORICAL_REPLAY',
        job_match_scores_computed=False,real_candidate_evidence_used=False,
        ownership_detector_implemented=False,partial_credit_policy_proposed=False,
        native_pipeline='deterministic keywords -> link -> structured -> validate -> single-row reselection -> taxonomy caps -> none recovery; stop before alignment',
        cohort_counts=counts,totals={k:sum(r[k] for r in counts) for k in ('baseline','A_full','B_atomic')},
        parents=parents,controls=controls)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'bulk_unresolved_stage2b_preview.json')
    parser.add_argument('--protected-baseline',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or not args.output.resolve().is_relative_to(ROOT):
        raise ValueError('Use a new output inside this worktree')
    result=study()
    ledger=json.loads(args.protected_baseline.read_text(encoding='utf-8-sig'))
    result['protected_sha256_before']=ledger['files']
    result['protected_sha256_after']={p:stage2.inventory.file_sha(ROOT/p) for p in ledger['files']}
    if result['protected_sha256_before']!=result['protected_sha256_after']:
        raise ValueError('A protected entry-state file changed')
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(totals=result['totals'],parents=len(result['parents']),protected_files=len(ledger['files']))))


if __name__=='__main__':
    main()
