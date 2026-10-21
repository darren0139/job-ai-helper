"""Bounded, deterministic receipt audit. No scoring rules or production storage."""
import csv
from io import BytesIO, StringIO
import json
import re
import time
import zipfile

from job_discovery import developer_comparison as adapter
from job_discovery.coordinated_sources import fingerprint

SCHEMA = 'developer-synthetic-batch-audit-v1'
MAX_CASES = 38
MAX_RETAINED_BYTES = 96 * 1024 * 1024
MAX_EXPORT_BYTES = 64 * 1024 * 1024
QUICK = ('E01', 'E02', 'E04')
EXTENDED = ('E01', 'E02', 'E03', 'E04', 'E07', 'E12', 'E24', 'F01', 'B01', 'C01')


def registry():
    cases = adapter.fixtures.synthetic_cases()
    ids = [c['id'] for c in cases]
    if len(ids) != MAX_CASES or len(set(ids)) != len(ids):
        raise ValueError('Synthetic registry changed; review the case limit and presets')
    return cases


def ordered(ids):
    known = [c['id'] for c in registry()]
    if not ids or len(ids) > MAX_CASES or len(ids) != len(set(ids)) or set(ids)-set(known):
        raise ValueError('Choose 1–38 distinct registered synthetic cases')
    return [key for key in known if key in ids]


def revision():
    return adapter.selection_identity(SCHEMA)


def new_batch(ids):
    return {'schema': SCHEMA, 'revision': revision(), 'requested': ordered(ids),
            'entries': {}, 'retained_bytes': 0}


def require_current(batch):
    if batch['schema'] != SCHEMA or batch['revision'] != revision():
        raise ValueError('Batch inputs/implementation changed. Start a new batch.')
    if batch['requested'] != ordered(batch['requested']):
        raise ValueError('Invalid batch registry order')


def case_key(batch, case_id):
    return fingerprint({'revision': batch['revision'], 'case_id': case_id})


def _finding(case_id, code, identity, observed, reason, severity='REVIEW', kind='HEURISTIC_REVIEW'):
    return {'case_id': case_id, 'code': code, 'identity': identity, 'observed': observed,
            'reason': reason, 'severity': severity, 'kind': kind,
            'provenance': 'deterministic-receipt-audit-v1'}


def review_rows(comparison):
    rows = adapter.requirement_rows(comparison)
    maps = [{r.requirement_id: r for r in v.requirements} for v in (comparison.published, comparison.gated)]
    for row in rows:
        rid = row['Requirement ID']
        before, after = [m.get(rid) for m in maps]
        sources = lambda r: {(e.get('source'), e.get('evidence_id')) for e in r.evidence} if r else set()
        row.update({'Source difference': sources(before) != sources(after),
            'Conflict': bool(after and after.conflict and after.conflict.get('quarantine')),
            'Withheld': bool(after and after.label.value == 'REVIEW_REQUIRED'),
            'Missing counterpart': before is None or after is None,
            'Geometry difference': before is None or after is None or before.allocation != after.allocation})
        row['Changed or flagged'] = (row['Source difference'] or row['Conflict'] or row['Withheld']
            or row['Geometry difference'] or row['Published'] != row['Experimental'])
    return rows


def filter_requirements(rows, category):
    if category == 'All': return rows
    if category in ('DIRECT', 'WEAK', 'NONE', 'TRANSFERABLE', 'REVIEW_REQUIRED'):
        return [r for r in rows if category in (r['Published'], r['Experimental'])]
    if category == 'Changed': return [r for r in rows if r['Changed or flagged']]
    return [r for r in rows if r.get(category) is True]


def merge_selection(selected, edited, visible_ids):
    """Widget positions never become stored identities; preserve hidden IDs."""
    if {r['Requirement ID'] for r in edited} != set(visible_ids):
        raise ValueError('Selection table identity changed')
    return sorted((set(selected)-set(visible_ids)) |
                  {r['Requirement ID'] for r in edited if r['Select'] is True})


