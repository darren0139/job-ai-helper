"""Versioned offline JD-source exports; no recognition policy or persistence.

Saved projections and newly canonicalized raw JDs are different views. Missing
inputs are never borrowed across them. Candidate evidence is never exported.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from analysis_stability.stable_evidence_scoring import canonicalise_requirements
from job_discovery.matching import current_match_versions
from tailoring.phase6d6_structured_matching import technology_requirement_structure
from tailoring.production_requirement_resolver import resolve_requirement_with_production_knowledge
from taxonomy_discovery.offline_execution import offline_execution

VERSION = 'source-aware-unresolved-inventory-v1'
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = Path(__file__).with_suffix('.schema.json')
FIXTURES = ('tests/fixtures/per_jd_scoring_audit.json',
            'tests/fixtures/confirmed_taxonomy_coverage.json')
JD_FIELDS = ('requirement_id','text','atomic_focus','atomic_focus_key','importance',
    'sources','parent_text','source_provenance','decomposition','scope',
    'parent_requirement_id','atomic_group_id','group_weight_fraction',
    'scoring_parent_occurrence_id','is_atomic','semantic_type','score_eligible',
    'evidence_eligible','tailoring_eligible','eligibility_rule','credential_policy',
    'explicit_only_requirement','structured_match_kind','structured_match_group_mode',
    'structured_match_required_terms','capability_recognition_rule')
PARENT_FIELDS = ('parent_occurrence_id','parent_text','raw_parent_text','source',
    'profile_field','source_group_fraction','grounding','contributes_scoring_allocation')
TEXT_KEYS = {'text','atomic_focus','parent_text','raw_parent_text','sentence_text',
             'matched_phrase','matched_alias','matched_term','normalized_requirement_text'}
PRIVACY = re.compile(r'(?i)[\w.+-]+@[\w.-]+\.[a-z]{2,}|\bsk-[\w-]{10,}|'
    r'\bbearer\s+\S+|\b(?:api[_ -]?key|password|token)\s*[:=]\s*\S+|'
    r'(?<![\w])\+?\d[\d ()-]{7,}\d(?![\w])')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def redact(value, key=None):
    if isinstance(value,dict):
        return {k:redact(v,k) for k,v in value.items()}
    if isinstance(value,list):
        return [redact(v,key) for v in value]
    identifier = key and (key.endswith(('_id','_ids','_fingerprint','_sha256')) or
                         key in ('schema_version','export_fingerprint','fixture_sha256'))
    if not identifier and isinstance(value,str):
        return PRIVACY.sub('[REDACTED]',value)
    return value


def knowledge_identity():
    paths=('taxonomy/capability_taxonomy_v1.json','taxonomy/technology_registry_v1.json',
        'tailoring/production_requirement_resolver.py','tailoring/requirement_scope.py',
        'tailoring/capability_taxonomy.py','tailoring/phase6d6_structured_matching.py',
        'analysis_stability/stable_evidence_scoring.py')
    return {'versions':current_match_versions(),
            'artifact_sha256':{p:file_sha(ROOT/p) for p in paths}}


def fixture_views(paths=FIXTURES):
    """Read ONLY the two tracked fixture formats; no arbitrary file or DB source."""
    views=[]
    for path in paths:
        if path not in FIXTURES:
            raise ValueError('Stage 1 accepts only the two tracked fixtures')
        data=json.loads((ROOT/path).read_text(encoding='utf-8'))
        for index,job in enumerate(data['snapshot']['audit']['corpus']['jobs']):
            base=dict(job_id=job['job_id'],cohort='saved_primary' if path==FIXTURES[0] else 'saved_alternate',
                requirements=deepcopy(job['baseline_stable_analysis']['canonical_requirements']),
                versions={k:v for k,v in job['baseline_stable_analysis'].items() if k.endswith('_version')},
                raw_jd_text=job.get('frozen_inputs',{}).get('raw_jd_text'),
                # These fixtures contain neither original profile nor full evidence context.
                original_profile_available=False,full_evidence_available=False,
                references=[{'fixture':path,'fixture_sha256':file_sha(ROOT/path),
                    'job_index':index,'row_container':'baseline_stable_analysis.canonical_requirements'}])
            views.append(base)
            if base['raw_jd_text']:
                with offline_execution('Source inventory forbids network'):
                    canonical=canonicalise_requirements({},raw_jd_text=base['raw_jd_text'])
                views.append({**deepcopy(base),'cohort':'raw_jd_only',
                    'requirements':canonical['requirements'],
                    'versions':{**current_match_versions(),**{k:v for k,v in canonical.items() if k.endswith('_version')}},
                    'references':[{**deepcopy(ref),'row_container':
                        'DERIVED: canonicalise_requirements({}, frozen_inputs.raw_jd_text).requirements'}
                        for ref in base['references']]})
    return views


def source_state(requirement, raw):
    parents=requirement.get('source_provenance') or []
    issues=[]
    normal=lambda s:' '.join(str(s or '').split())
    if not parents:
        issues.append('SOURCE_PROVENANCE_UNAVAILABLE')
    if not raw:
        issues.append('RAW_JD_UNAVAILABLE_IN_THIS_VIEW')
    for index,parent in enumerate(parents):
        if any(not parent.get(k) for k in ('parent_occurrence_id','parent_text','raw_parent_text','source')):
            issues.append(f'PARENT_{index}_REQUIRED_FIELDS_MISSING')
        if raw and parent.get('raw_parent_text') and normal(parent['raw_parent_text']) not in normal(raw):
            issues.append(f'PARENT_{index}_RAW_GROUNDING_NOT_LOCATED')
    return {'status':'COMPLETE_AVAILABLE_SOURCE' if not issues else 'PARTIAL_SOURCE_CONTEXT',
            'blockers':issues,'parent_occurrence_count':len(parents)}


def allocations(records):
    """Native source fractions, not newly invented parent or child weights."""
    groups=defaultdict(list)
    for record in records:
        for parent in record['requirement'].get('source_provenance') or []:
            if not parent.get('parent_occurrence_id'):
                continue  # Still retained in requirement; source completeness reports it.
            groups[parent['parent_occurrence_id']].append(parent)
    result=[]
    for pid,parents in sorted(groups.items()):
        contributors=[p for p in parents if p.get('contributes_scoring_allocation',True)]
        values=[p.get('source_group_fraction') for p in contributors]
        if any(type(v) not in (float,int) or v<0 for v in values):
            state='UNAVAILABLE_OR_INVALID_FRACTION'; total=None
        else:
            total=round(sum(values),6)
            state=('NON_CONTRIBUTING_PROVENANCE_ONLY' if not contributors else
                   'CONSERVED' if abs(total-1)<0.00001 else
                   'OVERALLOCATED' if total>1 else 'PARTIAL_RETAINED_ALLOCATION')
        result.append({'parent_occurrence_id':pid,'contributing_sum':total,'status':state,
                       'source_occurrence_count':len(parents)})
    return result


def record_for(row, view, view_id):
    requirement={k:deepcopy(row[k]) for k in JD_FIELDS if k in row}
    if 'source_provenance' in requirement:
        requirement['source_provenance']=[{k:deepcopy(p[k]) for k in PARENT_FIELDS if k in p}
                                         for p in requirement['source_provenance']]
    original=digest(requirement)
    with offline_execution('Source inventory forbids network'):
        native=resolve_requirement_with_production_knowledge(requirement)
        structure=technology_requirement_structure(requirement)
    source=source_state(requirement,view.get('raw_jd_text'))
    diagnostics={k:deepcopy(v) for k,v in native['taxonomy_diagnostics'].items() if k!='capability_record'}
    if native['resolution_source']=='technology_identity':
        resolution_reason=(native.get('identity_scope') or {}).get('reason')
    elif native['resolution_source']=='technology_registry':
        resolution_reason=(native.get('registry_resolution') or {}).get('reason')
    elif native['knowledge_status']=='CAPABILITY_RESOLVED':
        resolution_reason=diagnostics.get('reason')
    else:
        resolution_reason='UNRESOLVED_AFTER_NATIVE_KNOWLEDGE_ATTEMPTS'
    receipt=None
    if view['cohort']!='raw_jd_only' and 'match_label' in row:
        receipt={'label':row['match_label'],'value':row.get('match_value'),
                 'selected_row_count':len(row.get('evidence') or []),
                 'meaning':'STORED_RECEIPT_ONLY_NOT_CURRENT_EVIDENCE_EVALUATION'}
    missing=[]
    if not view.get('original_profile_available'):
        missing.append('ORIGINAL_EXTRACTED_JD_PROFILE_UNAVAILABLE')
    if not view.get('full_evidence_available'):
        missing.append('COMPLETE_FROZEN_CANDIDATE_EVIDENCE_UNAVAILABLE')
    historical=list(missing)
    if view['cohort']=='raw_jd_only':
        historical.append('DERIVED_RAW_ONLY_VIEW_IS_NOT_HISTORICAL_ANALYSIS')
    elif not view['versions']:
        historical.append('ORIGINAL_ANALYSIS_VERSIONS_UNAVAILABLE')
    elif view['versions'].get('scoring_version')!=current_match_versions()['scoring_version']:
        historical.append('HISTORICAL_IMPLEMENTATION_NOT_REPRODUCED_BY_CURRENT_CODE')
    if not view.get('raw_jd_text'):
        missing.append('RAW_JD_UNAVAILABLE_IN_THIS_VIEW')
        historical.append('RAW_JD_UNAVAILABLE_IN_THIS_VIEW')
    record={'record_id':'srcinv_'+digest([view_id,row['requirement_id'],original])[:24],
        'view_id':view_id,'job_id':view['job_id'],'requirement_id':row['requirement_id'],
        'requirement':requirement,'original_requirement_fingerprint':original,
        'native_structure':structure,
        'qualifier_observations':{
            'optional_cue':bool(re.search(r'\b(preferred|optional|advantageous|desirable|a plus)\b',row['text'],re.I)),
            'negative_cue':bool(re.search(r"\b(not|without|never|no experience|do not)\b",row['text'],re.I)),
            'meaning':'LEXICAL_DIAGNOSTIC_ONLY_NATIVE_IMPORTANCE_AND_STRUCTURE_RETAINED'},
        'source_completeness':source,
        'native_resolution':{'knowledge_status':native['knowledge_status'],
            'resolution_source':native['resolution_source'],
            'capability_id':native['decision'].get('capability_id'),
            'technology_id':native.get('technology_id'),
            'reason':resolution_reason,
            'taxonomy_diagnostics':diagnostics,'registry_diagnostics':native.get('registry_resolution'),
            'identity_scope':native.get('identity_scope')},
        'evidence':{'evaluation':'NOT_RUN','inputs_available':bool(view.get('full_evidence_available')),
                    'stored_receipt':receipt,'blockers':[] if view.get('full_evidence_available') else
                    ['COMPLETE_FROZEN_CANDIDATE_EVIDENCE_UNAVAILABLE']},
        'readiness':{'native_probe_executed':True,
            'recognition':'READY_CURRENT_INPUT' if source['status']=='COMPLETE_AVAILABLE_SOURCE' else 'PARTIAL_SOURCE_CONTEXT',
            'recognition_blockers':list(source['blockers']),
            'current_full_pipeline':'BLOCKED' if missing else 'INPUTS_AVAILABLE_NOT_EXECUTED',
            'current_full_pipeline_blockers':missing,
            'historical_reproduction':'BLOCKED' if historical else 'INPUTS_AVAILABLE_NOT_EXECUTED',
            'historical_reproduction_blockers':historical},
        'stage2_diagnostic':bool(re.fullmatch(r'[·\s]*Design,\s*(?:develop|build)',row['text'],re.I)),
        'privacy':{'redacted':False,'native_diagnostics_basis':'ORIGINAL_LOCAL_JD_INPUT_BEFORE_REDACTION'}}
    clean=redact(record)
    if clean!=record:
        clean['privacy']['redacted']=True
        clean['readiness']['recognition']='BLOCKED_REDACTED_EXPORT'
        clean['readiness']['recognition_blockers'].append('EXPORTED_JD_TEXT_REDACTED')
    if digest(requirement)!=original:
        raise ValueError('Native diagnostic mutated requirement')
    clean['exported_requirement_fingerprint']=digest(clean['requirement'])
    return clean


def build_export(views):
    """Accept explicit in-memory views; never obtain missing inputs implicitly."""
    original=digest(views); grouped={}
    for view in views:
        if view.get('original_profile_available') or view.get('full_evidence_available'):
            raise ValueError('Stage 1 fixture adapter cannot certify full original profile/evidence inputs')
        # Input capabilities are deliberately bounded: evidence is never evaluated here.
        body={k:deepcopy(view[k]) for k in ('job_id','cohort','requirements','versions','raw_jd_text',
            'original_profile_available','full_evidence_available')}
        body['requirements']=sorted(body['requirements'],key=lambda r:(r['requirement_id'],digest(r)))
        key=digest(body)
        if key not in grouped:
            grouped[key]={'body':body,'references':[]}
        grouped[key]['references'].extend(deepcopy(view['references']))
    exported_views=[]; records=[]
    for key,group in sorted(grouped.items()):
        body=group['body'];vid='srcview_'+key[:24]
        canonical_ids=[r['requirement_id'] for r in body['requirements']]
        if len(set(canonical_ids))!=len(canonical_ids):
            raise ValueError('Duplicate canonical requirement ID inside one source view')
        refs={digest(r):r for r in group['references']}
        rows=[record_for(r,body,vid) for r in body['requirements']]
        ids=[r['record_id'] for r in rows]
        if len(ids)!=len(set(ids)):
            raise ValueError('Duplicate canonical requirement record inside a source view')
        raw=body.get('raw_jd_text')
        exported_views.append({'view_id':vid,'job_id':body['job_id'],'cohort':body['cohort'],
            'source_versions':body['versions'],'references':[refs[k] for k in sorted(refs)],
            'raw_jd_reference':{'available':bool(raw),'text_sha256':hashlib.sha256(raw.encode()).hexdigest() if raw else None,
                'location':'frozen_inputs.raw_jd_text' if raw else None},
            'record_ids':ids,'source_allocations':allocations(rows)})
        records.extend(rows)
    result={'schema_version':VERSION,'schema_fingerprint':file_sha(SCHEMA),
        'knowledge_identity':knowledge_identity(),'views':exported_views,'records':records,
        'counts':{'unique_jobs':len({v['job_id'] for v in exported_views}),
                  'distinct_source_views':len(exported_views),'records':len(records),
                  'duplicate_input_views':len(views)-len(grouped)}}
    if digest(views)!=original:
        raise ValueError('Source views mutated')
    result['export_fingerprint']=digest(result)
    validate_export(result)
    return result


def validate_export(export):
    """Schema plus referential integrity, fingerprints and allocation accounting."""
    from jsonschema import Draft202012Validator
    schema=json.loads(SCHEMA.read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(export)
    from taxonomy_discovery.source_inventory_safety import validate_safe_payload
    validate_safe_payload(export, JD_FIELDS, PARENT_FIELDS)
    if export['schema_fingerprint']!=file_sha(SCHEMA):
        raise ValueError('Schema fingerprint mismatch')
    if export['export_fingerprint']!=digest({k:v for k,v in export.items() if k!='export_fingerprint'}):
        raise ValueError('Export fingerprint mismatch')
    records={r['record_id']:r for r in export['records']}
    if len(records)!=len(export['records']):
        raise ValueError('Duplicate record identity')
    seen=[]
    if len({v['view_id'] for v in export['views']})!=len(export['views']):
        raise ValueError('Duplicate source view identity')
    for view in export['views']:
        rows=[records[r] for r in view['record_ids']]
        if any(r['view_id']!=view['view_id'] or r['job_id']!=view['job_id'] for r in rows):
            raise ValueError('Cross-view provenance mismatch')
        if allocations(rows)!=view['source_allocations']:
            raise ValueError('Source allocation receipt mismatch')
        if any(a['status'] in ('OVERALLOCATED','UNAVAILABLE_OR_INVALID_FRACTION') for a in view['source_allocations']):
            raise ValueError('Invalid parent allocation')
        seen.extend(view['record_ids'])
    if sorted(seen)!=sorted(records):
        raise ValueError('Orphaned or repeated view records')
    for record in records.values():
        if record['requirement_id']!=record['requirement']['requirement_id']:
            raise ValueError('Canonical identity mismatch')
        if digest(record['requirement'])!=record['exported_requirement_fingerprint']:
            raise ValueError('Requirement fingerprint mismatch')
        if not record['privacy']['redacted'] and record['original_requirement_fingerprint']!=digest(record['requirement']):
            raise ValueError('Unredacted source fingerprint mismatch')
        if record['source_completeness']['parent_occurrence_count']!=len(record['requirement'].get('source_provenance') or []):
            raise ValueError('Parent occurrence count mismatch')
        ready=record['readiness']
        if ready['recognition']=='READY_CURRENT_INPUT' and (record['source_completeness']['status']!='COMPLETE_AVAILABLE_SOURCE' or ready['recognition_blockers'] or record['privacy']['redacted']):
            raise ValueError('Unsupported recognition readiness')
        for field in ('current_full_pipeline','historical_reproduction'):
            if (ready[field]=='BLOCKED')!=bool(ready[field+'_blockers']):
                raise ValueError('Replay status/blockers disagree')
        if record['evidence']['inputs_available']:
            raise ValueError('Full evidence is not available through the Stage 1 fixture adapter')
    if export['counts']['records']!=len(records) or export['counts']['distinct_source_views']!=len(export['views']) or export['counts']['unique_jobs']!=len({v['job_id'] for v in export['views']}):
        raise ValueError('Count mismatch')
    return True


def compact_summary(export):
    cohorts={}
    for cohort in sorted({v['cohort'] for v in export['views']}):
        vids={v['view_id'] for v in export['views'] if v['cohort']==cohort}
        rows=[r for r in export['records'] if r['view_id'] in vids]
        cohorts[cohort]={'rows':len(rows),'jobs':len({r['job_id'] for r in rows}),
            'source_completeness':dict(Counter(r['source_completeness']['status'] for r in rows)),
            'recognition_readiness':dict(Counter(r['readiness']['recognition'] for r in rows)),
            'knowledge_status':dict(Counter(r['native_resolution']['knowledge_status'] for r in rows)),
            'current_full_pipeline':dict(Counter(r['readiness']['current_full_pipeline'] for r in rows)),
            'blockers':dict(Counter(b for r in rows for b in r['readiness']['current_full_pipeline_blockers']))}
    references={r['fixture']:r['fixture_sha256'] for v in export['views'] for r in v['references']}
    byview={v['view_id']:v for v in export['views']}
    return {'artifact_kind':'compact_summary_not_full_export',
        'summary_version':'source-aware-inventory-summary-v1',
        'schema_version':VERSION,'schema_fingerprint':export['schema_fingerprint'],
        'export_fingerprint':export['export_fingerprint'],'counts':export['counts'],
        'sources':references,
        'knowledge_identity':export['knowledge_identity'],'cohorts':cohorts,
        'stage2_cases':[{'job_id':r['job_id'],'requirement_id':r['requirement_id'],
            'view_id':r['view_id'],'cohort':byview[r['view_id']]['cohort'],
            'source_references':byview[r['view_id']]['references'],
            'text':r['requirement']['text'],'action':'DIAGNOSE_ONLY_NO_REPAIR'}
            for r in export['records'] if r['stage2_diagnostic']],
        'evidence_evaluations_run':0,'full_pipeline_replays_run':0,
        'historical_snapshots_modified':0}
