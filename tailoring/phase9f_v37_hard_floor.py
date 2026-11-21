"""Bounded research-only selection with explicit per-requirement evidence floors."""
from analysis_stability.stable_evidence_scoring import MATCH_VALUES

HARD = frozenset({'deal_breaker', 'required', 'core'})
LEVELS = ('weak', 'transferable', 'direct')


def _meets(evidence, floor):
    return (MATCH_VALUES[evidence['label']] >= MATCH_VALUES[floor['label']]
            and evidence['strength'] >= floor['strength'])


def select_protected(candidates, requirements, floors, *, max_bullets, max_words, sources,
                     existing=(), fixed_links=None, bonus_order=()):
    """Solve the exact scoped pool. Candidates/links must have passed source review."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import csr_matrix

    if (bonus_order not in ((), ('supporting', 'preferred'), ('preferred', 'supporting'))
            or not 1 <= max_bullets <= 48 or max_words < 1 or not sources):
        raise ValueError('Invalid scoped research policy or budget.')
    if any(rid not in requirements or requirements[rid]['importance'] not in HARD
           or floor['label'] not in LEVELS or not 1 <= floor['strength'] <= 5
           for rid, floor in floors.items()):
        raise ValueError('Hard floors require a frozen hard requirement, positive label and evidence strength.')
    fixed = fixed_links or {}
    projects = {row['project'] for row in candidates}
    seen = {}
    for row in candidates:
        eligible = set(row['sources']).intersection(sources)
        if not eligible:
            continue
        key = (row['project'], row['text'])
        if key in seen:
            if seen[key]['links'] != row['links']:
                raise ValueError('Exact duplicate wording has inconsistent reviewed evidence.')
            seen[key]['sources'] = sorted(set(seen[key]['sources']) | eligible)
            seen[key]['lead'] |= row['lead']
        else:
            seen[key] = {**row, 'sources': sorted(eligible), 'words': len(row['text'].split())}
    pool = [seen[key] for key in sorted(seen)]
    base_receipt = {'floors': floors, 'max_bullets': max_bullets, 'max_words': max_words,
                    'constraint': 'For every protected ID, fixed evidence or at least one selected link must meet both saved label and strength.'}
    missing_leads = sorted(p for p in projects if not any(c['project'] == p and c['lead'] for c in pool))
    if missing_leads:
        return {**base_receipt, 'status': 'withheld', 'reason': 'missing_eligible_lead', 'projects': missing_leads}
    if not projects or len(pool) > 250 or len(requirements) > 250:
        raise ValueError('Research solve requires a nonempty bounded pool of at most 250 candidates and requirements.')
    allowed = HARD | set(bonus_order)
    n = len(pool)
    coverage = [(rid, level) for rid, req in sorted(requirements.items()) if req['importance'] in allowed
                for level in LEVELS]
    size = n + len(coverage)
    rows, lower, upper = [], [], []

    def constrain(coefficients, low, high):
        row = np.zeros(size)
        for index, value in coefficients.items():
            row[index] = value
        rows.append(row)
        lower.append(low)
        upper.append(high)

    for project in sorted(projects):
        group = [i for i, row in enumerate(pool) if row['project'] == project]
        constrain({i: 1 for i in group if pool[i]['lead']}, 1, 1)
        constrain({i: 1 for i in group}, 1, 8)
    constrain({i: 1 for i in range(n)}, 1, max_bullets)
    constrain({i: row['words'] for i, row in enumerate(pool)}, 1, max_words)
    witnesses = {}
    for rid, floor in floors.items():
        eligible = [i for i, row in enumerate(pool) if rid in row['links'] and _meets(row['links'][rid], floor)]
        already_fixed = rid in fixed and _meets(fixed[rid], floor)
        witnesses[rid] = {'fixed': already_fixed, 'eligible_wordings': [pool[i]['text'] for i in eligible]}
        if not already_fixed:
            constrain({i: 1 for i in eligible}, 1, np.inf)
    stages = {category: np.zeros(size) for category in ('hard', *bonus_order)}
    for index, (rid, label) in enumerate(coverage, n):
        if rid in fixed and MATCH_VALUES[fixed[rid]['label']] >= MATCH_VALUES[label]:
            constrain({index: 1}, 1, 1)
        else:
            links = {i: -1 for i, row in enumerate(pool) if rid in row['links']
                     and MATCH_VALUES[row['links'][rid]['label']] >= MATCH_VALUES[label]}
            constrain({index: 1, **links}, -np.inf, 0)
        requirement = requirements[rid]
        previous = ('none', *LEVELS)[LEVELS.index(label)]
        stage = 'hard' if requirement['importance'] in HARD else requirement['importance']
        stages[stage][index] = -round(requirement['weight'] * (MATCH_VALUES[label] - MATCH_VALUES[previous]) * 1_000_000)
    existing = set(existing)
    for name, costs in (
        ('words', [row['words'] for row in pool]),
        ('retain_existing', [-int((row['project'], row['text']) in existing) for row in pool]),
        ('stable_order', list(range(1, n + 1))),
    ):
        stages[name] = np.zeros(size)
        stages[name][:n] = costs
    values = {}
    for name, objective in stages.items():
        if not objective.any() and values:
            values[name] = 0
            continue
        outcome = milp(objective, integrality=np.ones(size), bounds=Bounds(0, 1),
                       constraints=LinearConstraint(csr_matrix(rows), lower, upper),
                       options={'time_limit': 1.0, 'mip_rel_gap': 0.0})
        if outcome.status != 0 or outcome.x is None:
            return {**base_receipt, 'status': 'withheld', 'protected_witnesses': witnesses,
                    'reason': 'floor_or_budget_conflict' if outcome.status == 2 else 'solver_unverified'}
        value = round(float(objective @ np.rint(outcome.x)))
        values[name] = value
        constrain({int(i): objective[i] for i in np.flatnonzero(objective)}, value, value)
    chosen = sorted((row for i, row in enumerate(pool) if outcome.x[i] > .5),
                    key=lambda row: (row['project'], not row['lead'], row['text']))
    return {**base_receipt, 'status': 'selected_proxy', 'protected_witnesses': witnesses,
            'objectives': values, 'selected': chosen, 'words': values['words'],
            'bullet_count': len(chosen)}


def verified_research_trial(baseline, trial, floors=None):
    """The existing compatible-native comparison plus the research page gate."""
    from tailoring.phase9f_v37_document_trial import compare_native_trials

    if baseline.get('pages') != 1 or trial.get('pages') != 1:
        return {'status': 'withheld', 'reason': 'one_page_required'}
    result = compare_native_trials(baseline, trial)
    if result['comparison_status'] != 'verified' or result['hard_regressions']:
        return {'status': 'withheld', 'reason': 'native_identity_or_hard_regression', 'comparison': result}
    if result['native_delta'] < 0:
        return {'status': 'withheld', 'reason': 'native_score_regression', 'comparison': result}
    actual = {row['id']: row for row in trial['requirements']}
    lost = [rid for rid, floor in (floors or {}).items() if rid not in actual
            or not _meets({'label': actual[rid]['match_label'], 'strength': actual[rid].get('evidence_strength') or 0}, floor)]
    if lost:
        return {'status': 'withheld', 'reason': 'native_evidence_floor', 'failed_ids': lost, 'comparison': result}
    return {'status': 'verified', 'comparison': result}


def research_disposition(verification, baseline_bonus, trial_bonus):
    """Retain the existing document on a genuine verified native and coverage tie."""
    if verification['status'] != 'verified':
        return 'withheld'
    if verification['comparison']['native_delta'] > 0:
        return 'native_improvement_for_review'
    deltas = [trial_bonus['categories'][k]['earned'] - baseline_bonus['categories'][k]['earned']
              for k in ('supporting', 'preferred')]
    if all(delta >= 0 for delta in deltas) and any(delta > 0 for delta in deltas):
        return 'research_coverage_improvement_for_review'
    return 'retain_existing'
