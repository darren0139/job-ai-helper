"""Read-only saved-JD coverage scores for V3.7 same-work candidates.

Never score actual DOCX evidence or claim a factual bullet winner. One source
wording gets one credit per distinct saved requirement identity. Protected
Required/Core distinct contributions remain visible instead of being discarded.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

VERSION = 'phase9f-v3.8-saved-jd-bullet-points-v1'
HARD = frozenset({'required', 'core', 'deal_breaker'})


def _norm(value: Any) -> str:
    return ' '.join(str(value or '').split()).casefold()


def _weights(projects: dict, comparison: dict) -> tuple[dict, dict, str]:
    """Use the production requirement ranking contract, not a new weighting formula."""
    from tailoring.phase9f_evidence_optimizer_v33 import _metadata
    weights, labels, error = _metadata(projects, comparison)
    if error or not weights:
        return {}, {}, str(error or 'Saved JD weights unavailable.')
    if any(type(n) not in (int, float) or not isfinite(n) or n <= 0 for n in weights.values()):
        return {}, {}, 'Nonfinite or invalid saved JD weight.'
    return weights, labels, ''


def _importance(projects: dict, groups: list[dict], weights: dict) -> tuple[dict, str]:
    from tailoring.phase9f_joint_resume_optimizer_v2_6 import _get_rank
    result = {}
    for group in groups:
        rank = _get_rank(projects, str(group.get('project') or ''))
        if not isinstance(rank, dict):
            return {}, 'Saved ranking missing for project.'
        for row in rank.get('requirement_matches') or []:
            rid = str(row.get('requirement_id') or '') if isinstance(row, dict) else ''
            if rid not in weights:
                continue
            kind = str(row.get('importance') or 'unknown').casefold()
            if rid in result and result[rid] != kind:
                return {}, 'Saved requirement importance conflicts across projects.'
            result[rid] = kind
    return result, ''


def _points(ids: set[str], weights: dict) -> float:
    return round(sum(weights[rid] for rid in ids), 4)


def score_saved_bullets(proposal: dict, projects: dict) -> dict:
    """Score exact source bullets and verify any dedupe *proposal* avoids a pair.

    Standalone points are NOT native Match scores. Marginal points are computed
    only against the proposed whole-résumé slate, not a modelled independent
    swap. A real final document still needs separate native scoring.
    """
    if not isinstance(proposal, dict) or not isinstance(projects, dict):
        return {'version': VERSION, 'status': 'unavailable', 'reason': 'Missing proposal or saved projects.'}
    comp = proposal.get('source_comparison')
    groups = comp.get('projects') if isinstance(comp, dict) else None
    if not isinstance(groups, list) or not groups:
        return {'version': VERSION, 'status': 'unavailable', 'reason': 'No exact frozen source pool.'}
    weights, labels, error = _weights(projects, comp)
    if error:
        return {'version': VERSION, 'status': 'unavailable', 'reason': error}
    importance, error = _importance(projects, groups, weights)
    if error:
        return {'version': VERSION, 'status': 'unavailable', 'reason': error}
    rows, paired, final_ids = [], [], set()
    selected_rows = []
    for group in groups:
        name = str(group.get('project') or '')
        candidates = group.get('candidates')
        if not name or not isinstance(candidates, list) or not candidates:
            return {'version': VERSION, 'status': 'unavailable', 'reason': 'Malformed project source pool.'}
        seen = set()
        local = []
        for item in candidates:
            if not isinstance(item, dict) or not isinstance(item.get('text'), str):
                return {'version': VERSION, 'status': 'unavailable', 'reason': 'Malformed source wording.'}
            wording = str(item['text'])
            norm = _norm(wording)
            if not norm or norm in seen:
                return {'version': VERSION, 'status': 'unavailable', 'reason': 'Ambiguous duplicate wording.'}
            seen.add(norm)
            ids = item.get('saved_jd_ids')
            if not isinstance(ids, list) or any(not isinstance(rid, str) for rid in ids):
                return {'version': VERSION, 'status': 'unavailable', 'reason': 'Unverified saved JD links.'}
            own = set(ids)
            if not own <= weights.keys():
                return {'version': VERSION, 'status': 'unavailable', 'reason': 'Unknown saved JD identity.'}
            chosen = item.get('selected_for_proposed_b')
            if type(chosen) is not bool:
                return {'version': VERSION, 'status': 'unavailable', 'reason': 'Proposal membership is unverified.'}
            provenance = item.get('source_labels') or []
            if not isinstance(provenance, list) or any(not isinstance(x, str) for x in provenance):
                return {'version': VERSION, 'status': 'unavailable', 'reason': 'Malformed source provenance.'}
            row = {'project': name, 'wording': wording, 'sources': list(provenance),
                   'saved_jd_ids': sorted(own), 'standalone_weighted_points': _points(own, weights),
                   'required_core_ids': sorted(r for r in own if importance.get(r) in HARD),
                   'selected_for_proposed_b': chosen,
                   'native_per_bullet_score': None,
                   'metric': 'Saved weighted JD-link coverage proxy, not native Job Match.'}
            local.append(row)
            rows.append(row)
            if chosen:
                selected_rows.append(row)
                final_ids.update(own)
        # Only cross-source same-work evidence is eligible as a conflict.
        from tailoring.phase9f_same_work_selection_v37 import _cross_source, _confident_same_work
        for i, first in enumerate(local):
            for second in local[i+1:]:
                if not _cross_source(first['sources'], second['sources']):
                    continue
                if not _confident_same_work(first['wording'], second['wording']):
                    continue
                lhs, rhs = set(first['saved_jd_ids']), set(second['saved_jd_ids'])
                both = first['selected_for_proposed_b'] and second['selected_for_proposed_b']
                unique_lhs = lhs-rhs
                unique_rhs = rhs-lhs
                paired.append({'project': name, 'first_wording': first['wording'],
                               'second_wording': second['wording'],
                               'first_weighted_points': first['standalone_weighted_points'],
                               'second_weighted_points': second['standalone_weighted_points'],
                               'first_unique_vs_other_points': _points(unique_lhs, weights),
                               'second_unique_vs_other_points': _points(unique_rhs, weights),
                               'first_required_core_unique_ids': sorted(r for r in unique_lhs if importance.get(r) in HARD),
                               'second_required_core_unique_ids': sorted(r for r in unique_rhs if importance.get(r) in HARD),
                               'both_in_proposal': both,
                               'status': 'unresolved_duplicate' if both else 'one_or_neither_selected',
                               'ranking_explanation': 'Higher standalone saved coverage is one signal; whole-résumé distinct coverage and native safeguards decide final selection.'})
    # Marginal points reflect coverage lost from the *proposed* whole résumé.
    if selected_rows:
        for row in rows:
            if not row['selected_for_proposed_b']:
                row['marginal_in_proposal_points'] = None
                continue
            other = set().union(*(set(entry['saved_jd_ids']) for entry in selected_rows if entry is not row))
            row['marginal_in_proposal_points'] = _points(set(row['saved_jd_ids']) - other, weights)
    else:
        for row in rows:
            row['marginal_in_proposal_points'] = None
    if any(pair['both_in_proposal'] for pair in paired):
        return {'version': VERSION, 'status': 'unverified_proposal',
                'reason': 'Proposed slate still contains a confirmed same-work conflict; cannot claim deduplication.',
                'bullets': rows, 'same_work_pairs': paired}
    return {'version': VERSION, 'status': 'available', 'bullets': rows,
            'same_work_pairs': paired, 'proposed_distinct_weighted_points': _points(final_ids, weights),
            'units': 'saved JD weighted coverage points',
            'limits': 'Not individual native scores; unsupported JD links do not prove factual claims. Proposed slate is not necessarily the selected final DOCX.'}


def attach_bullet_scores(proposal: dict, projects: dict) -> dict:
    """Add immutable explanatory receipt without changing optimizer membership."""
    if not isinstance(proposal, dict):
        return proposal
    out = dict(proposal)
    out['v38_bullet_score_receipt'] = score_saved_bullets(proposal, projects)
    if isinstance(out.get('candidate_variants'), list):
        out['candidate_variants'] = [
            {**candidate, 'v38_bullet_score_receipt': score_saved_bullets(candidate, projects)}
            if isinstance(candidate, dict) else candidate for candidate in out['candidate_variants']
        ]
    return out


def lookup_scored_wording(result: dict, project: str, text: str) -> dict | None:
    """Exact scoped lookup for UI; never infer scores across project/generation."""
    receipt = ((result or {}).get('proposal') or {}).get('v38_bullet_score_receipt')
    if not isinstance(receipt, dict) or receipt.get('status') not in ('available', 'unverified_proposal'):
        return None
    found = [row for row in receipt.get('bullets') or []
             if _norm(row.get('project')) == _norm(project) and _norm(row.get('wording')) == _norm(text)]
    return found[0] if len(found) == 1 else None
