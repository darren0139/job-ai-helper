"""Read-only source audit and bounded isolated native experiments."""
from __future__ import annotations

import argparse
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tailoring.phase9f_v37_corpus_benchmark import load_case, load_frozen_packet, readonly_db
from taxonomy_discovery.offline_execution import offline_execution

TARGET = 'Perform software implementation and testing'
NEGATIVE = 'Software implementation, testing, testing, testing.'
PACKET = Path.home() / 'Downloads' / 'job_ai_helper_phase2d3_rebaseline_v14.zip'


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def heldout_inputs(db) -> tuple[dict, dict, str]:
    report = json.loads(db.execute('SELECT report_json FROM applications WHERE id=152').fetchone()[0])
    packet, digest = load_frozen_packet(PACKET)
    job = next(row for row in packet if row['cohort'] == 'FROZEN' and row['job_id'] == 493)
    jd_sha = _digest(report['raw_jd_text'].encode())
    if job['raw_jd_sha256'] != jd_sha:
        raise ValueError('Frozen Job 493 and App 152 JD text differ.')
    row = next(req for req in report['stable_analysis']['canonical_requirements'] if req['text'] == TARGET)
    probes = [p for p in row.get('source_provenance', [])
              if p['grounding'].get('sentence_text') == TARGET
              and p['grounding'].get('section') == 'responsibilities']
    if row['importance'] != 'core' or len(probes) != 1:
        raise ValueError('The held-out testing duty lacks its reviewed Core responsibility span.')
    return report, job, digest


def testing_experiment(donor: dict, starting: dict, job: dict, packet_digest: str, work: Path) -> dict:
    from docx import Document

    from parse import read_resume_docx
    from tailoring.capability_taxonomy import evaluate_evidence, get_default_taxonomy
    from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
    from tailoring.phase9f_v37_testing_gate import has_attested_testing_activity

    project = next(row for row in donor['audit']['projects'] if row['project'].startswith('Job AI Helper'))
    lead = next(row['text'] for row in project['library'] if row['text'].startswith('Built a Streamlit'))
    factual = next(row['text'] for row in project['library'] if row['text'].startswith('Added automated unit tests'))
    skill_lines = donor['generation']['fit_result']['tailored_skills_used']['skill_lines']
    if not any('Python' in row['items'] for row in skill_lines):
        raise ValueError('The exact Python skill is unavailable in the frozen donor Skills section.')
    jd = starting['raw_jd_text']
    expected = starting['stable_analysis']['canonical_requirements']
    target = next(req for req in expected if req['text'] == TARGET)
    frozen = {req['requirement_id']: req['importance'] for req in expected}
    review = {
        'jd': 'Frozen Job 493 / App 152',
        'responsibility': TARGET,
        'positive': 'The exact Library bullet attests adding automated unit tests and running them in CI. This tests partial activity evidence; it does not attest all duties for this employer.',
        'negative': 'The list repeats JD terms and has no attested performed testing action.',
        'keyword_control': 'Exact Python in the Skills section is held fixed across all documents.',
    }
    outcomes = {}
    with TemporaryDirectory(prefix='v37-testing-holdout-', dir=work) as scratch:
        for name, item in [('no_testing', None), ('factual_partial', factual), ('unattested_repeat', NEGATIVE)]:
            bullets = [lead] + ([item] if item else [])
            doc = Document()
            doc.add_heading('PROJECTS', level=1)
            doc.add_paragraph('Job AI Helper')
            for text in bullets:
                doc.add_paragraph('• ' + text)
            doc.add_heading('SKILLS', level=1)
            doc.add_paragraph('Programming: Python')
            path = Path(scratch) / f'{name}.docx'
            doc.save(path)
            raw = read_resume_docx(str(path), preserve_complete_text=True)
            profile = {'projects': [{'title': 'Job AI Helper', 'bullets': bullets}],
                       'skills': {'Programming': ['Python']}}
            analysis = analyze_actual_resume_against_jd(
                resume_text=raw, jd_text=jd, jd_profile=starting['jd_profile'],
                resume_profile=profile, canonical_requirements=expected,
            )
            stable = analysis['stable_analysis']
            actual = {row['requirement_id']: row['importance'] for row in stable['canonical_requirements']}
            if actual != frozen:
                raise ValueError('Held-out requirement identity or importance drift.')
            testing = next(req for req in stable['canonical_requirements']
                           if req['requirement_id'] == target['requirement_id'])
            evidence = (testing.get('evidence') or [{}])[0]
            decision = evaluate_evidence(testing, evidence.get('text', ''), get_default_taxonomy())
            keyword = next((row for row in analysis['keyword_match']['present']
                            if row['keyword'] == TARGET), {})
            attested = {('resume_profile.projects[0].bullets[1]', factual)} if item == factual else set()
            outcomes[name] = {
                'native_score': stable['deterministic_alignment_score'], 'scoring_version': stable['scoring_version'],
                'docx_sha256': _digest(path.read_bytes()), 'jd_sha256': job['raw_jd_sha256'],
                'match_label': testing['match_label'], 'match_value': testing['match_value'],
                'match_source': testing['match_source'], 'native_evidence': evidence,
                'preliminary_keyword_label': keyword.get('match_type'),
                'taxonomy_decision': decision, 'has_exact_python_skill': 'Python' in raw,
                'passes_proposed_activity_gate': has_attested_testing_activity(testing, evidence, attested),
            }
    return {'status': 'verified', 'review': review, 'heldout_snapshot': job['job_id'],
            'packet_sha256': packet_digest, 'donor_docx_sha256': donor['audit']['docx_sha256'],
            'frozen_testing_requirement': target, 'controls': outcomes}


