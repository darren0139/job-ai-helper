"""V3.12-B1.4.1: fast, quality-gated source-grounded Portfolio reallocation.

This is deliberately a *conservative* companion to B1.4. It considers only
cross-project swaps that introduce a canonical JD requirement not supported by
any incumbent project bullet. Project-depth gains alone never justify swapping
away a different accomplishment on an equal native score.

Only one challenger may render, and the incumbent never changes when validation
fails. The budget is cooperative (checked before starting expensive work), not
a kill switch for a running LibreOffice subprocess. Normal one-page fitting is
unchanged. Native scoring, Required/Core floors, claims and DOCX readback remain
owned by the original engines.
"""
from __future__ import annotations

import math
import re
from copy import deepcopy
from time import perf_counter
from typing import Any, Callable

from tailoring.portfolio_quality_v312b14 import (
    B1_TAG, _count_one, _docx_authority, _identity, _metadata,
    _remap_metadata, _score_receipt, _source_rows, _title, native_floors,
)

VERSION = 'portfolio-quality-v312b141-fast-quality-native-gated-v1'
MAX_RENDER_PROBES = 1
SOFT_COMPARISON_BUDGET_SECONDS = 45.0
_STOPWORDS = frozenset(('a an and as at be been but by can for from had has have in into is its it of on or '
                        'the their them there these this those to was were which while with within via '
                        'built created configured developed designed implemented integrated managed using used '
                        'application applications system systems project projects work working support supported '
                        'including across through allows allowed allowing enabling enable enabled').split())


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r'[a-z0-9]+', str(text).casefold())
            if len(t) > 2 and t not in _STOPWORDS}


def _redundancy(left: str, right: str) -> float:
    """Cheap conservative lexical flag; never a substitute for native verification."""
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 1.0
    return len(a & b) / min(len(a), len(b))


def _metadata_ids(meta: dict[str, Any]) -> set[str] | None:
    raw = meta.get('supported_requirement_ids')
    if not isinstance(raw, list) or any(not isinstance(x, str) or not x.strip() for x in raw):
        return None
    return set(raw)


