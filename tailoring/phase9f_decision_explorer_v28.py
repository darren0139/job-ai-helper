"""Read-only, JD-first Source/Final Decision Explorer for verified Phase 9F fitting.

Every outcome is derived from a verified exact-DOCX audit plus frozen Base/Library
source and per-bullet receipts. Lexical overlap is separate from JD evidence.
No ranking, scoring, generation, network, filesystem, or DB modifications.
"""
from __future__ import annotations

import html
from contextlib import nullcontext
import hashlib
import re
from typing import Any

VERSION = 'phase9f-v28-verified-decision-explorer-v1'
STOP = frozenset('and the for with using your more into from have will can has through this that one its are been being an of to in on or as by at is it was were a be where such ability experience relevant related strong good'.split())
TOKENS = re.compile(r'(?<![a-z0-9])(?:[a-z][a-z0-9]*(?:[+#./-][a-z0-9+#]+)*)(?![a-z0-9])', re.I)
STRENGTH = {'direct': 4, 'transferable': 3, 'weak': 2, 'none': 1, 'no_saved_bullet_link': 0}


def clean(value: Any) -> str:
    return ' '.join(str(value or '').split())


def key(value: Any) -> str:
    return clean(value).casefold()


def terms(value: Any) -> set[str]:
    return {m.group().casefold() for m in TOKENS.finditer(str(value or '')) if len(m.group()) > 2 and m.group().casefold() not in STOP}


def _receipt_map(project: dict[str, Any], allowed: set[str]) -> tuple[dict[str, dict[str, Any]], str]:
    rows = project.get('bullet_decision_receipts')
    if not isinstance(rows, list):
        return {}, 'Per-bullet allocation receipts were not saved; historical selection causes cannot be reconstructed.'
    found = {}
    for receipt in rows:
        if not isinstance(receipt, dict) or not isinstance(receipt.get('bullet'), str):
            return {}, 'Malformed per-bullet allocation receipt.'
        ident = key(receipt['bullet'])
        if ident not in allowed or ident in found:
            return {}, 'Duplicate or foreign bullet in saved allocation receipts.'
        owners = receipt.get('sources')
        if not isinstance(owners, list) or set(owners) - {'base','library'} or not owners:
            return {}, 'Missing/unknown source ownership in saved receipt.'
        found[ident] = receipt
    return found, ''


