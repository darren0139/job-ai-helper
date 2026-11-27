"""Read-only evidence trail. No scoring, rendering, persistence or optimizer calls."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

VERSION = 'v312b214b4-optimizer-diagnostics-v1'


def obj(x):
    return x if isinstance(x, dict) else {}


def rows(x):
    return [r for r in x if isinstance(r, dict)] if isinstance(x, list) else []


def strings(x):
    return [s for s in x if isinstance(s, str) and s.strip()] if isinstance(x, list) else []


def wording(x):
    return ' '.join(x.split()) if isinstance(x, str) else ''


def title(p):
    return wording(p.get('display_title') or p.get('title') or p.get('project'))


def project_rows(value):
    return rows(value if isinstance(value, list) else obj(value).get('recommended_projects'))


def indexed(value):
    result = defaultdict(list)
    for p in project_rows(value):
        if title(p):
            result[title(p)].append(p)
    return result


def detach(value, active=None, depth=0):
    """Copy diagnostic receipts, never mutate them; mark cycles and non-JSON data."""
    if depth > 70:
        return {'diagnostic_omission': 'depth limit'}
    if isinstance(value, (dict, list, tuple)):
        active = set() if active is None else active
        if id(value) in active:
            return {'diagnostic_omission': 'cyclic receipt'}
        active.add(id(value))
        try:
            if isinstance(value, dict):
                return {str(k): detach(v, active, depth+1) for k,v in value.items()}
            return [detach(v, active, depth+1) for v in value]
        finally:
            active.remove(id(value))
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        import math
        return value if math.isfinite(value) else None
    return {'diagnostic_omission': 'non-JSON value', 'type': type(value).__name__}


def _decision_trace(projects, bullets, fit, result):
    """Explain exact wording presence or a bound recorded event at each stage."""
    from tailoring.phase9f_lead_intro_v310 import VERSION as LEAD_VERSION
    from tailoring.phase9f_prefit_dedupe_v39 import VERSION as DEDUPE_VERSION

    by_project = {row['project']: row for row in projects}
    prefit_events = defaultdict(list)
    for field, version, label in (('v39_auto_dedupe', DEDUPE_VERSION, 'Same-work deduplication'),
                                  ('v310_lead_intro', LEAD_VERSION, 'Project lead selection')):
        receipt = obj(fit.get(field))
        if receipt.get('version') != version:
            continue
        for event in rows(receipt.get('removals')):
            if event.get('removed') and event.get('project'):
                prefit_events[(wording(event['project']), wording(event['removed']))].append({
                    'name': label, 'reason': event.get('selection_reason') or event.get('reason'),
                    'retained': event.get('retained'),
                })

    active_events = defaultdict(list)
    for event in rows(fit.get('remaining_active_reductions')):
        for text in set(strings([event.get('removed_bullet'), event.get('merged_bullet')])
                        + strings(event.get('source_bullets'))):
            active_events[(wording(event.get('project')), wording(text))].append(event)
    proposed = defaultdict(list)
    comparison = obj(obj(result.get('proposal')).get('source_comparison'))
    for project in rows(comparison.get('projects')):
        for candidate in rows(project.get('candidates')):
            proposed[(wording(project.get('project')), wording(candidate.get('text')))].append(candidate)

    def stage(name, certainty, details):
        return {'stage': name, 'certainty': certainty, 'details': details}

    def presence(name, count):
        detail = ('This exact wording is absent.' if count == 0 else
                  f'Exact wording occurrences · {count}' if count is not None else 'No matching stage receipt.')
        return stage(name, 'Observed' if count is not None else 'Unavailable', detail)

    trace = []
    for row in bullets:
        key = (row['project'], row['wording'])
        project = by_project[row['project']]
        sources = [label for label in row['sources'] if not label.startswith('saved allocation:')]
        selected = row['saved_selected']
        steps = [
            stage('Frozen evidence', 'Observed' if sources else 'Unavailable',
                  ', '.join(sources) if sources else 'No exact Base or Library source established.'),
            stage('Candidate admission', 'Recorded' if selected is not None else 'Unavailable',
                  'An exact wording was present in saved allocation.' if selected is not None
                  else 'No unique allocation record for this wording.'),
            stage('Project ranking', 'Recorded' if project['saved_rank'] is not None else 'Unavailable',
                  {'rank': project['saved_rank'], 'recommendation': project['saved_recommendation'],
                   'reason': project['saved_rank_reason']}),
            stage('Initial selection', 'Recorded' if selected is not None else 'Unavailable',
                  {'selected': selected, 'reason': row['saved_reason'],
                   'strong_links': row['saved_supported_ids'], 'weak_links': row['saved_weak_ids']}),
            presence('Generation or fitter caller', row['generated_or_caller']),
        ]
        if row['generated_or_caller'] and row['fitter_start'] == 0:
            events = prefit_events[key]
            steps.append(stage('Preparation', 'Recorded' if events else 'Cause unknown',
                               events or 'Exact wording was present at the caller and absent at fitter start. No matching preparation event was recorded.'))
        else:
            steps.append(stage('Preparation', 'Unavailable', 'No exact wording change established at this boundary.'))
        steps.append(presence('Fitter input', row['fitter_start']))
        fitting = active_events[key]
        steps.append(stage('Fitting actions', 'Recorded' if fitting else 'Cause unknown',
                           fitting or 'No active fitting action names this exact wording.'))
        steps.extend((presence('Saved fitted wording', row['saved_fitted']),
                      presence('Actual DOCX readback', row['actual_readback'])))
        choices = proposed[key]
        considered = len(choices) == 1 and type(choices[0].get('selected_for_proposed_b')) is bool
        steps.append(stage('Optimizer challenger', 'Recorded' if considered else 'Unavailable',
                           {'proposed': choices[0]['selected_for_proposed_b']} if considered else
                           'No uniquely scoped proposal record for this wording.'))
        trace.append({'project': key[0], 'wording': key[1], 'stages': steps})

    native = [stage('Native optimizer A/B', 'Recorded' if result else 'Unavailable',
                    {'status': result.get('status'), 'stage': result.get('verification_stage'),
                     'reason': result.get('reason'), 'a_score': result.get('a_score'),
                     'b_score': result.get('b_score'), 'required_core_losses': result.get('hard_regressed_ids'),
                     'trials': [{k: trial.get(k) for k in ('trial', 'status', 'verification_stage', 'reason')}
                                for trial in rows(result.get('v35_trial_receipts'))]})]
    winner = result.get('winner') if result.get('status') == 'verified' else None
    native.append(stage('Optimizer document selection', 'Recorded' if winner else 'Unavailable',
                        winner or 'No verified optimizer selection.'))
    return {'wordings': trace, 'whole_document': native}


def build_report(*, application_id, generation_id, projects=None, fit=None, audit=None,
                 result=None, run_mode=None, baseline_report=None, raw_jd_text=None,
                 candidate_pool=None, historical_optimizer=None, phase8=None,
                 docx_bytes=None, optimizer_history=None, independent_scores=None,
                 optimizer_scope=None):
    projects, fit, audit, result = map(obj, (projects, fit, audit, result))
    gen = str(generation_id or '')
    fit_bound = bool(gen and fit.get('generation_id') == gen)
    # A readback audit is not an actual Phase 8 scoring receipt.
    audit_bound = bool(fit_bound and audit.get('verified') is True and audit.get('generation_id') == gen
                       and isinstance(audit.get('docx_sha256'), str) and len(audit['docx_sha256']) == 64)
    notes = []
    if not fit_bound:
        notes.append('No fitting receipt for the requested generation; stage joins withheld.')
    if not audit_bound:
        notes.append('Independent project DOCX readback unavailable; final stage is saved fitting output only.')
    snap = obj(fit.get('fitting_input_snapshot')) if fit_bound else {}
    caller = obj(snap.get('caller_input')).get('projects')
    prepared = obj(snap.get('prepared_initial_state')).get('projects')
    saved_final = fit.get('tailored_projects_used') if fit_bound else None
    stages = {'generated_or_caller': caller, 'fitter_start': prepared, 'saved_fitted': saved_final,
              'actual_readback': audit.get('projects') if audit_bound else None}
    stage_indexes = {k:indexed(v) for k,v in stages.items()}
    # Use frozen caller receipt for provenance where present. Current working controls are not history.
    source = indexed(projects if fit_bound else None)
    if fit_bound and not projects:
        notes.append('Allocation receipts unavailable in supplied project result.')
    notes.append('Allocation receipts are supplied project-result metadata; they are not inferred from the frozen fitter input.')
    pool = indexed(candidate_pool) if fit_bound else {}
    ranks = indexed(obj(caller).get('candidate_project_ranking') or projects.get('candidate_project_ranking')) if fit_bound else {}
    names = sorted(set(source) | set(pool) | set(ranks) | set().union(*(set(x) for x in stage_indexes.values())))
    active = rows(fit.get('remaining_active_reductions')) if fit_bound else []
    project_table, bullet_table, decisions = [], [], []
    def count_stage(stage, name):
        value = stages[stage]
        if not isinstance(value, list) and not (isinstance(value, dict) and isinstance(value.get('recommended_projects'), list)):
            return None, None
        raw_rows = value if isinstance(value,list) else value['recommended_projects']
        if any(not isinstance(p,dict) or not title(p) for p in raw_rows):
            return None, None
        matches = stage_indexes[stage].get(name, [])
        if len(matches)>1:
            return None, None
        if not matches:
            return 0, Counter()
        row = matches[0]
        if stage == 'actual_readback':
            words = [x.get('text') for x in rows(row.get('final'))]
        else:
            if not isinstance(row.get('draft_bullets'), list):
                return None, None
            words = row['draft_bullets']
        c = Counter(wording(w) for w in words if wording(w))
        return sum(c.values()), c
    for name in names:
        counts = {k:count_stage(k,name) for k in stages}
        rr = ranks.get(name, [])
        rank = rr[0] if len(rr)==1 else {}
        project_table.append({'project':name, **{k:v[0] for k,v in counts.items()},
                              'saved_rank':rank.get('selection_rank'), 'saved_recommendation':rank.get('recommendation'),
                              'saved_rank_reason':rank.get('reason')})
        evidence = defaultdict(set)
        source_rows = source.get(name, [])
        pool_rows = pool.get(name, [])
        if len(pool_rows)==1:
            for key, label in [('resume_evidence','Selected Base / résumé pool'),('evidence_library_evidence','Evidence Library')]:
                for text in strings(obj(pool_rows[0].get(key)).get('bullets')):
                    evidence[wording(text)].add(label)
        aa = stage_indexes['actual_readback'].get(name, [])
        if len(aa)==1:
            for key,label in [('base','Selected Base'),('library','Evidence Library')]:
                for item in rows(aa[0].get(key)):
                    if wording(item.get('text')):
                        evidence[wording(item['text'])].add(label)
        receipts = defaultdict(list)
        if len(source_rows)==1:
            for r in rows(source_rows[0].get('bullet_decision_receipts')):
                if wording(r.get('bullet')):
                    receipts[wording(r['bullet'])].append(r)
                    for s in strings(r.get('sources')): evidence[wording(r['bullet'])].add('saved allocation: '+s)
                    decisions.append({'project':name, 'receipt':r})
        all_text = set(evidence) | set(receipts) | set().union(*(set(c) for _,c in counts.values() if c is not None))
        for text in sorted(all_text):
            hits = {k:(c.get(text,0) if c is not None else None) for k,(_,c) in counts.items()}
            removal = [x for x in active if x.get('change_type')=='remove_bullet' and wording(x.get('project'))==name and wording(x.get('removed_bullet'))==text]
            r = receipts[text][0] if len(receipts[text])==1 else {}
            if hits['actual_readback']:
                outcome = 'Exact wording in readback'
            elif hits['saved_fitted']:
                outcome = 'Exact wording in saved fit (not independent readback)'
            elif removal:
                outcome = 'Active exact-wording removal recorded'
            elif hits['fitter_start']:
                outcome = 'Not found as exact final wording' if hits['saved_fitted']==0 else 'Final wording unavailable'
            elif hits['generated_or_caller']:
                outcome = 'Absent from prepared fitter wording' if hits['fitter_start']==0 else 'Prepared wording unavailable'
            else:
                outcome = 'Available / allocation receipt; not proof of rejection'
            bullet_table.append({'project':name,'wording':text,'sources':sorted(evidence[text]),**hits,
                'outcome':outcome,'saved_selected':r.get('selected'),'saved_reason':r.get('reason'),
                'saved_supported_ids':strings(r.get('supported_requirement_ids')),
                'saved_weak_ids':strings(r.get('weak_requirement_ids')),
                'active_removal_reasons':[x.get('evidence_loss_reason') for x in removal],
                'ambiguous_allocation_receipt':len(receipts[text])>1})
    proposal = obj(result.get('proposal'))
    version = result.get('scoring_version') or obj(result.get('a_vs_starting')).get('scoring_version') or obj(historical_optimizer).get('scorer_version')
    reference = obj(obj(baseline_report).get('stable_analysis')).get('scoring_version')
    phase8 = obj(phase8)
    jd_hash = sha256(raw_jd_text.encode('utf-8')).hexdigest() if isinstance(raw_jd_text,str) and raw_jd_text else None
    doc_hash = sha256(docx_bytes).hexdigest() if isinstance(docx_bytes,bytes) else (audit.get('docx_sha256') if audit_bound else None)
    phase8_bound = bool(fit_bound and doc_hash and jd_hash and phase8.get('application_id') == application_id
                       and phase8.get('generation_id') == gen and phase8.get('comparison_valid') is True
                       and obj(phase8.get('document_analysis')).get('final_document_sha256') == doc_hash
                       and obj(obj(phase8.get('document_analysis')).get('final')).get('jd_text_sha256') == jd_hash
                       and (not audit_bound or audit['docx_sha256'] == doc_hash))
    gaps, native = [], None
    if phase8_bound:
        after = obj(phase8.get('after_stable_analysis'))
        reference = after.get('scoring_version')
        native = {'authority_note':'Matches supplied DOCX bytes or audit digest and exact JD; historical unless independently established current. Offline fitting snapshot may lack its own DOCX digest.', 'verification_id':phase8.get('verification_id'), 'scoring_version':reference,
                  'verdict':phase8.get('verdict'), 'comparison':phase8.get('comparison'), 'requirements':[]}
        for r in rows(after.get('canonical_requirements')):
            rid = r.get('requirement_id')
            ev = [{'section':x.get('section'),'text':x.get('text'),'reason':x.get('capability_evidence_reason') or x.get('reason')} for x in rows(r.get('evidence'))]
            item = {'requirement_id':rid,'text':r.get('text'),'importance':r.get('importance'),
                    'semantic_type':r.get('semantic_type'),'match':r.get('match_label'),'score_eligible':r.get('score_eligible'),'evidence':ev}
            native['requirements'].append(item)
            if r.get('score_eligible') is True and r.get('match_label') in ('none','weak','transferable') and isinstance(rid,str):
                linked = [{'project':x['project'],'wording':x['wording'],'outcome':x['outcome']} for x in bullet_table
                          if rid in x['saved_supported_ids'] or rid in x['saved_weak_ids']]
                rank_clues = [{'project':name,'match':m.get('match_label'),'snippets':strings(m.get('evidence_snippets'))} for name, rr in ranks.items() if len(rr)==1 for m in rows(rr[0].get('requirement_matches')) if m.get('requirement_id')==rid and m.get('match_label') in ('direct','transferable','weak')]
                gaps.append({**item,'historical_project_rank_clues':rank_clues,'historical_saved_link_candidates':linked,'note':'Saved links are clues, not native counterfactual or proof of eligibility.'})
    elif phase8:
        notes.append('Phase 8 join withheld: requires matching application, generation, exact JD and final DOCX SHA-256.')
    if not reference or not version:
        freshness = 'unknown: missing scorer version'
    elif version != reference:
        freshness = 'different scorer versions; historical optimizer receipt is not comparable to the reference'
    else:
        freshness = 'scorer versions match only; cache validity not established'
    # History was loaded by the caller for this application, generation and DOCX.
    # It is not an active comparison, and its exact JD has not been revalidated.
    historical_rows = []
    if audit_bound:
        for entry in rows(optimizer_history):
            item = {k: entry.get(k) for k in ('Mode','Request','Status','Scorer','Execution','Saved UTC')}
            if not item['Mode'] or item['Status'] in (None, 'not_run'):
                continue
            scorer = item['Scorer']
            item['version_comparison'] = ('unknown: missing scorer version' if not scorer or not reference else
                'different scorer versions; historical only' if scorer != reference else
                'scorer versions match only; cache validity not established')
            historical_rows.append(item)
    independent = obj(independent_scores)
    independent_scope = obj(independent.get('scope'))
    independent_bound = bool(audit_bound and jd_hash and independent.get('status') == 'available'
        and independent.get('native_score_claim') is False
        and independent.get('optimizer_search_performed') is False
        and independent_scope.get('generation_id') == gen
        and independent_scope.get('a_docx_sha256') == doc_hash == audit.get('docx_sha256')
        and independent_scope.get('raw_jd_sha256') == jd_hash)
    independent_display = independent if independent_bound else {
        'status':'unavailable', 'reason': independent.get('reason') or 'No identity-bound standalone saved-link receipt supplied.'}
    trace_scope = obj(optimizer_scope) or obj(result.get('_exact_trial_scope'))
    trace_bound = bool(audit_bound and jd_hash and doc_hash == audit['docx_sha256']
                       and trace_scope.get('application_id') == application_id
                       and trace_scope.get('generation_id') == gen
                       and trace_scope.get('jd_sha256') == jd_hash
                       and trace_scope.get('docx_sha256') == doc_hash)
    decision_trace = _decision_trace(project_table, bullet_table, fit if fit_bound else {},
                                     result if trace_bound and result.get('status') != 'not_run' else {})
    notes += ['Historical mode rows are document-bound metadata only; no current comparison or exact JD authority is inferred.',
              'Standalone points use saved links; zero is not evidence of zero native relevance.',
              'Exact wording presence is not proof of causal lineage. Rewrites/fusions may change wording.',
              'No per-bullet native score or counterfactual score is calculated.',
              'Unrecorded modes/trials and unavailable stages stay unknown; no re-render or rescore is performed.',
              'Reference scorer is from the supplied Phase 8 or baseline report, not independently established as current.']
    return detach({'schema':VERSION,'application_id':application_id,'generation_id':gen,'fit_bound':fit_bound,
        'actual_readback_available':audit_bound,'docx_sha256':doc_hash,'jd_sha256':jd_hash,'notes':notes,
        'project_stages':project_table,'bullet_stages':bullet_table,'saved_allocation_decisions':decisions,
        'decision_trace':decision_trace,
        'active_reductions':active,'native_phase8':native,'native_gap_clues':gaps,
        'independent_bullet_scores':independent_display, 'historical_optimizer_records':historical_rows,
        'optimizer':{'mode':run_mode,'status':result.get('status'),'reason':result.get('reason'),'winner':result.get('winner'),
            'verification_stage':result.get('verification_stage'),'scoring_version':version,'reference_scoring_version':reference,
            'version_comparison':freshness,'historical_summary':historical_optimizer,
            'saved_native_scores':{k:result.get(k) for k in ('a_score','b_score','delta','hard_regressed_ids')},
            'saved_trials':result.get('v35_trial_receipts'),'saved_guarded_review':result.get('guarded_review'),
            'saved_baseline_comparison':result.get('a_vs_starting'),
            'proposal_version':proposal.get('version'),'proposal_status':proposal.get('status'),
            'proposal_reason':proposal.get('reason'),'saved_link_gain_ids':proposal.get('gained_jd_ids'),
            'saved_link_loss_ids':proposal.get('lost_jd_ids'),'saved_bullet_score_receipt':proposal.get('v38_bullet_score_receipt'),
            'saved_proposal':proposal},
        'fit_metrics':{k:fit.get(k) for k in ('page_count','fit_status','remaining_quality_loss','render_budget','render_budget_used','render_cache_hits','render_cache_misses','fitting_elapsed_seconds','section_locks')} if fit_bound else {},
        'fitting_input_fingerprint':fit.get('fitting_input_fingerprint') if fit_bound else None})


def from_bundle(bundle, *, phase8=None, docx_bytes=None):
    b=obj(bundle); f=obj(b.get('one_page_fitting_result')); history=obj(b.get('generation_settings_provenance_v312b214'))
    h=obj(history.get('historical_optimizer'))
    gen=f.get('generation_id') or obj(history.get('recorded')).get('generation_id')
    # Debug bundles do not carry a verified project readback or complete Best-of result.
    return build_report(application_id=obj(b.get('debug_meta')).get('application_id'),generation_id=gen,
        projects=b.get('tailored_projects_result'),fit=f,candidate_pool=b.get('combined_project_candidate_pool'),
        baseline_report=b.get('analysis_report'),raw_jd_text=obj(b.get('analysis_report')).get('raw_jd_text'),
        historical_optimizer=h,run_mode=h.get('mode'),phase8=phase8,docx_bytes=docx_bytes)


def render_diagnostics(st, *, application_id, generation_id, projects, fit, audit, result, run_mode,
                       baseline_report, raw_jd_text, context, optimizer_history=None, independent_scores=None,
                       optimizer_scope=None):
    """Only a projection of already-loaded receipts. Never run a comparison."""
    try:
        report=build_report(application_id=application_id,generation_id=generation_id,projects=projects,
            fit=fit,audit=audit,result=result,run_mode=run_mode,baseline_report=baseline_report,raw_jd_text=raw_jd_text,
            optimizer_history=optimizer_history, independent_scores=independent_scores,
            optimizer_scope=optimizer_scope)
        st.markdown('#### B2.14b-4 — Optimizer evidence trail')
        st.caption('Read-only · saved selection signals are not native per-bullet scores · no new optimizer or model calls.')
        st.caption(report['optimizer']['version_comparison'])
        st.caption('Active comparison context: '+str(run_mode or 'unknown')+' · '+str(report['optimizer']['status'] or 'unavailable'))
        if report['historical_optimizer_records']:
            st.write('Historical optimizer records — not current score or reuse authority')
            st.dataframe(report['historical_optimizer_records'],use_container_width=True,hide_index=True)
        else:
            st.caption('No document-bound historical mode records supplied.')
        standalone=report['independent_bullet_scores']
        if standalone.get('status') == 'available':
            st.write('Standalone saved-link points — historical ranking, not native Job Match')
            st.dataframe([{k:r.get(k) for k in ('project','wording','standalone_weighted_points','marginal_in_proposal_points')} for r in rows(standalone.get('bullets'))],use_container_width=True,hide_index=True)
        else:
            st.caption('Standalone points unavailable: '+str(standalone.get('reason')))
        if report['project_stages']:
            st.dataframe(report['project_stages'],use_container_width=True,hide_index=True)
        if report['bullet_stages']:
            st.dataframe([{**r,'sources':', '.join(r['sources']),'saved_supported_ids':', '.join(r['saved_supported_ids']),
                           'saved_weak_ids':', '.join(r['saved_weak_ids']),
                           'active_removal_reasons':'; '.join(str(x) for x in r['active_removal_reasons'] if x)} for r in report['bullet_stages']],use_container_width=True,hide_index=True)
        score_receipt = obj(report['optimizer']['saved_bullet_score_receipt'])
        if rows(score_receipt.get('bullets')):
            st.write('Recorded standalone and marginal saved-link points (not native scores)')
            st.dataframe([{k:r.get(k) for k in ('project','wording','standalone_weighted_points','marginal_in_proposal_points','selected_for_proposed_b')} for r in rows(score_receipt['bullets'])],use_container_width=True,hide_index=True)
        if report['optimizer']['saved_trials']:
            st.write('Recorded native trial receipts')
            st.dataframe(rows(report['optimizer']['saved_trials']),use_container_width=True,hide_index=True)
        for note in report['notes']:
            st.caption(note)
        st.download_button('Download optimizer evidence trail (JSON)',data=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8'),
            file_name=f'phase9f_app_{application_id}_{str(generation_id)[:8]}_optimizer_diagnostics.json',mime='application/json',
            key=f'b214b4_diagnostics_{application_id}_{context}',on_click='ignore')
    except Exception as exc:
        st.caption('Optimizer diagnostics unavailable: '+type(exc).__name__+'. Existing optimizer result unchanged.')
