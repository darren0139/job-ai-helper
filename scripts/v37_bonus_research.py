"""One bounded factual Job 493 bonus placement comparison. All sources are read-only."""
import argparse
from copy import deepcopy
from contextlib import closing
from pathlib import Path
import json

from scripts.v37_lead_ats_experiment import fresh_links
from scripts.v37_selection_quality import digest, heldout_inputs
from tailoring.phase9f_joint_resume_optimizer_v2_6 import _render_pdf
from tailoring.phase9f_v37_ats import ats_evidence, resume_excerpts
from tailoring.phase9f_v37_bonus_coverage import bonus_catalog, bonus_summary, reviewed_bonus_links
from tailoring.phase9f_v37_corpus_benchmark import load_case, readonly_db
from tailoring.phase9f_v37_hard_floor import HARD, research_disposition, select_protected, verified_research_trial
from tailoring.phase9f_v37_neutral_selection import select_shadow
from tailoring.phase9f_v37_project_leads import SOURCES, evaluate_lead_document
from taxonomy_discovery.offline_execution import offline_execution


REFERENCE = Path('reports/v37_job493_repaired_selection.json')
LEAD_REVIEW = Path('reports/v37_app156_lead_review.json')


def _order(slate):
    return {row['project']: row['after'] for row in slate['proposal']['projects']}


def _proposal(template, selected):
    proposal = deepcopy(template)
    for row in proposal['projects']:
        chosen = [bullet for bullet in selected if bullet['project'] == row['project']]
        row['after'] = [bullet['text'] for bullet in chosen]
        row['after_count'] = len(chosen)
        row['supporting_bullets'] = row['after'][1:]
        row['sources'] = [[SOURCES[source] for source in bullet['sources']] for bullet in chosen]
        row['supported_jd_ids'] = [sorted(bullet['links']) for bullet in chosen]
        row.pop('weak_jd_ids', None)
    return proposal


