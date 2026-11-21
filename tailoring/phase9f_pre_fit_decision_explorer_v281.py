"""Read-only, interactive JD-first explorer for saved PRE-FITTING bullets.

Pre-fit allocation and exact generated draft are not final-DOCX outcomes.
Source ownership is validated through the existing frozen source builder. Labels
for match strength only come from saved per-bullet receipts; literal JD-token
highlights are explicitly lexical, never evidence upgrades.
"""
from __future__ import annotations

import html
from typing import Any


def build_pre_fit_decisions(projects: Any, candidates: Any, stable_analysis: Any = None) -> dict[str, Any]:
    def hold(reason): return {'status':'withheld','reason':reason,'projects':[],'requirements':[]}
    if not isinstance(projects,dict):return hold('Saved generated Projects unavailable.')
    from tailoring.phase9f_project_bullet_sources_v2_3 import build_project_bullet_source_view
    from tailoring.phase9f_decision_explorer_v28 import _requirements, key, clean
    view=build_project_bullet_source_view(projects,candidates)
    source=view.get('projects') or []
    if not source:return hold(view.get('notice') or 'Frozen source comparison unavailable.')
    reqs,why=_requirements(projects)
    if why:return hold(why)
    if isinstance(stable_analysis,dict) and isinstance(stable_analysis.get('canonical_requirements'),list):
        entire={}
        for item in stable_analysis['canonical_requirements']:
            if not isinstance(item,dict):return hold('Malformed canonical JD source.')
            rid=clean(item.get('requirement_id'));text=clean(item.get('text'))
            importance=clean(item.get('importance')).lower()
            if not rid or not text:return hold('Canonical JD requirement identity missing.')
            if rid in entire:return hold('Duplicate canonical JD requirement identity.')
            entire[rid]={'id':rid,'text':text,'importance':importance}
        if not entire:return hold('No canonical JD requirements.')
        if any(r['id'] not in entire or r['text']!=entire[r['id']]['text'] or
               r['importance']!=entire[r['id']]['importance'] for r in reqs):
            return hold('Saved project JD identities conflict with frozen canonical JD source.')
        reqs=sorted(entire.values(),key=lambda x:x['text'].casefold())
    req_ids={x['id'] for x in reqs}
    out=[]
    for src in source:
        rows={}
        for owner,field,text_field in [('base','base_bullets','Base Resume bullet'),('library','library_bullets','Evidence Library bullet')]:
            for r in src[field]:
                value=clean(r.get(text_field));ident=key(value)
                if not ident:return hold('Empty frozen bullet.')
                rec=rows.setdefault(ident,{'text':value,'sources':[],'allocated':None,
                                    'draft_exact':False,'reason':'','links':{},'decision_context':None,'raw_receipt':None})
                if owner not in rec['sources']:rec['sources'].append(owner)
        receipts=src.get('bullet_decision_receipts') or []
        if not isinstance(receipts,list):return hold('Invalid saved per-bullet decisions.')
        observed=set()
        for r in receipts:
            if not isinstance(r,dict) or not isinstance(r.get('bullet'),str):return hold('Malformed allocation receipt.')
            ident=key(r['bullet'])
            if ident in observed or ident not in rows:return hold('Duplicate or foreign allocation receipt.')
            observed.add(ident)
            if set(r.get('sources') or [])!=set(rows[ident]['sources']):return hold('Allocation receipt ownership conflict.')
            strong=r.get('supported_requirement_ids') or []
            direct=r.get('direct_requirement_ids') or []
            weak=r.get('weak_requirement_ids') or []
            if not all(isinstance(group,list) and all(isinstance(x,str) and x in req_ids for x in group) for group in [strong,direct,weak]):
                return hold('Foreign or malformed JD requirement reference.')
            if not set(direct)<=set(strong):return hold('Direct JD evidence is missing from saved strong links.')
            rec=rows[ident]
            rec['allocated']=r.get('selected') if isinstance(r.get('selected'),bool) else None
            rec['reason']=clean(r.get('reason'))
            rec['links']={rid: ('direct' if rid in direct else 'transferable' if rid in strong else 'weak') for rid in set(strong+weak)}
            rec['decision_context']=r.get('decision_context') if isinstance(r.get('decision_context'),dict) else None
            rec['raw_receipt']=dict(r)
        draft_ids={key(r.get('Generated draft bullet')) for r in src['draft_bullets']}
        for ident,rec in rows.items():rec['draft_exact']=ident in draft_ids
        out.append({'project':src['project'],'rank':src['rank'],'project_rank_score':src.get('project_rank_score'),
                    'bullets':list(rows.values()),'draft_count':src['draft_count'],
                    'has_receipts':bool(receipts),'policy':src.get('bullet_source_policy_version')})
    return {'status':'ok','projects':out,'requirements':reqs,'notice':view.get('notice',''),
            'mode':((projects.get('deterministic_rule_debug') or {}).get('bullet_allocation') or {}).get('allocation_mode') or 'not_recorded'}


