"""Opt-in V3.3 evidence-aware challenger over exact, immutable source bullets.

V3.1's guarded evaluator supplies source identities and JD links. V3.3 adds
explainable marginal coverage, potential-duplicate diagnostics, and a bounded
single-edit quality search when V3.1 finds no *new* JD requirement. Nothing in
this module claims to verify factual semantics or to improve native Job Match.
A separate independently rendered DOCX/PDF and native A/B comparison are still
mandatory before B can be recommended. Every proposed edit preserves existing
JD identities; no source content is rewritten or moved between projects.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Callable

from tailoring.phase9f_auto_optimize_v31 import build_flexible_optimization
from tailoring.phase9f_joint_resume_optimizer_v2_6 import _key, _points, _rank_weights, _get_rank

VERSION = 'phase9f-evidence-aware-v3.3-v1'
OVERLAP_THRESHOLD = 0.46
_TOKEN = re.compile(r"[a-z0-9+#.]+")
_STOP = {'a','an','the','and','or','to','for','in','of','with','on','by','from','through',
         'as','at','into','that','while','using','used','use','implemented','built','developed',
         'supported','support','improved','more','one','other','will','be'}


def tokens(value: str) -> set[str]:
    return {x for x in _TOKEN.findall(str(value or '').casefold()) if len(x) >= 3 and x not in _STOP}


def overlap(a: str, b: str) -> float:
    x, y = tokens(a), tokens(b)
    return round(len(x & y) / len(x | y), 4) if x and y else 0.0


def _metadata(projects: dict, comparison: dict) -> tuple[dict, dict, str]:
    weights, labels = {}, {}
    for group in comparison.get('projects') or []:
        rank = _get_rank(projects, str(group.get('project') or ''))
        if rank is None: return {}, {}, 'Missing saved requirement ranking.'
        local, error = _rank_weights(rank)
        if error: return {}, {}, error
        for rid, weight in local.items():
            weights[rid] = max(weights.get(rid, 0.0), weight)
        for req in rank.get('requirement_matches') or []:
            if not isinstance(req, dict): return {}, {}, 'Invalid saved JD requirement.'
            rid = str(req.get('requirement_id') or '')
            if rid and rid not in labels:
                labels[rid] = str(req.get('requirement_text') or req.get('text') or '')
    return weights, labels, ''


def _current(comparison: dict, audit: dict) -> list[list[dict]] | None:
    """Preserve the *actual DOCX* section and bullet order, not source-pool order."""
    sections = audit.get('projects') or []
    groups = comparison.get('projects') or []
    if len(groups) != len(sections): return None
    out=[]
    for group, section in zip(groups, sections):
        if _key(group.get('project')) != _key(section.get('project')): return None
        found={_key(x['text']):x for x in group.get('candidates') or [] if isinstance(x,dict)}
        actual=[]
        for bullet in section.get('final') or []:
            if not isinstance(bullet,dict): return None
            row=found.get(_key(bullet.get('text')))
            if row is None or not row.get('in_original_a'): return None
            actual.append(row)
        if not 1<=len(actual)<=8 or len({_key(x['text']) for x in actual})!=len(actual):return None
        out.append(actual)
    return out


def _ids(rows: list[list[dict]]) -> set[str]:
    return {r for group in rows for bullet in group for r in bullet.get('saved_jd_ids') or []}


def _redundant_pairs(rows: list[list[dict]], *, labels: list[str]) -> list[dict]:
    pairs = []
    for name, group in zip(labels, rows):
        for i, a in enumerate(group):
            for b in group[i+1:]:
                common = sorted(set(a.get('saved_jd_ids') or []) & set(b.get('saved_jd_ids') or []))
                similarity = overlap(a['text'], b['text'])
                if common and similarity >= OVERLAP_THRESHOLD:
                    pairs.append({'project': name, 'first': a['text'], 'second': b['text'],
                                  'shared_jd_ids': common, 'token_jaccard': similarity,
                                  'assessment': 'Potential repeated evidence; human review recommended, not semantic proof.'})
    return pairs


def _explain(comparison: dict, projects: dict, chosen: list[list[dict]]) -> dict:
    weights, jd_text, error = _metadata(projects, comparison)
    if error: return {'status':'unavailable','reason':error}
    names = [str(x.get('project') or '') for x in comparison.get('projects') or []]
    flat = [x for g in chosen for x in g]
    global_ids = _ids(chosen)
    support_count = {rid:sum(rid in (x.get('saved_jd_ids') or []) for x in flat) for rid in global_ids}
    bullets, warnings = [], []
    for project, group in zip(names, chosen):
        for item in group:
            linked = set(item.get('saved_jd_ids') or [])
            exclusive = sorted(rid for rid in linked if support_count.get(rid,0)==1)
            weak_links = []
            for rid in sorted(linked):
                text = jd_text.get(rid) or ''
                # This heuristic is explicitly diagnostic. Indirect legitimate evidence
                # may have no lexical overlap, and matched words are not factual proof.
                if text and len(tokens(text) & tokens(item['text'])) < 2:
                    weak_links.append(rid)
                    warnings.append({'project':project,'bullet':item['text'], 'jd_id':rid,
                      'jd_requirement':text,'reason':'Low lexical corroboration; review saved semantic JD link. No score or credit automatically changed.'})
            bullets.append({'project':project,'text':item['text'],
               'source_labels':list(item.get('source_labels') or []),
               'saved_jd_ids':sorted(linked),
               'standalone_proxy_points':_points(linked, weights),
               'marginal_distinct_jd_points':_points(set(exclusive), weights),
               'exclusive_jd_ids_in_slate':exclusive,
               'shared_jd_ids_in_slate':sorted(linked-set(exclusive)),
               'word_count':item.get('word_count'),
               'low_lexical_corroboration_ids':weak_links})
    return {'status':'available', 'selected_distinct_proxy_points':_points(global_ids, weights),
            'selected_jd_ids':sorted(global_ids), 'selected_bullets':bullets,
            'potential_redundant_pairs':_redundant_pairs(chosen, labels=names),
            'advisory_jd_link_review':warnings,
            'meaning':'Marginal = leave-one-bullet-out distinct JD link contribution. Zero does not imply no narrative value.',
            'limits':'JD links come from saved matching; textual overlap is not semantic duplication; low lexical similarity is not disproof; no causal Base/Library winner claimed.'}


def _base_or_library(bullet: dict) -> str:
    s = set(bullet.get('source_labels') or [])
    if 'Selected Base' in s and 'Evidence Library' in s: return 'both'
    if 'Evidence Library' in s: return 'library'
    if 'Selected Base' in s: return 'base'
    return 'current_only'


def _rebuild_rows(old: list[list[dict]], new: list[list[dict]], comparison: dict) -> list[dict]:
    rows=[]
    for group, before, after in zip(comparison['projects'], old, new):
        rows.append({'project':group['project'],
            'before':[x['text'] for x in before], 'after':[x['text'] for x in after],
            'sources':[list(x.get('source_labels') or []) for x in after],
            'supported_jd_ids':[list(x.get('saved_jd_ids') or []) for x in after],
            'before_count':len(before),'after_count':len(after)})
    return rows


def build_evidence_aware_optimization(audit: dict, projects: dict, *,
            evaluator: Callable | None = None, library_tie_preference: bool = False) -> dict:
    """Use V3.1 whole-resume search, adding one guarded evidence-aware edit.

    A V3.1 proxy-coverage gain always wins precedence. Otherwise test bounded
    same-JD swaps and exact-JD-preserving redundant-bullet removal, choosing a
    quality challenger only when the verified A/B gate can evaluate it.
    """
    initial = build_flexible_optimization(audit, projects, evaluator=evaluator)
    if initial.get('status') == 'withheld':
        return {**initial, 'evidence_policy_version':VERSION}
    proposal = deepcopy(initial)
    comparison = proposal.get('source_comparison')
    if not isinstance(comparison, dict) or not isinstance(comparison.get('projects'), list):
        return {**proposal,'evidence_policy_version':VERSION}
    old = _current(comparison,audit)
    if old is None:
        return {**proposal,'evidence_policy_version':VERSION,
                'evidence_diagnostics':{'status':'unavailable','reason':'DOCX/source bullet order or membership mismatch.'}}
    diagnostics = _explain(comparison, projects, old)
    if diagnostics.get('status') != 'available':
        return {**proposal,'evidence_policy_version':VERSION,
                'evidence_diagnostics':diagnostics}
    proposal.update({'evidence_policy_version':VERSION,'evidence_diagnostics':diagnostics,
                     'library_tie_preference_used':bool(library_tie_preference)})
    proposal.setdefault('baseline_bullet_count',sum(map(len,old)))
    proposal.setdefault('baseline_words',sum(int(x.get('word_count') or 0) for g in old for x in g))
    proposal.setdefault('proposed_bullet_count',proposal['baseline_bullet_count'])
    proposal.setdefault('proposed_words',proposal['baseline_words'])
    proposal.setdefault('gained_jd_ids',[])
    proposal.setdefault('lost_jd_ids',[])
    if proposal.get('status') == 'candidate':
        # Preserve V3.1's protected JD gain; add a diagnostic view of its
        # selected slate, without mutating its ranking or winner policy.
        proposed = [[c for c in group.get('candidates') or [] if c.get('selected_for_proposed_b')]
                    for group in comparison['projects']]
        proposal['evidence_diagnostics_proposed']=_explain(comparison,projects,proposed)
        # New distinct JD coverage is the V3.1 objective. Never weaken this
        # already guarded candidate just to satisfy a redundant-wording hint.
        return proposal

    names = [str(x.get('project') or '') for x in comparison['projects']]
    original_ids = _ids(old)
    orig_words = sum(int(x.get('word_count') or 0) for g in old for x in g)
    original_pairs = _redundant_pairs(old, labels=names)
    choices=[]
    for pidx, group in enumerate(comparison['projects']):
        previous = old[pidx]
        unused=[c for c in group.get('candidates') or [] if not c.get('in_original_a')]
        for i, removed in enumerate(previous):
            # A deletion must remove a *recorded* overlapping pair, preserve
            # all JD link identities, and leave at least one bullet in project.
            if len(previous)>1 and any(pair['project']==names[pidx] and
                   removed['text'] in (pair['first'],pair['second']) for pair in original_pairs):
                new=deepcopy(old);new[pidx]=previous[:i]+previous[i+1:]
                if _ids(new)==original_ids:
                    newpairs=_redundant_pairs(new, labels=names)
                    if len(newpairs)<len(original_pairs):
                        choices.append(('redundancy_reduction',new, len(original_pairs)-len(newpairs), 0, 0))
            for candidate in unused:
                if set(candidate.get('saved_jd_ids') or []) != set(removed.get('saved_jd_ids') or []):
                    continue
                if int(candidate.get('word_count') or 0)>int(removed.get('word_count') or 0):
                    continue
                new=deepcopy(old);new[pidx]=previous[:i]+[candidate]+previous[i+1:]
                if _ids(new)!=original_ids:continue
                newpairs=_redundant_pairs(new, labels=names)
                reduction = len(original_pairs)-len(newpairs)
                pref=(library_tie_preference and _base_or_library(candidate)=='library'
                      and _base_or_library(removed)=='base'
                      and int(candidate.get('word_count') or 0)==int(removed.get('word_count') or 0))
                if reduction>0:
                    choices.append(('redundancy_reduction',new,reduction,0,0))
                elif pref and reduction==0:
                    choices.append(('library_genuine_proxy_tie',new,0,1,0))
    if not choices:
        proposal['evidence_selection_result']='No demonstrable redundancy reduction or configured exact-support source tie found.'
        return proposal
    # Redundancy improvement precedes optional wording preference; edits are
    # deterministic. Search is deliberately bounded to one edit from actual A.
    choices.sort(key=lambda c: (-c[2],-c[3],sum(int(x.get('word_count') or 0) for g in c[1] for x in g),
                               tuple(_key(x['text']) for g in c[1] for x in g)))
    reason, chosen, eliminated, preferred,_ = choices[0]
    if chosen==old:return proposal
    chosen_count=sum(map(len, chosen))
    chosen_words=sum(int(x.get('word_count') or 0) for g in chosen for x in g)
    if chosen_words>orig_words or chosen_count>48 or any(not 1<=len(g)<=8 for g in chosen):return proposal
    weights,_,error=_metadata(projects, comparison)
    if error:return proposal
    changes=[]
    for project,before,after in zip(names,old,chosen):
        oldmap={_key(x['text']):x for x in before}
        newmap={_key(x['text']):x for x in after}
        removed=[x for k,x in oldmap.items() if k not in newmap]
        added=[x for k,x in newmap.items() if k not in oldmap]
        if removed or added:
            changes.append({'project':project,'reason':reason,
                'removed':[{'text':x['text'],'source_labels':x.get('source_labels'),
                            'saved_jd_ids':x.get('saved_jd_ids'),'words':x.get('word_count')} for x in removed],
                'added':[{'text':x['text'],'source_labels':x.get('source_labels'),
                          'saved_jd_ids':x.get('saved_jd_ids'),'words':x.get('word_count')} for x in added],
                'meaning':('Candidate for actual-document testing, not proof of semantic redundancy, '
                           'individual Base/Library superiority, or Job Match improvement.')})
    result = {**proposal, 'version':VERSION, 'status':'candidate', 'changed':True,
              'reason':('A single-edit redundancy-aware or explicitly opted-in Library wording trial; '
                        'saved JD coverage is unchanged. Actual DOCX scoring must decide.'),
              'projects':_rebuild_rows(old,chosen,comparison),
              'project_set_unchanged':True,'variable_bullet_counts':True,
              'baseline_points':_points(original_ids, weights),
              'proposed_points':_points(_ids(chosen),weights),
              'baseline_words':orig_words,'proposed_words':chosen_words,
              'baseline_bullet_count':sum(map(len,old)),
              'proposed_bullet_count':chosen_count,
              'baseline_jd_ids':sorted(original_ids),'proposed_jd_ids':sorted(_ids(chosen)),
              'protected_baseline_jd_ids':sorted(original_ids),
              'gained_jd_ids':[],'lost_jd_ids':[],
              'requires_base_review':any(_base_or_library(x)=='base' and
                         not x.get('in_original_a') for g in chosen for x in g),
              'evidence_selection_result':reason,
              'recorded_edits':changes,
              'selection_receipt':{
                 'algorithm':'single-edit-source-grounded-v33-after-v31',
                 'redundant_pairs_removed':eliminated,'library_tie_preference_applied':bool(preferred),
                 'actual_docx_comparison_required':True,
                 'verified_fitting_explanation':False,
                 'limits':'At most one substitution/deletion; all existing saved JD links preserved; empirical native score needed.'}}
    # Source table now reflects the actually proposed V3.3 slate, not the
    # stale V3.1 slate. Keep original wording provenance for all candidates.
    actual_keys={names[i]:{_key(x['text']) for x in g} for i,g in enumerate(chosen)}
    for group in result['source_comparison']['projects']:
        for candidate in group.get('candidates') or []:
            candidate['selected_for_proposed_b']=_key(candidate['text']) in actual_keys[group['project']]
    result['evidence_diagnostics_proposed']=_explain(comparison,projects,chosen)
    return result
