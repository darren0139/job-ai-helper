"""Evidence-bound research coverage units, separate from native Job Match."""
from collections import Counter, defaultdict
import re

from analysis_stability.stable_evidence_scoring import IMPORTANCE_WEIGHTS, MATCH_VALUES, requirement_is_score_eligible
from tailoring.phase9f_v365_jd_evidence import requirement_fragment
from tailoring.phase9f_v37_testing_gate import _NON_PERFORMED

BONUS = ('supporting', 'preferred')
_ACTION = re.compile(
    r'^(?:I\s+)?(?:built|created|developed|implemented|deployed|configured|maintained|used|'
    r'added|integrated|automated|managed|collaborated|contributed|wrote|ran|designed|led|'
    r'set up|performed|carried out|engineered|tested)\s+\S+',
    re.IGNORECASE,
)


def bonus_catalog(requirements, raw_jd, *, expected_jd):
    """Keep frozen classifications and allocations, including withheld siblings."""
    rows, parent_mass = {}, defaultdict(float)
    for req in requirements:
        rid = req['requirement_id']
        if rid in rows:
            raise ValueError('Duplicate frozen JD requirement ID.')
        parent = req.get('scoring_parent_occurrence_id') or req.get('atomic_group_id') or rid
        fraction = req.get('group_weight_fraction')
        valid_fraction = type(fraction) in (int, float) and 0 < fraction <= 1
        spans = req.get('source_provenance') or []
        fragment = requirement_fragment({'text': req['text'], 'parent': req.get('parent_text'),
                                         'source_provenance': spans}, raw_jd, expected_jd_text=expected_jd)
        if valid_fraction:
            parent_mass[parent] += fraction
        rows[rid] = {'text': req['text'], 'importance': req['importance'], 'parent': parent, 'fraction': fraction,
                     'original_parent': fragment['parent'], 'source_spans': spans,
                     'source_status': fragment['source_status'], 'grammar_status': fragment['grammar_status'],
                     'eligible': (valid_fraction and fragment['eligible_for_bonus_explanation']
                                  and any(s.get('grounding', {}).get('span_id') for s in spans)
                                  and requirement_is_score_eligible(req) and req.get('evidence_eligible', False)),
                     'weight': IMPORTANCE_WEIGHTS.get(req['importance'], 0) * fraction if valid_fraction else 0,
                     'exclusion': (fragment['reason'] if not fragment['eligible_for_bonus_explanation']
                                   else 'frozen_span_or_evidence_eligibility_unverified')}
    for row in rows.values():
        if parent_mass[row['parent']] > 1.000001:
            row.update(eligible=False, exclusion='parent_allocation_exceeds_original')
    return rows


def reviewed_bonus_links(catalog, excerpts, reviews):
    """Bind each human-reviewed relation to exact source wording and JD span."""
    accepted, withheld = defaultdict(dict), []
    for review in reviews:
        rid, key = review['requirement_id'], review['excerpt']
        row, excerpt = catalog.get(rid, {}), excerpts.get(key, {})
        text = excerpt.get('text', '')
        label, strength = review['label'], review['strength']
        skill = (excerpt.get('section') == 'skills' and excerpt.get('independently_attested') is True
                 and review.get('skill_qualification') is True)
        if (not row.get('eligible') or row['importance'] not in BONUS
                or excerpt.get('verified') is not True or review['wording'] != text or not review.get('basis')
                or label not in {'direct', 'transferable'} or type(strength) is not int or not 1 <= strength <= 5
                or _NON_PERFORMED.search(text) or not (_ACTION.search(text) or skill)):
            withheld.append({**review, 'reason': 'factual_relation_or_frozen_scope_unverified'})
            continue
        if rid in accepted[key]:
            raise ValueError('An excerpt has competing review entries for one requirement.')
        accepted[key][rid] = {'label': label, 'strength': strength, 'basis': review['basis'],
                              'evidence': excerpt, 'excerpt': key}
    return dict(accepted), withheld


def bonus_summary(catalog, links_by_excerpt, selected):
    """Strongest reviewed label per requirement, weighted by its frozen parent share."""
    rows = []
    for rid, requirement in catalog.items():
        if requirement['importance'] not in BONUS:
            continue
        matched = [links_by_excerpt.get(key, {}).get(rid) for key in dict.fromkeys(selected)]
        matched = [link for link in matched if link and requirement['eligible']]
        best = max(matched, key=lambda link: (MATCH_VALUES[link['label']], link['strength']), default=None)
        rows.append({**requirement, 'id': rid, 'earned': requirement['weight'] * MATCH_VALUES[best['label']] if best else 0,
                     'best': best, 'witness_count': len(matched),
                     'coverage': 'shared' if len(matched) > 1 else 'unique' if matched else 'unsupported' if requirement['eligible'] else 'withheld'})
    totals = {}
    for category in BONUS:
        eligible = [r for r in rows if r['importance'] == category and r['eligible']]
        totals[category] = {'available': round(sum(r['weight'] for r in eligible), 6),
                            'earned': round(sum(r['earned'] for r in eligible), 6),
                            'status': 'applicable' if eligible else 'not_applicable'}
    return {'categories': totals, 'requirements': rows,
            'total_additional_coverage_units': round(sum(t['earned'] for t in totals.values()), 6),
            'formula': 'Frozen importance × original parent share × strongest reviewed match value per canonical ID. Separate from native Job Match.'}


def uploaded_bonus_excerpts(resume_text, profile=None):
    """Ordinary uploads provide exact document claims without Library provenance."""
    from analysis_stability.stable_evidence_scoring import build_resume_evidence_index
    from tailoring.document_grounded_analysis import represented_profile

    rows = build_resume_evidence_index(represented_profile(profile or {}, resume_text), resume_text)
    return {row['source']: {**row, 'verified': True, 'independently_attested': False,
                            'provenance': 'uploaded résumé text'} for row in rows}
