"""Request-local experimental JD admission, before native span/decomposition work.

No environment switch, text rewriting, global keyword exclusion or published
identity change. Administrative field syntax and section context are required.
"""
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
import re

ACTIVE = ContextVar('experimental_jd_metadata_admission', default=None)
PARSER_VERSION = 'jd-administrative-admission-v1'
SCORER_VERSION = 'stable-evidence-v1.22-phase6d26'
NAMESPACE = 'jd-metadata-comparison-v1'
ADMIN_HEADINGS = {'job information', 'employment details', 'job details', 'posting details',
                  'employment information', 'job particulars'}
FIELD_KEYS = {'period', 'location', 'working hours', 'work hours', 'employment type',
              'job type', 'salary', 'work location', 'working days'}
FIELDS = ('deal_breakers', 'required_skills', 'responsibilities', 'soft_skills',
          'preferred_skills', 'tools_technologies')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def classify(raw):
    """Keep exact original line/offset receipts; ambiguity never means NONE."""
    from . import stable_evidence_scoring as n
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('Experimental classification requires the original raw JD')
    lines = raw.splitlines(keepends=True)
    # Consult the actual native structural decisions, including inferred list
    # headings, without recursively applying this experiment.
    token = ACTIVE.set(None)
    try:
        native_spans = n._raw_jd_content_spans(raw)
    finally:
        ACTIVE.reset(token)
    native_headings = {n._normalise_jd_section_heading(s.get('section_heading')): s['section']
        for s in native_spans if s.get('section_heading') and s.get('section')}
    records = []
    section, heading, pending_field, offset = '', '', False, 0
    for index, original in enumerate(lines, 1):
        text = original.rstrip('\r\n')
        value = re.sub(r'^\s*(?:[-*\u2022]+|\d+[.)])\s*', '', text).strip()
        key = n._normalise_jd_section_heading(value)
        native_section = ('' if key in ADMIN_HEADINGS else
                          n._raw_section_for_heading(value) or native_headings.get(key, ''))
        explicit, native_reason = n._unheaded_span_status({'text': value})
        field, colon, payload = value.partition(':')
        field_key = n._normalise_jd_section_heading(field)
        if field_key in FIELD_KEYS:
            native_section = ''  # An inferred child list cannot turn a field into a heading.
        mixed_field = (explicit and bool(colon) and field_key in FIELD_KEYS
            and not re.match(r'^(?:(?:a|the)\s+)?(?:candidate|you|successful applicant|must|required|experience|knowledge|proficiency)\b', payload.strip(), re.I))
        classification, reason, reset = 'BLANK', 'empty_line', False
        if native_section:
            section, heading, pending_field = native_section, text, False
            classification, reason = 'STRUCTURAL_HEADING', 'native_controlled_heading'
        elif key in ADMIN_HEADINGS:
            section, heading, pending_field = 'administrative', text, False
            classification, reason, reset = 'ADMINISTRATIVE_METADATA', 'controlled_admin_boundary', True
        elif mixed_field:
            classification, reason, pending_field = 'AMBIGUOUS_CONTENT', 'mixed_administrative_field_and_obligation_requires_review', False
        elif explicit:
            classification = {'responsibilities': 'RESPONSIBILITY', 'preferred': 'PREFERRED_QUALIFICATION'}.get(section, 'CANDIDATE_QUALIFICATION')
            reason, pending_field = 'independent_candidate_obligation', False
        elif value:
            if field_key in FIELD_KEYS and (colon or key in FIELD_KEYS):
                classification, reason = 'ADMINISTRATIVE_METADATA', 'administrative_field_syntax'
                pending_field = not bool(payload.strip())
            elif pending_field:
                classification, reason, pending_field = 'ADMINISTRATIVE_METADATA', 'adjacent_administrative_value', False
            elif re.fullmatch(r'(?:Mon(?:day)?\s*[-\u2013\u2014]\s*Fri(?:day)?|Monday to Friday)\s+\d.*(?:am|pm)', value, re.I):
                classification, reason = 'ADMINISTRATIVE_METADATA', 'weekday_clock_schedule_literal'
            elif value.endswith(':') and len(value.split()) <= 8:
                section, heading = 'ambiguous', text
                classification, reason, reset = 'AMBIGUOUS_HEADING', 'unknown_boundary', True
            elif section in ('responsibilities', 'requirements', 'core', 'preferred'):
                classification = {'responsibilities': 'RESPONSIBILITY', 'preferred': 'PREFERRED_QUALIFICATION'}.get(section, 'CANDIDATE_QUALIFICATION')
                reason = 'native_requirement_section'
            elif section == 'stop':
                classification, reason = 'NON_REQUIREMENT_CONTEXT', 'native_stop_section'
            elif native_reason in ('contextual_company_or_team_prose', 'recruiting_call_to_action'):
                classification, reason = 'NATIVE_CONTEXT', 'retain_native_sentence_admission'
            else:
                classification, reason = 'AMBIGUOUS_CONTENT', 'no_independent_obligation_or_administrative_field'
        admitted = classification in ('RESPONSIBILITY', 'CANDIDATE_QUALIFICATION', 'PREFERRED_QUALIFICATION', 'NATIVE_CONTEXT')
        eligibility_override = explicit and bool(re.match(
            r'^(?:(?:a|the)\s+candidate\s+must\b|must\s+be\s+(?:available|willing)\b|'
            r'(?:location|working hours):\s*(?:(?:a|the)\s+)?(?:candidate\s+must|must\s+be)\b)', value, re.I))
        records.append({'line_index': index, 'raw_text': text, 'raw_span': [offset, offset+len(text)],
            'section': section, 'section_heading': heading, 'classification': classification,
            'reason': reason, 'admitted': admitted, 'reset_section': reset,
            'explicit_eligibility_admission': eligibility_override,
            'source': f'raw_jd.lines[{index}]', 'parser_version': PARSER_VERSION})
        offset += len(original)
    return {'parser_version': PARSER_VERSION, 'raw_jd_text': raw, 'lines': records,
            'ambiguous_content': [r for r in records if r['classification'] == 'AMBIGUOUS_CONTENT']}


