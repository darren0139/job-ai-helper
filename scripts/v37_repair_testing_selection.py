"""Solve one corrected Job 493 research slate and score its actual fitted document."""
import argparse
from contextlib import closing
import json
from pathlib import Path

from scripts.v37_lead_ats_experiment import fresh_links
from scripts.v37_selection_quality import SOURCE_NEUTRAL, REVIEW, digest, heldout_inputs
from tailoring.phase9f_joint_resume_optimizer_v2_6 import _render_pdf
from tailoring.phase9f_v37_ats import ats_evidence, resume_excerpts
from tailoring.phase9f_v37_corpus_benchmark import load_case, readonly_db
from tailoring.phase9f_v37_document_trial import compare_native_trials
from tailoring.phase9f_v37_neutral_selection import select_shadow
from tailoring.phase9f_v37_project_leads import evaluate_lead_document
from taxonomy_discovery.offline_execution import offline_execution


def run(donor, starting, job, packet, work):
    prior_bytes, review_bytes = SOURCE_NEUTRAL.read_bytes(), REVIEW.read_bytes()
    saved = json.loads(prior_bytes)
    old = saved['variants']['mixed']
    baseline = old['native']
    jd = starting['raw_jd_text']
    if (saved['job_id'] != job['job_id'] or saved['jd_sha256'] != digest(jd.encode())
            or saved['frozen_packet_sha256'] != packet or saved['lead_review_sha256'] != digest(review_bytes)
            or saved['source_docx_sha256'] != donor['audit']['docx_sha256']):
        raise ValueError('Saved selection inputs drifted.')
    case = {**donor, 'baseline': starting, 'raw_jd_text': jd}
    catalog = starting['stable_analysis']['canonical_requirements']
    model, pool_ats = fresh_links(case, preserve_weak_testing=True)
    selected = select_shadow(model, donor['audit'], json.loads(review_bytes)['review'], 'mixed')
    result = {'job': job['job_id'], 'status': selected['status'], 'source_application': donor['application_id'],
              'source_receipt_sha256': digest(prior_bytes), 'lead_review_sha256': digest(review_bytes),
              'frozen_packet_sha256': packet, 'baseline': baseline, 'selection': selected,
              'projection': model['weak_projection']}
    if selected['status'] != 'selected':
        return result
    projects = selected['proposal']['projects']
    decisions = []
    for link in model['weak_projection']['links']:
        rid, project, wording = link['requirement_id'], link['project'], link['wording']
        matching = [i for i in selected['indices'] if rid in model['bullets'][i].get('weak_ids', ())]
        included = any(model['bullets'][i]['project'] == project and model['bullets'][i]['text'] == wording
                       for i in matching)
        decisions.append({**link, 'included': included, 'shared': len(matching) > 1,
                          'reason': ('Selected and uniquely supplies this weak link in the slate.' if included and len(matching) == 1
                                     else 'Selected with shared weak coverage.' if included
                                     else 'Outside the optimal slate under coverage, word and layout-budget priorities.')})
    pdf_hashes = []

    def render(docx, directory):
        pdf = _render_pdf(docx, directory)
        pdf_hashes.append(digest(pdf.read_bytes()))
        return pdf

    trial = evaluate_lead_document(case, selected['proposal'], selected['leads'], work_root=work, renderer=render)
    before_order = old['native']['docx_project_order']
    after_order = trial['docx_project_order']
    before = {r['project']: r['after'] for r in before_order}
    after = {r['project']: r['after'] for r in after_order}
    for decision in decisions:
        name, wording = decision['project'], decision['wording']
        decision['controlled_addition'] = (
            after.keys() == before.keys() and name in before and wording not in before[name]
            and after[name].count(wording) == 1
            and all(([w for w in bullets if w != wording] if name == project else bullets) == before[project]
                    for project, bullets in after.items()))
    skills = donor['generation']['fit_result']['tailored_skills_used']['skill_lines']
    ats = ats_evidence(catalog, resume_excerpts(projects, skills), jd, scorer_rows=trial.get('requirements', []))
    return {**result, 'trial': trial, 'pdf_sha256': next(iter(pdf_hashes), None),
            'comparison': compare_native_trials(baseline, trial), 'decisions': decisions,
            'word_delta': selected['words'] - old['words'],
            'ats_before': old['ats']['distinct_exact_technologies'],
            'ats_after': ats['distinct_exact_technologies']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with closing(readonly_db(Path('data/applications.db'))) as db, offline_execution('V3.7 weak evidence research'):
        receipt = run(load_case(db, 251, Path.cwd()), *heldout_inputs(db), args.work_root)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(receipt, out, indent=2, ensure_ascii=False)
    print(args.output)


if __name__ == '__main__':
    main()
