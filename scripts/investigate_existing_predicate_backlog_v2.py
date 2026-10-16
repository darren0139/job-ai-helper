"""Read-only V2 investigation. Freeze V1 cohort before individual diagnostics."""
import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import re
from unittest.mock import patch

os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')
os.environ.setdefault('CAPABILITY_RAG_MODE', 'off')
from scripts import cluster_unresolved_backlog_v1 as c
from tailoring import capability_taxonomy as t
from taxonomy_discovery.technology_registry import get_default_registry
from taxonomy_discovery.unresolved_adjudication import fingerprint

ROOT = c.ROOT
VERSION = 'existing-predicate-investigation-v2'
MANIFEST = ROOT/'reports/unresolved_existing_predicate_investigation_v2_manifest.json'
REPORT = ROOT/'reports/unresolved_existing_predicate_investigation_v2.json'
DOC = ROOT/'docs/unresolved_existing_predicate_investigation_v2.md'
V1_FILES = ('docs/unresolved_backlog_clustering_v1.md',
            'reports/unresolved_backlog_clustering_v1.json',
            'scripts/cluster_unresolved_backlog_v1.py',
            'tests/test_unresolved_backlog_clustering_v1.py')
HISTORICAL_FIELDS = ('capability_id', 'capability_resolution', 'knowledge_status',
    'knowledge_resolution', 'capability_retrieval', 'capability_reselection',
    'taxonomy_diagnostics', 'taxonomy_cap', 'taxonomy_rejection')

# Individually inspected development-only meanings. These are analyst opinions,
# never reviewer decisions, routes, executable policies, or gold labels.
REVIEWS = {
 (45,'req_f1535cbe7edd'):('NOT_APPLICABLE','NO',
    'Application invitation permits relevant skillsets and interests; it does not demand explicit motivation. The observer pluralizes interest into interests.',
    'Turning invitation boilerplate into an explicit subjective qualification.'),
 (48,'req_89ae867baae9'):('PARTIALLY_APPLICABLE','NO',
    'Database design covers design data models only. Statistics, ML, analysis and dashboards remain distinct obligations. Stakeholders are dashboard beneficiaries, not a stated collaboration activity.',
    'One database or stakeholder term crediting the complete analytics/dashboard obligation.'),
 (48,'req_b50b5ed998f8'):('NOT_APPLICABLE','NO',
    'Helping lecturers and stakeholders obtain learning insights is an analysis deliverable, not an affirmative stakeholder collaboration requirement. U+FFFD is already in original stored JD/source; no current parser corruption is proved.',
    'Beneficiary nouns being treated as collaboration; silently repairing an unknown original character.'),
 (146,'req_9270e95898c8'):('FULLY_APPLICABLE','NEEDS_MORE_EVIDENCE',
    'One bounded RESTful API design/development obligation fits the capability meaning, with no distributed-architecture or product-name exclusion. Native restful api is not a whole match for RESTful APIs. No approved plural-equivalence rule was found.',
    'A global stemming change could match product names or credit incomplete REST/gRPC requirements.'),
 (158,'req_07301e1d0303'):('PARTIALLY_APPLICABLE','NO',
    'Relations with named internal/external stakeholders fit collaboration, but building workflows remains an additional obligation. Recognizing a collaboration facet must not qualify the entire workflow requirement.',
    'Collaboration proof granting workflow implementation credit.'),
 (158,'req_5e1c1de91a3c'):('PARTIALLY_APPLICABLE','NO',
    'Explicit collaboration is present, together with building mission-ready tools/platforms. Stakeholder collaboration alone does not prove those deliverables.',
    'A stakeholder match completing tools/platform implementation.'),
 (163,'req_44c51cdd0d6c'):('FULLY_APPLICABLE','NEEDS_MORE_EVIDENCE',
    'Engaging/updating management and users about pain-points and requirements describes a bounded stakeholder interaction. Native stakeholder does not match Stakeholders. Forward planning supplies purpose; no independent implementation is named. Human confirmation of this scope and plural policy remains required.',
    'Recognizing arbitrary stakeholder mentions as active collaboration.'),
 (240,'req_51d8311de0cb'):('PARTIALLY_APPLICABLE','NO',
    'Stakeholder influence and cross-team collaboration fit a facet; influence at senior-leadership level and the engineering/product/policy qualification exceed that facet. The strict cross-functional whole-sentence grammar is not satisfied.',
    'Basic collaboration credit proving senior influence or all cross-functional scope.'),
 (360,'req_db0a9e351a71'):('PARTIALLY_APPLICABLE','NO',
    'Production environment handling covers the production facet only; development plus performance, safety and reliability troubleshooting remain obligations. The original troubleshooting parent and both half-weight children are retained, so omission/corruption is not established.',
    'Live-environment handling implying complete safety/reliability troubleshooting.'),
 (562,'req_cc010ff84b86'):('PARTIALLY_APPLICABLE','NO',
    'Production environment is one context of AI deployment/performance validation in both test and production. Live handling does not prove AI validation. Non-game live-environment evidence is capped at weak by the existing contract; no applicant credit is assessed here.',
    'Environment mention substituting for AI deployment validation or game-domain evidence.'),
 (562,'req_e275bf93ddcb'):('PARTIALLY_APPLICABLE','NO',
    'Customer/stakeholder work is explicit, but delivering end-to-end SATCOM solutions adds substantive technical obligations. The original three-sentence parent and unheaded role-obligation grounding are retained; two contributing children still sum to one.',
    'Collaboration evidence proving SATCOM development, integration and delivery.'),
 (619,'req_0987348575fd'):('PARTIALLY_APPLICABLE','NO',
    'API and data-model design each cover a facet. Java/Spring Boot, business rules and reliable integrations across named systems are not covered by either predicate. Such-as technology wording must not become a universal mapping.',
    'API/database proof crediting business rules, language/framework and all integration domains.'),
 (619,'req_66b8a305bdf8'):('PARTIALLY_APPLICABLE','NO',
    'REST API and relational-database facets do not cover hands-on Java/Spring Boot experience, SQL, data modelling and transaction patterns. Including introduces examples/context; it does not prove independently allocated mandatory children.',
    'API/database recognition granting hands-on Java/Spring Boot or transaction-processing qualification.'),
}

