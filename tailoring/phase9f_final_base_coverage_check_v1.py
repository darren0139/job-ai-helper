"""Read-only JD project-bullet coverage proxy vs selected frozen Base.

Not the Phase 8 Initial-vs-Tailored résumé score: only supplied project
bullets, saved requirement ranking, and the same deterministic evaluator are used.
"""
from __future__ import annotations
from math import isfinite
from typing import Any, Callable

VERSION = 'phase9f-v27-final-base-project-coverage-proxy-v1'


def _norm(value: Any) -> str:
    return ' '.join(str(value or '').split()).casefold()


def build_final_vs_base_project_coverage(
    audit: dict[str, Any], projects: dict[str, Any],
    *, evaluator: Callable[..., list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Fail closed for unverified DOCX or missing comparable JD evidence."""
    def withheld(reason):
        return {'status': 'withheld', 'reason': reason, 'is_verified_overall_improvement': False}
    if not isinstance(audit, dict) or audit.get('verified') is not True:
        return withheld('Exact verified fitted DOCX audit required.')
    if not audit.get('generation_id') or not audit.get('docx_sha256'):
        return withheld('Final generation and DOCX digest are missing.')
    sections = audit.get('projects')
    ranks = (projects or {}).get('candidate_project_ranking') if isinstance(projects, dict) else None
    if not isinstance(sections, list) or not sections or not isinstance(ranks, list):
        return withheld('Final project sections and saved JD ranking are required.')
    if evaluator is None:
        from tailoring.stable_tailoring_ranking import build_bullet_evidence_priorities
        evaluator = build_bullet_evidence_priorities
    rank_map = {}
    for r in ranks:
        if not isinstance(r, dict) or not _norm(r.get('title') or r.get('display_title')):
            return withheld('Incomplete saved JD ranking.')
        key = _norm(r.get('display_title') or r.get('title'))
        if key in rank_map:
            return withheld('Duplicate project ranking identity.')
        rank_map[key] = r
    by_requirement, base_found, final_found = {}, set(), set()
    base_words = final_words = 0
    seen_titles = set()
    for item in sections:
        if not isinstance(item, dict):
            return withheld('Invalid audited project.')
        key = _norm(item.get('project'))
        if not key or key in seen_titles or key not in rank_map:
            return withheld('Project identity missing, duplicated or not in saved ranking.')
        seen_titles.add(key)
        rank = rank_map[key]
        rows = rank.get('requirement_matches')
        if not isinstance(rows, list):
            return withheld('Saved JD requirement evidence unavailable.')
        weights = {}
        for r in rows:
            if not isinstance(r, dict):
                return withheld('Invalid requirement row.')
            rid = str(r.get('requirement_id') or '')
            if not rid or rid in weights:
                return withheld('Ambiguous JD requirement identity.')
            label = str(r.get('match_label') or '').casefold()
            if label not in ('direct', 'transferable', 'weak', 'none'):
                return withheld('Unknown saved requirement match type.')
            if label != 'none':
                try: weight = float(r.get('coverage_points'))
                except (ValueError, TypeError): return withheld('Missing saved JD coverage weight.')
                if not isfinite(weight) or weight < 0 or weight > 10000:
                    return withheld('Invalid saved JD coverage weight.')
                weights[rid] = (weight, str(r.get('importance') or '').casefold())
        base = item.get('base'); final = item.get('final')
        if (not isinstance(base, list) or not isinstance(final, list) or not base or not final
                or any(not isinstance(x, dict) or not isinstance(x.get('text'), str)
                       or not _norm(x.get('text')) for x in base + final)):
            return withheld('A project lacks exact Base or final bullet text; not comparable.')
        base_texts = [r['text'] for r in base]
        final_texts = [r['text'] for r in final]
        if len({_norm(x) for x in base_texts}) != len(base_texts) or len({_norm(x) for x in final_texts}) != len(final_texts):
            return withheld('Duplicate bullet identities found.')
        base_words += sum(len(x.split()) for x in base_texts)
        final_words += sum(len(x.split()) for x in final_texts)
        for tag, bullets, dst in [('Base', base_texts, base_found), ('Final', final_texts, final_found)]:
            try: matched = evaluator(bullets=bullets, ranking_row=rank)
            except Exception: return withheld('JD coverage evaluator failed.')
            if (not isinstance(matched, list) or len(matched) != len(bullets)
                    or any(not isinstance(x, dict) or x.get('bullet_index') != i
                           or _norm(x.get('bullet_text')) != _norm(bullets[i])
                           or not isinstance(x.get('supported_requirement_ids'), list)
                           for i, x in enumerate(matched))):
                return withheld('JD evaluator did not preserve bullet identity/order.')
            for x in matched:
                for rid in x['supported_requirement_ids']:
                    if not isinstance(rid, str) or rid not in weights:
                        return withheld('JD evaluator returned unknown or non-scoring requirement.')
                    dst.add(rid)
        for rid, info in weights.items():
            if rid in by_requirement and by_requirement[rid] != info:
                return withheld('Same JD requirement has conflicting weights between projects.')
            by_requirement[rid] = info
    def points(ids): return round(sum(by_requirement[x][0] for x in ids), 4)
    lost = base_found - final_found
    gained = final_found - base_found
    lost_required = sorted(x for x in lost if by_requirement[x][1] in {'required', 'core'})
    old, new = points(base_found), points(final_found)
    if new > old and not lost_required:
        verdict = 'higher_project_coverage_proxy_no_primary_loss'
    elif new > old:
        verdict = 'higher_total_proxy_but_primary_coverage_loss'
    elif new == old:
        verdict = 'no_project_coverage_proxy_gain'
    else:
        verdict = 'lower_project_coverage_proxy'
    return {'status':'comparable_project_proxy', 'verdict':verdict,
            'base_points': old, 'final_points': new, 'delta': round(new-old,4),
            'base_words':base_words, 'final_words':final_words,
            'gained_ids': sorted(gained), 'lost_ids':sorted(lost), 'lost_required_core_ids':lost_required,
            'base_coverage_ids': sorted(base_found), 'final_coverage_ids':sorted(final_found),
            'generation_id':audit['generation_id'], 'docx_sha256':audit['docx_sha256'],
            'is_verified_overall_improvement':False,
            'notice':('This compares only project-bullet JD coverage against the selected frozen Base, using '
                      'one saved ranking and the same evaluator. It does not compare education, skills, work '
                      'experience or complete Phase 8 Initial-vs-Tailored Job Match scores; '
                      'it cannot certify an improved résumé.')}
