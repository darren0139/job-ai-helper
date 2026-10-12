"""Document input authority for the existing deterministic scorer.

No new weights, labels, requirement IDs, or evidence-matching policy live here.
Profile/library evidence is a separate opportunity input, never scorer input.
"""
from copy import deepcopy
import hashlib
import re

from analysis_stability.stable_evidence_scoring import (
    build_deterministic_keyword_match, build_stable_analysis, canonicalise_requirements,
)
from tailoring.job_match_ab_analysis import current_ab_identity
from tailoring.phase9e_blueprint_selection import fingerprint_value
from tailoring.phase9f_starting_source_ranking import canonical_requirement_scope_fingerprint

DOCUMENT_ANALYSIS_VERSION = 'application-document-authority-v1'


def text_fingerprint(text):
    return hashlib.sha256(str(text).encode('utf-8')).hexdigest()


def selected_base_analysis(baseline_report):
    """Read the selected native receipt without scoring or changing the initial.

    The caller supplies the effective report from the existing current source
    decision. Historical decisions must not be substituted for that context.
    """
    initial = baseline_report.get('frozen_initial_resume_report') or baseline_report
    initial_authority = validate_document_report(initial)
    selected_authority = validate_document_report(baseline_report)
    if (initial_authority['identity'] != selected_authority['identity']
            or initial_authority['canonical_requirement_fingerprint'] != selected_authority['canonical_requirement_fingerprint']):
        raise ValueError('Selected base and frozen initial have incompatible analysis identities')
    same = initial_authority['resume_text_sha256'] == selected_authority['resume_text_sha256']
    if same and document_outcomes(initial['stable_analysis']) != document_outcomes(baseline_report['stable_analysis']):
        raise ValueError('Same document has conflicting native analysis outcomes')
    return {
        'same_as_initial': same,
        'document_analysis': deepcopy(initial_authority if same else selected_authority),
        'stable_analysis': deepcopy(initial['stable_analysis'] if same else baseline_report['stable_analysis']),
        'starting_context': deepcopy((baseline_report.get('meta') or {}).get('phase9e_starting_context') or {}),
    }


def document_outcomes(stable):
    """Material native outputs, excluding cache/quality/diagnostic metadata."""
    from tailoring.phase8_score_explainability import build_score_breakdown
    return {'metrics': {key: stable.get(key) for key in
        ('deterministic_alignment_score', 'required_core_coverage_score',
         'preferred_coverage_score', 'evidence_strength_score')},
        'requirements': [{key: row.get(key) for key in
            ('requirement_id', 'match_label', 'match_value', 'evidence_strength', 'evidence')}
            for row in stable.get('canonical_requirements', [])],
        'contributions': build_score_breakdown(stable)['requirements']}


def represented_profile(profile, text):
    """Bound structured candidates to literal material present in this document.

    This is source selection, before native evidence evaluation. Unproven
    extracted/paraphrased/library material is omitted rather than granted credit.
    """
    source = ' '.join(str(text).casefold().split())
    def present(value):
        value = ' '.join(str(value or '').casefold().split())
        return bool(value and re.search(r'(?<!\w)' + re.escape(value) + r'(?!\w)', source))
    # Keep contact/layout metadata for the existing generation consumers. Only
    # the native scorer's evidence-bearing sections need source bounding.
    evidence_sections = {'projects', 'experience', 'education', 'certifications', 'skills'}
    out = {key: deepcopy(value) for key, value in (profile or {}).items() if key not in evidence_sections}
    for section in ('projects', 'experience', 'education', 'certifications'):
        items = []
        for item in (profile or {}).get(section, []) or []:
            if not isinstance(item, dict):
                if present(item):
                    items.append(item)
                continue
            bounded = {}
            for key, value in item.items():
                if isinstance(value, list):
                    bounded[key] = [v for v in value if isinstance(v, str) and present(v)]
                elif isinstance(value, str) and present(value):
                    bounded[key] = value
            if any(bounded.values()):
                items.append(bounded)
        out[section] = items
    out['skills'] = {k: [v for v in values if present(v)]
                     for k, values in ((profile or {}).get('skills') or {}).items()
                     if isinstance(values, list)}
    return out


