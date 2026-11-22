"""Presentation over existing estimator; no source-pair or scoring changes."""
from tailoring.bullet_choice_estimated import term_labels
import re
from tailoring.bullet_choice_estimated import estimate_pair
from hashlib import sha256
from html import escape


def wording_facts(row, catalog):
    """Presentation facts from exact phrases and the existing estimator.

    Context below is NOT added to estimator support, native evidence or scores.
    A phrase must occur in the wording and a performed claim must be present.
    """
    from tailoring.bullet_choice_estimated import action_status, terms
    from taxonomy_discovery.technology_registry import get_default_registry
    text = row['bullet']
    performed = action_status(text) == 'performed_claim'
    patterns = {
        'testing': r'\b(?:automated )?(?:unit|integration|system|user acceptance) test(?:s|ing)?\b|\bUAT\b|\bfull test suite\b',
        'ci': r'\bGitHub Actions CI\b|\bcompilation\b|\bdependency checks\b',
        'ui': r'\b(?:gameplay and )?UI features\b|\buser-facing UI features\b',
        'features': r'\bsliders\b|\blevel-locking screens\b|\bimage attachment\b|\basset (?:manager|loading)\b',
        'team': r'\b(?:small|[0-9]+-person) team\b|\bin a team\b',
        'release': r'\breleased on Google Play\b|\bpublished on Google Play\b|\bcompleted mobile game\b',
        'database': r'\bPostgREST\b|\bRow-Level Security(?: policies)?\b|\bdatabase access\b|\bPostgreSQL(?:-backed service)?\b',
        'purpose': r'\bto (?:support|secure|validate|control)[^.]*',
    }
    phrases = {kind:list(dict.fromkeys(m.group(0) for m in re.finditer(pattern, text, re.I))) if performed else []
               for kind,pattern in patterns.items()}
    technology_ids = {e['technology_id'] for e in get_default_registry().entries}
    technologies = term_labels(terms(text) & technology_ids) if performed else []
    estimate = estimate_pair(text, text, list(catalog.values()))
    strengths=[];limits=[]
    for kind,label in [('testing','Explicit testing activity'),('ci','Concrete build/verification tooling'),
                       ('ui','Transferable interface development context'),('features','Specific implemented details'),
                       ('team','Explicit team contribution'),('release','Released-product context'),
                       ('database','Specific database activity'),('purpose','Stated implementation purpose')]:
        if phrases[kind]:strengths.append(label+': “'+'”, “'.join(phrases[kind])+'”.')
    if technologies:strengths.append('Named technologies: '+', '.join(technologies)+'.')
    if not strengths:
        strengths.append('Performed work is described; inspect the requirement evidence below.' if performed
                         else 'No completed activity is established by this sentence; terminology alone is not experience.')
    rows=[]
    for q in estimate.get('requirements', []):
        item=q['base'];lower=q['text'].lower();matched=term_labels(item['lexical_terms'])
        quote=[];kind='Not established';reason='No relevant performed phrase is established.'
        if item['supported_facets']:
            quote=[m.group(0) for term in matched if (m:=re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text,re.I))]
            kind='Explicit wording · partial evidence'
            reason='Completed activity and matched terminology; proficiency and full requirement satisfaction are not verified.'
            if item.get('alternative_satisfied'):
                reason='An allowed one-or-more alternative is explicit; the other alternatives are optional. Proficiency is not verified.'
        relevant=bool(item['supported_facets'])
        if 'test' in lower and (phrases['testing'] or phrases['ui']):
            relevant=True
            if phrases['testing']:
                quote=phrases['testing'];kind='Partial testing activity'
                kinds={'unit testing':r'\bunit test(?:s|ing)?\b','integration testing':r'\bintegration test(?:s|ing)?\b',
                       'system testing':r'\bsystem test(?:s|ing)?\b','UAT':r'\b(?:user acceptance test(?:s|ing)?|uat)\b'}
                missing=[label for label,pattern in kinds.items() if not re.search(pattern,text,re.I)]
                reason=('Not established by this wording: '+', '.join(missing)+'. A test suite does not establish every test type.' if missing
                        else 'All named testing activities occur in the wording; this is not independent verification.')
            elif phrases['ui']:
                quote=[];reason='“user-facing” describes UI; incidental “user” is not user acceptance testing.'
        if any(s in lower for s in ('specifications','develop and enhance')) and phrases['ui']:
            relevant=True;quote=phrases['ui'];kind='Transferable development context'
            reason='Interface implementation is related development work; functional and technical specifications are not stated.'
        if 'frontend' in lower and ('framework' in lower) and (phrases['ui'] or item['supported_facets']):
            relevant=True
            if not item.get('alternative_satisfied'):
                quote=phrases['ui'];kind='Related UI context only'
                reason='UI development does not establish any named web-framework alternative.'
        if 'stakeholder' in lower and (phrases['team'] or phrases['ui']):
            relevant=True;quote=phrases['team'];kind='Not established'
            reason='Team contribution is not stakeholder requirements gathering.' if quote else 'No stakeholder requirements activity is stated.'
        if ('deploy' in lower or 'build automation' in lower) and (phrases['ci'] or phrases['release']):
            relevant=True;quote=phrases['ci'] or phrases['release'];kind='Related tooling / delivery context'
            reason='Build/CI or product release is stated; application deployment is not established.'
        if 'database' in lower and (phrases['database'] or re.search(r'\bAdded\b', text)):
            relevant=True;quote=phrases['database'];kind='Explicit database activity' if quote else 'Not matched'
            reason='Database activity is stated; proficiency is not verified.' if quote else '“Added” is generic wording, not database evidence.'
        if 'backend' in lower and 'language' in lower and phrases['database']:
            relevant=True
            if not item.get('alternative_satisfied'):
                quote=[];kind='Not established';reason='Database access does not establish a requested backend programming language.'
        # Relevant limitations, rather than a page of unrelated missing requirements.
        if relevant and kind in {'Not established','Not matched','Related UI context only'}:
            limits.append(reason)
        if relevant and ('not established' in reason or 'not stated' in reason):limits.append(reason)
        rows.append({'id':q['id'],'text':q['text'],'importance':q['importance'],
                     'phrases':quote,'kind':kind,'reason':reason,'relevant':relevant,
                     'supported':bool(item['supported_facets'])})
    return {'phrases':phrases,'technologies':technologies,'strengths':strengths,
            'limits':list(dict.fromkeys(limits))[:4], 'requirements':rows,
            'words':len(text.split()),'estimate':estimate}


