"""Bounded large-pool source preparation for V3.5/V3.7.

Small pools retain the historical V3.1 preparation and V3.5 local enumeration.
Large pools are not truncated to top-N bullets. All exact source candidates
are passed to the existing MILP when within its scope; fallback uses a bounded
local beam. No native scoring, approval, or document mutation here.
"""
from __future__ import annotations
from copy import deepcopy
from collections import Counter
from tailoring.phase9f_joint_resume_optimizer_v2_6 import (
    _get_rank, _key, _text, _points, _rank_weights, _source_pool, _support,
    MAX_PROJECTS, MAX_POOL_PER_PROJECT, MAX_BULLETS_PER_PROJECT, MAX_WORDS)

VERSION = 'phase9f-v312b214b2-large-pool-v1'
MAX_LARGE_PROJECT_POOL = 128
MAX_LARGE_TOTAL_POOL = 256
LOCAL_WIDTH = 24
# At most 128 + 7*24*128 evaluations, plus the incumbent, per large project.


def prepare_sources(audit, projects, *, evaluator=None, legacy_builder):
    """Use unchanged legacy builder for small inputs; skip its search for large.

    Return the same source_comparison row contract. Source-only is not a
    proposal; callers must independently select and gate a real challenger.
    """
    def hold(reason):
        return {'version': VERSION, 'status': 'withheld', 'reason': reason,
                'projects': []}
    if (not isinstance(audit, dict) or audit.get('verified') is not True
            or not isinstance(projects, dict)):
        return legacy_builder(audit, projects, evaluator=evaluator)
    sections = audit.get('projects')
    if not isinstance(sections, list) or not 1 <= len(sections) <= MAX_PROJECTS:
        return legacy_builder(audit, projects, evaluator=evaluator)
    if any(not isinstance(s, dict) for s in sections):
        return hold('Malformed frozen project section.')
    pools = []
    for section in sections:
        pool, error = _source_pool(section, max_pool=MAX_LARGE_PROJECT_POOL)
        if error:
            return hold(_text(section.get('project')) + ': ' + error)
        pools.append(pool)
    if all(len(pool) <= MAX_POOL_PER_PROJECT for pool in pools):
        return legacy_builder(audit, projects, evaluator=evaluator)
    if sum(map(len, pools)) > MAX_LARGE_TOTAL_POOL:
        return hold('Complete frozen candidate pool exceeds large-pool total limit.')
    names = [_text(s.get('project')) for s in sections]
    if not all(names) or len(set(map(_key, names))) != len(names):
        return hold('Final project identities missing or ambiguous.')
    if evaluator is None:
        from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
        evaluator = build_bullet_evidence_priorities
    weights, kinds, groups, counts = {}, {}, [], []
    baseline_ids = set()
    baseline_words = baseline_count = 0
    for name, section, pool in zip(names, sections, pools):
        rank = _get_rank(projects, name)
        if rank is None:
            return hold(name + ': missing or ambiguous frozen ranking.')
        local, error = _rank_weights(rank)
        if error:
            return hold(name + ': ' + error)
        for rid, w in local.items():
            weights[rid] = max(weights.get(rid, 0.), w)
        seen_ids = set()
        for req in rank['requirement_matches']:
            rid = _text(req.get('requirement_id'))
            if not rid or rid in seen_ids:
                return hold(name + ': missing or duplicate saved JD requirement identity.')
            seen_ids.add(rid)
            if rid not in local:
                continue
            kind = _text(req.get('importance')).casefold()
            if rid in kinds and kinds[rid] != kind:
                return hold('Conflicting importance for JD requirement ' + rid)
            kinds[rid] = kind
        original = section.get('final')
        if not isinstance(original, list) or not 1 <= len(original) <= MAX_BULLETS_PER_PROJECT:
            return hold(name + ': invalid final bullet count.')
        initial = [_key(row['text']) for row in original]
        if not all(initial) or len(set(initial)) != len(initial):
            return hold(name + ': ambiguous final wording.')
        bykey = {_key(row['text']): row for row in pool}
        if not set(initial) <= bykey.keys():
            return hold(name + ': missing actual final wording.')
        support, error = _support(pool, deepcopy(rank), evaluator)
        if support is None:
            return hold(name + ': ' + error)
        rows = []
        for row, ids in zip(pool, support):
            ids = set(ids) & local.keys()
            in_a = _key(row['text']) in initial
            if in_a:
                baseline_ids.update(ids)
                baseline_words += row['words']
                baseline_count += 1
            rows.append({'text': row['text'], 'source_labels': list(row['sources']),
                         'saved_jd_ids': sorted(ids), 'word_count': row['words'],
                         'in_original_a': in_a, 'selected_for_proposed_b': in_a})
        groups.append({'project': name, 'candidates': rows})
        counts.append({'project': name, 'distinct_candidates': len(rows)})
    if not weights or baseline_words > MAX_WORDS or baseline_count > 48:
        return hold('Missing saved weighted JD links or incumbent outside bounded word/count scope.')
    for group in groups:
        for row in group['candidates']:
            row['standalone_saved_coverage_points'] = _points(set(row['saved_jd_ids']), weights)
    return {'version': VERSION, 'status': 'no_proxy_gain', 'changed': False,
            'reason': 'Complete frozen source inventory prepared; no selection performed by preparation.',
            'projects': [], 'baseline_points': _points(baseline_ids, weights),
            'proposed_points': _points(baseline_ids, weights),
            'source_comparison': {
                'meaning': 'Exact frozen wording and saved JD links; preparation is not a selection decision.',
                'decision_basis': 'All validated source candidates; incumbent membership only until search.',
                'limits': 'No candidate truncated; actual DOCX verification remains mandatory.',
                'projects': groups,
                'large_pool_preparation': {'version': VERSION, 'project_counts': counts,
                    'total_candidates': sum(map(len, pools)), 'source_candidates_discarded': 0,
                    'max_project_pool': MAX_LARGE_PROJECT_POOL, 'max_total_pool': MAX_LARGE_TOTAL_POOL,
                    'legacy_search_skipped': True}}}


