"""Exact-source research evidence for one frozen database-knowledge requirement."""
from copy import deepcopy
from hashlib import sha256
import re

from analysis_stability.stable_evidence_scoring import IMPORTANCE_WEIGHTS, MATCH_VALUES, build_resume_evidence_index
from tailoring.document_grounded_analysis import represented_profile
from tailoring.phase9f_v37_testing_gate import _NON_PERFORMED


REQUIREMENT_ID = 'req_c3b362e0255b'
REQUIREMENT_TEXT = 'Knowledge of databases (SQL / NoSQL) is an advantage'
PARENT_ID = 'srcgrp_2478ae9e3f68'
SPAN_ID = 'jdspan_a1b662d31923'
_SUBJECT = r'^(?:(?:I|we)\s+)?'
_RULES = (
    ('sql_query_work', 'relational',
     r'(?:(?:wrote|ran|authored|executed|optimized|developed)\s+(?:complex\s+)?'
     r'(?:SQL\s+queries|queries\s+(?:using|in)\s+SQL)|'
     r'reconciled\s+invoice\s+records\s+by\s+writing\s+SQL\s+joins)\b'),
    ('postgresql_database_work', 'relational',
     r'(?:(?:ran|executed|wrote|optimized)\s+PostgreSQL\s+(?:queries|migrations)|'
     r'configured\s+row[- ]level security policies\s+(?:for|on)\s+PostgreSQL\s+tables)\b'),
    ('postgrest_data_access', 'relational',
     r'implemented\s+(?:backend\s+)?data access\s+(?:through|via|with|using)\s+PostgREST\b'),
    ('explicit_nosql_collection_work', 'nosql',
     r'(?:queried|indexed|migrated)\s+NoSQL\s+(?:collections|documents|records)\b'),
)
_ACTIVITY = [(kind, family, re.compile(_SUBJECT + rule, re.IGNORECASE))
             for kind, family, rule in _RULES]


def _digest(value):
    return sha256(value.encode('utf-8')).hexdigest()


def _validate_scope(requirement, jd, expected_digest):
    identity = (requirement['requirement_id'], requirement['text'], requirement['importance'],
                requirement['semantic_type'], requirement['scoring_parent_occurrence_id'],
                requirement['group_weight_fraction'])
    if (_digest(jd) != expected_digest
            or identity != (REQUIREMENT_ID, REQUIREMENT_TEXT, 'preferred', 'candidate_requirement', PARENT_ID, 1.0)
            or requirement.get('parent_text') != REQUIREMENT_TEXT
            or not requirement.get('score_eligible') or not requirement.get('evidence_eligible')):
        raise ValueError('The exact frozen database requirement is required.')
    lines = jd.splitlines()
    spans = []
    for item in requirement.get('source_provenance') or []:
        grounding = item.get('grounding') or {}
        line = grounding.get('line_index')
        if (item.get('parent_occurrence_id') == PARENT_ID and item.get('parent_text') == REQUIREMENT_TEXT
                and item.get('source_group_fraction') == 1.0 and item.get('contributes_scoring_allocation') is True
                and grounding.get('span_id') == SPAN_ID and grounding.get('sentence_text') == REQUIREMENT_TEXT
                and type(line) is int and 1 <= line <= len(lines) and REQUIREMENT_TEXT in lines[line - 1]):
            spans.append(item)
    if len(spans) != 1:
        raise ValueError('The frozen parent and exact original JD span are required.')
    return {'requirement_id': REQUIREMENT_ID, 'text': REQUIREMENT_TEXT, 'importance': 'preferred',
            'parent': PARENT_ID, 'parent_fraction': 1.0, 'source_span': deepcopy(spans[0]['grounding']),
            'jd_sha256': expected_digest}


def review_database_evidence(*, requirement, native, raw_jd, expected_jd_sha256, resume_text,
                             expected_resume_sha256, profile=None, donor_audit=None, donor_sha256=None):
    """Report performed evidence separately from an immutable supplied native receipt.

    Resume text proves that a claim appears in the reviewed document. A donor
    audit adds exact project/source ownership, not independent proof of the claim.
    """
    identity = _validate_scope(requirement, raw_jd, expected_jd_sha256)
    if (not resume_text.strip() or _digest(resume_text) != expected_resume_sha256
            or (native.get('id') or native.get('requirement_id')) != REQUIREMENT_ID
            or native.get('text') != REQUIREMENT_TEXT or native.get('importance') != 'preferred'):
        raise ValueError('Exact reviewed résumé text and the matching native requirement are required.')
    bounded = represented_profile(profile or {}, resume_text)
    owners = {}
    if donor_audit is not None:
        if not donor_audit.get('verified') or not donor_sha256 or donor_audit.get('docx_sha256') != donor_sha256:
            raise ValueError('A verified, hash-bound donor source audit is required.')
        for item in donor_audit['projects']:
            for field in ('base', 'library'):
                for index, bullet in enumerate(item.get(field) or (), 1):
                    owners.setdefault((item['project'], bullet['text']), []).append({'source': field, 'position': index})

    accepted, withheld = [], []
    seen = set()
    projects = bounded.get('projects') or []
    for row in build_resume_evidence_index(bounded, resume_text):
        text, source, section = row['text'], row['source'], row['section']
        if section not in {'projects', 'experience', 'raw_text', 'skills', 'professional_summary'}:
            continue
        identity_text = ' '.join(text.casefold().split())
        if identity_text in seen:
            continue
        project = re.fullmatch(r'resume_profile\.projects\[(\d+)\]\.bullets\[\d+\]', source)
        provenance = ([{'source': 'uploaded_document_text', 'path': source}] if donor_audit is None else
                      owners.get((projects[int(project[1])].get('title'), text), []) if project else [])
        clauses = re.split(r'\s*;\s*|(?<=\.)\s+|\s+and\s+', text, flags=re.IGNORECASE)
        activities = {(kind, family) for kind, family, pattern in _ACTIVITY
                      if any(pattern.search(clause) for clause in clauses)}
        if (not provenance or section == 'skills' or not activities or _NON_PERFORMED.search(text)):
            if re.search(r'\b(?:SQL|NoSQL|PostgREST|PostgreSQL|database\w*|row[- ]level security)\b', text, re.I):
                withheld.append({'text': text, 'path': source, 'reason': (
                    'no_exact_permitted_donor_ownership' if not provenance else
                    'no_unqualified_performed_database_activity')})
            continue
        seen.add(identity_text)
        accepted.extend({'text': text, 'path': source, 'provenance': provenance,
                         'activity': kind, 'family': family} for kind, family in sorted(activities))
    families = sorted({item['family'] for item in accepted})
    # This parent uses a slash with no resolved native structure. In research,
    # prove each branch independently and count the parent once.
    label = 'direct' if len(families) == 2 else 'transferable' if families else 'none'
    witnessed = {(row['text'], row['path']) for row in accepted}
    verified_native = [deepcopy(item) for item in native.get('evidence', [])
                       if any(text == (item.get('text') if isinstance(item, dict) else item)
                              and (not isinstance(item, dict) or not item.get('source') or item['source'] == path)
                              for text, path in witnessed)]
    return {'scope': identity, 'resume_sha256': expected_resume_sha256,
            'native': deepcopy(native), 'native_factual_citations_confirmed': verified_native,
            'research_label': label, 'families': families,
            'research_weighted_units': IMPORTANCE_WEIGHTS['preferred'] * identity['parent_fraction'] * MATCH_VALUES[label],
            'accepted': accepted, 'withheld': withheld}