def _comparison_table(st, headings, rows):
    cells=''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)
    st.markdown('<div class="bullet-fit-table"><table><thead><tr>'+''.join('<th>'+escape(v)+'</th>' for v in headings)+
                '</tr></thead><tbody>'+cells+'</tbody></table></div>',unsafe_allow_html=True)


def render_wording_comparison(st, *, base, library, catalog, recorded, result, key):
    """User-facing B4 presentation; all score/evidence decisions remain existing."""
    st.markdown('''<style>.bullet-fit-table{width:100%;overflow-x:auto;border:1px solid #56627366;border-radius:8px}
    .bullet-fit-table table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:14px}
    .bullet-fit-table th,.bullet-fit-table td{padding:12px;vertical-align:top;text-align:left;overflow-wrap:anywhere;border-bottom:1px solid #56627355}
    @media(max-width:800px){.bullet-fit-table th,.bullet-fit-table td{padding:7px;font-size:12px}}</style>''',unsafe_allow_html=True)
    rows=[r for r in (base,library) if r is not None]
    if len(rows)==2 and base['bullet']==library['bullet']:rows=[base]
    facts=[wording_facts(r,catalog) for r in rows]
    titles=(['Base Resume','Evidence Library'] if len(rows)==2 else
            ['Shared Base + Library wording'] if {'Selected Base','Evidence Library'}<=set(rows[0]['sources']) else
            ['Base Resume' if base is not None else 'Evidence Library'])
    for index,(target,row,fact,title) in enumerate(zip(st.columns(len(rows)),rows,facts,titles)):
        card=target.container(border=True)
        with card:
            card.markdown('##### '+title)
            card.write(row['bullet'])
            if recorded:
                before=bool(row.get('in_actual_a'));after=bool(row.get('in_proposed_b'))
                card.markdown('**'+('Kept in both versions' if before and after else 'Removed from alternative' if before else 'Added to alternative' if after else 'Not in either version')+'**')
                chosen=before if result.get('winner')=='existing_final' else after if result.get('winner')=='optimized_candidate' else None
                card.caption('Incumbent: '+('included' if before else 'excluded')+' · Alternative: '+('included' if after else 'excluded')+' · Chosen résumé: '+('included' if chosen is True else 'excluded' if chosen is False else 'unavailable'))
            else:card.caption('Saved membership unavailable; no selection is inferred.')
            card.caption(str(fact['words'])+' words · provenance: '+', '.join(row['sources']))
            card.markdown('**:green[Strengths]**')
            for item in fact['strengths']:card.write('+ '+item)
            card.markdown('**:red[Weaknesses / limits]**')
            for item in fact['limits'] or ['This sentence alone does not verify proficiency or a native score gain.']:card.write('− '+item)
    st.markdown('##### JD requirements & keyword evidence')
    st.caption('Estimated wording interpretation, not native match credit. Exact JD identities and historical importance are preserved.')
    relevant={q['id'] for f in facts for q in f['requirements'] if q['relevant']}
    reqs={q['id']:q for f in facts for q in f['requirements']}
    table=[]
    for rid,q in reqs.items():
        if rid not in relevant:continue
        values=[q['importance'].replace('_',' ').title()+' · '+q['text']]
        for fact in facts:
            item=next(x for x in fact['requirements'] if x['id']==rid)
            values.append(item['kind']+' · '+('“'+'”, “'.join(item['phrases'])+'”. ' if item['phrases'] else '')+item['reason'])
        table.append(values)
    if table:_comparison_table(st,['Current JD requirement',*titles],table)
    else:st.caption('No specific requirement relationship is established; the source wording remains available for inspection.')
    st.markdown('##### Keyword comparison at a glance')
    _comparison_table(st,['Category',*titles],[['Explicit technologies',*[', '.join(f['technologies']) or 'None named' for f in facts]],
        ['Related activity phrases',*['; '.join(p for values in f['phrases'].values() for p in values) or 'None established' for f in facts]],
        ['Word count',*[str(f['words']) for f in facts]]])
    st.markdown('##### Which wording is stronger — and why?')
    if len(rows)==2:
        estimate=estimate_pair(base['bullet'],library['bullet'],list(catalog.values()))
        st.write('Estimated JD relevance: '+estimate['outcome']+'. '+estimate['reason'])
        dimensions=[]
        for field,label in [('features','Specific implementation detail'),('team','Team contribution'),('release','Product delivery')]:
            a,b=bool(facts[0]['phrases'][field]),bool(facts[1]['phrases'][field])
            dimensions.append([label,'Both describe this context' if a and b else titles[0]+' explicitly describes this context' if a else titles[1]+' explicitly describes this context' if b else 'Not stated in either wording'])
        delta=facts[1]['words']-facts[0]['words']
        dimensions.extend([['Word efficiency',f"Base {facts[0]['words']} vs Library {facts[1]['words']} words ({abs(delta)}-word difference). Shorter is useful only if needed evidence is preserved; physical space benefit unmeasured."],
            ['Other retained bullets','Use compatible recorded coverage in supporting evidence; no redundancy is inferred from word counts.'],
            ['Broader JD corpus','Not evaluated here; no corpus frequency or general suitability score is invented.']])
        _comparison_table(st,['Dimension','Estimated trade-off'],dimensions)
        if not any(q['supported'] for f in facts for q in f['requirements']):
            st.write('No overall JD-fit winner is established. Compare concrete implementation detail with team/delivery context; neither substitutes for missing named JD capabilities.')
    else:st.caption('One wording is displayed; no source winner or head-to-head competition is inferred.')
    st.markdown('**What Best-of actually did**')
    for title,row in zip(titles,rows):
        if recorded:
            before=bool(row.get('in_actual_a'));after=bool(row.get('in_proposed_b'))
            st.write(title+': '+('included in both versions' if before and after else 'removed only from the tested alternative' if before else 'added to the tested alternative' if after else 'outside both versions')+'.')
            if before and not after and result.get('winner')=='existing_final':st.write('Best-of retained the incumbent; this wording remains in the chosen résumé.')
        else:st.write('Saved selection membership unavailable.')
    st.caption('Individual cause not recorded unless a compatible causal receipt is shown. Wording preference is an estimate, not the historical optimizer reason. Native bullet impact and physical space benefit are unmeasured here.')
    evidence_scope=sha256('|'.join(row['bullet'] for row in rows).encode()).hexdigest()[:12]
    details=st.expander('Supporting evidence & match details',expanded=False,
                        key=key+'_support_'+evidence_scope,on_change='rerun')
    with details:
        details.caption('Independent same-project wording assessment. Strict historical pairing and measured trials remain in Advanced Diagnostics.')
        for row in rows:
            details.write(row['bullet'])
            details.caption('Exact source provenance: '+', '.join(row['sources']))
            links=row.get('jd_links') or []
            if not links:details.caption('No compatible saved native citation is bound to this wording. This does not disprove relevance.')
            for link in links:
                details.write(link['importance']+' · '+link['text'])
                details.caption(link.get('status','Saved link; not independent attestation'))
                for role,e in link.get('native_evidence',{}).items():
                    details.caption(role+' document · '+e['match_label']+' · strength '+str(e.get('strength'))+'/5; requirement evidence, not a bullet score delta')
                    details.write(e['excerpt'])
        other=details.expander('Other JD requirements — complete wording assessment',expanded=False)
        with other:
            for q in reqs.values():
                if q['id'] not in relevant:other.caption(q['importance']+' · '+q['text']+' — no specific wording relationship established.')


