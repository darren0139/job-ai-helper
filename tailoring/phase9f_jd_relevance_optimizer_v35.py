"""V3.5 grounded JD-relevance-first shortlist for native DOCX best-of.

The frozen V3.1 source/JD evaluator is the only JD-support authority. Exact
textual JD terms are *advisory ranking signals*, never independent evidence
credit. All candidate slates are immutable Base/Library/Current-final wording.
A bounded native DOCX/PDF comparator, not this proxy, determines any winner.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from itertools import combinations
from math import sqrt
import re
from typing import Callable

from tailoring.phase9f_auto_optimize_v31 import build_flexible_optimization
from tailoring.phase9f_evidence_optimizer_v33 import _metadata, overlap
from tailoring.phase9f_large_pool_v312b214b2 import prepare_sources, bounded_local_slates
from tailoring.phase9f_joint_resume_optimizer_v2_6 import MAX_POOL_PER_PROJECT
from functools import lru_cache
from tailoring.phase9f_joint_resume_optimizer_v2_6 import _get_rank, _key, _points

VERSION = 'phase9f-jd-relevance-v3.5-v1'
MAX_LOCAL_SLATES = 72
MAX_BEAM = 180
MAX_TRIALS = 3
MAX_WORD_SLACK = 24
MAX_TOTAL_BULLETS = 48
MAX_COUNT_DELTA = 2
MAX_TOTAL_EDITS = 8
MAX_LOCAL_BULLETS = 8
HARD = {'required', 'core', 'deal_breaker'}
# High-frequency JD prose, not suitable as meaningful keywords on its own.
STOP = frozenset('a an and are as at be by can for from in into is it its of on or our the their these this through to up using use with will one more years year have has should possess ideal candidate requirement requirements relevant advantage ability able different support supports software application applications system systems develop development experience proficiency functional technical meet work working build'.split())
WORD = re.compile(r'[A-Za-z][A-Za-z0-9+#.\\/-]*')


def _terms(text: object) -> frozenset[str]:
    result = set()
    for raw in WORD.findall(str(text or '').casefold()):
        term = raw.strip('-./')
        if term.endswith('ies') and len(term) > 5:
            term = term[:-3] + 'y'
        elif term.endswith('ing') and len(term) > 6:
            term = term[:-3]
        elif term.endswith('s') and len(term) > 5 and not term.endswith('ss'):
            term = term[:-1]
        if len(term) >= 3 and term not in STOP:
            result.add(term)
    return frozenset(result)


def _hold(reason: str, original: dict | None = None) -> dict:
    out = {'version': VERSION, 'status': 'withheld', 'reason': reason, 'projects': []}
    if isinstance(original, dict) and isinstance(original.get('source_comparison'), dict):
        out['source_comparison'] = deepcopy(original['source_comparison'])
    return out


def build_jd_relevance_optimization(audit: dict, projects: dict, *,
                                    evaluator: Callable | None = None,
                                    max_trials: int = MAX_TRIALS) -> dict:
    """Bounded complete-resume beam; output up to three independently gated trials.

    Preserve every saved baseline JD identity, including Preferred. A shortlist
    may exceed original bullet-word count by at most 24 words, but an independent
    actual one-page PDF render is still mandatory. Never invent JD links or
    factual claims, equate keyword cues with match strength, or modify A.
    """
    if isinstance(max_trials, bool) or not isinstance(max_trials, int) or not 1 <= max_trials <= MAX_TRIALS:
        return _hold('Invalid bounded native trial count.')
    source = prepare_sources(audit, projects, evaluator=evaluator, legacy_builder=build_flexible_optimization)
    if source.get('status') == 'withheld':
        return _hold(str(source.get('reason') or 'Frozen source evaluation withheld.'), source)
    comp = source.get('source_comparison')
    groups = comp.get('projects') if isinstance(comp, dict) else None
    sections = audit.get('projects') if isinstance(audit, dict) else None
    if not isinstance(groups, list) or not isinstance(sections, list) or len(groups) != len(sections):
        return _hold('Source pool and verified actual DOCX project count differ.', source)
    weights, req_texts, err = _metadata(projects, comp)
    if err or not weights:
        return _hold(err or 'No saved JD coverage receipt.', source)
    kinds = {}
    for group in groups:
        rank = _get_rank(projects, str(group.get('project') or ''))
        if rank is None: return _hold('Frozen project rank missing.', source)
        for match in rank.get('requirement_matches') or []:
            rid = str(match.get('requirement_id') or '')
            if not rid or rid not in weights: continue
            k = str(match.get('importance') or 'unknown').casefold()
            if rid in kinds and kinds[rid] != k: return _hold('Conflicting JD importance receipts.', source)
            kinds[rid] = k
    req_terms = {rid: _terms(text) for rid, text in req_texts.items() if rid in weights}
    all_terms = frozenset().union(*req_terms.values()) if req_terms else frozenset()
    rarity = Counter(t for terms in req_terms.values() for t in terms)
    token_weight = {term: round(1 / sqrt(count), 4) for term, count in rarity.items()}
    project_items = []
    baseline_words = 0
    baseline_ids = set()
    baseline_bullets = 0
    for group, section in zip(groups, sections):
        name = str(group.get('project') or '')
        if _key(name) != _key(section.get('project')):
            return _hold('Frozen project ownership/order differs from actual A.', source)
        cands = group.get('candidates')
        actual = section.get('final')
        if not isinstance(cands, list) or not isinstance(actual, list) or not cands or not actual:
            return _hold('Missing exact source bullet candidates or actual A.', source)
        bykey = {}
        for n, c in enumerate(cands):
            if not isinstance(c, dict) or not isinstance(c.get('text'), str):
                return _hold('Malformed source bullet.', source)
            key = _key(c['text'])
            if not key or key in bykey: return _hold('Ambiguous duplicate source bullet identity.', source)
            bykey[key] = n
            ids = set(c.get('saved_jd_ids') or [])
            if not ids <= weights.keys(): return _hold('Unrecognized frozen JD requirement ID.', source)
            terms = _terms(c['text'])
            hits = sorted(terms & all_terms)
            c['v35_jd_term_hits'] = hits
            c['v35_jd_term_signal'] = round(sum(token_weight[t] for t in hits), 4)
            # Stronger terminology within an already saved JD link is an
            # auxiliary corroboration cue, not proof of a direct JD match.
            c['v35_link_corroboration'] = round(sum(
                min(1.0, len(terms & req_terms.get(rid, frozenset())) /
                    max(2, len(req_terms.get(rid, frozenset())))) * min(weights[rid], 30) / 10
                for rid in ids), 4)
            c['v35_no_new_evidence_claim'] = True
        original = [str(x.get('text') or '') for x in actual if isinstance(x, dict)]
        if len(original) != len(actual) or not all(original): return _hold('Invalid actual A bullet identity.', source)
        try: base = tuple(bykey[_key(x)] for x in original)
        except KeyError: return _hold('Actual A bullet not in the frozen candidate pool.', source)
        if len(set(base)) != len(base):return _hold('Duplicate bullet in actual A.', source)
        baseline_bullets += len(base)
        baseline_words += sum(int(cands[i]['word_count']) for i in base)
        baseline_ids.update(*(set(cands[i]['saved_jd_ids']) for i in base))
        # Local subsets: high JD coverage and specificity, compactness and
        # baseline identity all receive representation in the cross-project beam.
        counts = range(max(1, len(base)-1), min(len(cands), MAX_LOCAL_BULLETS, len(base)+2) + 1)
        pair_overlap = lru_cache(maxsize=8192)(overlap) if len(cands) > MAX_POOL_PER_PROJECT else overlap
        def score(combo):
            chosen = [cands[i] for i in combo]
            ids = {rid for c in chosen for rid in c['saved_jd_ids']}
            words = sum(int(c['word_count']) for c in chosen)
            terms = frozenset(t for c in chosen for t in c['v35_jd_term_hits'])
            corroboration = sum(max((float(c['v35_link_corroboration']) for c in chosen
                if rid in c['saved_jd_ids']), default=0.0) for rid in ids)
            overlaps = sum(1 for a, b in combinations(chosen, 2)
                if set(a['saved_jd_ids']) & set(b['saved_jd_ids']) and pair_overlap(a['text'], b['text']) >= .46)
            lex = sum(token_weight[t] for t in terms)
            # Scores are deliberately advisory and non-ATS; distinct saved
            # JD IDs dominate a small bounded lexical/overlap tie-break.
            quality = round(lex + 1.5 * corroboration - 3.25 * overlaps, 4)
            edits = len(set(combo) ^ set(base))
            library = sum('Evidence Library' in c['source_labels'] and
                          'Selected Base' not in c['source_labels'] for c in chosen)
            return {'ix':combo, 'ids':frozenset(ids), 'words':words,
                'terms':terms, 'corrob':corroboration, 'overlaps':overlaps,
                'quality':quality, 'edits':edits, 'library':library,
                'count':len(combo)}
        local = lambda s: (-_points(set(s['ids']), weights), -s['quality'],
                           s['overlaps'], s['edits'], s['words'], -s['library'], s['ix'])
        space = lambda s: (s['words'], -_points(set(s['ids']),weights), -s['quality'],s['ix'])
        stability = lambda s: (s['edits'], -s['quality'],s['words'],s['ix'])
        if len(cands) > MAX_POOL_PER_PROJECT:
            slates, receipt = bounded_local_slates(cands, base, counts, score, local, space, stability)
            group['large_pool_search'] = receipt
        else:
            slates = [score(combo) for count in counts for combo in combinations(range(len(cands)), count)]
        by_quality = sorted(slates, key=local)[:42]
        by_space = sorted(slates, key=lambda s: (s['words'], -_points(set(s['ids']),weights),
                                                       -s['quality'],s['ix']))[:15]
        by_stability = sorted(slates, key=lambda s: (s['edits'], -s['quality'],s['words'],s['ix']))[:15]
        if len(cands) > MAX_POOL_PER_PROJECT:
            # Preserve some low-frequency link states in the actual retained
            # local shortlist, not only the expansion beam. No static top-N
            # source filter: candidates outside these slates remain auditable.
            freq = Counter(r for c in cands for r in c['saved_jd_ids'])
            by_rare = sorted(slates, key=lambda s: (-sum(1/freq[r] for r in sorted(s['ids'])), local(s)))[:12]
            retained = by_quality[:36]+by_space[:12]+by_stability[:12]+by_rare
        else:
            retained = by_quality+by_space+by_stability
        kept = {s['ix']:s for s in retained}
        basekey = tuple(sorted(base))
        if basekey not in kept:
            kept[basekey] = next(s for s in slates if s['ix'] == basekey)
        project_items.append({'project':name,'candidates':cands,'actual':original,
                              'base':base,'slates':list(kept.values())[:MAX_LOCAL_SLATES+1]})
    if not baseline_ids or baseline_words > 1500 or baseline_bullets > MAX_TOTAL_BULLETS:
        return _hold('No bounded starting JD coverage or project bullet budget.', source)
    required = {rid for rid in baseline_ids if kinds.get(rid) != 'preferred'}
    budget = min(1500, baseline_words + min(MAX_WORD_SLACK, max(8, round(baseline_words * .08))))
    beam = [{'slates':(), 'ids':frozenset(), 'terms':frozenset(),
             'corrob':0., 'overlaps':0, 'words':0, 'count':0,
             'edits':0, 'library':0, 'signature':()}]
    def value(s:dict):
        cue = sum(token_weight[t] for t in s['terms'])
        return round(cue + 1.5*s['corrob'] - 3.25*s['overlaps'], 4)
    def order(s:dict):
        return (-_points(set(s['ids']),weights), -value(s),s['overlaps'],
                s['edits'], s['words'], -s['library'],s['signature'])
    for item in project_items:
        expanded=[]
        for state in beam:
            for slate in item['slates']:
                words = state['words'] + slate['words']
                count = state['count'] + slate['count']
                if (words > budget or count > MAX_TOTAL_BULLETS or
                        state['edits'] + slate['edits'] > MAX_TOTAL_EDITS): continue
                expanded.append({'slates':state['slates']+(slate,),
                    'ids':state['ids']|slate['ids'], 'terms':state['terms']|slate['terms'],
                    'corrob':state['corrob']+slate['corrob'],
                    'overlaps':state['overlaps']+slate['overlaps'],
                    'words':words,'count':count,'edits':state['edits']+slate['edits'],
                    'library':state['library']+slate['library'],
                    'signature':state['signature']+(slate['ix'],)})
        if not expanded:return _hold('No bounded slate fits the guarded pre-render word budget.',source)
        # Keep both strong candidates and some compact ones for future projects.
        ranked=sorted(expanded,key=order)[:145]
        lean=sorted(expanded,key=lambda s: (s['words'],-_points(set(s['ids']),weights),
                                                  -value(s),s['signature']))[:35]
        seen=set();beam=[]
        for state in ranked+lean:
            if state['signature'] not in seen:
                seen.add(state['signature']);beam.append(state)
            if len(beam)>=MAX_BEAM:break
    feasible=[s for s in beam if (required <= s['ids'] and baseline_ids <= s['ids'] and
        baseline_bullets-MAX_COUNT_DELTA <= s['count'] <= baseline_bullets+MAX_COUNT_DELTA)]
    if not feasible:
        return _hold('No bounded alternative preserves every baseline saved JD link.',source)
    base_ix = tuple(tuple(sorted(item['base'])) for item in project_items)
    baseline = next((s for s in feasible if s['signature']==base_ix),None)
    # Keep the true baseline for comparison even if beam pruned it.
    if baseline is None:
        slates = [next(s for s in item['slates'] if s['ix']==tuple(sorted(item['base']))) for item in project_items]
        baseline = {'slates':tuple(slates),'ids':frozenset(baseline_ids),
            'terms':frozenset().union(*(s['terms'] for s in slates)),
            'corrob':sum(s['corrob'] for s in slates), 'overlaps':sum(s['overlaps'] for s in slates),
            'words':baseline_words,'count':baseline_bullets,'edits':0,
            'library':sum(s['library'] for s in slates),'signature':base_ix}
    baseline_quality=value(baseline)
    ranked=sorted(feasible,key=order)
    admissible=[]
    tried_tradeoffs=set()
    for s in ranked:
        if s['signature']==base_ix:continue
        higher_coverage=_points(set(s['ids']),weights)>_points(baseline_ids,weights)
        better_quality=value(s)>baseline_quality+0.01
        exact_tie=(abs(value(s)-baseline_quality)<=0.01 and
                   s['words']==baseline_words and s['overlaps']==baseline['overlaps']
                   and s['library']>baseline['library'])
        if not (higher_coverage or better_quality or exact_tie):continue
        # Test distinct relevance/coverage trade-offs, not three almost
        # identical deletions with identical JD evidence and term signals.
        tradeoff=(_points(set(s['ids']),weights),round(value(s),2),
                  s['overlaps'], tuple(sorted(s['terms'])))
        if tradeoff in tried_tradeoffs:continue
        tried_tradeoffs.add(tradeoff)
        admissible.append(s)
        if len(admissible)>=max_trials:break
    def create(s:dict, rank_index:int) -> dict:
        rows=[];selected_by_group=[];base_only=False
        for item,slate in zip(project_items,s['slates']):
            chosen = {i for i in slate['ix']}
            # Preserve original order of surviving bullets, append newly chosen
            # frozen source wording after them. Do not reorder A just to score.
            indices=[i for i in item['base'] if i in chosen]
            indices += [i for i in slate['ix'] if i not in item['base']]
            selected=[item['candidates'][i] for i in indices]
            chosen_text=[c['text'] for c in selected]
            selected_by_group.append({_key(t) for t in chosen_text})
            base_only |= any('Selected Base' in c['source_labels'] and
                             'Evidence Library' not in c['source_labels'] and
                             'Current final' not in c['source_labels'] for c in selected)
            rows.append({'project':item['project'],'before':list(item['actual']),
                'after':chosen_text,'sources':[list(c['source_labels']) for c in selected],
                'supported_jd_ids':[list(c['saved_jd_ids']) for c in selected],
                'before_count':len(item['actual']), 'after_count':len(chosen_text)})
        selected_comp=deepcopy(comp)
        for group, selected in zip(selected_comp['projects'],selected_by_group):
            for bullet in group.get('candidates') or []:
                bullet['selected_for_proposed_b']=_key(bullet['text']) in selected
        gained=sorted(set(s['ids'])-baseline_ids)
        lost=sorted(baseline_ids-set(s['ids']))
        return {'version':VERSION,'status':'candidate','changed':True,
            'reason':'Source-grounded JD-relevance-first trial; native one-page and actual-DOCX scoring decide.',
            'projects':rows, 'project_set_unchanged':True,'variable_bullet_counts':True,
            'baseline_points':_points(baseline_ids,weights),
            'proposed_points':_points(set(s['ids']),weights),
            'baseline_words':baseline_words,'proposed_words':s['words'],
            'baseline_bullet_count':baseline_bullets,'proposed_bullet_count':s['count'],
            'baseline_jd_ids':sorted(baseline_ids),'proposed_jd_ids':sorted(s['ids']),
            'protected_baseline_jd_ids':sorted(required),
            'gained_jd_ids':gained,'lost_jd_ids':lost,'requires_base_review':base_only,
            'source_comparison':selected_comp,
            'relevance_diagnostics':{
                'baseline_advisory_relevance':baseline_quality,
                'candidate_advisory_relevance':value(s),
                'baseline_distinct_jd_cues':sorted(baseline['terms']),
                'candidate_distinct_jd_cues':sorted(s['terms']),
                'new_jd_cues':sorted(s['terms']-baseline['terms']),
                'lost_jd_cues':sorted(baseline['terms']-s['terms']),
                'baseline_overlap_pairs':baseline['overlaps'],
                'candidate_overlap_pairs':s['overlaps'],
                'word_budget_proxy':budget,
                'meaning':'Grounded JD terms and saved links are ranking signals, NOT native Match points, factual proof or guaranteed semantic relevance.'},
            'selection_receipt':{'algorithm':'v35-bounded-jd-relevance-first-beam',
                'rank_in_shortlist':rank_index,'max_native_trials':max_trials,
                'maximum_two_bullet_count_delta':MAX_COUNT_DELTA,
                'maximum_changed_bullet_memberships':MAX_TOTAL_EDITS,
                'ranking_order':['distinct saved JD coverage',
                    'distinct JD terminology and link corroboration',
                    'repeated-evidence reduction','word usage',
                    'genuine-tie Library preference'],
                'actual_docx_comparison_required':True,
                'verified_fitting_explanation':False,
                'limits':'Bounded slate search, unchanged project set, existing factual wording only, up to three independent one-page native trials.'}}
    if not admissible:
        unchanged=deepcopy(comp)
        for group in unchanged['projects']:
            for bullet in group.get('candidates') or []:
                bullet['selected_for_proposed_b']=bool(bullet.get('in_original_a'))
        return {'version':VERSION,'status':'no_proxy_gain','changed':False,
            'reason':'No stronger guarded JD relevance/coverage slate found; current A remains authoritative.',
            'projects':[],'source_comparison':unchanged,
            'baseline_points':_points(baseline_ids,weights),
            'proposed_points':_points(baseline_ids,weights),
            'relevance_diagnostics':{'baseline_advisory_relevance':baseline_quality,
                'word_budget_proxy':budget,
                'meaning':'No improved bounded advisory candidate; not proof of global optimality.'}}
    variants=[create(s,i+1) for i,s in enumerate(admissible)]
    # The returned envelope must NOT be one of its own trial variants:
    # attaching candidate_variants to variants[0] creates a recursive dict
    # (and makes the runner reject the shortlist and JSON export crash).
    # Keep the independent trial dicts free of envelope-only metadata.
    first=deepcopy(variants[0])
    # Always use the native shortlisted-trial runner, including one candidate,
    # so the same verification receipts exist for every V3.5 result.
    first['candidate_variants']=variants
    first['shortlist_size']=len(variants)
    return first
