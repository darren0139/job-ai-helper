"""B2.14b-1: read-only, mode-independent saved-link coverage for frozen wording.

Same saved requirement weights and deterministic link evaluator as V3.8.
No combinatorial search, native scoring, DOCX mutation, database or benchmark.
The caller supplies the generation-bound, verified source/DOCX audit already
constructed by the Best-of display path. Historical rank data is not upgraded.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
import re

from tailoring.phase9f_joint_resume_optimizer_v2_6 import (
    _get_rank, _key, _rank_weights, _source_pool, _support, _points)

VERSION = 'phase9f-v312b214b-independent-bullet-scores-v1'
# Linear inspection, NOT the optimizer's 16-candidate search budget.
MAX_INSPECTION_POOL = 512
MAX_INSPECTION_PROJECTS = 32
HARD = {'required', 'core', 'deal_breaker'}


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def build_independent_bullet_scores(audit, projects, baseline_report, raw_jd_text, *, evaluator=None):
    """Compute V3.8-compatible standalone points without requiring a slate.

    All rank identities, text and importance must match the saved canonical JD.
    A known empty ranking yields a real zero, never a fabricated match. A
    missing/invalid ranking fails closed. The receipt is display-only and is
    rebuilt from this generation's inputs; it has no proposal membership.
    """
    def unavailable(reason):
        return {'version': VERSION, 'status': 'unavailable', 'reason': reason,
                'bullets': [], 'native_score_claim': False}

    if not isinstance(audit, dict) or audit.get('verified') is not True:
        return unavailable('Verified frozen source and fitted-DOCX audit required.')
    generation_id = audit.get('generation_id')
    docx_hash = audit.get('docx_sha256')
    if not isinstance(generation_id, str) or not generation_id or not isinstance(docx_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', docx_hash):
        return unavailable('Generation identity or fitted DOCX digest missing.')
    if (not isinstance(baseline_report, dict) or not isinstance(raw_jd_text, str)
            or not raw_jd_text.strip() or baseline_report.get('raw_jd_text') != raw_jd_text):
        return unavailable('Current JD is missing or differs from the saved exact JD.')
    stable = baseline_report.get('stable_analysis')
    canonical = stable.get('canonical_requirements') if isinstance(stable, dict) else None
    if not isinstance(canonical, list) or not canonical:
        return unavailable('Saved canonical JD requirements unavailable.')
    catalog = {}
    for req in canonical:
        if not isinstance(req, dict):
            return unavailable('Malformed canonical JD requirement.')
        rid = req.get('requirement_id')
        text = req.get('text')
        kind = req.get('importance')
        if (not isinstance(rid, str) or not rid or rid in catalog or not isinstance(text, str)
                or not text.strip() or not isinstance(kind, str) or not kind.strip()):
            return unavailable('Missing or ambiguous canonical JD identity, text or importance.')
        catalog[rid] = req
    sections = audit.get('projects')
    ranks = projects.get('candidate_project_ranking') if isinstance(projects, dict) else None
    if not isinstance(sections, list) or not 1 <= len(sections) <= MAX_INSPECTION_PROJECTS or not isinstance(ranks, list):
        return unavailable('Saved project pool or ranking unavailable.')
    if any(not isinstance(r, dict) for r in ranks):
        return unavailable('Malformed saved project ranking.')
    names, inputs, weights = set(), [], {}
    for section in sections:
        if not isinstance(section, dict):
            return unavailable('Malformed audited project.')
        name = section.get('project')
        if not isinstance(name, str) or not _key(name) or _key(name) in names:
            return unavailable('Missing or ambiguous audited project identity.')
        names.add(_key(name))
        rank = _get_rank(projects, name)
        if rank is None:
            return unavailable(name + ': saved project ranking missing or ambiguous.')
        local, error = _rank_weights(rank)
        if error:
            return unavailable(name + ': ' + error)
        seen = set()
        for match in rank['requirement_matches']:
            rid = match.get('requirement_id')
            req = catalog.get(rid) if isinstance(rid, str) else None
            if (not req or rid in seen or req.get('score_eligible') is False
                    or _key(match.get('requirement_text') or match.get('text')) != _key(req['text'])
                    or _key(match.get('importance')) != _key(req['importance'])):
                return unavailable(name + ': saved ranking does not match canonical JD identity/text/importance.')
            seen.add(rid)
        for rid, value in local.items():
            # V3.8 uses the maximum saved weight for the same identity across
            # the audited project set, not the pre-fit evidence_value metric.
            weights[rid] = max(weights.get(rid, 0.0), value)
        pool, error = _source_pool(section, max_pool=MAX_INSPECTION_POOL)
        if error or not pool or not section.get('final'):
            return unavailable(name + ': ' + (error or 'Missing audited source/final wording.'))
        final_keys = [_key(x['text']) for x in section['final']]
        if len(final_keys) != len(set(final_keys)):
            return unavailable(name + ': ambiguous final bullet wording.')
        inputs.append((name, rank, local, pool))
    try:
        scope = {'generation_id': generation_id, 'a_docx_sha256': docx_hash,
                 'raw_jd_sha256': sha256(raw_jd_text.encode('utf-8')).hexdigest(),
                 'canonical_requirements_sha256': _digest(canonical),
                 'source_and_ranking_sha256': _digest([(name, rank, pool) for name, rank, _, pool in inputs])}
    except (TypeError, ValueError, OverflowError):
        return unavailable('Saved score inputs are not serializable.')
    rows = []
    for name, rank, local, pool in inputs:
        if not local:
            # A complete, validated ranking has no positively matched IDs.
            # No evaluator can give a positive weighted link in that scope.
            support = [set() for _ in pool]
        else:
            if evaluator is None:
                try:
                    from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
                    evaluator = build_bullet_evidence_priorities
                except ImportError as exc:
                    return unavailable('Saved-link evaluator unavailable: ' + type(exc).__name__)
            support, error = _support(pool, deepcopy(rank), evaluator)
            if support is None:
                return unavailable(name + ': ' + error)
        for candidate, ids in zip(pool, support):
            linked = set(ids) & local.keys()
            rows.append({'project': name, 'wording': candidate['text'],
                         'sources': list(candidate['sources']), 'saved_jd_ids': sorted(linked),
                         'standalone_weighted_points': _points(linked, weights),
                         'required_core_ids': sorted(r for r in linked if _key(catalog[r]['importance']) in HARD),
                         'native_per_bullet_score': None, 'marginal_in_proposal_points': None,
                         'metric': 'Saved weighted JD-link coverage proxy, not native Job Match.'})
    return {'version': VERSION, 'status': 'available', 'scope': scope, 'bullets': rows,
            'project_count': len(inputs), 'bullet_count': len(rows),
            'optimizer_search_performed': False, 'native_score_claim': False,
            'units': 'saved JD weighted coverage points',
            'limits': 'Independent standalone saved-link points; not pre-fit evidence priorities, native score, or optimizer membership.'}