def trial(donor, starting, job, packet, work):
    historical, lead_bytes = REFERENCE.read_bytes(), LEAD_REVIEW.read_bytes()
    prior = json.loads(historical)
    slate = prior['selection']
    baseline = prior['trial']
    jd = starting['raw_jd_text']
    if (baseline['jd_sha256'] != digest(jd.encode()) or prior['job'] != job['job_id']
            or baseline['layout_reference_sha256'] != donor['audit']['docx_sha256']
            or prior['lead_review_sha256'] != digest(lead_bytes) or prior['frozen_packet_sha256'] != packet):
        raise ValueError('The saved repaired reference is incompatible.')
    original = starting['stable_analysis']['canonical_requirements']
    catalog = bonus_catalog(original, jd, expected_jd=jd)
    existing = {(project, text) for project, bullets in _order(slate).items() for text in bullets}
    leads = {(project, row['wording']) for project, row in slate['leads'].items()}
    query = next(p for p in donor['audit']['projects'] if p['project'].startswith('QueryAI'))
    testing = next(row for row in prior['decisions'] if row['included'])
    base_db, library_db = query['base'][2]['text'], query['library'][1]['text']
    database = next(rid for rid,r in catalog.items() if r['text'] == 'Knowledge of databases (SQL / NoSQL) is an advantage')
    software = next(rid for rid,r in catalog.items() if r['text'] == 'Contribute to continuous improvement of software development best practices')
    fullstack = next(rid for rid,r in catalog.items() if r['text'] == 'Familiar with full-stack development')
    lead = slate['leads'][query['project']]['wording']
    reviews = [
        (query['project'], lead, fullstack, 'direct', 4, 'Exact source describes building full-stack workflows.'),
        (query['project'], lead, database, 'transferable', 3, 'Broad team workflow names PostgreSQL integration and does not specify the individual database work.'),
        (query['project'], base_db, database, 'direct', 4, 'Exact Base wording describes implementer-level database queries and access policy.'),
        (query['project'], library_db, database, 'direct', 4, 'Exact Library wording describes implementing database access and Row-Level Security.'),
        (testing['project'], testing['wording'], software, 'transferable', 3, 'Automating tests and CI supports improving development practices.'),
    ]
    scoped = existing | {(query['project'], text) for text in (base_db, library_db)}
    excerpts = {
        key: {'project': key[0], 'text': key[1], 'section': 'projects', 'verified': True,
              'independently_attested': False, 'provenance': [
                  {'source': source, 'position': index}
                  for p in donor['audit']['projects'] if p['project'] == key[0]
                  for source in SOURCES for index, row in enumerate(p[source], 1) if row['text'] == key[1]]}
        for key in sorted(scoped)
    }
    if any(not row['provenance'] for row in excerpts.values()):
        raise ValueError('The scoped slate contains unproven source wording.')
    accepted, withheld = reviewed_bonus_links(catalog, excerpts, [
        {'requirement_id': rid, 'excerpt': (p, t), 'wording': t, 'label': label, 'strength': strength, 'basis': basis}
        for p,t,rid,label,strength,basis in reviews
    ])
    if withheld:
        raise ValueError('The scoped factual review failed JD or document source validation.')
    floors = {r['id']: {'label': r['match_label'], 'strength': r['evidence_strength']}
              for r in baseline['requirements'] if r['importance'] in HARD and r['match_label'] != 'none'}
    candidates = []
    for key, excerpt in excerpts.items():
        links = dict(accepted.get(key, {}))
        for req in baseline['requirements']:
            if req['id'] in floors and key in existing and key[1] in req['evidence']:
                links[req['id']] = floors[req['id']]
        candidates.append({'project': key[0], 'text': key[1], 'lead': key in leads, 'links': links,
                           'sources': sorted({item['source'] for item in excerpt['provenance']})})
    # A controlled single extra slot and the same word bound for all strategies.
    cap = slate['words'] + max(len(base_db.split()), len(library_db.split()))
    limits = {'max_bullets': len(existing) + 1, 'max_words': cap, 'sources': {'base', 'library'}, 'existing': existing}
    forward = select_protected(candidates, catalog, floors, **limits, bonus_order=('supporting', 'preferred'))
    reverse = select_protected(candidates, catalog, floors, **limits, bonus_order=('preferred', 'supporting'))
    hard_only = select_protected(candidates, catalog, floors, **limits)
    case = {**donor, 'baseline': starting, 'raw_jd_text': jd}
    legacy, _ = fresh_links(case, preserve_weak_testing=True)
    for row in legacy['bullets']:
        if (row['project'], row['text']) not in scoped:
            row['source_labels'] = []
    current = select_shadow(legacy, donor['audit'], json.loads(lead_bytes)['review'], 'mixed',
                            max_words=cap, max_bullets=len(existing) + 1)
    reports = {}
    baseline_bonus = bonus_summary(catalog, accepted, sorted(existing))
    native_cache = {tuple((key, tuple(value)) for key,value in _order(slate).items()): (baseline, prior['pdf_sha256'])}
    for name, solve in (('current_research', current), ('hard_only', hard_only),
                        ('supporting_first', forward), ('preferred_first', reverse)):
        if solve['status'] not in {'selected', 'selected_proxy'}:
            reports[name] = solve
            continue
        proposal = solve['proposal'] if name == 'current_research' else _proposal(slate['proposal'], solve['selected'])
        key = tuple((r['project'], tuple(r['after'])) for r in proposal['projects'])
        if key not in native_cache:
            if len(native_cache) >= 3:
                reports[name] = {**solve, 'status': 'withheld', 'reason': 'bounded_render_limit'}
                continue
            pdf_hash = []

            def render(path, folder):
                pdf = _render_pdf(path, folder)
                pdf_hash.append(digest(pdf.read_bytes()))
                return pdf

            native = evaluate_lead_document(case, proposal, slate['leads'], work_root=work, renderer=render)
            native_cache[key] = (native, next(iter(pdf_hash), None))
        native, pdf_hash = native_cache[key]
        picked = [(p,t) for p,texts in key for t in texts]
        skill_lines = donor['generation']['fit_result']['tailored_skills_used']['skill_lines']
        ats = ats_evidence(original, resume_excerpts(proposal['projects'], skill_lines), jd,
                           scorer_rows=native.get('requirements', []))
        verification = verified_research_trial(baseline, native, floors)
        bonus = bonus_summary(catalog, accepted, picked)
        reports[name] = {**solve, 'proposal': proposal, 'native': native, 'pdf_sha256': pdf_hash,
                         'verification': verification, 'bonus': bonus,
                         'research_disposition': research_disposition(verification, baseline_bonus, bonus),
                         'exact_ats_technologies': ats['distinct_exact_technologies'],
                         'wording_added': sorted(set(picked)-existing), 'wording_removed': sorted(existing-set(picked))}
    return {'job_id': job['job_id'], 'jd_sha256': baseline['jd_sha256'], 'donor': donor['application_id'],
            'scope': 'Two reviewed wording alternatives on the same existing Job 493 slate. One analyst reviewed exact source evidence.',
            'source_receipt_sha256': digest(historical), 'source_docx_sha256': donor['audit']['docx_sha256'],
            'lead_review_sha256': digest(lead_bytes), 'frozen_packet_sha256': packet,
            'baseline': baseline, 'baseline_bonus': baseline_bonus,
            'source_reviews': [{'project': p, 'wording': t, 'requirement_id': rid, 'label': label,
                                'strength': strength, 'basis': basis} for p,t,rid,label,strength,basis in reviews],
            'withheld_bonus_reviews': withheld, 'floors': floors, 'max_words': cap,
            'max_bullets': limits['max_bullets'], 'variants': reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with closing(readonly_db(Path('data/applications.db'))) as db, offline_execution('Research-only bonus placement'):
        result = trial(load_case(db, 251, Path.cwd()), *heldout_inputs(db), args.work_root)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    print(args.output)


if __name__ == '__main__':
    main()
