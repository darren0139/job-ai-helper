"""Distinct historical receipt replay and current synthetic accounting inputs.

The historical context is a presentation/arithmetic test adapter, never a
currentness certificate or a re-execution of the old evidence evaluator.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from tests.governed_review_fixtures import isolated_taxonomy

HISTORICAL_FIXTURE = Path(__file__).with_name('fixtures')/'per_jd_scoring_audit.json'
HISTORICAL_SHA256 = 'a994e4ad7dd7f71e42e2f2c1421a13f4cbd554d36bf2310cec4cd8f22d35e93f'
HISTORICAL_SCORER = 'stable-evidence-v1.16-phase6d20'


def load_historical_bundle():
    raw = HISTORICAL_FIXTURE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != HISTORICAL_SHA256:
        raise ValueError('Historical Per-JD receipt bytes changed; review provenance')
    return json.loads(raw)


@contextmanager
def historical_accounting_context(bundle):
    """Replay frozen accounting under its declared, test-only old environment.

    Do not use around current-source tests, cache/publication/persistence, or
    native evidence scoring. Original result versions and every row stay intact.
    The production currentness guard is tested separately without this adapter.
    """
    manifest = bundle['snapshot']['manifest']
    if (manifest['scoring_version'] != HISTORICAL_SCORER
            or manifest['taxonomy_version'] != 'phase6d-capability-taxonomy-v1.5'
            or any(j['baseline_stable_analysis']['scoring_version'] != HISTORICAL_SCORER
                   for j in bundle['snapshot']['audit']['corpus']['jobs'])):
        raise ValueError('Not the historical v1.16 accounting contract')
    versions = {key: manifest[key] for key in (
        'scoring_version', 'taxonomy_version', 'technology_registry_version',
        'match_version', 'match_contract_version')}
    # Same explicit historical-presentation pattern as post-publication tests.
    # Only the consumer's version lookup is scoped; scorer constants and source
    # algorithms are never patched, and no old analysis is relabelled current.
    with isolated_taxonomy(), patch('job_discovery.matching.current_match_versions',
                                   side_effect=lambda: deepcopy(versions)):
        yield


def current_live_analysis(resolved, other, identities=0):
    """Run today's actual default-OFF scorer on authored synthetic JD inputs.

    This is a taxonomy-count control, not a prediction of a historical job score.
    No historical rows, candidate evidence or expected results are copied.
    """
    from analysis_stability.stable_evidence_scoring import build_stable_analysis

    requirements = [f'Perform regression testing for module {i}' for i in range(resolved)]
    requirements += [f'Perform quuxscope obligation {i}' for i in range(other)]
    # Current registry recognizes C# identity; identity alone is not capability.
    if identities:
        if identities != 1:
            raise ValueError('This control specifies exactly one identity row')
        requirements += ['C#']
    raw = 'Requirements:\n' + '\n'.join('- '+text for text in requirements)
    stable = build_stable_analysis(
        jd_profile={'required_skills': requirements, 'preferred_skills': [],
                    'responsibilities': [], 'soft_skills': [], 'tools_technologies': []},
        keyword_match={}, raw_jd_text=raw, raw_resume_text='',
        resume_profile={'projects': [], 'experience': [], 'skills': []},
        retrieval_mode_override='off')
    return raw, stable
