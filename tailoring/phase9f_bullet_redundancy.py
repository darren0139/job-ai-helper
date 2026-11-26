"""Conservative, explanatory near-duplicate recognition for project bullets.

Sharing a tool or a JD keyword is not proof of the same accomplishment. Exact
identity or a shared specific *performed activity* is required for a strong
warning. This module does not remove bullets or alter native scoring.
"""
from __future__ import annotations

import re


def _has(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text, re.IGNORECASE))


def _norm(text: str) -> str:
    return ' '.join(token.strip('.') for token in re.findall(r'[a-z0-9+#.]+', text.lower()))


def activity_facets(text: str) -> frozenset[str]:
    x = set()
    if _has(r'\b(?:github actions(?:\s+CI)?|CI pipeline|continuous integration)\b', text):
        x.add('ci_pipeline')
    if _has(r'\b(?:unit tests?|integration tests?|system tests?|regression|test suite|testing|automated tests?|audit tooling|validat(?:e|ed|ion))\b', text):
        x.add('testing_validation')
    if _has(r'\b(?:row.level security|\bRLS\b|access control|security policies)\b', text):
        x.add('security_controls')
    if _has(r'\b(?:database queries|PostgREST data access|backend data access|database access)\b', text):
        x.add('database_access')
    if _has(r'\b(?:sliders|level.locking screens|UI features|user interfaces|frontend features)\b', text):
        x.add('interface_features')
    if _has(r'\b(?:released on Google Play|published on Google Play|mobile game released)\b', text):
        x.add('release')
    if _has(r'\b(?:stakeholder requirements|requirements gathering|stakeholder interviews)\b', text):
        x.add('requirements_gathering')
    return frozenset(x)


def compare_project_bullets(base: str, library: str, *, same_project: bool = True) -> dict:
    """Explain *possible* redundancy without manufacturing a selection cause."""
    if not same_project:
        return {'status':'different_projects','shared_activities':[], 'reason':'Different projects; no common accomplishment inferred.'}
    if not base.strip() or not library.strip():
        return {'status':'unavailable','shared_activities':[], 'reason':'Both wordings are required for a comparison.'}
    if _norm(base) == _norm(library):
        return {'status':'same_wording','shared_activities':sorted(activity_facets(base)),
                'reason':'The wordings are identical after normalization; one source wording should be displayed, not two independent accomplishments.'}
    a, b = activity_facets(base), activity_facets(library)
    shared = sorted(a & b)
    # A named CI system PLUS a testing/validation activity is substantially
    # more specific than a shared generic word such as React, Python or UI.
    if {'ci_pipeline','testing_validation'} <= set(shared):
        level, reason = ('likely_same_work',
            'Both describe a GitHub Actions/CI testing and validation contribution in this project. Their unique details still need comparison before choosing wording.')
    elif {'database_access','security_controls'} <= set(shared):
        level, reason = ('likely_same_work',
            'Both describe database access and security controls in this project; review whether they are alternatives.')
    elif shared:
        level, reason = ('related_activity',
            'The bullets share an activity category, but distinct accomplishments have not been ruled out.')
    else:
        level, reason = ('distinct_or_unproven',
            'No sufficiently specific shared activity is established; common JD keywords alone are not redundancy proof.')
    return {'status':level,'shared_activities':shared,
            'base_only_activities':sorted(a-b), 'library_only_activities':sorted(b-a),
            'reason':reason}
