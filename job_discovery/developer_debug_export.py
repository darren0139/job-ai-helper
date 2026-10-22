"""Allowlisted, local debug bundles from retained comparison receipts only."""
import csv
import hashlib
from io import BytesIO, StringIO
import json
import re
import zipfile

from job_discovery.coordinated_sources import fingerprint
from job_discovery.coordinated_preview_model import analysis_view
from job_discovery import developer_batch_audit as batch
from analysis_stability.stable_evidence_scoring import IMPORTANCE_WEIGHTS

SCHEMA = 'developer-comparison-debug-v1'
DISPOSITIONS = {'PUBLISHED_NUMERIC', 'COMPLETE', 'ELIGIBLE_PARTIAL', 'REVIEW_REQUIRED',
                'COMPLETE_NATIVE_NONE', 'ELIGIBLE_PARTIAL_NATIVE_NONE', 'R1_EXCLUDED_NATIVE_NONE'}
CLASSIFICATIONS = {'BLANK', 'STRUCTURAL_HEADING', 'ADMINISTRATIVE_METADATA', 'AMBIGUOUS_CONTENT',
    'AMBIGUOUS_HEADING', 'CANDIDATE_QUALIFICATION', 'RESPONSIBILITY', 'PREFERRED_QUALIFICATION',
    'NON_REQUIREMENT_CONTEXT', 'NATIVE_CONTEXT'}


def _id(value):
    if isinstance(value, str) and re.fullmatch(r'(?:req|grp|ev|span|occ)_[0-9a-f]{8,64}', value):
        return value
    return None if value is None else 'digest_'+fingerprint(value)


def _enum(value, allowed):
    return value if value in allowed else 'UNRECOGNIZED'


def _importance(value):
    # Preserve exact authoritative categories; do not infer or normalize unknowns.
    return _enum(value, IMPORTANCE_WEIGHTS)


def _digest(value):
    return value if isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value) else fingerprint(value)


def _refs(row):
    return sorted([{'reference_fingerprint': fingerprint({k:e.get(k) for k in
        ('source','evidence_id','text','section')}), 'evidence_id': _id(e.get('evidence_id'))}
        for e in row.evidence], key=lambda e:e['reference_fingerprint']) if row else []


def review_rows(comparison):
    """Reuse canonical-ID joins; compare original receipt identities, not display text."""
    rows = batch.review_rows(comparison)
    maps = [{r.requirement_id:r for r in v.requirements} for v in (comparison.published,comparison.gated)]
    raw_maps = [{r['requirement_id']:r for r in a['canonical_requirements']}
                for a in (comparison.published_analysis,comparison.gated_analysis)]
    for row in rows:
        rid = row['Requirement ID']; before,after = [m.get(rid) for m in maps]
        raw_before,raw_after = [m.get(rid) for m in raw_maps]
        fields = ('text','importance','atomic_group_id','group_weight_fraction')
        row['Geometry difference'] = (before is None or after is None or
            any(raw_before.get(k)!=raw_after.get(k) for k in fields))
        row['Source difference'] = _refs(before) != _refs(after)
        row['Credit difference'] = before is None or after is None or before.contribution != after.contribution
        row['Changed or flagged'] = (row['Geometry difference'] or row['Source difference'] or
            row['Credit difference'] or row['Conflict'] or row['Withheld'] or row['Published']!=row['Experimental'])
        row['Identical'] = not row['Changed or flagged']
        row['Importance'] = _importance((raw_after or raw_before).get('importance'))
        row['Source/conflict status'] = ('Conflict' if row['Conflict'] else 'Source differs' if row['Source difference']
            else 'Review required' if row['Withheld'] else 'Geometry differs' if row['Geometry difference'] else 'Same source')
        reasons = [code for code,key in (('GEOMETRY_MISMATCH','Geometry difference'),
            ('SOURCE_RECEIPT_DIFFERENCE','Source difference'),('CREDIT_DIFFERENCE','Credit difference'),
            ('CONFLICT_QUARANTINE','Conflict'),('REVIEW_REQUIRED','Withheld')) if row[key]]
        if row['Published']!=row['Experimental']: reasons.append('LABEL_DIFFERENCE')
        row['Difference'] = ', '.join(reasons) or 'Same label, allocation, credit and source'
    return rows


