"""Common source-neutral research constraints, separate from production MILP."""
from __future__ import annotations

from itertools import chain

from tailoring.phase9f_certified_selection_v36 import MAX_TOTAL_BULLETS
from tailoring.phase9f_jd_relevance_optimizer_v35 import VERSION as WRITER_VERSION
from tailoring.phase9f_v37_project_leads import SOURCES, bind_project_leads, lead_first

STRATEGIES = {'base_only': {'base'}, 'library_only': {'library'}, 'mixed': {'base', 'library'}}


def select_shadow(model: dict, audit: dict, review: dict, strategy: str, *,
                  max_words: int | None = None, max_bullets: int = MAX_TOTAL_BULLETS,
                  time_limit: float = 2.0) -> dict:
    """Fix reviewed leads, maximize distinct link coverage, then minimize words."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import csr_matrix

    policy = STRATEGIES[strategy]
    review_result = bind_project_leads(audit, review, policy)
    selected_leads = review_result['leads']
    bullets = model['bullets']
    source_tags = {SOURCES[source] for source in policy}
    eligible = sorted((i for i, b in enumerate(bullets) if source_tags.intersection(b['source_labels'])),
                      key=lambda i: (bullets[i]['project'], bullets[i]['text'].casefold(), bullets[i]['text']))
    positions = {idx: column for column, idx in enumerate(eligible)}
    unavailable = [group['project'] for group, _, owned, _ in model['groups']
                   if not set(owned).intersection(positions)]
    if unavailable:
        return {'status': 'structurally_infeasible', 'failure': 'insufficient_candidates',
                'projects_without_candidates': unavailable}
    if review_result['missing']:
        return {**review_result, 'failure': 'lead_structure'}
    n = len(eligible)
    req_ids = sorted(set(chain.from_iterable(bullets[i]['ids'] for i in eligible)))
    weak_ids = sorted({rid for i in eligible for rid in bullets[i].get('weak_ids', ())})
    size = n + len(req_ids) + len(weak_ids)
    word_cap = model['max_words'] if max_words is None else max_words
    if type(word_cap) is not int or word_cap < 1 or not 1 <= max_bullets <= MAX_TOTAL_BULLETS or not 0 < time_limit <= 3:
        raise ValueError('Shadow bounds must specify a positive word budget and a bounded solver timeout.')
    rows, low, high = [], [], []

    def add(values: dict, lower, upper):
        row = np.zeros(size)
        for col, value in values.items():
            row[col] = value
        rows.append(row)
        low.append(lower)
        high.append(upper)

    for group, _, owned, _ in model['groups']:
        project = group['project']
        available = [idx for idx in owned if idx in positions]
        lead_indexes = [idx for idx in available if bullets[idx]['text'] == selected_leads[project]['wording']]
        if len(lead_indexes) != 1:
            return {'status': 'structurally_infeasible', 'failure': 'lead_missing_from_eligible_pool', 'project': project}
        add({positions[idx]: 1 for idx in available}, 1, min(8, len(available)))
        add({positions[lead_indexes[0]]: 1}, 1, 1)
    add({col: 1 for col in range(n)}, len(model['groups']), max_bullets)
    word_cost = {col: bullets[idx]['words'] for idx, col in positions.items()}
    add(word_cost, 0, word_cap)
    weighted = np.zeros(size)
    for col, requirement in enumerate(req_ids, n):
        linked = {positions[idx]: -1 for idx in eligible if requirement in bullets[idx]['ids']}
        add({col: 1, **linked}, -np.inf, 0)
        weighted[col] = -round(model['weights'][requirement] * 1000)
    weak = np.zeros(size)
    for col, requirement in enumerate(weak_ids, n + len(req_ids)):
        linked = {positions[idx]: -1 for idx in eligible if requirement in bullets[idx].get('weak_ids', ())}
        add({col: 1, **linked}, -np.inf, 0)
        weak[col] = -round(model['weak_weights'][requirement] * 1000)
    words = np.zeros(size)
    words[:n] = list(word_cost.values())
    stable = np.zeros(size)
    stable[:n] = range(1, n + 1)
    opts = {'time_limit': time_limit, 'mip_rel_gap': 0.0}
    values = []
    objectives = (weighted, weak, words, stable) if weak_ids else (weighted, words, stable)
    for objective in objectives:
        answer = milp(objective, integrality=np.ones(size), bounds=Bounds(0, 1),
                      constraints=LinearConstraint(csr_matrix(rows), low, high), options=opts)
        if answer.status != 0 or answer.x is None:
            failure = 'word_or_count_budget' if answer.status == 2 and not values else 'solver_unverified'
            return {'status': 'unavailable', 'failure': failure, 'detail': answer.message}
        value = round(float(objective @ np.rint(answer.x)))
        values.append(value)
        add({int(i): objective[i] for i in np.flatnonzero(objective)}, value, value)
    chosen = {idx for idx, col in positions.items() if answer.x[col] > 0.5}
    projects = []
    for group, _, owned, original in model['groups']:
        project = group['project']
        retained = sorted((i for i in owned if i in chosen),
                          key=lambda i: (-sum(model['weights'][rid] for rid in bullets[i]['ids']),
                                         bullets[i]['text'].casefold(), bullets[i]['text']))
        after = lead_first(project, [bullets[i]['text'] for i in retained], selected_leads)
        lookup = {bullets[i]['text']: bullets[i] for i in retained}
        projects.append({'project': project, 'before': [bullets[i]['text'] for i in original],
                         'after': after, 'before_count': len(original), 'after_count': len(after),
                         'sources': [lookup[text]['source_labels'] for text in after],
                         'supported_jd_ids': [sorted(lookup[text]['ids']) for text in after],
                         'lead': selected_leads[project], 'supporting_bullets': after[1:]})
        if weak_ids:
            projects[-1]['weak_jd_ids'] = [sorted(lookup[text].get('weak_ids', ())) for text in after]
    proposal = {'version': WRITER_VERSION, 'status': 'candidate', 'changed': True,
                'variable_bullet_counts': True, 'project_set_unchanged': True, 'projects': projects}
    return {'status': 'selected', 'leads': selected_leads, 'indices': sorted(chosen),
            **({'weak_proxy_points': -values[1] / 1000} if weak_ids else {}),
            'proxy_saved_points': -values[0] / 1000, 'words': values[-2], 'word_cap': word_cap,
            'proposal': proposal}
