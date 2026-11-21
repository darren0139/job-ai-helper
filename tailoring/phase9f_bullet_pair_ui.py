"""Read-only Base/Library decisions, with explicitly invoked proxy testing."""
from __future__ import annotations

from hashlib import sha256
import json

MISSING = 'Selection rationale unavailable for this saved generation.'
UNMEASURED = 'No independent Base-versus-Library winner measured.'


def anchor_id(key):
    return 'b4-compare-'+sha256(key.encode()).hexdigest()[:16]


def selection_available(calc, audit, result, report, jd):
    """Reject known stale display scopes; never upgrade an unavailable receipt."""
    if calc.get('status') != 'available':
        return False
    expected = report.get('raw_jd_text')
    if expected and expected != jd:
        return False
    if (audit.get('docx_sha256') and result.get('a_docx_sha256')
            and audit['docx_sha256'] != result['a_docx_sha256']):
        return False
    if any(type(r.get('in_proposed_b')) is not bool for r in calc.get('rows', ())):
        return False
    if audit.get('verified') and audit.get('projects'):
        owners = {}
        for group in audit['projects']:
            for field, tag in [('base', 'Selected Base'), ('library', 'Evidence Library'), ('final', 'Current final')]:
                for bullet in group.get(field, ()):
                    owners.setdefault((group['project'], bullet['text']), set()).add(tag)
        if any(set(r['sources']) - owners.get((r['project'], r['bullet']), set()) for r in calc.get('rows', ())):
            return False
    return True


def related_libraries(rows, base):
    """Same-project exact wording or grounded shared links, never proximity alone."""
    ids = set(base.get('native_requirement_ids', ())) | set(base.get('traceable_lexical_link_ids', ()))
    related = [r for r in rows if r['project'] == base['project'] and 'Evidence Library' in r['sources']
               and (r['bullet'] == base['bullet'] or ids.intersection(
                   set(r.get('native_requirement_ids', ())) | set(r.get('traceable_lexical_link_ids', ()))))]
    return sorted(related, key=lambda r: (r['bullet'] == base['bullet'], r['bullet']))


def selection_explanation(base, library, recorded):
    if not recorded:
        return {'case': 'unavailable', 'text': MISSING}
    if base['bullet'] == library['bullet']:
        return {'case': 'shared', 'text': 'Shared Base + Library wording. One candidate with both source provenances; no source winner.'}
    a, b = bool(base.get('in_proposed_b')), bool(library.get('in_proposed_b'))
    if a and b:
        text = 'Both wordings are included in the saved optimized combination. Neither is a winner over the other.'
        case = 'both_included'
    elif not a and not b:
        text = ('Both wordings are outside the saved optimized combination. The eligible pool records their availability; '
                'an individual rejection cause was not recorded.')
        case = 'both_excluded'
    else:
        included = 'Base Resume' if a else 'Evidence Library'
        excluded = 'Evidence Library' if a else 'Base Resume'
        text = (f'{included} wording is included in the saved optimized combination; {excluded} wording is not included. '
                'This records membership, not an independently tested source winner.')
        case = 'base_included' if a else 'library_included'
    return {'case': case, 'text': text}


def request_comparison(st, key, project, bullet):
    """A widget callback changes inspection state only, never the selected slate."""
    st.session_state[key+'_request'] = {'project': project, 'bullet': bullet}


