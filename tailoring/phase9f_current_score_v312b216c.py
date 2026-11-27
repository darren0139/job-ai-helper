"""Read-only display projection from an exact, current native Phase 8 receipt.
Never grants readiness, changes a saved score, or starts verification.
"""
from hashlib import sha256
from copy import deepcopy
from tailoring.phase9f_score_authority_v312b216a import inspect_receipt, METRICS, require

VERSION = 'v312b216c-current-score-display-v1'


def project_current_scores(*, application_id, historical_report, decision, generation,
                           receipt, exact_jd, runtime_identity, source_sha256,
                           verification_current):
    """Use existing authority checks; do not infer currentness from numeric parity."""
    require(verification_current is True, 'Phase 8 verification is not current')
    require(decision.get('application_id') == application_id and
            decision.get('scope_activation_status') == 'active' and
            decision.get('current_scope_status') == 'current', 'Current active binding required')
    gid = generation.get('generation_id')
    status = generation.get('status')
    require(isinstance(gid, str) and gid and status in ('draft', 'approved'), 'Current working or approved generation required')
    require(generation.get('application_id') == application_id, 'Generation application differs')
    expected = decision.get('decision_fingerprint')
    snapshot = (decision.get('starting_snapshot') or {}).get('starting_snapshot_fingerprint')
    binding = (generation.get('generation_settings') or {}).get('phase9e_binding') or {}
    require(bool(expected and snapshot) and binding.get('decision_fingerprint') == expected
            and binding.get('starting_snapshot_fingerprint') == snapshot,
            'Generation binding differs')
    ctx = (historical_report.get('meta') or {}).get('phase9e_starting_context') or {}
    require(ctx.get('starting_snapshot_fingerprint') == snapshot, 'Frozen source snapshot differs')
    require(exact_jd.get('application_id') == application_id, 'Linked JD belongs to another application')
    raw = exact_jd.get('raw_text')
    require(isinstance(raw, str) and raw.strip() and raw == historical_report.get('raw_jd_text')
            and sha256(raw.encode()).hexdigest() == exact_jd.get('raw_jd_sha256'), 'Exact linked JD differs')
    require(bool(receipt.get('verification_id')), 'Persisted verification identity required')
    diag = inspect_receipt(historical_report=historical_report, receipt=receipt,
                           application_id=application_id, generation_id=gid, expected_decision=expected)
    require(diag['selected_base_docx_sha256'] == source_sha256, 'Base DOCX identity differs')
    doc = receipt['document_analysis']
    for key, stable_key in (('initial', 'before_stable_analysis'), ('final', 'after_stable_analysis')):
        authority = doc[key]
        stable = receipt[stable_key]
        require(bool(runtime_identity) and authority.get('identity') == runtime_identity,
                'Scorer, taxonomy or registry identity differs')
        require(stable.get('scoring_version') == runtime_identity.get('scoring_version'), 'Scoring policy differs')
        require(bool(exact_jd.get('canonical_requirement_fingerprint')) and
                authority.get('canonical_requirement_fingerprint') == exact_jd['canonical_requirement_fingerprint'], 'Canonical scope fingerprint differs')
        ids = [r['requirement_id'] for r in stable['canonical_requirements']]
        require(bool(ids) and sorted(ids) == sorted(exact_jd.get('canonical_requirement_ids') or []), 'Canonical requirement IDs differ')
        require(all(type(stable.get(k)) is int and 0 <= stable[k] <= 100 for k in METRICS), 'Invalid native metric')
    return {'version': VERSION, 'application_id': application_id, 'generation_id': gid,
            'generation_status': status, 'verification_id': receipt['verification_id'],
            'decision_fingerprint': expected,
            'base_docx_sha256': diag['selected_base_docx_sha256'],
            'jd_sha256': diag['exact_jd_sha256'],
            'final_docx_sha256': diag['final_docx_sha256'],
            'base': {k: receipt['before_stable_analysis'][k] for k in METRICS},
            'final': {k: receipt['after_stable_analysis'][k] for k in METRICS},
            'historical': deepcopy(diag['historical_to_current_base']['before_metrics']),
            'delta': diag['native_score_delta'], 'scoring_version': runtime_identity['scoring_version']}