def render_source_wordings(st, *, scope, catalog, recorded, proposal, key):
    st.markdown('#### Available Source Wordings — Estimated JD Relevance')
    st.caption('Individual wording against this JD. This does not establish a replacement pair, equivalent experience, historical competition or a native score effect.')
    choices=[r for r in scope if set(r['sources']) & {'Selected Base','Evidence Library'}]
    if not choices:
        st.caption('No eligible source wording is available in this project.')
        return
    i=st.selectbox('Source wording to explain',range(len(choices)),format_func=lambda i:choices[i]['source_label']+' · '+choices[i]['bullet'],key=key+'_standalone')
    row=choices[i]
    render_wording_explanation(st, row=row, catalog=catalog, recorded=recorded)


def render_wording_explanation(st, *, row, catalog, recorded, incumbent_retained=False):
    """Existing standalone explanation, shared by primary and detailed views."""
    st.write(row['bullet'])
    st.caption('Source provenance: '+', '.join(row['sources']))
    # Same-wording comparison exposes the existing estimator's requirement rows;
    # no synthetic competing wording or new scoring mechanism is introduced.
    result=estimate_pair(row['bullet'],row['bullet'],list(catalog.values()))
    st.markdown('**Estimated JD Relevance — individual wording**')
    if not catalog:
        st.caption('Estimated relevance unavailable: compatible readable JD requirements are missing.')
    supported=[q for q in result.get('requirements',[]) if q['base']['supported_facets']]
    if not supported:st.write('No reliable performed capability support is estimated from the available requirement wording. This does not disprove relevance or experience.')
    for req in supported:
        item=req['base']
        st.write(req['importance'].replace('_',' ').title()+' · '+req['text'])
        st.caption('Estimated support: '+item['coverage'].replace('_',' ')+'. Explicit matched terminology: '+', '.join(term_labels(item['lexical_terms']))+'. Missing terminology: '+(', '.join(term_labels(item['missing_terms'])) or 'None detected; wording overlap alone does not prove full satisfaction.'))
        if item.get('alternative_satisfied'):
            st.caption('Explicit one-or-more alternative matched. Other listed alternatives are optional, not missing capabilities: '+', '.join(term_labels(item['optional_alternatives']))+'. This does not verify proficiency.')
    # Keep lexical cues distinguishable from performed support, with readable JD
    # text. Unrelated requirements remain in the existing detail expander below.
    lexical=[q for q in result.get('requirements',[]) if not q['base']['supported_facets'] and q['base']['lexical_terms']]
    for req in lexical:
        st.caption(req['importance'].title()+' · '+req['text']+' — lexical wording only: '+', '.join(term_labels(req['base']['lexical_terms']))+'. This does not establish the capability.')
    missing=[q for q in result.get('requirements',[]) if not q['base']['supported_facets']]
    if missing:
        details=st.expander('Other JD requirements — complete wording assessment', expanded=False)
        with details:
            for req in missing:
                details.caption(req['importance']+' · '+req['text']+' · '+('Lexical cues only: '+', '.join(term_labels(req['base']['lexical_terms'])) if req['base']['lexical_terms'] else 'No sufficient matched capability wording.'))
    jd=' '.join(q['text'] for q in catalog.values()).lower()
    if 'testing' in jd or 'tests' in jd:
        kinds={'unit testing':r'\bunit test(?:s|ing)?\b','integration testing':r'\bintegration test(?:s|ing)?\b','system testing':r'\bsystem test(?:s|ing)?\b','user acceptance testing':r'\b(?:user acceptance test(?:s|ing)?|uat)\b'}
        present=[label for label,pattern in kinds.items() if re.search(pattern,row['bullet'],re.I)]
        if present:
            st.write('Explicit testing terminology: '+', '.join(present)+'.')
            st.write('Not independently established by this wording: '+', '.join(k for k in kinds if k not in present)+'. Unit tests do not establish the entire compound testing requirement.')
    st.markdown('**Recorded Optimizer Selection**')
    existing_known=recorded or row.get('existing_membership_verified') is True
    st.caption('Existing fitted résumé: '+(('Present' if row.get('in_actual_a') else 'Not present') if existing_known else 'Membership unavailable'))
    st.write(('Included in the saved optimized proposal.' if row.get('in_proposed_b') else 'Excluded from the saved optimized proposal.') if recorded else 'Saved proposal membership unavailable.')
    if recorded and incumbent_retained and row.get('in_actual_a') and not row.get('in_proposed_b'):
        st.write('Removed only from the tested optimized alternative. Best-of retained the existing fitted résumé, where this wording remains present.')
    st.caption('Individual selection cause not recorded. The available evidence explains JD relevance, but does not establish which constraint caused this bullet to be included or excluded.')
    st.markdown('**Verified Evidence and Native Impact**')
    found=False;shown=set()
    for link in row.get('jd_links',[]):
        if link.get('native_evidence'):
            found=True;st.write(link['text']+' ['+link['importance']+']')
            for doc,e in link['native_evidence'].items():
                st.caption(f"Recorded {doc} document citation · {e['match_label']} · strength {e.get('strength')}/5")
                if e['excerpt'] not in shown:st.write(e['excerpt']);shown.add(e['excerpt'])
    if not found:st.caption('No bound native excerpt is recorded for this wording in the current view.')
    for link in row.get('jd_links',[]):
        if not link.get('native_evidence'):
            st.caption('Saved JD link · '+link['text']+' — '+link.get('status','Unverified saved link')+'. No bound native citation for this wording.')
    for basis,buckets in (row.get('coverage') or {}).items():
        shared=buckets.get('Shared in alternative',[])
        unique=buckets.get('Unique in alternative',[])
        if shared:
            st.caption(basis+' · requirement also supported elsewhere in the alternative: '+', '.join(req['text'] for req in shared)+'. This is coverage context, not a selection cause.')
        if unique:
            st.caption(basis+' · unique requirement link in the alternative: '+', '.join(req['text'] for req in unique)+'. Multiple citations do not add requirement weight.')
    st.caption(f"Word cost: {len(row['bullet'].split())}. Individual page-fit or space-use benefit was not measured.")
    st.caption('Estimated support is not factual attestation. Individual native impact is unmeasured; no historical replacement winner is inferred.')


