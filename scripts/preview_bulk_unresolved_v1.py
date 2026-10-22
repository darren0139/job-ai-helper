"""Read-only fixture inventory and context-local recognition experiments.

This is an investigation CLI, never a production resolver or database exporter.
It reuses native canonicalization, diagnostics, descriptive backlog clustering
and taxonomy scopes. No provider, publisher, persistence or refresh is called.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time

from analysis_stability import stable_evidence_scoring as scoring
from job_discovery.matching import current_match_versions
from scripts import cluster_unresolved_backlog_v1 as backlog
from tailoring import capability_taxonomy as taxonomy
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge as resolve

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'bulk-unresolved-fixture-investigation-v1'
SOURCES = ('tests/fixtures/per_jd_scoring_audit.json',
           'tests/fixtures/confirmed_taxonomy_coverage.json')
FIELDS = tuple(dict.fromkeys(backlog.FIELDS + (
    'semantic_type', 'evidence_eligible', 'tailoring_eligible', 'eligibility_rule',
    'capability_id', 'knowledge_status', 'capability_recognition_rule')))
API = 'backend.api_development'
# Analyst review examples, not a new runtime grammar or approved aliases.
PROPOSALS = {
    'Knowledge of REST APIs': 'Knowledge of REST API',
    'Knowledge of RESTful APIs': 'Knowledge of RESTful API',
    'Develop REST endpoints': 'Develop REST API endpoints',
    'Implement REST endpoints': 'Implement REST API endpoints',
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def requirement_input(row):
    return {k: deepcopy(row[k]) for k in FIELDS if k in row}


def safe(value, key=None):
    if isinstance(value, dict):
        return {k: safe(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [safe(v, key) for v in value]
    text_fields = {'text','atomic_focus','parent_text','raw_parent_text','sentence_text',
                   'original_requirement','requirement_text','wording','matched_phrase',
                   'exact_spans','proposed_comparator'}
    if key in text_fields and isinstance(value, str) and backlog.unsafe_text(value):
        return '[WITHHELD sensitive text; sha256=' + fingerprint(value) + ']'
    return value


def summary(native):
    diag = native['taxonomy_diagnostics']
    registry = native.get('registry_resolution') or {}
    identity = native.get('identity_scope') or {}
    return dict(knowledge_status=native['knowledge_status'],
                capability_id=native['decision'].get('capability_id'),
                technology_id=native.get('technology_id'),
                resolution_source=native['resolution_source'],
                taxonomy_reason=diag.get('reason'),
                matched_phrase=diag.get('matched_phrase'),
                recognition_rule=native.get('recognition_rule'),
                registry_status=registry.get('status'), registry_reason=registry.get('reason'),
                identity_scope=identity.get('category'), identity_reason=identity.get('reason'),
                evidence_label_with_empty_input=native['decision'].get('label'))


def load_jobs(paths=SOURCES):
    """Primary raw-JD fixture plus explicitly separate historical reference views.

    The coverage fixture omits raw JD and versions and has different row scopes.
    Never overwrite primary receipts or count those views as independent jobs.
    """
    jobs, manifests = {}, []
    for name in paths:
        path = ROOT / name
        data = json.loads(path.read_text(encoding='utf-8'))
        views = data['snapshot']['audit']['corpus']['jobs']
        manifest=dict(path=name, sha256=sha(path), job_views=len(views),
                      requirement_views=sum(len(j['baseline_stable_analysis']['canonical_requirements']) for j in views),
                      role='primary' if not manifests else 'alternate_historical_reference_not_merged',
                      alternate_views=[])
        manifests.append(manifest)
        for job in views:
            jid = job['job_id']
            if jid in jobs:
                primary=jobs[jid]['job']['baseline_stable_analysis']['canonical_requirements']
                alternate=job['baseline_stable_analysis']['canonical_requirements']
                p={r['requirement_id']:r for r in primary};a={r['requirement_id']:r for r in alternate}
                manifest['alternate_views'].append(dict(job_id=jid,
                    content_identical=jobs[jid]['content_fingerprint']==fingerprint(job),
                    raw_jd_available=bool(job.get('frozen_inputs',{}).get('raw_jd_text')),
                    primary_only_ids=sorted(p.keys()-a.keys()),alternate_only_ids=sorted(a.keys()-p.keys()),
                    different_row_ids=sorted(rid for rid in p.keys() & a.keys() if p[rid]!=a[rid])))
            else:
                if not job.get('frozen_inputs',{}).get('raw_jd_text'):
                    raise ValueError(f'No authoritative raw-JD primary for job {jid}')
                jobs[jid] = dict(job=deepcopy(job), content_fingerprint=fingerprint(job), source_files=[name])
    return [jobs[k] for k in sorted(jobs)], manifests


def exact_clusters(rows):
    groups = defaultdict(list)
    for r in rows:
        if r['current']['knowledge_status'] == 'UNRESOLVED':
            groups[backlog.normal(r['original_requirement'])].append(r)
    return sorted([dict(cluster_id='exact_' + fingerprint({'normalizer': VERSION, 'text': text})[:20],
                        relation='EXACT_NORMALIZED_WORDING_ONLY_NOT_SEMANTIC_EQUIVALENCE',
                        occurrences=len(group), job_count=len({r['job_id'] for r in group}),
                        wording=safe(group[0]['original_requirement']),
                        members=[dict(job_id=r['job_id'], requirement_id=r['requirement_id']) for r in group])
                   for text, group in groups.items()], key=lambda c: (-c['job_count'], -c['occurrences'], c['cluster_id']))


def inventory_row(row, job_id, source_files, raw_jd, versions, cohort):
    inp = requirement_input(row)
    frozen = fingerprint(inp)
    native = resolve(inp)
    assert fingerprint(inp) == frozen
    obs = backlog.observations(inp, native, raw_jd)
    unresolved = native['knowledge_status'] == 'UNRESOLVED'
    label = row.get('match_label')
    if not unresolved:
        if cohort == 'raw_jd_only_replay':
            category = 'recognized_evidence_not_evaluated'
        elif label == 'none':
            category = 'recognized_with_stored_no_credit'
        elif label in ('weak', 'transferable'):
            category = 'recognized_with_stored_partial_credit'
        else:
            category = 'recognized_with_stored_direct_credit'
    elif obs['native_scope'] == 'PARSER_OR_DECOMPOSITION_BLOCKED':
        category = 'unresolved_source_or_decomposition_review'
    elif any(word in backlog.normal(row.get('text')) for word in (' and ', ' or ')):
        category = 'unresolved_possible_compound_review'
    elif obs['predicate_observations']:
        category = 'unresolved_existing_predicate_candidate_review'
    else:
        category = 'unresolved_identity_or_coverage_review'
    return dict(job_id=job_id, requirement_id=row['requirement_id'],
                original_requirement=row.get('text'), input=inp,
                input_fingerprint=frozen, source_files=source_files, source_versions=versions,
                cohort=cohort, current=summary(native), stored_knowledge_status=row.get('knowledge_status'),
                stored_match_label=label, stored_evidence_count=len(row.get('evidence') or []),
                category=category, **obs)


def descriptive_clusters(rows):
    compatible = []
    for r in rows:
        if r['current']['knowledge_status'] != 'UNRESOLVED' or backlog.unsafe_text(r['original_requirement']):
            continue
        compatible.append(dict(r, job_key=f"fixture:{r['job_id']}", requirement_text=r['original_requirement'],
                               source_reference=f"{r['source_files'][0]}::job[{r['job_id']}]::requirement[{r['requirement_id']}]",
                               importance=r['input'].get('importance'),
                               normalized_text_fingerprint=fingerprint(backlog.normal(r['original_requirement'])),
                               record_provenance=[{'scope_provenance_fingerprint':fingerprint(r['input'].get('source_provenance'))}]))
    return backlog.clusters(compatible)


def count_rows(rows):
    return dict(total=len(rows), knowledge=dict(Counter(r['current']['knowledge_status'] for r in rows)),
                categories=dict(Counter(r['category'] for r in rows)),
                unresolved_eligible=sum(r['current']['knowledge_status']=='UNRESOLVED' and scoring.requirement_is_score_eligible(r['input']) for r in rows),
                unresolved_with_stored_positive_credit=sum(r['current']['knowledge_status']=='UNRESOLVED' and r['stored_match_label'] in ('direct','weak','transferable') for r in rows),
                missing_parent_provenance=sum(not r['input'].get('source_provenance') for r in rows))


def build_inventory(jobs):
    saved, fresh, comparisons = [], [], []
    for view in jobs:
        job = view['job']; jid = job['job_id']; stable = job['baseline_stable_analysis']
        raw = job['frozen_inputs']['raw_jd_text']
        versions = {k:stable.get(k) for k in ('scoring_version','capability_taxonomy_version','technology_registry_version')}
        old = [inventory_row(r, jid, view['source_files'], raw, versions, 'saved_projection')
               for r in stable['canonical_requirements']]
        # Missing original extracted profile: this is deliberately NOT snapshot replay.
        canonical = scoring.canonicalise_requirements({}, raw_jd_text=raw)
        new = [inventory_row(r, jid, view['source_files'], raw, current_match_versions(), 'raw_jd_only_replay')
               for r in canonical['requirements']]
        old_by_id = {r['requirement_id']:r for r in old}; new_by_id = {r['requirement_id']:r for r in new}
        common = old_by_id.keys() & new_by_id.keys()
        comparisons.append(dict(job_id=jid, raw_jd_sha256=fingerprint(raw),
            saved_count=len(old), raw_only_count=len(new),
            saved_only_ids=sorted(old_by_id.keys()-new_by_id.keys()), raw_only_ids=sorted(new_by_id.keys()-old_by_id.keys()),
            common_id_resolution_differences=[dict(requirement_id=rid, saved_projection=old_by_id[rid]['current'],
                raw_only=new_by_id[rid]['current']) for rid in sorted(common) if old_by_id[rid]['current']!=new_by_id[rid]['current']],
            filtered_rows=canonical['filtered_non_requirement_rows'],
            source_parent_allocation_sums={p:round(sum(s.get('source_group_fraction',0) for r in canonical['requirements'] for s in r.get('source_provenance',[]) if s.get('parent_occurrence_id')==p and s.get('contributes_scoring_allocation',True)),6)
                for p in sorted({s['parent_occurrence_id'] for r in canonical['requirements'] for s in r.get('source_provenance',[])})}))
        saved.extend(old); fresh.extend(new)
    return dict(saved_projection_counts=count_rows(saved), raw_jd_only_counts=count_rows(fresh),
                saved_rows=saved, raw_jd_only_rows=fresh, job_comparisons=comparisons,
                exact_clusters=exact_clusters(saved), descriptive_clusters=descriptive_clusters(saved),
                raw_only_descriptive_clusters=descriptive_clusters(fresh))


def preview(row):
    """Exact analyst fixtures + complete parent guard; native resolver in a scope.

    A future deployable scoped rule still needs design/approval. Adding these
    phrases to global any_terms is NOT the recommended production change.
    """
    inp = requirement_input(row); before = resolve(inp); frozen = fingerprint(inp)
    text = str(inp.get('text') or '').strip().rstrip('.')
    replacement = PROPOSALS.get(text)
    surface = lambda v: ' '.join(str(v or '').split()).strip().rstrip('.').casefold()
    scope_ok = surface(inp.get('atomic_focus') or text)==surface(text)
    scope_ok &= not inp.get('is_atomic') or bool(inp.get('source_provenance'))
    scope_ok &= 'source_provenance' not in inp or bool(inp['source_provenance'])
    scope_ok &= not inp.get('parent_text') or surface(inp['parent_text'])==surface(text)
    for p in inp.get('source_provenance') or []:
        scope_ok &= bool(p.get('source') and p.get('parent_occurrence_id')) and surface(p.get('parent_text'))==surface(text) and surface(p.get('raw_parent_text'))==surface(text)
    applied = bool(replacement and scope_ok and before['knowledge_status']=='UNRESOLVED')
    if applied:
        # Establish the existing singular/explicit-API comparator independently.
        comparator = resolve({'text':replacement})
        assert comparator['decision'].get('capability_id') == API
        base = taxonomy.get_default_taxonomy(); entries=deepcopy(list(base.capabilities))
        next(c for c in entries if c['capability_id']==API)['requirement']['any_terms'].append(text)
        overlay=taxonomy.CapabilityTaxonomy('DRY_RUN_ONLY-'+VERSION,tuple(entries))
        with taxonomy.temporary_taxonomy_scope(overlay):
            after=resolve(inp)
    else:
        after=before
    assert fingerprint(inp)==frozen and resolve(inp)==before, 'Preview leaked or changed requirement'
    return dict(requirement_id=inp.get('requirement_id'), original_requirement=inp.get('text'),
                proposed_comparator=replacement, proposal_applied=applied, baseline=summary(before), proposed=summary(after),
                original_input=inp, input_fingerprint=frozen, decomposition_changed=False,
                parent_weights_changed=False, evidence_eligibility_changed=False, source_provenance_changed=False,
                evidence_credit_computed=False, live_score_computed=False,
                review_basis='Exact analyst equivalence candidate; complete scope only; NOT verified human gold',
                proposed_runtime_rule_implemented=False)


def controls():
    texts = list(PROPOSALS) + ['Knowledge of REST API','Knowledge of API integration',
        'Integrate REST APIs','Knowledge of API development','Design and develop RESTful APIs',
        'Knowledge of REST and gRPC APIs','Do not develop REST endpoints',
        'Develop REST endpoints and design a database','Use Supabase for data access',
        'Generic data handling','Data Structures and Algorithms','Amazon Web Services',
        'Design REST interfaces','Develop gRPC endpoints','Experience with Node.js']
    return [preview({'requirement_id':'control_'+fingerprint(t)[:12], 'text':t,
                     'importance':'core','group_weight_fraction':1,'score_eligible':True}) for t in texts]


def benchmark(rows):
    inputs=[r['input'] for r in rows]
    unique={fingerprint(r):r for r in inputs}
    # Resolve once uncached and once by exact complete-input key, no fuzzy cache.
    uncached=[];cached=[]
    for _ in range(3):
        start=time.perf_counter(); before=[summary(resolve(r)) for r in inputs];uncached.append(time.perf_counter()-start)
        start=time.perf_counter(); memo={k:summary(resolve(r)) for k,r in unique.items()};after=[memo[fingerprint(r)] for r in inputs];cached.append(time.perf_counter()-start)
        assert before==after
    return dict(input_rows=len(inputs), unique_complete_inputs=len(unique), possible_exact_reuses=len(inputs)-len(unique),
                uncached_seconds=uncached, cached_seconds=cached,
                uncached_median_seconds=statistics.median(uncached), cached_median_seconds=statistics.median(cached),
                cache_key_basis='Complete allowlisted requirement + current knowledge/version identity; no candidate evidence cached',
                timing_is_machine_specific=True, measurements_include_warm_imports_only=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protected-baseline',type=Path)
    parser.add_argument('--final-review-dir',type=Path,
                        help='New local output directory; native corpus audit and exposed-context V5 companion only')
    args=parser.parse_args()
    if args.final_review_dir:
        destination=args.final_review_dir.resolve()
        if destination.exists() or not destination.is_relative_to(ROOT/'reports'):
            parser.error('Use a new local directory under this worktree reports/')
        # Never overwrite the historical inventory, V5 packet or gold receipts.
        corpus=final_corpus_review()
        packet,source=verified_review_sources()
        companion=review_companion(packet,source)
        destination.mkdir(parents=True)
        for name,value in [('corpus.json',corpus),('review_companion.json',companion)]:
            exported=safe(value)
            exported['fingerprint']=fingerprint({k:v for k,v in exported.items() if k!='fingerprint'})
            (destination/name).write_text(json.dumps(exported,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        (destination/'review_companion.md').write_text(companion_markdown(companion),encoding='utf-8')
        print(json.dumps({k:corpus[k] for k in ('saved_before','saved_after','raw_before','raw_after','compound_counts','changed_raw_jobs')},sort_keys=True))
        return
    if not args.protected_baseline:
        parser.error('--protected-baseline is required unless --final-review-dir is selected')
    ledger=json.loads(args.protected_baseline.read_text())
    assert all(sha(ROOT/p)==h for p,h in ledger.items()), 'Baseline already changed'
    jobs, manifests=load_jobs(); inv=build_inventory(jobs)
    proposed=[dict(job_id=r['job_id'],cohort=r['cohort'],**preview(r['input']))
              for r in inv['saved_rows']+inv['raw_jd_only_rows']]
    output=dict(investigation_version=VERSION, baseline_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(), current_versions=current_match_versions(),
                source_manifests=manifests, unique_jobs=len(jobs),
                alternate_job_views_not_independent_jobs=sum(m['job_views'] for m in manifests)-len(jobs),
                no_live_database_access=True, no_model_calls=True, no_scoring_changes=True,
                limitation='Tracked fixture projections only; original extracted JD profile and full candidate inputs unavailable. Raw-JD-only cohort is not historical or live replay.', **inv)
    experiment=dict(investigation_version=VERSION, proposals=PROPOSALS, controls=controls(),
                    corpus_previews=proposed, benchmark=benchmark(inv['saved_rows']),
                    protected_sha256_before=ledger,
                    protected_sha256_after={p:sha(ROOT/p) for p in ledger},
                    production_policy_changed=False, human_gold=False)
    assert experiment['protected_sha256_before']==experiment['protected_sha256_after']
    for name,data in [('bulk_unresolved_v1_inventory.json',output),('bulk_unresolved_v1_preview.json',experiment)]:
        (ROOT/name).write_text(json.dumps(safe(data),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(jobs=len(jobs),saved=inv['saved_projection_counts'],raw_only=inv['raw_jd_only_counts'],
        exact_clusters=len(inv['exact_clusters']),descriptive_clusters=len(inv['descriptive_clusters']),
        corpus_proposal_applications=sum(r['proposal_applied'] for r in proposed), protected=len(ledger))))


def compound_observation(row):
    """Review cues only; reuse native scope diagnostics, never create children."""
    import re
    from tailoring.phase6d6_structured_matching import technology_requirement_structure
    text=row['original_requirement']
    # These are deliberately lexical review strata, not an AND/OR parser or
    # a claim that a whole source scope has been proved from a connector.
    if re.search(r'\b(?:one or more|any of|either)\b',text,re.I): kind='EXPLICIT_ALTERNATIVE_CUE'
    elif scoring._preserves_coherent_parent(text): kind='EXAMPLE_OR_COHERENT_PARENT_CUE'
    elif '/' in text: kind='SLASH_OR_MIXED_SCOPE_REVIEW'
    else:
        and_cue=bool(re.search(r'\band\b',text,re.I));or_cue=bool(re.search(r'\bor\b',text,re.I))
        kind='MIXED_AND_OR_CUES' if and_cue and or_cue else 'EXPLICIT_OR_CUE' if or_cue else 'EXPLICIT_AND_CUE' if and_cue else 'UNCLEAR_SCOPE'
    return {'job_id':row['job_id'],'requirement_id':row['requirement_id'],
        'original_requirement':text,'input_fingerprint':row['input_fingerprint'],
        'review_stratum':kind,'native_structure':technology_requirement_structure(row['input']),
        'source_provenance_available':bool(row['input'].get('source_provenance')),
        'parent_text_located_in_raw_jd':row['parent_source_available'],
        'interpretation_approved':False,'scoring_children_created':False}


def _recognition_metrics(rows):
    unresolved=[r for r in rows if r['current']['knowledge_status']=='UNRESOLVED']
    return {'rows':len(rows),'knowledge':dict(sorted(Counter(r['current']['knowledge_status'] for r in rows).items())),
        'distinct_unresolved_ids':len({r['requirement_id'] for r in unresolved}),
        'distinct_unresolved_wordings':len({backlog.normal(r['original_requirement']) for r in unresolved})}


def _source_allocations(rows):
    totals=defaultdict(float)
    for row in rows:
        for p in row['input'].get('source_provenance',[]):
            if p.get('contributes_scoring_allocation',True):
                key=(p.get('grounding',{}).get('line_index'),fingerprint(p.get('raw_parent_text')))
                totals[key]+=p.get('source_group_fraction',0)
    return [{'line_index':k[0],'raw_parent_fingerprint':k[1],'allocation_sum':round(v,6)}
            for k,v in sorted(totals.items(),key=lambda item:str(item[0]))]


def final_corpus_review(jobs=None):
    """Same frozen views before/after native alias preservation; no evidence replay."""
    from analysis_stability.coordinated_runtime import approved_alias_surface_preview, APPROVED_ALIAS_POLICY
    from taxonomy_discovery.offline_execution import offline_execution
    jobs=jobs if jobs is not None else load_jobs()[0]
    with offline_execution('Phase 3A corpus review is offline'):
        before=build_inventory(jobs)
        saved=[];fresh=[]
        with approved_alias_surface_preview():
            for view in jobs:
                job=view['job'];raw=job['frozen_inputs']['raw_jd_text'];jid=job['job_id']
                saved.extend(inventory_row(r,jid,view['source_files'],raw,{},'saved_projection')
                    for r in job['baseline_stable_analysis']['canonical_requirements'])
                fresh.extend(inventory_row(r,jid,view['source_files'],raw,current_match_versions(),'raw_jd_only_replay')
                    for r in scoring.canonicalise_requirements({},raw_jd_text=raw)['requirements'])
        changed=[]
        for view in jobs:
            jid=view['job']['job_id'];old=[r for r in before['raw_jd_only_rows'] if r['job_id']==jid];new=[r for r in fresh if r['job_id']==jid]
            if [r['input'] for r in old]!=[r['input'] for r in new]:
                changed.append({'job_id':jid,'raw_jd_fingerprint':fingerprint(view['job']['frozen_inputs']['raw_jd_text']),
                    'before':[{k:r[k] for k in ('requirement_id','original_requirement','input_fingerprint','current')} for r in old],
                    'after':[{k:r[k] for k in ('requirement_id','original_requirement','input_fingerprint','current')} for r in new],
                    'allocation_before':_source_allocations(old),'allocation_after':_source_allocations(new),
                    'same_raw_source':True,'historical_candidate_scores_compared':False})
        compounds=[compound_observation(r) for r in before['saved_rows'] if r['category']=='unresolved_possible_compound_review']
        predicate_candidates=[{'job_id':r['job_id'],'requirement_id':r['requirement_id'],
            'original_requirement':r['original_requirement'],'input_fingerprint':r['input_fingerprint'],
            'existing_predicate_observations':r['predicate_observations'],
            'approval':'REQUIRED_NOT_APPROVED','review_destination':'existing resolver/maintenance fix-layer review',
            'evidence_credit_proposed':False}
            for r in before['raw_jd_only_rows'] if r['current']['knowledge_status']=='UNRESOLVED' and r['predicate_observations']]
    body={'review_version':'phase3a-final-corpus-review-v1','policy':APPROVED_ALIAS_POLICY,
        'historical_candidate_replay':False,'human_gold_created':False,
        'source_files':{name:sha(ROOT/name) for name in SOURCES},
        'implementation_sha256':{name:sha(ROOT/name) for name in (
            'analysis_stability/stable_evidence_scoring.py','analysis_stability/coordinated_runtime.py',
            'tailoring/production_requirement_resolver.py','scripts/preview_bulk_unresolved_v1.py')},
        'published_versions':current_match_versions(),'saved_before':_recognition_metrics(before['saved_rows']),
        'saved_after':_recognition_metrics(saved),'raw_before':_recognition_metrics(before['raw_jd_only_rows']),
        'raw_after':_recognition_metrics(fresh),'saved_input_geometry_unchanged':
            [r['input'] for r in before['saved_rows']]==[r['input'] for r in saved],
        'changed_raw_jobs':changed,'compound_counts':dict(sorted(Counter(r['review_stratum'] for r in compounds).items())),
        'compound_cases':compounds,'predicate_candidates_pending_approval':predicate_candidates}
    return {**body,'fingerprint':fingerprint(body)}


def verified_review_sources():
    """Authenticate existing local review sources through the tracked original manifest."""
    from tests.predicate_historical_fixtures import verified_paths
    _,manifest_path=verified_paths()
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    names=['reports/unresolved_independent_review_packet_v5.json','reports/unresolved_gold_decision_review_v3.json']
    values=[]
    for name in names:
        path=ROOT/name
        if not path.is_file() or sha(path)!=manifest['protected_hashes'][name]:
            raise ValueError('Missing or unauthenticated original review source: '+name)
        values.append(json.loads(path.read_text(encoding='utf-8')))
    return tuple(values)


def review_companion(packet,source):
    """Exposed context companion; never modify/import the blinded V5 decisions."""
    from taxonomy_discovery.unresolved_review_packet import QUESTIONS
    if packet.get('source_fingerprint')!=source.get('source_fingerprint'):
        raise ValueError('Review source identity differs')
    if packet.get('packet_fingerprint')!=fingerprint({k:v for k,v in packet.items() if k!='packet_fingerprint'}):
        raise ValueError('Original V5 packet seal differs')
    cases=packet['cases']
    if len(cases)!=38 or len({tuple(c['key']) for c in cases})!=38:
        raise ValueError('Exactly 38 distinct pending original cases required')
    taxonomy_snapshot=taxonomy.get_default_taxonomy()
    contracts=taxonomy_snapshot.by_id()
    recovered={tuple(c['key']):c for c in source['cases']};rows=[]
    for case in cases:
        original=recovered[tuple(case['key'])];frozen=case['frozen_input'];context=original['source_context']
        if original['exact_requirement']!=frozen['requirement_text'] or original['input_fingerprint']!=case['input_fingerprint']:
            raise ValueError('Frozen wording/input identity differs')
        jd=source['sources'].get(str(case['key'][0]));parents=[]
        if jd:
            raw=jd['raw_jd_text']
            actual=hashlib.sha256(raw.encode('utf-8')).hexdigest()
            if actual!=jd['raw_jd_sha256'] or actual!=case['source_provenance']['original_jd_sha256']:
                raise ValueError('Original JD hash differs')
            for p in context.get('parent_provenance',[]):
                if p.get('raw_parent_verified_in_jd'):
                    if p['raw_parent_text'] not in raw:
                        raise ValueError('Claimed original parent is not grounded')
                    parents.append({k:deepcopy(p.get(k)) for k in ('parent_text','raw_parent_text','parent_occurrence_id','grounding')})
        child={'text':frozen['requirement_text'],'importance':frozen['importance']}
        native=summary(resolve(child))
        question=QUESTIONS.get(original['number'],
            'Does the exact frozen wording satisfy a complete existing capability predicate, a pure approved technology identity, or neither? Identify the exact source span and any missing scope; defer rather than infer ownership or credit.')
        rows.append({'review_case_number':case['review_case_number'],'key':deepcopy(case['key']),
            'input_fingerprint':case['input_fingerprint'],'original_requirement':frozen['requirement_text'],
            'original_frozen_native_result':deepcopy(frozen['resolver']),
            'current_child_only_recognition':native,
            'original_source_provenance':deepcopy(case['source_provenance']),
            'additional_verified_scope_NOT_PART_OF_V5':parents,
            'proposed_candidates_NOT_APPROVED':deepcopy(frozen['taxonomy_candidates']),
            'current_contracts_NOT_HISTORICAL':[{
                'capability_id':c['capability_id'],'taxonomy_version':taxonomy_snapshot.version,
                'label':contracts[c['capability_id']].get('label'),
                'requirement':deepcopy(contracts[c['capability_id']]['requirement']),
                'does_not_prove':deepcopy(contracts[c['capability_id']].get('does_not_prove',[]))}
                for c in frozen['taxonomy_candidates'] if c.get('capability_id') in contracts],
            'question_requiring_human_judgment':question,
            'reviewer_judgment':{'decision':'','source_spans':[],'uncertainty':'','reviewer':'','reviewed_at':''},
            'review_state':'PENDING','evidence_credit_decided':False})
    body={'companion_version':'phase3a-exposed-context-review-companion-v1',
        'original_packet_fingerprint':packet['packet_fingerprint'],'source_fingerprint':packet['source_fingerprint'],
        'current_taxonomy_version':taxonomy_snapshot.version,
        'current_taxonomy_bytes_sha256':sha(ROOT/'taxonomy/capability_taxonomy_v1.json'),
        'is_independent_blind_review':False,'eligible_for_gold_import':False,
        'instructions':['Original V5 packet/blank receipts remain unchanged. This exposed-context companion is not blind review or gold.',
            'Additional source scope is separately authenticated and must not silently enter a child-only V5 judgment.',
            'Candidates and questions are review proposals, never approved identities, publication or applicant evidence.',
            'Record a separate context-aware policy decision; use existing governance for any later definition or credit change.'],
        'cases':rows}
    return {**body,'fingerprint':fingerprint(body)}


def companion_markdown(companion):
    lines=['# Phase 3A — 38 pending cases: context-aware review companion','',
        '**Exposed-context review; not independent blind gold. All 38 judgments remain PENDING.**','',
        'Original packet: `'+companion['original_packet_fingerprint']+'`. No candidate evidence is included.','']
    for c in companion['cases']:
        lines+=['## '+str(c['review_case_number'])+' — Job '+str(c['key'][0])+' / `'+c['key'][1]+'`','',
            '**Original frozen wording:** '+safe(c['original_requirement'],'original_requirement'),'',
            '**Current child-only recognition:** '+str(c['current_child_only_recognition']['knowledge_status'])+
            '; capability `'+str(c['current_child_only_recognition']['capability_id'])+'`. Missing source scope was not borrowed.','',
            '**Specific decision:** '+c['question_requiring_human_judgment'],'',
            '**Existing candidates (not approved):** '+', '.join(str(r.get('capability_id')) for r in c['proposed_candidates_NOT_APPROVED'])+'.','',
            '**Separately verified original scope (outside V5):**','']
        for p in c['additional_verified_scope_NOT_PART_OF_V5']:
            lines+=['> '+safe(p.get('raw_parent_text') or '', 'raw_parent_text').replace('\n',' '),'']
        if not c['additional_verified_scope_NOT_PART_OF_V5']:lines+=['Unavailable; do not infer a parent.','']
        lines+=['**Judgment:** PENDING. Reviewer / exact spans / uncertainty / time: blank.','']
    catalog={r['capability_id']:r for c in companion['cases'] for r in c['current_contracts_NOT_HISTORICAL']}
    lines+=['## Current contract catalog — not historical','',
        'Current taxonomy bytes: `'+companion['current_taxonomy_bytes_sha256']+'`. '+
        'These definitions support context-aware review; they do not reinterpret the archived taxonomy or approve a match.','']
    for cid,contract in sorted(catalog.items()):
        matcher=contract['requirement']
        lines+=['### `'+cid+'` — '+str(contract['label']),'',
            'Version: '+contract['taxonomy_version']+'. Native requirement terms: '+', '.join(matcher.get('any_terms',[]))+'.','',
            'Additional groups/guards: `'+json.dumps({k:v for k,v in matcher.items() if k!='any_terms'},sort_keys=True)+'`.','',
            'Does not prove: '+'; '.join(contract['does_not_prove'])+'.','']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    main()
