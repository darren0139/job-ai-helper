"""Opt-in V3.7 same-work exclusion over the existing certified Phase 9F solver.

A lexical/activity classifier is not a factual or native-score judge. Only
same-project, cross-source high-confidence pairs create a *proposed challenger*
constraint. Historical fitted A, frozen sources, all receipts and approvals stay
unchanged. Any proposed B must still pass existing native/document/base floors.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import combinations
from typing import Any

from tailoring.phase9f_bullet_redundancy import compare_project_bullets, activity_facets

VERSION = 'phase9f-same-work-v3.7-v1'
RUN_MODE = 'v37-same-work'
CONFLICT_STATUSES = frozenset({'likely_same_work', 'same_wording'})
NEAR_IDENTICAL_THRESHOLD = 0.70


def _confident_same_work(a: str, b: str) -> bool:
    review = compare_project_bullets(a, b)
    if review.get('status') in CONFLICT_STATUSES:
        return True
    # A second, deliberately high bar catches near-identical variants of the
    # same activity without turning one shared keyword into a duplicate.
    from tailoring.phase9f_evidence_optimizer_v33 import overlap, tokens
    common = tokens(a) & tokens(b)
    return bool(len(common) >= 6 and (activity_facets(a) & activity_facets(b)) and
                overlap(a, b) >= NEAR_IDENTICAL_THRESHOLD)



def _cross_source(a: Any, b: Any) -> bool:
    aa, bb = set(a or []), set(b or [])
    return (('Selected Base' in aa and 'Evidence Library' in bb) or
            ('Evidence Library' in aa and 'Selected Base' in bb))


def conflict_indices(bullets: list[dict], groups: list[tuple]) -> list[tuple[int, int]]:
    """Hard conflicts: same project + differing sources + specific performed work.

    Intentionally NOT transitively clustered: an ambiguous A~B~C chain must
    not cause A/C to be classified as the same accomplishment without evidence.
    """
    pairs: list[tuple[int, int]] = []
    for _group, _audit, owned, _baseline in groups:
        for i, j in combinations(owned, 2):
            a, b = bullets[i], bullets[j]
            if not _cross_source(a.get('source_labels'), b.get('source_labels')):
                continue
            if _confident_same_work(a['text'], b['text']):
                pairs.append((i, j))
    return pairs


def selected_conflicts(proposal: dict) -> list[dict]:
    """Check V3.5 fallback proposed B; do not modify its factual source rows."""
    found = []
    for project in proposal.get('projects') or []:
        if not isinstance(project, dict):
            continue
        texts, origins = project.get('after') or [], project.get('sources') or []
        if not isinstance(texts, list) or len(texts) != len(origins):
            # An incomplete fallback cannot be certified as deduplicated.
            return [{'project': str(project.get('project') or ''), 'reason': 'invalid_source_lineage'}]
        for i, j in combinations(range(len(texts)), 2):
            if not _cross_source(origins[i], origins[j]):
                continue
            if _confident_same_work(str(texts[i]), str(texts[j])):
                found.append({'project': str(project.get('project') or ''),
                              'first_index': i, 'second_index': j,
                              'reason': 'confident_same_work'})
    return found


def vet_fallback(result: dict) -> dict:
    """Never offer a duplicate-filled fallback as a V3.7 one-of-two challenger.

    A V3.5 fallback is still permitted if one of its already prepared variants
    meets the new policy. There is no unverified or silently edited selection.
    """
    if not isinstance(result, dict) or result.get('status') != 'candidate':
        return result
    variants = result.get('candidate_variants') or [result]
    valid = [v for v in variants if isinstance(v, dict) and v.get('projects') and
             not selected_conflicts(v)]
    if not valid:
        out = {k: deepcopy(v) for k, v in result.items()
               if k not in ('candidate_variants', 'projects')}
        out.update({'status': 'no_proxy_gain', 'changed': False, 'projects': [],
                    'reason': 'Fallback produced no candidate satisfying the same-work one-of-two rule; existing fitted résumé retained.',
                    'candidate_variants': [], 'same_work_fallback_screen': 'rejected_all'})
        return out
    # Variant has its own untouched source comparison and optimization objective.
    first = deepcopy({k: v for k, v in valid[0].items() if k != 'candidate_variants'})
    first['candidate_variants'] = [deepcopy({k: v for k, v in x.items()
                                            if k != 'candidate_variants'}) for x in valid]
    first['shortlist_size'] = len(valid)
    first['same_work_fallback_screen'] = 'verified_proposed_memberships'
    return first


def build_same_work_optimization(audit: dict, projects: dict, *, evaluator=None,
                                 max_trials=None, bonus_priorities=None) -> dict:
    """Propose a deduplicated challenger; NEVER auto-approve or alter incumbent."""
    from tailoring.phase9f_certified_selection_v36 import (
        MAX_TRIALS, build_certified_optimization)
    if max_trials is None:
        max_trials = MAX_TRIALS
    options = {'bonus_priorities': bonus_priorities} if bonus_priorities else {}
    result = build_certified_optimization(audit, projects, evaluator=evaluator,
                                          max_trials=max_trials, same_work_guard=True, **options)
    if not isinstance(result, dict):
        return {'status': 'withheld', 'version': VERSION,
                'reason': 'Certified optimizer did not return a receipt.'}
    # The existing A/B shortlist evaluator requires its historical V3.5
    # *proposal serialization version*. Keep that version intact and attach
    # the V3.7 policy separately; otherwise it rejects all shortlisted trials.
    out = dict(result)
    out['same_work_selector_version'] = VERSION
    policy = {
        'version': VERSION,
        'scope': 'same-project cross-source confident same-activity pairs',
        'candidate_rule': 'at_most_one',
        'incumbent_unchanged': True,
        'native_document_and_selected_base_floors_required': True,
        'inference_limit': 'Keyword/activity similarity does not prove one wording is factually better.',
    }
    out['same_work_policy'] = policy
    if isinstance(out.get('candidate_variants'), list):
        out['candidate_variants'] = [
            {**row, 'same_work_selector_version': VERSION, 'same_work_policy': policy}
            if isinstance(row, dict) else row
            for row in out['candidate_variants']]
    from tailoring.phase9f_bullet_score_v38 import attach_bullet_scores
    return attach_bullet_scores(out, projects)


def verified_tie_dedupe(*, audit: dict, proposal: dict,
                        original_score: dict, alternative_score: dict) -> bool:
    """Opt-in native score tie-break ONLY for verified same-work reductions.

    Call only after evaluate_auto independently verified both one-page DOCX
    files and compare_document_candidates reported a clean score tie. We also
    demand that *every* JD requirement label and numeric strength is non-worse.
    Selected Base floor is checked by the caller after this provisional choice.
    """
    if (not isinstance(proposal, dict) or
            (proposal.get('same_work_policy') or {}).get('version') != VERSION):
        return False
    audits = audit.get('projects') or []
    groups = (proposal.get('source_comparison') or {}).get('projects') or []
    after = proposal.get('projects') or []
    if not (isinstance(audits, list) and len(audits) == len(groups) == len(after)
            and len(audits) > 0):
        return False
    from tailoring.phase9f_joint_resume_optimizer_v2_6 import _key
    before_for_check = []
    original_count = optimized_count = 0
    for section, group, chosen in zip(audits, groups, after):
        name = _key(section.get('project'))
        if not name or _key(group.get('project')) != name or _key(chosen.get('project')) != name:
            return False
        pool = {}
        for entry in group.get('candidates') or []:
            k = _key(entry.get('text'))
            if not k or k in pool:
                return False
            pool[k] = entry
        previous = []
        for item in section.get('final') or []:
            word = str(item.get('text') or '')
            row = pool.get(_key(word))
            if row is None or not row.get('in_original_a'):
                return False
            previous.append((word, row.get('source_labels') or []))
        if not previous:
            return False
        proposed_words = chosen.get('after') or []
        proposed_origins = chosen.get('sources') or []
        if (not isinstance(proposed_words, list) or
                len(proposed_words) != len(proposed_origins) or not proposed_words):
            return False
        for word, origins in zip(proposed_words, proposed_origins):
            row = pool.get(_key(word))
            if row is None or set(row.get('source_labels') or []) != set(origins or []):
                return False
        before_for_check.append({'project': name,
                                 'after': [w for w, _ in previous],
                                 'sources': [p for _, p in previous]})
        original_count += len(previous)
        optimized_count += len(proposed_words)
    if optimized_count > original_count:
        return False
    before_conflicts = selected_conflicts({'projects': before_for_check})
    if not before_conflicts or selected_conflicts(proposal):
        return False
    old = original_score.get('canonical_requirements') or []
    new = alternative_score.get('canonical_requirements') or []
    if not old or len(old) != len(new):
        return False
    from tailoring.phase9f_automatic_bestof_v30 import RANK
    def req_map(rows):
        ret = {}
        for row in rows:
            rid = str(row.get('requirement_id') or '') if isinstance(row, dict) else ''
            if not rid or rid in ret:
                return None
            ret[rid] = row
        return ret
    aa, bb = req_map(old), req_map(new)
    if aa is None or bb is None or aa.keys() != bb.keys():
        return False
    for rid, a in aa.items():
        b = bb[rid]
        if (a.get('importance') != b.get('importance') or
                a.get('match_label') not in RANK or b.get('match_label') not in RANK or
                RANK[b['match_label']] < RANK[a['match_label']]):
            return False
        strength_a, strength_b = a.get('evidence_strength'), b.get('evidence_strength')
        if (isinstance(strength_a, (int,float)) and not isinstance(strength_a,bool)
                and isinstance(strength_b, (int,float)) and not isinstance(strength_b,bool)
                and strength_b < strength_a):
            return False
    return True
