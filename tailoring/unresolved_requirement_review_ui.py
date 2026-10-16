"""Explicit Job Match review using native, context-local requirement previews."""
import sqlite3
from taxonomy_discovery import governed_requirement_resolution as review
from taxonomy_discovery.corpus_expansion import fingerprint

ACTION_ERRORS=(ValueError,RuntimeError,OSError,KeyError,sqlite3.Error)


def _draft_context(packet):
    return fingerprint({'saved':packet.get('saved_governed'),
                        'regression':packet.get('governed_regression')})


def _context(row):
    return fingerprint({'input':review.requirement_input(row),'versions':review.current_match_versions(),
                        'knowledge':review.knowledge_fingerprint(),'preview_version':review.VERSION})


def _clear_actions(st, prefix, packet):
    for name in ('saved_governed','governed_regression','readiness','approval','publication',
                 'validation_error','approval_error','readiness_error','publication_error','action_context'):
        packet.pop(name,None)
    for suffix in ('_approve_confirm','_publish_confirm'):
        st.session_state.pop(prefix+suffix,None)


def _steps(st, packet):
    regression=packet.get('governed_regression')
    readiness=packet.get('readiness') or {}
    published=bool(packet.get('publication'))
    states=[('Inspect','failed' if packet.get('inspect_error') else 'completed' if packet.get('diagnostics') else 'pending'),
            ('Preview','completed' if published else 'failed' if packet.get('preview_error') else 'completed' if packet.get('validation') else 'pending'),
            ('Validate','failed' if packet.get('validation_error') else
             'blocked' if regression and regression.get('publication_blockers') else
             'completed' if regression else 'pending'),
            ('Approve','failed' if packet.get('approval_error') else
             'completed' if packet.get('approval') or readiness.get('ready') else 'blocked' if not regression or regression.get('publication_blockers') else 'pending'),
            ('Publish','failed' if packet.get('publication_error') else 'completed' if packet.get('publication') else
             'pending' if readiness.get('ready') else 'blocked')]
    st.caption(' → '.join(f'{name}: {state}' for name,state in states))