def audit_result(result):
    key = result['case_id']; c = result['comparison']; rows = review_rows(c)
    findings = []
    def flag(code, identity, observed, reason, **kwargs):
        findings.append(_finding(key, code, identity, observed, reason, **kwargs))
    from analysis_stability.stable_evidence_scoring import SCORING_VERSION
    from job_discovery.coordinated_sources import PROJECTED_SCORER_VERSION
    if c.published.scoring_version != SCORING_VERSION or c.gated.scoring_version != PROJECTED_SCORER_VERSION:
        flag('INCOMPATIBLE_SCORING_IDENTITY', 'whole_jd', {'published': c.published.scoring_version,
             'experimental': c.gated.scoring_version}, 'Comparison identities are outside this adapter contract.',
             severity='ERROR', kind='INVARIANT_VIOLATION')
    if not rows:
        flag('MISSING_REQUIREMENT_COVERAGE', 'whole_jd', {'requirements': 0}, 'No requirement diagnostics were produced.')
    geometry = any(r['Geometry difference'] for r in rows)
    if geometry:
        flag('INCOMPATIBLE_GEOMETRY', 'whole_jd', {'published_rows': len(c.published.requirements),
             'experimental_rows': len(c.gated.requirements)},
             'Decomposition/allocation differs. No requirement credit delta is inferred.', severity='INFO', kind='OBSERVATION')
    if geometry and c.published.alignment is not None and c.published.alignment == c.gated.alignment:
        flag('SAME_SCORE_DIFFERENT_GEOMETRY', 'whole_jd', {'published': c.published.alignment, 'experimental': c.gated.alignment},
             'Equal overall percentages do not establish equivalent requirement coverage; not a score regression.', severity='INFO', kind='OBSERVATION')
    for side, view, raw in (('published', c.published, c.published_analysis), ('experimental', c.gated, c.gated_analysis)):
        if view.review_count and (view.alignment is not None or raw.get('deterministic_alignment_score') is not None):
            flag('NUMERIC_WITHHELD_SCORE', side, {'alignment': view.alignment, 'review_count': view.review_count},
                 'Review-required whole-JD score must be null.', severity='ERROR', kind='INVARIANT_VIOLATION')
        for r in view.requirements:
            identity = side+':'+r.requirement_id
            if r.label.value == 'REVIEW_REQUIRED' and r.contribution is not None:
                flag('NUMERIC_WITHHELD_CREDIT', identity, {'credit': r.contribution},
                     'Review-required contribution must be null.', severity='ERROR', kind='INVARIANT_VIOLATION')
            if r.conflict and r.conflict.get('quarantine') and (r.label.value != 'REVIEW_REQUIRED' or r.contribution is not None):
                flag('CONFLICT_NOT_QUARANTINED', identity, {'label': r.label.value, 'credit': r.contribution},
                     'The conflict receipt requests quarantine but effective output is numeric.', severity='ERROR', kind='INVARIANT_VIOLATION')
            if r.label.value in ('DIRECT', 'WEAK', 'TRANSFERABLE') and (not r.evidence or
                    any(not e.get('source') or not e.get('evidence_id') for e in r.evidence)):
                flag('SOURCE_COVERAGE_REVIEW', identity, {'label': r.label.value, 'sources': len(r.evidence)},
                     'Positive credit has absent/incomplete source identifiers. Inspect the original receipt; not proof of false credit.')
    for r in rows:
        if r['Published'] == 'DIRECT' and r['Experimental'] != 'DIRECT':
            flag('DIRECT_DOWNGRADED_OR_REMOVED', r['Requirement ID'],
                 {'published': r['Published'], 'experimental': r['Experimental'], 'geometry': r['Geometry difference']},
                 'Inspect source selection and geometry. This observation does not establish an incorrect downgrade.')
    versions = list(result['metadata'])
    metadata = [result['metadata'][v]['lines'] for v in versions]
    # Diagnostic-only cues: these never exclude a line or modify a classifier.
    cues = re.compile(r'interested applicants|kindly email|[\w.+-]+@[\w.-]+\.[a-z]{2,}|applications sent through email|'
        r'shortlisted candidates|EA licen[cs]e|personal data|privacy|PDPA|submitting your application|^T:\s|'
        r'^\d+\s+.+\b(?:Road|Street|Avenue|Drive)\b', re.I)
    for version, receipt in result['metadata'].items():
        for line in receipt['lines']:
            if line['admitted'] and line['classification'] == 'CANDIDATE_QUALIFICATION' and cues.search(line['raw_text']):
                flag('METADATA_FOOTER_REVIEW', version+':'+line['source'],
                     {'classification': line['classification'], 'admitted': line['admitted'], 'indicator': 'recruiting_or_administrative_cue'},
                     'Heuristic footer concern in classification-only output. No effect on published matching is asserted.')
    if len(metadata) != 2 or {r['source'] for r in metadata[0]} != {r['source'] for r in metadata[1]}:
        flag('MISSING_METADATA_COVERAGE', 'metadata', {'versions': versions}, 'Metadata line coverage differs or is incomplete.')
    else:
        previous = {r['source']: r for r in metadata[0]}
        for line in metadata[1]:
            old = previous[line['source']]
            if (old['classification'], old['admitted']) != (line['classification'], line['admitted']):
                flag('METADATA_VERSION_DIFFERENCE', line['source'],
                     {versions[0]: old['classification'], versions[1]: line['classification']},
                     'Classifiers disagree; this is not evidence of a published score change.', severity='INFO', kind='OBSERVATION')
    return sorted(findings, key=lambda f: ({'ERROR': 0, 'REVIEW': 1, 'INFO': 2}[f['severity']], f['code'], f['identity']))


