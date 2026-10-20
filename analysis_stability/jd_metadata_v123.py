"""Bounded structural refinement. The v1.22 module and defaults are immutable."""
from copy import deepcopy
import re

from . import jd_metadata_policy as previous

SCORER_VERSION = 'stable-evidence-v1.23-phase6d27'
PARSER_VERSION = 'jd-administrative-boundary-refinement-v2'
NAMESPACE = 'jd-metadata-comparison-v2'
QUALIFICATION_HEADINGS = {'skillset', 'candidate skillset', 'additional qualifications include'}
RESPONSIBILITY_HEADINGS = {'other responsibilities include', 'additional responsibilities include'}
ADMIN_FIELDS = {'position', 'working location', 'salary range'}


def surface(text):
    return re.sub(r'^\s*(?:[-*\u2022]+|\d+[.)]|[a-z][.)])\s+', '', text).strip()


def child_kind(text):
    text = surface(text)
    if re.match(r'^(?:(?:strong|good|solid|working|relevant)\s+)?(?:experience|knowledge|proficiency|ability|familiarity)\b|'
                r'^(?:strong|good)\b.*\bskills\b|^meticulous\b.*\bdetail\b|^team player\b', text, re.I):
        return 'requirements'
    if re.match(r'^(?:support|provide|conduct|develop|design|build|maintain|implement|test|manage|deliver|analyse|analyze)\b',text,re.I):
        return 'responsibilities'
    return None


def classify(raw):
    from . import stable_evidence_scoring as n
    result = deepcopy(previous.classify(raw))
    result['parser_version'] = PARSER_VERSION
    records = result['lines']
    metadata_values = {}
    for row in records:
        if row['classification'] == 'ADMINISTRATIVE_METADATA':
            text = surface(row['raw_text'])
            value = text.partition(':')[2].strip() if ':' in text else text
            if value:
                metadata_values.setdefault(value.casefold(), row['source'])

    def change(row, category, reason, admitted=False, **extra):
        row.update(classification=category, reason=reason, admitted=admitted, **extra)

    active, parent_heading, previous_child, after_administrative = None, '', False, False
    last_known_section, last_known_heading = '', ''
    for index, row in enumerate(records):
        row['v22_classification'],row['v22_reason'] = row['classification'],row['reason']
        row['parser_version'] = PARSER_VERSION
        text = surface(row['raw_text'])
        key = n._normalise_jd_section_heading(text)
        field,colon,payload = text.partition(':')
        field_key = n._normalise_jd_section_heading(field)
        if row['classification'] == 'STRUCTURAL_HEADING':
            last_known_section,last_known_heading = row['section'],row['raw_text']
            active,previous_child = None,False
            after_administrative = False
        if not text:
            previous_child = False
            continue

        # Unknown labels require corroborating children AND an already verified
        # qualification section. Exact semantic introducers require two children.
        children = []
        for child in records[index+1:]:
            value = surface(child['raw_text'])
            if not value:
                if children: break
                continue
            if (child['classification'] == 'STRUCTURAL_HEADING' or value.endswith(':')
                    or child['classification'] == 'ADMINISTRATIVE_METADATA'):
                break
            children.append(child_kind(value))
            if len(children) == 4: break
        qualifier = key in QUALIFICATION_HEADINGS and children.count('requirements') >= 2
        duty = key in RESPONSIBILITY_HEADINGS and children.count('responsibilities') >= 2
        unfamiliar = (row['classification'] == 'AMBIGUOUS_HEADING'
            and last_known_section in ('requirements','core','preferred')
            and len(children) >= 2 and all(kind == 'requirements' for kind in children))
        if qualifier or duty or unfamiliar:
            active = 'responsibilities' if duty else ('preferred' if last_known_section == 'preferred' else 'requirements')
            parent_heading = last_known_heading if not duty and last_known_section == 'requirements' else row['raw_text']
            change(row,'STRUCTURAL_HEADING','corroborated_local_candidate_list',
                section_override=active, allocation_heading=parent_heading,
                structural_support={'child_kinds':children,'parent_section':last_known_section,'parent_heading':last_known_heading})
            previous_child = False
            after_administrative = False
            continue
        if row['classification'] in ('ADMINISTRATIVE_METADATA','AMBIGUOUS_HEADING'):
            active,previous_child = None,False
        if row['classification'] == 'ADMINISTRATIVE_METADATA':
            # v1.23 never lets later administrative prose inherit a scoring section.
            row['reset_section'] = True
            after_administrative = True
            last_known_section,last_known_heading = '', ''
            continue
        if colon and field_key in ADMIN_FIELDS and not re.search(r'\b(?:must|required|candidate|experience)\b',payload,re.I):
            change(row,'ADMINISTRATIVE_METADATA','anchored_posting_field',reset_section=True)
            active,previous_child = None,False
            after_administrative = True
            last_known_section,last_known_heading = '', ''
            continue
        if re.fullmatch(r'(?:Please note that )?only shortlisted applicants will be notified[.!]?',text,re.I):
            change(row,'ADMINISTRATIVE_METADATA','explicit_shortlisting_notification',reset_section=True)
            active,previous_child = None,False
            after_administrative = True
            last_known_section,last_known_heading = '', ''
            continue
        contract_start = re.match(r'^This is a \d+[- ]year contract\b',text,re.I)
        if contract_start and re.search(r'\b(?:must|required|you|candidate|available|willing)\b',text,re.I):
            change(row,'AMBIGUOUS_CONTENT','mixed_contract_duration_and_candidate_obligation',reset_section=True)
            active,previous_child = None,False
            after_administrative = True
            last_known_section,last_known_heading = '', ''
            continue
        if re.fullmatch(r'This is a \d+[- ]year contract(?: position)?[^.]*\.(?: All applicants will be notified[^.]*\.)?',text,re.I):
            change(row,'ADMINISTRATIVE_METADATA','explicit_contract_duration_and_notification',reset_section=True)
            active,previous_child = None,False
            after_administrative = True
            last_known_section,last_known_heading = '', ''
            continue
        if after_administrative and row['classification'] in ('CANDIDATE_QUALIFICATION','RESPONSIBILITY','PREFERRED_QUALIFICATION','NATIVE_CONTEXT'):
            if re.fullmatch(r'Those with (?:relevant|suitable) (?:skillsets?|skills) and interests may apply[.!]?',text,re.I):
                change(row,'NON_REQUIREMENT_CONTEXT','generic_recruiting_invitation_after_administrative_boundary')
                continue
            independently_admitted = row['explicit_eligibility_admission'] or bool(n._unheaded_role_rows({
                'text':text,'raw_text':row['raw_text'],'line_index':row['line_index'],'span_id':'admission_probe'})[0])
            if not independently_admitted:
                change(row,'AMBIGUOUS_CONTENT','unestablished_candidate_content_after_administrative_boundary',reset_section=True)
                continue
        if active and row['classification'] not in ('STRUCTURAL_HEADING','AMBIGUOUS_CONTENT','CANDIDATE_QUALIFICATION','RESPONSIBILITY','PREFERRED_QUALIFICATION'):
            previous_child = False
        if active:
            kind = child_kind(text)
            wrapped = previous_child and (row['raw_text'][:1].isspace() or re.match(r'^(?:and|with|using|for|to|in|of)\b',text,re.I))
            if kind == ('requirements' if active == 'preferred' else active) or wrapped:
                change(row,{'requirements':'CANDIDATE_QUALIFICATION','preferred':'PREFERRED_QUALIFICATION','responsibilities':'RESPONSIBILITY'}[active],
                    'child_of_corroborated_candidate_list',True)
                previous_child = True
                continue
            previous_child = False

        if row['classification'] != 'AMBIGUOUS_CONTENT':
            continue
        # Only unheaded preamble duplicates of independently classified original
        # field values acquire metadata status; no arbitrary text/skill blacklist.
        if row['section'] == '' and text.casefold() in metadata_values:
            change(row,'ADMINISTRATIVE_METADATA','verified_duplicate_posting_value',
                alias_of=metadata_values[text.casefold()],reset_section=True)
            after_administrative = True
            last_known_section,last_known_heading = '', ''
            continue
        if (row['line_index'] <= 2 and row['section'] == '' and len(text.split()) <= 20
                and re.search(r'\b(?:engineer|developer)\b',text,re.I)
                and not re.search(r'[.!?]|\b(?:must|will|required|experience|skills|develop|design|maintain|with|proficient|familiar|knowledge|ability|able|expertise|understanding|can)\b',text,re.I)):
            change(row,'NON_REQUIREMENT_CONTEXT','short_unheaded_role_title')
            continue
        candidate_cues = re.search(r'\b(?:candidate|applicant|you|your|must|required|experience|skills|responsible|will)\b',text,re.I)
        organisation_predicate = re.search(r'\bis (?:an?|the)\b.*\b(?:agency|division|world leader|group|centre|center)\b|\bis developing a suite of\b|\bis dedicated to the promotion of\b',text,re.I)
        role_purpose = re.match(r'^As a [^.!?]+, this role is crucial in\b',text,re.I)
        if row['section'] == '' and (organisation_predicate or role_purpose) and not candidate_cues:
            change(row,'NON_REQUIREMENT_CONTEXT','organisation_or_role_purpose_without_candidate_obligation')

    result['ambiguous_content'] = [r for r in records if r['classification'] == 'AMBIGUOUS_CONTENT']
    result['unresolved_classifications'] = result['ambiguous_content']
    return result


