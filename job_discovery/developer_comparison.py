"""Synthetic-only main-app boundary. No application loaders, saves or ranking."""
from copy import deepcopy
import json
import os

from job_discovery import coordinated_preview as preview
from job_discovery.coordinated_sources import fingerprint
from scripts import coordinated_job_match_preview_inputs as fixtures

GATE = 'JOB_AI_DEVELOPER_COMPARISON'
PAGE = 'Developer Diagnostics'
STATE = 'developer_job_match_ui_v1_result'
SCHEMA = 'developer-job-match-ui-v1'


def enabled():
    return os.environ.get(GATE, '') == '1'


def selection_identity(case_id):
    """Hash bytes, without extraction, normalization, or scoring on UI reruns."""
    paths = [fixtures.FIXTURE, preview.ROOT/'tests/fixtures/per_jd_scoring_audit.json',
             preview.ROOT/'tests/fixtures/coordinated_action_ownership_oracle_v1.json',
             preview.ROOT/'scripts/coordinated_acceptance.py',
             preview.ROOT/'scripts/coordinated_job_match_preview_inputs.py']
    return fingerprint({'schema': SCHEMA, 'case': case_id, 'source': preview.source_revision(),
                        'fixtures': [fingerprint(p.read_text(encoding='utf-8')) for p in paths]})


def evaluate(case_id, *, session_enabled=False):
    if not enabled() or session_enabled is not True:
        raise ValueError('Developer comparison is OFF')
    if case_id not in {c['id'] for c in fixtures.synthetic_cases()}:
        raise ValueError('Unknown synthetic example')
    identity = selection_identity(case_id)
    # The existing fixture helper memoizes parsed parents; refresh only on Run.
    fixtures.parents.cache_clear()
    inputs = fixtures.preview_inputs(case_id)
    if len(json.dumps(inputs)) > 250_000:
        raise ValueError('Synthetic comparison exceeds the input bound')
    request = preview.prepare_comparison(**deepcopy(inputs))
    comparison = preview.run_comparison(request, developer_enabled=True)
    from analysis_stability import jd_metadata_policy as v22, jd_metadata_v123 as v23
    metadata = {v22.SCORER_VERSION: v22.classify(request.raw_jd_text),
                v23.SCORER_VERSION: v23.classify(request.raw_jd_text)}
    if selection_identity(case_id) != identity:
        raise ValueError('Source changed during evaluation; run again')
    return {'identity': identity, 'case_id': case_id, 'comparison': comparison,
            'metadata': metadata}


def require_current(result, case_id):
    if result['case_id'] != case_id or result['identity'] != selection_identity(case_id):
        raise ValueError('Inputs or implementation changed; explicitly run again')
    return result


def requirement_rows(comparison):
    """Only exact canonical IDs align. Changed decomposition is not a text join."""
    sides = [{r.requirement_id: r for r in view.requirements}
             for view in (comparison.published, comparison.gated)]
    rows = []
    for rid in dict.fromkeys([*sides[0], *sides[1]]):
        before, after = (side.get(rid) for side in sides)
        reason = ('Different requirement geometry; no numeric row delta' if not before or not after
                  else 'Label/allocation differs' if (before.label, before.allocation) != (after.label, after.allocation)
                  else 'Same label/allocation; inspect source receipts')
        row = {'Requirement ID': rid, 'Requirement': (after or before).text, 'Difference': reason}
        for name, value in (('Published', before), ('Experimental', after)):
            row.update({name: value.label.value if value else 'Unavailable',
                        name+' allocation': value.allocation if value else None,
                        name+' credit': value.contribution if value else None,
                        name+' disposition': value.disposition if value else 'Unavailable',
                        name+' source': ', '.join(str(e.get('source', 'Unavailable')) for e in value.evidence) if value else 'Unavailable'})
        rows.append(row)
    return rows


def diagnostic_export(result, case_id, *, include_synthetic_text=False):
    """Allowlist only: no raw analyses, session dictionaries, paths or environment."""
    require_current(result, case_id)
    comparison = result['comparison']
    # Validate the retained numeric/null model before any export.
    from job_discovery.coordinated_preview_model import export_comparison
    export_comparison(comparison)
    rows = requirement_rows(comparison)
    if not include_synthetic_text:
        rows = [{k: v for k, v in r.items() if k != 'Requirement'} for r in rows]
    metadata = {version: [{k: r[k] for k in
                 ('source', 'classification', 'reason', 'admitted', 'raw_span') if k in r}
                 | ({'raw_text': r['raw_text']} if include_synthetic_text else {})
                 for r in receipt['lines']] for version, receipt in result['metadata'].items()}
    payload = {'schema_version': SCHEMA, 'development_preview_only': True,
        'ranking_eligible': False, 'persistence_eligible': False,
        'input_kind': 'SYNTHETIC_LIBRARY_WITH_FROZEN_JD', 'case_id': case_id,
        'input_fingerprint': comparison.identity, 'implementation_fingerprint': result['identity'],
        'authority': comparison.authority, 'currentness': 'FRESH_SYNTHETIC_EVALUATION',
        'published': comparison.published.summary(), 'experimental': comparison.gated.summary(),
        'knowledge': {k: comparison.gated_analysis.get(k) for k in
                      ('capability_taxonomy_version', 'technology_registry_version')},
        'requirements': rows,
        'experimental_evidence': [{'requirement_id': r.requirement_id,
            'native_label': r.native_label, 'disposition': r.disposition,
            'supported_actions': list(r.supported_actions), 'missing_actions': list(r.missing_actions),
            'technical_scope': r.technical_scope, 'conflict_quarantined': bool((r.conflict or {}).get('quarantine')),
            'sources': [{k: e.get(k) for k in ('source', 'evidence_id', 'section')} for e in r.evidence]}
            for r in comparison.gated.requirements],
        'metadata_classifications': metadata,
        'metadata_role': 'CLASSIFICATION_ONLY_NO_GO_NOT_ADDITIONAL_SCORES',
        'source_text_included': include_synthetic_text, 'errors': []}
    return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
