"""Bounded R1 exclusion contract for the entire supplied development packet.

Affirmative client use, generated-service integration and peripheral configuration
are separate activity grammars, never inferred from missing action words. Unknown
language or any unexamined source fails closed. This says nothing about experience
outside the supplied packet. No scenario names, evidence IDs or fixture imports.
"""
from copy import deepcopy
import re

from . import coordinated_policy as policy

VERSION = 'coordinated-finite-packet-exclusion-v1'

_GRAMMARS = (
    ('CLIENT_CONSUMPTION',
     r'(?P<activity>consumed|called)\s+(?:an?\s+)?(?:existing\s+)?(?P<artifact>REST APIs?)'
     r'\s+(?:using|via)\s+(?P<transport>HTTP requests)\s+and\s+(?P<payload>JSON responses)',
     'Client HTTP/JSON consumption does not assert ownership of the required authored artifact.'),
    ('GENERATED_SERVICE_INTEGRATION',
     r'(?P<activity>integrated)\s+(?:with\s+)?(?P<provider>Supabase)\s+(?P<service>PostgREST)'
     r'\s+(?P<origin>generated)\s+(?P<artifact>REST APIs?)\s+for\s+'
     r'(?P<purpose>CRUD and authentication|authentication and CRUD)',
     'Integration of generated services does not assert custom endpoint or coordinated artifact authorship.'),
    ('PERIPHERAL_CONFIGURATION',
     r'(?P<activity>configured)\s+(?P<platform>ESP32|STM32)\s+(?P<artifact>GPIO)'
     r'\s+(?P<facility>interrupts|pins)',
     'Peripheral configuration does not assert design, creation or lifecycle ownership of the required artifact.'),
)


def recognize_activity(text):
    """Parse a full affirmative single-actor activity, not a keyword exclusion."""
    if not isinstance(text, str) or '\n' in text or '\r' in text:
        return None
    for grammar, body, reason in _GRAMMARS:
        match = re.fullmatch(r'(?:I\s+)?'+body+r'\.?', text, re.I)
        if match:
            return {'grammar': grammar, 'reason': reason, 'activity': match.group('activity'),
                    'covered_span': [0, len(text)],
                    'roles': {name: {'text': match.group(name), 'span': list(match.span(name))}
                              for name in match.groupdict()}}
    return None


def exclusion_packet(*, requirement, obligation, profile, raw_resume, evidence_index,
                     proofs, native_final_label, raw_jd):
    """Require one fully enumerated original activity, with verified native NONE.

    The intentionally narrow packet schema rejects second sources (even duplicate
    text the native index would deduplicate), skills/education evidence, raw text,
    unknown profile fields and incomplete profiles. A neutral title is permitted
    only as metadata. The full original input, not a retrieved subset, is required.
    """
    from . import stable_evidence_scoring as native
    out = {'policy_version': VERSION, 'eligible': False, 'records': [],
           'packet_scope': 'ENTIRE_SUPPLIED_PROFILE_AND_RAW_TEXT_NOT_CANDIDATE_LIFETIME',
           'native_final_label': native_final_label}

    def reject(reason):
        return {**out, 'reason': reason}

    if native_final_label != 'none':
        return reject('native_final_ceiling_is_not_NONE')
    grounded = policy.prior.ground_to_raw_jd(policy.prior.extract_obligation(requirement), raw_jd)
    if (grounded != obligation or obligation.get('status') != 'SUPPORTED'
            or obligation.get('conjunction') != 'AND' or obligation.get('negation_present')
            or obligation.get('optional_qualifiers')
            or obligation.get('object_family') not in policy.HEADS):
        return reject('unsupported_or_unverified_original_parent')
    if (not isinstance(profile, dict)
            or not {'projects', 'experience', 'education', 'skills'} <= profile.keys()
            or profile.keys()-{'projects', 'experience', 'education', 'skills', 'certifications'}
            or profile['experience'] != [] or profile['education'] != [] or profile['skills'] != {}
            or profile.get('certifications', []) != [] or raw_resume != ''):
        return reject('partial_unknown_or_unexamined_packet_fields')
    projects = profile['projects']
    if not isinstance(projects, list) or len(projects) != 1 or not isinstance(projects[0], dict):
        return reject('requires_one_attributable_original_project')
    project = projects[0]
    if project.keys()-{'title', 'bullets'}:
        return reject('unexamined_project_fields')
    bullets = project.get('bullets')
    if not isinstance(bullets, list) or len(bullets) != 1 or not isinstance(bullets[0], str) or not bullets[0].strip():
        return reject('requires_one_substantive_original_not_empty_or_multiple_records')
    title = project.get('title', '')
    if not isinstance(title, str) or (title and not re.fullmatch(
            r'(?:(?:synthetic|sample|example|demo)\s+)?(?:acceptance\s+)?project', title, re.I)):
        return reject('title_is_not_proven_neutral_metadata')
    original_index = native.build_resume_evidence_index(profile, raw_resume)
    if (original_index != evidence_index or len(proofs) != len(original_index)
            or set(proofs) != {r['evidence_id'] for r in original_index}):
        return reject('incomplete_duplicate_or_mutated_original_index')
    activity_count = 0
    for record in original_index:
        item = proofs[record['evidence_id']]
        proof = policy.detect(obligation, record, original_index)
        if (item.get('record') != record or item.get('proof') != proof
                or item.get('admission') != 'REVIEW_REQUIRED'
                or proof.get('status') != 'INCOMPLETE' or proof.get('supported_actions')
                or proof.get('denied_actions') or proof.get('ambiguities')
                or not native._evidence_source_is_requirement_compatible(requirement, record)):
            return reject('source_or_proof_not_verified_or_positive_uncertain_record')
        receipt = {**deepcopy(record), 'source_verified': True}
        if record['source'] == 'resume_profile.projects[0]' and record['text'] == title:
            out['records'].append({**receipt, 'classification': 'NEUTRAL_METADATA',
                                   'reason': 'Title is not negative evidence.'})
            continue
        if record['source'] != 'resume_profile.projects[0].bullets[0]' or record['section'] != 'projects':
            return reject('unexamined_or_unattributable_source')
        activity = recognize_activity(record['text'])
        if not activity:
            return reject('unknown_or_nonexclusive_activity_language')
        activity_count += 1
        out['records'].append({**receipt, 'classification': 'EXCLUDED_ACTIVITY', **activity,
                               'original_supplied_text': bullets[0],
                               'requirement_family': obligation['object_family'],
                               'required_object': obligation['object']})
    if activity_count != 1:
        return reject('no_affirmative_substantive_exclusion')
    return {**out, 'eligible': True, 'reason': 'complete_verified_packet_excluded_with_native_NONE',
            'complete_supplied_index_verified': True}
