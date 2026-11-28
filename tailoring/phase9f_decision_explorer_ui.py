"""Structured projections of saved Phase 6B and Phase 8 decision receipts."""
from collections import defaultdict
import json

from tailoring.phase9f_decision_summary_ui import (
    project_requirements, render_bullet_summary, render_portfolio_visual, render_project_summary,
    render_ranking_overview, render_wording_pair,
)
from tailoring.phase9f_lead_intro_v310 import VERSION as LEAD_VERSION
from tailoring.phase9f_optimizer_diagnostics_v312b214b4 import obj, rows, strings, title, wording
from tailoring.phase9f_prefit_dedupe_v39 import VERSION as PREFIT_VERSION
from tailoring.portfolio_quality_v311 import _key as portfolio_project_key
from tailoring.project_title_resolution_v1 import mutually_resolve_project
from tailoring.stable_tailoring_ranking import describe_project_requirement_match


def render_raw_json(st, payload, *, key, filename, label='Download JSON'):
    """Both access paths use the original payload, independent of view state."""
    with st.expander('Advanced — Raw JSON'):
        st.json(payload, expanded=False)
        st.download_button(label, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8'),
                           file_name=filename, mime='application/json', key=key+'_raw', on_click='ignore')


def _matching(record, records, pool):
    match, _ = mutually_resolve_project(record, records, pool)
    return match or {}


def _sources(record):
    names = {'resume': 'Selected Base', 'base': 'Selected Base', 'library': 'Evidence Library',
             'evidence_library': 'Evidence Library', 'both': 'Selected Base + Evidence Library'}
    if record.get('currently_in_resume') or record.get('in_evidence_library'):
        return [label for label, field in (('Selected Base', 'currently_in_resume'),
                ('Evidence Library', 'in_evidence_library')) if record.get(field)]
    source = record.get('source')
    return [names.get(source, source)] if source else []


def _allocation_policy(record):
    mode = record.get('allocation_mode')
    if mode == 'all_canonical_before_fitting':
        return 'All canonical wordings admitted before fitting. The configured bullet limit did not cap this allocation.'
    if mode:
        return mode.replace('_', ' ').capitalize() + '. See the saved budget and decision factors below.'
    return 'Allocation policy unavailable.'