def _color_status(match: str) -> tuple[str,str]:
    return {
        'direct':('#17533d','#86efac'),
        'transferable':('#17446b','#93c5fd'),
        'weak':('#523d16','#fcd34d'),
        'no_saved_bullet_link':('#35383f','#d1d5db'),
    }.get(match,('#35383f','#d1d5db'))


def _badge(text: str, *, kind: str='no_saved_bullet_link') -> str:
    bg,fg=_color_status(kind)
    return (f'<span style="display:inline-block;background:{bg};color:{fg};border-radius:7px;'
            f'padding:2px 7px;font-size:0.8rem;font-weight:600;margin-right:5px">{html.escape(text)}</span>')


def _highlight(text: str, words: set[str]) -> str:
    from tailoring.phase9f_decision_explorer_v28 import TOKENS
    parts=[];pos=0
    for m in TOKENS.finditer(text):
        parts.append(html.escape(text[pos:m.start()]))
        word=html.escape(m.group())
        if m.group().casefold() in words:
            word='<mark style="background:#234c67;color:#c4ecff;padding:0 2px;border-radius:2px">'+word+'</mark>'
        parts.append(word);pos=m.end()
    parts.append(html.escape(text[pos:]))
    return ''.join(parts)


def render_pre_fit_decision_explorer(st: Any, *, projects: Any, candidates: Any, application_id: int, stable_analysis: Any = None) -> bool:
    from tailoring.phase9f_decision_explorer_v28 import terms, STRENGTH
    view=build_pre_fit_decisions(projects,candidates,stable_analysis)
    if view['status']!='ok':
        st.info('Pre-fit Decision Explorer withheld: '+view['reason']);return False
    st.markdown('### Decision Explorer — before fitting')
    st.caption('Click a JD requirement to compare **actual saved** Base/Library bullet evidence. '
               'Blue highlights are exact JD-word overlap, NOT proof of Direct/Transferable evidence. '
               '**Allocated is not Retained in final DOCX.**')
    st.caption(view['notice'])
    titles=[p['project'] for p in view['projects']]
    chosen=st.selectbox('Project to inspect',list(range(len(titles))),format_func=lambda i:titles[i],
                        key=f'phase9f_prefit_explorer_project_{application_id}')
    proj=view['projects'][chosen]
    st.caption(f"Saved project rank: {proj['rank'] or 'not recorded'} · Generated draft bullets: {proj['draft_count']} · Allocation mode: {view['mode']}")
    reqs=view['requirements']
    selected_key=f'phase9f_prefit_explorer_active_req_{application_id}_{chosen}'
    if st.session_state.get(selected_key) not in {r['id'] for r in reqs}:
        st.session_state[selected_key]=reqs[0]['id']
    st.markdown('**JD requirement coverage — click a row**')
    st.caption('The counts are saved per-bullet links, not complete whole-résumé requirement coverage.')
    for r in reqs:
        rid=r['id'];active=st.session_state[selected_key]==rid
        linked=[b for b in proj['bullets'] if rid in b['links']]
        nbase=sum('base' in b['sources'] for b in linked)
        nlib=sum('library' in b['sources'] for b in linked)
        cols=st.columns([8,2,2])
        with cols[0]:
            label=('● ' if active else '')+r['importance'].title()+' · '+r['text']
            if st.button(label,key=f'phase9f_prefit_req_{application_id}_{chosen}_{rid}',width='stretch'):
                st.session_state[selected_key]=rid
        with cols[1]:st.markdown(_badge(f'Base {nbase}',kind='transferable') ,unsafe_allow_html=True)
        with cols[2]:st.markdown(_badge(f'Library {nlib}',kind='direct'),unsafe_allow_html=True)
    jd=next(r for r in reqs if r['id']==st.session_state[selected_key]);jd_words=terms(jd['text'])
    st.markdown('**Selected JD requirement:** '+html.escape(jd['text']))
    st.caption('JD terms: '+(', '.join(sorted(jd_words)) or 'none'))
    columns=st.columns(2)
    open_key=f'phase9f_prefit_open_bullet_{application_id}_{chosen}_{jd["id"]}'
    for owner,column,title in [('base',columns[0],'Selected Base résumé'),('library',columns[1],'Evidence Library')]:
        with column:
            st.markdown('#### '+title)
            rows=[b for b in proj['bullets'] if owner in b['sources']]
            rows.sort(key=lambda b:(-STRENGTH.get(b['links'].get(jd['id'],'no_saved_bullet_link'),0),
                                    -len(terms(b['text']) & jd_words),b['text'].casefold()))
            show=st.checkbox('Show all '+title+' bullets',value=False,
                             key=f'phase9f_prefit_all_{owner}_{application_id}_{chosen}_{jd["id"]}') if len(rows)>3 else True
            for idx,b in enumerate(rows if show else rows[:3]):
                with st.container(border=True):
                    link=b['links'].get(jd['id'],'no_saved_bullet_link')
                    st.markdown(_badge('Base' if owner=='base' else 'Library',kind='transferable' if owner=='base' else 'direct')+
                        _badge(link.replace('_',' ').title(),kind=link)+
                        _badge('Allocated' if b['allocated'] is True else 'Not allocated' if b['allocated'] is False else 'Allocation unknown'),
                        unsafe_allow_html=True)
                    st.markdown('<p style="line-height:1.55">'+_highlight(b['text'],jd_words)+'</p>',unsafe_allow_html=True)
                    present=terms(b['text']) & jd_words
                    st.caption('Exact JD terms present: '+(', '.join(sorted(present)) or 'None'))
                    st.caption('JD terms absent: '+(', '.join(sorted(jd_words-present)) or 'None'))
                    if b['draft_exact']:st.caption('Exact bullet wording also appears in the generated draft.')
                    ident=owner+':'+str(idx)+':'+b['text']
                    if st.button('Hide bullet details' if st.session_state.get(open_key)==ident else 'Inspect bullet details',
                                 key=f'phase9f_prefit_inspect_{owner}_{application_id}_{chosen}_{jd["id"]}_{idx}'):
                        st.session_state[open_key]=None if st.session_state.get(open_key)==ident else ident
                    if st.session_state.get(open_key)==ident:
                        st.markdown('**What the saved allocation proves**')
                        st.write(b['reason'] or 'No recorded allocation reason for this bullet.')
                        st.caption('Saved per-bullet JD link for this requirement: '+link.replace('_',' '))
                        from tailoring.phase9f_project_bullet_sources_v2_3 import explain_saved_bullet_decision
                        decision=b.get('raw_receipt')
                        why=explain_saved_bullet_decision(decision) if isinstance(decision,dict) else None
                        if why and why.get('status')=='step_recorded':
                            st.caption(why.get('message') or '')
                            st.caption('Ranking factor: '+str(why.get('metric') or 'not recorded')+
                                       ' · Selected: '+str(why.get('chosen_value'))+
                                       ' · Opposite source: '+str(why.get('peer_value')))
                            peer=why.get('peer')
                            if isinstance(peer,dict):
                                st.markdown('**Actual best opposite-source alternative at this selection step**')
                                st.write(str(peer.get('bullet') or 'Alternative text not retained in saved receipt'))
                        elif why:
                            st.caption(why.get('message') or 'Comparative quality winner not recorded.')
                        else:
                            st.caption('No saved per-step quality comparison for this bullet.')
                        st.caption('A pre-fit allocation decision is not a final-DOCX quality verdict.')
    st.caption('Project ranking, allocation and one-page fitting are separate decisions. The pre-fit view does not predict the final winner.')
    return True