REGRESSION_PROPOSAL = {
 'status':'Design only; human authorization and version/currentness review before runtime change',
 'direction':'Start with bounded requirement-side REST API / RESTful API plural recognition, not global stemming and not new capability mappings. Stakeholder recognition needs affirmative interaction/scope review separately.',
 'positive':['The frozen Job146 bounded RESTful APIs obligation; singular RESTful API and REST API controls'],
 'negative':['Amazon Web Services product name; API-adjacent distributed architecture; beneficiary-only stakeholder nouns; application interests invitation'],
 'partial':['API plus database/business-rule/integration obligation; collaboration plus implementation; live environment plus AI validation'],
 'scope':['REST and gRPC both mandatory vs REST or gRPC alternatives; familiarity vs implementation; preferred vs required; absent or conflicting parent grounding; negated API work'],
 'stability':['Keep one conserved parent allocation; deterministic output; no evidence promotion from recognition; explicit gRPC completeness; no invented registry relationships; Phase8 verified-claim lineage unchanged; Phase9E project selection unchanged; review existing version/currentness mechanism before behavioral edits'],
 'missing_approval':'Approved plural-equivalence and complete-scope policy. Exact approved terms currently exclude these plurals, so semantic benefit is not proof of a contract violation.',
 'confirmed_development_defect_impact':0,
 'plausible_development_scope':['Job146 RESTful APIs','Job163 affirmative stakeholder interaction'],
 'broader_impact':'Unknown; do not extrapolate to 449 development occurrences',
 'protected_benchmark_impact':'Unevaluated; protected examples not used as development controls'}


def seal(value):
    return {**value, 'fingerprint': fingerprint(value)}


