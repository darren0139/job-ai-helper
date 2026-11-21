"""Proposed activity evidence gate for research replay only."""
from collections.abc import Collection
from copy import deepcopy
import re


def _in_scope(requirement: dict) -> bool:
    return (requirement.get('capability_id') == 'quality.qa_testing'
            and requirement.get('semantic_type') == 'role_responsibility'
            and requirement.get('match_label') == 'weak')


def has_attested_testing_activity(requirement: dict, excerpt: dict, attested_actions: Collection[tuple[str, str]]) -> bool:
    """Gate weak testing-duty credit on an exact reviewed document excerpt.

    The set contains (evidence source path, exact wording) pairs independently
    reviewed for performed testing. A caller must bind it to the document and
    JD under review before invoking this proposal.
    """
    if not _in_scope(requirement):
        return True
    return (excerpt.get('section') in {'projects', 'experience'}
            and bool(excerpt.get('text', '').strip())
            and (excerpt.get('source', ''), excerpt['text']) in attested_actions)


# A deliberately bounded first pass for common past-tense factual CV claims.
# A named kind of test, case, suite or plan is the object of a performed action.
_TEST_ACTION = re.compile(
    r'(?:^|[.!?;]\s+|\band\s+|\bI\s+)'
    r'(?:(?:added|authored|built|created|designed|developed|executed|implemented|maintained|ran|wrote)\s+'
    r'(?:(?:the|our|automated|manual|unit|integration|regression|system|end-to-end|acceptance|'
    r'performance|functional|smoke|security|load)\s+){0,5}(?:tests|test cases|test suites)'
    r'|(?:conducted|performed|carried out)\s+(?:automated\s+|manual\s+)?'
    r'(?:unit|integration|regression|system|end-to-end|acceptance|performance|functional|smoke|security|load)\s+testing)\b',
    re.IGNORECASE,
)
_NON_PERFORMED = re.compile(
    r"\b(?:did not|didn't|never|would|will|plan(?:ned)? to|planning to|intend(?:ed)? to|"
    r"wanted to|hope(?:d)? to|goal was to|could have|should have|not yet|scheduled to|"
    r"expected to|if we|if I|not (?:run|executed|performed|written|conducted))\b",
    re.IGNORECASE,
)
_PASSIVE_ACTION = re.compile(
    r'^(?:automated\s+)?(?:unit|integration|regression|system|end-to-end|acceptance)\s+'
    r'tests\s+were\s+(?:executed|run|written)\s+(?:against|for|on|before|during|by)\s+\S+',
    re.IGNORECASE,
)


def apply_shadow_testing_gate(requirements: list[dict], *, resume_text: str, resume_profile: dict | None = None,
                              reviewed_actions: Collection[tuple[str, str]] = ()) -> tuple[list[dict], list[dict]]:
    """Recheck currently credited citations against the exact résumé under review.

    Explicit performed-action wording is a document claim even when the upload
    has no structured profile or Library. Independent review can confirm other
    exact document excerpts. The shadow gate never promotes a native label.
    """
    from analysis_stability.stable_evidence_scoring import build_resume_evidence_index
    from tailoring.document_grounded_analysis import represented_profile

    verified = build_resume_evidence_index(represented_profile(resume_profile or {}, resume_text), resume_text)
    verified_actions = {(row['source'], row['text']) for row in verified
                        if row['section'] in {'projects', 'experience', 'raw_text'}}
    # Some native link paths serialize text and section without a source ID.
    sources_by_excerpt = {}
    for row in verified:
        sources_by_excerpt.setdefault((row['section'], row['text']), set()).add(row['source'])

    result = deepcopy(requirements)
    audit = []
    for row in result:
        if not _in_scope(row):
            continue
        accepted, decisions = [], []
        for excerpt in row.get('evidence') or []:
            text, section, source = excerpt.get('text', ''), excerpt.get('section'), excerpt.get('source')
            matches = sources_by_excerpt.get((section, text), set())
            if not source and len(matches) == 1:
                source = next(iter(matches))
            if source not in matches or (source, text) not in verified_actions:
                reason = 'no_exact_document_activity_excerpt'
            elif (source, text) in reviewed_actions:
                reason = 'independently_reviewed_performed_testing'
            elif (_TEST_ACTION.search(text) or _PASSIVE_ACTION.search(text)) and not _NON_PERFORMED.search(text):
                reason = 'explicit_performed_testing_claim_in_document'
            else:
                reason = 'no_performed_testing_claim_in_cited_text'
            if reason in {'independently_reviewed_performed_testing', 'explicit_performed_testing_claim_in_document'}:
                accepted.append(excerpt)
            decisions.append({'section': section, 'source': source, 'text': text, 'reason': reason})
        row['evidence'] = accepted
        if not accepted:
            row.update(match_label='none', match_value=0.0, evidence_strength=0)
        audit.append({'requirement_id': row['requirement_id'], 'requirement': row['text'],
                      'importance': row['importance'], 'before': 'weak', 'after': row['match_label'],
                      'decisions': decisions})
    return result, audit