def scope_key(calc, proposal, audit, projects, jd):
    data = [calc, proposal, audit, projects, jd]
    return sha256(json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()[:16]


def native_trials(binding, *, audit, catalog, jd, scorer, project, wordings):
    """Use the existing fail-closed importer; only return controlled additions."""
    if (not isinstance(binding, dict) or not isinstance(binding.get('data'), bytes)
            or binding.get('scoring_version') != scorer or not scorer):
        return []
    from tailoring.phase9f_v37_trial_view import controlled_trial_rows
    try:
        rows = controlled_trial_rows(binding.get('data', b''), receipt_sha256=binding.get('receipt_sha256'),
            jd_sha256=sha256(jd.encode()).hexdigest(), scoring_version=scorer,
            baseline_sha256=binding.get('baseline_sha256'), trial_sha256=binding.get('trial_sha256'),
            catalog=catalog, audit=audit)
    except (TypeError, ValueError, KeyError):
        return []
    matched = [r for r in rows if r['project'] == project and r['wording'] in wordings and r['native_delta'] is not None]
    if not matched:
        return []
    receipt = json.loads(binding['data'])
    for document in (receipt['baseline'], receipt['trial']):
        requirements = {r['id']: r for r in document['requirements']}
        if requirements.keys() != catalog.keys() or any(
                (r['text'], r['importance']) != (catalog[rid]['text'], catalog[rid]['importance'])
                for rid, r in requirements.items()):
            return []
    from tailoring.phase9f_v37_document_trial import compare_native_trials, RANK
    comparison = compare_native_trials(receipt['baseline'], receipt['trial'])
    before = {r['id']: r for r in receipt['baseline']['requirements']}
    after = {r['id']: r for r in receipt['trial']['requirements']}
    hard_losses = [r['text'] for rid, r in before.items() if r['importance'] in {'core', 'required', 'deal_breaker'}
                   and (RANK[after[rid]['match_label']] < RANK[r['match_label']]
                        or (type(after[rid].get('evidence_strength')) is int and type(r.get('evidence_strength')) is int
                            and after[rid]['evidence_strength'] < r['evidence_strength']))]
    return [{**r, 'hard_losses': hard_losses, 'baseline_sha256': binding['baseline_sha256'],
             'trial_sha256': binding['trial_sha256'], 'comparison': comparison} for r in matched]


def _card(st, title, row, recorded, proposal):
    st.markdown('##### ' + title)
    st.write(row['bullet'])
    st.caption('Source provenance · ' + ' + '.join(row['sources']))
    st.write('Existing fitted résumé · ' + (('Present' if row.get('in_actual_a') else 'Absent')
        if recorded or row.get('existing_membership_verified') else 'Unknown'))
    st.write('Optimized proposal · ' + (('Included' if row.get('in_proposed_b') else 'Excluded') if recorded else 'Unknown'))
    actual_words = len(row['bullet'].split())
    st.caption('Word count · '+str(actual_words))
    if row.get('words') != actual_words:
        st.caption('Saved selection word cost · '+str(row.get('words', 'Unavailable'))+
                   '; displayed word count uses the exact wording. The saved objective is unchanged.')
    for link in row['jd_links']:
        st.write(f"{link['text']} ({link['importance'].replace('_', ' ').title()})")
        st.caption(link['status'])
        for role, evidence in link['native_evidence'].items():
            st.caption(f"{role.title()} document · {evidence['match_label']} · strength {evidence.get('strength', 'Unknown')}/5")
            st.write(evidence['excerpt'])
    if not row['jd_links']:
        st.caption('No resolved saved JD links or verified native excerpts.')
    st.caption('Factual-review status · ' + (
        'Proposal-level Base-only review required; no individual attestation inferred.' if recorded and proposal.get('requires_base_review') else
        'No proposal-level review flag recorded; this is not independent attestation.' if recorded else
        'Unknown without a compatible selection receipt.'))


def _proxy(st, *, base, library, calc, proposal, audit, projects, jd, key, recorded):
    st.markdown('##### Test mathematical selection impact (proxy only)')
    st.caption('Explicitly runs forced inclusion/exclusion for one bullet. It does not render DOCX/PDF, '
               'call a model, measure native Job Match, or change the saved selection. Other bullets may change in each solve.')
    if not recorded or not proposal.get('source_comparison') or not audit.get('verified'):
        st.caption('A compatible saved source pool and selection receipt are required for a mathematical test.')
        return
    options = [base] if base['bullet'] == library['bullet'] else [base, library]
    chosen = st.selectbox('Wording to test', range(len(options)),
        format_func=lambda i: ('Base Resume' if i == 0 else 'Evidence Library') + ' · ' + options[i]['bullet'], key=key+'_proxy_wording')
    row = options[chosen]
    digest = scope_key(calc, proposal, audit, projects, jd)
    identity = sha256((row['project']+'\0'+row['bullet']).encode()).hexdigest()[:16]
    cache = key+'_proxy_'+digest+'_'+identity
    if st.button('Test mathematical selection impact (proxy only)', key=key+'_proxy_run'):
        from tailoring.phase9f_certified_selection_v36 import compare_forced_bullet
        st.session_state[cache] = compare_forced_bullet(audit, projects, proposal,
            project=row['project'], bullet=row['bullet'])
    outcome = st.session_state.get(cache)
    if not isinstance(outcome, dict):
        st.caption('No measured proxy result for this wording in the current evidence scope.')
        return
    if (outcome.get('status') != 'calculated' or outcome.get('project') != row['project']
            or outcome.get('bullet') != row['bullet']):
        st.warning('Proxy result unavailable or incompatible. ' + str(outcome.get('reason') or ''))
        return
    labels = {'force_in_proxy_preferred': 'Including this bullet was preferred in the constrained proxy test.',
              'force_out_proxy_preferred': 'Excluding this bullet was preferred in the constrained proxy test.',
              'proxy_tie': 'The constrained proxy tests tied.', 'not_proven': 'A feasible optimum was not established in both tests.'}
    st.info(labels.get(outcome.get('comparison'), 'Proxy outcome unavailable.'))
    for name, title in [('force_in', 'Forced inclusion'), ('force_out', 'Forced exclusion')]:
        detail = outcome.get(name) or {}
        st.write(f"{title} · {detail.get('status', 'Unavailable')} · words {detail.get('selected_words', 'Unavailable')}")
        st.json(detail.get('objectives') or [])
    st.caption('This is not a direct Base-versus-Library swap and does not explain the historical decision causally. Native impact remains unmeasured.')


def render_pair_comparison(st, *, ranked, recorded, calc, audit, proposal, result,
                           catalog, projects, jd, report, key, project='All projects', offline_trial=None):
    """One local panel; no optimization or native rendering on passive display."""
    st.markdown('<span id="'+anchor_id(key)+'"></span>', unsafe_allow_html=True)
    st.markdown('### Compare Base vs Library')
    st.caption('Compare exact source wordings and recorded evidence in one place. A shared requirement establishes '
               'related evidence, not that these bullets are mutually exclusive substitutes.')
    if not recorded:
        st.info(MISSING)
    names = sorted({r['project'] for r in ranked if 'Selected Base' in r['sources']})
    if project != 'All projects':
        names = [p for p in names if p == project]
    if not names:
        st.info('No Base Resume bullet is recorded for this project scope.')
        return
    request = st.session_state.pop(key+'_request', None)
    if request and request['project'] in names:
        st.session_state[key+'_compare_project'] = request['project']
    chosen_project = st.selectbox('Comparison project', names, key=key+'_compare_project')
    scope = [r for r in ranked if r['project'] == chosen_project]
    from tailoring.phase9f_wording_explanation_ui import render_source_wordings
    source_catalog = catalog if not report.get('raw_jd_text') or report['raw_jd_text']==jd else {}
    if not source_catalog:st.caption('Standalone estimate unavailable: no compatible readable JD requirement context.')
    render_source_wordings(st, scope=scope, catalog=source_catalog, recorded=recorded,
        proposal=proposal, key=key+'_'+sha256(chosen_project.encode()).hexdigest()[:12])
    st.markdown('#### Strict saved-evidence Base/Library pair')
    bases = [r for r in scope if 'Selected Base' in r['sources']]
    project_key = key+'_'+sha256(chosen_project.encode()).hexdigest()[:12]
    requested_library = None
    if request and request['project'] == chosen_project:
        matching = [i for i, row in enumerate(bases) if row['bullet'] == request['bullet']]
        if not matching:
            matching = [i for i, row in enumerate(bases)
                        if any(lib['bullet'] == request['bullet'] for lib in related_libraries(scope, row))]
            requested_library = request['bullet']
        if matching:
            st.session_state[project_key+'_base'] = matching[0]
        else:
            st.info('The requested bullet has no grounded Base/Library pair. No unrelated wording was selected for it.')
    chosen = st.selectbox('Base Resume wording', range(len(bases)), format_func=lambda i: bases[i]['bullet'], key=project_key+'_base')
    base = bases[chosen]
    libraries = related_libraries(scope, base)
    if not libraries:
        _card(st, 'Base Resume bullet', base, recorded, proposal)
        st.info('No related Library alternative is established by exact wording or traceable shared JD evidence. '
                'Other same-project Library bullets remain available in the inspector; they are not silently paired.')
        st.markdown('#### JD Relevance Comparison')
        st.caption('Pair-level estimated relevance is unavailable because a grounded competing pair has not been established.')
        st.markdown('#### Why was this wording selected?')
        st.caption('Only the recorded membership shown above is available. An individual selection cause and native replacement impact were not measured.')
        return
    pair_key = project_key+'_'+sha256(base['bullet'].encode()).hexdigest()[:12]
    if requested_library:
        for i, row in enumerate(libraries):
            if row['bullet'] == requested_library:
                st.session_state[pair_key+'_library'] = i
    choice = st.selectbox('Related Evidence Library wording', range(len(libraries)),
        format_func=lambda i: libraries[i]['bullet'], key=pair_key+'_library')
    library = libraries[choice]
    pair_key += '_'+sha256(library['bullet'].encode()).hexdigest()[:12]
    # Scope styles to this one container; Streamlit's default breakpoint is narrower than 760px.
    st.markdown('<style>@media(max-width:800px){.st-key-'+pair_key+'_cards '
        '[data-testid="stHorizontalBlock"]{flex-direction:column!important}.st-key-'+pair_key+'_cards '
        '[data-testid="stColumn"]{width:100%!important;flex:1 1 100%!important;min-width:0!important}}</style>', unsafe_allow_html=True)
    with st.container(key=pair_key+'_cards', border=True):
        if base['bullet'] == library['bullet']:
            _card(st, 'Shared Base + Library wording', base, recorded, proposal)
        else:
            left, right = st.columns(2, gap='large')
            _card(left, 'Base Resume bullet', base, recorded, proposal)
            _card(right, 'Evidence Library bullet', library, recorded, proposal)
    from tailoring.phase9f_bullet_relevance_diagnostic import compare_ranked_bullets
    diagnostic = compare_ranked_bullets(base, library, catalog,
        [r for r in ranked if recorded and r.get('in_proposed_b')])
    st.markdown('#### JD Relevance Comparison')
    from tailoring.bullet_choice_estimated import estimate_pair
    from tailoring.bullet_choice_lab_ui import render_estimated
    estimated = estimate_pair(base['bullet'], library['bullet'],
        list(catalog.values()), selected=[r['bullet'] for r in ranked
            if recorded and r.get('in_proposed_b') and r['bullet'] not in {base['bullet'], library['bullet']}])
    render_estimated(st, estimated)
    st.markdown('**Verified Evidence — saved document citations**')
    st.caption('Diagnostic version · '+diagnostic['version'])
    st.info(diagnostic['outcome'])
    st.write(diagnostic.get('reason', ''))
    st.caption('Different assessment bases: the estimate compares explicit wording; saved-document evidence compares only bound recorded citations. Equivalent wording relevance can coexist with stronger Base citation support. An uncited alternative is not disproven. Neither establishes a historical optimizer cause. Actual membership and measured native impact are separate below.')
    st.caption('The wording estimate compares explicit sentence contents; saved-document evidence compares bound citations available in recorded documents. Equivalent wording relevance can coexist with stronger recorded Base support when citations differ. An uncited alternative is not disproven. Neither assessment establishes an individual optimizer selection cause or measured native impact.')
    for label, field in [('Shared recorded support', 'shared'), ('Base-only recorded support', 'base_only'),
                         ('Library-only recorded support', 'library_only'),
                         ('Already supported elsewhere', 'already_supported_elsewhere')]:
        st.write(label+' · '+('; '.join(catalog[r]['text']+' ('+catalog[r]['importance']+')'
                                      for r in diagnostic.get(field, [])) or 'None established'))
    for role in ('base', 'library'):
        st.caption(role.title()+' explicit testing terminology · '+(', '.join(diagnostic.get('explicit_testing_terms', {}).get(role, [])) or 'None'))
        st.caption(role.title()+' testing activities not established by this wording · '+(', '.join(diagnostic.get('unestablished_testing_terms', {}).get(role, [])) or 'None listed'))
    st.caption(diagnostic.get('terminology_limit', ''))
    for warning in diagnostic.get('warnings', []): st.warning(warning)
    st.caption('Relevance is a versioned evidence diagnostic, not native Job Match. Weak or transferable evidence is partial support; source provenance is not independent factual attestation.')
    st.markdown('#### Why was this wording selected?')
    explanation = selection_explanation(base, library, recorded)
    st.info(explanation['text'])
    from tailoring.phase9f_bullet_relevance_diagnostic import selection_alignment
    estimated_alignment = {'Base stronger':'Base has stronger estimated relevance.',
                           'Library stronger':'Library has stronger estimated relevance.'}.get(estimated['outcome'], estimated['outcome'])
    st.caption('Estimated preference versus saved selection: '+selection_alignment(
        estimated_alignment, base.get('in_proposed_b'), library.get('in_proposed_b'), recorded))
    if explanation['case'] not in {'shared', 'unavailable'}:
        st.caption(UNMEASURED + ' Whole-slate objective measurements are context, not a per-bullet causal explanation.')
    st.markdown('#### Native Job Match impact')
    st.caption('Native bullet impact unmeasured unless a compatible controlled trial is explicitly displayed below.')
    if result.get('hard_regressed_ids'):
        st.warning('The recorded challenger has Required/Core regression. An increased overall native score does not establish a safe challenger.')
    with st.expander('Saved evidence differences and selection constraints', expanded=False):
        left = {r['id']: r for r in base['jd_links']}
        right = {r['id']: r for r in library['jd_links']}
        for rid in sorted(left.keys() | right.keys()):
            req = catalog[rid]
            st.write(f"{req['text']} ({req['importance'].replace('_', ' ').title()})")
            if rid in left and rid in right:
                st.caption('Shared requirement identity; counted once, not extra coverage.')
            for title, links in [('Base', left), ('Library', right)]:
                st.caption(title+' · '+(links[rid]['status'] if rid in links else 'No recorded link or native excerpt'))
        for title, row, other in [('Base', base, library), ('Library', library, base)]:
            unique = set(row.get('native_requirement_ids', ())) - set(other.get('native_requirement_ids', ()))
            st.write(title+'-only verified native excerpts · '+('; '.join(catalog[r]['text'] for r in sorted(unique)) or 'None recorded'))
            terms = set(row.get('jd_wide_term_cues', ())) - set(other.get('jd_wide_term_cues', ()))
            st.caption(title+'-only JD terminology cues · '+(', '.join(sorted(terms)) or 'None'))
        st.write(f"Library wording saves {len(base['bullet'].split())-len(library['bullet'].split()):+d} words relative to Base wording.")
        st.caption('Word differences do not prove additional useful content or a one-page fit benefit. '
                   'Saved links, lexical cues and native excerpts are separate; none is a measured per-bullet Job Match contribution.')
        if recorded:
            st.write('Recorded whole-slate objectives and constraints')
            st.json({'objective_stages': calc.get('objective_stages') or [], 'summary': calc.get('summary') or {},
                'constraints': (proposal.get('mathematical_certificate') or {}).get('constraints') or
                               (proposal.get('selection_receipt') or {}).get('constraints') or {}})
        else:
            st.caption(MISSING)
    trials = native_trials(offline_trial, audit=audit, catalog=catalog, jd=jd,
        scorer=(report.get('stable_analysis') or {}).get('scoring_version'), project=chosen_project,
        wordings={base['bullet'], library['bullet']})
    if trials and st.checkbox('Show saved controlled native trial (read-only)', key=pair_key+'_native'):
        st.caption('Offline controlled addition; separate from the current application recommendation or approval.')
        for item in trials:
            st.write(item['wording'])
            st.write(f"{item['requirement']} ({item['importance']}) · {item['before_label']} → {item['after_label']}")
            st.write(f"Measured native Job Match delta {item['native_delta']:+g}; {item['word_delta']:+d} words; both PDFs one page.")
            st.caption('Baseline DOCX SHA-256 · '+item['baseline_sha256'])
            st.caption('Trial DOCX SHA-256 · '+item['trial_sha256'])
            st.caption('Scorer · '+str((report.get('stable_analysis') or {}).get('scoring_version'))+
                       ' · JD SHA-256 · '+sha256(jd.encode()).hexdigest())
            if item['hard_losses']:
                st.warning('Recorded Required/Core evidence regression: '+'; '.join(item['hard_losses'])+
                           '. A higher total is not a safe-challenger result.')
            st.caption('This tests adding this exact bullet, not a Base-versus-Library swap. It does not establish a source winner.')
    with st.expander('Optional mathematical counterfactual', expanded=False):
        _proxy(st, base=base, library=library, calc=calc, proposal=proposal, audit=audit,
               projects=projects, jd=jd, key=pair_key, recorded=recorded)