def build_metadata_preview(*, developer_enabled=False, source_projection=None, **inputs):
    if not developer_enabled:
        raise ValueError('JD v1.23 experiment defaults OFF; explicit developer invocation required')
    from .coordinated_integration import build_coordinated_analysis
    receipt = classify(inputs.get('raw_jd_text'))
    receipt['original_jd_profile'] = deepcopy(inputs.get('jd_profile'))
    token = previous.ACTIVE.set(receipt)
    try:
        result = build_coordinated_analysis(source_projection=source_projection, **deepcopy(inputs))
    finally:
        previous.ACTIVE.reset(token)
    result.update(scoring_version=SCORER_VERSION,jd_metadata_parser_version=PARSER_VERSION,
                  preview_namespace=NAMESPACE,jd_metadata_classification=receipt)
    for row in result['canonical_requirements']:
        if row.get('coordinated_action_receipt'):
            row['coordinated_action_receipt']['policy_identities'].update(
                scoring_version=SCORER_VERSION,jd_metadata_parser_version=PARSER_VERSION)
    if receipt['unresolved_classifications'] or not result['canonical_requirements']:
        for field in ('deterministic_alignment_score','required_core_coverage_score','preferred_coverage_score',
                      'evidence_strength_score','alignment_band','boundary_status'):
            result[field] = None
        result['score_publication_status'] = ('WITHHELD_PENDING_JD_CLASSIFICATION_REVIEW'
            if receipt['unresolved_classifications'] else 'WITHHELD_NO_ADMISSIBLE_JD_REQUIREMENTS')
    result['input_fingerprint'] = previous.digest({'base':result['input_fingerprint'],
        'scoring_version':SCORER_VERSION,'parser_version':PARSER_VERSION,'namespace':NAMESPACE,
        'original_profile':inputs.get('jd_profile'),'classification':receipt})
    return result