def summary(result):
    c=result['comparison']; rows=review_rows(c)
    geometry=any(r['Geometry difference'] for r in rows)
    comparative_withheld = result.get('mode')=='RETROSPECTIVE_FROZEN_INPUTS_V1' and geometry
    return {'total_requirements':len(rows), 'published_requirements':len(c.published.requirements),
        'experimental_requirements':len(c.gated.requirements), 'identical_rows':sum(r['Identical'] for r in rows),
        'changed_labels':sum(r['Published']!=r['Experimental'] for r in rows),
        'changed_sources':sum(r['Source difference'] for r in rows),
        'geometry_mismatches':sum(r['Geometry difference'] for r in rows),
        'requiring_review':sum(r['Withheld'] or r['Conflict'] for r in rows),
        'withheld_scores':sum(not v.score_available or comparative_withheld for v in (c.published,c.gated)),
        'comparative_geometry_withheld':comparative_withheld,
        'published':{k:v for k,v in c.published.summary().items() if k!='rating_band'},
        'experimental':{k:v for k,v in c.gated.summary().items() if k!='rating_band'}}


def filter_rows(rows, *, search='', published='All', experimental='All', discrepancy='All', review='All'):
    query=search.casefold().strip()
    return [r for r in rows if (not query or query in r['Requirement'].casefold() or query in r['Requirement ID'].casefold())
        and (published=='All' or r['Published']==published)
        and (experimental=='All' or r['Experimental']==experimental)
        and (discrepancy=='All' or (discrepancy=='Identical' and r['Identical']) or
             (discrepancy=='Changed' and r['Changed or flagged']) or r.get(discrepancy) is True)
        and (review=='All' or (review=='Requires review' and (r['Withheld'] or r['Conflict']))
             or (review=='No review flag' and not r['Withheld'] and not r['Conflict']))]


def _side(row, raw):
    if row is None: return None
    return {'label':row.label.value, 'native_label':None if row.native_label is None else _enum(str(row.native_label).upper(),
        {'DIRECT','TRANSFERABLE','WEAK','NONE','REVIEW_REQUIRED'}),
        'disposition':_enum(row.disposition,DISPOSITIONS), 'disposition_fingerprint':fingerprint(row.disposition),
        'allocation':row.allocation, 'match_value':row.match_value, 'standalone_credit':row.contribution,
        'parent_id':_id(raw.get('atomic_group_id')), 'importance':_importance(raw.get('importance')),
        'evidence_references':_refs(row), 'supported_action_count':len(row.supported_actions),
        'missing_action_count':len(row.missing_actions), 'technical_scope_fingerprint':fingerprint(row.technical_scope),
        'evidence_selection_status':'ACCEPTED_SOURCE_REFERENCES_PRESENT' if row.evidence else 'NO_ACCEPTED_SOURCE_SELECTED',
        'evaluation_receipt_fingerprint':fingerprint(row.receipt), 'conflict_quarantined':bool(row.conflict and row.conflict.get('quarantine'))}


def _metadata(receipt):
    return [{'line_index':i, 'classification':_enum(r.get('classification'),CLASSIFICATIONS),
        'admitted':r.get('admitted') is True, 'reason_fingerprint':fingerprint(r.get('reason')),
        'source_fingerprint':fingerprint(r.get('source')), 'text_fingerprint':fingerprint(r.get('raw_text'))}
        for i,r in enumerate(receipt.get('lines',[]))]