def summary(case_id, entry):
    theme = next(c['theme'] for c in registry() if c['id'] == case_id)
    base = {'Case ID': case_id, 'Scenario': theme, 'Execution': entry.get('status', 'PENDING'),
            'Published alignment': None, 'Experimental alignment': None,
            'Whole-JD comparison': 'Unavailable', 'Priority': 'ERROR' if entry.get('status') == 'ERROR' else 'PENDING'}
    if entry.get('status') != 'COMPLETED': return base
    c = entry['result']['comparison']; rows = review_rows(c)
    findings = entry['findings']; geometry = any(r['Geometry difference'] for r in rows)
    def counts(view):
        values = view.summary()['counts']
        return '/'.join(str(values[k]) for k in ('DIRECT','WEAK','TRANSFERABLE','NONE','REVIEW_REQUIRED'))
    return base | {'Published alignment': c.published.alignment, 'Experimental alignment': c.gated.alignment,
        'Whole-JD comparison': ('WITHHELD' if not c.published.score_available or not c.gated.score_available
                                else 'DIFFERENT_GEOMETRY' if geometry else 'AVAILABLE_SEPARATE_CONTRACTS'),
        'Published D/W/T/N/R': counts(c.published), 'Experimental D/W/T/N/R': counts(c.gated),
        'Geometry difference': geometry, 'Changed labels': sum(r['Published'] != r['Experimental'] for r in rows if not r['Missing counterpart']),
        'Conflict quarantine': any(r['Conflict'] for r in rows), 'Withheld': not c.gated.score_available,
        'Metadata warnings': sum(f['code'] in ('METADATA_FOOTER_REVIEW','METADATA_VERSION_DIFFERENCE','MISSING_METADATA_COVERAGE') for f in findings),
        'Changed scores': c.published.alignment is not None and c.gated.alignment is not None and c.published.alignment != c.gated.alignment,
        'Priority': ('ERROR' if any(f['severity'] == 'ERROR' for f in findings) else
                     'REVIEW' if any(f['severity'] == 'REVIEW' for f in findings) else 'OBSERVATION' if findings else 'NORMAL')}


def case_report(result, *, include_text=False):
    """Extend the Phase 1 allowlist with review receipts, never a raw analysis."""
    data = json.loads(adapter.diagnostic_export(result, result['case_id'], include_synthetic_text=include_text))
    c = result['comparison']
    data['review_receipts'] = []
    for side, view in (('published',c.published), ('experimental',c.gated)):
        for row in view.requirements:
            conflict = row.conflict or {}
            record = {'side': side, 'requirement_id': row.requirement_id,
                'object_family': row.receipt.get('obligation', {}).get('object_family'),
                'disposition': row.disposition, 'native_label': row.native_label,
                'effective_label': row.label.value, 'supported_actions': list(row.supported_actions),
                'missing_actions': list(row.missing_actions), 'technical_scope': row.technical_scope,
                'conflict_quarantined': bool(conflict.get('quarantine')),
                'conflict_reason': conflict.get('reason'),
                'conflict_findings': [{'source': f.get('negative_original',{}).get('source'),
                    'evidence_id': f.get('negative_original',{}).get('evidence_id'),
                    'relationship': f.get('relationship'), 'reason': f.get('reason')} for f in conflict.get('findings',[])]}
            if include_text:
                record['synthetic_selected_originals'] = [{k: e.get(k) for k in ('source','evidence_id','text')} for e in row.evidence]
                record['synthetic_contrary_originals'] = [{k: f.get('negative_original',{}).get(k)
                    for k in ('source','evidence_id','original_text')} for f in conflict.get('findings',[])]
            data['review_receipts'].append(record)
    return data


