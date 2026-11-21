"""Phase 9F V3.6 transparent exact *proxy* optimization, guarded by native verification.

The integer program models saved JD links, distinct JD terminology, limited
repeated evidence, word budget and source provenance. It does NOT mathematically
model DOCX layout or the native scorer. The caller must independently render,
score, and check a comparable Selected Base before recommending a challenger.

If SciPy/HiGHS is unavailable or cannot prove an optimum, the existing bounded
V3.5 selector is retained as an explicitly uncertified fallback.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from itertools import combinations
import math

from tailoring.phase9f_jd_relevance_optimizer_v35 import (
    VERSION as V35_VERSION, build_jd_relevance_optimization, _terms,
    MAX_TRIALS, MAX_COUNT_DELTA, MAX_TOTAL_EDITS, MAX_WORD_SLACK, MAX_TOTAL_BULLETS,
)
from tailoring.phase9f_auto_optimize_v31 import build_flexible_optimization
from tailoring.phase9f_evidence_optimizer_v33 import _metadata, overlap
from tailoring.phase9f_joint_resume_optimizer_v2_6 import _key, _points

VERSION = 'phase9f-certified-proxy-v3.6-v1'
MODEL_REVIEW = 'An optimal MILP status certifies only the explicit proxy model, never human JD fit, native Job Match, or actual one-page feasibility.'
SOLVER_LIMIT_SECONDS = 12.0
MAX_CANDIDATES = 90
MAX_JD_TERMS = 140


def _fallback(audit:dict, projects:dict, reason:str, *, evaluator=None) -> dict:
    result = build_jd_relevance_optimization(audit, projects, evaluator=evaluator)
    result['mathematical_certificate'] = {
        'status':'not_proven', 'solver':'V3.5 bounded beam fallback',
        'reason':reason, 'claim':MODEL_REVIEW, 'native_verification_required':True,
        'optimality_gap':None,
    }
    return result


def _matrix_program(audit:dict, source:dict, projects:dict):
    """Build exact binary ILP variables and published coefficients and constraints."""
    groups = source.get('source_comparison',{}).get('projects')
    actual = audit.get('projects')
    if not isinstance(groups,list) or not isinstance(actual,list) or len(groups)!=len(actual):
        raise ValueError('Frozen source pool and fitted project audit differ.')
    weights, req_text, error = _metadata(projects,source['source_comparison'])
    if error or not weights:
        raise ValueError(error or 'Frozen JD weights unavailable.')
    bullets=[]; baseline_indices=[]; groups_of=[]; baseline_ids=set()
    for gi,(group,project) in enumerate(zip(groups,actual)):
        if _key(group.get('project'))!=_key(project.get('project')):
            raise ValueError('Project identities differ from fitted A.')
        cands=group.get('candidates')
        saved=project.get('final')
        if not isinstance(cands,list) or not cands or not isinstance(saved,list) or not saved:
            raise ValueError('Incomplete frozen Base/Library bullets.')
        owned=[]
        seen=set()
        actual_ids=[]
        for src in cands:
            if not isinstance(src,dict) or not isinstance(src.get('text'),str):
                raise ValueError('Invalid saved source bullet.')
            norm=_key(src['text'])
            if not norm or norm in seen: raise ValueError('Ambiguous duplicate wording in frozen pool.')
            seen.add(norm)
            ids=set(src.get('saved_jd_ids') or [])
            if not ids <= weights.keys(): raise ValueError('Unrecognized saved JD requirement identity.')
            ix=len(bullets)
            bullets.append({'index':ix,'project_index':gi,'project':group['project'],
                'text':src['text'],'source_labels':list(src.get('source_labels') or []),
                'ids':frozenset(ids),'words':int(src['word_count']),
                'terms':_terms(src['text']), 'original':False})
            owned.append(ix)
        map_ix={_key(bullets[i]['text']):i for i in owned}
        for row in saved:
            k=_key(row.get('text') if isinstance(row,dict) else None)
            if k not in map_ix: raise ValueError('Actual A contains wording missing from frozen pool.')
            idx=map_ix[k]
            if idx in actual_ids: raise ValueError('Duplicate wording in actual fitted project.')
            actual_ids.append(idx)
            bullets[idx]['original']=True
            baseline_ids.update(bullets[idx]['ids'])
            baseline_indices.append(idx)
        groups_of.append((group,project,owned,tuple(actual_ids)))
    if not baseline_ids or len(bullets)>MAX_CANDIDATES:
        raise ValueError('JD coverage or candidate pool outside exact-solver scope.')
    baselines=len(baseline_indices)
    word_base=sum(bullets[i]['words'] for i in baseline_indices)
    word_cap=min(1500,word_base+min(MAX_WORD_SLACK,max(8,round(word_base*.08))))
    req_ids=tuple(sorted(set().union(*(b['ids'] for b in bullets))))
    terms=tuple(sorted(set().union(*(_terms(req_text.get(r,'')) for r in req_ids))))
    if len(terms)>MAX_JD_TERMS:
        raise ValueError('JD terminology pool exceeds exact-solver scope.')
    pairs=[]
    for _,_,owned,_ in groups_of:
        for i,j in combinations(owned,2):
            if bullets[i]['ids'] & bullets[j]['ids'] and overlap(bullets[i]['text'],bullets[j]['text'])>=.46:
                pairs.append((i,j))
    return {'bullets':bullets,'groups':groups_of,'weights':weights,
        'req_ids':req_ids,'terms':terms,'pairs':pairs,
        'baseline_indices':frozenset(baseline_indices), 'baseline_ids':frozenset(baseline_ids),
        'baseline_count':baselines,'baseline_words':word_base,'max_words':word_cap}


def _solve(model:dict, no_good:list[tuple[int,...]], *, time_limit:float, forced:dict[int,int]|None=None):
    try:
        import numpy as np
        from scipy.optimize import milp, LinearConstraint, Bounds
        from scipy.sparse import lil_matrix
    except ImportError as exc:
        raise RuntimeError('Optional SciPy MILP dependency unavailable; exact optimization not performed.') from exc
    bullets=model['bullets']; n=len(bullets)
    req=model['req_ids']; nr=len(req)
    terms=model['terms']; nt=len(terms)
    pairs=model['pairs']; npairs=len(pairs)
    N=n+nr+nt+npairs
    Y=n; T=n+nr; P=T+nt
    rows=[]
    def add(coeff:dict[int,int],lo=-math.inf,hi=math.inf, label=''):
        rows.append((coeff,float(lo),float(hi),label))
    by_proj=model['groups']
    for group,_,indices,_ in by_proj:
        add({i:1 for i in indices},1,min(8,len(indices)),f'project:{group["project"]}')
    add({i:1 for i in range(n)},max(len(by_proj),model['baseline_count']-MAX_COUNT_DELTA),
        min(MAX_TOTAL_BULLETS,model['baseline_count']+MAX_COUNT_DELTA), 'total_bullets')
    add({i:bullets[i]['words'] for i in range(n)},0,model['max_words'],'word_proxy')
    # Number of changed memberships = selected_new + removed_old.
    original=model['baseline_indices']
    add({i: (-1 if i in original else 1) for i in range(n)},
        -math.inf, MAX_TOTAL_EDITS-len(original), 'changed_bullet_memberships')
    for r,rid in enumerate(req):
        supporters=[i for i,b in enumerate(bullets) if rid in b['ids']]
        # y <= sum(x), and y >= x_i for each supporter. Baseline links preserved.
        add({Y+r:1,**{i:-1 for i in supporters}},-math.inf,0,f'cover:{rid}')
        for i in supporters: add({Y+r:1,i:-1},0,math.inf, f'cover_consistency:{rid}')
        if rid in model['baseline_ids']:
            add({Y+r:1},1,1,f'baseline_coverage:{rid}')
    for t,term in enumerate(terms):
        supporters=[i for i,b in enumerate(bullets) if term in b['terms']]
        if supporters:
            add({T+t:1,**{i:-1 for i in supporters}},-math.inf,0,f'term:{term}')
            for i in supporters: add({T+t:1,i:-1},0,math.inf,f'term_consistency:{term}')
        else:
            add({T+t:1},0,0,f'term_absent:{term}')
    for p,(i,j) in enumerate(pairs):
        add({P+p:1,i:-1,j:-1},-1,math.inf,'overlap_lower')
        add({P+p:1,i:-1},-math.inf,0,'overlap_upper_i')
        add({P+p:1,j:-1},-math.inf,0,'overlap_upper_j')
    for index, include in (forced or {}).items():
        if (not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= n
                or include not in (0, 1)):
            raise ValueError('Invalid forced bullet membership constraint')
        add({index: 1}, include, include, 'forced_bullet_membership')
    for k,selection in enumerate(no_good):
        chosen=set(selection)
        # Sum_{selected}(1-x)+sum_{not selected}x >=1.
        add({i:(-1 if i in chosen else 1) for i in range(n)},
            1-len(chosen),math.inf,f'no_good_{k}')
    matrix=lil_matrix((len(rows),N),dtype=float)
    for r,(coeff,_,_,_) in enumerate(rows):
        for i,w in coeff.items():matrix[r,i]=w
    lower=np.array([r[1] for r in rows]);upper=np.array([r[2] for r in rows]);
    A=matrix.tocsr();limits=LinearConstraint(A,lower,upper)
    opts={'time_limit':float(time_limit),'mip_rel_gap':0.0, 'disp':False}
    # Explicit objective phases: best weighted distinct links -> distinct JD
    # terminology less overlap -> fewer edits -> fewer words. Each optimum is
    # fixed before optimizing the next phase. No unexplained weighted blend.
    phase_objectives=[]
    c0=np.zeros(N);c0[Y:Y+nr]=-np.array([round(model['weights'][rid]*1000) for rid in req])
    phase_objectives.append(('weighted_saved_JD_coverage',c0))
    c1=np.zeros(N);c1[T:T+nt]=-10
    c1[P:P+npairs]=18
    phase_objectives.append(('distinct_JD_terms_minus_overlap',c1))
    c2=np.zeros(N)
    for i,b in enumerate(bullets):c2[i]= -1 if b['original'] else 1
    phase_objectives.append(('membership_changes',c2))
    c3=np.zeros(N)
    for i,b in enumerate(bullets):c3[i]=b['words']
    phase_objectives.append(('source_bullet_words',c3))
    phase_results=[]
    for name,c in phase_objectives:
        answer=milp(c,integrality=np.ones(N),bounds=Bounds(np.zeros(N),np.ones(N)),
            constraints=limits, options=opts)
        if answer.status!=0 or answer.x is None:
            return {'status':'not_proven','reason':f'MILP {name}: {answer.message}',
                    'phase_receipts':phase_results,'solver_status':int(answer.status)}
        objective=float(np.dot(c,np.rint(answer.x)))
        phase_results.append({'priority':name,'minimization_objective':round(objective,6),
            'status':'optimal','best_bound_reported':getattr(answer,'mip_dual_bound',None),
            'node_count':getattr(answer,'mip_node_count',None)})
        # Exact integer objective on binaries; freeze the established optimum.
        A2=lil_matrix((1,N),dtype=float)
        for i,v in enumerate(c):
            if v: A2[0,i]=v
        from scipy.sparse import vstack
        A=vstack([A,A2.tocsr()]).tocsr()
        lower=np.append(lower,objective);upper=np.append(upper,objective)
        limits=LinearConstraint(A,lower,upper)
    selection=tuple(i for i in range(n) if answer.x[i]>.5)
    return {'status':'optimal_proxy','selected_indices':selection,'phase_receipts':phase_results,
            'solver':'SciPy MILP / HiGHS','optimality_gap':0.0,
            'model_variable_count':N,'model_constraint_count':len(rows)}


def _candidate(model:dict, source:dict, solution:dict, rank:int) -> dict:
    selected=set(solution['selected_indices']);groups=model['groups'];bullets=model['bullets']
    baseline=model['baseline_ids']; newids={rid for i in selected for rid in bullets[i]['ids']}
    rows=[];selected_comp=deepcopy(source['source_comparison'])
    for gi,(group,project,owned,base) in enumerate(groups):
        ordered=[i for i in base if i in selected]
        ordered += [i for i in owned if i in selected and i not in base]
        chosen=[bullets[i] for i in ordered]
        rows.append({'project':group['project'],
            'before':[str(row['text']) for row in project['final']],
            'after':[b['text'] for b in chosen],
            'sources':[list(b['source_labels']) for b in chosen],
            'supported_jd_ids':[sorted(b['ids']) for b in chosen],
            'before_count':len(base),'after_count':len(chosen)})
        for row in selected_comp['projects'][gi]['candidates']:
            row['selected_for_proposed_b']=any(_key(row['text'])==_key(b['text']) for b in chosen)
            row['v35_jd_term_hits']=sorted(_terms(row['text']) & set(model['terms']))
            row['v35_link_corroboration']=None  # Unmeasured; never invent a strength score.
    chosenwords=sum(bullets[i]['words'] for i in selected)
    allterms=set().union(*(bullets[i]['terms'] & set(model['terms']) for i in selected))
    ablations=[]
    for i in sorted(selected):
        remain=selected-{i}
        remaining_ids={rid for j in remain for rid in bullets[j]['ids']}
        remaining_terms=set().union(*(bullets[j]['terms'] & set(model['terms']) for j in remain))
        ablations.append({'project':bullets[i]['project'],'bullet':bullets[i]['text'],
            'source_labels':bullets[i]['source_labels'],
            'standalone_saved_JD_ids':sorted(bullets[i]['ids']),
            'unique_saved_JD_ids_lost_if_removed':sorted(newids-remaining_ids),
            'unique_JD_terms_lost_if_removed':sorted(allterms-remaining_terms),
            'words_freed_if_removed':bullets[i]['words'],
            'native_score_delta_if_removed':'not_measured',
            'interpretation':'Proxy leave-one-out is not evidence that this bullet has no résumé or narrative value.'})
    baseonly=any('Selected Base' in bullets[i]['source_labels'] and
                 'Evidence Library' not in bullets[i]['source_labels'] and
                 'Current final' not in bullets[i]['source_labels'] for i in selected)
    return {'version':V35_VERSION,'status':'candidate','changed':True,
        'reason':'Certified optimality within the explicit binary JD-coverage model; native document and Base-floor checks mandatory.',
        'projects':rows,'source_comparison':selected_comp,
        'project_set_unchanged':True,'variable_bullet_counts':True,
        'baseline_points':_points(set(baseline),model['weights']),
        'proposed_points':_points(set(newids),model['weights']),
        'baseline_words':model['baseline_words'],'proposed_words':chosenwords,
        'baseline_bullet_count':model['baseline_count'],'proposed_bullet_count':len(selected),
        'baseline_jd_ids':sorted(baseline),'proposed_jd_ids':sorted(newids),
        'protected_baseline_jd_ids':sorted(baseline),
        'gained_jd_ids':sorted(newids-baseline),'lost_jd_ids':sorted(baseline-newids),
        'requires_base_review':baseonly,
        'selection_receipt':{'algorithm':'v36-exact-lexicographic-MILP',
            'rank_in_shortlist':rank,'actual_docx_comparison_required':True,
            'verified_fitting_explanation':False,
            'limits':MODEL_REVIEW,
            'solver':solution['solver'],'status':solution['status'],
            'optimality_gap':solution['optimality_gap'],
            'phase_receipts':solution['phase_receipts'],
            'model_variable_count':solution['model_variable_count'],
            'model_constraint_count':solution['model_constraint_count'],
        },
        'mathematical_certificate':{'status':'optimal_proxy','solver':solution['solver'],
            'optimality_gap':0.0,'rank_in_shortlist':rank,
            'phase_receipts':solution['phase_receipts'],
            'model_variable_count':solution['model_variable_count'],
            'model_constraint_count':solution['model_constraint_count'],
            'constraints':{
                'candidate_pool':len(model['bullets']),
                'same_projects':len(model['groups']),
                'each_project_min_bullets':1,
                'each_project_max_bullets':8,
                'baseline_bullet_count':model['baseline_count'],
                'total_bullet_count_delta_limit':MAX_COUNT_DELTA,
                'max_changed_memberships':MAX_TOTAL_EDITS,
                'original_project_bullet_words':model['baseline_words'],
                'word_proxy_upper_bound':model['max_words'],
                'baseline_JD_identities_must_remain':sorted(model['baseline_ids']),
                'actual_rendered_page_limit':'one page, enforced by separate renderer',
                'native_score_floor':'requires independently comparable Selected Base',
            },
            'objectives_in_priority_order':[
                'maximize weighted distinct saved JD links (integer x1000)',
                'maximize 10 per distinct grounded JD term minus 18 per overlapping same-project evidence pair',
                'minimize changes to existing fitted bullet membership',
                'minimize source bullet words',
            ],
            'claim':MODEL_REVIEW,'native_verification_required':True},
        'relevance_diagnostics':{
            'selected_proxy_JD_ids':sorted(newids),
            'selected_JD_term_hits':sorted(set().union(*(bullets[i]['terms'] for i in selected)) & set(model['terms'])),
            'zero_saved_JD_id_bullets':[bullets[i]['text'] for i in sorted(selected) if not bullets[i]['ids']],
            'ablation_preview':ablations,
            'meaning':'No saved JD links is NOT zero narrative value; native drop-one tests needed for causal score attribution.',
        }}


def build_certified_optimization(audit:dict,projects:dict,*,evaluator=None,max_trials:int=MAX_TRIALS)->dict:
    """Exact lexicographic surrogate, fallback to bounded V3.5 when uncertified.

    Up to max_trials distinct exact-optimal-ranked solutions are submitted to
    the unchanged V3.5 native A/B runner. No proxy-only promotion.
    """
    if isinstance(max_trials,bool) or not isinstance(max_trials,int) or not 1<=max_trials<=MAX_TRIALS:
        return {'version':V35_VERSION,'status':'withheld','reason':'Invalid trial count.',
            'projects':[],'mathematical_certificate':{'status':'not_proven','claim':MODEL_REVIEW}}
    frozen=build_flexible_optimization(audit,projects,evaluator=evaluator)
    if frozen.get('status')=='withheld' or not isinstance(frozen.get('source_comparison'),dict):
        return _fallback(audit,projects,'Frozen source pool is unavailable.',evaluator=evaluator)
    try:
        model=_matrix_program(audit,frozen,projects)
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        return _fallback(audit,projects,'Exact model not applicable: '+str(exc),evaluator=evaluator)
    selections=[];certs=[];no_good=[]
    base=model['baseline_indices']
    for i in range(max_trials):
        try:
            solved=_solve(model,no_good,time_limit=SOLVER_LIMIT_SECONDS)
        except (RuntimeError,ValueError,OverflowError) as exc:
            return _fallback(audit,projects,'Exact solver unavailable: '+str(exc),evaluator=evaluator)
        if solved.get('status')!='optimal_proxy':
            if i==0:return _fallback(audit,projects,'Exact solver did not prove optimality: '+str(solved.get('reason')),evaluator=evaluator)
            break
        selected=solved['selected_indices']
        no_good.append(selected)
        if set(selected)==base:continue  # Baseline can be optimal; no candidate claimed.
        selections.append(_candidate(model,frozen,solved,len(selections)+1))
        certs.append(solved)
    if not selections:
        out=deepcopy(frozen)
        out.update({'version':V35_VERSION,'status':'no_proxy_gain','changed':False,
            'reason':'The fitted starting slate is the best solved proxy candidate or no alternative is certified.',
            'projects':[],
            'mathematical_certificate':{'status':'optimal_proxy','claim':MODEL_REVIEW,
                'solver':'SciPy MILP / HiGHS','optimality_gap':0.0,
                'native_verification_required':True}})
        return out
    first=deepcopy(selections[0])
    first['candidate_variants']=selections
    first['shortlist_size']=len(selections)
    first['mathematical_certificate']['shortlist_size']=len(selections)
    return first


def selected_base_floor_gate(result:dict, starting:dict|None)->dict:
    """No recommendation without comparable Selected Base vs actual A.

    Deliberately conservative: if A itself regressed from the actual Selected
    Base, B>A alone does not prove B>=Base at each Required/Core requirement.
    Keep all A/B scores and diagnostics intact, but suppress a recommendation.
    """
    out=dict(result)
    if out.get('winner')!='optimized_candidate':return out
    if not isinstance(starting,dict) or starting.get('status')!='verified':
        verdict='Selected Base document comparison is unavailable.'
    elif (str(result.get('a_docx_sha256') or '') !=
          str(starting.get('a_docx_sha256') or '') or
          not result.get('a_docx_sha256')):
        verdict='Selected Base proof applies to a different or unidentifiable fitted DOCX.'
    elif (result.get('scoring_version') != starting.get('scoring_version') or
          not result.get('scoring_version') or
          result.get('a_score') != starting.get('a_score')):
        verdict='Selected Base proof uses a different score, scorer or authority.'
    elif starting.get('selected_base_comparison_status') not in ('maintained','improved'):
        verdict='Actual fitted A is not verified non-regressed against comparable Selected Base.'
    elif starting.get('selected_base_required_core_losses'):
        verdict='A loses protected Required/Core evidence relative to Selected Base.'
    else:
        out['base_floor_verdict']='passed_by_transitivity'
        return out
    out['base_floor_verdict']='not_proven'
    out['base_floor_reason']=verdict
    out['verified_better_than_a_only']=True
    out['winner']='existing_final'
    out['reason']=str(out.get('reason') or '')+' B is not recommended: '+verdict
    return out


def compare_forced_bullet(audit:dict, projects:dict, saved_proposal:dict, *,
                          project:str, bullet:str, time_limit:float=6.0)->dict:
    """On-demand *proxy-only* head-to-head: force candidate in vs out.

    Never says one bullet improved native Job Match, never writes sources,
    never changes which A/B DOCX has already been verified. Exact frozen
    candidate identities must match the saved proposal before optimization.
    """
    from tailoring.phase9f_auto_optimize_v31 import build_flexible_optimization
    from tailoring.phase9f_joint_resume_optimizer_v2_6 import _key
    if not isinstance(saved_proposal,dict) or not isinstance(saved_proposal.get('source_comparison'),dict):
        return {'status':'unavailable','reason':'Saved proposal/source ownership unavailable'}
    frozen=build_flexible_optimization(audit,projects)
    if frozen.get('status')=='withheld':
        return {'status':'unavailable','reason':'Current frozen source pool unavailable'}
    def canonical(slate):
        groups=(slate.get('source_comparison') or {}).get('projects') or []
        return sorted((str(g.get('project') or '').casefold(),_key(c.get('text')),
                       tuple(sorted(c.get('saved_jd_ids') or [])),
                       tuple(sorted(c.get('source_labels') or [])))
                      for g in groups for c in g.get('candidates') or [])
    if canonical(frozen)!=canonical(saved_proposal):
        return {'status':'withheld','reason':'Current source/requirement pool differs from saved optimizer receipt'}
    try:
        model=_matrix_program(audit,frozen,projects)
        matches=[b for b in model['bullets'] if _key(b['project'])==_key(project) and _key(b['text'])==_key(bullet)]
        if len(matches)!=1:
            return {'status':'withheld','reason':'Bullet wording is not unique in saved source'}
        index=matches[0]['index']
        outcomes={}
        for name,val in [('force_in',1),('force_out',0)]:
            solved=_solve(model,[],time_limit=time_limit,forced={index:val})
            if solved.get('status')!='optimal_proxy':
                outcomes[name]={'status':'not_proven','reason':solved.get('reason','Solver failed or infeasible')}
            else:
                choices=set(solved['selected_indices'])
                outcomes[name]={'status':'optimal_proxy',
                    'objectives':[{k:v for k,v in stage.items() if k in ('priority','minimization_objective','status')}
                                  for stage in solved['phase_receipts']],
                    'selected_bullets':len(choices),
                    'selected_words':sum(model['bullets'][i]['words'] for i in choices),
                    'selected_requirement_ids':sorted({rid for i in choices for rid in model['bullets'][i]['ids']}),
                    'alternative_wordings':[(model['bullets'][i]['project'],model['bullets'][i]['text']) for i in sorted(choices)],
                    'optimality_gap':solved['optimality_gap']}
        interpretation='not_proven'
        a,b=outcomes['force_in'],outcomes['force_out']
        if a.get('status')=='optimal_proxy' and b.get('status')=='optimal_proxy':
            aa=[p['minimization_objective'] for p in a['objectives']]
            bb=[p['minimization_objective'] for p in b['objectives']]
            interpretation='force_in_proxy_preferred' if tuple(aa)<tuple(bb) else 'force_out_proxy_preferred' if tuple(aa)>tuple(bb) else 'proxy_tie'
        return {'status':'calculated','project':project,'bullet':bullet,
                'comparison':interpretation,'force_in':a,'force_out':b,
                'claim':'Proxy-only exact constrained solves; native score and actual one-page feasibility NOT measured.',
                'changes_saved_selection':False}
    except (ValueError,KeyError,TypeError,RuntimeError,OverflowError) as exc:
        return {'status':'withheld','reason':str(exc),
                'claim':'No causal bullet preference claimed without two proven forced solves.'}