def read_sealed(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if value['fingerprint'] != fingerprint({k:v for k,v in value.items() if k!='fingerprint'}):
        raise ValueError('Fingerprint mismatch: '+str(path))
    return value


def safe_history(value):
    """Retain requirement diagnostics; never export applicant evidence payloads."""
    if isinstance(value, dict):
        return {k:safe_history(v) for k,v in value.items()
                if not any(word in k.lower() for word in ('evidence','resume','profile','claim','document'))}
    if isinstance(value, list):return [safe_history(x) for x in value]
    return deepcopy(value)


def assert_preserved(manifest, db):
    if c.sha(db)!=manifest['database_sha256']:raise ValueError('Database changed; cohort cannot be substituted')
    for name, expected in manifest['protected_hashes'].items():
        if c.sha(ROOT/name)!=expected:raise ValueError('Protected bytes changed: '+name)


def active_records(jobs, snapshots):
    jobmap = {j['id']:j for j in jobs};latest = {}
    for s in snapshots:
        jid=s['discovered_job_id']
        if jid not in latest or s['id']>latest[jid]['id']:latest[jid]=s
    records=[]
    for jid,s in sorted(latest.items()):
        j=jobmap.get(jid)
        if not j or j['lifecycle_status']!='active' or j['content_hash']!=s['job_content_hash']:continue
        for req in c.canon(s):
            records.append({'job_key':f'job:{jid}', 'job_id':jid, 'snapshot_id':s['id'],
                'source_table':'job_match_snapshots', 'source_versions':{k:s.get(k) for k in
                ('scoring_version','taxonomy_version','match_version','created_at')},
                'requirement':req, 'raw_jd_text':j['description'],
                'content_hash':s['job_content_hash'], 'canonical_rows_sha256':c.sha_text(s['requirements_json'])})
    return records


def reconstruct(records, protected, resolve=c.resolve_requirement_with_production_knowledge):
    captured=[]
    # Reuse the exact V1 analyze selection/deduplication/quarantine, not a new selector.
    original=c.clusters
    def collect(rows):captured.extend(deepcopy(rows));return original(rows)
    with patch.object(c,'clusters',side_effect=collect):
        stats=c.analyze(records,protected,resolve=resolve)
    rows=[r for r in captured if 'existing_predicate_observations' in r['dimensions']]
    return rows,stats


def validate_cohort(cases, expected_count=13, expected_jobs=9):
    keys={(r['job_id'],r['requirement_id']) for r in cases}
    if len(cases)!=expected_count or len(keys)!=expected_count or len({r['job_id'] for r in cases})!=expected_jobs:
        raise ValueError('Original cohort mismatch; stop before causal conclusions')
    if len({r['normalized_text_fingerprint'] for r in cases})!=expected_count:
        raise ValueError('Original unique wording mismatch')
    if not all(r['parent_source_available'] and r['parent_provenance_verified'] for r in cases):
        raise ValueError('Original parent corroboration mismatch')


def freeze(db):
    if MANIFEST.exists():raise ValueError('Preserve frozen manifest; no overwrite')
    prior=read_sealed(ROOT/V1_FILES[1]);before=c.sha(db)
    if before!=prior['database_sha256_before']:raise ValueError('V1 database bytes changed; cannot reconstruct exact cohort')
    hashes={**prior['protected_hashes'], **{name:c.sha(ROOT/name) for name in V1_FILES}}
    for name,key in ((V1_FILES[2],'script_sha256'),(V1_FILES[3],'tests_sha256')):
        if hashes[name]!=prior[key]:raise ValueError('V1 reconstruction implementation changed')
    jobs,snapshots,_,info=c.read_database(db)
    records=active_records(jobs,snapshots);protected=c.protected_sources()
    rows,stats=reconstruct(records,protected)
    expected=prior['scopes']['active_same_hash']
    if stats!=expected:raise ValueError('V1 active inventory differs; no substitute cohort')
    validate_cohort(rows)
    lookup={(r['job_id'],r['requirement']['requirement_id']):r for r in records}
    cases=[]
    for row in sorted(rows,key=lambda r:(r['job_id'],r['requirement_id'])):
        record=lookup[row['job_id'],row['requirement_id']];req=record['requirement']
        inp={k:deepcopy(req[k]) for k in c.FIELDS if k in req}
        if any(c.unsafe_text(s.get('raw_parent_text','')) for s in inp.get('source_provenance',[])):
            raise ValueError('Unsafe source surface; stop instead of changing cohort')
        siblings=[r['requirement'] for r in records if r['job_id']==row['job_id'] and
            r['requirement'].get('scoring_parent_occurrence_id')==req.get('scoring_parent_occurrence_id')]
        cases.append({**row, 'input':inp,'input_fingerprint':fingerprint(inp),
            'snapshot_id':record['snapshot_id'],'content_hash':record['content_hash'],
            'canonical_rows_sha256':record['canonical_rows_sha256'],
            'original_jd_sha256':c.sha_text(record['raw_jd_text']),
            'historical':{k:safe_history(req[k]) for k in HISTORICAL_FIELDS if k in req},
            'historical_recorded_unresolved':c.stored_unresolved(req),
            'historical_row_fields':sorted(req),
            'parent_allocation_receipts':[{'requirement_id':r['requirement_id'],
                'group_weight_fraction':r.get('group_weight_fraction')} for r in siblings],
            'source_fingerprint':fingerprint({'input':inp,'snapshot_id':record['snapshot_id'],
                'jd_sha256':c.sha_text(record['raw_jd_text']),'content_hash':record['content_hash']})})
    manifest=seal({'schema_version':VERSION+'-manifest','v1_report_fingerprint':prior['fingerprint'],
        'selection':'Exact V1 active_same_hash analyze; development quarantine/privacy unchanged',
        'database_sha256':before,'protected_hashes':hashes,'database_read_mode':info,
        'cohort_count':len(cases),'job_count':len({r['job_id'] for r in cases}),
        'native_versions_at_selection':prior['native_knowledge_versions'],
        'freeze_boundary':'Cohort selection recheck only; per-predicate probes occur after this file is sealed',
        'cases':cases})
    assert_preserved(manifest,db)
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'frozen':13,'jobs':9,'fingerprint':manifest['fingerprint']}))


