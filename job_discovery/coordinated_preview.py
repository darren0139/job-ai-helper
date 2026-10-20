"""Explicit, nonpersisting developer comparison; no production workflow imports."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from analysis_stability import stable_evidence_scoring as native
from analysis_stability import coordinated_integration as gated
from job_discovery.coordinated_sources import (
    build_library_projection, fingerprint, PROJECTED_SCORER_VERSION, PROJECTION_VERSION,
    ALIAS_POLICY_VERSION, LIBRARY_AUTHORITY,
)
from job_discovery.coordinated_preview_model import AnalysisView, analysis_view, MODEL_VERSION

PREVIEW_NAMESPACE = 'developer-job-match-comparison-v1'
PREVIEW_SESSION_KEY = 'developer_coordinated_job_match_comparison_v1'
ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ComparisonRequest:
    raw_jd_text: str
    jd_profile: dict
    projection: dict
    identity: str


@dataclass(frozen=True)
class Comparison:
    namespace: str
    authority: str
    identity: str
    published: AnalysisView
    gated: AnalysisView
    published_analysis: dict
    gated_analysis: dict


def source_revision():
    """Invalidate in-memory receipts on implementation, knowledge or policy edits."""
    paths = []
    for folder in ('analysis_stability', 'job_discovery', 'tailoring', 'taxonomy_discovery'):
        paths.extend((ROOT/folder).glob('*.py'))
    paths.extend((ROOT/'taxonomy').glob('*.json'))
    return fingerprint([(str(p.relative_to(ROOT)), fingerprint(p.read_text(encoding='utf-8')))
                        for p in sorted(paths)])


def prepare_comparison(*, raw_jd_text, evidence_items, jd_profile=None, jd_profile_extractor=None, raw_only_text=''):
    if not isinstance(raw_jd_text, str) or not raw_jd_text.strip():
        raise ValueError('The original raw JD is required')
    if jd_profile is None:
        if jd_profile_extractor is None:
            raise ValueError('Supply frozen JD extraction or an explicitly injected offline extractor')
        jd_profile = jd_profile_extractor(raw_jd_text)
    if not isinstance(jd_profile, dict):
        raise ValueError('Frozen JD extraction must be an object')
    projection = build_library_projection(evidence_items, raw_only_text=raw_only_text)
    identity = fingerprint({'namespace': PREVIEW_NAMESPACE, 'view': MODEL_VERSION,
        'authority': LIBRARY_AUTHORITY, 'source_projection': PROJECTION_VERSION,
        'alias_policy': ALIAS_POLICY_VERSION, 'gated_version': PROJECTED_SCORER_VERSION,
        'native_version': native.SCORING_VERSION, 'policies': gated.IDENTITIES,
        'source_revision': source_revision(), 'projection': projection,
        'jd_profile': jd_profile, 'original_raw_jd': raw_jd_text})
    return ComparisonRequest(raw_jd_text, deepcopy(jd_profile), projection, identity)


def run_comparison(request, *, developer_enabled=False):
    if not developer_enabled:
        raise ValueError('Developer comparison is OFF; explicit invocation required')
    # Reprepare to reject forged/mutated inputs and stale code/policy identities.
    verified = prepare_comparison(raw_jd_text=request.raw_jd_text, jd_profile=request.jd_profile,
        evidence_items=request.projection['evidence_items'], raw_only_text=request.projection['raw_only_text'])
    if verified != request:
        raise ValueError('Preview input identity is stale or its source receipts were changed')
    context = request.projection['context']
    kwargs = dict(jd_profile=deepcopy(request.jd_profile), keyword_match={},
        raw_jd_text=request.raw_jd_text, resume_profile=deepcopy(context['resume_profile']),
        raw_resume_text=context['raw_resume_text'], retrieval_mode_override='off')
    canonical = native.canonicalise_requirements(request.jd_profile, raw_jd_text=request.raw_jd_text)
    kwargs['keyword_match'] = native.build_deterministic_keyword_match(
        requirements=canonical['requirements'], acronym_map=canonical['acronym_map'],
        resume_profile=context['resume_profile'], raw_resume_text=context['raw_resume_text'])
    published = native.build_stable_analysis(**kwargs, coordinated_actions_enabled=False)
    corrected = gated.build_coordinated_analysis(**kwargs, source_projection=request.projection)
    return Comparison(PREVIEW_NAMESPACE, LIBRARY_AUTHORITY, request.identity,
                      analysis_view(published), analysis_view(corrected), published, corrected)


def retained_comparison(result, request):
    """Selection/filtering only reads this receipt; stale input never rebuilds it."""
    current = prepare_comparison(raw_jd_text=request.raw_jd_text, jd_profile=request.jd_profile,
        evidence_items=request.projection['evidence_items'], raw_only_text=request.projection['raw_only_text'])
    if (result.namespace != PREVIEW_NAMESPACE or result.identity != request.identity or current != request):
        raise ValueError('Preview is stale; explicitly run the comparison again')
    return result
