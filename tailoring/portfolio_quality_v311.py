"""Opt-in, deterministic portfolio PROJECT selection, using saved evidence only.

Pre-fit portfolio utility is NOT a native Job Match score or a page-fit guarantee.
No AI calls, database IO, fitter calls, document writes, or approval changes.
"""
from __future__ import annotations
from copy import deepcopy
from itertools import combinations
from math import isfinite
from typing import Any

VERSION = 'portfolio-quality-selection-v311-preview-1'
DIRECT = frozenset({'direct', 'transferable'})
HARD = frozenset({'required', 'core'})
MAX_POOL = 8
MAX_SHOW = 5


def _key(row: dict[str, Any]) -> str:
    pid = str(row.get('project_id') or '').strip().casefold()
    if pid:
        return 'id:' + pid
    title = ' '.join(str(row.get('title') or row.get('display_title') or '').casefold().split())
    return 'title:' + title if title else ''


def _pool(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError('Projects result must be a mapping')
    result = payload.get('adaptive_fit_original_projects')
    if result is None:
        result = payload.get('recommended_projects')
    if not isinstance(result, list) or not (1 <= len(result) <= MAX_POOL):
        raise ValueError('Saved generated project pool is missing or oversized')
    seen = set()
    for p in result:
        if not isinstance(p, dict) or not _key(p) or _key(p) in seen:
            raise ValueError('Project identity is missing or duplicated')
        b = p.get('draft_bullets')
        if not isinstance(b, list) or not b or any(not isinstance(s, str) or not s.strip() for s in b):
            raise ValueError('Project lacks validated saved draft bullets')
        seen.add(_key(p))
    return result


def _evidence(project: dict[str, Any]) -> tuple[dict[str, str], bool]:
    """Count one independently identified requirement at most once; weak is never credit."""
    found: dict[str, str] = {}
    had_unknown = False
    matches = project.get('requirement_matches')
    if not isinstance(matches, list):
        return found, True
    for m in matches:
        if not isinstance(m, dict):
            had_unknown = True
            continue
        label = str(m.get('match_label') or '').strip().casefold()
        if label not in DIRECT:
            continue
        rid = str(m.get('requirement_id') or '').strip()
        if not rid:
            had_unknown = True
            continue
        importance = str(m.get('importance') or m.get('requirement_importance') or '').strip().casefold()
        if importance not in {'required','core','preferred','supporting'}:
            importance = 'unknown'
            had_unknown = True
        rank = {'required':5,'core':4,'preferred':3,'supporting':2,'unknown':1}
        if rank[importance] > rank.get(found.get(rid), 0):
            found[rid] = importance
    return found, had_unknown


def _fit_score(project: dict[str, Any]) -> float:
    try:
        n = float(project.get('project_fit_score') or 0)
        return max(0.0, min(100.0, n)) if isfinite(n) else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _candidate(pool: list[dict[str, Any]], indices: tuple[int, ...], required_set: set[str]) -> dict[str, Any]:
    covered: dict[str, str] = {}
    missing_metadata = False
    for i in indices:
        evidence, unknown = _evidence(pool[i])
        missing_metadata |= unknown
        for rid, importance in evidence.items():
            rank = {'required':5,'core':4,'preferred':3,'supporting':2,'unknown':1}
            if rank[importance] > rank.get(covered.get(rid), 0):
                covered[rid] = importance
    protected = {rid for rid, importance in covered.items() if importance in HARD}
    hard_loss = sorted(required_set - protected)
    weights = {'required':40.0,'core':40.0,'preferred':10.0,'supporting':3.0,'unknown':1.0}
    coverage = sum(weights[kind] for kind in covered.values())
    depth = sum(2.0 * min(3, len(pool[i]['draft_bullets'])) for i in indices)
    fit_tie = sum(_fit_score(pool[i]) for i in indices) / 30.0
    # Each additional project has header and bullet cost on a one-page document.
    utility = coverage + depth + fit_tie - 7.0 * len(indices)
    sparse = [i for i in indices if len(pool[i]['draft_bullets']) == 1]
    return dict(
        indices=list(indices), selected_keys=[_key(pool[i]) for i in indices],
        selected_count=len(indices), verified_requirement_count=len(covered),
        hard_required_core_covered=len(protected), hard_required_core_lost=len(hard_loss),
        coverage_units=round(coverage,3), depth_units=round(depth,3),
        proxy_utility=round(utility,4), one_bullet_projects=len(sparse),
        uncertain_evidence=missing_metadata,
    )


def optimize_portfolio_projects(projects: dict[str, Any], *, minimum: int=2,
                                maximum: int=5) -> dict[str, Any]:
    """Explore bounded temporary combinations and return ONE selected fitted input.

    Existing normal fit lifecycle persists at most its single chosen generation.
    Never delete or rewrite the input; current V3.9/3.10 fitter owns bullet changes.
    """
    if type(minimum) is not int or type(maximum) is not int or minimum != 2 or maximum != 5:
        raise ValueError('V3.11 supports default minimum=2 and maximum=5 only')
    pool = _pool(projects)
    all_evidence = [_evidence(p) for p in pool]
    hard = {rid for evidence, _ in all_evidence for rid, kind in evidence.items() if kind in HARD}
    if not any(evidence for evidence,_ in all_evidence):
        raise ValueError('Portfolio quality held: no independently linked direct/transferable JD evidence')
    start = min(minimum, len(pool))
    end = min(maximum, len(pool))
    candidates = [_candidate(pool, indices, hard)
                  for count in range(start, end+1)
                  for indices in combinations(range(len(pool)), count)]
    allowed = [c for c in candidates if c['hard_required_core_lost'] == 0]
    if not allowed:
        raise ValueError('Portfolio quality held: no 2–5 project slate preserves all recorded Required/Core project coverage')
    # Stable order and smaller slates win exact ties, but no unverified JD match gets credit.
    winner = max(allowed, key=lambda c: (c['proxy_utility'], -c['selected_count'],
                                         -c['one_bullet_projects'], tuple(-i for i in c['indices'])))
    chosen = set(winner['indices'])
    out = deepcopy(projects)
    out['adaptive_fit_original_projects'] = deepcopy(pool)
    out['recommended_projects'] = [deepcopy(p) for i,p in enumerate(pool) if i in chosen]
    excluded = [i for i in range(len(pool)) if i not in chosen]
    uncertainty = sum(1 for _, flag in all_evidence if flag)
    out['portfolio_quality_selection'] = {
        'version': VERSION, 'mode': 'portfolio_quality', 'status': 'proxy_selected_not_native_verified',
        'input_project_count': len(pool), 'candidate_count': len(candidates),
        'hard_floor_candidate_count': len(allowed),
        'selected_project_ids': winner['selected_keys'],
        'excluded_project_ids': [_key(pool[i]) for i in excluded],
        'selected_count': winner['selected_count'],
        'minimum_rule': ('one_project_exception_only_saved_project' if len(pool)==1 else 'at_least_two'),
        'target_supporting_bullet_depth': 2,
        'one_bullet_selected': winner['one_bullet_projects'],
        'jd_linked_evidence_unknown_projects': uncertainty,
        'score_kind': 'selection_proxy_not_native_job_match',
        'provisional_utility': winner['proxy_utility'],
        'baseline': _candidate(pool, tuple(range(len(pool))), hard),
        'winner': deepcopy(winner),
        'top_candidates': [deepcopy(c) for c in sorted(
            candidates, key=lambda c: (-int(c['hard_required_core_lost']==0),
                                       -c['proxy_utility'], c['selected_count'], tuple(c['indices'])))[:6]],
        'note': ('Candidate comparisons are saved-evidence project-selection estimates only. '
                 'No independent DOCX fit/native Job Match is performed for each candidate. '
                 'The selected slate must pass normal one-page fitting, actual DOCX readback, '
                 'native Phase 8 and Required/Core verification before approval.'),
        'no_new_content_or_job_match_credit': True,
        'no_candidate_generations_persisted': True,
    }
    out['adaptive_fit_selection'] = {
        'policy_version': VERSION, 'mode': 'portfolio_quality',
        'selected_project_ids': winner['selected_keys'],
        'excluded_project_ids': [_key(pool[i]) for i in excluded],
        'original_generated_count':len(pool), 'selected_count':len(chosen),
        'source':'saved_generated_project_bullets_only',
        'no_new_content_or_job_match_credit': True,
    }
    return out
