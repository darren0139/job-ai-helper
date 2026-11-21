"""Bounded native App 156 research. Reads the frozen application and lead review only."""
from __future__ import annotations

import argparse
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path

from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
from tailoring.phase9f_v37_ats import ats_evidence, resume_excerpts
from tailoring.phase9f_v37_corpus_benchmark import build_case_model, load_case, readonly_db
from tailoring.phase9f_v37_document_trial import compare_native_trials, evaluate_document_trial
from tailoring.phase9f_v37_neutral_selection import STRATEGIES, select_shadow
from tailoring.phase9f_v37_project_leads import bind_project_leads, evaluate_lead_document
from tailoring.stable_tailoring_ranking import _coverage_points
from taxonomy_discovery.offline_execution import offline_execution


def fresh_links(case: dict, *, trace_requirements: frozenset[str] = frozenset(),
                preserve_weak_testing: bool = False) -> tuple[dict, dict]:
    # Reuse the source and layout extraction only. Rebuild every linked ID below.
    model, _ = build_case_model(case['audit'], case['projects'])
    catalog = {row['requirement_id']: row for row in case['baseline']['stable_analysis']['canonical_requirements']}
    candidates = [row for row in model['bullets'] if {'Selected Base', 'Evidence Library'}.intersection(row['source_labels'])]
    profiles = {}
    for row in candidates:
        profiles.setdefault(row['project'], []).append(row['text'])
    project_profile = [{'title': project, 'bullets': bullets} for project, bullets in profiles.items()]
    text = 'PROJECTS\n' + '\n'.join('\n'.join([project, *bullets]) for project, bullets in profiles.items())
    analysis = analyze_actual_resume_against_jd(
        resume_text=text, jd_text=case['raw_jd_text'], jd_profile=case['baseline']['jd_profile'],
        resume_profile={'projects': project_profile},
    )
    rows = analysis['stable_analysis']['canonical_requirements']
    pinned = {rid: req['importance'] for rid, req in catalog.items()}
    if {row['requirement_id']: row['importance'] for row in rows} != pinned:
        raise ValueError('Fresh JD analysis changed requirement identity or importance.')
    if trace_requirements:
        model['pool_native_trace'] = [row for row in rows if row['requirement_id'] in trace_requirements]
    ats = ats_evidence(list(catalog.values()), [
        {'section': 'projects', 'project': row['project'], 'text': row['text'], 'attested': True}
        for row in candidates
    ], case['raw_jd_text'], scorer_rows=rows)
    links = {}
    for req in ats['requirements']:
        for match in req['matches']:
            weak_quote = match['native_excerpt_label'] == 'weak' and req['evidence_scope_eligible']
            if match['grounded_support'] or weak_quote:
                links.setdefault((match['project'], match['text']), set()).add(req['id'])
    for row in model['bullets']:
        row['ids'] = links.get((row['project'], row['text']), set())
    _, model['weights'] = _coverage_points(
        [{'requirement_id': rid, 'match_label': 'direct'} for rid in catalog], catalog,
    )
    if preserve_weak_testing:
        from tailoring.phase9f_v37_selection_evidence import project_weak_testing_links

        eligible_ids = {r['id'] for r in ats['requirements'] if r['evidence_scope_eligible']}
        model['weak_projection'] = project_weak_testing_links(
            model, catalog, rows, eligible_ids, {'projects': project_profile}, text)
    return model, ats


def measured(case: dict, slate: dict, work: Path, *, unattested: str | None = None) -> dict:
    if slate['status'] != 'selected':
        return slate
    proposal = slate['proposal']
    native = evaluate_lead_document(case, proposal, slate['leads'], work_root=work)
    skills = case['generation']['fit_result']['tailored_skills_used']['skill_lines']
    excerpts = resume_excerpts(proposal['projects'], skills)
    for excerpt in excerpts:
        if excerpt['text'] == unattested:
            excerpt['attested'] = False
    ats = ats_evidence(case['baseline']['stable_analysis']['canonical_requirements'], excerpts,
                       case['raw_jd_text'], scorer_rows=native.get('requirements', []))
    return {**slate, 'native': native, 'ats': ats}