def predicate_trace(inp, record):
    """Expose existing native term tests, not an alternate resolver."""
    matcher=record['requirement'];text=' '.join([t._clean(inp.get('text')),t._clean(inp.get('atomic_focus'))])
    return {'capability_id':record['capability_id'],'contract':deepcopy(record),
        'any_term_checks':{s:t._contains(text,s) for s in matcher.get('any_terms',[])},
        'all_term_checks':{s:t._contains(text,s) for s in matcher.get('all_terms',[])},
        'all_group_checks':[{s:t._contains(text,s) for s in group} for group in matcher.get('all_groups',[])],
        'native_direct_requirement_selection':t.classify_requirement_diagnostics(inp)['capability_id'],
        'implementation_location':'tailoring/capability_taxonomy.py::classify_requirement_diagnostics/_contains',
        'exclusions_location':'does_not_prove and evidence_tiers govern applicant credit; not selector exclusions',
        'no_applicant_evidence_evaluated':True}


def probe(db):
    manifest=read_sealed(MANIFEST);assert_preserved(manifest,db)
    if REPORT.exists():raise ValueError('Preserve investigation report; no overwrite')
    taxonomy=t.get_default_taxonomy().by_id();cases=[]
    for row in manifest['cases']:
        inp=deepcopy(row['input']);before=fingerprint(inp)
        native=c.resolve_requirement_with_production_knowledge(inp)
        if fingerprint(inp)!=before:raise ValueError('Native resolver mutated input')
        cases.append({'key':[row['job_id'],row['requirement_id']], 'current':native,
            'predicate_traces':[predicate_trace(inp,taxonomy[p['capability_id']]) for p in row['predicate_observations']],
            'comparison':'UNCHANGED_UNRESOLVED' if row['historical_recorded_unresolved'] and native['status']=='unresolved'
                else 'NOW_RESOLVED' if row['historical_recorded_unresolved'] else 'NEWLY_UNRESOLVED',
            'comparison_limit':'Stored historical output vs current pure resolver; NOT executable historical replay; empty evidence is not qualification assessment'})
    report=seal({'schema_version':VERSION, 'manifest_fingerprint':manifest['fingerprint'],
        'current_versions':{'taxonomy':t.get_default_taxonomy().version,'registry':get_default_registry().version},
        'cases':cases,'protected_hashes':manifest['protected_hashes'],
        'database_sha256_before':manifest['database_sha256'],'database_sha256_after':c.sha(db),
        'model_calls':0,'network_calls':0,'database_writes':0,'scoring_recalculations':0})
    assert_preserved(manifest,db)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'probed':len(cases),'comparisons':dict(Counter(x['comparison'] for x in cases))}))


def source_anchors(inp, jd):
    result=[]
    for source in inp.get('source_provenance',[]):
        raw=source.get('raw_parent_text') or ''
        pattern=r'\s+'.join(re.escape(word) for word in raw.split())
        spans=list(re.finditer(pattern,jd)) if pattern else []
        grounding=source.get('grounding') or {}
        result.append({'parent_occurrence_id':source.get('parent_occurrence_id'),
            'raw_parent_text':raw,'raw_parent_fingerprint':fingerprint(raw),
            'grounding':deepcopy(grounding),
            'corroborated_occurrence_count':len(spans),
            'source_spans':[{'start':m.start(),'end':m.end(),
                'one_based_start_line':jd[:m.start()].count('\n')+1,
                'source_surface_sha256':c.sha_text(m.group())} for m in spans],
            'recorded_line_matches_occurrence':any(jd[:m.start()].count('\n')+1==grounding.get('line_index') for m in spans),
            'verification_limit':'Stored JD wording/occurrence corroboration; not Phase8 applicant-claim verification'})
    return result