def _arithmetic(analysis, view):
    if not view.score_available: return {'available':False,'reason':'SCORE_WITHHELD'}
    from tailoring.phase8_score_explainability import build_score_breakdown
    b=build_score_breakdown(analysis)  # presentation arithmetic; never an analysis/scorer call
    numeric=('score','weight','weighted_points','numerator','denominator')
    return {'available':True,'role':'EXISTING_PUBLISHED_ARITHMETIC_EXPLANATION',
        'score_parity':b['score_parity'],'scorer_score':b['scorer_score'],
        'reconstructed_score':b['reconstructed_score'], 'unrounded_total':b['unrounded_total'],
        'components':[{k:r.get(k) for k in numeric} | {'component_index':i} for i,r in enumerate(b['components'])],
        'requirements':[{k:r.get(k) for k in ('importance_weight','effective_weight','match_value',
            'coverage_numerator_contribution','evidence_strength','overall_coverage_points',
            'overall_evidence_points','overall_point_contribution')} | {'requirement_id':_id(r['requirement_id'])}
            for r in b['requirements']]}


def build_report(loaded, result):
    """Explicit export action only. No databases, scorer, log or environment access."""
    c=result['comparison']
    from job_discovery import coordinated_preview as preview
    if (loaded['identity']!=result['identity'] or loaded.get('mode')!=result.get('mode') or loaded['request'].identity!=c.identity or
        analysis_view(c.published_analysis)!=c.published or analysis_view(c.gated_analysis)!=c.gated or
        c.published.scoring_version!=preview.native.SCORING_VERSION or c.gated.scoring_version!=preview.PROJECTED_SCORER_VERSION):
        raise ValueError('Comparison source/receipt identity differs')
    from analysis_stability import jd_metadata_policy as v22, jd_metadata_v123 as v23
    diagnostics=[]; maps=[{r.requirement_id:r for r in v.requirements} for v in (c.published,c.gated)]
    raw_maps=[{r['requirement_id']:r for r in a['canonical_requirements']} for a in (c.published_analysis,c.gated_analysis)]
    rows=review_rows(c); stats=summary(result); safe_rows=[]
    for row in rows:
        rid=row['Requirement ID']
        sides=[_side(m.get(rid),raw.get(rid,{})) for m,raw in zip(maps,raw_maps)]
        diagnostics.append({'requirement_id':_id(rid),'published':sides[0],'experimental':sides[1],
            'reason_codes':row['Difference'].split(', ') if not row['Identical'] else ['IDENTICAL_RECEIPTS'],
            'withholding_reason':'REVIEW_REQUIRED' if row['Withheld'] else
                'INCOMPATIBLE_GEOMETRY' if stats['comparative_geometry_withheld'] else None})
        safe_rows.append({'requirement_id':_id(rid), 'published_label':row['Published'], 'experimental_label':row['Experimental'],
            'published_allocation':row['Published allocation'], 'experimental_allocation':row['Experimental allocation'],
            'published_credit':None if stats['comparative_geometry_withheld'] else row['Published credit'],
            'experimental_credit':None if stats['comparative_geometry_withheld'] else row['Experimental credit'],
            'source_difference':row['Source difference'],'conflict':row['Conflict'],
            'geometry_mismatch':row['Geometry difference'],'review_required':row['Withheld'], 'identical':row['Identical']})
    context=loaded['context']
    from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint as geometry
    identities={'application_id':loaded['application_id'],'mode':_enum(result.get('mode','STRICT_CURRENT_VERSION'),
                {'STRICT_CURRENT_VERSION','RETROSPECTIVE_FROZEN_INPUTS_V1'}),
        'authority':'FROZEN_JOB_FINDER_LIBRARY', 'input_fingerprint':result['identity'],
        'fresh_request_fingerprint':c.identity, 'jd_fingerprint':fingerprint(loaded['request'].raw_jd_text),
        'original_jd_sha256':_digest(context.get('raw_jd_sha256')),
        'original_evidence_fingerprint':_digest(context.get('evidence_fingerprint')),
        'evidence_projection_fingerprint':fingerprint(loaded['request'].projection),
        'saved_reference_fingerprint':fingerprint(loaded['saved']['identity']),
        'published_geometry_fingerprint':geometry(c.published_analysis['canonical_requirements']),
        'experimental_geometry_fingerprint':geometry(c.gated_analysis['canonical_requirements']),
        'implementation_revision':preview.source_revision(),
        'archived_versions':{k:loaded['saved']['versions'].get(k) for k in ('scoring_version','capability_taxonomy_version','technology_registry_version')},
        'current_application_report_differs':bool(context.get('current_application_report_differs')),
        'current_application_session_included':False,'phase8_result_included':False}
    identities['currentness']='FROZEN_INPUTS_VERIFIED_NOT_CURRENT_SESSION_AUTHORITY'
    for key in ('discovered_job_id','source_snapshot_id'):
        identities[key]=context.get(key) if type(context.get(key)) is int and context[key]>0 else None
    # Version fields are schema identities, never arbitrary metadata values.
    for v in identities['archived_versions'].values():
        if v is not None and not re.fullmatch(r'(?:stable-evidence-v\d+\.\d+-phase\w+|phase6d-capability-taxonomy-v\d+\.\d+|technology-registry-v\d+\.\d+)',str(v)):
            raise ValueError('Unrecognized archived version identity')
    metadata={'v122':_metadata(result['metadata'][v22.SCORER_VERSION]),
              'v123':_metadata(result['metadata'][v23.SCORER_VERSION])}
    old={r['source_fingerprint']:r for r in metadata['v122']}
    changes=[{'source_fingerprint':r['source_fingerprint'],'before':old[r['source_fingerprint']]['classification'],
        'after':r['classification'],'before_admitted':old[r['source_fingerprint']]['admitted'],'after_admitted':r['admitted']}
        for r in metadata['v123'] if r['source_fingerprint'] in old and
        (r['classification'],r['admitted'])!=(old[r['source_fingerprint']]['classification'],old[r['source_fingerprint']]['admitted'])]
    warnings=[]
    if identities['current_application_report_differs']: warnings.append('CURRENT_REPORT_EXCLUDED')
    if stats['geometry_mismatches']: warnings.append('INCOMPATIBLE_REQUIREMENT_GEOMETRY')
    if stats['withheld_scores']: warnings.append('SCORE_OR_COMPARISON_WITHHELD')
    return {'schema_version':SCHEMA,'development_preview_only':True,'persistence_eligible':False,
        'source_text_included':False,'source_identity':identities,'comparison_summary':stats,
        'requirements':safe_rows,'requirement_diagnostics':diagnostics,'metadata':metadata,
        'metadata_changes':changes,'metadata_role':'CLASSIFICATION_ONLY_NO_GO',
        'published_arithmetic':_arithmetic(c.published_analysis,c.published),
        'warnings':warnings,'exceptions':[], 'historical_numeric_delta':None}


