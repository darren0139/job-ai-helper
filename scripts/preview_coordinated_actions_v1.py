"""Offline coordinated-action experiment using an isolated native namespace.

No production globals/functions are patched, no snapshot is reinterpreted, and
no score or evidence label is produced. Only current raw-JD canonicalization is
compared. The proposed guard is an analyst hypothesis, not approved policy.
"""
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
import argparse
import inspect
import json
from pathlib import Path
import re
import statistics
import subprocess
import time
from types import FunctionType

from analysis_stability import stable_evidence_scoring as native
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve
from taxonomy_discovery import source_aware_inventory as inventory
from taxonomy_discovery.offline_execution import offline_execution

VERSION='DRY_RUN_ONLY-coordinated-actions-v1'
VERBS=r'(?:design|develop|build|implement|create|maintain|test|deploy)'
VERB_PREFIX=re.compile(rf'^\s*(?:\u00b7|\u2022)?\s*{VERBS}(?:\s*,\s*{VERBS}){{1,5}}\s*$',re.I)
EXTRA_ACTION=re.compile(rf'\band\s+{VERBS}\b',re.I)
OBJECTS={'application','applications','software','module','modules','pipeline','pipelines',
    'infrastructure','service','services','system','systems','component','components',
    'tool','tools','endpoint','endpoints','api','apis','code'}


@lru_cache(maxsize=1)
def preview_namespace():
    # Function code is reused verbatim, with a separate globals dictionary for
    # every native-defined function. Imported helpers retain their native policy.
    namespace=dict(native.__dict__)
    for name,fn in list(namespace.items()):
        if inspect.isfunction(fn) and fn.__globals__ is native.__dict__:
            clone=FunctionType(fn.__code__,namespace,name,fn.__defaults__,fn.__closure__)
            clone.__kwdefaults__=deepcopy(fn.__kwdefaults__)
            namespace[name]=clone
    baseline_pair=namespace['_split_safe_independent_and_pair']
    baseline_nonpreference=namespace['_split_non_preference_clause']

    def shared_object(value):
        pair=baseline_pair(value)
        if len(pair)!=2 or not VERB_PREFIX.fullmatch(pair[0]):
            return False
        # Conservative negatives/alternatives and extra independent actions stay
        # outside this preview. No qualifier or protocol is removed from input.
        if re.search(r'\b(?:or|not|never|without|no)\b',value,re.I):
            return False
        match=re.match(rf'^\s*{VERBS}\s+(?P<object>.+)$',pair[1],re.I)
        if not match or EXTRA_ACTION.search(match['object']):
            return False
        head=re.findall(r'[a-zA-Z][\w-]*',match['object'].lower())[:12]
        if not OBJECTS.intersection(head):
            return False
        return True

    def bounded_nonpreference(value,importance,parent_text):
        # The whole-obligation guard belongs before paired/from-enumeration
        # splitting. Merely returning [] from the pair helper allows a later
        # enumeration branch to introduce different unwanted children (Job 16).
        if not namespace['_preserves_coherent_parent'](value) and shared_object(value):
            return [namespace['_clause_record'](text=value,importance=importance,
                parent_text=parent_text,focus_text=value,
                atomic_group_id=namespace['_stable_id']('grp',namespace['_normalise_basic'](parent_text)),
                is_atomic=False)]
        return baseline_nonpreference(value,importance,parent_text)
    namespace['_split_non_preference_clause']=bounded_nonpreference
    return namespace


def canonical(raw, *, proposed=False, profile=None):
    before=deepcopy(profile or {})
    function=preview_namespace()['canonicalise_requirements'] if proposed else native.canonicalise_requirements
    with offline_execution('Coordinated-action preview forbids network'):
        result=function(deepcopy(before),raw_jd_text=raw)
    return result


def recognition(row):
    n=resolve(row)
    return {'knowledge_status':n['knowledge_status'],'capability_id':n['decision'].get('capability_id'),
            'resolution_source':n['resolution_source'],'taxonomy_reason':n['taxonomy_diagnostics'].get('reason'),
            'registry_reason':(n.get('registry_resolution') or {}).get('reason'),
            'identity_reason':(n.get('identity_scope') or {}).get('reason')}


def parent_rows(canonicalized):
    parents=defaultdict(list)
    for row in canonicalized['requirements']:
        for source in row.get('source_provenance',[]):
            parents[source['parent_occurrence_id']].append((row,source))
    return parents


def allocation(rows):
    return round(sum(s['source_group_fraction'] for _,s in rows
                     if s.get('contributes_scoring_allocation',True)),6)


def group_sums(canonicalized):
    groups=defaultdict(float)
    for r in canonicalized['requirements']:
        groups[r['atomic_group_id']]+=r['group_weight_fraction']
    return {g:round(v,6) for g,v in sorted(groups.items())}


def receipt(row,source):
    keys=('requirement_id','text','atomic_focus','importance','is_atomic','atomic_group_id',
          'group_weight_fraction','scoring_parent_occurrence_id','evidence_eligible',
          'score_eligible','tailoring_eligible','semantic_type')
    return {**{k:row[k] for k in keys if k in row},'source_occurrence':deepcopy(source),
            'recognition':recognition(row)}