def render_bullet_choice_card(st, *, row, catalog, recorded, incumbent_retained=False):
    """User-facing projection of the existing estimator and saved membership."""
    estimate=estimate_pair(row['bullet'], row['bullet'], list(catalog.values()))
    relevant=[q for q in estimate.get('requirements', []) if q['base']['supported_facets']]
    st.write(row['bullet'])
    st.caption('Source: '+('Shared Base + Library wording' if {'Selected Base','Evidence Library'}<=set(row['sources']) else row.get('source_label', ', '.join(row['sources']))))
    if recorded:
        before=bool(row.get('in_actual_a'));after=bool(row.get('in_proposed_b'))
        state='Kept in both versions' if before and after else 'Removed from alternative' if before else 'Added to alternative' if after else 'Not selected in either version'
        st.markdown('**'+state+'**')
        st.caption('Existing fitted résumé: '+('Included' if before else 'Not included')+' · Optimized alternative: '+('Included' if after else 'Not included'))
    else:st.caption('Saved selection membership unavailable.')
    st.markdown('**Why it fits this JD — estimated wording relevance**')
    if not catalog:
        st.write('A compatible JD context is unavailable; no fit assessment is shown.')
    elif not relevant:
        st.write('No clear direct JD match is established by this wording. Its project activity may be useful context, but it does not explicitly demonstrate the specific capabilities in the available JD requirements.')
    for q in relevant[:3]:
        item=q['base'];terms=', '.join(term_labels(item['supported_facets']))
        st.write('• '+q['importance'].replace('_',' ').title()+': '+q['text'])
        kinds={'unit testing':r'\bunit test(?:s|ing)?\b','integration testing':r'\bintegration test(?:s|ing)?\b','system testing':r'\bsystem test(?:s|ing)?\b','user acceptance testing':r'\b(?:user acceptance test(?:s|ing)?|uat)\b'}
        demonstrated=[label for label,pattern in kinds.items() if re.search(pattern,row['bullet'],re.I)] if 'test' in q['text'].lower() else []
        if demonstrated:
            st.write('This wording explicitly describes '+', '.join(demonstrated)+'. It supports part of this testing responsibility, not the whole requirement.')
            missing=[label for label in kinds if label not in demonstrated]
            if missing:st.write('Not established by this bullet: '+', '.join(missing)+'.')
        else:
            st.write('This wording connects a completed activity to '+terms+'. '+('It addresses an allowed alternative; other listed alternatives are optional.' if item.get('alternative_satisfied') else 'This is partial wording support, not proof of the whole requirement.' if item['coverage']!='full_wording_overlap' else 'The wording overlaps the requirement; this does not verify complete proficiency.'))
            missing=term_labels(item['missing_terms'])
            if missing:st.caption('Not established here: '+', '.join(missing)+'.')
    if relevant:st.caption('Wording estimate only. Source attestation and saved native evidence are separate; this does not change Job Match.')
    st.markdown('**What Best-of actually did**')
    if recorded:
        if incumbent_retained and row.get('in_actual_a'):
            st.write('Best-of kept the existing fitted résumé, so this bullet remains in the chosen document.'+(' Only the tested alternative removed it.' if not row.get('in_proposed_b') else ' The tested alternative also included it.'))
        else:st.write('The saved proposal '+('includes' if row.get('in_proposed_b') else 'does not include')+' this wording. This is a recorded membership fact, not proof of an individual winner.')
    else:st.write('A compatible saved selection receipt is unavailable.')
    coverage=row.get('coverage') or {}
    shared=[]
    for basis,buckets in coverage.items():
        for q in buckets.get('Shared in alternative',[]):
            if q['text'] not in shared:shared.append(q['text'])
    if shared:st.caption('Recorded coverage remains elsewhere in the alternative: '+'; '.join(shared[:2])+'. This does not identify the cause of removal.')
    st.caption('Individual selection cause not recorded. Native impact of this bullet alone: not independently measured.')
    citations=[(link,doc,e) for link in row.get('jd_links',[]) for doc,e in link.get('native_evidence',{}).items()]
    if citations:
        link,doc,e=citations[0]
        st.caption('Saved native evidence: '+link['text']+' · '+doc+' document · '+e['match_label']+' · strength '+str(e.get('strength'))+'/5. This is requirement evidence, not a bullet score delta.')
    else:st.caption('No compatible native citation is bound to this exact wording. Missing citation does not disprove its estimated relevance.')
    st.caption(str(len(row['bullet'].split()))+' words · Individual page-fit benefit unmeasured.')
    details=st.expander('Supporting evidence and complete wording assessment', expanded=False)
    with details:
        render_wording_explanation(details,row=row,catalog=catalog,recorded=recorded,incumbent_retained=incumbent_retained)