def concise_summary(report):
    s=report['comparison_summary']; identity=report['source_identity']
    def score(side):
        v=s[side]
        return 'Unavailable' if not v['score_available'] or s['comparative_geometry_withheld'] else str(v['alignment'])+'%'
    prefix='No successful comparison; counts below refer to evaluated rows, not JD length.\n' if s.get('status')=='NO_EVALUATION_RESULT' else ''
    return (prefix+f"Application {identity['application_id']} · {identity['mode']}\n"
        f"Published {score('published')} | Experimental {score('experimental')}\n"
        f"{s['total_requirements']} requirements; {s['identical_rows']} identical; {s['changed_labels']} label changes; "
        f"{s['changed_sources']} source changes; {s['geometry_mismatches']} geometry mismatches; "
        f"{s['requiring_review']} review flags; {s['withheld_scores']} withheld scores.\n"
        'Frozen Job Finder library only; current Application Session and Phase 8 excluded.\n'
        'Agreement does not establish scoring correctness. No saved analysis updated.')


def _json(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2)


def _csv(rows, fallback):
    stream=StringIO(newline=''); fields=list(rows[0]) if rows else fallback
    writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    return stream.getvalue()


def bundle(report):
    files={'comparison_summary.json':_json(report['comparison_summary']),
        'requirements.csv':_csv(report['requirements'],['requirement_id']),
        'requirement_diagnostics.json':_json({'schema_version':SCHEMA,'requirements':report['requirement_diagnostics'],
            'published_arithmetic':report['published_arithmetic'],'metadata_changes':report['metadata_changes'],
            'warnings':report['warnings'],'exceptions':report['exceptions']}),
        'source_identity.json':_json(report['source_identity']),
        'metadata_v122.csv':_csv(report['metadata']['v122'],['line_index','classification','admitted']),
        'metadata_v123.csv':_csv(report['metadata']['v123'],['line_index','classification','admitted']),
        'diagnostic_notes.md':concise_summary(report)+'\n\nShare-safe: no raw source wording. Metadata is classification-only NO-GO.\n'
            'Standalone credits are not comparable across geometry mismatches. NONE does not prove absence of experience.\n'
            'Private selected excerpts require separate opt-in and review. No raw exception payloads are exported.\n'}
    files['manifest.json']=_json({'schema_version':SCHEMA,'source_text_included':False,'development_preview_only':True,
        'application_id':report['source_identity']['application_id'],
        'input_fingerprint':report['source_identity']['input_fingerprint'],
        'requirement_count':len(report['requirements']),
        'files':{name:{'sha256':hashlib.sha256(value.encode('utf-8')).hexdigest(),
                        'bytes':len(value.encode('utf-8'))} for name,value in files.items()}})
    if sum(len(v.encode('utf-8')) for v in files.values())>16*1024*1024:
        raise ValueError('Debug bundle exceeds the bounded in-memory export size')
    output=BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,value in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,value.encode('utf-8'))
    return _json(report).encode('utf-8'),output.getvalue()