def plan_quality_swaps(*, source_projects: dict[str, Any], incumbent_fit: dict[str, Any]):
    """Find all cheap eligible swaps, returning at most one without render calls.

    All candidate IDs must be verified from aligned source metadata. Novelty is
    measured against ALL incumbent projects, not just the recipient project.
    """
    counts = {'donor_bullet_candidates': 0, 'recipient_bullet_candidates': 0,
              'rejected_no_global_jd_novelty': 0, 'rejected_bullet_overlap': 0,
              'rejected_removed_unique_jd_evidence': 0,
              'rejected_missing_or_invalid_metadata': 0,
              'source_grounded_novel_candidates': 0}
    fit_projects = incumbent_fit.get('tailored_projects_used') if isinstance(incumbent_fit, dict) else None
    resolved = _source_rows(source_projects, fit_projects)
    if resolved is None:
        return [], counts, 'SOURCE_METADATA_UNVERIFIED'
    originals, rows = resolved
    all_current_ids: set[str] = set()
    for project in rows:
        for meta in project['bullet_evidence_priorities']:
            ids = _metadata_ids(meta)
            if ids is None:
                return [], counts, 'SOURCE_METADATA_UNVERIFIED'
            all_current_ids.update(ids)
    candidates = []
    for donor_i, donor in enumerate(rows):
        bullets = donor['draft_bullets']
        if len(bullets) < 4:
            continue
        metas = _metadata(donor)
        if metas is None:
            return [], counts, 'SOURCE_METADATA_UNVERIFIED'
        for remove_i, removed_text in enumerate(bullets):
            rm = metas[removed_text]
            if (rm.get('protect_during_fitting') or rm.get('protected_requirement_ids')
                or int(rm.get('unique_required_core_count', 0) or 0) > 0):
                continue
            counts['donor_bullet_candidates'] += 1
            removed_ids = _metadata_ids(rm)
            if removed_ids is None:
                counts['rejected_missing_or_invalid_metadata'] += 1
                continue
            preserved_ids = set()
            for p_i, project in enumerate(rows):
                for b_i, meta in enumerate(project['bullet_evidence_priorities']):
                    if p_i == donor_i and b_i == remove_i:
                        continue
                    ids = _metadata_ids(meta)
                    if ids is None:
                        return [], counts, 'SOURCE_METADATA_UNVERIFIED'
                    preserved_ids.update(ids)
            if not removed_ids.issubset(preserved_ids):
                counts['rejected_removed_unique_jd_evidence'] += 1
                continue
            for recipient_i, recipient in enumerate(rows):
                if recipient_i == donor_i or len(recipient.get('draft_bullets') or []) != 1:
                    continue
                source_recipient = originals[_identity(recipient)]
                rec_meta = _metadata(source_recipient)
                if rec_meta is None:
                    return [], counts, 'SOURCE_METADATA_UNVERIFIED'
                for added_text in source_recipient['draft_bullets']:
                    if added_text in recipient['draft_bullets']:
                        continue
                    counts['recipient_bullet_candidates'] += 1
                    meta = rec_meta[added_text]
                    if meta.get('fusion_source_count', 1) not in (None, 1):
                        counts['rejected_missing_or_invalid_metadata'] += 1
                        continue
                    new_ids = _metadata_ids(meta)
                    if new_ids is None:
                        counts['rejected_missing_or_invalid_metadata'] += 1
                        continue
                    # IMPORTANT: recipient-local JD ID novelty is NOT sufficient.
                    globally_new_ids = new_ids - all_current_ids
                    if not globally_new_ids:
                        counts['rejected_no_global_jd_novelty'] += 1
                        continue
                    overlap = max(_redundancy(added_text, current)
                                  for current in recipient['draft_bullets'])
                    if overlap >= 0.55:
                        counts['rejected_bullet_overlap'] += 1
                        continue
                    try:
                        value = float(meta.get('evidence_value', 0) or 0)
                        if not math.isfinite(value) or value < 0:
                            raise ValueError('invalid evidence value')
                    except (TypeError, ValueError):
                        counts['rejected_missing_or_invalid_metadata'] += 1
                        continue
                    # Construct only passing candidates, not hundreds of full deep copies.
                    dnew = _remap_metadata(donor, originals[_identity(donor)],
                        [b for i, b in enumerate(bullets) if i != remove_i])
                    rnew = _remap_metadata(recipient, source_recipient,
                        [*recipient['draft_bullets'], added_text])
                    if dnew is None or rnew is None:
                        counts['rejected_missing_or_invalid_metadata'] += 1
                        continue
                    alternative = deepcopy(fit_projects)
                    alternative['recommended_projects'][donor_i] = dnew
                    alternative['recommended_projects'][recipient_i] = rnew
                    candidates.append({
                        'projects': alternative,
                        'donor': _title(donor), 'recipient': _title(recipient),
                        'removed_bullet': removed_text, 'added_bullet': added_text,
                        'added_global_requirement_ids': sorted(globally_new_ids),
                        'removed_requirement_ids': sorted(removed_ids),
                        'addition_overlap_fraction': round(overlap, 4),
                        'added_evidence_value': value,
                    })
    counts['source_grounded_novel_candidates'] = len(candidates)
    candidates.sort(key=lambda c:(-len(c['added_global_requirement_ids']),
                                  c['addition_overlap_fraction'],
                                  -c['added_evidence_value'], c['donor'],
                                  c['recipient'], c['removed_bullet'], c['added_bullet']))
    if not candidates:
        return [], counts, 'NO_GLOBALLY_NOVEL_NONREDUNDANT_SOURCE_BULLET'
    return candidates[:MAX_RENDER_PROBES], counts, 'PASS'


