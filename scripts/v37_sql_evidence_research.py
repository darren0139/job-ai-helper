"""Replay existing database probes through the research gate and inspect App 149 inputs."""
from argparse import ArgumentParser
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path

from resume_builder.fitting_provenance import fitting_input_fingerprint
from tailoring.phase9f_v37_corpus_benchmark import load_case, readonly_db
from tailoring.phase9f_v37_sql_evidence import review_database_evidence


TRACE = Path('reports/v37_supporting_validation.json')


def app149_checklist(db, previous):
    case = load_case(db, 221, Path.cwd())
    if case['application_id'] != 149:
        raise ValueError('Unexpected application for the pinned generation.')
    fit = case['generation']['fit_result']
    snapshot = fit['fitting_input_snapshot']
    fingerprint = fitting_input_fingerprint(snapshot)
    if snapshot['fitting_input_fingerprint'] != fingerprint or fit['fitting_input_fingerprint'] != fingerprint:
        raise ValueError('The historical fitting snapshot failed its fingerprint check.')
    original = snapshot['source_artifact']
    files = [path for path in Path('data/saved_resumes').glob('app_149_*.docx') if path.is_file()]
    originals = [path.as_posix() for path in sorted(files) if path.stat().st_size == original['byte_size']
                 and sha256(path.read_bytes()).hexdigest() == original['sha256']]
    execution_count = db.execute(
        'SELECT COUNT(*) FROM phase9f_tailoring_executions WHERE application_id=? AND generation_id=?',
        (149, case['generation_id'])).fetchone()[0]
    return {
        'status': 'withheld', 'job': 644, 'application': 149, 'generation_row': 221,
        'original_fitter_input': {**original, 'matched_paths': originals, 'candidates_checked': len(files),
                                  'same_version_original_base_analysis_established': False,
                                  'same_generation_execution_receipts': execution_count},
        'eligible_bullets': {
            'exact_source_audit_verified': case['audit']['verified'],
            'base': sum(len(row['base']) for row in case['audit']['projects']),
            'library': sum(len(row['library']) for row in case['audit']['projects']),
            'independent_claim_review_established': previous['independent_source_attestation_established'],
            'independent_canonical_lead_review_established': previous['authorized_reviewed_leads_established'],
        },
        'jd_identity': {
            'raw_jd_sha256': sha256(case['raw_jd_text'].encode()).hexdigest(),
            'frozen_raw_hash_match': previous['jd_hash_matches_frozen'],
            'saved_importance_differences': previous['shared_importance_differences'],
            'frozen_only_ids': previous['frozen_only_requirements'],
            'application_only_ids': previous['application_only_requirements'],
            'prior_native_identity_failure': previous['previous_native_failure'],
        },
        'compatible_scorer_established': False, 'stored_scorer_versions': previous['scorer_versions'],
        'document_layout': {
            'fitting_input_fingerprint': fingerprint,
            'fitted_docx_sha256': case['audit']['docx_sha256'], 'recorded_pages': fit['page_count'],
            'margin_profile': fit['margin_profile'], 'page_density_mode': fit['page_density_mode'],
            'project_header_layout': fit['project_header_layout_used'],
            'fitting_policy_version': snapshot['fitting_policy_version'],
            'historical_fitter_invocation_recoverable': True,
            'same_scope_native_comparison_established': False,
        },
        'comparison_runs': 0,
    }


def _digest(text):
    return sha256(text.encode()).hexdigest()


def replay(saved, starting, donor):
    requirement = saved['database_requirement']
    jd = starting['raw_jd_text']
    if not any(row == requirement for row in starting['stable_analysis']['canonical_requirements']):
        raise ValueError('The saved diagnostic and current frozen requirement records differ.')
    kw = {name: row['text'] for name, row in saved['database_controls'].items()}
    sql = kw['synthetic_explicit_sql_activity']
    nosql = 'Queried NoSQL collections to reconcile archived events.'
    kw.update({
        'synthetic_postgresql_migration': 'Executed PostgreSQL migrations for the application.',
        'synthetic_negated': 'I did not write SQL queries or run PostgreSQL migrations.',
        'synthetic_future': 'I plan to write SQL queries next quarter.',
        'synthetic_duplicate_sql': f'{sql}\n{sql}',
        'synthetic_nosql_only': nosql,
        'synthetic_both_branches': f'{sql}\n{nosql}',
        'synthetic_unhandled_factual_paraphrase': 'I reconciled invoice records by writing SQL joins.',
    })
    expected = {
        'exact_library': 'transferable', 'synthetic_explicit_sql_activity': 'transferable',
        'synthetic_keywords_only': 'none', 'synthetic_unrelated_action': 'none',
        'synthetic_postgresql_migration': 'transferable', 'synthetic_negated': 'none', 'synthetic_future': 'none',
        'synthetic_duplicate_sql': 'transferable', 'synthetic_nosql_only': 'transferable',
        'synthetic_both_branches': 'direct', 'synthetic_unhandled_factual_paraphrase': 'transferable',
    }
    results = {}
    audit = donor['audit']
    project = next(row['project'] for row in audit['projects']
                   if any(bullet['text'] == kw['exact_library'] for bullet in row['library']))
    for name, text in kw.items():
        prior = saved['database_controls'].get(name)
        native = {field: requirement[field] for field in ('requirement_id', 'text', 'importance')}
        native['match_label'] = prior['native_label'] if prior else None
        native['evidence_strength'] = prior['native_strength'] if prior else None
        native['evidence'] = ((prior or {}).get('stages') or {}).get('_apply_capability_none_recovery', {}).get('evidence') or []
        source_options = {}
        content = text
        if name == 'exact_library':
            content = f'Projects\n{project}\n{text}'
            source_options = {'profile': {'projects': [{'title': project, 'bullets': [text]}]},
                              'donor_audit': audit, 'donor_sha256': audit['docx_sha256']}
        result = review_database_evidence(
            requirement=requirement, native=native, raw_jd=jd, expected_jd_sha256=saved['jd_sha256'],
            resume_text=content, expected_resume_sha256=_digest(content), **source_options)
        results[name] = {**result, 'expected_research_label': expected[name],
                         'agrees_with_review': result['research_label'] == expected[name],
                         'native_status': 'reused_in_memory_control' if prior else 'not_measured'}
    return results


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    trace = TRACE.read_bytes()
    saved = json.loads(trace)
    baseline = json.loads(Path('reports/v37_job493_bonus_research.json').read_bytes())
    with closing(readonly_db(Path('data/applications.db'))) as db:
        starting = json.loads(db.execute('SELECT report_json FROM applications WHERE id=?', (152,)).fetchone()[0])
        donor = load_case(db, 251, Path.cwd())
        if donor['audit']['docx_sha256'] != baseline['source_docx_sha256']:
            raise ValueError('App 156’s audited source no longer matches the saved trial.')
        controls = replay(saved, starting, donor)
        portfolio = app149_checklist(db, saved['independent_preflight'])
    result = {
        'reused_trace_sha256': sha256(trace).hexdigest(), 'controls': controls,
        'independent_portfolio': portfolio, 'new_native_scoring_runs': 0, 'new_native_renders': 0,
        'saved_job_493_native_score': baseline['variants']['supporting_first']['native']['score'],
    }
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    print(args.output)


if __name__ == '__main__':
    main()