def bounded_local_slates(candidates, base, counts, score, order, space, stability):
    """Expand deterministic bounded beams, not combinations(n,k) on large n.

    Every candidate receives a singleton evaluation. Retain diverse coverage,
    compact and stable states. The actual incumbent is explicitly included.
    Approximation: does not promise all possible subsets or global optimality.
    """
    n = len(candidates)
    if not 1 <= n <= MAX_LARGE_PROJECT_POOL:
        raise ValueError('Local candidate count outside bounded scope')
    counts = tuple(counts)
    base = tuple(sorted(base))
    seen_count = 0
    outputs = {}
    parents = [()]
    freq = Counter(r for c in candidates for r in c['saved_jd_ids'])
    for size in range(1, max(counts) + 1):
        combos = {tuple(sorted((*parent, i))) for parent in parents for i in range(n) if i not in parent}
        # Preserve incumbent prefixes as explicit anchors at each depth.
        if size <= len(base):
            combos.add(base[:size])
        level = [score(ix) for ix in sorted(combos)]
        seen_count += len(level)
        if size in counts:
            outputs.update((s['ix'], s) for s in level)
        # Deterministic priority streams; rarity favors low-frequency links,
        # without introducing new evidence or changing the final objective.
        rarity = lambda s: (-sum(1/freq[r] for r in sorted(s['ids'])), order(s))
        ranked = sorted(level, key=order)[:10]
        lean = sorted(level, key=space)[:5]
        stable = sorted(level, key=stability)[:5]
        rare = sorted(level, key=rarity)[:4]
        parents = list(dict.fromkeys(s['ix'] for s in ranked+lean+stable+rare))
        if size < len(base) and base[:size] not in parents:
            parents = parents[:LOCAL_WIDTH-1] + [base[:size]]
    if base not in outputs:
        outputs[base] = score(base)
        seen_count += 1
    return list(outputs.values()), {'version': VERSION, 'method': 'bounded_local_beam',
        'pool_candidates': n, 'singleton_candidates_evaluated': n,
        'local_slate_evaluations': seen_count, 'beam_width': LOCAL_WIDTH,
        'source_candidates_discarded': 0, 'incumbent_retained': True,
        'global_optimum_claim': False}
