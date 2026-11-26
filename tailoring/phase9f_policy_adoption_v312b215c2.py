"""B2.15c-2: explicit current-policy adoption without rewriting D/F identity.

The D decision remains historical provenance. A sealed acceptance event records
current JD scope and native Base analysis; only the verified Full F context may
use that scope. All user-facing approval gates remain native Phase 8 gates.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from copy import deepcopy
from pathlib import Path

from tailoring.phase9f_policy_transition_v312b215c import (
    CURRENT_SCORER, _fingerprint, _require, _file_hash,
    classify_transition, authenticate_execution,
)

VERSION = 'v312b215c2-explicit-policy-adoption-v1'
EVENT = 'scoring_policy_transition_accepted_v312b215c2'
BASE_FIELDS = ('stable_analysis', 'keyword_match', 'resume_profile', 'raw_resume_text', 'jd_profile', 'raw_jd_text')


def preview_identity(preview: dict) -> str:
    """Seal the reviewed outcome, including exact document and native row proof."""
    _require(preview.get('status') == 'native_preview_completed', 'A completed native recheck is required.')
    return _fingerprint(preview)


def _event_details(connection, application_id, decision):
    rows = connection.execute('''SELECT * FROM application_blueprint_binding_events
        WHERE application_id=? AND decision_id=? AND event_type=?''',
        (int(application_id), decision['decision_id'], EVENT)).fetchall()
    if not rows:
        return None
    _require(len(rows) == 1, 'Duplicate scoring policy acceptances.')
    row = rows[0]
    event = json.loads(row['event_json'])
    digest = event.pop('event_fingerprint', None)
    _require(digest == row['event_fingerprint'] == _fingerprint(event), 'Scoring policy acceptance event checksum differs.')
    _require(all(event.get(k) == row[k] for k in ('event_id','event_type','application_id','decision_id','decision_fingerprint')), 'Scoring policy acceptance event identity differs.')
    _require(event['decision_fingerprint'] == decision['decision_fingerprint'], 'Scoring policy acceptance belongs to another decision.')
    details = event['event_details']
    _require(details.get('version') == VERSION, 'Unsupported scoring policy acceptance.')
    _require(details.get('acceptance_fingerprint') == _fingerprint({k:v for k,v in details.items() if k != 'acceptance_fingerprint'}), 'Scoring policy acceptance content changed.')
    return details


def _historical_scope(*, decision, exact_jd, confirmation, execution):
    from tailoring.phase9f_tailoring_execution import validate_minor_full_execution_scope
    from analysis_stability.stable_evidence_scoring import SCORING_VERSION
    _require(decision.get('scope_activation_status') == 'active', 'The original binding is not active.')
    stale = {**decision, 'current_scope_status':'stale'}
    transition = classify_transition(decision=stale, current_jd=exact_jd, active_scorer=SCORING_VERSION)
    scope = validate_minor_full_execution_scope(application_id=int(decision['application_id']),
        confirmation=confirmation, decision=decision, exact_jd=decision['current_jd_snapshot'])
    # Full uses all immutable evidence; Minor has a policy-dependent positive-gain
    # subset and cannot be silently migrated through this first release.
    _require(scope.get('confirmed_intensity') == 'full', 'This transition supports confirmed Full tailoring; Minor needs separate scope recomputation.')
    _require(isinstance(execution, dict) and execution.get('confirmed_intensity') == 'full', 'The frozen Full execution is unavailable.')
    from database.phase9f_tailoring_execution_manager import is_phase9f_normal_lifecycle_execution
    _require(is_phase9f_normal_lifecycle_execution(execution), 'Only the normal Full lifecycle is supported.')
    authenticate_execution(execution, scope)
    return transition, scope


def _validate_projection(projection, transition, contract):
    _require(isinstance(projection, dict) and set(projection) == set(BASE_FIELDS) | {'document_analysis'}, 'Current Base projection missing or malformed.')
    from tailoring.document_grounded_analysis import validate_document_report
    from tailoring.job_match_ab_analysis import current_ab_identity
    authority = validate_document_report({**projection, 'meta': {'document_analysis':projection['document_analysis']}})
    _require(authority['identity'] == current_ab_identity(projection['raw_jd_text']), 'Accepted Base runtime identity is stale.')
    _require(authority['fingerprint'] == contract.get('selected_base_document_analysis_fingerprint') and authority['resume_text_sha256'] == contract.get('selected_base_resume_text_sha256'), 'Accepted Base document authority differs.')
    stable = projection['stable_analysis']
    _require(stable.get('scoring_version') == transition['new_scorer'], 'Accepted Base scorer is stale.')
    _require(sorted(row['requirement_id'] for row in stable.get('canonical_requirements', [])) == transition['surviving_requirement_ids'], 'Accepted Base scope differs.')
    _require(hashlib.sha256(projection['raw_jd_text'].encode('utf-8')).hexdigest() == transition['raw_jd_sha256'], 'Accepted Base JD differs.')
    _require(contract.get('mode') == 'selected_base_docx_only' and contract.get('scoring_scope_refresh',{}).get('current_count') == transition['current_count'], 'Accepted Base document role differs.')
    _require(isinstance(projection['resume_profile'],dict) and isinstance(projection['keyword_match'],dict), 'Accepted Base document inputs missing.')


def read_accepted_transition(*, application_id, decision, exact_jd):
    """Read and authenticate an explicit acceptance. Does not run native scoring."""
    # A detached/legacy binding without persisted identity cannot own an
    # acceptance. Keep the original stale-scope diagnostic and do not open DB.
    if not all(isinstance(decision.get(key), str) and decision[key].strip()
               for key in ('decision_id', 'decision_fingerprint')):
        return None
    from database import application_blueprint_manager as bindings
    connection = bindings._connect()
    try:
        accepted = _event_details(connection, application_id, decision)
    finally:
        connection.close()
    if accepted is None:
        return None
    from database import phase9f_tailoring_execution_manager as manager
    confirmation = manager.get_phase9f_application_confirmation(int(application_id))
    execution = manager.get_phase9f_tailoring_execution(int(application_id))
    transition, _ = _historical_scope(decision=decision, exact_jd=exact_jd, confirmation=confirmation, execution=execution)
    _require(accepted['transition'] == transition, 'Accepted scoring policy no longer matches the current JD.')
    _require(accepted['execution_fingerprint'] == execution['execution_fingerprint'] and accepted['confirmation_fingerprint'] == confirmation['confirmation_fingerprint'], 'Accepted execution or confirmation changed.')
    source = manager._resolve_prepared_source_artifact(decision=decision, confirmation=confirmation, expected_identity=execution['source_artifact'])
    _require(accepted['source_sha256'] == source['sha256'] == accepted['starting_document_contract']['selected_base_docx_sha256'], 'Accepted source artifact changed.')
    _validate_projection(accepted['current_base'], transition, accepted['starting_document_contract'])
    return accepted


def validate_execution_scope(*, application_id, confirmation, decision, exact_jd):
    """Keep original ownership identity; validate the current scope separately."""
    from tailoring.phase9f_tailoring_execution import validate_minor_full_execution_scope
    if not decision.get('scoring_policy_transition'):
        return validate_minor_full_execution_scope(application_id=application_id,confirmation=confirmation,decision=decision,exact_jd=exact_jd)
    accepted = read_accepted_transition(application_id=application_id,decision=decision,exact_jd=exact_jd)
    _require(accepted is not None and accepted == decision['scoring_policy_transition'], 'Current scoring-policy acceptance is no longer valid.')
    from database.phase9f_tailoring_execution_manager import get_phase9f_tailoring_execution
    _, scope = _historical_scope(decision=decision,exact_jd=exact_jd,confirmation=confirmation,execution=get_phase9f_tailoring_execution(application_id))
    return scope


def current_base_report(report: dict, decision: dict) -> dict:
    """Overlay current document analysis, never relabel the old D receipt."""
    accepted = decision.get('scoring_policy_transition')
    if not accepted:
        return report
    _require(decision.get('current_scope_status') == 'current', 'Accepted scoring scope is not current.')
    _validate_projection(accepted['current_base'],accepted['transition'],accepted['starting_document_contract'])
    effective = deepcopy(report)
    for key in BASE_FIELDS:
        effective[key] = deepcopy(accepted['current_base'][key])
    # This is a Selected Base handoff, not a separately uploaded Initial.
    effective.setdefault('meta',{})['phase9f_scoring_policy_transition'] = {
        'version': VERSION, 'acceptance_fingerprint': accepted['acceptance_fingerprint'],
        'selected_base_document_contract': deepcopy(accepted['starting_document_contract'])}
    return effective


def _insert_native_receipt(connection, result, now):
    """Insert the complete native Phase 8 receipt in the caller's transaction."""
    _require(bool(result.get('verification_fingerprint')), 'Native verification fingerprint missing.')
    rows = connection.execute('''SELECT * FROM application_tailoring_verifications
        WHERE application_id=? AND generation_id=? AND verification_fingerprint=?''',
        (result['application_id'],result['generation_id'],result['verification_fingerprint'])).fetchall()
    if rows:
        _require(len(rows)==1, 'Duplicate native verification identity.')
        stored=json.loads(rows[0]['result_json'])
        comparable={k:v for k,v in stored.items() if k not in ('verification_id','created_at','cache_status')}
        _require(comparable==result, 'An existing native verification with this identity differs.')
        return stored
    stored={**result,'verification_id':uuid.uuid4().hex,'created_at':now}
    connection.execute('''INSERT INTO application_tailoring_verifications
        (application_id,verification_id,generation_id,phase8_version,verification_mode,verification_fingerprint,result_json,created_at)
        VALUES(?,?,?,?,?,?,?,?)''', (stored['application_id'],stored['verification_id'],stored['generation_id'],stored['phase8_version'],stored['verification_mode'],stored['verification_fingerprint'],json.dumps(stored,ensure_ascii=False,default=str),now))
    return stored


