"""Bounded research replay. Reads frozen sources and writes an isolated diagnostic receipt."""
from __future__ import annotations

import argparse
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from scripts.v37_evidence_readiness import TARGET, heldout_inputs
from tailoring.phase9f_v37_corpus_benchmark import load_case, readonly_db
from taxonomy_discovery.offline_execution import offline_execution


REPORTS = Path('reports')
SOURCE_NEUTRAL = REPORTS / 'v37_job493_source_neutral.json'
CONTROLS = REPORTS / 'v37_heldout_testing.json'
REVIEW = REPORTS / 'v37_app156_lead_review.json'


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def append_test_bullet(slate: dict, candidate: dict, *, total_limit: int, project_limit: int) -> dict:
    """Create a one-bullet counterfactual that preserves every existing bullet and its order."""
    proposal = deepcopy(slate['proposal'])
    project = next(row for row in proposal['projects'] if row['project'] == candidate['project'])
    if candidate['text'] in project['after']:
        raise ValueError('The controlled testing bullet must be absent from the saved slate.')
    if (len(project['after']) >= project_limit
            or sum(len(row['after']) for row in proposal['projects']) >= total_limit
            or slate['words'] + candidate['words'] > slate['word_cap']):
        raise ValueError('The additional bullet exceeds a source-neutral constraint.')
    project['after'].append(candidate['text'])
    project['after_count'] += 1
    project['sources'].append(candidate['source_labels'])
    project['supported_jd_ids'].append(sorted(candidate['ids']))
    project['supporting_bullets'].append(candidate['text'])
    return proposal