def compare_and_select(*, source_projects: dict[str, Any], incumbent_fit: dict[str, Any],
                       render: Callable[[dict[str, Any]], dict[str, Any]],
                       verify: Callable[[dict[str, Any]], dict[str, Any]],
                       limit: int = MAX_RENDER_PROBES):
    """Quality-first native-gated selection with true wall-time receipts.

    A probe is never started when the soft time budget has already elapsed;
    an in-progress fit is not force-killed. The caller persists only the winner.
    """
    t0 = perf_counter()
    receipt = {'version':VERSION, 'status':'HOLD_INCUMBENT', 'probes':[],
               'native_score_checked':False,'required_core_checked':False,
               'no_approval_or_scorer_changes':True,
               'render_probe_limit':MAX_RENDER_PROBES,
               'soft_comparison_budget_seconds':SOFT_COMPARISON_BUDGET_SECONDS}
    def finish(selected):
        receipt['comparison_elapsed_seconds'] = round(perf_counter()-t0, 3)
        receipt['render_probes_attempted'] = len(receipt['probes'])
        return selected, receipt
    if not _docx_authority(incumbent_fit):
        receipt['reason'] = 'INCUMBENT_DOCX_NOT_AUTHENTICATED'
        return finish(incumbent_fit)
    # Early cheap screen BEFORE invoking native baseline verification.
    try:
        proposals, counts, reason = plan_quality_swaps(
            source_projects=source_projects, incumbent_fit=incumbent_fit)
    except Exception as exc:
        receipt['reason'] = 'QUALITY_PREFLIGHT_EXCEPTION_' + type(exc).__name__
        return finish(incumbent_fit)
    receipt['prefilter'] = counts
    receipt['proposal_elapsed_seconds'] = round(perf_counter()-t0,3)
    if not proposals:
        receipt['status'] = 'NO_ELIGIBLE_SOURCE_GROUNDED_SWAP'
        receipt['reason'] = reason
        return finish(incumbent_fit)
    if limit <= 0:
        receipt['reason'] = 'PROBES_DISABLED_BY_LIMIT'
        return finish(incumbent_fit)
    if perf_counter()-t0 >= SOFT_COMPARISON_BUDGET_SECONDS:
        receipt['reason'] = 'COMPARISON_BUDGET_EXHAUSTED_PRE_VERIFY'
        return finish(incumbent_fit)
    vt = perf_counter()
    try:
        baseline_verification = verify(incumbent_fit)
        baseline = _score_receipt(baseline_verification)
    except Exception as exc:
        receipt['reason'] = 'INCUMBENT_NATIVE_VERIFICATION_FAILED_' + type(exc).__name__
        receipt['incumbent_verify_elapsed_seconds'] = round(perf_counter()-vt,3)
        return finish(incumbent_fit)
    receipt['incumbent_verify_elapsed_seconds'] = round(perf_counter()-vt,3)
    if baseline is None:
        receipt['reason'] = 'INCUMBENT_NATIVE_VERIFICATION_UNAVAILABLE'
        return finish(incumbent_fit)
    receipt['native_score_checked'] = True
    receipt['required_core_checked'] = True
    receipt['incumbent_native_score'] = baseline['score']
    for n, candidate in enumerate(proposals[:min(MAX_RENDER_PROBES, int(limit))],1):
        if perf_counter()-t0 >= SOFT_COMPARISON_BUDGET_SECONDS:
            receipt['reason'] = 'COMPARISON_BUDGET_EXHAUSTED_PRE_RENDER'
            return finish(incumbent_fit)
        row = {'number':n,'donor':candidate['donor'],
               'recipient':candidate['recipient'],
               'global_new_requirement_ids':candidate['added_global_requirement_ids'],
               'addition_overlap_fraction':candidate['addition_overlap_fraction'],
               'status':'HOLD'}
        receipt['probes'].append(row)
        t_render = perf_counter()
        try:
            alternative_fit = render(candidate['projects'])
            row['render_elapsed_seconds'] = round(perf_counter()-t_render,3)
            if not _docx_authority(alternative_fit):
                row['reason'] = 'ONE_PAGE_OR_DOCX_READBACK_FAILED'
                continue
            alternative_projects = alternative_fit.get('tailored_projects_used') or {}
            if _count_one(alternative_projects) >= _count_one(incumbent_fit.get('tailored_projects_used')):
                row['reason'] = 'NO_ACTUAL_PROJECT_DEPTH_GAIN'
                continue
            fitted_rows = {_identity(p):p for p in alternative_projects.get('recommended_projects') or []
                           if isinstance(p,dict)}
            recipients=[p for p in fitted_rows.values() if _title(p)==candidate['recipient']]
            if len(recipients)!=1 or candidate['added_bullet'] not in recipients[0].get('draft_bullets',[]):
                row['reason'] = 'SOURCE_GROUNDED_ADDITION_NOT_IN_FINAL_DOCX'
                continue
            v_start = perf_counter()
            verification=verify(alternative_fit)
            row['native_verify_elapsed_seconds'] = round(perf_counter()-v_start,3)
            okay, reason, details = native_floors(baseline_verification,verification)
            row['native'] = details
            row['reason'] = reason
            if not okay:
                continue
            row['status'] = 'VERIFIED_FEASIBLE'
            row['one_bullet_projects'] = _count_one(alternative_projects)
            # Even a passing native score is NOT a license for depth-only promotion.
            # Global canonical novelty was verified *before* this expensive render.
            receipt.update({'status':'SELECTED_NATIVE_SAFE_DEPTH_IMPROVEMENT',
                            'winner_probe':n,'selected_native_score':details['challenger'],
                            'selected_one_bullet_projects':row['one_bullet_projects'],
                            'reason':'GLOBALLY_NOVEL_JD_EVIDENCE_AND_NATIVE_FLOORS_PASS'})
            return finish(alternative_fit)
        except Exception as exc:
            row.setdefault('render_elapsed_seconds',round(perf_counter()-t_render,3))
            row['reason'] = 'CANDIDATE_EXCEPTION_' + type(exc).__name__
            continue
    receipt['reason'] = 'NO_QUALITY_ELIGIBLE_NATIVE_SAFE_CHALLENGER'
    return finish(incumbent_fit)
