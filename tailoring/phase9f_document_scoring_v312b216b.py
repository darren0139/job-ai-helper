"""Exact Base DOCX scoring adapter for new Phase 9F-B rankings.

Does not change historical source identity, native scoring, or approval.
Only ordinary JD scopes with readable authoritative DOCX are promoted.
Legacy source comparisons are not document receipts.
"""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, is_zipfile, BadZipFile
import json

VERSION = 'v312b216b-base-docx-native-ranking-v1'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), default=str).encode('utf-8')).hexdigest()


def text_hash(text):
    return sha256(text.encode('utf-8')).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ordinary_scope(jd):
    return not (jd.get('semantic_identity', {}).get('effective_requirement_scope')
        or jd.get('application_local_jd_user_inputs', {}).get('preferred_requirement_overrides'))


def prepare_document_input(source, artifact, jd):
    """After existing immutable master validation, bind actual readback separately."""
    if source.get('source_type') != 'base_resume' or not ordinary_scope(jd):
        return None
    prov = source.get('provenance') or {}
    if prov.get('artifact_type') != 'docx':
        return None
    content = artifact.get('artifact_bytes')
    require(artifact.get('authoritative') is True and artifact.get('master_version_id') == source['source_id']
        and isinstance(content, bytes) and bool(content) and len(content) == artifact.get('byte_size')
        and sha256(content).hexdigest() == artifact.get('sha256') == prov.get('artifact_sha256'),
        'Base DOCX byte authority changed')
    # Older opaque source artifacts retain legacy diagnostics, never document authority.
    if not is_zipfile(BytesIO(content)):
        return None
    try:
        with ZipFile(BytesIO(content)) as z:
            require('word/document.xml' in z.namelist() and '[Content_Types].xml' in z.namelist(),
                'Base artifact is not a Word DOCX')
    except BadZipFile as exc:
        raise ValueError('Base DOCX container is corrupt') from exc
    from parse import read_resume_docx
    with TemporaryDirectory(prefix='b216b_base_docx_') as folder:
        path = Path(folder) / 'source.docx'
        path.write_bytes(content)
        try:
            text = read_resume_docx(str(path), preserve_complete_text=True)
        except Exception as exc:
            raise ValueError('Authoritative Base DOCX readback failed: '+str(exc)) from exc
        require(sha256(path.read_bytes()).hexdigest() == artifact['sha256'], 'Base DOCX changed during readback')
    require(isinstance(text, str) and bool(text.strip()), 'Base DOCX has no extractable text')
    identity = {'version': VERSION, 'normalized_source_fingerprint': source['normalized_source_fingerprint'],
        'artifact_sha256': artifact['sha256'], 'artifact_byte_size': len(content),
        'resume_text_sha256': text_hash(text), 'source_profile_fingerprint': digest(source['resume_profile_snapshot'])}
    return {'identity': identity, 'identity_fingerprint': digest(identity), 'resume_text': text}


def score_document_input(source, jd):
    prepared = source['_document_score_input']
    identity = prepared['identity']
    require(ordinary_scope(jd), 'Document ranking does not support custom or reviewed scope yet')
    require(identity.get('version') == VERSION and prepared['identity_fingerprint'] == digest(identity)
        and identity.get('normalized_source_fingerprint') == source['normalized_source_fingerprint']
        and identity.get('artifact_sha256') == source['provenance']['artifact_sha256']
        and identity.get('source_profile_fingerprint') == digest(source['resume_profile_snapshot'])
        and identity.get('resume_text_sha256') == text_hash(prepared['resume_text']), 'Document scoring input is inconsistent')
    from tailoring.document_grounded_analysis import analyze_actual_resume_against_jd, validate_document_report
    result = analyze_actual_resume_against_jd(resume_text=prepared['resume_text'], jd_text=jd['raw_text'],
        jd_profile=deepcopy(jd['jd_profile']), resume_profile=deepcopy(source['resume_profile_snapshot']),
        canonical_requirements=deepcopy(jd['canonical_requirements']))
    report = {'raw_resume_text': result['raw_resume_text'], 'raw_jd_text': result['raw_jd_text'],
        'resume_profile': result['resume_profile'], 'stable_analysis': result['stable_analysis'],
        'meta': {'document_analysis': result['document_analysis']}}
    validate_document_report(report)
    receipt = {'identity': deepcopy(identity), 'identity_fingerprint': prepared['identity_fingerprint'],
        'resume_text': prepared['resume_text'], 'bounded_profile': deepcopy(result['resume_profile']),
        'document_analysis': deepcopy(result['document_analysis'])}
    receipt['fingerprint'] = digest(receipt)
    return result['stable_analysis'], result['keyword_match'], receipt


def validate_ranked_document_receipt(snapshot, candidate):
    receipt = snapshot.get('document_score_receipt')
    if receipt is None:
        require(candidate.get('document_score_authority') != VERSION, 'Missing ranked document receipt')
        return
    from tailoring.document_grounded_analysis import represented_profile, validate_document_report
    identity = receipt['identity']
    require(candidate.get('document_score_authority') == VERSION and identity.get('version') == VERSION
        and candidate.get('source_type') == 'base_resume' and receipt['identity_fingerprint'] == digest(identity)
        and receipt['fingerprint'] == digest({k:v for k,v in receipt.items() if k != 'fingerprint'})
        and identity.get('normalized_source_fingerprint') == candidate['normalized_source_fingerprint']
        and identity.get('source_profile_fingerprint') == digest(snapshot['resume_profile_snapshot'])
        and identity.get('resume_text_sha256') == text_hash(receipt['resume_text'])
        and receipt['bounded_profile'] == represented_profile(snapshot['resume_profile_snapshot'], receipt['resume_text']),
        'Ranked document receipt identity differs')
    from tailoring.phase9f_starting_source_ranking import PHASE9F_B_SCORING_POLICY_VERSION
    scoring_identity = {'exact_jd': snapshot['exact_jd_identity'], 'source': snapshot['source_identity'],
        'scoring_version': candidate['scoring_version'], 'capability_taxonomy_version': candidate['capability_taxonomy_version'],
        'evidence_policy_version': VERSION, 'scoring_policy_version': PHASE9F_B_SCORING_POLICY_VERSION,
        'retrieval_mode': 'lexical', 'document_score_input': identity,
        'document_native_identity': receipt['document_analysis']['identity']}
    require(candidate.get('evidence_policy_version') == VERSION and digest(scoring_identity) == candidate['stable_input_fingerprint'],
        'Document scoring identity differs from ranked input')
    validate_document_report({'raw_resume_text': receipt['resume_text'], 'raw_jd_text': snapshot['raw_jd_text_snapshot'],
        'resume_profile': receipt['bounded_profile'], 'stable_analysis': snapshot['stable_analysis_snapshot'],
        'meta': {'document_analysis': receipt['document_analysis']}})


def score_authority_label(candidate):
    return ('Actual Base DOCX · native document score' if candidate.get('document_score_authority') == VERSION
            else 'Legacy frozen profile/text · fresh-target diagnostic')