def build_explorer(projects, candidates=(), *, report=None, fit=None, application_id=None, generation_id=None):
    """Use frozen inputs and existing audit projections. No ranking is run here."""
    report = obj(report)
    debug = obj(projects.get('deterministic_rule_debug'))
    allocation = obj(debug.get('bullet_allocation'))
    selection_debug = obj(projects.get('selection_debug'))
    competition = obj(debug.get('project_selection_competition'))
    if (competition.get('schema') != 'phase9f-project-selection-competition-v1'
            or not competition.get('candidate_profile_fingerprint')
            or competition.get('candidate_profile_fingerprint') != selection_debug.get('candidate_profile_fingerprint')
            or competition.get('ranking_version') != selection_debug.get('ranking_version')
            or (report and (not report.get('fit_bound') or competition.get('jd_sha256') != report.get('jd_sha256')
                            or competition.get('scoring_version') != obj(report.get('optimizer')).get('reference_scoring_version')))):
        competition = {}
    bound_fit = obj(fit) if report.get('fit_bound') else {}
    snapshot = obj(bound_fit.get('fitting_input_snapshot'))
    invocation = obj(snapshot.get('fitter_invocation'))
    prefit = obj(bound_fit.get('v39_auto_dedupe'))
    prefit_events, prefit_comparisons = defaultdict(list), defaultdict(list)
    if prefit.get('version') == PREFIT_VERSION:
        for event in rows(prefit.get('removals')):
            for role in ('removed', 'retained'):
                prefit_events[wording(event.get('project')), wording(event.get(role))].append(
                    event.get(role+'_saved_evidence_points'))
        for record in rows(prefit.get('project_scores')):
            for entry in rows(record.get('bullets')):
                key = wording(record.get('project')), wording(entry.get('text'))
                prefit_comparisons[key].append(entry.get('saved_evidence_points'))
    preparation_lineage = defaultdict(list)
    for field, version in (('v39_auto_dedupe', PREFIT_VERSION), ('v310_lead_intro', LEAD_VERSION)):
        saved = obj(bound_fit.get(field))
        if saved.get('version') == version:
            for event in rows(saved.get('removals')):
                if event.get('removed') and event.get('retained'):
                    preparation_lineage[wording(event['project']), wording(event['removed'])].append(event)
    ranks = rows(projects.get('candidate_project_ranking'))
    pool = rows(list(candidates or ()))
    plans = rows(allocation.get('projects'))
    recommended = rows(projects.get('recommended_projects'))
    removed = rows(projects.get('projects_to_remove_or_deprioritize'))
    universe = ranks + [row for row in pool if not _matching(row, pool, ranks)]
    if not universe:
        universe = plans or recommended
    traces = obj(report.get('decision_trace'))
    wording_traces = defaultdict(dict)
    for row in rows(traces.get('wordings')):
        wording_traces[row['project']][wording(row['wording'])] = row
    bullet_stages = defaultdict(dict)
    for row in rows(report.get('bullet_stages')):
        bullet_stages[row['project']][wording(row['wording'])] = row
    independent = defaultdict(list)
    scores = obj(report.get('independent_bullet_scores'))
    if scores.get('status') == 'available':
        for row in rows(scores.get('bullets')):
            independent[row['project'], wording(row['wording'])].append(row)
    optimizer_scores = defaultdict(list)
    optimizer = obj(report.get('optimizer'))
    optimizer_receipt = obj(optimizer.get('saved_bullet_score_receipt'))
    if optimizer_receipt.get('status') == 'available':
        for row in rows(optimizer_receipt.get('bullets')):
            optimizer_scores[row['project'], wording(row['wording'])].append(row)
    ordinal = {(row.get('project_id'), row.get('bullet_id')): order
               for order, row in enumerate(rows(allocation.get('selection_trace')), 1)
               if row.get('project_id') and row.get('bullet_id')}
    competing = rows(debug.get('complementary_selection'))
    portfolio = obj(projects.get('portfolio_quality_selection'))
    included_keys = set(strings(portfolio.get('selected_project_ids')))
    excluded_keys = set(strings(portfolio.get('excluded_project_ids')))
    display_projects, display_bullets = [], []
    for record in universe:
        name = title(record)
        rank = _matching(record, universe, ranks)
        candidate = _matching(record, universe, pool)
        plan = _matching(record, universe, plans)
        selected = _matching(record, universe, recommended)
        removal = _matching(record, universe, removed)
        selection = _matching(record, universe, competing)
        stage = _matching(record, universe, rows(report.get('project_stages')))
        base_change = _matching(record, universe, rows(report.get('resume_changes')))
        stage_name = stage.get('project', name)
        recommendation = rank.get('recommendation')
        portfolio_key = portfolio_project_key(rank or record)
        portfolio_status = ('Selected by portfolio' if portfolio_key in included_keys else
                            'Excluded by portfolio before fitting' if portfolio_key in excluded_keys else None)
        if base_change.get('status') == 'Removed' or removal:
            status = 'Removed / deprioritized'
        elif portfolio_key in excluded_keys:
            status = 'Excluded before fitting'
        elif stage.get('actual_readback') == 0 and (plan or selected):
            status = 'Selected, absent from fitted DOCX'
        elif plan or selected or stage.get('actual_readback'):
            status = 'Selected'
        elif recommendation == 'exclude':
            status = 'Rejected'
        elif rank and recommendation in ('include', 'maybe'):
            status = 'Eligible, unselected'
        elif rank:
            status = 'Evaluated, unselected'
        else:
            status = 'Ranking unavailable'
        display_projects.append({
            'Project': name, 'Rank': rank.get('selection_rank'), 'Base ranking score': rank.get('final_score'),
            'Selection score': rank.get('selection_score'), 'Decision': status,
            'Source': ' + '.join(_sources(candidate or rank or record)) or None,
            'Requested limit': plan.get('max_bullets_per_project'), 'Allocated': plan.get('allocated_bullet_count'),
            'Caller': stage.get('generated_or_caller'), 'Prepared': stage.get('fitter_start'), 'Final DOCX': stage.get('actual_readback'),
            'Priority': selected.get('priority', rank.get('priority')), 'Frozen candidate': 'Present' if candidate else None,
            'Recommended action': recommendation, 'Space action': selected.get('space_action', rank.get('space_action')),
            'Portfolio decision': portfolio_status, 'portfolio_key': portfolio_key,
            'rank_receipt': rank, 'allocation': plan, 'selection': selection, 'removal': removal,
        })
        frozen = defaultdict(list)
        for label, field in (('Selected Base', 'resume_evidence'), ('Evidence Library', 'evidence_library_evidence')):
            for text in strings(obj(candidate.get(field)).get('bullets')):
                frozen[wording(text)].append(label)
        receipts = defaultdict(list)
        for receipt in rows(plan.get('bullet_decision_receipts') or selected.get('bullet_decision_receipts')):
            receipts[wording(receipt.get('bullet'))].append(receipt)
        stage_rows = bullet_stages[stage_name]
        for text in dict.fromkeys([*frozen, *receipts, *stage_rows]):
            if not text:
                continue
            receipt = receipts[text][0] if len(receipts[text]) == 1 else {}
            observed = stage_rows.get(text, {})
            decision = wording_traces[stage_name].get(text, {})
            if not decision and not frozen[text] and not receipt:
                continue
            stages = rows(decision.get('stages'))
            proposal = next((step for step in stages if step['stage'] == 'Optimizer challenger'
                             and step['certainty'] == 'Recorded'), {})
            prefit_points = prefit_events[stage_name, text] or prefit_comparisons[stage_name, text]
            points = independent[stage_name, text]
            if not points and stage_name != name:
                points = independent[name, text]
            proxy = optimizer_scores[stage_name, text] if proposal else []
            allocation_status = {True: 'Allocated', False: 'Evaluated, unselected'}.get(receipt.get('selected'))
            state = allocation_status or ('Frozen, no allocation receipt' if frozen[text] else 'No allocation receipt')
            ownership = frozen[text] or [{'base': 'Selected Base', 'library': 'Evidence Library'}.get(s, s)
                                         for s in strings(receipt.get('sources'))]
            if not ownership:
                ownership = [s for s in strings(observed.get('sources')) if not s.startswith('saved allocation:')]
            context = obj(receipt.get('decision_context'))
            lineage = preparation_lineage[wording(stage_name), text]
            display_bullets.append({
                'Project': name, 'Wording': text, 'Source': ' + '.join(dict.fromkeys(ownership)) or None,
                'Portfolio decision': portfolio_status,
                'Decision': state, 'Allocation order': ordinal.get((plan.get('project_id'), receipt.get('bullet_id'))),
                'Allocation evidence': receipt.get('evidence_value'),
                'Weak allocation evidence': obj(context.get('selected')).get('weak_evidence_value'),
                'Pre-fit deduplication points': prefit_points[0] if len(prefit_points) == 1 else None,
                'Independent saved-link points': points[0].get('standalone_weighted_points') if len(points) == 1 else None,
                'Optimizer marginal proxy': proxy[0].get('marginal_in_proposal_points') if len(proxy) == 1 else None,
                'Words': receipt.get('word_count') if receipt else len(text.split()),
                'Caller': _presence(observed.get('generated_or_caller')),
                'Prepared': _presence(observed.get('fitter_start')),
                'Final DOCX': _presence(observed.get('actual_readback')),
                'Optimizer proposal': {True: 'Included', False: 'Considered, excluded'}.get(
                    obj(proposal.get('details')).get('proposed')),
                'Reason': receipt.get('reason'), 'receipt': receipt, 'trace': stages,
                'preparation_lineage': lineage[0] if len(lineage) == 1 else {},
                'saved_links': points[0].get('saved_jd_ids', []) if len(points) == 1 else [],
            })
    return {'projects': display_projects, 'bullets': display_bullets, 'allocation': allocation,
            'selection': selection_debug, 'competition': competition, 'fitter_invocation': invocation,
            'fit_geometry': {key: bound_fit[key] for key in ('page_count', 'page_fill_ratio', 'density_target_max',
                                                            'project_header_layout_used') if bound_fit.get(key) is not None},
            'fit_risk': obj(projects.get('one_page_fit')).get('reason'), 'portfolio': portfolio,
            'scope': {'application_id': report.get('application_id', application_id),
                      'generation_id': report.get('generation_id', generation_id), 'docx_sha256': report.get('docx_sha256'),
                      'source_docx_sha256': obj(snapshot.get('source_artifact')).get('sha256'),
                      'fitting_input_fingerprint': bound_fit.get('fitting_input_fingerprint')},
            'optimizer_status': next((step['details'].get('status') for step in rows(traces.get('whole_document'))
                                      if step['stage'] == 'Native optimizer A/B' and step['certainty'] == 'Recorded'), None)}