def failure_report(loaded, code):
    if code!='COMPARISON_FAILED': raise ValueError('Unknown public diagnostic exception code')
    missing={'score_available':False,'alignment':None,'counts':None}
    stats={'total_requirements':0,'published_requirements':0,'experimental_requirements':0,
        'identical_rows':0,'changed_labels':0,'changed_sources':0,'geometry_mismatches':0,
        'requiring_review':0,'withheld_scores':2,'comparative_geometry_withheld':True,
        'published':missing,'experimental':dict(missing),'status':'NO_EVALUATION_RESULT'}
    return {'schema_version':SCHEMA,'development_preview_only':True,'persistence_eligible':False,
        'source_text_included':False,'source_identity':{'application_id':loaded['application_id'],
            'input_fingerprint':loaded['identity'],'mode':_enum(loaded.get('mode','STRICT_CURRENT_VERSION'),
            {'STRICT_CURRENT_VERSION','RETROSPECTIVE_FROZEN_INPUTS_V1'}),'authority':'FROZEN_JOB_FINDER_LIBRARY'},
        'comparison_summary':stats,'requirements':[],'requirement_diagnostics':[],
        'metadata':{'v122':[],'v123':[]},'metadata_changes':[],
        'published_arithmetic':{'available':False,'reason':'NO_EVALUATION_RESULT'},
        'warnings':['NO_EVALUATION_RESULT'],'exceptions':[{'code':code}], 'historical_numeric_delta':None}


def selected_excerpts(result, selected_ids, *, opted_in=False):
    if opted_in is not True or not selected_ids: raise ValueError('Explicit selected private excerpt opt-in required')
    c=result['comparison']; ids={r.requirement_id for v in (c.published,c.gated) for r in v.requirements}
    if not set(selected_ids)<=ids: raise ValueError('Unknown selected requirement identity')
    return {'privacy':'PRIVATE_UNREDACTED_SELECTED_EXCERPTS_REVIEW_BEFORE_SHARING','source_text_included':True,
        'requirements':[{'side':side,'requirement_id':r.requirement_id,'requirement_excerpt':r.text[:2000],
            'selected_evidence_excerpts':[str(e.get('text') or '')[:2000] for e in r.evidence]}
            for side,v in (('published',c.published),('experimental',c.gated)) for r in v.requirements if r.requirement_id in selected_ids]}