def render_primary_bullet_explanation(st, *, ranked, catalog, recorded, result, key):
    """Select a saved wording, then reuse the standalone estimator/evidence UI.

    Changed membership is the display default, not a new relevance ranking.
    Neither a competing source nor an independently tested swap is required.
    """
    st.markdown('#### Bullet Choices')
    st.caption('Choose a project and wording to see its JD fit and what Best-of actually included. No source pair is required.')
    if not ranked:
        st.caption('No saved eligible wording is available to explain.')
        return
    project=st.selectbox('Bullet explanation project', ['All projects', *sorted({r['project'] for r in ranked})], key=key+'_project')
    scope=[r for r in ranked if project=='All projects' or r['project']==project]
    changed=[r for r in scope if recorded and r.get('in_actual_a')!=r.get('in_proposed_b')]
    choices=changed+[r for r in scope if r not in changed]
    def label(i):
        row=choices[i]
        if not recorded: membership='Membership unavailable'
        elif row.get('in_actual_a') and not row.get('in_proposed_b'):membership='Removed from alternative'
        elif row.get('in_actual_a') and row.get('in_proposed_b'):membership='Included in both'
        elif row.get('in_proposed_b'):membership='Added to alternative'
        else:membership='Excluded from both'
        return row['project']+' · '+membership+' · '+row['bullet']
    choice=st.selectbox('Bullet to explain',range(len(choices)),format_func=label,
        key=key+'_'+sha256(project.encode()).hexdigest()[:12]+'_wording')
    render_bullet_choice_card(st,row=choices[choice],catalog=catalog,recorded=recorded,
        incumbent_retained=result.get('status')=='verified' and result.get('winner')=='existing_final')