def forced_testing(donor: dict, starting: dict, job: dict, packet_digest: str, work: Path,
                   *, visual_qa: Path | None = None) -> dict:
    from docx import Document
    from pypdf import PdfReader

    from scripts.v37_lead_ats_experiment import fresh_links
    from tailoring.phase6d_ranking_adapter import match_requirement_to_candidate
    from tailoring.phase9f_certified_selection_v36 import MAX_TOTAL_BULLETS
    from tailoring.phase9f_joint_resume_optimizer_v2_6 import MAX_BULLETS_PER_PROJECT, _bullet_locations, _render_pdf
    from tailoring.phase9f_v37_ats import ats_evidence, resume_excerpts
    from tailoring.phase9f_v37_document_trial import compare_native_trials
    from tailoring.phase9f_v37_project_leads import SOURCES, bind_project_leads, evaluate_lead_document

    blobs = {path: path.read_bytes() for path in (SOURCE_NEUTRAL, CONTROLS, REVIEW)}
    source, controls, review = (json.loads(blobs[path]) for path in (SOURCE_NEUTRAL, CONTROLS, REVIEW))
    jd_sha = digest(starting['raw_jd_text'].encode())
    donor_sha = donor['audit']['docx_sha256']
    if (source['job_id'] != job['job_id'] or source['jd_sha256'] != jd_sha
            or source['source_docx_sha256'] != donor_sha or controls['donor_docx_sha256'] != donor_sha
            or controls['heldout_snapshot'] != job['job_id'] or source['frozen_packet_sha256'] != packet_digest
            or controls['packet_sha256'] != packet_digest or source['lead_review_sha256'] != digest(blobs[REVIEW])):
        raise ValueError('The saved testing and source-neutral receipts do not use the same source or JD.')
    slate = source['variants']['mixed']
    expected = starting['stable_analysis']['canonical_requirements']
    requirement = next(row for row in expected if row['text'] == TARGET)
    target_id = requirement['requirement_id']
    baseline = slate['native']
    if (baseline['status'] != 'verified' or baseline['pages'] != 1 or baseline['jd_sha256'] != jd_sha
            or not baseline['docx_leads_verified'] or baseline['layout_reference_sha256'] != donor_sha
            or not slate.get('identical_render_verified_by')):
        raise ValueError('The saved Mixed slate lacks a compatible verified native baseline.')
    if bind_project_leads(donor['audit'], review['review'], set(SOURCES))['leads'] != slate['leads']:
        raise ValueError('The saved lead bindings changed.')

    case = {**donor, 'baseline': starting, 'raw_jd_text': starting['raw_jd_text']}
    model, pool_ats = fresh_links(case, trace_requirements=frozenset({target_id}))
    wording = controls['controls']['factual_partial']['native_evidence']['text']
    project_source = next(row for row in donor['audit']['projects'] if row['project'].startswith('Job AI Helper'))
    source_rows = [i for i, item in enumerate(project_source['library'], 1) if item['text'] == wording]
    candidate = next(row for row in model['bullets']
                     if row['project'] == project_source['project'] and row['text'] == wording)
    if len(source_rows) != 1 or SOURCES['library'] not in candidate['source_labels']:
        raise ValueError('The saved factual control does not identify one eligible Library wording.')
    selected = slate['proposal']['projects']
    linked = {rid for row in selected for ids in row['supported_jd_ids'] for rid in ids}
    new_links = sorted(candidate['ids'] - linked)
    proposal = append_test_bullet(slate, candidate, total_limit=MAX_TOTAL_BULLETS,
                                  project_limit=MAX_BULLETS_PER_PROJECT)

    def untouched_body(document: Document, expected_projects: list[dict]) -> bytes:
        locations = _bullet_locations(document, expected_projects)
        excluded = {p._element for group in locations for p in group}
        return '\n'.join(element.xml for element in document.element.body if element not in excluded).encode()

    source_document = Document(donor['source_docx'])
    original_body = untouched_body(source_document, proposal['projects'])
    document_checks = {}

    def render(docx, work_dir):
        rendered_body = untouched_body(Document(docx), [
            {'project': row['project'], 'before': row['after']} for row in proposal['projects']
        ])
        if original_body != rendered_body:
            raise ValueError('The writer changed content or formatting outside project bullets.')
        pdf = _render_pdf(docx, work_dir)
        pdf_bytes = pdf.read_bytes()
        pages = PdfReader(pdf).pages
        if len(pages) == 1 and ' '.join(wording.split()) not in ' '.join(pages[0].extract_text().split()):
            raise ValueError('The added wording was not readable from the rendered PDF.')
        document_checks.update(non_bullet_body_sha256=digest(original_body), pdf_sha256=digest(pdf_bytes),
                               exact_pdf_excerpt=len(pages) == 1)
        if visual_qa is not None and len(pages) == 1:
            import fitz

            with fitz.open(stream=pdf_bytes, filetype='pdf') as preview:
                preview[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(str(visual_qa))
        return pdf

    native = evaluate_lead_document(case, proposal, slate['leads'], work_root=work, renderer=render)
    comparison = compare_native_trials(baseline, native)
    before_rows = {row['id']: row for row in baseline['requirements']}
    after_rows = {row['id']: row for row in native.get('requirements', [])}
    changes = [
        {'id': rid, 'requirement': before['text'], 'importance': before['importance'],
         'before': before['match_label'], 'after': after_rows[rid]['match_label']}
        for rid, before in before_rows.items()
        if comparison['comparison_status'] == 'verified' and before['match_label'] != after_rows[rid]['match_label']
    ]
    skills = donor['generation']['fit_result']['tailored_skills_used']['skill_lines']
    old_ats = slate['ats']['distinct_exact_technologies']
    new_ats = ats_evidence(expected, resume_excerpts(proposal['projects'], skills), case['raw_jd_text'],
                           scorer_rows=native.get('requirements', []))['distinct_exact_technologies']
    return {
        'job': job['job_id'], 'source_application': donor['application_id'], 'jd_sha256': jd_sha,
        'frozen_packet_sha256': packet_digest, 'source_docx_sha256': donor_sha,
        'source_receipts': {str(path): digest(data) for path, data in blobs.items()},
        'tested_bullet': {'wording': wording, 'wording_sha256': digest(wording.encode()),
                          'eligible_sources': sorted(set(candidate['source_labels']).intersection(SOURCES.values())),
                          'source_provenance': candidate['source_labels'], 'library_position': source_rows[0],
                          'words': candidate['words'], 'target_id': target_id},
        'selection_trace': {
            'target_pool_native': model['pool_native_trace'][0],
            'target_pool_ats': next(row for row in pool_ats['requirements'] if row['id'] == target_id),
            'target_standalone_capability_match': match_requirement_to_candidate(
                requirement=requirement, candidate_evidence_text=wording),
            'saved_proxy_link_ids': sorted(linked), 'candidate_link_ids': sorted(candidate['ids']),
            'added_link_ids': new_links, 'new_proxy_points': round(sum(model['weights'][rid] for rid in new_links), 3),
            'saved_proxy_points': slate['proxy_saved_points'],
            'objective_order': ['maximize weighted distinct linked IDs', 'minimize words', 'stable project/text order'],
            'word_cap': slate['word_cap'], 'total_bullet_cap': MAX_TOTAL_BULLETS,
            'project_bullet_cap': MAX_BULLETS_PER_PROJECT, 'before_words': slate['words'],
            'after_words': slate['words'] + candidate['words'],
        },
        'saved_mixed_native': baseline, 'forced_addition_native': native, 'comparison': comparison,
        'requirement_label_changes': changes, 'before_testing_requirement': before_rows[target_id],
        'after_testing_requirement': after_rows.get(target_id), 'proposal': proposal,
        'skills_sha256': digest(json.dumps(skills, ensure_ascii=False, sort_keys=True).encode()),
        'exact_ats_technologies': {'before': old_ats, 'after': new_ats}, 'document_checks': document_checks,
    }


def testing_gate_controls(starting: dict, job: dict, packet_digest: str, *, extended: bool = False) -> dict:
    from analysis_stability.stable_evidence_scoring import compute_deterministic_alignment
    from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd
    from tailoring.phase9f_v37_ats import ats_evidence
    from tailoring.phase9f_v37_testing_gate import apply_shadow_testing_gate

    jd_text = starting['raw_jd_text']
    expected = starting['stable_analysis']['canonical_requirements']
    fixtures = {
        'complete_compound_duty': (
            'Implemented the inventory API and wrote integration tests for refund and failure paths.', True),
        'partial_testing_only': (
            'Added automated regression tests for failed payments and ran them before deployment.', True),
        'unstructured_uploaded_prose': (
            'While maintaining our scheduling service, I wrote integration tests for timeout handling.', False),
        'named_testing_activity': (
            'Performed system testing for the release.', False),
        'unattested_keyword_list': (
            'Software implementation, testing, quality assurance, unit tests.', True),
        'unattested_repeated_terms': (
            'Software implementation, testing, testing, testing, testing.', False),
        'planned_or_negated': (
            'Planned to write automated unit tests for checkout. I did not run testing.', False),
    }
    if extended:
        fixtures = {
            'passive_unstructured': ('Integration tests were executed against the payments API before release.', False),
            'unusual_partial_action': ('Carried out regression testing for failures in the reconciliation service.', False),
            'separate_testing_excerpts': (
                'Wrote regression tests for invoice retries.\nPerformed system testing for the release.', True),
            'conditional_future': ('If we run unit tests next quarter, we will validate checkout.', False),
            'passive_negation': ('Integration tests were not run against the payments API.', False),
            'future_with_keyword_repetition': ('We are scheduled to execute regression tests. Testing, testing.', False),
            'technology_keywords_only': ('Java, Python, JavaScript', False),
        }
    results = {}
    for name, (wording, structured) in fixtures.items():
        raw = f'Work experience\n{wording}\nSkills\nProgramming: Python'
        profile = {'experience': [{'bullets': wording.splitlines()}],
                   'skills': {'Programming': ['Python']}} if structured else {}
        native = analyze_actual_resume_against_jd(resume_text=raw, jd_text=jd_text,
            jd_profile=starting['jd_profile'], resume_profile=profile, canonical_requirements=expected)
        stable = native['stable_analysis']
        before = stable['canonical_requirements']
        after, audit = apply_shadow_testing_gate(before, resume_text=raw, resume_profile=profile)
        target_before = next(row for row in before if row['text'] == TARGET)
        target_after = next(row for row in after if row['requirement_id'] == target_before['requirement_id'])
        excerpts = [{'section': 'skills', 'text': 'Python', 'attested': True}]
        exact_before = ats_evidence(expected, excerpts, jd_text, scorer_rows=before)['distinct_exact_technologies']
        exact_after = ats_evidence(expected, excerpts, jd_text, scorer_rows=after)['distinct_exact_technologies']
        shadow_scores = compute_deterministic_alignment(after)
        edits = []
        before_labels, after_labels = {}, {}
        for old, new in zip(before, after, strict=True):
            rid = old['requirement_id']
            before_labels[rid] = old['match_label']
            after_labels[rid] = new['match_label']
            if old['match_label'] != new['match_label']:
                edits.append({'id': rid, 'requirement': old['text'], 'importance': old['importance'],
                              'before': old['match_label'], 'after': new['match_label']})
        results[name] = {
            'synthetic_fixture_excerpt': wording, 'document_text_sha256': digest(raw.encode()),
            'structured_profile': structured, 'reviewed_actions_provided': False,
            'native_score': stable['deterministic_alignment_score'], 'shadow_score': shadow_scores['deterministic_alignment_score'],
            'native_required_core_score': stable['required_core_coverage_score'],
            'shadow_required_core_score': shadow_scores['required_core_coverage_score'],
            'native_target': {'label': target_before['match_label'], 'value': target_before['match_value'],
                              'evidence': target_before['evidence']},
            'shadow_target': {'label': target_after['match_label'], 'value': target_after['match_value'],
                              'evidence': target_after['evidence']},
            'labels_before': before_labels, 'labels_after': after_labels,
            'requirement_label_changes': edits, 'decisions': audit,
            'exact_ats_technologies': {'before': exact_before, 'after': exact_after},
        }
    return {'job': job['job_id'], 'jd_sha256': job['raw_jd_sha256'], 'frozen_packet_sha256': packet_digest,
            'scoring_version': stable['scoring_version'],
            'scope': 'Shadow recheck of only the weak QA role-duty evidence already cited by the native scorer.',
            'controls': results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('forced-testing', 'testing-gate', 'extended-testing-gate'), default='forced-testing')
    parser.add_argument('--work-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--visual-qa', type=Path)
    args = parser.parse_args()
    if args.mode == 'forced-testing' and args.work_root is None:
        parser.error('--work-root is required for forced-testing')
    with closing(readonly_db(Path('data/applications.db'))) as db, offline_execution('Selection quality research'):
        context = heldout_inputs(db)
        if args.mode == 'forced-testing':
            donor = load_case(db, 251, Path.cwd())
            report = forced_testing(donor, *context, args.work_root, visual_qa=args.visual_qa)
        else:
            report = testing_gate_controls(*context, extended=args.mode == 'extended-testing-gate')
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    print(args.output)


if __name__ == '__main__':
    main()