def _presence(value):
    return None if value is None else ('Present' if value else 'Absent')


def _filter(st, records, *, key, filters, sorts):
    selected = {}
    with st.container(horizontal=True, gap='small'):
        for field in filters:
            options = sorted({row[field] for row in records if row[field]})
            if options:
                selected[field] = st.multiselect('Filter by '+field.lower(), options,
                                                 key=key+'_filter_'+field, width=180)
        sort = st.selectbox('Sort by', sorts, key=key+'_sort', width=220)
    visible = [row for row in records if all(not choices or row[field] in choices for field, choices in selected.items())]
    return sorted(visible, key=lambda row: (row[sort] is None,
                  -row[sort] if isinstance(row[sort], (float,int)) and sort not in ('Rank','Allocation order')
                  else row[sort] if row[sort] is not None else 0))


def _table(st, records, columns):
    if records:
        st.dataframe([{key: row[key] for key in columns} for row in records], hide_index=True)
    else:
        st.caption('No saved rows match this view.')


def _inspect(st, label, all_rows, visible, key, format_row):
    positions = {id(row): i for i, row in enumerate(all_rows)}
    choice = st.selectbox(label, [positions[id(row)] for row in visible], key=key, index=None,
                          format_func=lambda i: format_row(all_rows[i]))
    return all_rows[choice] if choice is not None else None