def supporting_space_experiment(case: dict, work: Path) -> dict:
    from pypdf import PdfReader

    from tailoring.phase9f_joint_resume_optimizer_v2_6 import _render_pdf
    from tailoring.phase9f_v37_ats import ats_evidence, resume_excerpts
    from tailoring.phase9f_v37_document_trial import compare_native_trials
    from tailoring.phase9f_v37_project_leads import SOURCES, evaluate_lead_document

    saved = Path('reports/v37_app156_source_neutral.json').read_bytes()
    prior = json.loads(saved)
    reference = prior['variants']['mixed']
    native = reference['native']
    if (prior['generation_row'] != case['generation_row'] or native['status'] != 'verified'
            or native['pages'] != 1 or not native['docx_leads_verified']
            or native['layout_reference_sha256'] != case['audit']['docx_sha256']
            or native['jd_sha256'] != _digest(case['raw_jd_text'].encode())):
        raise ValueError('Saved one-page baseline is stale or lacks verified project leads.')
    expected = case['baseline']['stable_analysis']['canonical_requirements']
    skills = case['generation']['fit_result']['tailored_skills_used']['skill_lines']
    proposals = {}
    for name, prefix, source, position, review in (
        ('queryai_database_access', 'QueryAI', 'library', 2,
         'The introduction describes the app and team contribution; the added action explains a distinct database access control implementation.'),
        ('job_ai_implementation', 'Job AI Helper', 'base', 2,
         'Adds the deterministic scoring architecture. It introduces several technical details in one sentence.'),
    ):
        slate = deepcopy(reference['proposal'])
        audited = next(group for group in case['audit']['projects'] if group['project'].startswith(prefix))
        wording = audited[source][position - 1]['text']
        row = next(group for group in slate['projects'] if group['project'] == audited['project'])
        if wording in row['after']:
            raise ValueError('Supporting bullet is already present.')
        if reference['words'] + len(wording.split()) > reference['word_cap'] or len(row['after']) >= 8:
            raise ValueError('Supporting bullet exceeds the research layout budget.')
        eligible_links = sorted({
            req['id'] for req in prior['source_pool_ats']['requirements'] for m in req['matches']
            if m['project'] == audited['project'] and m['text'] == wording
            and (m['grounded_support'] or (m['native_excerpt_label'] == 'weak'
                 and req['fragment_status'] in {'exact_span', 'text_normalization_difference'}))
        })
        selected_links = {rid for group in slate['projects'] for ids in group['supported_jd_ids'] for rid in ids}
        row['after'].append(wording)
        row['after_count'] += 1
        row['sources'].append([SOURCES[source]])
        row['supported_jd_ids'].append(eligible_links)
        row['supporting_bullets'].append(wording)
        render_metrics = {}

        def render(docx, directory):
            pdf = _render_pdf(docx, directory)
            render_metrics['nonempty_pdf_text_lines'] = [
                sum(bool(line.strip()) for line in page.extract_text(extraction_mode='layout').splitlines())
                for page in PdfReader(str(pdf)).pages
            ]
            return pdf

        evaluated = evaluate_lead_document(case, slate, reference['leads'], work_root=work, renderer=render)
        ats = ats_evidence(expected, resume_excerpts(slate['projects'], skills), case['raw_jd_text'],
                           scorer_rows=evaluated.get('requirements', []))
        proposals[name] = {
            'addition': wording, 'provenance': {'project': row['project'], 'source': source, 'source_position': position,
                                                'wording_sha256': _digest(wording.encode())},
            'proposal_words': reference['words'] + len(wording.split()),
            'proposal_bullet_count': sum(len(p['after']) for p in slate['projects']),
            'new_shadow_link_ids': sorted(set(eligible_links) - selected_links),
            'new_exact_jd_technologies': sorted(set(ats['distinct_exact_technologies'])
                                                - set(reference['ats']['distinct_exact_technologies'])),
            'ats': ats, 'readability_review': review, 'render_metrics': render_metrics,
            'native': evaluated, 'comparison': compare_native_trials(native, evaluated),
        }
    return {'status': 'evaluated', 'application_id': case['application_id'],
            'reference_receipt_sha256': _digest(saved), 'reference_native': native,
            'reference_words': reference['words'], 'word_cap': reference['word_cap'],
            'reference_bullet_count': sum(len(row['after']) for row in reference['proposal']['projects']),
            'trials': proposals}


