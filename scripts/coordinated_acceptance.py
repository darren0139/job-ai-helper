"""Safe synthetic inputs for the real default-OFF and gated analysis entry point."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from analysis_stability import stable_evidence_scoring as n
from analysis_stability.coordinated_integration import canonicalise_coordinated_requirements
from analysis_stability.coordinated_ownership import extract_obligation

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def parents():
    oracle = json.loads((ROOT/'tests/fixtures/coordinated_action_ownership_oracle_v1.json').read_text(encoding='utf-8'))
    corpus = json.loads((ROOT/'tests/fixtures/per_jd_scoring_audit.json').read_text(encoding='utf-8'))
    jobs = {r['job_id']: r for r in corpus['snapshot']['audit']['corpus']['jobs']}
    output = []
    for parent in oracle['parents']:
        raw = jobs[parent['job_id']]['frozen_inputs']['raw_jd_text']
        canonical = canonicalise_coordinated_requirements({}, raw)
        row = next(r for r in canonical['requirements'] if
                   r.get('scoring_parent_occurrence_id') == parent['parent_occurrence_id'])
        output.append({**parent, 'raw_jd': raw, 'requirement': row,
                       'obligation': extract_obligation(row)})
    return output


def scenarios(parent):
    o = parent['obligation'];obj = o['object']
    verbs = {'design': 'designed', 'develop': 'developed', 'maintain': 'maintained', 'deploy': 'deployed'}
    all_verbs = ', '.join(verbs[a['action']] for a in o['actions'])
    lifecycle = verbs[o['actions'][-1]['action']]
    short = {'pipeline': 'data pipelines', 'embedded': 'embedded software modules',
             'fullstack': 'full-stack applications', 'backend': 'backend services',
             'cloud': 'cloud applications'}[o['object_family']]
    return {
        'Maintenance only': ['Maintained '+obj+'.'],
        'Design and development': ['Designed and developed '+obj+'.'],
        'All mandatory actions': ['I '+all_verbs+' '+obj+'.'],
        'Passive first-person ownership': [obj+' were '+all_verbs+' by me.'],
        'Relative-clause ownership': ['Used '+obj+' which I '+all_verbs+'.'],
        'Shortened object': ['I '+all_verbs+' '+short+'.'],
        'API consumption': ['Consumed REST APIs using HTTP requests and JSON responses.'],
        'PostgREST integration': ['Integrated Supabase PostgREST generated REST APIs for CRUD and authentication.'],
        'Complete alternative second bullet': ['Maintained '+obj+'. Learned to design and develop '+obj+'.',
                                              obj+' were '+all_verbs+' by me.'],
        'Zero-overlap topic recovery': ['Configured ESP32 GPIO interrupts.'],
        'Separate partial records': ['Designed '+obj+'.', 'Developed '+obj+'.', lifecycle.capitalize()+' '+obj+'.'],
        'Denied lifecycle': ['Designed and developed '+obj+'. Never '+lifecycle+' '+obj+'.'],
    }


def analyze(parent, evidence, enabled):
    profile = {'projects': [{'title': 'Synthetic acceptance project', 'bullets': evidence}],
               'experience': [], 'education': [], 'skills': {}}
    canonical = n.canonicalise_requirements({}, parent['raw_jd'])
    keyword = n.build_deterministic_keyword_match(requirements=canonical['requirements'],
        acronym_map=canonical['acronym_map'], resume_profile=profile, raw_resume_text='')
    return n.build_stable_analysis(jd_profile={}, keyword_match=keyword,
        raw_jd_text=parent['raw_jd'], resume_profile=profile, raw_resume_text='',
        retrieval_mode_override='off', coordinated_actions_enabled=enabled)


def comparison(parent, scenario):
    return deepcopy(_comparison_cached(parent['parent_occurrence_id'], scenario))


@lru_cache(maxsize=80)
def _comparison_cached(pid, scenario):
    parent = next(p for p in parents() if p['parent_occurrence_id'] == pid)
    evidence = scenarios(parent)[scenario]
    before = analyze(parent, evidence, False)
    after = analyze(parent, evidence, True)
    pid = parent['parent_occurrence_id']
    relevant = lambda data: [r for r in data['canonical_requirements']
                             if r.get('scoring_parent_occurrence_id') == pid]
    return {'job_id': parent['job_id'], 'parent_occurrence_id': pid, 'scenario': scenario,
            'synthetic_evidence': evidence, 'before': before, 'after': after,
            'before_rows': relevant(before), 'after_rows': relevant(after)}


def all_results():
    return [comparison(parent, scenario) for parent in parents() for scenario in scenarios(parent)]