def weak_experiment(case: dict, model: dict, review: dict, work: Path) -> dict:
    minimum = deepcopy(model)
    openings = bind_project_leads(case['audit'], review, {'base'})['leads']
    for row in minimum['bullets']:
        if row['text'] != openings[row['project']]['wording']:
            row['source_labels'] = []
    weak = select_shadow(minimum, case['audit'], review, 'base_only')
    strong = select_shadow(model, case['audit'], review, 'library_only')
    if weak['status'] != 'selected' or strong['status'] != 'selected':
        return {'status': 'unavailable', 'weak_base': weak, 'factual_library': strong}
    negative = deepcopy(weak)
    row = next(row for row in negative['proposal']['projects'] if row['project'].startswith('Job AI Helper'))
    stuffing = 'Java, Python, .NET, PHP, HTML5, Angular, React JS, unit testing, integration testing, system testing, user acceptance testing.'
    row['after'].append(stuffing)
    row['after_count'] += 1
    row['sources'].append([])
    row['supported_jd_ids'].append([])
    row['supporting_bullets'].append(stuffing)
    negative.update(words=negative['words'] + len(stuffing.split()), provenance='intentional_unattested_negative_control')
    # It is deliberately ineligible as a candidate. Diagnostic rendering can reveal whether
    # the native scorer accepts the string despite the independent provenance failure.
    weak_measured = measured(case, weak, work)
    strong_measured = measured(case, strong, work)
    negative_measured = measured(case, negative, work, unattested=stuffing)
    return {
        'status': 'evaluated', 'weak_base': weak_measured, 'factual_library': strong_measured,
        'negative_control': negative_measured,
        'library_comparison': compare_native_trials(weak_measured['native'], strong_measured['native']),
        'negative_comparison': compare_native_trials(weak_measured['native'], negative_measured['native']),
    }


def neutral_experiment(case: dict, model: dict, review: dict, work: Path) -> dict:
    reference = evaluate_document_trial(case, work_root=work)
    variants = {}
    for strategy in STRATEGIES:
        result = measured(case, select_shadow(model, case['audit'], review, strategy), work)
        if result.get('native'):
            result['reference_comparison'] = compare_native_trials(reference, result['native'])
            native = result['native']
            if native['status'] != 'verified':
                reason = native.get('reason', '').lower()
                result['failure'] = ('document_fitting' if native['status'] == 'fit_failed' else
                                     'jd_requirement_or_importance_drift' if 'requirement' in reason and
                                     ('identit' in reason or 'importance' in reason) else
                                     'native_analysis')
            elif result['reference_comparison'].get('hard_regressions'):
                result['finding'] = 'native_required_core_evidence_loss'
        variants[strategy] = result
    comparisons = {
        f'{a}_vs_{b}': compare_native_trials(variants[a].get('native', {}), variants[b].get('native', {}))
        for a, b in (('base_only', 'library_only'), ('base_only', 'mixed'), ('library_only', 'mixed'))
    }
    for check in comparisons.values():
        delta = check['native_delta']
        check['score_outcome'] = ('unavailable' if delta is None else 'tie' if delta == 0 else
                                  'second_higher' if delta > 0 else 'first_higher')
    historical = json.loads(Path('reports/v37_corpus_pilot.json').read_bytes())
    production = next((row['strategies'] for row in historical['development']
                       if row['generation_row'] == case['generation_row']), {})
    return {'reference': reference, 'variants': variants, 'comparisons': comparisons,
            'historical_production_constraints': {
                key: {field: production[key].get(field) for field in ('status', 'reason', 'source_preflight', 'native')}
                for key in STRATEGIES if key in production}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('weak', 'neutral'), required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    review = json.loads(args.review.read_bytes())['review']
    with closing(readonly_db(Path('data/applications.db'))) as db, offline_execution('Lead/ATS research is offline'):
        case = load_case(db, review['generation_row'], Path.cwd())
        model, ats = fresh_links(case)
        experiment = weak_experiment if args.mode == 'weak' else neutral_experiment
        report = {'application_id': case['application_id'], 'generation_row': case['generation_row'],
                  'mode': args.mode, 'source_pool_ats': ats, **experiment(case, model, review, args.work_root)}
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(report, out, ensure_ascii=False, indent=2)
    print(args.output)


if __name__ == '__main__':
    main()