def run_chunk(batch, *, session_enabled=False, limit=1, should_stop=lambda: False, progress=lambda *args: None):
    if not adapter.enabled() or session_enabled is not True:
        raise ValueError('Developer batch audit is OFF')
    if type(limit) is not int or not 1 <= limit <= MAX_CASES:
        raise ValueError('Invalid chunk limit')
    require_current(batch)
    completed = 0
    for case_id in batch['requested']:
        if case_id in batch['entries']: continue
        if completed >= limit or should_stop(): break
        require_current(batch)
        started = time.perf_counter()
        progress(case_id, 'RUNNING', len(batch['entries']), len(batch['requested']))
        try:
            result = adapter.evaluate(case_id, session_enabled=True)
            from job_discovery.coordinated_preview_model import export_comparison
            retained = len(export_comparison(result['comparison']).encode('utf-8'))
            if batch['retained_bytes'] + retained > MAX_RETAINED_BYTES:
                raise ValueError('Retention bound exceeded')
            entry = {'status': 'COMPLETED', 'result': result, 'findings': audit_result(result), 'receipt_bytes': retained}
            batch['retained_bytes'] += retained
        except Exception:
            entry = {'status': 'ERROR', 'error_code': 'EVALUATION_OR_RESOURCE_FAILURE',
                     'findings': [_finding(case_id, 'EVALUATION_FAILURE', 'case', {'status': 'ERROR'},
                                  'Evaluation, validation or resource bound failed; no numeric result exists.', 'ERROR', 'EXECUTION_ERROR')]}
        entry.update(case_fingerprint=case_key(batch, case_id), elapsed_seconds=round(time.perf_counter()-started, 6))
        batch['entries'][case_id] = entry
        completed += 1
        progress(case_id, entry['status'], len(batch['entries']), len(batch['requested']))
    return batch


def selected_export(result, requirement_ids, *, include_text=False):
    data = case_report(result, include_text=include_text)
    known = {r['Requirement ID'] for r in data['requirements']}
    if not requirement_ids or set(requirement_ids)-known:
        raise ValueError('Select known requirement identities')
    data['selected_requirement_ids'] = sorted(set(requirement_ids))
    data['requirements'] = [r for r in data['requirements'] if r['Requirement ID'] in requirement_ids]
    data['experimental_evidence'] = [r for r in data['experimental_evidence'] if r['requirement_id'] in requirement_ids]
    data['review_receipts'] = [r for r in data['review_receipts'] if r['requirement_id'] in requirement_ids]
    data.pop('metadata_classifications')
    return json.dumps(data, sort_keys=True, indent=2, allow_nan=False)


def export_bundle(batch, *, include_text=False):
    require_current(batch)
    records = [summary(key, batch['entries'].get(key, {})) for key in batch['requested']]
    findings = sorted([f for key in batch['requested'] for f in batch['entries'].get(key, {}).get('findings', [])],
        key=lambda f: ({'ERROR':0,'REVIEW':1,'INFO':2}[f['severity']], batch['requested'].index(f['case_id']), f['code'], f['identity']))
    manifest = {'schema_version': SCHEMA, 'development_preview_only': True, 'ranking_eligible': False,
        'persistence_eligible': False, 'implementation_fingerprint': batch['revision'],
        'requested': batch['requested'], 'completed': sum(e['status']=='COMPLETED' for e in batch['entries'].values()),
        'errors': sum(e['status']=='ERROR' for e in batch['entries'].values()),
        'pending': len(batch['requested'])-len(batch['entries']),
        'metadata_role': 'CLASSIFICATION_ONLY_NO_GO_NOT_SCORING', 'source_text_included': include_text}
    cases = {}
    for key in batch['requested']:
        entry = batch['entries'].get(key, {})
        cases[key] = {'status': entry.get('status', 'PENDING'), 'case_fingerprint': case_key(batch, key)}
        if entry.get('status') == 'COMPLETED':
            cases[key]['report'] = case_report(entry['result'], include_text=include_text)
        elif entry.get('status') == 'ERROR':
            cases[key]['error_code'] = entry['error_code']
    report = {'manifest': manifest, 'summary': records, 'findings': findings, 'cases': cases}
    encode = lambda obj: json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8')
    json_bytes = encode(report)
    if len(json_bytes) > MAX_EXPORT_BYTES: raise ValueError('Export bound exceeded')
    stream = StringIO(newline='')
    columns = list(dict.fromkeys(k for record in records for k in record))
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
    writer.writeheader(); writer.writerows(records)
    csv_bytes = stream.getvalue().encode('utf-8')  # None becomes empty, not numeric zero.
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        files = {'manifest.json': encode(manifest), 'summary.csv': csv_bytes, 'findings.json': encode(findings)}
        files.update({'cases/'+key+'.json': encode(value) for key, value in cases.items()})
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    zip_bytes = output.getvalue()
    if len(zip_bytes) + len(json_bytes) + len(csv_bytes) > MAX_EXPORT_BYTES:
        raise ValueError('Combined export bound exceeded')
    return {'json': json_bytes, 'csv': csv_bytes, 'zip': zip_bytes}
