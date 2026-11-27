"""Read-only gate for meaningful Base/Library comparisons in V3.7.

Matching a JD requirement or mentioning the same language/tool is NOT enough.
A related comparison is not a claim that the two wordings are substitutes,
that either is more truthful, or that a native Job Match delta was measured.
"""
from __future__ import annotations

import re
from tailoring.phase9f_bullet_redundancy import compare_project_bullets

# Single activities that are sufficiently specific for a *related* inspection.
# A generic testing/validation or shared JD link alone must not force pairing.
SPECIFIC_RELATED_ACTIVITIES = frozenset({
    'ci_pipeline', 'database_access', 'security_controls', 'interface_features',
    'release', 'requirements_gathering',
})


def classify_related_pair(base: dict, library: dict) -> dict:
    """Fail closed on ungrounded identity, ownership, provenance, or activity.

    This function only governs UI pairing; V3.7 solver exclusion is unchanged.
    """
    if not isinstance(base, dict) or not isinstance(library, dict):
        return {'eligible': False, 'status': 'unavailable',
                'reason': 'Missing source wording record.'}
    project_a, project_b = (str(x.get('project') or '').strip().casefold()
                            for x in (base, library))
    if not project_a or not project_b or project_a != project_b:
        return {'eligible': False, 'status': 'different_projects',
                'reason': 'Both wordings must belong to the same identified project.'}
    if ('Selected Base' not in (base.get('sources') or ()) or
            'Evidence Library' not in (library.get('sources') or ())):
        return {'eligible': False, 'status': 'source_unverified',
                'reason': 'Exact Base/Library source provenance is unavailable.'}
    a, b = base.get('bullet'), library.get('bullet')
    if not isinstance(a, str) or not a.strip() or not isinstance(b, str) or not b.strip():
        return {'eligible': False, 'status': 'unavailable',
                'reason': 'Both exact wordings are required.'}
    review = compare_project_bullets(a, b, same_project=True)
    status = str(review.get('status') or 'unavailable')
    common = set(review.get('shared_activities') or ())
    eligible = (status in {'same_wording', 'likely_same_work'} or
                (status == 'related_activity' and bool(common & SPECIFIC_RELATED_ACTIVITIES)))
    # UI-only explicit performed API development; shared tool or JD text is insufficient.
    api = re.compile(r"^(?:built|developed|implemented|created|designed)\s+(?:[a-z0-9+#.-]+\s+){0,3}APIs?\b", re.I)
    denied = re.compile(r"\b(?:not|never|without|planned|proposed|tutorial|documentation|guide|mock|sample|example)\b", re.I)
    if (not eligible and api.search(a.strip()) and api.search(b.strip())
            and not denied.search(a) and not denied.search(b)):
        return {'eligible': True, 'status': 'related_activity',
                'shared_activities': sorted(common | {'api_development'}),
                'reason': 'Both wordings explicitly describe API development in this project; distinct accomplishments remain possible.'}
    return {'eligible': bool(eligible), 'status': status,
            'shared_activities': sorted(common),
            'reason': str(review.get('reason') or 'No grounded activity overlap.')}


_DELIVERABLE = re.compile(
    r"^(?:built|created|developed|implemented|designed|delivered)\s+(?:(?:a|an|the)\s+)?"
    r"(.+?)(?:\s+(?:with|using|featuring|spanning|to)\s+|[,.;]|$)",
    re.I,
)
_GENERAL = {"full", "stack", "web", "mobile", "new", "application", "app", "platform", "system", "tool"}


def _deliverable(wording: str) -> tuple[str, ...]:
    match = _DELIVERABLE.match(wording.strip())
    words = tuple(re.findall(r"[a-z0-9]+", match[1].casefold())) if match else ()
    return words if len(set(words) - _GENERAL) >= 3 else ()


def classify_comparison_pair(base: dict, library: dict) -> dict:
    """Allow a grounded shared deliverable for read-only related inspection."""
    relation = classify_related_pair(base, library)
    if relation['eligible'] or relation['status'] in {
        'unavailable', 'different_projects', 'source_unverified',
    }:
        return relation
    deliverable = _deliverable(base['bullet'])
    if deliverable and deliverable == _deliverable(library['bullet']):
        return {**relation, 'eligible': True, 'status': 'shared_deliverable',
                'reason': 'Both describe building the same deliverable. Each wording supplies different details about it.'}
    return relation