def line_decision(raw, line_index):
    state = ACTIVE.get()
    if state is None:
        return None
    if raw != state['raw_jd_text']:
        raise ValueError('Experimental raw JD authority changed during parsing')
    return state['lines'][line_index-1]


def build_metadata_preview(*, developer_enabled=False, source_projection=None, **inputs):
    """Explicit isolated scorer; v17/v20/v21 routes never install this context."""
    if not developer_enabled:
        raise ValueError('JD metadata policy is development-gated and defaults OFF')
    from .coordinated_integration import build_coordinated_analysis
    receipt = classify(inputs.get('raw_jd_text'))
    receipt['original_jd_profile'] = deepcopy(inputs.get('jd_profile'))
    token = ACTIVE.set(receipt)
    try:
        result = build_coordinated_analysis(source_projection=source_projection, **deepcopy(inputs))
    finally:
        ACTIVE.reset(token)
    result['scoring_version'] = SCORER_VERSION
    result['jd_metadata_parser_version'] = PARSER_VERSION
    result['preview_namespace'] = NAMESPACE
    result['jd_metadata_classification'] = receipt
    for row in result['canonical_requirements']:
        if row.get('coordinated_action_receipt'):
            row['coordinated_action_receipt']['policy_identities'].update(
                scoring_version=SCORER_VERSION, jd_metadata_parser_version=PARSER_VERSION)
    if receipt['ambiguous_content'] or not result['canonical_requirements']:
        for field in ('deterministic_alignment_score', 'required_core_coverage_score',
                      'preferred_coverage_score', 'evidence_strength_score', 'alignment_band', 'boundary_status'):
            result[field] = None
        result['score_publication_status'] = ('WITHHELD_PENDING_JD_CLASSIFICATION_REVIEW'
            if receipt['ambiguous_content'] else 'WITHHELD_NO_ADMISSIBLE_JD_REQUIREMENTS')
    result['input_fingerprint'] = digest({'base': result['input_fingerprint'],
        'scoring_version': SCORER_VERSION, 'parser_version': PARSER_VERSION,
        'original_jd_profile': inputs.get('jd_profile'), 'classification': receipt})
    return result