def _requirements(st, ids, catalog, label):
    if ids:
        st.caption(label)
        for rid in ids:
            st.write(obj(catalog.get(rid)).get('text') or rid)


def render_project_ranking(st, explorer, *, key):
    st.markdown('#### Project Ranking Explorer')
    visible = _filter(st, explorer['projects'], key=key, filters=('Decision','Source'),
                      sorts=('Rank','Project','Base ranking score','Selection score'))
    render_ranking_overview(st, visible)
    if visible:
        row = _inspect(st, 'Inspect project ranking', explorer['projects'], visible, key+'_detail',
                       lambda item: item['Project'])
        if row is not None:
            _render_project_detail(st, explorer, row, key)
    with st.expander('Ranking table and fit limits'):
        _table(st, visible, ('Project','Rank','Base ranking score','Selection score','Decision','Source',
                            'Priority','Recommended action','Space action','Frozen candidate','Requested limit',
                            'Allocated','Caller','Prepared','Final DOCX'))
        invocation = explorer['fitter_invocation']
        if invocation:
            st.caption(f"Fitter caps · Projects requested {invocation.get('requested_max_projects', 'unavailable')}, "
                       f"effective {invocation.get('max_projects', 'unavailable')} · Bullets per project requested "
                       f"{invocation.get('requested_max_bullets_per_project', 'unavailable')}, effective "
                       f"{invocation.get('max_bullets_per_project', 'unavailable')}.")
        if explorer['selection'].get('project_count_reason'):
            st.caption(explorer['selection']['project_count_reason'])