def compare_job(job,index):
    raw=job['frozen_inputs']['raw_jd_text']
    baseline=canonical(raw);proposed=canonical(raw,proposed=True)
    b=parent_rows(baseline);a=parent_rows(proposed)
    if b.keys()!=a.keys():
        raise ValueError('Preview changed source occurrence inventory')
    changed=[]
    for pid in sorted(b):
        signature=lambda rows:[(r['requirement_id'],r['text'],s['source_group_fraction'],
                                s.get('contributes_scoring_allocation',True)) for r,s in rows]
        if signature(b[pid])==signature(a[pid]):
            continue
        old=[receipt(r,s) for r,s in b[pid]];new=[receipt(r,s) for r,s in a[pid]]
        grounding=deepcopy(b[pid][0][1])
        old_scope={k:grounding.get(k) for k in ('parent_text','raw_parent_text','source','grounding')}
        spans_preserved=all({k:s.get(k) for k in old_scope}==old_scope for _,s in a[pid])
        raw_parent=grounding['raw_parent_text']
        changed.append(dict(parent_occurrence_id=pid,original_raw_parent=raw_parent,
            source_reference={'fixture':inventory.FIXTURES[0],'job_index':index,
                'field':'frozen_inputs.raw_jd_text','fixture_sha256':inventory.file_sha(inventory.ROOT/inventory.FIXTURES[0])},
            exact_grounding=grounding.get('grounding'),baseline=old,proposed=new,
            baseline_native_pair=native._split_safe_independent_and_pair(
                native._normalise_requirement_surface(raw_parent)),
            baseline_native_clauses=native._split_single_requirement_clause(raw_parent,old[0]['importance']),
            baseline_allocation_sum=allocation(b[pid]),proposed_allocation_sum=allocation(a[pid]),
            allocation_conserved=abs(allocation(b[pid])-allocation(a[pid]))<0.00001,
            child_count_delta=len(new)-len(old),
            removed_child_ids=sorted({r['requirement_id'] for r in old}-{r['requirement_id'] for r in new}),
            added_child_ids=sorted({r['requirement_id'] for r in new}-{r['requirement_id'] for r in old}),
            canonical_identities_change={r['requirement_id'] for r in old}!={r['requirement_id'] for r in new},
            source_spans_preserved=spans_preserved,
            importance_values_change={r['importance'] for r in old}!={r['importance'] for r in new},
            evidence_eligibility_values_change={r.get('evidence_eligible') for r in old}!={r.get('evidence_eligible') for r in new},
            currentness_increment_required=True))
    return {'job_id':job['job_id'],'baseline_requirement_count':len(baseline['requirements']),
            'proposed_requirement_count':len(proposed['requirements']),
            'baseline_atomic_group_sums':group_sums(baseline),'proposed_atomic_group_sums':group_sums(proposed),
            'changed_parents':changed,'deterministic_repeat':proposed==canonical(raw,proposed=True),
            'native_repeat_unchanged':baseline==canonical(raw)}


def benchmark(jobs,repeats=3):
    samples={name:[] for name in ('baseline','proposed')}
    for _ in range(repeats):
        for name in samples:
            start=time.perf_counter()
            for job in jobs:
                canonical(job['frozen_inputs']['raw_jd_text'],proposed=name=='proposed')
            samples[name].append(time.perf_counter()-start)
    return {'jobs_per_sample':len(jobs),'samples_seconds':samples,
            'median_seconds':{k:statistics.median(v) for k,v in samples.items()},
            'warm_namespace':True,'machine_specific':True,'no_model_or_evidence_work':True}


def study():
    data=json.loads((inventory.ROOT/inventory.FIXTURES[0]).read_text(encoding='utf-8'))
    jobs=data['snapshot']['audit']['corpus']['jobs']
    comparisons=[compare_job(job,i) for i,job in enumerate(jobs)]
    manifest=json.loads((inventory.ROOT/'bulk_unresolved_stage1_summary.json').read_text(encoding='utf-8'))
    if (manifest['sources'][inventory.FIXTURES[0]]!=inventory.file_sha(inventory.ROOT/inventory.FIXTURES[0])
            or sum(j['baseline_requirement_count'] for j in comparisons)!=manifest['cohorts']['raw_jd_only']['rows']):
        raise ValueError('Current UTF-8 fixture replay disagrees with the Stage 1 source manifest')
    return {'preview_version':VERSION,'current_versions_unchanged':inventory.knowledge_identity(),
            'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'scope':'CURRENT_RAW_JD_ONLY_NOT_HISTORICAL_REPLAY','jobs':comparisons,
            'changed_jobs':[j['job_id'] for j in comparisons if j['changed_parents']],
            'changed_parents':sum(len(j['changed_parents']) for j in comparisons),
            'baseline_requirements':sum(j['baseline_requirement_count'] for j in comparisons),
            'proposed_requirements':sum(j['proposed_requirement_count'] for j in comparisons),
            'benchmark':benchmark([j for j in jobs if j['job_id'] in (16,359,479,566)]),
            'job_match_scores_computed':False,'candidate_evidence_evaluated':False,
            'production_parser_modified':False,'historical_snapshots_modified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('bulk_unresolved_stage2_preview.json'))
    parser.add_argument('--protected-baseline',type=Path,required=True)
    args=parser.parse_args()
    if not args.output.resolve().is_relative_to(inventory.ROOT) or args.output.exists():
        raise ValueError('Use a new Stage 2 output path inside this worktree')
    result=study()
    ledger=json.loads(args.protected_baseline.read_text(encoding='utf-8'))
    result['protected_sha256_before']=ledger['files']
    result['protected_sha256_after']={p:inventory.file_sha(inventory.ROOT/p) for p in ledger['files']}
    result['intentional_validation_only_changes']=['taxonomy_discovery/source_aware_inventory.py']
    bad=[p for p,h in ledger['files'].items() if result['protected_sha256_after'][p]!=h
         and p not in result['intentional_validation_only_changes']]
    if bad:
        raise ValueError('Protected baseline unexpectedly changed')
    args.output.write_text(json.dumps(inventory.redact(result),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('changed_jobs','changed_parents','baseline_requirements','proposed_requirements')}))


if __name__=='__main__':
    main()
