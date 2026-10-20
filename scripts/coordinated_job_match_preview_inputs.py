"""Safe standalone-page inputs: existing frozen JDs and synthetic originals only."""
from copy import deepcopy
import json
from pathlib import Path
from scripts.coordinated_acceptance import parents

FIXTURE = Path(__file__).resolve().parents[1]/'tests/fixtures/coordinated_realistic_profiles_v1.json'


def synthetic_cases():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']


def library_items(case):
    """Do not assign résumé-wide skills to a project that did not claim them."""
    items = []
    for section, category in (('projects', 'Project'), ('experience', 'Internship')):
        for record in case['profile'].get(section, []):
            items.append({'id': 100+len(items), 'category': category,
                'title': record.get('title', ''), 'subtitle': record.get('company', ''),
                'period': record.get('date', ''), 'bullets': deepcopy(record.get('bullets', []))})
    # Preserve other supplied sections as explicitly unscoped records, not
    # responsibility ownership under an invented project association.
    remainder = {k: deepcopy(v) for k,v in case['profile'].items() if k not in ('projects','experience') and v}
    if remainder:
        items.append({'id': 900, 'category': 'Other', 'title': 'Unscoped synthetic résumé fields',
                      'source_metadata': remainder})
    return items


def preview_inputs(case_id):
    case = next(c for c in synthetic_cases() if c['id'] == case_id)
    parent = next(p for p in parents() if p['obligation']['object_family'] == case['family'])
    return {'raw_jd_text': parent['raw_jd'], 'jd_profile': {}, 'evidence_items': library_items(case),
            'raw_only_text': case['raw_resume_text']}