def _render_project_detail(st, explorer, row, key):
    rank = row['rank_receipt']
    requirements = project_requirements(rank)
    primary_id = obj(rank.get('ranking_explanation')).get('primary_requirement_id')
    primary_match = next((item for item in requirements if primary_id and item.get('requirement_id') == primary_id), {})
    render_project_summary(st, row, requirements)
    plan = row['allocation']
    if row['removal'].get('reason'):
        st.write(row['removal']['reason'])
    if plan:
        st.caption(f"Canonical wordings {plan.get('canonical_bullet_count', 'unavailable')} · "
                   f"Allocated {plan.get('allocated_bullet_count', 'unavailable')} · "
                   f"Prepared {row['Prepared'] if row['Prepared'] is not None else 'unavailable'} · "
                   f"Final DOCX {row['Final DOCX'] if row['Final DOCX'] is not None else 'unavailable'}")
    if requirements:
        with st.expander('JD requirements and supporting evidence'):
            _render_requirement_evidence(st, rank, requirements, key, primary_id)
    _render_portfolio(st, explorer, key)
    with st.expander('Advanced — Project ranking details'):
        if primary_match:
            st.caption('Saved project-level attribution')
            st.text(describe_project_requirement_match(primary_match))
        elif not requirements and rank.get('reason'):
            st.caption('Saved project-level attribution')
            st.text(rank['reason'])
        if rank.get('support_components'):
            st.dataframe([obj(rank['support_components'])], hide_index=True)
        if plan:
            st.caption(_allocation_policy(plan))
        peers = row['selection'].get('near_tied_project_ids') or []
        peers = [p['Project'] for p in explorer['projects'] if p['rank_receipt'].get('project_id') in peers and p is not row]
        if peers:
            st.caption('Recorded near-tie projects · ' + ', '.join(peers))
        competition = explorer['competition']
        steps = rows(competition.get('steps'))
        step = next((step for step in steps if step.get('step') == row['selection'].get('selection_rank')), {})
        if step:
            st.caption('Recorded alternatives at this complementary-selection step')
            st.dataframe(rows(step.get('candidates')), hide_index=True)
        elif rank:
            st.caption('The saved ranking does not record each competitor’s adjusted score at this step.')
        if competition:
            render_raw_json(st, {**explorer['scope'], **competition}, key=key+'_competition',
                            filename=key+'_project_selection_competition.json',
                            label='Download project selection competition (JSON)')


def _render_requirement_evidence(st, rank, requirements, key, primary_id):
    def label(i):
        match = requirements[i]
        strength = match.get('match_label')
        outcome = 'Unmatched' if strength == 'none' else str(strength or 'Unavailable').capitalize()
        return f"{outcome} · {match.get('requirement_text') or match.get('requirement_id')}"

    default = next((i for i, item in enumerate(requirements)
                    if primary_id and item.get('requirement_id') == primary_id), None)
    choice = st.selectbox('Inspect JD requirement', range(len(requirements)), key=key+'_requirement',
                          format_func=label, index=default)
    if choice is None:
        return
    match = requirements[choice]
    st.text(label(choice))
    evidence_ids = strings(match.get('evidence_ids') or match.get('supporting_evidence_ids'))
    records = rows(obj(rank.get('project_relevance')).get('supporting_evidence_records'))
    evidence = [record for record in records if record.get('evidence_id') in evidence_ids]
    snippets = strings(match.get('evidence_snippets') or match.get('supporting_evidence_snippets'))
    if evidence or snippets:
        st.caption('Evidence recorded for the project match. The strength applies to the project as a whole.')
    displayed = set()
    for record in evidence:
        text = record.get('text')
        if text:
            st.text(text)
            displayed.add(text)
        source = record.get('source')
        owner = {'resume': 'Selected Base', 'evidence_library': 'Evidence Library'}.get(source, source)
        provenance = ' · '.join(str(value) for value in (record.get('kind'), owner) if value)
        if provenance:
            st.caption(provenance)
    for snippet in dict.fromkeys(snippets):
        if snippet not in displayed:
            st.text(snippet)
    if not evidence and not snippets:
        st.caption('No supporting evidence is recorded for this requirement.')
    details = [match.get(field) for field in ('capability_id', 'deterministic_rule') if match.get(field)]
    if details:
        st.caption(' · '.join(details))