def _check_artifacts(material):
    from database import phase9f_tailoring_execution_manager as manager
    preview=material['preview']; source=material['source']; generation=material['generation']
    fresh=manager._resolve_prepared_source_artifact(decision=material['decision'], confirmation=material['confirmation'], expected_identity=material['execution']['source_artifact'])
    data=fresh.get('artifact_bytes')
    _require(isinstance(data,bytes) and len(data)==fresh.get('byte_size') and data==source.get('artifact_bytes') and hashlib.sha256(data).hexdigest()==fresh.get('sha256')==preview['selected_base_docx_sha256'], 'The authoritative Selected Base DOCX changed during acceptance.')
    _require(_file_hash(Path(generation['fit_result']['docx_path']))==preview['final_docx_sha256'], 'The fitted DOCX changed during acceptance.')


def _persist_acceptance(connection, *, material, reviewed_fingerprint, actor_label):
    """All application writes occur under the caller's BEGIN IMMEDIATE."""
    from database import application_blueprint_manager as bindings
    from database import phase9f_tailoring_execution_manager as manager
    from database.phase9f_session_revision import execution_table
    from tailoring.phase9f_v361_approval_floor import assess_phase9f_approval_floor
    preview=material['preview']; result=deepcopy(material['native_result']); decision=material['decision']; execution=material['execution']; generation=material['generation']; source=material['source']
    _require(preview_identity(preview)==reviewed_fingerprint, 'Native recheck changed; review it again before accepting.')
    _require(generation.get('application_id')==preview['application_id']==result['application_id'] and generation.get('generation_id')==preview['generation_id']==result['generation_id'], 'Native result identity differs.')
    _require(result.get('comparison_valid') is True and result.get('fit_one_page') is True, 'A comparable one-page verification is required.')
    _require(execution.get('confirmed_intensity')=='full', 'Only confirmed Full tailoring is supported by this release.')
    _require(_event_details(connection,preview['application_id'],decision) is None,'Policy transition was already accepted; reload the application.')
    _check_artifacts(material)
    projection=material['current_base']
    _validate_projection(projection,preview['transition'],preview['starting_document_contract'])
    floor=assess_phase9f_approval_floor(result,generation_id=preview['generation_id'],docx_sha256=preview['final_docx_sha256'])
    now=bindings._now()
    stored=_insert_native_receipt(connection,result,now)
    details={'version':VERSION,'transition':deepcopy(preview['transition']),'source_sha256':preview['selected_base_docx_sha256'],
        'execution_fingerprint':execution['execution_fingerprint'],'confirmation_fingerprint':execution['confirmation_fingerprint'],
        'generation_id':preview['generation_id'],'prior_verification_id':preview['prior_verification_id'],
        'verification_id':stored['verification_id'],'verification_fingerprint':stored['verification_fingerprint'],
        'reviewed_preview_fingerprint':reviewed_fingerprint,'final_docx_sha256':preview['final_docx_sha256'],
        'verified_generation_snapshot_fingerprint':stored['verified_generation_snapshot_fingerprint'],
        'starting_document_contract':deepcopy(preview['starting_document_contract']),'current_base':deepcopy(projection),
        'approval_floor_ready_at_acceptance':floor.get('ready') is True,'native_verdict':preview['native_verdict']}
    details['acceptance_fingerprint']=_fingerprint(details)
    # Same F identity and frozen stage inputs; only its mutable latest verification
    # pointer advances, exactly as normal Phase 8 does. Old receipts remain rows.
    if floor.get('ready') is True:
        approved=generation['status']=='approved'; status='completed' if approved else 'waiting_for_approval'
        stage='normal_phase8_verified' if approved else 'normal_phase8_verified_waiting_for_approval'
        outputs=deepcopy(execution.get('stage_outputs') or {})
        outputs['normal_phase8']={'generation_id':preview['generation_id'],'verification_id':stored['verification_id'],
            'verification_fingerprint':stored['verification_fingerprint'],'verified_generation_snapshot_fingerprint':stored['verified_generation_snapshot_fingerprint'], 'verified_before_approval':not approved}
        table=execution_table(connection,execution['execution_id'])
        updated=connection.execute(f'''UPDATE {table} SET status=?,current_stage=?,stage_outputs_json=?,
            phase8_verification_id=?,phase8_verification_fingerprint=?,last_error_code=NULL,last_error_message=NULL,updated_at=?,
            completed_at=CASE WHEN ?='completed' THEN ? ELSE completed_at END
            WHERE execution_id=? AND execution_fingerprint=? AND (generation_id IS NULL OR generation_id='')''',
            (status,stage,manager._dump(outputs),stored['verification_id'],stored['verification_fingerprint'],now,status,now,execution['execution_id'],execution['execution_fingerprint']))
        _require(updated.rowcount==1,'The exact Full execution changed during acceptance.')
        manager._insert_event(connection,execution_id=execution['execution_id'],application_id=preview['application_id'],attempt_number=execution['attempt_count'],event_type=EVENT,status=status,current_stage=stage,actor_label=actor_label,details={'generation_id':preview['generation_id'],'verification_fingerprint':stored['verification_fingerprint'],'acceptance_fingerprint':details['acceptance_fingerprint']},created_at=now)
    bindings._insert_binding_event(connection,event_type=EVENT,application_id=preview['application_id'],decision=decision,previous_decision_id=decision['decision_id'],actor_label=actor_label,created_at=now,event_details=details)
    _check_artifacts(material)
    return details