def render_why_slate(st, info, calc):
    st.markdown('#### Why These Bullets?')
    if info['native_delta'] is not None:
        st.write(f"Best-of: existing fitted résumé {info['a_score']:g} → optimized alternative {info['b_score']:g}. "+info['verdict'])
    st.caption('Phase 8 compares Selected Base with Final; Best-of compares the existing fitted résumé with another optimized alternative. Their baselines and deltas must not be conflated. No document delta is an individual bullet contribution.')
    if calc.get('status')!='available':st.caption('Saved whole-slate selection receipt unavailable.');return
    rows=calc.get('rows',[])
    added=[r for r in rows if not r.get('in_actual_a') and r.get('in_proposed_b')]
    removed=[r for r in rows if r.get('in_actual_a') and not r.get('in_proposed_b')]
    retained=sum(bool(r.get('in_actual_a') and r.get('in_proposed_b')) for r in rows)
    st.write(f'{len(added)} added · {len(removed)} removed · {retained} retained wordings. A removal/addition does not by itself establish a replacement pair.')
    for label,items in [('Added',added),('Removed',removed)]:
        for row in items:st.write(label+' · '+row['project']+' · '+row['bullet'])
    st.caption('Saved whole-slate objectives and word changes above explain the recorded comparison context. Individual causal selection reasons and useful page-space savings are unmeasured unless separately recorded.')
