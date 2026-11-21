"""Explicit bindings for individual hard floors at native candidate evaluation."""
from hashlib import sha256
import json
from pathlib import Path

from tailoring.phase9f_v37_hard_floor import HARD, verified_research_trial


def _sha(data):
    return sha256(data).hexdigest()


def _fingerprint(data):
    return _sha(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                           allow_nan=False).encode())


def _requirement_scope(rows):
    scope = {}
    for row in rows:
        rid, kind, text = row['requirement_id'], row['importance'], row['text']
        if not all(isinstance(item, str) and item.strip() for item in (rid, kind, text)) or rid in scope:
            raise ValueError('Invalid or duplicate frozen JD requirement.')
        scope[rid] = (kind, text)
    if not scope:
        raise ValueError('Empty frozen JD requirement scope.')
    return scope


def _evidence_fingerprint(score):
    return _fingerprint({
        'score': score['deterministic_alignment_score'],
        'requirements': sorted(score['canonical_requirements'], key=lambda row: row['requirement_id']),
    })


def _source_binding(audit, raw_jd, baseline_report, incumbent_pdf):
    if audit.get('verified') is not True or baseline_report.get('raw_jd_text') != raw_jd:
        raise ValueError('The verified source and exact frozen JD are required.')
    scope = _requirement_scope(baseline_report['stable_analysis']['canonical_requirements'])
    return {
        'generation_id': audit['generation_id'], 'docx_sha256': audit['docx_sha256'],
        'pdf_sha256': _sha(incumbent_pdf), 'jd_sha256': _sha(raw_jd.encode()),
        'scope_sha256': _fingerprint(scope), 'projects_sha256': _fingerprint(audit['projects']),
    }, scope


def _pdf_pages(data):
    from io import BytesIO

    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        return len(PdfReader(BytesIO(data)).pages)
    except PdfReadError as error:
        raise ValueError('The guarded PDF cannot be read.') from error


def _protected_floors(score):
    floors = {}
    for row in score['canonical_requirements']:
        if row['importance'] in HARD and row['match_label'] != 'none':
            strength = row.get('evidence_strength')
            if (type(strength) is not int or not 1 <= strength <= 5
                    or not any(isinstance(item, dict) and isinstance(item.get('text'), str) and item['text'].strip()
                               for item in row.get('evidence') or [])):
                raise ValueError('A credited hard requirement lacks verified native evidence or strength.')
            floors[row['requirement_id']] = {'label': row['match_label'], 'strength': strength}
    return floors


def bind_guarded_floor(*, audit, raw_jd, baseline_report, incumbent_pdf, trusted_native):
    """Create an invocation binding from an operator-trusted actual-document result."""
    from tailoring.phase9f_automatic_bestof_v30 import _rows

    binding, scope = _source_binding(audit, raw_jd, baseline_report, incumbent_pdf)
    score, error = _rows(trusted_native)
    if (error or score['sha256'] != binding['docx_sha256'] or _pdf_pages(incumbent_pdf) != 1
            or _requirement_scope(trusted_native['canonical_requirements']) != scope):
        raise ValueError('The trusted native source and one-page receipt must match the frozen scope.')
    return {**binding, 'scoring_version': score['version'],
            'evidence_sha256': _evidence_fingerprint(trusted_native), 'floors': _protected_floors(trusted_native)}


def verify_guarded_source(binding, *, audit, raw_jd, baseline_report, fit, output_root):
    """Reject stale source inputs before any solver, scorer or materializer call."""
    pdf = Path(fit['pdf_path']).resolve()
    pdf.relative_to(output_root)
    if pdf.suffix.lower() != '.pdf' or fit.get('page_count') != 1:
        raise ValueError('The guarded source requires an owned one-page PDF.')
    data = pdf.read_bytes()
    actual, scope = _source_binding(audit, raw_jd, baseline_report, data)
    if any(binding[key] != value for key, value in actual.items()) or _pdf_pages(data) != 1:
        raise ValueError('Stale JD, source document, PDF or source evidence binding.')
    return scope


def verify_guarded_wording(audit, proposal):
    groups = {row['project']: row for row in audit['projects']}
    changes = proposal['projects']
    if (len(groups) != len(audit['projects'])
            or [row['project'] for row in changes] != list(groups)):
        raise ValueError('The guarded challenger must retain the exact project set and order.')
    for row in changes:
        source = groups[row['project']]
        if row['before'] != [bullet['text'] for bullet in source['final']]:
            raise ValueError('Challenger incumbent wording differs from the source audit.')
        permitted = {name: {bullet['text'] for bullet in source[key]} for name, key in (
            ('Selected Base', 'base'), ('Evidence Library', 'library'), ('Current final', 'final'))}
        for text, labels in zip(row['after'], row['sources'], strict=True):
            if not labels or any(text not in permitted.get(label, ()) for label in labels):
                raise ValueError('Challenger bullet source ownership is unverified.')


def verify_guarded_incumbent(binding, scope, score):
    if (score['scoring_version'] != binding['scoring_version']
            or _requirement_scope(score['canonical_requirements']) != scope
            or _evidence_fingerprint(score) != binding['evidence_sha256']
            or _protected_floors(score) != binding['floors']):
        raise ValueError('Stale native scorer or incumbent evidence binding.')


def verify_guarded_artifact(proposal, docx, pdf):
    from zipfile import BadZipFile

    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError
    from lxml.etree import XMLSyntaxError

    from tailoring.phase9f_joint_resume_optimizer_v2_6 import _bullet_locations

    if _pdf_pages(pdf.read_bytes()) != 1:
        raise ValueError('The guarded challenger PDF must contain exactly one page.')
    expected = [{'project': row['project'], 'before': row['after']} for row in proposal['projects']]
    try:
        document = Document(docx)
        groups = _bullet_locations(document, expected)
    except (BadZipFile, PackageNotFoundError, XMLSyntaxError) as error:
        raise ValueError('The guarded DOCX cannot be read.') from error
    if any(not group for group in groups):
        raise ValueError('The guarded DOCX has an empty project.')
    positions = {paragraph._element: index for index, paragraph in enumerate(document.paragraphs)}
    starts = [positions[group[0]._element] for group in groups]
    if starts != sorted(starts):
        raise ValueError('The guarded DOCX changed the expected project order.')


def verify_guarded_scores(binding, scope, before, after):
    if (_requirement_scope(after['canonical_requirements']) != scope
            or after['scoring_version'] != binding['scoring_version']):
        raise ValueError('The guarded challenger changed frozen requirements or scorer identity.')
    _protected_floors(after)

    def trial(score):
        return {'status': 'verified', 'pages': 1, 'score': score['deterministic_alignment_score'],
                'jd_sha256': binding['jd_sha256'], 'scoring_version': score['scoring_version'],
                'layout_reference_sha256': binding['docx_sha256'],
                'requirements': [{**row, 'id': row['requirement_id']} for row in score['canonical_requirements']]}

    return verified_research_trial(trial(before), trial(after), binding['floors'])