def load_active_score(application_id, workspace, diagnostics=None):
    """Existing persistence APIs only; a missing/incompatible receipt is a display hold."""
    def hold(reason):
        if isinstance(diagnostics, dict):
            diagnostics['reason'] = reason
        return None
    try:
        decision = workspace.get('phase9e_binding') or {}
        if decision.get('current_scope_status') != 'current' or decision.get('scope_activation_status') != 'active':
            return hold('No current active Tailoring Base binding.')
        generation = workspace.get('loaded_generation') or workspace.get('approved_generation')
        if not isinstance(generation, dict) or not generation.get('generation_id'):
            return hold('No loaded working draft or current approved résumé.')
        from database.db_manager import get_application_by_id
        from database.jd_library_manager import get_exact_job_description_for_application
        from database.tailoring_verification_manager import get_latest_tailoring_verification
        from database.phase9f_tailoring_execution_manager import (
            get_phase9f_application_confirmation, get_phase9f_tailoring_execution, _resolve_prepared_source_artifact)
        from tailoring.phase8_auto_verification import phase8_verification_is_current
        from tailoring.job_match_ab_analysis import current_ab_identity
        receipt = get_latest_tailoring_verification(application_id, generation['generation_id'])
        if not phase8_verification_is_current(receipt, generation):
            return hold('The selected generation has no current exact Phase 8 verification.')
        report = (get_application_by_id(application_id) or {}).get('report') or {}
        exact = get_exact_job_description_for_application(application_id) or {}
        execution = get_phase9f_tailoring_execution(application_id, generation_id=generation['generation_id'])
        if not execution or not execution.get('source_artifact'):
            return hold('The selected generation has no matching frozen execution source.')
        confirmation = get_phase9f_application_confirmation(application_id)
        if not confirmation or not exact.get('raw_text'):
            return hold('The frozen confirmation or exact linked JD is unavailable.')
        source = _resolve_prepared_source_artifact(decision=decision, confirmation=confirmation,
                                                  expected_identity=execution['source_artifact'])
        return project_current_scores(application_id=application_id, historical_report=report,
            decision=decision, generation=generation, receipt=receipt, exact_jd=exact,
            runtime_identity=current_ab_identity(exact['raw_text']), source_sha256=source['sha256'],
            verification_current=True)
    except Exception as exc:
        # Presentation must never prevent application access or promote a partial receipt.
        # Show known validation errors, not raw traceback/database details.
        return hold(str(exc) if isinstance(exc, ValueError) else f'Score authority unavailable ({type(exc).__name__}).')


def sidebar_score_label(saved_score, projection):
    if projection:
        kind = 'Verified draft' if projection['generation_status'] == 'draft' else 'Verified approved'
        return f"{kind} {projection['final'][METRICS[0]]}/100 · Base {projection['base'][METRICS[0]]}"
    return f'Saved score {saved_score}/100' if saved_score is not None else ''


def render_current_base(st, projection):
    st.markdown('**Current verified Selected Base DOCX**')
    cols = st.columns(4)
    for col, label, key in zip(cols, ('Base Job Match', 'Required/Core', 'Preferred', 'Evidence strength'), METRICS):
        col.metric(label, projection['base'][key])
    kind = 'working draft' if projection['generation_status'] == 'draft' else 'approved résumé'
    st.caption(f"Saved current native comparison for {kind} {projection['generation_id'][:8]}: "
               f"Base {projection['base'][METRICS[0]]} → Final {projection['final'][METRICS[0]]} "
               f"({projection['delta']:+d}). Verification does not imply approval.")
    st.caption('Historical confirmation retained below. Phase 8 can inspect other fitted versions separately.')