def render_unresolved_requirement_review(st, view):
    from taxonomy_discovery import governed_review_recovery as recovery
    rows=[r['native'] for r in view['requirements'] if not r['native'].get('capability_id')
          and r['native'].get('knowledge_status') not in ('CAPABILITY_RESOLVED','TECHNOLOGY_IDENTITY_RESOLVED')]
    if not rows:return
    by_id={r['requirement_id']:r for r in rows}
    prefix='unresolved_review_'+fingerprint({'identity':view['identity'],'provenance':view['provenance']})[:16]
    with st.expander('Unresolved Requirement Review'):
        st.caption('Saved unresolved requirements are review leads, not proven taxonomy gaps. '
                   'Review uses current knowledge without rewriting this historical analysis.')
        rid=st.selectbox('Requirement to review',list(by_id),
            format_func=lambda key:by_id[key].get('text',key),key=prefix+'_selected')
        if rid not in by_id:return
        row=by_id[rid];context=_context(row);state_key=prefix+'_packet'
        packet=st.session_state.get(state_key)
        if not isinstance(packet,dict) or packet.get('context')!=context:
            packet={'context':context};st.session_state[state_key]=packet
            for suffix in ('_approve_confirm','_publish_confirm'):st.session_state.pop(prefix+suffix,None)
        elif packet.get('action_context') and packet['action_context']!=_draft_context(packet):
            _clear_actions(st,prefix,packet)
        recovery_key=(context,recovery.store_identity())
        reload_saved=st.button('Reload saved review',key=prefix+'_recover')
        if packet.get('recovery_key')!=recovery_key or reload_saved:
            try:found=recovery.recover(row,view['identity'])
            except ACTION_ERRORS as exc:found={'status':'stale','message':'Saved review lookup failed','blockers':[str(exc)]}
            # Store changes invalidate actionable session receipts. Never retain
            # an earlier approval over a newer persisted rejection or draft.
            if packet.get('recovery_key') is not None or packet.get('publication') or (
                    packet.get('approval') or packet.get('governed_regression')):
                _clear_actions(st,prefix,packet)
            packet.update(recovery=found,recovery_key=recovery_key)
            if found['status'] in ('ready','published'):
                packet.pop('preview_error',None)
                if found['status']=='published':packet['publication']=found['publication']
                packet.update({k:found[k] for k in ('saved_governed','governed_regression','approval','readiness')})
                packet['action_context']=_draft_context(packet)
            elif found['status']=='validated':
                packet.update({k:found[k] for k in ('saved_governed','governed_regression')})
                packet['action_context']=_draft_context(packet)
        found=packet.get('recovery',{})
        st.write(row.get('text'))
        st.caption('Importance: '+str(row.get('importance'))+'  /  Discovered job: '+str(view['identity'].get('discovered_job_id'))+
                   '  /  Snapshot: '+str(view['identity'].get('id')))
        step_status=st.empty()
        if found.get('status') in ('stale','publication_mismatch'):
            st.warning(found['message'])
            for blocker in found.get('blockers',[]):st.caption(blocker)
        elif found.get('status')=='published':st.success(found['message'])
        elif found.get('status') in ('pending','validated'):st.info(found['message'])
        elif found.get('status')=='missing' and not packet.get('approval'):st.caption(found['message'])

        with st.container(border=True):
            st.subheader('Inspect diagnostics')
            if st.button('Inspect diagnostics',key=prefix+'_inspect'):
                packet.pop('inspect_error',None)
                try:packet['diagnostics']=review.diagnostic_view(row)
                except ACTION_ERRORS as exc:packet['inspect_error']=str(exc)
            diagnostics=packet.get('diagnostics')
            if packet.get('inspect_error'):st.error('Inspect failed: '+packet['inspect_error'])
            elif diagnostics:
                native=diagnostics['native']
                st.success('Inspect completed')
                st.write('Current native classification: '+str(native.get('knowledge_status')))
                st.write('Native resolver reason: '+str(native.get('reason')))
                st.write('Capability candidate: '+str(native.get('capability_id') or 'No native selection'))
                diagnostics['saved_analysis_identity']={k:view['identity'].get(k) for k in
                    ('id','discovered_job_id','job_content_hash','scoring_version','taxonomy_version','match_version')}
                with st.expander('Inspect details',expanded=False):
                    st.json(diagnostics)
                    st.dataframe(diagnostics['candidate_observations'],hide_index=True,width='stretch')
                if any(c['separate_confirmation_required'] for c in diagnostics['candidate_observations']):
                    st.info('Stakeholder recognition requires separate policy confirmation. The API preview does not enable it.')
            else:st.caption('Inspect pending')

        with st.container(border=True):
            st.subheader('Preview proposed correction')
            if st.button('Preview proposed correction',key=prefix+'_preview',
                         disabled=bool(packet.get('publication')) or found.get('status')=='publication_mismatch'):
                # An unchanged diagnostic preview cannot revoke a persisted approval.
                if found.get('status') not in ('ready','validated'):_clear_actions(st,prefix,packet)
                packet.pop('preview_error',None)
                try:
                    proposal=review.propose(row)
                    packet.update(proposal=proposal,validation=review.preview(proposal,explicit_execution=True),rejected=False)
                except ACTION_ERRORS as exc:
                    packet.pop('proposal',None);packet.pop('validation',None);packet['preview_error']=str(exc)
            validation=packet.get('validation')
            if packet.get('publication'):st.success('Already published — correction active')
            elif found.get('status')=='publication_mismatch':st.warning('Preview blocked — reconcile the publication receipt/artifact mismatch.')
            elif packet.get('preview_error'):st.error('Preview failed: '+packet['preview_error'])
            elif validation:
                comparison=validation['selected_requirement']
                st.write('Before classification: '+str(comparison['before']['knowledge_status']))
                st.write('After classification: '+str(comparison['after']['knowledge_status']))
                st.write('Target capability: '+str(packet['proposal']['target_capability_id']))
                rules=packet['proposal']['proposed_change']['recognition_fallback_rules']
                st.write('Rule identifier: '+', '.join(r['rule_id'] for r in rules))
                st.caption(f"Control tests: {sum(bool(x['passed']) for x in validation['controls'])}/{len(validation['controls'])} passed")
                st.info('Preview only — not published')
                with st.expander('Preview Advanced details',expanded=False):
                    st.json({'proposal':packet['proposal'],'preview':validation})
                    st.dataframe(validation['controls'],hide_index=True,width='stretch')
                reject_reviewer=st.session_state.get(prefix+'_reviewer','')
                if st.button('Reject proposed correction',key=prefix+'_reject',
                        disabled=bool(packet.get('publication')) or bool(packet.get('saved_governed')) and not str(reject_reviewer).strip()):
                    try:
                        if packet.get('saved_governed'):
                            from database.taxonomy_discovery_review_manager import save_governed_research_review
                            saved=packet['saved_governed']
                            save_governed_research_review(saved['result']['research_result_id'],
                                result_fingerprint=saved['result']['result_fingerprint'],decision='reject',reviewer=reject_reviewer)
                        _clear_actions(st,prefix,packet)
                        packet.pop('proposal',None);packet.pop('validation',None);packet['rejected']=True
                        packet.pop('rejection_error',None)
                    except ACTION_ERRORS as exc:packet['rejection_error']=str(exc)
                if packet.get('rejection_error'):st.error('Rejection failed: '+packet['rejection_error'])
            else:st.caption('Preview pending; opening saved receipts does not run a new preview.')
            if packet.get('rejected'):st.info('Preview rejected. No production change was made.')

        with st.container(border=True):
            st.subheader('Validate draft')
            if st.button('Validate draft',key=prefix+'_validate',disabled=not packet.get('validation') or
                         bool(packet.get('publication')) or found.get('status') in ('ready','validated','publication_mismatch')):
                _clear_actions(st,prefix,packet)
                try:
                    identity=view['identity']
                    provenance=[{'job_id':identity.get('discovered_job_id'),'snapshot_id':identity.get('id'),
                        'requirement_id':rid,'job_content_hash':identity.get('job_content_hash'),
                        'observed_versions':{k:identity.get(k) for k in ('scoring_version','taxonomy_version','match_version')}}]
                    saved=review.create_local_governed_draft(row,provenance,explicit_execution=True)
                    from taxonomy_discovery.regression_corpus import export_saved_corpus
                    regression=review.validate_governed_draft(saved,export_saved_corpus(),explicit_execution=True)
                    packet.update(saved_governed=saved,governed_regression=regression)
                    packet['action_context']=_draft_context(packet)
                    packet['recovery_key']=(context,recovery.store_identity())
                except ACTION_ERRORS as exc:
                    packet['validation_error']=str(exc)
                    packet['recovery_key']=(context,recovery.store_identity())
            regression=packet.get('governed_regression');saved=packet.get('saved_governed')
            if packet.get('validation_error'):st.error('Validation failed: '+packet['validation_error'])
            elif regression:
                blockers=regression['publication_blockers']
                if blockers:st.warning('Validation blocked: '+'; '.join(map(str,blockers)))
                elif packet.get('publication'):st.success('Historical validation completed for this publication.')
                else:st.success('Draft validated — no publication blockers.')
                st.write('Saved draft ID: '+str(saved['draft']['resolver_draft_id']))
                st.write('Regression status: '+('blocked' if blockers else 'passed')+'  /  Unexpected changes: '+
                         str(len(regression['unexpectedly_changed_requirements'])))
                if found.get('status') in ('ready','published','validated'):st.caption('Recovered persisted validation receipt; no scoring replay performed.')
                with st.expander('Validation details',expanded=False):st.json(regression)
            else:st.caption('Validation pending — a current saved validation receipt is required.')

        with st.container(border=True):
            st.subheader('Approve validated draft')
            if regression:
                reviewer=st.text_input('Reviewer',key=prefix+'_reviewer')
                confirmed=st.checkbox('I approve this exact validated draft for publication review',key=prefix+'_approve_confirm')
                if st.button('Approve validated draft',key=prefix+'_approve',disabled=bool(packet.get('approval')) or
                             not reviewer.strip() or not confirmed or bool(regression['publication_blockers'])):
                    from database.taxonomy_discovery_review_manager import save_governed_research_review
                    for name in ('readiness','approval_error','readiness_error','publication_error'):packet.pop(name,None)
                    st.session_state.pop(prefix+'_publish_confirm',None)
                    try:
                        receipt=save_governed_research_review(saved['result']['research_result_id'],
                            result_fingerprint=saved['result']['result_fingerprint'],decision='approve_for_publication',
                            reviewer=reviewer,regression=regression)
                        packet['approval']={'receipt':receipt,'draft_fingerprint':regression['draft_fingerprint']}
                        packet['recovery_key']=(context,recovery.store_identity())
                    except ACTION_ERRORS as exc:packet['approval_error']=str(exc)
                    if packet.get('approval'):
                        try:packet['readiness']=review.approval_readiness(saved['result']['research_result_id'])
                        except ACTION_ERRORS as exc:packet['readiness_error']=str(exc)
                        st.rerun()
                if packet.get('approval_error'):st.error('Approval failed: '+packet['approval_error'])
                elif packet.get('approval'):
                    receipt=packet['approval']['receipt'] or {}
                    st.success('Historical approval — published' if packet.get('publication') else
                               'Already approved' if found.get('status')=='ready' else 'Draft approval saved successfully.')
                    st.write('Reviewer: '+str(receipt.get('reviewer') or reviewer))
                    st.write('Approval timestamp: '+str(receipt.get('updated_at') or (packet.get('readiness') or {}).get('approval_timestamp')))
                    st.caption('Historical draft/approval verified against the completed publication receipt.' if packet.get('publication') else
                               'Draft fingerprint/currentness verified by the publication preflight.' if
                               (packet.get('readiness') or {}).get('ready') else 'Currentness is not confirmed; review the readiness blockers.')
                readiness_status=st.empty()
                if st.button('Review approval readiness',key=prefix+'_ready',disabled=bool(packet.get('publication'))):
                    packet.pop('readiness',None);packet.pop('readiness_error',None)
                    st.session_state.pop(prefix+'_publish_confirm',None)
                    try:packet['readiness']=review.approval_readiness(saved['result']['research_result_id'])
                    except ACTION_ERRORS as exc:packet['readiness_error']=str(exc)
                with readiness_status.container():
                    if packet.get('readiness_error'):st.error('Readiness check failed: '+packet['readiness_error'])
                    readiness=packet.get('readiness')
                    if readiness and not packet.get('publication'):
                        if readiness.get('ready'):
                            st.success('Approved — Ready for publication')
                            st.write('Target taxonomy version: '+str(readiness.get('version_after'))+'  /  Blockers: 0')
                        else:
                            st.warning('Publication blocked: '+'; '.join(map(str,readiness.get('blockers',[]))))
                            st.caption('Blocker count: '+str(len(readiness.get('blockers',[]))))
            else:
                st.button('Approve validated draft',key=prefix+'_activate',disabled=True,
                          help='Missing current governed draft, regression and approval receipts.')
                if found.get('status')=='stale' and found.get('review'):
                    previous=found['review']
                    st.warning('Previously approved — requires revalidation')
                    st.write('Reviewer: '+str(previous.get('reviewer')))
                    st.write('Approval timestamp: '+str(previous.get('updated_at')))
                st.caption('Approval blocked — validation is required.')

        with st.container(border=True):
            st.subheader('Publish approved correction')
            readiness=packet.get('readiness') or {}
            st.write('Active taxonomy version: '+review.current_match_versions()['taxonomy_version'])
            if packet.get('publication'):
                receipt=packet['publication']
                st.success('Published — taxonomy '+receipt['version_after'].rsplit('-',1)[-1]+' active')
                st.success('Published knowledge version '+receipt['version_after']+'; historical analyses were not refreshed.')
                st.write('Publication receipt',receipt.get('publication_id'),receipt.get('status'),receipt['version_after'])
                st.write('Reviewer: '+str(receipt.get('reviewer'))+' / Approval timestamp: '+str(receipt.get('approval_timestamp')))
                st.write('Publication timestamp: '+str(receipt.get('publication_timestamp')))
                change=receipt.get('change_applied') or {}
                st.write('Published capability: '+str(change.get('capability_id')))
                st.write('Rule identifier: '+', '.join(r['rule_id'] for r in change.get('recognition_fallback_rules',[])))
                if found.get('native'):
                    st.write('Current native classification: '+str(found['native']['knowledge_status']))
                    st.write('Native resolver reason: '+str(found['native']['reason']))
                st.button('Publish approved correction',key=prefix+'_publish',disabled=True)
                with st.expander('Publication receipt details',expanded=False):st.json(receipt)
            elif readiness:
                st.write('Target taxonomy version: '+str(readiness.get('version_after') or 'Unavailable'))
                st.caption('Publication ready' if readiness.get('ready') else 'Publication blocked')
                publish_confirm=st.checkbox('I authorize publication of this exact approved version',key=prefix+'_publish_confirm')
                if st.button('Publish approved correction',key=prefix+'_publish',disabled=bool(packet.get('publication')) or
                             not readiness.get('ready') or not publish_confirm):
                    from taxonomy_discovery.governed_publication import publish_approved_change
                    packet.pop('publication_error',None)
                    try:packet['publication']=publish_approved_change(saved['result']['research_result_id'],explicit_publish=True,refresh_jobs=False)
                    except ACTION_ERRORS as exc:packet['publication_error']=str(exc)
                    if packet.get('publication'):
                        packet['context']=_context(row);packet['published_versions']=review.current_match_versions()
                        packet['recovery_key']=(packet['context'],recovery.store_identity())
                        st.rerun()
                if packet.get('publication_error'):st.error('Publication failed: '+packet['publication_error'])
                if packet.get('publication'):
                    receipt=packet['publication']
                    st.success('Published knowledge version '+receipt['version_after']+'; historical analyses were not refreshed.')
                    st.write('Publication receipt',receipt.get('publication_id'),receipt.get('status'),receipt['version_after'])
                    with st.expander('Publication receipt details',expanded=False):st.json(receipt)
            else:st.caption('Publication blocked — explicit current approval and separate confirmation are required.')
        with step_status.container():_steps(st,packet)
        if not packet.get('approval'):st.caption('Preview is not approval. Publication requires explicit human authorization.')
        with st.expander('Advanced diagnostics',expanded=False):
            st.json({'saved_analysis_identity':view['identity'],'recovery':found,
                     'proposal':packet.get('proposal'),'preview':packet.get('validation'),
                     'approval':packet.get('approval'),'readiness':packet.get('readiness'),
                     'publication_receipt':packet.get('publication')})
        if packet.get('diagnostics'):
            st.download_button('Download privacy-sanitized debug bundle',review.debug_bundle(packet['diagnostics'],packet.get('validation')),
                file_name='requirement_review.zip',mime='application/zip',key=prefix+'_download',on_click='ignore')
