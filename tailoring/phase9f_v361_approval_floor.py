"""Fail-closed, read-only Phase 9F final vs Initial AND Selected Base floor.

No scoring, parsing, DB writes, or inference from a missing comparison.  An
approval candidate must have a currently verified actual DOCX and two native
comparable A/B receipts.  This module does not decide which optimization slate
is best; it protects approval of the saved fitted A.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

VERSION = 'phase9f-v3.6.1-approval-base-floor-v1'
HARD = frozenset({'deal_breaker', 'required', 'core'})
RANK = {'none': 0, 'weak': 1, 'transferable': 2, 'direct': 3}


def _fail(reason: str) -> dict[str, Any]:
    return {'ready': False, 'reason': reason, 'version': VERSION, 'comparisons': {}}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) and 0 <= value <= 100 else None


def _one_ab(name: str, receipt: Any) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(receipt, dict) or receipt.get('comparable') is not True:
        return None, name + ': native comparison absent or incompatible'
    summary = receipt.get('summary')
    rows = receipt.get('requirements')
    if not isinstance(summary, dict) or not isinstance(rows, list) or not rows:
        return None, name + ': native scores or requirement receipts missing'
    before = _number(summary.get('initial_score'))
    after = _number(summary.get('tailored_score'))
    delta = summary.get('score_delta')
    if (before is None or after is None or isinstance(delta, bool)
            or not isinstance(delta, (int, float)) or not math.isfinite(float(delta))
            or abs(float(delta) - (after-before)) > 1e-5):
        return None, name + ': invalid or inconsistent native score delta'
    if after < before - 1e-6:
        return None, name + ': final Job Match score regressed'
    seen = set()
    hard_losses = []
    for row in rows:
        if not isinstance(row, dict):
            return None, name + ': malformed requirement receipt'
        ident = row.get('requirement_id')
        a, b = row.get('initial'), row.get('tailored')
        if not isinstance(ident, str) or not ident or ident in seen or not isinstance(a, dict) or not isinstance(b, dict):
            return None, name + ': ambiguous requirement identity'
        seen.add(ident)
        if a.get('requirement_id') != ident or b.get('requirement_id') != ident:
            return None, name + ': requirement identity is inconsistent'
        importance = str(a.get('importance') or '').lower()
        left, right = str(a.get('final_match') or '').lower(), str(b.get('final_match') or '').lower()
        if (not importance or importance != str(b.get('importance') or '').lower()
                or left not in RANK or right not in RANK):
            return None, name + ': invalid requirement match or importance'
        if importance in HARD and RANK[right] < RANK[left]:
            hard_losses.append(ident)
    if hard_losses:
        return None, name + ': Required/Core evidence regressed: ' + ', '.join(hard_losses)
    return {'before': before, 'after': after, 'delta': round(after-before, 6),
            'hard_regressions': [], 'requirements_checked': len(rows)}, ''


def assess_phase9f_approval_floor(receipt: Any, *, generation_id: str,
                                    docx_sha256: str) -> dict[str, Any]:
    """Pure receipt validation; fail closed on missing actual-document authority."""
    if not isinstance(receipt, dict) or receipt.get('generation_id') != generation_id:
        return _fail('Missing or foreign Phase 8 generation receipt')
    if (receipt.get('fit_one_page') is not True or receipt.get('comparison_valid') is not True
            or receipt.get('approval_ready') is not True):
        return _fail('Phase 8 fit, identity or approval readiness is not verified')
    authority = receipt.get('document_analysis')
    if not isinstance(authority, dict):
        return _fail('Missing Phase 8 actual fitted DOCX analysis receipt')
    if not isinstance(docx_sha256, str) or len(docx_sha256) != 64:
        return _fail('Missing or invalid expected fitted DOCX digest')
    digest = authority.get('final_document_sha256')
    if not isinstance(digest, str) or len(digest) != 64:
        return _fail('Phase 8 actual fitted DOCX hash missing or invalid')
    if digest != docx_sha256:
        return _fail('Phase 8 document hash differs from the expected fitted DOCX')
    selected = receipt.get('selected_base_analysis')
    if not isinstance(selected, dict):
        return _fail('Selected Base identity/analysis unavailable')
    contract = receipt.get('starting_document_contract')
    if (receipt.get('initial_document_status') == 'not_available_for_handoff'
            and not (isinstance(contract, dict) and contract.get('mode') == 'selected_base_docx_only')):
        return _fail('Selected Base-only verification role contract missing or invalid')
    if isinstance(contract, dict) and contract and contract.get('mode') != 'selected_base_docx_only':
        return _fail('Unknown Selected Base document role contract')
    if isinstance(contract, dict) and contract.get('mode') == 'selected_base_docx_only':
        from tailoring.phase9f_v364_document_reverify import CONTRACT_VERSION
        doc = receipt.get('document_analysis') or {}
        selected_source = selected.get('document_analysis') or {}
        if (contract.get('version') != CONTRACT_VERSION
                or contract.get('initial_status') != 'not_a_separately_uploaded_initial_document'
                or receipt.get('initial_document_status') != 'not_available_for_handoff'
                or selected.get('same_as_initial') is not True
                or not isinstance(doc.get('initial'), dict)
                or doc['initial'] != selected_source
                or selected_source.get('fingerprint') != contract.get('selected_base_document_analysis_fingerprint')
                or selected_source.get('resume_text_sha256') != contract.get('selected_base_resume_text_sha256')
                or not isinstance(contract.get('selected_base_docx_sha256'), str)
                or len(contract['selected_base_docx_sha256']) != 64):
            return _fail('Frozen Selected Base DOCX identity/role contract inconsistent')
        chosen_result, why = _one_ab('Selected Base', receipt.get('job_match_ab'))
        if why:
            return _fail(why)
        if receipt.get('verdict') not in ('improved', 'maintained'):
            return _fail('Native Selected Base versus Final verdict is not safe')
        return {'ready': True,
                'reason': 'Actual fitted DOCX meets frozen Selected Base DOCX floor; separate Initial unavailable',
                'version': VERSION, 'comparisons': {'Selected Base': chosen_result},
                'starting_role': 'selected_base_docx_only', 'docx_sha256': docx_sha256}
    initial_result, why = _one_ab('Initial', receipt.get('job_match_ab'))
    if why:
        return _fail(why)
    if selected.get('same_as_initial') is True:
        selected_result = dict(initial_result)
    elif selected.get('same_as_initial') is False:
        selected_result, why = _one_ab('Selected Base', receipt.get('selected_base_job_match_ab'))
        if why:
            return _fail(why)
        if abs(selected_result['after'] - initial_result['after']) > 1e-6:
            return _fail('Final score inconsistent across native baseline comparisons')
    else:
        return _fail('Selected Base versus Initial relationship not established')
    if receipt.get('verdict') not in ('improved', 'maintained'):
        return _fail('Native Phase 8 verdict is not approved for no-regression')
    return {'ready': True, 'reason': 'Actual fitted A meets both Initial and Selected Base floors',
            'version': VERSION, 'comparisons': {'Initial': initial_result, 'Selected Base': selected_result},
            'docx_sha256': docx_sha256}


def verify_current_phase9f_floor(application_id: int, generation_id: str,
                                 generation: dict[str, Any]) -> dict[str, Any]:
    """Use existing verification-manager gate, then validate exact DOCX bytes."""
    from database.tailoring_verification_manager import (
        get_latest_tailoring_verification, get_tailoring_verification_approval_gate,
    )
    gate = get_tailoring_verification_approval_gate(application_id, generation_id)
    if not isinstance(gate, dict) or gate.get('ready') is not True:
        return _fail('Current Phase 8 verification gate is not ready')
    result = get_latest_tailoring_verification(application_id, generation_id)
    fit = generation.get('fit_result')
    if not isinstance(fit, dict) or fit.get('fit_one_page') is not True:
        return _fail('The saved fitted generation is not one page')
    path = fit.get('docx_path')
    if not isinstance(path, str) or not path.strip():
        return _fail('Saved fitted DOCX path missing')
    try:
        sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return _fail('Actual fitted DOCX could not be read')
    source_contract = (result or {}).get('starting_document_contract') or {}
    if source_contract.get('mode') == 'selected_base_docx_only':
        from database.phase9f_tailoring_execution_manager import get_phase9f_tailoring_execution
        execution = get_phase9f_tailoring_execution(int(application_id))
        saved_source_sha = ((execution or {}).get('source_artifact') or {}).get('sha256')
        if (not isinstance(saved_source_sha, str)
                or saved_source_sha != source_contract.get('selected_base_docx_sha256')):
            return _fail('Selected Base DOCX no longer matches the frozen Phase 9F source binding')
    return assess_phase9f_approval_floor(result, generation_id=generation_id, docx_sha256=sha)