def source_neutral_holdout(donor: dict, starting: dict, job: dict, packet_digest: str, work: Path) -> dict:
    from scripts.v37_lead_ats_experiment import fresh_links, measured
    from tailoring.phase9f_v37_document_trial import compare_native_trials
    from tailoring.phase9f_v37_neutral_selection import STRATEGIES, select_shadow

    review_bytes = Path('reports/v37_app156_lead_review.json').read_bytes()
    review = json.loads(review_bytes)['review']
    case = {**donor, 'baseline': starting, 'raw_jd_text': starting['raw_jd_text']}
    receipt = {
        'cohort': 'heldout', 'jd_application_id': 152, 'job_id': job['job_id'],
        'jd_sha256': job['raw_jd_sha256'], 'frozen_packet_sha256': packet_digest,
        'source_application_id': donor['application_id'], 'source_generation_row': donor['generation_row'],
        'source_docx_sha256': donor['audit']['docx_sha256'], 'lead_review_sha256': _digest(review_bytes),
        'production_comparison': 'unavailable; the material and layout come from a separate application',
    }
    try:
        model, evidence = fresh_links(case)
    except ValueError as error:
        return {**receipt, 'status': 'withheld', 'reason': str(error)}
    variants = {}
    documents = {}
    for strategy in STRATEGIES:
        try:
            slate = select_shadow(model, case['audit'], review, strategy)
        except ValueError as error:
            variants[strategy] = {'status': 'withheld', 'failure': 'lead_review_or_source_binding',
                                  'reason': str(error)}
            continue
        if slate['status'] != 'selected':
            variants[strategy] = slate
            continue
        key = tuple((row['project'], tuple(row['after'])) for row in slate['proposal']['projects'])
        if key in documents:
            prior = documents[key]
            result = {**slate, 'native': variants[prior]['native'], 'ats': variants[prior]['ats'],
                      'identical_render_verified_by': prior}
        else:
            result = measured(case, slate, work)
            documents[key] = strategy
        native = result['native']
        if native['status'] != 'verified':
            result['failure'] = ('document_fitting' if native['status'] == 'fit_failed' else
                                 'jd_requirement_or_importance_drift' if 'requirement' in native.get('reason', '')
                                 else 'native_analysis')
        variants[strategy] = result
    comparisons = {}
    for first, second in (('base_only', 'library_only'), ('base_only', 'mixed'), ('library_only', 'mixed')):
        outcome = compare_native_trials(variants[first].get('native', {}), variants[second].get('native', {}))
        delta = outcome['native_delta']
        outcome['score_outcome'] = ('unavailable' if delta is None else 'tie' if delta == 0 else
                                    'second_higher' if delta > 0 else 'first_higher')
        comparisons[f'{first}_vs_{second}'] = outcome
    return {**receipt, 'status': 'evaluated', 'source_pool_ats': evidence,
            'variants': variants, 'comparisons': comparisons}


def guarded_lead_preview(case: dict, work: Path) -> dict:
    from tailoring.phase9f_v37_lead_candidate import build_lead_guarded_candidate
    from tailoring.phase9f_v37_project_leads import evaluate_lead_document

    review_bytes = Path('reports/v37_app156_lead_review.json').read_bytes()
    review = json.loads(review_bytes)['review']
    proposal = build_lead_guarded_candidate(case['audit'], case['projects'], lead_review=review)
    native = None
    if proposal.get('lead_contract'):
        native = evaluate_lead_document(case, proposal, proposal['lead_contract']['leads'], work_root=work)
    return {'source_application_id': case['application_id'], 'source_generation_row': case['generation_row'],
            'source_docx_sha256': case['audit']['docx_sha256'], 'lead_review_sha256': _digest(review_bytes),
            'proposal': proposal, 'native': native}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('testing', 'space', 'guarded-lead', 'holdout'), required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with closing(readonly_db(Path('data/applications.db'))) as db, offline_execution('V3.7 readiness experiment is offline'):
        donor = load_case(db, 251, Path.cwd())
        if args.mode == 'space':
            report = supporting_space_experiment(donor, args.work_root)
        elif args.mode == 'guarded-lead':
            report = guarded_lead_preview(donor, args.work_root)
        else:
            evaluate = testing_experiment if args.mode == 'testing' else source_neutral_holdout
            report = evaluate(donor, *heldout_inputs(db), args.work_root)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(report, out, ensure_ascii=False, indent=2)
    print(args.output)


if __name__ == '__main__':
    main()
