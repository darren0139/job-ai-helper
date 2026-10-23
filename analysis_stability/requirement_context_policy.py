"""Bounded release-candidate correction using the existing native JD pipeline.

Explicit request scope only; published defaults and saved snapshots stay frozen.
This changes admission/importance, never capability recognition or evidence credit.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import re

ACTIVE = ContextVar('requirement_importance_context_correction', default=False)
POLICY_VERSION = 'requirement-importance-context-v2'
SCORING_IDENTITY = 'stable-evidence-v1.17-phase6d21+importance-context-v2'
# Prepared release identity. No production caller enters this scope by default.
RELEASE_SCORING_VERSION = 'stable-evidence-v1.27-phase6d31'
RELEASE = ContextVar('requirement_context_release', default=False)
# Release preparation only. Changing this requires the separate activation review.
PRODUCTION_ENABLED = False
SUSPENDED = ContextVar('requirement_context_baseline_isolation', default=False)


@contextmanager
def suspend_for_baseline_comparison():
    """Keep an existing preview's native-baseline probe on its own policy."""
    token = SUSPENDED.set(True)
    try:
        yield
    finally:
        SUSPENDED.reset(token)


def release_enabled():
    if SUSPENDED.get():
        return False
    if RELEASE.get():
        return True
    if ACTIVE.get():
        return False  # An explicit preview never inherits production publication.
    if not PRODUCTION_ENABLED:
        return False
    from . import coordinated_runtime as runtime
    from .jd_metadata_policy import ACTIVE as metadata
    return not (runtime.CONTEXT.get() is not None or runtime.ELIGIBLE_WEAK_FALLBACK.get()
                or runtime.APPROVED_ALIAS_SURFACE.get() is not None or metadata.get() is not None)


def enabled():
    return not SUSPENDED.get() and (ACTIVE.get() or release_enabled())


def current_scoring_version():
    from .stable_evidence_scoring import SCORING_VERSION
    return RELEASE_SCORING_VERSION if release_enabled() else SCORING_VERSION


@contextmanager
def requirement_context_release():
    """Explicit release integration/recomputation scope; never inferred from UI/env.

    Existing workflow actions supply their own authoritative inputs. This scope
    changes neither input ownership nor persistence decisions made by callers.
    """
    with requirement_context_correction():
        token = RELEASE.set(True)
        try:
            yield
        finally:
            RELEASE.reset(token)


@contextmanager
def requirement_context_correction():
    """Explicit developer/release validation; no production activation switch."""
    from . import coordinated_runtime as runtime
    from .jd_metadata_policy import ACTIVE as metadata
    if (RELEASE.get() or runtime.CONTEXT.get() is not None or runtime.ELIGIBLE_WEAK_FALLBACK.get()
            or runtime.APPROVED_ALIAS_SURFACE.get() is not None or metadata.get() is not None):
        raise ValueError('Validate the context correction independently of other previews')
    token = ACTIVE.set(True)
    try:
        yield
    finally:
        ACTIVE.reset(token)


def supporting_trait(text):
    return enabled() and bool(re.fullmatch(
        r'ability to (?:learn (?:quickly|rapidly|fast)|quickly learn)', text, re.I))


def semantic_correction(surface, *, importance='', parent_text=''):
    """Return an exclusion only for an independently complete context statement.

    Explicit hard qualifications and mixed/compound obligations fail closed.
    No decision is inherited from a neighbouring sentence or inferred role title.
    """
    if not enabled():
        return None
    text = surface.strip(' .').replace('\u200b', '')
    hard = importance in ('required', 'deal_breaker') or re.search(
        r'\b(?:must|required|minimum|essential|mandatory|prerequisite)\b', text, re.I)
    if hard:
        return None
    # A separate action in a coordinated sentence must not disappear with a
    # learning preamble. Retain uncertain compounds for native scope handling.
    mixed = re.search(
        r'(?:\b(?:and|or|but|also|then|as well as)\s+(?:(?:you|the candidate)\s+(?:will|must)\s+)?'
        r'(?:design|develop|build|implement|maintain|manage|test|lead|operate)\b)|[;]',
        parent_text or text, re.I)
    if mixed:
        return None
    if re.match(r'^(?:(?:you|the candidate) will )?gain hands-on experience\b', text, re.I):
        return 'training_outcome', 'training_outcome_future_learning'
    value = re.fullmatch(r'public service spirit(?::\s*(.+))?', text, re.I)
    explanation = value.group(1) if value else None
    if value and (not explanation or (
        re.match(r'^(?:(?:you|we) (?:care|value|believe)\b|(?:a )?commitment to\b)', explanation, re.I)
        and not re.search(r'\b(?:experience|knowledge|proficiency|expertise|will|should)\b|ability to|skills? in', explanation, re.I)
    )):
        return 'values_context', 'non_prerequisite_public_service_value'
    if re.fullmatch(
        r'(?:you will )?plan and guide (?:the professional growth of (?:your|the) team|'
        r'your team[’\x27]s professional growth)(?:,? in both general and technical areas)?',
        text, re.I,
    ):
        return 'role_context', 'non_prerequisite_people_development_duty'
    return None


def stamp_analysis(analysis):
    if not enabled():
        return analysis
    if analysis['scoring_version'] != 'stable-evidence-v1.17-phase6d21':
        raise ValueError('Context correction requires the unmodified published scorer base')
    identity = RELEASE_SCORING_VERSION if release_enabled() else SCORING_IDENTITY
    analysis.update(base_scoring_version=analysis['scoring_version'],
                    scoring_version=identity,
                    requirement_context_policy_version=POLICY_VERSION)
    if not release_enabled():
        analysis.update(development_preview_only=True, preview_namespace=POLICY_VERSION)
    analysis['input_fingerprint'] = hashlib.sha256(json.dumps({
        'base': analysis['input_fingerprint'], 'policy': POLICY_VERSION,
        'scoring_identity': identity,
    }, sort_keys=True).encode()).hexdigest()
    return preserve_unavailable_score(analysis, analysis['canonical_requirements'])


def preserve_unavailable_score(score, requirements):
    """Used by native aggregation, including subsequent Phase 8 reconciliation."""
    if enabled() and not any(r.get('score_eligible', True) for r in requirements):
        for key in ('deterministic_alignment_score', 'alignment_band',
                    'required_core_coverage_score', 'preferred_coverage_score', 'evidence_strength_score'):
            score[key] = None
        score.update(score_publication_status='UNAVAILABLE_NO_SCORING_REQUIREMENTS',
                     score_interpretation='No scoring requirements remain; alignment is unavailable.')
    return score


def is_context_only_release(analysis):
    """Empty geometry is admissible only with retained non-scoring source receipts."""
    debug = analysis.get('canonicalisation_debug') or {}
    exclusions = list(debug.get('filtered_non_requirement_rows') or [])
    exclusions += (debug.get('decomposition') or {}).get('unheaded_raw_exclusions') or []
    return (analysis.get('scoring_version') == RELEASE_SCORING_VERSION
            and analysis.get('requirement_context_policy_version') == POLICY_VERSION
            and analysis.get('canonical_requirements') == []
            and analysis.get('score_publication_status') == 'UNAVAILABLE_NO_SCORING_REQUIREMENTS'
            and all(analysis.get(k) is None for k in (
                'deterministic_alignment_score', 'required_core_coverage_score',
                'preferred_coverage_score', 'evidence_strength_score', 'alignment_band'))
            and bool(exclusions)
            and all(r.get('score_eligible') is False or r.get('reason') == 'explicit_non_scoring_section'
                    for r in exclusions))
