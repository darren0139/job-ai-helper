"""V3.6.4: independently verify the *frozen Selected Base DOCX* for a Phase 9F handoff.

This is an actual document analysis; it is NOT a recovered uploaded Initial
analysis. Source bytes must already have passed the Phase 9F exact-artifact
binding contract. No generation, model calls, library reads, or database writes.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
from typing import Any

CONTRACT_VERSION = 'phase9f-v364-selected-base-source-docx-v1'


def build_frozen_selected_base_document_report(*, baseline_report: dict[str, Any],
                                               jd_text: str, source_artifact: dict[str, Any]
                                               ) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a new, sealed actual-DOCX selected-base report, never an Initial report.

    `source_artifact` must come from `_resolve_prepared_source_artifact` with
    `expected_identity=execution['source_artifact']`; refuse absent byte authority.
    """
    if not isinstance(baseline_report, dict) or not str(jd_text).strip():
        raise ValueError('Frozen selected-base DOCX verification requires a current JD and saved source analysis')
    if (baseline_report.get('meta') or {}).get('document_analysis'):
        raise ValueError('An existing document-grounded starting analysis must use the original Initial/Selected Base path')
    content = source_artifact.get('artifact_bytes') if isinstance(source_artifact, dict) else None
    if not isinstance(content, bytes) or not content:
        raise ValueError('The frozen Selected Base DOCX bytes are unavailable')
    expected_sha = str(source_artifact.get('sha256') or '')
    sha = hashlib.sha256(content).hexdigest()
    if source_artifact.get('artifact_type') != 'docx' or sha != expected_sha or len(sha) != 64:
        raise ValueError('The frozen Selected Base DOCX does not match its authorized source identity')
    try:
        expected_size = int(source_artifact.get('byte_size'))
    except (ValueError, TypeError):
        expected_size = -1
    if expected_size != len(content):
        raise ValueError('The frozen Selected Base DOCX byte count changed')

    # read_resume_docx is the same actual-DOCX extraction path Phase 8 uses for
    # final DOCX. Temporary source bytes are not stored or edited in the repo.
    from parse import read_resume_docx
    from tailoring.document_grounded_analysis import (
        analyze_actual_resume_against_jd, seal_document_report,
    )
    from tailoring.jd_user_input_overrides import apply_application_session_jd_user_inputs
    with TemporaryDirectory(prefix='phase9f_base_verify_') as folder:
        path = Path(folder) / 'frozen_selected_base.docx'
        path.write_bytes(content)
        text = read_resume_docx(str(path), preserve_complete_text=True)
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Frozen Selected Base DOCX contains no extractable résumé text')
    expected = (baseline_report.get('stable_analysis') or {}).get('canonical_requirements')
    actual = analyze_actual_resume_against_jd(
        resume_text=text, jd_text=jd_text,
        jd_profile=baseline_report.get('jd_profile') or {},
        resume_profile=baseline_report.get('resume_profile') or {},
        canonical_requirements=expected,
    )
    preferences = ((baseline_report.get('meta') or {}).get('jd_user_inputs') or {}).get('preferred_requirement_overrides') or []
    actual = apply_application_session_jd_user_inputs(
        actual, raw_jd_text=jd_text, raw_resume_text=text,
        preferred_requirements=preferences,
    )
    actual['raw_resume_text'] = text
    actual['raw_jd_text'] = jd_text
    # Only a verified actual-document report is promoted as the Phase 8
    # starting context. The old profile-based analysis is not modified.
    sealed = deepcopy(baseline_report)
    for key in ('stable_analysis', 'keyword_match', 'resume_profile', 'jd_profile',
                'raw_resume_text', 'raw_jd_text'):
        if key in actual:
            sealed[key] = deepcopy(actual[key])
    sealed.pop('frozen_initial_resume_report', None)  # No uploaded Initial exists here.
    sealed.setdefault('meta', {})['document_analysis'] = deepcopy(actual['document_analysis'])
    seal_document_report(sealed)
    source_authority = sealed['meta']['document_analysis']
    contract = {
        'version': CONTRACT_VERSION,
        'mode': 'selected_base_docx_only',
        'initial_status': 'not_a_separately_uploaded_initial_document',
        'selected_base_docx_sha256': sha,
        'selected_base_resume_text_sha256': source_authority['resume_text_sha256'],
        'selected_base_document_analysis_fingerprint': source_authority['fingerprint'],
        'comparison_scope': 'selected_base_document_vs_actual_fitted_document',
    }
    return sealed, contract
