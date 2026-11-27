"""Restore an explicitly accepted fitted draft into session state, never approval.
The accepted decision is supplied by the validated workspace reader. No scoring,
new generations, preference writes, or fallback to an arbitrary latest draft.
"""


def current_owned_draft(application_id, workspace, generation):
    decision = workspace.get('phase9e_binding') or {}
    if not isinstance(generation, dict):
        return False
    expected = decision.get('decision_fingerprint')
    snapshot = (decision.get('starting_snapshot') or {}).get('starting_snapshot_fingerprint')
    stored = (generation.get('generation_settings') or {}).get('phase9e_binding') or {}
    return bool(expected and snapshot and decision.get('application_id') == application_id
                and decision.get('scope_activation_status') == 'active'
                and decision.get('current_scope_status') == 'current'
                and generation.get('application_id') == application_id
                and generation.get('status') == 'draft' and generation.get('generation_id')
                and generation.get('phase9e_decision_fingerprint') == expected
                and stored.get('decision_fingerprint') == expected
                and stored.get('starting_snapshot_fingerprint') == snapshot)


def show_unapproved_workspace(application_id, workspace):
    return not workspace.get('application_approved_generation') and any(
        current_owned_draft(application_id, workspace, g)
        for g in workspace.get('current_drafts') or [])


def queue_accepted_restore(session, application_id, accepted):
    session[f'b216c2_pending_{application_id}'] = accepted['acceptance_fingerprint']


def accepted_draft(application_id, workspace, session, *, receipt_loader, current_gate):
    """Select only the exact receipt reviewed at acceptance. No silent draft switching."""
    decision = workspace.get('phase9e_binding') or {}
    acceptance = decision.get('scoring_policy_transition') or {}
    token = acceptance.get('acceptance_fingerprint')
    if not token or workspace.get('application_approved_generation'):
        return None, 'No eligible unapproved accepted draft.'
    pending = session.get(f'b216c2_pending_{application_id}') == token
    if not pending and (workspace.get('loaded_generation') or session.get(f'tailored_generation_id_{application_id}')):
        return None, 'An explicit workspace selection is retained.'
    if not pending and session.get(f'b216c2_attempted_{application_id}') == token:
        return None, 'Automatic recovery already attempted; use Résumé Workspace.'
    if not pending and any(session.get(f'{prefix}_{application_id}') is not None for prefix in
            ('tailored_projects_result','tailored_skills_result','tailored_resume_fit_result','tailored_resume_copy_path')):
        return None, 'Unsaved working content is retained.'
    gid = acceptance.get('generation_id')
    matches = [g for g in workspace.get('current_drafts') or [] if g.get('generation_id') == gid]
    if len(matches) != 1 or not current_owned_draft(application_id, workspace, matches[0]):
        return None, 'Accepted draft no longer belongs to the active binding.'
    generation = matches[0]
    if (generation.get('fit_result') or {}).get('fit_one_page') is not True:
        return None, 'Accepted fitted draft is unavailable.'
    receipt = receipt_loader(application_id, gid) or {}
    if not (receipt.get('application_id') == application_id and receipt.get('generation_id') == gid
            and acceptance.get('verification_id') and receipt.get('verification_id') == acceptance['verification_id']
            and acceptance.get('verification_fingerprint') and receipt.get('verification_fingerprint') == acceptance['verification_fingerprint']
            and acceptance.get('verified_generation_snapshot_fingerprint')
            and receipt.get('verified_generation_snapshot_fingerprint') == acceptance['verified_generation_snapshot_fingerprint']
            and acceptance.get('final_docx_sha256')
            and (receipt.get('document_analysis') or {}).get('final_document_sha256') == acceptance['final_docx_sha256']
            and receipt.get('comparison_valid') is True and current_gate(receipt, generation)):
        return None, 'Accepted draft receipt is not the current exact fitted verification.'
    return generation, 'Restored accepted fitted draft.'


def restore_accepted_workspace(st, application_id, workspace):
    """Called before sidebar score projection. Errors never block manual recovery."""
    decision = workspace.get('phase9e_binding') or {}
    token = (decision.get('scoring_policy_transition') or {}).get('acceptance_fingerprint')
    if not token:
        return workspace
    session = st.session_state
    try:
        from database.tailoring_verification_manager import get_latest_tailoring_verification
        from tailoring.phase8_auto_verification import phase8_verification_is_current
        from tailoring.generation_controls_ui import restore_generation_to_session
        generation, reason = accepted_draft(application_id, workspace, session,
            receipt_loader=get_latest_tailoring_verification, current_gate=phase8_verification_is_current)
        if generation is not None:
            restore_generation_to_session(application_id, generation)
            workspace = {**workspace, 'loaded_generation':generation, 'loaded_mode':'working_draft'}
    except Exception as exc:
        reason = 'Accepted draft recovery unavailable (' + type(exc).__name__ + '). Use Résumé Workspace.'
    session[f'b216c2_attempted_{application_id}'] = token
    session.pop(f'b216c2_pending_{application_id}', None)
    session[f'b216c2_restore_reason_{application_id}'] = reason
    return workspace


def draft_to_preserve(application_id, workspace, binding_identity, execution=None):
    """A marker change clears transient state. Rehydrate only an exact current draft."""
    generation = workspace.get('loaded_generation')
    if not current_owned_draft(application_id, workspace, generation):
        return None
    stored = (generation.get('generation_settings') or {}).get('phase9e_binding') or {}
    if not all(binding_identity.get(k) and stored.get(k) == binding_identity[k]
               for k in ('decision_fingerprint','starting_snapshot_fingerprint')):
        return None
    action = binding_identity.get('workflow_action_fingerprint')
    if action:
        return generation if stored.get('workflow_action_fingerprint') == action else None
    # Normal Phase 9F has no Phase 9E workflow-action fingerprint. Its frozen F
    # provenance is the equivalent ownership contract; do not accept blank IDs.
    settings = generation.get('generation_settings') or {}
    lifecycle = settings.get('phase9f_f_normal_lifecycle') or {}
    provenance = lifecycle.get('provenance') or {}
    execution = execution or {}
    if not stored.get('workflow_action_fingerprint') and provenance and provenance == settings.get('phase9f_f_provenance') and all(
        execution.get(k) and provenance.get(k) == execution[k] for k in
        ('execution_id','execution_fingerprint','confirmation_fingerprint','phase9e_decision_fingerprint','starting_snapshot_fingerprint','exact_jd_identity_fingerprint','evidence_snapshot_fingerprint','section_scope_fingerprint')):
        return generation
    return None
