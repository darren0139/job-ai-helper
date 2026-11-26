"""V3.12 B1.4: bounded, source-grounded cross-project one-page comparisons.

An alternative is never promoted from a depth heuristic. The caller must
render its own DOCX, check exact final-DOCX readback, and recompute the native
Phase 8 verification for incumbent and each surviving alternative. A single
uncertainty holds the incumbent; no approvals, scorer weights or DB writes.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

VERSION = 'portfolio-quality-v312b14-guarded-native-cross-project-swap-v1'
B1_TAG = 'portfolio-quality-v312b1-fit-input-marginal-v1'
MAX_PROBES = 3
RANK = {'none': 0, 'weak': 1, 'transferable': 2, 'direct': 3, 'full': 3}
IMPORTANT = {'required', 'core', 'deal_breaker'}


def _title(row: dict[str, Any]) -> str:
    return str(row.get('display_title') or row.get('title') or '').strip()


def _identity(row: dict[str, Any]) -> str:
    return str(row.get('project_id') or _title(row)).strip()


def _metadata(row: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    bullets = row.get('draft_bullets')
    rows = row.get('bullet_evidence_priorities')
    if not isinstance(bullets, list) or not isinstance(rows, list) or len(rows) != len(bullets):
        return None
    output = {}
    for index, (text, meta) in enumerate(zip(bullets, rows)):
        if not isinstance(text, str) or not text.strip() or not isinstance(meta, dict):
            return None
        if text in output or meta.get('bullet_index') != index or str(meta.get('bullet_text') or '') != text:
            return None
        output[text] = deepcopy(meta)
    return output


def _source_rows(projects: dict[str, Any] | None, fitted: dict[str, Any] | None):
    if not isinstance(projects, dict) or projects.get('portfolio_quality_b1_active') != B1_TAG:
        return None
    if not isinstance(fitted, dict):
        return None
    original = projects.get('recommended_projects')
    current = fitted.get('recommended_projects')
    if not isinstance(original, list) or not isinstance(current, list) or not current:
        return None
    original_map = {_identity(x): x for x in original if isinstance(x, dict)}
    if len(original_map) != len(original) or not all(_metadata(x) is not None for x in original):
        return None
    seen = set()
    for row in current:
        if not isinstance(row, dict) or _identity(row) not in original_map or _identity(row) in seen:
            return None
        seen.add(_identity(row))
        if _metadata(row) is None:
            return None
        if not set(row['draft_bullets']).issubset(set(original_map[_identity(row)]['draft_bullets'])):
            return None
    return original_map, current


def _remap_metadata(row: dict[str, Any], source: dict[str, Any], bullets: list[str]):
    source_meta = _metadata(source)
    if not source_meta or not bullets or len(bullets) != len(set(bullets)):
        return None
    if any(x not in source_meta for x in bullets):
        return None
    out = deepcopy(row)
    out['draft_bullets'] = list(bullets)
    out['bullet_evidence_priorities'] = []
    for i, text in enumerate(bullets):
        meta = deepcopy(source_meta[text])
        meta['bullet_index'] = i
        meta['bullet_text'] = text
        out['bullet_evidence_priorities'].append(meta)
    out['protected_bullet_indexes'] = [
        i for i, meta in enumerate(out['bullet_evidence_priorities'])
        if meta.get('protect_during_fitting') or meta.get('protected_requirement_ids')
        or int(meta.get('unique_required_core_count', 0) or 0) > 0
    ]
    # A partial compact-bullet array must not be treated as an aligned rewrite.
    compact = source.get('compact_bullets')
    if isinstance(compact, list) and len(compact) == len(source['draft_bullets']):
        indices = [source['draft_bullets'].index(t) for t in bullets]
        out['compact_bullets'] = [compact[i] for i in indices]
    else:
        out['compact_bullets'] = []
    out['allocated_bullet_count'] = len(bullets)
    return out


def propose_swaps(source_projects: dict[str, Any] | None,
                  incumbent_fit: dict[str, Any] | None, *, limit: int = MAX_PROBES) -> list[dict[str, Any]]:
    """Suggest one-for-one swaps, never invent text or project membership.

    The donor must retain >=3 bullets, and its removed bullet's JD evidence
    must still appear elsewhere in the retained document. Each recipient
    gains one *previously existing* source bullet with intact evidence metadata.
    Actual fit and native-scorer checks happen later, never here.
    """
    if not isinstance(incumbent_fit, dict):
        return []
    current_payload = incumbent_fit.get('tailored_projects_used')
    resolved = _source_rows(source_projects, current_payload)
    if resolved is None:
        return []
    originals, rows = resolved
    candidates = []
    for donor_idx, donor in enumerate(rows):
        donor_bullets = donor['draft_bullets']
        if len(donor_bullets) < 4:
            continue
        donor_meta = _metadata(donor)
        if donor_meta is None:
            continue
        for remove_idx in range(len(donor_bullets)-1, -1, -1):
            removed = donor_bullets[remove_idx]
            rm = donor_meta[removed]
            if (rm.get('protect_during_fitting') or rm.get('protected_requirement_ids')
                or int(rm.get('unique_required_core_count', 0) or 0) > 0):
                continue
            preserved_ids = set()
            for j, row in enumerate(rows):
                for n, meta in enumerate(row['bullet_evidence_priorities']):
                    if j != donor_idx or n != remove_idx:
                        preserved_ids.update(meta.get('supported_requirement_ids') or [])
            removed_ids = set(rm.get('supported_requirement_ids') or [])
            if not removed_ids.issubset(preserved_ids):
                continue
            for recipient_idx, recipient in enumerate(rows):
                if recipient_idx == donor_idx or len(recipient['draft_bullets']) != 1:
                    continue
                original_recipient = originals[_identity(recipient)]
                original_meta = _metadata(original_recipient)
                if original_meta is None:
                    continue
                existing = set(recipient['draft_bullets'])
                existing_ids = set()
                for meta in recipient['bullet_evidence_priorities']:
                    existing_ids.update(meta.get('supported_requirement_ids') or [])
                for addition in original_recipient['draft_bullets']:
                    if addition in existing:
                        continue
                    m = original_meta[addition]
                    # Documented bullet with attributable metadata is necessary.
                    # A no-JD-ID bullet can still help depth, but receives no JD credit.
                    if m.get('fusion_source_count', 1) not in (None, 1):
                        continue
                    new_ids = set(m.get('supported_requirement_ids') or []) - existing_ids
                    try:
                        ev = float(m.get('evidence_value', 0) or 0)
                    except (TypeError, ValueError):
                        continue
                    alternative = deepcopy(current_payload)
                    alternative_rows = alternative['recommended_projects']
                    dnew = _remap_metadata(donor, originals[_identity(donor)],
                                            [t for i,t in enumerate(donor_bullets) if i != remove_idx])
                    rnew = _remap_metadata(recipient, original_recipient,
                                            [*recipient['draft_bullets'], addition])
                    if dnew is None or rnew is None:
                        continue
                    alternative_rows[donor_idx] = dnew
                    alternative_rows[recipient_idx] = rnew
                    candidates.append({
                        'projects': alternative,
                        'donor': _title(donor), 'recipient': _title(recipient),
                        'removed_bullet': removed, 'added_bullet': addition,
                        'removed_requirement_ids': sorted(removed_ids),
                        'added_distinct_requirement_ids': sorted(new_ids),
                        'added_evidence_value': ev,
                        'source_grounded': True,
                    })
    candidates.sort(key=lambda c: (-len(c['added_distinct_requirement_ids']),
                                   -c['added_evidence_value'], c['recipient'],
                                   c['removed_bullet'],c['added_bullet']))
    if int(limit) <= 0:
        return []
    distinct = set()
    output = []
    for candidate in candidates:
        identity = (candidate['donor'],candidate['recipient'],candidate['removed_bullet'],candidate['added_bullet'])
        if identity in distinct:continue
        distinct.add(identity)
        output.append(candidate)
        if len(output) == max(0,min(int(limit),MAX_PROBES)):
            break
    return output


def _score_receipt(verification: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(verification, dict) or verification.get('comparison_valid') is not True:
        return None
    if (verification.get('job_match_ab') or {}).get('comparable') is not True:
        return None
    analysis = verification.get('after_stable_analysis')
    if not isinstance(analysis,dict):return None
    version = str(analysis.get('scoring_version') or '')
    score = analysis.get('deterministic_alignment_score')
    if not version or not isinstance(score,int) or isinstance(score,bool):return None
    rows = analysis.get('canonical_requirements')
    if not isinstance(rows,list) or not rows:return None
    requirements = {}
    for r in rows:
        if not isinstance(r,dict):return None
        key = str(r.get('requirement_id') or '')
        if not key or key in requirements:return None
        strength = r.get('evidence_strength')
        if not isinstance(strength,int):return None
        requirements[key] = {'importance':str(r.get('importance') or '').lower(),
                             'strength':strength,'label':str(r.get('match_label') or 'none').lower()}
    lineage=verification.get('claim_lineage') or {}
    claim_risks=lineage.get('claim_review_required_count')
    if not isinstance(claim_risks,int) or claim_risks<0:return None
    return {'score':score,'scoring_version':version,'requirements':requirements,
            'claim_review_required_count':claim_risks}


def native_floors(incumbent: dict[str, Any], challenger: dict[str, Any]) -> tuple[bool,str,dict[str, Any]]:
    left,right = _score_receipt(incumbent),_score_receipt(challenger)
    if left is None or right is None:
        return False,'NATIVE_VERIFICATION_INCOMPLETE',{}
    if left['scoring_version']!=right['scoring_version'] or set(left['requirements'])!=set(right['requirements']):
        return False,'NATIVE_IDENTITIES_CHANGED',{}
    if right['score']<left['score']:
        return False,'NATIVE_SCORE_REGRESSION',{'incumbent':left['score'],'challenger':right['score']}
    if right['claim_review_required_count']>left['claim_review_required_count']:
        return False,'CLAIM_REVIEW_RISK_INCREASED',{}
    for key,base in left['requirements'].items():
        target=right['requirements'][key]
        if base['importance']!=target['importance']:
            return False,'REQUIREMENT_IMPORTANCE_CHANGED',{'requirement_id':key}
        if base['importance'] in IMPORTANT:
            if base['label'] not in RANK or target['label'] not in RANK:
                return False,'UNRECOGNISED_REQUIREMENT_LABEL',{'requirement_id':key}
            if (target['strength']<base['strength'] or
                    RANK.get(target['label'],-1)<RANK.get(base['label'],-1)):
                return False,'REQUIRED_CORE_REGRESSION',{'requirement_id':key}
    return True,'PASS',{'incumbent':left['score'],'challenger':right['score'],
                        'score_delta':right['score']-left['score'],
                        'claim_reviews':right['claim_review_required_count']}


def _docx_authority(fit: dict[str, Any]) -> bool:
    if not isinstance(fit,dict) or fit.get('fit_one_page') is not True or fit.get('page_count')!=1:
        return False
    audit=fit.get('portfolio_quality_b1_final_audit')
    if not isinstance(audit,dict):return False
    if audit.get('is_actual_docx_readback') is not True or audit.get('exact_saved_fitted_bullets_match_docx') is not True:
        return False
    h=audit.get('docx_sha256')
    if not isinstance(h,str) or len(h)!=64:return False
    from pathlib import Path
    from hashlib import sha256
    docx=Path(str(fit.get('docx_path') or ''))
    return docx.is_file() and sha256(docx.read_bytes()).hexdigest()==h


def _count_one(projects: dict[str, Any] | None)->int:
    if not isinstance(projects,dict):return 999
    return sum(len(p.get('draft_bullets') or [])==1
               for p in projects.get('recommended_projects') or [] if isinstance(p,dict))


def compare_and_select(*, source_projects: dict[str, Any], incumbent_fit: dict[str, Any],
                       render: Callable[[dict[str, Any]], dict[str, Any]],
                       verify: Callable[[dict[str, Any]], dict[str, Any]],
                       limit: int=MAX_PROBES):
    """Bounded ACTIVE selector: only adopts an independently native-verified fit.

    Returns (selected_fit, full_receipt), never mutates incumbent or source.
    Errors hold the incumbent. Caller alone owns DB persistence.
    """
    receipt={'version':VERSION,'status':'HOLD_INCUMBENT','probes':[],
             'native_score_checked':False,'required_core_checked':False,
             'no_approval_or_scorer_changes':True}
    if not _docx_authority(incumbent_fit):
        receipt['reason']='INCUMBENT_DOCX_NOT_AUTHENTICATED';return incumbent_fit,receipt
    try:
        initial_verification=verify(incumbent_fit)
        initial=_score_receipt(initial_verification)
    except Exception as exc:
        receipt['reason']='INCUMBENT_NATIVE_VERIFICATION_FAILED_'+type(exc).__name__
        return incumbent_fit,receipt
    if initial is None:
        receipt['reason']='INCUMBENT_NATIVE_VERIFICATION_UNAVAILABLE';return incumbent_fit,receipt
    receipt['native_score_checked']=True
    receipt['required_core_checked']=True
    receipt['incumbent_native_score']=initial['score']
    source=propose_swaps(source_projects, incumbent_fit,limit=limit)
    if not source:
        receipt['status']='NO_ELIGIBLE_SOURCE_GROUNDED_SWAP'
        return incumbent_fit,receipt
    best_fit=incumbent_fit
    best_rank=(initial['score'],-_count_one(incumbent_fit.get('tailored_projects_used')))
    winner=None
    for i,candidate in enumerate(source,1):
        row={'number':i,'donor':candidate['donor'],'recipient':candidate['recipient'],
             'added_distinct_requirement_ids':candidate['added_distinct_requirement_ids'],
             'status':'HOLD'}
        receipt['probes'].append(row)
        try:
            alt=render(candidate['projects'])
            if not _docx_authority(alt):
                row['reason']='ONE_PAGE_OR_DOCX_READBACK_FAILED';continue
            actual=alt.get('tailored_projects_used')
            if not isinstance(actual,dict) or _count_one(actual)>=_count_one(incumbent_fit.get('tailored_projects_used')):
                row['reason']='NO_PROJECT_DEPTH_GAIN';continue
            fitted_rows={_identity(p):p for p in actual.get('recommended_projects') or [] if isinstance(p,dict)}
            recipients=[p for p in fitted_rows.values() if _title(p)==candidate['recipient']]
            if len(recipients)!=1 or candidate['added_bullet'] not in recipients[0].get('draft_bullets',[]):
                row['reason']='ADDED_EVIDENCE_NOT_RETAINED';continue
            alt_verification=verify(alt)
            okay,reason,details=native_floors(initial_verification,alt_verification)
            row.update({'reason':reason,'native':details})
            if not okay:continue
            alt_depth=_count_one(actual)
            rank=(details['challenger'],-alt_depth)
            row['status']='VERIFIED_FEASIBLE'
            row['one_bullet_projects']=alt_depth
            if rank>best_rank:
                best_fit=alt
                best_rank=rank
                winner=i
        except Exception as exc:
            row['reason']='CANDIDATE_EXCEPTION_'+type(exc).__name__
            continue
    if winner is None:
        receipt['reason']='NO_NATIVE_SAFE_DEPTH_IMPROVEMENT'
        return incumbent_fit,receipt
    receipt['status']='SELECTED_NATIVE_SAFE_DEPTH_IMPROVEMENT'
    receipt['winner_probe']=winner
    receipt['selected_native_score']=best_rank[0]
    receipt['selected_one_bullet_projects']=-best_rank[1]
    receipt['no_approval_or_scorer_changes']=True
    return best_fit,receipt