def comparison(saved, current):
    """Compare recorded knowledge status, not historical implementation guesses."""
    if saved.get('status') not in ('resolved','unresolved'):
        return 'INSUFFICIENT_HISTORICAL_EVIDENCE'
    if current.get('status') not in ('resolved','unresolved'):return 'NOT_COMPARABLE'
    if saved['status']=='resolved' and current['status']=='unresolved':return 'NEWLY_UNRESOLVED'
    if saved['status']=='unresolved' and current['status']=='resolved':return 'NOW_RESOLVED'
    old_reason=saved.get('registry_reason');new_reason=(current.get('registry_resolution') or {}).get('reason')
    old_scope=saved.get('scope_category');new_scope=(current.get('identity_scope') or {}).get('category')
    if saved['status']=='unresolved':
        if (old_reason is not None and old_reason!=new_reason) or (old_scope is not None and old_scope!=new_scope):
            return 'BEHAVIOR_CHANGED_BUT_UNRESOLVED'
        return 'UNCHANGED_UNRESOLVED'
    return 'NOT_COMPARABLE'  # No resolved-to-resolved category requested.


def finalize(db):
    manifest=read_sealed(MANIFEST);report=read_sealed(REPORT)
    if DOC.exists() or report.get('analyst_review_complete'):raise ValueError('Preserve final review outputs')
    assert_preserved(manifest,db)
    jobs,snapshots,_,_=c.read_database(db)
    jobmap={j['id']:j for j in jobs};snapshotmap={s['id']:s for s in snapshots}
    contracts={};findings=[]
    for case,row in zip(report['cases'],manifest['cases']):
        key=tuple(case['key'])
        if key!=(row['job_id'],row['requirement_id']):raise ValueError('Probe membership drift')
        snapshot=snapshotmap[row['snapshot_id']]
        if c.sha_text(snapshot['requirements_json'])!=row['canonical_rows_sha256']:raise ValueError('Frozen source changed')
        original=next(r for r in c.canon(snapshot) if r['requirement_id']==row['requirement_id'])
        extra={k:safe_history(original[k]) for k in ('capability_resolution_source',
            'capability_taxonomy_cap_status','technology_registry_resolution') if k in original}
        old_scope=(row['historical'].get('knowledge_resolution',{}).get('identity_scope') or {}).get('category')
        saved={'status':'unresolved' if row['historical_recorded_unresolved'] else 'resolved',
            'registry_reason':extra.get('technology_registry_resolution',{}).get('reason'),'scope_category':old_scope}
        applicability,fix,meaning,risk=REVIEWS[key]
        predicate_reviews=[]
        for trace in case['predicate_traces']:
            cid=trace['capability_id'];contracts[cid]=trace['contract']
            # No matched native conjunction is concealed by the observer.
            if any(trace['any_term_checks'].values()) or trace['native_direct_requirement_selection']:
                raise ValueError('Native path differs from individually inspected no-term-match path')
            per_app=applicability
            if key==(48,'req_89ae867baae9') and cid=='collaboration.stakeholder':per_app='NOT_APPLICABLE'
            predicate_reviews.append({'capability_id':cid,'applicability':per_app,
                'native_gate':'No any_term matched; candidate skipped before evidence/exclusion evaluation',
                'semantic_contract_vs_literal_match':'Meaning assessment is analyst interpretation; approved literal predicate does not license final-s expansion',
                'required_conjunctions':trace['contract']['requirement'].get('all_terms',[]),
                'required_groups':trace['contract']['requirement'].get('all_groups',[]),
                'qualification_boundary':'Requirement recognition is distinct from implementation/familiarity evidence tiers',
                'does_not_prove':trace['contract'].get('does_not_prove',[])})
        flags=['VALID_UNRESOLVED']
        if applicability=='PARTIALLY_APPLICABLE':flags.append('PREDICATE_PARTIAL_ONLY')
        if fix=='NEEDS_MORE_EVIDENCE':flags.append('CONTEXT_OR_RELATIONSHIP_INVESTIGATION')
        anchors=source_anchors(row['input'],jobmap[row['job_id']]['description'])
        if not all(x['corroborated_occurrence_count']==1 and x['recorded_line_matches_occurrence'] for x in anchors):
            raise ValueError('Exact original occurrence cannot be corroborated')
        allocation=sum(x['group_weight_fraction'] for x in row['parent_allocation_receipts'])
        if abs(allocation-1)>1e-9:raise ValueError('Parent allocation not conserved')
        retrieval=row['historical'].get('capability_retrieval') or {}
        ids={x.get('capability_id') for x in retrieval.get('candidates',[])}
        case.update({k:deepcopy(row[k]) for k in ('job_id','requirement_id','requirement_text','importance',
            'source_reference','source_versions','snapshot_id','content_hash','input_fingerprint','source_fingerprint',
            'input','technology_alias_candidates','predicate_observations','parent_allocation_receipts')})
        case.update(historical={**row['historical'],**extra},
            recorded_historical_summary=saved,comparison=comparison(saved,case['current']),
            source_anchors=anchors,parent_allocation_sum=allocation,
            historical_candidate_retrieval={'status':retrieval.get('status'),
                'candidates':sorted(ids),'shadow_only':retrieval.get('shadow_only'),
                'influences_scoring':retrieval.get('influences_scoring'),
                'observer_candidates_retrieved':{p['capability_id']:p['capability_id'] in ids for p in row['predicate_observations']},
                'causality_limit':'Shadow retrieval occurs after pure resolution; disabled or retrieved candidates cannot force native selection'},
            applicability=applicability,predicate_reviews=predicate_reviews,findings=flags,
            fix_justified=fix,individual_review=meaning,regression_risk=risk,
            supported_function='tailoring/capability_taxonomy.py::_contains (33); classify_requirement_diagnostics (466,552-554)',
            historical_cause_limit='Saved cap unrecognised and registry reason corroborate abstention; no saved taxonomy per-term trace or executable historical replay',
            missing_evidence='Approved bounded plural recognition and human complete-scope confirmation' if fix=='NEEDS_MORE_EVIDENCE' else
                'No new runtime evidence needed to explain literal abstention; broader remediation requires a separately approved scope investigation')
        findings.append(case)
    report.pop('fingerprint')
    from analysis_stability.stable_evidence_scoring import SCORING_VERSION
    report['current_versions'].update(scorer_identification_only=SCORING_VERSION,
        resolver_separate_version=None,resolver_file_sha256=c.sha(ROOT/'tailoring/production_requirement_resolver.py'))
    report.update(analyst_review_complete=True,summary={
        'cases':13,'jobs':9,'applicability_counts':dict(Counter(x['applicability'] for x in findings)),
        'current_unresolved':sum(x['current']['status']=='unresolved' for x in findings),
        'comparisons':dict(Counter(x['comparison'] for x in findings)),
        'confirmed_current_defects':0,'confirmed_source_defects':0,'legitimate_abstentions_without_fix_recommendation':11,
        'semantic_full_cases_needing_policy_review':2,
        'interpretation':'All thirteen comply with the existing literal selector; two full semantic fits warrant separate policy review, not a proven violated rule'},
        capability_contracts=contracts,regression_proposal=REGRESSION_PROPOSAL,
        common_findings={'shared_literal_boundary_cases':13,'shared_confirmed_defects':0,
            'explanation':'Plural-only observer spans share an exact-term rejection boundary. This is not a common defect: beneficiary mentions, mixed requirements and two full semantic fits differ.'},
        preservation={'protected_files':len(manifest['protected_hashes']),'database_bytes_unchanged':True,
            'frozen_manifest_unchanged':c.sha(MANIFEST),'gold_decisions_used':False,
            'no_scoring_evidence_matching_parser_or_retrieval_executed':True},
        script_sha256=c.sha(Path(__file__)),tests_sha256=c.sha(ROOT/'tests/test_existing_predicate_investigation_v2.py'),
        next_authorization='Human review of semantic applicability and bounded REST API plural-recognition policy; separate runtime-change approval required. No YES fixes under current contract.')
    assert_preserved(manifest,db)
    report=seal(report)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    DOC.write_text(markdown(report,manifest),encoding='utf-8')
    print(json.dumps(report['summary']))