def _requirements(projects: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    ranked = projects.get('candidate_project_ranking')
    if not isinstance(ranked, list):
        return [], 'Saved JD ranking unavailable.'
    result = {}
    for item in ranked:
        if not isinstance(item, dict):
            return [], 'Invalid saved ranking row.'
        for m in item.get('requirement_matches') or []:
            if not isinstance(m, dict):
                return [], 'Invalid saved JD requirement.'
            rid, text = clean(m.get('requirement_id')), clean(m.get('requirement_text'))
            if not rid or not text:
                return [], 'Unresolvable JD requirement ID/text.'
            identity = (text, clean(m.get('importance')).lower())
            if rid in result and result[rid]['identity'] != identity:
                return [], 'Inconsistent saved JD requirement identity.'
            result[rid] = {'id':rid,'text':text,'importance':identity[1],
                           'identity':identity}
    if not result:
        return [], 'No saved canonical JD requirements available.'
    return sorted(({k:v for k,v in row.items() if k!='identity'} for row in result.values()),key=lambda x:x['text'].casefold()), ''


def build_decision_explorer(projects: Any, candidates: Any, final_audit: Any) -> dict[str, Any]:
    """Fail closed on missing/ambiguous scope rather than infer final source winners."""
    def withheld(reason):return {'status':'withheld', 'reason':reason, 'projects':[], 'requirements':[]}
    if not isinstance(final_audit, dict) or final_audit.get('verified') is not True or not final_audit.get('generation_id'):
        return withheld('An exact verified final DOCX audit and generation identity are required.')
    if not isinstance(projects, dict):return withheld('Saved generated project result missing.')
    try:
        from tailoring.phase9f_project_bullet_sources_v2_3 import build_project_bullet_source_view
        source = build_project_bullet_source_view(projects, candidates)
    except (TypeError, KeyError, ValueError, ImportError) as exc:
        return withheld('Saved source validation unavailable: '+str(exc))
    saved=source.get('projects') or []
    if not saved:return withheld(source.get('notice') or 'No validated frozen source rows.')
    rows=final_audit.get('projects') or []
    if not isinstance(rows,list) or len(rows)!=len(saved):return withheld('Verified final project set differs from saved source selection.')
    indexes={key(x.get('project')):x for x in rows if isinstance(x,dict) and key(x.get('project'))}
    if len(indexes)!=len(rows):return withheld('Final DOCX contains ambiguous project identities.')
    reqs,why=_requirements(projects)
    if why:return withheld(why)
    by_id={r['id']:r for r in reqs}
    generated={key(x.get('display_title') or x.get('title')):x for x in projects.get('recommended_projects') or [] if isinstance(x,dict)}
    out=[]
    for src in saved:
        title=src['project']; kk=key(title)
        actual=indexes.get(kk); gen=generated.get(kk)
        if actual is None or gen is None:return withheld('Saved project identity missing in final or generation.')
        texts={}
        for owner,field in (('base','base_bullets'),('library','library_bullets')):
            for item in src.get(field) or []:
                raw=item.get('Base Resume bullet') if owner=='base' else item.get('Evidence Library bullet')
                if not isinstance(raw,str) or not key(raw):return withheld('Source bullet text missing.')
                ident=key(raw)
                if ident not in texts:texts[ident]={'text':clean(raw),'sources':[]}
                if owner not in texts[ident]['sources']:texts[ident]['sources'].append(owner)
        recs,rec_reason=_receipt_map(src,set(texts))
        if rec_reason.startswith(('Malformed','Duplicate','Missing/unknown')):return withheld(rec_reason)
        final_rows=actual.get('final') or []
        final_texts={key(x['text']) for x in final_rows if isinstance(x,dict) and isinstance(x.get('text'),str)}
        fitting={}
        for ev in actual.get('changes') or []:
            if ev.get('action')=='Removed during fitting' and key(ev.get('text')):
                fitting[key(ev['text'])]=clean(ev.get('reason'))
        draft_text={key(x.get('Generated draft bullet')) for x in src.get('draft_bullets') or []}
        bullets=[]
        for ident,bullet in texts.items():
            r=recs.get(ident) or {}
            owners=sorted(bullet['sources'])
            if r and set(r.get('sources') or []) != set(owners):
                return withheld('Bullet source ownership disagrees with validated frozen source.')
            direct=r.get('direct_requirement_ids') or []
            strong=r.get('supported_requirement_ids') or []
            weak=r.get('weak_requirement_ids') or []
            if any(not isinstance(x,str) or x not in by_id for x in direct+strong+weak):
                return withheld('Bullet JD link points to an unknown canonical requirement.')
            direct_set, strong_set, weak_set=set(direct),set(strong),set(weak)
            if not direct_set<=strong_set:return withheld('Direct bullet support not in recorded strong support.')
            links={rid:('direct' if rid in direct_set else 'transferable' if rid in strong_set else 'weak')
                   for rid in direct_set | strong_set | weak_set}
            if ident in final_texts:
                status='retained'
            elif ident in fitting:
                status='removed_fitting'
            elif ident in draft_text:
                status='not_final_unattributed'
            elif r and r.get('selected') is False:
                status='not_allocated'
            else:
                status='not_final_unattributed'
            bullets.append({'id':(r.get('bullet_id') or hashlib.sha256((title+'\0'+ident).encode()).hexdigest()[:12]),
                'text':bullet['text'],'sources':owners,'words':len(bullet['text'].split()),
                'status':status,'reason':clean(r.get('reason')),
                'selected_in_allocation':r.get('selected') if r else None,
                'fit_reason':fitting.get(ident,''),'links':links,
                'decision_context':r.get('decision_context') if isinstance(r.get('decision_context'),dict) else None})
        final_unattributed=sum(1 for k in final_texts if k not in texts)
        out.append({'project':title,'rank':src.get('rank'), 'bullets':bullets,
            'final_count':len(final_rows),'unattributed_final':final_unattributed,
            'receipt_warning':rec_reason, 'source_policy':src.get('bullet_source_policy_version')})
    all_bullets=[b for p in out for b in p['bullets']]
    return {'status':'ok','projects':out,'requirements':reqs,
            'generation_id':final_audit['generation_id'],
            'count_candidates':len(all_bullets),
            'count_final':sum(p['final_count'] for p in out),
            'count_removed':sum(b['status']=='removed_fitting' for b in all_bullets),
            'decision_mode': ((projects.get('deterministic_rule_debug') or {}).get('bullet_allocation') or {}).get('allocation_mode') or 'not_recorded'}


def highlight_words(text: str, jd_words: set[str]) -> str:
    """Escape saved source text and bold only exact JD tokens; not evidence credit."""
    def esc(x: str) -> str:
        return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', html.escape(x, quote=False))
    parts=[];cursor=0
    for match in TOKENS.finditer(text):
        parts.append(esc(text[cursor:match.start()]))
        span=esc(match.group())
        parts.append('**'+span+'**' if match.group().casefold() in jd_words else span)
        cursor=match.end()
    parts.append(esc(text[cursor:]))
    return ''.join(parts)


def evidence_label(bullet: dict[str, Any], rid: str) -> str:
    return bullet['links'].get(rid,'no_saved_bullet_link')


def display_reason(bullet: dict[str,Any], *, mode: str) -> str:
    """Separate actual fitting cause, admission reason and unknown counterfactual."""
    if bullet['status']=='removed_fitting':
        return ('**Recorded fitting removal:** '+bullet['fit_reason'] if bullet['fit_reason']
                else 'Removed during fitting; detailed removal reason unavailable.')
    context=bullet.get('decision_context')
    if mode=='all_canonical_before_fitting':
        return ('**Retained in the fitted DOCX.** Both Base and Library bullets were admitted; '
                'no head-to-head Base-versus-Library quality winner was recorded.'
                if bullet['status']=='retained' else
                'This source was eligible. No head-to-head source winner was recorded.')
    if isinstance(context,dict) and context.get('version')=='phase9f-v27-bullet-selection-explanation-v1' and context.get('decision_kind')=='ranked_allocation':
        peer=context.get('best_opposite_source_peer_at_step')
        factor=clean(context.get('first_differing_rank_factor'))
        if isinstance(peer,dict) and factor and factor not in ('no_opposite_source_peer','rank_tie'):
            return '**Recorded allocation comparison:** chose this bullet ahead of an available other-source candidate; first differing factor: `'+factor+'`. Later fitting is a separate decision.'
    return ('**Retained in the final DOCX.** The saved record does not establish that it won '
            'a direct quality contest against a Base/Library alternative.' if bullet['status']=='retained'
            else 'No verified comparative selection cause was saved for this source bullet.')


def multi_project_table_rows(view: dict[str, Any]) -> list[dict[str, Any]]:
    """Read-only V2.8 source receipts, before any UI checkbox state is applied."""
    if not isinstance(view, dict) or view.get('status') != 'ok':
        return []
    rows = []
    for project in view.get('projects', []):
        bullets = project.get('bullets') or []
        rows.append({
            'Inspect': False,
            'Project': project['project'],
            'Base candidates': sum('base' in b['sources'] for b in bullets),
            'Library candidates': sum('library' in b['sources'] for b in bullets),
            'Final DOCX': int(project.get('final_count') or 0),
            'Fitting removals': sum(b.get('status') == 'removed_fitting' for b in bullets),
        })
    return rows


def render_multi_project_source_explorer(st: Any, *, view: dict[str, Any],
                                         application_id: int) -> None:
    """Several checked projects, JD links and actual source alternatives at once.

    Selection is display-only: no writing back to the source, fitter or DOCX.
    """
    rows = multi_project_table_rows(view)
    if not rows:
        return
    st.markdown('#### Compare multiple projects — Base / Library / JD')
    st.caption('Check several projects; this table only changes what is shown. '
               'JD links and exact-word matches do not establish a head-to-head winner.')
    gen = view['generation_id']
    key_name = f'phase9f_v361_source_projects_{int(application_id)}_{gen}'
    selected = set(st.session_state.get(key_name) or [])
    if hasattr(st, 'checkbox') and hasattr(st, 'columns'):
        # Native checkbox per project: one click, no data_editor cell-focus
        # or competing widget/session-state ownership. Stable source hashes
        # keep row selection attached to the same project on rerender.
        import hashlib
        headers=st.columns([1.0,4.0,1.0,1.0,1.0,1.3])
        for cell,label in zip(headers,('Inspect','Project','Base','Library','Final','Fit actions')):
            cell.caption(label)
        wanted=[]
        for row in rows:
            columns=st.columns([1.0,4.0,1.0,1.0,1.0,1.3])
            title=str(row['Project'])
            ident=hashlib.sha256(title.encode('utf-8')).hexdigest()[:12]
            checked=columns[0].checkbox('Inspect '+title, value=title in selected,
                key=key_name+'_native_'+ident, label_visibility='collapsed')
            columns[1].write(title)
            for cell,key in zip(columns[2:],('Base candidates','Library candidates','Final DOCX','Fitting removals')):
                cell.write(row[key])
            if checked:wanted.append(title)
    else:
        # Compatibility for isolated legacy Streamlit test doubles that
        # implement data_editor but not native checkbox/column primitives.
        for row in rows:
            row['Inspect'] = row['Project'] in selected
        import pandas as pd
        source_table = pd.DataFrame(rows)
        edited = st.data_editor(
            source_table, hide_index=True, width='stretch',
            disabled=[col for col in source_table.columns if col != 'Inspect'],
            column_config={'Inspect': st.column_config.CheckboxColumn(
                'Inspect together', help='Select several projects for read-only inspection')},
            key=key_name+'_editor',
        )
        wanted = [str(row['Project']) for _, row in edited.iterrows() if bool(row['Inspect'])]
    st.session_state[key_name] = wanted
    if not wanted:
        st.caption('Select projects above to compare their JD links and source candidates.')
        return
    chosen = {p['project']: p for p in view['projects'] if p['project'] in wanted}
    jd_rows = []
    for requirement in view['requirements']:
        rid = requirement['id']
        row = {'JD requirement': requirement['text'], 'Importance': requirement['importance']}
        for name, project in chosen.items():
            bs = project.get('bullets') or []
            nbase = sum('base' in b['sources'] and rid in b['links'] for b in bs)
            nlib = sum('library' in b['sources'] and rid in b['links'] for b in bs)
            nfinal = sum(b.get('status') == 'retained' and rid in b['links'] for b in bs)
            row[name] = f'Base {nbase} / Library {nlib} / Final {nfinal}'
        jd_rows.append(row)
    with st.expander('Cross-project JD evidence comparison (wide table)', expanded=False):
        st.dataframe(jd_rows, hide_index=True, width='stretch')
        st.caption('Counts are saved bullet-to-JD links, not independent proof of relevant experience.')
    for name, project in chosen.items():
        with st.expander('Base / Library alternatives — '+name, expanded=False):
            bullets = project.get('bullets') or []
            source_rows = []
            for bullet in bullets:
                source_rows.append({
                    'Source': 'Base + Library' if set(bullet['sources']) == {'base','library'}
                              else 'Base' if 'base' in bullet['sources'] else 'Library',
                    'Exact saved bullet': bullet['text'],
                    'Recorded JD links': ', '.join(sorted(bullet['links'])) or 'None',
                    'Actual final outcome': bullet['status'],
                    'Words': bullet['words'],
                })
            st.dataframe(source_rows, hide_index=True, width='stretch')
            if project.get('unattributed_final'):
                st.warning('Some final wording does not exactly match either source; attribution is withheld.')


def render_decision_explorer(st: Any, *, application_id: int, projects: Any,
                             candidates: Any, final_audit: Any) -> bool:
    """One project/JD at a time, inline details; deliberately no iframe scrolling."""
    view=build_decision_explorer(projects,candidates,final_audit)
    if view['status']!='ok':
        st.info('Decision Explorer withheld: '+view['reason'])
        return False
    st.markdown('### Decision Explorer — JD vs Base / Library')
    st.caption('Read-only. **Final** means present in the verified fitted DOCX, not a proven winner. Blue/green highlighted words mean exact JD-word overlap, not a proven semantic match.')
    a,b,c=st.columns(3)
    a.metric('Eligible source bullets',view['count_candidates'])
    b.metric('Final DOCX bullets',view['count_final'])
    c.metric('Recorded fitting removals',view['count_removed'])
    if view['decision_mode']=='all_canonical_before_fitting':
        st.info('**Fit from all eligible evidence:** Both Base and Library entered fitting. A retained Library bullet was not necessarily ranked above a Base alternative.')
    render_multi_project_source_explorer(st, view=view, application_id=application_id)
    st.caption('Optional single-project drill-down — the original V2.8 detail view remains below.')
    gen=view['generation_id']
    index=st.selectbox('Project',list(range(len(view['projects']))),
        format_func=lambda n:view['projects'][n]['project'],
        key=f'phase9f_explorer_project_{application_id}_{gen}')
    project=view['projects'][index]
    reqs=view['requirements']
    req_key=f'phase9f_explorer_req_{application_id}_{gen}'
    # A genuine Streamlit control per JD row provides keyboard and mouse
    # activation; unlike an HTML-only mock table, selection updates the app.
    with (st.expander('JD requirement coverage map — click a row', expanded=True) if hasattr(st,'expander') else nullcontext()):
        st.caption('Counts reflect saved per-bullet JD links, not proof of complete résumé coverage.')
        def _badge(label, *, kind='weak'):
            bg,fg={'direct':('#17533d','#86efac'),'transferable':('#17446b','#93c5fd'),
                   'weak':('#523d16','#fcd34d')}.get(kind,('#35383f','#d1d5db'))
            return '<span style=\"background:'+bg+';color:'+fg+';border-radius:6px;padding:2px 5px\">'+html.escape(label)+'</span>'
        for req_index,req in enumerate(reqs):
            rid=req['id']
            a_count=sum('base' in bullet['sources'] and rid in bullet['links'] for bullet in project['bullets'])
            b_count=sum('library' in bullet['sources'] and rid in bullet['links'] for bullet in project['bullets'])
            f_count=sum(bullet['status']=='retained' and rid in bullet['links'] for bullet in project['bullets'])
            cells=st.columns([7,2,2,2] if hasattr(st,'expander') else 4)
            with cells[0]:
                if st.button(req['importance'].title()+' · '+req['text'],
                             key=f'phase9f_explorer_req_btn_{application_id}_{gen}_{index}_{rid}',width='stretch'):
                    st.session_state[req_key]=req_index
            with cells[1]:st.markdown(_badge('Base '+str(a_count),kind='transferable'),unsafe_allow_html=True)
            with cells[2]:st.markdown(_badge('Library '+str(b_count),kind='direct'),unsafe_allow_html=True)
            with cells[3]:st.markdown(_badge('Final '+str(f_count),kind='weak' if not f_count else 'direct'),unsafe_allow_html=True)
    ridx=st.selectbox('JD requirement to inspect',list(range(len(reqs))),
        format_func=lambda i:(reqs[i]['importance'].title()+' · '+reqs[i]['text']),
        key=req_key)
    jd=reqs[ridx]
    st.markdown('**JD requirement:** '+jd['text'])
    if any(p['source_policy'] != 'phase9f-combined-project-bullet-sources-v2.7' for p in view['projects']):
        st.warning('This contains legacy generations. Historical Library-first policy may have been the selection cause; do not infer a quality comparison.')
    if project['unattributed_final']:
        st.warning(str(project['unattributed_final'])+' final DOCX bullet(s) have changed wording with no exact Base/Library ownership; no source winner is inferred for them.')
    jd_words=terms(jd['text'])
    st.caption('JD content terms: '+(', '.join(sorted(jd_words)) or 'No exact content terms extracted'))
    def candidates_for(owner):
        result=[r for r in project['bullets'] if owner in r['sources']]
        result.sort(key=lambda r:(-STRENGTH[evidence_label(r,jd['id'])],
            -len(terms(r['text']) & jd_words), r['status']!='retained',r['text'].casefold()))
        return result
    base_best=candidates_for('base')
    library_best=candidates_for('library')
    if base_best and library_best:
        one,two=base_best[0],library_best[0]
        strength_a=evidence_label(one,jd['id'])
        strength_b=evidence_label(two,jd['id'])
        if STRENGTH[strength_a]!=STRENGTH[strength_b]:
            stronger='Library' if STRENGTH[strength_b]>STRENGTH[strength_a] else 'Base'
            st.info('**Saved JD evidence comparison:** Best '+stronger+' candidate has a stronger per-bullet recorded match '
                    'for this specific JD requirement ('+strength_a+' vs '+strength_b+'). '
                    '**This explains evidence strength, not the fitter’s causal selection.**')
        else:
            st.caption('The leading Base and Library candidates have the same recorded per-bullet match level for this JD. Keyword counts alone do not establish a winner.')
    retained=[x for x in project['bullets'] if x['status']=='retained']
    st.caption('Final project bullets: '+str(project['final_count'])+
        ' · Base-only '+str(sum(set(x['sources'])=={'base'} for x in retained))+
        ' · Library-only '+str(sum(set(x['sources'])=={'library'} for x in retained))+
        ' · Shared '+str(sum(set(x['sources'])=={'base','library'} for x in retained)))
    bcols=st.columns(2)
    for owner,column,heading in [('base',bcols[0],'Selected Base résumé'),('library',bcols[1],'Evidence Library')]:
        with column:
            st.markdown('#### '+heading)
            available=candidates_for(owner)
            st.caption(str(len(available))+' source bullets · ordered by saved JD link, then lexical overlap (display order only)')
            if not available:
                st.caption('No eligible bullet from this source.')
            count=min(len(available),3)
            if len(available)>3 and st.checkbox('Show all '+heading+' bullets',key=f'phase9f_explorer_show_{owner}_{application_id}_{gen}_{index}'):
                count=len(available)
            for n,bullet in enumerate(available[:count]):
                with st.container(border=True):
                    matched=terms(bullet['text']) & jd_words
                    st.markdown('**'+('Retained in final DOCX' if bullet['status']=='retained' else
                        'Removed during fitting' if bullet['status']=='removed_fitting' else
                        'Not allocated' if bullet['status']=='not_allocated' else 'Not in final — cause not established')+'**')
                    st.markdown(highlight_words(bullet['text'],jd_words))
                    st.caption('Saved JD link: **'+evidence_label(bullet,jd['id']).replace('_',' ')+'** · '+str(bullet['words'])+' words')
                    st.caption('Exact JD terms present: '+(', '.join(sorted(matched)) or 'None'))
                    st.caption('JD terms absent: '+(', '.join(sorted(jd_words-matched)) or 'None'))
                    ck=f'phase9f_explorer_inspect_{application_id}_{gen}_{index}_{owner}_{bullet["id"]}'
                    open_key=f'phase9f_explorer_open_{application_id}_{gen}_{index}_{ridx}'
                    identity=owner+':'+str(bullet['id'])
                    if st.button('Hide details' if st.session_state.get(open_key)==identity else 'Inspect bullet details',key=ck):
                        st.session_state[open_key]=None if st.session_state.get(open_key)==identity else identity
                    if st.session_state.get(open_key)==identity:
                        st.markdown(display_reason(bullet,mode=view['decision_mode']))
                        if bullet['reason']:st.caption('Allocator receipt: '+bullet['reason'])
                        if bullet['fit_reason']:st.caption('Fitting removal receipt: '+bullet['fit_reason'])
                        if bullet.get('decision_context') and view['decision_mode']!='all_canonical_before_fitting':
                            d=bullet['decision_context']; peer=d.get('best_opposite_source_peer_at_step')
                            if isinstance(peer,dict):
                                st.markdown('**Recorded other-source candidate at selection time**')
                                st.write(str(peer.get('bullet') or 'No text saved'))
                                st.caption('First different ranking factor: '+str(d.get('first_differing_rank_factor') or 'Not recorded'))
                        else:
                            st.caption('No verified competing Base-versus-Library selection pair in this run. An alternative shown elsewhere is only a visual comparison.')
    st.caption('Project-level scores and raw keywords alone cannot prove a particular bullet is Direct evidence. Full final improvement requires the separate Phase 8 verified Job Match comparison.')
    return True
