"""Presentation over existing estimator; no source-pair or scoring changes."""
from tailoring.bullet_choice_estimated import term_labels
import re
from tailoring.bullet_choice_estimated import estimate_pair


def render_source_wordings(st, *, scope, catalog, recorded, proposal, key):
    st.markdown('#### Available Source Wordings — Estimated JD Relevance')
    st.caption('Individual wording against this JD. This does not establish a replacement pair, equivalent experience, historical competition or a native score effect.')
    choices=[r for r in scope if set(r['sources']) & {'Selected Base','Evidence Library'}]
    i=st.selectbox('Source wording to explain',range(len(choices)),format_func=lambda i:choices[i]['source_label']+' · '+choices[i]['bullet'],key=key+'_standalone')
    row=choices[i]
    st.write(row['bullet'])
    st.caption('Source provenance: '+', '.join(row['sources']))
    # Same-wording comparison exposes the existing estimator's requirement rows;
    # no synthetic competing wording or new scoring mechanism is introduced.
    result=estimate_pair(row['bullet'],row['bullet'],list(catalog.values()))
    st.markdown('**Estimated JD Relevance — individual wording**')
    supported=[q for q in result.get('requirements',[]) if q['base']['supported_facets']]
    if not supported:st.write('No reliable performed capability support is estimated from the available requirement wording. This does not disprove relevance or experience.')
    for req in supported:
        item=req['base']
        st.write(req['importance'].replace('_',' ').title()+' · '+req['text'])
        st.caption('Estimated support: '+item['coverage'].replace('_',' ')+'. Explicit matched terminology: '+', '.join(term_labels(item['lexical_terms']))+'. Missing terminology: '+(', '.join(term_labels(item['missing_terms'])) or 'None detected; wording overlap alone does not prove full satisfaction.'))
        if item.get('alternative_satisfied'):
            st.caption('Explicit one-or-more alternative matched. Other listed alternatives are optional, not missing capabilities: '+', '.join(term_labels(item['optional_alternatives']))+'. This does not verify proficiency.')
    missing=[q for q in result.get('requirements',[]) if not q['base']['supported_facets']]
    if missing:
        with st.expander('Other JD requirements — complete wording assessment', expanded=False):
            for req in missing:
                st.caption(req['importance']+' · '+req['text']+' · '+('Lexical cues only: '+', '.join(term_labels(req['base']['lexical_terms'])) if req['base']['lexical_terms'] else 'No sufficient matched capability wording.'))
    jd=' '.join(q['text'] for q in catalog.values()).lower()
    if 'testing' in jd or 'tests' in jd:
        kinds={'unit testing':r'\bunit test(?:s|ing)?\b','integration testing':r'\bintegration test(?:s|ing)?\b','system testing':r'\bsystem test(?:s|ing)?\b','user acceptance testing':r'\b(?:user acceptance test(?:s|ing)?|uat)\b'}
        present=[label for label,pattern in kinds.items() if re.search(pattern,row['bullet'],re.I)]
        if present:
            st.write('Explicit testing terminology: '+', '.join(present)+'.')
            st.write('Not independently established by this wording: '+', '.join(k for k in kinds if k not in present)+'. Unit tests do not establish the entire compound testing requirement.')
    st.markdown('**Recorded Optimizer Selection**')
    st.caption('Existing fitted résumé: '+('Present' if row.get('in_actual_a') else 'Not present'))
    st.write(('Included in the saved optimized proposal.' if row.get('in_proposed_b') else 'Excluded from the saved optimized proposal.') if recorded else 'Saved proposal membership unavailable.')
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
    st.caption('Estimated support is not factual attestation. Individual native impact is unmeasured; no historical replacement winner is inferred.')


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
