"""Research projection of exact weak Core QA citations, separate from full coverage."""
import re
from collections import defaultdict

from tailoring.phase9f_v37_project_leads import SOURCES
from tailoring.phase9f_v37_testing_gate import apply_shadow_testing_gate
from tailoring.stable_tailoring_ranking import _coverage_points


def project_weak_testing_links(model, catalog, native_rows, eligible_ids, profile, text):
    """Update only the scratch model. Leave ATS and native scoring outputs intact."""
    candidates = {(b['project'], b['text']): b for b in model['bullets']}
    parent_fractions = defaultdict(float)
    for rid, req in catalog.items():
        parent = req.get('scoring_parent_occurrence_id') or req.get('atomic_group_id') or rid
        parent_fractions[parent] += float(req.get('group_weight_fraction', 1))
    weak_rows = [r for r in native_rows if r['requirement_id'] in eligible_ids
                 and r['importance'] in {'deal_breaker', 'required', 'core'}
                 and r.get('capability_id') == 'quality.qa_testing'
                 and r.get('semantic_type') == 'role_responsibility' and r.get('match_label') == 'weak']
    validated, decisions = apply_shadow_testing_gate(weak_rows, resume_text=text, resume_profile=profile)
    weights = {}
    links = []
    for row in validated:
        rid = row['requirement_id']
        # The original projection treated even a weak native-only quote as a full link.
        for bullet in model['bullets']:
            bullet['ids'].discard(rid)
        requirement = catalog[rid]
        parent = requirement.get('scoring_parent_occurrence_id') or requirement.get('atomic_group_id') or rid
        if not (0 < float(requirement.get('group_weight_fraction', 1)) <= 1
                and 0 < parent_fractions[parent] <= 1.000001):
            continue
        for excerpt in row['evidence']:
            match = re.fullmatch(r'resume_profile\.projects\[(\d+)\]\.bullets\[(\d+)\]',
                                 excerpt.get('source') or '')
            if not match or excerpt['section'] != 'projects':
                continue
            project_index, bullet_index = map(int, match.groups())
            project = profile['projects'][project_index]
            wording = project['bullets'][bullet_index]
            bullet = candidates.get((project['title'], wording))
            if not bullet or wording != excerpt['text'] or not set(bullet['source_labels']).intersection(SOURCES.values()):
                continue
            ids = bullet.setdefault('weak_ids', set())
            if rid in ids:
                continue
            ids.add(rid)
            links.append({'project': project['title'], 'wording': wording, 'requirement_id': rid,
                          'requirement': row['text'], 'importance': row['importance'], 'label': 'weak',
                          'evidence_strength': row['evidence_strength'], 'citation': excerpt,
                          'provenance': bullet['source_labels']})
            _, points = _coverage_points([{'requirement_id': rid, 'match_label': 'weak'}], catalog)
            weights.update(points)
    model['weak_weights'] = weights
    return {'links': links, 'decisions': decisions}