def accept_policy_transition(application_id: int, generation_id: str, *, reviewed_fingerprint: str, explicitly_confirmed: bool, actor_label='Local user') -> dict:
    """Fresh native replay + atomic adoption; no provider calls or regeneration."""
    _require(explicitly_confirmed is True,'Explicit scoring-policy acceptance is required.')
    from database import application_blueprint_manager as bindings
    from database import tailoring_verification_manager as verifications
    from tailoring.phase9f_policy_transition_v312b215c import run_transition_preview
    existing=bindings.get_current_application_blueprint_decision(int(application_id)) or {}
    accepted=existing.get('scoring_policy_transition')
    if accepted:
        _require(accepted['generation_id']==str(generation_id) and accepted['reviewed_preview_fingerprint']==reviewed_fingerprint,'A different policy transition is already current.')
        return accepted
    verifications.init_tailoring_verifications()
    connection=bindings._connect()
    try:
        other=verifications._connect()
        try:
            _require(Path(connection.execute('PRAGMA database_list').fetchone()[2]).resolve()==Path(other.execute('PRAGMA database_list').fetchone()[2]).resolve(),'Binding and verification databases differ.')
        finally:
            other.close()
        revision=connection.execute('PRAGMA data_version').fetchone()[0]
        material=run_transition_preview(int(application_id),str(generation_id),_return_material=True)
        from database.phase9f_tailoring_execution_manager import get_phase9f_tailoring_execution
        active=get_phase9f_tailoring_execution(int(application_id)) or {}
        _require(active.get('execution_fingerprint')==material['execution']['execution_fingerprint'], 'The selected fit is not owned by the active Full execution.')
        # The replay uses normal readers; any concurrent commit, including an
        # unrelated write, forces a fresh review rather than promoting stale data.
        connection.execute('BEGIN IMMEDIATE')
        _require(connection.execute('PRAGMA data_version').fetchone()[0]==revision,'Database changed during recheck; retry the policy acceptance.')
        details=_persist_acceptance(connection,material=material,reviewed_fingerprint=reviewed_fingerprint,actor_label=actor_label)
        connection.commit()
        return details
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