def markdown(report,manifest):
    lines=['# Existing-predicate resolver investigation V2','',
        '**Research only. Analyst interpretations are not independent gold decisions. No production fix implemented.**','',
        '## Cohort and result','',
        'Exact V1 active_same_hash inventory reconstructed with the original analyzer, latest-snapshot selection, '
        'whole-parent/near-text benchmark quarantine and privacy filters. All active inventory statistics matched '
        'the sealed V1 report. Thirteen requirements / thirteen distinct texts / nine jobs, including overlapping '
        'predicate observations counted once. Manifest was sealed before per-predicate probes.','',
        '```json',json.dumps(report['summary'],indent=2),'```','',
        'All thirteen violate no existing literal matcher rule: none contains an approved native any_term. '
        'The report-only observer accepts a final plural s; production _contains does not. This explains the '
        'current path, but not a confirmed contract violation. Two complete semantic fits deserve human policy '
        'review. Eleven other cases are partial or non-applicable; lowering unresolved counts is not justification.','',
        '## Native path and historical limits','',
        'Production resolver calls classify_requirement_diagnostics on the exact text plus atomic_focus. '
        'No approved any_term matches for any observed candidate; all all_terms/all_groups are empty. '
        'API contextual web-services variants also do not match these inputs. The selector returns '
        'no_taxonomy_requirement_rule_matched. Registry fallback matches complete candidate terms with bounded '
        'wrappers, not arbitrary technology substrings: all thirteen report no_exact_registry_alias_match. '
        'That is not proof of missing identities. Identity scope subsequently fails complete-identity qualification '
        '(seven MIXED_SCOPE, five TECHNOLOGY_PLUS_ACTIVITY, one PARSER_OR_DECOMPOSITION_BLOCKED).','',
        'Historical snapshots record unresolved/unrecognised and the same registry fallback reason. Eight older '
        'rows lack recorded knowledge/identity diagnostics; historical per-term causality cannot be reconstructed. '
        'Five newer rows retain identity scopes, which agree with current scopes. No previous implementation was '
        'executed or checked out. UNCHANGED_UNRESOLVED means recorded knowledge outcome agreement, not proof '
        'that every historical implementation branch was identical. Versions alone establish no causality.','',
        'Shadow capability retrieval follows resolution in cap_requirement_with_taxonomy. Eight rows have '
        'retrieval disabled; five retain lexical candidates. Retrieval never influences scoring/selection. '
        'A retrieved API/stakeholder candidate does not bypass native predicates. No retrieval was run here.','',
        'Empty evidence in the pure helper is not an applicant qualification assessment. Current decision labels '
        'remain diagnostics only; no evidence credits, scores, rankings, eligibility or tailoring were recomputed.','',
        '## All thirteen decisions','',
        '| Case | Exact requirement | Candidate predicates | Historical / current | Applicability | Finding | Supported function | Fix justified? | Concrete risk |',
        '|---|---|---|---|---|---|---|---|---|']
    for x in report['cases']:
        cells=[f"Job {x['job_id']} / {x['requirement_id']}",x['requirement_text'],
            ', '.join(p['capability_id'] for p in x['predicate_reviews']),
            f"UNRESOLVED / {x['current']['knowledge_status']}",x['applicability'],', '.join(x['findings']),
            '_contains → classify_requirement_diagnostics',x['fix_justified'],x['regression_risk']]
        lines.append('| '+' | '.join(s.replace('|','\\|').replace('\n',' ') for s in cells)+' |')
    for n,x in enumerate(report['cases'],1):
        lines+=['',f"### {n}. Job {x['job_id']} — {x['requirement_id']}",'',
            '> '+x['requirement_text'],'',x['individual_review'],'',
            f"**Applicability:** {x['applicability']}. **Fix:** {x['fix_justified']}. Findings: {', '.join(x['findings'])}.",'',
            f"Source: `{x['source_reference']}`; snapshot {x['snapshot_id']}, {x['source_versions']['created_at']}. "
            f"Importance {x['importance']}; content hash `{x['content_hash']}`. Input fingerprint `{x['input_fingerprint']}`.",'',
            'Historical versions: '+json.dumps(x['source_versions'])+'. Recorded cap '+x['historical']['capability_taxonomy_cap_status']+
            '; registry '+x['historical']['technology_registry_resolution']['reason']+'.','',
            'Observed exact spans: '+json.dumps(x['predicate_observations'],ensure_ascii=False)+'. '
            'All corresponding native any_term checks are false; see complete trace in JSON.','',
            'Stored shadow retrieval: '+json.dumps(x['historical_candidate_retrieval'])+'.','',
            'Current knowledge '+x['current']['knowledge_status']+'; scope '+x['current']['identity_scope']['category']+
            ': '+x['current']['identity_scope']['reason']+'. Comparison '+x['comparison']+'.','',
            'Parent receipts: '+json.dumps(x['parent_allocation_receipts'])+f"; allocation sum {x['parent_allocation_sum']}. "
            'Original raw occurrence appears once; recorded one-based source line agrees, allowing source line wrapping/bullet prefixes. '
            'This is JD occurrence corroboration, not Phase8 verified applicant evidence.','']
        for anchor in x['source_anchors']:
            lines+=['Original bounded parent/source:', '', '> '+anchor['raw_parent_text'].replace('\n','\n> '),'',
                'Grounding: '+json.dumps(anchor['grounding'],ensure_ascii=False)+'.','']
        lines+=[x['historical_cause_limit']+'. Missing evidence / next step: '+x['missing_evidence']+'.',
            'Regression risk: '+x['regression_risk'],
            'Supported current location: '+x['supported_function']+'. Registry fallback: '
            '`taxonomy_discovery/technology_registry.py::resolve_requirement_text`; identity scope: '
            '`tailoring/requirement_scope.py::technology_identity_scope`.','']
    lines+=['## Full existing contracts','',
        'These are byte-preserved native definitions, not abbreviated observer terms. any_terms is disjunctive; '
        'all_terms/all_groups are conjunctive (empty for these records). Evidence conjunctions and does_not_prove '
        'are applicant-credit boundaries, not additional exclusions executed by the requirement selector. '
        'Backend API product guards apply to contextual variants; REST/gRPC completeness applies to evidence. '
        'Subjective motivation requires explicit evidence. Live environments distinguish game evidence from '
        'non-game evidence capped at weak. None of those evidence rules was used to grant credit here.','',
        '```json',json.dumps(report['capability_contracts'],ensure_ascii=False,indent=2),'```','',
        '## Shared findings, bounded next decision and proposed controls','',
        'Common literal boundary confirmed in all thirteen; common production defect confirmed in zero. '
        'Seven stakeholder observations include beneficiaries, explicit interactions and mixed technical delivery. '
        'Three API observations comprise one bounded API obligation and two broad mixed requirements. '
        'They must not receive one uniform remedy. No source loss is established: raw parent grounding and '
        'conserved allocations remain recorded. U+FFFD and wrapped source lines are already present in stored JD; '
        'their origin is not proven to be the current parser.','',
        report['next_authorization'],'',
        '```json',json.dumps(report['regression_proposal'],indent=2),'```','',
        'No YES fix is established, so no test asserts an unapproved production promotion. The strongest next '
        'review is the exact Job146 plural API obligation, under an explicitly bounded recognition policy rather '
        'than modifying _contains globally. Approval must cover source completeness and existing '
        'version/currentness identity before behavioral edits. Unknown broader impact; protected benchmark impact '
        'unevaluated. This report must not be used as a V5 reviewer packet or human gold.','',
        '## Preservation and reproducibility','',
        f"Manifest fingerprint: `{manifest['fingerprint']}`. V1 source report: `{manifest['v1_report_fingerprint']}`. "
        f"Protected prior files: {len(manifest['protected_hashes'])}. Database SHA256: `{manifest['database_sha256']}`.",'',
        'Current versions: '+json.dumps(report['current_versions'])+'. No separate resolver version exists in '
        'this helper; its file hash is recorded as a research diagnostic, not a parallel production version system.','',
        'Run `python -B -m scripts.investigate_existing_predicate_backlog_v2 freeze`, then `probe`, then `finalize` '
        'only against absent versioned outputs and the exact V1 DB/protected bytes. Each stage fails closed on drift. '
        'Existing outputs are retained. JSON records original inputs, source anchors, full contracts, term checks, '
        'saved historical provenance and current pure outcomes.','',
        'Zero model/network/provider calls; zero DB writes, parser/evidence matching/scoring executions or '
        'production edits. No gold reads, labels, benchmark execution, commits, pushes, merges or branch changes.','']
    return '\n'.join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('freeze','probe','finalize'))
    parser.add_argument('--db',type=Path,default=ROOT/'data/applications.db')
    args=parser.parse_args(argv)
    {'freeze':freeze,'probe':probe,'finalize':finalize}[args.stage](args.db)


if __name__=='__main__':main()