def _render_portfolio(st, explorer, key):
    portfolio = explorer['portfolio']
    winner = obj(portfolio.get('winner'))
    if not winner:
        return
    baseline = obj(portfolio.get('baseline'))
    slates = [('Selected slate', winner)]
    seen = {tuple(strings(winner.get('selected_keys')))}
    if baseline and tuple(strings(baseline.get('selected_keys'))) not in seen:
        slates.append(('Original slate', baseline))
        seen.add(tuple(strings(baseline.get('selected_keys'))))
    alternative_number = 1
    for candidate in rows(portfolio.get('top_candidates')):
        composition = tuple(strings(candidate.get('selected_keys')))
        if composition and composition not in seen:
            slates.append((f'Alternative {alternative_number}', candidate))
            alternative_number += 1
            seen.add(composition)
    render_portfolio_visual(st, slates)
    with st.expander('Portfolio compositions and constraints'):
        if portfolio.get('minimum_rule'):
            minimum = {'at_least_two': 'At least two projects',
                       'one_project_exception_only_saved_project': 'One project was available'}.get(portfolio['minimum_rule'])
            if minimum:
                st.caption(minimum + ' · The selection had to preserve the saved Required/Core project coverage.')
        if portfolio.get('target_supporting_bullet_depth') is not None:
            st.caption(f"Target supporting bullet depth {portfolio['target_supporting_bullet_depth']}.")
        choice = st.selectbox('Inspect portfolio slate', range(len(slates)),
                              format_func=lambda i: slates[i][0], key=key+'_portfolio')
        slate = slates[choice][1]
        names = {project['portfolio_key']: project['Project'] for project in explorer['projects']}
        selected = strings(winner.get('selected_keys'))
        composition = strings(slate.get('selected_keys'))
        st.markdown('**Projects in this slate**')
        for pid in composition:
            suffix = ' · Added relative to selected slate' if pid not in selected else ''
            st.text(names.get(pid, pid)+suffix)
        excluded = [names.get(pid, pid) for pid in selected if pid not in composition]
        if excluded:
            st.markdown('**Omitted from this slate**')
            for name in excluded:
                st.text(name)
        fields = {'Proxy utility': 'proxy_utility', 'Coverage units': 'coverage_units', 'Depth units': 'depth_units',
                  'Required/Core covered': 'hard_required_core_covered', 'Required/Core lost': 'hard_required_core_lost',
                  'One-bullet projects': 'one_bullet_projects', 'Verified requirements': 'verified_requirement_count',
                  'Uncertain evidence': 'uncertain_evidence'}
        metrics = {label: slate[field] for label, field in fields.items() if slate.get(field) is not None}
        if metrics:
            st.dataframe([metrics], hide_index=True)
        if portfolio.get('version') == 'portfolio-quality-selection-v311-preview-1' and type(slate.get('selected_count')) is int:
            st.caption(f"Project space penalty · {slate['selected_count']} projects × 7 = {slate['selected_count'] * 7} proxy points.")


def _bullet_reason(row):
    for stage in row['trace']:
        if stage['certainty'] != 'Recorded':
            continue
        if stage['stage'] == 'Preparation':
            reasons = [item['reason'] for item in rows(stage['details']) if item.get('reason')]
            if reasons:
                return ' / '.join(reasons)
            return None
        if stage['stage'] == 'Fitting actions':
            reasons = [event['evidence_loss_reason'] for event in rows(stage['details'])
                       if event.get('evidence_loss_reason') and wording(event.get('removed_bullet')) == row['Wording']]
            if reasons:
                return ' / '.join(reasons)
    if row['Portfolio decision'] == 'Excluded by portfolio before fitting':
        return row['Portfolio decision']
    return {'minimum_project_coverage': 'Allocated to meet minimum project coverage.',
            'all_canonical_before_fitting_fill': 'Admitted under the all-canonical allocation policy.'}.get(
                row['Reason'], row['Reason'])


