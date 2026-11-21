"""Read-only, fail-closed Phase 8 improvement verdict.

This module consumes *saved* Phase 8 authoritative results. It never scores,
reruns document analysis, alters generation output, or promotes a blueprint.
"""
from __future__ import annotations

import math
import re
from typing import Any

VERSION = 'phase8-final-initial-and-selected-base-verdict-v1'
MATCH_RANK = {'none': 0, 'weak': 1, 'transferable': 2, 'direct': 3}
HARD = {'required', 'core', 'deal_breaker'}


def _str(value: Any) -> str:
    return str(value or '').strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    return v if math.isfinite(v) and 0 <= v <= 100 else None


def _rows(analysis: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
    rows = analysis.get('canonical_requirements')
    if not isinstance(rows, list) or not rows:
        return {}, 'Canonical requirement rows are unavailable.'
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            return {}, 'Malformed canonical requirement row.'
        rid = _str(row.get('requirement_id'))
        label = _str(row.get('match_label')).lower()
        importance = _str(row.get('importance')).lower()
        if not rid or rid in found or label not in MATCH_RANK or not importance:
            return {}, 'Missing/duplicate requirement ID, unknown label, or importance.'
        found[rid] = row
    return found, ''


def _compare(name: str, before: Any, after: Any, ab: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        'name': name, 'verified': False, 'before_score': None,
        'after_score': None, 'delta': None, 'hard_regressions': [],
        'reason': '', 'assessment': 'unavailable',
    }
    if not isinstance(before, dict) or not isinstance(after, dict):
        result['reason'] = 'Saved baseline or final stable analysis missing.'
        return result
    if not isinstance(ab, dict) or ab.get('comparable') is not True:
        result['reason'] = 'Saved Job Match A/B identity is not comparable.'
        return result
    bver = _str(before.get('scoring_version'))
    aver = _str(after.get('scoring_version'))
    if not bver or bver != aver:
        result['reason'] = 'Scoring versions differ or are absent.'
        return result
    bscore, ascore = _number(before.get('deterministic_alignment_score')), _number(after.get('deterministic_alignment_score'))
    if bscore is None or ascore is None:
        result['reason'] = 'A verified numeric score is missing or invalid.'
        return result
    left, e1 = _rows(before)
    right, e2 = _rows(after)
    if e1 or e2:
        result['reason'] = e1 or e2
        return result
    if left.keys() != right.keys():
        result['reason'] = 'Canonical requirement IDs differ.'
        return result
    if any(_str(left[r].get('importance')).lower() != _str(right[r].get('importance')).lower() for r in left):
        result['reason'] = 'Requirement classifications changed between comparisons.'
        return result
    summary = ab.get('summary') or {}
    if not isinstance(summary, dict):
        result['reason'] = 'Malformed A/B summary.'
        return result
    # AB comparability is the authoritative JD/registry/scorer identity check.
    # Verify the published numbers agree with the native analysis rows.
    for key, score in [('initial_score', bscore), ('tailored_score', ascore)]:
        v = summary.get(key)
        if v is not None and (_number(v) is None or abs(float(v) - score) > 0.00001):
            result['reason'] = f'A/B {key} disagrees with the native analysis.'
            return result
    if 'score_delta' in summary:
        v = summary['score_delta']
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or abs(float(v) - (ascore - bscore)) > .00001:
            result['reason'] = 'A/B score delta disagrees with native analyses.'
            return result
    lost = [
        {'requirement_id': rid,
         'requirement': _str(right[rid].get('text')) or _str(left[rid].get('text')),
         'importance': _str(right[rid].get('importance')),
         'before_match': _str(left[rid].get('match_label')),
         'final_match': _str(right[rid].get('match_label'))}
        for rid in sorted(left)
        if _str(left[rid].get('importance')).lower() in HARD
        and MATCH_RANK[_str(right[rid].get('match_label')).lower()] < MATCH_RANK[_str(left[rid].get('match_label')).lower()]
    ]
    delta = ascore - bscore
    result.update(verified=True, before_score=bscore, after_score=ascore,
                  delta=round(delta, 6), hard_regressions=lost,
                  assessment=('hard_regression' if lost else 'increased' if delta > 0
                              else 'decreased' if delta < 0 else 'unchanged'),
                  scoring_version=bver)
    return result


def build_final_improvement_verdict(result: dict[str, Any], *, baseline_mode: str = 'initial') -> dict[str, Any]:
    """Grade a fitted result vs both saved baselines; never infer a missing baseline."""
    out: dict[str, Any] = {
        'version': VERSION, 'status': 'not_verifiable', 'certified_improved': False,
        'actual_document': False, 'comparisons': {}, 'reasons': [],
    }
    if not isinstance(result, dict):
        out['reasons'].append('Phase 8 result is missing.')
        return out
    doc = result.get('document_analysis')
    authority = (isinstance(doc, dict) and isinstance(doc.get('initial'), dict)
                 and isinstance(doc.get('final'), dict)
                 and bool(re.fullmatch(r'[a-fA-F0-9]{64}', _str(doc.get('final_document_sha256')))))
    out['actual_document'] = authority
    if result.get('comparison_valid') is not True:
        out['reasons'].append('Phase 8 canonical/identity comparison is not verified.')
        return out
    if result.get('fit_one_page') is not True:
        out['reasons'].append('The exact final fitted résumé is not verified to fit one page.')
        return out
    final = result.get('after_stable_analysis')
    before = result.get('before_stable_analysis')
    main_ab = result.get('job_match_ab')
    selected = result.get('selected_base_analysis')
    if authority:
        out['comparisons']['Initial'] = _compare('Initial', before, final, main_ab)
        if isinstance(selected, dict) and selected.get('same_as_initial') is True:
            out['comparisons']['Selected Base'] = dict(out['comparisons']['Initial'], name='Selected Base', alias_of='Initial')
        elif isinstance(selected, dict):
            out['comparisons']['Selected Base'] = _compare(
                'Selected Base', selected.get('stable_analysis'), final,
                result.get('selected_base_job_match_ab'))
        else:
            out['comparisons']['Selected Base'] = _compare('Selected Base', None, final, None)
    else:
        # Legacy Phase 8 constructs a profile. It has not proved it read the actual
        # final DOCX and therefore cannot certify an actual-document improvement.
        out['reasons'].append('Actual final-DOCX document identity is unavailable: this is a reconstructed-profile comparison only.')
        mode = _str(baseline_mode).lower()
        named = 'Selected Base' if mode == 'selected_base' else 'Initial'
        out['comparisons'][named] = _compare(named, before, final, main_ab)
        other = 'Initial' if named == 'Selected Base' else 'Selected Base'
        out['comparisons'][other] = _compare(other, None, final, None)
    comparable = [c for c in out['comparisons'].values() if c['verified']]
    missing = [c for c in out['comparisons'].values() if not c['verified']]
    for c in missing:
        out['reasons'].append(f"{c['name']}: {c['reason']}")
    if not comparable:
        return out
    if any(c['hard_regressions'] for c in comparable):
        out['status'] = 'required_core_regression'
        out['reasons'].append('At least one Required/Core requirement lost verified evidence strength.')
        return out
    lineage = result.get('claim_lineage')
    risks = lineage.get('claim_review_required_count') if isinstance(lineage, dict) else None
    if risks is None or isinstance(risks, bool) or not isinstance(risks, int) or risks < 0:
        out['status'] = 'review_required'
        out['reasons'].append('A valid claim-lineage review count is missing.')
        return out
    if risks:
        out['status'] = 'review_required'
        out['reasons'].append(f'{risks} claim-lineage issue(s) require review.')
        return out
    if any(c['delta'] < 0 for c in comparable):
        out['status'] = 'worse_against_a_baseline'
        return out
    if not authority or missing:
        out['status'] = 'partial_comparison_only'
        return out
    if all(c['delta'] > 0 for c in comparable):
        out['status'] = 'improved_vs_both'
        out['certified_improved'] = True
    elif all(c['delta'] == 0 for c in comparable):
        out['status'] = 'unchanged_vs_both'
    else:
        out['status'] = 'not_improved_vs_both'
    return out
