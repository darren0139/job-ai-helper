"""Read-only, auditable bullet-selection calculation for Phase 9F V3.6.

A membership/coverage receipt is not evidence of a causal per-bullet winner.
This module never rewrites source evidence, invokes an optimizer, performs a
native Job Match comparison, reads files, or approves a candidate.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

VERSION = 'phase9f-bullet-calculation-receipt-v3.6.3-v1'


def _words(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0 or int(value) != value:
        return None
    return int(value)


def build_bullet_selection_calculation(proposal: Any, result: Any) -> dict[str, Any]:
    """Describe exactly what the saved proxy proposal establishes, not why a human would pick it."""
    def unavailable(why: str) -> dict[str, Any]:
        return {'schema': VERSION, 'status': 'unavailable', 'reason': why, 'rows': [],
                'source_competitions': [], 'objective_stages': [], 'actual_verification': {}}

    if not isinstance(proposal, dict) or not isinstance(result, dict):
        return unavailable('No optimizer result/proposal saved.')
    groups = (proposal.get('source_comparison') or {}).get('projects')
    if not isinstance(groups, list) or not groups:
        return unavailable('Frozen eligible Base/Library candidate list not saved.')
    certificate = proposal.get('mathematical_certificate') or {}
    if not isinstance(certificate, dict):
        certificate = {}
    rows = []
    by_wording = {}
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get('project'), str):
            return unavailable('Malformed source project group.')
        project = group['project']
        for candidate in group.get('candidates') or []:
            if not isinstance(candidate, dict) or not isinstance(candidate.get('text'), str):
                return unavailable('Malformed candidate text.')
            wording = candidate['text'].strip()
            ident = (project, wording)
            if not wording:
                return unavailable('Blank source wording cannot be explained.')
            raw_ids = candidate.get('saved_jd_ids') or []
            if not isinstance(raw_ids, (list, tuple)) or any(not isinstance(v, str) or not v for v in raw_ids):
                return unavailable('Invalid canonical JD identities in candidate.')
            sources = candidate.get('source_labels') or []
            if not isinstance(sources, list) or any(not isinstance(x, str) for x in sources):
                return unavailable('Invalid saved source labels.')
            hits = candidate.get('v35_jd_term_hits') or []
            if not isinstance(hits, list) or any(not isinstance(x, str) for x in hits):
                return unavailable('Invalid JD terminology hits.')
            row = {'project': project, 'bullet': wording, 'sources': list(dict.fromkeys(sources)),
                         'in_actual_a': bool(candidate.get('in_original_a')),
                         'in_proposed_b': bool(candidate.get('selected_for_proposed_b')),
                         'saved_jd_ids': sorted(set(raw_ids)),
                         'jd_terms': sorted(set(hits)),
                         'words': _words(candidate.get('word_count')),
                         'standalone_proxy_points': candidate.get('standalone_saved_coverage_points'),
                         'link_corroboration': candidate.get('v35_link_corroboration'),
                         }
            previous = by_wording.get(ident)
            if previous is None:
                by_wording[ident] = row
                rows.append(row)
                continue
            for key in ('sources', 'saved_jd_ids', 'jd_terms'):
                previous[key] = list(dict.fromkeys(previous[key] + row[key]))
            for key in ('in_actual_a', 'in_proposed_b'):
                previous[key] |= row[key]
            for key in ('words', 'standalone_proxy_points', 'link_corroboration'):
                if previous[key] != row[key]:
                    previous[key] = None
    selected = [r for r in rows if r['in_proposed_b']]
    if not selected:
        return {**unavailable('The eligible pool was saved without a selected slate.'), 'rows': rows}
    support = Counter(rid for row in selected for rid in row['saved_jd_ids'])
    term_support = Counter(t for row in selected for t in row['jd_terms'])
    covered = set(support)
    terms_covered = set(term_support)
    for row in rows:
        if row['in_proposed_b']:
            row['exclusive_jd_ids_in_b'] = [r for r in row['saved_jd_ids'] if support[r] == 1]
            row['shared_jd_ids_in_b'] = [r for r in row['saved_jd_ids'] if support[r] > 1]
            row['exclusive_jd_terms_in_b'] = [t for t in row['jd_terms'] if term_support[t] == 1]
            row['potential_new_jd_ids'] = []
            row['potential_new_jd_terms'] = []
            row['decision_code'] = 'included_in_proposed_slate'
        else:
            row['exclusive_jd_ids_in_b'] = []
            row['shared_jd_ids_in_b'] = []
            row['exclusive_jd_terms_in_b'] = []
            row['potential_new_jd_ids'] = sorted(set(row['saved_jd_ids']) - covered)
            row['potential_new_jd_terms'] = sorted(set(row['jd_terms']) - terms_covered)
            row['decision_code'] = 'excluded_from_proposed_slate'
        row['claim_limit'] = ('This is a saved-link/wording membership calculation; '
                              'it does not prove semantic evidence strength, native score effect, '
                              'or that this bullet individually defeated an alternative.')

    # Pairs only show directly inspectable Base vs Library alternatives sharing a
    # saved canonical JD identity within the same project; they are NOT a
    # counterfactual optimization with one source forced in/out.
    pair_rows = []
    for a in rows:
        a_base = 'Selected Base' in a['sources'] and 'Evidence Library' not in a['sources']
        if not a_base:
            continue
        for b in rows:
            if a['project'] != b['project'] or 'Evidence Library' not in b['sources'] or 'Selected Base' in b['sources']:
                continue
            both = sorted(set(a['saved_jd_ids']) & set(b['saved_jd_ids']))
            if not both:
                continue
            pair_rows.append({'project':a['project'], 'base_bullet':a['bullet'], 'library_bullet':b['bullet'],
                'shared_saved_jd_ids':both,
                'base_in_a':a['in_actual_a'], 'library_in_a':b['in_actual_a'],
                'base_in_b':a['in_proposed_b'], 'library_in_b':b['in_proposed_b'],
                'base_words':a['words'], 'library_words':b['words'],
                'base_jd_terms':a['jd_terms'], 'library_jd_terms':b['jd_terms'],
                'conclusion':'Membership and saved evidence overlap only; no head-to-head causal winner measured.'})
    phase_rows = []
    for p in certificate.get('phase_receipts') or []:
        if not isinstance(p, dict):
            continue
        label = str(p.get('priority') or '')
        raw = p.get('minimization_objective')
        value = None
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            if label == 'weighted_saved_JD_coverage': value = -float(raw)/1000.0
            elif label == 'distinct_JD_terms_minus_overlap': value = -float(raw)
            elif label == 'source_bullet_words': value = float(raw)
        phase_rows.append({'priority': label, 'recorded_minimization_objective': raw,
                           'interpreted_maximum_or_cost': value,
                           'status': p.get('status'), 'best_bound': p.get('best_bound_reported')})
    trials = result.get('v35_trial_receipts') or []
    actual = [{'trial':t.get('trial'), 'status':t.get('status'),
               'a_score':t.get('a_score'), 'b_score':t.get('b_score'),
               'native_delta':t.get('native_delta'), 'winner':t.get('winner')}
              for t in trials if isinstance(t, dict)]
    start = result.get('a_vs_starting')
    starting = ({'status': start.get('status'),
                'initial_comparison_status':start.get('initial_comparison_status'),
                'selected_base_comparison_status':start.get('selected_base_comparison_status')}
                if isinstance(start, dict) else {'status':'not_available'})
    return {'schema':VERSION,'status':'available',
            'solver_status':certificate.get('status') or 'not_recorded',
            'solver':certificate.get('solver') or 'not_recorded',
            'optimality_gap':certificate.get('optimality_gap'),
            'proxy_is_not_native_optimality': True,
            'objective_stages':phase_rows,
            'rows':rows,'source_competitions':pair_rows,
            'summary':{'eligible_wordings':len(rows), 'selected_bullets_in_b':len(selected),
                       'actual_a_bullets_in_pool':sum(r['in_actual_a'] for r in rows),
                       'saved_jd_ids_in_b':sorted(covered),
                       'jd_terms_in_b':sorted(terms_covered),
                       'proxy_points_baseline':proposal.get('baseline_points'),
                       'proxy_points_proposed':proposal.get('proposed_points'),
                       'word_cost_baseline':proposal.get('baseline_words'),
                       'word_cost_proposed':proposal.get('proposed_words')},
            'actual_verification':{'status':result.get('status'),'winner':result.get('winner'),
                'reason':result.get('reason'), 'trials':actual,
                'starting_resumes':starting},
            'interpretation':('A selected bullet may have zero exclusive saved JD IDs and still have narrative or '
                'evidence-strength value. An excluded bullet with potential coverage is not automatically feasible '
                'to insert under the page budget. To attribute causality, rerun native DOCX scoring or an explicit '
                'forced-in/out mathematical counterfactual; neither is computed by this receipt.')}