def _wording_pair(row, bullets):
    # Require a recorded transition before presenting two wordings as related by removal.
    for step in row['trace']:
        if step['certainty'] != 'Recorded':
            continue
        if step['stage'] == 'Preparation':
            events = [event for event in rows(step['details']) if event.get('retained')]
            if len(events) == 1:
                retained = events[0]['retained']
                raw = row['preparation_lineage']
                after_points = raw.get('retained_saved_evidence_points') if wording(raw.get('retained')) == wording(retained) else None
                before_points = (raw.get('removed_saved_evidence_points', row['Pre-fit deduplication points'])
                                 if wording(raw.get('retained')) == wording(retained) else row['Pre-fit deduplication points'])
                label = 'Recorded retained wording'
                break
        if step['stage'] == 'Fitting actions' and row['Final DOCX'] == 'Absent':
            events = [event for event in rows(step['details']) if event.get('merged_bullet')
                      and row['Wording'] in [wording(value) for value in strings(event.get('source_bullets'))]]
            if len(events) == 1:
                retained = events[0]['merged_bullet']
                before_points = row['Pre-fit deduplication points']
                after_points = None
                label = 'Recorded fused wording'
                break
    else:
        return []
    candidates = [other for other in bullets if other['Project'] == row['Project'] and other['Wording'] == wording(retained)]
    other = candidates[0] if len(candidates) == 1 else {}
    return [('Discarded wording', row['Wording'], row['Source'], before_points, row['Independent saved-link points']),
            (label, retained, other.get('Source'),
             after_points if after_points is not None else other.get('Pre-fit deduplication points'),
             other.get('Independent saved-link points'))]


def _related_wording_pairs(row, bullets):
    project_bullets = [item for item in bullets if item['Project'] == row['Project']]
    for item in project_bullets:
        pair = _wording_pair(item, project_bullets)
        if pair and (item is row or wording(pair[1][1]) == row['Wording']):
            yield pair


def render_bullet_ranking(st, explorer, catalog, *, key):
    st.markdown('#### Bullet Allocation Explorer')
    visible = _filter(st, explorer['bullets'], key=key, filters=('Project','Decision','Source','Final DOCX'),
                      sorts=('Allocation order','Project','Allocation evidence','Weak allocation evidence',
                             'Pre-fit deduplication points','Independent saved-link points','Optimizer marginal proxy','Words'))
    if visible:
        row = _inspect(st, 'Inspect bullet decision', explorer['bullets'], visible, key+'_detail',
                       lambda item: item['Project'] + ' · ' + item['Wording'])
        if row is not None:
            render_bullet_summary(st, row, _bullet_reason(row))
            for pair in _related_wording_pairs(row, explorer['bullets']):
                render_wording_pair(st, 'Recorded wording comparison', pair)
            with st.expander('Advanced — Bullet evidence and ranking factors'):
                _render_bullet_details(st, row, catalog)
    with st.expander('Bullet table and allocation limits'):
        _table(st, visible, ('Project','Allocation order','Wording','Source','Decision','Allocation evidence',
                             'Weak allocation evidence','Pre-fit deduplication points','Independent saved-link points',
                             'Optimizer marginal proxy','Words','Prepared','Final DOCX','Optimizer proposal','Reason'))
        st.caption('Allocation points order the initial slate. Pre-fit points compare similar wordings during preparation. '
                   'Independent saved-link points apply to exact wordings. The optimizer proxy describes its proposal.')
        if explorer['fit_risk']:
            st.caption('Saved pre-fit estimate · '+explorer['fit_risk'])
        if explorer['fit_geometry']:
            st.dataframe([{field.replace('_', ' ').capitalize(): value
                           for field, value in explorer['fit_geometry'].items()}], hide_index=True)
        if explorer['optimizer_status']:
            st.caption('Saved whole-document optimizer verification · '+explorer['optimizer_status'])
        allocation = explorer['allocation']
        if allocation:
            st.caption(_allocation_policy(allocation))
            st.dataframe([{'Base budget': allocation.get('base_bullet_budget'),
                           'Available slots': allocation.get('total_available_slots'),
                           'Allocated total': allocation.get('total_allocated_bullets')}], hide_index=True)