def analyze_actual_resume_against_jd(*, resume_text, jd_text, jd_profile,
                                    resume_profile=None, canonical_requirements=None):
    """Use native matcher/scorer against the exact text, with bounded candidates."""
    if not str(resume_text or '').strip() or not str(jd_text or '').strip():
        raise ValueError('Exact resume/JD text required for document analysis')
    profile = represented_profile(resume_profile or {}, resume_text)
    canonical = canonicalise_requirements(jd_profile=jd_profile, raw_jd_text=jd_text)
    keyword = build_deterministic_keyword_match(requirements=canonical['requirements'],
        acronym_map=canonical['acronym_map'], resume_profile=profile, raw_resume_text=resume_text)
    stable = build_stable_analysis(jd_profile=jd_profile, keyword_match=keyword,
        raw_jd_text=jd_text, raw_resume_text=resume_text, resume_profile=profile,
        retrieval_mode_override='lexical')
    if canonical_requirements is not None and canonical_requirement_scope_fingerprint(stable['canonical_requirements']) != canonical_requirement_scope_fingerprint(canonical_requirements):
        raise ValueError('Document analysis changed the canonical requirement scope')
    authority = {'version': DOCUMENT_ANALYSIS_VERSION, 'resume_text_sha256': text_fingerprint(resume_text),
        'jd_text_sha256': text_fingerprint(jd_text), 'identity': current_ab_identity(jd_text),
        'canonical_requirement_fingerprint': canonical_requirement_scope_fingerprint(stable['canonical_requirements']),
        'stable_analysis_fingerprint': fingerprint_value(stable),
        'resume_profile_fingerprint': fingerprint_value(profile), 'input_authority': 'ACTUAL_RESUME_DOCUMENT'}
    authority['fingerprint'] = fingerprint_value(authority)
    return {'stable_analysis': stable, 'keyword_match': keyword, 'resume_profile': profile, 'jd_profile': deepcopy(jd_profile),
            'raw_resume_text': resume_text, 'raw_jd_text': jd_text, 'document_analysis': authority}


def validate_document_report(report):
    authority = (report.get('meta') or {}).get('document_analysis') or {}
    if (authority.get('version') != DOCUMENT_ANALYSIS_VERSION
        or authority.get('fingerprint') != fingerprint_value({k:v for k,v in authority.items() if k != 'fingerprint'})
        or authority.get('resume_text_sha256') != text_fingerprint(report.get('raw_resume_text', ''))
        or authority.get('jd_text_sha256') != text_fingerprint(report.get('raw_jd_text', ''))
        or authority.get('stable_analysis_fingerprint') != fingerprint_value(report.get('stable_analysis'))
        or authority.get('resume_profile_fingerprint') != fingerprint_value(report.get('resume_profile'))):
        raise ValueError('Document analysis provenance unavailable or inconsistent')
    if authority.get('canonical_requirement_fingerprint') != canonical_requirement_scope_fingerprint(report['stable_analysis']['canonical_requirements']):
        raise ValueError('Document analysis canonical scope is inconsistent')
    return deepcopy(authority)


def seal_document_report(report):
    """Seal the effective application-local scope after existing override handling."""
    authority = report.setdefault('meta', {}).get('document_analysis') or {}
    authority.update(version=DOCUMENT_ANALYSIS_VERSION, input_authority='ACTUAL_RESUME_DOCUMENT',
        resume_text_sha256=text_fingerprint(report['raw_resume_text']),
        jd_text_sha256=text_fingerprint(report['raw_jd_text']), identity=current_ab_identity(report['raw_jd_text']),
        canonical_requirement_fingerprint=canonical_requirement_scope_fingerprint(report['stable_analysis']['canonical_requirements']),
        stable_analysis_fingerprint=fingerprint_value(report['stable_analysis']),
        resume_profile_fingerprint=fingerprint_value(report['resume_profile']))
    authority.pop('fingerprint', None)
    authority['fingerprint'] = fingerprint_value(authority)
    report['meta']['document_analysis'] = authority
    return report


def build_tailoring_evidence_opportunities(report, evidence_items, *, limit=30):
    """Native governed candidate matching only; no projected scorer or score."""
    from tailoring.phase6d_ranking_adapter import match_requirement_to_candidate
    from tailoring.phase9a_evidence_opportunity import _evidence_text
    authority = validate_document_report(report)
    if authority['identity'] != current_ab_identity(report['raw_jd_text']):
        raise ValueError('Document analysis is stale; explicit analysis required before current opportunity comparison')
    rows = []
    for requirement in (report.get('stable_analysis') or {}).get('canonical_requirements', []):
        if requirement.get('importance') not in {'required', 'core', 'deal_breaker', 'preferred'}:
            continue
        available = []
        pending = False
        for item in evidence_items:
            decision = match_requirement_to_candidate(requirement=requirement,
                                                      candidate_evidence_text=_evidence_text(item))
            if decision.get('label') in {'direct', 'transferable'}:
                available.append({'evidence_item_id': item.get('id'), 'title': item.get('title'),
                                  'native_label': decision['label'], 'reason': decision.get('reason')})
            elif decision.get('label') is None:
                pending = True
        label = requirement.get('match_label')
        state = ('ALREADY_REPRESENTED' if label == 'direct' else
                 'SUPPORTED_BUT_UNDERREPRESENTED' if label == 'transferable' else
                 'GROUNDED_EVIDENCE_AVAILABLE' if available else
                 'REVIEW_PENDING' if pending else 'NO_CONFIRMED_SUPPORT')
        rows.append({'requirement_id': requirement['requirement_id'], 'requirement': requirement.get('text'),
                     'current_resume': label or 'Review pending', 'state': state,
                     'additional_grounded_evidence': available})
        if len(rows) >= limit:
            break
    return rows