def _render_bullet_details(st, row, catalog):
    receipt = row['receipt']
    for field, label in (('direct_requirement_ids','Direct allocation links'),
                         ('supported_requirement_ids','Supported allocation links'),
                         ('weak_requirement_ids','Weak allocation links')):
        _requirements(st, strings(receipt.get(field)), catalog, label)
    _requirements(st, row['saved_links'], catalog, 'Independent saved links')
    for stage in row['trace']:
        if stage['stage'] == 'Fitting actions' and stage['certainty'] == 'Recorded':
            render_trace_stage(st, stage)
    context = obj(receipt.get('decision_context'))
    factors = strings(context.get('factor_order'))
    selected = obj(context.get('selected'))
    peer = obj(context.get('best_opposite_source_peer_at_step'))
    if context.get('decision_kind') == 'all_canonical_admission':
        st.caption('The allocation step admitted all canonical alternatives. A peer and its factors explain order only.')
    if peer.get('bullet'):
        st.text('Recorded opposite-source peer · '+peer['bullet'])
    if factors:
        st.dataframe([{'Factor': name.replace('_', ' '), 'Selected': value, 'Peer': comparison}
                      for name, value, comparison in zip(factors, selected.get('rank_tuple', ()),
                      (peer.get('rank_tuple') or [None]*len(factors)))], hide_index=True)


def render_trace_stage(st, stage):
    st.caption(stage['stage']+' · '+stage['certainty'])
    details = stage['details']
    if isinstance(details, str):
        st.write(details)
    elif stage['stage'] == 'Preparation':
        for item in rows(details):
            st.write('**'+item['name']+'** · '+(item.get('reason') or 'Reason unavailable'))
            if item.get('retained'):
                st.write('Recorded retained wording · '+item['retained'])
    elif isinstance(details, dict):
        fields = {name.replace('_', ' ').capitalize(): ', '.join(map(str, value)) if isinstance(value, list) else value
                  for name, value in details.items() if value is not None and name != 'trials'}
        if fields:
            st.dataframe([fields], hide_index=True)
        if details.get('trials'):
            st.dataframe(details['trials'], hide_index=True)
    elif rows(details):
        st.dataframe(rows(details), hide_index=True)


def render_project_tailoring_explorers(st, projects, candidates, *, application_id, generation_id):
    """Replace the primary raw panels while preserving their original datasets."""
    from tailoring.phase9f_v365_jd_evidence import requirement_catalog
    explorer = build_explorer(projects, candidates, application_id=application_id, generation_id=generation_id)
    allocation_payload = obj(projects.get('deterministic_rule_debug')).get('bullet_allocation', {})
    prefix = f'phase9f_app_{application_id}_{generation_id or "working"}'
    for label, slug, payload in (
        ('Projects to remove or deprioritize', 'projects_to_remove_or_deprioritize',
         projects.get('projects_to_remove_or_deprioritize', [])),
        ('All candidate projects scored', 'candidate_project_ranking', projects.get('candidate_project_ranking', [])),
        ('Phase 6B.2 bullet allocation', 'bullet_allocation', allocation_payload),
        ('Full tailored projects JSON', 'tailored_projects', projects),
    ):
        key = prefix+'_'+slug
        with st.expander(label):
            if slug == 'candidate_project_ranking':
                render_project_ranking(st, explorer, key=key)
            elif slug == 'bullet_allocation':
                render_bullet_ranking(st, explorer, requirement_catalog(None, projects), key=key)
            elif slug == 'projects_to_remove_or_deprioritize':
                if payload:
                    st.dataframe([{'Project': title(row), 'Recorded reason': row.get('reason')}
                                  for row in rows(payload)], hide_index=True)
                else:
                    st.caption('No saved removal or deprioritization recommendations.')
            else:
                _table(st, explorer['projects'], ('Project', 'Rank', 'Decision', 'Allocated', 'Recommended action'))
            render_raw_json(st, payload, key=key, filename=key+'.json')

